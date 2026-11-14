param(
    [string]$PythonExecutable = "python",
    [double]$ControlTxGain = 60
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$Campaign = Join-Path $RepoRoot "real_collision_experiment\paper_experiments\generated\fig9_10_sf10_bw125_bw250_d025_r3_20s\campaign.json"
$ManifestDir = Join-Path $RepoRoot "real_collision_experiment\run_manifests\fig9_10_sf10_bw125_bw250_d025_r3_20s_offline"
$Controller = Join-Path $ScriptDir "offline_controller_campaign.py"

& $PythonExecutable $Controller `
    --campaign $Campaign `
    --repo-root $RepoRoot `
    --manifest-dir $ManifestDir `
    --start-sequence 2 `
    --end-sequence 10 `
    --slot-s 100 `
    --position-pause-s 20 `
    --pre-config-delay-s 5 `
    --continue-on-run-error `
    --control-tx-gain $ControlTxGain
if ($LASTEXITCODE -ne 0) {
    throw "Offline Fig. 9/10 controller campaign failed with exit code $LASTEXITCODE"
}
