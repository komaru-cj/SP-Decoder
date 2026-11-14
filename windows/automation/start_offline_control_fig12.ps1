param(
    [string]$PythonExecutable = "python",
    [double]$ControlTxGain = 60
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$Campaign = Join-Path $RepoRoot "real_collision_experiment\paper_experiments\generated\fig9_10_fig12_phy5_d05_d075_r1_20s\campaign.json"
$ManifestDir = Join-Path $RepoRoot "real_collision_experiment\run_manifests\fig9_10_fig12_phy5_d05_d075_r1_20s_offline"
$Controller = Join-Path $ScriptDir "offline_controller_campaign.py"

& $PythonExecutable $Controller `
    --campaign $Campaign `
    --repo-root $RepoRoot `
    --manifest-dir $ManifestDir `
    --start-sequence 11 `
    --end-sequence 15 `
    --slot-s 70 `
    --position-pause-s 20 `
    --pre-config-delay-s 5 `
    --continue-on-run-error `
    --control-tx-gain $ControlTxGain
if ($LASTEXITCODE -ne 0) {
    throw "Offline Fig. 12 controller campaign failed with exit code $LASTEXITCODE"
}
