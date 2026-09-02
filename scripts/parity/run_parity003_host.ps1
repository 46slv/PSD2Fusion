[CmdletBinding()]
param(
    [string]$Fixtures = '.\.local\parity003-fixtures',
    [string]$Output = ''
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Output) {
    $Output = Join-Path $Root (Join-Path 'parity-output' ('PARITY-003-host-' + (Get-Date -Format 'yyyyMMdd-HHmmss')))
}
$FixturesPath = (Resolve-Path (Join-Path $Root $Fixtures)).Path
$OutputPath = [IO.Path]::GetFullPath((Join-Path $Root $Output))
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

$fuscript = 'C:\Program Files\Blackmagic Design\DaVinci Resolve\fuscript.exe'
$probe = Join-Path $Root 'scripts\resolve\parity003_probe.lua'
$manifestPath = Join-Path $FixturesPath 'manifest.json'
if (-not (Test-Path -LiteralPath $fuscript)) {
    $payload = @{ status = 'BLOCKED'; reason = 'resolve_fuscript_missing'; path = $fuscript }
    $payload | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputPath 'summary.json')
    $payload | ConvertTo-Json
    exit 3
}
if (-not (Test-Path -LiteralPath $manifestPath)) {
    $payload = @{ status = 'BLOCKED'; reason = 'fixture_manifest_missing'; path = $manifestPath }
    $payload | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputPath 'summary.json')
    $payload | ConvertTo-Json
    exit 3
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$paths = @($manifest.host_candidates | ForEach-Object {
    $candidate = Join-Path $FixturesPath $_.candidate_comp
    if (-not (Test-Path -LiteralPath $candidate)) { throw "missing host candidate: $candidate" }
    (Resolve-Path -LiteralPath $candidate).Path
})
$init = "fusion = bmd.scriptapp('Fusion', 'localhost'); if fusion ~= nil then fu=fusion; app=fu; end"
$logPath = Join-Path $OutputPath 'resolve-probe.txt'
# Remove only the generated outputs named by this manifest so an old file
# cannot turn a timed-out host request into a false PASS.
foreach ($candidate in $manifest.host_candidates) {
    $render = Join-Path $FixturesPath $candidate.render_output
    if (Test-Path -LiteralPath $render) {
        Remove-Item -LiteralPath $render -Force
    }
}
& $fuscript -l Lua -x $init $probe @paths 2>&1 | Tee-Object -LiteralPath $logPath
$exitCode = $LASTEXITCODE
$log = if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Raw } else { '' }
[int]$loads = [regex]::Matches($log, 'LOAD_PASS=true').Count
[int]$renders = [regex]::Matches($log, 'RENDER_OUTPUT_EXISTS=true').Count
$comparisons = @()
foreach ($candidate in $manifest.host_candidates) {
    $render = Join-Path $FixturesPath $candidate.render_output
    $expected = Join-Path $FixturesPath $candidate.expected
    $compareJson = Join-Path $OutputPath (('compare-' + ($candidate.id -replace '[^A-Za-z0-9_.-]', '_')) + '.json')
    if (-not (Test-Path -LiteralPath $render)) {
        $comparisons += [ordered]@{ id = $candidate.id; status = 'BLOCKED'; reason = 'render_output_missing'; candidate = $render; reference = $expected }
        continue
    }
    & python (Join-Path $Root 'scripts\parity\parity.py') compare --candidate $render --reference $expected --json $compareJson 2>&1 | Out-Null
    $compareExit = $LASTEXITCODE
    $comparison = if (Test-Path -LiteralPath $compareJson) {
        Get-Content -LiteralPath $compareJson -Raw | ConvertFrom-Json
    } else {
        [ordered]@{ status = 'BLOCKED'; reason = 'comparison_not_written' }
    }
    $comparisons += [ordered]@{ id = $candidate.id; status = $comparison.status; exit_code = $compareExit; metrics = $comparison }
}
$comparisonPass = @($comparisons).Count -eq $paths.Count -and (@($comparisons | Where-Object { $_.status -ne 'PASS' }).Count -eq 0)
$payload = [ordered]@{
    status = if ($loads -eq $paths.Count -and $renders -eq $paths.Count -and $comparisonPass) { 'PASS' } else { 'BLOCKED' }
    reason = if ($loads -ne $paths.Count) { 'resolve_host_load_not_recorded' } elseif ($renders -ne $paths.Count) { 'resolve_host_render_not_recorded' } elseif (-not $comparisonPass) { 'resolve_host_pixel_comparison_not_pass' } else { $null }
    fuscript = $fuscript
    probe = $probe
    candidate_count = $paths.Count
    load_pass_count = $loads
    render_output_count = $renders
    fuscript_exit_code = $exitCode
    log = 'resolve-probe.txt'
    comparisons = $comparisons
}
$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $OutputPath 'summary.json')
$payload | ConvertTo-Json -Depth 8
if ($payload.status -eq 'PASS') { exit 0 }
exit 3
