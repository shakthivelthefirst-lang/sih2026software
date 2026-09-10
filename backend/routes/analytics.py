
from fastapi import APIRouter,Header,HTTPException
from backend.core import conn,current_user
router=APIRouter()
@router.get("/")
def analytics(authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 c=conn()
 district=[dict(x) for x in c.execute("SELECT district,count(*) parcels,round(avg(delay_days),2) avg_delay FROM parcels GROUP BY district ORDER BY avg_delay DESC").fetchall()]
 stages=[dict(x) for x in c.execute("SELECT current_stage stage,count(*) projects FROM projects GROUP BY current_stage ORDER BY projects DESC").fetchall()]
 types=[dict(x) for x in c.execute("SELECT project_type,count(*) projects FROM projects GROUP BY project_type ORDER BY projects DESC").fetchall()]
 avg=c.execute("SELECT round(avg(delay_days),2) FROM parcels").fetchone()[0] or 0
 legal=c.execute("SELECT round(100.0*avg(CASE WHEN legal_disputes>0 THEN 1 ELSE 0 END),2) FROM parcels").fetchone()[0] or 0
 c.close()
 return {"district_delay":district,"stage_frequency":stages,"project_type_distribution":types,"average_acquisition_delay_days":avg,"legal_dispute_frequency_pct":legal,"policy_observations":["Data-driven observation: districts are ranked by observed average parcel delay.","Data-driven observation: stages are ranked by project frequency, not causal proof."],"recommendations":["AI-generated recommendation: prioritize review of high-delay districts and overdue workflow stages.","AI-generated recommendation: monitor compensation, legal and documentation backlogs before escalation."]}

@router.get("/operations")
def operations(authorization: str = Header(None)):
	if not current_user(authorization):
		raise HTTPException(401, "Authentication required")
	c = conn()
	count = lambda sql: c.execute(sql).fetchone()[0] or 0
	risk_distribution = [dict(r) for r in c.execute("""
		SELECT COALESCE(risk_category, 'UNKNOWN') AS category, COUNT(*) AS count,
			   ROUND(AVG(risk_score), 2) AS average_score
		FROM parcels GROUP BY COALESCE(risk_category, 'UNKNOWN') ORDER BY count DESC
	""").fetchall()]
	risk_base = "COALESCE(rp.risk_category, pa.risk_category)"
	risk_score = "COALESCE(rp.risk_score, pa.risk_score)"
	risk_rows = lambda sql: [dict(r) for r in c.execute(sql).fetchall()]
	project_risk = risk_rows(f"""
		SELECT pa.project_id, COALESCE(p.project_name, pa.project_id) AS project_name,
			   COUNT(*) AS parcels, SUM(CASE WHEN {risk_base} IN ('HIGH','CRITICAL') THEN 1 ELSE 0 END) AS high_risk,
			   ROUND(AVG({risk_score}), 2) AS average_risk_score
		FROM parcels pa LEFT JOIN projects p ON p.project_id=pa.project_id
		LEFT JOIN risk_predictions rp ON rp.id=(SELECT MAX(id) FROM risk_predictions WHERE parcel_id=pa.id)
		GROUP BY pa.project_id ORDER BY high_risk DESC, average_risk_score DESC LIMIT 100
	""")
	village_risk = risk_rows(f"""
		SELECT pa.village, pa.taluk, pa.district, COUNT(*) AS parcels,
			   SUM(CASE WHEN {risk_base} IN ('HIGH','CRITICAL') THEN 1 ELSE 0 END) AS high_risk,
			   ROUND(AVG({risk_score}), 2) AS average_risk_score
		FROM parcels pa LEFT JOIN risk_predictions rp ON rp.id=(SELECT MAX(id) FROM risk_predictions WHERE parcel_id=pa.id)
		GROUP BY pa.village, pa.taluk, pa.district ORDER BY high_risk DESC, average_risk_score DESC LIMIT 100
	""")
	top_risk = risk_rows(f"""
		SELECT pa.id AS parcel_id, pa.record_id, pa.survey_no, pa.village, pa.taluk, pa.district,
			   pa.project_id, p.project_name, p.current_stage, {risk_base} AS risk_category,
			   {risk_score} AS risk_score, COALESCE(rp.created_at, pa.last_updated, pa.created_at) AS assessed_at
		FROM parcels pa LEFT JOIN projects p ON p.project_id=pa.project_id
		LEFT JOIN risk_predictions rp ON rp.id=(SELECT MAX(id) FROM risk_predictions WHERE parcel_id=pa.id)
		WHERE {risk_base} IN ('HIGH','CRITICAL')
		ORDER BY CASE {risk_base} WHEN 'CRITICAL' THEN 0 ELSE 1 END, {risk_score} DESC, pa.id LIMIT 100
	""")
	c.execute("SELECT 1")
	result = {
		"projects": {
			"total": count("SELECT COUNT(*) FROM projects"),
			"active": count("SELECT COUNT(*) FROM projects WHERE project_status IN ('Active','In Progress')"),
			"delayed": count("SELECT COUNT(*) FROM projects WHERE project_status='Delayed'"),
			"completed": count("SELECT COUNT(*) FROM projects WHERE project_status='Completed'"),
			"by_stage": [dict(r) for r in c.execute("SELECT current_stage AS stage, COUNT(*) AS count FROM projects GROUP BY current_stage ORDER BY count DESC").fetchall()],
			"by_district": [dict(r) for r in c.execute("SELECT district, COUNT(*) AS count FROM projects GROUP BY district ORDER BY count DESC").fetchall()],
		},
		"parcels": {
			"total": count("SELECT COUNT(*) FROM parcels"),
			"affected": count("SELECT COUNT(*) FROM parcels WHERE project_id IS NOT NULL AND project_id != ''"),
			"verified": count("SELECT COUNT(DISTINCT parcel_id) FROM field_verifications WHERE status IN ('Verified','Completed')"),
			"acquired": count("SELECT COUNT(*) FROM parcels WHERE acquisition_status IN ('Award','Compensation','Possession','Rehabilitation')"),
			"pending_verification": count("SELECT COUNT(DISTINCT parcel_id) FROM field_assignments WHERE status='Pending Verification'"),
			"risk_distribution": risk_distribution,
		},
		"risk": {
			"total": count("SELECT COUNT(*) FROM parcels WHERE risk_category IS NOT NULL"),
			"average_score": c.execute("SELECT ROUND(AVG(risk_score),2) FROM parcels WHERE risk_score IS NOT NULL").fetchone()[0],
			"prediction_count": count("SELECT COUNT(*) FROM risk_predictions"),
			"prediction_distribution": [dict(r) for r in c.execute("SELECT risk_category AS category, COUNT(*) AS count FROM risk_predictions GROUP BY risk_category ORDER BY count DESC").fetchall()],
			"project_wise": project_risk,
			"village_wise": village_risk,
			"top_parcels": top_risk,
			"synthetic_note": "SYNTHETIC PROTOTYPE DATA" if count("SELECT COUNT(*) FROM parcels WHERE risk_score IS NULL") > 0 else "",
		},
		"acquisition": {
			"by_stage": [dict(r) for r in c.execute("SELECT acquisition_status AS stage, COUNT(*) AS count FROM parcels GROUP BY acquisition_status ORDER BY count DESC").fetchall()],
			"compensation_pending": count("SELECT COUNT(*) FROM compensation WHERE status != 'Paid'"),
			"compensation_completed": count("SELECT COUNT(*) FROM compensation WHERE status='Paid'"),
			"possession": [dict(r) for r in c.execute("SELECT acquisition_status AS status, COUNT(*) AS count FROM parcels WHERE acquisition_status='Possession' GROUP BY acquisition_status").fetchall()],
			"rehabilitation": [dict(r) for r in c.execute("SELECT status, COUNT(*) AS count FROM r_and_r GROUP BY status").fetchall()],
		},
		"sla": {
			"due_soon": count("SELECT COUNT(*) FROM project_milestones WHERE status!='Completed' AND expected_date IS NOT NULL AND julianday(expected_date)-julianday('now') BETWEEN 0 AND 7"),
			"breached": count("SELECT COUNT(*) FROM project_milestones WHERE status!='Completed' AND (delay_days>0 OR (expected_date IS NOT NULL AND julianday(expected_date)<julianday('now')))"),
			"average_delay": c.execute("SELECT ROUND(AVG(delay_days),2) FROM project_milestones WHERE delay_days>0").fetchone()[0] or 0,
			"bottlenecks": count("SELECT COUNT(*) FROM project_milestones WHERE status!='Completed' AND delay_days>0"),
		},
		"grievances": {
			"total": count("SELECT COUNT(*) FROM grievances"),
			"by_status": [dict(r) for r in c.execute("SELECT status, COUNT(*) AS count FROM grievances GROUP BY status ORDER BY count DESC").fetchall()],
		},
	}
	c.close()
	return result
