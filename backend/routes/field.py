
from fastapi import APIRouter,Header,HTTPException,UploadFile,File
from backend.core import conn,current_user,audit,UPLOADS
import uuid
router=APIRouter()
@router.get("/officers")
def officers(authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u["role"] not in ("district_authority","authority","admin"): raise HTTPException(403,"Officer directory access required")
 c=conn(); rows=[dict(x) for x in c.execute("SELECT id,email,role FROM users WHERE role='field_officer' AND active=1 ORDER BY email").fetchall()]; c.close(); return rows
@router.post("/assign")
def assign(p:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u["role"] not in ("district_authority","authority","admin","acquisition_officer"): raise HTTPException(403,"Insufficient permissions")
 c=conn(); parcel=c.execute("SELECT id,project_id,survey_no,village,district FROM parcels WHERE id=?",(p.get("parcel_id"),)).fetchone(); officer=c.execute("SELECT email FROM users WHERE email=? AND role='field_officer' AND active=1",(p.get("officer_email"),)).fetchone()
 if not parcel: c.close(); raise HTTPException(404,"Parcel not found")
 if not officer: c.close(); raise HTTPException(404,"Field officer not found")
 if p.get("project_id") and parcel["project_id"]!=str(p["project_id"]): c.close(); raise HTTPException(400,"Parcel is not linked to the selected project")
 if c.execute("SELECT 1 FROM field_assignments WHERE parcel_id=? AND officer_email=?",(parcel["id"],officer["email"])).fetchone(): c.close(); raise HTTPException(409,"Parcel is already assigned to this field officer")
 c.execute("INSERT INTO field_assignments(parcel_id,officer_email,assigned_by,status) VALUES(?,?,?,?)",(parcel["id"],officer["email"],u["email"],"Pending Verification"))
 district_users=c.execute("SELECT email FROM users WHERE role='district_authority' AND active=1 ORDER BY id").fetchall(); district_email=next((r["email"] for r in district_users if (parcel["district"] or "").lower() in r["email"].lower()), district_users[0]["email"] if district_users else None)
 aid="ALT-"+uuid.uuid4().hex[:10].upper(); message=f"Parcel {parcel['id']} ({parcel['survey_no']}) assigned for field verification."; c.execute("INSERT INTO alerts(alert_id,project_id,parcel_id,type,severity,trigger,message,recommended_action,assigned_to,status) VALUES(?,?,?,?,?,?,?,?,?,?)",(aid,parcel["project_id"],parcel["id"],"New Parcels Assigned for Verification","INFO","District Officer",message,"Complete field verification",officer["email"],"Open")); c.commit(); c.close(); audit(u["email"],"ASSIGN_FIELD_PARCEL","parcel",p["parcel_id"],new_value=officer["email"]); return {"message":"Field officer assignment completed","parcel_id":parcel["id"],"project_id":parcel["project_id"],"officer_email":officer["email"],"assignment_status":"Pending Verification","alert_id":aid,"district_officer":district_email}
@router.get("/assigned")
def assigned(authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u["role"] not in ("field_officer","authority","admin"): raise HTTPException(403,"Field officer access required")
 c=conn(); rows=[dict(x) for x in c.execute("""
  SELECT a.id AS assignment_id, a.parcel_id AS parcel_id, a.officer_email,
         a.assigned_by, a.status AS assignment_status, a.created_at AS assigned_at,
         p.record_id, p.survey_no, p.subdivision, p.village, p.taluk, p.district,
         p.project_id, p.acquisition_status, v.id AS verification_id,
         v.status AS verification_status, v.created_at AS verified_at
  FROM field_assignments a
  JOIN parcels p ON p.id=a.parcel_id
  LEFT JOIN field_verifications v ON v.id=(
   SELECT MAX(id) FROM field_verifications WHERE parcel_id=a.parcel_id AND officer_email=a.officer_email
  )
  WHERE a.officer_email=? OR ? IN ('authority','admin')
  ORDER BY a.id DESC
 """,(u["email"],u["role"])).fetchall()]; c.close(); return rows
@router.post("/{parcel_id}/verify")
def verify(parcel_id:int,p:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u["role"]!="field_officer": raise HTTPException(403,"Field officer required")
 c=conn()
 assignment=c.execute("""SELECT a.id assignment_id,a.parcel_id,p.project_id,p.survey_no,p.district
  FROM field_assignments a JOIN parcels p ON p.id=a.parcel_id
  WHERE a.parcel_id=? AND a.officer_email=?""",(parcel_id,u["email"])).fetchone()
 if not assignment: c.close(); raise HTTPException(403,"Parcel is not assigned to this field officer")
 verification=c.execute("""SELECT id FROM field_verifications
  WHERE parcel_id=? AND officer_email=? ORDER BY id DESC LIMIT 1""",(parcel_id,u["email"])).fetchone()
 if verification:
  verification_id=verification["id"]
 else:
  cur=c.execute("INSERT INTO field_verifications(parcel_id,officer_email,gps_lat,gps_lon,status,remarks) VALUES(?,?,?,?,?,?)",(parcel_id,u["email"],p.get("gps_lat"),p.get("gps_lon"),"Verified",p.get("remarks","")))
  verification_id=cur.lastrowid
 c.execute("UPDATE field_assignments SET status='Verified' WHERE parcel_id=? AND officer_email=?",(parcel_id,u["email"]))
 district_users=c.execute("SELECT email FROM users WHERE role='district_authority' AND active=1 ORDER BY id").fetchall(); district_email=next((r["email"] for r in district_users if (assignment["district"] or "").lower() in r["email"].lower()), district_users[0]["email"] if district_users else None)
 alert=c.execute("""SELECT alert_id FROM alerts WHERE type='Field Verification Completed' AND parcel_id=? AND assigned_to=? ORDER BY id DESC LIMIT 1""",(parcel_id,district_email)).fetchone()
 if alert:
  alert_id=alert["alert_id"]
 else:
  alert_id="ALT-"+uuid.uuid4().hex[:10].upper()
  c.execute("""INSERT INTO alerts(alert_id,project_id,parcel_id,type,severity,trigger,message,recommended_action,assigned_to,status)
   VALUES(?,?,?,?,?,?,?,?,?,?)""",(alert_id,assignment["project_id"],parcel_id,"Field Verification Completed","INFO","Field Officer",f"Field verification completed for survey {assignment['survey_no']}.","Review verified field evidence",district_email,"Open"))
 c.commit(); c.close(); audit(u["email"],"FIELD_VERIFICATION_SUBMITTED","parcel",parcel_id)
 return {"message":"Field verification completed","assignment_id":assignment["assignment_id"],"parcel_id":parcel_id,"verification_id":verification_id,"assignment_status":"Verified","verification_status":"Verified","alert_id":alert_id}

@router.post("/assignments/{assignment_id}/verify")
def verify_assignment(assignment_id:int,p:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u["role"]!="field_officer": raise HTTPException(403,"Field officer required")
 c=conn(); assignment=c.execute("SELECT parcel_id FROM field_assignments WHERE id=? AND officer_email=?",(assignment_id,u["email"])).fetchone(); c.close()
 if not assignment: raise HTTPException(403,"Assignment is not assigned to this field officer")
 return verify(assignment["parcel_id"],p,authorization)
