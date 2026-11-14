# Fig. 9–12 实验设计与控制参数

## 1. 正式实验矩阵

当前冻结的 campaign 是 `fig9_12_duty_v4`。运行前必须给全部节点烧录扩展 traffic
profile 的新版固件：

所有轮次的节点射频发射功率固定为 **16 dBm**；Windows 命令中的
`ControlTxGain` 只控制控制 B210，不改变节点数据包功率。
Ubuntu 接收 B210 的两个通道增益都固定为 **20 dB**；首轮链路门会检查
ADC clipping，若 clipping 非零则不应继续后续轮次。

| 图 | 实验条件 | USRP run 数 |
|---|---|---:|
| Fig. 9/10 | `N={3,6,9,12,15}`，`d={0.05,0.15,0.25}`，每个设置 2 个独立 seed | 30 |
| Fig. 11 | 从 SF10/BW250 实机业务窗选择碰撞组；报告 decoder-only 时间与 shared-fine-sync conditional PRR | 0 |
| Fig. 12 | 间隔 `2/5/10/20/>20 cm`，固定 `d=0.25`，每点 2 个独立 seed | 10 |
| 合计 | — | 40 |

Fig. 12 的“5×2=10”表示每个距离的同一设置做两次真正重复。

## 2. 控制端怎样保持相同单节点占空比

节点固件和控制端使用相同的16项 profile 表。控制协议中：

- active mask 决定哪些物理节点发包；
- `numActiveNodes` 必须等于 active mask 的置位数；
- `G / numActiveNodes` 决定每个活动节点的平均占空比；
- manifest 记录真实聚合负载 `G=N×d`。

编码表为：

| N | d=5% | d=15% | d=25% |
|---:|---:|---:|---:|
| 3 | G=0.15 | G=0.45 | G=0.75 |
| 6 | G=0.30 | G=0.90 | G=1.50 |
| 9 | G=0.45 | G=1.35 | G=2.25 |
| 12 | G=0.60 | G=1.80 | G=3.00 |
| 15 | G=0.75 | G=2.25 | G=3.75 |

固件 profile ID 的唯一映射见 `docs/11_节点固件扩展traffic_profile提示词.md`。
`N=15,d=0.25` 是有意设置的高过载点，平均碰撞阶数会明显超过 2--4 包；它用于观察
各方法在拥塞区的退化，不应在后处理时因 PRR 很低而删除。

## 3. 统计口径

Fig. 9 和 Fig. 10 复用同一批 30 个 IQ captures，比较：

| 论文图例 | report method |
|---|---|
| Standard LoRaWAN | `ch0` |
| MRC | `mrc` |
| CIC | `cic` |
| PCube | `pcube` |
| MaLoRaGW | `maloragw` |
| SP-Decoder | `sp_sync_refine` |

Fig. 9 主指标为 common frontend 完整检测包上的：

```text
conditional_prr = (M + U) / (D + U)
```

其中 `M` 为身份匹配且 CRC 有效的解码包数，`U` 为 CRC 有效但身份不匹配的解码包数，`D` 为
共享 fine-sync 库检出的包数。`U` 在逐轮 JSON 和导出 CSV 中单列保留。

Fig. 10 主指标为有效解码 TPS：

```text
effective_tps = (M + U) × 20 × 8 / max(business_duration_s, decoder_work_s)
```

`decoder_work_s` 是该方案在全部共享候选（包括失败候选）上的 post-shared-sync 参数估计与
payload 解码时间之和；公共 fine-sync 前端对所有方案均排除。因而解码快于实时输入时，Fig.10
仍受 5 s 业务窗口限制；解码慢于实时输入时，Fig.10 反映解码器的处理瓶颈。

两个 seed 的 run-level 指标用于计算 95% CI。由于只有两个重复，置信区间会很不稳定；
图和论文中应明确标注 `n=2`，不能把同一 run 内的包当成独立重复。

活动节点 0 包只触发故障复核。只有结合控制日志、LED/UART、RF 能量和采集 metadata
确认属于硬件/控制/采集故障时，才丢弃整个 attempt 并重跑同一设置；不能因结果差而
删数据，也不能只排除单个节点或补造吞吐量。

## 3.1 共享 Fine-Sync 匿名物理库 v2：全局建库与审计

Fig.9/10/11 的正式窗口为业务阶段严格中间 5 秒，即 20 秒业务区间内的
`[traffic_start+7.5s, traffic_start+12.5s]`。PRR 为 CRC 有效解码匿名物理候选数除以
检测匿名物理候选数；Fig.10 则遵循上面的有效解码 TPS 定义。节点和序号只允许在 CRC 有效
payload 中读取，不能参与同步检测或候选入库。

`analysis/build_fine_sync_database.py` 的 v2 建库流程如下：

1. 读取完整中间 5 秒 IQ，在物理双通道、PCA 和残差投影上执行一次全窗前导/SFD 搜索。
2. manifest 只用于确定业务窗口、PHY 参数和检测完成后的总候选数上限断言；计划起点、节点、
   序号不会传给检测器，也不会生成逐计划包搜索窗口。
3. 每个 IQ 结构候选围绕自身检测起点完成 SFD 锚定、CFO/STO、双通道信道和固定 CFO 小范围
   start 细化。只有同时通过 preamble、两个 Sync-word chirp 和两个 SFD chirp 结构证书者入库。
4. 第一轮发现的强候选仅用于已知前导/Sync/SFD 消除和空间零陷；残差重新做完整全窗检测，
   不解码或消除 payload，也不使用 manifest 时间。
5. 去重必须同时满足严格的物理起点、CFO 和双通道信道方向一致性。结构分数只能在三维都一致
   的算法别名组内选择代表；不同 CFO 或不同信道方向的弱候选不会被强候选替换。
6. manifest 总数是失败断言而不是排序额度。若全局去重后的结构候选超过上限，建库直接失败，
   不允许按分数截断。输出 schema 为 `fine_sync_anonymous_physical_v2`，不含 node/sequence、
   planned/expected start、node offset 或 association 字段。

先为问题 run 建到临时目录，避免在审计前覆盖正式库或正在读取它的解码任务：

```bash
cd /home/chengjing/real_usrp_experiment/real_collision_experiment/analysis
python3 build_fine_sync_database.py \
  --run-id 03012131 \
  --out-dir /tmp/run_03012131_fine_sync_v2 \
  --overwrite |& tee /tmp/run_03012131_fine_sync_v2.build.log

python3 audit_fine_sync_database.py \
  /tmp/run_03012131_fine_sync_v2/fine_sync/run_03012131.json
```

只有第二条命令输出 `FINE_SYNC_DATABASE_AUDIT_OK` 才能把同一 `--run-id` 的 `--out-dir` 改为
`fig9_10_12_preview` 覆盖正式库。审计器会拒绝非 5 秒窗口、旧 schema、schedule-guided 标记、
身份/计划时间字段、缺结构证书、残留物理别名和超过总上限的候选。失败时不得用该库重解码或画图。

## 4. Fig. 11 实机碰撞区间口径

Fig. 11 不新增 USRP 采集，直接使用 SF10/BW250 的正式业务中间五秒报告及其 manifest。
碰撞阶数定义为：目标包自身，加上与其完整帧时间区间存在正长度重叠的其他包数；
不是某一个采样时刻的瞬时并发数。场景仅按 manifest 调度选择，不按任何解码器的
CRC、SER、margin 或运行时间挑数据。

- Fig. 11(a) 对一个碰撞组内全部包的“方案参数估计 + payload 解码”时间求和；
  共享 SP 最终精同步的耗时不重复计入各方案；
- Fig. 11(b) 的 PRR 为（身份匹配且 CRC 有效的成功解码包数 + CRC 有效但身份不匹配的包数）/
  （共享 fine-sync 库中检测到的包数 + CRC 有效但身份不匹配的包数）。身份不匹配数保留在审计
  字段中，不再静默视为解码失败。
- 所有方法共享 SP 候选与预载荷 fine start/CFO/STO 种子；LoRaWAN/MRC/CIC 保持该
  同步不变，PCube/MaLoRaGW 可在种子附近以各自物理-Rx/PCA 前导、Sync-word、SFD
  做一次有界局部 start/CFO 重估。该步骤不读取 payload、FEC/CRC、manifest、期望
  payload、SP lambda 或 SP residual；匹配失败则回退到共享种子。之后各自完成论文
  所需参数估计和解码；
- payload 真值由 manifest 的 payload seed 经正式 PHY encoder 重建，只用于 CSV 中的
  辅助 SER 审计，不传给解码器，也不改变 Fig. 11(b) 的 PRR 口径。

先覆盖生成所需 BW250 正式报告，再画图：

```bash
cd /home/chengjing/real_usrp_experiment
python3 real_collision_experiment/analysis/decode_fig9_10_12_middle5s.py \
  --run-id 03015131 --run-id 06015131 --run-id 09015131 \
  --run-id 0c015131 --run-id 0f015131 --overwrite

python3 real_collision_experiment/analysis/build_fig11_real_run_intervals.py \
  --orders 2,4,6,8,10 \
  --scenes-per-order 8
```

主图为 `real_usrp_outputs/fig11_real_run_intervals/fig11_real_decoder_time_ser.*`；
区间表、逐场景结果、聚合结果和审计 JSON 保存在同一目录。旧报告会被脚本明确
标为 `stale report`，不会与最终统一同步口径混用。

## 5. Fig. 12 摆放

Node01 固定在距网关约 2 m；Node02 与 Node01 相对网关保持同一方位角，依次间隔：

```text
2 cm, 5 cm, 10 cm, 20 cm, >20 cm
```

当前可执行 manifest 用 30 cm 代表 `>20 cm`。每个位置记录：

- 两节点三维坐标及卷尺实测间隔；
- 网关双天线中点和天线间距；
- 天线高度、方向和极化；
- 实测方位角；
- 现场照片。

同一位置连续跑两次 `d=0.25, G=0.5` 的独立重复。位置切换前自动预留 300 秒。

布局预览：

```bash
python3 real_collision_experiment/paper_experiments/render_fig12_layout.py \
  --campaign real_collision_experiment/paper_experiments/generated/fig9_12_duty_v4/campaign.json \
  --out-prefix real_collision_experiment/paper_experiments/generated/fig9_12_duty_v4/fig12_layout
```

## 6. Campaign 生成与检查

默认生成：

```bash
cd /home/chengjing/real_usrp_experiment
python3 real_collision_experiment/paper_experiments/plan_fig9_12_campaign.py \
  --out-dir real_collision_experiment/paper_experiments/generated/fig9_12_duty_v4 \
  --campaign-id fig9_12_duty_v4
```

关键生成物：

- `campaign.json`：两边自动脚本读取的唯一实验计划；
- `run_sheet.csv`：40 轮人工审计表；
- `report_index_template.csv`：离线汇总入口；
- `run_campaign.ps1` / `dry_run_campaign.ps1`：逐轮交互式备选脚本。

自动无网络采集应直接使用：

- Ubuntu：`automation/start_offline_rx_preflight.sh`，通过后运行
  `automation/start_offline_rx_remaining.sh`；
- Windows：对应运行 `automation/start_offline_control_preflight.ps1` 和
  `automation/start_offline_control_remaining.ps1`。

完整现场命令见 `docs/10_Fig9-12逐轮采集命令.md`。

复制数据后可做结构校验：

```bash
python3 real_collision_experiment/paper_experiments/validate_fig9_12_artifacts.py \
  --campaign real_collision_experiment/paper_experiments/generated/fig9_12_duty_v4/campaign.json \
  --artifact-root /path/to/copied/artifacts \
  --allow-missing \
  --out /path/to/copied/artifacts/validation.json
```

只复制 Windows manifest 不足以画图；还必须保留 Ubuntu 的双通道 `.sc16`、对应 metadata、
后续六方法 report，以及 Fig. 12 的现场记录。
