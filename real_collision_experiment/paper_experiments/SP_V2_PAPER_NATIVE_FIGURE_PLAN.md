# SP-Decoder v2：文章原生最终版插图设计

本版不再从“已有 TODO 要求画什么形式”出发，而是先判断图片在正文中的证明责任，
再选择最少且足够的视觉证据。总体原则是：

- 一个 figure 只完成一个证明责任；
- 单个 figure 最多两个主要子图；
- 机制示例与总体统计明确分开；
- 优先使用读者熟悉的折线、方向图、热图、配对散点和分组柱状图；
- 不使用装饰性 3D，不重复正文公式，不留下只用于摆放图例的空白。

## Figure 2(a-b)：空间反证是否真实存在

**正文位置：** 2.5 动机实验 A。

**证明责任：** MRC wrong bin 不仅可能具有较强目标方向投影，还通常暴露更强的
目标正交反证。

**设计：**

- Figure 2(a) 使用一个真实 trace-driven MRC 错误符号，展示 target/wrong 两个
  bin 在支持、反证和 signed ranking 下的变化；
- Figure 2(b) 使用全部 MRC 错误事件的 \(\eta\) 配对分布，证明 Figure 2(a)
  不是孤立案例。

**逻辑：** 个例解释机制，分布证明普遍性。两张图均不展示全部 FFT bins，避免
视觉重心从“wrong bin 的额外反证”偏移到谱形状。

## Figure 2(c)：固定全局权重为什么不成立

**正文位置：** 2.5 动机实验 B。

**证明责任：** 不同碰撞包的最低 SER 权重区间不一定重合，且 SER 不随
\(\lambda\) 单调改善。

**形式：** 单面板在线性 \(0\)–\(10\) 横轴上绘制四个代表性碰撞包的完整
SER 曲线，数据点以 0.25 为均匀步长。星号标出各包最低 SER 区间的起点；
图例置于绘图区上方，并直接给出每个包的 SIR、相对起点和方向偏移。

**数据范围：** 图中四例只承担机制解释；候选生成过程保留在 sidecar 中，但不在
图片或正文中作为视觉重心。

**建议版宽：** 双栏。

## Figure 2(d)：方向误差下是否仍存在可用权重

**正文位置：** 2.5 动机实验 C。

**证明责任：** 在 SIR 驱动的碰撞前导方向误差下，固定的九点候选区间内是否
仍存在低 SER 工作点。

**形式：** 单坐标散点图。横轴为带符号方向误差，纵轴为 payload SER；底层均衡池
的每个碰撞计算 \(\{0,0.5,\ldots,4\}\) 九点，全部小圆点保留并以颜色编码
权重。不再绘制最低点菱形或 best-case envelope，只标出 SER=0.2 的 80%
符号成功率边界。

**学术定位：** 图中不突出读取 SER 的子集，也不声称所有碰撞在该角度范围内均可恢复。

**建议版宽：** 单栏。

## Figure 4：同一目标面对不同竞争包时的可靠性几何

**正文位置：** 4.3 包级归一化区分度。

**证明责任：** 同一个目标 \(L_u\) 固定时，竞争包空间几何仍可令 \(U_{uv}\)
发生巨大变化，因此同一 \(\lambda\) 不会对所有 pair 同样安全。

**形式：** 一张连续画布，不分割为三个独立坐标：

1. 左侧画目标、easy competitor 和 near-collinear competitor 三个方向；
2. 右侧紧接 \(L_u/U_{uv}\) 定量条形对照。

**关键数值：**

- easy pair：\(\widehat\theta_{uv}=85.3^\circ\)，\(U_{uv}=0.014\)；
- near-collinear pair：\(\widehat\theta_{uv}=0.2^\circ\)，\(U_{uv}=1.000\)；
- 两者共享 \(L_u=0.999\)。

**选择规则：** 同一实测目标的最低相干和最高相干竞争包。该图是机制对照。

**建议版宽：** 双栏。

## Figure 5：从包区间到 pair-wise risk

**正文位置：** 4.4 有限候选点上的反证权重选择开头。

**证明责任：** 先说明哪些包进入 \(\mathcal{I}_u\)，再说明集合中的每个成员如何
限制 \(\lambda\)。

**形式：** 仅两个子图，按模型构造顺序排列：

- 左图：packet timeline。蓝色背景为目标 payload 区间；相交的橙色包进入
  \(\mathcal{I}_u\)，灰色包被排除；
- 右图：与左图 \(v_1,\ldots,v_7\) 一一对应的风险热图。蓝色为正 margin，
  红色为负 margin，星号为 zero-margin flip。

**为何使用热图：** 该处需要同时比较全部 overlap 的安全区间，而不是精确读取每条
曲线极值。热图比 3D 曲线更适合完成集合级比较。精确下包络选择留给 Figure 7。

**建议版宽：** 双栏。

## Figure 6：有限候选是否足以替代 dense search

**正文位置：** 4.4 候选集合定义之后。

**证明责任：** 有限候选必须同时在选择目标和最终解码结果上接近 dense reference。

**形式：** 两个子图：

- 左图：dense \(\lambda\) 与 finite \(\widehat\lambda\) 的配对散点；颜色区分
  objective 精确匹配与非零 gap，并在图内报告 objective/weight 的 95th percentile；
- 右图：finite 与 dense 的 SER/PRR 分组柱状图，直接标注 percentage-point 差异。

**总体结果：**

- 94% 场景 objective 精确匹配；
- 95th objective loss 不超过 0.163%；
- 95th weight difference 不超过 0.713%；
- PRR 差为 0.000 pp。

**数据范围：** 全部 240 个 formal collision scenes，不挑选。

**建议版宽：** 双栏。

## Figure 7：在线如何选择 \(\widehat\lambda_u\)

**正文位置：** 4.4 有限候选集合和最终 argmax 之后。

**证明责任：** 读者需要在一张图中看到 pair curves、worst-pair envelope、
有限候选点和最终选择之间的关系。

**形式：** 单个二维坐标：

- 灰色虚线：用于解释的 pair curves；
- 黑色粗线：\(G_u(\lambda)=\min_vR_{uv}(\lambda)\)；
- 蓝点：在线实际求值的有限候选；
- 红星：候选中使 \(G_u\) 最大的 \(\widehat\lambda_u\)；
- 灰色竖虚线：仅用于解释的 envelope switches。

候选来源以一个紧凑文本框列出，不再增加流程子图或多类 marker 图例。

**选择规则：** 受控四包碰撞保留实测方向和可靠性锥，仅声明三路 SIR；构造要求
$v_3\!\to\!v_1\!\to\!v_2$ 三段下包络，且两次 switch 分别贴近固定
$1/4$ 和 $3/4$ coverage 点。总体逼近精度由 Figure 6 保证。

**建议版宽：** 单栏宽图或双栏。

## Figure 8：稳健包级空间统计怎样抑制污染快照

**正文位置：** 5.3 稳健包级空间统计。

**证明责任：** 干扰进入前导窗口后，local isolation 和角残差能够降低这些窗口的
聚合权重，从而改善最终 \(\widehat{\mathbf h}\)。

**形式：** 两个子图：

- 左图共用同一时间轴：蓝线为 snapshot direction error，绿/紫线为 isolation 和
  robust weight，红色区域表示干扰开始重叠；
- 右图只比较与该论点直接相关的 5-bin unweighted 和 robust estimate。

**案例结果：** 方向误差由 0.039° 降到 0.011°，降低 72%。

**学术边界：** selected measured case，只展示机制，不声称所有 pair 均改善 72%。

**建议版宽：** 双栏。

## 空气信道测量 I：包内相干性

**正文位置：** 6.2 空气信道测量。

**证明责任：** 重复前导 chirps 能提供稳定的包级信道方向，误差随 SNR 变化。

**形式：** 两个子图：

- 左图为 \(-5\) dB 下全部包的误差直方图，并在图内嵌入一个实测包的 8-chirp
  轨迹；
- 右图为全部 SNR 下的 median/IQR。

这样既保留单包直觉，又不为单包示例额外增加第三个子图。

**数据范围：** 全部 9,408 个 chirp observations。

## 空气信道测量 II：碰撞下的信道估计

**正文位置：** 6.2 空气信道测量。

**证明责任：** SIR 与 FFT-bin separation 如何共同影响碰撞中的目标信道估计。

**形式：**

- 左图为 SIR × bin separation 的带数字 median-error 热图；
- 右图用共享 log 纵轴绘制三个 SIR 的 median/IQR，并标出 4-bin 转折区域。

**数据范围：** 全部 200 次 measured-waveform collisions。

**建议版宽：** 双栏。

## 复现命令

```bash
python3 real_collision_experiment/paper_experiments/render_sp_v2_paper_native_figures.py \
  --data-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --source-figure-dir real_usrp_outputs/sp_paper_figures \
  --out-dir real_usrp_outputs/sp_v2_paper_native_figures
```

代表性案例选择规则、全量统计范围和各图 proof obligation 记录在输出目录中的
`paper_native_figure_manifest.json`。
