# SP-Dechirp：面向双天线 LoRa 并发解码的符号投影解啁啾方案 v2

## 摘要

本文提出 **SP-Dechirp（Signed Projective Dechirp，符号投影解啁啾）**，一种面向双天线 LoRa 网关的低复杂度并发符号解码方法。传统最大比合并（MRC）将双天线观测投影到目标信道方向后形成单一非负 FFT 功率谱，目标包与干扰包仍在同一 top-1 峰值域中竞争；当 near-far 效应存在时，强干扰即使与目标信道低相干，也可能凭借功率优势抢占最高 bin。

SP-Dechirp 的核心改变是：不再把双天线观测过早压缩为一个非负功率谱，而是保留目标信道方向与目标正交方向两路 FFT 证据，并构造带正负极性的判决谱

$$
D_u[k] = |P_u[k]|^2 - \lambda_u |Q_u[k]|^2 .
$$

其中 $P_u[k]$ 为目标方向聚焦谱，$Q_u[k]$ 为目标阻塞方向谱，$\lambda_u$ 为排斥系数。该设计使目标分量获得正分数，使与目标信道方向不一致的干扰分量被显式惩罚。理论上，当干扰与目标的归一化平方信道相干度满足

$$
\rho_{uv} < \frac{\lambda_u}{1+\lambda_u},
$$

该干扰在所有 FFT bin 上的单源贡献均为负，且这一性质不依赖干扰绝对功率。

最新真机评估使用 USRP B210 双通道采集的 LoRa 节点实测信号，从 pos01-pos10 中提取干净包后合成 10 包并发碰撞，逐包 offset 为 5-15 个 LoRa 符号的小数级间隔。在 380 个 payload 符号上，检测估计链路下 MRC 的 SER/PRR 为 0.371/5-10，SP-Dechirp 自适应版本达到 0.047/10-10；oracle 参数下 SP-Dechirp 自适应版本达到 0.021/10-10。

---

## 1. 研究背景

### 1.1 LoRa 并发接收问题

LoRa 通过 chirp spread spectrum 在低功耗、远距离物联网场景中获得较高链路预算。真实部署中，同一网关覆盖范围内存在大量异步终端，多个节点可能在同一频点、同一扩频因子下近似同时发送。由于 LoRa 常采用 ALOHA 式随机接入，包碰撞不是异常情况，而是高负载场景下的常态。

并发 LoRa 接收的难点主要体现在三个层面：

- **检测层面**：多个包的 preamble、sync word、SFD 与 payload 可能重叠，弱包前导峰会被强包掩盖；
- **估计层面**：每个包具有独立的起始采样位置、CFO、STO 与双天线复信道，估计误差会直接破坏 payload FFT 聚焦；
- **判决层面**：即使已知每个包的同步与信道参数，目标符号 bin 仍可能被强干扰 bin 超过，导致 top-1 判决错误。

现有接收方案通常沿三条路径展开。第一类是 SIC，即先解强包，再重构并消除强包；其问题是复杂度高、依赖完整解码正确性，并存在误差传播。第二类是聚类或多用户检测，通常需要较高维度的候选搜索或跨符号关联。第三类是多天线线性合并，例如 MRC 或 IRC；这类方法工程实现简单，但若输出仍是非负功率谱，强干扰仍有机会在频域中抢峰。

### 1.2 双天线 MRC 的局限

考虑目标包 $u$。MRC 使用目标信道 $\mathbf h_u$ 对双天线 FFT 观测 $\mathbf Y_u[k]$ 做匹配投影：

$$
M_u[k] = |\mathbf a_u^H \mathbf Y_u[k]|^2,\qquad
\mathbf a_u = \frac{\mathbf h_u}{\|\mathbf h_u\|}.
$$

对干扰包 $v$，定义目标与干扰的归一化平方信道相干度

$$
\rho_{uv} =
\frac{|\mathbf h_u^H \mathbf h_v|^2}
{\|\mathbf h_u\|^2\|\mathbf h_v\|^2}.
$$

若干扰在某个 FFT bin 上的功率为 $P_v$，其在 MRC 目标方向上的峰值近似与 $P_v\rho_{uv}$ 成正比。因此 MRC 的失败条件可直观写成

$$
P_v\rho_{uv} > P_u ,
$$

其中 $P_u$ 为目标峰功率。该式说明：MRC 只是按空间相干度缩放干扰，并没有改变干扰峰的非负属性。当 near-far 比足够大时，低相干干扰仍可能成为 top-1。

### 1.3 本方案设计概要

SP-Dechirp 的设计目标是实现一种直接 top-1 的目标条件化 FFT 判决器：对每个目标包，使用该目标的同步参数和双天线信道构造解啁啾算子，使目标符号在判决谱中聚焦为正峰，使非目标干扰在判决谱中受到显式负惩罚。

方案由两部分组成：

- **PCube-SP 前端**：负责并发包检测、start/CFO/STO/channel 初始化，吸收 MaLoRaGW 与 PCube 的分离前导、SFD 锚定同步和相干信道估计思想；
- **SP-Dechirp 后端**：在每个目标 payload 符号上构造目标方向谱 $P_u[k]$ 与目标阻塞谱 $Q_u[k]$，用有符号判决谱 $D_u[k]$ 直接输出 top-1 符号。

MRC 只作为对照基线，不作为 SP-Dechirp 的候选来源或 fallback。SP-Dechirp 的输出符号由自身的 signed spectrum top-1 直接给出。

### 1.4 主要贡献

本文档对应当前项目中的最终主线实现，主要贡献如下：

1. **提出符号投影解啁啾判决域**：将传统非负 FFT 功率谱扩展为目标方向功率与目标正交方向功率之差，使干扰可被映射为负贡献。
2. **给出双天线空间极性条件**：推导干扰单源负化条件 $\rho_{uv}<\lambda_u/(1+\lambda_u)$，说明该条件不依赖干扰绝对功率。
3. **设计自适应排斥系数**：根据已检测包之间的信道相干度闭式选择 $\lambda_u$，在强 near-far 和高相干场景下增强干扰排斥。
4. **接入真机前端检测估计**：实现 PCube-SP 风格的分离前导检测、sync/SFD 结构评分、SFD 锚定 start/CFO refine 与前导相干信道估计。
5. **完成真实双天线 LoRa 碰撞验证**：使用 USRP B210 采集的 pos01-pos10 实测波形合成并发碰撞，验证 SP-Dechirp 相比 MRC 的 SER/PRR 增益。

---

## 2. 系统模型

### 2.1 双天线接收模型

双天线接收机在采样时刻 $n$ 的观测向量为

$$
\mathbf y[n] =
\sum_{v=1}^{U}\mathbf h_v x_v[n-\tau_v] e^{j2\pi f_v n/N}
+ \mathbf w[n],
$$

其中：

- $U$ 为当前重叠包数量；
- $\mathbf y[n]\in\mathbb C^2$ 为双天线复基带采样；
- $\mathbf h_v\in\mathbb C^2$ 为第 $v$ 个包的窄带平坦等效双天线信道；
- $x_v[\cdot]$ 为第 $v$ 个 LoRa 基带波形；
- $\tau_v$ 为包起始采样位置，允许小数采样偏移；
- $f_v$ 为以 FFT bin 为单位的 CFO；
- $N$ 为每个 LoRa 符号的采样点数；
- $\mathbf w[n]$ 为接收噪声和未建模硬件失真。

当前项目实验中，LoRa 采样率为 1 MHz，带宽为 125 kHz，因此过采样率为 8。对 SF10，$M=1024$，每个 LoRa 符号包含

$$
N = M\cdot \mathrm{OSR} = 8192
$$

个采样点。

### 2.2 目标对齐的符号窗口

对目标包 $u$ 的第 $\ell$ 个 payload 符号，前端给出估计参数

$$
\hat\theta_u =
(\hat\tau_u,\hat f_u,\widehat{\mathrm{STO}}_u,\hat{\mathbf h}_u).
$$

接收机从双天线流中读取目标对齐窗口，补偿 CFO，并乘以目标对齐的标准 downchirp $d_u[n]$。理想同步下，目标符号 $s_{u,\ell}$ 满足

$$
x_u[n]d_u[n] = e^{j2\pi s_{u,\ell} n/M}
$$

在 folded FFT 后聚焦到第 $s_{u,\ell}$ 个 LoRa bin。

### 2.3 过采样 LoRa FFT

当前实现采用 folded-sum 风格的过采样 LoRa 解调：每个符号窗口先完成逐采样 downchirp，再将 $N=8192$ 点过采样序列按 OSR=8 折叠到 $M=1024$ 个 LoRa bin 上执行 FFT。该处理与 grLoRa 风格的过采样解调一致，避免把完整 $N$ 点 FFT bin 误当成 LoRa 符号 bin。

工程实现中，核心函数为 `lora_symbol_fft` 与 `dechirp_fft`。MRC 与 SP-Dechirp 使用同一套 folded FFT，保证对比只来自判决准则差异，而不是解调器差异。

### 2.4 实验物理层参数

| 参数 | 取值 |
|---|---:|
| 中心频率 | 487.7 MHz |
| USRP 采样率 | 1 MHz |
| USRP 接收带宽 | 250 kHz |
| LoRa 带宽 | 125 kHz |
| 扩频因子 | SF10 |
| LoRa bin 数 $M$ | 1024 |
| 过采样率 | 8 |
| 每符号采样点 $N$ | 8192 |
| Preamble | 8 symbols |
| Sync word | 0x12 |
| Header | implicit fixed length |
| 编码率 | CR 4/5 |
| Payload | 32 bytes |
| Payload 符号数 | 38 |
| Payload 起始位置 | 12.25 symbols |

---

## 3. 总体接收架构

### 3.1 数据流

当前项目主链路只保留 MRC 与 SP-Dechirp 两个方案：

1. `real_usrp_b210_capture.py` 或 GNU Radio 负责双通道 IQ 采集；
2. `gnuradio_c64_to_npz.py` 将两路 raw complex64 文件转换为统一 `.npz` 格式；
3. `real_usrp_clean_packet_synth.py` 从 pos01-pos10 中提取干净实测包，并按指定小数符号 offset 合成并发碰撞；
4. `sp_detection_frontend.py` 执行 PCube-SP 并发检测与参数估计；
5. `lora_mrc_sp_core.py` 提供 LoRa 基础波形、folded FFT、MRC 与 SP 所需的公共函数；
6. `evaluate_sp_dechirp_real_pos.py` 运行 MRC 与 SP-Dechirp 对比评估。

### 3.2 接收流程

对一段并发双天线 IQ，接收机执行以下步骤：

1. **输入预处理**：双通道去均值，必要时应用射频链校准；
2. **PCA 检测增强**：从双天线信号构造主分量投影流，增强弱包前导可见度；
3. **并发前导轨道检测**：在滑动窗口中搜索重复 preamble FFT bin 轨道；
4. **sync/SFD 结构验证**：利用 sync word 与 SFD 的固定结构剔除伪峰；
5. **start/CFO/channel 精修**：对候选包执行快速精修和 SFD 锚定相干 refine；
6. **payload 符号解调**：对每个检测包逐符号读取窗口、补偿 CFO、folded FFT；
7. **MRC 基线判决**：计算目标方向非负功率谱并取 top-1；
8. **SP-Dechirp 判决**：计算目标方向谱、目标正交谱与 signed spectrum，并取 top-1；
9. **指标统计**：按已检测包计算 SER，并以 SER $\le 20\%$ 作为包成功解码条件统计 PRR。

---

## 4. 并发数据包检测与参数估计

### 4.1 设计来源

PCube-SP 前端吸收了 MaLoRaGW 与 PCube 对 LoRa 并发前导的两个关键观察：

- LoRa preamble 由多个重复 upchirp 组成，重叠包可在时频平面上形成不同的重复 bin 轨道；
- SFD/downchirp 与 preamble/upchirp 的 bin 偏移关系可用于联合约束 CFO 与 CTO/start，避免只依赖单一前导峰。

当前实现不是将论文系统原样复刻，而是将这些思想接入双天线 SP-Dechirp 的参数初始化需求：输出每个包的 start、CFO、STO 接口与双天线信道估计。

### 4.2 PCA 投影与多轨道前导检测

前端首先从双天线接收矩阵中提取 PCA 投影流。PCA 的作用不是替代双天线解码，而是在检测阶段把被强包遮蔽的弱包前导从多天线子空间中显现出来。

在候选 start 上，`preamble_multi_tracks` 对连续 preamble 符号执行 downchirp FFT，寻找重复出现的峰 bin。每条轨道记录：

- preamble 命中次数；
- 轨道 bin 稳定性；
- 峰值功率；
- 邻近 bin 投票；
- 与其他候选轨道的时间间隔。

随后通过时间 NMS 删除近重复候选，并保留高置信度候选进入精修阶段。

### 4.3 sync/SFD 结构评分

LoRa 帧结构中，preamble 后跟 sync word，再跟两个 downchirp SFD 与四分之一下 chirp。PCube-SP 使用 `sync_word_score` 和 `sfd_score` 对候选包做结构验证。该步骤解决的问题是：单纯 preamble 峰在强碰撞下可能出现伪轨道，而 sync/SFD 的相对位置和 chirp 方向提供了更强的帧级约束。

### 4.4 SFD 锚定 start/CFO 联合 refine

对低相干评分、CFO 非物理或弱包候选，前端启用 `sfd_anchored_start_cfo_refine`。该步骤同时利用 preamble upchirp bin 与 SFD downchirp bin 的互补关系：

$$
\hat f = \frac{z_{\mathrm{up}} + z_{\mathrm{sfd}}}{2},\qquad
\widehat{\mathrm{CTO}} = \frac{z_{\mathrm{up}} - z_{\mathrm{sfd}}}{2}.
$$

其中 $z_{\mathrm{up}}$ 与 $z_{\mathrm{sfd}}$ 分别表示 upchirp 与 SFD 观测到的等效 bin 偏移。随后根据 CTO 修正 start，并在局部窗口中执行 coherent refine。

### 4.5 前导相干信道估计

给定 start/CFO 后，前端在多个 preamble 符号上提取目标 bin 的双天线复向量，进行相干平均得到

$$
\hat{\mathbf h}_u =
\frac{1}{P}\sum_{p=0}^{P-1}\mathbf y_{u,p}.
$$

同时通过相位一致性、前导命中数和结构评分构造候选置信度。最终 CFO 在 payload 解调前 snap 到整数 bin：

$$
\hat f_u^{\mathrm{payload}} = \left\lfloor \hat f_u^{\mathrm{ML}} + 0.5 \right\rfloor .
$$

该做法匹配当前 folded FFT 判决器：信道估计保留相干 ML 结果，payload 解调使用整数 CFO bin 对齐，减少分数 CFO 残差造成的符号 bin 偏移。

### 4.6 输出参数

每个检测候选输出：

| 参数 | 含义 |
|---|---|
| `start_sample` | 包起始采样位置 |
| `cfo_bins` | payload 解调使用的 CFO bin |
| `sto_samples` | STO 接口，当前主链路保留为 0 |
| `channel` | 双天线复信道估计 |
| `confidence` | 综合检测置信度 |
| `pcube_track_hits` | preamble 轨道命中数 |
| `pcube_coherent_metric` | 相干 refine 指标 |
| `sfd_confidence` | SFD 结构置信度 |

---

## 5. 核心设计：SP-Dechirp

### 5.1 为什么不继续使用单输出时变 downchirp

一种直觉方案是为两根天线设计随采样变化的权重，再把双天线信号合成一个标量序列：

$$
z_u[n] = \mathbf w_u^H[n]\mathbf y[n]d_u[n].
$$

若要求目标包在每个采样点严格保持聚焦，则必须满足

$$
\mathbf w_u^H[n]\mathbf h_u = 1,\qquad \forall n.
$$

在双天线中，满足该约束后的权重只剩一个复自由度。它可以给某个干扰方向制造扩散或置零，但无法同时对多个独立干扰方向消除相干常数项。更重要的是，单输出结构最终仍落入一个标量 FFT 谱，目标和干扰仍要在同一 top-1 机制中竞争。

因此，SP-Dechirp 放弃“单输出时变合并”，转向“双输出投影加有符号判决”：不把目标正交方向的信息丢掉，而是把它作为反证项写入判决函数。

### 5.2 目标信道正交基

对目标包 $u$，由前端估计双天线信道 $\hat{\mathbf h}_u$。归一化得到目标方向

$$
\mathbf a_u = \frac{\hat{\mathbf h}_u}{\|\hat{\mathbf h}_u\|}.
$$

在二维复空间中构造其正交单位方向

$$
\mathbf b_u =
\begin{bmatrix}
-a_{u,2}^{*}\\
a_{u,1}^{*}
\end{bmatrix},
\qquad
\mathbf b_u^H\mathbf a_u = 0.
$$

这里 $\mathbf a_u$ 对应“目标应当存在”的方向，$\mathbf b_u$ 对应“目标理想情况下不存在”的方向。

### 5.3 矩阵值双分支解啁啾

定义目标条件化矩阵解啁啾算子

$$
\mathbf G_u[n] =
d_u[n]
\begin{bmatrix}
\mathbf a_u^H\\
\mathbf b_u^H
\end{bmatrix}.
$$

作用于双天线观测后得到两条时间序列：

$$
p_u[n] = d_u[n]\mathbf a_u^H\mathbf y[n],
$$

$$
q_u[n] = d_u[n]\mathbf b_u^H\mathbf y[n].
$$

其中 $p_u[n]$ 为目标聚焦分支，$q_u[n]$ 为目标阻塞分支。对二者执行 LoRa folded FFT：

$$
P_u[k] = \mathcal F_{\mathrm{LoRa}}\{p_u[n]\},\qquad
Q_u[k] = \mathcal F_{\mathrm{LoRa}}\{q_u[n]\}.
$$

### 5.4 目标响应

若信道估计准确，

$$
\mathbf a_u^H\mathbf h_u = \|\mathbf h_u\|,\qquad
\mathbf b_u^H\mathbf h_u = 0.
$$

因此目标符号 bin $s_u$ 上近似满足

$$
P_u[s_u]\approx C\|\mathbf h_u\|,\qquad
Q_u[s_u]\approx 0,
$$

其中 $C$ 为 LoRa folded FFT 的相干增益。目标在 $P$ 分支形成正峰，在 $Q$ 分支被阻塞。

### 5.5 有符号投影谱

SP-Dechirp 定义判决谱

$$
\boxed{
D_u[k] = |P_u[k]|^2 - \lambda_u |Q_u[k]|^2
}
$$

并直接输出

$$
\boxed{
\hat s_u = \arg\max_k D_u[k].
}
$$

该谱不是功率谱，而是不定二次型判决谱。$|P_u[k]|^2$ 是支持目标的证据，$|Q_u[k]|^2$ 是反对目标的证据。若某个 bin 的能量主要来自目标方向，它得到正分；若主要来自目标正交方向，它被扣分。

### 5.6 干扰极性推导

对干扰包 $v$，将其信道分解到 $\{\mathbf a_u,\mathbf b_u\}$ 上：

$$
|\mathbf a_u^H\mathbf h_v|^2
= \|\mathbf h_v\|^2\rho_{uv},
$$

$$
|\mathbf b_u^H\mathbf h_v|^2
= \|\mathbf h_v\|^2(1-\rho_{uv}).
$$

设干扰经过目标 downchirp 后在 bin $k$ 的 LoRa 频谱形状为 $A_{uv}[k]$，则其在两分支的单源贡献为

$$
P_{uv}[k] = (\mathbf a_u^H\mathbf h_v)A_{uv}[k],
\qquad
Q_{uv}[k] = (\mathbf b_u^H\mathbf h_v)A_{uv}[k].
$$

代入 signed spectrum：

$$
\begin{aligned}
D_{uv}[k]
&= |P_{uv}[k]|^2-\lambda_u|Q_{uv}[k]|^2\\
&= \|\mathbf h_v\|^2|A_{uv}[k]|^2
\left[\rho_{uv}-\lambda_u(1-\rho_{uv})\right]\\
&= \|\mathbf h_v\|^2|A_{uv}[k]|^2
\left[(1+\lambda_u)\rho_{uv}-\lambda_u\right].
\end{aligned}
$$

因此当

$$
\rho_{uv}<\frac{\lambda_u}{1+\lambda_u}
$$

时，$D_{uv}[k]<0$ 对所有 $k$ 成立。该结论解释了 SP-Dechirp 为什么能处理 near-far：干扰越强，其负分数绝对值越大，而不是更容易抢占正峰 top-1。

### 5.7 固定排斥系数

若取 $\lambda_u=1$，

$$
D_u[k]=|P_u[k]|^2-|Q_u[k]|^2,
$$

干扰负化条件变为 $\rho_{uv}<0.5$。该版本不需要额外参数，适合目标与干扰信道差异明显的场景。但在 pos01-pos10 真实数据中，部分位置之间信道相干度很高，固定 $\lambda=1$ 不足以压制所有强干扰。

### 5.8 自适应排斥系数

定义目标包与其他已检测包之间的最大平方相干度

$$
\rho_{u,\max}^{I}=\max_{v\ne u}\rho_{uv}.
$$

若希望所有已检测干扰满足单源负化条件，需要

$$
\lambda_u >
\frac{\rho_{u,\max}^{I}}{1-\rho_{u,\max}^{I}}.
$$

实际实现使用闭式自适应规则：

$$
\lambda_u =
\min\left(
\lambda_{\max},
(1+\mu)
\frac{\rho_{u,\max}^{I}}{1-\rho_{u,\max}^{I}}
\right),
$$

其中 $\mu$ 为安全裕量，$\lambda_{\max}$ 防止高相干场景中过度放大正交分支噪声。最新实验设置为

$$
\mu=0.05,\qquad \lambda_{\max}=4.0.
$$

### 5.9 与 MRC 的本质差异

MRC 的判决谱为

$$
M_u[k]=|P_u[k]|^2.
$$

它只使用目标方向投影，不使用目标正交方向证据。SP-Dechirp 使用

$$
D_u[k]=|P_u[k]|^2-\lambda_u|Q_u[k]|^2.
$$

因此二者的差异不是“SP 比 MRC 多一点抑制增益”，而是判决域的符号属性不同：

- MRC 中所有峰都是非负证据，强干扰只要足够大就可能赢；
- SP-Dechirp 中低相干干扰可转化为负证据，强干扰越强越不应成为目标 top-1。

### 5.10 多干扰与交叉项

上述负化条件是单源条件。若多个干扰在同一 bin 相干叠加，signed spectrum 展开后包含交叉项：

$$
|P_1+P_2|^2-\lambda|Q_1+Q_2|^2.
$$

因此“每个干扰单独为负”不严格推出“多个干扰相干和一定为负”。真实系统中仍需要依靠以下因素降低交叉项风险：

- 不同包 start/CFO/STO 造成的 bin 分散；
- payload 符号随机性导致的跨符号非持续同 bin；
- 双天线信道差异使 $P$ 与 $Q$ 中的相干相位不同；
- 自适应 $\lambda$ 提高正交分支惩罚强度。

这也是必须用真实波形验证 SP-Dechirp 的原因。

### 5.11 复杂度

对每个目标符号，SP-Dechirp 需要：

- 两天线 CFO 补偿与 downchirp；
- 两路 LoRa folded FFT；
- 目标方向与目标正交方向两个复线性组合；
- 一个逐 bin 实数差分；
- 一次 top-1 搜索。

复杂度为 $O(M\log M)$，与普通双天线 LoRa FFT 解调同量级。不需要 SIC，不需要逐符号候选搜索，不需要多轮迭代优化。

---

## 6. 实现对应关系

当前项目中与 SP-Dechirp 全流程直接相关的文件如下：

| 文件 | 作用 |
|---|---|
| `experiment_defaults.py` | 统一实验物理层默认参数 |
| `usrp_b210_lora_tx.py` | USRP B210 LoRa 发射脚本，生成 SX127x 兼容帧 |
| `real_usrp_b210_capture.py` | USRP B210 双通道接收采集脚本 |
| `gnuradio_c64_to_npz.py` | GNU Radio raw complex64 到 `.npz` 的转换脚本 |
| `real_usrp_clean_packet_synth.py` | 干净真机包提取与并发碰撞合成 |
| `lora_mrc_sp_core.py` | LoRa chirp、folded FFT、MRC 与 SP 公共核心 |
| `sp_detection_frontend.py` | PCube-SP 并发检测与参数估计前端 |
| `evaluate_sp_dechirp_real_pos.py` | MRC 与 SP-Dechirp 的真实 pos 数据评估入口 |

历史 TVC、TID、fragment notch 等探索性方案已不属于当前主线。当前可验收主线仅包含 MRC 对比与 SP-Dechirp 方案。

---

## 7. 最新真机实验设置

### 7.1 数据采集

真实数据来自 LoRa 节点实机发射与 USRP B210 双天线接收。实验中改变发射节点空间位置，得到 pos01-pos10 十组接收数据。每个位置文件包含双天线复基带 IQ，中心频率 487.7 MHz，采样率 1 MHz。

从 pos01-pos10 中共提取 26 个干净完整包，分布如下：

| 位置 | 干净包数 |
|---|---:|
| pos01 | 3 |
| pos02 | 2 |
| pos03 | 3 |
| pos04 | 2 |
| pos05 | 3 |
| pos06 | 3 |
| pos07 | 3 |
| pos08 | 2 |
| pos09 | 2 |
| pos10 | 3 |

每个干净包保留双天线原始帧片段，形状为 $2\times 411648$，不重生成理想 LoRa 波形。

### 7.2 并发碰撞合成

最新评估使用 10 个实测包合成一段 pos01-pos10 并发碰撞，设置为：

| 配置项 | 取值 |
|---|---|
| 合成文件 | `real_usrp_outputs/synth_sp_pos01to10_moderate_offset5_15_seed11.npz` |
| 评估输出 | `real_usrp_outputs/eval_sp_final_pos01to10_offset5_15.json` |
| 源包顺序 | `[4,25,6,15,17,9,10,1,20,21]` |
| 对应位置 | pos02, pos10, pos03, pos06, pos07, pos04, pos05, pos01, pos08, pos09 |
| offset 规则 | 每个包较前一个包延迟一个小数级 LoRa 符号间隔 |
| offset 范围 | 5-15 symbols |
| 实际 offset 序列 | 10.585, 12.724, 10.640, 10.084, 14.933, 12.039, 14.380, 9.447, 13.691 |
| 随机种子 | 11 |
| 功率归一化 | 否，保留真实 near-far |
| payload 符号数 | 10 packets x 38 symbols = 380 symbols |

### 7.3 检测估计设置

PCube-SP 前端参数为：

| 参数 | 取值 |
|---|---:|
| frontend | `pcube_sp` |
| threshold | 5.5 |
| scan step | 4096 samples |
| max candidates | 14 |
| min sync score | 1000 |
| min coherent metric | 1000 |
| adaptive margin $\mu$ | 0.05 |
| adaptive $\lambda_{\max}$ | 4.0 |

包成功解码定义为该包 payload SER $\le 20\%$。PRR 只在检测到且与真实包匹配的包上统计；本次实验检测链路成功匹配全部 10 个目标包。

---

## 8. 最新实验结果

### 8.1 总体结果

| 参数来源 | MRC SER | SP-Fixed SER | SP-Adaptive SER | MRC PRR | SP-Fixed PRR | SP-Adaptive PRR |
|---|---:|---:|---:|---:|---:|---:|
| Oracle start/CFO/STO/h | 0.374 | 0.305 | **0.021** | 5/10 | 5/10 | **10/10** |
| PCube-SP 检测估计 | 0.371 | 0.321 | **0.047** | 5/10 | 5/10 | **10/10** |

结论：

- MRC 在该 10 包真实碰撞场景中只能成功 5 个包，说明场景确实包含 MRC top-1 失败的 near-far/高碰撞压力；
- 固定 $\lambda=1$ 的 SP-Dechirp 仍不足以处理部分高相干强干扰；
- 自适应 SP-Dechirp 在 oracle 和检测估计两种链路下均达到 10/10 PRR；
- 检测估计链路相较 oracle 的 SER 损失为 0.047-0.021=0.026，说明当前前端误差已经不是主要瓶颈。

### 8.2 检测估计精度

PCube-SP 检测估计与 oracle 的平均差距为：

| 指标 | 数值 |
|---|---:|
| 检测匹配包数 | 10/10 |
| 平均绝对 start 误差 | 27.18 samples |
| 平均绝对 CFO 误差 | 3.40 bins |
| 平均绝对 STO 误差 | 0.00 samples |
| 平均信道一致性 | 0.999805 |

其中 start 误差约为 $27.18/8192=0.0033$ 个 LoRa 符号周期。信道一致性接近 1，说明 SP-Dechirp 所需的目标方向与正交方向可以由当前前端稳定提供。

### 8.3 检测估计链路逐包结果

| 源包 | 最相干包 | $\rho_{\max}$ | 信道一致性 | $\lambda_u$ | MRC SER | SP-Fixed SER | SP-Adaptive SER | SP-Adaptive 成功 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| pos02 | pos04 | 0.998 | 0.999981 | 4.000 | 0.000 | 0.000 | 0.000 | 是 |
| pos10 | pos09 | 0.953 | 0.999994 | 4.000 | 0.000 | 0.000 | 0.000 | 是 |
| pos03 | pos01 | 0.954 | 0.999979 | 4.000 | 1.000 | 0.816 | 0.184 | 是 |
| pos06 | pos01 | 0.803 | 0.999070 | 4.000 | 0.947 | 0.947 | 0.026 | 是 |
| pos07 | pos06 | 0.764 | 0.999996 | 3.396 | 0.184 | 0.184 | 0.184 | 是 |
| pos04 | pos02 | 0.998 | 0.999935 | 4.000 | 0.632 | 0.368 | 0.000 | 是 |
| pos05 | pos03 | 0.902 | 0.999155 | 4.000 | 0.289 | 0.263 | 0.026 | 是 |
| pos01 | pos03 | 0.954 | 0.999965 | 4.000 | 0.000 | 0.000 | 0.000 | 是 |
| pos08 | pos10 | 0.918 | 0.999995 | 4.000 | 0.000 | 0.000 | 0.000 | 是 |
| pos09 | pos04 | 0.991 | 0.999983 | 4.000 | 0.658 | 0.632 | 0.053 | 是 |

### 8.4 Oracle 链路逐包结果

| 源包 | $\lambda_u$ | MRC SER | SP-Fixed SER | SP-Adaptive SER | SP-Adaptive 成功 |
|---|---:|---:|---:|---:|---|
| pos02 | 4.000 | 0.000 | 0.000 | 0.000 | 是 |
| pos10 | 4.000 | 0.000 | 0.000 | 0.000 | 是 |
| pos03 | 4.000 | 1.000 | 0.816 | 0.105 | 是 |
| pos06 | 4.000 | 0.947 | 0.947 | 0.053 | 是 |
| pos07 | 4.000 | 0.000 | 0.000 | 0.000 | 是 |
| pos04 | 4.000 | 0.868 | 0.500 | 0.053 | 是 |
| pos05 | 4.000 | 0.289 | 0.263 | 0.000 | 是 |
| pos01 | 4.000 | 0.000 | 0.000 | 0.000 | 是 |
| pos08 | 4.000 | 0.000 | 0.000 | 0.000 | 是 |
| pos09 | 4.000 | 0.632 | 0.526 | 0.000 | 是 |

### 8.5 结果解释

MRC 失败的根本原因是：它只看目标方向投影 $|P_u[k]|^2$。当强干扰在目标方向上仍保留足够大的投影分量时，MRC 会把干扰 bin 当成目标 bin。pos03、pos06、pos04、pos09 的 MRC SER 很高，正是因为它们在碰撞区间内频繁被其他包的强峰抢占。

SP-Dechirp 成功的原因是：它同时观察目标方向和目标正交方向。当某个 bin 来自非目标包时，即使该 bin 在目标方向 $P$ 中很强，它通常也会在目标正交方向 $Q$ 中留下证据。自适应 $\lambda_u$ 把该正交证据转化为足够强的负惩罚，使这些 bin 不再是 top-1。对 pos03、pos06、pos04、pos09，SP-Adaptive 分别将 SER 从 1.000、0.947、0.632、0.658 降至 0.184、0.026、0.000、0.053。

需要注意的是，真实 pos 数据中很多位置对的信道相干度很高，例如 pos02-pos04 的 $\rho_{\max}=0.998$。这意味着双天线空间可分性本身有限。SP-Dechirp 能在该场景中获得 10/10 PRR，依赖的不只是低相干负化条件，也包括 offset、CFO、payload 随机性和 signed spectrum 在多符号上的统计稳定性。

---

## 9. 适用边界与后续重点

SP-Dechirp 当前最适合以下条件：

- 双天线接收，且目标与干扰存在可利用的空间方向差异；
- 前端可提供稳定的 start/CFO/channel 估计；
- 并发包之间存在一定 offset 或 CFO 差异；
- 需要低复杂度、非迭代、直接 top-1 的 payload 符号判决。

主要边界包括：

- 若目标与干扰双天线信道几乎完全共线，任何只依赖双天线空间方向的接收器都缺乏足够自由度；
- 多个干扰在同一 bin 上相干叠加时，signed spectrum 的交叉项可能破坏单源负化条件；
- $\lambda_u$ 过大可能放大目标信道估计误差与正交分支噪声，因此需要上限或可靠性约束；
- 当前 PRR 定义基于符号级 SER 阈值，完整 PHY 译码链路仍需进一步接入白化、交织、Hamming/CRC 等步骤。

后续最有价值的改进不是增加暴力搜索，而是围绕以下方向增强理论与工程闭环：

1. 给出多干扰交叉项的概率界或 margin 条件；
2. 使用前导分组一致性估计目标信道可靠性，从而自适应调整 $\lambda_{\max}$；
3. 将 signed margin 纳入前端候选排序，减少伪检测对后端的影响；
4. 在更多位置组合、更多 offset 范围和更强 near-far 条件下验证 PRR 稳定性；
5. 接入完整 LoRa PHY 译码，报告 packet-level CRC 成功率。

---

## 10. 结论

SP-Dechirp v2 的核心观点是：双天线 LoRa 并发解码不应只追求“更好的非负合并功率谱”，而应利用目标信道正交方向提供的反证信息，构造有符号 FFT 判决域。

最终判决形式为

$$
\hat s_u =
\arg\max_k
\left(
|P_u[k]|^2-\lambda_u|Q_u[k]|^2
\right).
$$

在当前真实 USRP B210 双天线 LoRa 实验中，SP-Dechirp 自适应版本在 10 包并发、offset 5-15 符号、380 个 payload 符号的场景下，将检测估计链路的 SER 从 MRC 的 0.371 降至 0.047，将 PRR 从 5/10 提升至 10/10。该结果表明，基于目标信道的符号投影解啁啾具有明确的理论动机、较低的实现复杂度和可观的真机实验收益。
