import urllib.request
import json

def api(path, token):
    req = urllib.request.Request(f'http://127.0.0.1:8001{path}', headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read())

# Login
login_req = urllib.request.Request('http://127.0.0.1:8001/auth/login', 
                                   data=json.dumps({"email":"state@cbe.ac.in", "password":"Tngov@CBE#2026"}).encode(),
                                   headers={'Content-Type':'application/json'})
with urllib.request.urlopen(login_req) as res:
    token = json.loads(res.read())['access_token']

print("--- Testing GET /api/parcels/stats (Dedicated Endpoint) ---")
stats_res = api('/api/parcels/stats', token)
print("Stats response:", stats_res['stats'])
assert stats_res['stats']['all'] == 25005, f"Expected 25005, got {stats_res['stats']['all']}"
assert stats_res['stats']['acquired'] == 9372, f"Expected 9372, got {stats_res['stats']['acquired']}"
assert stats_res['stats']['pending'] == 15633, f"Expected 15633, got {stats_res['stats']['pending']}"
assert stats_res['stats']['acquired'] + stats_res['stats']['pending'] + stats_res['stats']['disputed'] == stats_res['stats']['all']

print("--- Testing GET /api/parcels with no filter ---")
all_res = api('/api/parcels?limit=150', token)
print("Total matching rows:", all_res['total'])
print("Page items length:", len(all_res['items']))
print("Stats:", all_res['stats'])
assert all_res['stats']['all'] == 25005
assert all_res['stats']['acquired'] == 9372
assert all_res['stats']['pending'] == 15633

print("--- Testing GET /api/parcels with acquisition_status=ACQUIRED ---")
acq_res = api('/api/parcels?limit=150&acquisition_status=ACQUIRED', token)
print("Acquired filtered matching rows:", acq_res['total'])
print("Page items length:", len(acq_res['items']))
print("Stats on Acquired filter:", acq_res['stats'])
assert acq_res['total'] == 9372
assert len(acq_res['items']) == 150
# CRITICAL: stats must remain static and NOT show 150 / 0!
assert acq_res['stats']['all'] == 25005, "All count must remain 25005, not jump!"
assert acq_res['stats']['acquired'] == 9372, "Acquired stat must remain 9372, not 150!"
assert acq_res['stats']['pending'] == 15633, "Pending stat must remain 15633, not 0!"

print("--- Testing GET /api/parcels with acquisition_status=PENDING ---")
pen_res = api('/api/parcels?limit=150&acquisition_status=PENDING', token)
print("Pending filtered matching rows:", pen_res['total'])
print("Page items length:", len(pen_res['items']))
print("Stats on Pending filter:", pen_res['stats'])
assert pen_res['total'] == 15633
assert len(pen_res['items']) == 150
# CRITICAL: stats must remain static and NOT show 0 / 150!
assert pen_res['stats']['all'] == 25005, "All count must remain 25005, not jump to 15633!"
assert pen_res['stats']['acquired'] == 9372, "Acquired stat must remain 9372, not 0!"
assert pen_res['stats']['pending'] == 15633, "Pending stat must remain 15633, not 150!"

print("--- Testing Project Scoped Stats ---")
# Get first project with parcels
first_pid = all_res['items'][0]['project_id']
prj_res = api(f'/api/parcels?limit=150&project_id={first_pid}', token)
prj_stats = prj_res['stats']
print(f"Project {first_pid} stats:", prj_stats)
assert prj_stats['acquired'] + prj_stats['pending'] + prj_stats['disputed'] == prj_stats['all']
# Now test project + status filter
prj_acq_res = api(f'/api/parcels?limit=150&project_id={first_pid}&acquisition_status=ACQUIRED', token)
print(f"Project {first_pid} stats when filtering Acquired:", prj_acq_res['stats'])
assert prj_acq_res['stats'] == prj_stats, "Project stats must remain identical when filtering status!"

print("\nALL AUTOMATED TESTS PASSED SUCCESSFULLY!")
