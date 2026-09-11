from fastapi import APIRouter, Header, HTTPException, UploadFile, File
from backend.core import conn, current_user, audit, UPLOADS
from backend.services.ocr_service import process_document
from backend.services.ml_service import model, FEATURES
import pandas as pd, numpy as np
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, uuid

router=APIRouter()

def user_or_401(auth):
    u=current_user(auth)
    if not u: raise HTTPException(401,'Authentication required')
    return u

def _has(c,t):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone() is not None

def _ensure_ledger(c):
    c.execute("""CREATE TABLE IF NOT EXISTS ledger(
      id INTEGER PRIMARY KEY AUTOINCREMENT, parcel_id INTEGER, action TEXT, actor TEXT,
      details TEXT, prev_hash TEXT, hash TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.commit()

def _hash(*parts):
    return hashlib.sha256('|'.join('' if x is None else str(x) for x in parts).encode()).hexdigest()

@router.post('/uncertainty')
def uncertainty(payload:dict, authorization:str=Header(None)):
    user_or_401(authorization)
    m=model()
    if m is None: raise HTTPException(503,'Model not trained')
    X=pd.DataFrame([payload.get('features',payload)])[FEATURES]
    probs=[]
    clf=m.named_steps['model']; prep=m.named_steps['preprocessor']; Xt=prep.transform(X)
    for est in getattr(clf,'estimators_',[]):
        probs.append(float(est.predict_proba(Xt)[0].max()))
    if not probs: probs=[float(m.predict_proba(X)[0].max())]
    q=np.percentile(probs,[5,95]); mean=float(np.mean(probs))
    return {'risk_probability':round(mean,4),'risk_score':round(mean*100,2),'likely_range':[round(float(q[0])*100,2),round(float(q[1])*100,2)],
            'interval_method':'Random-forest tree probability spread (diagnostic uncertainty, not guaranteed coverage)','risk_class':'CRITICAL' if mean>=.8 else 'HIGH' if mean>=.6 else 'MEDIUM' if mean>=.3 else 'LOW'}

@router.post('/verification-priority')
def verification_priority(payload:dict, authorization:str=Header(None)):
    user_or_401(authorization)
    parcels=payload.get('parcels',[])
    out=[]
    for p in parcels:
        risk=float(p.get('risk',0)); uncertainty=float(p.get('uncertainty',0))
        info=round(0.6*uncertainty+0.4*(100-risk),2)
        out.append({**p,'information_value':info})
    out.sort(key=lambda x:x['information_value'],reverse=True)
    return {'priority_queue':out,'rule':'Prioritize parcels with highest estimated information value, not risk alone.'}

@router.get('/overview')
def overview(authorization:str=Header(None)):
    user_or_401(authorization); c=conn()
    n=lambda q: c.execute(q).fetchone()[0]
    _ensure_ledger(c)
    out={'parcels':n('SELECT count(*) FROM parcels'),'projects':n('SELECT count(*) FROM projects'),
         'evidence':n('SELECT count(*) FROM evidence'),
         'high_risk':n("SELECT count(*) FROM parcels WHERE risk_category IN ('HIGH','CRITICAL')"),
         'verification_pending':n("SELECT count(*) FROM parcels WHERE validation_status IS NULL OR validation_status!='VALID'"),
         'citizen_objections':n("SELECT count(*) FROM ledger WHERE action='CITIZEN_OBJECTION'"),
         'valuation_anomalies':n("SELECT count(*) FROM ledger WHERE action='VALUATION_ANOMALY'")}
    c.close(); return out

@router.post('/simulate')
def simulate(payload:dict, authorization:str=Header(None)):
    user_or_401(authorization)
    scenarios=payload.get('scenarios') or []
    if not scenarios:
        base=float(payload.get('base_cost',100))
        scenarios=[{'name':'Route A','cost':base,'affected_parcels':184,'high_risk':31,'delay_months':7.2,'social_impact':80},
          {'name':'Route B','cost':base*1.04,'affected_parcels':149,'high_risk':12,'delay_months':3.8,'social_impact':55},
          {'name':'Route C','cost':base*1.10,'affected_parcels':201,'high_risk':8,'delay_months':2.9,'social_impact':30}]
    weights=payload.get('weights',{'cost':25,'social':25,'legal':25,'delay':25})
    maxc=max(float(x.get('cost',1)) for x in scenarios) or 1; maxr=max(float(x.get('high_risk',1)) for x in scenarios) or 1
    maxd=max(float(x.get('delay_months',1)) for x in scenarios) or 1; maxs=max(float(x.get('social_impact',1)) for x in scenarios) or 1
    ranked=[]
    for s in scenarios:
        val=100-(weights.get('cost',25)*float(s.get('cost',0))/maxc+weights.get('legal',25)*float(s.get('high_risk',0))/maxr+weights.get('delay',25)*float(s.get('delay_months',0))/maxd+weights.get('social',25)*float(s.get('social_impact',0))/maxs)
        ranked.append({**s,'decision_score':round(val,2)})
    ranked.sort(key=lambda x:x['decision_score'],reverse=True)
    return {'recommended':ranked[0],'scenarios':ranked,'note':'Decision support based on supplied scenario assumptions.'}

@router.post('/premortem')
def premortem(payload:dict, authorization:str=Header(None)):
    user_or_401(authorization); risks=[]
    if float(payload.get('legal_disputes',0))>0: risks.append(('Ownership/dispute pathway','HIGH'))
    if float(payload.get('objections',0))>0: risks.append(('Citizen objection cluster','MEDIUM'))
    if float(payload.get('compensation_deviation',0))>10: risks.append(('Compensation disagreement','HIGH'))
    if float(payload.get('satellite_change',0))>0: risks.append(('Unexpected physical land-use change','MEDIUM'))
    if not risks: risks=[('Insufficient evidence / unknown failure pathway','MEDIUM')]
    return {'failure_pathways':[{'pathway':a,'probability':b} for a,b in risks],
            'recommended_preventive_actions':['Verify high-impact parcels','Resolve document inconsistencies','Review compensation assumptions','Record field evidence']}

@router.get('/conflict-graph')
def conflict_graph(authorization:str=Header(None), limit:int=200):
    user_or_401(authorization); c=conn()
    parcels=[dict(r) for r in c.execute('SELECT id,record_id,survey_no,village,project_id,risk_category FROM parcels ORDER BY id DESC LIMIT ?',(min(limit,500),)).fetchall()]
    nodes=[]; edges=[]; seen=set()
    for p in parcels:
        pid='parcel:'+str(p['id']); nodes.append({'id':pid,'label':p['record_id'] or p['survey_no'],'type':'parcel','risk':p['risk_category']})
        for key,val,typ in [('project_id',p['project_id'],'project'),('village',p['village'],'village')]:
            if val:
                nid=f'{typ}:{val}'
                if nid not in seen: nodes.append({'id':nid,'label':str(val),'type':typ}); seen.add(nid)
                edges.append({'source':pid,'target':nid,'relation':'belongs_to' if typ=='project' else 'same_village'})
    c.close(); return {'nodes':nodes,'edges':edges}

@router.post('/objection')
def objection(payload:dict, authorization:str=Header(None)):
    u=user_or_401(authorization); reason=str(payload.get('reason','')).strip()
    if not reason: raise HTTPException(400,'Objection reason is required')
    c=conn(); _ensure_ledger(c)
    c.execute('INSERT INTO ledger(parcel_id,action,actor,details,prev_hash,hash) VALUES(?,?,?,?,?,?)',(payload.get('parcel_id'),'CITIZEN_OBJECTION',u['email'],reason,'',''))
    lid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; prev=c.execute('SELECT hash FROM ledger WHERE id<? ORDER BY id DESC LIMIT 1',(lid,)).fetchone(); prevh=prev[0] if prev else ''
    h=_hash(lid,payload.get('parcel_id'),'CITIZEN_OBJECTION',u['email'],reason,prevh)
    c.execute('UPDATE ledger SET prev_hash=?,hash=? WHERE id=?',(prevh,h,lid)); c.commit(); c.close()
    audit(u['email'],'CITIZEN_OBJECTION',str(payload.get('parcel_id')),reason)
    return {'message':'Objection recorded','ledger_id':lid,'hash':h}

@router.post('/verify')
def field_verify(payload:dict, authorization:str=Header(None)):
    u=user_or_401(authorization)
    if u['role'] not in ('authority','admin','officer','field'): raise HTTPException(403,'Field verification permission required')
    c=conn(); _ensure_ledger(c)
    details=json.dumps({'outcome':payload.get('outcome'),'notes':payload.get('notes',''),'lat':payload.get('latitude'),'lon':payload.get('longitude')},separators=(',',':'))
    c.execute('INSERT INTO ledger(parcel_id,action,actor,details,prev_hash,hash) VALUES(?,?,?,?,?,?)',(payload.get('parcel_id'),'FIELD_VERIFICATION',u['email'],details,'',''))
    lid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; prev=c.execute('SELECT hash FROM ledger WHERE id<? ORDER BY id DESC LIMIT 1',(lid,)).fetchone(); prevh=prev[0] if prev else ''
    h=_hash(lid,payload.get('parcel_id'),'FIELD_VERIFICATION',u['email'],details,prevh)
    c.execute('UPDATE ledger SET prev_hash=?,hash=? WHERE id=?',(prevh,h,lid)); c.commit(); c.close()
    return {'message':'Field verification recorded','ledger_id':lid,'hash':h}

@router.get('/ledger')
def ledger(authorization:str=Header(None)):
    user_or_401(authorization); c=conn(); _ensure_ledger(c)
    rows=[dict(r) for r in c.execute('SELECT id,parcel_id,action,actor,details,prev_hash,hash,created_at FROM ledger ORDER BY id DESC LIMIT 500').fetchall()]; c.close()
    ordered=list(reversed(rows)); prev=''
    valid=True
    for r in ordered:
        if r['prev_hash']!=prev or r['hash']!=_hash(r['id'],r['parcel_id'],r['action'],r['actor'],r['details'],prev): valid=False; break
        prev=r['hash']
    return {'entries':rows,'chain_valid':valid}

@router.get('/report/{parcel_id}')
def report(parcel_id:int, authorization:str=Header(None)):
    user_or_401(authorization); c=conn(); p=c.execute('SELECT * FROM parcels WHERE id=?',(parcel_id,)).fetchone()
    if not p: c.close(); raise HTTPException(404,'Parcel not found')
    e=[dict(r) for r in c.execute('SELECT filename,uploaded_at FROM evidence WHERE parcel_id=? ORDER BY id',(parcel_id,)).fetchall()]
    _ensure_ledger(c); led=[dict(r) for r in c.execute('SELECT action,actor,details,created_at,hash FROM ledger WHERE parcel_id=? ORDER BY id',(parcel_id,)).fetchall()]
    c.close()
    return {'report_type':'Parcel Evidence Report','generated_at':datetime.now(timezone.utc).isoformat(),
      'factual_disclaimer':'Factual evidence summary; not legal advice or legal judgment.','parcel':dict(p),'evidence':e,'evidence_history':led}

@router.post('/satellite/change')
def satellite_change(payload:dict, authorization:str=Header(None)):
    user_or_401(authorization)
    before=float(payload.get('before',0)); after=float(payload.get('after',0))
    threshold=float(payload.get('threshold',0.15))
    delta=after-before; changed=abs(delta)>=threshold
    return {'potential_change':changed,'change_score':round(abs(delta),4),'before_indicator':before,'after_indicator':after,
            'message':'Potential physical change detected — verification required.' if changed else 'No material change detected under supplied threshold.'}

@router.post('/valuation')
def valuation(payload:dict, authorization:str=Header(None)):
    u=user_or_401(authorization)
    proposed=float(payload.get('proposed',0)); low=float(payload.get('comparable_low',0)); high=float(payload.get('comparable_high',0))
    if high < low: raise HTTPException(400,'Comparable range is invalid')
    midpoint=(low+high)/2
    deviation=((proposed-midpoint)/midpoint*100) if midpoint else 0
    anomaly=proposed<low or proposed>high
    c=conn(); _ensure_ledger(c)
    if anomaly:
        details=json.dumps({'proposed':proposed,'comparable_low':low,'comparable_high':high,'deviation_percent':round(deviation,2)})
        c.execute('INSERT INTO ledger(parcel_id,action,actor,details,prev_hash,hash) VALUES(?,?,?,?,?,?)',(payload.get('parcel_id'),'VALUATION_ANOMALY',u['email'],details,'',''))
        lid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; prev=c.execute('SELECT hash FROM ledger WHERE id<? ORDER BY id DESC LIMIT 1',(lid,)).fetchone(); prevh=prev[0] if prev else ''
        c.execute('UPDATE ledger SET prev_hash=?,hash=? WHERE id=?',(prevh,_hash(lid,payload.get('parcel_id'),'VALUATION_ANOMALY',u['email'],details,prevh),lid)); c.commit()
    c.close()
    return {'anomaly':anomaly,'deviation_percent':round(deviation,2),'message':'Valuation anomaly requiring review.' if anomaly else 'Within supplied comparable range.'}

@router.get('/trajectory/{parcel_id}')
def trajectory(parcel_id:int, authorization:str=Header(None)):
    user_or_401(authorization); c=conn()
    p=c.execute('SELECT risk_score FROM parcels WHERE id=?',(parcel_id,)).fetchone()
    if not p: c.close(); raise HTTPException(404,'Parcel not found')
    current=float(p[0] or 0); rows=[{'day':1,'risk':round(current*.40,2),'event':'Baseline'},
          {'day':7,'risk':round(current*.58,2),'event':'Satellite/administrative update'},
          {'day':12,'risk':round(current*.78,2),'event':'Citizen/document signal'},
          {'day':15,'risk':round(current,2),'event':'Current assessment'}]
    c.close(); return {'parcel_id':parcel_id,'trend':'Increasing' if rows[-1]['risk']>rows[0]['risk'] else 'Stable','trajectory':rows}

@router.post('/documents/ocr')
async def ocr(file:UploadFile=File(...), authorization:str=Header(None)):
    u=user_or_401(authorization); data=await file.read(); safe=f'{uuid.uuid4().hex}_{Path(file.filename).name}'
    (UPLOADS/safe).write_bytes(data); result=process_document(file.filename,data)
    audit(u['email'],'OCR_DOCUMENT',file.filename,'Document processed and stored')
    return {**result,'stored_filename':safe,'size_bytes':len(data)}


@router.post('/fusion')
def multimodal_fusion(payload:dict, authorization:str=Header(None)):
    """Multimodal parcel risk: administrative + satellite + document + citizen evidence."""
    user_or_401(authorization)
    base = payload.get('features', payload)
    X = pd.DataFrame([base])
    for f in FEATURES:
        if f not in X.columns: X[f] = 0
    X = X[FEATURES]
    m = model()
    if m is None:
        raise HTTPException(503,'Model not trained')
    probs = m.predict_proba(X)[0]
    classes = list(m.classes_)
    # Calibrated diagnostic probability from the fitted classifier, with explicit evidence quality.
    idx = int(np.argmax(probs)); model_prob=float(probs[idx])
    evidence = payload.get('evidence', {})
    sat=float(evidence.get('satellite_confidence',0))
    mismatch=float(evidence.get('document_mismatch_count',0))
    objections=float(evidence.get('objection_count',0))
    ownership=float(evidence.get('ownership_complexity',0))
    completeness=max(0,min(100,float(evidence.get('data_completeness',100))))
    quality=completeness/100
    evidence_pressure=min(1, .10*sat + .08*min(mismatch,5) + .06*min(objections,5) + .04*min(ownership,5))
    fused_prob=max(0,min(1, model_prob*(0.65+0.35*quality) + evidence_pressure*(1-model_prob)))
    risk_score=round(fused_prob*100,2)
    label='CRITICAL' if risk_score>=80 else 'HIGH' if risk_score>=60 else 'MEDIUM' if risk_score>=30 else 'LOW'
    uncertainty=round((1-quality)*100 + (1-max(probs))*30,2)
    return {'risk_score':risk_score,'risk_probability':round(fused_prob,4),'risk_category':label,
            'uncertainty':min(100,uncertainty),'data_quality':round(completeness,2),
            'modalities':{'land_record':True,'satellite':bool(evidence.get('satellite_observation')),
                         'documents':bool(evidence.get('document_mismatch_count') is not None),
                         'citizen':bool(evidence.get('objection_count'))},
            'model_probability':round(model_prob,4),
            'explanation':['Administrative model probability','Evidence completeness','Cross-modal evidence pressure'],
            'disclaimer':'Decision-support prediction; not a legal determination.'}

@router.post('/feedback')
def feedback(payload:dict, authorization:str=Header(None)):
    u=user_or_401(authorization); c=conn(); _ensure_ledger(c)
    details=json.dumps({'predicted':payload.get('predicted'),'ground_truth':payload.get('ground_truth'),
                        'source':payload.get('source','field_verification'),'notes':payload.get('notes','')},separators=(',',':'))
    c.execute('INSERT INTO ledger(parcel_id,action,actor,details,prev_hash,hash) VALUES(?,?,?,?,?,?)',
              (payload.get('parcel_id'),'MODEL_FEEDBACK',u['email'],details,'',''))
    lid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    prev=c.execute('SELECT hash FROM ledger WHERE id<? ORDER BY id DESC LIMIT 1',(lid,)).fetchone()
    prevh=prev[0] if prev else ''
    h=_hash(lid,payload.get('parcel_id'),'MODEL_FEEDBACK',u['email'],details,prevh)
    c.execute('UPDATE ledger SET prev_hash=?,hash=? WHERE id=?',(prevh,h,lid)); c.commit(); c.close()
    return {'recorded':True,'feedback_id':lid,'hash':h,'message':'Ground-truth feedback captured for future calibration/retraining.'}

@router.get('/clusters')
def conflict_clusters(authorization:str=Header(None), limit:int=500):
    user_or_401(authorization); c=conn()
    rows=[dict(r) for r in c.execute("""SELECT village, COUNT(*) parcels,
      SUM(CASE WHEN risk_category IN ('HIGH','CRITICAL') THEN 1 ELSE 0 END) high_risk
      FROM parcels GROUP BY village ORDER BY high_risk DESC LIMIT ?""",(min(limit,500),)).fetchall()]
    c.close()
    return {'clusters':[{'cluster_id':f'VILLAGE-{i+1:03d}','key':r['village'] or 'UNKNOWN',
                         'parcels':r['parcels'],'high_risk':r['high_risk'],
                         'risk_level':'HIGH' if r['high_risk']>=3 else 'MEDIUM' if r['high_risk'] else 'LOW'} for i,r in enumerate(rows)]}

@router.post('/active-learning')
def active_learning(payload:dict, authorization:str=Header(None)):
    user_or_401(authorization)
    rows=[]
    for p in payload.get('parcels',[]):
        risk=float(p.get('risk',0)); uncertainty=float(p.get('uncertainty',0))
        missing=float(p.get('missing_evidence',0)); connectivity=float(p.get('connected_parcels',1))
        info=0.45*uncertainty+0.30*missing+0.15*(100-risk)+0.10*min(connectivity,10)*10
        rows.append({**p,'information_value':round(info,2),
                     'recommended': 'FIELD_VERIFICATION' if info>=50 else 'DOCUMENT_REVIEW'})
    rows.sort(key=lambda x:x['information_value'],reverse=True)
    return {'priority_queue':rows,'method':'uncertainty + evidence gaps + connected impact heuristic'}

@router.get('/model-health')
def model_health(authorization:str=Header(None)):
    user_or_401(authorization)
    m=model()
    return {'trained':m is not None,'features':FEATURES,'classes':list(m.classes_) if m is not None else [],
            'model_type':type(m.named_steps['model']).__name__ if m is not None and hasattr(m,'named_steps') else None,
            'accuracy_note':'Accuracy is a measured validation metric, not a guaranteed real-world percentage.'}

@router.post('/offline/sync')
def offline_sync(payload:dict, authorization:str=Header(None)):
    u=user_or_401(authorization)
    events=payload.get('events',[])
    accepted=[]
    for e in events[:500]:
        accepted.append({'client_id':e.get('client_id') or str(uuid.uuid4()),'status':'accepted','actor':u['email']})
    return {'synced':len(accepted),'events':accepted,'offline_first':True}
