@echo off
setlocal
cd /d %~dp0

set "PATH=%ProgramFiles%\nodejs;%PATH%"

echo ============================================================
echo   FX Signal Monitor
echo ============================================================

REM --- Check python deps ---
py -c "import fastapi, yfinance, pandas" >nul 2>&1
if errorlevel 1 goto install_py
goto check_node

:install_py
echo [Setup] Installing Python packages...
py -m pip install --user -r requirements.txt
if errorlevel 1 goto fail_py

:check_node
if not exist "frontend\node_modules\next" goto install_node
goto check_build

:install_node
echo [Setup] Installing Node packages...
pushd frontend
call npm install
if errorlevel 1 goto fail_node
popd

:check_build
REM Always rebuild to pick up source changes. Next.js caches incremental
REM builds, so repeated runs are fast (only changed modules recompile).
echo [Setup] Building Next.js bundle (incremental)...
pushd frontend
call npm run build
if errorlevel 1 goto fail_build
popd

:run
echo.
echo Starting backend on http://127.0.0.1:8000
echo Starting frontend on http://localhost:3000
echo.

start "FX Signal Backend" cmd /k "cd /d %~dp0 && py -m uvicorn api:app --host 127.0.0.1 --port 8000"

REM small delay so backend boots first
ping -n 3 127.0.0.1 >nul

start "" "http://localhost:3000"

pushd frontend
call npm run start
popd
goto end

:fail_py
echo [Error] Python package install failed
pause
exit /b 1

:fail_node
echo [Error] npm install failed
popd
pause
exit /b 1

:fail_build
echo [Error] Next.js build failed
popd
pause
exit /b 1

:end
endlocal
