@echo off
setlocal
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
    echo Backend Python environment is missing. Install backend requirements first.
    pause
    exit /b 1
)
if not exist "frontend\dist\index.html" (
    echo Built frontend is missing. Run npm.cmd run build inside frontend first.
    pause
    exit /b 1
)

netstat -aon | findstr ":8000 " | findstr LISTEN >nul
if not errorlevel 1 (
    echo Port 8000 is already in use. Open the running app or close it manually.
    pause
    exit /b 1
)

echo StoryForge is starting locally at http://127.0.0.1:8000
echo Keep this window open while working. Press Ctrl+C to stop.
cd backend
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
endlocal
