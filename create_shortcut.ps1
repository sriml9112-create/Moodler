$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalExe = Join-Path $Root "Moodler.exe"
$BuiltExe = Join-Path $Root "dist\Moodler\Moodler.exe"
$Exe = if (Test-Path $LocalExe) { $LocalExe } else { $BuiltExe }
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Moodler.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)

if (Test-Path $Exe) {
    $Shortcut.TargetPath = $Exe
    $Shortcut.Arguments = ""
    $Shortcut.WorkingDirectory = Split-Path -Parent $Exe
} else {
    $LocalPythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"
    $LocalPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $LocalPythonw) {
        $Python = $LocalPythonw
    } elseif (Test-Path $LocalPython) {
        $Python = $LocalPython
    } else {
        $PythonCommand = Get-Command pythonw -ErrorAction SilentlyContinue
        if (-not $PythonCommand) {
            $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
        }
        if (-not $PythonCommand) {
            $PythonCommand = Get-Command py -ErrorAction SilentlyContinue
        }
        $Python = $PythonCommand.Source
    }
    if (-not $Python) {
        Write-Host "Python wurde nicht gefunden. Baue zuerst die EXE mit build_app.bat oder installiere Python."
        exit 1
    }
    $Shortcut.TargetPath = $Python
    if ((Split-Path -Leaf $Python) -ieq "py.exe") {
        $Shortcut.Arguments = "-3 `"$Root\main.py`""
    } else {
        $Shortcut.Arguments = "`"$Root\main.py`""
    }
    $Shortcut.WorkingDirectory = $Root
}

$Shortcut.WindowStyle = 7
$Shortcut.Description = "Moodler starten"
$Shortcut.Save()

Write-Host "Desktop-Verknuepfung erstellt: $ShortcutPath"
Write-Host "Zum Anheften: Rechtsklick auf die Verknuepfung oder laufende App > An Taskleiste anheften."
