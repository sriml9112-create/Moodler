@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
if defined PYTHON_EXE set "PYTHON_CMD="%PYTHON_EXE%""
if not defined PYTHON_CMD if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=".venv\Scripts\python.exe""
if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo Python wurde nicht gefunden. Installiere Python oder setze PYTHON_EXE.
  exit /b 1
)

echo Installing requirements...
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if exist "dist\Moodler" rmdir /S /Q "dist\Moodler"

echo Building Moodler.exe...
%PYTHON_CMD% -m PyInstaller --noconfirm --clean --windowed --name Moodler --hidden-import google.genai --distpath dist --workpath build --specpath build main.py
if errorlevel 1 exit /b 1

if exist "dist\Moodler" (
  copy /Y README.md "dist\Moodler\README.md" >nul
  copy /Y .env.example "dist\Moodler\.env.example" >nul
)

echo Done: dist\Moodler\Moodler.exe
endlocal
