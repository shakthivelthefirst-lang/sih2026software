
from fastapi import APIRouter,Header,HTTPException
from backend.core import current_user,conn
import json
from pathlib import Path
router=APIRouter(); GEO=Path(__file__).resolve().parents[2]/"data/coimbatore/19_gis_parcels.geojson"
@router.get("/parcels")
def gis_parcels(authorization:str=Header(None),survey_no:str="",village:str="",district:str="",risk_category:str="",limit:int=500):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 data=json.loads(GEO.read_text()) if GEO.exists() else {"type":"FeatureCollection","features":[]}; fs=data.get("features",[])
 def ok(f):
  p=f.get("properties",{}); return all(not x or str(p.get(k,"")).lower()==x.lower() for k,x in [("survey_no",survey_no),("village",village),("district",district),("risk_category",risk_category)])
 return {"type":"FeatureCollection","features":[f for f in fs if ok(f)][:min(max(limit,1),2000)],"source_classification":"SYNTHETIC DEMO POINTS","cadastral_geometry":False,"disclaimer":"Coordinates are synthetic demonstration points, not official cadastral boundaries."}
@router.get("/config")
def gis_config(authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 return {"base_map":"OpenStreetMap","source_classification":"SYNTHETIC DEMO","authorized_cadastral_adapter":True,"tngis_portal":"https://tngis.tn.gov.in/apps.html"}
