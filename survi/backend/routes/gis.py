from fastapi import APIRouter,Header,HTTPException
from backend.core import conn,current_user
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; GEO=ROOT/'data/coimbatore/19_gis_parcels.geojson'
router=APIRouter()
@router.get('/parcels')
def gis_parcels(authorization:str=Header(None),survey_no:str='',village:str='',limit:int=500):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 data=json.loads(GEO.read_text()) if GEO.exists() else {'type':'FeatureCollection','features':[]}; fs=data.get('features',[])
 def ok(f):
  p=f.get('properties',{}); return (not survey_no or str(p.get('survey_no','')).lower()==survey_no.lower()) and (not village or str(p.get('village','')).lower()==village.lower())
 fs=[f for f in fs if ok(f)][:min(limit,2000)]; return {'type':'FeatureCollection','features':fs,'source':'bundled demo GIS points; cadastral geometry not asserted as official'}
@router.get('/config')
def gis_config(authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 return {'tngis_portal':'https://tngis.tn.gov.in/apps.html','base_map':'OpenStreetMap','cadastral_notice':'Use TNGIS/authorized cadastral layers for legal parcel boundaries.'}
