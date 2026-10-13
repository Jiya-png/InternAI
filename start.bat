@echo off
REM Starts the API (port 8000) and the website (port 5173) in two windows.
cd /d "%~dp0"
start "InternAI backend" cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"
start "InternAI frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 6 >nul
start "" http://localhost:5173
