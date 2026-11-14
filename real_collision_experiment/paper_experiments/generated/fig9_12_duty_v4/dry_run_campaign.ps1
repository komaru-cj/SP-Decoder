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
Write-Host "DRY RUN (no RF): $CampaignId (40 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/40] seq=1 run_0f0a0501; N=15; d=0.05; effective G=0.75; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0A0501 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x69C7E0D9 --payload-seed 0x5F472ABD --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0a0501" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/40] seq=2 run_03060501; N=3; d=0.05; effective G=0.15; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03060501 --active-nodes 1,2,3 --offered-load 0.15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6443661F --payload-seed 0x52C3AC7B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.15' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03060501" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/40] seq=3 run_03060502; N=3; d=0.05; effective G=0.15; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03060502 --active-nodes 1,2,3 --offered-load 0.15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x644F067C --payload-seed 0x52CFCC18 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.15' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03060502" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/40] seq=4 run_06070501; N=6; d=0.05; effective G=0.3; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06070501 --active-nodes 1,2,3,4,5,6 --offered-load 0.3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE160249F --payload-seed 0xD7E0EEFB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06070501" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/40] seq=5 run_06070502; N=6; d=0.05; effective G=0.3; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06070502 --active-nodes 1,2,3,4,5,6 --offered-load 0.3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE16C44FC --payload-seed 0xD7EC8E98 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06070502" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/40] seq=6 run_09080501; N=9; d=0.05; effective G=0.45; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09080501 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.45 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xEF81A3F8 --payload-seed 0xD901699C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.45' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09080501" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/40] seq=7 run_09080502; N=9; d=0.05; effective G=0.45; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09080502 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.45 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xEF8DC39B --payload-seed 0xD90D09FF --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.45' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09080502" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/40] seq=8 run_0c090501; N=12; d=0.05; effective G=0.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C090501 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6AA2E178 --payload-seed 0x5C222B1C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c090501" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/40] seq=9 run_0c090502; N=12; d=0.05; effective G=0.6; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C090502 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6AAE811B --payload-seed 0x5C2E4B7F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c090502" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/40] seq=10 run_0f0a0502; N=15; d=0.05; effective G=0.75; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0A0502 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x69CB80BA --payload-seed 0x5F4B4ADE --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0a0502" }

# 011: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[11/40] seq=11 run_03080f01; N=3; d=0.15; effective G=0.45; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03080F01 --active-nodes 1,2,3 --offered-load 0.45 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x8CC05858 --payload-seed 0xBA40923C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.45' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03080f01" }

# 012: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[12/40] seq=12 run_03080f02; N=3; d=0.15; effective G=0.45; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03080F02 --active-nodes 1,2,3 --offered-load 0.45 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x8CCC383B --payload-seed 0xBA4CF25F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.45' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03080f02" }

# 013: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[13/40] seq=13 run_060b0f01; N=6; d=0.15; effective G=0.9; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x060B0F01 --active-nodes 1,2,3,4,5,6 --offered-load 0.9 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x49A53AF9 --payload-seed 0x7F25F09D --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_060b0f01" }

# 014: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[14/40] seq=14 run_060b0f02; N=6; d=0.15; effective G=0.9; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x060B0F02 --active-nodes 1,2,3,4,5,6 --offered-load 0.9 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x49A95A9A --payload-seed 0x7F2990FE --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_060b0f02" }

# 015: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[15/40] seq=15 run_090c0f01; N=9; d=0.15; effective G=1.35; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x090C0F01 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 1.35 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x464CBD1A --payload-seed 0x70CC777E --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.35' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_090c0f01" }

# 016: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[16/40] seq=16 run_090c0f02; N=9; d=0.15; effective G=1.35; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x090C0F02 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 1.35 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4640DD79 --payload-seed 0x70C0171D --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.35' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_090c0f02" }

# 017: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[17/40] seq=17 run_0c0d0f01; N=12; d=0.15; effective G=1.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C0D0F01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 1.8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xC36FFF9A --payload-seed 0xF5EF35FE --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c0d0f01" }

# 018: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[18/40] seq=18 run_0c0d0f02; N=12; d=0.15; effective G=1.8; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C0D0F02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 1.8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xC3639FF9 --payload-seed 0xF5E3559D --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c0d0f02" }

# 019: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[19/40] seq=19 run_0f0e0f01; N=15; d=0.15; effective G=2.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0E0F01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 2.25 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xC00AFE3B --payload-seed 0xF68A345F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0e0f01" }

# 020: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[20/40] seq=20 run_0f0e0f02; N=15; d=0.15; effective G=2.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0E0F02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 2.25 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xC0069E58 --payload-seed 0xF686543C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0e0f02" }

# 021: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[21/40] seq=21 run_030a1901; N=3; d=0.25; effective G=0.75; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x030A1901 --active-nodes 1,2,3 --offered-load 0.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x96448319 --payload-seed 0xA0C4497D --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_030a1901" }

# 022: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[22/40] seq=22 run_030a1902; N=3; d=0.25; effective G=0.75; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x030A1902 --active-nodes 1,2,3 --offered-load 0.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x9648E37A --payload-seed 0xA0C8291E --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_030a1902" }

# 023: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[23/40] seq=23 run_06031901; N=6; d=0.25; effective G=1.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06031901 --active-nodes 1,2,3,4,5,6 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x126FC11D --payload-seed 0x24EF0B79 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06031901" }

# 024: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[24/40] seq=24 run_06031902; N=6; d=0.25; effective G=1.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06031902 --active-nodes 1,2,3,4,5,6 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1263A17E --payload-seed 0x24E36B1A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06031902" }

# 025: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[25/40] seq=25 run_090e1901; N=9; d=0.25; effective G=2.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x090E1901 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 2.25 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x5CC8665B --payload-seed 0x6A48AC3F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_090e1901" }

# 026: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[26/40] seq=26 run_090e1902; N=9; d=0.25; effective G=2.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x090E1902 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 2.25 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x5CC40638 --payload-seed 0x6A44CC5C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_090e1902" }

# 027: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[27/40] seq=27 run_0c051901; N=12; d=0.25; effective G=3; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x98A5047E --payload-seed 0xAE25CE1A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051901" }

# 028: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[28/40] seq=28 run_0c051902; N=12; d=0.25; effective G=3; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x98A9641D --payload-seed 0xAE29AE79 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051902" }

# 029: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[29/40] seq=29 run_0f0f1901; N=15; d=0.25; effective G=3.75; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0F1901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBAEB155B --payload-seed 0x8C6BDF3F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0f1901" }

# 030: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[30/40] seq=30 run_0f0f1902; N=15; d=0.25; effective G=3.75; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0F1902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBAE77538 --payload-seed 0x8C67BF5C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0f1902" }

# 031: Fig. 12; same_bearing_distance_prr
Write-Host "[31/40] seq=31 run_0201c101; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C101 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xAD33C6BC --payload-seed 0x9BB30CD8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c101" }

# 032: Fig. 12; same_bearing_distance_prr
Write-Host "[32/40] seq=32 run_0201c102; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C102 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xAD3FA6DF --payload-seed 0x9BBF6CBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=1' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c102" }

# 033: Fig. 12; same_bearing_distance_prr
Write-Host "[33/40] seq=33 run_0201c201; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C201 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA153A38C --payload-seed 0x97D369E8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c201" }

# 034: Fig. 12; same_bearing_distance_prr
Write-Host "[34/40] seq=34 run_0201c202; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C202 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA15FC3EF --payload-seed 0x97DF098B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=2' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c202" }

# 035: Fig. 12; same_bearing_distance_prr
Write-Host "[35/40] seq=35 run_0201c301; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C301 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA573809C --payload-seed 0x93F34AF8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c301" }

# 036: Fig. 12; same_bearing_distance_prr
Write-Host "[36/40] seq=36 run_0201c302; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C302 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xA57FE0FF --payload-seed 0x93FF2A9B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=3' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c302" }

# 037: Fig. 12; same_bearing_distance_prr
Write-Host "[37/40] seq=37 run_0201c401; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C401 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB99369EC --payload-seed 0x8F13A388 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c401" }

# 038: Fig. 12; same_bearing_distance_prr
Write-Host "[38/40] seq=38 run_0201c402; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C402 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB99F098F --payload-seed 0x8F1FC3EB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=4' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c402" }

# 039: Fig. 12; same_bearing_distance_prr
Write-Host "[39/40] seq=39 run_0201c501; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C501 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBDB34AFC --payload-seed 0x8B338098 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c501" }

# 040: Fig. 12; same_bearing_distance_prr
Write-Host "[40/40] seq=40 run_0201c502; N=2; d=0.25; effective G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0201C502 --active-nodes 1,2 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBDBF2A9F --payload-seed 0x8B3FE0FB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'position_index=5' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0201c502" }

