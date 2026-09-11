from pathlib import Path
import pandas as pd, joblib, json, shutil, time
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
ROOT=Path(__file__).resolve().parents[2]; DATA=ROOT/'data/coimbatore/18_ml_training_features.csv'; MODEL_DIR=ROOT/'models'; DATA.parent.mkdir(exist_ok=True); MODEL_DIR.mkdir(exist_ok=True)
FEATURES=['project_type','land_required','affected_parcels','affected_families','legal_disputes','compensation_pending','approval_pending','documentation_pending','rehabilitation_pending','notification_pending','award_pending','possession_pending','stakeholder_responsiveness','environmental_risk','weather_risk']; TARGET='delay_risk_label'
def train_new():
 df=pd.read_csv(DATA, low_memory=False); df=df.dropna(subset=[TARGET]); X=df[FEATURES].copy(); y=df[TARGET].astype(str).str.upper(); num=[c for c in FEATURES if c!='project_type']; X[num]=X[num].apply(pd.to_numeric,errors='coerce'); cat=['project_type']; X['project_type']=X['project_type'].astype(str)
 prep=ColumnTransformer([('num',SimpleImputer(strategy='median'),num),('cat',Pipeline([('imp',SimpleImputer(strategy='most_frequent')),('oh',OneHotEncoder(handle_unknown='ignore'))]),cat)])
 pipe=Pipeline([('preprocessor',prep),('model',RandomForestClassifier(n_estimators=180,random_state=42,class_weight='balanced',n_jobs=-1))]); Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,random_state=42,stratify=y); pipe.fit(Xtr,ytr); acc=float(accuracy_score(yte,pipe.predict(Xte)))
 ts=time.strftime('%Y%m%d_%H%M%S'); version='v'+ts; path=MODEL_DIR/f'delay_risk_{version}.joblib'; joblib.dump(pipe,path); shutil.copy2(path,MODEL_DIR/'delay_risk_model.joblib'); meta={'version':version,'rows':len(df),'accuracy':acc,'features':FEATURES}; (MODEL_DIR/f'{version}.json').write_text(json.dumps(meta,indent=2)); return meta
def model():
 p=MODEL_DIR/'delay_risk_model.joblib'; return joblib.load(p) if p.exists() else None
def predict(features):
 m=model();
 if m is None: raise RuntimeError('Model not trained')
 X=pd.DataFrame([features])[FEATURES]; probs=m.predict_proba(X)[0]; classes=list(m.classes_); idx=int(probs.argmax()); label=str(classes[idx]); return {'risk_category':label,'risk_probability':float(probs[idx]),'risk_score':round(float(probs[idx])*100,2),'probabilities':{str(c):round(float(p),4) for c,p in zip(classes,probs)}}
