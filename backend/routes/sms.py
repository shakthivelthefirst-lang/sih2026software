from fastapi import APIRouter, HTTPException, Header
from backend.core import conn, current_user, audit
from backend.services.sms_service import send_sms, smpp_health
import datetime

router = APIRouter()

@router.get("/smpp/health")
def smpp_health_check(authorization: str = Header(None)):
    u = current_user(authorization)
    if not u:
        raise HTTPException(401, "Authentication required")
    return smpp_health()

def generate_message(parcel: dict) -> str:
    return (
        f"Land Record Notification\n\n"
        f"Parcel ID: {parcel.get('record_id') or parcel.get('id')}\n"
        f"Survey No.: {parcel.get('survey_no')}\n"
        f"District: {parcel.get('district')}\n"
        f"State: {parcel.get('state', 'Tamil Nadu')}\n"
        f"Current Status: {parcel.get('acquisition_status', 'VERIFIED')}\n\n"
        f"Your land parcel record has been updated.\n"
        f"Please refer to the official land-record portal for further details.\n\n"
        f"This is a system-generated notification."
    )

@router.post("/parcel/{parcel_id}")
def send_parcel_sms(parcel_id: int, authorization: str = Header(None)):
    u = current_user(authorization)
    if not u or u["role"] not in ("authority", "admin", "district_authority", "state_authority"):
        raise HTTPException(403, "Insufficient permissions")

    c = conn()
    parcel = c.execute("SELECT * FROM parcels WHERE id=?", (parcel_id,)).fetchone()
    if not parcel:
        c.close()
        raise HTTPException(404, "Parcel not found")
    
    parcel = dict(parcel)
    mobile = parcel.get("mobile_number")
    
    if not mobile:
        c.close()
        raise HTTPException(400, "No mobile number associated with this parcel")
        
    msg = generate_message(parcel)
    
    # Send SMS via SMPP
    result = send_sms(mobile, msg)
    
    status = result["status"]
    message_id = result["message_id"] or "N/A"
    
    # Update DB
    c.execute(
        "UPDATE parcels SET notification_status=? WHERE id=?",
        (status, parcel_id)
    )
    c.commit()
    c.close()
    
    audit(u["email"], "SEND_SMS", "parcel", f"id={parcel_id}, Status: {status}, MsgId: {message_id}")
    
    return {"message": "SMS processed", **result, "message_id": message_id}

@router.post("/test-bulk")
def test_bulk_sms(authorization: str = Header(None)):
    u = current_user(authorization)
    if not u or u["role"] not in ("authority", "admin", "district_authority", "state_authority"):
        raise HTTPException(403, "Insufficient permissions")
        
    c = conn()
    # Fetch the first 6 records
    parcels = c.execute("SELECT * FROM parcels ORDER BY id ASC LIMIT 6").fetchall()
    
    results = []
    success_count = 0
    failed_count = 0
    
    for parcel in parcels:
        p_dict = dict(parcel)
        mobile = p_dict.get("mobile_number")
        
        if not mobile:
            failed_count += 1
            results.append({"parcel_id": p_dict["id"], "status": "FAILED", "reason": "No mobile"})
            continue
            
        msg = generate_message(p_dict)
        res = send_sms(mobile, msg)
        
        c.execute("UPDATE parcels SET notification_status=? WHERE id=?", (res["status"], p_dict["id"]))
        
        if res["success"]:
            success_count += 1
        else:
            failed_count += 1
            
        results.append({
            "parcel_id": p_dict["id"],
            "mobile": mobile,
            "status": res["status"],
            "message_id": res["message_id"],
            "success": res["success"],
            "smpp_command_status": res.get("smpp_command_status"),
            "error_code": res.get("error_code"),
            "error_description": res.get("error_description"),
            "exception_type": res.get("exception_type"),
            "exception_message": res.get("exception_message"),
            "retryable": res.get("retryable", False),
        })
        
    c.commit()
    c.close()
    
    audit(u["email"], "BULK_SMS_TEST", "system", f"target=first_6_parcels, Success: {success_count}, Failed: {failed_count}")
    
    return {
        "summary": {
            "Total Parcels": len(parcels),
            "Submitted": len(parcels),
            "Successful": success_count,
            "Failed": failed_count,
            "Mode": "SIMULATION" if any(result["status"] == "SIMULATED" for result in results) else "SMPP"
        },
        "details": results
    }
