# 修改版 SP：值得写入正文的设计与可用草稿

当前实现已进一步升级为 `pair_and_noise_reference_guard_v2`。下文噪声竞争与候选搜索仍适用；原两轨道门控是基础保护。双包分支现在还统一CFO补偿后的MRC参考与功率标尺，并加入空间可分、强度置信及正裕量保护；多包主导干扰幅度/剩余干扰门控仍属未来工作。用户明确保留单分支，不按负载CRC选择λ。

新增可靠性设计可写在配置与实现部分：**Confidence-gated counter-evidence.** A more favorable normalized surrogate does not necessarily indicate recoverability when its signed margin remains negative. We therefore enable extended counter-evidence only when the observed spatial cones are separated, preamble strength estimates indicate a confidently dominant competitor, and the proposed joint margin is positive. Otherwise, the receiver selects zero weight before payload decoding. The fallback combiner is mapped into whitened coordinates to reproduce physical MRC at the supplied synchronization. These safeguards preserve single-path decoding and introduce no CRC-guided weight search.

强度置信采用前导平均高斯近似，只能作为经验性系统保护。参考/功率标尺统一属于实现正确性，不能包装成独立创新。细节、公式、实验限制见 `compare/SP_REFERENCE_GUARD.md`；应如实报告少数SP独有救回减少，不能宣称对所有部署都不劣于MRC。

## 1. 正文核心：显式考虑最大噪声竞争峰

### 价值与放置位置

建议在原 §4.2 的包间分离度后增加一个小段，在 §4.3 给出修订的配置目标。它解决的是明确的模型缺口：包间裕量变大，并不保证目标超过所有其他 FFT bin。原风险分母已有噪声方差，但没有把最大噪声竞争峰单独纳入目标。

原成对风险为 `R(λ)=(A+Bλ)/sqrt(C0+C2 λ²)`。其导数符号由 `B C0−A C2 λ` 决定。在 `A<0<B` 的强干扰条件，它随 λ 单调上升；仅放宽上限容易驱使选择器取过大的权重。这给出了增加噪声竞争项的设计动机，不能只写成“将最大 λ 从4调大”。

### 可用于正文的英文表述

**Noise-maximum-aware weight configuration.** A packet-pair margin compares the target with a structured interferer, but a larger pairwise margin does not ensure that the target outranks noise-dominated FFT bins. This distinction becomes important when the admissible counter-evidence range is enlarged. In particular, when the pair coefficients satisfy A<0<B, the pairwise surrogate increases monotonically with the weight and can favor unnecessarily strong penalties. We therefore add an explicit target-to-noise-maximum margin to packet-level configuration. The resulting weight balances suppression of structured interference against protection of the target from noise-induced ranking errors.

### 建议保留的公式

令 `n=σ_N²` 为每个正交 FFT 噪声投影的复方差，`M` 为 FFT 大小。白化复高斯噪声下，对非负 t，

`Pr(D_N>t)=exp(−t/n)/(1+λ)`。

对至多 `M−1` 个纯噪声竞争 bin 使用联合界，取

`τ_N(λ)=n [log((M−1)/α)−log(1+λ)]_+`。

本文实现采用每符号 `α=0.05`。这个参数不是原目标保护参数 `γ`，也不是整包错误预算。

使用前导估计的 S、L 建立目标响应的名义矩模型：

`μ_u(λ)=S_u L_u−λ S_u(1−L_u)+n(1−λ)`；

`V_u(λ)=n²+2nS_uL_u+λ²[n²+2nS_u(1−L_u)]`；

`R_uN(λ)=[μ_u(λ)−τ_N(λ)]/sqrt(V_u(λ))`。

在启用新分支时，配置目标为

`G_u^N(λ)=min{ min_v R_uv(λ), R_uN(λ) }`。

这是目标响应的标准化代理裕量。将 L 对应的名义分量代入方差，并不构成所有参考误差和混合信号下的严格最坏方差上界。严格的噪声超限界仅限于所述白化高斯噪声模型；目标矩估计、方向不确定性代理、结构化泄漏等使整体解码性能仍需实验验证。

### 公式之后的英文说明

Under the white complex Gaussian noise model, the nonnegative tail of an empty-bin score is exp(−t/n)/(1+λ). A union bound over at most M−1 noise-only competitors yields the threshold τ_N. We combine this threshold with preamble-derived target moments to construct a standardized target-to-noise margin, and maximize the minimum of this margin and the packet-pair margins. The threshold controls modeled noise-only exceedances; it does not bound total symbol or packet errors in mixed-signal bins.

不建议在贡献列表中单列“新增α参数”。正文描述其含义，具体取值放实现参数表，灵敏度放评价或附录。

## 2. 正文实现：按观测重叠轨道保守放宽

### 应如何定位

建议放原 §5.2，作为避免模型外推造成退化的系统策略。它重要，但当前依据不足以将“等于两个”包装成一般性理论结论或独立主要创新。动机是：多包时，目标 bin 也可能包含其他用户的贡献，纯目标加热噪声模型不足以描述其得分。

设 `q_hat_u` 为接收机检测到、与目标载荷重叠的竞争轨道数。启用新目标的条件是 `q_hat_u=1`，而不是已知真实发送包数为2。

- `q_hat_u=1`：使用 `G_u^N`，去掉额外固定4上限，但保留参考可靠性上限。
- `q_hat_u≥2`：保留原包间目标与固定上限4。
- 无竞争轨道或 L≤γ：保持 λ=0。

对 γ<L<1，可写成

`λ_cap,u = (L_u−γ)/(1−L_u)`，当 `q_hat_u=1`；

`λ_cap,u = min{4,(L_u−γ)/(1−L_u)}`，当 `q_hat_u≥2`。

上述为论文的名义表达。实现还保留数值正则化及用户显式设置的额外上限；正文不必展开工程选项。

### 可用于正文的英文表述

**Conservative relaxation from observed overlap tracks.** The noise-maximum model treats a target bin as a target response plus thermal noise. With several overlapping packets, that bin may also contain substantial structured interference, making unrestricted weight relaxation overly aggressive. The receiver therefore enables the extended range only when it currently observes one competing track overlapping the target payload. If it observes multiple competing tracks, it retains the bounded packet-pair configuration. Both branches preserve the reference-reliability constraint and configure one weight before payload decoding. The gate uses receiver observations rather than transmitted packet counts, identities, or decoded payloads.

### 必须保留的边界说明

This observational gate is an implementation safeguard, not a certificate that only two transmitters are active. Missed tracks and duplicate hypotheses can change its activation; its effect must therefore be assessed with the acquisition front end as well as under controlled synchronization.

已有 C 数据中，46场景触发新分支，其中26场景真实 K=2，14场景真实 K=4，6场景真实 K=6。这些真值只用于离线统计，不参与门控。这个结果支持明确报告误检/漏检下的门控行为，不支持将“两条检测轨道”等同“两包空口碰撞”。

不能把多包 PDR 保持原数值写成“新噪声模型保证多包稳定”：该分支直接沿用旧配置。可以写“保守分支避免了在这些场景中无条件放宽引起的退化”，并交代对照来源。

## 3. 正文简述、附录展开：有限候选搜索

它是支持设计1可实现的必要配套，不建议独立列为贡献。

**正文可用句：** To cover the enlarged range without dense online search, we augment the packet-derived candidates with geometric checkpoints and pair/noise-margin intersections. The selected weight remains fixed throughout the packet, and no CRC-guided weight retry is introduced.

几何序列起点1/16、倍增规则和求根容差放附录或实现参数表；正文只需说明候选覆盖机制。交点通过有界标量求根获得，不应写成全为解析解，也不应宣称得到任意场景下的精确连续最优解。

新增候选后，原文 `|C_u|≤K_u+5` 的具体上界不能直接沿用。还需核对原有实现中的极性中点候选。多竞争者分支仍保持原有量级；两轨道分支额外代价由几何区间数及标量求根迭代决定。逐符号的投影、签名排名和FFT复杂度没有改变，但完整运行时间需重新测量，不能复用旧论文的加速百分比。

### 已有附录支撑数据

对当前缓存中2007个有效两轨道配置，候选数最少5、中位数18、90分位23、最多25。与8192个正对数网格点加零点的离线扫描比较，最大归一化目标差为 `3.7342e−5`；归一化分母为 `max(1,abs(G_dense))`。保存目标值与重新计算值的最大绝对差为 `1.43e−14`。

这验证的是有限搜索对代理目标的覆盖，不是 PDR 最优性，也不是任意信道的理论保证。数据见 `real_usrp_outputs/revision_abc_noise_two_packet_v1/finite_search_audit.json`。

## 4. 评价怎样支撑“可靠性增强”

建议至少区分以下策略，不只放最终热图：

1. 原始成对配置与上限4。
2. 仅放宽上限，不加入噪声竞争（已有关键双包切片；未完成全部多包切片）。
3. 加入噪声竞争，但不作观测轨道门控（已有1536场景重放）。
4. 最终两轨道门控策略（已有完整场景缓存的精确分支复用，另有8个重建波形场景的权重核对；尚不是整套门控接收机的重新解码运行）。

| 条件 | 原版 | 全场景噪声竞争 | 两轨道门控 |
|---|---:|---:|---:|
| SNR10/SIR−20，10–60° | 50% | 93.75% | 93.75% |
| SNR10/SIR−20，0–10° | 0% | 56.25% | 56.25% |
| SNR−20/SIR0，10–60° | 0% | 25% | 25% |
| A：7包、SNR0 | 79.46% | 62.95% | 79.46% |
| B：10包、SNR0 | 88.75% | 61.88% | 88.75% |

双包格每格16场景，A为32场景/224包，10包为16场景/160包。固定实测源库上的Monte Carlo重复属于开发及验证数据，不能称为独立部署或独立留出测试集。MRC在−20dB普通夹角/SIR0的PDR为43.75%，所以不能据此写“已经解决低SNR退化”。

建议报告的可靠性证据：PDR之外保留相对MRC的救回/伤害、λ及上限分布、门控触发时的漏检情况、参数α的敏感性、候选数量和单次配置开销。哪些尚未完成就留为待补验证，不在文字中预先承诺结果。

## 5. 哪些不应写成新增关键设计

- 固定数值4改成16/1024：只是参数调整；应写为有模型依据的受约束配置机制。
- α=0.05、γ取值、几何步长、容差：参数表/附录。
- 原有 S、L、U、噪声统计与强度自适应：已在原文中，不能再列新贡献。
- CRC重选λ、主导干扰幅度门控、按幅度动态设cap：尚未实现，不能写成现有功能。
- MRC+CIC、MRC+CoRa与A/B/C模拟：分别属于公平基线和验证方法，不属于SP接收算法新增模块；需要写进评价。
- 原文二值快照权重与既有代码软权重、固定方向容差的差异：应如实统一论文和实现，但没有独立对照证据前，不包装成新的可靠性贡献。

## 6. 摘要/贡献列表建议

若保留新增设计，建议合为原“包级配置”的增强，不新增多条主贡献：

We extend packet-level spatial configuration with an explicit noise-maximum competitor and conservative, observation-based range relaxation. This preserves once-per-packet configuration while addressing strong-interference suppression and excessive counter-evidence penalties.

正文与评价需明确模型假设和现有边界，不能把这句话扩展成“所有低SNR/小角度/高阶碰撞均稳定优于MRC”或“对包交付提供理论保证”。
