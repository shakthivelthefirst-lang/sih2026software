from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.auth import router as auth_router
from backend.routes.projects import router as projects_router
from backend.routes.land_records import router as land_router
from backend.routes.ml import router as ml_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.gis import router as gis_router
from backend.routes.intelligence import router as intelligence_router
app=FastAPI(title='SURVI Land Acquisition Intelligence API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
app.include_router(auth_router,prefix='/auth',tags=['Authentication']); app.include_router(projects_router,prefix='/projects',tags=['Projects']); app.include_router(land_router,prefix='/land-records',tags=['Land Records']); app.include_router(ml_router,prefix='/ml',tags=['Machine Learning']); app.include_router(dashboard_router,prefix='/dashboard',tags=['Dashboard']); app.include_router(gis_router,prefix='/gis',tags=['GIS']); app.include_router(intelligence_router,prefix='/intelligence',tags=['Intelligence'])
@app.get('/')
def root(): return {'name':'SURVI','status':'running','version':'1.0.0'}
@app.get('/health')
def health(): return {'status':'ok'}
