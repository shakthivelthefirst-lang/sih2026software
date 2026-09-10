# SURVI / LANDNEXUS — SIH 26016 Prototype

## 1. Overview
LANDNEXUS is a parcel-centric Land Acquisition Intelligence Platform. SIH 26016 is the core acquisition-management backbone; predictive delay/risk intelligence, intelligent documents/OCR, geospatial intelligence, parcel-centric Land Stack architecture, and policy analytics are integrated layers rather than separate products.

**USP:** From Land Records to Land Acquisition — From Monitoring to Prediction — From Data to Decisions.

> Demo data is synthetic. It is not official government land, ownership, cadastral, compensation, or project data.

## 2. Architecture
`Land Record → Parcel → Project → Acquisition Workflow → Evidence/Documents → GIS → Risk Prediction → Explainable AI → Stage Risk → Corrective Action → Alerts → Officer Outcome → Verified Training Example → Retraining → Model Version → Audit → Analytics`

Backend: FastAPI + SQLite + scikit-learn + SHAP-compatible explanation service.
Frontend: React + Vite + Leaflet.
Storage: persistent SQLite database, uploaded document storage, versioned model files.

## 3. Main features
- Secure signed bearer-token authentication with PBKDF2 password hashing.
- Permanent protected TNGOV authority account.
- RBAC: Master Authority, Administrator, Acquisition Officer, Field Officer, Citizen.
- Projects and parcel management with validation and duplicate protection.
- Acquisition lifecycle and milestone tracking.
- Seven-stage risk intelligence.
- Supervised delay-risk model with categorical preprocessing and missing-value handling.
- Persistent verified training examples and retained model versions.
- Model acceptance gate; worse candidates are rejected and previous active model remains.
- SHAP explanation where compatible; fallback is explicitly labelled as feature importance.
- Corrective-action recommendations.
- Alerts center.
- Interactive Leaflet GIS using a legitimate basemap and bundled synthetic point layer.
- Document metadata and secure file upload.
- OCR adapter status endpoint; no false OCR-accuracy claims.
- Command Center, analytics, audit trail, citizen-safe status view.
- English/Tamil key navigation labels.
- Responsive field-officer-friendly web UI.
- `.env.example`, Windows scripts and local startup workflow.

## 4. Folder structure
```
backend/
  main.py
  core.py
  routes/
  services/
frontend/
  src/
ml/
models/
data/coimbatore/
tests/
docs/
scripts/
uploads/
README.md
.env.example
run_backend.bat
run_frontend.bat
start.bat
```

## 5. Installation — Windows beginner guide
Open PowerShell in the extracted project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm install
cd ..
```

Start backend:

```powershell
.\run_backend.bat
```

Start frontend in another terminal:

```powershell
.\run_frontend.bat
```

Open the Vite address shown by the frontend terminal, normally `http://localhost:5173`.

### Linux/macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
In another terminal:
```bash
cd frontend
npm run dev
```

## 6. Environment variables
Copy `.env.example` to `.env`.

- `JWT_SECRET` — signing secret; change before deployment.
- `TNGOV_DEMO_PASSWORD` — optional prototype authority password override.
- `MODEL_ACCEPTANCE_THRESHOLD` — minimum candidate accuracy (default `0.80`).
- `VITE_API_URL` — optional frontend backend URL.

Never commit `.env`, real API keys, cloud credentials or production passwords.

## 7. Database
The bundled `data/survi.db` is preserved and migrated at startup. New tables include training examples, model versions, documents, OCR extractions, alerts, risk records, spatial conflicts, field verifications and append-only audit logs.

For a clean prototype database, back up and remove `data/survi.db`, then start the backend. The application recreates its schema and seed authority account.

## 8. ML
The existing 100,000-row `18_ml_training_features.csv` is preserved. The model uses a preprocessing pipeline with numeric imputation and one-hot encoding for `project_type`, preventing categorical-to-float errors.

Run manually:
```bash
python -m ml.train_model
```

The application retraining endpoint:
`POST /ml/retrain`

Verified parcel labels are stored permanently in `training_examples`. Retraining synchronizes those verified examples into the training dataset. Every training run creates a new model file and database model-version record. A candidate is activated only if it meets the configurable quality gate; otherwise it is retained as rejected and the previous active model remains.

## 9. GIS
The bundled GeoJSON is explicitly classified as **SYNTHETIC DEMO POINTS**. It is not cadastral geometry. The map uses OpenStreetMap as a basemap. The API exposes an adapter/configuration boundary for authorized TNGIS/cadastral services.

No survey boundary, ULPIN, or government GIS integration is claimed.

## 10. OCR
Document upload is implemented with file-type and 10 MB size controls, generated safe storage names and SHA-256 hashes.

OCR is a modular adapter. If no local OCR engine is configured, the API reports that OCR is unavailable and requires human verification rather than pretending to have extracted data.

## 11. Demo credentials
Permanent authority:
- Email: `Tngov@cbe.ac.in`
- Demo password: `Tngov@CBE#2026`

The authority cannot be disabled, deleted, demoted or replaced through normal APIs.

Create additional demo users from **Users** after logging in as authority. Example safe prototype roles: `admin`, `acquisition_officer`, `field_officer`, `citizen`.

Change demo credentials and `JWT_SECRET` before any deployment beyond the local prototype.

## 12. API documentation
With backend running:
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`
- Health: `http://127.0.0.1:8000/health`

Core groups: `/auth`, `/projects`, `/land-records`, `/documents`, `/ocr`, `/gis`, `/ml`, `/alerts`, `/dashboard`, `/audit`, `/citizen`.

## 13. Tests
Backend syntax:
```bash
python -m compileall backend
```
Automated tests:
```bash
python -m pytest -q
```

Frontend:
```bash
cd frontend
npm install
npm run build
```

## 14. Data disclaimer
All bundled Coimbatore datasets are synthetic/correlated demonstration data. They must not be presented as official Tamil Nadu Government records. GIS coordinates are synthetic points in a broad Coimbatore-area envelope.

## 15. Production notes
For production, replace SQLite with PostgreSQL/PostGIS, use object storage for documents, connect only authorized government GIS/data services, enforce HTTPS, use a managed secret store, add refresh-token/session revocation, rate limiting, malware scanning, stronger audit infrastructure, background workers, observability and formal security review.

## 16. SIH 5–7 minute demonstration
1. Login as authority.
2. Open Command Center and show database-driven metrics.
3. Open GIS and explain synthetic-data boundary.
4. Open a parcel/risk view.
5. Generate overall risk, seven-stage risk and SHAP explanation.
6. Show corrective actions.
7. Create an alert and update its status.
8. Show Projects and acquisition workflow.
9. Show ML Monitoring and persistent verified training rows.
10. Retrain; show candidate metrics, model version and acceptance decision.
11. Show Audit Trail.
12. Open Citizen View and demonstrate restricted public-safe information.
13. Switch English/தமிழ்.

## 17. Troubleshooting
**401 Invalid credentials:** confirm the demo password and that the backend is using the same database.

**503 Model not trained:** run `python -m ml.train_model` once.

**Frontend cannot reach API:** make sure the backend is running on port 8000; optionally set `VITE_API_URL`.

**OCR unavailable:** this is an explicit optional-service state. Configure a local OCR engine before claiming extraction.

**Map tiles unavailable:** the application still loads its local synthetic GIS layer; internet is required for live OpenStreetMap tiles.

## 18. Quality / verification notes
The implementation preserves the existing datasets and model core while expanding the application around them. Backend compile/import, automated API smoke tests, project creation, parcel creation/validation/prediction, seven-stage risk, SHAP, GIS, dashboard, alerts and model retraining were executed in the build environment. A fresh-process restart check confirmed persistent training-example/model database state.

Frontend dependency installation/build could not be completed in the build environment because the npm installation did not finish within the available execution window; therefore this package does **not** falsely claim a completed `npm run build` in this environment. Run `npm install` and `npm run build` locally as part of final deployment validation.

## 19. Honesty rules
Never claim:
- synthetic data is government data;
- demo coordinates are official cadastral boundaries;
- OCR is 100% accurate;
- ML predictions are guaranteed;
- government APIs are connected unless verified;
- production deployment is complete unless tested.

Use labels: `SYNTHETIC`, `DEMO`, `PROTOTYPE`, and `AUTHORIZED EXTERNAL DATA`.
>>>>>>> d315df3 (Initial commit)
