param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 0
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_12_v1"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "REAL RF CAMPAIGN: $CampaignId (6 runs)"

# 037: Fig. 12; clean_channel_node01
Write-Host "[37/6] run_0101c140; N=1; G=0.5; capture >= 45s"
Read-Host "Arm RX for run_0101c140 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0101C140 --active-nodes 1 --offered-load 0.5 --duration-s 20 --warmup-s 5 --node-tx-power 10 --global-seed 0xCF3FDFD9 --payload-seed 0xF9BF15BD --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'active_node=1' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=single_node_calibration' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.25' --experiment-tag 'node_separation_m=0.25' --experiment-tag 'position_index=1' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0101c140" }

# 038: Fig. 12; clean_channel_node02
Write-Host "[38/6] run_0101c180; N=1; G=0.5; capture >= 45s"
Read-Host "Arm RX for run_0101c180 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0101C180 --active-nodes 2 --offered-load 0.5 --duration-s 20 --warmup-s 5 --node-tx-power 10 --global-seed 0xCC27C695 --payload-seed 0xFAA70CF1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'active_node=2' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=single_node_calibration' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.25' --experiment-tag 'node_separation_m=0.25' --experiment-tag 'position_index=1' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0101c180" }

# 042: Fig. 12; clean_channel_node02
Write-Host "[42/6] run_0101c280; N=1; G=0.5; capture >= 45s"
Read-Host "Arm RX for run_0101c280 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0101C280 --active-nodes 2 --offered-load 0.5 --duration-s 20 --warmup-s 5 --node-tx-power 10 --global-seed 0xC047A3A5 --payload-seed 0xF6C769C1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'active_node=2' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=single_node_calibration' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.5' --experiment-tag 'node_separation_m=0.5' --experiment-tag 'position_index=2' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0101c280" }

# 046: Fig. 12; clean_channel_node02
Write-Host "[46/6] run_0101c380; N=1; G=0.5; capture >= 45s"
Read-Host "Arm RX for run_0101c380 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0101C380 --active-nodes 2 --offered-load 0.5 --duration-s 20 --warmup-s 5 --node-tx-power 10 --global-seed 0xC46780B5 --payload-seed 0xF2E74AD1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'active_node=2' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=single_node_calibration' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=3' --experiment-tag 'node_separation_m=1' --experiment-tag 'position_index=3' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0101c380" }

# 050: Fig. 12; clean_channel_node02
Write-Host "[50/6] run_0101c480; N=1; G=0.5; capture >= 45s"
Read-Host "Arm RX for run_0101c480 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0101C480 --active-nodes 2 --offered-load 0.5 --duration-s 20 --warmup-s 5 --node-tx-power 10 --global-seed 0xD88769C5 --payload-seed 0xEE07A3A1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'active_node=2' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=single_node_calibration' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=4' --experiment-tag 'node_separation_m=2' --experiment-tag 'position_index=4' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0101c480" }

# 054: Fig. 12; clean_channel_node02
Write-Host "[54/6] run_0101c580; N=1; G=0.5; capture >= 45s"
Read-Host "Arm RX for run_0101c580 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0101C580 --active-nodes 2 --offered-load 0.5 --duration-s 20 --warmup-s 5 --node-tx-power 10 --global-seed 0xDCA74AD5 --payload-seed 0xEA2780B1 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'active_node=2' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=single_node_calibration' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=6' --experiment-tag 'node_separation_m=4' --experiment-tag 'position_index=5' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0101c580" }

