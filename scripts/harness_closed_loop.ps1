[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$LoopArgs
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot
try {
    & python ".\scripts\harness_closed_loop.py" @LoopArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PSD2Fusion harness loop failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
