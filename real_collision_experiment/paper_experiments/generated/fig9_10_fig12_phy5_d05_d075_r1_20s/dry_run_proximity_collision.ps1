param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 60
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_10_fig12_phy5_d05_d075_r1_20s"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "DRY RUN (no RF): $CampaignId (5 runs)"

# 011: Fig. 12; same_bearing_distance_prr
Write-Host "[1/5] seq=11 run_0203c111; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C111 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xED37E4AC --payload-seed 0xDBB72EC8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c111" }

# 012: Fig. 12; same_bearing_distance_prr
Write-Host "[2/5] seq=12 run_0203c211; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C211 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xE157819C --payload-seed 0xD7D74BF8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c211" }

# 013: Fig. 12; same_bearing_distance_prr
Write-Host "[3/5] seq=13 run_0203c311; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C311 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xE577A28C --payload-seed 0xD3F768E8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c311" }

# 014: Fig. 12; same_bearing_distance_prr
Write-Host "[4/5] seq=14 run_0203c411; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C411 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF9974BFC --payload-seed 0xCF178198 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c411" }

# 015: Fig. 12; same_bearing_distance_prr
Write-Host "[5/5] seq=15 run_0203c511; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C511 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xFDB768EC --payload-seed 0xCB37A288 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c511" }

