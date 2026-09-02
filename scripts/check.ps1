[CmdletBinding()]
param(
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
}

Push-Location $RepoRoot
try {
    Invoke-Checked python ".\scripts\validate_control_state.py"
    Invoke-Checked python "-m" "unittest" "discover" "-s" "tests" "-p" "test_*.py"
    if (-not $SkipCompile) {
        Invoke-Checked python "-m" "compileall" "-q" ".\psd2fusion" ".\scripts"
    }
}
finally {
    Pop-Location
}
