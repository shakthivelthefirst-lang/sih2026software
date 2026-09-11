from fastapi import APIRouter,HTTPException,Header
from pydantic import BaseModel
from backend.core import conn,verify,hash_password,token,current_user,audit,AUTH_EMAIL
router=APIRouter()
class Login(BaseModel): email:str; password:str
class UserIn(BaseModel): email:str; password:str; role:str
@router.post('/login')
def login(x:Login):
 c=conn(); u=c.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND active=1',(x.email,)).fetchone(); c.close()
 if not u or not verify(x.password,u['password_hash']): raise HTTPException(401,'Invalid credentials')
 return {'access_token':token(u['email'],u['role']),'token_type':'bearer','user':{'email':u['email'],'role':u['role'],'is_authority':bool(u['is_authority'])}}
@router.get('/me')
def me(authorization:str=Header(None)):
 u=current_user(authorization)
 if not u: raise HTTPException(401,'Authentication required')
 return {'email':u['email'],'role':u['role'],'is_authority':bool(u['is_authority'])}
@router.get('/users')
def users(authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u['role']!='authority': raise HTTPException(403,'Authority only')
 c=conn(); rows=[dict(r) for r in c.execute('SELECT id,email,role,active,is_authority,created_at FROM users').fetchall()]; c.close(); return rows
@router.post('/users')
def add_user(x:UserIn,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u['role']!='authority': raise HTTPException(403,'Authority only')
 if x.role not in ('admin','officer','field','citizen') or x.email.lower()==AUTH_EMAIL.lower(): raise HTTPException(400,'Invalid role or protected authority account')
 c=conn()
 try: c.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)',(x.email,hash_password(x.password),x.role)); c.commit()
 except Exception as e: raise HTTPException(400,'Unable to create user: '+str(e))
 finally: c.close()
 audit(u['email'],'CREATE_USER',x.email,x.role); return {'message':'User created'}
@router.delete('/users/{user_id}')
def disable_user(user_id:int,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u['role']!='authority': raise HTTPException(403,'Authority only')
 c=conn(); row=c.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
 if not row: raise HTTPException(404,'User not found')
 if row['is_authority'] or row['email'].lower()==AUTH_EMAIL.lower(): raise HTTPException(400,'Permanent TNGOV Authority cannot be deleted')
 c.execute('UPDATE users SET active=0 WHERE id=?',(user_id,)); c.commit(); c.close(); audit(u['email'],'DISABLE_USER',row['email']); return {'message':'User disabled'}
