# SP\-Decode v0

## 摘要

1. 引言
低功耗广域网络（Low-Power Wide-Area Network, LPWAN）以低终端复杂度和广域覆盖支撑城市感知、工业监测与大规模物联网接入。随着节点规模与业务负载持续增长，随机上行造成的同频碰撞逐渐成为限制网络容量的重要因素。LoRa 采用 chirp spread spectrum（CSS）调制以获得较高的接收灵敏度和链路预算，但标准接收机在碰撞场景中仍主要依赖 capture effect 恢复具有明显功率优势的传输。对于近等功率或高度重叠的并发包，传统单包解调通常难以可靠恢复，从而引发重传并进一步增加信道占用。因此，如何从同一时间—频率资源中恢复多个 LoRa 包，是提升密集 LoRa 网络并发接收能力的关键问题。
已有研究表明，LoRa 碰撞并非天然不可恢复。CIC 利用异步 chirp 在局部频谱上的差异识别稳定峰值，CurvingLoRa 通过改变 chirp 结构主动增强并发波形的可分性，Mc-LoRa 等系统进一步利用跨符号或跨信道特征区分重叠传输 \cite{cic_sigcomm21,curvinglora_nsdi22,mclora_mobicom23}。另一类工作利用多天线接收所提供的空间维度。同步采集的多个射频通道不仅记录频谱峰值的幅度，还保留由传播信道决定的跨天线复数关系。PCube 利用节点相关的跨天线相位特征关联并发峰，MaLoRaGW 则通过信道估计和空间投影获得更有利于单用户解码的目标观测 \cite{pcube_tosn22,maloragw_sensys22}。这些方法通过波形设计、频谱结构或空间维度提高并发传输的可分性，为后续符号恢复创造更有利的观测条件。对于多天线接收器，空间信息主要被用于峰值关联、目标增强或用户分离，随后再执行 LoRa 的 FFT-bin 判决。
然而，有限的空间自由度并不能保证完全分离。当并发包数量增加、不同节点的空间信道方向接近，或强竞争分量仍在目标方向保留显著投影时，空间处理后的目标观测仍可能包含结构化残留。此时，一个由竞争包形成的错误 FFT bin 即使并不符合目标包的完整空间特征，也可能因为在目标方向上具有较大的投影而超过真实 bin。传统目标投影或 MRC 型判决最终仅依据该方向上的非负能量进行排序，因此，多天线前端已经观测到的空间不一致性并未进入最终的 symbol decision。
本文关注这一尚未被充分利用的接收机接口：多天线 FFT bin 不仅具有强度，还具有空间身份；在不完全分离之后，剩余空间结构仍可直接参与最终的 bin attribution。 对于一个真实目标 bin，其空间向量应主要与目标信道方向一致；对于一个强竞争 bin，即使其目标方向投影足以造成传统判决错误，其完整空间向量仍可能在目标正交子空间中暴露显著能量。由此，目标方向投影可以被解释为支持候选属于目标包的正向证据，而目标正交投影则提供该候选与目标空间身份不一致的反向证据。SP-Decoder 因而不再仅比较候选 bin 的目标方向强度，而是将最终符号恢复表述为 target-conditioned spatial bin attribution：对每个候选同时评估目标一致证据与目标不一致证据。
这一思路的困难不在于简单引入一个正交惩罚项，而在于如何在真实接收条件下可靠地配置其强度。首先，目标空间方向本身只能由有限前导观测估计；噪声、射频链路失配、碰撞污染以及包内漂移均可能使真实目标能量泄漏到估计的正交子空间。过强的反向证据会因此侵蚀正确 bin 的判决裕量。其次，不同碰撞包具有不同的接收强度、方向可靠性、竞争包空间相似度和时域重叠关系，使“压制竞争 bin 所需的最小反证强度”与“保护真实 bin 所允许的最大反证强度”均呈现明显的 packet dependence。更重要的是，接收机在 payload 解码前并不知道真实 symbol，因此无法直接依据 symbol error 或真实 bin 对多个候选权重进行在线比较。问题的关键并非搜索区间是否足够小，而是在缺少 payload truth 的条件下，应以何种可观测统计量配置判决器。
基于上述观察，本文提出 SP-Decoder。SP-Decoder 首先将多天线 FFT observation 投影到目标信道方向及其正交子空间，并从局部统计假设出发得到同时包含目标支持与空间反证的 signed bin score。随后，系统利用重复前导构造目标空间方向及其不确定性，并结合已建立竞争包的接收强度和空间关系，将不可直接观测的 payload 条件统计量映射为可在解码前获得的 packet-level proxies。在此基础上，SP-Decoder 为每个目标包配置一次可靠性感知的反证权重，并由整个 payload 共享。配置完成后，每个 symbol 仍只执行一次 dechirp/FFT 和一次固定的 top-1 判决，无需逐符号参数搜索、干扰 payload 恢复或 SIC 式的顺序解码。
本文的主要贡献如下。
1. 重新表述多天线 LoRa 的最终符号判决问题。 现有多天线接收器主要利用空间信息进行峰值关联、目标增强或用户分离。SP-Decoder 进一步利用不完全分离后仍保留的空间结构，将 FFT-bin selection 表述为目标条件的空间归属检验：目标方向分量提供支持证据，目标正交分量提供反向证据。基于该表述，我们给出 signed spatial score 及其符号级判决裕量，刻画空间反证能够修复传统目标投影错误的条件，以及过强反证可能损伤既有正确判决的情形。
2. 设计无需 payload truth 的可靠性感知包级 detector configuration。 SP-Decoder 不直接依赖未知的 payload-bin 条件统计量，而是利用前导阶段可观测的目标方向可靠性、包级接收强度和目标—竞争包空间关系构造由前导观测驱动的包级统计代理，并据此同时约束“需要多少反证才能压制竞争者”和“最多允许多少反证而不显著损伤目标”。该配置仅在目标包建立时执行一次，并由整个 payload 共享，从而避免 CRC 驱动的多次完整解码、逐符号 oracle tuning 和干扰符号恢复。
3. 实现并评估双通道 SP-Decoder 接收链。 原型保留标准 LoRa 的 dechirp、FFT、FEC 和 PHY 解码流程，仅在最终 FFT-bin attribution 中加入目标条件的空间判决。我们通过实测双通道波形构造的可控碰撞以及真实空口实验，评估空间反证的可观测性、packet-specific weight 的必要性、前导可靠性 proxy 与 payload 风险之间的关系，以及不同碰撞强度、时域偏移和空间方向歧义下的端到端解码性能。[最终版本在此加入 2–3 个最有说服力的定量结果。]
<!-- FIGURE 1:
(a) 异步并发 LoRa 包进入双天线网关，前端已经建立目标包但无法完全消除结构化残留；
(b) target bin 与 strong wrong bin 的空间向量：wrong bin 的目标方向投影可以更强，但同时具有显著目标正交分量；
(c) preamble-derived packet statistics -> once-per-packet configuration -> fixed signed top-1 over payload。
图内尽量减少说明文字，以“support / counter-evidence / packet-level configuration”作为核心标签。
-->
2. 背景与动机
本节首先回顾 LoRa 的 FFT-bin 符号判决，并建立双天线接收下的空间 FFT 观测模型。在此基础上，我们从目标方向与其正交方向两个互补分量描述候选 bin 的空间一致性，并给出相应的有符号判决形式。随后，基于实测双通道 LoRa 波形构造的可控碰撞，从空间反证的可观测性、反证权重的包间差异以及目标方向估计误差三个方面验证该判决思路的实际依据。
2.1 LoRa 符号解调与碰撞
LoRa 采用 chirp spread spectrum 调制。对于扩频因子 $$\mathrm{SF}$$，一个符号从 $$M$$ 个可能值中选择，其中
$$M=2^{\mathrm{SF}}.$$
令标准 upchirp 为
$$c[n]
=
\exp\!\left[
j2\pi
\left(
\frac{n^2}{2M}
-
\frac{n}{2}
\right)
\right],
\qquad
0\le n<M.$$
符号 $$s$$ 可表示为标准 upchirp 的循环频移：
$$x_s[n]
=
c[n]
\exp\!\left(
j2\pi\frac{s}{M}n
\right),
\qquad
s\in\{0,\ldots,M-1\}.$$
接收机完成包检测、符号边界估计和载波频偏补偿后，将目标符号窗口与参考 downchirp 相乘。对于单包平坦信道，dechirp 后的观测为
$$z_s[n]
=
h
\exp\!\left(
j2\pi\frac{s}{M}n
\right)
+
w[n],$$
其中，$$h$$ 为该符号窗口内的复信道增益，$$w[n]$$ 为接收噪声。dechirp 将 chirp 转换为频率由符号值决定的近似单音。执行 $$M$$ 点离散傅里叶变换后得到
$$Z_s[k]
=
\sum_{n=0}^{M-1}
z_s[n]
\exp\!\left(
-j2\pi\frac{kn}{M}
\right).$$
在理想同步条件下，目标能量集中于与 $$s$$ 对应的 FFT bin，因此标准非相干 LoRa 符号判决为
$$\widehat{s}
=
\arg\max_{0\le k<M}
|Z_s[k]|^2.$$
因此，LoRa 后端解调本质上将符号恢复转化为 FFT-bin ranking。单包条件下，最大谱峰通常对应真实符号；发生碰撞后，目标对齐窗口同时包含其他发送端的 chirp 片段。相对起点、相对 CFO、符号边界和复相位使这些分量形成竞争峰、邻 bin 泄漏及相干叠加，即使目标包已经准确同步，最强 FFT bin 仍可能并非目标符号。本文关注目标包已经建立后的这一最终判决阶段。
<!-- FIGURE :
单包/多包碰撞FFT频谱
-->
2.2 双天线空间 FFT 观测
标准单天线接收机在每个 FFT bin 上得到一个复数，并通常依据其幅度或能量进行排序。对于同步双天线接收机，同一个 bin 对应二维复向量
$$\mathbf Y_{u,\ell}[k]
=
\begin{bmatrix}
Y^{(1)}_{u,\ell}[k]\\
Y^{(2)}_{u,\ell}[k]
\end{bmatrix}
\in\mathbb C^2,$$
其中，$$u$$ 表示当前目标包，$$\ell$$ 表示其 payload symbol 索引，$$k$$ 表示 FFT bin。因而，多天线 FFT bin 不仅具有强度，还保留由跨天线幅度与相位关系决定的空间结构。
考虑多个 LoRa 包同时到达网关。接收机按照目标包 $$u$$ 的 timing 和 CFO 对齐第 $$\ell$$ 个 payload symbol，并分别在两根天线上执行 dechirp 和 FFT。bin $$k$$ 的空间观测可写为
$$\mathbf Y_{u,\ell}[k]
=
\sum_v
\mathbf h_v A_{uv,\ell}[k]
+
\mathbf N_{u,\ell}[k],$$
其中，$$\mathbf h_v\in\mathbb C^2$$ 为包 $$v$$ 的有效双天线空间信道，$$A_{uv,\ell}[k]$$ 为包 $$v$$ 在以目标包 $$u$$ 为参考的解调窗口中对 bin $$k$$ 形成的复 FFT 系数，$$\mathbf N_{u,\ell}[k]$$ 为 FFT 域噪声。目标分量在解调窗口正确对齐后主要集中于真实 symbol bin；其他包由于相对 timing 和 CFO 不同，可形成强竞争峰或跨 bin 泄漏。
目标包真实信道对应的归一化空间方向记为
$$\mathbf a_u
=
\frac{\mathbf h_u}
{\|\mathbf h_u\|_2}.$$
$$\mathbf a_u$$ 描述目标包的实际空间方向，但真实场景中无法被接收机直接获得，以往工作可利用目标前导估计其有效信道 $$\widehat{\mathbf h}_u$$，并据此构造实际判决所采用的目标参考方向
$$\widehat{\mathbf a}_u
=
\frac{\widehat{\mathbf h}_u}
{|\widehat{\mathbf h}_u|_2}.$$
对于双天线接收，可进一步构造与 $$\widehat{\mathbf a}_u$$ 正交的单位向量。若
$$\widehat{\mathbf a}_u
=
\begin{bmatrix}
\widehat a_{u,1}\
\widehat a_{u,2}
\end{bmatrix},$$
则取
$$\widehat{\mathbf b}_u
=
\begin{bmatrix}
-\widehat a_{u,2}^{*}\
\widehat a_{u,1}^{*}
\end{bmatrix},$$
从而满足
$$\widehat{\mathbf a}_u^H\widehat{\mathbf b}_u=0,
\qquad
|\widehat{\mathbf b}_u|_2=1.$$
接收机据此将每个候选 bin 的二维空间观测分解为目标参考方向投影
$$P_{u,\ell}[k]
=
\widehat{\mathbf a}*u^H
\mathbf Y*{u,\ell}[k],$$
以及目标正交方向投影
$$Q_{u,\ell}[k]
=
\widehat{\mathbf b}*u^H
\mathbf Y*{u,\ell}[k].$$
其中，$$|P_{u,\ell}[k]|^2$$ 衡量候选 bin 沿估计目标方向的响应，而 $$|Q_{u,\ell}[k]|^2$$ 则刻画其在该方向之外保留的空间分量。传统目标投影仅依据 $$|P_{u,\ell}[k]|^2$$ 完成 FFT-bin ranking。当某个竞争峰在目标方向上的投影超过真实 bin 时，该判决可能失效；然而，同一竞争峰在 $$Q_{u,\ell}[k]$$ 中仍可能保留与目标空间身份不一致的信息。
值得注意的是，$$\widehat{\mathbf a}*u$$ 是由有限前导观测得到的估计方向，而非真实方向 $$\mathbf a_u$$。因此，即使一个 FFT bin 确实属于目标包，其能量也不必完全落在 $$P*{u,\ell}[k]$$ 中；当 $$\widehat{\mathbf a}*u$$ 偏离 $$\mathbf a_u$$ 时，部分目标能量同样会出现在 $$Q*{u,\ell}[k]$$ 中。这使正交分量同时包含潜在的竞争判别信息和目标方向估计误差所引入的泄漏，并构成后续有符号空间判决需要处理的基本权衡。
2.3 目标一致与竞争 bin 的空间证据
对目标包 $$u$$ 的候选 bin $$k$$，我们考虑两种局部空间假设：
$$\mathcal H_T(k):
\quad
\text{bin }k\text{ 与目标包 }u\text{ 的空间特征一致},$$
$$\mathcal H_C(k):
\quad
\text{bin }k\text{ 主要由其他并发包、频谱泄漏或噪声形成}.$$
竞争成分可以来自一个或多个重叠包，也可包含异步 chirp 泄漏和噪声。该判别不要求识别竞争峰的发送端，其关注点是候选 bin 与当前目标空间身份的一致程度。为获得可解析的判决形式，我们以局部二阶统计近似未知碰撞幅相和叠加项，并将 $$P[k]$$ 与 $$Q[k]$$ 建模为条件圆对称复高斯变量
$$\begin{aligned}
P[k]\mid\mathcal H_T &\sim \mathcal{CN}(0,\nu_{T,\parallel}),
&
 Q[k]\mid\mathcal H_T &\sim \mathcal{CN}(\mathbf 0,\nu_{T,\perp}),\\
P[k]\mid\mathcal H_C &\sim \mathcal{CN}(0,\nu_{C,\parallel}),
&
Q[k]\mid\mathcal H_C &\sim \mathcal{CN}(\mathbf 0,\nu_{C,\perp}).
\end{aligned}$$
其中，$$\mathcal{CN}(\boldsymbol\mu,\mathbf\Sigma)$$ 表示均值为 $$\boldsymbol\mu$$、协方差为 $$\mathbf\Sigma$$ 的圆对称复高斯分布，四个 $$\nu$$ 分别表示两类假设在目标方向和正交方向上的条件二阶能量。下标 $$T$$ 和 $$C$$ 分别对应目标一致假设与竞争 bin 假设；下标 $$\parallel$$ 和 $$\perp$$ 分别表示目标信道方向与其正交子空间。目标一致 bin 通常在目标方向上具有更强的统计支持，而空间不一致的竞争成分更可能在正交方向留下额外能量。因此，我们关注的典型工作区域为
$$\nu_{T,\parallel}>\nu_{C,\parallel},
\qquad
\nu_{C,\perp}>\nu_{T,\perp}.$$
2.4 有符号空间判决
在上述局部模型下，目标一致假设相对于竞争假设的对数似然比可写为
$$\log
\frac{
p\!\left(
\mathbf Y[k]\mid\mathcal H_T
\right)
}{
p\!\left(
\mathbf Y[k]\mid\mathcal H_C
\right)
}
=
c
+
\alpha |P[k]|^2
-
\beta |Q[k]|^2,$$
其中，$$c$$ 与 bin index 无关，且
$$\alpha
=
\frac{1}{\nu_{C,\parallel}}
-
\frac{1}{\nu_{T,\parallel}},$$
$$\beta
=
\frac{1}{\nu_{T,\perp}}
-
\frac{1}{\nu_{C,\perp}}.$$
在上述工作区域内，$$\alpha$$ 与 $$\beta$$ 均为正。去除不影响 bin ranking 的常数项和正比例因子后，可得到 signed spatial score
$$D_{u,\ell}[k]
=
|P_{u,\ell}[k]|^2
-
\lambda_u
|Q_{u,\ell}[k]|^2,$$
其中
$$\lambda_u
=
\frac{\beta}{\alpha}.$$
最终符号判决为
$$\widehat{s}_{u,\ell}
=
\arg\max_{0\le k<M}
D_{u,\ell}[k].$$
该形式将两个空间分量赋予不同的判决含义：$$|P[k]|^2$$ 提供目标一致支持，$$|Q[k]|^2$$ 则降低空间不一致候选的得分。当竞争峰在目标方向上足够强而造成传统 ranking 错误时，正交分量能够提供额外的区分依据。
与此同时，$$\lambda_u$$ 决定正交证据在最终判决中的相对作用。若真实目标也存在明显的正交泄漏，过大的 $$\lambda_u$$ 会同时降低正确 bin 的得分；若目标与竞争假设在正交方向上的统计差异较弱，则较大的反证权重也难以带来稳定收益。因此，$$\lambda_u$$ 的配置应同时考虑目标方向可靠性与竞争空间结构。下一节基于实测波形考察这两类因素对空间反证有效性的实际影响。
2.5 实测波形中的动机证据
我们从十个接收位置的双通道 USRP 采集中提取 26 个无碰撞 LoRa frame；每个 frame 含 38 个 payload symbols。对于每个 trace-driven collision，将两段实测复基带波形按指定相对起点叠加，并用复增益实现给定 SIR；保留原始 CFO、双天线幅相响应和射频波形失真，同时通过额外的复指数平移设置两包前导峰的相对 FFT-bin separation。除动机 A 为隔离空间反证而使用 clean target reference 外，动机 B/C 均从合成碰撞的目标八个前导窗口估计 $$\widehat{\mathbf h}_u$$，并以该方向固定解码整个 payload；在动机 C 的上界受控分支中，固定 payload 混合后仅替换用于估计该方向的前导观测。clean trace 的 symbol sequence 仅在离线阶段用于计算 SER 和区间端点，不参与前导方向估计或任何在线权重选择。以下三个实验依次验证空间反证是否存在、固定权重是否足够，以及可用反证范围为何受到两类约束。
2.5.1 动机 A：错误峰保留了可利用的空间反证
为先排除方向估计误差这一混杂因素，动机 A 对每个 target 使用其 collision-free trace 中估计的 CFO 和空间方向；随后按 SIR 为 −5 至 0 dB 的两包碰撞、不同 packet pair 和相对起点逐个解调。对每个产生 MRC 错误的 payload symbol，我们同时记录真实 bin 和 MRC 最大峰在 $$P$$、$$Q$$ 两个投影上的能量。因而该实验的问题不是“前导是否已能可靠地估计方向”，而是“在方向给定时，错误峰本身是否仍带有可利用的反证”。
对目标包 $$u$$ 的第 $$\ell$$ 个 symbol，定义候选 bin 的归一化空间不一致度
$$\eta_{u,\ell}[k]
=
\frac{
|Q_{u,\ell}[k]|^2
}{
|P_{u,\ell}[k]|^2
+
|Q_{u,\ell}[k]|^2
}.$$
图 2(a) 给出一个代表性 MRC 错误。传统目标投影将 bin 304 判为最大响应，而真实 bin 为 537；错误 bin 的空间不一致度为 0.862，真实 bin 仅为$$1.56\times10^{-4}$$。因此，该错误峰虽然在目标方向上具有更强响应，却同时暴露出明显的目标正交分量；加入适度反证后，真实 bin 的排序得到恢复。
图 2(b) 进一步统计 SIR 为 −5 至 0 dB 的全部两包 trace-driven collisions。在 MRC 错误 symbols 中，99.12% 满足$$\eta_{\mathrm{wrong}}
>
\eta_{\mathrm{target}}$$，且二者中位数相差约 279 倍。结果说明，造成传统 ranking 错误的强竞争峰通常仍保留可用于归属判别的空间信息，为 signed spatial decision 提供了直接的实验依据。
[图片]
[图片]
2.5.2 动机 B：反证权重具有显著的包间差异
为直接检验同一固定权重能否适用于不同碰撞包，我们以 7 个两包 trace-driven collision 场景逐包扫描反证强度。每个场景都从 clean dual-channel traces 中取一个 target 和一个 interferer，在复基带按指定 SIR、相对起点和前导峰 separation 相加；接收机仅利用 collided preamble 的八个窗口估计一次 $$\widehat{\mathbf h}_u$$，随后保持该方向不变，在完整的 38 个 payload symbols 上评估 $$\lambda=0,0.25,\ldots,10$$。图中场景的 SIR 覆盖 $$-8$$ 至 $$-2$$ dB，相对起点覆盖 $$0.5T_s$$、$$1T_s$$ 和 $$2T_s$$，前导峰 separation 为 $$0$$、$$1$$ 或 $$3$$ bins；clean target bin 仅用于离线计算 SER，不参与方向估计或权重配置。

图 2(c) 给出七个碰撞包的完整 payload SER 曲线，星号标示各包在扫描网格上的最低 SER。七条曲线的最低点分别始于 $$\lambda=0.25,0.75,1.5,2,3.25,4$$ 和 $$5.25$$；其中 6 条曲线的精确最小值平台宽度不超过 $$1.25$$。低 SER 区域因而随碰撞包发生明显平移，而非汇聚为一个对所有包都有效的公共区间。具体而言，较小的权重能够压制 P1--P4 的竞争峰，却不足以恢复 P6--P7；当权重增大以修复 P6--P7 时，前几条曲线又迅速退化。单条曲线的最优点并不能迁移为另一条曲线的可靠配置。

固定权重的 full-payload PRR 将这一现象量化为包级结果：这里 PRR 定义为 7 个场景中全部 38 个 payload symbols 均正确的比例，即 $$\operatorname{SER}=0$$ 的曲线数除以 7，并非 PHY CRC 指标。柱状统计表明，大多数能够恢复完整 payload 的固定权重也仅恢复 1/7 个包（14.3%）；在最有利的 $$\lambda=5.25,5.5,5.75$$，PRR 也只达到 2/7（28.6%），在整个扫描范围内从未超过 0.6。因而，即使允许利用完整 payload truth 事后选择常数，固定反证强度仍无法同时稳定恢复这组碰撞包。$$\lambda_u$$ 必须在 payload 到达前按包配置，且其可用范围将同时受竞争需求和目标方向可靠性约束；下一节通过受控实验分解这两类约束。

![图 2(c)：trace-driven 碰撞的逐包 payload SER--权重曲线](real_usrp_outputs/sp_v2_paper_native_figures/fig2c_packet_dependent_lambda.png)
2.5.3 动机 C：可用反证强度受竞争需求与目标可靠性共同约束
图 2(d) 中两张图研究的是同一个 packet-level 可用区间，而不是各自独立的最优点。对每个完整 payload，在 $$\lambda=0,0.25,\ldots,10$$ 上定义
$$\Omega_u=\{\lambda:\operatorname{SER}_u(\lambda)<0.20\},\qquad
\lambda_u^{\mathrm{low}}=\min\Omega_u,\qquad
\lambda_u^{\mathrm{high}}=\max\Omega_u.$$
其中 SER 由全部 38 个 payload symbols 的实际 top-1 判决计算；clean symbol bins 只在离线阶段用于判定该符号是否正确。因而，$$\lambda_u^{\mathrm{low}}$$ 是压制竞争峰所需的最小反证，$$\lambda_u^{\mathrm{high}}$$ 则是在目标 bin 被反证明显损伤前所允许的最大反证。热图的每一个色块都是一次完整 payload 解码的 SER，黑线直接从该列满足 $$\operatorname{SER}<0.20$$ 的网格点取端点。

**竞争需求决定下界。** 固定 target reference 的质量和 payload offset：先在一个固定的 collided-preamble 条件（前导 SIR 为 $$-2$$ dB、offset 为 $$1T_s$$、峰 separation 为 6 bins）估计一次 $$\widehat{\mathbf h}_u$$，该方向相对 clean reference 的误差为 $$1.56^\circ$$，随后保持不变。对同一 clean packet pair，payload 仍取 $$1T_s$$ offset 和 6-bin separation，只将 payload SIR 从 $$-5$$ 扫到 $$1$$ dB。图 2(d-left) 中，竞争增强时低 SER 区域从更大的 $$\lambda$$ 才开始出现：SIR 为 $$1,0,-1,-2,-3,-4,-5$$ dB 时，$$\lambda_u^{\mathrm{low}}$$ 分别为 $$0,0,2.5,4.75,6.25,7.5,8.5$$。由于投影方向与相对起点均被固定，这一左边界的右移只来自更强的 payload 竞争；SIR 越低，压制竞争峰所需的最小反证越大。

**目标可靠性决定上界。** 这里固定另一个 packet pair 的 payload collision：payload SIR 为 $$-2$$ dB、offset 为 $$1T_s$$、峰 separation 为 0 bin。随后不改变这段 payload 混合，只改变用于估计 $$\widehat{\mathbf h}_u$$ 的 collided-preamble 观测。前导的相对起点固定为 $$1T_s$$、峰 separation 固定为 0，仅将前导 SIR 设为 $$15,10,8,6,4,2,0,-2$$ dB，从而得到 $$\theta_u=4.97,8.90,11.26,14.24,17.99,22.59,28.00,34.05^\circ$$ 的目标方向误差。图 2(d-right) 的相应上界为 $$10,8.75,6.5,4.75,3.25,2,1.25,0.75$$；随着误差增大，安全上界在同一扫描网格内连续向左收缩。尤其在 $$\theta_u=34.05^\circ$$ 时，可用区间只剩 $$[0.25,0.75]$$。因此，前导方向越不可靠，过强反证越早开始伤及真实目标 bin，允许的最大反证越小。

两张图共同给出图 2(c) 中 packet-dependent 配置的区间解释：每个包所需的 $$\lambda_u$$ 并非仅因单一最优点漂移，而是其可用区间同时受到两侧约束。竞争越强，需要更大的最小反证；目标参考越不可靠，允许的最大反证越小。这正是后续 detector configuration 同时建模竞争关系与目标可靠性、并在 payload 到达前配置 packet-specific $$\lambda_u$$ 的依据。

![图 2(d-left)：竞争需求决定可用反证区间的下界](real_usrp_outputs/sp_v2_paper_native_figures/fig2d_competition_lower_bound_heatmap.png)

![图 2(d-right)：目标可靠性决定可用反证区间的上界](real_usrp_outputs/sp_v2_paper_native_figures/fig2d_target_reliability_upper_bound_heatmap.png)
2.6 设计启示
上述结果揭示了空间分离之后仍可利用的一项判决自由度：未被消除的正交结构并非仅是残余干扰，其中仍包含 FFT-bin 归属信息。因而，多天线接收机无需将“完全消除非目标分量”作为利用空间信息的唯一途径；在分离受限时，残余空间结构仍可直接参与最终符号判决。
这一机会同时受到目标方向可靠性和竞争空间关系的约束。SP-Decoder 因此将反证强度配置提升至 packet level：在 payload 开始前依据可观测的包级空间统计确定 $$\lambda_u$$，随后以固定 signed score 完成整个 payload 的符号判决。

## 3\. SP\-Decoder 概览

SP\-Decoder 将理想似然判决转化为一个可部署的接收流程。其核心思想是：先在包级建立可靠的目标空间模型与竞争条件，再配置一次有符号判决器，最后以固定规则完成整个 payload 的符号恢复。整体流程包括以下四个阶段。

**目标信道估计。**
目标前导码在 payload 到达之前提供了重复且具有已知结构的多天线空间快照。SP\-Decoder 对多个前导快照进行稳健聚合，得到目标空间方向。与此同时，接收机将快照间离散度、前导码前后段的方向漂移以及射频链路残余失配综合为包级方向不确定性，用于刻画目标信道估计在后续 payload 中的可信范围。

**竞争条件建模。**
对于与目标 payload 时间重叠的已检测包，SP\-Decoder利用其包级空间方向、相对强度和估计不确定性，近似描述竞争信号在目标方向及其正交子空间中的潜在能量分布。当多个包同时重叠时，接收机根据最不利的目标—竞争包关系配置判决器。该包级模型仅用于确定判决参数；实际符号恢复仍直接作用于包含全部干扰、频谱泄漏和复相干叠加的多天线 FFT 观测，因此无需预先判断某个错误峰由哪个干扰包产生。

**包级判决器配置。**
理想似然判决所需的目标一致和竞争 bin 统计参数无法在 payload 解码前直接获得。SP\-Decoder 因此利用前导码侧可观测的目标能量保留、竞争信号泄漏、相对强度和噪声水平构造可靠性感知的归一化区分度，并在目标假设保持有效的权重区间内选择有符号判决权重。该配置仅在目标包建立时执行一次，随后由整个 payload 共享，其计算开销不随 payload 长度或 FFT bin 数增长。

**固定有符号空间评分。**
包级权重确定后，SP\-Decoder 对目标包的全部 payload symbols 使用同一判决规则。对于每个符号，接收机分别在各天线上完成时间—频率补偿、dechirp 和 FFT，将每个候选 bin 投影到目标方向及其正交子空间，并通过支持能量与空间反证的有符号组合完成 top\-1 判决。所得符号随后进入标准 LoRa PHY 处理。

\<\!\-\- FIGURE 3 TODO: SP\-Decoder overview。只画三层：目标候选与稳健目标假设；竞争几何与每包一次 detector configuration；固定 signed top\-1 与标准 PHY。将前端具体检测流折叠成一个方框。CRC refinement 用虚线旁路，标注 lambda fixed。 \-\-\>

## 4\. 可靠性感知的 detector configuration

### 4\.1 符号级判决裕量

对目标包 $u$ 的第 $\ell$ 个 payload symbol，令真实目标 bin 为 $s=s_{u,\ell}$，任意竞争 bin 为 $k$。二者之间的 signed margin 为

$\Delta_{u,\ell,k}(\lambda)
=
D_{u,\ell}[s]-D_{u,\ell}[k].$

展开得到

$\Delta_{u,\ell,k}(\lambda)
=
A_{u,\ell,k}
+
\lambda B_{u,\ell,k},$

其中

$A_{u,\ell,k}
=
|P_{u,\ell}[s]|^2-|P_{u,\ell}[k]|^2$

是 MRC margin，而

$B_{u,\ell,k}
=
\|\mathbf Q_{u,\ell}[k]\|_2^2
-
\|\mathbf Q_{u,\ell}[s]\|_2^2$

表示竞争 bin 相对于真实 bin 的正交反证优势。

**命题 1（有符号翻转条件）。** 对给定的碰撞后 FFT 观测，真实 bin 的得分高于竞争 bin 当且仅当

$A_{u,\ell,k}+\lambda B_{u,\ell,k}>0.$

该结论直接作用于实际复 FFT 向量，多干扰叠加、频谱泄漏、相对相位和同 bin 交叉项均已包含在 $P$ 与 $\mathbf Q$ 中。它不依赖独立干扰假设。

当 $A<0$ 且 $B>0$ 时，MRC 错误但竞争 bin 暴露出更强反证，所需翻转权重为

$\lambda_{u,\ell,k}^{\mathrm{flip}}
=
-\frac{A_{u,\ell,k}}{B_{u,\ell,k}}.$

当 $A\ge0$ 且 $B<0$ 时，MRC 当前正确，但过大的反证权重会侵蚀该 pair 的裕量。该精确分解解释了动机实验中的 repair–damage 现象，也说明在线接收机不能使用逐符号 oracle 权重：真实 bin 在解码前未知，而同一 payload 内同时包含可修复和需要保护的判决。

### 4\.2 目标方向的可靠性建模

SP\-Decoder 的目标投影基由估计信道 $\widehat{\mathbf h}_u$ 构造。若 payload 阶段的真实信道方向偏离该估计方向，部分目标能量会泄漏到估计正交子空间，并可能被误解释为空间反证。因此，接收机需要同时刻画目标方向本身的可靠性，以及竞争包与目标方向的潜在匹配程度。定义两个非零复信道向量之间的射影夹角

$d(\mathbf h_1,\mathbf h_2)
=
\arccos
\frac{
|\mathbf h_1^H\mathbf h_2|
}{
\|\mathbf h_1\|_2\|\mathbf h_2\|_2
}.$

对于目标包 $u$，接收机根据重复前导快照估计目标方向的不确定性。具体而言，$\theta_{u,\mathrm{obs}}$ 描述前导快照相对于稳健信道中心的离散程度，$\theta_{u,\mathrm{drift}}$ 描述前导码前、后半段中心之间的方向漂移，$\theta_{\mathrm{rf}}$ 则用于吸收未被显式建模的固定射频链路失配。三者共同形成包级方向不确定性

$\theta_u
=
\min\left\{
\frac{\pi}{2},
\theta_{u,\mathrm{obs}}
+
\theta_{u,\mathrm{drift}}
+
\theta_{\mathrm{rf}}
\right\}.$

由此定义目标方向能量保留量

$L_u
=
\cos^2\theta_u.$

$L_u$ 表示在当前方向不确定性下，真实目标沿估计目标方向所能保留的能量比例 proxy。相应地，

$1-L_u
=
\sin^2\theta_u$

描述目标可能泄漏到估计正交子空间的能量比例。较大的 $L_u$ 表示目标方向稳定，接收机可以更积极地利用正交反证；较小的 $L_u$ 则意味着真实目标本身可能产生较强正交泄漏，应采用更保守的判决配置。

对于已检测竞争包 $v$，目标与竞争包的估计方向夹角为

$\widehat\theta_{uv}
=
d(
\widehat{\mathbf h}_u,
\widehat{\mathbf h}_v
).$

由于竞争包自身也存在方向不确定性 $\theta_v$，其真实方向可能相对于估计方向进一步靠近目标方向。因而，竞争包与目标方向之间的保守最小夹角近似为

$\theta_{uv}^{\min}
=
\max
\left\{
\widehat\theta_{uv}-\theta_v,
0
\right\}.$

据此定义竞争包沿目标方向的最大匹配度 proxy：

$U_{uv}
=
\cos^2
\theta_{uv}^{\min}
=
\cos^2
\left(
\max
\left\{
\widehat\theta_{uv}-\theta_v,
0
\right\}
\right).$

较大的 $U_{uv}$ 表示竞争包即使考虑方向不确定性，仍可能与目标方向高度匹配，因而容易在目标投影中形成强竞争峰；较小的 $U_{uv}$ 则表示竞争包更多能量可能暴露在目标正交子空间中。

为避免将目标自身的正交泄漏误判为反证，SP\-Decoder 要求目标在不确定性边界处仍保持正的 signed polarity：

$L_u-\lambda(1-L_u)\ge\gamma,$

其中 $\gamma>0$ 为全局目标保留项。由此得到

$0\le\lambda\le\lambda_{u,\mathrm{cap}},$

$\lambda_{u,\mathrm{cap}}
=
\min\left\{
\lambda_{\max},
\frac{L_u-\gamma}{1-L_u}
\right\}.$

若 $L_u\le\gamma$，当前目标假设不足以支撑可靠反证，接收机直接选择 $\lambda_u=0$。该区间限制的是目标假设的有效性，而不是人为缩小搜索空间；它使 detector 在空间信息可靠时使用额外判别力，在目标方向不稳定时自然退化为 MRC。

### 4\.3 包级归一化区分度

在 payload 解码开始前，接收机尚不知道每个 symbol 的真实 FFT bin，因此不能直接利用符号级判决裕量选择反证权重。SP\-Decoder 转而使用前导码阶段可观测的包级信道强度、方向稳定性和目标—竞争包空间关系，近似不同权重下的判决可分离程度。令

$S_u=\|\widehat{\mathbf h}_u\|_2^2,
\qquad
S_v=\|\widehat{\mathbf h}_v\|_2^2$

分别表示目标包 $u$ 与竞争包 $v$ 的 coherent strength proxies。它们由前导码稳健信道估计得到，用于描述两个包的整体接收强度。上一节定义的 $L_u$ 描述目标能量沿估计目标方向的保留比例，$U_{uv}$ 描述竞争包沿目标方向的潜在匹配程度。据此，将目标包和竞争包的包级能量近似分解为目标方向分量与目标正交分量：

$\begin{aligned}
E_{u,\parallel}&=S_uL_u,
&
E_{u,\perp}&=S_u(1-L_u),\\
E_{v,\parallel}&=S_vU_{uv},
&
E_{v,\perp}&=S_v(1-U_{uv}).
\end{aligned}$

相应的，目标相对于竞争包的包级判决裕量近似为

$\begin{aligned}
\mu_{uv}(\lambda)
&=
\left(
E_{u,\parallel}
-
\lambda E_{u,\perp}
\right)
-
\left(
E_{v,\parallel}
-
\lambda E_{v,\perp}
\right)\\
&=
A_{uv}
+
\lambda B_{uv},
\end{aligned}$

其中

$\begin{aligned}
A_{uv}
&=
S_uL_u-S_vU_{uv},\\
B_{uv}
&=
S_v(1-U_{uv})-S_u(1-L_u).
\end{aligned}$

仅比较 $\mu_{uv}(\lambda)$ 仍然不够，因为相同的平均裕量可能对应不同的噪声波动。为此，SP\-Decoder 对判决裕量进行噪声归一化。设白化后每个投影分支的 FFT 噪声为圆对称复高斯。对于 $z=\mu+n$、$n\sim\mathcal{CN}(0,\sigma^2)$，其能量方差满足

$\operatorname{Var}(|z|^2)
=
\sigma^4+2\sigma^2|\mu|^2.$

据此，目标方向能量差与正交方向能量差的方差分别近似为

$C_{0,uv}
=
2\sigma^4
+
2\sigma^2\left(S_uL_u+S_vU_{uv}\right),$

$C_{2,uv}
=
2\sigma^4
+
2\sigma^2\left[S_u(1-L_u)+S_v(1-U_{uv})\right].$

由于正交能量差在最终判决中被乘以 $\lambda$，其方差相应被放大为 $\lambda^2C_{2,uv}$。于是，SP\-Decoder 定义目标包 $u$ 相对于竞争包 $v$ 的归一化区分度

$R_{uv}(\lambda)
=
\frac{A_{uv}+\lambda B_{uv}}
{\sqrt{C_{0,uv}+\lambda^2C_{2,uv}}}.$

图 4 回答仅知道目标方向可靠性是否足以确定反证强度。对同一个实测目标，$L_u$ 均为 0.999，但空间上易分离和近共线的两个竞争包分别产生 $U_{uv}=0.014$ 和 1.000。结果表明，目标本身同样稳定时，竞争方向仍可将可利用的正交反证从充分变为几乎不存在；这与 $U_{uv}$ 刻画最坏竞争匹配度的机制一致。因此，包级配置必须保留目标--竞争包关系，而不能只按目标 SNR 或前导稳定度给出单包权重。

### 4\.4 有限候选点上的反证权重选择

对于每个竞争包 $v\in\mathcal I_u$，$R_{uv}(\lambda)$ 都给出一条随反证权重变化的 pair\-risk 曲线。在任意给定的 $\lambda$ 下，真正限制目标包可分离性的不是所有竞争关系的平均值，而是其中区分度最小的一个。因此，

$G_u(\lambda)
=
\min_{v\in\mathcal I_u}
R_{uv}(\lambda)$

是所有 pair\-risk 曲线的逐点最小值，也称为这些曲线的下包络。

图 5 回答时间重叠集合是否已经足以决定 $\lambda$。在一个目标与 10 个 payload 重叠包的实测几何中，不同竞争包对 $R_{uv}(\lambda)$ 施加的限制明显不同，决定下包络的最坏竞争包还会随 $\lambda$ 切换。原因是时间关系只决定谁进入 $\mathcal I_u$，而功率和空间方向决定每个成员在哪一段权重范围内最危险。该观察支持以逐 pair 最小值构造 $G_u(\lambda)$：接收机需要保留每个重叠包的约束，但不需要枚举其所有组合子集。

沿着 $\lambda$ 轴移动时，当前位于最下方的曲线对应最危险的竞争包。随着 $\lambda$ 改变，最危险竞争包的身份可能发生切换。SP\-Decoder 寻找下包络的最高点，即在目标安全约束允许的范围内，使最危险竞争关系尽可能容易区分的权重。SP\-Decoder 则希望将在线配置限制为每包一次、候选数量有界的有限点评估，因此候选集合同时包含单条曲线的解析结构点，以及用于覆盖多曲线切换区域的少量补充检查点。

对 $R_{uv}(\lambda)$ 求导可得

$\frac{\mathrm dR_{uv}}{\mathrm d\lambda}
=
\frac{B_{uv}C_{0,uv}-A_{uv}C_{2,uv}\lambda}
{(C_{0,uv}+\lambda^2C_{2,uv})^{3/2}}.$

当 $A_{uv}<0<B_{uv}$ 时，$\lambda=0$ 下该 pair 的近似判决裕量为负，而正交反证能够逐步改善该裕量。临界权重为

$\lambda_{uv}^{\mathrm{flip}}
=
-\frac{A_{uv}}{B_{uv}}.$

该点表示对该竞争包而言，反证强度首次足以抵消目标方向上的支持劣势。

当 $A_{uv}>0$ 且 $B_{uv}>0$ 时，目标在 $\lambda=0$ 下已具有正裕量，增加反证最初可以继续提高归一化区分度，但过大的 $\lambda$ 也会放大正交分支的噪声波动。令导数为零，得到内部 peak 点

$\lambda_{uv}^{\mathrm{peak}}
=
\frac{B_{uv}C_{0,uv}}
{A_{uv}C_{2,uv}}.$

该点对应单条 pair\-risk 曲线在安全区间内可能出现的内部最大值。$\lambda_{uv}^{\mathrm{flip}}$ 与 $\lambda_{uv}^{\mathrm{peak}}$ 的有效条件在 $A_{uv}$ 的符号上互斥，因此每个目标—竞争 pair 至多贡献一个有效解析候选。

单曲线解析点不能覆盖下包络的全部高值区域，因为下包络的最大值还可能位于两条曲线的交叉附近，即最危险竞争包发生切换的位置。为避免显式求解所有两两交点，SP\-Decoder 增加一个自适应中点和三个固定覆盖点。

为建模自适应中点，将任意 bin 的 signed score 改写为

$D[k]
=
(1+\lambda)\|\mathbf Y[k]\|_2^2
\left[
\frac{|P[k]|^2}{\|\mathbf Y[k]\|_2^2}
-
t
\right],
\qquad
t
=
\frac{\lambda}{1+\lambda}.$

因此，$t$ 是候选 bin 获得正分数所需的目标方向能量占比阈值，且

$\lambda=\frac{t}{1-t}.$

由于 $L_u$ 和 $U_{uv}$ 分别表示目标保留比例和竞争匹配比例，二者可直接在该阈值尺度上比较。令

$U_u^{\max}
=
\max_{v\in\mathcal I_u}U_{uv}.$

当 $U_u^{\max}<L_u$ 时，定义

$t_u^{\mathrm{mid}}
=
\frac{L_u+U_u^{\max}}{2},
\qquad
\lambda_u^{\mathrm{mid}}
=
\frac{t_u^{\mathrm{mid}}}
{1-t_u^{\mathrm{mid}}}.$

该点将空间一致性阈值置于目标保留程度和最强竞争匹配度之间，是一个具有几何意义的自适应候选，而非解析最优点。此外，接收机在安全区间内加入三个均匀覆盖点：

$\frac14\lambda_{u,\mathrm{cap}},
\qquad
\frac12\lambda_{u,\mathrm{cap}},
\qquad
\frac34\lambda_{u,\mathrm{cap}}$

三个固定检查点，以常数开销覆盖安全区间前部、中部和后部可能出现的曲线切换区域。

图 6 回答少量区间覆盖点能否捕获解析点之外的有用区域。对一个目标和两个干扰的受控机制案例，仅评估区间端点时 PRR 为 95.625%；加入 $\{1/4,1/2,3/4\}\lambda_{\mathrm{cap}}$ 后升至 99.375%，继续加密到 63 个内部点才达到 100%。结果表明，大部分收益来自覆盖区间内部，而最后的差异来自一个很窄的邻域；这与多条 pair 曲线切换可能形成内部高值区的解释一致。设计上，三个固定覆盖点提供了常数开销下的主要覆盖收益，密集网格只作为机制参考；由于在线目标是 $G_u(\lambda)$ 而不是真实 PRR，该案例不意味着候选越多时 PRR 必然单调上升。

综合区间端点、有效解析点、自适应中点和固定覆盖点，得到

$\begin{aligned}
\mathcal C_u
=
&\{0,\lambda_{u,\mathrm{cap}}\}\\
&\cup
\left\{
\lambda_{uv}^{\mathrm{flip}}
:
v\in\mathcal I_u,\;
A_{uv}<0<B_{uv}
\right\}\\
&\cup
\left\{
\lambda_{uv}^{\mathrm{peak}}
:
v\in\mathcal I_u,\;
A_{uv}>0,\;
B_{uv}>0
\right\}\\
&\cup
\{\lambda_u^{\mathrm{mid}}\}\\
&\cup
\left\{
\frac14\lambda_{u,\mathrm{cap}},
\frac12\lambda_{u,\mathrm{cap}},
\frac34\lambda_{u,\mathrm{cap}}
\right\}.
\end{aligned}$

接收机删除不满足定义条件的点，将剩余点限制在$[0,\lambda_{u,\mathrm{cap}}]$内，并按照数值去重。由于每个竞争包至多贡献一个解析点，候选数量满足$|\mathcal C_u|
\le
K_u+6$。最终选择

$\widehat\lambda_u
=
\arg\max_{\lambda\in\mathcal C_u}
G_u(\lambda).$

若多个候选取得相同的最坏 pair 区分度，则选择较小的 $\lambda$，以减少不必要的正交惩罚。

图 7 回答有限候选集是否会错过最坏 pair 下包络的有效峰值。该五包案例中，限制目标的竞争包随 $\lambda$ 多次切换，但有限算法仍在解析 stat 点选择 $\widehat\lambda_u=0.9530455$；离线 4,001 点参考搜索得到 0.95300。两者几乎重合，说明候选集能够同时覆盖单条曲线的解析结构和下包络切换附近的内部区域。其设计含义是，接收机可以用每包有界的风险评估替代密集搜索；这里比较的是同一个无真值目标 $G_u$，并不使用 payload、FEC 或 CRC 作为 oracle。

## 5\. 端到端接收器

### 5\.1 双通道白化与校准

前端输入为同步采集的双通道复基带序列 $\mathbf y[n]\in\mathbb C^2$。接收机在无包背景区估计 DC 向量和噪声协方差：

$\widehat{\mathbf d}
=
\frac{1}{N_0}\sum_{n=0}^{N_0-1}\mathbf y[n],$

$\widehat{\mathbf R}_n
=
\frac{1}{N_0}
\sum_{n=0}^{N_0-1}
(\mathbf y[n]-\widehat{\mathbf d})
(\mathbf y[n]-\widehat{\mathbf d})^H
+
\epsilon\mathbf I.$

令 $\mathbf W$ 满足

$\mathbf W\widehat{\mathbf R}_n\mathbf W^H
=
\mathbf I_2,$

白化信号为

$\widetilde{\mathbf y}[n]
=
\mathbf W(\mathbf y[n]-\widehat{\mathbf d}).$

接收器以采集开头配置为无包的区间（默认 $3$ s；至少 $128$ 个复采样）估计上述量；实验采集必须保证该区间不含业务信号，否则 DC、噪声底和白化方向都会受污染。FFT-bin 噪声方差按未归一化 $M$ 点 FFT 的定义换算为 $\widehat\sigma^2_{\rm FFT}=M\widehat\sigma_t^2$。白化统一两个射频通道的噪声尺度，使目标方向、正交能量和第 4 节的噪声 proxy 在同一坐标系中定义。

双通道静态幅相校正是一个可选的、与白化不同的步骤。若部署时已用功分器将同一校准 LoRa/CW 信号注入两路接收链，则可在同一中心频率、采样率和 RX gain 下估计相对复增益 $\mathbf c=[1,\hat g_2/\hat g_1]^T$，并在白化前施加 $y_i[n]\leftarrow y_i[n]/c_i$。当前离线实测数据的默认路径不施加这一额外校正；因此下文的 $\theta_{\rm rf}=0.02$ rad 是保守的固定裕量，而非由本批 IQ 自动估得的校准残差。若启用实测校准，应在独立保留的校准帧上取校正后方向相对理想共模方向 $[1,1]^T$ 的 $95\%$（或更高）角误差分位数，并以该值替换固定裕量。

### 5\.2 结构辅助同步与信道估计

在普通长采集中，接收机可先使用双通道平均能量定位 busy regions；该步骤仅用于搜索剪枝，且只有噪声底可由无包采样可靠估计时才启用。正式评测的连续业务窗口则直接扫描整段 IQ：高占空比碰撞会污染窗口内的低分位能量估计，若据此预筛，弱帧可能在进入结构检测前被静默丢弃。

每个扫描流都以归一化 chirp 匹配滤波产生结构候选；归一化分母使用当前窗口能量，因此白化后恒包络 LoRa chirp 不依赖原始幅度门限。对每个候选，接收机利用重复 preamble upchirp 与两段完整 SFD downchirp 对 timing offset 的相反响应分离 coarse CFO 和 coarse timing。令重复 upchirps 与完整 SFD downchirps 的中位峰位置分别为 $z_\uparrow$ 和 $z_\downarrow$，则

$z_\uparrow\approx\nu+\xi,
\qquad
z_\downarrow\approx\nu-\xi,$

其中 $\nu$ 为以 LoRa bin 表示的 CFO，$\xi$ 为 timing\-induced bin shift。因此

$\widehat\nu_{\mathrm{SFD}}
=
\frac{z_\uparrow+z_\downarrow}{2},
\qquad
\widehat\xi
=
\frac{z_\uparrow-z_\downarrow}{2}.$

前端据此修正候选起点，并在 CFO 补偿后重新验证 sync word 和 SFD 残差。整数 FFT bin 的半和/半差解存在耦合的 start--CFO 别名：CFO 改变一个 bin 时，起点也须同步移动一个 OSR。接收机枚举中点附近常数个整数分支，并仅以 preamble、sync word 与 SFD 的联合分数选取代表分支。

可选的前导相干细化会利用重复前导间的相位演化评估信道统计。设第 $p$ 个前导窗口的双通道复向量为 $\mathbf z_p$，对候选相位斜率 $\epsilon$，相位对齐快照为

$\widetilde{\mathbf z}_p(\epsilon)
=
\mathbf z_p e^{-j2\pi\epsilon p}.$

接收机在常数规模候选集合上最大化跨前导相干累积与方向一致性的联合指标，以获得稳定的前端信道中心。实测 B210 中该跨 chirp 相位斜率还会包含采样时钟漂移，故它只服务于可选的前导相干评分和信道统计；正式 payload 解调仍使用 SFD 选定的整数 CFO 分支，而不把该斜率直接当作 within-symbol 的连续 CFO。候选按照时间、CFO 和归一化信道方向联合去重；时间和 CFO 接近但空间方向不同的候选被保留为并发目标。

#### 5.2.1 正式评测的全窗匿名高召回同步

上述描述给出了一个已检测轨道的同步方法。正式 PRR 评测还需要在同一段 IQ 中为所有方法建立一份公共、匿名的物理候选库；因此，实际前端不是从 manifest 的节点时刻逐包启动，而是在严格业务窗口（Fig.9--13 当前为居中 5 s）上执行如下全局检测。检测器的输入只有白化后的双通道 IQ、PHY 参数和窗口边界。manifest 只用于定位该业务窗口、配置 PHY，并在检测完成后记录计划发包数这一统计参考；它不提供候选起点、节点身份、序号、payload、CRC 或候选数上限。

**多空间流和迭代零陷。** 第 0 轮同时扫描两条原始天线流、双通道协方差的 PCA 投影流，以及最弱 PCA 方向的 residual 流。对每一条流，前端以归一化匹配滤波分别搜索 upchirp 和 downchirp；归一化分母为该窗口的瞬时能量，避免白化后恒包络 chirp 因原始能量门限而被遗漏。完成一轮物理候选认证后，对每个空间方向明显不同的既有候选 $\mathbf h=(h_1,h_2)^T$ 构造归一化零陷流

$$r_{\mathbf h}[n]
=
\frac{[-h_2,\ h_1]\mathbf y[n]}
{\|[-h_2,\ h_1]\|_2},$$

并与原始/PCA 流一起重新扫描完整窗口。该操作使已经较强的候选在其自身空间方向上被压低，从而暴露时间接近但空间方向不同的弱前导。每轮重新认证并合并候选，直到不再出现新的物理候选为止。这里不重建、不抵消 payload，也不对已认证帧头做波形相减；零陷仅产生额外的检测观测流，因而不会把某个候选的 payload 假设泄露给发现过程。

**两个互补的结构种子。** 第一条路径从 downchirp 匹配滤波峰中取相隔一个符号的 SFD 对，且只把该对的第一个 downchirp 作为起点锚点。该锚点还必须在其之前找到相位一致的完整前导 upchirp 链。第二条路径专门补偿 SFD 被强包淹没的情形：直接寻找间隔为一个符号的连续 upchirp 峰链。正式高召回配置中，upchirp 的归一化相关至少为 $0.55$，连续链至少含 6 个 chirp；完整八 chirp 链直接给出唯一的前导首符号，较短链才展开有限个首符号假设，随后交给相同的 SFD/CFO 认证。两条路径取并集，且不按候选分数作 top-$K$ 截断，也不让较强峰占用同一粗时间桶的配额。因此，多个时间相近的弱结构假设会同时进入后续认证。

**独立 SFD/CFO 认证与整数别名消解。** 对每个结构种子，前端在其附近一个符号的局部范围内重新测量前导与两段完整 SFD，而不直接信任种子阶段的 CFO。设重测到的前导和 SFD bin 中位数为 $z_\uparrow$ 与 $z_\downarrow$，则先取

$$\widehat\nu=\frac{z_\uparrow+z_\downarrow}{2},
\qquad
\widehat\xi=\frac{z_\uparrow-z_\downarrow}{2},
\qquad
\widehat\tau=\tau_{\rm seed}-\widehat\xi\,\mathrm{OSR}.$$

随后在 $\widehat\nu$ 补偿后检查 SFD 残差，并要求 CFO 落在预设物理范围内、起点修正不超过 $0.8T_s$、完整帧头仍位于 IQ 窗口中。整数 FFT bin 会形成耦合的 start--CFO 别名：CFO 改变一个 bin 时，起点须同步移动一个 OSR。实现枚举中点附近常数个整数 CFO 分支及其对应起点，以 preamble、sync word 与 SFD 的固定-CFO 联合分数选择分支；这一步避免把正确波形锁到半 bin 残差的中点上。

认证后计算三项彼此独立的帧头证据：前导峰/谱底比、两个 sync word 的局部峰/谱底比、两个 SFD 的局部峰/谱底比，以及它们的对数联合结构分数。严格证书阈值分别为 $1000$、$64$、$128$ 和 $10$。这些阈值只标记强结构证据、用于审计和同一物理别名的代表选择，**不是**高召回候选的准入门限；只要一个种子通过上述 SFD/CFO 物理认证，即使其完整帧头证书较弱，也会作为匿名候选保留。若三项局部证据至少为 $8$、$2$、$2$，接收机还会在固定 CFO 下做两级小范围起点细化：先在 $\pm T_s/4$ 内以 $T_s/32$ 步长搜索，再在 $\pm T_s/32$ 内以 $T_s/256$ 步长搜索。细化失败或未触发不会删除已经 SFD 锚定的候选。

**物理级去重和停止条件。** 候选只有在起点相差不超过 $0.05T_s$、CFO 相同或满足已知的整数别名关系、且双通道方向高度一致时才会视为同一物理帧。去重采用 complete-link：一个候选必须与簇内每个成员都满足该条件，才可并入该簇；这避免由链式近邻把两个独立碰撞包错误合并。普通同 CFO 别名要求方向 coherence 至少为 $0.98$；$1$--$3$ 个 bin 的耦合整数别名要求 CFO 误差不超过 $0.10$ bin 且 coherence 至少为 $0.95$。仅在同一别名簇内以结构分数选择代表，绝不跨物理候选按分数淘汰。重扫时重新认证可能把早期的两个算法别名合并为一个候选；候选数不增即表示达到固定点，而不是检测失败。

候选数据库允许检测数大于窗口内计划发包数。计划数只在后续 PRR 的分母审计中使用；节点和序号只有在某个候选的 payload 通过 CRC 且能唯一识别后才绑定。这一高召回策略把“是否确有可解的包”交由后续的 FEC/CRC 闭合，而不在同步阶段以未知 payload truth 或发包表提前删除弱假设。

### 5\.3 稳健包级空间统计

前端信道用于候选验证，SP\-Decoder 进一步从重复前导构造适合最终判决的稳健空间统计。对目标包 $u$ 的第 $p$ 个前导窗口，在最终 CFO 最接近的整数 bin 中心附近聚合多 bin 复快照：

$\mathbf g_{u,p}
=
e^{-j2\pi\widehat\epsilon_u p}
\sum_{d=-2}^{2}c_d
\mathbf Z_{u,p}[k_0+d],$

其中实机部署的五 bin 核为

$[c_{-2},c_{-1},c_0,c_1,c_2]
=
[0.12,0.45,1,0.45,0.12].$

多 bin 聚合降低 fractional CFO 和微小 timing residual 导致的单 bin 波动，同时保留双通道复方向。令 $E^{\rm loc}_{u,p}$ 为五个局部 bin、两根天线上的总能量，$E^{\rm all}_{u,p}$ 为该窗口完整频谱能量；先计算 isolation $\iota_{u,p}=E^{\rm loc}_{u,p}/E^{\rm all}_{u,p}$，并将其截断到不低于该包的 $25$ 分位数。初始权重为 $w^{\rm iso}_{u,p}=\iota_{u,p}/\max_q\iota_{u,q}$，初始中心为

$$
\bar{\mathbf h}_u
=
\frac{\sum_p w^{\rm iso}_{u,p}\mathbf g_{u,p}}
{\sum_p w^{\rm iso}_{u,p}}.
$$

对每个快照计算射影角残差 $\alpha_{u,p}=d(\mathbf g_{u,p},\bar{\mathbf h}_u)$，再以

$$
w_{u,p}
=
\max\!\left\{
w^{\rm iso}_{u,p}
\exp\!\left[-\left(\frac{\alpha_{u,p}}{0.35}\right)^2\right],
10^{-6}
\right\}
$$

抑制方向离群的前导窗口，最终得到

$\widehat{\mathbf h}_u
=
\frac{\sum_p w_{u,p}\mathbf g_{u,p}}
{\sum_p w_{u,p}},$

$S_u
=
\|\widehat{\mathbf h}_u\|_2^2.$

这一步只使用已同步的前导 IQ，不读取 payload bin、FEC 或 CRC。它既能降低碰撞污染的影响，也保留所有前导快照以产生下述不确定性度量，而不是以 hard trimming 丢弃窗口。

图 8 回答局部多 bin 聚合能否在前导部分受碰撞时稳定空间方向。该机制案例将两段实测波形以 SIR $=-6$ dB、相对起点 $3.35T_s$ 叠加，使目标的前三个前导窗口保持干净、后五个窗口受到更强包污染。碰撞开始后，单个偏移 bin 的方向误差明显增大并分布在参考方向两侧，而五 bin 聚合 $\mathbf g_p$ 仍比任一局部快照稳定。该趋势与谱泄漏、fractional CFO 和残余定时在相邻 bin 间分散的解释一致：对局部频谱加权聚合可以抵消部分单 bin 偏差，随后包级权重再降低受污染窗口的影响。因而最终信道估计不应依赖单个前导窗口或单个 FFT bin；该图用于解释机制，不把这个选定 pair 的改善幅度外推为总体性能。

**方向不确定性的实际获得。** 观测项以 leave-one-out 重估计衡量。对每个前导快照 $p$，从上述加权和删去该快照得到 $\widehat{\mathbf h}^{(-p)}_u$，并计算 $\delta_{u,p}=d(\widehat{\mathbf h}^{(-p)}_u,\widehat{\mathbf h}_u)$。有至少四个快照时，

$$
\theta_{u,\mathrm{obs}}
=
Q_{0.8}\{\delta_{u,p}\}_p;
$$

否则实现保守回退为 $0.35$ rad。因而该量严格来说是“估计对单个前导观测的敏感度”，而不是 payload 真值下的方向误差。将时间序列按中点分为早、晚两组，使用相同权重分别求 $\widehat{\mathbf h}^{\rm early}_u$ 与 $\widehat{\mathbf h}^{\rm late}_u$，并取

$$
\theta_{u,\mathrm{drift}}
=
d(\widehat{\mathbf h}^{\rm early}_u,
\widehat{\mathbf h}^{\rm late}_u).
$$

当前实现取 $\theta_{\rm rf}=0.02$ rad（约 $1.15^\circ$）作为未显式建模的双通道射频残余安全裕量；其可替换为第 5.1 节所述独立校准验证集的高分位残差。最终可靠性为

$$
\theta_u
=
\min\!\left\{\frac{\pi}{2},
\theta_{u,\mathrm{obs}}+\theta_{u,\mathrm{drift}}+\theta_{\rm rf}\right\},
\qquad
L_u=\cos^2\theta_u.
$$

根据包时间区间构造重叠集合

$\mathcal I_u
=
\left\{
v\ne u:
\tau_v<\tau_u^{\mathrm{end}},
\;\tau_v^{\mathrm{end}}>\tau_u^{\mathrm{pay}}
\right\}.$

只有与目标 payload 实际重叠的候选参与 detector configuration。包级 $\widehat\lambda_u$ 确定后，对目标包的全部 payload symbols 保持不变。第 $\ell$ 个 symbol 按照目标连续起点截取窗口，补偿最终选定的 SFD CFO 分支，并在两根天线上分别 dechirp 和执行 FFT，得到 $\mathbf Y_{u,\ell}[k]$。随后计算

$P_{u,\ell}[k]
=
\widehat{\mathbf a}_u^H\mathbf Y_{u,\ell}[k],$

$Q_{u,\ell}[k]
=
\widehat{\mathbf b}_u^H\mathbf Y_{u,\ell}[k],$

$D_{u,\ell}[k]
=
|P_{u,\ell}[k]|^2
-
\widehat\lambda_u|Q_{u,\ell}[k]|^2,$

并输出

$\widehat s_{u,\ell}
=
\arg\max_kD_{u,\ell}[k].$

全部符号进入标准 LoRa Gray demapping、deinterleaving、Hamming FEC、dewhitening、explicit\-header 解析和 PHY CRC。

### 5\.4 CRC 触发的有界同步重试

主路径 `SP-Core` 对每个匿名物理候选只使用一次前端输出、一次包级 $\widehat\lambda_u$ 和一次完整 payload 解码。只有主路径未闭合 CRC，且该候选同时具有独立的 preamble/sync/SFD 结构证据以及符合固定 PHY profile 的 explicit header 时，`SP+sync-refine` 才执行局部 start/CFO 重试。这一门控避免对随机 payload 假设做盲目搜索；它不读取 manifest、身份或预期 payload。

围绕前端连续起点，接收机依次尝试

$$
\Delta\tau\in
\{-2,-1,-3,-0.5,-1.5,-2.5,-3.5,
0.5,1,2,3,4,-4,0\}
$$

个采样点。该顺序把实测中较常见的轻微 late-window 偏差放在前面。对每个起点，再从

$$
\widehat\nu,
\quad \widehat\nu\pm0.1,
\quad \widehat\nu\pm0.2,
\quad \widehat\nu\pm0.3,
\quad \operatorname{round}(2\widehat\nu)/2,
\quad \operatorname{round}(\widehat\nu),
\quad \widehat\nu\pm0.5,
\quad \widehat\nu\pm1
$$

中去重后依次取 CFO。每个 trial 都重新估计局部前导信道并重跑 signed top-1、FEC 和 CRC；累计次数（包括首次 SP-Core）最多为 $32$，一旦 CRC 闭合即停止。整个过程中 $\widehat\lambda_u$ 保持为 payload 到达前配置的原值，CRC 只接受或拒绝一个同步 trial，绝不用于重新选择 $\lambda$。因此该阶段应报告为“固定包级权重的 CRC-triggered bounded start/CFO refinement”，而不是 payload-blind 前端同步或新的干扰消除机制。

正式对比中，所有基线首先共享同一匿名物理候选及其 pre-payload fine start/CFO/STO 种子；PCube 和 MaLoRaGW 可在该种子附近运行各自论文原生的、仅依赖 preamble/sync/SFD 的有界局部重估。比较方法既不接收 SP 的 payload CRC 所选同步点，也不接收 SP 的 $\widehat\lambda_u$ 或空间残差信息。

### 5\.5 复杂度

令第 $r$ 次全窗发现中的检测流数为 $J_r$、窗口采样数为 $N$、结构提议数为 $H_r$，$P$ 为前导 chirp 数。滑动 downchirp/upchirp 相关的代价为

$$
O\!\left(\sum_r J_rN\log N\right),
$$

而每个提议的 SFD/CFO 认证、帧头复核与可选两级固定-CFO 起点细化只在常数大小局部范围内执行，代价为

$$
O\!\left(\sum_r H_rPM\log M\right).
$$

第 $0$ 轮使用原始双天线、PCA 与 minor-direction residual 流；后续轮额外加入至多 8 条相互空间可分的零陷流，并在没有新增物理候选时停止。普通长采集若启用能量预筛，则将上述 $N$ 替换为各 busy region 的长度之和；正式全窗评测不以能量门限删减候选。

对目标包 $u$，候选集合规模满足 $|\mathcal C_u|\le K_u+6$，其中 $K_u=|\mathcal I_u|$。当前实现对每个候选权重评估全部 pair risks，因此包级配置为

$O(K_u|\mathcal C_u|)
=
O(K_u^2).$

该开销每包执行一次，与 payload 长度和 FFT bin 数无关。设 payload 含 $L_{\mathrm{pay}}$ 个 symbols，逐符号阶段复杂度为

$O\left(
L_{\mathrm{pay}}[M\log M+M]
\right).$

因此，在目标候选已经建立后，SP\-Decoder 后端复杂度为

$O\left(
K_u^2
+
L_{\mathrm{pay}}M\log M
\right).$

它不重构干扰波形，不按用户顺序重复执行 SIC，也不进行指数级 symbol 组合搜索。

## 6\. 评估

### 6\.1 方法

LoRa节点。SF10、BW125 kHz、CR4/5；

实验设置。室内室外，低传输速率

指标。\(1\)PRR，\(2\)吞吐量，\(3\)SER。

为了描述真实碰撞强度，对目标包 uuu 定义 payload 期间的实际碰撞重数：

$m_u
=
1+
\left|
\left\{
v\ne u:
v\text{ 与 }u\text{ 的 payload 时间重叠}
\right\}
\right|.$

比较。LoRaWAN、MRC、CIC、PCube、MaLoRaGW

### 6\.2 空气信道测量

双天线信道 $\mathbf h=[h_0,h_1]^T$ 同时包含总增益、天线间相对幅度和相对相位。复射影角

$$
d(\mathbf h_1,\mathbf h_2)=
\arccos\frac{|\mathbf h_1^H\mathbf h_2|}
{\|\mathbf h_1\|_2\|\mathbf h_2\|_2}
$$

适合第 4–5 节的空间投影方向分析。本实验的目的正是验证 SP 所依赖的空间方向是否稳定，因此三个子图统一以 degree 报告方向偏差，不再把增益和原始相对相位拆成额外子图。为保留参考方向两侧的信息，实验使用与图 8 相同的带符号射影角

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

该定义满足 $|\Delta\psi|=d$，所以完全保留原射影角误差的大小，同时增加正负方向。评价估计精度时应观察 $|\Delta\psi|$ 或分布宽度，而不能只看可能因正负抵消而接近零的有符号均值或中位数。

包内相干性实验直接读取单节点实测 run `run_02000001` 中 23 个 CRC-valid 完整包。该 PHY 配置包含 8 个前导 chirp、2 个 sync chirp、2.25 个 SFD chirp和 33 个 payload chirp，整帧长度为 $45.25T_s$。我们在每包的 45 个完整 chirp 上估计复信道：窗口起点为 $0,\ldots,11T_s$ 与 $12.25,\ldots,44.25T_s$；末个完整 SFD 窗口与首个 payload 窗口之间相隔 $1.25T_s$，末尾 $0.25T_s$ SFD 片段不被错误地当作完整 chirp。为避免由异常包主导图形，先仅依据无噪整帧的第 90 百分位增益离散度和天线间相位离散度，从 23 个包中固定选出 8 包质量池；这一筛选不读取后续加噪或碰撞结果。

随后仅在已经正确检测并对齐的完整包上加入独立复高斯噪声，扫描 $-10$、$-5$、0、5、10、15 和 20 dB，每包每档重复 8 次，共获得 $8\times7\times8=448$ 个包级估计。这里显式区分两种测量口径。图 (a) 和图 (b) 的目的是观察物理包内相干性，因此利用已知正确 FFT bin 提取 45 个逐 chirp 空间快照；这是一项 oracle\-bin 信道测量，不声称是在线前端输出。两图使用同一个 $-10$ dB 代表包：在预先固定的 8 包质量池内，选择包内第 90 百分位绝对方向偏差最小的 realization，若并列再按包级绝对方向误差选择。散点覆盖 preamble、sync、两个完整 SFD chirp 和 33 个 payload chirp；图 (a) 的纵轴固定为 $[-20^\circ,20^\circ]$，避免局部起伏占满画布。图 (c) 则真正调用生产接收路径中的 `robust_preamble_channel_sp`，仅从八个含噪前导窗口估计包级 $\widehat{\mathbf h}_u$，并与同一 collision\-free 包由相同前端得到的参考方向比较。$-10$ 至 20 dB 下，生产前端方向误差绝对值的中位数依次为 $2.60^\circ$、$1.45^\circ$、$0.65^\circ$、$0.40^\circ$、$0.25^\circ$、$0.14^\circ$ 和 $0.08^\circ$；90 分位依次为 $6.75^\circ$、$3.18^\circ$、$1.80^\circ$、$0.79^\circ$、$0.50^\circ$、$0.26^\circ$ 和 $0.19^\circ$。这一拆分使图 (a–b) 回答“物理信道是否在包内稳定”，图 (c) 回答“现有前端能否从含噪前导恢复该方向”，两者不再混用。

新增图 (d) 验证 collision-free 条件下的小方向误差是否会破坏解码。以实测 $\mathbf h_{\rm clean}$ 为基准，沿复射影空间构造误差为 $-7.5^\circ,-5^\circ,-2.5^\circ,0^\circ,2.5^\circ,5^\circ,7.5^\circ$ 的 $\widehat{\mathbf h}$，并用于 $D[k]=|P[k]|^2-4|Q[k]|^2$ 的完整 payload top-1。SNR 与本文其余 AWGN 实验保持一致，定义为**解啁啾前**目标波形平均功率与时域复采样 AWGN 功率之比；代码直接按该 SNR 注噪，不再额外扣除 FFT 处理增益。每个点聚合 8 个实测包、每包 8 次独立噪声实现，共 2,112 个 payload 符号；同一次噪声实现跨七个方向误差点配对复用。结果显示，在输入 SNR 为 $-10$ 至 10 dB、方向误差不超过 $\pm7.5^\circ$ 时均未观察到符号错误。该结果符合 SF10 解啁啾的处理增益，也说明单用户场景中的小方向偏差并不是主要错误源。相应地，本图不能用来证明碰撞下的方向失配鲁棒性；该问题应由后续 trace-driven 并发信道实验回答。由于加噪发生在已检测包之后，本实验也不构成低 SNR 前端检测结论。

并发信道测量的 target 复用 Node02 八包质量池，而 interferer 从 PHY 参数完全相同的 Node01 和 Node03 单节点实测包中抽取。固定种子生成 8 个跨节点有序 pair，并在所有 SIR 和 FFT-bin 间隔单元复用。干扰包错开 $1T_s$ 后离线相加；SIR 取 $-5$、$-2$、0、2 和 5 dB，FFT-bin 间隔取 0、2、4、8 和 16，共形成 $5\times5\times8=200$ 个 trace-driven 碰撞。为控制版面，图 (a)–(c) 只展示 $-5$、0 和 5 dB 三个代表性 SIR 下的带符号方向误差，而图 (d) 使用全部五档 SIR。$-5$ dB SIR 下，五个间隔的 $|\Delta\psi|$ 中位数为 $24.067^\circ$、$16.450^\circ$、$7.425^\circ$、$3.340^\circ$ 和 $1.608^\circ$；0 dB 下为 $13.824^\circ$、$11.255^\circ$、$4.951^\circ$、$2.286^\circ$ 和 $1.108^\circ$；5 dB 下为 $8.955^\circ$、$7.033^\circ$、$3.053^\circ$、$1.398^\circ$ 和 $0.674^\circ$。

图 (d) 将五档 SIR 下碰撞前导估计得到的 $\widehat{\mathbf h}$ 用于完整 payload 的有符号 top-1 压力测试，不绘制逐 pair 散点。SIR=$-5$ dB 时，0、2、4、8 和 16 bin 的 SER 为 73.86%、85.23%、24.24%、12.50% 和 12.12%；SIR=$-2$ dB 时为 46.59%、60.61%、12.50%、1.52% 和 0；SIR=0 dB 时为 25.00%、1.14%、0.38%、0 和 0；SIR=2 dB 时为 25.00%、0、0.38%、0 和 0；SIR=5 dB 时全部为 0。0 与 2 bins 均落在五 bin 局部估计核的强混叠区，SER 不要求在二者之间单调；当间隔达到 4–16 bins、干扰逐步离开该局部核后，方向误差和 SER 才整体快速下降。尤其在 8–16 bins 时，即使目标比干扰弱 2 dB，碰撞前导估计仍足以使 SER 接近或达到 0。该图不替代第 6.4 节使用包级 $\widehat\lambda_u$、FEC/CRC 和 PRR 的端到端结果。

### 6\.3 有限候选集的覆盖与配置开销

**实验目标。** 该实验检验在线配置 $\widehat\lambda_u$ 时，各类有限候选是否会在真实的竞争几何中承担不可替代的角色，以及生产有限集相对以 10,000 个均匀内点替换三个固定点的高代价对照，能否保持相同的符号恢复质量并降低配置时间。它不以 payload 结果反选候选或场景。

**设置。** 第一部分用固定种子构造 30,000 个受控多包场景。每场从 26 个实测双通道包的方向和可靠性锥中无放回抽取一个目标和 1--5 个竞争包；各竞争包的声明 SIR 独立均匀取自 $[-8,12]$ dB，目标 SNR 均匀取自 $[10,30]$ dB。生产策略的候选并集为区间端点、pair-specific flip/peak 点、可靠极性自适应中点和三个固定均匀内点；对照策略保留端点、解析点和中点，仅以 10,000 个均匀内点替换三个固定点。两种策略均只比较前导统计给出的 $G_u(\lambda)$，不读取 payload、SER、PRR 或 CRC。

第二部分单独抽取固定种子的 10 个实测 IQ trace 场景用于核验 SER 与配置时延。每场把两个实测双通道包按声明 SIR 和非整数相对起点在复基带相加，不注入合成 AWGN；两种候选策略共享同一碰撞波形和目标前导信道估计。clean target 的 symbol bins 仅在权重确定后用于离线计算 SER。每场候选构造和下包络选择重复 500 次后取均值；前导估计和 payload 判决因对两者完全相同而不计入该配置时间。

**结果分析。** 在 30,000 个场景中，生产有限集的赢家来源依次为：区间端点 53.64%、解析 flip/peak 点 38.64%、自适应中点 0.36% 和三个常数点 7.36%。把三个常数点改为 10,000 个后，端点、解析 flip/peak 和密集常数点分别为 52.18%、36.03% 和 11.79%，中点为 0%。因此，解析点不是均匀检查点的重复；即使高密度网格可用，它仍在超过三分之一的竞争场景中直接赢得 $G_u(\lambda)$。十个实测 IQ trace 场景中，两种策略的平均 SER 均为 15.26%，而生产有限集的平均配置时间为 0.650 ms/场景，10,000 点对照为 1.338 ms/场景，即后者约为前者的 2.06 倍。

**对系统的影响。** 在线接收机只需计算与竞争包数平方同阶的小候选集，而不必在 payload 前扫描稠密网格；端点覆盖可靠性约束，解析 flip/peak 覆盖单 pair 的关键极值，少量几何与固定点补足 pair 切换附近的包络区域。10,000 点策略仅作为离线压力对照，不应进入实时路径。30,000 场统计证明候选来源的覆盖角色，10 场 trace 场景证明该压缩在实测波形上没有观察到 SER 损失并减少配置开销；端到端 FEC/CRC/PRR 与多包并发收益仍由下一节的并行解码实验承担。

### 6\.4 并行解码性能

可扩展性性能。在室内环境中依次启用 1、3、6、9、12 和 15 个节点。各节点保持相同的平均发包速率，因此更大的节点数量对应更高的 offered load。

\<\!\-\- FIGURE 9\(a\) TODO: 横轴为活跃节点数 N=\{1,3,6,9,12,15\}，纵轴为端到端 PRR。 比较标准 LoRaWAN、MRC、CIC、PCube、MaLoRaGW 和 SP\-Decoder。 显示三轮实验的 95% 置信区间。 \-\-\> 

\<\!\-\- FIGURE 9\(b\) TODO: 横轴为活跃节点数，纵轴为聚合 吞吐量。 使用与 Fig\. 9\(a\) 相同的方法和实验轮次。 \-\-\> 

将全部目标包按照

$m_u=1,\quad 2,\quad 3,\quad 4,\quad \geq5$

分组。

\<\!\-\- FIGURE 9\(c\) TODO: 横轴为目标包实际碰撞重数，纵轴为 PRR。 比较 MRC、PCube 和 SP\-Decoder。 每个分组下方标注样本数量。 \-\-\> 

**共享检测下的解码开销与 SER。** 为把载荷算法差异与粗检测召回解耦，图 11 先由 SP 前端产生一份公共包列表。LoRaWAN 与 MRC 直接复用 SP 的精 start/CFO/STO/信道参数；CIC、PCube 与 MaLoRaGW 只获得量化到 $T_s/8$ 的粗起点，并在对应局部窗口内执行各论文的精同步和参数估计。公共前端不向任何基线暴露 payload FFT、符号判决、FEC、CRC 或 $\lambda_u$。我们从 10 个不同实测位置提取双通道信道方向与 CFO，并承载具有已知发送符号和有效 CRC 的标准 PHY 帧。对 $N\in\{2,4,6,8\}$，包起点以约 $4.25T_s$ 的间隔略微扰动后均匀错开；首末跨度分别为 $4.25T_s$、$12.75T_s$、$21.25T_s$ 和 $29.75T_s$，均小于 $45.25T_s$ 的帧长，且任意两个起点在 ADC 采样域均不相差整数个 chirp。由此四种规模的最大同时前导数均为 2，同时仍保留显著的 payload 碰撞。

图 11(a) 仅统计同步参数产生后每个候选包进入载荷解码器的墙钟时间。预处理、公共检测以及各方法的 start/CFO/STO/信道细化均不计时；SP 的包级 $\lambda_u$ 配置、各基线的 method-specific context 构造和 payload 判决计入时间。每个 $N$ 使用 4 个独立场景，每场景重复计时 3 次，先取场景内中位数，再以场景为统计单元计算 95% 置信区间。SP-Decoder 在 2、4、6 和 8 包时分别耗时 99.9、87.0、85.9 和 64.3 ms；MRC 为 153.2、86.8、99.0 和 65.7 ms，LoRaWAN 为 123.7、87.9、87.9 和 60.3 ms，CIC 为 426.7、313.4、339.2 和 239.8 ms，PCube 为 199.0、118.8、129.9 和 85.1 ms，MaLoRaGW 为 427.2、319.5、308.5 和 226.0 ms。SP-Decoder 的开销与非迭代 MRC/LoRaWAN 同阶，并显著低于需要更复杂上下文处理或干扰恢复的三种并发基线。

图 11(b) 在同一批场景上报告共享检测后的严格 SER；某方法若不能从粗起点完成精参数估计，整包按 SER=1 计入。真值只在所有解码结束后用于一对一匹配，不参与检测、同步或候选选择。SP-Decoder 在 2、4、6 和 8 包时的 SER 分别为 0、0.0019、0.0025 和 0.0095；使用相同精同步和信道参数的 MRC 分别为 0、0、0.0051 和 0.0133。LoRaWAN 在四种规模下为 0.0227、0.1818、0.4040 和 0.4100，CIC 为 0.0455、0.0966、0.2311 和 0.2898，PCube 为 0、0.1402、0.1730 和 0.3059，MaLoRaGW 为 0、0.2008、0.2134 和 0.3655。由于 MRC 与 SP 使用完全相同的前端参数，两者在 6/8 包下的差异直接来自有符号空间判决，而不是同步优势；2/4 包处接近零的 SER 同时表明 SP 不会在轻度碰撞下系统性损伤正确符号。

<!-- FIGURE 11(a) DONE: real_usrp_outputs/fig11_trace_runtime/fig11_decoder_time.pdf。共享检测和全部同步/参数估计时间排除，只计 decoder 配置与 payload 判决。 -->
<!-- FIGURE 11(b) DONE: real_usrp_outputs/fig11_trace_runtime/fig11_decoder_ser.pdf。LoRaWAN/MRC 共享 SP 精参数；CIC/PCube/MaLoRaGW 从 SP 粗起点执行论文内精估计；精估计失败按 SER=1；无 oracle 信息进入接收器。 -->

节点位置的接近性。室内，两节点相对于网管角度一致，1）摆放图；2）h观察；3）不同距离下不同解码器的PRR。

信噪比和分组配置。室外，不同解码器的1）不同SNR（$<-10~\mathrm{dB},\quad
[-10,0)~\mathrm{dB},\quad
[0,10)~\mathrm{dB},\quad
\geq10~\mathrm{dB}.$下PRR；2）不同SF\(8\\10\\12\)下的PRR；3）不同带宽下\(125\\250\\500\)的PRR。

近远效果。室外，A距离网关80m、B距离20\-400米8个位置（20、40、60、80、100、150、200、400），分类为：A碰撞、B碰撞、B不碰撞，观察三类PRR。

## 7\. Related Work

## 8\. Discussion

## 9\. 结论

本文提出 SP\-Decoder，将并发 LoRa 接收中已检测目标的最终 FFT\-bin attribution 表述为目标条件的空间假设检验。该视角区分了两类信息：目标方向上的能量支持候选归属，目标正交方向上的能量反驳候选归属。在局部方向统计模型下，两者导出有符号空间似然得分，而 MRC 是正交观测不提供额外判别信息时的特殊情况。

SP\-Decoder 进一步将理想检测器转化为可部署的包级接收器。它从前导码构造稳健目标方向和方向不确定性，根据已检测重叠包近似竞争统计，在目标假设有效区间内配置一次 detector，并由整个 payload 共享。逐符号路径仍然只执行一次 FFT top\-1，不恢复干扰波形，也不依赖 SIC 顺序。全文评估围绕同观测判决增益、可靠性配置和端到端并发价值三项主张组织，以证明空间反证不是额外复杂度，而是多天线 LoRa 最终判决中尚未被充分使用的信息。

## References

\\bibitem\{kay\_detection\}

S\. M\. Kay\. 1998\. \*Fundamentals of Statistical Signal Processing, Volume II: Detection Theory\*\. Prentice Hall\.

\\bibitem\{scharf\_matched\_subspace\}

L\. L\. Scharf and B\. Friedlander\. 1994\. Matched Subspace Detectors\. *IEEE Transactions on Signal Processing* 42, 8, 2146\-\-2157\.

\\bibitem\{tse\_viswanath\}

D\. Tse and P\. Viswanath\. 2005\. \*Fundamentals of Wireless Communication\*\. Cambridge University Press\.

\\bibitem\{cic\_sigcomm21\}

M\. O\. Shahid, M\. Philipose, K\. Chintalapudi, S\. Banerjee, and B\. Krishnaswamy\. 2021\. Concurrent Interference Cancellation: Decoding Multi\-Packet Collisions in LoRa\. In \*Proceedings of ACM SIGCOMM 2021\*, 503\-\-515\. https://doi\.org/10\.1145/3452296\.3472931\.

\\bibitem\{curvinglora\_nsdi22\}

C\. Li, X\. Guo, L\. Shangguan, Z\. Cao, and K\. Jamieson\. 2022\. CurvingLoRa to Boost LoRa Network Throughput via Concurrent Transmission\. In \*Proceedings of the 19th USENIX Symposium on Networked Systems Design and Implementation \(NSDI 2022\)\*\.

\\bibitem\{pcube\_tosn22\}

X\. Xia, N\. Hou, Y\. Zheng, and T\. Gu\. 2022\. PCube: Scaling LoRa Concurrent Transmissions with Reception Diversities\. *ACM Transactions on Sensor Networks* 18, 4, Article 66, 1\-\-25\. https://doi\.org/10\.1145/3545571\.

\\bibitem\{maloragw\_sensys22\}

H\. Pirayesh, S\. Zhang, P\. K\. Sangdeh, and H\. Zeng\. 2022\. MaLoRaGW: Multi\-User MIMO Transmission for LoRa\. In \*Proceedings of ACM SenSys 2022\*\. https://doi\.org/10\.1145/3560905\.3568533\.

\\bibitem\{mclora\_mobicom23\}

F\. Yu, X\. Zheng, L\. Liu, and H\. Ma\. 2023\. Enabling Concurrency for Non\-orthogonal LoRa Channels\. In \*Proceedings of ACM MobiCom 2023\*, Article 54, 1\-\-15\. https://doi\.org/10\.1145/3570361\.3613268\.

\\bibitem\{xgate\_mobicom24\}

S\. Yu, X\. Xia, N\. Hou, Y\. Zheng, and T\. Gu\. 2024\. Revolutionizing LoRa Gateway with XGate: Scalable Concurrent Transmission across Massive Logical Channels\. In \*Proceedings of ACM MobiCom 2024\*, 482\-\-496\. https://doi\.org/10\.1145/3636534\.3649375\.



**有符号空间评分**：signed spatial score；

**正交反证权重**：orthogonal counter\-evidence weight； 

**反证惩罚系数**：counter\-evidence penalty coefficient。

[实验](https://a60hwbo9d1.feishu.cn/wiki/Crq0wG5nnivfEkkRFcbcoiYRnoF)

[实验配置](https://a60hwbo9d1.feishu.cn/wiki/Lgphwq6GgiP9PKkLLmNc9FpvnSh)

[完整实验规划](https://a60hwbo9d1.feishu.cn/wiki/NmjcwbcajibTkCk97CCca4EpnZg)
