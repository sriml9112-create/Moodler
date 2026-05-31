@echo off
setlocal
cd /d "%~dp0"

call build_app.bat
if errorlevel 1 exit /b 1

if exist "dist\Moodler-portable.zip" del /Q "dist\Moodler-portable.zip"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_portable.ps1"
if errorlevel 1 exit /b 1

echo Done: dist\Moodler-portable.zip
endlocal
