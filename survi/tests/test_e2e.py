from fastapi.testclient import TestClient
from backend.main import app

def test_core():
 c=TestClient(app); r=c.post('/auth/login',json={'email':'Tngov@cbe.ac.in','password':'Tngov@CBE#2026'}); assert r.status_code==200
 h={'Authorization':'Bearer '+r.json()['access_token']}; assert c.get('/health').status_code==200; assert c.get('/auth/me',headers=h).status_code==200; assert c.get('/projects/?limit=1',headers=h).status_code==200; assert c.get('/gis/parcels?limit=1',headers=h).status_code==200; assert c.get('/ml/versions',headers=h).status_code==200
