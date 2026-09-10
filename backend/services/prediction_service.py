from pathlib import Path
import joblib
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "delay_risk_model.joblib"
def predict_risk(payload: dict):
    if MODEL_PATH.exists():
        return {"status": "model_available",
                "message": "Add production feature transformation matching the training pipeline."}
    return {"risk_score": 50, "delay_probability": 0.50,
            "risk_category": "MEDIUM",
            "top_reasons": ["Model not trained yet"],
            "recommendations": ["Train the model with ml/train_model.py"]}
