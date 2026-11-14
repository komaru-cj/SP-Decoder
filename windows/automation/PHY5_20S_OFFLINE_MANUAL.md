# SF10、20 秒 Fig.9/10/12 离线实验手册

Fig.9/10 使用两个数据 PHY：`phyProfileId=2`（SF10/BW125k/CR4/5）和 `phyProfileId=5`（SF10/BW250k/CR4/5）。接收端统一为双通道 750 ksample/s、500 kHz 模拟带宽、20 dB 增益。节点 TX 功率为 16 dBm；Windows 控制 B210 的 TX gain 固定为 60 dB。控制帧仍为 SF10/BW125k。

Fig.9/10/12 的正式比较默认使用共享前端边界：所有方法复用 SP 的统一候选和最终精确 start/CFO/STO，之后任何对比方案都不再重新同步。LoRaWAN 在该同步上直接做物理 Ch0 top-1 payload 解调；MRC、CIC、PCube、MaLoRaGW 分别只做其方案所需的信道、RSSI/分数频率、PDoA 或信道矩阵/峰特征估计，再独立完成 payload 解码。报告中记录为 `comparison_frontend_scope=common`；这不是各基线独立检测前端的端到端比较。

实验矩阵：

- Fig.9/10：N={3,6,9,12,15}，单节点 duty=0.25，数据带宽={125 kHz,250 kHz}，SF=10；每个设置只做 1 轮，共 10 轮。
- Fig.12：间距={2,5,10,20,>20 cm}，单节点 duty=0.75，每个位置只做 1 轮，共 5 轮。
- 每轮节点业务发送 20 秒；为覆盖五次 CONFIG/START、预热和两台电脑最多 10 秒的启动偏差，IQ 请求 50 秒并额外加 5 秒 guard，即实际接收 55 秒。
- Fig.9/10 固定 slot 为 100 秒，Ubuntu 与 Windows 必须一致。该余量允许最长约 73.8 秒的 B210 watchdog、partial 恢复和 IQ 合并完成，避免拖延后错过下一轮；节点业务发送仍为 20 秒。Fig.12 相邻两轮之间双方统一留 20 秒换位。
- Fig.9/10 的 sequence 1 同时是 BW125k、N=15、duty=0.25 的正式数据点和唯一一次链路预检，不重复采集。Fig.12 继续使用它自己的旧 campaign sequence 11–15；两套 sequence 不应混用。

## 0. 前提

所有 15 个节点必须刷入协议 V2 固件，节点 ID 保持 1–15 唯一。Ubuntu 与 Windows 各连接一台 B210，不指定 serial。两台电脑使用同一份 `real_collision_experiment` 目录。

当前固件源文件已经与控制端和接收端逐字节核对匹配：profile 1–3 使用 bandwidth index 0（BW125k），profile 4–6 使用 index 1（BW250k），profile 7–9 使用 index 2（BW500k）。Fig.9/10 使用 profile 2 和 5；应确保所有节点烧录的是这份已核对源码生成的固件。

正式解码已默认启用前导码轨道＋逐样本连续 SFD 补充检测。每窗候选预算为 `max(64, 4×活跃节点数)`，前导码/SFD 合并后的全局上限为 `max(800, 3×manifest 预期包数)`；一次性 gate 不再覆盖回旧的 400 上限。

Windows 的示例 Python 路径：

```powershell
$Py = "D:\mysoft2\radioconda\python.exe"
```

## 1. 只做一次链路预检

Ubuntu 先执行：

```bash
cd /home/chengjing/real_usrp_experiment
bash real_collision_experiment/automation/start_offline_rx_preflight.sh
```

看到 `START THE WINDOWS CONTROL SCRIPT NOW` 后，Windows 在 10 秒内执行：

```powershell
& "C:\real_usrp_experiment\real_collision_experiment\automation\start_offline_control_preflight.ps1" `
  -PythonExecutable "D:\mysoft2\radioconda\python.exe" `
  -ControlTxGain 60
```

这一步只对 Fig.9/10 sequence 1（`run_0f012131`，profile 2、BW125k、N=15、duty=0.25）采集并做一次快速链路门限检查。它只用于现场发现明显的 USRP/ADC/控制故障，不作为 Fig.9/10/12 的正式统计结果。

Fig.9/10/12 出图前必须用 `analysis/decode_fig9_10_12_middle5s.py` 覆盖生成业务阶段严格中间 5 秒的报告。脚本先把控制事件模板与 IQ 能量对齐以确定 `traffic_start`，再取 `[traffic_start+7.5s, traffic_start+12.5s]`。建库只在这 5 秒完整 IQ 上执行全局、无身份的前导/SFD 检测；manifest schedule 不进入同步检测、精细化或候选排序。画图脚本会拒绝全部 10 秒旧报告和 anonymous v1 旧库。PRR 为 CRC 有效解码匿名物理候选数除以检测匿名物理候选数，TPS 为 CRC 有效解码包数乘 20×8 bit 再除以 5 s。

Fig.12 的当前五个 run 完成采集并复制 manifest 后，按以下顺序处理；只生成现有的 PRR 图，不额外生成 Fig.12 TPS 图：

```bash
cd /home/chengjing/real_usrp_experiment

python3 real_collision_experiment/analysis/decode_fig9_10_12_middle5s.py \
  --include-figure fig12 \
  --run-id 0203c111 --run-id 0203c211 --run-id 0203c311 \
  --run-id 0203c411 --run-id 0203c511 \
  --alignment-only

python3 real_collision_experiment/analysis/build_fine_sync_database.py \
  --run-id 0203c111 --run-id 0203c211 --run-id 0203c311 \
  --run-id 0203c411 --run-id 0203c511 \
  --overwrite

python3 real_collision_experiment/analysis/decode_fig9_10_12_middle5s.py \
  --include-figure fig12 \
  --run-id 0203c111 --run-id 0203c211 --run-id 0203c311 \
  --run-id 0203c411 --run-id 0203c511 \
  --overwrite

python3 real_collision_experiment/analysis/plot_fig9_10_12_from_reports.py
```

## 2. Fig.9/10 剩余正式采集（sequence 2–10）

Ubuntu 先执行：

```bash
cd /home/chengjing/real_usrp_experiment
bash real_collision_experiment/automation/start_offline_rx_fig9_10.sh
```

Windows 在提示后执行：

```powershell
& "C:\real_usrp_experiment\real_collision_experiment\automation\start_offline_control_fig9_10.ps1" `
  -PythonExecutable "D:\mysoft2\radioconda\python.exe" `
  -ControlTxGain 60
```

## 3. Fig.12 正式采集（sequence 11–15）

Ubuntu 先执行：

```bash
cd /home/chengjing/real_usrp_experiment
bash real_collision_experiment/automation/start_offline_rx_fig12.sh
```

Windows 在提示后执行：

```powershell
& "C:\real_usrp_experiment\real_collision_experiment\automation\start_offline_control_fig12.ps1" `
  -PythonExecutable "D:\mysoft2\radioconda\python.exe" `
  -ControlTxGain 60
```

启动脚本前先摆好 2 cm 位置。之后每次出现 `POSITION_BREAK 20s`，在 20 秒内把 Node02 依次移动到 5 cm、10 cm、20 cm 和 >20 cm；每个位置只采一轮。

## 4. 数据与时间

- 55 秒双通道 IQ 在 750 ksample/s 下约 330 MB/轮（约 0.307 GiB）。
- Fig.9/10 的 10 轮 IQ 约 3.30 GB（3.07 GiB）；若再做 Fig.12 的 5 轮，全部约 4.95 GB（4.61 GiB）。连同单轮 merge headroom 和 1 GiB 保留空间，做完整两组前建议预留 7 GiB。
- 预检约 1 分钟；剩余 9 轮 Fig.9/10 按 100 秒 slot 约 15 分钟；Fig.12 含四次 20 秒换位约 7 分钟。两套 campaign 分开启动，不再使用旧的 sequence 2–15 合并入口。
- Fig.9/10 的 Windows manifest 位于 `run_manifests/fig9_10_sf10_bw125_bw250_d025_r3_20s_offline`；Fig.12 manifest 仍位于 `run_manifests/fig9_10_fig12_phy5_d05_d075_r1_20s_offline`。实验后分别整体复制到 Ubuntu。

任何一轮失败时双方继续下一个固定 slot；最终分别查看 `offline_rx_failure_summary` 和 `offline_control_failure_summary`，只重跑列出的 run ID。

若离线解码后发现某个设置存在截断、clipping、节点控制失败或零观测节点，不补造数据，也不重跑整个 campaign；只使用 failure summary 或最终质量汇总中列出的对应 run ID 专门重采该轮。

## 4.1 复制 manifest 后统一匿名建库、解码、报告和画图

把 Windows 产生的 Fig.9/10 manifest 复制到相应 Ubuntu run 目录后执行：

```bash
cd /home/chengjing/real_usrp_experiment
python3 real_collision_experiment/analysis/decode_fig9_10_12_middle5s.py --alignment-only --overwrite
python3 real_collision_experiment/analysis/build_fine_sync_database.py --overwrite
for database in real_collision_experiment/analysis/fig9_10_12_preview/fine_sync/run_*.json; do
  python3 real_collision_experiment/analysis/audit_fine_sync_database.py "$database" || exit 1
done
python3 real_collision_experiment/analysis/decode_fig9_10_12_middle5s.py --overwrite
python3 real_collision_experiment/analysis/plot_fig9_10_12_from_reports.py
```

Fig.11 使用 SF10/BW250 实机运行中目标帧碰撞阶数为 2/4/6/8/10 的完整碰撞组。
覆盖生成最终统一同步口径的报告后运行：

```bash
python3 real_collision_experiment/analysis/decode_fig9_10_12_middle5s.py \
  --run-id 03015131 --run-id 06015131 --run-id 09015131 \
  --run-id 0c015131 --run-id 0f015131 --overwrite

python3 real_collision_experiment/analysis/build_fig11_real_run_intervals.py \
  --orders 2,4,6,8,10 \
  --scenes-per-order 8
```

Fig.11(a) 的时间是一个碰撞组内全部匿名物理候选在共享 SP 最终精同步之后的方案参数估计与
payload 解码耗时之和；Fig.11(b) 的 PRR 是 CRC 有效解码的匿名物理候选数除以共享 fine-sync 库
检测到的匿名物理候选数。场景仅按 manifest 的后处理时间区间和库检测结果选择，不按某个方案
成功与否筛场景，也不把计划身份绑定到候选。

Fig.9/10 的流程先由控制事件能量对齐得到 `traffic_start`，再严格截取业务阶段中间 5 秒。建库器在完整 5 秒 IQ 上做一次全局前导/SFD 搜索和匿名残差搜索；manifest schedule 只在检测完成后折叠为总候选数上限断言，不向检测器暴露计划起点、节点或序号。所有方案读取同一匿名物理候选的 fine start/CFO/STO 种子，身份只在 CRC 有效 payload 中读取。

结果文件：

- `analysis/fig9_10_12_preview/reports/run_*.json`：逐轮完整报告，`detection_and_decode.by_method.<method>.prr` 是共享 fine-sync 库口径的逐轮条件 PRR。
- `analysis/fig9_10_12_preview/fine_sync/run_*.json`：全局匿名物理候选库；旧 schema 会被正式解码器拒绝。
- `analysis/fig9_10_12_preview/fig9_prr_preview.*`：共享匿名物理候选口径 PRR。
- `analysis/fig9_10_12_preview/fig10_tps_preview.*`：20 字节有效载荷 goodput（kbps）。

注意：正式库扫描完整业务中间 5 秒 IQ。真正的节点身份只认 CRC 正确的 `node_id + sequence`；计划包时刻不会形成候选，也不参与同步校准、排序或去重。

## 5. 只重采一个有问题的 Fig.9/10 设置

sequence 与设置对应关系：

| sequence | 设置 |
|---:|---|
| 1 | Fig.9/10，BW125k，N=15，duty=0.25（同时是预检） |
| 2–5 | Fig.9/10，BW125k，N依次为3、6、9、12，duty=0.25 |
| 6–10 | Fig.9/10，BW250k，N依次为3、6、9、12、15，duty=0.25 |

Fig.12 使用另一套 campaign 的 sequence 11–15，仍依次对应 2、5、10、20、>20 cm；不要把这些编号交给下面的 Fig.9/10 单轮重采脚本。

假设 sequence 7 有问题，双方约定同一个重采标签 `retry1`。Ubuntu先执行：

```bash
cd /home/chengjing/real_usrp_experiment
bash real_collision_experiment/automation/rerun_offline_rx_one.sh 7 retry1
```

看到启动提示后，Windows执行：

```powershell
& "C:\real_usrp_experiment\real_collision_experiment\automation\rerun_offline_control_one.ps1" `
  -Sequence 7 `
  -RetryLabel "retry1" `
  -PythonExecutable "D:\mysoft2\radioconda\python.exe" `
  -ControlTxGain 60
```

重采 IQ 保存在 Ubuntu 的 `real_collision_experiment/reruns/retry1/`，manifest 保存在 Windows 的 `run_manifests/fig9_10_sf10_bw125_bw250_d025_r3_20s_reruns/retry1/`。这样不会覆盖原始失败数据。
