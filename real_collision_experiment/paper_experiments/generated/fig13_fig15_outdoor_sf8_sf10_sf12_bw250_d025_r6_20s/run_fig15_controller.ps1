param(
    [string]$PythonExecutable = "python",
    [double]$ControlTxGain = 60
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..")).Path
$Campaign = Join-Path $ScriptDir "campaign.json"
$ManifestDir = Join-Path $RepoRoot "real_collision_experiment\run_manifests\fig13_fig15_outdoor_sf8_sf10_sf12_bw250_d025_r6_20s_offline"
$Controller = Join-Path $RepoRoot "real_collision_experiment\automation\offline_controller_campaign.py"

& $PythonExecutable $Controller `
    --campaign $Campaign `
    --repo-root $RepoRoot `
    --manifest-dir $ManifestDir `
    --start-sequence 11 `
    --end-sequence 24 `
    --slot-s 75 `
    --position-pause-s 30 `
    --pre-config-delay-s 5 `
    --continue-on-run-error `
    --control-tx-gain $ControlTxGain
if ($LASTEXITCODE -ne 0) {
    throw "Offline Fig.15 controller campaign failed with exit code $LASTEXITCODE"
}
