import os
from fastapi import APIRouter, Header, HTTPException, Body
from backend.core import conn, current_user, audit
from backend.services.ocr_service import process_document_for_ocr

router = APIRouter()

@router.post("/{document_id}/process")
def process(document_id: str, authorization: str = Header(None)):
    u = current_user(authorization)
    # Allow field_officer to run OCR too
    if not u or u["role"] not in ("authority", "admin", "acquisition_officer", "field_officer"):
        raise HTTPException(403, "Insufficient permissions")
    
    c = conn()
    d = c.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
    if not d:
        c.close()
        raise HTTPException(404, "Document not found")
        
    file_path = d["path"]
    
    # Process OCR
    result = process_document_for_ocr(file_path)
    
    if not result["success"]:
        c.execute("UPDATE documents SET ocr_status='Failed', remarks=? WHERE document_id=?", (result["message"], document_id))
        c.commit()
        c.close()
        raise HTTPException(500, f"OCR failed: {result['message']}")
        
    c.execute("UPDATE documents SET ocr_status='Verification Required', ocr_confidence=?, remarks=? WHERE document_id=?", 
              (result.get("confidence", 0.0), result.get("message", ""), document_id))
              
    # Delete old extractions for this document if re-running
    c.execute("DELETE FROM ocr_extractions WHERE document_id=?", (document_id,))
    
    extracted = result.get("extracted", {})
    for field_name, value in extracted.items():
        if value: # Only insert if we have a value
            c.execute("INSERT INTO ocr_extractions (document_id, field_name, value, confidence, validation_status) VALUES (?, ?, ?, ?, ?)",
                      (document_id, field_name, value, result.get("confidence", 0.0), 'Pending'))
                      
    c.commit()
    c.close()
    
    audit(u["email"], "OCR_PROCESS", "documents", document_id, "", "Verification Required", "success")
    
    return {
        "document_id": document_id,
        "ocr_status": "Verification Required",
        "human_verification_required": True,
        "extractions": extracted,
        "message": result.get("message", "OCR processing complete")
    }

@router.get("/{document_id}")
def get_ocr_details(document_id: str, authorization: str = Header(None)):
    u = current_user(authorization)
    if not u:
        raise HTTPException(401, "Authentication required")
        
    c = conn()
    d = c.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
    if not d:
        c.close()
        raise HTTPException(404, "Document not found")
        
    extractions = c.execute("SELECT * FROM ocr_extractions WHERE document_id=?", (document_id,)).fetchall()
    c.close()
    
    return {
        "document_id": document_id,
        "ocr_status": d["ocr_status"],
        "ocr_confidence": d["ocr_confidence"],
        "extractions": [dict(e) for e in extractions]
    }

@router.post("/{document_id}/verify")
def verify_ocr(document_id: str, payload: dict = Body(...), authorization: str = Header(None)):
    u = current_user(authorization)
    if not u or u["role"] not in ("authority", "admin", "acquisition_officer", "field_officer"):
        raise HTTPException(403, "Insufficient permissions")
        
    c = conn()
    d = c.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
    if not d:
        c.close()
        raise HTTPException(404, "Document not found")
        
    verified_fields = payload.get("fields", {})
    
    c.execute("DELETE FROM ocr_extractions WHERE document_id=?", (document_id,))
    
    for field_name, value in verified_fields.items():
        if value:
            c.execute("INSERT INTO ocr_extractions (document_id, field_name, value, confidence, validation_status, human_verified) VALUES (?, ?, ?, ?, ?, ?)",
                      (document_id, field_name, value, 1.0, 'Verified', 1))
                      
    c.execute("UPDATE documents SET ocr_status='Verified', verification_status='Verified' WHERE document_id=?", (document_id,))
    c.commit()
    c.close()
    
    audit(u["email"], "OCR_VERIFY", "documents", document_id, "Verification Required", "Verified", "success")
    
    return {"success": True, "message": "OCR data verified successfully"}
