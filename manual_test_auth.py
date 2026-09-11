import urllib.request
import json

req = urllib.request.Request(
    'http://127.0.0.1:8001/auth/login',
    data=b'{"email":"state@cbe.ac.in","password":"Tngov@CBE#2026"}',
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(req)
data = json.loads(res.read())
print("LOGIN:", data)

token = data['access_token']
req2 = urllib.request.Request(
    'http://127.0.0.1:8001/auth/me',
    headers={'Authorization': 'Bearer ' + token}
)
res2 = urllib.request.urlopen(req2)
print("ME:", json.loads(res2.read()))
