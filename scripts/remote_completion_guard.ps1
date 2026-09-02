[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$TaskId,[Parameter(Mandatory=$true)][string]$ExpectedActiveTaskId,[string]$ExpectedStatus="done",[string]$ExpectedVerification="pass")
$ErrorActionPreference="Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try { & python .\scripts\remote_completion_guard.py -TaskId $TaskId -ExpectedActiveTaskId $ExpectedActiveTaskId -ExpectedStatus $ExpectedStatus -ExpectedVerification $ExpectedVerification; exit $LASTEXITCODE } finally { Pop-Location }
