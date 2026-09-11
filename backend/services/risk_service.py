
STAGES=["Notification","Approval","Award","Compensation","Legal Dispute","Possession","Rehabilitation"]
MAP={"Notification":"notification_pending","Approval":"approval_pending","Award":"award_pending","Compensation":"compensation_pending","Legal Dispute":"legal_disputes","Possession":"possession_pending","Rehabilitation":"rehabilitation_pending"}
def stage_risk(f):
 out=[]
 for s,k in MAP.items():
  v=float(f.get(k,0) or 0); score=min(100,max(0,v*35+(20 if s=="Legal Dispute" and v else 0)+float(f.get("weather_risk",0) or 0)*.15+float(f.get("environmental_risk",0) or 0)*.15))
  cat="CRITICAL" if score>=80 else "HIGH" if score>=60 else "MEDIUM" if score>=30 else "LOW"
  action={"Legal Dispute":"Review cases and initiate legal resolution plan","Compensation":"Prioritize assessment/payment workflow","Approval":"Escalate pending departmental approval","Rehabilitation":"Assign RR case officer and track milestones","Notification":"Complete statutory notification checklist","Award":"Accelerate award preparation and approvals","Possession":"Resolve objections and schedule possession"}[s]
  out.append({"stage":s,"risk_score":round(score,2),"risk_category":cat,"status":"Pending" if v else "Clear","delay_days":int(f.get("delay_days",0) or 0),"reason":f"{k.replace('_',' ')} value={v:g}" if v else "No pending indicator","recommended_action":action})
 return out
