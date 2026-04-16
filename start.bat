@echo off
REM ────────────────────────────────────────────────────────────
REM simple_demo 一鍵啟動（Windows）
REM   只有一個 server：http://localhost:5488/
REM     - /            → index.html（前端）
REM     - /api/*       → FastAPI
REM ────────────────────────────────────────────────────────────

setlocal
cd /d "%~dp0"

REM 啟動 backend（serve 前端 + API）
start "simple_demo" cmd /k "cd backend && python -m uvicorn app.main:app --port 5488"

REM 等一下再開瀏覽器
timeout /t 2 /nobreak >nul
start http://localhost:5488/

echo.
echo  simple_demo launching.
echo    UI + API: http://localhost:5488/
echo.
endlocal
