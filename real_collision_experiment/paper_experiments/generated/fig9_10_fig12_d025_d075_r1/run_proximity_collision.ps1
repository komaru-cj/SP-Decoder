param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 0
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_10_fig12_d025_d075_r1"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "REAL RF CAMPAIGN: $CampaignId (5 runs)"

# 006: Fig. 12; same_bearing_distance_prr
Write-Host "[1/5] seq=6 run_0203c101; N=2; d=0.75; effective G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c101 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C101 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xED75E69D --payload-seed 0xDBF52CF9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d075_r1' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c101" }

# 007: Fig. 12; same_bearing_distance_prr
Write-Host "[2/5] seq=7 run_0203c201; N=2; d=0.75; effective G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C201 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE11583AD --payload-seed 0xD79549C9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d075_r1' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c201" }

# 008: Fig. 12; same_bearing_distance_prr
Write-Host "[3/5] seq=8 run_0203c301; N=2; d=0.75; effective G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c301 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C301 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE535A0BD --payload-seed 0xD3B56AD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d075_r1' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c301" }

# 009: Fig. 12; same_bearing_distance_prr
Write-Host "[4/5] seq=9 run_0203c401; N=2; d=0.75; effective G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c401 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C401 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF9D549CD --payload-seed 0xCF5583A9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d075_r1' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c401" }

# 010: Fig. 12; same_bearing_distance_prr
Write-Host "[5/5] seq=10 run_0203c501; N=2; d=0.75; effective G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c501 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C501 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xFDF56ADD --payload-seed 0xCB75A0B9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d075_r1' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c501" }

