from pathlib import Path
import sqlite3, hashlib, hmac, base64, json, time, secrets
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DB=DATA/'survi.db'; MODEL_DIR=ROOT/'models'; MODEL_DIR.mkdir(exist_ok=True); UPLOADS=ROOT/'uploads'; UPLOADS.mkdir(exist_ok=True)
AUTH_EMAIL='Tngov@cbe.ac.in'; AUTH_PASSWORD='Tngov@CBE#2026'
def _st_as_geojson(geom):
 if not geom: return None
 try:
  if isinstance(geom, str): return json.dumps(json.loads(geom))
  elif isinstance(geom, dict): return json.dumps(geom)
 except: pass
 return None

def _st_centroid(geom):
 if not geom: return None
 try:
  g = json.loads(geom) if isinstance(geom, str) else geom
  if isinstance(g, dict) and g.get('type') == 'Point': return json.dumps(g.get('coordinates'))
  elif isinstance(g, dict) and g.get('type') in ('Polygon', 'MultiPolygon'):
   coords = g.get('coordinates', [[]])[0]
   if coords:
    ring = coords[:-1] if len(coords) > 1 and coords[0] == coords[-1] else coords
    return json.dumps([sum(pt[0] for pt in ring)/len(ring), sum(pt[1] for pt in ring)/len(ring)])
 except: pass
 return None

def _st_x(centroid):
 if not centroid: return None
 try:
  c = json.loads(centroid) if isinstance(centroid, str) else centroid
  return float(c[0])
 except: return None

def _st_y(centroid):
 if not centroid: return None
 try:
  c = json.loads(centroid) if isinstance(centroid, str) else centroid
  return float(c[1])
 except: return None

def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 c.create_function('ST_AsGeoJSON', 1, _st_as_geojson)
 c.create_function('ST_Centroid', 1, _st_centroid)
 c.create_function('ST_X', 1, _st_x)
 c.create_function('ST_Y', 1, _st_y)
 return c
def hash_password(p):
 salt=secrets.token_bytes(16); dk=hashlib.pbkdf2_hmac('sha256',p.encode(),salt,120000); return base64.b64encode(salt+dk).decode()
def verify(p,stored):
 try:
  raw=base64.b64decode(stored); return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',p.encode(),raw[:16],120000),raw[16:])
 except: return False
def secret_key(): return 'SURVI-TNGOV-MASTER-CHANGE-IN-PRODUCTION-2026'
def token(email,role):
 payload={'email':email,'role':role,'exp':int(time.time())+8*3600}; raw=base64.urlsafe_b64encode(json.dumps(payload,separators=(',',':')).encode()).decode().rstrip('='); sig=hmac.new(secret_key().encode(),raw.encode(),hashlib.sha256).hexdigest(); return raw+'.'+sig
def current_user(authorization):
 if not authorization or not authorization.startswith('Bearer '): return None
 try:
  raw,sig=authorization[7:].split('.',1); expected=hmac.new(secret_key().encode(),raw.encode(),hashlib.sha256).hexdigest()
  if not hmac.compare_digest(sig,expected): return None
  p=json.loads(base64.urlsafe_b64decode(raw+'==='));
  if p['exp']<time.time(): return None
  c=conn(); u=c.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND active=1',(p['email'],)).fetchone(); c.close()
  if not u: return None
  ud=dict(u)
  if not ud.get("district") and "cbe" in ud.get("email","").lower() and ud.get("role") != "state_authority":
   ud["district"]="Coimbatore"
  if not ud.get("taluk") and ud.get("role")=="field_officer":
   ud["taluk"]="Sulur"
  return ud
 except: return None
def audit(user,action,target,details=''):
 c=conn(); c.execute('INSERT INTO audit(user_email,action,target,details) VALUES(?,?,?,?)',(user,action,target,details)); c.commit(); c.close()
def init_db():
 DATA.mkdir(exist_ok=True); c=conn(); c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,active INTEGER DEFAULT 1,is_authority INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS parcels(id INTEGER PRIMARY KEY AUTOINCREMENT,record_id TEXT UNIQUE,survey_no TEXT,subdivision TEXT,village TEXT,taluk TEXT,district TEXT,area REAL,classification TEXT,project_id TEXT,latitude REAL,longitude REAL,validation_status TEXT,risk_category TEXT,risk_probability REAL,risk_score REAL,delay_probability REAL,training_label TEXT,created_by TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,parcel_id INTEGER,filename TEXT,path TEXT,uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,user_email TEXT,action TEXT,target TEXT,details TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS model_versions(id INTEGER PRIMARY KEY AUTOINCREMENT,version TEXT UNIQUE,model_path TEXT,training_rows INTEGER,accuracy REAL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS projects(project_id TEXT PRIMARY KEY,project_name TEXT,project_type TEXT,district TEXT,taluk TEXT,total_land_required REAL,affected_parcels INTEGER,affected_families INTEGER,project_start_date TEXT,expected_completion_date TEXT);
CREATE TABLE IF NOT EXISTS workflow(project_id TEXT,stage TEXT,status TEXT,notes TEXT,updated_by TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(project_id,stage));''')
 row=c.execute('SELECT * FROM users WHERE lower(email)=lower(?)',(AUTH_EMAIL,)).fetchone()
 if not row: c.execute('INSERT INTO users(email,password_hash,role,is_authority) VALUES(?,?,?,1)',(AUTH_EMAIL,hash_password(AUTH_PASSWORD),'authority'))
 else: c.execute('UPDATE users SET is_authority=1,role="authority",active=1 WHERE lower(email)=lower(?)',(AUTH_EMAIL,))
 try:
  import pandas as pd; csv=ROOT/'data/coimbatore/06_acquisition_projects.csv'
  if csv.exists() and c.execute('SELECT count(*) n FROM projects').fetchone()['n']==0:
   df=pd.read_csv(csv).fillna('')
   for _,r in df.iterrows(): c.execute('INSERT OR IGNORE INTO projects VALUES(?,?,?,?,?,?,?,?,?,?)',tuple(r.get(k,'') for k in ['project_id','project_name','project_type','district','taluk','total_land_required','affected_parcels','affected_families','project_start_date','expected_completion_date']))
 except Exception: pass
 try:
  cols = set(r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall())
  for col, ctype in [('district','TEXT'),('taluk','TEXT')]:
   if col not in cols: c.execute(f'ALTER TABLE users ADD COLUMN {col} {ctype}')
 except Exception: pass
 try:
  cols = set(r['name'] for r in c.execute('PRAGMA table_info(parcels)').fetchall())
  for col, ctype in [('geom','TEXT'),('geometry','TEXT'),('survey_number','TEXT'),('locality','TEXT'),('revenue_village','TEXT'),('stage','TEXT'),('is_acquired','INTEGER'),('owner_name','TEXT')]:
   if col not in cols: c.execute(f'ALTER TABLE parcels ADD COLUMN {col} {ctype}')
 except Exception: pass
 c.commit(); c.close()
init_db()
