$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $Root "dist\Moodler"
$ZipPath = Join-Path $Root "dist\Moodler-portable.zip"

if (-not (Test-Path $AppDir)) {
    throw "dist\Moodler fehlt. Fuehre zuerst build_app.bat aus."
}

Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination (Join-Path $AppDir "README.md") -Force
Copy-Item -LiteralPath (Join-Path $Root ".env.example") -Destination (Join-Path $AppDir ".env.example") -Force
Copy-Item -LiteralPath (Join-Path $Root "START_HIER.bat") -Destination (Join-Path $AppDir "START_HIER.bat") -Force
Copy-Item -LiteralPath (Join-Path $Root "create_shortcut.bat") -Destination (Join-Path $AppDir "create_shortcut.bat") -Force
Copy-Item -LiteralPath (Join-Path $Root "create_shortcut.ps1") -Destination (Join-Path $AppDir "create_shortcut.ps1") -Force
if (Test-Path (Join-Path $Root "RELEASE_CHECKLIST.md")) {
    Copy-Item -LiteralPath (Join-Path $Root "RELEASE_CHECKLIST.md") -Destination (Join-Path $AppDir "RELEASE_CHECKLIST.md") -Force
}

Get-ChildItem -Path $AppDir -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$BlockedNames = @(".env", "moodler.db", "moodler.log")
$BlockedExtensions = @(".db", ".sqlite", ".sqlite3", ".log")

Get-ChildItem -Path $AppDir -Recurse -File | Where-Object {
    $BlockedNames -contains $_.Name -or $BlockedExtensions -contains $_.Extension
} | Remove-Item -Force -ErrorAction SilentlyContinue

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Compress-Archive -Path (Join-Path $AppDir "*") -DestinationPath $ZipPath -Force
Write-Host "Portable ZIP erstellt: $ZipPath"
