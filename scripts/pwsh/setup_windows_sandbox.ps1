
#requires -Version 5.1

[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')]
    [string]$CourseRepo = 'GC-STEM/crs000'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repos = Join-Path $HOME 'Repos'
$soeRoot = Join-Path $repos '_shared\SOE'
$courseName = ($CourseRepo -split '/')[1]
$courseRoot = Join-Path $repos $courseName
$logs = Join-Path $repos '_logs'
New-Item -ItemType Directory -Force $logs | Out-Null
Start-Transcript -Path (Join-Path $logs 'sandbox-setup.log') -Force

function Get-PropertyValue($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Assert-Exit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed (exit code $LASTEXITCODE)."
    }
}

function Get-Repository([string]$Repository, [string]$Destination) {
    $temp = Join-Path $env:TEMP ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force $temp | Out-Null
    try {
        $zip = Join-Path $temp 'repo.zip'
        $url = "https://github.com/$Repository/archive/refs/heads/main.zip"

        & curl.exe -fLsS --retry 5 -o $zip $url
        Assert-Exit "Downloading $Repository"

        Expand-Archive -LiteralPath $zip -DestinationPath $temp
        $source = Get-ChildItem $temp -Directory | Select-Object -First 1
        if (-not $source) { throw "Invalid archive: $Repository" }

        New-Item -ItemType Directory -Force (
            Split-Path $Destination -Parent
        ) | Out-Null
        Move-Item -LiteralPath $source.FullName -Destination $Destination
    }
    finally {
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

try {
    if ($env:USERNAME -ne 'WDAGUtilityAccount') {
        throw 'This script is intended for Windows Sandbox.'
    }

    Write-Host 'Downloading SOE and course repositories...'
    Get-Repository 'GC-STEM/SOE' $soeRoot
    Get-Repository $CourseRepo $courseRoot

    $soe = Get-Content (Join-Path $soeRoot '.config\soe_manifest.json') `
        -Raw | ConvertFrom-Json
    $cso = Get-Content (Join-Path $courseRoot '.config\cso_manifest.json') `
        -Raw | ConvertFrom-Json

    if ($soe.schema_version -ne '3.2' -or
        $cso.schema_version -ne '3.2' -or
        $cso.manifest_type -ne 'course' -or
        $cso.baseline.baseline_id -ne $soe.baseline.baseline_id -or
        $cso.baseline.path -ne '${SOE_ROOT}/.config/soe_manifest.json') {
        throw 'The course CSO must use the current SOE schema and baseline.'
    }

    if (@($cso.overrides).Count -gt 0) {
        throw 'CSO overrides require an implemented Windows resolver.'
    }

    # Compose the Windows SOE and additive CSO bindings.
    $bindings = [ordered]@{}
    foreach ($entry in $soe.platforms.windows.capability_bindings.PSObject.Properties) {
        $bindings[$entry.Name] = $entry.Value
    }

    $extensions = Get-PropertyValue $cso.additions 'platform_extensions'
    $windows = Get-PropertyValue $extensions 'windows'
    $extra = Get-PropertyValue $windows 'capability_bindings'

    if ($extra) {
        foreach ($entry in $extra.PSObject.Properties) {
            if ($bindings.Contains($entry.Name)) {
                throw "Duplicate capability: $($entry.Name)"
            }
            $bindings[$entry.Name] = $entry.Value
        }
    }

    # Install WinGet in a clean Windows Sandbox.
    Write-Host 'Installing Windows Package Manager...'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    Install-PackageProvider NuGet -Force -Scope CurrentUser | Out-Null
    Install-Module Microsoft.WinGet.Client -Repository PSGallery `
        -Scope CurrentUser -Force -AllowClobber
    Import-Module Microsoft.WinGet.Client
    Repair-WinGetPackageManager -AllUsers | Out-Null

    $env:Path = (
        [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
        [Environment]::GetEnvironmentVariable('Path', 'User') +
        ";$env:LOCALAPPDATA\Microsoft\WindowsApps"
    )

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        $wingetPath = $winget.Source
    }
    else {
        $app = Get-AppxPackage Microsoft.DesktopAppInstaller |
            Select-Object -First 1
        if (-not $app) { throw 'App Installer is unavailable.' }
        $wingetPath = Join-Path $app.InstallLocation 'winget.exe'
    }
    if (-not (Test-Path $wingetPath)) {
        throw 'WinGet installation could not be verified.'
    }

    & $wingetPath source update --name winget
    Assert-Exit 'Updating WinGet source'

    # Install system tools selected by the manifests.
    foreach ($binding in $bindings.Values) {
        if (-not $binding.required -or
            $binding.installer_adapter_id -ne 'winget_package') {
            continue
        }

        $id = [string]$binding.package_identifier
        Write-Host "Installing $id ..."

        & $wingetPath install --id $id --exact --source winget `
            --silent --disable-interactivity `
            --accept-source-agreements --accept-package-agreements
        Assert-Exit "Installing $id"
    }

    # Refresh PATH following installer operations.
    $env:Path = (
        [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
        [Environment]::GetEnvironmentVariable('Path', 'User') +
        ";$env:LOCALAPPDATA\Microsoft\WindowsApps"
    )

    $code = @(
        "$env:ProgramFiles\Microsoft VS Code\bin\code.cmd"
        "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $code) { throw 'VS Code CLI was not found.' }

    # Install SOE and CSO editor extensions.
    $ids = @($bindings.Values |
        Where-Object {
            $_.required -and $_.installer_adapter_id -eq 'vscode_extension'
        } |
        ForEach-Object { $_.package_identifier } |
        Select-Object -Unique)

    foreach ($id in $ids) {
        & $code --install-extension $id --force
        Assert-Exit "Installing extension $id"
    }

    # Prepare course-specific Python environments.
    $python = @(
        "$env:ProgramFiles\Python312\python.exe"
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $python) { throw 'Python 3.12 was not found.' }

    $environments = Get-PropertyValue $cso 'course_environments'

    foreach ($binding in $bindings.Values) {
        if (-not $binding.required -or
            $binding.installer_adapter_id -ne 'python_venv_package') {
            continue
        }

        $definition = Get-PropertyValue $environments $binding.environment_id
        if (-not $definition -or $definition.kind -ne 'python_venv') {
            throw 'Invalid CSO Python environment.'
        }

        if ($definition.path -ne '${COURSE_ROOT}/.venv') {
            throw 'This bootstrap currently supports only the course .venv.'
        }

        $venv = Join-Path $courseRoot '.venv'
        $venvPython = Join-Path $venv 'Scripts\python.exe'

        if (-not (Test-Path $venvPython)) {
            & $python -m venv $venv
            Assert-Exit 'Creating course virtual environment'
        }

        $package = [string]$binding.package_identifier
        $version = Get-PropertyValue $binding 'version_rule_override'
        if ($version -and $version.comparison -eq 'exact') {
            $package += "==$($version.value)"
        }

        & $venvPython -m pip install $package
        Assert-Exit "Installing course package $package"
    }

    # Reject unsupported required installation adapters.
    foreach ($binding in $bindings.Values) {
        if ($binding.required -and $binding.installer_adapter_id -notin @(
            'winget_package', 'vscode_extension', 'python_venv_package'
        )) {
            throw "Unsupported adapter: $($binding.installer_adapter_id)"
        }
    }

    # Verify the baseline Python runtime and editor.
    & $python -c 'import sys; assert sys.version_info[:2] == (3, 12)'
    Assert-Exit 'Verifying Python 3.12'

    & $code --version
    Assert-Exit 'Verifying VS Code'

    Write-Host ''
    Write-Host 'Windows Sandbox setup completed successfully.'
    Write-Host "SOE:    $soeRoot"
    Write-Host "Course: $courseRoot"
    Write-Host "Log:    $logs\sandbox-setup.log"
}
catch {
    Write-Host "SETUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
    throw
}
finally {
    Stop-Transcript
}
