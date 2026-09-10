# SURVI Architecture
React frontend → FastAPI → services → data/ML/OCR/GIS.
Land document → OCR → structured fields → validation → verified parcel → acquisition project → feature engineering → delay model → risk score → SHAP → recommendation → dashboard/GIS.
Core linkage: record_id → parcel_id → project_id → case_id / compensation_id / approval_id / delay_id.
PS 26018: OCR, multilingual extraction, confidence, human verification, validation.
PS 26017: risk score, delay probability, delay drivers, explainability, GIS, recommendations, alerts, continuous learning.
