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
Write-Host "DRY RUN (no RF): $CampaignId (36 runs)"

# 001: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[1/36] run_0f010901; N=15; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F010901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x392B44BC --payload-seed 0x0FAB8ED8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f010901" }

# 002: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[2/36] run_01000901; N=1; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x01000901 --active-nodes 1 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xD708B3BC --payload-seed 0xE18879D8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_01000901" }

# 003: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[3/36] run_01000902; N=1; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x01000902 --active-nodes 1 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xD704D3DF --payload-seed 0xE18419BB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_01000902" }

# 004: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[4/36] run_01000903; N=1; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x01000903 --active-nodes 1 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xD700F3FE --payload-seed 0xE180399A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_01000903" }

# 005: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[5/36] run_03000901; N=3; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000901 --active-nodes 1,2,3 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x950892BC --payload-seed 0xA38858D8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000901" }

# 006: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[6/36] run_03000902; N=3; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000902 --active-nodes 1,2,3 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x9504F2DF --payload-seed 0xA38438BB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000902" }

# 007: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[7/36] run_03000903; N=3; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03000903 --active-nodes 1,2,3 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x9500D2FE --payload-seed 0xA380189A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03000903" }

# 008: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[8/36] run_06000901; N=6; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000901 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x3008C03C --payload-seed 0x06880A58 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000901" }

# 009: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[9/36] run_06000902; N=6; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000902 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x3004A05F --payload-seed 0x06846A3B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000902" }

# 010: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[10/36] run_06000903; N=6; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06000903 --active-nodes 1,2,3,4,5,6 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x3000807E --payload-seed 0x06804A1A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06000903" }

# 011: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[11/36] run_09000901; N=9; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000901 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xDF0837BC --payload-seed 0xE988FDD8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000901" }

# 012: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[12/36] run_09000902; N=9; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000902 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xDF0457DF --payload-seed 0xE9849DBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000902" }

# 013: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[13/36] run_09000903; N=9; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09000903 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xDF0077FE --payload-seed 0xE980BD9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09000903" }

# 014: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[14/36] run_0c000901; N=12; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x7A08653C --payload-seed 0x4C88AF58 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000901" }

# 015: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[15/36] run_0c000902; N=12; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x7A04055F --payload-seed 0x4C84CF3B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000902" }

# 016: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[16/36] run_0c000903; N=12; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C000903 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x7A00257E --payload-seed 0x4C80EF1A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c000903" }

# 017: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[17/36] run_0f000901; N=15; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x190854BC --payload-seed 0x2F889ED8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000901" }

# 018: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[18/36] run_0f000902; N=15; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x190434DF --payload-seed 0x2F84FEBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000902" }

# 019: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[19/36] run_0f000903; N=15; G=0.25; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F000903 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.25 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x190014FE --payload-seed 0x2F80DE9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p25' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f000903" }

# 020: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[20/36] run_01010901; N=1; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x01010901 --active-nodes 1 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xF72BA3BC --payload-seed 0xC1AB69D8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_01010901" }

# 021: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[21/36] run_01010902; N=1; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x01010902 --active-nodes 1 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xF727C3DF --payload-seed 0xC1A709BB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_01010902" }

# 022: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[22/36] run_01010903; N=1; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x01010903 --active-nodes 1 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xF723E3FE --payload-seed 0xC1A3299A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_01010903" }

# 023: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[23/36] run_03010901; N=3; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03010901 --active-nodes 1,2,3 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xB52B82BC --payload-seed 0x83AB48D8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03010901" }

# 024: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[24/36] run_03010902; N=3; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03010902 --active-nodes 1,2,3 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xB527E2DF --payload-seed 0x83A728BB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03010902" }

# 025: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[25/36] run_03010903; N=3; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x03010903 --active-nodes 1,2,3 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xB523C2FE --payload-seed 0x83A3089A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_03010903" }

# 026: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[26/36] run_06010901; N=6; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06010901 --active-nodes 1,2,3,4,5,6 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x102BD03C --payload-seed 0x26AB1A58 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06010901" }

# 027: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[27/36] run_06010902; N=6; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06010902 --active-nodes 1,2,3,4,5,6 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x1027B05F --payload-seed 0x26A77A3B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06010902" }

# 028: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[28/36] run_06010903; N=6; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x06010903 --active-nodes 1,2,3,4,5,6 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x1023907E --payload-seed 0x26A35A1A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_06010903" }

# 029: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[29/36] run_09010901; N=9; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09010901 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xFF2B27BC --payload-seed 0xC9ABEDD8 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09010901" }

# 030: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[30/36] run_09010902; N=9; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09010902 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xFF2747DF --payload-seed 0xC9A78DBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09010902" }

# 031: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[31/36] run_09010903; N=9; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x09010903 --active-nodes 1,2,3,4,5,6,7,8,9 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0xFF2367FE --payload-seed 0xC9A3AD9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_09010903" }

# 032: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[32/36] run_0c010901; N=12; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C010901 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x5A2B753C --payload-seed 0x6CABBF58 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=1' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c010901" }

# 033: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[33/36] run_0c010902; N=12; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C010902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x5A27155F --payload-seed 0x6CA7DF3B --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c010902" }

# 034: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[34/36] run_0c010903; N=12; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0C010903 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x5A23357E --payload-seed 0x6CA3FF1A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0c010903" }

# 035: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[35/36] run_0f010902; N=15; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F010902 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x392724DF --payload-seed 0x0FA7EEBB --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=2' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f010902" }

# 036: Fig. 9,10; end_to_end_prr_and_throughput
Write-Host "[36/36] run_0f010903; N=15; G=0.5; capture >= 145s"
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F010903 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 0.5 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x392304FE --payload-seed 0x0FA3CE9A --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig9_10' --experiment-tag 'layout=A' --experiment-tag 'metric_group=g0p5' --experiment-tag 'round=3' --experiment-tag 'traffic_semantics=aggregate_offered_load' --dry-run"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f010903" }

