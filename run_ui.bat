@echo off
cd /d "%~dp0"
echo Running MandirWiki preflight checks...
python self_test.py
if errorlevel 1 (
  echo.
  echo Preflight failed. Fix the error above before starting the UI.
  pause
  exit /b 1
)
echo.
echo Starting MandirWiki UI...
python -m streamlit run app.py
pause
