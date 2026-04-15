@echo off
REM ────────────────────────────────────────────────────────────
REM simple_demo 一鍵啟動（Windows）
REM   backend: http://127.0.0.1:5488  (FastAPI)
REM   frontend: http://localhost:5174 (Vite)
REM ────────────────────────────────────────────────────────────

setlocal
cd /d "%~dp0"

REM 1. 啟動後端（新視窗）
start "simple_demo backend" cmd /k "cd backend && python -m uvicorn app.main:app --port 5488 --reload"

REM 2. 啟動前端（新視窗）
start "simple_demo frontend" cmd /k "npm run dev"

echo.
echo Both servers launching in separate windows.
echo   Backend:  http://127.0.0.1:5488
echo   Frontend: http://localhost:5174
echo.
endlocal
