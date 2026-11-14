param(
    [Parameter(Mandatory = $true)]
    [string]$ReceiverHost,
    [string]$PythonExecutable = "python",
    [double]$ControlTxGain = 60,
    [double]$InterRunGapSeconds = 5,
    [int]$StartSequence = 1,
    [int]$EndSequence = 0
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$Campaign = Join-Path $RepoRoot "real_collision_experiment\paper_experiments\generated\fig9_10_fig12_phy5_d05_d075_r1_20s\campaign.json"
$ManifestDir = Join-Path $RepoRoot "real_collision_experiment\run_manifests\fig9_10_fig12_phy5_d05_d075_r1_20s"
$Client = Join-Path $ScriptDir "controller_campaign_client.py"

$Arguments = @(
    $Client,
    "--campaign", $Campaign,
    "--receiver-host", $ReceiverHost,
    "--port", "39091",
    "--repo-root", $RepoRoot,
    "--manifest-dir", $ManifestDir,
    "--control-tx-gain", "$ControlTxGain",
    "--inter-run-gap-s", "$InterRunGapSeconds",
    "--start-sequence", "$StartSequence"
)
if ($EndSequence -gt 0) {
    $Arguments += @("--end-sequence", "$EndSequence")
}

& $PythonExecutable @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "Controller campaign failed with exit code $LASTEXITCODE"
}
