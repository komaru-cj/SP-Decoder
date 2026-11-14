param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 0
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_12_duty_v4"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "REAL RF CAMPAIGN: $CampaignId (10 runs)"

# 031: Fig. 12; same_bearing_distance_prr
Write-Host "[1/10] seq=31 run_0201c101; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c101 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C101 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xAD33C6BC --payload-seed 0x9BB30CD8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c101" }

# 032: Fig. 12; same_bearing_distance_prr
Write-Host "[2/10] seq=32 run_0201c102; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c102 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C102 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xAD3FA6DF --payload-seed 0x9BBF6CBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=1' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c102" }

# 033: Fig. 12; same_bearing_distance_prr
Write-Host "[3/10] seq=33 run_0201c201; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C201 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA153A38C --payload-seed 0x97D369E8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c201" }

# 034: Fig. 12; same_bearing_distance_prr
Write-Host "[4/10] seq=34 run_0201c202; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c202 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C202 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA15FC3EF --payload-seed 0x97DF098B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=2' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c202" }

# 035: Fig. 12; same_bearing_distance_prr
Write-Host "[5/10] seq=35 run_0201c301; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c301 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C301 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA573809C --payload-seed 0x93F34AF8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c301" }

# 036: Fig. 12; same_bearing_distance_prr
Write-Host "[6/10] seq=36 run_0201c302; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c302 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C302 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA57FE0FF --payload-seed 0x93FF2A9B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=3' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c302" }

# 037: Fig. 12; same_bearing_distance_prr
Write-Host "[7/10] seq=37 run_0201c401; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c401 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C401 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB99369EC --payload-seed 0x8F13A388 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c401" }

# 038: Fig. 12; same_bearing_distance_prr
Write-Host "[8/10] seq=38 run_0201c402; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c402 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C402 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB99F098F --payload-seed 0x8F1FC3EB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=4' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c402" }

# 039: Fig. 12; same_bearing_distance_prr
Write-Host "[9/10] seq=39 run_0201c501; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c501 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C501 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBDB34AFC --payload-seed 0x8B338098 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c501" }

# 040: Fig. 12; same_bearing_distance_prr
Write-Host "[10/10] seq=40 run_0201c502; N=2; d=0.25; effective G=0.5; capture >= 145s"
Read-Host "Arm RX for run_0201c502 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C502 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBDBF2A9F --payload-seed 0x8B3FE0FB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=5' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c502" }

