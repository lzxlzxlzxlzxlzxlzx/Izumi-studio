@echo off
chcp 65001 >nul
set PORT=8004

:: Find and kill any process on target port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr LISTEN') do (
    echo [run] Port %PORT% is in use by PID %%a, killing...
    taskkill /F /PID %%a >nul 2>&1
    timeout /t 2 /nobreak >nul
)

cd /d "%~dp0"
echo [run] Starting uvicorn on port %PORT%...
start /B "" python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% --log-level info > ..\data\logs\backend.log 2>&1

timeout /t 3 /nobreak >nul
echo [run] Backend started. Check ..\data\logs\backend.log for status.
