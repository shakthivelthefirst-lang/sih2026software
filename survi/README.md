# SURVI LANDNEXUS — Multimodal Land Acquisition Intelligence

The application name **SURVI LANDNEXUS** is preserved from the supplied package.

## What is included
- Permanent authority account: `Tngov@cbe.ac.in`
- Role-based authentication and authority user management
- Land Digital Twin / parcel records and validation
- Coimbatore demo datasets already bundled
- ML risk prediction, seven-stage risk and SHAP explanation
- Model versioning and retraining
- Risk trajectory
- Diagnostic uncertainty interval
- Satellite-change evidence endpoint (indicator-based prototype)
- Citizen objection workflow
- Field verification workflow
- Compensation valuation anomaly review
- Conflict graph
- Active-learning verification-priority endpoint
- Acquisition route/decision simulator
- Acquisition pre-mortem
- Tamper-evident hash-linked evidence ledger
- Factual parcel evidence report
- Document upload/OCR integration point
- GIS map with clear demo-data disclaimer

## Run on Windows
1. Install Python 3.10+ and Node.js LTS.
2. Open a terminal in the `survi` folder.
3. `python -m pip install -r backend/requirements.txt`
4. `python -m ml.train_model`
5. Double-click `run_backend.bat`.
6. In another terminal, `cd frontend && npm install && npm run dev`.
7. Open the Vite URL shown in the terminal.

Or use the supplied batch files.

## Demo login
Email: `Tngov@cbe.ac.in`
Password: `Tngov@CBE#2026`

Change the demo password and application secret before any real deployment.

## Important accuracy note
No responsible software can guarantee 100% real-world ML prediction accuracy. The app is engineered for deterministic validation, consistent calculations, reproducible model training, auditability and demonstrable end-to-end functionality. The bundled ML accuracy is an evaluation metric on the available training/test data, not a guarantee about unseen government land-acquisition events.

## Data / legal note
The bundled GIS points are demo locations and are not authoritative cadastral boundaries. Satellite change is reported as a potential change requiring verification. Compensation output is an anomaly requiring review, not a legal or corruption finding. Generated reports are factual evidence summaries, not legal advice or legal judgments.

## Feature status
Core SIH MVP features are implemented locally. Advanced production integrations (authorized live satellite feeds, government cadastral APIs, production OCR engines, SMS gateways, and a trained national labelled dataset) require their respective authorized data/services and credentials.


## Final implementation coverage (2026-09-07)
The prototype includes multimodal fusion, uncertainty/data-quality diagnostics, conflict clustering, active verification prioritization, field feedback capture, offline-first PWA shell, route simulation, pre-mortem, OCR integration, satellite-change analysis, valuation anomaly review, evidence ledger and factual reporting. The ML validation accuracy is measured on the supplied dataset; no honest software can guarantee 100% real-world ML accuracy. Current hold-out validation: 94.125%.
