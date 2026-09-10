from fastapi import APIRouter
from backend.core import conn

router = APIRouter()

@router.get("/")
def get_reports():
    c = conn()
    projects = c.execute("SELECT COUNT(*) as cnt FROM projects").fetchone()["cnt"]
    delayed_milestones = c.execute("SELECT COUNT(*) as cnt FROM project_milestones WHERE delay_days > 0").fetchone()["cnt"]
    total_compensation = c.execute("SELECT SUM(pending_amount) as total FROM compensation").fetchone()["total"] or 0
    total_rr = c.execute("SELECT COUNT(*) as cnt FROM r_and_r WHERE status='Pending'").fetchone()["cnt"]
    
    project_wise = c.execute("SELECT project_id, project_name, current_stage, progress FROM projects LIMIT 50").fetchall()
    
    c.close()
    
    return {
        "summary": {
            "total_projects": projects,
            "delayed_cases": delayed_milestones,
            "total_pending_compensation": total_compensation,
            "pending_rr": total_rr
        },
        "project_wise": [dict(p) for p in project_wise]
    }
