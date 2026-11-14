# SP+sync-refine 面向 MobiCom 投稿的完整实验路线图

> **历史路线图说明（2026-07-31）：** 本文后半部的旧 R1–R4 采集矩阵仅保留研究设计
> 背景，不再作为现场命令。当前冻结的 40 轮 Fig. 9/10/12 实验以
> `docs/09_Fig9-12实验计划与Windows控制.md` 和
> `docs/10_Fig9-12逐轮采集命令.md` 为准。

> 版本定位：**信号仿真 + trace-driven 碰撞仿真 + 噪声仿真 + 15 节点真实空口实验**。
>
> 设计原则：仿真负责难以在空口精确控制的机制变量和失败边界，真实实验负责证明方案不是只在理想模型中成立。本文不修改现有 CONFIG v1、控制端协议或节点固件，也不依赖射频衰减器。

---

## 0. 最终论文主张和证据链

论文主方案固定为 **SP+sync-refine**：

1. 从前端给出的完整包目标取得 start、CFO 和双通道 channel；
2. 根据包级 channel reliability、噪声和干扰方向选择风险约束 `lambda_u`；
3. 对每个 payload symbol 构造
   `D_u[k]=|P_u[k]|²-lambda_u|Q_u[k]|²`；
4. signed top-1 后进入标准 LoRa FEC/PHY CRC；
5. SP-core 失败时才进行有界 start/CFO refinement；
6. SP+repair 只作为附录诊断上界，不作为正文主方案。

完整论证链如下：

```text
实测 clean waveform
    ↓ trace-driven collision
MRC 错峰中是否存在稳定的目标正交反证？
    ↓ controlled formal-PHY simulation
rho、near-far、噪声、多干扰分别怎样影响 signed decision？
    ↓ risk-lambda / sync-refine controlled validation
收益是否来自论文声称的机制，而不是无界 CRC 搜索？
    ↓ 15-node real air experiments
在真实 CFO、异步碰撞、多径、硬件不一致和前端误差下是否仍成立？
    ↓ common-front-end baselines + held-out runs
相对 MRC、CIC、PCube、MaLoRaGW 的增益是否稳定且公平？
```

仿真不能替代真实实验；真实实验也不适合承担 `rho`、精确 power gap、精确同步误差等变量的 ground truth。两类证据必须互补。

---

## 1. 指标和比较口径

### 1.1 正式指标

- **Packet Detection Rate**：检测到的完整包目标数 / 实际发送包数；
- **Schedule-normalized Packet Detection Rate**：检测到的完整包目标数 / manifest 计划发送数；
- **Conditional PRR**：检测到的完整包目标中，FEC/CRC 后 payload 正确的包数 / 检测到的完整包目标数；
- **End-to-end delivery ratio**：正确 payload 唯一包数 / 实际或计划发送包数；
- **Payload goodput**：每秒正确解码的唯一 20-byte payload 比特数，单位
  `kbps`；计算式为 `成功包数 × 20 × 8 / business_duration / 1000`。
  原 TPS（每秒正确解码包数）只作为诊断字段。

截断包不进入 Conditional PRR 分母，但需要单独报告。不能再用“80% 符号正确”定义成功。

### 1.2 仿真成功判据

新增 formal-PHY 仿真固定使用：

- SF10、BW125 kHz、CR4/5；
- 20-byte payload；
- explicit header；
- PHY CRC on；
- 8-symbol preamble；
- sync word `0x34`；
- 与真实节点相同的 interleaving、Hamming、whitening 和 Gray mapping。

仿真包成功必须同时满足：

1. 标准 PHY CRC 通过；
2. 解出的 20-byte payload 与发送 payload 完全一致。

旧的 trace-driven preliminary 图可以报告 symbol error、margin 或空间反证比例，但不能把 SER≤20% 写成 PRR。

### 1.3 基线公平性

真实报告中的 MRC、CIC、PCube、MaLoRaGW 属于：

> common-complete-target、common bounded-sync-refine 的 decoder comparison。

它不是各论文 native front-end 的端到端复现。正文必须明确：

- SP+sync-refine；
- MRC；
- CIC；
- PCube-2Rx；
- MaLoRaGW-2Rx-uplink；
- SP-core 为消融；
- SP+repair 放附录。

---

## 2. 建议的完整章/节目录

## 2.1 Chapter 1：Introduction

### 1.1 并发 LoRa 接收问题

概要：

- 传统单峰解调在碰撞下产生多个候选；
- MRC 对目标方向和干扰方向的能量都只能做非负累加；
- 现有并发解码在低 SNR、near-far、两天线和多干扰下仍有不足。

不放复杂实验，只用一张系统示意图。

### 1.2 核心观察

概要：

- 目标在自身 channel direction 上相干增强；
- 竞争峰若主要来自其他空间方向，会在目标正交方向留下更强证据；
- 将该证据作为负项可能改变错误 top-1。

引用 Chapter 2 的真实 trace-driven 结果，不在 Introduction 重复完整图。

### 1.3 挑战

列出三个挑战：

1. channel 存在估计误差，负项不能无限增大；
2. 任意多干扰下 pairwise polarity 不自动保证混合信号安全；
3. start/CFO 小误差会破坏 packet-level CRC，需要有界而非无界 refinement。

### 1.4 Contributions

贡献必须与后面的实验一一对应：

- signed spatial spectrum；
- reliability/risk-constrained packet-level lambda；
- bounded sync-refine；
- 双天线非迭代实现；
- trace-driven、formal-PHY simulation 和 15-node 空口验证。

建议图：

- **Fig. 1：系统概览**，不需要实验数据。

---

## 2.2 Chapter 2：Background and Motivation

### 2.1 LoRa collision 与双天线模型

给出：

- dechirp FFT；
- 双通道向量 `Y[k]`；
- 目标归一化方向 `a_u`；
- 正交方向 `b_u`；
- `P_u[k]=a_u^H Y[k]`；
- `Q_u[k]=b_u^H Y[k]`；
- `rho_uv=|h_u^Hh_v|²/(||h_u||²||h_v||²)`。

本节无实验图。

### 2.2 M1：真实 waveform 中的 MRC 错峰和正交反证

目的：

- 证明 signed observation 不是理想高斯信道中人为构造出来的；
- 保留真实 SX127x 波形、CFO、两路幅相不一致和硬件失真。

方法：

1. 使用 `real_usrp_outputs/clean_pos_packets.npz` 中实测 clean packets；
2. 合成异步多包碰撞；
3. 自动寻找 MRC top-1 错误而 signed score 恢复正确 bin 的真实符号；
4. 画 `|P|²`、`|Q|²`、`D[k]`；
5. 汇总 MRC 错峰和正确 bin 的空间不一致比例 `eta`。

图：

- **Fig. 2(a)**：一个真实 trace-driven signed-spectrum case；
- **Fig. 2(b)**：target bin 与 MRC wrong bin 的 `eta` 分布。

命令：

```bash
MPLCONFIGDIR=/tmp/sp_matplotlib \
python3 generate_sp_preliminary_figures.py
```

输出：

```text
real_usrp_outputs/sp_paper_figures/fig1_sp_core_observation.*
real_usrp_outputs/sp_paper_figures/fig3_eta_distribution.*
real_usrp_outputs/sp_paper_figures/preliminary_summary.json
real_usrp_outputs/sp_paper_figures/preliminary_records.json
```

注意：该脚本是 trace-driven symbol mechanism study，不把 SER threshold 写成正式 PRR。

### 2.3 M2：`rho × SIR` 下 MRC 为什么失效

目的：

- 只建立“传统 MRC 何时失效”的动机事实，此处尚未引入 SP 和 `lambda_u`；
- 直接复用 `fig2_mrc_failure_heatmap` 的真实波形记录，避免理想化单 bin
  模型在高 SNR 下产生大片 0/1 饱和；
- 替代原来需要 15 节点逐包测 `rho` heatmap 的复杂方案。

数据与变量：

- 输入 `preliminary_records.json` 中的 22800 个真实波形符号观测；
- 这些记录来自 26 个双通道 clean packets，保留实测 CFO、天线幅相差、
  波形失真和 packet-to-packet channel variation；
- 两包碰撞使用 20 个不同 target/interferer pair、5 个分数符号 offset；
- `SIR = 10log10(P_target/P_interferer)`，取 `-5,-4,-3,-2,-1,0 dB`；
- `rho` 按 `[0,0.2),[0.2,0.6),[0.6,0.8),[0.8,1.0]` 分箱；
- 指标是 oracle start/CFO/channel 下的 MRC symbol-bin SER。

图：

- **Fig. 3**：单张 MRC SER heatmap；
- 横轴 `rho`，纵轴 per-interferer SIR，颜色和标注风格与
  `fig2_mrc_failure_heatmap.svg` 一致，使用 `magma`；
- 默认输出与 `fig2_mrc_failure_heatmap` 使用完全相同的数据和分箱，数值应一致。

这张图回答：

- 强干扰经过空间投影后，什么 `rho/SIR` 组合会压过目标；
- 为什么整包 PRR 在这里不适合作图：一个错误符号就可能让整包失败，大片
  PRR=0 会掩盖失效程度，而 SER 能连续显示由轻到重的过渡；
- 这一节只提出问题，不提前展示本文解法。

### 2.4 M3：并发包数量和噪声如何加剧符号判决失效

目的：

- 说明 MRC 的问题并非仅存在于两包 near-far 特例；
- 随并发包数量增加，展示多个干扰投影的累积效应；
- 正文动机主图仍优先展示 MRC，避免在方案介绍前提前解释 `lambda_u`；
- 同一批符号窗口额外输出 SP、PCube、MaLoRaGW companion figures，用于内部检查
  和后文章节引用；
- 不需要真实节点严格 barrier。

数据与变量：

- concurrent packet number `2,4,6,8,15`，包含目标包，即目标加
  `1,3,5,7,14` 个干扰包；
- 从与 M2 相同的 26 个实测双通道 clean packets 中随机选目标和干扰；
- 每个干扰的 median SIR 为 `0 dB`，逐次加入 `1.5 dB` 标准差的功率抖动；
- 分数符号 offset 从 `0,0.1,0.25,0.5,0.9` 随机抽取；
- target waveform SNR（dechirp 之前）取
  `-30,-27.5,-25,-22.5,-20,-17.5,-15 dB`；
- 每点至少 500 个随机符号，正式稿推荐 1000；
- 真实 packet pair 自然提供不同 `rho`、CFO 和硬件失真，不再人为固定
  `rho=0.3`。

图：

- **Fig. 4**：单张 MRC `concurrent packet number × SNR` SER heatmap；
- companion：SP、PCube、MaLoRaGW 使用同一批 target/interferer/symbol/offset/noise
  样本分别作 SER heatmap；
- `m3_methods_ser_collision_snr.pdf` 给 2×2 总览，方便检查四种方法在同一低 SNR
  压力下的相对趋势；
- 使用 `magma`、白色格内数值，色标固定 `[0,1]`，与 M2 视觉一致。

这些图仍使用目标包的 oracle start/CFO/channel，只测试检测到完整包后的符号判决，
不重新测试低 SNR 前端检测。SP 图中的 `lambda_u` 按每个碰撞样本的实测 channel
方向、接收强度和当前噪声点重新计算；PCube 和 MaLoRaGW 则使用同一 dual-Rx
符号谱上的 PDoA/ZF-ratio 判决规则。

### 2.5 M4：主动暴露完全同步失败边界（可选，暂缓）

目的：

- 证明论文没有隐藏最困难的反例；
- 完全同步时所有节点 explicit header 相同，目标和强干扰可能落在同一 FFT bin；
- 此时 Q 分支不能简单把整个共享 bin 当作“错误峰”负掉。

变量：

- 相同两包信号，一组异步 symbol shift，一组完全同步 header；
- `rho=0.3`；
- 干扰强 10 dB；
- post-dechirp bin SNR 25 dB。

图（需要时才生成）：

- **Appendix Fig. A1**：asynchronous 与 fully aligned 的 MRC SER bar。

默认 decision 命令不生成 M4。需要写限制讨论时加 `--include-m4`，图放附录，
主文仅用一句话说明完全同步共享 bin 是困难边界。

### 2.6 Motivation 小结

从 M1–M4 得出设计需求：

1. 仅沿目标方向累加正能量会被强干扰的空间投影压过；
2. 两包现象会随并发包数量增加而加剧；
3. 下一章需要利用目标正交方向中的反证信息，而不是继续提高 MRC 能量；
4. 系统面向异步并发；完全同步共享 header 是明确限制。

---

## 2.3 Chapter 3：SP Design

### 3.1 Receiver overview

图：

- **Fig. 6：pipeline**  
  complete target → joint estimate → reliability/risk lambda → signed top-1 → bounded sync-refine → FEC/CRC。

说明前端 packet detection 与 SP decoder 的接口，不把 manifest 信息输入算法。

### 3.2 Signed spatial spectrum

给出 `a_u/b_u`、`P/Q`、`D[k]` 和 top-1。

用 Chapter 2 的 Fig. 2 作为经验支持，本节不新增实验。

### 3.3 Reliability 和风险约束 lambda

解释：

- `L_u` 是目标能量留在目标方向的保守下界；
- `U_uv` 是干扰泄漏到目标方向的保守上界；
- `lambda_cap` 防止 channel 不可靠时过度负化；
- 候选只取区间边界、pair-specific flip/peak points 和少量固定 checkpoints；
- 在有限候选点上最大化 worst-pair normalized margin。

不再要求从真实空口寻找 oracle channel-angle error。

### 3.4 D1：为什么 `lambda_u` 必须按条件选择

实验来源：

- D1 单独使用 formal-PHY 仿真；M2/M3 使用实测波形，二者不混写；
- D1 位于 signed spectrum 和风险约束公式之后，此时才正式出现 `lambda_u`；
- 代表 objective condition：`rho=0.4`、并发包数量 4、per-interferer
  SIR=-10 dB、SNR=5 dB；
- empirical sweep 使用
  `lambda={0,0.01,0.03,0.1,0.25,0.5,1,2,4,10,30,100,300,1000}`；
- 使用 9 个 `(rho,SIR)` 组合，覆盖低/中/高 coherence 和目标较强、
  同功率、强干扰区域；
- `100/300/1000` 仅为故意越过生产 cap 的 stress controls，用来展示过度相减
  和 Q 分支噪声放大的后果；生产接收机的有限候选搜索仍限制在 `[0,4]`。

图：

- **Fig. 7(a)**：一个包的 `lambda_u` 选择过程。纵轴
  “guaranteed minimum decision margin” 是对所有目标—干扰 pair 取最差值后的
  保守判决裕量，正值表示目标在保守模型下胜过全部干扰；蓝色阴影
  “uncertainty-safe range” 是由 channel/noise reliability 给出的允许区间；
  橙点是代码真正计算的少量 lambda；红星是在允许区间内使最差裕量最大的选择。
- **Fig. 7(b)**：9行 `(rho,SIR)` × 多列 fixed lambda 的 SER heatmap，
  青色星号标出每个条件下 risk-selected `lambda_u`。直接看颜色即可判断固定
  `lambda=1/100/1000` 为什么不能通用；白色虚线明确分开接收机允许搜索的
  `lambda<=4` 和只用于观察过度相减的更大权重，不再使用重叠折线或含糊的
  “stress-only region” 阴影。
- **Fig. 7(c)**：不再比较“risk lambda 数值是否等于 oracle lambda 数值”。
  横轴改为同一安全区间 `[0,lambda_max]` 内、使用发送真值后验得到的最优 SER；
  纵轴是 risk-selected `lambda_u` 的 SER。对角线表示两者性能相同，同时报告
  median/90th-percentile excess SER，所有偏离点均保留。

这组图同时回答三个问题：

1. 代码不是在连续区间盲目 dense search，而只计算少量有理论意义的候选；
2. `lambda=1`、`100` 或 `1000` 都不可能在所有 `rho/SIR` 下固定最优；
3. risk-selected lambda 不要求数值等于 oracle lambda；真正应验证的是两者的
   SER 是否接近。这样避免因宽平坦最优区而错误贬低方案，也不通过挑点美化结果。

### 3.5 Bounded sync-refine

明确算法含义：

- SP-core 使用前端一次给出的 start/CFO/channel；
- 如果标准 PHY CRC 已闭环，完全不搜索；
- 只有 core 失败时，在固定 start/CFO 列表中最多运行 `max_sync_trials` 次；
- 不使用真实 payload、manifest sequence 或期望 symbol；
- CRC 只作为普通接收机的闭环检查。

### 3.6 D2：真实 core-failure 包如何被 bounded sync-refine 救回

正文不再把“人为向 coarse estimate 加入已知误差”作为主实验。那种图只能证明
算法对合成偏差敏感，不足以解释真实接收链路里 SP-core 为什么失败。D2 主图改为
从真实 report 中筛选：

```text
SP-core PHY CRC fail  AND  SP+sync-refine PHY CRC ok
```

流程：

1. 复用正式真实 run 的 `candidates[].methods[]`，不重新检测、不重新解码；
2. 对每个候选比较同一包的 SP-core 和 SP+sync-refine；
3. 只统计 core 失败、sync-refine 成功的 rescued packets；
4. 展示 bounded search 最终选择的 start/CFO correction；
5. 展示 refinement 前后的 payload byte errors、corrected/uncorrected codewords；
6. 搜索仍然由接收机实现限制为固定 `max_sync_trials`，不使用 manifest 做搜索。

图：

- **Fig. 8(a)**：一个真实 rescued packet 的 byte-level 缺陷图。横轴是 payload
  byte index，两行分别为 SP-core 和 SP+sync-refine；红色表示相对 expected payload
  的 byte mismatch，绿色表示一致。图注给出该包选择的
  `start_delta_samples`、`cfo_delta_bins` 和 `sync_trials`。
- **Fig. 8(b)**：所有 rescued packets 的 `start_delta_samples × cfo_delta_bins`
  scatter，颜色表示实际用了多少 sync trials。这个图直观看出 bounded refine
  不是无限搜索，而是在少数固定 correction 点闭环。
- **Fig. 8(c)**：所有 rescued packets 上，SP-core 和 SP+sync-refine 的 payload
  byte errors 曲线。排序后展示 core 的缺陷如何被 refine 消掉。
- **Fig. 8(d)**：rescued packets 的平均 corrected codewords、uncorrected
  codewords、byte errors 对比柱状图。

如果正文空间紧，保留 Fig. 8(a)(b)，把 Fig. 8(c)(d) 放 appendix。

原来的 known-error injection 只作为 appendix sanity check：用仿真已知真实
start/CFO，向 coarse estimate 注入 `0..3 samples` 和 `+0.6 bin`，画
SP-core/SP+sync-refine PRR vs injected error。它用于说明边界，不作为真实缺陷
根因证据。

### 3.7 Complexity

理论上给出：

- SP 每 symbol 两个空间投影和一个 signed subtraction；
- 无逐干扰 waveform reconstruction；
- lambda 搜索候选数随 detected interferer 数线性增长；
- sync-refine 有固定 trial cap。

实测 wall-clock 放 Evaluation，不在设计章节堆 FFT 次数/peak memory/p99。

---

## 2.4 Chapter 4：Implementation

### 4.1 Hardware

- 15 × STM32F103/SX1276；
- 控制 B210；
- 双通道同步接收 B210；
- 两根接收天线；
- 控制端和接收端无需共时钟；
- 接收 B210 的两个通道必须同机同步。

### 4.2 PHY/MAC

- 487.7 MHz；
- SF10、BW125 kHz、CR4/5；
- preamble 8；
- explicit header；
- PHY CRC on；
- sync `0x34`；
- 20-byte payload；
- CONFIG v1 和 Poisson traffic。

### 4.3 Software

说明：

- 前端持续忙区检测和空间方向去重；
- SP-core、SP+sync-refine、SP+repair；
- MRC/CIC/PCube/MaLoRaGW common-front-end baselines；
- JSON v5 report；
- 所有结果由冻结 JSON 生成。

本章放：

- **Table 1：硬件和 PHY 参数**；
- **Table 2：各方法硬件能力与比较范围**。

---

## 2.5 Chapter 5：Experimental Methodology

### 5.1 仿真分成三层

#### Layer S1：trace-driven signal simulation

- 输入实测 clean SX127x 双通道 waveform；
- 保留 CFO、硬件波形失真、实测 channel；
- M1/M2 使用已冻结的二包符号记录；
- M3从相同 clean packets 随机合成多包碰撞、功率抖动和时域 AWGN；
- 用于 M1、M2、M3；
- 输出 symbol mechanism，不输出正式 PRR。

#### Layer S2：formal-PHY collision/noise simulation

- 生成标准 20-byte LoRa payload；
- 完整 whitening、Hamming、interleaving、Gray mapping；
- 精确控制 `rho`、per-interferer SIR、concurrent packet number 和 FFT-bin noise；
- D1输出 lambda sweep、风险选择、SER 和标准 PHY 闭环审计数据；
- 用于 D1，以及可选 M4。

#### Layer S3：full-waveform sync simulation

- 生成过采样 preamble、sync、SFD、payload；
- 双通道 spatial mixture；
- 加 CFO、异步 start、AWGN；
- 注入已知 coarse start/CFO error；
- 调生产版 `decode_sp_stages()`；
- 用于 D2。

仿真随机性：

- 正式每 point 至少 200 packets；关键边界建议 500；
- 至少保存一个 master seed；
- 每包 payload、symbol phase 和噪声独立；
- 图中给 Wilson/seed bootstrap 95% CI；heatmap 可在 CSV 中保留分子分母。

### 5.2 不改固件的 Poisson seed 预选

现有 CONFIG v1 已包含 `run_id/global_seed/payload_seed`，固件调度可重放。
在采集前搜索包含所需碰撞阶数的 seed：

```bash
python3 real_collision_experiment/paper_experiments/select_poisson_seeds.py \
  --run-id 0xB1040001 \
  --active-nodes 1-4 \
  --offered-load 2.0 \
  --duration-s 60 \
  --payload-seed 0x22222222 \
  --seed-count 2000 \
  --target-orders 2,3,4 \
  --top 5 \
  --out real_collision_experiment/runs/seed_plan_B1040001.json
```

选择结果只用于 CONFIG 的 `--global-seed` 和事后重叠标签，不输入 RF detector。

### 5.3 真实布局

#### Layout A：开放/半开放主布局

接收天线中点 `(0,0)`，15 节点摆在前方 3 × 5 网格：

| 节点 | 坐标 m | 节点 | 坐标 m | 节点 | 坐标 m |
|---|---:|---|---:|---|---:|
| 01 | (-4,3) | 06 | (-4,5) | 11 | (-4,7) |
| 02 | (-2,3) | 07 | (-2,5) | 12 | (-2,7) |
| 03 | (0,3) | 08 | (0,5) | 13 | (0,7) |
| 04 | (2,3) | 09 | (2,5) | 14 | (2,7) |
| 05 | (4,3) | 10 | (4,5) | 15 | (4,7) |

若房间尺寸不足，将所有坐标同比缩小；正式 run 中不得移动。

#### Layout B：混合 LoS/NLoS

- Node01–05：同房间 3–6 m；
- Node06–10：走廊 8–15 m；
- Node11–15：隔一面墙或相邻房间 10–25 m；
- 节点尽量分散方位；
- 不追求人为相同 RSSI；
- 用于验证真实功率不均和多径环境。

只在 Layout B 做两个代表点：15 节点 `G=1.0` 和 `G=3.0`，每点 3 seed。

#### Layout NF：无衰减器 near-far

- Node01 强节点固定在距网关约 3 m、方位 `-35°`；
- Node02 弱节点沿 `+35°` 射线移动；
- Node02 距离档建议 `3,6,10,15,20 m`；
- 场地不足时用 `3 m LoS、6 m LoS、隔门、隔一面墙、隔两面墙` 五档；
- 每档先做 Node01/Node02 单节点短校准；
- 横轴使用实测 `strong-minus-weak channel-power gap`，不是距离本身；
- RX gain 和两节点 TX power 始终固定。

这样 power gap 由距离/墙体产生，不需要衰减器。

### 5.4 接收端固定设置

- 487.7 MHz；
- 500 kS/s/channel；
- bandwidth 200 kHz；
- RX gain 20 dB；
- RX2；
- 两根同型号、同极化、等长线缆；
- 天线间距约 30 cm；
- 天线中点高约 1.2 m；
- 任何持续 overflow 或明显 ADC clipping 的 run 作废并重采。

### 5.5 真实实验重复和冻结

- pilot：30 秒；
- 正式：60 秒；
- 每 point 至少 3 个独立 run/seed；
- 方差较大的 point 增加到 5 seed；
- 参数在正式 held-out run 前冻结；
- 同一 IQ 对所有算法离线运行；
- 失败 run 和排除原因必须记录。

---

## 2.6 Chapter 6：Evaluation

### 6.1 R0：15 节点单节点门禁

目的：

- 确认每个节点收到 CONFIG/START；
- 确认 node_id/run_id/sequence；
- 确认单节点 SP+sync-refine Conditional PRR 接近 100%；
- 保存各节点 channel power 和 CFO，发现坏节点。

Layout A 每节点 20 秒、`G=0.5`。这是实验门禁，不占正文主图；结果可放 artifact 表。

### 6.2 R1：并发节点规模

目的：测 PRR/有效载荷吞吐量随活动节点数变化。

变量：

- `N=2,4,8,15`；
- 固定 `G=1.5`；
- Layout A；
- 每个 N 三组不同节点子集/seed，避免只用最容易 pair。

推荐子集：

- N=2：`1,8`、`3,10`、`5,12`；
- N=4：`1,5,9,13`、`2,6,10,14`、`3,7,11,15`；
- N=8：`1-8`、`4-11`、`8-15`；
- N=15：`1-15`，3 seed。

图：

- **Fig. 9(a)**：Schedule-normalized Detection Rate vs N；
- **Fig. 9(b)**：Conditional PRR vs N；
- **Fig. 9(c)**：payload goodput (kbps) vs N。

### 6.3 R2：offered load

变量：

- Layout A；
- Node01–15；
- `G=0.25,0.5,1.0,2.0,3.0`；
- 每点 3 seed；
- 每 run 60 秒。

图：

- **Fig. 10(a)**：Detection Rate vs G；
- **Fig. 10(b)**：Conditional PRR vs G；
- **Fig. 10(c)**：decoded payload goodput (kbps) vs G。

同一批数据按 manifest 重叠关系输出 concurrent packet number 分层，不再另采 barrier 数据。

### 6.4 R3：解码开销与共享检测下的 SER

使用不同实测位置的双通道信道/CFO 承载可校验标准 PHY 帧，离线构造
`N=2,4,6,8` 的等 RMS 异步碰撞；起点以约 `4.25 Ts` 间隔近均匀错开，首末跨度
小于一帧且任意两包不按整数 chirp 对齐，每档 4 个独立场景。所有方法共享 SP 检测；
LoRaWAN/MRC 共享 SP 精参数，CIC/PCube/MaLoRaGW 从 1/8-chirp 粗起点执行论文内精估计。

图：

- **Fig. 11(a)**：每个检测候选的 decoder 时间；检测/同步不计时，从同步 estimate
  输入方案之后的包级 `lambda` 配置、method-specific context 和 payload 判决均计时；
- **Fig. 11(b)**：共享检测、方法内参数估计下的 SER，精估计失败记为 1；
- oracle 参数只用于解码完成后的匹配和 SER 计算，不输入任何接收机。

作用：

- 验证 SP 的有符号判决没有引入随碰撞规模增长的迭代抵消开销；
- 在不使用 oracle 的前提下，将粗检测召回与载荷判决解耦；MRC/SP 共享精参数，直接
  比较普通 top-1 与有符号空间判决。

### 6.5 R4：无衰减器 near-far

变量：

- Layout NF；
- Node01/Node02；
- Node02 五个距离/墙体档；
- `G=1.5`；
- 每档 3 seed；
- 每档并发前做两个 20 秒单节点校准。

图：

- **Fig. 12**：弱 Node02 Conditional PRR vs 实测 power gap；
- strong Node01 可作为淡色虚线。

补充：

- 仿真 Fig. 3 提供规则 `rho × exact SIR` 全网格；
- 实测 Fig. 12 证明相同趋势在真实距离、多径和 CFO 下存在。

### 6.6 R5：低 SNR decoder-only stress

口径：

- 从高 SNR report 复用完整检测目标；
- 按实测双通道 noise covariance 加噪；
- 每个 noise point 重新估计 SP reliability 和 lambda；
- 所有方法使用同一完整目标和 bounded sync-refine；
- 不对加噪后的整段 IQ 重新跑检测。

图：

- **Fig. 13**：Conditional PRR vs median estimated preamble SNR。

正文只声称低 SNR 下 signed decision 增益，不声称低 SNR detection/sync 增益。

### 6.7 R6：真实数据消融

复用 R1/R2/R4：

- MRC；
- SP-core；
- SP+sync-refine；
- SP+repair appendix；
- lambda distribution；
- refine trigger fraction；
- start/CFO correction magnitude。

图：

- **Fig. 14**：三个代表 real conditions 的 SP-core/SP+sync-refine/MRC bar；
- lambda 和 trigger 统计放小表或 appendix。

### 6.8 R7：concurrent packet number 分层

复用 R2：

- 按 manifest 计划时刻计算每个 identity 对应的最大 concurrent packet number；
- 报告方法 PRR vs concurrent packet number；
- 与仿真 Fig. 4 相互验证。

图：

- **Fig. 15 或 Appendix Fig. A2**：Conditional PRR vs observed/planned concurrent packet number。

### 6.9 R8：简化运行时间

固定一台 CPU，选 15 节点 `G=3` run，完整离线命令重复 3 次。

正文只报告：

- wall-clock；
- `wall-clock / capture-duration` real-time factor。

不再测 FFT 次数、peak memory、p99、单/多线程全矩阵。由于当前工具一次运行六种方法，这只能证明完整离线工具链开销；若声称 SP 单独实时，需要以后加方法级 profiler。

---

## 3. 所有仿真实验的可运行命令

## 3.1 M1：trace-driven motivation

clean packet 文件已经存在时：

```bash
MPLCONFIGDIR=/tmp/sp_matplotlib \
python3 generate_sp_preliminary_figures.py
```

如果以后重新采 clean positions，先提取：

```bash
python3 real_usrp_clean_packet_synth.py extract \
  --inputs real_usrp_outputs/pos01.npz \
           real_usrp_outputs/pos02.npz \
           real_usrp_outputs/pos03.npz \
           real_usrp_outputs/pos04.npz \
           real_usrp_outputs/pos05.npz \
           real_usrp_outputs/pos06.npz \
           real_usrp_outputs/pos07.npz \
           real_usrp_outputs/pos08.npz \
           real_usrp_outputs/pos09.npz \
           real_usrp_outputs/pos10.npz \
  --out real_usrp_outputs/clean_pos_packets.npz \
  --min-preamble-score 250
```

clean position 建议摆放：

- 接收机不动；
- 单个发送节点依次放在距接收机 3–10 m 的 10 个不同方位；
- 每个位置只发单节点；
- 这些位置用于获得多样化实测 channel，不要求对应正式 15 节点布局。

## 3.2 M2/M3 实测波形碰撞 + D1 formal-PHY decision suite

快速 smoke：

```bash
python3 real_collision_experiment/paper_experiments/simulate_sp_mechanisms.py decision \
  --out-dir real_collision_experiment/runs/sim_smoke \
  --m2-records real_usrp_outputs/sp_paper_figures/preliminary_records.json \
  --clean-packets real_usrp_outputs/clean_pos_packets.npz \
  --collision-number 2,8 \
  --snr-db=-30,-22.5,-15 \
  --m3-symbol-trials 30 \
  --lambda-sweep 0,0.1,1,4,100,1000 \
  --d1-case-rho 0.2,0.4,0.8 \
  --d1-case-sir-db 10,0,-10 \
  --d1-oracle-rho 0.2,0.8 \
  --d1-oracle-sir-db=-10,0,10 \
  --d1-trials 10 \
  --d1-oracle-trials 5
```

正式命令：

```bash
python3 real_collision_experiment/paper_experiments/simulate_sp_mechanisms.py decision \
  --out-dir real_collision_experiment/runs/sim_formal_seed20260731 \
  --seed 20260731 \
  --m2-records real_usrp_outputs/sp_paper_figures/preliminary_records.json \
  --m2-sir-db=-5,-4,-3,-2,-1,0 \
  --m2-rho-edges 0,0.2,0.6,0.8,1.0001 \
  --clean-packets real_usrp_outputs/clean_pos_packets.npz \
  --collision-number 2,4,6,8,15 \
  --snr-db=-30,-27.5,-25,-22.5,-20,-17.5,-15 \
  --m3-median-sir-db 0 \
  --m3-sir-jitter-db 1.5 \
  --m3-offset-symbols 0,0.1,0.25,0.5,0.9 \
  --m3-symbol-trials 1000 \
  --theta-deg 5 \
  --sp-gamma 0.05 \
  --sp-lambda-max 4 \
  --lambda-sweep 0,0.01,0.03,0.1,0.25,0.5,1,2,4,10,30,100,300,1000 \
  --d1-case-rho 0,0.2,0.2,0.4,0.4,0.6,0.6,0.8,0.8 \
  --d1-case-sir-db 10,10,3,3,0,0,-3,-3,-10 \
  --d1-oracle-rho 0,0.2,0.4,0.6,0.8,0.95 \
  --d1-oracle-sir-db=-20,-10,0,3,6,10,20 \
  --d1-snr-db 25 \
  --d1-collision-number 4 \
  --d1-trials 200 \
  --d1-oracle-trials 50 \
  --d1-example-rho 0.4 \
  --d1-example-sir-db -10 \
  --d1-example-snr-db 5
```

输出：

```text
decision_records.csv
decision_config.json
m2_mrc_ser_rho_sir.pdf
m3_mrc_ser_collision_snr.pdf
m3_sp_ser_collision_snr.pdf
m3_pcube_ser_collision_snr.pdf
m3_maloragw_ser_collision_snr.pdf
m3_methods_ser_collision_snr.pdf
d1_lambda_records.csv
d1_lambda_selection.pdf
d1_lambda_diagnostics.json
```

M2没有重新随机仿真，而是对参考 Fig.2 的原始记录重新分箱，因此数值必须一致。
M3的 SNR 是 **目标包时域波形功率 / 加入的时域噪声功率**，测量点位于
dechirp 之前；D1的 SNR 仍是 formal-PHY FFT-bin 模型中的目标 bin SNR，二者必须
在图注中分别说明。上述命令不生成 M4；只有需要附录边界图时在命令末尾显式增加：

```bash
  --include-m4 \
  --alignment-rho 0.3 \
  --alignment-sir-db -10 \
  --alignment-snr-db 25
```

此时额外输出 `m4_alignment_boundary.pdf`。

正式稿建议再运行两个 seed 检查趋势：

```bash
python3 real_collision_experiment/paper_experiments/simulate_sp_mechanisms.py decision \
  --out-dir real_collision_experiment/runs/sim_formal_seed20260732 \
  --trials 200 \
  --seed 20260732

python3 real_collision_experiment/paper_experiments/simulate_sp_mechanisms.py decision \
  --out-dir real_collision_experiment/runs/sim_formal_seed20260733 \
  --trials 200 \
  --seed 20260733
```

汇总多个 decision seed：

```bash
python3 real_collision_experiment/paper_experiments/simulate_sp_mechanisms.py aggregate \
  --decision-csv \
    real_collision_experiment/runs/sim_formal_seed20260731/decision_records.csv \
    real_collision_experiment/runs/sim_formal_seed20260732/decision_records.csv \
    real_collision_experiment/runs/sim_formal_seed20260733/decision_records.csv \
  --out-dir real_collision_experiment/runs/sim_formal_aggregate
```

## 3.3 D2：真实 rescued packets 的 bounded sync-refine 图

复用任意已经由 `sp_node01_receiver.py` 生成、且包含 `candidates[].methods[]`
分阶段结果的真实 report。示例：

```bash
python3 real_collision_experiment/paper_experiments/plot_sync_refine_cases.py \
  --report real_collision_experiment/runs/run_04020001/n4_sp_staged_v1.json \
  --out-dir real_collision_experiment/runs/run_04020001/d2_sync_refine_cases \
  --max-sync-trials 32
```

输出：

```text
d2_sync_refine_rescued_cases.csv
d2_sync_refine_rescued_cases.pdf
d2_sync_refine_summary.json
```

如果要固定展示某个 rescued 包：

```bash
python3 real_collision_experiment/paper_experiments/plot_sync_refine_cases.py \
  --report real_collision_experiment/runs/run_04020001/n4_sp_staged_v1.json \
  --out-dir real_collision_experiment/runs/run_04020001/d2_sync_refine_cases \
  --max-sync-trials 32 \
  --case-candidate-id 3
```

只有当真实 report 中没有足够 rescued cases 时，才运行下面的 appendix sanity
check。它不是 D2 正文主证据。

```bash
python3 real_collision_experiment/paper_experiments/simulate_sp_mechanisms.py sync \
  --out-dir real_collision_experiment/runs/sync_sim_appendix \
  --trials 30 \
  --seed 20260801 \
  --start-error-samples 0,1,2,3 \
  --cfo-error-bins 0.6 \
  --rho 0.3 \
  --power-gap-db 10 \
  --snr-db 10 \
  --interferer-offset-symbols 0.35 \
  --target-cfo-bins 0.27 \
  --interferer-cfo-bins -0.35 \
  --max-sync-trials 32
```

---

## 4. 真实实验统一命令

以下用 60 秒业务区间；捕获 85 秒覆盖控制、warmup 和 tail。

### 4.1 终端 A：接收

```bash
mkdir -p real_collision_experiment/runs/run_B1040001

python3 real_collision_experiment/node01_sp_receiver/capture_dual_b210_gr.py \
  --out real_collision_experiment/runs/run_B1040001/run_B1040001.sc16 \
  --run-id 0xB1040001 \
  --duration 85 \
  --center-freq 487700000 \
  --rate 500000 \
  --gain 20 \
  --bandwidth 200000 \
  --channels 0,1 \
  --antenna RX2 \
  --notes 'paper Layout-A N4 G1.5'
```

### 4.2 终端 B：现有 CONFIG v1

```bash
python3 real_collision_experiment/control_usrp/usrp_run_controller.py \
  --run-id 0xB1040001 \
  --active-nodes 1,5,9,13 \
  --offered-load 1.5 \
  --duration-s 60 \
  --warmup-s 5 \
  --node-tx-power 10 \
  --global-seed 0xSELECTED \
  --payload-seed 0x22222222 \
  --config-repeat 5 \
  --config-interval-s 1 \
  --pre-config-delay-s 2 \
  --pre-start-delay-s 3 \
  --tail-s 5 \
  --usrp-tx-gain 20 \
  --antenna TX/RX \
  --manifest-dir real_collision_experiment/runs/manifests
```

必须把 `0xSELECTED` 替换成 seed 搜索结果。

### 4.3 终端 C：统一六方案解码

```bash
python3 real_collision_experiment/node01_sp_receiver/sp_node01_receiver.py \
  --iq real_collision_experiment/runs/run_B1040001/run_B1040001.sc16 \
  --metadata real_collision_experiment/runs/run_B1040001/run_B1040001.sc16.json \
  --manifest real_collision_experiment/runs/manifests/run_b1040001.json \
  --out real_collision_experiment/runs/run_B1040001/six_methods.json \
  --threshold 3.0 \
  --max-candidates 1000 \
  --frontend-candidates-per-window 16 \
  --energy-top-windows 0 \
  --energy-min-ratio 3 \
  --cfo-min -32 \
  --cfo-max 32
```

使用 manifest 时不需要逐个追加 `--active-node`。

---

## 5. 每个真实实验的执行命令变化

## 5.1 R0 单节点门禁

Node01 示例：

```bash
python3 real_collision_experiment/control_usrp/usrp_run_controller.py \
  --run-id 0xB0010001 \
  --active-nodes 1 \
  --offered-load 0.5 \
  --duration-s 20 \
  --warmup-s 5 \
  --node-tx-power 10 \
  --global-seed 0x11111111 \
  --payload-seed 0x22222222 \
  --config-repeat 5 \
  --config-interval-s 1 \
  --pre-config-delay-s 2 \
  --pre-start-delay-s 3 \
  --tail-s 5 \
  --usrp-tx-gain 20 \
  --antenna TX/RX \
  --manifest-dir real_collision_experiment/runs/manifests
```

捕获时长改为 45 秒。Node02–15 替换 run_id 和 active node。

## 5.2 R1 并发规模

每个 subset 先运行 seed selector。例如：

```bash
python3 real_collision_experiment/paper_experiments/select_poisson_seeds.py \
  --run-id 0xB1080001 \
  --active-nodes 1-8 \
  --offered-load 1.5 \
  --duration-s 60 \
  --payload-seed 0x22222222 \
  --seed-count 2000 \
  --target-orders 2,3,4,5,6,7,8 \
  --top 3 \
  --out real_collision_experiment/runs/seed_plan_B1080001.json
```

然后按第 4 节替换 run_id、active nodes 和 seed。

## 5.3 R2 offered load

G=3 示例：

```bash
python3 real_collision_experiment/paper_experiments/select_poisson_seeds.py \
  --run-id 0xB2150001 \
  --active-nodes 1-15 \
  --offered-load 3.0 \
  --duration-s 60 \
  --payload-seed 0x22222222 \
  --seed-count 2000 \
  --target-orders 2,3,4,5,6,7,8 \
  --top 3 \
  --out real_collision_experiment/runs/seed_plan_B2150001.json
```

实际控制只把 `--offered-load` 依次改为 `0.25/0.5/1.0/2.0/3.0`。

## 5.4 R3 Layout B

节点摆好后不移动，只运行：

```text
N=15, G=1.0, 3 seeds
N=15, G=3.0, 3 seeds
```

命令与 R2 相同，在 notes 和 report index 中把 layout 写成 `B`。

## 5.5 R4 无衰减器 near-far

每个 Node02 距离档：

1. Node01 单节点 20 秒；
2. Node02 单节点 20 秒；
3. Node01+02 并发 60 秒 × 3 seed。

并发 seed：

```bash
python3 real_collision_experiment/paper_experiments/select_poisson_seeds.py \
  --run-id 0xB4020001 \
  --active-nodes 1-2 \
  --offered-load 1.5 \
  --duration-s 60 \
  --payload-seed 0x22222222 \
  --seed-count 2000 \
  --target-orders 2 \
  --top 3 \
  --out real_collision_experiment/runs/seed_plan_B4020001.json
```

计算实测 gap：

```bash
python3 real_collision_experiment/paper_experiments/analyze_paper_results.py power-gap \
  --strong-report real_collision_experiment/runs/CAL_STRONG/six_methods.json \
  --weak-report real_collision_experiment/runs/CAL_WEAK/six_methods.json \
  --strong-node 1 \
  --weak-node 2 \
  --out real_collision_experiment/runs/GAP_POINT/power_gap.json
```

脚本把 whitened channel vector 逆变换回物理双通道，再计算中位 `||h||²` 比值。两份校准必须使用相同 RX gain、天线和 TX power。

## 5.6 R5 AWGN decoder stress

单 seed：

```bash
python3 real_collision_experiment/node01_sp_receiver/evaluate_awgn_prr_sweep.py \
  --report real_collision_experiment/runs/run_04020002/n4_six_methods.json \
  --out real_collision_experiment/runs/run_04020002/awgn_seed_20260721.json \
  --noise-rise-db 0 20 30 35 40 45 50 \
  --max-candidates 400 \
  --seed 20260721
```

正式 10 seed：

```bash
for NOISE_SEED in 20260721 20260722 20260723 20260724 20260725 \
                  20260726 20260727 20260728 20260729 20260730; do
  python3 real_collision_experiment/node01_sp_receiver/evaluate_awgn_prr_sweep.py \
    --report real_collision_experiment/runs/run_04020002/n4_six_methods.json \
    --out real_collision_experiment/runs/run_04020002/awgn_seed_${NOISE_SEED}.json \
    --noise-rise-db 0 20 30 35 40 45 50 \
    --max-candidates 400 \
    --seed ${NOISE_SEED}
done
```

不要加 `--fixed-front-end-estimates`，不要用
`evaluate_awgn_frontend_decode_sweep.py`。

汇总：

```bash
python3 real_collision_experiment/paper_experiments/analyze_paper_results.py awgn \
  --sweeps real_collision_experiment/runs/run_04020002/awgn_seed_*.json \
  --out-dir real_collision_experiment/runs/paper_results/awgn
```

## 5.7 R8 wall-clock

```bash
/usr/bin/time -f 'elapsed_s=%e' \
  -o real_collision_experiment/runs/RUN/timing_1.txt \
  python3 real_collision_experiment/node01_sp_receiver/sp_node01_receiver.py \
    --iq real_collision_experiment/runs/RUN/RUN.sc16 \
    --metadata real_collision_experiment/runs/RUN/RUN.sc16.json \
    --manifest real_collision_experiment/runs/manifests/RUN.json \
    --out real_collision_experiment/runs/RUN/timing_report_1.json \
    --threshold 3.0 \
    --max-candidates 1000 \
    --frontend-candidates-per-window 16 \
    --energy-top-windows 0 \
    --energy-min-ratio 3 \
    --cfo-min -32 \
    --cfo-max 32
```

重复 3 次，取 median。

---

## 6. 真实报告统一汇总

复制索引模板：

```bash
cp real_collision_experiment/paper_experiments/report_index_template.csv \
   real_collision_experiment/runs/paper_report_index.csv
```

每个 report 一行：

```csv
experiment,x_value,x_label,report,nodes,offered_load,seed,power_gap_db,weak_node,layout,notes
scale_n,4,N=4,real_collision_experiment/runs/run_B1040001/six_methods.json,4,1.5,1,,,A,Layout A
load_g,3,G=3,real_collision_experiment/runs/run_B2150001/six_methods.json,15,3,1,,,A,Layout A
environment,3,G=3,real_collision_experiment/runs/run_B3150001/six_methods.json,15,3,1,,,B,Layout B
near_far,10.4,gap=10.4 dB,real_collision_experiment/runs/run_B4020001/six_methods.json,2,1.5,1,10.4,2,NF,Node02 weak
```

生成 CSV/PDF：

```bash
MPLCONFIGDIR=/tmp/sp_matplotlib \
python3 real_collision_experiment/paper_experiments/analyze_paper_results.py reports \
  --index real_collision_experiment/runs/paper_report_index.csv \
  --out-dir real_collision_experiment/runs/paper_results
```

输出：

- `runs.csv`；
- `method_runs.csv`；
- `packets.csv`；
- `*_detection.pdf`；
- `*_prr.pdf`；
- `*_tps.pdf`；
- `*_ablation.pdf`；
- `collision_order_prr.pdf`；
- `near_far_weak_prr.pdf`；
- `environment_prr.pdf`；
- `lambda_distribution.pdf`；
- `lambda_summary.csv`；
- `sync_refine_summary.csv`。

绘图脚本只读冻结 JSON，不重新解码或修改成功判据。

---

## 7. 图表总表和正文/附录取舍

| 图 | 章节 | 数据来源 | 回答的问题 | 建议位置 |
|---|---|---|---|---|
| Fig.1 系统概览 | Introduction | 示意 | 系统做什么 | 正文 |
| Fig.2 signed case + eta | Motivation | trace-driven real waveform | 正交反证是否真实存在 | 正文 |
| Fig.3 rho × SIR MRC SER | Motivation | real-trace symbol collisions | MRC 的二包失效边界 | 正文 |
| Fig.4 packet number × SNR SER | Motivation / Design sanity | real-waveform bootstrap collisions | MRC 在多干扰和噪声下的失效程度；同数据检查 SP/PCube/MaLoRaGW | 正文主图 MRC，其余后文或附录 |
| Fig.5 alignment boundary | Motivation | formal-PHY simulation | 完全同步反例 | 可选附录 |
| Fig.6 pipeline | Design | 示意 | 算法链路 | 正文 |
| Fig.7 lambda selection | Design | formal-PHY simulation | 风险 lambda 是否有依据且为何不能固定 | 正文 |
| Fig.8 sync-refine | Design | full-waveform simulation | bounded refine 是否必要 | 正文 |
| Fig.9 scale | Evaluation | Layout A | 随节点数变化 | 正文 |
| Fig.10 load | Evaluation | Layout A | 随 offered load 变化 | 正文 |
| Fig.11 decoder time + shared-detection SER | Evaluation | trace-driven collision | 解码开销与方法内精估计/判决 | 正文 |
| Fig.12 real near-far | Evaluation | Layout NF | 距离产生的强弱差 | 正文 |
| Fig.13 decoder SNR | Evaluation | real IQ + covariance noise | 低 SNR 判决优势 | 正文 |
| Fig.14 real ablation | Evaluation | 复用 real runs | core/refine 增益 | 正文 |
| Fig.15 packet-number stratification | Evaluation | 复用 load runs | 高并发碰撞趋势 | 附录或正文 |

正文图太多时：

- Fig.5、Fig.15 放附录；
- R0 只放 artifact table；
- wall-clock 放一行表；
- SP+repair 只放附录；
- 不删除 Fig.2、Fig.3、Fig.4、Fig.7、Fig.8、Fig.9–14。

---

## 8. 建议执行顺序

### Phase 1：先完成全部仿真

1. M1 trace-driven；
2. M2/M3 real-trace collision + D1 formal-PHY decision，M4 仅在需要附录边界图时启用；
3. D2 full-waveform sync；
4. 检查适用边界是否与理论一致；
5. 冻结 gamma、lambda cap 和 sync trial cap。

### Phase 2：真实门禁和 pilot

1. Layout A 的 15 节点单节点门禁；
2. N=2 pilot；
3. N=4 pilot；
4. 修复 Packet Detection Rate 问题；
5. 冻结前端参数。

### Phase 3：正式空口

1. R1 scale；
2. R2 load；
3. R3 Layout B；
4. R4 distance near-far；
5. held-out seed，不再调参。

### Phase 4：离线复用

1. R5 AWGN；
2. R6 ablation；
3. R7 collision order；
4. R8 wall-clock；
5. 一键汇总。

---

## 9. 实际工作量

仿真：

- formal decision：约 73 points × 200 packets；
- sync：4 points × 30 packets；
- trace-driven：复用已有 clean packets。

真实空口：

- R0：15 个 20 秒单节点 run；
- R1：12 个 60 秒 run；
- R2：15 个 60 秒 run；
- R3：6 个 60 秒 run；
- R4：15 个 60 秒并发 run + 10 个短校准 run；
- R5–R8 不新增空口采集。

正式并发空口总计 48 个 run，工作量明显小于原始“每变量全空口扫描”，但比上一版 36 个 run 多了环境重复和五档真实 near-far，可信度更完整。

---

## 10. 投稿前最低闭环

必须满足：

- formal simulation 的每个 PRR 都由标准 FEC/PHY CRC/payload equality 定义；
- trace-driven SER 与正式 PRR 不混用；
- 仿真明确区分 M3 的 target-waveform SNR、D1 的 post-dechirp bin SNR 和真实空口 RSSI；
- 完全同步 header 失败边界被主动报告；
- 15 个节点均通过单节点门禁；
- Layout A/B 都有 held-out 数据；
- distance near-far 使用实测 channel-power gap；
- Detection Rate 与 Conditional PRR 分开；
- common-front-end 与 native end-to-end claim 不混用；
- 所有参数在 held-out runs 前冻结；
- SP+repair 不冒充主方案；
- manifest 不参与检测、同步、lambda 或 payload 决策。

完成后，论文的逻辑不是“我们做了很多图”，而是：

> 真实 waveform 给出现象，formal-PHY 仿真解释机制和边界，full-waveform 仿真验证 bounded refinement，15 节点空口实验验证真实系统收益，反例和比较口径同时公开。
