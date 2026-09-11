
from fastapi import APIRouter,HTTPException,Header
from backend.core import current_user,conn,audit
from datetime import date
router=APIRouter(); STAGES=["Proposal","Scrutiny","Approval","Notification","Survey","Award","Compensation","Legal Dispute / Resolution","Rehabilitation & Resettlement","Possession","Closure / Completion"]
WORKFLOW_STAGES=["Proposal","SIA / Survey","Notification","Legal Dispute / Resolution","Approval","Award","Compensation","Possession","Rehabilitation","Closure / Completion"]
WORKFLOW_LABELS={"Proposal":"Proposal","SIA / Survey":"SIA / Survey","Notification":"Notification","Legal Dispute / Resolution":"Objections","Approval":"Approval","Award":"Award","Compensation":"Compensation","Possession":"Possession","Rehabilitation":"Rehabilitation","Closure / Completion":"Completed"}
CURRENT_STAGE_ALIASES={"Survey":"SIA / Survey","Rehabilitation & Resettlement":"Rehabilitation"}
TRANSITION_ALERTS={"SIA / Survey":"Acquisition Survey Started","Notification":"Land Acquisition Notification Stage Started","Legal Dispute / Resolution":"Objection Period Started","Approval":"Project Awaiting Approval","Award":"Land Acquisition Award Issued","Compensation":"Compensation Process Started","Possession":"Land Possession Stage Started","Rehabilitation":"Rehabilitation / R&R Stage Started","Closure / Completion":"Land Acquisition Completed"}
def guard(a,roles=("authority","admin","acquisition_officer","district_authority")):
 u=current_user(a)
 if not u or u["role"] not in roles: raise HTTPException(403,"Insufficient permissions")
 return u

def _notification_target(c, actor, district):
 role="district_authority" if actor["role"] in ("state_authority","authority","admin") else "state_authority"
 users=c.execute("SELECT email FROM users WHERE role=? AND active=1 ORDER BY id",(role,)).fetchall()
 return next((r["email"] for r in users if district and district.lower() in r["email"].lower()), users[0]["email"] if users else None)

def _transition(project_id, next_stage, authorization):
 u=guard(authorization, roles=("district_authority","authority","admin","acquisition_officer"))
 if next_stage not in WORKFLOW_STAGES: raise HTTPException(422,"Invalid acquisition stage")
 c=conn(); project=c.execute("SELECT * FROM projects WHERE project_id=?",(project_id,)).fetchone()
 if not project: c.close(); raise HTTPException(404,"Project not found")
 current=CURRENT_STAGE_ALIASES.get(project["current_stage"],project["current_stage"]); current_idx=WORKFLOW_STAGES.index(current) if current in WORKFLOW_STAGES else -1; next_idx=WORKFLOW_STAGES.index(next_stage)
 if current_idx < 0: c.close(); raise HTTPException(409,f"Current project stage {project['current_stage']} is not in the acquisition lifecycle")
 if next_idx != current_idx+1:
  required=WORKFLOW_LABELS[WORKFLOW_STAGES[current_idx+1]] if current_idx+1 < len(WORKFLOW_STAGES) else None
  message=f"Cannot move project from {WORKFLOW_LABELS[current]} directly to {WORKFLOW_LABELS[next_stage]}." if not required else f"Cannot move project from {WORKFLOW_LABELS[current]} directly to {WORKFLOW_LABELS[next_stage]}. Complete {required} first."
  c.close(); raise HTTPException(409,message)
 if current=="Proposal" and next_stage=="SIA / Survey":
  pending=c.execute("""SELECT COUNT(1) FROM parcels p LEFT JOIN field_assignments a ON a.parcel_id=p.id AND a.status='Verified' WHERE p.project_id=? AND a.id IS NULL""",(project_id,)).fetchone()[0]
  if pending: c.close(); raise HTTPException(409,f"{pending} linked parcel(s) are still pending field verification.")
 current_row=c.execute("SELECT id FROM project_milestones WHERE project_id=? AND stage=? ORDER BY id LIMIT 1",(project_id,current)).fetchone()
 if current_row: c.execute("UPDATE project_milestones SET status='Completed',actual_date=COALESCE(actual_date,date('now')),responsible_officer=COALESCE(responsible_officer,?),updated_at=CURRENT_TIMESTAMP WHERE id=?",(u["email"],current_row["id"]))
 else: c.execute("INSERT INTO project_milestones(project_id,stage,status,actual_date,responsible_officer) VALUES(?,?, 'Completed',date('now'),?)",(project_id,current,u["email"]))
 next_row=c.execute("SELECT id FROM project_milestones WHERE project_id=? AND stage=? ORDER BY id LIMIT 1",(project_id,next_stage)).fetchone()
 if next_row: c.execute("UPDATE project_milestones SET status='In Progress',planned_date=COALESCE(planned_date,date('now')),expected_date=COALESCE(expected_date,date('now','+30 day')),responsible_officer=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(u["email"],next_row["id"]))
 else: c.execute("INSERT INTO project_milestones(project_id,stage,status,planned_date,expected_date,responsible_officer) VALUES(?,?, 'In Progress',date('now'),date('now','+30 day'),?)",(project_id,next_stage,u["email"]))
 progress=round((next_idx/(len(WORKFLOW_STAGES)-1))*100,1); status="Completed" if next_stage=="Closure / Completion" else "Active"; c.execute("UPDATE projects SET current_stage=?,project_status=?,progress=?,last_updated=CURRENT_TIMESTAMP WHERE project_id=?",(next_stage,status,progress,project_id)); c.execute("UPDATE parcels SET acquisition_status=?,last_updated=CURRENT_TIMESTAMP WHERE project_id=?",(WORKFLOW_LABELS[next_stage],project_id))
 alert_id=None; target=_notification_target(c,u,project["district"])
 if target:
  import uuid
  alert_id="ALT-"+uuid.uuid4().hex[:10].upper(); c.execute("INSERT INTO alerts(alert_id,project_id,type,severity,trigger,message,recommended_action,assigned_to,status) VALUES(?,?,?,?,?,?,?,?,?)",(alert_id,project_id,TRANSITION_ALERTS[next_stage],"INFO",u["role"],f"{project['project_name']} moved to {WORKFLOW_LABELS[next_stage]}.",f"Review {WORKFLOW_LABELS[next_stage]} stage",target,"Open"))
 c.commit(); c.close(); audit(u["email"],"WORKFLOW_TRANSITION","project",project_id,new_value=next_stage); return {"message":"Workflow transition completed","project_id":project_id,"previous_stage":current,"current_stage":next_stage,"current_stage_label":WORKFLOW_LABELS[next_stage],"progress":progress,"project_status":status,"alert_id":alert_id}
@router.get("/")
def list_projects(authorization:str=Header(None),limit:int=100,offset:int=0):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 c=conn(); rows=[dict(r) for r in c.execute("SELECT * FROM projects ORDER BY rowid DESC LIMIT ? OFFSET ?",(min(limit,500),offset)).fetchall()]; c.close(); return {"items":rows,"count":len(rows)}
@router.get("/{project_id}")
def get_project(project_id:str,authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 c=conn(); r=c.execute("SELECT * FROM projects WHERE project_id=?",(project_id,)).fetchone()
 if not r: c.close(); raise HTTPException(404,"Project not found")
 d=dict(r); d["workflow"]=[dict(x) for x in c.execute("SELECT * FROM project_milestones WHERE project_id=? ORDER BY id",(project_id,)).fetchall()]; d["parcels"]=[dict(x) for x in c.execute("""
  SELECT p.*, COALESCE(f.assignment_status, 'Not Assigned') AS assignment_status,
    COALESCE(f.verified_count, 0) AS verification_count
  FROM parcels p LEFT JOIN (
   SELECT a.parcel_id, a.status assignment_status,
     SUM(CASE WHEN a.status='Verified' THEN 1 ELSE 0 END) verified_count
   FROM field_assignments a GROUP BY a.parcel_id
  ) f ON f.parcel_id=p.id
  WHERE p.project_id=? ORDER BY p.id DESC LIMIT 500
 """,(project_id,)).fetchall()]; d["linked_parcel_count"]=len(d["parcels"]); d["linked_land_area"]=round(sum(float(p.get("area") or 0) for p in d["parcels"]),2); d["verified_parcel_count"]=sum(1 for p in d["parcels"] if p.get("assignment_status")=="Verified"); d["pending_verification_count"]=sum(1 for p in d["parcels"] if p.get("assignment_status")=="Pending Verification"); risk_order={"CRITICAL":4,"HIGH":3,"MEDIUM":2,"LOW":1}; risks=[p.get("risk_category") for p in d["parcels"] if p.get("risk_category")]; d["project_risk"]=max(risks,key=lambda x:risk_order.get(x,0)) if risks else "N/A"; c.close(); return d

@router.get("/{project_id}/parcels")
@router.get("/{project_id}/parcels/map")
def get_project_parcels(project_id:str,format:str=None,authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,"Authentication required")
 c=conn(); project=c.execute("SELECT project_id,project_name,current_stage,project_status FROM projects WHERE project_id=?",(project_id,)).fetchone()
 if not project: c.close(); raise HTTPException(404,"Project not found")
 # SQL query converting spatial polygons to GeoJSON:
 #   SELECT 
 #       p.id AS parcel_id,
 #       p.survey_number AS survey_no,
 #       COALESCE(p.locality, p.revenue_village, p.village) AS specific_area,
 #       p.village,
 #       p.area,
 #       p.stage,
 #       p.is_acquired,
 #       ST_AsGeoJSON(p.geom)::json AS geometry,
 #       ST_Y(ST_Centroid(p.geom)) AS latitude,
 #       ST_X(ST_Centroid(p.geom)) AS longitude
 #   FROM parcels p
 #   WHERE p.project_id = $1;
 rows=[dict(r) for r in c.execute("""
  SELECT 
    p.id AS parcel_id,
    COALESCE(p.survey_number, p.survey_no) AS survey_no,
    COALESCE(p.locality, p.revenue_village, p.village) AS specific_area,
    p.village,
    p.area,
    COALESCE(p.stage, p.acquisition_status) AS stage,
    p.is_acquired,
    ST_AsGeoJSON(p.geom) AS geometry,
    ST_Y(ST_Centroid(p.geom)) AS latitude,
    ST_X(ST_Centroid(p.geom)) AS longitude,
    p.project_id,
    p.subdivision,
    p.taluk,
    p.district,
    p.area_unit,
    p.acquisition_status
  FROM parcels p
  WHERE p.project_id=?
  ORDER BY p.id ASC
 """,(project_id,)).fetchall()]
 c.close()
 VILLAGE_COORDINATES = {
  "sulur": (11.0245, 77.1256),
  "pollachi": (10.6609, 77.0048),
  "mettupalayam": (11.3000, 76.9400),
  "coimbatore north": (11.0300, 76.9500),
  "coimbatore south": (10.9800, 76.9600),
  "madukkarai": (10.9021, 76.9612),
  "kinathukadavu": (10.8200, 77.0200),
  "perur": (10.9700, 76.9200),
  "annur": (11.2300, 77.1800),
  "karamadai": (11.2400, 76.9600),
  "thondamuthur": (10.9900, 76.8300),
  "singanallur": (11.0000, 77.0200),
  "saravanampatti": (11.0800, 76.9900),
  "kovilpalayam": (11.1400, 77.0400),
  "negamam": (10.7800, 77.0900),
  "valparai": (10.3200, 76.9500),
  "irugur": (11.0100, 77.0600),
  "kalapatti": (11.0700, 77.0300),
  "vadavalli": (11.0200, 76.9000),
  "peelamedu": (11.0300, 77.0000),
 }
 import json, math
 seen_coords=set()
 formatted=[]
 for i, r in enumerate(rows):
  lat=r.get("latitude")
  lon=r.get("longitude")
  if lat is not None and lon is not None:
   try: lat=float(lat); lon=float(lon)
   except: lat,lon=None,None
  v_name=str(r.get("village") or r.get("taluk") or "").strip().lower()
  if lat is None or lon is None or (v_name=="sulur" and lat < 10.9):
   if v_name in VILLAGE_COORDINATES:
    base_lat, base_lon = VILLAGE_COORDINATES[v_name]
    lat, lon = base_lat + (i * 0.002), base_lon + (i * 0.002)
   else:
    lat, lon = 11.0168 + (i * 0.003), 76.9558 + (i * 0.003)
  elif (round(lat,5),round(lon,5)) in seen_coords:
   offset=0.002*(i+1)
   lat=lat+(offset if i%2==0 else -offset)
   lon=lon+(offset if i%3==0 else -offset)
  seen_coords.add((round(lat,5),round(lon,5)))

  raw_geom=r.get("geometry")
  geom_obj=None
  if raw_geom:
   try: geom_obj=json.loads(raw_geom) if isinstance(raw_geom, str) else raw_geom
   except: geom_obj=None

  if not geom_obj or geom_obj.get("type") != "Polygon":
   area_val=float(r.get("area") or 1.0)
   side_m=math.sqrt(max(area_val, 0.1) * 4046.86)
   d_lat=max(min((side_m / 111000.0) / 2.0, 0.003), 0.0003)
   d_lon=max(min((side_m / (111000.0 * max(math.cos(math.radians(lat)), 0.1))) / 2.0, 0.003), 0.0003)
   geom_obj={
    "type": "Polygon",
    "coordinates": [[
     [round(lon - d_lon, 6), round(lat - d_lat, 6)],
     [round(lon + d_lon, 6), round(lat - d_lat, 6)],
     [round(lon + d_lon, 6), round(lat + d_lat, 6)],
     [round(lon - d_lon, 6), round(lat + d_lat, 6)],
     [round(lon - d_lon, 6), round(lat - d_lat, 6)]
    ]]
   }

  st_val=str(r.get("stage") or r.get("acquisition_status") or "").strip().upper()
  if st_val in ("NOT ACQUIRED","NOT_ACQUIRED","PENDING","PROPOSAL","OPEN"):
   is_acq=False
  else:
   is_acq=bool(r.get("is_acquired")) if r.get("is_acquired") is not None else (st_val in ("ACQUIRED","COMPLETED","POSSESSION","PAID","ON TRACK","CLOSED","VERIFIED"))
  
  status_str="ACQUIRED" if is_acq else "NOT ACQUIRED"
  record={
   "parcel_id":r["parcel_id"],
   "survey_no":r.get("survey_no") or "N/A",
   "specific_area":r.get("specific_area") or r.get("village") or "",
   "village":r.get("village") or "",
   "area":float(r.get("area") or 0.0),
   "stage":status_str,
   "is_acquired":is_acq,
   "geometry":geom_obj,
   "latitude":float(lat),
   "longitude":float(lon),
   "id":r["parcel_id"],
   "project_id":r.get("project_id") or project_id,
   "subdivision":r.get("subdivision") or "",
   "taluk":r.get("taluk") or "",
   "district":r.get("district") or "",
   "area_unit":r.get("area_unit") or "acres",
   "acquisition_status":status_str,
   "raw_status":status_str,
   "normalized_status":status_str,
   "type":"Feature",
   "properties":{
    "parcel_id":r["parcel_id"],
    "survey_no":r.get("survey_no") or "N/A",
    "specific_area":r.get("specific_area") or r.get("village") or "",
    "village":r.get("village") or "",
    "area":float(r.get("area") or 0.0),
    "stage":status_str,
    "is_acquired":is_acq,
    "project_id":r.get("project_id") or project_id,
    "acquisition_status":status_str,
    "latitude":float(lat),
    "longitude":float(lon)
   }
  }
  formatted.append(record)
 if format and str(format).strip().lower() in ("geojson","featurecollection"):
  return {"type":"FeatureCollection","features":formatted}
 return formatted


@router.post("/{project_id}/parcels/{parcel_id}")
def link_parcel(project_id:str, parcel_id:int, authorization:str=Header(None)):
 u=guard(authorization, roles=("district_authority","authority","admin"))
 c=conn(); project=c.execute("SELECT project_id FROM projects WHERE project_id=?",(str(project_id),)).fetchone(); parcel=c.execute("SELECT id,project_id FROM parcels WHERE id=?",(parcel_id,)).fetchone()
 if not project: c.close(); raise HTTPException(404,"Project not found")
 if not parcel: c.close(); raise HTTPException(404,"Parcel not found")
 if parcel["project_id"]==str(project_id): c.close(); raise HTTPException(409,"Parcel is already linked to this project.")
 c.execute("UPDATE parcels SET project_id=?,last_updated=CURRENT_TIMESTAMP WHERE id=?",(str(project_id),parcel_id)); c.commit(); c.close(); audit(u["email"],"LINK_PARCEL_TO_PROJECT","parcel",parcel_id,new_value=str(project_id)); return {"message":"Parcel linked to project","project_id":str(project_id),"parcel_id":parcel_id}
import uuid

@router.post("/")
def create_project(p:dict,authorization:str=Header(None)):
 u=guard(authorization, roles=("authority","admin","state_authority","acquisition_officer"))
 req=["project_id","project_name","project_type","district","taluk"]; miss=[x for x in req if not p.get(x)]
 if miss: raise HTTPException(400,{"missing_fields":miss})
 p["current_stage"] = "Proposal"
 p["progress"] = 0
 c=conn()
 try:
  c.execute("""INSERT INTO projects(project_id,project_name,project_type,department,authority,district,taluk,village,description,priority,land_required,number_of_parcels,affected_parcels,affected_families,estimated_project_cost,estimated_land_cost,project_start_date,planned_completion_date,current_stage,project_status,progress,responsible_officer) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
  [p.get(k, "") for k in ["project_id","project_name","project_type","department","authority","district","taluk","village","description","priority","land_required","number_of_parcels","affected_parcels","affected_families","estimated_project_cost","estimated_land_cost","project_start_date","planned_completion_date","current_stage","project_status","progress","responsible_officer"]])
  for s in STAGES: c.execute("INSERT INTO project_milestones(project_id,stage) VALUES(?,?)",(p["project_id"],s))
  c.execute("UPDATE project_milestones SET status='In Progress',planned_date=date('now'),expected_date=date('now','+30 day') WHERE project_id=? AND stage='Proposal'",(p["project_id"],))
  
  # Create district notification
  aid="ALT-"+uuid.uuid4().hex[:10].upper()
  assigned_to = _notification_target(c,u,p.get("district"))
  msg = f"{p.get('project_name')} has been created by State Authority."
  c.execute("INSERT INTO alerts(alert_id,project_id,type,severity,trigger,message,assigned_to,status) VALUES(?,?,?,?,?,?,?,?)",
    (aid, p.get("project_id"), "New Project Created", "INFO", "State Authority", msg, assigned_to, "Open"))
  c.commit()
 except Exception as e:
  c.rollback(); c.close(); raise HTTPException(400,f"Unable to create project; project_id may already exist. {str(e)}")
 c.close(); audit(u["email"],"CREATE_PROJECT","project",p["project_id"]); return {"message":"Project created","project_id":p["project_id"]}
@router.patch("/{project_id}")
def edit_project(project_id:str,p:dict,authorization:str=Header(None)):
 u=guard(authorization); allowed=["project_name","priority","description","current_stage","project_status","progress","responsible_officer","planned_completion_date","actual_completion_date"]
 sets=[k+"=?" for k in allowed if k in p]; args=[p[k] for k in allowed if k in p]
 if not sets: raise HTTPException(400,"No supported fields")
 c=conn(); args.append(project_id); cur=c.execute("UPDATE projects SET "+",".join(sets)+",last_updated=CURRENT_TIMESTAMP WHERE project_id=?",args); c.commit(); c.close()
 if not cur.rowcount: raise HTTPException(404,"Project not found")
 audit(u["email"],"EDIT_PROJECT","project",project_id,new_value=str(p)); return {"message":"Project updated"}
@router.post("/{project_id}/workflow/transition")
def transition(project_id:str,p:dict,authorization:str=Header(None)):
 return _transition(project_id,p.get("next_stage") or p.get("stage"),authorization)
@router.put("/{project_id}/workflow/{stage}")
def update_workflow(project_id:str,stage:str,payload:dict,authorization:str=Header(None)):
 return _transition(project_id,stage,authorization)
