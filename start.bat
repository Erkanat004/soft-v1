@echo off
title StoryForge AI Launcher

echo ========================================================
echo                 StoryForge AI Engine
echo ========================================================
echo Checking ports & launching application...

cd /d "%~dp0"

:: Kill any leftover processes on port 8000 or 5173 to prevent WinError 10013
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTEN') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTEN') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Starting FastAPI Backend...
start "StoryForge Backend (FastAPI)" cmd /k "cd backend && .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting React Frontend...
start "StoryForge Frontend (Vite)" cmd /k "cd frontend && npm run dev"



echo.
echo StoryForge AI is running!
echo Web Interface: http://localhost:5173
echo API Backend:   http://127.0.0.1:8000/docs
echo ========================================================
