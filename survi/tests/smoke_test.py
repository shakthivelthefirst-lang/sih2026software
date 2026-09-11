import sys
from fastapi.testclient import TestClient
sys.path.insert(0,'.')
from backend.main import app
c=TestClient(app)
assert c.get('/health').status_code==200
r=c.post('/auth/login',json={'email':'Tngov@cbe.ac.in','password':'Tngov@CBE#2026'})
assert r.status_code==200
h={'Authorization':'Bearer '+r.json()['access_token']}
for path in ['/intelligence/overview','/projects/','/gis/config','/gis/parcels?limit=2','/intelligence/ledger']:
    assert c.get(path,headers=h).status_code==200, path
assert c.post('/intelligence/simulate',headers=h,json={}).status_code==200
assert c.post('/intelligence/satellite/change',headers=h,json={'before':.1,'after':.5}).status_code==200
print('SURVI LANDNEXUS smoke test: PASS')
