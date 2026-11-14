param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 0
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_12_duty_v2"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "DRY RUN (no RF): $CampaignId (10 runs)"

# 031: Fig. 12; same_bearing_distance_prr
Write-Host "[1/10] seq=31 run_0204c101; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C101 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x0D9C96FE --payload-seed 0x3B1C5C9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c101" }

# 032: Fig. 12; same_bearing_distance_prr
Write-Host "[2/10] seq=32 run_0203c102; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C102 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xED7986FE --payload-seed 0xDBF94C9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=1' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c102" }

# 033: Fig. 12; same_bearing_distance_prr
Write-Host "[3/10] seq=33 run_0204c201; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C201 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x01FCF3CE --payload-seed 0x377C39AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c201" }

# 034: Fig. 12; same_bearing_distance_prr
Write-Host "[4/10] seq=34 run_0203c202; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C202 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE119E3CE --payload-seed 0xD79929AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=2' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c202" }

# 035: Fig. 12; same_bearing_distance_prr
Write-Host "[5/10] seq=35 run_0204c301; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C301 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x05DCD0DE --payload-seed 0x335C1ABA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c301" }

# 036: Fig. 12; same_bearing_distance_prr
Write-Host "[6/10] seq=36 run_0203c302; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C302 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE539C0DE --payload-seed 0xD3B90ABA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=3' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c302" }

# 037: Fig. 12; same_bearing_distance_prr
Write-Host "[7/10] seq=37 run_0204c401; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C401 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x193C39AE --payload-seed 0x2FBCF3CA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c401" }

# 038: Fig. 12; same_bearing_distance_prr
Write-Host "[8/10] seq=38 run_0203c402; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C402 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF9D929AE --payload-seed 0xCF59E3CA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=4' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c402" }

# 039: Fig. 12; same_bearing_distance_prr
Write-Host "[9/10] seq=39 run_0204c501; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C501 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1D1C1ABE --payload-seed 0x2B9CD0DA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c501" }

# 040: Fig. 12; same_bearing_distance_prr
Write-Host "[10/10] seq=40 run_0203c502; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C502 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xFDF90ABE --payload-seed 0xCB79C0DA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=5' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c502" }

