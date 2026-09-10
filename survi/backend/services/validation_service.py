def validate_land_record(r):
 required=['survey_no','subdivision','village','taluk','district','area','classification']
 errors=[f for f in required if r.get(f) in (None,'')]
 try:
  if float(r.get('area',0))<=0: errors.append('area must be > 0')
  lat=float(r.get('latitude',0)); lon=float(r.get('longitude',0))
  if not (-90<=lat<=90 and -180<=lon<=180): errors.append('invalid GPS')
 except: errors.append('area/GPS must be numeric')
 return {'valid':not errors,'errors':errors,'validation_status':'VALID' if not errors else 'INVALID'}
