$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $RootDir ".venv"

py -m venv $VenvDir
& (Join-Path $VenvDir "Scripts\Activate.ps1")
python -m pip install --upgrade pip
python -m pip install --force-reinstall --no-cache-dir "Pillow>=10,<12.2"

$Wheels = Get-ChildItem -Path (Join-Path $RootDir "wheels") -Filter "*.whl" -ErrorAction SilentlyContinue
if ($Wheels) {
  python -m pip install $Wheels.FullName
}

$AppWheels = Get-ChildItem -Path (Join-Path $RootDir "wheels") -Filter "cadis_travel_spark-*.whl" -ErrorAction SilentlyContinue
if (-not $AppWheels) {
  python -m pip install $RootDir
}

Write-Host "TravelSpark installed. Activate with:"
Write-Host "  .venv\Scripts\Activate.ps1"
Write-Host "Then run:"
Write-Host "  travelspark C:\path\to\photos --scene-id world_8192 --output travel.jpg"
Write-Host "Or run without activating:"
Write-Host "  .venv\Scripts\travelspark C:\path\to\photos --scene-id world_8192 --output travel.jpg"
