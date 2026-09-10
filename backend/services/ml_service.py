
from pathlib import Path
import pandas as pd, joblib, json, shutil, time
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score
ROOT=Path(__file__).resolve().parents[2]; DATA=ROOT/"data/coimbatore/18_ml_training_features.csv"; MODEL_DIR=ROOT/"models"
FEATURES=["project_type","land_required","affected_parcels","affected_families","legal_disputes","compensation_pending","approval_pending","documentation_pending","rehabilitation_pending","notification_pending","award_pending","possession_pending","stakeholder_responsiveness","environmental_risk","weather_risk"]; TARGET="delay_risk_label"
def build_pipeline():
    num=[c for c in FEATURES if c!="project_type"]
    prep=ColumnTransformer([("num",SimpleImputer(strategy="median"),num),("cat",Pipeline([("imp",SimpleImputer(strategy="most_frequent")),("oh",OneHotEncoder(handle_unknown="ignore"))]),["project_type"])])
    return Pipeline([("preprocessor",prep),("model",RandomForestClassifier(n_estimators=180,random_state=42,class_weight="balanced",n_jobs=-1))])
def sync_db_examples():
    try:
        from backend.core import conn
        c=conn(); rows=c.execute("SELECT features_json,label,delay_days FROM training_examples").fetchall(); c.close()
        if not rows: return
        df=pd.read_csv(DATA,low_memory=False)
        existing={(str(r.get("features_json","")),str(r.get("label",""))) for _,r in pd.DataFrame().iterrows()}
        additions=[]
        for r in rows:
            f=json.loads(r["features_json"]); f[TARGET]=r["label"]; f["delay_days"]=r["delay_days"]; additions.append(f)
        if additions:
            add=pd.DataFrame(additions)
            cols=df.columns.tolist()
            for col in cols:
                if col not in add: add[col]=""
            add=add[cols]
            # DB is source of persistent user-labelled examples; append only rows not already represented by identical feature+label.
            keys=set(zip(df.get("project_type",pd.Series(dtype=str)).astype(str),df.get(TARGET,pd.Series(dtype=str)).astype(str),df.get("delay_days",pd.Series(dtype=str)).astype(str)))
            add=add[~add.apply(lambda r:(str(r.get("project_type")),str(r.get(TARGET)),str(r.get("delay_days"))) in keys,axis=1)]
            if len(add): add.to_csv(DATA,mode="a",header=False,index=False)
    except Exception:
        pass
def train_new(allow_deploy=True, created_by="system"):
    sync_db_examples()
    df=pd.read_csv(DATA,low_memory=False).dropna(subset=[TARGET]); X=df[FEATURES].copy(); y=df[TARGET].astype(str).str.upper()
    for c in FEATURES:
        if c!="project_type": X[c]=pd.to_numeric(X[c],errors="coerce")
    X["project_type"]=X["project_type"].astype(str)
    if len(y)<8 or y.nunique()<2: raise ValueError("Training data needs at least 8 rows and 2 classes")
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,random_state=42,stratify=y)
    pipe=build_pipeline(); pipe.fit(Xtr,ytr); pred=pipe.predict(Xte)
    acc=float(accuracy_score(yte,pred)); pre=float(precision_score(yte,pred,average="weighted",zero_division=0)); rec=float(recall_score(yte,pred,average="weighted",zero_division=0)); f1=float(f1_score(yte,pred,average="weighted",zero_division=0))
    ts=time.strftime("%Y%m%d_%H%M%S"); version="v"+ts; path=MODEL_DIR/f"delay_risk_{version}.joblib"; joblib.dump(pipe,path)
    meta={"version":version,"rows":len(df),"validation_rows":len(yte),"accuracy":acc,"precision":pre,"recall":rec,"f1":f1,"features":FEATURES,"model_path":str(path.name),"status":"candidate","created_by":created_by}
    (MODEL_DIR/f"{version}.json").write_text(json.dumps(meta,indent=2))
    return meta
def model(): 
    p=MODEL_DIR/"delay_risk_model.joblib"; return joblib.load(p) if p.exists() else None
def predict(features):
    m=model()
    if m is None: raise RuntimeError("Model not trained")
    X=pd.DataFrame([features])
    for c in FEATURES:
        if c not in X: X[c]=0 if c!="project_type" else "Road"
        if c!="project_type": X[c]=pd.to_numeric(X[c],errors="coerce")
    X["project_type"]=X["project_type"].astype(str)
    probs=m.predict_proba(X[FEATURES])[0]; classes=list(m.classes_); idx=int(probs.argmax()); label=str(classes[idx])
    return {"risk_category":label,"risk_probability":float(probs[idx]),"risk_score":round(float(probs[idx])*100,2),"probabilities":{str(c):round(float(p),4) for c,p in zip(classes,probs)}}
