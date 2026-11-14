
#requires -Version 5.1
# Provision a named Ubuntu 24.04 WSL2 instance for the SOE or a course CSO.

[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')]
    [string]$CourseRepo,
    [switch]$SoeOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($SoeOnly -and $CourseRepo) {
    throw 'Use -SoeOnly or -CourseRepo, not both.'
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw 'WSL is unavailable. Install or enable WSL first.'
}

# Select the Ubuntu 24.04 image and the desired instance name.
$baseDistro = 'Ubuntu-24.04'

if ($CourseRepo) {
    $courseId = ($CourseRepo -split '/')[1].ToUpperInvariant()
    $distro = "Ubuntu-$courseId"
    $kind = 'course'
}
else {
    $distro = 'Ubuntu-SOE'
    $kind = 'soe-only'
}

Write-Host "WSL distribution: $distro"

# Discover existing instances without modifying them.
$installed = @(
    & wsl.exe --list --quiet 2>$null |
        ForEach-Object { ($_ -replace "`0", '').Trim() } |
        Where-Object { $_ }
)

# Create a dedicated instance when one does not already exist.
if ($installed -notcontains $distro) {
    Write-Host "Installing $baseDistro as $distro ..."

    & wsl.exe --install --distribution $baseDistro --name $distro

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install $distro. Check that WSL supports --name."
    }

    Write-Host ''
    Write-Host "WSL distribution created: $distro"
    Write-Host 'Complete Ubuntu user initialization if prompted.'
    Write-Host 'Then rerun this script to provision the SOE/CSO.'
    return
}

# Verify WSL 2 without attempting an unnecessary conversion.
$pattern = '^\s*\*?\s*' + [regex]::Escape($distro) +
    '\s+\S+\s+2\s*$'

$versionLine = & wsl.exe --list --verbose |
    ForEach-Object { $_ -replace "`0", '' } |
    Where-Object { $_ -match $pattern } |
    Select-Object -First 1

if (-not $versionLine) {
    throw "$distro must use WSL 2. Check 'wsl --list --verbose'."
}

# Run Ubuntu provisioning inside the selected instance.
# Bash reads the script from standard input.
$bootstrap = @'
set -Eeuo pipefail

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  --no-install-recommends git

mkdir -p "$HOME/Repos/_shared"

if [ ! -e "$HOME/Repos/_shared/SOE" ]; then
  git clone https://github.com/GC-STEM/SOE.git \
    "$HOME/Repos/_shared/SOE"
fi

setup="$HOME/Repos/_shared/SOE/scripts/bash/setup_ubuntu_runtime.sh"

if [ ! -f "$setup" ]; then
  echo 'SOE installation script not found.' >&2
  exit 1
fi

if [ "$2" = "soe-only" ]; then
  bash "$setup" --deployment wsl2 --soe-only
else
  bash "$setup" --deployment wsl2 --course-repo "$1"
fi
'@

# Normalize line endings before passing the script to Bash.
$bootstrap = $bootstrap.Replace("`r", '')

# Pass the course repository and installation mode separately.
$repositoryArg = if ($CourseRepo) {
    $CourseRepo
}
else {
    'GC-STEM/SOE'
}

($bootstrap + "`n") |
    & wsl.exe --distribution $distro -- bash -s -- $repositoryArg $kind

if ($LASTEXITCODE -ne 0) {
    throw "WSL2 SOE/CSO setup failed in $distro."
}

Write-Host ''
Write-Host "WSL2 provisioning succeeded: $distro"
Write-Host "Mode: $kind"
