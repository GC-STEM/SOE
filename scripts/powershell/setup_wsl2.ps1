#requires -Version 5.1
# Launch the Ubuntu 24.04 SOE/CSO in Windows Subsystem for Linux 2.
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')]
    [string]$CourseRepo = 'GC-STEM/crs000',
    [switch]$SoeOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw 'WSL is unavailable. Use Windows 11 or a supported Windows 10 release.'
}

$distro = 'Ubuntu-24.04'
$installed = @(& wsl.exe --list --quiet 2>$null | ForEach-Object {
    ($_ -replace "`0", '').Trim()
})
if ($installed -notcontains $distro) {
    Write-Host "Installing $distro with WSL 2. This may require elevation and a restart."
    & wsl.exe --install -d $distro
    if ($LASTEXITCODE -ne 0) { throw 'WSL distribution installation failed.' }
    Write-Host 'Restart Windows if prompted; initialize your Ubuntu user, then rerun this script.'
    exit 0
}

& wsl.exe --set-version $distro 2
if ($LASTEXITCODE -ne 0) { throw 'Failed to select WSL 2.' }

# The initial Ubuntu launch may prompt once for a Linux username and password.
# Use a fixed Bash program; pass the course repo as a positional argument.
$bootstrap = @'
set -Eeuo pipefail
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git
mkdir -p "$HOME/Repos/_shared"
if [ ! -e "$HOME/Repos/_shared/SOE" ]; then
  git clone https://github.com/GC-STEM/SOE.git "$HOME/Repos/_shared/SOE"
fi
if [ ! -f "$HOME/Repos/_shared/SOE/scripts/bash/setup_ubuntu_runtime.sh" ]; then
  echo 'SOE installation script not found; check the selected SOE checkout.' >&2
  exit 1
fi
if [ "$2" = "soe-only" ]; then
  bash "$HOME/Repos/_shared/SOE/scripts/bash/setup_ubuntu_runtime.sh" --deployment wsl2 --soe-only
else
  bash "$HOME/Repos/_shared/SOE/scripts/bash/setup_ubuntu_runtime.sh" --deployment wsl2 --course-repo "$1"
fi
'@
$kind = if ($SoeOnly) { 'soe-only' } else { 'course' }
& wsl.exe --distribution $distro -- bash -lc $bootstrap -- $CourseRepo $kind
if ($LASTEXITCODE -ne 0) { throw 'WSL2 SOE/CSO setup failed.' }
Write-Host "Ubuntu 24.04 WSL2 SOE/CSO setup succeeded."
