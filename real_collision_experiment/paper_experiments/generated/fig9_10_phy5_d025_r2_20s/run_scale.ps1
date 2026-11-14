param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 60
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_10_phy5_d025_r2_20s"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "REAL RF CAMPAIGN: $CampaignId (5 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/5] seq=1 run_0f011921; N=15; PHY=5 SF10/BW250000; d=0.25; effective G=3.75; capture >= 50s"
Read-Host "Arm RX for run_0f011921 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F011921 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7BAD71DE --payload-seed 0x4D2DBBBA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_phy5_d025_r2_20s' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f011921" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/5] seq=2 run_03011921; N=3; PHY=5 SF10/BW250000; d=0.25; effective G=0.75; capture >= 50s"
Read-Host "Arm RX for run_03011921 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03011921 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF7ADB7DE --payload-seed 0xC12D7DBA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_phy5_d025_r2_20s' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03011921" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/5] seq=3 run_06011921; N=6; PHY=5 SF10/BW250000; d=0.25; effective G=1.5; capture >= 50s"
Read-Host "Arm RX for run_06011921 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06011921 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x52ADE55E --payload-seed 0x642D2F3A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_phy5_d025_r2_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06011921" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/5] seq=4 run_09011921; N=9; PHY=5 SF10/BW250000; d=0.25; effective G=2.25; capture >= 50s"
Read-Host "Arm RX for run_09011921 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09011921 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBDAD12DE --payload-seed 0x8B2DD8BA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_phy5_d025_r2_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09011921" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/5] seq=5 run_0c011921; N=12; PHY=5 SF10/BW250000; d=0.25; effective G=3; capture >= 50s"
Read-Host "Arm RX for run_0c011921 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C011921 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x18AD405E --payload-seed 0x2E2D8A3A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_phy5_d025_r2_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c011921" }

