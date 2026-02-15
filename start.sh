#!/bin/bash

echo "Starting OptionsFlow Platform..."
echo ""

# Start backend server
echo "Starting Backend Server..."
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'\" && python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"'

sleep 3

# Start frontend server
echo "Starting Frontend Server..."
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'/frontend\" && npm run dev"'

echo ""
echo "OptionsFlow Platform is starting!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo ""
