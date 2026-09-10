
def validate_land_record(r):
 required=["survey_no","subdivision","village","taluk","district","area","classification","latitude","longitude"]
 errors=[f for f in required if r.get(f) in (None,"")]
 try:
  if float(r.get("area",0))<=0: errors.append("area must be > 0")
  lat=float(r.get("latitude")); lon=float(r.get("longitude"))
  if not (-90<=lat<=90 and -180<=lon<=180): errors.append("invalid GPS range")
 except Exception: errors.append("area/GPS must be numeric")
 if r.get("training_label","").upper() not in ("LOW","MEDIUM","HIGH","CRITICAL"): errors.append("training_label must be LOW, MEDIUM, HIGH or CRITICAL")
 if r.get("acquisition_status") and r["acquisition_status"] not in ("Proposal","Scrutiny","Approval","Notification","Survey","Award","Compensation","Legal Dispute / Resolution","Rehabilitation & Resettlement","Possession","Closure / Completion"): errors.append("invalid acquisition status")
 return {"valid":not errors,"errors":errors,"validation_status":"VALID" if not errors else "INVALID"}
