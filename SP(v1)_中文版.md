# SP-Decoder：面向并发 LoRa 接收的风险约束有符号空间解码器

## 摘要

LoRa 以低功耗、远距离和低成本射频前端支撑了大量物联网部署，但其类 ALOHA 的随机接入方式使得同频、同带宽、同扩频因子的包碰撞随着节点密度上升而不可避免。已有并发接收系统分别利用时间偏移、频偏、功率差异和多天线相位特征恢复碰撞包。这些方法显著提升了 LoRa 并发接收能力，但仍保留了一个关键的判决层瓶颈：当目标包已经被检测、同步并获得信道估计后，最终的 LoRa FFT bin 判决通常仍由非负能量分数完成。因此，一个强干扰包即使空间方向与目标不一致，也可能凭借较大的目标方向投影赢得目标包的 top-1 判决。

本文提出 SP-Decoder，一个双天线 LoRa 并发解码器，将最终符号判决从仅累加正能量的合并方式，转化为以目标包为条件的有符号空间检验。对每一个检测到的完整包，SP-Decoder 将每个 dechirp 后的 FFT bin 分别投影到目标信道方向和目标正交空间方向，前者形成支持证据，后者形成反证证据。SP-Decoder 构造有符号谱

$$
D_{u,\ell}[k]=|P_{u,\ell}[k]|^2-\lambda_u |Q_{u,\ell}[k]|^2,
$$

其中包级权重 $\lambda_u$ 不是固定经验参数，而是由可靠性约束下的风险目标选择。接收机显式考虑信道不确定性、噪声以及任意多个已检测干扰包，在目标可靠极性区间内只评估有限个具有理论意义的候选权重。所得解码器非迭代，不重构干扰波形，不要求发射端修改，并兼容标准 COTS LoRa 节点。

我们在双通道 USRP B210 接收机和 15 个 STM32/SX1276 LoRa 节点上实现 SP-Decoder。系统将包检测率与检测后条件 PRR 严格分离，以标准 LoRa FEC 和 PHY CRC 闭环后的 payload 完全正确作为包成功准则，并在相同完整检测目标上比较 SP-Decoder、MRC、CIC、PCube 和 MaLoRaGW。实验方法结合实测波形碰撞合成、符合 LoRa PHY 的可控仿真和真实空口实验，分别隔离正能量判决失效、验证风险约束权重选择，并测试真实并发流量下的完整接收链路。

## 1. 引言

低功耗广域网已经成为大规模感知和控制系统的重要底层通信技术。LoRa 物理层采用 chirp spread spectrum 调制，能够以低成本射频芯片在低信噪比下完成远距离通信，因此被广泛用于城域感知、工业监测和环境采集等场景。然而，一个 LoRa 网关通常覆盖大量独立节点。当多个节点在相同中心频率、带宽、扩频因子和编码率下同时发送时，它们的包会在网关处发生碰撞。标准 LoRa 接收机主要依赖 capture effect；未被捕获的包需要重传，进而降低网络吞吐并增加节点能耗。

已有研究表明，LoRa 碰撞并不总是不可恢复。时域方法利用包起始偏移和符号边界不连续性；频域方法利用载波频偏或峰值轨迹；功率域方法按照接收幅度对频谱峰分组；多天线方法进一步利用相位差、信道比值或 MIMO 投影获得空间分集。CIC、PCube 和 MaLoRaGW 分别代表了该方向的重要进展：CIC 通过选择子符号片段并求频谱交集消除干扰 \cite{cic_sigcomm21}；PCube 利用多接收天线形成的相位域聚类区分碰撞符号 \cite{pcube_mobicom21}；MaLoRaGW 通过空间投影和信道估计支持多用户 MIMO LoRa 上行接收 \cite{maloragw_sensys22}。

这些工作引出了一个更具体的问题：当接收机已经找到一个完整目标包，并估计出它的起始位置、CFO 和双通道信道后，应该如何判定每个 LoRa FFT bin 属于该目标包？在双天线接收机中，最大比合并 MRC 将 dechirp 后的 FFT 向量投影到目标信道方向，并按非负能量排序。这在单用户高斯噪声模型下是提高 SNR 的标准选择，但碰撞产生的是不同的判决问题。来自其他包的 bin 仍可能在目标方向上具有较大投影。MRC 最多只能衰减该投影，却不能利用该 bin 同时在目标正交方向上暴露出强能量这一事实。

SP-Decoder 的核心观察是：目标正交方向上的能量并不只是无意义的残留噪声。对一个同步正确的目标符号，真实目标 bin 应当与目标信道空间方向一致，因此在目标正交方向上较弱。由其他包产生的竞争 bin 可能沿目标方向仍然很强，但往往会在目标正交方向留下更强分量。这个分量是“该 bin 不属于目标包”的反证。SP-Decoder 显式保留这一反证，并将其纳入 LoRa 符号排序。

直接用固定系数减去正交谱并不足以形成稳定接收机。若目标信道估计存在误差，真实目标能量会泄漏到正交分支，过大的减法权重会惩罚正确 bin；若权重过小，SP-Decoder 退化为 MRC，仍会在 near-far 碰撞中失败；若权重过大，噪声和信道漂移会被放大，导致过度相减。在多个干扰同时存在时，最差目标—干扰对可能主导目标判决，因此不存在一个跨信道相关性、SIR 和 SNR 都固定最优的全局权重。

SP-Decoder 用可靠性约束的有符号空间解码解决这一问题。它为每个包估计信道方向置信区间，将该区间转化为目标极性下界和干扰泄漏上界，并在风险约束区间内选择一个包级 $\lambda_u$，以最大化最差目标—干扰对的归一化判决裕量。随后接收机对每个 payload 符号执行直接的 signed top-1 判决，并进入标准 LoRa FEC 和 PHY CRC。只有当一次解码未通过 CRC 时，系统才触发有界 start/CFO refinement；本文将包含该条件式细化的完整接收器称为 SP-Decoder，将不含细化的一次解码路径称为 SP-Core。

本文贡献如下。

第一，本文指出双天线 LoRa 碰撞解码中的正能量判决瓶颈。基于真实 SX127x 波形和 trace-driven 碰撞，我们展示 MRC 的错误常发生在错误 bin 仍具有足够目标方向能量，同时又暴露出明显目标正交反证的情况下。

第二，本文提出 LoRa 有符号投影解码。解码器构造目标条件下的支持谱和反证谱，并按有符号空间分数排序。不同于逐次干扰抵消，SP-Decoder 不需要先解出干扰包，不重构干扰波形，也不依赖功率顺序。

第三，本文设计包级可靠性和风险机制来选择 $\lambda_u$。实现中考虑信道不确定性、噪声和任意数量的已检测干扰包，只评估区间边界、目标-干扰对特定的 flip/peak 点以及少量固定检查点，并将搜索限制在防止不可靠过度相减的安全区间内。

第四，本文在真实双天线 LoRa 接收机上实现和评估 SP-Decoder。评估将包检测率与条件 PRR 分离，以 FEC/PHY CRC 闭环 payload 正确作为成功准则，并在相同完整检测目标上比较 SP-Decoder、MRC、CIC、PCube 和 MaLoRaGW。

## 2. 背景与动机

### 2.1 LoRa FFT 解调

对于扩频因子 $\mathrm{SF}$，每个 LoRa 符号表示

$$
M=2^{\mathrm{SF}}
$$

种循环 chirp 偏移。设带宽为 $\mathrm{BW}$，过采样因子为 $L$，则一个符号包含 $N=LM$ 个复采样。标准接收机将接收到的 upchirp 与 downchirp 相乘，并在合适的 polyphase 分支上执行 $M$ 点 LoRa FFT。在无碰撞时，符号对应一个主导 FFT bin：

$$
\hat{s}=\arg\max_{0\le k<M} |Z[k]|^2.
$$

碰撞会将频谱从单个主峰变为多个竞争峰。接收机必须判断哪个峰属于当前正在解码的目标包。

### 2.2 双天线碰撞模型

考虑 $U$ 个 LoRa 包在双天线网关处重叠。令 $\mathbf{h}_v\in\mathbb{C}^{2}$ 表示包 $v$ 的有效双通道信道。接收机对目标包 $u$ 对齐、补偿 CFO、对第 $\ell$ 个 payload 符号 dechirp，并在两根天线上执行 LoRa FFT 后，bin $k$ 的向量观测可写为

$$
\mathbf{Y}_{u,\ell}[k]
=
\sum_{v=1}^{U}\mathbf{h}_v A_{uv,\ell}[k]
+\mathbf{N}_{u,\ell}[k],
$$

其中 $A_{uv,\ell}[k]$ 是包 $v$ 在目标对齐窗口内的标量 FFT 响应。对目标包而言，若同步准确，大部分能量应集中在 $k=s_{u,\ell}$；对干扰包而言，响应由相对起始时间、CFO、符号值和信道共同决定。

目标包的归一化信道方向为

$$
\mathbf{a}_u=\frac{\mathbf{h}_u}{\|\mathbf{h}_u\|}.
$$

在二维空间中，与 $\mathbf{a}_u$ 正交的单位向量可取为

$$
\mathbf{b}_u=
\begin{bmatrix}
-a_{u,2}^*\\
a_{u,1}^*
\end{bmatrix}.
$$

目标 $u$ 和干扰 $v$ 的归一化平方相干性定义为

$$
\rho_{uv}=
\frac{|\mathbf{h}_u^H\mathbf{h}_v|^2}
{\|\mathbf{h}_u\|^2\|\mathbf{h}_v\|^2}.
$$

高 $\rho_{uv}$ 表示两包在双天线空间中接近共线，难以分离；低 $\rho_{uv}$ 表示目标正交方向可以提供更有价值的反证。

### 2.3 正能量合并为什么失败

MRC 按如下分数对 bin 排序：

$$
M_{u,\ell}[k]=|\mathbf{a}_u^H\mathbf{Y}_{u,\ell}[k]|^2.
$$

设正确目标 bin 能量为 $E_u$，干扰包形成的竞争峰能量为 $E_v$。MRC 近似看到

$$
M_{u,\ell}[s_u]\approx E_u,\qquad
M_{u,\ell}[k_v]\approx E_v\rho_{uv}.
$$

因此，当 $E_v\rho_{uv}>E_u$ 时，即使 $\rho_{uv}<1$，干扰峰也可能赢得 top-1。MRC 可以衰减空间不一致的干扰，但不会把空间不一致本身作为负证据。解码器只知道一个 bin 在目标方向上有能量，却没有检查同一 bin 是否同时违背目标方向。

这就是正能量判决瓶颈。它不同于包检测失败或同步失败。即使目标 start、CFO 和 channel 已由 oracle 给出，最终符号 top-1 仍可能因为只累加非负支持证据而出错。

### 2.4 现有碰撞解码维度

CIC、PCube 和 MaLoRaGW 展示了 LoRa 接收机如何突破标准单包解调。

CIC 利用子符号结构。它选择干扰集合不同的时间片段，并对这些片段的频谱求交集，从而抵消不共同出现的峰 \cite{cic_sigcomm21}。其优势是不依赖干扰功率顺序即可消除部分干扰；局限在于短窗口降低频率分辨率，且高度对齐或频偏接近的干扰仍然困难。

PCube 使用相位域聚类。多根网关天线产生空中信道相位多样性，使来自不同发射机的符号在 I/Q 相位域形成不同簇 \cite{pcube_mobicom21}。该方法将 LoRa 并发解码扩展到空间维度，但要求簇可区分，并从多个接收天线对中受益。

MaLoRaGW 使用空间投影和信道估计进行多用户 MIMO LoRa 接收 \cite{maloragw_sensys22}。它将接收流投影到空间子空间中，估计信道并执行 MIMO 处理。其设计强调了多天线 LoRa 接收中打破同步和信道估计相互依赖的重要性。

SP-Decoder 与这些思路互补。它聚焦于完整目标包已经被检测之后的目标条件符号判决。SP-Decoder 不对跨包符号聚类，也不重构用户波形，而是直接判断每个候选 FFT bin 是否与目标包自身的空间方向一致。

### 2.5 Trace-driven 动机实验

动机实验使用双通道 B210 接收机采集的干净 LoRa 包。Trace-driven 碰撞合成保留 SX127x 波形细节、包间 CFO 差异、模拟前端不平衡和真实信道方向，同时允许控制目标包与干扰包混合关系。

M1 展示单个有符号谱案例。对目标包 $u$，SP-Decoder 构造

$$
P_{u,\ell}[k]=\mathbf{a}_u^H\mathbf{Y}_{u,\ell}[k],
\qquad
Q_{u,\ell}[k]=\mathbf{b}_u^H\mathbf{Y}_{u,\ell}[k].
$$

在支持谱 $|P|^2$ 中，强干扰可能成为 MRC top-1；在反证谱 $|Q|^2$ 中，同一个错误 bin 表现出强目标正交能量，而真实目标 bin 仍然较弱。这一真实观测支持有符号分数，而不是另一个非负合并器。

M2 刻画两包碰撞中 MRC 何时失败。实验复用 preliminary heatmap 背后的真实 trace 记录，按信道相干性 $\rho$ 和 SIR 分箱，并在 oracle 目标同步和信道条件下报告符号错误率。该实验目的不是提前引入 SP-Decoder，而是说明 MRC 的失败边界由空间相干性和 near-far 功率关系共同决定。

M3 将动机扩展到多包并发和噪声。实验从实测干净包中自助采样合成碰撞，将并发包数量从 2 提高到 15，并在 dechirp 前加入目标参考的波形噪声。MRC SER heatmap 表明正能量判决瓶颈不是两包特例。SP-Decoder 和比较解码器在后续章节用同一批符号样本评估，此时有符号判决规则已经被正式引入。

这些观察得到设计需求：接收机应同时保留目标方向支持、目标正交反证，并根据包级可靠性和干扰风险控制反证强度。

## 3. SP-Decoder 系统概览

SP-Decoder 位于并发包前端与标准 LoRa 信道译码之间。前端负责从双通道 IQ 忙区中持续发现完整包候选，并为每个候选输出 start、CFO、STO、双天线信道及与其时间重叠的候选集合。SP-Decoder 不要求先恢复干扰包的 payload，也不重构或抵消干扰波形；它只利用包级同步、空间方向、接收功率和噪声统计，为每个目标包配置一次判决器，再对该包的全部 payload 符号执行直接 top-1 解调。

> **[图 5 占位：SP-Decoder 系统概览]**
>
> 图从左到右分为三层：  
> **并发前端**：双通道 IQ $\rightarrow$ 忙区内持续前导码搜索 $\rightarrow$ start/CFO/STO/channel 候选 $\rightarrow$ 时间—空间去重；  
> **包级配置**：噪声白化 $\rightarrow$ 信道可靠性与重叠关系 $\rightarrow$ 有界风险权重 $\lambda_u$；  
> **符号与包恢复**：逐符号 dechirp/FFT $\rightarrow$ 支持谱与反证谱 $\rightarrow$ signed top-1 $\rightarrow$ 标准 LoRa FEC/PHY CRC。  
> 从 CRC 失败端画一条虚线反馈到“有界 start/CFO 细化”，trial 中重新估计目标信道、复用首次选定的包级 $\lambda_u$，再进入同一个符号判决模块；CRC 成功时不触发反馈。图中应明确标注 manifest、期望 payload 和应用层序号仅进入离线评估，不进入接收算法。

该架构刻意区分两类状态。start、CFO、信道和 $\lambda_u$ 是包级参数，在一个解码 trial 内由所有 payload 符号共享；支持谱、反证谱和 top-1 bin 是符号级量。第 4 章定义信道不确定、噪声和多个干扰下的包级风险目标及安全区间；第 5 章负责其有限点求解，并将前端检测、逐符号有符号判决和 CRC 闭环串成完整流程。

## 4. 包级反证权重的有界风险选择

本章建立 SP-Decoder 的包级决策模型。对检测到的目标包 $u$，接收机按照前端给出的 start/STO 截取第 $\ell$ 个 payload 符号，补偿目标 CFO，并在两根天线上分别完成 downchirp 与 LoRa FFT，得到双天线 bin 向量 $\mathbf{Y}_{u,\ell}[k]$。问题不是再次估计当前干扰符号，而是根据包级可靠性选择一个权重 $\lambda_u$：它应足以压低空间上不符合目标方向的竞争 bin，同时不能将目标自身因估计误差泄漏到正交分支的能量过度扣除。

### 4.1 从有符号裕量到反证权重

对检测到的目标包 $u$ 和 payload 符号 $\ell$，SP-Decoder 计算

$$
P_{u,\ell}[k]=\mathbf{a}_u^H\mathbf{Y}_{u,\ell}[k],
\qquad
Q_{u,\ell}[k]=\mathbf{b}_u^H\mathbf{Y}_{u,\ell}[k].
$$

$P$ 是目标方向支持，$Q$ 是目标正交反证。有符号判决谱定义为

$$
D_{u,\ell}[k]=|P_{u,\ell}[k]|^2-\lambda_u|Q_{u,\ell}[k]|^2.
$$

解码符号为

$$
\hat{s}_{u,\ell}=\arg\max_k D_{u,\ell}[k].
$$

当 $\lambda_u=0$ 时，SP-Decoder 退化为 MRC。正的 $\lambda_u$ 会惩罚与目标信道不一致的 bin。该方法仍是 top-1 符号判决；它不在多个符号候选之间分支，也不执行逐次干扰抵消。

### 4.2 权重的空间阈值解释

SP-Decoder 的有符号谱也可以写成 Hermitian 二次型。定义

$$
\mathbf{W}_u(\lambda_u)
=
\mathbf{a}_u\mathbf{a}_u^H
-
\lambda_u\mathbf{b}_u\mathbf{b}_u^H.
$$

则

$$
D_{u,\ell}[k]
=
\mathbf{Y}_{u,\ell}^H[k]\mathbf{W}_u(\lambda_u)\mathbf{Y}_{u,\ell}[k].
$$

$\mathbf{W}_u$ 在目标方向上的特征值为 $1$，在目标正交方向上的特征值为 $-\lambda_u$。因此，$D_{u,\ell}[k]$ 不是非负功率，而是一个不定二次型：目标方向能量被保留，目标正交能量被赋予负极性。

令

$$
t_u=\frac{\lambda_u}{1+\lambda_u},
\qquad 0\le t_u<1.
$$

由于 $\lambda_u$ 对同一包的所有 FFT bin 固定，最大化 $D_{u,\ell}[k]$ 等价于最大化

$$
S_{u,\ell}[k]
=
\frac{D_{u,\ell}[k]}{1+\lambda_u}
=
\|\mathbf{Y}_{u,\ell}[k]\|^2
\left(
\xi_{u,\ell}[k]-t_u
\right),
$$

其中

$$
\xi_{u,\ell}[k]
=
\frac{|\mathbf{a}_u^H\mathbf{Y}_{u,\ell}[k]|^2}
{\|\mathbf{Y}_{u,\ell}[k]\|^2}
$$

表示该 bin 的目标空间一致性。这个形式说明，SP-Decoder 不是简单“减一个谱峰”，而是在目标条件下要求强能量 bin 同时满足足够高的空间一致性。若一个错误 bin 能量很强但主要来自非目标空间方向，它的总能量越大，正交反证带来的惩罚也越大。因此，选择 $\lambda_u$ 等价于为整个目标包选择一个空间一致性阈值 $t_u$。

### 4.3 竞争峰翻转条件

设目标包当前真实符号为 $s=s_{u,\ell}$。目标 bin 与错误 bin $k$ 之间的 signed margin 为

$$
\Delta_{u,\ell,k}(\lambda_u)
=
D_{u,\ell}[s]-D_{u,\ell}[k].
$$

展开可得

$$
\Delta_{u,\ell,k}(\lambda_u)
=
A_{u,\ell,k}+\lambda_u B_{u,\ell,k},
$$

其中

$$
A_{u,\ell,k}
=
|P_{u,\ell}[s]|^2-|P_{u,\ell}[k]|^2
$$

是 MRC margin，而

$$
B_{u,\ell,k}
=
|Q_{u,\ell}[k]|^2-|Q_{u,\ell}[s]|^2
$$

表示错误 bin 相对正确 bin 的目标正交反证优势。SP-Decoder 将目标 bin 排在该错误 bin 前，当且仅当

$$
A_{u,\ell,k}+\lambda_u B_{u,\ell,k}>0.
$$

因此，当 MRC 已经失败，即 $A_{u,\ell,k}<0$，但错误 bin 拥有更强正交反证，即 $B_{u,\ell,k}>0$ 时，SP-Decoder 修复该错误所需的权重满足

$$
\lambda_u>
\frac{-A_{u,\ell,k}}{B_{u,\ell,k}}.
$$

该条件直接作用于实测碰撞后的 FFT 向量，因此多干扰相干叠加、频谱泄漏和交叉项都已包含在 $P$ 与 $Q$ 中，不需要假设不同干扰彼此独立。

这里的 $-A_{u,\ell,k}/B_{u,\ell,k}$ 是已知正确 bin 后对单个实际符号的精确解释量，接收机在解码前并不知道 $s_{u,\ell}$，因此不能直接用它选择包级权重。第 4.4–4.5 节将这一逐符号条件替换为基于信道可靠性、包功率和噪声的保守 pair 模型；第 5.3 节再由该模型推导可在线计算的 $\lambda_{uv}^{\mathrm{flip}}$。两者分别用于机理解释和实际求解。

### 4.4 包级可靠性边界

反证分支只有在目标方向可靠时才有价值。因此，SP-Decoder 为每个候选估计保守的角度不确定性。实现中使用稳健 preamble 快照、隔离权重、leave-one-out 变化、early-late 漂移和小的 RF 链路余量，得到

$$
\theta_u=\theta_{\mathrm{obs}}+\theta_{\mathrm{drift}}+\theta_{\mathrm{rf}}.
$$

目标可靠极性下界为

$$
L_u=\cos^2\theta_u.
$$

对干扰包 $v$，设 $\widehat{\theta}_{uv}$ 为 $u$ 与 $v$ 的测量信道夹角。由于干扰包自身信道估计也存在不确定性，SP-Decoder 使用保守泄漏上界

$$
U_{uv}=
\cos^2\left(\max(\widehat{\theta}_{uv}-\theta_v,0)\right).
$$

$L_u$ 下界化目标能量留在目标分支中的比例，$U_{uv}$ 上界化干扰能量泄漏到目标分支中的比例。因此，$\lambda_u$ 的选择依赖可靠性，而不仅是测得的信道相干性。

### 4.5 多干扰风险目标

固定 $\lambda$ 无法同时适应 near-far 比、信道相干性和噪声。SP-Decoder 对每个包只选择一次 $\lambda_u$。若 $L_u$ 过小或没有重叠干扰，接收机令 $\lambda_u=0$。否则，它要求目标在最坏信道偏差下仍保留正的有符号增益：

$$
L_u-\lambda_u(1-L_u)\ge \gamma.
$$

因此，搜索被限制在

$$
0\le \lambda_u\le
\lambda_{\mathrm{cap}}
=
\min\left(
\lambda_{\max},
\frac{L_u-\gamma}{1-L_u}
\right),
$$

其中 $\gamma$ 是目标极性保护项，$\lambda_{\max}$ 是系统上限。该约束直接给出实现中的 $\lambda_{\mathrm{cap}}$，防止信道方向不可靠时将目标自身泄漏误作反证。

对每个目标—干扰对 $(u,v)$，SP-Decoder 计算一个保守的有符号裕量代理。令 $S_u$ 和 $S_v$ 表示包功率，$\sigma^2$ 表示白化后的 FFT 域噪声方差。该 pair 贡献

$$
A_{uv}=S_uL_u-S_vU_{uv},
$$

$$
B_{uv}=S_v(1-U_{uv})-S_u(1-L_u).
$$

在 $\lambda$ 处的归一化风险分数为

$$
R_{uv}(\lambda)=
\frac{A_{uv}+\lambda B_{uv}}
{\sqrt{C_{0,uv}+\lambda^2C_{2,uv}}},
$$

其中

$$
C_{0,uv}
=
2\sigma^4+
2\sigma^2\left[S_uL_u+S_vU_{uv}\right],
$$

$$
C_{2,uv}
=
2\sigma^4+
2\sigma^2\left[S_u(1-L_u)+S_v(1-U_{uv})\right].
$$

分母用支持分支和反证分支中的噪声诱导变化对保守裕量归一化。令 $\mathcal I_u$ 表示与目标 payload 时间重叠的已检测干扰集合，定义最差对风险目标

$$
G_u(\lambda)=\min_{v\in\mathcal I_u}R_{uv}(\lambda).
$$

理想的包级权重选择问题为

$$
\lambda_u^\star
=
\arg\max_{0\le\lambda\le\lambda_{\mathrm{cap}}}
G_u(\lambda).
$$

该目标把任意数量的已检测干扰统一为一个一维 max–min 问题：每个 $R_{uv}$ 描述一个目标—干扰对，$G_u$ 则由当前最危险的 pair 决定。直接在连续区间密集采样虽然可以近似求解，但会引入与采样分辨率相关的成本，也无法解释最终权重为何被选择。第 5 章据此推导解析关键点与少量固定检查点，在不改变本章风险目标和安全区间的前提下完成有限求值。

### 4.6 本章小结

第 4 章完成三个建模步骤：首先将逐 bin 判决写成支持证据与正交反证的有符号二次型；其次用 $L_u$、$U_{uv}$ 和 $\lambda_{\mathrm{cap}}$ 描述信道不确定性下的目标保护区间；最后将噪声和所有已检测干扰纳入 $G_u(\lambda)$。本章只定义“应优化什么”，不规定接收器如何离散求解，也不重复描述前端检测、逐符号 FFT 或 CRC 流程。下一章给出与该模型对应的完整在线算法。

## 5. SP-Decoder 解码流程

第 4 章给出了连续约束问题 $\max_{\lambda\in[0,\lambda_{\mathrm{cap}}]}G_u(\lambda)$。本章将其嵌入完整接收链：前端首先产生可解码的完整包目标；随后接收机建立目标—干扰关系并构造有限 $\lambda$ 候选；最后，所选包级权重被用于该包的全部 payload 符号。整个过程只使用接收端可观测量和标准 PHY CRC，不依赖发送真值。

### 5.1 双通道预处理与并发包检测

设原始双通道采样为 $\mathbf x[n]\in\mathbb C^2$，空闲区估计的噪声均值和协方差分别为 $\widehat{\boldsymbol\mu}_n$ 与 $\widehat{\mathbf R}_n$。接收机首先执行

$$
\widetilde{\mathbf x}[n]
=
\mathbf W
\left(
\mathbf x[n]-\widehat{\boldsymbol\mu}_n
\right),
\qquad
\mathbf W\widehat{\mathbf R}_n\mathbf W^H=\mathbf I_2.
$$

白化使第 4 章中的 $\sigma^2$ 和双通道空间投影建立在一致噪声尺度上。前端在能量忙区中持续搜索前导码，而不是在发现最强包后跳过整个忙区。每个局部峰经 coarse CFO、SFD、start/STO 和双通道信道一致性验证后形成候选

$$
\mathcal P_i=
\left(
\widehat{\tau}_i,
\widehat{\epsilon}_i,
\widehat{\delta}_i,
\widehat{\mathbf h}_i,
\eta_i
\right),
$$

其中 $\eta_i$ 为综合同步置信度。对于时间接近的两个候选 $i,j$，前端使用归一化信道相似度

$$
\kappa_{ij}
=
\frac{
\left|\widehat{\mathbf h}_i^H\widehat{\mathbf h}_j\right|
}{
\|\widehat{\mathbf h}_i\|\|\widehat{\mathbf h}_j\|
}
$$

执行去重。只有在 start、CFO 均接近且 $\kappa_{ij}$ 超过去重阈值时，二者才视为同一物理包，并保留一个代表候选；时间接近但 CFO 或空间方向不同的候选被保留为并发目标。候选窗口必须满足

$$
0\le \widehat{\tau}_i,
\qquad
\widehat{\tau}_i+N_{\mathrm{frame}}\le N_{\mathrm{capture}},
$$

才能进入条件 PRR 解码集合。截断包单独计数，不作为 SP-Decoder 解码失败。

这一小节解决“同一忙区内是否还能发现后到达或更弱的包”，并向后端提供完整目标，而不承担 $\lambda_u$ 选择。包检测率和截断比例在第 7 章单独报告，因此不会与检测后条件 PRR 混合。

> **[结果占位：忙区内持续检测]**  
> 选取一个包含多个异步包的真实 busy region：上半图画双通道合并能量时间轴并标出各候选 start，下半图画 preamble track 的时间—CFO 散点，颜色表示归一化信道方向。图中同时标注“传统检测到最强包后跳过忙区”会漏掉的后到达候选，以及 SP-Decoder 前端保留的空间方向不同候选。统计结果放在第 7 章，以并发节点数或 offered load 为横轴报告完整包检测率；该结果只评价前端召回，不混入条件 PRR。

### 5.2 目标—干扰关系与包级统计

对目标候选 $u$，令其 payload 起点和整包终点分别为 $\tau_u^{\mathrm{pay}}$ 与 $\tau_u^{\mathrm{end}}$。与目标 payload 实际重叠的已检测干扰集合为

$$
\mathcal I_u
=
\left\{
v\ne u:
\tau_v<\tau_u^{\mathrm{end}},
\quad
\tau_v^{\mathrm{end}}>\tau_u^{\mathrm{pay}}
\right\}.
$$

只有 $\mathcal I_u$ 中的候选参与目标 $u$ 的风险建模。该限制避免把同一采集文件中出现但不影响当前 payload 的包错误计入最差干扰。

接收机在目标前导的多个稳定符号上取得信道快照 $\mathbf z_{u,p}$，并根据局部频谱隔离度和相对稳健中心的角度残差分配权重 $w_{u,p}$：

$$
\widehat{\mathbf h}_u
=
\frac{
\sum_{p\in\mathcal S_u^{\mathrm{pre}}}
w_{u,p}\mathbf z_{u,p}
}{
\sum_{p\in\mathcal S_u^{\mathrm{pre}}}w_{u,p}
}.
$$

leave-one-out 变化、前导前后半段漂移和 RF 余量共同形成第 4.4 节的 $\theta_u$。由此得到目标可靠性 $L_u$、各干扰泄漏上界 $U_{uv}$、包功率 $S_u,S_v$ 和白化后噪声方差 $\sigma^2$。本步骤只实例化第 4 章模型所需参数，不重新定义风险函数。

当 $\mathcal I_u=\varnothing$ 或 $L_u\le\gamma$ 时，接收机直接令 $\lambda_u=0$；前者表示没有已检测重叠干扰，后者表示目标方向不足以安全支撑反证。其余目标进入下一节的有限候选求值。

### 5.3 解析边界点与固定检查点

第 4 章的安全区间为 $[0,\lambda_{\mathrm{cap}}]$。SP-Decoder 不在其中做均匀 dense search，而是从第 4.5 节定义的每个 pair 风险函数 $R_{uv}(\lambda)$ 推导关键点。其分子由负转正的边界为

$$
\lambda_{uv}^{\mathrm{flip}}
=
-\frac{A_{uv}}{B_{uv}},
\qquad
A_{uv}<0<B_{uv}.
$$

该点表示目标相对干扰的保守有符号裕量刚好完成极性翻转。另一方面，

$$
\frac{\mathrm dR_{uv}(\lambda)}{\mathrm d\lambda}
=
\frac{
B_{uv}C_{0,uv}
-A_{uv}C_{2,uv}\lambda
}{
\left(
C_{0,uv}+\lambda^2C_{2,uv}
\right)^{3/2}
},
$$

因此单个 pair 的内部驻点为

$$
\lambda_{uv}^{\mathrm{peak}}
=
\frac{
B_{uv}C_{0,uv}
}{
A_{uv}C_{2,uv}
},
\qquad
A_{uv}>0,\;B_{uv}>0.
$$

只有落入 $[0,\lambda_{\mathrm{cap}}]$ 的 flip/peak 点才有效。每个 pair 在上述符号条件下至多贡献一个解析候选。

解析 pair 点仍不足以覆盖 max–min 目标。第 4.5 节定义的 $G_u(\lambda)$ 是多条风险曲线的下包络；其最大值可能落在区间端点，也可能靠近两条曲线发生“最差干扰身份切换”的交点。显式求解所有 pair 曲线交点会把候选构造提高到 $O(K_u^2)$。为保持线性候选规模，SP-Decoder 加入三个固定区间检查点

$$
\mathcal C_u^{\mathrm{fixed}}
=
\left\{
\frac14\lambda_{\mathrm{cap}},
\frac12\lambda_{\mathrm{cap}},
\frac34\lambda_{\mathrm{cap}}
\right\}.
$$

此外，令

$$
U_u^{\max}=\max_{v\in\mathcal I_u}U_{uv},
\qquad
t_u^{\mathrm{mid}}=
\frac{L_u+U_u^{\max}}{2},
$$

则可靠极性中点对应

$$
\lambda_u^{\mathrm{mid}}
=
\frac{t_u^{\mathrm{mid}}}
{1-t_u^{\mathrm{mid}}}.
$$

它仅在 $U_u^{\max}<L_u$ 且落入安全区间时加入。最终候选集合为

$$
\begin{aligned}
\mathcal C_u
=\;&
\{0,\lambda_{\mathrm{cap}}\}
\cup
\left\{
\lambda_{uv}^{\mathrm{flip}}
\right\}_{v\in\mathcal I_u}
\cup
\left\{
\lambda_{uv}^{\mathrm{peak}}
\right\}_{v\in\mathcal I_u}\\
&\cup
\left\{
\lambda_u^{\mathrm{mid}}
\right\}
\cup
\mathcal C_u^{\mathrm{fixed}},
\end{aligned}
$$

其中无效点被删除，剩余点截断到安全区间并按数值去重。若 $K_u=|\mathcal I_u|$，则

$$
|\mathcal C_u|\le K_u+6.
$$

因此候选规模随已检测干扰数量线性增长。

### 5.4 有限点评估与包级权重确定

SP-Decoder 对每个 $\lambda\in\mathcal C_u$ 计算全部 pair 风险，并按照第 4.5 节的定义取得 $G_u(\lambda)$。最终选择

$$
\widehat{\lambda}_u
=
\arg\max_{\lambda\in\mathcal C_u}G_u(\lambda).
$$

若多个候选具有相同目标值，接收机选择较小的 $\lambda$，使反证强度保持保守。选定权重对应空间一致性阈值

$$
\widehat t_u
=
\frac{\widehat\lambda_u}{1+\widehat\lambda_u}.
$$

当

$$
U_u^{\max}<\widehat t_u<L_u
$$

时，目标保留下界与干扰泄漏上界分别位于阈值两侧，接收机记录可靠极性证书；否则仍使用风险最优候选解码，但不宣称几何可分性得到认证。

> **[图 6 占位：有限边界点评估模型]**
>
> **左侧：参数生成。** 从目标不确定锥和多个干扰方向得到 $L_u$、$U_{uv}$，再形成每个 pair 的 $A_{uv},B_{uv},C_{0,uv},C_{2,uv}$。  
> **右侧：风险下包络。** 横轴为 $\lambda\in[0,\lambda_{\mathrm{cap}}]$；彩色细线画各 $R_{uv}(\lambda)$，粗黑线画 $G_u(\lambda)$。用不同形状标出端点、flip、peak、极性中点和三个固定检查点，并以红星标记 $\widehat\lambda_u$。图中至少包含一个单条曲线在 peak 点附近达到最大值的 pair，以及一次最差 pair 身份切换，使 flip/peak 与固定检查点各自承担的作用可被直接看出。连续曲线仅用于论文解释，在线算法只计算标出的有限点。

算法 1 在论文中应按如下输入输出呈现：

```text
Input : complete candidates {P_i}, whitened IQ, gamma, lambda_max
Output: decoded payloads and PHY-CRC states
for each complete target u:
    build overlap set I_u
    estimate h_u, L_u, {U_uv}, {S_v}, sigma^2
    derive lambda_cap and finite set C_u
    lambda_u <- arg max over C_u of min_v R_uv(lambda)
    decode every payload symbol using the shared lambda_u
    run standard LoRa FEC/CRC
    if CRC fails: invoke bounded start/CFO refinement
```

### 5.5 多个边界点的必要性验证

我们使用 formal-PHY 碰撞仿真专门验证有限候选构造。该实验固定 oracle start/CFO，从而只隔离“如何求解第 4 章风险目标”，不把前端漏检和同步误差混入结果。仿真保留标准 LoRa whitening、interleaving、Hamming FEC、Gray mapping、explicit header 和 PHY CRC。

每个样本包含一个目标和 $K_u\in\{1,3,7,14\}$ 个干扰，并分层覆盖信道相干性 $\rho\in[0.1,0.95]$、单干扰 SIR $\in[-15,5]$ dB、SNR $\in[0,20]$ dB 和信道不确定角 $[1^\circ,15^\circ]$。每个并发档至少生成 500 个包，固定并公开 master seed；所有样本均进入统计，不按结果筛选。

消融比较五种求值策略：

1. **Endpoints**：仅求值 $0$ 和 $\lambda_{\mathrm{cap}}$；
2. **Pairwise**：Endpoints 加所有有效 flip/peak 点；
3. **Polarity**：Pairwise 加可靠极性中点；
4. **Full-set**：Polarity 加 $1/4$、$1/2$、$3/4$ 固定检查点，即生产版候选构造；
5. **Dense-reference**：在同一安全区间取 4097 个等距点，仅作离线参照。

> **[图 7 占位：多边界点消融结果]**
>
> **(a) 代表性多干扰样本。** 展示各 pair 风险、下包络、所有候选来源、Full-set 选择和 Dense-reference 最优点。  
> **(b) 目标函数离散化损失 CDF。** 绘制
> $\delta_G=G_u(\lambda_{\mathrm{dense}}^\star)-G_u(\widehat\lambda_u)$，
> 比较 Endpoints、Pairwise、Polarity 和 Full-set。  
> **(c) SER–并发数曲线。** 横轴为干扰数 $K_u$，纵轴为 SER，同时画五种策略；若 Full-set 接近 Dense-reference，说明有限求值没有明显牺牲判决性能。  
> **(d) 候选来源与开销。** 堆叠条显示最终选择来自 low/cap boundary、flip、stat、midpoint 或 fixed checkpoint 的比例；副轴同时画平均 $|\mathcal C_u|$ 和实际 pair-risk 求值次数 $K_u|\mathcal C_u|$，分别呈现线性候选增长与当前 max–min 实现的二次求值开销。

该实验分别检验三件事：解析 pair 点能否补足仅取区间端点的损失；最差干扰身份发生切换时，固定检查点能否进一步逼近 dense reference；增加候选后得到的目标函数改善能否转化为实际 SER 改善。如果某一候选类别既从未被选中，也不降低 $\delta_G$ 或 SER，则应从最终算法中删除，而不能只根据示意图保留。

### 5.6 Payload 符号投影与 signed top-1

包级 $\widehat\lambda_u$ 选定后，对同一目标包的全部 payload 符号保持不变。对第 $\ell$ 个符号，接收机按 $\widehat\tau_u+\widehat\delta_u$ 读取双通道窗口，并补偿连续 CFO：

$$
\mathbf r_{u,\ell}[n]
=
\widetilde{\mathbf x}
\left[
\widehat\tau_u+\widehat\delta_u+
\left(\nu_{\mathrm{pay}}+\ell\right)N+n
\right]
\exp\left(
-j2\pi\widehat\epsilon_u n/N
\right).
$$

其中 $\nu_{\mathrm{pay}}$ 是从包起点到 payload 起点的已知 PHY 符号偏移。

两根天线分别乘以标准 downchirp $c_\downarrow[n]$ 并执行 LoRa FFT：

$$
\mathbf Y_{u,\ell}[k]
=
\begin{bmatrix}
\operatorname{FFT}\{r_{u,\ell}^{(1)}[n]c_\downarrow[n]\}[k]\\
\operatorname{FFT}\{r_{u,\ell}^{(2)}[n]c_\downarrow[n]\}[k]
\end{bmatrix}.
$$

随后将 $\mathbf Y_{u,\ell}[k]$ 代入第 4.1 节已经定义的 $P_{u,\ell}[k]$、$Q_{u,\ell}[k]$ 和 $D_{u,\ell}[k]$，使用本包共享的 $\widehat\lambda_u$ 完成 signed top-1。为记录判决置信度，接收机同时保存最高与次高有符号分数之差

$$
m_{u,\ell}
=
D_{u,\ell}[k_{(1)}]
-
D_{u,\ell}[k_{(2)}],
$$

其中 $k_{(1)}$ 和 $k_{(2)}$ 分别为得分第一和第二的 bin。该步骤只执行一次 top-1，不保留组合式候选树，也不依赖当前干扰符号。第 2.5 节 M1 已通过同一真实碰撞符号的支持谱、反证谱和有符号谱展示错误峰如何被压低，因此本节不重复设计第二组等价频谱实验。

### 5.7 标准 PHY 闭环与有界同步细化

全部 $\widehat s_{u,\ell}$ 依次进入 LoRa Gray demapping、deinterleaving、Hamming FEC、dewhitening、explicit-header 解析和 PHY CRC。SP-Decoder 的成功条件是标准 FEC/CRC 后 payload 完全正确，而不是符号正确率超过某个阈值。

若首次解码通过 PHY CRC，接收机立即输出，不执行任何搜索。若失败，则在前端估计附近评估预定义的有限 trial 集

$$
\mathcal T_u
=
\left\{
\left(
\Delta\tau_j,\Delta\epsilon_j
\right)
\right\}_{j=1}^{J},
\qquad
J\le 32.
$$

每个 trial 使用

$$
\tau_u^{(j)}
=
\widehat\tau_u+\Delta\tau_j,
\qquad
\epsilon_u^{(j)}
=
\widehat\epsilon_u+\Delta\epsilon_j,
$$

在 trial CFO 附近重新估计目标信道，并重跑第 5.6 节的符号判决和标准 PHY。生产实现复用首次风险选择的 $\widehat\lambda_u$，因此 sync-refine 不会演变为对 timing、CFO 和 $\lambda$ 的无界联合 oracle 搜索。搜索在 PHY CRC 闭环或达到 trial 上限时停止；manifest、期望 payload 和应用层序号均不参与选择。

> **[结果占位：SP-Core 与 SP-Decoder 消融]**  
> 该结果放在第 7 章真实空口实验，而不在设计章节另立同步实验。图以并发数或 offered load 为横轴，同时报告 SP-Core 和 SP-Decoder 的条件 PRR；附表报告触发 refinement 的包比例、平均 trial 数和达到 32 次上限的比例。该消融只回答有界细化对端到端方案的贡献，不把本文包装成新的同步算法。

正文将包含条件式细化的完整方法称为 **SP-Decoder**，将首次一次解码路径称为 **SP-Core**。实现中的 `sp_sync_refine` 对应 SP-Decoder；`sp_repair` 会进一步重试其他理论候选点或执行频谱/FEC 修复，仅作为附录诊断上界。

### 5.8 复杂度

设目标包有 $K_u$ 个已检测重叠干扰、$L_{\mathrm{pay}}$ 个 payload 符号，每个符号包含 $M=2^{\mathrm{SF}}$ 个 LoRa bins。包级阶段生成至多 $K_u+6$ 个候选需要 $O(K_u)$；每个候选必须对 $K_u$ 个 pair 计算最差风险，因此当前实现的完整有限点评估复杂度为

$$
O\left(K_u|\mathcal C_u|\right)=O(K_u^2).
$$

这一复杂度关于 FFT bin 数和 payload 长度无关；在本文最多 14 个干扰的设置下，候选风险计算远小于逐符号 FFT。符号阶段在两根天线上执行 FFT、两个二维投影和一次逐 bin top-1，复杂度为

$$
O\left(
L_{\mathrm{pay}}
\left[
M\log M+M
\right]
\right).
$$

因此 SP-Core 的总复杂度为

$$
O\left(
K_u^2+
L_{\mathrm{pay}}M\log M
\right).
$$

若 CRC 失败并触发 $J$ 次有界同步 trial，最坏复杂度增加为 $J$ 倍符号译码代价，但 $J\le32$ 且只作用于失败包。SP-Decoder 不重构干扰波形，不按干扰数量串行执行 SIC，也不进行指数级符号组合搜索。

## 6. 原型实现

### 6.1 硬件与 PHY

原型由一台双通道同步接收 USRP B210、15 个 STM32F103/SX1276 LoRa 节点和一台发送 CONFIG/START 的控制 B210 构成。节点发送未经修改的标准 LoRa 包。接收参数固定为 487.7 MHz、SF10、BW125 kHz、CR4/5、8-symbol preamble、explicit header、PHY CRC、sync word 0x34 和 20-byte payload。接收端保存原始双通道 IQ，依次执行 DC 去除、通道校准和基于实测噪声协方差的白化。完整参数集中列于 Table 1，不在正文重复展开。

### 6.2 软件与候选接口

软件前端输出完整包候选及其 start、CFO、STO、稳健信道、信道不确定性、功率、重叠关系和噪声统计；SP-Decoder 在此基础上记录 $L_u$、$U_{uv}$、$\lambda_{\mathrm{cap}}$、全部候选点和最终 $\lambda_u$。每个候选同时保存 SP-Core、SP-Decoder、SP-repair 及各基线的 PHY/FEC/CRC 结果，以便从冻结 JSON 重建所有论文图。manifest 和期望 payload 仅用于离线计数与正确性核验，从不参与检测、同步、候选选择或 CRC 搜索。

### 6.3 比较方法

所有解码器运行在相同的完整检测目标和相同的有界 refined timing/CFO 上，从而将包检测率与检测后条件 PRR 分离。MRC 使用目标信道最大比合并；CIC 实现 ICSS spectral intersection、fractional-CFO/RSSI filtering 和 ten-window SED，并固定在一个物理天线分支；PCube-2Rx 使用唯一物理接收天线对的 preamble PDoA 与逐 bin PDoA 聚类，不声称多 pair combining；MaLoRaGW-2Rx 实现上行信道选择、Moore–Penrose ZF 投影以及频率/时间/信道比峰聚类，不评估其下行校准或 beamforming。正文主方法统一记为 SP-Decoder，SP-Core 用于消融，SP-repair 仅列于附录。

## 7. 评估方法

### 7.1 指标

评估将检测和解码分开。

包检测率是检测到的完整包目标数除以实际发送包数。当只有 manifest 可用时，使用 schedule-normalized 包检测率，即检测到的完整包目标数除以 manifest 计划发送数。

条件 PRR 是检测到的完整包目标中，FEC/PHY CRC 闭环且 payload 正确的包数，除以检测到的完整包目标数。截断包不进入该分母，并单独报告。成功准则是标准 FEC 和 PHY CRC 后 payload 完全一致；不使用符号正确率阈值。

端到端 delivery ratio 使用正确唯一 payload 数除以实际或计划发送数。TPS 表示每秒正确解码包数。

### 7.2 仿真与 Trace-driven 研究

评估只在真实空口难以精确控制的变量上使用仿真。

M1 使用实测 clean packet 展示 MRC 错误 bin 中常存在目标正交反证。它保留真实波形损伤，并展示 signed spectrum 观察。

M2 复用实测 clean packet 产生的 trace records，绘制 MRC SER 关于 $\rho$ 和 SIR 的变化。该图避免理想化 0/1 heatmap，并在引入 SP-Decoder 之前建立 near-far/coherence 失败边界。

M3 从实测 clean packet 自助采样合成多包碰撞，并加入受控波形噪声。主图报告 MRC SER 关于并发包数量和目标波形 SNR 的变化。它是动机图，不声称低 SNR 前端检测增益。

D1 在有符号谱和风险目标引入之后评估 $\lambda_u$。该 formal-PHY 实验包含 explicit header、FEC、whitening、interleaving、Hamming coding、Gray mapping 和 PHY CRC，并使用第 5.5 节定义的 Endpoints、Pairwise、Polarity、Full-set 与 Dense-reference 五组候选集。主结果报告目标函数离散化损失 CDF、SER 随并发数的变化和最终候选来源比例，以分别验证解析 pair 点、固定检查点和候选数量线性增长的意义。

正文不设置独立的 sync-refine 机制实验。有界同步细化通过主真实空口 SP-Decoder 结果和 SP-Core 消融体现。

### 7.3 真实空口实验

真实空口实验使用 15 个节点和双天线 B210 接收机。由于当前控制端和固件采用 CONFIG v1 与 Poisson offered load，实验不要求 deterministic barrier traffic 或精确 per-node offset。相反，实验依赖重复 run、seed 选择和 manifest accounting 获得不同碰撞阶数。

真实实验包括：

- 15 个节点的单节点 gate check；
- active node count scaling；
- offered-load sweep；
- 至少两个物理布局，避免只报告有利信道；
- 使用距离变化而非射频衰减器的 near-far 研究；
- 对已检测完整目标进行 decoder-only AWGN stress；
- SP-Core/SP-Decoder 消融；
- 完整离线接收机 wall-clock runtime。

主真实空口图包括条件 PRR、包检测率、TPS 和端到端 delivery。由于前端检测和条件解码回答的问题不同，本文不把它们合并为一个含糊 delivery 指标。

### 7.4 公平性与范围

所有真实空口方法比较使用相同完整检测目标。该设计隔离检测和同步之后的解码器行为。本文不声称复现每个 baseline 论文的完整 native front end。对 CIC、PCube 和 MaLoRaGW，实现遵循对应论文在双通道上行 B210 记录约束内可执行的 decoder 操作，并在报告中明确这些限制。

主比较集合为：

- SP-Decoder；
- MRC；
- CIC；
- PCube-2Rx；
- MaLoRaGW-2Rx-uplink。

SP-Core 是消融。SP-repair 只放附录。

## 8. 适用区间与设计含义

有符号模型指出 SP-Decoder 相对 MRC 获益需要三个条件：目标和干扰在空间上并非近共线，干扰足够强以形成 MRC 错峰，目标信道足够可靠使反证不会惩罚真实 bin。这些条件常见于异步 near-far 碰撞和两根分离接收天线，但并非普遍成立。

当信道相干性很高，即 $\rho_{uv}\approx 1$ 时，目标正交分支无法可靠地区分目标和干扰。可靠性约束会将 SP-Decoder 推向较小 $\lambda_u$，接近 MRC。因此，高相干碰撞是 SP-Decoder 的明确适用边界，而不是被忽略的角落情况。

在很低 SNR 下，反证只有在目标已经被检测和同步之后才可能帮助判决。因此，噪声 sweep 衡量的是完整目标上的 decoder robustness，而不是低 SNR preamble detection 增益。

当包完全对齐且共享 header 符号时，多个用户可能在同一 FFT bin 放置能量。此时该 bin 同时包含目标和干扰证据，简单减去整个目标正交分量可能不足，甚至有害。SP-Decoder 面向异步并发 LoRa 流量；完全对齐共享 bin 碰撞是明确限制。

## 9. 讨论

SP-Decoder 在 LoRa 碰撞恢复设计空间中占据一个明确位置。它不是包检测、时域分离或多 pair 空间聚类的替代品。相反，它在双天线接收机已经获得完整包候选之后，改进最终目标条件符号判决。这个范围比完整端到端碰撞恢复更窄，但也正是方法轻量且兼容标准 LoRa 发射机的原因。

可靠性约束的 $\lambda_u$ 是该范围成立的关键。较大的固定相减权重可以产生有吸引力的个例，但在信道不确定性和噪声下会失败；零权重安全，但退化为 MRC。SP-Decoder 的贡献在于包级机制：判断何时反证可信，以及在不违反目标可靠极性区间的前提下能相减到什么程度。

双天线设置既是约束也是机会。只有两根天线时，目标正交方向唯一，因此有符号谱解释简单且计算代价低。更多天线可以形成更高维反证子空间，但该扩展需要新的可靠性模型，不属于本文研究的双天线系统。

## 10. 结论

本文提出 SP-Decoder，一种面向并发 LoRa 接收的风险约束有符号空间解码器。SP-Decoder 揭示了 MRC 式合并中的正能量判决瓶颈，并通过同时保留目标方向支持和目标正交反证解决该问题。在信道不确定性、噪声和多个干扰存在时，SP-Decoder 在安全区间的有限候选点上优化最差目标—干扰对风险，选择包级反证权重。接收机将有符号判决与条件式有界同步细化、标准 LoRa FEC 和 PHY CRC 结合，不重构干扰波形，也不修改发射端。将包检测率与条件 PRR 分离，使评估能够准确区分前端召回和检测后解码。该架构为双天线网关上的碰撞恢复提供了一条轻量路径，同时明确指出高相干和同步边界。

## References

\bibitem{cic_sigcomm21}
M. O. Shahid, M. Philipose, K. Chintalapudi, S. Banerjee, and B. Krishnaswamy. 2021. Concurrent Interference Cancellation: Decoding Multi-Packet Collisions in LoRa. In *ACM SIGCOMM 2021*. https://doi.org/10.1145/3452296.3472931.

\bibitem{pcube_mobicom21}
X. Xia, N. Hou, Y. Zheng, and T. Gu. 2021. PCube: Scaling LoRa Concurrent Transmissions with Reception Diversities. In *ACM MobiCom 2021*. https://doi.org/10.1145/3447993.3483268.

\bibitem{maloragw_sensys22}
H. Pirayesh, S. Zhang, P. K. Sangdeh, and H. Zeng. 2022. MaLoRaGW: Multi-User MIMO Transmission for LoRa. In *ACM SenSys 2022*. https://doi.org/10.1145/3560905.3568533.
