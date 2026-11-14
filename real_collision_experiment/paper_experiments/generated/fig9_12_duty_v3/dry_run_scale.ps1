param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 0
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_12_duty_v3"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "DRY RUN (no RF): $CampaignId (30 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/30] seq=1 run_0f000201; N=15; d=0.0208333; effective G=0.3125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x3469290C --payload-seed 0x02E9E368 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.3125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000201" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/30] seq=2 run_03000201; N=3; d=0.0208333; effective G=0.0625; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000201 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB869EF0C --payload-seed 0x8EE92568 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.0625' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000201" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/30] seq=3 run_03000202; N=3; d=0.0208333; effective G=0.0625; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000202 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB8658F6F --payload-seed 0x8EE5450B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.0625' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000202" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/30] seq=4 run_06000201; N=6; d=0.0208333; effective G=0.125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000201 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1D69BD8C --payload-seed 0x2BE977E8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000201" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/30] seq=5 run_06000202; N=6; d=0.0208333; effective G=0.125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000202 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1D65DDEF --payload-seed 0x2BE5178B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000202" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/30] seq=6 run_09000201; N=9; d=0.0208333; effective G=0.1875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000201 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF2694A0C --payload-seed 0xC4E98068 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.1875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000201" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/30] seq=7 run_09000202; N=9; d=0.0208333; effective G=0.1875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000202 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF2652A6F --payload-seed 0xC4E5E00B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.1875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000202" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/30] seq=8 run_0c000201; N=12; d=0.0208333; effective G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x5769188C --payload-seed 0x61E9D2E8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000201" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/30] seq=9 run_0c000202; N=12; d=0.0208333; effective G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000202 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x576578EF --payload-seed 0x61E5B28B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000202" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/30] seq=10 run_0f000202; N=15; d=0.0208333; effective G=0.3125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000202 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x3465496F --payload-seed 0x02E5830B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.3125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000202" }

# 011: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[11/30] seq=11 run_03000301; N=3; d=0.03125; effective G=0.09375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000301 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBC49CC1C --payload-seed 0x8AC90678 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.09375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000301" }

# 012: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[12/30] seq=12 run_03000302; N=3; d=0.03125; effective G=0.09375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000302 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBC45AC7F --payload-seed 0x8AC5661B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.09375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000302" }

# 013: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[13/30] seq=13 run_06000301; N=6; d=0.03125; effective G=0.1875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000301 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x19499E9C --payload-seed 0x2FC954F8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.1875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000301" }

# 014: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[14/30] seq=14 run_06000302; N=6; d=0.03125; effective G=0.1875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000302 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1945FEFF --payload-seed 0x2FC5349B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.1875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000302" }

# 015: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[15/30] seq=15 run_09000301; N=9; d=0.03125; effective G=0.28125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000301 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF649691C --payload-seed 0xC0C9A378 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.28125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000301" }

# 016: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[16/30] seq=16 run_09000302; N=9; d=0.03125; effective G=0.28125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000302 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF645097F --payload-seed 0xC0C5C31B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.28125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000302" }

# 017: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[17/30] seq=17 run_0c000301; N=12; d=0.03125; effective G=0.375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000301 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x53493B9C --payload-seed 0x65C9F1F8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000301" }

# 018: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[18/30] seq=18 run_0c000302; N=12; d=0.03125; effective G=0.375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000302 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x53455BFF --payload-seed 0x65C5919B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000302" }

# 019: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[19/30] seq=19 run_0f000301; N=15; d=0.03125; effective G=0.46875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000301 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x30490A1C --payload-seed 0x06C9C078 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.46875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000301" }

# 020: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[20/30] seq=20 run_0f000302; N=15; d=0.03125; effective G=0.46875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000302 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x30456A7F --payload-seed 0x06C5A01B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.46875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000302" }

# 021: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[21/30] seq=21 run_03000401; N=3; d=0.0416667; effective G=0.125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000401 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA0A9256C --payload-seed 0x9629EF08 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000401" }

# 022: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[22/30] seq=22 run_03000402; N=3; d=0.0416667; effective G=0.125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000402 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA0A5450F --payload-seed 0x96258F6B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000402" }

# 023: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[23/30] seq=23 run_06000401; N=6; d=0.0416667; effective G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000401 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x05A977EC --payload-seed 0x3329BD88 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000401" }

# 024: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[24/30] seq=24 run_06000402; N=6; d=0.0416667; effective G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000402 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x05A5178F --payload-seed 0x3325DDEB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000402" }

# 025: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[25/30] seq=25 run_09000401; N=9; d=0.0416667; effective G=0.375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000401 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xEAA9806C --payload-seed 0xDC294A08 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000401" }

# 026: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[26/30] seq=26 run_09000402; N=9; d=0.0416667; effective G=0.375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000402 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xEAA5E00F --payload-seed 0xDC252A6B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000402" }

# 027: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[27/30] seq=27 run_0c000401; N=12; d=0.0416667; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000401 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4FA9D2EC --payload-seed 0x79291888 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000401" }

# 028: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[28/30] seq=28 run_0c000402; N=12; d=0.0416667; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000402 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4FA5B28F --payload-seed 0x792578EB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000402" }

# 029: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[29/30] seq=29 run_0f000401; N=15; d=0.0416667; effective G=0.625; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000401 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2CA9E36C --payload-seed 0x1A292908 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.625' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000401" }

# 030: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[30/30] seq=30 run_0f000402; N=15; d=0.0416667; effective G=0.625; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000402 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2CA5830F --payload-seed 0x1A25496B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.625' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000402" }

