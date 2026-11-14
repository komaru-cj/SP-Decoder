param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 0
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_10_fig12_d025_d05_d07_r1"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "DRY RUN (no RF): $CampaignId (5 runs)"

# 011: Fig. 12; same_bearing_distance_prr
Write-Host "[1/5] seq=11 run_0213c101; N=2; d=0.7; effective G=1.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0213C101 --active-nodes 1,2 --offered-load 1.4 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xEF65E795 --payload-seed 0xD9E52DF1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=1.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.7' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0213c101" }

# 012: Fig. 12; same_bearing_distance_prr
Write-Host "[2/5] seq=12 run_0213c201; N=2; d=0.7; effective G=1.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0213C201 --active-nodes 1,2 --offered-load 1.4 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE30582A5 --payload-seed 0xD58548C1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=1.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.7' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0213c201" }

# 013: Fig. 12; same_bearing_distance_prr
Write-Host "[3/5] seq=13 run_0213c301; N=2; d=0.7; effective G=1.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0213C301 --active-nodes 1,2 --offered-load 1.4 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE725A1B5 --payload-seed 0xD1A56BD1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=1.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.7' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0213c301" }

# 014: Fig. 12; same_bearing_distance_prr
Write-Host "[4/5] seq=14 run_0213c401; N=2; d=0.7; effective G=1.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0213C401 --active-nodes 1,2 --offered-load 1.4 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xFBC548C5 --payload-seed 0xCD4582A1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=1.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.7' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0213c401" }

# 015: Fig. 12; same_bearing_distance_prr
Write-Host "[5/5] seq=15 run_0213c501; N=2; d=0.7; effective G=1.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0213C501 --active-nodes 1,2 --offered-load 1.4 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xFFE56BD5 --payload-seed 0xC965A1B1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=1.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.7' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0213c501" }

