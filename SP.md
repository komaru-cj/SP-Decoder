1 引言
低功耗广域网络（Low-Power Wide-Area Network，LPWAN）通过低速率、长距离和低功耗通信，为大规模物联网设备提供广域连接能力。作为应用最广泛的 LPWAN 技术之一，LoRa 使用 Chirp Spread Spectrum（CSS）调制并采用基于 ALOHA 的随机接入机制。随着同一网关覆盖范围内设备数量增加，多个终端在相同载频、带宽和扩频因子下近似同时发送的概率显著上升。传统 LoRa 接收机通常只能利用捕获效应恢复最强包，其余碰撞包需要重传，由此带来的信道占用和能量开销逐渐成为限制 LoRa 网络容量的主要因素。
现有 LoRa 并发解码研究主要从时间、频率和空间三个维度提取包间差异，多天线方法则尝试利用传播信道提供的接收为并发分集。这些研究表明，LoRa 碰撞并非被视为不可恢复的干扰。然而，在完成目标包检测、同步和信道估计后，目标符号仍可能在最终 FFT 判决阶段被强干扰峰覆盖。在传统MIMO的最大比合并（Maximum Ratio Combining，MRC）算法中，以最小支持波束赋形的双天线为例，设目标包 $$u$$ 的单位信道方向为 $$\mathbf a_u$$，目标对齐并完成解啁啾后的第 $$k$$ 个双天线 FFT 观测为 $$\mathbf Y_u[k]$$。MRC 使用
$$M_u[k]
=
\left|
\mathbf a_u^H\mathbf Y_u[k]
\right|^2$$
对各个 FFT bin 排序。该处理能够增强与目标信道方向一致的信号。空间不一致只会降低干扰在目标方向上的投影，而不会使该干扰失去成为候选峰的资格。当干扰功率足够强时，即使其信道方向与目标并不一致，残余投影仍可能超过目标符号峰并占据 top-1。受MRC启发，本文首次揭示了这一制约LoRa并发解码性能的关键因素，并将其正式命名为非负判决瓶颈（positive-only decision bottleneck）。
这一瓶颈并非源于双天线观测缺少空间信息，而是源于传统合并在判决前丢弃了部分已有信息。对于目标包而言，除目标信道方向外，二维接收空间中还存在一个与目标信道正交的方向。理想目标信号应主要出现在目标方向，而在正交方向上接近于零。相反，一个由非目标包产生的错误 FFT 峰，即使在目标方向上具有较强投影，通常仍会在目标正交方向留下可观能量。如图 1 所示，该正交分量是反驳“该 FFT bin 属于目标包”这一假设的重要空间反证。
[图片]
图 1：非负判决瓶颈与 SP-Decode 的核心观察。图中展示同一个真实多包碰撞符号在三种频谱中的差异：（a）目标方向支持谱 $$|P_u[k]|^2$$ 中，强干扰峰成为 MRC 的最高峰；（b）目标正交方向反证谱 $$|Q_u[k]|^2$$ 中，该错误峰呈现显著空间不一致性，而真实目标 bin 的正交能量接近于零；（c）有符号谱 $$D_u[k]$$ 中，错误峰受到正交反证惩罚后，真实目标 bin 成为最终 Top-1。
基于上述观察，本文提出 SP-Decode（Signed Projective Decode），首次将目标—正交子空间判别嵌入 LoRa 解啁啾后的逐 bin 符号排序，并解决其在并发包同步、信道不确定性和多干扰聚合条件下的系统化实现问题。对每个已检测目标包$$u$$，接收机依据其双天线信道构造目标方向$$\mathbf a_u$$及正交方向$$\mathbf b_u$$分别获得支持谱与反证谱，随后构造基于反证权重$$\lambda_u$$的有符号空间判决谱。与MRC 仅对干扰进行空间衰减不同，SP-Decode 将空间不一致性显式写入符号排序：能量很强但空间方向与目标不符的 FFT 峰将受到与其正交能量相对应的惩罚。该方法不依赖干扰包重构，不需要按功率顺序执行串行干扰消除，也不需要在多个符号候选之间进行组合搜索。其主要计算由双通道 LoRa $$M$$ 点 FFT、二维空间投影和逐 bin 实数运算构成，与标准双天线 LoRa 解调具有相同的 $$O(M\log M)$$ 复杂度量级。
然而，将这一简洁判决机制转化为可部署的 LoRa 并发接收系统仍面临三个关键问题。首先，SP-Decode 需要为每个目标包获得可靠的起始位置、CFO、STO 和双天线信道方向，而并发前导码之间的重叠会污染同步峰与信道估计。尤其在 near-far 场景中，弱包前导可能被强包压制，若目标信道方向估计偏移，目标能量本身也会泄漏到正交分支并被错误扣除。其次，反证权重 $$\lambda_u$$ 不能仅由干扰信道相干度决定。过小的 $$\lambda_u$$ 无法修正强错误峰，过大的 $$\lambda_u$$ 则会放大正交分支噪声和信道估计误差。最后，在多包碰撞中，同一 FFT bin 可能包含多个干扰的相干叠加，其聚合空间方向不一定等同于任何单个干扰信道。因而，系统既需要刻画 SP-Decode 的可保证工作区间，也需要明确空间近共线和多干扰聚合条件下的能力边界。
为解决上述问题，本文设计并实现一个完整的双天线 LoRa 并发接收流程。
本文的主要贡献概括如下：
1. 揭示双天线 LoRa 符号判决中的非负判决瓶颈。 本文指出，传统空间合并仅保留目标方向上的非负支持能量，使强干扰即使与目标信道方向不一致，仍可能凭借 near-far 优势成为 top-1。通过真实接收波形，我们进一步验证错误峰与正确目标峰在目标正交方向上呈现可利用的差异。
2. 提出目标条件化的有符号空间解啁啾方法。 SP-Decode 同时保留每个 FFT bin 的目标方向支持证据与目标正交方向反证，将 LoRa 符号判决从非负峰值竞争转化为空间一致性约束下的有符号排序。该方法保持 COTS LoRa 发送端兼容，并以一次直接 Top-1 输出目标符号。
3. 构建具有可靠性约束的双天线 LoRa 并发接收系统。 本文设计多投影前导检测、SFD 辅助同步、碰撞鲁棒信道估计和信道方向置信建模，并联合目标可靠性、干扰相干度与噪声风险选择包级反证权重。我们在双天线 SDR 原型上从符号级、包级和系统开销三个层面评估 SP-Decode，并明确其在高信道相干、多干扰聚合及信道动态条件下的适用边界。
2 背景与动机
本章首先给出支撑后续设计所需的 LoRa 解调与双天线碰撞模型，随后分析现有并发解码方法在最终符号判决阶段保留和丢弃的信息。最后，我们使用真实双通道 LoRa 接收波形开展初步研究，回答两个问题：在同步和信道参数准确时，传统双天线合并是否仍会发生大量符号错误；目标正交方向是否稳定包含能够区分正确峰与错误峰的信息。上述观察共同导出 SP-Decode 的设计需求。
2.1 LoRa 调制与 FFT 解调
2.1.1 LoRa 符号
设扩频因子为 $$\mathrm{SF}$$，则一个 LoRa 符号可表示
$$M=2^{\mathrm{SF}}$$
种取值，符号持续时间为
$$T_{\mathrm{sym}}
=
\frac{M}{\mathrm{BW}},$$
其中 $$\mathrm{BW}$$ 为 LoRa 信号带宽。
设接收采样率为
$$F_s=L\cdot \mathrm{BW},$$
其中 $$L$$ 为过采样率，则每个符号包含
$$N=LM$$
个复采样。记标准离散基准 upchirp 为 $$c[n]$$，$$0\leq n<N$$。符号 $$s\in\{0,\ldots,M-1\}$$ 可写为
$$x_s[n]
=
c[n]
\exp
\left(
j2\pi\frac{s}{N}n
\right)
e^{j\phi_s},$$
其中 $$\phi_s$$ 为与符号索引和离散 chirp 定义有关、但不影响非相干 FFT 判决的常相位
2.1.2 Dechirp 与 LoRa FFT
接收端将符号与标准 downchirp
$$d[n]=c^*[n]$$
逐点相乘。理想单包条件下，
$$x_s[n]d[n]
=
e^{j\phi_s}
\exp
\left(
j2\pi\frac{s}{N}n
\right),$$
即原始 chirp 被转换为频率由 $$s$$ 决定的单音信号。记接收端从 $$N=LM$$ 个过采样点中提取与实际 LoRa 解调一致的 polyphase 分支，并在该分支上执行 $$M$$ 点 FFT 的算子为
$$\mathcal F_{\mathrm{LoRa}}\{\cdot\}.$$
理想情况下，
$$Z_s[k]
=
\mathcal F_{\mathrm{LoRa}}
\left\{
x_s[n]d[n]
\right\}[k]$$
在 $$k=s$$ 处形成相干峰。标准 LoRa 接收机据此执行
$$\hat s
=
\arg\max_{0\leq k<M}
|Z_s[k]|^2.$$
CFO、分数 STO、窗口错位、多径和并发干扰会使能量偏移或扩散到其他 bins，但标准接收机的最终判决仍然是从一个非负 FFT 功率谱中选择最大峰。
2.2 双天线并发接收模型
考虑 $$U$$ 个使用相同载频、带宽和扩频因子的 LoRa 包在双天线网关处发生重叠。接收信号写为
$$\mathbf y[n]
=
\sum_{v=1}^{U}
\mathbf h_v
x_v[n-\tau_v]
\exp
\left(
j2\pi\frac{\epsilon_v}{N}n
\right)
+
\mathbf w[n],$$
其中：
- $$\mathbf y[n]\in\mathbb C^2$$ 为双天线复基带观测；
- $$\mathbf h_v\in\mathbb C^2$$ 为包 $$v$$ 的双天线等效复信道；
- $$\tau_v$$ 为包起始时间及 STO；
- $$\epsilon_v$$ 为以 LoRa FFT bin 归一化的载波频偏；
- $$x_v[\cdot]$$ 为包 $$v$$ 的 LoRa 基带波形；
- $$\mathbf w[n]$$ 为接收噪声和未建模硬件失真。
图 2：双天线并发接收示意图。
对于目标包 $$u$$ 的第 $$\ell$$ 个 payload 符号，接收机依据目标参数读取符号窗口，补偿 $$\tau_u$$ 和 $$\epsilon_u$$，并在两根天线上执行相同的标准 dechirp 与 $$M$$ 点 FFT。第 $$k$$ 个 LoRa bin 的双天线观测可统一写为
$$\boxed{
\mathbf Y_{u,\ell}[k]
=
\sum_{v=1}^{U}
\mathbf h_v
A_{uv,\ell}[k]
+
\mathbf N_{u,\ell}[k],
}$$
其中 $$A_{uv,\ell}[k]$$ 表示包 $$v$$ 在目标包 $$u$$ 的窗口、同步补偿和 downchirp 下产生的标量频谱响应。
对于目标包自身，在同步准确且信道在一个符号内近似平坦时，
$$A_{uu,\ell}[k]
\approx
\begin{cases}
C, & k=s_{u,\ell},\\
0, & k\neq s_{u,\ell},
\end{cases}$$
其中 $$s_{u,\ell}$$ 为目标符号，$$C$$ 为 $$M$$ 点 FFT 的相干增益。对非目标包，其响应由相对 STO、CFO、当前符号及窗口切分共同决定，可能在某个 bin 形成集中峰，也可能在多个 bins 间产生泄漏。
在进入空间判决前，双天线观测经过射频链校准和噪声预白化。为简化符号，本文后续的 $$\mathbf Y_{u,\ell}[k]$$、$$\mathbf h_v$$ 和 $$\mathbf N_{u,\ell}[k]$$ 均表示预白化后的量，满足
$$\mathbf N_{u,\ell}[k]
\sim
\mathcal{CN}
\left(
\mathbf0,\sigma^2\mathbf I_2
\right).$$
2.3 现有并发解码方法
LoRa 并发解码的核心任务不是简单检测多个 FFT 峰，而是判断每个峰代表哪个符号、属于哪个包，以及如何在强干扰下保留弱目标。现有工作主要利用以下几类可分性。
2.3.1 时间与频率结构
FTrack、CoLoRa、NScale、Pyramid、CIC 和 AlignTrack 等工作利用异步发送带来的 symbol offset、峰值轨迹、相邻窗口峰值比例或子符号边界差异恢复并发包 \cite{ftrack_sensys19,colora_infocom20,nscale_mobisys20,pyramid_infocom21,cic_sigcomm21,aligntrack_icnp21}。这类方法能够在单天线条件下分离多个包，但其判决依赖目标和干扰在时间或频率结构上存在足够差异。当包边界接近、多个包出现相同符号、弱峰被强峰覆盖或子窗口过短时，可利用特征会显著减弱。
2.3.2 波形重设计
CurvingLoRa 等工作通过修改发送 chirp 改善碰撞信号的互相关结构 \cite{curvinglora_nsdi22}，但需要改变发送端物理层。本文聚焦于标准 LoRa 发射波形和不依赖串行重构的接收端设计。
2.3.3 空间信道特征
多天线为每个 FFT bin 提供复向量观测。PCube 从多个接收天线中提取跨天线信道相位，并将其作为包级聚类特征，从相位域补充传统时间域和频率域方法 \cite{pcube_mobicom21}。MaLoRaGW 使用空间投影和主成分分析支持 LoRa 多用户接收 \cite{maloragw_sensys22}。Hi²LoRa 进一步融合双天线信道、硬件差异和时间模式构造高维分类特征 \cite{hi2lora_icnp23}。
这些方法证明了传播信道可以为 LoRa 碰撞恢复提供新的区分维度。然而，它们主要将空间信息用于：
- 跨符号聚类；
- 多用户流投影；
- 设备或包级特征分类；
- 接收信噪比增强。
本文关注一个更靠近解调器末端的问题：当目标包已经被检测、同步并获得信道估计后，如何利用双天线空间信息决定当前 FFT bins 中哪一个最可能属于目标符号。
表 1 总结了不同方法在最终判决前保留的主要证据。
方法类别
代表方法
主要证据
典型输出
对当前问题的局限
时间轨迹/窗口关系
FTrack、CoLoRa、NScale、AlignTrack
STO、峰值轨迹、窗口比例
包级聚类或目标峰
高度对齐、相同符号或弱峰不可见时退化
子符号消除
CIC
多个子窗口中的频率不变性
公共频率集合
短窗频率分辨率下降，依赖 symbol transition
波形重构
CurvingLoRa
非线性模板不匹配时能量散射
目标峰
频谱污染随包数增加
相位聚类
PCube
PDoA/air-channel phase
符号所属包
相位污染或信道相近时类簇重叠
空间投影
MRC、MaLoRaGW
目标方向或干扰零空间
单路合并信号
最终峰值通常仍为非负能量竞争
高维特征
Hi²LoRa
CSI、硬件与时间模式
包级分类结果
依赖特征稳定性和训练分布
本文
SP-Decode
目标方向支持与正交方向反证
目标条件化有符号 Top-1
需要可靠信道方向，近共线场景受限
2.4 双天线 MRC 的非负判决瓶颈
设目标包 $$u$$ 的单位信道方向为
$$\mathbf a_u
=
\frac{\mathbf h_u}{\|\mathbf h_u\|}.$$
MRC 对每个 FFT bin 计算
$$M_{u,\ell}[k]
=
\left|
\mathbf a_u^H
\mathbf Y_{u,\ell}[k]
\right|^2$$
并选择最大值。MRC 可以在加性白噪声和单目标条件下最大化输出信噪比，但在碰撞解调中，它仍然把所有 bins 映射为非负分数。
为直观说明这一局限，考虑正确目标 bin 主要包含目标包，某个错误 bin 主要包含干扰包 $$v$$。定义目标与干扰的归一化平方信道相干度
$$\rho_{uv}
=
\frac{
|\mathbf h_u^H\mathbf h_v|^2
}{
\|\mathbf h_u\|^2
\|\mathbf h_v\|^2
}.$$
若目标峰和干扰峰的接收能量分别为 $$E_u$$ 和 $$E_v$$，且目标信道估计准确，则它们在 MRC 输出中的主要分量近似为
$$\begin{aligned}
M_u[s_u]&\approx E_u,\\
M_u[k_v]&\approx E_v\rho_{uv}.
\end{aligned}$$
因此，当
$$E_v\rho_{uv}>E_u$$
时，MRC 会选择错误干扰峰。降低 $$\rho_{uv}$$ 只能按比例衰减干扰；只要 $$E_v$$ 足够大，错误峰仍然可以成为 top-1。换言之，MRC 能回答“该 bin 在目标方向上有多强”，但无法回答“该 bin 是否还包含大量与目标方向矛盾的能量”。
2.5 初步研究与观察
在二维接收空间中，令 $$\mathbf b_u$$ 为与 $$\mathbf a_u$$ 正交的单位方向
$${\mathbf b}_u
=
\begin{bmatrix}
- a_{u,2}^*\\
a_{u,1}^*
\end{bmatrix},$$
并满足
$$\hat{\mathbf b}_u^H\hat{\mathbf a}_u=0,
\qquad
\|\hat{\mathbf b}_u\|=1.$$
对任意 FFT bin，构造两路复数证据：
$$\begin{aligned}
P_u[k]
&=
\mathbf a_u^H\mathbf Y_u[k],\\
Q_u[k]
&=
\mathbf b_u^H\mathbf Y_u[k].
\end{aligned}$$
$$P_{u,\ell}[k]$$ 是目标对齐分支。当该 bin 来自目标包时，其空间向量应主要投影到该分支。$$Q_{u,\ell}[k]$$ 是目标阻塞分支。若信道估计准确，理想目标信号在该分支中应被完全消除。传统 MRC 在形成单路标量输出时丢弃了 $$Q$$ 分支，因此形成非负判决瓶颈。为了检验目标正交方向是否在真实接收波形中提供稳定反证，我们基于同步双通道 USRP B210 采集的 LoRa 波形开展 trace-driven 初步研究。
实验使用当前真实采集的 SF10、BW125 kHz、1 MS/s 双天线 LoRa 数据。我们从十个空间位置的 clean traces 中提取完整 LoRa 包，保留其接收功率、CFO、硬件失真、噪声背景和双天线复信道；随后选择二包组合并以分数符号偏移合成为碰撞窗口。该初步研究只用于验证符号判决瓶颈，因此采用 oracle 包起点、CFO 和双天线信道，避免将前端检测误差混入最终符号判决现象。实验共覆盖 $$20$$ 个二包方向组合、$$6$$ 个 SIR 水平（$$-5$$ dB 到 $$0$$ dB）以及 $$5$$ 个分数符号偏移，共得到 $$22{,}800$$ 个 payload 符号观测。
图 3 统计了 MRC 在 oracle 同步和 oracle 信道条件下的符号错误率。横轴为目标与干扰信道方向的平方相干度 $$\rho$$，并按低相干、中等相干、高相干和近共线四个区间聚合；纵轴为 SIR，SIR 越低表示干扰相对于目标越强。结果显示，当信道相干度较低时，即使存在明显远近效应，MRC 错误率仍然较低；但当 $$\rho>0.8$$ 且 SIR 降至 $$-5$$ dB 时，MRC SER 达到 $$0.970$$。这表明错误并非主要来自同步或信道估计误差，而是来自非负峰值竞争本身：强干扰只要在目标方向上保留足够投影，就可能覆盖目标符号。
[图片]
图 3：MRC 在 oracle 同步和信道条件下的符号错误率
为了验证正交分支是否具有统计稳定性，图 4 比较了 MRC 错误符号中真实目标 bin 与 MRC 最高错误 bin 的空间不一致度
$$\eta_u[k]
=
\frac{|Q_u[k]|^2}
{|P_u[k]|^2+|Q_u[k]|^2+\varepsilon}.$$
其中 $$\eta_u[k]$$ 表示第 $$k$$ 个 bin 中落在目标正交方向的能量比例。若某个 bin 真正属于目标包，该比例应接近零；若该 bin 主要由非目标包形成，则通常会包含更强的目标正交分量。在 $$5{,}794$$ 个 MRC 错误符号上，真实目标 bin 的 $$\eta$$ 中位数为 $$0.0008$$，而 MRC 最高错误 bin 的 $$\eta$$ 中位数为 $$0.222$$，约为前者的 $$279$$ 倍。因此，目标正交方向并非只在个别碰撞中偶然有用，而是在真实接收波形中形成稳定的空间反证。
[图片]
图 4：真实目标 bin 与 MRC 错误 bin 的空间不一致度分布
上述观察形成了关键设计要求：接收器应在最终符号排序中同时保留目标方向支持和目标正交方向反证，而不能在 FFT 判决前将双天线观测压缩为单一非负功率谱。基于这些观察，第 3 章给出 SP-Decode 的端到端系统架构。第 4 章介绍目标条件化的有符号空间判决及其可行性条件，第 5 章介绍并发包获取、双射频链校准、鲁棒信道估计和可靠性约束。
3 SP-Decode 接收系统概览
SP-Decode 的目标是在不修改 LoRa 发送端、不依赖串行干扰消除的条件下，从双天线并发接收信号中直接恢复每个已检测包的 payload 符号。系统输入为双通道复基带观测 $$\mathbf y[n]\in\mathbb C^2$$，输出为每个目标包的符号序列 $$\{\hat s_{u,\ell}\}_{\ell}$$。与传统接收机先将双天线观测合成为一路非负功率谱不同，SP-Decode 在最终 FFT 判决域保留两类证据：目标方向支持和目标正交方向反证。
整个接收流程包含两个相互衔接的部分。第一部分是并发包获取与可靠性估计。接收机从原始天线流和 PCA 投影流中检测重复 preamble 轨道，利用 sync word 与 SFD 的帧结构约束精修连续包起点和 CFO，并从前导符号中鲁棒估计每个包的双天线信道。该前端不直接决定 payload 符号，而是为后端提供一组估计参数：
$$\mathcal P_u
=
\left\{
\hat t_u,
\hat\epsilon_u,
\hat{\mathbf h}_u
\right\}.$$
其中 $$\hat t_u$$ 和 $$\hat\epsilon_u$$ 分别表示目标包的连续起点和 CFO；$$\hat{\mathbf h}_u$$ 表示双天线信道。
第二部分是目标条件化的有符号空间判决。对于目标包 $$u$$ 的每个 payload 符号，接收机首先按照 $$\hat t_u$$ 读取符号窗口，并使用 $$\hat\epsilon_u$$ 补偿 CFO；随后在两根天线上分别执行 LoRa dechirp 和 $$M$$ 点 FFT，得到双天线频域向量 $$\mathbf Y_{u,\ell}[k]$$。依据目标信道方向 $$\hat{\mathbf a}_u$$ 及其正交方向 $$\hat{\mathbf b}_u$$，接收机计算
$$P_{u,\ell}[k]
=
\hat{\mathbf a}_u^H
\mathbf Y_{u,\ell}[k],
\qquad
Q_{u,\ell}[k]
=
\hat{\mathbf b}_u^H
\mathbf Y_{u,\ell}[k].$$
$$P$$ 分支衡量该 bin 对目标方向的支持，$$Q$$ 分支衡量该 bin 与目标空间方向的矛盾。SP-Decode 计算包级反证权重 $$\lambda_u$$ 并构造有符号谱
$$D_{u,\ell}[k]
=
|P_{u,\ell}[k]|^2
-
\lambda_u|Q_{u,\ell}[k]|^2,$$
并直接选择最大值作为目标符号。这样，payload 判决阶段只需对每个符号执行一次双通道 LoRa FFT、两次二维投影和逐 bin 实数打分。
这种架构将“包级参数估计”和“符号级空间判决”解耦。前端负责提供足够可靠的同步和信道信息；后端负责在每个符号的实际碰撞频谱中执行目标条件化 Top-1 判决。因此，SP-Decode 不需要知道干扰包当前符号，也不需要重构或消除干扰波形。只要错误峰在目标正交方向上呈现足够反证，SP-Decode 就可以在最终排序中压低该错误峰；若目标与干扰信道近共线或多个干扰相干叠加形成目标方向，系统则通过可靠性约束标识其能力边界。
图 5 概括了 SP-Decode 的端到端接收链路。第 4 章从给定 $$\mathcal P_u$$ 的条件出发，分析有符号空间判决的 Top-1 条件、near-far 容忍度、多干扰聚合边界以及噪声风险约束；第 5 章进一步说明如何从真实并发 LoRa 接收信号中获得 $$\mathcal P_u$$。
图5：SP-Decode 的端到端接收链路。
4 符号投影解啁啾与有符号空间判决
本章介绍 SP-Decode 的核心判决机制。考虑已由第 5 章前端检测到的目标包 $$u$$，并提供包起始位置、CFO、STO、双天线信道。SP-Decode 的核心是改变发生在接收端解啁啾后的双天线 FFT 判决域：接收机同时保留目标信道方向上的支持证据和目标正交方向上的反证，最终符号直接由
$$\boxed{
\hat s_{u,\ell}
=
\arg\max_k
D_{u,\ell}[k]
}$$
给出。
4.1 二次型与空间一致性解释
定义 Hermitian 判决矩阵
$$\mathbf W_u(\lambda_u)
=
\hat{\mathbf a}_u\hat{\mathbf a}_u^H
-
\lambda_u
\hat{\mathbf b}_u\hat{\mathbf b}_u^H.$$
则
$$D_{u,\ell}[k]
=
\mathbf Y_{u,\ell}^H[k]
\mathbf W_u(\lambda_u)
\mathbf Y_{u,\ell}[k].$$
矩阵 $$\mathbf W_u$$ 在目标方向上的特征值为 $$1$$，在目标正交方向上的特征值为 $$-\lambda_u$$。因此，$$D_{u,\ell}[k]$$ 不是非负功率，而是一个不定二次型：目标方向能量被保留，正交方向能量被赋予负极性。
为了获得可调控的有界阈值，定义
$$t_u
=
\frac{\lambda_u}{1+\lambda_u},
\qquad
0\leq t_u<1.$$
由于 $$\lambda_u$$ 是与 FFT bin 无关的包级正的常数，最终符号判决等价于最大化
$$S_{u,\ell}[k]
=
\frac{
D_{u,\ell}[k]
}{
1+\lambda_u
}.$$
利用
$$\|\mathbf Y_{u,\ell}[k]\|^2
=
|P_{u,\ell}[k]|^2
+
|Q_{u,\ell}[k]|^2,$$
可得
$$S_{u,\ell}[k]
=
|P_{u,\ell}[k]|^2
-
t_u
\|\mathbf Y_{u,\ell}[k]\|^2.$$
定义总能量
$$E_{u,\ell}[k]
=
\|\mathbf Y_{u,\ell}[k]\|^2$$
和目标空间一致性
$$\xi_{u,\ell}[k]
=
\frac{
|\hat{\mathbf a}_u^H\mathbf Y_{u,\ell}[k]|^2
}{
\|\mathbf Y_{u,\ell}[k]\|^2
},$$
则
$$\boxed{
S_{u,\ell}[k]
=
E_{u,\ell}[k]
\left(
\xi_{u,\ell}[k]-t_u
\right).
}$$
因此，$$t_u$$ 可以解释为目标空间一致性阈值。一个 FFT bin 只有在其空间一致性高于 $$t_u$$ 时，才获得正的归一化分数；否则，其能量越强，负惩罚越大。
传统 MRC 的 score 为
$$M_{u,\ell}[k]
=
E_{u,\ell}[k]\xi_{u,\ell}[k].$$
MRC 只衡量目标方向上的支持能量，而不判断该 bin 的总能量中有多少与目标空间方向矛盾。等价地，SP-Decode 保留目标方向投影项，并显式引入总能量约束项 $$t_uE_{u,\ell}[k]$$，从而将空间一致性写入最终符号排序。
在一个对角复高斯判决模型下，若目标 bin 具有更高的目标方向方差和更低的正交方向方差，而非目标 bin 具有相反统计特征，则目标与非目标假设之间的对数似然比可以写为
$$c_P|P[k]|^2-c_Q|Q[k]|^2+C,$$
其中 $$c_P,c_Q>0$$。忽略与 bin 无关的常数并进行正比例归一化后，即得到 SP-Decode 的有符号二次型。因此，SP-Decode 也可以视为目标方向支持和正交方向反证之间的二次判别统计量，而不是经验性的峰值相减。
4.2 精确的 Top-1 margin 条件
设目标包当前真实符号为 $$s=s_{u,\ell}$$。定义目标 bin 与错误 bin $$k$$ 之间的判决 margin：
$$\Delta_{u,\ell,k}(\lambda_u)
=
D_{u,\ell}[s]
-
D_{u,\ell}[k].$$
将其展开得到
$$\Delta_{u,\ell,k}(\lambda_u)
=
A_{u,\ell,k}
+
\lambda_uB_{u,\ell,k},$$
其中
$$A_{u,\ell,k}
=
|P_{u,\ell}[s]|^2
-
|P_{u,\ell}[k]|^2$$
是传统 MRC margin，而
$$B_{u,\ell,k}
=
|Q_{u,\ell}[k]|^2
-
|Q_{u,\ell}[s]|^2$$
表示错误 bin 相对于正确 bin 的正交反证优势。
定理 1：精确的竞争 bin 修复条件。
对于任意错误 bin $$k$$，SP-Decode 将目标 bin 排在该错误 bin 之前，当且仅当
$$A_{u,\ell,k}
+
\lambda_uB_{u,\ell,k}
>0.$$
若 MRC 判决错误，即 $$A_{u,\ell,k}<0$$，但错误 bin 具有更强的正交反证，即 $$B_{u,\ell,k}>0$$，则 SP-Decode 修复该错误的充分必要条件为
$$\lambda_u
>
\frac{
-A_{u,\ell,k}
}{
B_{u,\ell,k}
}.$$
该条件不要求错误 bin 的最终有符号得分为负。只要反证项足以翻转正确 bin 与错误 bin 的相对次序，SP-Decode 即可恢复正确 Top-1。
为了同时超过所有错误 bins，$$\lambda_u$$ 必须满足
$$A_{u,\ell,k}
+
\lambda_uB_{u,\ell,k}
>0,
\qquad
\forall k\neq s.$$
对应的精确可行区间为
$$\begin{aligned}
\lambda_{u,\ell}^{\mathrm{low}}
&=
\max_{k:B_{u,\ell,k}>0}
\left[
-\frac{
A_{u,\ell,k}
}{
B_{u,\ell,k}
}
\right]_+,\\
\lambda_{u,\ell}^{\mathrm{high}}
&=
\min_{k:B_{u,\ell,k}<0}
\frac{
A_{u,\ell,k}
}{
-B_{u,\ell,k}
}.
\end{aligned}$$
若某个 $$B_{u,\ell,k}=0$$，则必须有 $$A_{u,\ell,k}>0$$。当
$$\lambda_{u,\ell}^{\mathrm{low}}
<
\lambda_{u,\ell}^{\mathrm{high}},$$
存在一个反证权重使目标 bin 成为全局 Top-1。
该定理直接作用于碰撞后的实际 FFT 向量，因此所有多用户相干叠加和交叉项均已包含在 $$P$$ 和 $$Q$$ 中，不需要假设不同干扰之间相互独立。
4.3 单源空间模型及 near-far 容忍度
为了建立信道几何与 Top-1 margin 的关系，考虑一个目标 bin 主要由目标包 $$u$$ 贡献，而一个错误 bin 主要由干扰包 $$v$$ 贡献的情况。
定义真实目标方向相对于估计方向的可靠性
$$r_u
=
\frac{
|\hat{\mathbf a}_u^H\mathbf h_u|^2
}{
\|\mathbf h_u\|^2
},$$
以及目标估计方向与干扰信道之间的相干度
$$\rho_{uv}
=
\frac{
|\hat{\mathbf a}_u^H\mathbf h_v|^2
}{
\|\mathbf h_v\|^2
}.$$
设目标和干扰在对应 FFT bin 中的总能量分别为 $$E_u$$ 和 $$E_v$$，则
$$\begin{aligned}
D_u[s]
&=
E_u
\left[
r_u-\lambda_u(1-r_u)
\right],\\
D_u[k]
&=
E_v
\left[
\rho_{uv}
-
\lambda_u(1-\rho_{uv})
\right].
\end{aligned}$$
目标—干扰 margin 为
$$\Delta_{uv}(\lambda_u)
=
A_{uv}
+
\lambda_uB_{uv},$$
其中
$$\begin{aligned}
A_{uv}
&=
E_ur_u-E_v\rho_{uv},\\
B_{uv}
&=
E_v(1-\rho_{uv})
-
E_u(1-r_u).
\end{aligned}$$
$$A_{uv}$$ 是 MRC margin。若 $$A_{uv}<0$$，MRC 将选择干扰峰。
$$B_{uv}$$ 是正交反证优势。只有在
$$B_{uv}>0$$
时，提高 $$\lambda_u$$ 才会改善该目标—干扰对的判决 margin。
当 $$A_{uv}<0$$ 且 $$B_{uv}>0$$ 时，SP-Decode 修复该 MRC 错误所需的最小权重为
$$\boxed{
\lambda_{uv}^{\mathrm{flip}}
=
\frac{
E_v\rho_{uv}-E_ur_u
}{
E_v(1-\rho_{uv})
-
E_u(1-r_u)
}.
}$$
该修复阈值通常小于将干扰 score 完全变成负值所需的
$$\lambda_{uv}^{\mathrm{negative}}
=
\frac{
\rho_{uv}
}{
1-\rho_{uv}
}.$$
因此，SP-Decode 的有效工作区间不仅包括干扰完全负化区域，也包括更广泛的软反证区域。
若干扰 score 仍为正，即
$$\rho_{uv}
-
\lambda_u(1-\rho_{uv})
>0,$$
则无噪声下的 near-far 解码条件为
$$\frac{E_v}{E_u}
<
\frac{
r_u-\lambda_u(1-r_u)
}{
\rho_{uv}
-
\lambda_u(1-\rho_{uv})
}.$$
相比 MRC 的条件
$$\frac{E_v}{E_u}
<
\frac{r_u}{\rho_{uv}},$$
只要 $$r_u>\rho_{uv}$$ 且 $$\lambda_u>0$$，SP-Decode 可以提高可容忍的干扰功率。
当
$$\lambda_u
>
\frac{
\rho_{uv}
}{
1-\rho_{uv}
},$$
干扰 score 变为负值。在无噪声且目标 score 为正的单源模型中，此时干扰功率不再构成 top-1 上界。
与此同时，目标 score 保持正值要求
$$\lambda_u
<
\frac{
r_u
}{
1-r_u
}.$$
因此，完整的单源极性分离区间为
$$\frac{
\rho_{uv}
}{
1-\rho_{uv}
}
<
\lambda_u
<
\frac{
r_u
}{
1-r_u
},$$
其存在的充要条件为
$$\rho_{uv}<r_u.$$
当 $$\rho_{uv}\rightarrow1$$ 时，干扰正交能量趋近于零，所需 $$\lambda_u$$ 趋于无穷大。若目标与干扰的双天线信道严格共线，则任何仅依赖二维空间方向的有符号空间判决器都无法改变两者的相对空间分数。
4.4 多干扰下的聚合一致性
单源相干度 $$\rho_{uv}$$ 便于解释空间几何，但真实错误 bin 可能同时包含多个干扰包。令去噪后的聚合 FFT 向量为
$$\boldsymbol\mu_{u,\ell}[k]
=
\sum_v
\mathbf h_vA_{uv,\ell}[k].$$
定义聚合能量和聚合空间一致性
$$\begin{aligned}
E_{u,\ell}^{(0)}[k]
&=
\|\boldsymbol\mu_{u,\ell}[k]\|^2,\\
\xi_{u,\ell}^{(0)}[k]
&=
\frac{
|\hat{\mathbf a}_u^H
\boldsymbol\mu_{u,\ell}[k]|^2
}{
\|\boldsymbol\mu_{u,\ell}[k]\|^2
}.
\end{aligned}$$
则归一化有符号得分精确为
$$S_{u,\ell}^{(0)}[k]
=
E_{u,\ell}^{(0)}[k]
\left[
\xi_{u,\ell}^{(0)}[k]-t_u
\right].$$
定理 2：聚合 bin 极性条件。
若目标 bin 满足
$$\xi_{u,\ell}^{(0)}[s]>t_u$$
且所有错误 bins 满足
$$\xi_{u,\ell}^{(0)}[k]<t_u,
\qquad
k\neq s,$$
则
$$D_{u,\ell}[s]>0>D_{u,\ell}[k],
\qquad
\forall k\neq s,$$
因此 $$\hat s_{u,\ell}=s$$，且该结论与各错误 bin 的绝对能量无关。
该结果完整包含了多干扰交叉项，但也揭示了 SP-Decode 的另一项边界：两个或多个干扰信道向量的相干组合可能恰好朝向目标信道，使错误 bin 的聚合一致性高于任一单独干扰的相干度。因此，包间两两相干度只能用于包级参数初始化，不能单独构成多干扰场景的确定性保证。
4.5 信道不确定性与可靠极性区间
前端输出目标信道方向 $$\hat{\mathbf a}_u$$ 以及角度不确定性 $$\theta_u$$。定义复信道方向之间的主角距离
$$\theta(\mathbf x,\mathbf y)
=
\arccos
\frac{
|\mathbf x^H\mathbf y|
}{
\|\mathbf x\|\|\mathbf y\|
}.$$
若真实目标方向位于以 $$\hat{\mathbf a}_u$$ 为中心、半径为 $$\theta_u$$ 的置信锥内，则目标可靠性满足
$$r_u
\geq
L_u
=
\cos^2\theta_u.$$
对已检测干扰包 $$v$$，设其估计方向为 $$\hat{\mathbf a}_v$$，角度不确定性为 $$\theta_v$$。定义估计方向间夹角
$$\hat\theta_{uv}
=
\arccos
|\hat{\mathbf a}_u^H\hat{\mathbf a}_v|.$$
根据主角距离的三角关系，干扰真实方向相对于目标检测方向的相干度满足上界
$$\rho_{uv}
\leq
U_{uv}
=
\cos^2
\left(
[\hat\theta_{uv}-\theta_v]_+
\right),$$
其中 $$[x]_+=\max(x,0)$$。
令
$$U_u
=
\max_{v\neq u}U_{uv}.$$
若
$$U_u<L_u,$$
则存在可靠极性区间
$$U_u<t_u<L_u.$$
在只考虑方向不确定性的 max-min 准则下，最优闭式阈值为
$$\boxed{
t_u^{\mathrm{mid}}
=
\frac{
L_u+U_u
}{2},
}$$
对应
$$\boxed{
\lambda_u^{\mathrm{mid}}
=
\frac{
L_u+U_u
}{
2-L_u-U_u
}.
}$$
该阈值使目标方向的最小正 margin
$$L_u-t_u$$
与干扰方向的最小负 margin
$$t_u-U_u$$
相等，最大化二者中的较小值。
若 $$U_u\geq L_u$$，则基于当前信道估计无法给出目标为正且所有干扰为负的可靠保证。SP-Decode 仍可通过软反证改善 Top-1 排序，但此时应将该包标记为不满足可靠分离条件，而不能声称满足极性分离定理。
4.6 噪声影响与风险约束的反证权重
考虑一个无噪声 FFT bin $$\boldsymbol\mu$$ 和白噪声
$$\mathbf n
\sim
\mathcal{CN}
\left(
\mathbf0,\sigma^2\mathbf I_2
\right).$$
令
$$\begin{aligned}
E&=\|\boldsymbol\mu\|^2,\\
c&=
\frac{
|\hat{\mathbf a}_u^H\boldsymbol\mu|^2
}{E}.
\end{aligned}$$
则有符号得分的均值为
$$\mathbb E[D]
=
E
\left[
c-\lambda_u(1-c)
\right]
+
(1-\lambda_u)\sigma^2,$$
方差为
$$\operatorname{Var}[D]
=
\sigma^4(1+\lambda_u^2)
+
2\sigma^2E
\left[
c+\lambda_u^2(1-c)
\right].$$
噪声均值项对所有 FFT bins 相同，不改变平均 ranking；但方差随 $$\lambda_u$$ 增大，表明强反证权重会提高随机错误峰的波动。
对一个目标 bin 和一个竞争 bin，定义
$$\begin{aligned}
A
&=
E_ur_u-E_v\rho_{uv},\\
B
&=
E_v(1-\rho_{uv})
-
E_u(1-r_u).
\end{aligned}$$
其 signed margin 的均值和方差分别为
$$\begin{aligned}
\mathbb E[\Delta]
&=
A+B\lambda_u,\\
\operatorname{Var}[\Delta]
&=
C_0+C_2\lambda_u^2,
\end{aligned}$$
其中
$$\begin{aligned}
C_0
&=
2\sigma^4
+
2\sigma^2
\left(
E_ur_u+E_v\rho_{uv}
\right),\\
C_2
&=
2\sigma^4
+
2\sigma^2
\left[
E_u(1-r_u)
+
E_v(1-\rho_{uv})
\right].
\end{aligned}$$
定义标准化 margin
$$J_{uv}(\lambda_u)
=
\frac{
A+B\lambda_u
}{
\sqrt{
C_0+C_2\lambda_u^2
}
}.$$
当 $$A>0$$ 且 $$B>0$$ 时，单竞争 bin 模型下的驻点为
$$\lambda_{uv}^{\mathrm{peak}}
=
\frac{
BC_0
}{
AC_2
}.$$
当 $$A\leq0$$ 且 $$B>0$$ 时，增大 $$\lambda_u$$ 可以修复 MRC margin，但最终权重必须受目标信道可靠性和噪声约束限制。当 $$B\leq0$$ 时，提高正交惩罚不会改善该竞争 bin。
系统针对目标包 $$u$$ 使用前端估计的功率、信道置信区间和噪声方差，构造保守的 margin 参数
$$\begin{aligned}
\underline A_{uv}
&=
\hat E_uL_u-\hat E_vU_{uv},\\
\underline B_{uv}
&=
\hat E_v(1-U_{uv})
-
\hat E_u(1-L_u).
\end{aligned}$$
反证权重通过以下一维 max-min 问题确定：
$$\boxed{
\lambda_u^\star
=
\arg\max_{
0\leq\lambda\leq\lambda_{u,\mathrm{cap}}
}
\min_{v\neq u}
\frac{
\underline A_{uv}
+
\lambda\underline B_{uv}
}{
\sqrt{
\overline C_{0,uv}
+
\lambda^2\overline C_{2,uv}
}
}.
}$$
$$\lambda_{u,\mathrm{cap}}$$ 由目标可靠性和最低目标 margin 决定。若要求目标单源系数至少为 $$\gamma_u>0$$，则
$$L_u-\lambda_{u,\mathrm{cap}}(1-L_u)
\geq\gamma_u,$$
即
$$\lambda_{u,\mathrm{cap}}
\leq
\frac{
L_u-\gamma_u
}{
1-L_u
}.$$
该优化仅在每个检测包建立时执行一次，是一个有界一维问题，实际实现可以在区间边界、各目标—干扰对的 $$\lambda^{\mathrm{flip}}$$、$$\lambda^{\mathrm{peak}}$$ 及少量固定检查点上求值。
5 并发数据包获取与可靠性估计
并发 LoRa 前端需要同时满足召回率和参数精度两类要求。PCube 表明，多天线空口相位可以为 LoRa 并发解码提供额外维度，但 CFO、STO、射频硬件相位及碰撞污染会直接破坏相位测量 [R1]。MaLoRaGW 进一步指出，弱包检测需要空间投影，而空间投影又依赖同步与信道估计，从而形成检测、同步和信道估计之间的循环依赖；其使用 PCA 作为不依赖用户 CSI 的初始空间投影 [R2]。上述观察说明，并发前端必须同时解决弱包可见性、帧结构一致性和信道方向可靠性，才能为 SP-Decode 提供稳定的包级空间参考。
本文采用两阶段前端：先用全局原始流和 PCA 流上的 separated preamble 轨道生成高召回粗候选，再通过帧结构一致性约束接受 start、CFO 与 STO 精修结果。
5.1 校准与预白化
双天线原始观测写为
$$\mathbf y_{\mathrm{raw}}[n]
=
\mathbf C
\sum_v
\mathbf h_vx_v[n]
+
\mathbf n_{\mathrm{raw}}[n],$$
其中
$$\mathbf C
=
\begin{bmatrix}
c_1&0\\
0&c_2
\end{bmatrix}$$
表示两条射频链的固定复增益和相位响应差异。接收机首先补偿射频链响应并去除直流分量：
$$\tilde{\mathbf y}[n]
=
\hat{\mathbf C}^{-1}\mathbf y_{\mathrm{raw}}[n]
-
\frac{1}{N}\sum_{m=0}^{N-1}
\hat{\mathbf C}^{-1}\mathbf y_{\mathrm{raw}}[m].$$
随后在不含有效 LoRa 包的背景采样集合 $$\mathcal N_0$$ 上估计噪声协方差
$$\hat{\mathbf R}_n
=
\frac{1}{|\mathcal N_0|}
\sum_{n\in\mathcal N_0}
\tilde{\mathbf y}[n]\tilde{\mathbf y}^{H}[n],$$
并得到预白化观测
$$\bar{\mathbf y}[n]
=
\hat{\mathbf R}_n^{-1/2}\tilde{\mathbf y}[n].$$
第 4 章中的信道相干度、正交方向和有符号二次型均在预白化空间中定义，避免某一接收链的噪声或增益不平衡被误解释为目标正交方向能量。
5.2 多流前导获取
LoRa preamble 由重复 upchirps 构成。对正确的 symbol 对齐窗口，乘以 downchirp 后，同一包的多个 preamble symbols 会在 FFT 中形成稳定的 bin 轨道。为提高弱包可见性，接收机构造检测投影集合
$$\mathcal V_{\mathrm{det}}
=
\left\{
\mathbf e_1,
\mathbf e_2,
\mathbf q_1,
\mathbf q_2
\right\},$$
其中 $$\mathbf e_1,\mathbf e_2$$ 为原始双天线分支，$$\mathbf q_1,\mathbf q_2$$ 为观测协方差
$$\hat{\mathbf R}_y
=
\frac{1}{N}
\sum_{n=0}^{N-1}
\bar{\mathbf y}[n]\bar{\mathbf y}^{H}[n]$$
的两个单位特征向量。每个投影产生一个标量检测流
$$z_{\mathbf v}[n]
=
\mathbf v^H\bar{\mathbf y}[n],
\qquad
\mathbf v\in\mathcal V_{\mathrm{det}}.$$
对每个滑动窗口和每个检测流，接收机执行 LoRa dechirp FFT：
$$Z_{r,p}[k]
=
\operatorname{FFT}_M
\left(
z_r[n]d^*[n]
\right),$$
其中 $$d[n]$$ 为标准 upchirp，$$M=2^{\mathrm{SF}}$$。过采样信号使用与 LoRa 解调一致的 $$M$$ 点 FFT 分支，而不是对 OSR 个采样进行简单求和。
令
$$\eta_{r,p}[k]
=
\frac{|Z_{r,p}[k]|^2}
{\operatorname{median}_{j}|Z_{r,p}[j]|^2+\varepsilon}$$
表示局部峰值强度。若同一 bin 在多个投影流和多个 preamble 窗口中重复出现，则形成一个前导轨道。定义 hit 集合
$$\mathcal H_k
=
\left\{(r,p):
k\in\operatorname{TopK}(|Z_{r,p}[\cdot]|^2)
\right\}.$$
前导轨道得分为
$$\Gamma_{\mathrm{trk}}(k)
=
\operatorname{median}
\left(
\{\eta_{r,p}[k]\}_{(r,p)\in\mathcal H_k}
\right)
\cdot
\sqrt{|\mathcal H_k|}
\cdot
\frac{|\mathcal H_k|}{|\mathcal V_{\mathrm{det}}|N_{\mathrm{pre}}}.$$
该得分同时鼓励高峰值、跨 symbol 重复性和跨空间投影一致性。随后，接收机对频域近邻轨道和时间近邻轨道执行非极大值抑制，得到粗候选集合
$$\mathcal C
=
\left\{
(\hat n_u^{(0)},\hat\epsilon_u^{(0)},\Gamma_u^{\mathrm{trk}})
\right\}_u.$$
5.3 帧结构验证
仅有重复 FFT 峰不足以确认完整 LoRa 帧。对每个粗候选，接收机根据 $$\hat n_u^{(0)}$$ 和 $$\hat\epsilon_u^{(0)}$$ 预测 preamble、sync word、SFD 和 payload 起点，并计算结构一致性得分。
sync word 得分由两个 sync symbols 的局部峰值稳定性给出。设 $$\mathbf Y_{u,i}^{\mathrm{sync}}[k]\in\mathbb C^2$$ 为第 $$i$$ 个 sync symbol 在双天线上的 FFT 向量，$$\mathcal B_{\mathrm{sync},i}$$ 为由 sync word 和当前 CFO 预测得到的局部 bin 集合，则
$$\Gamma_u^{\mathrm{sync}}
=
\operatorname{median}_{i=1,2}
\frac{
\max_{k\in\mathcal B_{\mathrm{sync},i}}
\|\mathbf Y_{u,i}^{\mathrm{sync}}[k]\|^2
}{
\operatorname{median}_{j}
\|\mathbf Y_{u,i}^{\mathrm{sync}}[j]\|^2+\varepsilon
}.$$
SFD 得分以相同方式在两个 SFD downchirps 上计算。令 $$\mathbf Y_{u,i}^{\mathrm{SFD}}[k]$$ 表示 SFD 窗口乘以标准 upchirp 后的双天线 FFT 向量，$$\mathcal B_{\mathrm{SFD}}$$ 为 CFO 预测的局部 bin 集合，则
$$\Gamma_u^{\mathrm{SFD}}
=
\operatorname{median}_{i=1,2}
\frac{
\max_{k\in\mathcal B_{\mathrm{SFD}}}
\|\mathbf Y_{u,i}^{\mathrm{SFD}}[k]\|^2
}{
\operatorname{median}_{j}
\|\mathbf Y_{u,i}^{\mathrm{SFD}}[j]\|^2+\varepsilon
}.$$
综合候选置信度写为
$$\Gamma_u^{\mathrm{cand}}
=
\Gamma_u^{\mathrm{trk}}
\sqrt{\max(\Gamma_u^{\mathrm{sync}},1)}
\sqrt{\max(\Gamma_u^{\mathrm{SFD}},1)}
\sqrt{N_{\mathrm{hit},u}}.$$
由于并发碰撞会污染 sync 和 SFD，结构得分不作为唯一硬门限，而作为候选排序和后续同步精修的约束项。该设计保留弱包召回，同时抑制由 payload 峰或短时拍频造成的伪轨道。
5.4 连续起点与 CFO 精修
LoRa dechirp FFT 中，start 偏差和 CFO 都会造成峰值 bin 偏移，近似满足
$$\Delta k
\approx
\frac{\Delta n}{\mathrm{OSR}}.$$
因此，同步精修必须避免在 start/CFO 斜脊上无约束漂移。系统采用受约束的多阶段精修，并最终以连续包起点 $$\hat t_u$$ 表示整数 start 与分数采样偏移。
首先，在粗 CFO 固定的条件下搜索 start，并使用 preamble、sync word 与 SFD 的联合结构得分作为目标：
$$\hat n_u^{\mathrm{fix}}
=
\arg\max_n
\Gamma^{\mathrm{frame}}(n,\hat\epsilon_u^{(0)}).$$
对于具有足够跨流 hit 数和较高轨道置信度的包，接收机进一步在局部窗口内重新评估 separated preamble 轨道，得到候选精修结果
$$(\hat n_u^{\mathrm{ref}},\hat\epsilon_u^{\mathrm{ref}}).$$
该更新必须满足一致性约束
$$|\hat\epsilon_u^{\mathrm{ref}}-\hat\epsilon_u^{(0)}|
\leq
\Delta_{\epsilon}^{\mathrm{ref}},$$
并且精修起点的帧结构得分不低于固定 CFO 结果。若该条件不满足，则保留粗候选。
接着利用 preamble upchirp 和 SFD downchirp 的峰值关系估计 CFO 与时间偏移的耦合量。理想情况下，二者满足
$$\begin{aligned}
s_{\mathrm{up},u}
&=
(L_{\mathrm{CFO},u}+L_{\mathrm{STO},u})\bmod M,\\
s_{\mathrm{down},u}
&=
(L_{\mathrm{CFO},u}-L_{\mathrm{STO},u})\bmod M.
\end{aligned}$$
因此
$$\begin{aligned}
\hat L_{\mathrm{CFO},u}
&=
\frac{1}{2}
\Gamma_M[(s_{\mathrm{up},u}+s_{\mathrm{down},u})\bmod M],\\
\hat L_{\mathrm{STO},u}
&=
(s_{\mathrm{up},u}-\hat L_{\mathrm{CFO},u})\bmod M.
\end{aligned}$$
上述关系用于给出 SFD-anchor 的连续起点修正。最后，在小范围分数采样网格中估计残余分数偏移，并由跨 preamble 相干性估计分数 CFO。最终同步参数写为
$$\hat\epsilon_u
=
\hat L_{\mathrm{CFO},u}+\hat\lambda_{\mathrm{CFO},u},
\qquad
\hat t_u
=
\hat n_u+\hat\delta_u,$$
其中 $$\hat\delta_u$$ 为最终保留的分数采样偏移。payload 窗口以 $$\hat t_u$$ 读取，并使用连续 CFO $$\hat\epsilon_u$$ 补偿，以减少邻频扩散对目标方向谱和正交方向谱的影响。
5.5 鲁棒双天线信道估计
完成同步后，每个可用 preamble symbol 在目标 bin 附近提供一个双天线信道 snapshot。对第 $$p$$ 个 snapshot，接收机从连续起点 $$\hat t_u$$ 对齐的窗口中计算
$$\mathbf z_{u,p}
=
e^{-j2\pi\hat\epsilon_{u}^{\mathrm{frac}}p}
\sum_{q=-Q}^{Q}
c_q
\mathbf Y_{u,p}[\hat k_u+q],$$
其中 $$\hat k_u=\operatorname{round}(\hat\epsilon_u)\bmod M$$ 为前导主峰所在整数 bin，$$\hat\epsilon_{u}^{\mathrm{frac}}=\hat\epsilon_u-\operatorname{signed}(\hat k_u)$$ 为跨 preamble symbols 的残余分数 CFO，$$c_q$$ 为局部谱泄漏补偿权重。由于部分 preamble snapshots 可能被其他包污染，直接平均会偏向干扰方向。本文首先计算频谱隔离度
$$\iota_{u,p}
=
\frac{
\sum_{q=-Q}^{Q}\|\mathbf Y_{u,p}[\hat k_u+q]\|^2
}{
\sum_{k=0}^{M-1}\|\mathbf Y_{u,p}[k]\|^2+\varepsilon
}.$$
然后用隔离度和方向残差构造鲁棒权重
$$w_{u,p}
=
w_{\mathrm{iso}}(\iota_{u,p})
\cdot
\exp
\left[-
\left(
\frac{\theta(\mathbf z_{u,p},\tilde{\mathbf h}_u)}{\theta_0}
\right)^2
\right],$$
其中 $$\tilde{\mathbf h}_u$$ 为初始加权均值。最终信道估计为
$$\boxed{
\hat{\mathbf h}_u
=
\frac{
\sum_p w_{u,p}\mathbf z_{u,p}
}{
\sum_p w_{u,p}
}.
}$$


