from fastapi import APIRouter,HTTPException,Header,UploadFile,File
from backend.core import conn,current_user,audit,UPLOADS
from backend.services.ml_service import predict
from backend.services.risk_service import stage_risk
from backend.services.explain_service import explain
from backend.services.validation_service import validate_land_record
import shutil,uuid
router=APIRouter()
@router.post('/validate')
def validate(record:dict,authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 return validate_land_record(record)
@router.get('/')
def list_parcels(authorization:str=Header(None),survey_no:str='',village:str='',taluk:str='',district:str='',limit:int=100):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 q='SELECT * FROM parcels WHERE 1=1'; args=[]
 for col,val in [('survey_no',survey_no),('village',village),('taluk',taluk),('district',district)]:
  if val: q+=f' AND {col} LIKE ?'; args.append('%'+val+'%')
 q+=' ORDER BY id DESC LIMIT ?'; args.append(min(limit,1000)); c=conn(); rows=[dict(r) for r in c.execute(q,args).fetchall()]; c.close(); return rows
@router.post('/')
def add(parcel:dict,authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u['role'] not in ('authority','admin'): raise HTTPException(403,'Insufficient permissions')
 required=['record_id','survey_no','subdivision','village','taluk','district','area','classification','project_id','latitude','longitude','training_label']
 missing=[x for x in required if parcel.get(x) in (None,'')]
 if missing: raise HTTPException(400,{'missing_fields':missing})
 valid=validate_land_record(parcel)
 if not valid.get('valid',False): raise HTTPException(400,valid)
 features=parcel.get('ml_features',{}); features.setdefault('project_type',parcel.get('project_type','Road')); features.setdefault('land_required',parcel['area']); features.setdefault('affected_parcels',1); features.setdefault('affected_families',0); features.setdefault('legal_disputes',0); features.setdefault('compensation_pending',0); features.setdefault('approval_pending',0); features.setdefault('documentation_pending',0); features.setdefault('rehabilitation_pending',0); features.setdefault('notification_pending',0); features.setdefault('award_pending',0); features.setdefault('possession_pending',0); features.setdefault('stakeholder_responsiveness',80); features.setdefault('environmental_risk',20); features.setdefault('weather_risk',20)
 try: pred=predict(features)
 except Exception as e: raise HTTPException(503,str(e))
 c=conn()
 try:
  c.execute('INSERT INTO parcels(record_id,survey_no,subdivision,village,taluk,district,area,classification,project_id,latitude,longitude,validation_status,risk_category,risk_probability,risk_score,delay_probability,training_label,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(parcel['record_id'],parcel['survey_no'],parcel['subdivision'],parcel['village'],parcel['taluk'],parcel['district'],parcel['area'],parcel['classification'],parcel['project_id'],parcel['latitude'],parcel['longitude'],'VALID',pred['risk_category'],pred['risk_probability'],pred['risk_score'],pred['risk_probability'],parcel['training_label'].upper(),u['email']))
  c.commit(); pid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
 except Exception as e: c.rollback(); raise HTTPException(400,str(e))
 finally: c.close()
 # Persist labelled example into training CSV, then retrain is explicit/automatic.
 import pandas as pd
 from backend.services.ml_service import DATA,FEATURES,train_new
 row={k:features.get(k,0) for k in FEATURES}; row.update({'project_id':parcel['project_id'],'risk_score':pred['risk_score'],'delay_probability':pred['risk_probability'],'delay_risk_label':parcel['training_label'].upper(),'delay_days':0}); cols=pd.read_csv(DATA,nrows=0).columns.tolist(); pd.DataFrame([{c:row.get(c,'') for c in cols}]).to_csv(DATA,mode='a',header=False,index=False); meta=train_new(); c=conn(); c.execute('INSERT OR IGNORE INTO model_versions(version,model_path,training_rows,accuracy) VALUES(?,?,?,?)',(meta['version'],meta['version']+'.joblib',meta['rows'],meta['accuracy'])); c.commit(); c.close(); audit(u['email'],'ADD_PARCEL',parcel['record_id'],'ML retrained '+meta['version'])
 return {'message':'Parcel saved, training example persisted, and model retrained','parcel_id':pid,'prediction':pred,'stages':stage_risk(features),'explanation':explain(features),'model_version':meta['version'],'training_rows':meta['rows']}
@router.post('/{parcel_id}/evidence')
def evidence(parcel_id:int,file:UploadFile=File(...),authorization:str=Header(None)):
 u=current_user(authorization)
 if not u or u['role'] not in ('authority','admin','officer','field'): raise HTTPException(403,'Insufficient permissions')
 c=conn(); row=c.execute('SELECT id FROM parcels WHERE id=?',(parcel_id,)).fetchone(); c.close()
 if not row: raise HTTPException(404,'Parcel not found')
 name=f'{uuid.uuid4().hex}_{file.filename}'; path=UPLOADS/name
 with open(path,'wb') as out: shutil.copyfileobj(file.file,out)
 c=conn(); c.execute('INSERT INTO evidence(parcel_id,filename,path) VALUES(?,?,?)',(parcel_id,file.filename,str(path))); c.commit(); c.close(); audit(u['email'],'UPLOAD_EVIDENCE',str(parcel_id),file.filename); return {'message':'Evidence uploaded','filename':file.filename}
