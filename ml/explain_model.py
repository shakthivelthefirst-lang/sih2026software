from backend.services.explain_service import explain
sample={'project_type':'Road','land_required':1,'affected_parcels':5,'affected_families':2,'legal_disputes':1,'compensation_pending':1,'approval_pending':1,'documentation_pending':0,'rehabilitation_pending':0,'notification_pending':0,'award_pending':1,'possession_pending':0,'stakeholder_responsiveness':50,'environmental_risk':30,'weather_risk':40}
print(explain(sample))
