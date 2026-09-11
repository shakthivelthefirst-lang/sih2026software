from datetime import date
import uuid
from fastapi import APIRouter, Header, HTTPException
from backend.core import conn, current_user, audit

router = APIRouter()

def _rows(c, where="", args=()):
    return [dict(r) for r in c.execute("""
        SELECT c.id AS compensation_id, c.project_id, c.parcel_id,
               p.survey_no, p.village, p.taluk, p.district,
               c.assessed_amount AS eligible_amount, c.approved_amount,
               c.paid_amount, c.pending_amount, c.status, c.payment_date
        FROM compensation c JOIN parcels p ON p.id=c.parcel_id
    """ + where + " ORDER BY c.id DESC", args).fetchall()]

@router.get("/project/{project_id}")
def project_compensation(project_id: str, authorization: str = Header(None)):
    u = current_user(authorization)
    if not u or u["role"] not in ("state_authority", "district_authority", "authority", "admin"):
        raise HTTPException(403, "District Officer access required")
    c = conn(); rows = _rows(c, " WHERE c.project_id=? AND c.status != 'Paid'", (project_id,)); c.close()
    return rows

@router.get("/mine")
def my_compensation(authorization: str = Header(None)):
    u = current_user(authorization)
    if not u or u["role"] != "citizen":
        raise HTTPException(403, "Citizen access required")
    c = conn(); rows = _rows(c, " WHERE lower(p.owner_reference)=lower(?)", (u["email"],)); c.close()
    return rows

@router.post("/project/{project_id}/parcel/{parcel_id}/pay")
def pay(project_id: str, parcel_id: int, authorization: str = Header(None)):
    u = current_user(authorization)
    if not u or u["role"] != "district_authority":
        raise HTTPException(403, "District Officer access required")
    c = conn()
    row = c.execute("""SELECT c.*,p.survey_no,p.village,p.owner_reference
        FROM compensation c JOIN parcels p ON p.id=c.parcel_id
        WHERE c.project_id=? AND c.parcel_id=?""", (project_id, parcel_id)).fetchone()
    if not row:
        c.close(); raise HTTPException(404, "Compensation record not found")
    if row["status"] == "Paid" or float(row["pending_amount"] or 0) <= 0:
        c.close(); raise HTTPException(409, "Compensation has already been paid.")
    amount = float(row["pending_amount"])
    paid = float(row["paid_amount"] or 0) + amount
    c.execute("UPDATE compensation SET paid_amount=?,pending_amount=0,status='Paid',payment_date=date('now') WHERE project_id=? AND parcel_id=?", (paid, project_id, parcel_id))
    recipient = c.execute("SELECT email FROM users WHERE role='citizen' AND active=1 AND lower(email)=lower(?)", (row["owner_reference"] or "",)).fetchone()
    alert_id = None
    if recipient:
        alert_id = "ALT-" + uuid.uuid4().hex[:10].upper()
        c.execute("""INSERT INTO alerts(alert_id,project_id,parcel_id,type,severity,trigger,message,recommended_action,assigned_to,status)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (alert_id, project_id, parcel_id, "Compensation Payment Completed", "INFO", "District Officer", f"Compensation payment completed for survey {row['survey_no']}.", "Review payment record", recipient["email"], "Open"))
    c.commit(); c.close(); audit(u["email"], "COMPENSATION_PAID", "parcel", parcel_id, new_value=str(amount))
    return {"message": "Compensation payment completed", "project_id": project_id, "parcel_id": parcel_id, "paid_amount": paid, "pending_amount": 0, "status": "Paid", "payment_date": date.today().isoformat(), "alert_id": alert_id, "citizen_alert_created": bool(recipient)}