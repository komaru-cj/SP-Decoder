param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 60
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_10_sf10_bw125_bw250_d025_r3_20s"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "REAL RF CAMPAIGN: $CampaignId (10 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/10] seq=1 run_0f012131; N=15; PHY=2 SF10/BW125000; d=0.25; effective G=3.75; capture >= 50s"
Read-Host "Arm RX for run_0f012131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F012131 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 2 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x9CE8386F --payload-seed 0xAA68F20B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=125000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw125k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=2' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f012131" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/10] seq=2 run_03012131; N=3; PHY=2 SF10/BW125000; d=0.25; effective G=0.75; capture >= 50s"
Read-Host "Arm RX for run_03012131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03012131 --active-nodes 1,2,3 --phy-profile-id 2 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x10E8FE6F --payload-seed 0x2668340B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=125000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw125k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=2' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03012131" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/10] seq=3 run_06012131; N=6; PHY=2 SF10/BW125000; d=0.25; effective G=1.5; capture >= 50s"
Read-Host "Arm RX for run_06012131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06012131 --active-nodes 1,2,3,4,5,6 --phy-profile-id 2 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xB5E8ACEF --payload-seed 0x8368668B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=125000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw125k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=2' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06012131" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/10] seq=4 run_09012131; N=9; PHY=2 SF10/BW125000; d=0.25; effective G=2.25; capture >= 50s"
Read-Host "Arm RX for run_09012131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09012131 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 2 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5AE85B6F --payload-seed 0x6C68910B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=125000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw125k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=2' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09012131" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/10] seq=5 run_0c012131; N=12; PHY=2 SF10/BW125000; d=0.25; effective G=3; capture >= 50s"
Read-Host "Arm RX for run_0c012131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C012131 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 2 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xFFE809EF --payload-seed 0xC968C38B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=125000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw125k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=2' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c012131" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/10] seq=6 run_03015131; N=3; PHY=5 SF10/BW250000; d=0.25; effective G=0.75; capture >= 50s"
Read-Host "Arm RX for run_03015131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03015131 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xDEE6696F --payload-seed 0xE866A30B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=250000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw250k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03015131" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/10] seq=7 run_06015131; N=6; PHY=5 SF10/BW250000; d=0.25; effective G=1.5; capture >= 50s"
Read-Host "Arm RX for run_06015131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06015131 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7BE63BEF --payload-seed 0x4D66F18B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=250000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw250k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06015131" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/10] seq=8 run_09015131; N=9; PHY=5 SF10/BW250000; d=0.25; effective G=2.25; capture >= 50s"
Read-Host "Arm RX for run_09015131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09015131 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x94E6CC6F --payload-seed 0xA266060B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=250000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw250k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09015131" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/10] seq=9 run_0c015131; N=12; PHY=5 SF10/BW250000; d=0.25; effective G=3; capture >= 50s"
Read-Host "Arm RX for run_0c015131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C015131 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x31E69EEF --payload-seed 0x0766548B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=250000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw250k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c015131" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/10] seq=10 run_0f015131; N=15; PHY=5 SF10/BW250000; d=0.25; effective G=3.75; capture >= 50s"
Read-Host "Arm RX for run_0f015131 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F015131 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x52E6AF6F --payload-seed 0x6466650B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bandwidth_hz=250000' --experiment-tag 'campaign=fig9_10_sf10_bw125_bw250_d025_r3_20s' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25_bw250k' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'phy_profile_id=5' --experiment-tag 'round=1' --experiment-tag 'run_id_revision=3' --experiment-tag 'spreading_factor=10' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f015131" }

