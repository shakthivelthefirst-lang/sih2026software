from fastapi import APIRouter
from services.prediction_service import predict_risk
router = APIRouter()
@router.post("/risk")
def risk_prediction(payload: dict):
    return predict_risk(payload)
