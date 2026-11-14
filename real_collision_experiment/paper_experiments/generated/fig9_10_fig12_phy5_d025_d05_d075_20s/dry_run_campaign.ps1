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
Write-Host "DRY RUN (no RF): $CampaignId (40 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/40] seq=1 run_0f011901; N=15; PHY=5 SF10/BW250000; d=0.25; effective G=3.75; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F011901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7B2975BC --payload-seed 0x4DA9BFD8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f011901" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/40] seq=2 run_03011901; N=3; PHY=5 SF10/BW250000; d=0.25; effective G=0.75; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03011901 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF729B3BC --payload-seed 0xC1A979D8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03011901" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/40] seq=3 run_03011902; N=3; PHY=5 SF10/BW250000; d=0.25; effective G=0.75; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03011902 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF725D3DF --payload-seed 0xC1A519BB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=0.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03011902" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/40] seq=4 run_06011901; N=6; PHY=5 SF10/BW250000; d=0.25; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06011901 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5229E13C --payload-seed 0x64A92B58 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06011901" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/40] seq=5 run_06011902; N=6; PHY=5 SF10/BW250000; d=0.25; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06011902 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5225815F --payload-seed 0x64A54B3B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06011902" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/40] seq=6 run_09011901; N=9; PHY=5 SF10/BW250000; d=0.25; effective G=2.25; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09011901 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBD2916BC --payload-seed 0x8BA9DCD8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09011901" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/40] seq=7 run_09011902; N=9; PHY=5 SF10/BW250000; d=0.25; effective G=2.25; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09011902 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBD2576DF --payload-seed 0x8BA5BCBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09011902" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/40] seq=8 run_0c011901; N=12; PHY=5 SF10/BW250000; d=0.25; effective G=3; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C011901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x1829443C --payload-seed 0x2EA98E58 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c011901" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/40] seq=9 run_0c011902; N=12; PHY=5 SF10/BW250000; d=0.25; effective G=3; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C011902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x1825245F --payload-seed 0x2EA5EE3B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c011902" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/40] seq=10 run_0f011902; N=15; PHY=5 SF10/BW250000; d=0.25; effective G=3.75; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F011902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.25 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7B2515DF --payload-seed 0x4DA5DFBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p25' --experiment-tag 'per_node_duty_cycle=0.25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f011902" }

# 011: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[11/40] seq=11 run_03023201; N=3; PHY=5 SF10/BW250000; d=0.5; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03023201 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x3E299C2D --payload-seed 0x08A95649 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03023201" }

# 012: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[12/40] seq=12 run_03023202; N=3; PHY=5 SF10/BW250000; d=0.5; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03023202 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x3E25FC4E --payload-seed 0x08A5362A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03023202" }

# 013: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[13/40] seq=13 run_06023201; N=6; PHY=5 SF10/BW250000; d=0.5; effective G=3; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06023201 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x9B29CEAD --payload-seed 0xADA904C9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06023201" }

# 014: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[14/40] seq=14 run_06023202; N=6; PHY=5 SF10/BW250000; d=0.5; effective G=3; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06023202 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x9B25AECE --payload-seed 0xADA564AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=3' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06023202" }

# 015: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[15/40] seq=15 run_09023201; N=9; PHY=5 SF10/BW250000; d=0.5; effective G=4.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09023201 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7429392D --payload-seed 0x42A9F349 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09023201" }

# 016: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[16/40] seq=16 run_09023202; N=9; PHY=5 SF10/BW250000; d=0.5; effective G=4.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09023202 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7425594E --payload-seed 0x42A5932A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09023202" }

# 017: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[17/40] seq=17 run_0c023201; N=12; PHY=5 SF10/BW250000; d=0.5; effective G=6; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C023201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xD1296BAD --payload-seed 0xE7A9A1C9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c023201" }

# 018: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[18/40] seq=18 run_0c023202; N=12; PHY=5 SF10/BW250000; d=0.5; effective G=6; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C023202 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xD1250BCE --payload-seed 0xE7A5C1AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=6' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c023202" }

# 019: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[19/40] seq=19 run_0f023201; N=15; PHY=5 SF10/BW250000; d=0.5; effective G=7.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F023201 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xB2295A2D --payload-seed 0x84A99049 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=7.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f023201" }

# 020: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[20/40] seq=20 run_0f023202; N=15; PHY=5 SF10/BW250000; d=0.5; effective G=7.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F023202 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.5 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xB2253A4E --payload-seed 0x84A5F02A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=7.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p5' --experiment-tag 'per_node_duty_cycle=0.5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f023202" }

# 021: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[21/40] seq=21 run_03034b01; N=3; PHY=5 SF10/BW250000; d=0.75; effective G=2.25; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03034B01 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF52520BD --payload-seed 0xC3A5EAD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03034b01" }

# 022: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[22/40] seq=22 run_03034b02; N=3; PHY=5 SF10/BW250000; d=0.75; effective G=2.25; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03034B02 --active-nodes 1,2,3 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF52940DE --payload-seed 0xC3A98ABA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=2.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03034b02" }

# 023: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[23/40] seq=23 run_06034b01; N=6; PHY=5 SF10/BW250000; d=0.75; effective G=4.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06034B01 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5025723D --payload-seed 0x66A5B859 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06034b01" }

# 024: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[24/40] seq=24 run_06034b02; N=6; PHY=5 SF10/BW250000; d=0.75; effective G=4.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06034B02 --active-nodes 1,2,3,4,5,6 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x5029125E --payload-seed 0x66A9D83A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=4.5' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06034b02" }

# 025: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[25/40] seq=25 run_09034b01; N=9; PHY=5 SF10/BW250000; d=0.75; effective G=6.75; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09034B01 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBF2585BD --payload-seed 0x89A54FD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=6.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09034b01" }

# 026: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[26/40] seq=26 run_09034b02; N=9; PHY=5 SF10/BW250000; d=0.75; effective G=6.75; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09034B02 --active-nodes 1,2,3,4,5,6,7,8,9 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xBF29E5DE --payload-seed 0x89A92FBA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=6.75' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09034b02" }

# 027: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[27/40] seq=27 run_0c034b01; N=12; PHY=5 SF10/BW250000; d=0.75; effective G=9; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C034B01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x1A25D73D --payload-seed 0x2CA51D59 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c034b01" }

# 028: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[28/40] seq=28 run_0c034b02; N=12; PHY=5 SF10/BW250000; d=0.75; effective G=9; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C034B02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x1A29B75E --payload-seed 0x2CA97D3A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=9' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c034b02" }

# 029: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[29/40] seq=29 run_0f034b01; N=15; PHY=5 SF10/BW250000; d=0.75; effective G=11.25; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F034B01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x7925E6BD --payload-seed 0x4FA52CD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=11.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f034b01" }

# 030: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[30/40] seq=30 run_0f034b02; N=15; PHY=5 SF10/BW250000; d=0.75; effective G=11.25; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F034B02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0x792986DE --payload-seed 0x4FA94CBA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=11.25' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=d0p75' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f034b02" }

# 031: Fig. 12; same_bearing_distance_prr
Write-Host "[31/40] seq=31 run_0203c101; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C101 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xED75E69D --payload-seed 0xDBF52CF9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=1' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c101" }

# 032: Fig. 12; same_bearing_distance_prr
Write-Host "[32/40] seq=32 run_0203c102; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C102 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xED7986FE --payload-seed 0xDBF94C9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.02' --experiment-tag 'node_separation_label=2cm' --experiment-tag 'node_separation_m=0.02' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=1' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c102" }

# 033: Fig. 12; same_bearing_distance_prr
Write-Host "[33/40] seq=33 run_0203c201; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C201 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xE11583AD --payload-seed 0xD79549C9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=2' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c201" }

# 034: Fig. 12; same_bearing_distance_prr
Write-Host "[34/40] seq=34 run_0203c202; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C202 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xE119E3CE --payload-seed 0xD79929AA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.05' --experiment-tag 'node_separation_label=5cm' --experiment-tag 'node_separation_m=0.05' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=2' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c202" }

# 035: Fig. 12; same_bearing_distance_prr
Write-Host "[35/40] seq=35 run_0203c301; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C301 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xE535A0BD --payload-seed 0xD3B56AD9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=3' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c301" }

# 036: Fig. 12; same_bearing_distance_prr
Write-Host "[36/40] seq=36 run_0203c302; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C302 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xE539C0DE --payload-seed 0xD3B90ABA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.1' --experiment-tag 'node_separation_label=10cm' --experiment-tag 'node_separation_m=0.1' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=3' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c302" }

# 037: Fig. 12; same_bearing_distance_prr
Write-Host "[37/40] seq=37 run_0203c401; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C401 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF9D549CD --payload-seed 0xCF5583A9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=4' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c401" }

# 038: Fig. 12; same_bearing_distance_prr
Write-Host "[38/40] seq=38 run_0203c402; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C402 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xF9D929AE --payload-seed 0xCF59E3CA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.2' --experiment-tag 'node_separation_label=20cm' --experiment-tag 'node_separation_m=0.2' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=4' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c402" }

# 039: Fig. 12; same_bearing_distance_prr
Write-Host "[39/40] seq=39 run_0203c501; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C501 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xFDF56ADD --payload-seed 0xCB75A0B9 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=5' --experiment-tag 'round=1' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c501" }

# 040: Fig. 12; same_bearing_distance_prr
Write-Host "[40/40] seq=40 run_0203c502; N=2; PHY=5 SF10/BW250000; d=0.75; effective G=1.5; capture >= 30s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0203C502 --active-nodes 1,2 --phy-profile-id 5 --per-node-duty-cycle 0.75 --duration-s 20 --warmup-s 2 --node-tx-power 16 --global-seed 0xFDF90ABE --payload-seed 0xCB79C0DA --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'bearing_deg=0' --experiment-tag 'campaign=fig9_10_fig12_phy5_d025_d05_d075_20s' --experiment-tag 'effective_aggregate_offered_load=1.5' --experiment-tag 'figure=fig12' --experiment-tag 'layout=COLLINEAR_INDOOR' --experiment-tag 'mode=two_node_collision' --experiment-tag 'node1_distance_m=2' --experiment-tag 'node2_distance_m=2.3' --experiment-tag 'node_separation_label=>20cm' --experiment-tag 'node_separation_m=0.3' --experiment-tag 'per_node_duty_cycle=0.75' --experiment-tag 'position_index=5' --experiment-tag 'round=2' --experiment-tag 'round_semantics=independent_replication_same_setting' --experiment-tag 'rx_antenna_spacing_m=0.5' --experiment-tag 'traffic_semantics=fixed_per_node_duty_cycle' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0203c502" }

