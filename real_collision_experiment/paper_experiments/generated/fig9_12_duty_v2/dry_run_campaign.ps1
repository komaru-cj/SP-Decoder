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
Write-Host "DRY RUN (no RF): $CampaignId (40 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/40] seq=1 run_0f051401; N=15; d=0.2; effective G=3; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F051401 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xCE04822E --payload-seed 0xF884484A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f051401" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/40] seq=2 run_03051401; N=3; d=0.2; effective G=0.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03051401 --active-nodes 1,2,3 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4204442E --payload-seed 0x74848E4A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03051401" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/40] seq=3 run_03051402; N=3; d=0.2; effective G=0.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03051402 --active-nodes 1,2,3 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4208244D --payload-seed 0x7488EE29 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03051402" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/40] seq=4 run_06051401; N=6; d=0.2; effective G=1.2; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06051401 --active-nodes 1,2,3,4,5,6 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE70416AE --payload-seed 0xD184DCCA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.2' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06051401" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/40] seq=5 run_06051402; N=6; d=0.2; effective G=1.2; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06051402 --active-nodes 1,2,3,4,5,6 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE70876CD --payload-seed 0xD188BCA9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.2' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06051402" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/40] seq=6 run_09051401; N=9; d=0.2; effective G=1.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09051401 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x0804E12E --payload-seed 0x3E842B4A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09051401" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/40] seq=7 run_09051402; N=9; d=0.2; effective G=1.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09051402 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x0808814D --payload-seed 0x3E884B29 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09051402" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/40] seq=8 run_0c051401; N=12; d=0.2; effective G=2.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051401 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xAD04B3AE --payload-seed 0x9B8479CA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.4' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051401" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/40] seq=9 run_0c051402; N=12; d=0.2; effective G=2.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051402 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xAD08D3CD --payload-seed 0x9B8819A9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.4' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051402" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/40] seq=10 run_0f051402; N=15; d=0.2; effective G=3; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F051402 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xCE08E24D --payload-seed 0xF8882829 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f051402" }

# 011: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[11/40] seq=11 run_03051e01; N=3; d=0.3; effective G=0.9; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03051E01 --active-nodes 1,2,3 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6B451A8E --payload-seed 0x5DC5D0EA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03051e01" }

# 012: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[12/40] seq=12 run_03051e02; N=3; d=0.3; effective G=0.9; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03051E02 --active-nodes 1,2,3 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6B497AED --payload-seed 0x5DC9B089 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03051e02" }

# 013: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[13/40] seq=13 run_06051e01; N=6; d=0.3; effective G=1.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06051E01 --active-nodes 1,2,3,4,5,6 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xCE45480E --payload-seed 0xF8C5826A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06051e01" }

# 014: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[14/40] seq=14 run_06051e02; N=6; d=0.3; effective G=1.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06051E02 --active-nodes 1,2,3,4,5,6 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xCE49286D --payload-seed 0xF8C9E209 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06051e02" }

# 015: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[15/40] seq=15 run_09051e01; N=9; d=0.3; effective G=2.7; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09051E01 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2145BF8E --payload-seed 0x17C575EA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.7' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09051e01" }

# 016: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[16/40] seq=16 run_09051e02; N=9; d=0.3; effective G=2.7; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09051E02 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2149DFED --payload-seed 0x17C91589 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.7' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09051e02" }

# 017: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[17/40] seq=17 run_0c051e01; N=12; d=0.3; effective G=3.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051E01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x8445ED0E --payload-seed 0xB2C5276A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051e01" }

# 018: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[18/40] seq=18 run_0c051e02; N=12; d=0.3; effective G=3.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051E02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x84498D6D --payload-seed 0xB2C94709 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051e02" }

# 019: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[19/40] seq=19 run_0f051e01; N=15; d=0.3; effective G=4.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F051E01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE745DC8E --payload-seed 0xD1C516EA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f051e01" }

# 020: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[20/40] seq=20 run_0f051e02; N=15; d=0.3; effective G=4.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F051E02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE749BCED --payload-seed 0xD1C97689 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f051e02" }

# 021: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[21/40] seq=21 run_03042801; N=3; d=0.4; effective G=1.2; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03042801 --active-nodes 1,2,3 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x95A093EE --payload-seed 0xA320598A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.2' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03042801" }

# 022: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[22/40] seq=22 run_03042802; N=3; d=0.4; effective G=1.2; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03042802 --active-nodes 1,2,3 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x95ACF38D --payload-seed 0xA32C39E9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1.2' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03042802" }

# 023: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[23/40] seq=23 run_06042801; N=6; d=0.4; effective G=2.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06042801 --active-nodes 1,2,3,4,5,6 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x30A0C16E --payload-seed 0x06200B0A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.4' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06042801" }

# 024: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[24/40] seq=24 run_06042802; N=6; d=0.4; effective G=2.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06042802 --active-nodes 1,2,3,4,5,6 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x30ACA10D --payload-seed 0x062C6B69 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=2.4' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06042802" }

# 025: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[25/40] seq=25 run_09042801; N=9; d=0.4; effective G=3.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09042801 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xDFA036EE --payload-seed 0xE920FC8A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09042801" }

# 026: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[26/40] seq=26 run_09042802; N=9; d=0.4; effective G=3.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09042802 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xDFAC568D --payload-seed 0xE92C9CE9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=3.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09042802" }

# 027: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[27/40] seq=27 run_0c042801; N=12; d=0.4; effective G=4.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C042801 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x7AA0646E --payload-seed 0x4C20AE0A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=4.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c042801" }

# 028: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[28/40] seq=28 run_0c042802; N=12; d=0.4; effective G=4.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C042802 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x7AAC040D --payload-seed 0x4C2CCE69 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=4.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c042802" }

# 029: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[29/40] seq=29 run_0f042801; N=15; d=0.4; effective G=6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F042801 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x19A055EE --payload-seed 0x2F209F8A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f042801" }

# 030: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[30/40] seq=30 run_0f042802; N=15; d=0.4; effective G=6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F042802 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x19AC358D --payload-seed 0x2F2CFFE9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p4' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f042802" }

# 031: Fig. 12; same_bearing_distance_prr
Write-Host "[31/40] seq=31 run_0204c101; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C101 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x0D9C96FE --payload-seed 0x3B1C5C9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c101" }

# 032: Fig. 12; same_bearing_distance_prr
Write-Host "[32/40] seq=32 run_0203c102; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C102 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xED7986FE --payload-seed 0xDBF94C9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=1' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c102" }

# 033: Fig. 12; same_bearing_distance_prr
Write-Host "[33/40] seq=33 run_0204c201; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C201 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x01FCF3CE --payload-seed 0x377C39AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c201" }

# 034: Fig. 12; same_bearing_distance_prr
Write-Host "[34/40] seq=34 run_0203c202; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C202 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE119E3CE --payload-seed 0xD79929AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=2' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c202" }

# 035: Fig. 12; same_bearing_distance_prr
Write-Host "[35/40] seq=35 run_0204c301; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C301 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x05DCD0DE --payload-seed 0x335C1ABA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c301" }

# 036: Fig. 12; same_bearing_distance_prr
Write-Host "[36/40] seq=36 run_0203c302; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C302 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE539C0DE --payload-seed 0xD3B90ABA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=3' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c302" }

# 037: Fig. 12; same_bearing_distance_prr
Write-Host "[37/40] seq=37 run_0204c401; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C401 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x193C39AE --payload-seed 0x2FBCF3CA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c401" }

# 038: Fig. 12; same_bearing_distance_prr
Write-Host "[38/40] seq=38 run_0203c402; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C402 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF9D929AE --payload-seed 0xCF59E3CA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=4' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c402" }

# 039: Fig. 12; same_bearing_distance_prr
Write-Host "[39/40] seq=39 run_0204c501; N=2; d=0.4; effective G=0.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0204C501 --active-nodes 1,2 --offered-load 2 --traffic-reference-nodes 5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1D1C1ABE --payload-seed 0x2B9CD0DA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=0.8' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.4' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0204c501" }

# 040: Fig. 12; same_bearing_distance_prr
Write-Host "[40/40] seq=40 run_0203c502; N=2; d=0.5; effective G=1; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C502 --active-nodes 1,2 --offered-load 1.5 --traffic-reference-nodes 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xFDF90ABE --payload-seed 0xCB79C0DA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v2' --experiment-tag 'effective_aggregate_offered_load=1' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'position_index=5' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c502" }

