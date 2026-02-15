# OptionsFlow Platform Startup Script for PowerShell

Write-Host "Starting OptionsFlow Platform..." -ForegroundColor Cyan
Write-Host ""

# Start backend server
Write-Host "Starting Backend Server..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

Start-Sleep -Seconds 3

# Start frontend server
Write-Host "Starting Frontend Server..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "OptionsFlow Platform is starting!" -ForegroundColor Cyan
Write-Host "Backend: " -NoNewline
Write-Host "http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend: " -NoNewline
Write-Host "http://localhost:5173" -ForegroundColor Yellow
Write-Host "API Docs: " -NoNewline
Write-Host "http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
