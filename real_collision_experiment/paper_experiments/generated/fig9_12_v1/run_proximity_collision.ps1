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
Write-Host "REAL RF CAMPAIGN: $CampaignId (15 runs)"

# 039: Fig. 12; same_bearing_distance_prr
Write-Host "[39/15] run_0203c101; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c101 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C101 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xED75E69D --payload-seed 0xDBF52CF9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.25' --experiment-tag 'node_separation_m=0.25' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c101" }

# 040: Fig. 12; same_bearing_distance_prr
Write-Host "[40/15] run_0203c102; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c102 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C102 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xED7986FE --payload-seed 0xDBF94C9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.25' --experiment-tag 'node_separation_m=0.25' --experiment-tag 'position_index=1' --experiment-tag 'round=2' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c102" }

# 041: Fig. 12; same_bearing_distance_prr
Write-Host "[41/15] run_0203c103; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c103 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C103 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xED7DA6DF --payload-seed 0xDBFD6CBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.25' --experiment-tag 'node_separation_m=0.25' --experiment-tag 'position_index=1' --experiment-tag 'round=3' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c103" }

# 043: Fig. 12; same_bearing_distance_prr
Write-Host "[43/15] run_0203c201; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C201 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xE11583AD --payload-seed 0xD79549C9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.5' --experiment-tag 'node_separation_m=0.5' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c201" }

# 044: Fig. 12; same_bearing_distance_prr
Write-Host "[44/15] run_0203c202; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c202 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C202 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xE119E3CE --payload-seed 0xD79929AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.5' --experiment-tag 'node_separation_m=0.5' --experiment-tag 'position_index=2' --experiment-tag 'round=2' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c202" }

# 045: Fig. 12; same_bearing_distance_prr
Write-Host "[45/15] run_0203c203; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c203 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C203 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xE11DC3EF --payload-seed 0xD79D098B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.5' --experiment-tag 'node_separation_m=0.5' --experiment-tag 'position_index=2' --experiment-tag 'round=3' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c203" }

# 047: Fig. 12; same_bearing_distance_prr
Write-Host "[47/15] run_0203c301; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c301 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C301 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xE535A0BD --payload-seed 0xD3B56AD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=3' --experiment-tag 'node_separation_m=1' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c301" }

# 048: Fig. 12; same_bearing_distance_prr
Write-Host "[48/15] run_0203c302; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c302 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C302 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xE539C0DE --payload-seed 0xD3B90ABA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=3' --experiment-tag 'node_separation_m=1' --experiment-tag 'position_index=3' --experiment-tag 'round=2' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c302" }

# 049: Fig. 12; same_bearing_distance_prr
Write-Host "[49/15] run_0203c303; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c303 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C303 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xE53DE0FF --payload-seed 0xD3BD2A9B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=3' --experiment-tag 'node_separation_m=1' --experiment-tag 'position_index=3' --experiment-tag 'round=3' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c303" }

# 051: Fig. 12; same_bearing_distance_prr
Write-Host "[51/15] run_0203c401; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c401 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C401 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xF9D549CD --payload-seed 0xCF5583A9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=4' --experiment-tag 'node_separation_m=2' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c401" }

# 052: Fig. 12; same_bearing_distance_prr
Write-Host "[52/15] run_0203c402; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c402 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C402 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xF9D929AE --payload-seed 0xCF59E3CA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=4' --experiment-tag 'node_separation_m=2' --experiment-tag 'position_index=4' --experiment-tag 'round=2' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c402" }

# 053: Fig. 12; same_bearing_distance_prr
Write-Host "[53/15] run_0203c403; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c403 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C403 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xF9DD098F --payload-seed 0xCF5DC3EB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=4' --experiment-tag 'node_separation_m=2' --experiment-tag 'position_index=4' --experiment-tag 'round=3' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c403" }

# 055: Fig. 12; same_bearing_distance_prr
Write-Host "[55/15] run_0203c501; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c501 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C501 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xFDF56ADD --payload-seed 0xCB75A0B9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=6' --experiment-tag 'node_separation_m=4' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c501" }

# 056: Fig. 12; same_bearing_distance_prr
Write-Host "[56/15] run_0203c502; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c502 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C502 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xFDF90ABE --payload-seed 0xCB79C0DA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=6' --experiment-tag 'node_separation_m=4' --experiment-tag 'position_index=5' --experiment-tag 'round=2' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c502" }

# 057: Fig. 12; same_bearing_distance_prr
Write-Host "[57/15] run_0203c503; N=2; G=1.5; capture >= 145s"
Read-Host "Arm RX for run_0203c503 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C503 --active-nodes 1,2 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xFDFD2A9F --payload-seed 0xCB7DE0FB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=6' --experiment-tag 'node_separation_m=4' --experiment-tag 'position_index=5' --experiment-tag 'round=3' --experiment-tag 'rx_antenna_spacing_m=0.5'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c503" }

