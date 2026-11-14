param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 0
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_10_fig12_d025_d05_d07_r1"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "REAL RF CAMPAIGN: $CampaignId (10 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/10] seq=1 run_0f0f1901; N=15; d=0.25; effective G=3.75; capture >= 145s"
Read-Host "Arm RX for run_0f0f1901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F0F1901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xBAEB155B --payload-seed 0x8C6BDF3F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f0f1901" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/10] seq=2 run_030a1901; N=3; d=0.25; effective G=0.75; capture >= 145s"
Read-Host "Arm RX for run_030a1901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x030A1901 --active-nodes 1,2,3 --offered-load 0.75 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x96448319 --payload-seed 0xA0C4497D --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_030a1901" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/10] seq=3 run_06031901; N=6; d=0.25; effective G=1.5; capture >= 145s"
Read-Host "Arm RX for run_06031901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06031901 --active-nodes 1,2,3,4,5,6 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x126FC11D --payload-seed 0x24EF0B79 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06031901" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/10] seq=4 run_090e1901; N=9; d=0.25; effective G=2.25; capture >= 145s"
Read-Host "Arm RX for run_090e1901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x090E1901 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 2.25 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x5CC8665B --payload-seed 0x6A48AC3F --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_090e1901" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/10] seq=5 run_0c051901; N=12; d=0.25; effective G=3; capture >= 145s"
Read-Host "Arm RX for run_0c051901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C051901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x98A5047E --payload-seed 0xAE25CE1A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c051901" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/10] seq=6 run_03033201; N=3; d=0.5; effective G=1.5; capture >= 145s"
Read-Host "Arm RX for run_03033201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03033201 --active-nodes 1,2,3 --offered-load 1.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x1E0A8C2D --payload-seed 0x288A4649 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03033201" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/10] seq=7 run_06053201; N=6; d=0.5; effective G=3; capture >= 145s"
Read-Host "Arm RX for run_06053201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06053201 --active-nodes 1,2,3,4,5,6 --offered-load 3 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x7BC0BECE --payload-seed 0x4D4074AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06053201" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/10] seq=8 run_09103201; N=9; d=0.5; effective G=4.5; capture >= 145s"
Read-Host "Arm RX for run_09103201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09103201 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 4.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0x367F1804 --payload-seed 0x00FFD260 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09103201" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/10] seq=9 run_0c113201; N=12; d=0.5; effective G=6; capture >= 145s"
Read-Host "Arm RX for run_0c113201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C113201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 6 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB35C5A84 --payload-seed 0x85DC90E0 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c113201" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/10] seq=10 run_0f123201; N=15; d=0.5; effective G=7.5; capture >= 145s"
Read-Host "Arm RX for run_0f123201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F123201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 7.5 --duration-s 120 --warmup-s 5 --node-tx-power 16 --global-seed 0xB0395B25 --payload-seed 0x86B99141 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_d025_d05_d07_r1' --experiment-tag 'effective_aggregate_offered_load=7.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f123201" }

