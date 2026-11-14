param(
    [string]$Controller = "control-user@CONTROL_PC_IP",
    [string]$RemoteRoot = "/home/control/real_usrp_experiment",
    [string]$DeviceArgs = "serial=CONTROL_B210_SERIAL",
    [double]$ControlTxGain = 0
)
$ErrorActionPreference = "Stop"
$CampaignId = "fig9_10_fig12_phy5_d025_d05_d075_20s"
$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"
$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"
Write-Host "REAL RF CAMPAIGN: $CampaignId (30 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/30] seq=1 run_0f011901; N=15; PHY=5 SF10/BW250000; d=0.25; effective G=3.75; capture >= 30s"
Read-Host "Arm RX for run_0f011901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F011901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7B2975BC --payload-seed 0x4DA9BFD8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f011901" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/30] seq=2 run_03011901; N=3; PHY=5 SF10/BW250000; d=0.25; effective G=0.75; capture >= 30s"
Read-Host "Arm RX for run_03011901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03011901 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF729B3BC --payload-seed 0xC1A979D8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03011901" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/30] seq=3 run_03011902; N=3; PHY=5 SF10/BW250000; d=0.25; effective G=0.75; capture >= 30s"
Read-Host "Arm RX for run_03011902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03011902 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF725D3DF --payload-seed 0xC1A519BB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03011902" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/30] seq=4 run_06011901; N=6; PHY=5 SF10/BW250000; d=0.25; effective G=1.5; capture >= 30s"
Read-Host "Arm RX for run_06011901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06011901 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5229E13C --payload-seed 0x64A92B58 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06011901" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/30] seq=5 run_06011902; N=6; PHY=5 SF10/BW250000; d=0.25; effective G=1.5; capture >= 30s"
Read-Host "Arm RX for run_06011902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06011902 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5225815F --payload-seed 0x64A54B3B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06011902" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/30] seq=6 run_09011901; N=9; PHY=5 SF10/BW250000; d=0.25; effective G=2.25; capture >= 30s"
Read-Host "Arm RX for run_09011901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09011901 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBD2916BC --payload-seed 0x8BA9DCD8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09011901" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/30] seq=7 run_09011902; N=9; PHY=5 SF10/BW250000; d=0.25; effective G=2.25; capture >= 30s"
Read-Host "Arm RX for run_09011902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09011902 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBD2576DF --payload-seed 0x8BA5BCBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09011902" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/30] seq=8 run_0c011901; N=12; PHY=5 SF10/BW250000; d=0.25; effective G=3; capture >= 30s"
Read-Host "Arm RX for run_0c011901 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C011901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x1829443C --payload-seed 0x2EA98E58 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c011901" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/30] seq=9 run_0c011902; N=12; PHY=5 SF10/BW250000; d=0.25; effective G=3; capture >= 30s"
Read-Host "Arm RX for run_0c011902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C011902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x1825245F --payload-seed 0x2EA5EE3B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c011902" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/30] seq=10 run_0f011902; N=15; PHY=5 SF10/BW250000; d=0.25; effective G=3.75; capture >= 30s"
Read-Host "Arm RX for run_0f011902 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F011902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7B2515DF --payload-seed 0x4DA5DFBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f011902" }

# 011: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[11/30] seq=11 run_03023201; N=3; PHY=5 SF10/BW250000; d=0.5; effective G=1.5; capture >= 30s"
Read-Host "Arm RX for run_03023201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03023201 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x3E299C2D --payload-seed 0x08A95649 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03023201" }

# 012: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[12/30] seq=12 run_03023202; N=3; PHY=5 SF10/BW250000; d=0.5; effective G=1.5; capture >= 30s"
Read-Host "Arm RX for run_03023202 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03023202 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x3E25FC4E --payload-seed 0x08A5362A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03023202" }

# 013: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[13/30] seq=13 run_06023201; N=6; PHY=5 SF10/BW250000; d=0.5; effective G=3; capture >= 30s"
Read-Host "Arm RX for run_06023201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06023201 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x9B29CEAD --payload-seed 0xADA904C9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06023201" }

# 014: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[14/30] seq=14 run_06023202; N=6; PHY=5 SF10/BW250000; d=0.5; effective G=3; capture >= 30s"
Read-Host "Arm RX for run_06023202 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06023202 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x9B25AECE --payload-seed 0xADA564AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06023202" }

# 015: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[15/30] seq=15 run_09023201; N=9; PHY=5 SF10/BW250000; d=0.5; effective G=4.5; capture >= 30s"
Read-Host "Arm RX for run_09023201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09023201 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7429392D --payload-seed 0x42A9F349 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09023201" }

# 016: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[16/30] seq=16 run_09023202; N=9; PHY=5 SF10/BW250000; d=0.5; effective G=4.5; capture >= 30s"
Read-Host "Arm RX for run_09023202 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09023202 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7425594E --payload-seed 0x42A5932A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09023202" }

# 017: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[17/30] seq=17 run_0c023201; N=12; PHY=5 SF10/BW250000; d=0.5; effective G=6; capture >= 30s"
Read-Host "Arm RX for run_0c023201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C023201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xD1296BAD --payload-seed 0xE7A9A1C9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c023201" }

# 018: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[18/30] seq=18 run_0c023202; N=12; PHY=5 SF10/BW250000; d=0.5; effective G=6; capture >= 30s"
Read-Host "Arm RX for run_0c023202 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C023202 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xD1250BCE --payload-seed 0xE7A5C1AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c023202" }

# 019: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[19/30] seq=19 run_0f023201; N=15; PHY=5 SF10/BW250000; d=0.5; effective G=7.5; capture >= 30s"
Read-Host "Arm RX for run_0f023201 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F023201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xB2295A2D --payload-seed 0x84A99049 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=7.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f023201" }

# 020: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[20/30] seq=20 run_0f023202; N=15; PHY=5 SF10/BW250000; d=0.5; effective G=7.5; capture >= 30s"
Read-Host "Arm RX for run_0f023202 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F023202 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xB2253A4E --payload-seed 0x84A5F02A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=7.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f023202" }

# 021: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[21/30] seq=21 run_03034b01; N=3; PHY=5 SF10/BW250000; d=0.75; effective G=2.25; capture >= 30s"
Read-Host "Arm RX for run_03034b01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03034B01 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF52520BD --payload-seed 0xC3A5EAD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03034b01" }

# 022: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[22/30] seq=22 run_03034b02; N=3; PHY=5 SF10/BW250000; d=0.75; effective G=2.25; capture >= 30s"
Read-Host "Arm RX for run_03034b02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03034B02 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF52940DE --payload-seed 0xC3A98ABA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03034b02" }

# 023: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[23/30] seq=23 run_06034b01; N=6; PHY=5 SF10/BW250000; d=0.75; effective G=4.5; capture >= 30s"
Read-Host "Arm RX for run_06034b01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06034B01 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5025723D --payload-seed 0x66A5B859 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06034b01" }

# 024: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[24/30] seq=24 run_06034b02; N=6; PHY=5 SF10/BW250000; d=0.75; effective G=4.5; capture >= 30s"
Read-Host "Arm RX for run_06034b02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06034B02 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5029125E --payload-seed 0x66A9D83A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06034b02" }

# 025: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[25/30] seq=25 run_09034b01; N=9; PHY=5 SF10/BW250000; d=0.75; effective G=6.75; capture >= 30s"
Read-Host "Arm RX for run_09034b01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09034B01 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBF2585BD --payload-seed 0x89A54FD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=6.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09034b01" }

# 026: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[26/30] seq=26 run_09034b02; N=9; PHY=5 SF10/BW250000; d=0.75; effective G=6.75; capture >= 30s"
Read-Host "Arm RX for run_09034b02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09034B02 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBF29E5DE --payload-seed 0x89A92FBA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=6.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09034b02" }

# 027: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[27/30] seq=27 run_0c034b01; N=12; PHY=5 SF10/BW250000; d=0.75; effective G=9; capture >= 30s"
Read-Host "Arm RX for run_0c034b01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C034B01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x1A25D73D --payload-seed 0x2CA51D59 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c034b01" }

# 028: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[28/30] seq=28 run_0c034b02; N=12; PHY=5 SF10/BW250000; d=0.75; effective G=9; capture >= 30s"
Read-Host "Arm RX for run_0c034b02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C034B02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x1A29B75E --payload-seed 0x2CA97D3A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c034b02" }

# 029: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[29/30] seq=29 run_0f034b01; N=15; PHY=5 SF10/BW250000; d=0.75; effective G=11.25; capture >= 30s"
Read-Host "Arm RX for run_0f034b01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F034B01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7925E6BD --payload-seed 0x4FA52CD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=11.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f034b01" }

# 030: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[30/30] seq=30 run_0f034b02; N=15; PHY=5 SF10/BW250000; d=0.75; effective G=11.25; capture >= 30s"
Read-Host "Arm RX for run_0f034b02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F034B02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x792986DE --payload-seed 0x4FA94CBA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=11.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f034b02" }

