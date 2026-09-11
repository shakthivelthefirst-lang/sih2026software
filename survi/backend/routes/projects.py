from fastapi import APIRouter,HTTPException,Header
from backend.core import current_user,conn,audit
router=APIRouter(); STAGES=['Notification','Approval','Award','Compensation','Legal Dispute','Possession','Rehabilitation']
@router.get('/')
def list_projects(authorization:str=Header(None),limit:int=100):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 c=conn(); rows=[dict(r) for r in c.execute('SELECT * FROM projects ORDER BY project_id LIMIT ?',(min(limit,1000),)).fetchall()]; c.close(); return rows
@router.get('/{project_id}')
def get_project(project_id:str,authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 c=conn(); r=c.execute('SELECT * FROM projects WHERE project_id=?',(project_id,)).fetchone(); wf=[dict(x) for x in c.execute('SELECT stage,status,notes,updated_by,updated_at FROM workflow WHERE project_id=?',(project_id,)).fetchall()]; c.close()
 if not r: raise HTTPException(404,'Project not found')
 d=dict(r); d['workflow']=wf; return d
@router.post('/')
def create_project(p:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u['role'] not in ('authority','admin','officer'): raise HTTPException(403,'Authority, Admin or Officer required')
 req=['project_id','project_name','project_type','district','taluk']; miss=[x for x in req if not p.get(x)]
 if miss: raise HTTPException(400,{'missing_fields':miss})
 c=conn()
 try:
  c.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?)',(p['project_id'],p['project_name'],p['project_type'],p['district'],p['taluk'],p.get('total_land_required',0),p.get('affected_parcels',0),p.get('affected_families',0),p.get('project_start_date',''),p.get('expected_completion_date',''))); c.commit()
 except Exception as e: raise HTTPException(400,str(e))
 finally:c.close()
 audit(u['email'],'CREATE_PROJECT',p['project_id']); return {'message':'Project created','project_id':p['project_id']}
@router.put('/{project_id}/workflow/{stage}')
def update_workflow(project_id:str,stage:str,payload:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u['role'] not in ('authority','admin','officer'): raise HTTPException(403,'Authority, Admin or Officer required')
 if stage not in STAGES: raise HTTPException(400,'Invalid stage')
 status=payload.get('status','Pending'); notes=payload.get('notes',''); c=conn();
 if not c.execute('SELECT 1 FROM projects WHERE project_id=?',(project_id,)).fetchone(): c.close(); raise HTTPException(404,'Project not found')
 c.execute('INSERT INTO workflow(project_id,stage,status,notes,updated_by,updated_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(project_id,stage) DO UPDATE SET status=excluded.status,notes=excluded.notes,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP',(project_id,stage,status,notes,u['email'])); c.commit(); c.close(); audit(u['email'],'UPDATE_WORKFLOW',project_id,stage+': '+status); return {'message':'Workflow updated','stage':stage,'status':status}
