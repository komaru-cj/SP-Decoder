# Fig. 9–12 无网络、固定时间槽采集

> 新的 profile 5、20 秒、协议 V2 实验请使用
> [`PHY5_20S_OFFLINE_MANUAL.md`](PHY5_20S_OFFLINE_MANUAL.md)。下文仅保留为旧协议 V1
> campaign 的历史说明。

这个方案不使用 IP、端口、ping 或两机握手。Ubuntu 和 Windows 分别读取同一份
`campaign.json`，按照相同顺序和固定时间槽运行。

## 固定时序

每个普通时间槽为 240 秒：

| 相对控制端本轮开始 | 控制端动作 |
|---:|---|
| 约 1 秒 | 发送 CONFIG 1 |
| 约 2 秒 | 发送 CONFIG 2 |
| 约 3 秒 | 发送 CONFIG 3 |
| 约 4 秒 | 发送 CONFIG 4 |
| 约 5 秒 | 发送 CONFIG 5 |
| 约 9.0–11.4 秒 | 发送 START 1–5；5 个 START 都指向同一个 warm-up 起点 |
| 约 13 秒 | 节点统一进入 warm-up |
| 约 18 秒 | 节点自动按本轮参数发包 |
| 到 240 秒 | 控制端不再发送，等待下一轮固定槽 |

Ubuntu 在本轮开始时启动双通道接收：

- Fig. 9/10 和 Fig. 12：接收 155 秒；
- 两个接收通道的 gain 都固定为 20 dB；
- 剩余时间用于停止流图、合并双通道 IQ 和等待下一时间槽；
- 下一轮按照程序启动时刻加固定偏移开始，不把上一轮处理耗时累加进去。

先启动 Ubuntu，再在 10 秒内启动 Windows。这样 Windows 相对 Ubuntu 的启动偏差会在
整场实验中保持不变，10 秒接收保护时间可以覆盖这个偏差。不要在运行中暂停其中任意
一个脚本。

Fig. 12 的位置 1–5 之前，两边会自动插入 300 秒换位时间。屏幕会显示 Node02 的目标
距离；不需要按回车，倒计时结束后自动继续。

## 第一步：只采集并解码一轮

节点全部摆好并上电。Ubuntu 先执行：

```bash
cd /home/chengjing/real_usrp_experiment
bash real_collision_experiment/automation/start_offline_rx_preflight.sh
```

然后在 10 秒内到 Windows PowerShell 执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& "C:\real_usrp_experiment\real_collision_experiment\automation\start_offline_control_preflight.ps1"
```

控制端约十几秒后结束是正常的；节点仍在执行这一轮。等待 Ubuntu 完成 155 秒采集和
一次低内存链路解码。链路门只分析 IQ 的 20–50 秒并分块检查完整 155 秒 ADC 数据，
从而跳过控制端的 CONFIG/START 和 warm-up、覆盖 v4 首轮5%占空比下各节点的发包机会；前端
`energy_min_ratio=3`，且不运行
四个论文比较解码器。只有看到下面的消息，才说明链路、节点和 ADC 检查通过：

```text
ONE_TIME_GATE_OK
```

如果失败，不要启动剩余 39 轮，先调整节点、天线或增益。

如果采集已经成功、只有解码过程被 `SIGKILL 9` 或 OOM 中断，不要重新发包。更新代码后
直接复用现有 IQ：

```bash
cd /home/chengjing/real_usrp_experiment
bash real_collision_experiment/automation/retry_offline_rx_gate.sh
```

若输出显示 `clipped_count=[0, 0]` 但 15 个节点全部缺失，说明采集文件中没有节点业务包，
应检查节点 LED 是否经历“CONFIG 后常亮、START 后熄灭、随后发送闪烁”。

## 第二步：自动采集剩余 39 轮

完整 40 轮最终 IQ 约占 21.6 GiB。加上单轮合并临时空间和默认 1 GiB 保留空间，
开始完整实验前应保证约 23.2 GiB 可用；脚本会针对本次所选轮次做精确检查。

如果已经准备了大容量磁盘，Ubuntu 使用 `RUNS_ROOT` 指定一次输出位置；这不是 run_id
或实验参数：

```bash
cd /home/chengjing/real_usrp_experiment
RUNS_ROOT=/你的大容量磁盘/fig9_12_runs \
  bash real_collision_experiment/automation/start_offline_rx_remaining.sh
```

如果已在当前工作盘腾出足够空间，可以直接执行：

```bash
cd /home/chengjing/real_usrp_experiment
bash real_collision_experiment/automation/start_offline_rx_remaining.sh
```

Ubuntu 脚本通过空间检查并开始第 2 轮后，在 10 秒内到 Windows 执行：

```powershell
& "C:\real_usrp_experiment\real_collision_experiment\automation\start_offline_control_remaining.ps1"
```

剩余部分约需 3 小时，包括五次 Fig. 12 换位等待。后续 39 轮只采集和校验文件，
不执行解码。

## 实验结束后复制什么

从 Windows 完整复制这个目录回 Ubuntu：

```text
C:\real_usrp_experiment\real_collision_experiment\run_manifests\fig9_12_duty_v4_offline\
```

其中应有 40 个 `run_*.json`。Ubuntu 保留全部 `run_*/run_*.sc16` 和对应
`.sc16.json`。manifest 本身不包含接收数据，不能代替 Ubuntu 的 IQ 文件。

## 防错规则

- 两边必须都运行 preflight，或者都运行 remaining，不能混用。
- 每次都是 Ubuntu 先启动，Windows 在 10 秒内启动。
- remaining 阶段的单轮错误会被记录并跳到下一个固定槽；不要只在一边临时补轮。
- 脚本拒绝覆盖已有 IQ 或 manifest；发生中断时先记录失败的 sequence，再决定恢复范围。
- 两台电脑不需要校时，因为时间槽都相对于各自脚本的启动时刻计算。
- Fig. 9 使用完整检测包上的 `conditional_prr`。每个 `(N,d)` 计划保留 2 个有效轮次。
- 经现场证据确认的硬件、控制或采集故障应归档整个 attempt，并用相同设置重采；不能因
  PRR 低而排除，也不能删除单个节点或给 TPS 补值。

正式 remaining 批次不会因为某个节点 0 包而中途停止：remaining 阶段本来就只采集、
不在线解码。全部轮次结束并完成离线解码后，统一汇总需要重跑的
`sequence/run_id/(N,G,round)`。随后生成一对包含相同重跑清单的 Ubuntu RX 脚本和
Windows control 脚本；必须把 Windows 脚本及其重跑清单复制到控制电脑后再开始补采。
重跑结果写入新的 attempt 目录，原失败 attempt 保留用于审计。接收端不能在控制端
不知情时单方面补足。
