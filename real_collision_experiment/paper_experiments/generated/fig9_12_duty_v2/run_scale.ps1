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
Write-Host "REAL RF CAMPAIGN: $CampaignId (30 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/30] seq=1 run_0f051401; N=15; d=0.2; effective G=3; capture >= 145s"
Read-Host "Arm RX for run_0f051401 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F051401 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xCE04822E --payload-seed 0xF884484A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f051401" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/30] seq=2 run_03051401; N=3; d=0.2; effective G=0.6; capture >= 145s"
Read-Host "Arm RX for run_03051401 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03051401 --active-nodes 1,2,3 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4204442E --payload-seed 0x74848E4A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03051401" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/30] seq=3 run_03051402; N=3; d=0.2; effective G=0.6; capture >= 145s"
Read-Host "Arm RX for run_03051402 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03051402 --active-nodes 1,2,3 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4208244D --payload-seed 0x7488EE29 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03051402" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/30] seq=4 run_06051401; N=6; d=0.2; effective G=1.2; capture >= 145s"
Read-Host "Arm RX for run_06051401 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06051401 --active-nodes 1,2,3,4,5,6 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE70416AE --payload-seed 0xD184DCCA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.2' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06051401" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/30] seq=5 run_06051402; N=6; d=0.2; effective G=1.2; capture >= 145s"
Read-Host "Arm RX for run_06051402 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06051402 --active-nodes 1,2,3,4,5,6 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE70876CD --payload-seed 0xD188BCA9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.2' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06051402" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/30] seq=6 run_09051401; N=9; d=0.2; effective G=1.8; capture >= 145s"
Read-Host "Arm RX for run_09051401 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09051401 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x0804E12E --payload-seed 0x3E842B4A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09051401" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/30] seq=7 run_09051402; N=9; d=0.2; effective G=1.8; capture >= 145s"
Read-Host "Arm RX for run_09051402 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09051402 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x0808814D --payload-seed 0x3E884B29 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09051402" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/30] seq=8 run_0c051401; N=12; d=0.2; effective G=2.4; capture >= 145s"
Read-Host "Arm RX for run_0c051401 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051401 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xAD04B3AE --payload-seed 0x9B8479CA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.4' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051401" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/30] seq=9 run_0c051402; N=12; d=0.2; effective G=2.4; capture >= 145s"
Read-Host "Arm RX for run_0c051402 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051402 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xAD08D3CD --payload-seed 0x9B8819A9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.4' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051402" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/30] seq=10 run_0f051402; N=15; d=0.2; effective G=3; capture >= 145s"
Read-Host "Arm RX for run_0f051402 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F051402 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xCE08E24D --payload-seed 0xF8882829 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f051402" }

# 011: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[11/30] seq=11 run_03051e01; N=3; d=0.3; effective G=0.9; capture >= 145s"
Read-Host "Arm RX for run_03051e01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03051E01 --active-nodes 1,2,3 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6B451A8E --payload-seed 0x5DC5D0EA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03051e01" }

# 012: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[12/30] seq=12 run_03051e02; N=3; d=0.3; effective G=0.9; capture >= 145s"
Read-Host "Arm RX for run_03051e02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03051E02 --active-nodes 1,2,3 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6B497AED --payload-seed 0x5DC9B089 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03051e02" }

# 013: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[13/30] seq=13 run_06051e01; N=6; d=0.3; effective G=1.8; capture >= 145s"
Read-Host "Arm RX for run_06051e01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06051E01 --active-nodes 1,2,3,4,5,6 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xCE45480E --payload-seed 0xF8C5826A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06051e01" }

# 014: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[14/30] seq=14 run_06051e02; N=6; d=0.3; effective G=1.8; capture >= 145s"
Read-Host "Arm RX for run_06051e02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06051E02 --active-nodes 1,2,3,4,5,6 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xCE49286D --payload-seed 0xF8C9E209 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06051e02" }

# 015: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[15/30] seq=15 run_09051e01; N=9; d=0.3; effective G=2.7; capture >= 145s"
Read-Host "Arm RX for run_09051e01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09051E01 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2145BF8E --payload-seed 0x17C575EA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.7' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09051e01" }

# 016: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[16/30] seq=16 run_09051e02; N=9; d=0.3; effective G=2.7; capture >= 145s"
Read-Host "Arm RX for run_09051e02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09051E02 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2149DFED --payload-seed 0x17C91589 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.7' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09051e02" }

# 017: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[17/30] seq=17 run_0c051e01; N=12; d=0.3; effective G=3.6; capture >= 145s"
Read-Host "Arm RX for run_0c051e01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051E01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x8445ED0E --payload-seed 0xB2C5276A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051e01" }

# 018: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[18/30] seq=18 run_0c051e02; N=12; d=0.3; effective G=3.6; capture >= 145s"
Read-Host "Arm RX for run_0c051e02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051E02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x84498D6D --payload-seed 0xB2C94709 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051e02" }

# 019: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[19/30] seq=19 run_0f051e01; N=15; d=0.3; effective G=4.5; capture >= 145s"
Read-Host "Arm RX for run_0f051e01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F051E01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE745DC8E --payload-seed 0xD1C516EA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f051e01" }

# 020: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[20/30] seq=20 run_0f051e02; N=15; d=0.3; effective G=4.5; capture >= 145s"
Read-Host "Arm RX for run_0f051e02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F051E02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE749BCED --payload-seed 0xD1C97689 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f051e02" }

# 021: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[21/30] seq=21 run_03042801; N=3; d=0.4; effective G=1.2; capture >= 145s"
Read-Host "Arm RX for run_03042801 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03042801 --active-nodes 1,2,3 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x95A093EE --payload-seed 0xA320598A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.2' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03042801" }

# 022: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[22/30] seq=22 run_03042802; N=3; d=0.4; effective G=1.2; capture >= 145s"
Read-Host "Arm RX for run_03042802 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03042802 --active-nodes 1,2,3 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x95ACF38D --payload-seed 0xA32C39E9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.2' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03042802" }

# 023: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[23/30] seq=23 run_06042801; N=6; d=0.4; effective G=2.4; capture >= 145s"
Read-Host "Arm RX for run_06042801 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06042801 --active-nodes 1,2,3,4,5,6 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x30A0C16E --payload-seed 0x06200B0A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.4' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06042801" }

# 024: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[24/30] seq=24 run_06042802; N=6; d=0.4; effective G=2.4; capture >= 145s"
Read-Host "Arm RX for run_06042802 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06042802 --active-nodes 1,2,3,4,5,6 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x30ACA10D --payload-seed 0x062C6B69 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.4' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06042802" }

# 025: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[25/30] seq=25 run_09042801; N=9; d=0.4; effective G=3.6; capture >= 145s"
Read-Host "Arm RX for run_09042801 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09042801 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xDFA036EE --payload-seed 0xE920FC8A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09042801" }

# 026: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[26/30] seq=26 run_09042802; N=9; d=0.4; effective G=3.6; capture >= 145s"
Read-Host "Arm RX for run_09042802 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09042802 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xDFAC568D --payload-seed 0xE92C9CE9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09042802" }

# 027: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[27/30] seq=27 run_0c042801; N=12; d=0.4; effective G=4.8; capture >= 145s"
Read-Host "Arm RX for run_0c042801 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C042801 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x7AA0646E --payload-seed 0x4C20AE0A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=4.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c042801" }

# 028: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[28/30] seq=28 run_0c042802; N=12; d=0.4; effective G=4.8; capture >= 145s"
Read-Host "Arm RX for run_0c042802 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C042802 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x7AAC040D --payload-seed 0x4C2CCE69 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=4.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c042802" }

# 029: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[29/30] seq=29 run_0f042801; N=15; d=0.4; effective G=6; capture >= 145s"
Read-Host "Arm RX for run_0f042801 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F042801 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x19A055EE --payload-seed 0x2F209F8A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f042801" }

# 030: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[30/30] seq=30 run_0f042802; N=15; d=0.4; effective G=6; capture >= 145s"
Read-Host "Arm RX for run_0f042802 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F042802 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x19AC358D --payload-seed 0x2F2CFFE9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f042802" }

