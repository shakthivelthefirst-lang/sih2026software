
from fastapi import APIRouter,HTTPException,Header,UploadFile,File
from backend.core import conn,current_user,audit,UPLOADS
from backend.services.ml_service import predict,FEATURES,train_new
from backend.services.risk_service import stage_risk
from backend.services.explain_service import explain
from backend.services.validation_service import validate_land_record
import uuid, hashlib, json, os
router=APIRouter()
@router.post("/validate")
def validate(record:dict,authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 return validate_land_record(record)
def _features(p):
 d={k:p.get(k,0) for k in FEATURES}; d["project_type"]=p.get("project_type") or "Road"; d["land_required"]=p.get("land_required",p.get("area",0)); return d
def _build_base_parcel_conditions(
    u: dict,
    q: str = "",
    survey_no: str = "",
    subdivision: str = "",
    village: str = "",
    taluk: str = "",
    district: str = "",
    project_id: str = "",
    assigned_to_me: bool = False
):
    conditions = ["1=1"]
    args = []

    # 1. Role-based Server-Side Boundaries
    role = u.get("role", "")
    user_district = u.get("district")
    user_taluk = u.get("taluk")

    if role == "district_authority":
        dist = user_district or "Coimbatore"
        conditions.append("LOWER(p.district) = LOWER(?)")
        args.append(dist)
    elif role == "field_officer":
        tlk = user_taluk or "Sulur"
        conditions.append("(LOWER(p.taluk) = LOWER(?) OR LOWER(p.village) = LOWER(?))")
        args.extend([tlk, tlk])
    elif role in ("state_authority", "authority", "admin"):
        if district and district.strip() and district.strip().lower() not in ("all", "all districts"):
            conditions.append("LOWER(p.district) = LOWER(?)")
            args.append(district.strip())
    else:
        if user_district:
            conditions.append("LOWER(p.district) = LOWER(?)")
            args.append(user_district)

    # 2. General text search `q`
    if q and q.strip():
        term = f"%{q.strip()}%"
        conditions.append("""(
            p.survey_no LIKE ? OR 
            p.survey_number LIKE ? OR 
            p.record_id LIKE ? OR 
            CAST(p.id AS TEXT) LIKE ? OR 
            p.owner_name LIKE ? OR 
            p.owner_reference LIKE ? OR 
            p.project_id LIKE ? OR 
            p.village LIKE ? OR 
            p.taluk LIKE ?
        )""")
        args.extend([term, term, term, term, term, term, term, term, term])

    # 3. Parametric filters
    if survey_no and survey_no.strip():
        conditions.append("(p.survey_no LIKE ? OR p.survey_number LIKE ?)")
        args.extend([f"%{survey_no.strip()}%", f"%{survey_no.strip()}%"])
    if subdivision and subdivision.strip():
        conditions.append("p.subdivision LIKE ?")
        args.append(f"%{subdivision.strip()}%")
    if village and village.strip() and village.strip().lower() not in ("all", "all villages"):
        conditions.append("LOWER(p.village) = LOWER(?)")
        args.append(village.strip())
    if taluk and taluk.strip() and taluk.strip().lower() not in ("all", "all taluks") and role != "field_officer":
        conditions.append("LOWER(p.taluk) = LOWER(?)")
        args.append(taluk.strip())
    if project_id and project_id.strip() and project_id.strip().lower() not in ("all", "all projects"):
        conditions.append("LOWER(p.project_id) = LOWER(?)")
        args.append(project_id.strip())

    # Assigned to Me filter (Field Officer)
    if assigned_to_me and u.get("email"):
        conditions.append("fa.officer_email = ?")
        args.append(u["email"])

    return conditions, args


def _get_parcel_stats_dict(c, base_conditions, base_args):
    base_where_clause = " AND ".join(base_conditions)
    stats_sql = f"""
    SELECT 
        COUNT(*) AS "all",
        COUNT(*) FILTER (WHERE UPPER(p.stage) = 'ACQUIRED' OR p.is_acquired = true OR p.is_acquired = 1 OR UPPER(p.acquisition_status) = 'ACQUIRED') AS acquired,
        COUNT(*) FILTER (WHERE (UPPER(p.stage) != 'ACQUIRED' OR p.stage IS NULL) AND (p.is_acquired = false OR p.is_acquired = 0 OR p.is_acquired IS NULL) AND (UPPER(p.acquisition_status) != 'ACQUIRED' OR p.acquisition_status IS NULL)) AS pending,
        COUNT(*) FILTER (WHERE UPPER(COALESCE(fa.status, '')) = 'DISPUTED' OR UPPER(COALESCE(fa.status, '')) LIKE '%DISPUT%' OR p.legal_disputes > 0 OR UPPER(p.acquisition_status) LIKE '%DISPUT%') AS disputed,
        COUNT(*) FILTER (WHERE UPPER(COALESCE(fa.status, 'PENDING')) LIKE '%PENDING%' OR fa.status IS NULL) AS verification_pending
    FROM parcels p
    LEFT JOIN field_assignments fa ON fa.parcel_id = p.id
    WHERE {base_where_clause}
    """
    row = c.execute(stats_sql, base_args).fetchone()
    return {
        "all": int(row["all"] or 0) if row else 0,
        "acquired": int(row["acquired"] or 0) if row else 0,
        "pending": int(row["pending"] or 0) if row else 0,
        "disputed": int(row["disputed"] or 0) if row else 0,
        "verification_pending": int(row["verification_pending"] or 0) if row else 0
    }


@router.get("/")
def list_parcels(
    authorization: str = Header(None),
    q: str = "",
    survey_no: str = "",
    subdivision: str = "",
    village: str = "",
    taluk: str = "",
    district: str = "",
    project_id: str = "",
    acquisition_status: str = "",
    stage: str = "",
    verification_status: str = "",
    risk_level: str = "",
    risk_category: str = "",
    assigned_to_me: bool = False,
    limit: int = 100,
    offset: int = 0
):
    u = current_user(authorization)
    if not u: raise HTTPException(401, "Authentication required")

    base_conditions, base_args = _build_base_parcel_conditions(
        u=u, q=q, survey_no=survey_no, subdivision=subdivision,
        village=village, taluk=taluk, district=district, project_id=project_id,
        assigned_to_me=assigned_to_me
    )

    filtered_conditions = list(base_conditions)
    filtered_args = list(base_args)

    # 4. Acquisition Status / Stage filter (applied to table items only)
    acq_filter = (acquisition_status or stage).strip().upper()
    if acq_filter and acq_filter not in ("ALL", "ALL STAGES", "ALL STATUSES"):
        if acq_filter == "ACQUIRED":
            filtered_conditions.append("(p.is_acquired = 1 OR p.is_acquired = true OR UPPER(p.acquisition_status) = 'ACQUIRED' OR UPPER(p.stage) = 'ACQUIRED')")
        elif acq_filter in ("NOT ACQUIRED", "PENDING"):
            filtered_conditions.append("((p.is_acquired = 0 OR p.is_acquired = false OR p.is_acquired IS NULL) AND (UPPER(p.stage) != 'ACQUIRED' OR p.stage IS NULL) AND (UPPER(p.acquisition_status) != 'ACQUIRED' OR p.acquisition_status IS NULL))")
        elif acq_filter == "DISPUTED":
            filtered_conditions.append("(p.legal_disputes > 0 OR UPPER(p.acquisition_status) LIKE '%DISPUTE%' OR UPPER(p.stage) LIKE '%DISPUTE%' OR UPPER(p.stage) LIKE '%OBJECTION%')")
        else:
            filtered_conditions.append("(UPPER(p.acquisition_status) LIKE ? OR UPPER(p.stage) LIKE ?)")
            filtered_args.extend([f"%{acq_filter}%", f"%{acq_filter}%"])

    # 5. Verification status filter (applied to table items only)
    v_filter = verification_status.strip().upper()
    if v_filter and v_filter not in ("ALL", "ALL STATUSES"):
        if v_filter == "VERIFIED":
            filtered_conditions.append("fa.status = 'Verified'")
        elif v_filter in ("PENDING", "PENDING INSPECTION", "PENDING_INSPECTION", "VERIFICATION PENDING"):
            filtered_conditions.append("(fa.status IS NULL OR fa.status = 'Pending Verification' OR fa.status = 'Pending' OR UPPER(fa.status) LIKE '%PENDING%')")
        elif v_filter == "DISPUTED":
            filtered_conditions.append("(fa.status = 'Disputed' OR p.legal_disputes > 0)")
        elif v_filter == "REJECTED":
            filtered_conditions.append("fa.status = 'Rejected'")
        else:
            filtered_conditions.append("UPPER(fa.status) LIKE ?")
            filtered_args.append(f"%{v_filter}%")

    # 6. Risk level / SLA risk filter (applied to table items only)
    risk = (risk_level or risk_category).strip().upper()
    if risk and risk not in ("ALL", "ALL RISKS"):
        if risk in ("SLA_BREACH", "BREACHED"):
            filtered_conditions.append("(p.delay_probability > 0.7 OR p.delay_days > 30)")
        elif risk in ("AT_RISK", "AT RISK"):
            filtered_conditions.append("(UPPER(p.risk_category) IN ('HIGH', 'CRITICAL') OR p.risk_score > 60)")
        elif risk == "NORMAL":
            filtered_conditions.append("(UPPER(p.risk_category) IN ('LOW', 'MEDIUM') OR p.risk_score <= 60)")
        else:
            filtered_conditions.append("UPPER(p.risk_category) = ?")
            filtered_args.append(risk)

    where_clause = " AND ".join(filtered_conditions)

    sql = f"""
    SELECT 
        p.id AS id,
        p.id AS parcel_id,
        p.record_id,
        COALESCE(p.survey_number, p.survey_no) AS survey_no,
        COALESCE(p.survey_number, p.survey_no) AS survey_number,
        p.subdivision,
        COALESCE(p.locality, p.revenue_village, p.village) AS specific_area,
        p.village,
        p.taluk,
        p.district,
        p.area,
        p.area_unit,
        p.classification,
        p.land_use,
        p.project_id,
        COALESCE(p.owner_name, p.owner_reference, 'Unknown') AS owner_name,
        COALESCE(p.owner_reference, p.owner_name, '') AS owner_reference,
        COALESCE(p.stage, p.acquisition_status, 'Proposal') AS stage,
        COALESCE(p.acquisition_status, p.stage, 'Proposal') AS acquisition_status,
        COALESCE(p.is_acquired, 0) AS is_acquired,
        COALESCE(p.risk_category, 'LOW') AS risk_category,
        COALESCE(p.risk_score, 0) AS risk_score,
        COALESCE(p.delay_probability, 0) AS delay_probability,
        p.latitude,
        p.longitude,
        ST_AsGeoJSON(p.geom) AS geometry,
        COALESCE(fa.status, 'Pending Verification') AS verification_status,
        fa.officer_email AS assigned_officer,
        fa.id AS assignment_id
    FROM parcels p
    LEFT JOIN field_assignments fa ON fa.parcel_id = p.id
    WHERE {where_clause}
    ORDER BY p.id DESC
    LIMIT ? OFFSET ?
    """
    
    count_sql = f"""
    SELECT COUNT(1) AS total_count
    FROM parcels p
    LEFT JOIN field_assignments fa ON fa.parcel_id = p.id
    WHERE {where_clause}
    """

    c = conn()
    total_count = c.execute(count_sql, filtered_args).fetchone()["total_count"]
    stats = _get_parcel_stats_dict(c, base_conditions, base_args)
    
    query_args = filtered_args + [min(max(limit, 1), 1000), max(offset, 0)]
    rows = []
    for r in c.execute(sql, query_args).fetchall():
        d = dict(r)
        if d.get("geometry") and isinstance(d["geometry"], str):
            try: d["geometry"] = json.loads(d["geometry"])
            except: pass
        rows.append(d)
    c.close()

    role = u.get("role", "")
    user_district = u.get("district")
    user_taluk = u.get("taluk")

    return {
        "items": rows,
        "count": len(rows),
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "stats": stats,
        "scope": {
            "role": role,
            "district": user_district if role == "district_authority" else district or "All",
            "taluk": user_taluk if role == "field_officer" else taluk or "All"
        }
    }


@router.get("/stats")
def get_parcel_stats(
    authorization: str = Header(None),
    q: str = "",
    survey_no: str = "",
    subdivision: str = "",
    village: str = "",
    taluk: str = "",
    district: str = "",
    project_id: str = "",
    assigned_to_me: bool = False
):
    u = current_user(authorization)
    if not u: raise HTTPException(401, "Authentication required")

    base_conditions, base_args = _build_base_parcel_conditions(
        u=u, q=q, survey_no=survey_no, subdivision=subdivision,
        village=village, taluk=taluk, district=district, project_id=project_id,
        assigned_to_me=assigned_to_me
    )
    c = conn()
    stats = _get_parcel_stats_dict(c, base_conditions, base_args)
    c.close()
    return {
        "stats": stats,
        **stats
    }


@router.get("/{parcel_id}")
def get_parcel(parcel_id:int,authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 c=conn(); p=c.execute("SELECT * FROM parcels WHERE id=?",(parcel_id,)).fetchone()
 if not p: c.close(); raise HTTPException(404,"Parcel not found")
 d=dict(p); d["stage_risk"]=stage_risk(d); d["explanation"]=explain(d); d["documents"]=[dict(x) for x in c.execute("SELECT * FROM documents WHERE parcel_id=?",(parcel_id,)).fetchall()]; d["alerts"]=[dict(x) for x in c.execute("SELECT * FROM alerts WHERE parcel_id=? ORDER BY id DESC",(parcel_id,)).fetchall()]; d["audit"]=[dict(x) for x in c.execute("SELECT * FROM audit_logs WHERE entity_id=? ORDER BY id DESC LIMIT 50",(str(parcel_id),)).fetchall()]; c.close(); return d
@router.post("/")
def add(parcel:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u["role"] not in ("authority","admin","acquisition_officer"): raise HTTPException(403,"Insufficient permissions")
 required=["record_id","survey_no","subdivision","village","taluk","district","area","classification","project_id","latitude","longitude","training_label"]
 missing=[x for x in required if parcel.get(x) in (None,"")]
 if missing: raise HTTPException(400,{"missing_fields":missing})
 valid=validate_land_record(parcel)
 if not valid["valid"]: raise HTTPException(400,valid)
 c=conn()
 if not c.execute("SELECT 1 FROM projects WHERE project_id=?",(parcel["project_id"],)).fetchone(): c.close(); raise HTTPException(400,"Project does not exist")
 if c.execute("SELECT 1 FROM parcels WHERE survey_no=? AND subdivision=? AND village=? AND taluk=? AND district=?",(parcel["survey_no"],parcel["subdivision"],parcel["village"],parcel["taluk"],parcel["district"])).fetchone(): c.close(); raise HTTPException(409,"Duplicate survey/subdivision parcel")
 f=_features(parcel)
 try: pred=predict(f)
 except Exception as e: c.close(); raise HTTPException(503,"ML prediction unavailable: "+str(e))
 c.execute("""INSERT INTO parcels(record_id,survey_no,subdivision,village,taluk,district,owner_reference,case_reference,area,area_unit,classification,land_use,project_id,acquisition_status,latitude,longitude,training_label,project_type,affected_families,legal_disputes,compensation_pending,approval_pending,documentation_pending,rehabilitation_pending,notification_pending,award_pending,possession_pending,stakeholder_responsiveness,environmental_risk,weather_risk,historical_delay,delay_days,remarks,validation_status,risk_category,risk_probability,risk_score,delay_probability,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
 [parcel["record_id"],parcel["survey_no"],parcel["subdivision"],parcel["village"],parcel["taluk"],parcel["district"],parcel.get("owner_reference",""),parcel.get("case_reference",""),float(parcel["area"]),parcel.get("area_unit","acres"),parcel["classification"],parcel.get("land_use",""),parcel["project_id"],parcel.get("acquisition_status","Proposal"),float(parcel["latitude"]),float(parcel["longitude"]),parcel["training_label"].upper(),f["project_type"],int(parcel.get("affected_families",0)),*[int(parcel.get(k,0) or 0) for k in ["legal_disputes","compensation_pending","approval_pending","documentation_pending","rehabilitation_pending","notification_pending","award_pending","possession_pending"]],float(parcel.get("stakeholder_responsiveness",80)),float(parcel.get("environmental_risk",20)),float(parcel.get("weather_risk",20)),float(parcel.get("historical_delay",0)),float(parcel.get("delay_days",0)),parcel.get("remarks",""),"VALID",pred["risk_category"],pred["risk_probability"],pred["risk_score"],pred["risk_probability"],u["email"]])
 pid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
 # Permanent supervised-learning record in DB
 c.execute("INSERT INTO training_examples(parcel_id,project_id,features_json,label,delay_days,verified_by) VALUES(?,?,?,?,?,?)",(pid,parcel["project_id"],json.dumps(f),parcel["training_label"].upper(),parcel.get("delay_days",0),u["email"]))
 c.execute("INSERT INTO risk_predictions(parcel_id,project_id,risk_score,risk_category,delay_probability,model_version) VALUES(?,?,?,?,?,?)",(pid,parcel["project_id"],pred["risk_score"],pred["risk_category"],pred["risk_probability"],"active"))
 c.commit(); c.close()
 audit(u["email"],"ADD_PARCEL","parcel",pid,new_value=json.dumps({"label":parcel["training_label"].upper()}))
 # Dataset is source-of-truth CSV plus persistent DB example. Retraining is explicit to avoid blocking requests.
 return {"message":"Parcel saved and verified training example persisted","parcel_id":pid,"prediction":pred,"stages":stage_risk(f),"explanation":explain(f),"training_example_persisted":True}
@router.put("/{parcel_id}")
def update(parcel_id:int,payload:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u["role"] not in ("authority","admin","acquisition_officer","field_officer"): raise HTTPException(403,"Insufficient permissions")
 c=conn(); old=c.execute("SELECT * FROM parcels WHERE id=?",(parcel_id,)).fetchone()
 if not old: c.close(); raise HTTPException(404,"Parcel not found")
 allowed=["acquisition_status","remarks","compensation_pending","approval_pending","documentation_pending","rehabilitation_pending","notification_pending","award_pending","possession_pending","legal_disputes","stakeholder_responsiveness","environmental_risk","weather_risk","delay_days","training_label"]
 sets=[]; args=[]
 for k in allowed:
  if k in payload: sets.append(k+"=?"); args.append(payload[k])
 if not sets: c.close(); raise HTTPException(400,"No supported fields to update")
 sets.append("last_updated=CURRENT_TIMESTAMP"); args.append(parcel_id); c.execute("UPDATE parcels SET "+",".join(sets)+" WHERE id=?",args); c.commit(); c.close(); audit(u["email"],"UPDATE_PARCEL","parcel",parcel_id,new_value=json.dumps(payload)); return {"message":"Parcel updated"}
@router.post("/{parcel_id}/evidence")
def evidence(parcel_id:int,file:UploadFile=File(...),authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u["role"] not in ("authority","admin","acquisition_officer","field_officer"): raise HTTPException(403,"Insufficient permissions")
 ext=os.path.splitext(file.filename or "")[1].lower()
 if ext not in (".pdf",".png",".jpg",".jpeg",".tif",".tiff",".webp"): raise HTTPException(400,"Unsupported document type")
 data=file.file.read(10*1024*1024+1)
 if len(data)>10*1024*1024: raise HTTPException(413,"File exceeds 10 MB limit")
 c=conn(); row=c.execute("SELECT id,project_id FROM parcels WHERE id=?",(parcel_id,)).fetchone()
 if not row: c.close(); raise HTTPException(404,"Parcel not found")
 safe=uuid.uuid4().hex+ext; path=UPLOADS/safe; path.write_bytes(data); sha=hashlib.sha256(data).hexdigest(); did="DOC-"+uuid.uuid4().hex[:12].upper()
 c.execute("INSERT INTO documents(document_id,project_id,parcel_id,document_type,document_name,path,format,uploaded_by,sha256) VALUES(?,?,?,?,?,?,?,?,?)",(did,row["project_id"],parcel_id,"Evidence",file.filename,safe,ext[1:],u["email"],sha)); c.commit(); c.close(); audit(u["email"],"UPLOAD_DOCUMENT","parcel",parcel_id,new_value=file.filename); return {"message":"Document uploaded","document_id":did,"sha256":sha}
