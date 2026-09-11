import os
import uuid
import shutil
import logging
import mimetypes
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from backend.core import ROOT, current_user, conn, UPLOADS, parcel_scope

router = APIRouter()
logger = logging.getLogger(__name__)

def _stored_file_path(stored_path: str) -> Path | None:
    """Resolve a document only within the application's uploads directory."""
    uploads_root = UPLOADS.resolve()
    raw_path = Path(stored_path) if stored_path else Path()
    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
        candidates.append(uploads_root / raw_path.name)
    else:
        candidates.extend((ROOT / raw_path, uploads_root / raw_path.name))

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved == uploads_root or uploads_root not in resolved.parents:
            continue
        if resolved.is_file():
            return resolved
    return None

@router.get("/")
def docs(authorization: str = Header(None), parcel_id: int = None, project_id: str = None):
    u=current_user(authorization)
    if not u: raise HTTPException(401, "Authentication required")
    c = conn()
    scope,scope_args=parcel_scope(u,"p")
    query="SELECT d.* FROM documents d LEFT JOIN parcels p ON p.id=d.parcel_id WHERE " + scope
    args=list(scope_args)
    if parcel_id: query += " AND d.parcel_id=?"; args.append(parcel_id)
    if project_id: query += " AND d.project_id=?"; args.append(project_id)
    query += " ORDER BY d.id DESC LIMIT 500"
    rows = [dict(x) for x in c.execute(query,args).fetchall()]
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

@router.get("/{document_id}/download")
def download_doc(document_id: str, authorization: str = Header(None)):
    u = current_user(authorization)
    if not u:
        raise HTTPException(401, "Authentication required")

    c = conn()
    scope,scope_args=parcel_scope(u,"p")
    document = c.execute(f"SELECT d.document_name, d.path, d.format FROM documents d LEFT JOIN parcels p ON p.id=d.parcel_id WHERE d.document_id=? AND {scope}",[document_id]+scope_args).fetchone()
    c.close()
    if not document:
        raise HTTPException(404, "Document not found")

    file_path = _stored_file_path(document["path"])
    if not file_path:
        logger.warning("Document download requested: id=%s user=%s file_found=NO", document_id, u["email"])
        raise HTTPException(404, "DOCUMENT_FILE_NOT_FOUND")

    filename = Path(document["document_name"] or file_path.name).name
    media_type = mimetypes.guess_type(filename)[0] or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    logger.info("Document download requested: id=%s user=%s file_found=YES", document_id, u["email"])
    return FileResponse(file_path, media_type=media_type, filename=filename)
