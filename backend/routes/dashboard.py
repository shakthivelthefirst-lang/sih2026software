
from fastapi import APIRouter,Header,HTTPException
from backend.core import conn,current_user
router=APIRouter()

def get_base_metrics(c, query_filter=""):
    q = lambda sql: c.execute(sql).fetchone()[0]
    return {
        "total_projects": q(f"SELECT count(*) FROM projects {query_filter}"),
        "active_projects": q(f"SELECT count(*) FROM projects WHERE project_status IN ('Active','In Progress') {query_filter.replace('WHERE', 'AND') if 'WHERE' in query_filter else ''}"),
        "completed_projects": q(f"SELECT count(*) FROM projects WHERE project_status='Completed' {query_filter.replace('WHERE', 'AND') if 'WHERE' in query_filter else ''}"),
        "delayed_projects": q(f"SELECT count(*) FROM projects WHERE project_status='Delayed' {query_filter.replace('WHERE', 'AND') if 'WHERE' in query_filter else ''}"),
        "total_parcels": q("SELECT count(*) FROM parcels"),
        "affected_families": q("SELECT COALESCE(sum(affected_families),0) FROM projects"),
        "total_compensation": q("SELECT sum(assessed_amount) FROM compensation") or 0,
        "approved_compensation": q("SELECT sum(approved_amount) FROM compensation") or 0,
        "paid_compensation": q("SELECT sum(paid_amount) FROM compensation") or 0,
        "pending_compensation": q("SELECT sum(pending_amount) FROM compensation") or 0,
        "legal_disputes": q("SELECT count(*) FROM grievances WHERE status != 'Resolved'"),
        "sla_breaches": q("SELECT count(DISTINCT project_id) FROM project_milestones WHERE delay_days > 0"),
        "ocr_verification_pending": q("SELECT count(*) FROM documents WHERE ocr_status='Verification Required'")
    }

@router.get("/")
def dashboard(authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 c=conn(); q=lambda sql: c.execute(sql).fetchone()[0]
 d=get_base_metrics(c)
 d["risk_distribution"]=[dict(r) for r in c.execute("SELECT COALESCE(risk_category,'UNKNOWN') category,count(*) count FROM parcels GROUP BY risk_category").fetchall()]
 d["projects_by_stage"]=[dict(r) for r in c.execute("SELECT current_stage stage,count(*) count FROM projects GROUP BY current_stage").fetchall()]
 d["delay_causes"]=[dict(r) for r in c.execute("SELECT delay_reason reason,count(*) count FROM (SELECT 'Compensation' delay_reason FROM parcels WHERE compensation_pending>0 UNION ALL SELECT 'Legal' FROM parcels WHERE legal_disputes>0 UNION ALL SELECT 'Documentation' FROM parcels WHERE documentation_pending>0 UNION ALL SELECT 'Approval' FROM parcels WHERE approval_pending>0) GROUP BY delay_reason").fetchall()]
 d["high_risk_projects"]=sum(x["count"] for x in d["risk_distribution"] if x["category"] in ("HIGH","CRITICAL"))
 d["critical_projects"]=sum(x["count"] for x in d["risk_distribution"] if x["category"]=="CRITICAL")
 priority_actions = [dict(r) for r in c.execute("SELECT stage as action, delay_days as severity, project_id FROM project_milestones WHERE delay_days > 15 ORDER BY delay_days DESC LIMIT 5").fetchall()]
 d["priority_actions"] = [{"task": f"SLA Breached ({p['severity']} days) at {p['action']}", "project_id": p["project_id"]} for p in priority_actions]
 workload = [dict(r) for r in c.execute("SELECT assigned_to, count(*) as count FROM alerts WHERE status='Open' AND assigned_to IS NOT NULL GROUP BY assigned_to").fetchall()]
 d["officer_workload"] = workload
 c.close(); return d

@router.get("/state")
def state_dashboard(authorization:str=Header(None)):
    c=conn()
    d=get_base_metrics(c)
    d["escalated_cases"] = c.execute("SELECT count(*) FROM grievances WHERE status = 'Escalated'").fetchone()[0]
    d["high_risk_projects"] = c.execute("SELECT count(*) FROM parcels WHERE risk_category IN ('HIGH', 'CRITICAL')").fetchone()[0]
    d["critical_projects"] = c.execute("SELECT count(*) FROM parcels WHERE risk_category = 'CRITICAL'").fetchone()[0]
    
    # State specific aggregations
    d["district_performance"] = [dict(r) for r in c.execute("SELECT district, count(*) as projects, avg(progress) as avg_progress FROM projects GROUP BY district").fetchall()]
    d["bottlenecks"] = [dict(r) for r in c.execute("""
        SELECT stage, COUNT(*) AS count FROM (
            SELECT CASE
                WHEN m.stage IN ('Survey','SIA / Survey') THEN 'Survey'
                WHEN m.stage='Legal Dispute / Resolution' THEN 'Objections'
                WHEN m.stage='Rehabilitation & Resettlement' THEN 'R&R'
                ELSE m.stage END AS stage
            FROM projects p
            JOIN project_milestones m ON m.project_id=p.project_id
                AND (m.stage=p.current_stage
                     OR (p.current_stage='Survey' AND m.stage='SIA / Survey')
                     OR (p.current_stage='Rehabilitation & Resettlement' AND m.stage='Rehabilitation'))
            WHERE p.project_status NOT IN ('Completed','Closed')
              AND m.status != 'Completed'
              AND (m.status IN ('Pending','In Progress')
                   OR (m.expected_date IS NOT NULL AND julianday(m.expected_date) < julianday('now')))
            UNION ALL
            SELECT 'Field Verification' AS stage
            FROM field_assignments
            WHERE status IN ('Pending Verification','In Progress')
        ) GROUP BY stage ORDER BY count DESC
    """).fetchall()]
    d["rr_progress"] = [dict(r) for r in c.execute("SELECT status, count(*) as count FROM r_and_r GROUP BY status").fetchall()]
    d["projects_by_stage"]=[dict(r) for r in c.execute("SELECT current_stage stage,count(*) count FROM projects GROUP BY current_stage").fetchall()]
    d["risk_distribution"]=[dict(r) for r in c.execute("SELECT COALESCE(risk_category,'UNKNOWN') category,count(*) count FROM parcels GROUP BY risk_category").fetchall()]

    c.close(); return d

@router.get("/district")
def district_dashboard(authorization:str=Header(None)):
    c=conn()
    d=get_base_metrics(c)
    d["escalated_cases"] = c.execute("SELECT count(*) FROM grievances WHERE status = 'Escalated'").fetchone()[0]
    d["high_risk_projects"] = c.execute("SELECT count(*) FROM parcels WHERE risk_category IN ('HIGH', 'CRITICAL')").fetchone()[0]
    d["critical_projects"] = c.execute("SELECT count(*) FROM parcels WHERE risk_category = 'CRITICAL'").fetchone()[0]
    d["pending_verification"] = c.execute("SELECT count(*) FROM field_assignments WHERE status = 'Pending Verification'").fetchone()[0]

    # District specific aggregations
    d["taluk_overview"] = [dict(r) for r in c.execute("SELECT taluk, count(*) as projects, avg(progress) as avg_progress FROM projects GROUP BY taluk").fetchall()]
    priority_actions = [dict(r) for r in c.execute("SELECT stage as action, delay_days as severity, project_id FROM project_milestones WHERE delay_days > 15 ORDER BY delay_days DESC LIMIT 5").fetchall()]
    d["priority_actions"] = [{"task": f"SLA Breached ({p['severity']} days) at {p['action']}", "project_id": p["project_id"]} for p in priority_actions]
    d["officer_workload"] = [dict(r) for r in c.execute("SELECT officer_email as assigned_to, count(*) as count FROM field_assignments WHERE status!='Completed' GROUP BY officer_email").fetchall()]
    
    d["payment_completion"] = round((d["paid_compensation"] / d["total_compensation"] * 100) if d["total_compensation"] > 0 else 0, 1)
    
    # Reports
    d["compensation_paid_report"] = [dict(r) for r in c.execute("SELECT c.project_id, p.survey_no, p.taluk, p.owner_reference, c.approved_amount, c.paid_amount, c.status FROM compensation c JOIN parcels p ON c.parcel_id = p.id WHERE c.status = 'Paid' LIMIT 10").fetchall()]
    d["compensation_pending_report"] = [dict(r) for r in c.execute("SELECT c.project_id, p.survey_no, p.taluk, p.owner_reference, c.assessed_amount, c.pending_amount, c.status FROM compensation c JOIN parcels p ON c.parcel_id = p.id WHERE c.status != 'Paid' LIMIT 10").fetchall()]

    c.close(); return d
