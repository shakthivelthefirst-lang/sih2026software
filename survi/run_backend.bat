@echo off
cd /d %~dp0
python -m ml.train_model
python -m uvicorn backend.main:app --reload
