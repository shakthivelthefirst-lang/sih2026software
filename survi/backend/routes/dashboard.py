from fastapi import APIRouter,Header,HTTPException
from backend.core import conn,current_user
router=APIRouter()
@router.get('/')
def dashboard(authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 c=conn(); total=c.execute('SELECT count(*) n FROM parcels').fetchone()['n']; counts={r['risk_category']:r['n'] for r in c.execute('SELECT risk_category,count(*) n FROM parcels GROUP BY risk_category')}; users=c.execute('SELECT count(*) n FROM users WHERE active=1').fetchone()['n']; models=c.execute('SELECT count(*) n FROM model_versions').fetchone()['n']; c.close(); return {'parcels':total,'risk_counts':counts,'active_users':users,'model_versions':models}
