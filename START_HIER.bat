@echo off
cd /d "%~dp0"

if exist "Moodler.exe" (
    start "" "Moodler.exe"
    exit /b
)

if exist "dist\Moodler\Moodler.exe" (
    start "" "dist\Moodler\Moodler.exe"
    exit /b
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
    exit /b
)

where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw main.py
    exit /b
)

where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 main.py
    exit /b
)

python main.py
