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
Write-Host "REAL RF CAMPAIGN: $CampaignId (3 runs)"

# 037: Fig. 11; decoder_runtime_collision_orders_2_4_8
Write-Host "[37/3] run_0f050b01; N=15; G=3; capture >= 145s"
Read-Host "Arm RX for run_0f050b01 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F050B01 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x0000005E --payload-seed 0x22222222 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig11' --experiment-tag 'layout=A' --experiment-tag 'round=1' --experiment-tag 'target_collision_orders=2_4_8'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f050b01" }

# 038: Fig. 11; decoder_runtime_collision_orders_2_4_8
Write-Host "[38/3] run_0f050b02; N=15; G=3; capture >= 145s"
Read-Host "Arm RX for run_0f050b02 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F050B02 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x0000005D --payload-seed 0x22222222 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig11' --experiment-tag 'layout=A' --experiment-tag 'round=2' --experiment-tag 'target_collision_orders=2_4_8'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f050b02" }

# 039: Fig. 11; decoder_runtime_collision_orders_2_4_8
Write-Host "[39/3] run_0f050b03; N=15; G=3; capture >= 145s"
Read-Host "Arm RX for run_0f050b03 first, then press Enter (Ctrl+C aborts)" | Out-Null
$RemoteCommand = "python3 '$ControllerScript' --run-id 0x0F050B03 --active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --offered-load 3 --duration-s 120 --warmup-s 5 --node-tx-power 10 --global-seed 0x0000005C --payload-seed 0x22222222 --usrp-tx-gain $ControlTxGain --device-args '$DeviceArgs' --manifest-dir '$ManifestDir' --experiment-tag 'campaign=fig9_12_v1' --experiment-tag 'figure=fig11' --experiment-tag 'layout=A' --experiment-tag 'round=3' --experiment-tag 'target_collision_orders=2_4_8'"
ssh $Controller $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Controller failed for run_0f050b03" }

