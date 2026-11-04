@echo off
setlocal
cd /d "%~dp0"
set "VENV=%~dp0..\.venv"
set "PY=%VENV%\Scripts\python.exe"
if not exist "%PY%" (
  echo Creating virtual environment...
  python -m venv "%VENV%" || goto :fail
)
echo.
echo [1/4] Updating pip so interrupted downloads can resume...
"%PY%" -m pip install --upgrade pip --timeout 120 --retries 10
echo.
echo [2/4] Installing bundled packages (no internet needed)...
if exist "wheels\*.whl" "%PY%" -m pip install --no-index --find-links wheels pypdf
echo.
echo [3/4] Installing packages (about 400 MB on a fresh setup). If it stops, just run this file again: finished packages are kept.
"%PY%" -m pip install -r requirements.txt --find-links wheels --timeout 120 --retries 20 --resume-retries 20
if errorlevel 1 "%PY%" -m pip install -r requirements.txt --find-links wheels --timeout 120 --retries 20
if errorlevel 1 goto :fail
echo.
echo [4/4] Starting PRAGYAAN at http://localhost:8501  (close this window to stop it)
start "" cmd /c "timeout /t 12 >/dev/null & start http://localhost:8501"
"%PY%" -m streamlit run app\Home.py --server.port 8501 --server.headless true
goto :eof
:fail
echo.
echo Install did not finish. Check your internet connection, then run this file again.
pause
