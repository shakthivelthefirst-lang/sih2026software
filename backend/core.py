from pathlib import Path
import sqlite3, hashlib, hmac, base64, json, time, secrets
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DB=DATA/'survi.db'; MODEL_DIR=ROOT/'models'; MODEL_DIR.mkdir(exist_ok=True); UPLOADS=ROOT/'uploads'; UPLOADS.mkdir(exist_ok=True)
AUTH_EMAIL='Tngov@cbe.ac.in'; AUTH_PASSWORD='Tngov@CBE#2026'
def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
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
  c=conn(); u=c.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND active=1',(p['email'],)).fetchone(); c.close(); return dict(u) if u else None
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
 c.commit(); c.close()
init_db()
