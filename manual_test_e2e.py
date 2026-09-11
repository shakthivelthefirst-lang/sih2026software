import urllib.request
import json
import time

def api(path, method="GET", body=None, token=None):
    req = urllib.request.Request(f'http://127.0.0.1:8001{path}', method=method)
    if body:
        req.data = json.dumps(body).encode()
        req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        res = urllib.request.urlopen(req)
        return json.loads(res.read()), res.status
    except Exception as e:
        return {"error": str(e)}, 500

# 1. State Authority Login
print("Logging in State Authority...")
resp, status = api('/auth/login', "POST", {"email":"state@cbe.ac.in", "password":"Tngov@CBE#2026"})
state_token = resp['access_token']

# 2. Get Initial Dashboard State
resp, _ = api('/dashboard/state', token=state_token)
initial_projects = resp['total_projects']

# 3. Create Project
print("Creating Project...")
new_id = f"PRJ-2026-DIST-{int(time.time())}"
payload = {
    "project_id": new_id,
    "project_name": "Test End-to-End Metro",
    "project_type": "Rail",
    "district": "Coimbatore",
    "taluk": "North",
    "village": "Vadavalli",
    "land_required": 12.5,
    "priority": "High",
    "project_start_date": "2026-10-01",
    "planned_completion_date": "2028-10-01",
    "description": "E2E Test",
    "department": "Transport",
    "estimated_project_cost": 5000000
}
create_resp, create_status = api('/projects/', "POST", payload, token=state_token)
print("Create Project Response:", create_resp)

# 4. Check Dashboard Update
resp, _ = api('/dashboard/state', token=state_token)
new_projects = resp['total_projects']
print(f"Dashboard Projects: {initial_projects} -> {new_projects}")

# 5. District Authority Login
print("Logging in District Authority...")
resp, _ = api('/auth/login', "POST", {"email":"district@cbe.ac.in", "password":"Tngov@CBE#2026"})
dist_token = resp['access_token']

# 6. Check Notifications
resp, _ = api('/alerts/?status=Open', token=dist_token)
my_alerts = [a for a in resp if a['assigned_to'] == 'district@cbe.ac.in' and a['project_id'] == new_id]
print("District Notifications found:", len(my_alerts))

# 7. Check Project Details
resp, _ = api(f'/projects/{new_id}', token=dist_token)
print("Project Details (Stage):", resp.get('current_stage'))
