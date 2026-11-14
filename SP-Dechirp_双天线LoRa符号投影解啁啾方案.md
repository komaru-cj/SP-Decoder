# SP-Dechirp：面向双天线 LoRa 并发解码的符号投影解啁啾

## 1. 研究目标

本文面向双天线 LoRa 接收机，研究如下问题：

> 已知目标包的起始位置、载波频偏和双天线复信道，能否重新设计接收端解啁啾与 FFT 判决过程，使目标符号直接成为输出频谱的 top-1，而不依赖 MRC 先产生候选峰，也不依赖高复杂度搜索、SIC 或迭代聚类？

设接收端已经完成：

- 目标包前导码检测；
- 符号起始位置估计；
- CFO 粗估与补偿；
- 双天线复信道估计。

目标是设计一个低复杂度、目标条件化的双天线解啁啾算子，使：

1. 目标包在其符号 bin 上保持相干聚焦；
2. 与目标信道方向不一致的干扰包在判决域中受到显式排斥；
3. 最终直接通过一次频谱 top-1 判决得到目标符号。

本文提出 **SP-Dechirp（Signed Projective Dechirp，符号投影解啁啾）**。其核心并非重新包装 MRC，而是保留目标信道方向与其正交方向的两路 FFT 输出，并构造具有正负极性的判决谱。

---

## 2. 系统模型

考虑双天线接收机。第 \(n\) 个采样时刻的接收向量为

$$
\mathbf y[n]
=
\sum_{v=1}^{U}
\mathbf h_v x_v[n]
+
\mathbf w[n],
$$

其中：

- \(U\) 为当前重叠包数量；
- \(x_v[n]\) 为第 \(v\) 个 LoRa 包的基带信号；
- \(\mathbf h_v\in\mathbb C^2\) 为第 \(v\) 个包到双天线接收机的复信道；
- \(\mathbf w[n]\) 为双天线接收噪声。

对目标包 \(u\)，其双天线信道写为

$$
\mathbf h_u
=
\begin{bmatrix}
h_{u,1}\\
h_{u,2}
\end{bmatrix}.
$$

假设目标包的符号边界和 CFO 已经补偿，目标对齐的标准 LoRa downchirp 记为

$$
d_u[n].
$$

若目标符号为 \(s_u\)，理想情况下，目标信号与 \(d_u[n]\) 相乘后应转化为单频复指数：

$$
x_u[n]d_u[n]
=
e^{j2\pi s_u n/N},
$$

其中 \(N\) 为单个 LoRa symbol 的采样点数。

---

## 3. 为什么单输出时变 downchirp 难以从根本上超越 MRC

一种直观思路是：为两根天线设计不同的时变 downchirp，再将两路结果相加，希望目标保持聚焦，而干扰被时变调制扩散。

任意此类单输出线性接收器都可以写成

$$
z_u[n]
=
\mathbf w_u^H[n]\mathbf y[n]d_u[n],
$$

其中 \(\mathbf w_u[n]\in\mathbb C^2\) 是随时间变化的双天线权重。

为了保证目标符号在 FFT 后仍然严格聚焦，需要满足

$$
\mathbf w_u^H[n]\mathbf h_u
=
1,
\qquad
\forall n.
$$

否则，目标自身也会受到时变幅相调制，导致目标能量扩散。

定义目标信道的单位方向

$$
\mathbf a_u
=
\frac{\mathbf h_u}{\|\mathbf h_u\|},
$$

再构造其正交单位向量

$$
\mathbf b_u
=
\begin{bmatrix}
-a_{u,2}^{*}\\
a_{u,1}^{*}
\end{bmatrix},
\qquad
\mathbf b_u^H\mathbf a_u=0.
$$

满足目标不变约束的所有权重都可以表示为

$$
\mathbf w_u[n]
=
\frac{\mathbf a_u}{\|\mathbf h_u\|}
+
\beta[n]\mathbf b_u.
$$

对任意干扰包 \(v\)，其等效系数为

$$
c_{uv}[n]
=
\mathbf w_u^H[n]\mathbf h_v.
$$

将 \(\beta[n]\) 分解为均值与零均值部分，可得：

$$
c_{uv}[n]
=
\underbrace{
\bar{\mathbf w}_u^H\mathbf h_v
}_{\text{相干常数项}}
+
\underbrace{
\tilde{\beta}^{*}[n]\mathbf b_u^H\mathbf h_v
}_{\text{时变扩散项}}.
$$

其中

$$
\bar{\mathbf w}_u
=
\frac{1}{N}
\sum_{n=0}^{N-1}
\mathbf w_u[n].
$$

时变项可以给干扰增加边带，但干扰原始 FFT bin 上仍保留相干分量

$$
N\bar{\mathbf w}_u^H\mathbf h_v.
$$

若希望同时消除多个干扰，需要满足

$$
\bar{\mathbf w}_u^H\mathbf h_u=1,
$$

以及

$$
\bar{\mathbf w}_u^H\mathbf h_v=0,
\qquad
\forall v\ne u.
$$

然而，双天线权重仅有两个复维度。在满足目标保持约束后，只剩一个复自由度，因此最多只能精确置零一个独立干扰方向。

由此得到一个重要结论：

> 在“双天线、单个标量输出、目标严格聚焦、一次 FFT 判决”的条件下，仅依靠时变 downchirp 无法保证多个任意干扰同时失去相干峰。

因此，继续在“一个标量 downchirp 输出”上增加时变相位、分段调制或非线性扰动，通常只能在原有干扰峰之外增加扩散项，难以获得稳定且显著的 top-1 改善。

---

## 4. 核心设计：矩阵值双分支解啁啾

SP-Dechirp 不再把双天线观测压缩成单个标量序列，而是保留两个相互正交的输出：

1. 目标信道方向上的聚焦分支；
2. 目标信道正交方向上的排斥分支。

### 4.1 目标信道基

根据目标包前导码估计其双天线信道

$$
\hat{\mathbf h}_u.
$$

归一化得到目标信道方向

$$
\mathbf a_u
=
\frac{\hat{\mathbf h}_u}
{\|\hat{\mathbf h}_u\|}.
$$

构造与其正交的单位方向

$$
\mathbf b_u
=
\begin{bmatrix}
-a_{u,2}^{*}\\
a_{u,1}^{*}
\end{bmatrix}.
$$

则有

$$
\mathbf a_u^H\mathbf b_u=0,
$$

以及

$$
\|\mathbf a_u\|=\|\mathbf b_u\|=1.
$$

### 4.2 双分支解啁啾算子

定义目标条件化的矩阵解啁啾算子

$$
\mathbf G_u[n]
=
d_u[n]
\begin{bmatrix}
\mathbf a_u^H\\
\mathbf b_u^H
\end{bmatrix}.
$$

作用于双天线接收向量后，得到两路时间序列：

$$
p_u[n]
=
d_u[n]\mathbf a_u^H\mathbf y[n],
$$

$$
q_u[n]
=
d_u[n]\mathbf b_u^H\mathbf y[n].
$$

其中：

- \(p_u[n]\) 为目标聚焦分支；
- \(q_u[n]\) 为目标阻塞分支。

两路 FFT 分别为

$$
P_u[k]
=
\operatorname{FFT}\{p_u[n]\},
$$

$$
Q_u[k]
=
\operatorname{FFT}\{q_u[n]\}.
$$

---

## 5. 目标包的响应

若信道估计准确，则

$$
\mathbf a_u^H\mathbf h_u
=
\|\mathbf h_u\|,
$$

而

$$
\mathbf b_u^H\mathbf h_u
=
0.
$$

因此，在目标符号 bin \(s_u\) 上，

$$
P_u[s_u]
\approx
N\|\mathbf h_u\|,
$$

$$
Q_u[s_u]
\approx
0.
$$

目标包具有以下结构：

- 在聚焦分支中形成强相干峰；
- 在阻塞分支中理想消失；
- 不需要依赖 MRC top-1 生成候选；
- 不需要在多个候选 bin 中再做目标归属。

仅使用 \(P_u[k]\) 仍然会退化为普通信道匹配投影，因此 SP-Dechirp 的关键不在第一分支本身，而在于如何联合利用两个正交分支。

---

## 6. Signed Projective Spectrum

定义符号投影判决谱

$$
D_u[k]
=
|P_u[k]|^2
-
\lambda_u|Q_u[k]|^2,
$$

其中 \(\lambda_u>0\) 为排斥系数。

最终符号判决为

$$
\boxed{
\hat s_u
=
\arg\max_k D_u[k]
}
$$

必要时再增加有效性阈值

$$
D_u[\hat s_u]>\tau_u.
$$

该频谱不是传统非负功率谱，而是一个具有正负极性的判决量：

- 与目标信道方向一致的分量倾向于得到正分数；
- 与目标正交方向占优的分量倾向于得到负分数。

因此，SP-Dechirp 的目标不是简单压低干扰峰，而是改变干扰峰在判决域中的符号。

---

## 7. 干扰极性分析

定义目标包 \(u\) 与干扰包 \(v\) 的归一化平方信道相干度

$$
\rho_{uv}
=
\frac{
|\mathbf h_u^H\mathbf h_v|^2
}{
\|\mathbf h_u\|^2
\|\mathbf h_v\|^2
}.
$$

其取值范围为

$$
0\le\rho_{uv}\le1.
$$

由于 \(\{\mathbf a_u,\mathbf b_u\}\) 构成二维复空间中的正交基，有

$$
|\mathbf a_u^H\mathbf h_v|^2
=
\|\mathbf h_v\|^2\rho_{uv},
$$

$$
|\mathbf b_u^H\mathbf h_v|^2
=
\|\mathbf h_v\|^2(1-\rho_{uv}).
$$

设干扰包 \(v\) 经过目标对齐 downchirp 后的频谱形状为

$$
A_{uv}[k].
$$

该频谱可以包含：

- 干扰符号本身的 FFT 峰；
- STO 失配导致的泄漏；
- CFO 残差导致的频谱偏移；
- LoRa 循环移位和符号边界截断效应。

干扰在两路分支中的响应分别为

$$
P_{uv}[k]
=
\mathbf a_u^H\mathbf h_v A_{uv}[k],
$$

$$
Q_{uv}[k]
=
\mathbf b_u^H\mathbf h_v A_{uv}[k].
$$

因此，其对判决谱的单源贡献为

$$
D_{uv}[k]
=
|P_{uv}[k]|^2
-
\lambda_u|Q_{uv}[k]|^2.
$$

代入后得到

$$
D_{uv}[k]
=
\|\mathbf h_v\|^2
|A_{uv}[k]|^2
\left[
\rho_{uv}
-
\lambda_u(1-\rho_{uv})
\right].
$$

进一步写为

$$
\boxed{
D_{uv}[k]
=
\|\mathbf h_v\|^2
|A_{uv}[k]|^2
\left[
(1+\lambda_u)\rho_{uv}
-
\lambda_u
\right]
}
$$

于是，只要满足

$$
\rho_{uv}
<
\frac{\lambda_u}{1+\lambda_u},
$$

就有

$$
D_{uv}[k]<0,
\qquad
\forall k.
$$

这意味着，只要干扰信道与目标信道的相干度低于给定阈值，无论干扰能量集中在一个 bin，还是因为 STO/CFO 泄漏到多个 bin，其对整个判决谱的单源贡献都为负。

### 7.1 固定参数 \(\lambda=1\)

最简单的实现取

$$
\lambda_u=1.
$$

此时

$$
D_u[k]
=
|P_u[k]|^2-|Q_u[k]|^2,
$$

干扰负化条件变为

$$
\rho_{uv}<\frac{1}{2}.
$$

因此：

- 目标包：理想情况下为正峰；
- 低相干干扰：在其所有频谱分量上表现为负值；
- 白噪声：两路均值近似抵消。

该特性特别适合低信道相干、强 near-far 干扰场景。

---

## 8. 与 MRC 的差异

MRC 对目标包 \(u\) 的频谱判决通常等价于

$$
M_u[k]
=
|P_u[k]|^2.
$$

对干扰包 \(v\)，其 MRC 峰值与

$$
P_v\rho_{uv}
$$

近似成比例，其中 \(P_v\) 为干扰功率。

因此，即使 \(\rho_{uv}\) 较低，只要干扰足够强，MRC 的干扰峰仍可能超过目标峰。

例如：

$$
\rho_{uv}=0.2,
$$

$$
P_v=100P_u.
$$

则 MRC 中干扰峰约为

$$
P_v\rho_{uv}
=
20P_u.
$$

干扰仍然可能成为 top-1。

SP-Dechirp 取 \(\lambda=1\) 时，干扰贡献变为

$$
D_{uv}
=
P_v(2\rho_{uv}-1).
$$

代入 \(\rho_{uv}=0.2\)，有

$$
D_{uv}
=
-0.6P_v.
$$

干扰功率越强，其负分数绝对值越大，而不会挤占正谱 top-1。

因此，SP-Dechirp 与 MRC 的差异不在于多获得若干 dB 的干扰抑制，而在于：

> MRC 仍然让目标与干扰在同一个非负功率域中竞争；SP-Dechirp 则试图将目标和低相干干扰映射到不同极性的判决域中。

---

## 9. 排斥系数的闭式选择

定义目标包与所有已检测干扰包之间的最大平方相干度

$$
\rho_{u,\max}^{I}
=
\max_{v\ne u}\rho_{uv}.
$$

为了使所有已知干扰的单源贡献均为负，需要

$$
\lambda_u
>
\frac{
\rho_{u,\max}^{I}
}{
1-\rho_{u,\max}^{I}
}.
$$

另一方面，目标信道估计存在误差。定义估计信道与真实目标信道的一致性

$$
\rho_u^{T}
=
\frac{
|\hat{\mathbf h}_u^H\mathbf h_u|^2
}{
\|\hat{\mathbf h}_u\|^2
\|\mathbf h_u\|^2
}.
$$

为了保证目标仍然得到正分数，需要

$$
\lambda_u
<
\frac{
\rho_u^{T}
}{
1-\rho_u^{T}
}.
$$

因此，可行参数区间存在的条件是

$$
\boxed{
\rho_{u,\max}^{I}
<
\rho_u^{T}
}
$$

该条件反映了一个基本可分性要求：

> 目标信道估计自身的一致性必须高于目标与最相似干扰之间的相干度。

实际系统中，可将前导码拆分为两组，分别估计

$$
\hat{\mathbf h}_u^{(1)},
\qquad
\hat{\mathbf h}_u^{(2)},
$$

并用二者的平方相干度近似评估 \(\rho_u^T\)。

为了避免不必要的噪声放大，可选择满足干扰负化条件的最小排斥系数

$$
\lambda_u
=
(1+\mu)
\frac{
\rho_{u,\max}^{I}
}{
1-\rho_{u,\max}^{I}
},
$$

其中 \(\mu>0\) 为小幅安全裕量。

对于首轮验证，不建议引入自适应参数搜索，直接使用

$$
\lambda_u=1
$$

即可检验核心假设。

---

## 10. 噪声与判决阈值

假设双天线观测经过白化，且两路 FFT 噪声近似满足

$$
P_w[k],Q_w[k]
\sim
\mathcal{CN}(0,\nu).
$$

则

$$
D_w[k]
=
|P_w[k]|^2
-
\lambda|Q_w[k]|^2.
$$

在 \(t\ge0\) 时，其右尾概率可写为

$$
\Pr(D_w[k]>t)
=
\frac{1}{1+\lambda}
e^{-t/\nu}.
$$

对全部 \(N\) 个 FFT bin 使用联合上界，可取

$$
\tau_u
=
\nu
\log
\frac{
N
}{
(1+\lambda_u)\delta
},
$$

使纯噪声产生高于阈值正峰的概率不超过约 \(\delta\)。

最终判决规则为

$$
\hat s_u
=
\arg\max_k D_u[k],
$$

并检查

$$
D_u[\hat s_u]>\tau_u.
$$

若只验证 top-1 机制，可暂时不加阈值，先直接比较 signed margin。

---

## 11. 实现流程

### 11.1 输入

对每个目标包 \(u\)，接收机需要获得：

- 双天线时域采样 \(y_1[n],y_2[n]\)；
- 目标符号窗口；
- 目标包 STO；
- 目标包 CFO；
- 目标包双天线复信道估计 \(\hat{\mathbf h}_u\)。

### 11.2 算法步骤

1. 对目标符号窗口进行 STO 对齐；
2. 补偿目标包 CFO；
3. 两根天线分别乘目标对齐的标准 downchirp；
4. 对两路结果分别执行 FFT；
5. 根据 \(\hat{\mathbf h}_u\) 构造目标方向 \(\mathbf a_u\)；
6. 构造正交方向 \(\mathbf b_u\)；
7. 在频域形成目标聚焦谱 \(P_u[k]\)；
8. 形成目标阻塞谱 \(Q_u[k]\)；
9. 计算 signed spectrum \(D_u[k]\)；
10. 直接输出 \(\arg\max_k D_u[k]\)。

### 11.3 伪代码

```python
import numpy as np

def sp_dechirp_decode(
    y1,
    y2,
    downchirp,
    h_target,
    lam=1.0,
    threshold=None,
):
    """
    Decode one target LoRa symbol from two-antenna samples.
    """

    norm_h = np.linalg.norm(h_target)
    if norm_h <= 0:
        raise ValueError("Target channel norm must be positive.")

    a = h_target / norm_h

    b = np.array(
        [-np.conj(a[1]), np.conj(a[0])],
        dtype=np.complex128,
    )

    z1 = y1 * downchirp
    z2 = y2 * downchirp

    Y1 = np.fft.fft(z1)
    Y2 = np.fft.fft(z2)

    P = np.conj(a[0]) * Y1 + np.conj(a[1]) * Y2
    Q = -a[1] * Y1 + a[0] * Y2

    score = np.abs(P) ** 2 - lam * np.abs(Q) ** 2

    symbol_hat = int(np.argmax(score))

    if threshold is None:
        valid = True
    else:
        valid = bool(score[symbol_hat] > threshold)

    return symbol_hat, valid, score
```

---

## 12. 复杂度

SP-Dechirp 对每个目标符号仅需：

- 两路逐点 dechirp；
- 两个 \(N\)-点 FFT；
- 两个逐 bin 复线性组合；
- 一个逐 bin 实数差分；
- 一次 top-1 搜索。

总体复杂度为

$$
O(N\log N).
$$

与普通双天线 LoRa FFT 接收机处于同一量级。

该方案不需要：

- top-\(K\) 候选搜索；
- 多轮迭代优化；
- 符号级 SIC；
- 网格化波形搜索；
- 每个干扰包单独构造复杂模板；
- 高维聚类。

---

## 13. 适用边界

### 13.1 低相干干扰

当

$$
\rho_{uv}
<
\frac{\lambda_u}{1+\lambda_u},
$$

单个干扰包在整个 signed spectrum 上均表现为负贡献。

这是该方案最明确的优势区域。

### 13.2 STO 和 CFO 泄漏

若窄带平坦信道假设成立，同一干扰包泄漏到不同 bin 的频谱分量仍共享相同空间信道方向。

因此，STO 或 CFO 造成的频谱扩散不会改变该干扰对应的空间相干度，其单源负化条件仍然成立。

### 13.3 多个干扰落在同一 bin

若多个包在同一 FFT bin 上相干叠加，则

$$
\mathbf Y[k]
=
\sum_v
A_v[k]\mathbf h_v.
$$

此时 signed spectrum 中会出现交叉项

$$
2\operatorname{Re}
\left\{
A_i^*[k]A_j[k]
\mathbf h_i^H
\mathbf Q_u
\mathbf h_j
\right\},
$$

其中

$$
\mathbf Q_u
=
\mathbf a_u\mathbf a_u^H
-
\lambda_u\mathbf b_u\mathbf b_u^H.
$$

因此，“每个单独干扰均为负”不能直接保证“多个干扰的相干和仍为负”。

这是 SP-Dechirp 必须通过真实数据重点验证的部分。

一种低复杂度增强方式是将单个符号划分为少量固定子窗，对每个子窗计算 signed spectrum，再采用中位数或截尾均值聚合，以减弱偶然交叉相干。该增强不应在首轮验证中引入，以免掩盖核心机制。

### 13.4 高信道相干

当

$$
\rho_{uv}\rightarrow1,
$$

目标与干扰的双天线信道方向近似共线。

此时任何只依赖双天线复信道方向的接收器都缺乏足够可辨识性。

高相干区域不能仅通过增大 \(\lambda_u\) 解决，因为这会同时放大：

- 目标信道估计误差；
- 阻塞分支噪声；
- 硬件相位漂移；
- 双天线校准误差。

高相干场景需要额外利用：

- CFO 差异；
- STO 差异；
- 符号边界结构；
- 多径响应；
- 更多接收天线；
- 跨符号观测。

因此，SP-Dechirp 应首先定位为低相干和中等相干区域的直接 top-1 解码器，而不应声称解决所有双天线不可分场景。

---

## 14. 最小可行性验证

首轮实验不应直接扩展到完整 PRR，也不应加入 SIC、聚类和复杂子窗机制。

首先验证一个问题：

> 当 MRC 的 top-1 是强干扰时，SP-Dechirp 的 top-1 能否直接恢复为目标符号？

### 14.1 数据准备

使用真实双天线 LoRa 碰撞数据。

对每个目标包估计：

- 目标双天线信道 \(\hat{\mathbf h}_u\)；
- 各干扰包双天线信道 \(\hat{\mathbf h}_v\)；
- 目标与干扰之间的平方相干度

$$
\hat\rho_{uv}
=
\frac{
|\hat{\mathbf h}_u^H\hat{\mathbf h}_v|^2
}{
\|\hat{\mathbf h}_u\|^2
\|\hat{\mathbf h}_v\|^2
}.
$$

### 14.2 相干度分组

建议按以下区间统计：

$$
\rho<0.2,
$$

$$
0.2\le\rho<0.5,
$$

$$
0.5\le\rho<0.8,
$$

$$
\rho\ge0.8.
$$

### 14.3 对比方法

至少比较：

1. 单天线 FFT top-1；
2. 双天线等增益合并；
3. MRC top-1；
4. SP-Dechirp，固定 \(\lambda=1\)；
5. SP-Dechirp，自适应 \(\lambda_u\)。

### 14.4 核心指标

首要指标为目标符号 top-1 命中率

$$
P_{\mathrm{top1}}
=
\Pr
\left[
\arg\max_k D_u[k]
=
s_u
\right].
$$

同时统计 signed margin

$$
\Delta D_u
=
D_u[s_u]
-
\max_{k\ne s_u}D_u[k].
$$

建议记录以下中间量：

- 目标 bin 的 \(|P_u[s_u]|^2\)；
- 目标 bin 的 \(|Q_u[s_u]|^2\)；
- 最强干扰 bin 的 \(|P_u[k_I]|^2\)；
- 最强干扰 bin 的 \(|Q_u[k_I]|^2\)；
- MRC margin；
- SP-Dechirp margin；
- 目标信道跨前导码一致性；
- 目标与最强干扰的信道相干度。

### 14.5 压力测试参数

重点测试：

$$
\mathrm{SIR}
\in
\{-20,-15,-10,-5,0\}\ \mathrm{dB},
$$

并分别报告不同相干度区间的结果。

最值得观察的现象是：

1. MRC 的干扰峰随干扰功率持续增长；
2. 在低相干区间，SP-Dechirp 的干扰峰转为负值；
3. 目标 bin 保持正值；
4. top-1 由功率竞争转变为空间极性竞争。

---

## 15. 论文贡献边界

仅提出

$$
|P_u[k]|^2-\lambda_u|Q_u[k]|^2
$$

并不足以形成完整顶会贡献。

更合理的论文逻辑应包括：

### 15.1 单输出解啁啾的结构性限制

证明在双天线、单标量输出、目标严格聚焦的约束下，时变 downchirp 无法同时消除多个任意独立干扰的相干常数项。

### 15.2 目标条件化的矩阵解啁啾

将传统标量 downchirp 扩展为双输出矩阵算子，显式保留：

- 目标信道投影；
- 目标正交投影。

### 15.3 有符号 FFT 判决域

构造不定二次型频谱

$$
D_u[k]
=
\mathbf Y^H[k]
\left(
\mathbf a_u\mathbf a_u^H
-
\lambda_u
\mathbf b_u\mathbf b_u^H
\right)
\mathbf Y[k].
$$

使目标与低相干干扰在判决域中获得相反极性。

### 15.4 near-far 无关的单源负化条件

证明当

$$
\rho_{uv}
<
\frac{\lambda_u}{1+\lambda_u}
$$

时，干扰的单源贡献为负，其符号不依赖干扰绝对功率。

### 15.5 信道估计误差下的可行条件

给出

$$
\rho_{u,\max}^{I}
<
\rho_u^{T}
$$

这一可分条件，并研究硬件相位漂移、信道估计误差和天线校准误差对可行区间的影响。

### 15.6 真实 LoRa 碰撞验证

重点证明：

> 即使 MRC top-1 被强干扰占据，SP-Dechirp 仍能在不搜索候选、不做 SIC 的情况下，使目标符号直接成为 top-1。

该实验结果将决定方案是否具备进一步扩展为完整论文的价值。

---

## 16. 当前结论

SP-Dechirp 的基本出发点不是继续设计更复杂的单输出时变 downchirp，而是承认双天线单标量输出存在自由度限制。

其核心变化为：

1. 不再将双天线观测过早压缩成一个非负功率谱；
2. 同时保留目标方向和目标正交方向的 FFT 证据；
3. 构造有符号判决谱；
4. 使低相干干扰从“较小的正峰”变为“负分数”；
5. 直接以 signed spectrum 的 top-1 输出目标符号。

最终判决为

$$
\boxed{
\hat s_u
=
\arg\max_k
\left(
|P_u[k]|^2
-
\lambda_u|Q_u[k]|^2
\right)
}
$$

该方案最明确的适用区域是：

- 双天线接收；
- 目标包同步参数已知或已估计；
- 目标信道估计稳定；
- 干扰与目标的信道相干度较低；
- near-far 差异明显；
- 需要低复杂度、非迭代的直接 top-1 解码。

下一步最关键的工作不是继续增加模块，而是使用真实接收数据验证：

$$
\rho_{uv}<0.5
$$

时，SP-Dechirp 是否能够系统性地将 MRC 的错误强干扰峰转为负值，并显著提高目标符号 top-1 命中率。
