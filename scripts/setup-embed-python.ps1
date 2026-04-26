# Creates ./python-runtime with official Windows embeddable Python + pip + requirements.txt
# Run from repo root: powershell -ExecutionPolicy Bypass -File scripts\setup-embed-python.ps1
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimeDir = Join-Path $Root "python-runtime"
$Req = Join-Path $Root "requirements.txt"

$PythonVer = "3.13.3"
$ZipName = "python-$PythonVer-embed-amd64.zip"
$ZipUrl = "https://www.python.org/ftp/python/$PythonVer/$ZipName"

if (-not (Test-Path $Req)) {
  Write-Error "requirements.txt not found at $Req"
}

Write-Host "Removing old python-runtime (if any)..."
if (Test-Path $RuntimeDir) {
  Remove-Item -Recurse -Force $RuntimeDir
}
New-Item -ItemType Directory -Path $RuntimeDir | Out-Null

$ZipPath = Join-Path $env:TEMP $ZipName
Write-Host "Downloading $ZipUrl ..."
Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing

Write-Host "Extracting to $RuntimeDir ..."
Expand-Archive -Path $ZipPath -DestinationPath $RuntimeDir -Force

# Enable site-packages + local Lib (pip will use Lib\site-packages)
$Pth = Get-ChildItem -Path $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
if (-not $Pth) { Write-Error "Could not find python*._pth in embed zip" }

$PthLines = @(
  "python313.zip",
  ".",
  "Lib\site-packages",
  "import site"
)
Set-Content -Path $Pth.FullName -Value ($PthLines -join "`r`n") -Encoding ascii
Write-Host "Wrote $($Pth.Name) for pip + site-packages"

$SitePackages = Join-Path $RuntimeDir "Lib\site-packages"
New-Item -ItemType Directory -Path $SitePackages -Force | Out-Null

# Prevent `%AppData%\Python\...\site-packages` from being visible during install.
# Otherwise pip's resolver reports fake "conflicts" with poetry/streamlit/etc. you have globally.
$env:PYTHONNOUSERSITE = "1"

Write-Host "Installing pip..."
$GetPip = Join-Path $env:TEMP "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip -UseBasicParsing
$Py = Join-Path $RuntimeDir "python.exe"
# -s = no user site-directory (same goal as PYTHONNOUSERSITE; belt and suspenders)
& $Py -s $GetPip --no-warn-script-location

Write-Host "Installing requirements into Lib\site-packages (forced --target; torch is large)..."
# Embeddable layout: without --target, pip may install somewhere the embed exe does not load.
& $Py -s -m pip install --no-cache-dir --upgrade --target $SitePackages --ignore-installed -r $Req

Write-Host "Verifying imports (isolated from user site-packages)..."
& $Py -s -c "import flask, flask_cors; import ultralytics; print('OK:', flask.__version__)"

Write-Host ""
Write-Host "Done. You can now run: npm run dist:win"
