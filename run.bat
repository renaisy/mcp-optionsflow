@echo off
echo Starting OptionsFlow Platform...
echo.

echo Starting Backend Server...
start "Backend Server" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo Starting Frontend Server...
start "Frontend Server" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo OptionsFlow Platform is starting!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
pause
