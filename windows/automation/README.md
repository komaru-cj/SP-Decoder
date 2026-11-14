# 双机自动采集

两台电脑无法联网时，请使用
[`OFFLINE_NO_NETWORK.md`](OFFLINE_NO_NETWORK.md) 中的固定时间槽脚本。该方案不使用
TCP 握手，并把一次链路预检与后续 39 轮正式采集分开。

这两个脚本使用 TCP 握手，不依赖两台电脑的时钟同步：

- Ubuntu：`receiver_campaign_server.py`
- Windows/控制环境：`controller_campaign_client.py`

默认流程为 `CAPTURE_STREAMING_GR → controller CONFIG/START → capture done/metadata valid → 10 s gap → next run`。
第一轮接收端自动运行一次有界前缀链路解码并要求 15 个节点全部出现；后续 run 不解码。
Fig. 12 每次改变位置时，控制端会暂停并显示 Node02 的目标距离。

两台电脑都必须保存同一份 `campaign.json`。连接时会比较 SHA-256 摘要和完整
run ID 列表；文件或 `--start-sequence/--end-sequence` 不一致时拒绝开始。

脚本不传 `--device-args`，适用于每台电脑只连接一台 USRP 的配置。

## 正式运行

先把同一份仓库（至少 `automation/`、控制/接收代码和 generated campaign）
放到两台电脑。

Ubuntu 接收端先运行：

```bash
cd /home/chengjing/real_usrp_experiment
bash real_collision_experiment/automation/start_receiver_campaign.sh
```

看到 `RECEIVER_CAMPAIGN_LISTENING` 后，在 Windows PowerShell 运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& "C:\real_usrp_experiment\real_collision_experiment\automation\start_controller_campaign.ps1" `
  -ReceiverHost "192.168.1.10"
```

`192.168.1.10` 替换为 Ubuntu 接收电脑的 IP。控制端本地保存所有 manifests，
接收端本地保存 IQ、metadata 和第一轮 gate report。

## 中断后续跑

假设 1--20 已完成，从 21 开始时两端必须使用相同范围。

Ubuntu：

```bash
START_SEQUENCE=21 bash real_collision_experiment/automation/start_receiver_campaign.sh
```

Windows：

```powershell
& "C:\real_usrp_experiment\real_collision_experiment\automation\start_controller_campaign.ps1" `
  -ReceiverHost "192.168.1.10" `
  -StartSequence 21
```

恢复执行时不要重复 gate 解码：

```bash
START_SEQUENCE=21 DECODE_FIRST=0 \
  bash real_collision_experiment/automation/start_receiver_campaign.sh
```
