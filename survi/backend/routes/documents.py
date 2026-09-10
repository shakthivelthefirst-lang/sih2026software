from fastapi import APIRouter,Header,HTTPException
from backend.core import current_user
router=APIRouter()
@router.get('/')
def docs(authorization:str=Header(None)):
 if not current_user(authorization): raise HTTPException(401,'Authentication required')
 return {'message':'Evidence is uploaded against parcels via /land-records/{parcel_id}/evidence'}
