[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$launcherSource = Join-Path $repoRoot "scripts\resolve\PSD2Fusion.lua"
$bridgePath = Join-Path $repoRoot "scripts\resolve\psd2fusion_bridge.py"

if (-not (Test-Path -LiteralPath $launcherSource -PathType Leaf)) {
    throw "Launcher source was not found: $launcherSource"
}
if (-not (Test-Path -LiteralPath $bridgePath -PathType Leaf)) {
    throw "Python bridge was not found: $bridgePath"
}

$appData = $env:APPDATA
if ([string]::IsNullOrWhiteSpace($appData)) {
    throw "APPDATA is not available; a per-user Resolve installation cannot be located."
}

$scriptRoot = Join-Path $appData "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts"
$targetRoot = Join-Path $scriptRoot "Comp"
$targetLauncher = Join-Path $targetRoot "PSD2Fusion.lua"

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Get-ResolveExecutable {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
        $candidates += Join-Path $env:ProgramFiles "Blackmagic Design\DaVinci Resolve\Resolve.exe"
    }
    if (-not [string]::IsNullOrWhiteSpace(${env:ProgramFiles(x86)})) {
        $candidates += Join-Path ${env:ProgramFiles(x86)} "Blackmagic Design\DaVinci Resolve\Resolve.exe"
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $null
}

function Get-PythonExecutable {
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        $command = Get-Command python -ErrorAction SilentlyContinue
    }
    if ($null -eq $command) {
        return $null
    }
    if (-not [string]::IsNullOrWhiteSpace($command.Source)) {
        return $command.Source
    }
    return $command.Path
}

function Test-OwnedLauncher {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    $content = Get-Content -LiteralPath $Path -Raw
    return $content.Contains("PSD2Fusion Resolve/Fusion launcher.")
}

if ($Uninstall) {
    if (-not (Test-Path -LiteralPath $targetLauncher -PathType Leaf)) {
        Write-Output "PSD2Fusion Resolve launcher is already absent: $targetLauncher"
        exit 0
    }
    if (-not (Test-OwnedLauncher -Path $targetLauncher) -and -not $Force) {
        throw "Refusing to remove an unrelated file at $targetLauncher. Use -Force only after verifying it."
    }
    Remove-Item -LiteralPath $targetLauncher -Force
    Write-Output "Removed PSD2Fusion Resolve launcher: $targetLauncher"
    exit 0
}

$resolveExe = Get-ResolveExecutable
if ($null -eq $resolveExe) {
    throw "DaVinci Resolve was not found under the standard Program Files location."
}

$installedDocs = Join-Path ${env:ProgramData} "Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt"
if (-not (Test-Path -LiteralPath $installedDocs -PathType Leaf)) {
    throw "Resolve scripting documentation was not found: $installedDocs"
}

$pythonExe = Get-PythonExecutable
if ($null -eq $pythonExe) {
    throw "Python 3 was not found on PATH. Install Python 3.10+ for the PSD2Fusion core, then rerun this script."
}

$bridgeProbe = & $pythonExe $bridgePath "--help" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Output "PSD2Fusion dependencies are missing; installing the repository in editable mode."
    & $pythonExe "-m" "pip" "install" "-e" $repoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Python dependency installation failed."
    }
    & $pythonExe $bridgePath "--help" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "The PSD2Fusion Python bridge still could not start after dependency installation."
    }
}

if ((Test-Path -LiteralPath $targetLauncher -PathType Leaf) -and
    -not (Test-OwnedLauncher -Path $targetLauncher) -and
    -not $Force) {
    throw "Refusing to overwrite an unrelated file at $targetLauncher. Use -Force only after verifying it."
}

$launcher = Get-Content -LiteralPath $launcherSource -Raw
$launcher = $launcher.Replace("__PSD2FUSION_REPO__", $repoRoot)
$launcher = $launcher.Replace("__PSD2FUSION_PYTHON__", $pythonExe)
$launcher = $launcher.Replace("__PSD2FUSION_BRIDGE__", $bridgePath)
if ($launcher.Contains("__PSD2FUSION_REPO__") -or
    $launcher.Contains("__PSD2FUSION_PYTHON__") -or
    $launcher.Contains("__PSD2FUSION_BRIDGE__")) {
    throw "Launcher token replacement was incomplete."
}

New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null
Write-Utf8NoBom -Path $targetLauncher -Content $launcher

Write-Output "Installed PSD2Fusion Resolve Comp script."
Write-Output "  Resolve: $resolveExe"
Write-Output "  Script:  $targetLauncher"
Write-Output "  Python:  $pythonExe"
Write-Output "Re-run this script to reinstall; use -Uninstall to remove the launcher."
