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
Write-Host "REAL RF CAMPAIGN: $CampaignId (15 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/15] seq=1 run_0f023211; N=15; PHY=5 SF10/BW250000; d=0.5; effective G=7.5; capture >= 50s"
Read-Host "Arm RX for run_0f023211 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F023211 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xB26B581C --payload-seed 0x84EB9278 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=7.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f023211" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/15] seq=2 run_03023211; N=3; PHY=5 SF10/BW250000; d=0.5; effective G=1.5; capture >= 50s"
Read-Host "Arm RX for run_03023211 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03023211 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x3E6B9E1C --payload-seed 0x08EB5478 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03023211" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/15] seq=3 run_06023211; N=6; PHY=5 SF10/BW250000; d=0.5; effective G=3; capture >= 50s"
Read-Host "Arm RX for run_06023211 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06023211 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x9B6BCC9C --payload-seed 0xADEB06F8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06023211" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/15] seq=4 run_09023211; N=9; PHY=5 SF10/BW250000; d=0.5; effective G=4.5; capture >= 50s"
Read-Host "Arm RX for run_09023211 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09023211 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x746B3B1C --payload-seed 0x42EBF178 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09023211" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/15] seq=5 run_0c023211; N=12; PHY=5 SF10/BW250000; d=0.5; effective G=6; capture >= 50s"
Read-Host "Arm RX for run_0c023211 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C023211 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xD16B699C --payload-seed 0xE7EBA3F8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c023211" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/15] seq=6 run_03034b11; N=3; PHY=5 SF10/BW250000; d=0.75; effective G=2.25; capture >= 50s"
Read-Host "Arm RX for run_03034b11 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03034B11 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF567228C --payload-seed 0xC3E7E8E8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03034b11" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/15] seq=7 run_06034b11; N=6; PHY=5 SF10/BW250000; d=0.75; effective G=4.5; capture >= 50s"
Read-Host "Arm RX for run_06034b11 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06034B11 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5067700C --payload-seed 0x66E7BA68 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06034b11" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/15] seq=8 run_09034b11; N=9; PHY=5 SF10/BW250000; d=0.75; effective G=6.75; capture >= 50s"
Read-Host "Arm RX for run_09034b11 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09034B11 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBF67878C --payload-seed 0x89E74DE8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=6.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09034b11" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/15] seq=9 run_0c034b11; N=12; PHY=5 SF10/BW250000; d=0.75; effective G=9; capture >= 50s"
Read-Host "Arm RX for run_0c034b11 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C034B11 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x1A67D50C --payload-seed 0x2CE71F68 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c034b11" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/15] seq=10 run_0f034b11; N=15; PHY=5 SF10/BW250000; d=0.75; effective G=11.25; capture >= 50s"
Read-Host "Arm RX for run_0f034b11 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F034B11 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7967E48C --payload-seed 0x4FE72EE8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=11.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f034b11" }

# 011: Fig. 12; same_bearing_distance_prr
Write-Host "[11/15] seq=11 run_0203c111; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
Read-Host "Arm RX for run_0203c111 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C111 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xED37E4AC --payload-seed 0xDBB72EC8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c111" }

# 012: Fig. 12; same_bearing_distance_prr
Write-Host "[12/15] seq=12 run_0203c211; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
Read-Host "Arm RX for run_0203c211 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C211 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xE157819C --payload-seed 0xD7D74BF8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c211" }

# 013: Fig. 12; same_bearing_distance_prr
Write-Host "[13/15] seq=13 run_0203c311; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
Read-Host "Arm RX for run_0203c311 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C311 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xE577A28C --payload-seed 0xD3F768E8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c311" }

# 014: Fig. 12; same_bearing_distance_prr
Write-Host "[14/15] seq=14 run_0203c411; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
Read-Host "Arm RX for run_0203c411 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C411 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF9974BFC --payload-seed 0xCF178198 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c411" }

# 015: Fig. 12; same_bearing_distance_prr
Write-Host "[15/15] seq=15 run_0203c511; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 50s"
Read-Host "Arm RX for run_0203c511 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C511 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xFDB768EC --payload-seed 0xCB37A288 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d05_d075_r1_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'run_id_revision=1' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c511" }

