[CmdletBinding()]
param(
    [ValidateSet('baseline','inspect','convert','compare','offline','host-required')]
    [string]$Mode = 'baseline',
    [string]$Psd = 'D:\Downloads\a.psd',
    [string]$Reference = 'D:\Downloads\20260812.png',
    [string]$Candidate,
    [string]$Output = ''
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Output) { $Output = Join-Path $Root (Join-Path 'parity-output' (Get-Date -Format 'yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Force -Path $Output | Out-Null
Push-Location $Root
try {
    switch ($Mode) {
        'offline' { & pwsh -NoProfile -File .\scripts\check.ps1; if ($LASTEXITCODE) { exit $LASTEXITCODE }; break }
        'host-required' { $payload = @{ status = 'BLOCKED'; reason = 'HOST_REQUIRED'; message = 'Photoshop/Resolve host validation is unavailable in this environment.' } | ConvertTo-Json; $payload | Tee-Object -FilePath (Join-Path $Output 'host-required.json'); exit 3 }
        'inspect' { & python .\scripts\parity\parity.py inspect --psd $Psd --reference $Reference --output (Join-Path $Output 'summary.json'); exit $LASTEXITCODE }
        'convert' {
            # Keep stored composite and PSD2Fusion candidate as separate origins.
            $stored = Join-Path $Output 'psd_stored_composite.png'
            & python .\scripts\parity\parity.py convert --psd $Psd --output $stored
            if ($LASTEXITCODE) { exit $LASTEXITCODE }
            $candidateDir = Join-Path $Output 'psd2fusion_candidate'
            New-Item -ItemType Directory -Force -Path $candidateDir | Out-Null
            & python -m psd2fusion $Psd --output $candidateDir --force | Tee-Object -FilePath (Join-Path $Output 'psd2fusion-convert.json')
            if ($LASTEXITCODE) { exit $LASTEXITCODE }
            @{ status = 'PASS'; stored_composite = $stored; candidate_origin = 'psd2fusion_conversion'; candidate_output = $candidateDir } | ConvertTo-Json | Set-Content -Path (Join-Path $Output 'convert-summary.json')
            break
        }
        'compare' {
            if (-not $Candidate) { throw '-Candidate is required for compare mode' }
            & python .\scripts\parity\parity.py compare --candidate $Candidate --reference $Reference --output-dir $Output --json (Join-Path $Output 'comparison.json'); exit $LASTEXITCODE
        }
        'baseline' { & python .\scripts\parity\parity.py inspect --psd $Psd --reference $Reference --output (Join-Path $Output 'summary.json'); $code = $LASTEXITCODE; if ($code -ne 0) { exit $code }; break }
    }
}
finally { Pop-Location }
