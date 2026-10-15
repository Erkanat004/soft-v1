@echo off
title StoryForge AI Launcher

echo ========================================================
echo                 StoryForge AI Engine
echo ========================================================
echo Checking ports & launching application...

cd /d "%~dp0"

:: Never kill unrelated applications or active generation jobs to claim a port.
for %%p in (8000 5173) do (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%%p " ^| findstr LISTEN') do (
        echo Port %%p is already in use by PID %%a. Close that application or use the running StoryForge instance.
        pause
        exit /b 1
    )
)

echo Starting FastAPI Backend...
start "StoryForge Backend (FastAPI)" cmd /k "cd backend && .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1"

echo Starting React Frontend...
start "StoryForge Frontend (Vite)" cmd /k "cd frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"



echo.
echo StoryForge AI is running!
echo Web Interface: http://localhost:5173
echo API Backend:   http://127.0.0.1:8000/docs
echo ========================================================
