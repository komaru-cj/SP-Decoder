# 6. 评估

本节依次回答三个问题：双天线空间方向能否在一个 LoRa 帧内稳定测得；在小时间偏移的实测波形碰撞下，该方向估计和符号恢复如何随 SNR、SIR 变化；以及该判决是否能转化为室内、室外并发流量中的 PRR 与有效吞吐量收益。叙述按“实验平台与指标—物理层测量—端到端并发性能”组织。

## 6.1 实验设置

**平台与 PHY。** 我们使用两路相位同步的 USRP B210 接收机和 COTS SX1276 LoRa 节点。除特别说明外，室内主实验采用 SF10、BW 125 kHz、CR 4/5；室外扩展实验采用 BW 250 kHz，并报告 SF8 与 SF10。所有结果使用标准 LoRa FEC 与 PHY CRC：一个 payload 仅当 CRC 闭合且去重后的 payload identity 有效时计为成功。

**比较方法与公平边界。** 比较 LoRaWAN、MRC、CIC、PCube、MaLoRaGW 和 SP-Decoder。真实空口的主比较采用共享匿名物理候选和 pre-payload fine start/CFO/STO：LoRaWAN 与 MRC 在该同步上解调；CIC、PCube 和 MaLoRaGW 可在局部 preamble/sync/SFD 窗口内执行各自的参数估计。共享前端不向基线暴露 payload FFT、符号判决、FEC/CRC 结果、SP 的 $\lambda$ 或空间残差。因此，比较隔离的是在同一认证候选集合上的解码差异，而非每个系统完整 native detector 的端到端召回率。

**指标。** PRR 定义为去重后的 CRC 成功 payload 数除以 $\min\{\text{计划包数},\text{匿名物理候选数}\}$；有效吞吐量为 CRC 成功 payload bit 数除以 $\max\{\text{业务窗口},\text{post-shared-sync decoder work time}\}$。后者把慢于实时的解码工作显式计入分母。对受控 trace 场景，我们还报告逐 symbol SER 和每个碰撞场景的 estimation-plus-decoding 墙钟时间。图 11、图 12 和图 14 的每个设置当前只有一次可用实测运行，故图中不绘制 95% 置信区间；图 13 的场景统计则按场景给出均值及区间。

## 6.2 参数敏感性测试

SP-Decoder 在全文固定使用 $\gamma=0.05$ 和 $\lambda_{\max}=4$。其中，$\gamma$ 是可靠性风险约束的全局裕量；$\lambda_{\max}$ 只是防止异常数值扩张的统一实现上限，而不是每个场景手工调节的增益。实际的可行区间由 packet-level cap 决定，最终 $\widehat\lambda_u$ 仍由目标--竞争包的 max--min 配置在该区间内一次性选择。

**有限候选覆盖。** 图 6 使用 30,000 个由实测方向和可靠性锥构成的受控竞争场景，比较生产策略的三个固定内点与将其替换为 10,000 个均匀内点的策略。候选选择只读取前导统计和下包络目标，不读取 payload、SER、PRR 或 CRC。生产策略中，区间端点、解析 flip/peak 点、自适应中点和三个固定内点分别赢得 53.64%、38.64%、0.36% 和 7.36% 的场景；即使给出 10,000 个内点，端点和解析点仍分别赢得 52.18% 和 36.03%。因此，解析候选覆盖的是竞争几何的真实切换点，不能被盲目稠密采样替代。对应的 10 个 trace-driven IQ 碰撞中，三内点和 10,000 内点的平均 SER 同为 0.153，而前者的候选构造与选择时间为 0.650 ms，低于后者的 1.338 ms。

![图 6：以 10,000 个均匀检查点作对照时，各类候选点成为下包络赢家的份额。](real_usrp_outputs/sp_v2_paper_native_figures/candidate_winner_share_10000_checkpoints.png)

**全局常数扫描。** 为检验默认常数并非按场景调参，我们固定随机种子、10 个目标/干扰 IQ 包对、SIR、非整数起点和 payload 判决，仅联合扫描五组全局常数：$(0.01,1)$、$(0.02,2)$、$(0.05,4)$、$(0.10,8)$ 与 $(0.20,16)$。图 7 和下表报告生产有限候选策略的平均 SER 与零-SER 包比例。常数从 $(0.01,1)$ 放宽至默认 $(0.05,4)$ 时，平均 SER 从 0.226 降至 0.153；之后继续放宽两档并没有额外收益。因而正文统一采用 $(0.05,4)$：它避免过小上限截断有效配置，又不依赖更宽松的全局取值。该联合扫描旨在证明一组默认常数可跨同一批真实碰撞复用，而非分别归因 $\gamma$ 与 $\lambda_{\max}$ 的边际效应；所有后续图均固定使用默认值。尤其是，$\lambda_{\max}$ 始终只是统一实现上限，核心自适应仍来自 packet-level cap 与包间 max--min 配置。

![图 7：同一批 10 个 trace-driven 实测波形碰撞上，五组全局常数的平均 SER；绿色为正文默认值。](real_usrp_outputs/sp_v2_paper_native_figures/parameter_sensitivity_mean_ser.png)

| 全局常数 $(\gamma,\lambda_{\max})$ | 平均 SER | 零-SER 包比例 |
| --- | ---: | ---: |
| 偏小 $(0.01,1)$ | 0.226 | 0.40 |
| 较小 $(0.02,2)$ | 0.216 | 0.40 |
| 默认 $(0.05,4)$ | 0.153 | 0.40 |
| 较大 $(0.10,8)$ | 0.153 | 0.40 |
| 偏大 $(0.20,16)$ | 0.153 | 0.40 |

## 6.3 空气信道测量

双天线信道写作 $\mathbf h=[h_0,h_1]^T$。为剥离共同复相位与整体增益，我们使用复射影角

$$
d(\mathbf h_1,\mathbf h_2)=\arccos\frac{|\mathbf h_1^H\mathbf h_2|}{\|\mathbf h_1\|_2\|\mathbf h_2\|_2},
$$

并以跨天线相对相位的符号为该角赋予方向，得到带符号方向偏差 $\Delta\psi$。因而 $|\Delta\psi|=d$；分布的宽度而非有符号均值，才表示估计误差。

**帧内相干性。** 我们从 isolated clean corpus 的 50.25-symbol 标准帧抽取完整 chirp 快照。帧由 8 个 preamble、2 个 sync、2.25 个 SFD 和 38 个 payload symbols 组成；其中 50 个完整 chirp 进入逐 symbol 测量，末尾 0.25 个 SFD 不被误作完整符号。图 8(a) 在 SNR $=-20$ dB 下展示一个完整帧：尽管低 SNR 会放大逐 chirp 抖动，估计仍围绕同一包级方向波动，而没有随 payload 持续漂移。图 8(b)--(d) 分别汇总 SNR $=-20,-10,0$ dB 的误差分布。由 $-20$ dB 至 0 dB，分布从十余度量级迅速收缩到零附近，说明包级前导估计在中等及以上 SNR 下具有稳定的空间参考；极低 SNR 下则应将该不确定性传递给后续可靠性约束，而不能把单次快照当作精确 CSI。

![图 8：碰撞自由包的 50.25-symbol 帧内方向误差与 SNR 分布。](real_usrp_outputs/sp_v2_paper_native_figures/fig_air_within_packet_coherence.png)

**并发前导估计。** 随后将两个 clean-corpus 实测波形以 $\Delta\tau=0.2T_s$ 错开后相加。为避免近共线信道掩盖空间判别作用，target--interferer 对预先限制在 $20^\circ$--$60^\circ$ 的测得射影夹角；300 个随机基准对的实际范围为 $20.3^\circ$--$60.0^\circ$，中位数为 $38.5^\circ$。图 9(a) 的 SIR $=-20$ dB 轨迹表明，干扰最强时前导个别快照仍会出现偏离；但图 9(b)--(d) 显示 SIR 从 $-20$ dB 提升至 $0$ dB 后，误差质量迅速集中到零附近。该结果说明 SP 的稳健前导聚合能在非整数时间错开、但仍高度重叠的碰撞中保留目标空间方向。

![图 9：$\Delta\tau=0.2T_s$ 实测波形碰撞下的方向估计误差。](real_usrp_outputs/sp_v2_paper_native_figures/fig_air_concurrent_channel_estimation.png)

**SNR--SIR 压力测试。** 图 10 在每个 SNR$\times$SIR 单元重放同一批 300 对碰撞（共 4,800 次条件评估），从而使单元差异不混入不同波形对的抽样差异。SER 随 SIR 提升整体下降：在 SNR/SIR $=(-20,-20)$ dB 时为 0.393，SIR 提升到 $-10,0,10$ dB 后依次为 0.266、0.136 和 0.117；在 $(-10,-10)$ dB 时为 0.147。高 SIR 且 SNR 不低于 $-10$ dB 时，SER 已降至 $0.003$ 以下。该二维结果同时表明：低 SNR 与强干扰叠加时，有限天线维度仍会受到显著污染；而当目标空间方向可可靠估计时，有符号空间 bin 判决能够在零额外 FFT-bin 分离下抑制该污染。

![图 10：20°--60° 方向分离、$\Delta\tau=0.2T_s$ 碰撞的 SER 热力图。](real_usrp_outputs/sp_v2_paper_native_figures/fig_air_collision_ser_heatmap.png)

## 6.4 并发实验

**室内负载扩展。** 图 11 和图 12 使用严格的业务中间 5 s 窗口，在 BW 125 kHz 与 250 kHz、每节点 25% duty 下，将活跃节点数从 3 扩展至 24。负载增加时所有方法的 PRR 都下降，但 SP-Decoder 在两种带宽下保持最高或并列最高的 PRR，并保持明显更高的有效吞吐量。例如在 BW 250 kHz、$N=24$ 时，SP-Decoder 的 PRR 为 0.194、有效吞吐量为 1,024 bit/s；PCube 为 0.158 和 506 bit/s，MRC 为 0.036 和 192 bit/s。BW 125 kHz、$N=24$ 时，SP-Decoder 与 PCube 的 PRR 同为 0.237，但 SP-Decoder 的有效吞吐量为 608 bit/s，高于 PCube 的 491 bit/s。这一差异来自 CRC 成功数和 decoder work time 的共同作用，而不只是无线侧成功数。

![图 11：室内负载扩展下的 PRR。](real_collision_experiment/analysis/fig9_10_12_5s/fig9_prr_preview.png)

![图 12：室内负载扩展下的有效 decoder TPS。](real_collision_experiment/analysis/fig9_10_12_5s/fig10_tps_preview.png)

**Clean-packet 瞬时高阶碰撞。** 图 13 从 clean corpus 中随机选择不同位置的双接收信道方向和 CFO，构造 2、4、6、8、10 包的密集瞬时碰撞。每包均使用固定种子生成的 50.25-symbol、CRC-enabled LoRa 帧；在每个场景中，所有包的起点被压缩到少于一帧的窗口内，因此最后一包接入时所有包仍在空口。我们对每个碰撞阶数随机生成 10 组不同 position 组合（共 50 组），并在每包 20 dB SNR 下报告均值和 95% bootstrap 区间。三种方法共享同一候选与精同步边界，以隔离 payload 决策的差异：PCube 使用 PDoA 聚类，SP-Decoder 使用有符号空间评分，PCube+SP 仅将 PCube 的 PDoA-clustered FFT-bin 集合作为 SP 的输入；SP 的 packet-level channel 和 $\lambda$ 保持不变，且 cluster/bin 选择不读取 CRC、payload 或真值。

随着阶数升高，PRR 按预期下降；SP-Decoder 在 6、8、10 包下分别达到 0.533、0.388 和 0.210，高于 PCube 的 0.400、0.325 和 0.120。更重要的是，PCube+SP 在相同 PCube 聚类边界下分别达到 0.467、0.363 和 0.130：它在 6--10 包均优于 PCube，说明 SP 可作为 PCube cluster 后端的可插拔 bin scorer；但其仍低于独立 SP，表明过窄的 PDoA cluster 有时会提前排除正确 bin。该结果给出的是接口兼容性和收益边界，而非声称级联必然超过 SP。时间上，PCube+SP 为约 247--268 ms/candidate，包含 PCube 的前导 PDoA 聚类、SP 的 packet-level $\lambda$ 配置和受限 signed decoding。

![图 13：clean-packet trace-driven 密集瞬时碰撞下 PCube、SP-Decoder 与 PCube+SP 的解码开销和 PRR。](real_usrp_outputs/fig11_clean_instantaneous_plugin/fig11_clean_instantaneous_time_prr.png)

**近距离节点。** 图 14 将两个发射节点的间距从 2 cm 扩展至超过 20 cm，并把 per-node duty cycle 提高到 75%。该图保留 MRC、PCube、MaLoRaGW 与 SP-Decoder，以聚焦碰撞解码器在空间方向接近时的退化；LoRaWAN 与 CIC 的结果已在负载扩展实验中报告。SP-Decoder 在全部距离分组保持 0.881--0.974 的 PRR；在 10 cm 处，SP-Decoder 为 0.949，PCube 和 MaLoRaGW 分别为 0.667 和 0.692，而 MRC 未恢复有效 payload。结果表明，空间方向不完全正交时，利用正交残差进行反证仍比只保留正向投影更稳健。

![图 14：室内近距离双节点、75% duty 下 MRC、PCube、MaLoRaGW 与 SP-Decoder 的 PRR。](real_collision_experiment/analysis/fig9_10_12_5s/fig12_prr_preview.png)

**室外泛化。** 最后，我们在 BW 250 kHz、每节点 25% duty 的室外采集上评估 SF8 和 SF10；$N=3,6,9,12,15$ 为物理采集，$N=18,21,24$ 由时间对齐的真实 IQ 叠加构造，所有点仍以严格中间 5 s 和共享匿名候选统计。图 15 显示，随着节点数上升，PRR 下降是预期现象，但 SP-Decoder 在两种 SF 下维持较高的有效吞吐量。SF8、$N=24$ 时，SP-Decoder PRR 为 0.205、有效吞吐量为 2,651 bit/s，高于 PCube 的 0.160、246 bit/s；SF10、$N=24$ 时，SP-Decoder 为 0.216、1,280 bit/s，PCube 为 0.168、568 bit/s。该结果覆盖了比室内低速 SF10/BW125 更短和更长的空口时间尺度，说明收益并不依赖单一 PHY 配置。

![图 15(a)：室外 SF8 下的 PRR。](real_collision_experiment/analysis/outdoor_fig13_5s/fig13_sf8_prr.png)

![图 15(b)：室外 SF8 下的有效 TPS。](real_collision_experiment/analysis/outdoor_fig13_5s/fig13_sf8_tps.png)

![图 15(c)：室外 SF10 下的 PRR。](real_collision_experiment/analysis/outdoor_fig13_5s/fig13_sf10_prr.png)

![图 15(d)：室外 SF10 下的有效 TPS。](real_collision_experiment/analysis/outdoor_fig13_5s/fig13_sf10_tps.png)

综上，微基准确认双天线方向在 50.25-symbol 帧内可测，并量化了低 SNR/SIR 下的误差边界；受控碰撞显示该边界对应的 SER 行为；室内和室外并发流量则表明，SP-Decoder 将这些空间信息转化为更高的 CRC 成功率与更高的有效吞吐量，同时保持与 MRC 同阶的解码开销。
