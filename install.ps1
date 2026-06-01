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

$PyTag = python -c "import sys; print('cp%d%d' % sys.version_info[:2])"
$PlatformKey = $null
$OSArch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
if ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::OSX) -and $OSArch -eq [System.Runtime.InteropServices.Architecture]::Arm64) {
  $PlatformKey = "darwin-arm64"
} elseif ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Linux) -and $OSArch -eq [System.Runtime.InteropServices.Architecture]::X64) {
  $PlatformKey = "linux-amd64"
}
if ($PlatformKey) {
  $NativeWheelDir = Join-Path (Join-Path $RootDir "wheels") $PlatformKey
  $NativeWheels = Get-ChildItem -Path $NativeWheelDir -Filter "cadis_native_cgd-*-$PyTag-*.whl" -ErrorAction SilentlyContinue
  if ($NativeWheels) {
    python -m pip install $NativeWheels.FullName
  } else {
    Write-Host "No compatible cadis_native_cgd wheel for $PlatformKey/$PyTag; CADIS will use its Python CGD fallback."
  }
} else {
  Write-Host "No vendored cadis_native_cgd wheel for this platform; CADIS will use its Python CGD fallback."
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
