from pathlib import Path
import pandas as pd, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.core import conn
from backend.services.ml_service import predict
ROOT=Path(__file__).resolve().parents[1]
land=pd.read_csv(ROOT/"data/coimbatore/01_land_records.csv")
ml=pd.read_csv(ROOT/"data/coimbatore/18_ml_training_features.csv")
c=conn()
for i,r in land.head(1000).iterrows():
    if c.execute("SELECT 1 FROM parcels WHERE record_id=?",(str(r.record_id),)).fetchone(): continue
    mf=ml.iloc[i % len(ml)].to_dict()
    try: pred=predict(mf)
    except: pred={"risk_category":str(mf.get("delay_risk_label","LOW")),"risk_probability":float(mf.get("delay_probability",0)),"risk_score":float(mf.get("risk_score",0))}
    c.execute("""INSERT OR IGNORE INTO parcels(record_id,survey_no,subdivision,village,taluk,district,area,classification,project_id,latitude,longitude,validation_status,risk_category,risk_probability,risk_score,delay_probability,training_label,created_by)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (str(r.record_id),str(r.survey_no),str(r.subdivision),r.village,r.taluk,r.district,float(r.area),r.classification,str(mf['project_id']),11.0168+(i%20)*.001,76.9558+(i%20)*.001,"VALID",pred["risk_category"],pred["risk_probability"],pred["risk_score"],pred["risk_probability"],str(mf['delay_risk_label']),"demo-seed"))
c.commit(); c.close(); print("Seeded demo parcels:",len(land.head(1000)))
