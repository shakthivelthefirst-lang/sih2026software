
from fastapi import APIRouter,Header,HTTPException
from backend.core import conn,current_user
router=APIRouter()
@router.get("/")
def audit_logs(authorization:str=Header(None),limit:int=200):
 u=current_user(authorization)
 if not u or u["role"] not in ("authority","admin"): raise HTTPException(403,"Admin or Authority required")
 c=conn(); rows=[dict(x) for x in c.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",(min(limit,500),)).fetchall()]; c.close(); return rows
