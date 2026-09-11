
from fastapi import APIRouter,Header,HTTPException
from backend.core import conn,current_user,audit
import uuid
router=APIRouter()
@router.get("/")
def alerts(authorization:str=Header(None),status:str=""):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 c=conn(); q="SELECT * FROM alerts"; args=[]; 
 if status: q+=" WHERE status=?"; args=[status]
 q+=" ORDER BY id DESC LIMIT 500"; rows=[dict(x) for x in c.execute(q,args).fetchall()]; c.close(); return rows

@router.get("/operations")
def operations(authorization: str = Header(None)):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 c=conn(); rows=[dict(x) for x in c.execute("""
	 SELECT a.*, p.project_name, p.district, p.current_stage,
					pa.record_id, pa.survey_no, pa.village, pa.taluk,
					CASE WHEN a.status='Open' THEN 'Unread' ELSE 'Read' END AS read_status,
					CASE
						WHEN lower(a.type) LIKE '%risk%' OR lower(a.severity) IN ('high','critical') THEN 'Risk'
						WHEN lower(a.type) LIKE '%deadline%' OR lower(a.type) LIKE '%sla%' THEN 'SLA'
						WHEN lower(a.type) LIKE '%project%' OR lower(a.type) LIKE '%stage%' THEN 'Project'
						WHEN lower(a.type) LIKE '%grievance%' THEN 'Grievance'
						WHEN lower(a.type) LIKE '%verification%' OR lower(a.type) LIKE '%parcel%' THEN 'Verification'
						ELSE 'Other'
					END AS category
	 FROM alerts a LEFT JOIN projects p ON p.project_id=a.project_id LEFT JOIN parcels pa ON pa.id=a.parcel_id
	 ORDER BY a.id DESC LIMIT 500
 """).fetchall()]; c.close(); return rows
@router.post("/")
def create(a:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u["role"] not in ("authority","admin","acquisition_officer"): raise HTTPException(403,"Insufficient permissions")
 aid="ALT-"+uuid.uuid4().hex[:10].upper(); c=conn(); c.execute("INSERT INTO alerts(alert_id,project_id,parcel_id,type,severity,trigger,message,recommended_action,assigned_to,due_date) VALUES(?,?,?,?,?,?,?,?,?,?)",(aid,a.get("project_id"),a.get("parcel_id"),a.get("type","Delay Risk"),a.get("severity","HIGH"),a.get("trigger","Manual"),a.get("message","Review required"),a.get("recommended_action","Review case"),a.get("assigned_to"),a.get("due_date"))); c.commit(); c.close(); audit(u["email"],"ALERT_GENERATED","alert",aid); return {"alert_id":aid}
@router.patch("/{alert_id}")
def update(alert_id:str,p:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u: raise HTTPException(401,"Authentication required")
 status=p.get("status"); allowed=("Open","Acknowledged","In Progress","Resolved")
 if status not in allowed: raise HTTPException(400,"Invalid status")
 c=conn(); cur=c.execute("UPDATE alerts SET status=?,acknowledged_at=CASE WHEN ?='Acknowledged' THEN CURRENT_TIMESTAMP ELSE acknowledged_at END,resolved_at=CASE WHEN ?='Resolved' THEN CURRENT_TIMESTAMP ELSE resolved_at END WHERE alert_id=?",(status,status,status,alert_id)); c.commit(); c.close()
 if not cur.rowcount: raise HTTPException(404,"Alert not found")
 audit(u["email"],"ALERT_STATUS_UPDATED","alert",alert_id,new_value=status); return {"message":"Alert updated"}
