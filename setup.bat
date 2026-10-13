@echo off
REM ============================================================
REM  InternAI - one-time setup for Windows
REM  Needs: Python 3.11 (python on PATH) and Node.js 18+ (npm)
REM ============================================================
setlocal
cd /d "%~dp0backend"

echo [1/7] Creating Python virtual environment...
if not exist .venv ( python -m venv .venv || goto :error )
call .venv\Scripts\activate.bat || goto :error

echo [2/7] Installing Python packages (first time takes a few minutes)...
python -m pip install --upgrade pip || goto :error
pip install -r requirements.txt || goto :error

echo [3/7] Downloading spaCy English model...
python -m spacy download en_core_web_sm || goto :error

echo [4/7] Building + validating the skills/jobs/courses catalog...
python -m app.ml.build_courses || goto :error
python -m app.ml.validate_catalog || goto :error

echo [5/7] Generating 5,400 synthetic resumes...
python -m app.ml.generate_data || goto :error

echo [6/7] Training models (downloads all-MiniLM-L6-v2 once, ~90 MB)...
python -m app.ml.train || goto :error

echo [7/7] Installing frontend packages...
cd /d "%~dp0frontend"
call npm install || goto :error

echo.
echo Setup complete!  Run start.bat to launch InternAI.
exit /b 0

:error
echo.
echo Setup failed at the step above. Fix the error and run setup.bat again.
exit /b 1
