# SP-Decoder 逐图实验说明与结果分析

本文档给出可直接插入 `SP-Decode v2.md` 的中文正文段落。每段依次交代图的证明目标、数据来源、样本选择规则、主要结果及其对 SP-Decoder 设计的启示。为避免选择性汇报，文中严格区分三类图：全部样本统计、受控仿真统计和仅用于解释机制的特选案例。

## 共用实测数据来源

图 2–8 的机制实验实测波形来自 `real_usrp_outputs/clean_pos_packets.npz`。该数据集由 USRP B210 的两个同步接收通道采集，从 `pos01` 至 `pos10` 的单包记录中提取出 26 个完整 LoRa 包；PHY 参数为 SF10、125 kHz 带宽、1 MHz 采样率、CR 4/5、8 个前导码 chirp 和 CRC。后续 trace-driven 实验不重新生成理想波形，而是直接缩放、平移并叠加这些双通道复基带样本，因此保留了实测 CFO、双天线幅相差、射频失真和底噪。图 2–8 关注 SP 的归一化空间投影方向，其方向误差采用不受公共复相位影响的射影角

$$
d(\mathbf h_1,\mathbf h_2)
=
\arccos
\frac{|\mathbf h_1^H\mathbf h_2|}
{\|\mathbf h_1\|\,\|\mathbf h_2\|}.
$$

第 6.2 节的室内空气信道测量改用真实 500 kS/s 单节点采集 `run_02000001`，因为该 run 的实测帧长度与论文配置一致，确为 45.25 symbols。三个子图统一展示 degree 方向偏差，并将射影角的绝对值按相对相位所在侧赋予正负号。这样既保留原方向误差的物理大小，也能显示估计围绕参考方向的正负偏置。

## 图 1：SP-Decoder 系统概览

图 1 展示 SP-Decoder 的端到端设计逻辑，而不是一项独立实验：分离优先的前端首先输出目标包的时间、频偏和信道方向假设；SP-Decoder 随后把目标方向上的投影解释为支持证据，把目标正交方向上的投影解释为反证，并为每个包只配置一次反证权重，最后在每个 payload 符号的有符号谱上执行 top-1 判决。图中应把前端画成输入接口，将视觉中心放在“强错误峰虽然具有较大支持能量，却同时暴露出更强的目标正交分量”这一矛盾上。该图不使用实验样本，也不应在图后声称性能增益；它提出的三个可验证命题分别由图 2 的动机观测、图 5–7 的包级权重配置和图 8 的稳健空间统计验证。

## 图 2(a)：一个 MRC 错误符号中的反证如何改变排序

如图 2(a) 所示，我们展示一个由实测双通道波形合成的四干扰碰撞符号。目标取 clean packet 20，四个干扰分别取 packet 0、22、10 和 25，其相对起点为 $0$、$4.4T_s$、$7.25T_s$ 和 $10.6T_s$，对应 SIR 为 $-5$、$-2$、$-3$ 和 $-4$ dB，并在叠加后的波形上加入 24 dB SNR 的复高斯噪声。该案例不是随机抽取：程序先从两包碰撞中找到可由 signed spectrum 修复的 MRC 错误，再使用固定随机种子构造 520 个四干扰组合，仅保留“MRC 判错、signed top-1 恢复真实 bin、错误 bin 的空间不一致度高于真实 bin”的样本，最后依据反证差、修复后 margin 和频谱结构清晰度选择用于机制展示的案例。因此，该图应被表述为解释性 case study，而不是平均性能。该符号的真实 bin 为 537，MRC 将 bin 304 选为最大支持峰；两者的空间不一致度分别为 $1.56\times10^{-4}$ 和 0.862。当 $\lambda=0.05$ 时，错误峰携带的强正交能量被扣除，top-1 回到真实 bin。这个例子说明 MRC 的错误并非总是“目标证据不足”，还可能是“把带有明显空间矛盾的干扰峰误当成目标”；因此，SP-Decoder 需要保留反证，而不能只在正投影能量上继续做峰值增强。

**口径提醒。** 图 2(a) 是有意选择的清晰案例。论文应明确给出选择条件，并由图 2(b) 的全部错误符号分布证明该现象不是单个好看样本造成的。

## 图 2(b)：错误峰是否普遍具有更强反证

如图 2(b) 所示，我们汇总同一实测 clean-packet 库产生的全部两包 trace-driven 碰撞。实验先按照信道相干度 $\rho$ 分层选择 20 个有序目标—干扰包对，再扫描 $0$、$0.1T_s$、$0.25T_s$、$0.5T_s$ 和 $0.9T_s$ 五种相对起点以及 $-5$ 至 0 dB 的六档 SIR；每个包包含 38 个 payload 符号，共得到 22,800 个符号观测。图中不挑选位置或 SIR，而是保留其中全部 5,794 个 MRC 错误符号，并分别计算真实 bin 与 MRC 错误 bin 的

$$
\eta[k]=
\frac{|Q_u[k]|^2}
{|P_u[k]|^2+|Q_u[k]|^2}.
$$

结果显示，真实 bin 的 $\eta$ 中位数仅为 $7.98\times10^{-4}$，错误 bin 的中位数为 0.222，后者约为前者的 279 倍；99.12% 的 MRC 错误符号满足 $\eta_{\rm wrong}>\eta_{\rm target}$。这说明图 2(a) 中“错误峰暴露额外反证”的现象在受控的实测波形碰撞中具有统计普遍性，也给出了 signed spectrum 的直接动机。与此同时，仍有约 0.88% 的错误符号不满足该关系，因此反证不能无限制加权；如何避免误罚真实 bin，正是图 2(c)、图 2(d) 和第 4 节包级可靠性建模需要解决的问题。

## 图 2(c)：为什么反证权重必须按包配置

如图 2(c) 所示，我们先用固定种子构造 240 个两包 trace-driven 候选碰撞，扫描
SIR \(\{-6,-4,-2,0,2\}\) dB、相对起点
\(\{0.25,0.5,1,1.5,2\}T_s\) 和前导频差
\(\{0,1,2,3,4,6\}\) bins，再对每个候选使用扩展权重网格

$$
\lambda\in\{0,0.1,0.25,0.5,0.75,1,1.5,2,2.5,3,4,5,6,8,10,15,20,30,50,75,100\}
$$

执行完整 payload signed top-1。图中左侧绘制完整 SER 曲线，右侧绘制达到最低 SER 的权重区间；\(\lambda>4\) 只作为离线无界压力测试。四个案例的最低区间分别为
\([0.75,1]\)、\([1,4]\)、\(\{1.5\}\) 和 \([3,8]\)，四者交集为空。四条曲线都先下降后回升，且在 \(\lambda=100\) 时均为 SER=1，因此“取一个足够大的固定权重”同时被两类证据排除。

这四个实例是机制案例：程序要求相对 \(\lambda=0\) 至少修复 50 个百分点、最低 SER 不超过 3%、\(\lambda=100\) 至少损伤 75 个百分点，并保证目标和干扰包不重复。选择过程读取了解码结果，因此图 2(c) 不能作为总体性能统计，也不能证明在线算法已经知道 oracle 最优权重；240 个候选的完整曲线和固定权重汇总均保留在 sidecar 中。未筛选总体中，最好的固定全局权重为 \(\lambda=8\)，平均 SER 为 21.8%；逐场景离线最低值平均为 13.5%；固定 \(\lambda=100\) 的平均 SER 则升到 32.0%。它证明的是“包相关且有界的工作区间确实存在”，从而把论文问题自然交给第 4 节：如何仅用前导可靠性、目标—干扰信道几何和功率关系在线预测一个安全的包级 \(\lambda_u\)。

## 图 2(d)：方向估计偏差下是否仍存在可用权重

图 2(d) 检验的是另一个更基本的命题：当前导码信道方向被碰撞拉偏时，候选区间内是否仍存在可用的反证权重。实验将两路实测 PHY 波形错开 $1T_s$，固定 3-bin 前导频差并扫描 $-4$ 至 6 dB 的 SIR，使方向误差覆盖约 $-12.5^\circ$ 至 $+12.5^\circ$。每个碰撞都评估生产区间内的九个权重 $\lambda\in\{0,0.5,1,1.5,2,2.5,3,3.5,4\}$。程序先按 $2.5^\circ$ 方向误差区间构造 72 碰撞均衡池，每个区间最多 8 个；这一统计池选择不读取 SER、FEC 或 CRC。图中保留全部 648 个彩色小圆点，不再使用黑色菱形或任何读取 SER 的高亮子集。

边界统计使用完整的 72 碰撞池。在 $|\Delta\psi|\in[7.5^\circ,12.5^\circ]$ 的 24 个边界实例中，最低 SER 的中位数为 2.6%，80 分位为 15.8%，87.5% 至少存在一个权重使符号成功率达到 80%。最低值仅作为正文离线统计，不在图中单独标记。图 2(c) 证明工作点随包变化，图 2(d) 证明存在估计误差时仍常保留低 SER 工作点；第 4 节随后负责用 $L_u$、$U_{uv}$ 和风险代理把这种离线存在性转化为无真值的在线选择。

## 图 3：SP-Decoder 的处理流程

如图 3 所示，该图给出算法的处理顺序，而不是新的实验结果。前端为每个完整目标包输出 $\widehat\tau_u$、$\widehat\nu_u$、$\widehat{\mathbf h}_u$、噪声和重叠区间；包级配置阶段利用目标不确定性、已检测竞争包集合以及各 pair 的 $R_{uv}(\lambda)$ 构造有限候选集合并选出一次性的 $\widehat\lambda_u$；逐符号阶段只计算支持谱和反证谱，并在 $D_{u,\ell}[k]=|P_{u,\ell}[k]|^2-\widehat\lambda_u|Q_{u,\ell}[k]|^2$ 上执行一次 top-1，随后进入标准 LoRa FEC/CRC。CRC 触发的有界 start/CFO refinement 应画成旁路，并明确 refinement 期间 $\widehat\lambda_u$ 不因 payload 或 CRC 筛选而改变。图 3 的作用是界定系统边界：本文的核心贡献是包级有符号空间判决，而不是把前端检测或 CRC 穷举包装成主要增益来源。

## 图 5：从时间重叠集合到 pair-wise 风险约束

如图 5(a) 所示，11 个实测包构成一个目标加 10 个竞争包的受控异步场景。竞争包起点位于目标前后的 $-7T_s$ 至 $20T_s$，十个区间均与目标 payload 相交，因此 $|\mathcal I_u|=10$。如图 5(b) 所示，十个竞争包分别从 `pos01` 至 `pos10` 各选一个实测包，竞争集合内部不存在重复位置；目标另取 `pos10#0`。受控 SIR 覆盖 $-13.6$ 至 $+14.8$ dB。程序以固定种子检查 500 组包选择和 SIR 排列，只按热力图正负裕量平衡、动态范围和下包络切换复杂度评分，不读取 SER 或 CRC。

右侧热力图的红色表示负 $R_{uv}(\lambda)$，蓝色表示正值，黑白阶梯线标出当前真正决定 $G_u(\lambda)$ 的最坏竞争包。所选案例约 33.3% 的网格为负裕量，5%–95% 分位范围为 $[-26.16,17.30]$，因而能够直观呈现不同位置、功率和空间几何造成的约束差异。该图说明时间重叠只决定哪些包进入 $\mathcal I_u$，而不能用单一聚合干扰功率替代逐 pair 风险；十个约束也不要求枚举 $2^{10}$ 个干扰子集。由于案例按几何对比度选择，它只用于解释风险结构，不用于估计平均解码性能。

## 图 6：更密覆盖如何修复三个固定点后的最后失败包

如图 6 所示，我们从 240 个固定种子的受控碰撞场景中选择 scene 25 的实测空间几何。该配置包含一个目标和两个干扰；SNR 为 28.54 dB。为了构造“已接近完整可靠、但仍存在最后一个失败包”的可解释临界点，程序将两路干扰相对目标同时降低 1.25 dB，使受控 SIR 为 11.84 dB 和 1.81 dB。公共偏移保持实测双通道方向和两路干扰的相对功率关系不变，只控制总体碰撞强度。该场景和 SIR 工作点通过离线搜索得到，因此属于机制案例，不是自然场景分布的随机样本。

$$
J\in\{0,1,2,3,5,7,11,15,31,63\},
$$

单个 payload 的 CRC 结果只有成功或失败，不能直接产生连续 PRR。因此程序固定 scene 25 的双通道方向、干扰集合、受控 SIR 和 SNR，使用固定种子 250025 生成 160 组独立 payload、相位和噪声实现；所有 $J$ 共享逐试验完全相同的随机输入，并针对受控功率重新计算包级 $\lambda$。累计评估 5,280 个 payload 符号。原始统计和完整控制变量分别保存在 `fig6_representative_scene.csv` 与 `fig6_representative_scene_summary.json`。

图 6 改用严格嵌套的 dyadic 网格：$J\in\{0,1,3,7,15,31,63\}$，对应分母 $J+1\in\{1,2,4,8,16,32,64\}$。因此每次增加检查点时，前一级的全部候选均被保留。仅使用端点时为 0.568% SER/95.625% PRR；加入一个中点后为 0.227%/97.500%；三个固定点达到 0.076%/99.375%。$J=7,15,31$ 均保留三个固定点并继续选择 $\lambda=1$，结果保持不变。最终 $J=63$ 新增的细粒度位置使在线目标选择 $\lambda=15/16$，将符号错误数从 4 个降到 3 个；标准 FEC 修复三个错误后，160/160 个包通过 CRC，PRR 达到 100%。嵌套设计消除了“15 是 5 的倍数却不包含 5 点网格”的歧义，也使复杂度增加的含义变成真正的候选集扩张。由于选择准则是 $G_u(\lambda)$ 而非真实 PRR，嵌套性仍不提供一般性的 PRR 单调保证；本图只展示受控临界案例。

### 第六章补充：30,000 个受控碰撞中的候选赢家来源

两张补充柱图以固定种子生成 30,000 个目标加 1--5 个竞争包的受控碰撞；包的方向和可靠性锥从实测包抽取，每一路声明 SIR 在 $[-8,12]$ dB 均匀采样，SNR 在 $[10,30]$ dB 均匀采样。实验只比较 $G_u(\lambda)$，不读取 payload、SER、PRR 或 CRC。第一张图在生产候选并集（端点、pair flip/peak、中点、三个固定内点）上统计最终赢家来源：端点 53.64%，解析 flip/peak 38.64%，中点 0.36%，三个常数点 7.36%。

第二张图保持端点、解析点和中点不变，仅把三个固定内点替换为 10,000 个均匀内点。此时端点、解析 flip/peak 和密集常数点的赢家份额分别为 52.18%、36.03% 和 11.79%；中点为 0%。因此解析 flip/peak 在密集常数网格已经可用时仍直接赢得超过三分之一的碰撞，而不是少量固定检查点的重复。该统计证明的是各类候选的实际覆盖角色；有限集逼近 dense search 的总体误差仍应由图 6 的 objective/weight/PRR 对照承担。

PNG/PDF 与逐类计数分别位于 `candidate_winner_share_three_checkpoints.*`、`candidate_winner_share_10000_checkpoints.*`、`candidate_winner_share_summary.json` 和 `candidate_winner_share.csv`。

## 图 7：有限候选如何覆盖竞争 pair 的切换

图 7 使用一个受控四包碰撞，而不是从性能结果反选自然场景。目标 `pos07#2` 与竞争包 `pos08#0`、`pos02#0`、`pos08#1` 的方向和可靠性锥均来自实测包；三路声明 SIR 为 $0.56$、$6.91$、$-4.97$ dB，SNR 为 $18.85$ dB。构造只约束 pair-margin 几何，不读取 payload、CRC、SER 或 PRR。浅蓝区域为完整安全区间内的下包络，黑色粗线为 $G_u(\lambda)$，灰色虚线为三条竞争 pair 曲线。

在 $[0,4]$ 内，真正主导下包络的竞争包依次是 $v_3\!\to\!v_1\!\to\!v_2$；两次切换位于 $\lambda\approx0.995$ 和 $2.900$，因此分别紧贴 $\lambda=1$ 与 $\lambda=3$ 的固定 coverage 点。图中标出该 pair 身份转换，使蓝色固定点不再只是均匀散布：$\lambda=1$ 和 $3$ 检查切换两侧，$\lambda=2$ 检查中间的 active-pair 峰值区域。橙色三角是 pair flip/peak 点，紫色菱形是可靠极性中点，灰色竖线为区间边界。

最终在线选择是 active $v_1$ 的 peak 点 $\widehat\lambda_u=1.892238$；$v_3$ 的 flip 点为 $0.072982$，$v_2$ 的 peak 点为 $0.961184$，自适应中点为 $2.144263$。因此解析候选刻画各单 pair 的关键变化，几何中点与三枚固定点则补上竞争 pair 切换和中间包络区域。连续曲线和竖虚线仅用于论文解释；在线算法只计算图中标出的有限候选，有限集相对 dense reference 的总体精度仍由 Figure 6 的全部 240 个场景提供。

## 图 8：稳健包级空间统计如何抑制被碰撞的前导码窗口

如图 8 所示，我们将实测 target packet 24（`pos10#1`）与 interferer packet 5（`pos03#0`）直接叠加，设置 SIR 为 $-6$ dB、相对起点为 $3.35T_s$，且不额外加入 AWGN。该 pair 被显式选择，是为了形成前三个窗口较干净、后五个窗口开始碰撞的机制案例，而不是构造总体性能结论。图 (a) 为同一碰撞的 LoRa chirp 时频能量：较弱目标从 $0T_s$ 开始，较强干扰从 $3.35T_s$ 开始，后半段目标前导内同时存在两条清晰 chirp 轨迹，直接揭示局部信道快照为何会被污染。

图 (b) 的五条彩色曲线分别为目标峰附近 $d\in\{-2,-1,0,1,2\}$ 的局部快照

$$
\mathbf g_{u,p}^{(d)}
=
e^{-j2\pi\widehat\epsilon_up}
\mathbf Z_{u,p}[k_0+d],
$$

图例给出相应聚合系数

$$
[c_{-2},c_{-1},c_0,c_1,c_2]
=
[0.12,0.45,1,0.45,0.12].
$$

灰色虚线为五 bin 加权聚合快照

$$
\mathbf g_p
=
\sum_{d=-2}^{2}c_d\mathbf g_{u,p}^{(d)},
$$

纵轴采用带符号射影角：绝对值仍为各方向相对 collision-free $\mathbf h_{\rm clean}$ 的射影角，符号由双天线相对相位偏差决定。这样不会把参考方向两侧的误差都折叠到正半轴。单独乘以正实数 $c_d$ 不改变局部方向，因而彩色曲线展示五个核输入自身的质量，$c_d$ 只控制其对灰色曲线的贡献。干扰出现后，若干局部 bin 分别偏向正负两侧，而灰色聚合仍明显比单个偏移 bin 稳定。最终包级 $\widehat{\mathbf h}_u$ 仍由八个 $\mathbf g_p$ 按 $w_{u,p}$ 在代码中计算，但为使本子图只回答“局部五 bin 隔离如何形成 $\mathbf g_p$”，不再额外绘制原来的粗黑水平线。

## 空气信道测量 I：包内方向相干性

包内相干性实验只验证 SP 使用的空间方向，因此三个子图统一统计 degree，并采用带符号射影角

$$
\Delta\psi(\widehat{\mathbf h},\mathbf h_{\rm clean})
=
\operatorname{sgn}\!\left(
\operatorname{wrap}\!\left[
\angle(\widehat h_1\widehat h_0^*)-
\angle(h_{{\rm clean},1}h_{{\rm clean},0}^*)
\right]\right)
d(\widehat{\mathbf h},\mathbf h_{\rm clean}).
$$

它的绝对值与原射影角完全一致，符号仅表示估计位于参考方向的哪一侧。因此评价准确度时观察 $|\Delta\psi|$ 和箱体宽度，有符号中位数只用于检查偏置。

数据直接来自 `run_02000001` 的 23 个 CRC-valid 完整包，每帧含 8 preamble、2 sync、2.25 SFD 和 33 payload chirp，总长 $45.25T_s$。每包估计 45 个完整 chirp：起点为 $0,\ldots,11T_s$ 及 $12.25,\ldots,44.25T_s$，从而保留末个完整 SFD 到首个 payload 的 $1.25T_s$ 跨度。实验先只根据无噪整帧的第 90 百分位增益离散度与相对相位离散度固定选择 8 包质量池，不读取后续加噪或碰撞结果。

正式实验对已检测、已对齐的完整包加入 AWGN，扫描 $-10$ 至 20 dB 七档，每包每档重复 8 次，共得到 448 个包级估计。图 (a) 和图 (b) 使用同一个 $-10$ dB 代表包；图 (a) 的纵轴固定为 $[-20^\circ,20^\circ]$。新增图 (d) 沿复射影空间对 collision-free 实测信道施加 $-7.5^\circ$ 至 $+7.5^\circ$、步长 $2.5^\circ$ 的受控误差，并用所得 $\widehat{\mathbf h}$ 执行 $D[k]=|P[k]|^2-4|Q[k]|^2$。SNR 与项目其余 AWGN 实验统一定义为解啁啾前目标波形平均功率与时域复采样 AWGN 功率之比，直接按标称值注噪，不扣除 FFT 处理增益。每点聚合 8 包、每包 8 次噪声实现，共 2,112 个符号；同一噪声实现跨方向误差点配对复用。输入 SNR 为 $-10$ 至 10 dB 且误差不超过 $\pm7.5^\circ$ 时均未观察到符号错误。这说明 SF10 的处理增益足以覆盖该 collision-free 压力范围，也说明该子图不能替代碰撞下的方向失配实验。

这里必须区分“测量物理信道”和“评估现有前端”。图 (a)(b) 为了取得整包 45 个逐 chirp 样本，使用已知正确 FFT bin 提取空间向量；它们是 oracle-bin 包内相干性测量，因为生产前端只输出一个包级 $\widehat{\mathbf h}_u$。图 (c) 已改为实际调用 `robust_preamble_channel_sp`，只读取八个含噪前导窗口，并与同一 collision-free 包由相同前端给出的参考方向比较。$-10$ 至 20 dB 下，实际前端绝对方向误差中位数从 $2.60^\circ$ 降至 $0.08^\circ$，90 分位从 $6.75^\circ$ 降至 $0.19^\circ$。图 (d) 则是人为控制投影方向误差的 collision-free 解码敏感性实验，不是一次前端估计实验。三类口径分别回答包内物理稳定性、生产前端含噪估计精度和解码器对方向失配的敏感性，不能混写。

## 空气信道测量 II：碰撞下的带符号方向估计

并发信道测量的 target 严格复用上述 Node02 八包质量池；interferer 从 PHY 参数完全相同的 Node01 与 Node03 单节点实测包中抽取。固定种子生成 8 个跨节点有序 pair。干扰包相对目标错开 $1T_s$，SIR 为 $-5$、$-2$、0、2 和 5 dB，FFT-bin 间隔为 0、2、4、8 和 16，共形成 200 个 trace-driven 碰撞。

图 (a)–(c) 分别展示三档 SIR 下的带符号方向误差。$-5$ dB SIR 下五个间隔的 $|\Delta\psi|$ 中位数为 $24.067^\circ$、$16.450^\circ$、$7.425^\circ$、$3.340^\circ$ 和 $1.608^\circ$；0 dB 下为 $13.824^\circ$、$11.255^\circ$、$4.951^\circ$、$2.286^\circ$ 和 $1.108^\circ$；5 dB 下为 $8.955^\circ$、$7.033^\circ$、$3.053^\circ$、$1.398^\circ$ 和 $0.674^\circ$。

图 (d) 将五档 SIR 下碰撞前导估计得到的 $\widehat{\mathbf h}$ 用于完整 payload 判决，不绘制散点。五条 SER 曲线在 0、2、4、8、16 bin 下分别为：$-5$ dB 时 73.86%、85.23%、24.24%、12.50%、12.12%；$-2$ dB 时 46.59%、60.61%、12.50%、1.52%、0；0 dB 时 25.00%、1.14%、0.38%、0、0；2 dB 时 25.00%、0、0.38%、0、0；5 dB 时全部为 0。图 (a)–(c) 只保留 $-5$、0、5 dB 三个代表性方向误差分布，图 (d) 则以五档 SIR 展示更完整的解码趋势。0 与 2 bins 都处在五 bin 局部估计核的强混叠范围内，因此两点之间不应强求单调；真正稳定的转折出现在干扰离开局部核的 4–8 bins 区间。

## 室内信道实验复现命令

图 2(d) 的碰撞方向误差—九点权重扫描实验：

```bash
python3 real_collision_experiment/paper_experiments/generate_sp_v2_mechanism_figures.py \
  --clean real_usrp_outputs/clean_pos_packets.npz \
  --out-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --seed 20260824 \
  --sp-gamma 0.05 \
  --sp-lambda-max 4 \
  --only-fig2d
```

图 2(d) 单独渲染：

```bash
python3 real_collision_experiment/paper_experiments/render_sp_v2_clear_figures.py \
  --data-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --source-figure-dir real_usrp_outputs/sp_paper_figures \
  --out-dir real_usrp_outputs/sp_v2_paper_native_figures \
  --only-fig2d
```

包内相干性数据生成：

```bash
python3 real_collision_experiment/paper_experiments/generate_sp_v2_mechanism_figures.py \
  --air-iq real_collision_experiment/runs/run_02000001/run_02000001.sc16 \
  --air-report real_collision_experiment/runs/run_02000001/node02_sp_report.json \
  --out-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --seed 20260808 \
  --coherence-snr-db=-10,-5,0,5,10,15,20 \
  --coherence-noise-trials 8 \
  --coherence-display-snr-db -10 \
  --coherence-quality-pool-size 8 \
  --only-air-within
```

trace-driven 并发信道测量：

```bash
python3 real_collision_experiment/paper_experiments/generate_sp_v2_mechanism_figures.py \
  --air-iq real_collision_experiment/runs/run_02000001/run_02000001.sc16 \
  --air-report real_collision_experiment/runs/run_02000001/node02_sp_report.json \
  --air-interferer-iq real_collision_experiment/runs/run_01000001/run_01000001.sc16 \
  --air-interferer-report real_collision_experiment/runs/run_01000001/node01_sp_report.json \
  --air-interferer-iq real_collision_experiment/runs/run_03000001/run_03000001.sc16 \
  --air-interferer-report real_collision_experiment/runs/run_03000001/node03_sp_report.json \
  --out-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --seed 20260808 \
  --channel-sir-db=-5,-2,0,2,5 \
  --channel-bin-distance=0,2,4,8,16 \
  --channel-pair-trials 8 \
  --channel-offset-symbols 1 \
  --only-air-concurrent
```

只渲染这两张论文图：

```bash
python3 real_collision_experiment/paper_experiments/render_sp_v2_paper_native_figures.py \
  --data-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --out-dir real_usrp_outputs/sp_v2_paper_native_figures \
  --only-air
```

## 尚未产生数据的结果图

`SP-Decode v2.md` 中的图 9(a–c) 仍是待完成的端到端并发实验，当前仓库没有与其设计完全对应的三轮 1/3/6/9/12/15 节点统计，因此现在不能补写“结果表明”式段落。正式完成后，每段至少应报告：节点布局与功率控制、每个横轴点的完整目标包数量、三轮实验的独立性、PRR 的 FEC/CRC 口径、检测率与条件 PRR 的分离、95% 置信区间算法，以及 SP-Decoder 相对各基线的绝对百分点提升。不得用图 2–8 的 trace-driven 或 symbol-domain 数据代替图 9 的端到端结论。
