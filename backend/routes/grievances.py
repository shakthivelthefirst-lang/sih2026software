from fastapi import APIRouter
from pydantic import BaseModel
from backend.core import conn

router = APIRouter()

class GrievanceCreate(BaseModel):
    parcel_id: int
    project_id: str
    submitted_by: str
    type: str
    description: str


@router.get('/all')
def get_all_grievances():
    c = conn()
    res = c.execute("SELECT * FROM grievances ORDER BY created_at DESC LIMIT 100").fetchall()
    c.close()
    return [dict(r) for r in res]

@router.get("/{project_id}")
def get_grievances(project_id: str):
    c = conn()
    res = c.execute("SELECT * FROM grievances WHERE project_id=? ORDER BY created_at DESC", (project_id,)).fetchall()
    c.close()
    return [dict(r) for r in res]

@router.post("/")
def create_grievance(g: GrievanceCreate):
    c = conn()
    c.execute("INSERT INTO grievances(parcel_id, project_id, submitted_by, type, description) VALUES(?, ?, ?, ?, ?)", (g.parcel_id, g.project_id, g.submitted_by, g.type, g.description))
    c.commit()
    c.close()
    return {"status": "success", "message": "Grievance submitted"}

@router.post("/{grievance_id}/resolve")
def resolve_grievance(grievance_id: int, resolution: dict):
    c = conn()
    c.execute("UPDATE grievances SET status='Resolved', resolution=? WHERE id=?", (resolution.get("resolution", ""), grievance_id))
    c.commit()
    c.close()
    return {"status": "success"}
