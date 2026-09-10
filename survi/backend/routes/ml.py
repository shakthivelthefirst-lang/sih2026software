from fastapi import APIRouter,HTTPException,Header
from backend.core import current_user,conn
from backend.services.ml_service import train_new,predict
from backend.services.risk_service import stage_risk
from backend.services.explain_service import explain
router=APIRouter()
@router.post('/retrain')
def retrain(authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u['role'] not in ('authority','admin'): raise HTTPException(403,'Admin or Authority required')
 meta=train_new(); c=conn(); c.execute('INSERT INTO model_versions(version,model_path,training_rows,accuracy) VALUES(?,?,?,?)',(meta['version'],meta['version']+'.joblib',meta['rows'],meta['accuracy'])); c.commit(); c.close(); return meta
@router.get('/versions')
def versions(authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 c=conn(); rows=[dict(r) for r in c.execute('SELECT * FROM model_versions ORDER BY id DESC').fetchall()]; c.close(); return rows
@router.post('/risk')
def risk(payload:dict,authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 return predict(payload)
@router.post('/stage-risk')
def stages(payload:dict,authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 return {'stages':stage_risk(payload)}
@router.post('/explain')
def explanation(payload:dict,authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 return explain(payload)
