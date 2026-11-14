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
Write-Host "DRY RUN (no RF): $CampaignId (40 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/40] seq=1 run_0f000201; N=15; d=0.0208333; effective G=0.3125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x3469290C --payload-seed 0x02E9E368 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.3125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000201" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/40] seq=2 run_03000201; N=3; d=0.0208333; effective G=0.0625; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000201 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB869EF0C --payload-seed 0x8EE92568 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.0625' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000201" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/40] seq=3 run_03000202; N=3; d=0.0208333; effective G=0.0625; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000202 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB8658F6F --payload-seed 0x8EE5450B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.0625' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000202" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/40] seq=4 run_06000201; N=6; d=0.0208333; effective G=0.125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000201 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1D69BD8C --payload-seed 0x2BE977E8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000201" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/40] seq=5 run_06000202; N=6; d=0.0208333; effective G=0.125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000202 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1D65DDEF --payload-seed 0x2BE5178B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000202" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/40] seq=6 run_09000201; N=9; d=0.0208333; effective G=0.1875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000201 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF2694A0C --payload-seed 0xC4E98068 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.1875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000201" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/40] seq=7 run_09000202; N=9; d=0.0208333; effective G=0.1875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000202 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF2652A6F --payload-seed 0xC4E5E00B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.1875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000202" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/40] seq=8 run_0c000201; N=12; d=0.0208333; effective G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x5769188C --payload-seed 0x61E9D2E8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000201" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/40] seq=9 run_0c000202; N=12; d=0.0208333; effective G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000202 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x576578EF --payload-seed 0x61E5B28B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000202" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/40] seq=10 run_0f000202; N=15; d=0.0208333; effective G=0.3125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000202 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 12 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x3465496F --payload-seed 0x02E5830B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.3125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0208333' --experiment-tag 'per_node_duty_cycle=0.0208333' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000202" }

# 011: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[11/40] seq=11 run_03000301; N=3; d=0.03125; effective G=0.09375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000301 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBC49CC1C --payload-seed 0x8AC90678 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.09375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000301" }

# 012: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[12/40] seq=12 run_03000302; N=3; d=0.03125; effective G=0.09375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000302 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBC45AC7F --payload-seed 0x8AC5661B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.09375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000302" }

# 013: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[13/40] seq=13 run_06000301; N=6; d=0.03125; effective G=0.1875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000301 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x19499E9C --payload-seed 0x2FC954F8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.1875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000301" }

# 014: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[14/40] seq=14 run_06000302; N=6; d=0.03125; effective G=0.1875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000302 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1945FEFF --payload-seed 0x2FC5349B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.1875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000302" }

# 015: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[15/40] seq=15 run_09000301; N=9; d=0.03125; effective G=0.28125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000301 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF649691C --payload-seed 0xC0C9A378 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.28125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000301" }

# 016: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[16/40] seq=16 run_09000302; N=9; d=0.03125; effective G=0.28125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000302 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xF645097F --payload-seed 0xC0C5C31B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.28125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000302" }

# 017: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[17/40] seq=17 run_0c000301; N=12; d=0.03125; effective G=0.375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000301 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x53493B9C --payload-seed 0x65C9F1F8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000301" }

# 018: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[18/40] seq=18 run_0c000302; N=12; d=0.03125; effective G=0.375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000302 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x53455BFF --payload-seed 0x65C5919B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000302" }

# 019: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[19/40] seq=19 run_0f000301; N=15; d=0.03125; effective G=0.46875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000301 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x30490A1C --payload-seed 0x06C9C078 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.46875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000301" }

# 020: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[20/40] seq=20 run_0f000302; N=15; d=0.03125; effective G=0.46875; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000302 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x30456A7F --payload-seed 0x06C5A01B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.46875' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p03125' --experiment-tag 'per_node_duty_cycle=0.03125' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000302" }

# 021: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[21/40] seq=21 run_03000401; N=3; d=0.0416667; effective G=0.125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000401 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA0A9256C --payload-seed 0x9629EF08 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000401" }

# 022: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[22/40] seq=22 run_03000402; N=3; d=0.0416667; effective G=0.125; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000402 --active-nodes 1,2,3 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA0A5450F --payload-seed 0x96258F6B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.125' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000402" }

# 023: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[23/40] seq=23 run_06000401; N=6; d=0.0416667; effective G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000401 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x05A977EC --payload-seed 0x3329BD88 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000401" }

# 024: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[24/40] seq=24 run_06000402; N=6; d=0.0416667; effective G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000402 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x05A5178F --payload-seed 0x3325DDEB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000402" }

# 025: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[25/40] seq=25 run_09000401; N=9; d=0.0416667; effective G=0.375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000401 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xEAA9806C --payload-seed 0xDC294A08 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000401" }

# 026: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[26/40] seq=26 run_09000402; N=9; d=0.0416667; effective G=0.375; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000402 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xEAA5E00F --payload-seed 0xDC252A6B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.375' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000402" }

# 027: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[27/40] seq=27 run_0c000401; N=12; d=0.0416667; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000401 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4FA9D2EC --payload-seed 0x79291888 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000401" }

# 028: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[28/40] seq=28 run_0c000402; N=12; d=0.0416667; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000402 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4FA5B28F --payload-seed 0x792578EB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000402" }

# 029: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[29/40] seq=29 run_0f000401; N=15; d=0.0416667; effective G=0.625; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000401 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2CA9E36C --payload-seed 0x1A292908 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.625' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000401" }

# 030: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[30/40] seq=30 run_0f000402; N=15; d=0.0416667; effective G=0.625; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000402 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --traffic-reference-nodes 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2CA5830F --payload-seed 0x1A25496B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.625' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p0416667' --experiment-tag 'per_node_duty_cycle=0.0416667' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000402" }

# 031: Fig. 12; same_bearing_distance_prr
Write-Host "[31/40] seq=31 run_0205c101; N=2; d=0.2; effective G=0.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C101 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2DBF86FE --payload-seed 0x1B3F4C9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c101" }

# 032: Fig. 12; same_bearing_distance_prr
Write-Host "[32/40] seq=32 run_0205c102; N=2; d=0.3; effective G=0.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C102 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x2DB3E69D --payload-seed 0x1B332CF9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'position_index=1' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c102" }

# 033: Fig. 12; same_bearing_distance_prr
Write-Host "[33/40] seq=33 run_0205c201; N=2; d=0.2; effective G=0.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C201 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x21DFE3CE --payload-seed 0x175F29AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c201" }

# 034: Fig. 12; same_bearing_distance_prr
Write-Host "[34/40] seq=34 run_0205c202; N=2; d=0.3; effective G=0.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C202 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x21D383AD --payload-seed 0x175349C9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'position_index=2' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c202" }

# 035: Fig. 12; same_bearing_distance_prr
Write-Host "[35/40] seq=35 run_0205c301; N=2; d=0.2; effective G=0.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C301 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x25FFC0DE --payload-seed 0x137F0ABA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c301" }

# 036: Fig. 12; same_bearing_distance_prr
Write-Host "[36/40] seq=36 run_0205c302; N=2; d=0.3; effective G=0.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C302 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x25F3A0BD --payload-seed 0x13736AD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'position_index=3' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c302" }

# 037: Fig. 12; same_bearing_distance_prr
Write-Host "[37/40] seq=37 run_0205c401; N=2; d=0.2; effective G=0.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C401 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x391F29AE --payload-seed 0x0F9FE3CA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c401" }

# 038: Fig. 12; same_bearing_distance_prr
Write-Host "[38/40] seq=38 run_0205c402; N=2; d=0.3; effective G=0.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C402 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x391349CD --payload-seed 0x0F9383A9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'position_index=4' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c402" }

# 039: Fig. 12; same_bearing_distance_prr
Write-Host "[39/40] seq=39 run_0205c501; N=2; d=0.2; effective G=0.4; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C501 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x3D3F0ABE --payload-seed 0x0BBFC0DA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.4' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.2' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c501" }

# 040: Fig. 12; same_bearing_distance_prr
Write-Host "[40/40] seq=40 run_0205c502; N=2; d=0.3; effective G=0.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0205C502 --active-nodes 1,2 --offered-load 3 --traffic-reference-nodes 10 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x3D336ADD --payload-seed 0x0BB3A0B9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v3' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.3' --experiment-tag 'position_index=5' --experiment-tag 'round=2' --experiment-tag 'round_semantics=duty_condition_not_same_setting_replication' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0205c502" }

