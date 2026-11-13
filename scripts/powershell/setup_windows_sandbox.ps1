
#requires -Version 5.1

[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')]
    [string]$CourseRepo,
    [switch]$SoeOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ([bool]$CourseRepo -eq [bool]$SoeOnly) {
    throw 'Specify exactly one of -SoeOnly or -CourseRepo OWNER/REPO.'
}

$repos = Join-Path $HOME 'Repos'
$soeRoot = Join-Path $repos '_shared\SOE'
$courseRoot = $null

if ($CourseRepo) {
    $courseRoot = Join-Path $repos (($CourseRepo -split '/')[1])
}

$logs = Join-Path $repos '_logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
Start-Transcript -Path (Join-Path $logs 'sandbox-setup.log') -Force

function Assert-Exit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed (exit code $LASTEXITCODE)."
    }
}

function Update-SessionPath {
    $env:Path = (
        [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
        [Environment]::GetEnvironmentVariable('Path', 'User') +
        ";$env:LOCALAPPDATA\Microsoft\WindowsApps" +
        ";$env:LOCALAPPDATA\Python\bin" +
        ";$env:ProgramFiles\Python\bin"
    )
}

function Get-PropertyValue($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-Executable {
    param(
        [string]$Name,
        [string[]]$FallbackPaths = @()
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    foreach ($path in $FallbackPaths) {
        if (Test-Path $path) { return $path }
    }

    throw "Required executable not found: $Name"
}

function Get-Repository {
    param(
        [string]$Repository,
        [string]$Destination
    )

    $temp = Join-Path $env:TEMP ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $temp | Out-Null

    try {
        $zip = Join-Path $temp 'repo.zip'
        $url = "https://github.com/$Repository/archive/refs/heads/main.zip"

        & curl.exe -fLsS --retry 5 -o $zip $url
        Assert-Exit "Downloading $Repository"

        Expand-Archive -LiteralPath $zip -DestinationPath $temp

        $source = Get-ChildItem $temp -Directory |
            Select-Object -First 1

        if (-not $source) {
            throw "Invalid archive: $Repository"
        }

        New-Item -ItemType Directory -Force `
            -Path (Split-Path $Destination -Parent) | Out-Null

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

    # Download the canonical SOE repository.

    Write-Host 'Downloading the SOE repository...'
    Get-Repository 'GC-STEM/SOE' $soeRoot

    $soe = Get-Content (
        Join-Path $soeRoot '.config\soe_manifest.json'
    ) -Raw | ConvertFrom-Json

    if ($soe.schema_version -ne '3.2' -or
        $soe.manifest_type -ne 'soe') {
        throw 'The SOE manifest must use schema 3.2.'
    }

    # Optionally download and validate the course CSO.

    $cso = $null

    if (-not $SoeOnly) {
        Write-Host "Downloading course repository: $CourseRepo ..."
        Get-Repository $CourseRepo $courseRoot

        $cso = Get-Content (
            Join-Path $courseRoot '.config\cso_manifest.json'
        ) -Raw | ConvertFrom-Json

        if ($cso.schema_version -ne '3.2' -or
            $cso.manifest_type -ne 'course' -or
            $cso.baseline.baseline_id -ne $soe.baseline.baseline_id -or
            $cso.baseline.path -ne '${SOE_ROOT}/.config/soe_manifest.json') {
            throw 'The course CSO must use the current SOE schema and baseline.'
        }

        if (@($cso.overrides).Count -gt 0) {
            throw 'CSO overrides require an implemented Windows resolver.'
        }
    }

    # Compose SOE and additive CSO capability bindings.

    $bindings = [ordered]@{}

    foreach ($entry in $soe.platforms.windows.capability_bindings.PSObject.Properties) {
        $bindings[$entry.Name] = $entry.Value
    }

    $extensions = Get-PropertyValue (
        Get-PropertyValue $cso 'additions'
    ) 'platform_extensions'

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

    # Reject unsupported required installation adapters.

    $supportedAdapters = @(
        'winget_package',
        'pymanager_runtime',
        'vscode_extension',
        'python_venv_package'
    )

    foreach ($binding in $bindings.Values) {
        if ($binding.required -and
            $binding.installer_adapter_id -notin $supportedAdapters) {
            throw "Unsupported adapter: $($binding.installer_adapter_id)"
        }
    }

    # Install Windows Package Manager.

    Write-Host 'Installing Windows Package Manager...'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    Install-PackageProvider NuGet -Force -Scope CurrentUser | Out-Null

    Install-Module Microsoft.WinGet.Client -Repository PSGallery `
        -Scope CurrentUser -Force -AllowClobber

    Import-Module Microsoft.WinGet.Client
    Repair-WinGetPackageManager -AllUsers | Out-Null

    Update-SessionPath

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue

    if ($winget) {
        $wingetPath = $winget.Source
    }
    else {
        $app = Get-AppxPackage Microsoft.DesktopAppInstaller |
            Select-Object -First 1

        if (-not $app) {
            throw 'App Installer is unavailable.'
        }

        $wingetPath = Join-Path $app.InstallLocation 'winget.exe'
    }

    if (-not (Test-Path $wingetPath)) {
        throw 'WinGet installation could not be verified.'
    }

    & $wingetPath source update --name winget
    Assert-Exit 'Updating WinGet source'

    # Install required system tools from the manifests.
    # Includes PowerShell 7+ and Python Install Manager.
    # Does not install Python 3.12 directly through WinGet.

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

    Update-SessionPath

    # Verify PowerShell 7+.

    Write-Host 'Verifying PowerShell 7+ ...'

    $pwsh = Get-Executable 'pwsh.exe' @(
        "$env:ProgramFiles\PowerShell\7\pwsh.exe"
    )

    & $pwsh -NoProfile -Command (
        'if ($PSVersionTable.PSVersion.Major -lt 7) { exit 1 }; ' +
        '$PSVersionTable.PSVersion.ToString()'
    )

    Assert-Exit 'Verifying PowerShell 7+'

    # Install Python 3.12 through Python Install Manager.

    Write-Host 'Locating Python Install Manager...'

    $pymanager = Get-Executable 'pymanager.exe' @(
        "$env:LOCALAPPDATA\Python\bin\pymanager.exe"
        "$env:ProgramFiles\Python\bin\pymanager.exe"
    )

    & $pymanager --version
    Assert-Exit 'Verifying Python Install Manager'

    $runtime = $bindings['programming_language_runtime']

    if (-not $runtime -or
        $runtime.installer_adapter_id -ne 'pymanager_runtime' -or
        $runtime.package_identifier -ne '3.12') {
        throw 'Windows SOE must declare Python 3.12 via pymanager_runtime.'
    }

    Write-Host 'Installing Python 3.12...'

    & $pymanager install 3.12 --quiet --yes
    Assert-Exit 'Installing Python 3.12'

    # Resolve the managed interpreter, not a legacy Python installation.

    $pythonPaths = @(
        & $pymanager list --one --only-managed --format=exe 3.12
    )
    Assert-Exit 'Resolving Python 3.12'

    $python = $pythonPaths |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and (Test-Path $_) } |
        Select-Object -First 1

    if (-not $python) {
        throw 'Python Install Manager did not return a Python 3.12 executable.'
    }

    & $python -c 'import sys; assert sys.version_info[:2] == (3, 12)'
    Assert-Exit 'Verifying Python 3.12'

    & $python --version
    Assert-Exit 'Reporting Python version'

    # Locate Visual Studio Code.

    $code = @(
        "$env:ProgramFiles\Microsoft VS Code\bin\code.cmd"
        "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd"
    ) | Where-Object {
        Test-Path $_
    } | Select-Object -First 1

    if (-not $code) {
        throw 'VS Code CLI was not found.'
    }

    # Install required VS Code extensions.

    $ids = @(
        $bindings.Values |
            Where-Object {
                $_.required -and
                $_.installer_adapter_id -eq 'vscode_extension'
            } |
            ForEach-Object { $_.package_identifier } |
            Select-Object -Unique
    )

    foreach ($id in $ids) {
        Write-Host "Installing extension $id ..."
        & $code --install-extension $id --force
        Assert-Exit "Installing extension $id"
    }

    # Create course-specific Python virtual environments when required.

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

    # Final SOE verification.

    Write-Host ''
    Write-Host 'Verifying installed SOE components...'

    & $wingetPath --version
    Assert-Exit 'Verifying WinGet'

    & $pymanager exec -V:3.12 --version
    Assert-Exit 'Verifying managed Python 3.12'

    & $pwsh -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
    Assert-Exit 'Verifying PowerShell 7+'

    & $code --version
    Assert-Exit 'Verifying VS Code'

    Write-Host ''
    Write-Host 'Windows Sandbox setup completed successfully.'
    Write-Host "SOE:        $soeRoot"
    Write-Host "Python:     $python"
    Write-Host "PowerShell: $pwsh"

    if ($SoeOnly) {
        Write-Host 'Mode:       SOE only'
    }
    else {
        Write-Host "Course:     $courseRoot (SOE + CSO)"
    }

    Write-Host "Log:        $logs\sandbox-setup.log"
}
catch {
    Write-Host "SETUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
    throw
}
finally {
    Stop-Transcript
}
