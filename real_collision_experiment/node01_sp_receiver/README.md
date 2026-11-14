# Node01 单节点闭环接收机

> 当前 campaign 会在运行时选择 SF/BW：BW125/BW250 使用 750 ksample/s，
> BW500 使用 1 Msample/s；B210 模拟带宽分别至少为 500 kHz/1 MHz。
> 操作命令见 [`../automation/PHY5_20S_OFFLINE_MANUAL.md`](../automation/PHY5_20S_OFFLINE_MANUAL.md)。

本目录只服务下一阶段真实碰撞实验的 Node01 单节点闭环验收，不修改主目录现有代码。

## 输入

- 接收端 B210 双通道连续采集的 `.sc16`
- 同名 `.sc16.json`
- 可选控制端 manifest，仅用于离线校验 `run_id/node_id/sequence`，不参与检测、同步、CFO 或信道估计

## 可选数据 PHY

- 487.7 MHz
- SF8/SF10/SF12
- BW125/BW250/BW500 kHz
- CR 4/5
- preamble 8
- explicit header
- PHY CRC on
- sync word `0x34`
- payload 20 bytes
- RX sample rate 750 kS/s/channel（BW125/BW250）或 1 MS/s/channel（BW500）

## 运行示例

采集时先确认没有并发解码或大磁盘任务，并保持当前正式接收增益 20 dB：

```bash
python3 real_collision_experiment/node01_sp_receiver/capture_dual_b210_gr.py \
  --out real_collision_experiment/runs/run_01000001/run_01000001.sc16 \
  --run-id 0x01000001 \
  --duration 60 \
  --center-freq 487700000 \
  --rate 500000 \
  --gain 20 \
  --bandwidth 200000 \
  --channels 0,1 \
  --antenna RX2
```

采集以每通道目标 sample 数完成；无文件增长 30 秒或超过有限 watchdog 才失败。
失败时两个通道会自动合并为不覆盖旧文件的 `.partial.sc16`，原 `.tmp` 继续
保留。脚本默认拒绝删除同名旧数据；只有确认已有残片另存后才使用
`--overwrite`。正式实验要求控制台没有 UHD `O`（overflow）、最终状态为
`CAPTURE_DONE_GR` 且 `samples=30000000`。

解码示例：

```bash
python3 real_collision_experiment/node01_sp_receiver/sp_node01_receiver.py \
  --iq real_collision_experiment/runs/run_01000101/run_01000101.sc16 \
  --metadata real_collision_experiment/runs/run_01000101/run_01000101.sc16.json \
  --out real_collision_experiment/runs/run_01000101/node01_sp_report.json \
  --run-id 0x01000101 \
  --active-node 1 \
  --threshold 5.5 \
  --max-candidates 100 \
  --frontend-candidates-per-window 8 \
  --cfo-min -32 \
  --cfo-max 32
```

这里的候选预算不能小于单节点 run 的预期发包数。当前 30 秒实采中
Node01 有 26 个预期包，因此默认使用 100 个全局候选、每个 0.8 秒包局部
能量窗口 8 个前端候选。能量门限会在 manifest 提供期望包数时自动升高到
“事件数接近期望包数但不低于它”的最低档，避免强信号削顶把一个包切成多个
重复窗口。三块已测节点的物理 CFO 约为 `+11` 到 `+21` bins；最终候选仍
限制在 `[-32, 32]`，SFD 内部保留独立的去别名半径。

默认快速路径不开 separated-preamble 大网格。只有整窗没有强 SFD 候选时，
补扫一次半符号错位的检测相位；只有 explicit header 正确但 PHY CRC 失败时，
才在已判决 bins 上做有界的分段 `±1 bin` 漂移修复，不重复 FFT。确需原 SP
局部网格时可显式加 `--fast-grid-refine`。

TX power 提高后不要继续使用过高 RX gain。接收报告会输出 `adc` 统计；任何
`clipped_count > 0` 都表示采集不适合作为 100% PRR 验收数据，应先降低 RX
gain（采集脚本默认 20 dB），再重新采集。

## 输出

每个候选输出：

- start/CFO/STO/channel reliability/lambda
- Ch0、Ch1、MRC、SP 四路 symbol bins
- LoRa PHY payload、PHY CRC、应用层 CRC
- `run_id/node_id/sequence` 校验和去重结果

闭环通过标准：Node01 的应用层 CRC 通过包数接近 UART 记录的发送包数，且 sequence 连续递增。
