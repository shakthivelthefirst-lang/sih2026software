
from fastapi import APIRouter,HTTPException,Header
from backend.core import conn
router=APIRouter()
@router.get("/status")
def citizen_status(case_id:str="",parcel_id:str="",authorization:str=Header(None)):
 # Public-safe status; authentication is optional for the citizen view.
 c=conn(); q="SELECT * FROM parcels WHERE "; args=[]
 if parcel_id: q+="(id=? OR record_id=?)"; args=[parcel_id,parcel_id]
 elif case_id: q+="case_reference=?"; args=[case_id]
 else: c.close(); raise HTTPException(400,"Provide case_id or parcel_id")
 p=c.execute(q,args).fetchone(); c.close()
 if not p: raise HTTPException(404,"Case or parcel not found")
 return {"parcel_id":p["record_id"],"case_reference":p["case_reference"],"district":p["district"],"village":p["village"],"survey_no":p["survey_no"],"notification":p["notification_pending"]==0,"award":p["award_pending"]==0,"compensation":"Pending" if p["compensation_pending"] else "Recorded","possession":"Pending" if p["possession_pending"] else "Recorded","rehabilitation":"Pending" if p["rehabilitation_pending"] else "Recorded","current_status":p["acquisition_status"],"next_step":"Check with the designated acquisition office for case-specific action."}
