
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
@router.get("/")
def list_parcels(authorization:str=Header(None),survey_no:str="",subdivision:str="",village:str="",taluk:str="",district:str="",risk_category:str="",project_id:str="",limit:int=100,offset:int=0):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 q="SELECT * FROM parcels WHERE 1=1"; args=[]
 for col,val in [("survey_no",survey_no),("subdivision",subdivision),("village",village),("taluk",taluk),("district",district),("risk_category",risk_category),("project_id",project_id)]:
  if val: q+=f" AND {col} LIKE ?"; args.append("%"+val+"%")
 q+=" ORDER BY id DESC LIMIT ? OFFSET ?"; args += [min(max(limit,1),1000),max(offset,0)]
 c=conn(); rows=[dict(r) for r in c.execute(q,args).fetchall()]; c.close(); return {"items":rows,"count":len(rows),"limit":limit,"offset":offset}
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
