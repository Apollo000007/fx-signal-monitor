@echo off
setlocal
cd /d %~dp0
set "PATH=%ProgramFiles%\nodejs;%PATH%"

echo [Rebuild] Forcing clean Next.js build...
pushd frontend
if exist ".next" (
    rmdir /s /q .next
)
call npm run build
if errorlevel 1 (
    echo [Error] build failed
    popd
    pause
    exit /b 1
)
popd
echo [Rebuild] Done. Restart start.bat to run.
pause
endlocal
