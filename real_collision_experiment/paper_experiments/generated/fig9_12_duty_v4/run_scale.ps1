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
Write-Host "REAL RF CAMPAIGN: $CampaignId (30 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/30] seq=1 run_0f0a0501; N=15; d=0.05; effective G=0.75; capture >= 145s"
Read-Host "Arm RX for run_0f0a0501 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0A0501 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x69C7E0D9 --payload-seed 0x5F472ABD --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0a0501" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/30] seq=2 run_03060501; N=3; d=0.05; effective G=0.15; capture >= 145s"
Read-Host "Arm RX for run_03060501 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03060501 --active-nodes 1,2,3 --offered-load 0.15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6443661F --payload-seed 0x52C3AC7B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.15' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03060501" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/30] seq=3 run_03060502; N=3; d=0.05; effective G=0.15; capture >= 145s"
Read-Host "Arm RX for run_03060502 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03060502 --active-nodes 1,2,3 --offered-load 0.15 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x644F067C --payload-seed 0x52CFCC18 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.15' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03060502" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/30] seq=4 run_06070501; N=6; d=0.05; effective G=0.3; capture >= 145s"
Read-Host "Arm RX for run_06070501 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06070501 --active-nodes 1,2,3,4,5,6 --offered-load 0.3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE160249F --payload-seed 0xD7E0EEFB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06070501" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/30] seq=5 run_06070502; N=6; d=0.05; effective G=0.3; capture >= 145s"
Read-Host "Arm RX for run_06070502 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06070502 --active-nodes 1,2,3,4,5,6 --offered-load 0.3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xE16C44FC --payload-seed 0xD7EC8E98 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06070502" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/30] seq=6 run_09080501; N=9; d=0.05; effective G=0.45; capture >= 145s"
Read-Host "Arm RX for run_09080501 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09080501 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.45 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xEF81A3F8 --payload-seed 0xD901699C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.45' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09080501" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/30] seq=7 run_09080502; N=9; d=0.05; effective G=0.45; capture >= 145s"
Read-Host "Arm RX for run_09080502 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09080502 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.45 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xEF8DC39B --payload-seed 0xD90D09FF --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.45' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09080502" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/30] seq=8 run_0c090501; N=12; d=0.05; effective G=0.6; capture >= 145s"
Read-Host "Arm RX for run_0c090501 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C090501 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6AA2E178 --payload-seed 0x5C222B1C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c090501" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/30] seq=9 run_0c090502; N=12; d=0.05; effective G=0.6; capture >= 145s"
Read-Host "Arm RX for run_0c090502 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C090502 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x6AAE811B --payload-seed 0x5C2E4B7F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c090502" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/30] seq=10 run_0f0a0502; N=15; d=0.05; effective G=0.75; capture >= 145s"
Read-Host "Arm RX for run_0f0a0502 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0A0502 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x69CB80BA --payload-seed 0x5F4B4ADE --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p05' --experiment-tag 'per_node_duty_cycle=0.05' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0a0502" }

# 011: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[11/30] seq=11 run_03080f01; N=3; d=0.15; effective G=0.45; capture >= 145s"
Read-Host "Arm RX for run_03080f01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03080F01 --active-nodes 1,2,3 --offered-load 0.45 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x8CC05858 --payload-seed 0xBA40923C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.45' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03080f01" }

# 012: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[12/30] seq=12 run_03080f02; N=3; d=0.15; effective G=0.45; capture >= 145s"
Read-Host "Arm RX for run_03080f02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03080F02 --active-nodes 1,2,3 --offered-load 0.45 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x8CCC383B --payload-seed 0xBA4CF25F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.45' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03080f02" }

# 013: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[13/30] seq=13 run_060b0f01; N=6; d=0.15; effective G=0.9; capture >= 145s"
Read-Host "Arm RX for run_060b0f01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x060B0F01 --active-nodes 1,2,3,4,5,6 --offered-load 0.9 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x49A53AF9 --payload-seed 0x7F25F09D --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_060b0f01" }

# 014: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[14/30] seq=14 run_060b0f02; N=6; d=0.15; effective G=0.9; capture >= 145s"
Read-Host "Arm RX for run_060b0f02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x060B0F02 --active-nodes 1,2,3,4,5,6 --offered-load 0.9 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x49A95A9A --payload-seed 0x7F2990FE --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_060b0f02" }

# 015: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[15/30] seq=15 run_090c0f01; N=9; d=0.15; effective G=1.35; capture >= 145s"
Read-Host "Arm RX for run_090c0f01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x090C0F01 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 1.35 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x464CBD1A --payload-seed 0x70CC777E --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.35' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_090c0f01" }

# 016: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[16/30] seq=16 run_090c0f02; N=9; d=0.15; effective G=1.35; capture >= 145s"
Read-Host "Arm RX for run_090c0f02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x090C0F02 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 1.35 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x4640DD79 --payload-seed 0x70C0171D --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.35' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_090c0f02" }

# 017: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[17/30] seq=17 run_0c0d0f01; N=12; d=0.15; effective G=1.8; capture >= 145s"
Read-Host "Arm RX for run_0c0d0f01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C0D0F01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 1.8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xC36FFF9A --payload-seed 0xF5EF35FE --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c0d0f01" }

# 018: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[18/30] seq=18 run_0c0d0f02; N=12; d=0.15; effective G=1.8; capture >= 145s"
Read-Host "Arm RX for run_0c0d0f02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C0D0F02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 1.8 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xC3639FF9 --payload-seed 0xF5E3559D --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.8' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c0d0f02" }

# 019: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[19/30] seq=19 run_0f0e0f01; N=15; d=0.15; effective G=2.25; capture >= 145s"
Read-Host "Arm RX for run_0f0e0f01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0E0F01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 2.25 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xC00AFE3B --payload-seed 0xF68A345F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0e0f01" }

# 020: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[20/30] seq=20 run_0f0e0f02; N=15; d=0.15; effective G=2.25; capture >= 145s"
Read-Host "Arm RX for run_0f0e0f02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0E0F02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 2.25 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xC0069E58 --payload-seed 0xF686543C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p15' --experiment-tag 'per_node_duty_cycle=0.15' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0e0f02" }

# 021: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[21/30] seq=21 run_030a1901; N=3; d=0.25; effective G=0.75; capture >= 145s"
Read-Host "Arm RX for run_030a1901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x030A1901 --active-nodes 1,2,3 --offered-load 0.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x96448319 --payload-seed 0xA0C4497D --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_030a1901" }

# 022: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[22/30] seq=22 run_030a1902; N=3; d=0.25; effective G=0.75; capture >= 145s"
Read-Host "Arm RX for run_030a1902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x030A1902 --active-nodes 1,2,3 --offered-load 0.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x9648E37A --payload-seed 0xA0C8291E --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_030a1902" }

# 023: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[23/30] seq=23 run_06031901; N=6; d=0.25; effective G=1.5; capture >= 145s"
Read-Host "Arm RX for run_06031901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06031901 --active-nodes 1,2,3,4,5,6 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x126FC11D --payload-seed 0x24EF0B79 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06031901" }

# 024: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[24/30] seq=24 run_06031902; N=6; d=0.25; effective G=1.5; capture >= 145s"
Read-Host "Arm RX for run_06031902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06031902 --active-nodes 1,2,3,4,5,6 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1263A17E --payload-seed 0x24E36B1A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06031902" }

# 025: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[25/30] seq=25 run_090e1901; N=9; d=0.25; effective G=2.25; capture >= 145s"
Read-Host "Arm RX for run_090e1901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x090E1901 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 2.25 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x5CC8665B --payload-seed 0x6A48AC3F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_090e1901" }

# 026: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[26/30] seq=26 run_090e1902; N=9; d=0.25; effective G=2.25; capture >= 145s"
Read-Host "Arm RX for run_090e1902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x090E1902 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 2.25 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x5CC40638 --payload-seed 0x6A44CC5C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_090e1902" }

# 027: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[27/30] seq=27 run_0c051901; N=12; d=0.25; effective G=3; capture >= 145s"
Read-Host "Arm RX for run_0c051901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x98A5047E --payload-seed 0xAE25CE1A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051901" }

# 028: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[28/30] seq=28 run_0c051902; N=12; d=0.25; effective G=3; capture >= 145s"
Read-Host "Arm RX for run_0c051902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x98A9641D --payload-seed 0xAE29AE79 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051902" }

# 029: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[29/30] seq=29 run_0f0f1901; N=15; d=0.25; effective G=3.75; capture >= 145s"
Read-Host "Arm RX for run_0f0f1901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0F1901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBAEB155B --payload-seed 0x8C6BDF3F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0f1901" }

# 030: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[30/30] seq=30 run_0f0f1902; N=15; d=0.25; effective G=3.75; capture >= 145s"
Read-Host "Arm RX for run_0f0f1902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0F1902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBAE77538 --payload-seed 0x8C67BF5C --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_duty_v4' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0f1902" }

