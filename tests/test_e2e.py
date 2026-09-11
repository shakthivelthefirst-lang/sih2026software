
import uuid
from fastapi.testclient import TestClient
from backend.main import app
CLIENT=TestClient(app)
def auth(email="Tngov@cbe.ac.in",password="Tngov@CBE#2026"):
 r=CLIENT.post("/auth/login",json={"email":email,"password":password}); assert r.status_code==200; return {"Authorization":"Bearer "+r.json()["access_token"]}
def test_health_and_login():
 assert CLIENT.get("/health").status_code==200
 assert CLIENT.post("/auth/login",json={"email":"Tngov@cbe.ac.in","password":"bad"}).status_code==401
def test_authority_and_rbac():
 h=auth(); assert CLIENT.get("/auth/me",headers=h).status_code==200
 assert CLIENT.post("/auth/users",headers=h,json={"email":f"test-{uuid.uuid4().hex[:6]}@example.gov.in","password":"DemoPass#123","role":"admin"}).status_code==200
 assert CLIENT.delete("/auth/users/1",headers=h).status_code==400
def test_project_parcel_and_validation():
 h=auth(); pid="T-"+uuid.uuid4().hex[:8]
 assert CLIENT.post("/projects/",headers=h,json={"project_id":pid,"project_name":"Test Project","project_type":"Road","district":"Coimbatore","taluk":"Coimbatore North"}).status_code==200
 bad=CLIENT.post("/land-records/validate",headers=h,json={"survey_no":"1","subdivision":"1","village":"x","taluk":"x","district":"Coimbatore","area":-1,"classification":"Agricultural","latitude":99,"longitude":1})
 assert bad.json()["valid"] is False
 p={"record_id":"R-"+uuid.uuid4().hex[:8],"survey_no":uuid.uuid4().hex[:5],"subdivision":"1","village":"Demo Village","taluk":"Coimbatore North","district":"Coimbatore","area":2,"classification":"Agricultural","project_id":pid,"latitude":11.0168,"longitude":76.9558,"training_label":"HIGH","project_type":"Road","legal_disputes":1,"compensation_pending":1,"approval_pending":1}
 r=CLIENT.post("/land-records/",headers=h,json=p); assert r.status_code==200; parcel_id=r.json()["parcel_id"]
 assert CLIENT.get(f"/land-records/{parcel_id}",headers=h).status_code==200
 assert CLIENT.post("/land-records/",headers=h,json=p).status_code==409
def test_intelligence_and_gis():
 h=auth(); payload={"project_type":"Road","land_required":2,"affected_parcels":5,"affected_families":2,"legal_disputes":1,"compensation_pending":1,"approval_pending":1,"documentation_pending":0,"rehabilitation_pending":0,"notification_pending":0,"award_pending":1,"possession_pending":0,"stakeholder_responsiveness":50,"environmental_risk":30,"weather_risk":40}
 assert CLIENT.post("/ml/risk",headers=h,json=payload).status_code==200
 st=CLIENT.post("/ml/stage-risk",headers=h,json=payload); assert st.status_code==200 and len(st.json()["stages"])==7
 ex=CLIENT.post("/ml/explain",headers=h,json=payload); assert ex.status_code==200 and ex.json()["explanation_method"] in ("SHAP","feature_importance_fallback")
 assert CLIENT.get("/gis/parcels?limit=2",headers=h).status_code==200
def test_alert_dashboard_audit_documents_citizen():
 h=auth()
 assert CLIENT.get("/dashboard/",headers=h).status_code==200
 a=CLIENT.post("/alerts/",headers=h,json={"type":"Delay Risk","severity":"HIGH","message":"test","recommended_action":"review"}); assert a.status_code==200
 assert CLIENT.get("/alerts/",headers=h).status_code==200
 assert CLIENT.get("/audit/",headers=h).status_code==200
 assert CLIENT.get("/documents/",headers=h).status_code==200
 assert CLIENT.get("/citizen/status?parcel_id=999999").status_code==404
def test_model_versions_and_persistence():
 h=auth(); assert CLIENT.get("/ml/versions",headers=h).status_code==200
 r=CLIENT.get("/ml/training",headers=h); assert r.status_code==200 and r.json()["persistent_training_rows"]>=1
