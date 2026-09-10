import os
import uuid
import shutil
from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form
from backend.core import current_user, conn, UPLOADS

router = APIRouter()

@router.get("/")
def docs(authorization: str = Header(None), parcel_id: int = None, project_id: str = None):
    if not current_user(authorization): raise HTTPException(401, "Authentication required")
    c = conn()
    if parcel_id:
        rows = [dict(x) for x in c.execute("SELECT * FROM documents WHERE parcel_id=? ORDER BY id DESC", (parcel_id,)).fetchall()]
    elif project_id:
        rows = [dict(x) for x in c.execute("SELECT * FROM documents WHERE project_id=? ORDER BY id DESC", (project_id,)).fetchall()]
    else:
        rows = [dict(x) for x in c.execute("SELECT * FROM documents ORDER BY id DESC LIMIT 500").fetchall()]
    c.close()
    return rows

@router.post("/")
async def upload_doc(
    authorization: str = Header(None),
    file: UploadFile = File(...),
    project_id: str = Form(None),
    parcel_id: int = Form(None)
):
    u = current_user(authorization)
    if not u: raise HTTPException(401, "Authentication required")
    
    doc_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{doc_id}{file_ext}"
    file_path = UPLOADS / safe_filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    c = conn()
    c.execute("""
        INSERT INTO documents (document_id, project_id, parcel_id, document_name, path, format, uploaded_by, verification_status, ocr_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 'Not Started')
    """, (doc_id, project_id, parcel_id, file.filename, str(file_path), file_ext, u["email"]))
    c.commit()
    c.close()
    
    return {"document_id": doc_id, "message": "Uploaded successfully"}
