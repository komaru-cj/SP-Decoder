# SP-Decoder v2 清晰版论文图设计逻辑

## 1. 总体原则

本版不再追求“单张图塞入尽可能多的算法元素”，而采用以下统一规则。

1. **一张图只回答一个研究问题。** 标题直接写问题所对应的结论，但不使用
   “dramatic”“radically superior”等宣传性表述。
2. **自然阅读顺序。** 多子图统一按照“观测现象 → 方法动作 → 最终结果”
   从左向右排列。
3. **颜色含义固定。**
   - 蓝色：目标、有限候选或正 margin；
   - 绿色：可靠、修复或低误差；
   - 橙色：不确定目标或中间状态；
   - 红色：负 margin、污染或损伤；
   - 黑色：需要优化的主目标，例如下包络 \(G_u\)。
4. **示意图与统计图分工。** 机制图可以选择最易理解的代表性 case，但必须
   标注 `selected/representative case`；承担总体结论的统计图使用全部样本。
5. **取消装饰性 3D。** 三维透视会同时扭曲曲线高度、遮挡交点并增加图例负担。
   多 pair 的 \(R_{uv}(\lambda)\) 改用风险热图，单包选择过程保留二维下包络。
6. **图内文字只解释编码规则。** 公式推导和完整实验条件写入 caption 或正文，
   不在图中重复论文段落。

## 2. Figure 2(a)：一个错误符号中的 signed ranking

### 论文问题

MRC 选错的 bin 是否同时暴露了更强的目标正交反证？

### 表达方式

直接采用 `fig1_sp_core_observation`。图中只强调 target bin 和 MRC wrong bin，
比较支持能量、正交反证以及加入 signed penalty 后的排序变化。

### 阅读顺序

1. MRC 只看支持能量，因此选择 wrong bin；
2. wrong bin 的正交反证更大；
3. signed score 惩罚该 wrong bin，target bin 回到 top-1。

### 学术边界

它是一个机制示例，不能单独证明总体增益；总体规律由 Figure 2(b) 支撑。

## 3. Figure 2(b)：错误峰的空间不一致性分布

### 论文问题

Figure 2(a) 中的现象是个例，还是在大量 MRC 错误事件中普遍存在？

### 表达方式

采用 `fig3_eta_distribution`，在同一对数横轴上比较 target bin 和 MRC wrong bin
的 \(\eta\) 配对分布。视觉中心是两个中位数虚线及其数量级差异。

### 阅读顺序

先比较中位数位置，再观察两个分布的主体是否分离。该图不再展示全部 FFT bins，
避免读者寻找与论点无关的谱峰。

## 4. Figure 2(c)：为什么不能使用固定全局 \(\lambda\)

### 论文问题

不同实测波形碰撞包的最低 SER 工作区间是否重合？过大的反证权重是否会重新
损伤目标符号？

### 图形设计

- 使用单个线性坐标，在 \(0\)–\(10\) 上以 0.25 的均匀步长绘制四条
  payload SER–\(\lambda\) 曲线；
- 星号标出最低 SER 集合中的最小权重；
- 图例移到绘图区上方，并列出每个包的 SIR、相对起点和方向偏移。

### 数据范围

展示案例要求最低 SER 不超过 3%、相对 \(\lambda=0\) 至少修复 50 个百分点，
并保证目标包和干扰包不重复。该选择读取 SER，必须明确标为 illustrative cases，
不能用于总体性能结论；候选池统计不进入图片或正文主叙事。

### 视觉结论

四个最低 SER 区间没有共同交集，且曲线在过大权重下重新回升。均匀网格把
旧图中未解析出的区间边界进一步细化，正文以生成 sidecar 中的新边界为准。

## 5. Figure 2(d)：方向误差下是否仍存在可用权重

### 论文问题

当前导碰撞使估计方向偏离真实目标方向时，固定候选区间内是否仍存在低 SER
的 counter-evidence weight？

### 表达方式

横轴为碰撞前导估计相对 collision-free 目标方向的带符号误差，纵轴为 payload
SER。底层 72 个碰撞均计算 \(\lambda\in\{0,0.5,\ldots,4\}\)，全部 648 个
评估全部作为分散的小圆点展示，不再使用菱形或 best-case 高亮。SER=0.2 以下区域标为至少
80% 符号成功率。

### 逻辑

该图承接 Figure 2(c) 的包相关工作点，并为第 4 节的在线配置提出证明责任。
图只用完整散点分布证明约 \(\pm10^\circ\) 的偏差下仍常存在可用权重。

## 6. Figure 4：Reliability geometry

### 论文问题

为什么相同目标包面对不同竞争包时，安全的 \(\lambda\) 可以完全不同？

### 子图设计

- **(a) Easy competitor。** 蓝色目标方向与绿色竞争方向接近正交，
  实测射影夹角为 \(85.3^\circ\)。
- **(b) Near-collinear competitor。** 红色竞争方向几乎覆盖蓝色目标方向，
  射影夹角只有 \(0.2^\circ\)。
- **(c) 能量界比较。** 同一个目标使用同一条
  \(L_u=0.999\) 蓝色虚线；竞争包上界 \(U_{uv}\) 从 0.014 增至 1.000。

### 为什么采用方向箭头

“near-collinear”本质是几何关系。角度尺或极坐标柱需要读者先翻译数值；
两个箭头是否重合则可以直接感知。右侧的 \(L_u/U_{uv}\) 条形图再把直觉连接到
第 4.3 节公式。

### 选择规则

同一实测目标分别选择空间相干性最低和最高的实测竞争包。这是代表性对照，不是
总体分布。

## 7. Figure 5(a)：由时间区间构造重叠集合

### 论文问题

哪些已检测包应进入目标 \(u\) 的竞争集合 \(\mathcal I_u\)？

### 表达方式

蓝色竖向背景表示 target payload 区间；每一行是一个包，浅色段为前导码，
深色段为 payload。橙色包只要与蓝色区间相交就打勾并进入 \(\mathcal I_u\)；
灰色 excluded packet 完全错过该区间。

### 视觉结论

该图只解释时间集合，不同时解释 \(R_{uv}\) 或 \(\lambda\)，避免模型层次混杂。

## 8. Figure 5(b)：所有 overlap 的 pair-risk

### 论文问题

进入 \(\mathcal I_u\) 后，不同竞争包如何共同限制可用的 \(\lambda\)？

### 表达方式

取消三维曲线，改为二维风险热图：

- 每一行对应一个竞争包 \(v\)；
- 横轴为 \(\lambda\)；
- 蓝色表示 \(R_{uv}(\lambda)>0\)，即正 margin；
- 红色表示 \(R_{uv}(\lambda)<0\)，即负 margin；
- 黄色星号标出该 pair 的 zero-margin flip。

### 为什么热图更合适

该处的目的不是精确读取曲线局部极值，而是建立“每个 overlap 给出不同安全区间”
的认识。热图可以同时显示全部 7 个 pair，且不会产生三维透视遮挡。曲线精确形状
和下包络最大值留到 Figure 7。

### 视觉结论

\(v_1\)–\(v_3\) 基本保持正 margin；\(v_4\)–\(v_6\) 需要不同大小的
\(\lambda\) 才翻为正；近共线的 \(v_7\) 在整个区间仍为负。

## 9. Figure 6：有限候选点是否逼近 dense search

### 论文问题

常数规模的在线候选集合，是否在 objective、所选权重和最终解码三个层面接近
高分辨率离线搜索？

### 子图设计

- **(a) Objective CDF。** 直接报告 94% 场景精确匹配，95th percentile loss
  不超过 0.163%。
- **(b) Dense-vs-finite 配对散点。** 横轴为 dense \(\lambda\)，纵轴为 finite
  \(\widehat\lambda\)，虚线为完全一致。少数偏离对角线的场景仍得到相同的符号错误数，
  因而不能只凭权重数值差异判断解码损失。
- **(c) 最终 SER/PRR。** 每个指标用方块和圆点配对，直接标注 percentage-point
  差值；PRR 差为 0.000 pp。

### 数据范围

全部 240 个 formal collision scenes，不挑选 case。

### 论证链

该图依次验证“优化目标接近 → 所选配置大体一致 → 最终通信结果不受损”，避免只用
一张相同高度的柱状图宣称候选点有效。

## 10. Figure 7：有限包级配置的在线过程

### 论文问题

接收机不做 dense search 时，实际如何得到 \(\widehat\lambda_u\)？

### 子图设计

- **(a) 下包络。** 灰色虚线为用于解释的部分 pair curves，黑色粗线为
  \(G_u(\lambda)=\min_vR_{uv}(\lambda)\)。蓝点是在线真正求值的有限候选，
  红星是候选中 objective 最大的点。
- **(b) 三步流程。** `Build candidates → Evaluate → Select` 自上而下排列，
  与算法正文顺序一致。

### 为什么不再区分五种 marker

读者在理解“有限点足够”时，首先只需区分“在线求值点”和“连续解释曲线”。
boundary、flip/peak、midpoint、coverage 的来源已在右侧第一步和正文公式中列出，
无需再让每一类 marker 占用一条图例。

### 选择规则

使用一个受控四包碰撞：信道方向和可靠性锥来自实测包，只声明三路 SIR，
使最坏 pair 依次经历 $v_3\!\to\!v_1\!\to\!v_2$，且两次切换分别贴近
$\lambda=1$、$\lambda=3$ 的固定覆盖点。这是机制案例；有限点的总体近似精度由
Figure 6 的 240 个场景给出。

## 11. Figure 8：稳健包级空间统计

### 论文问题

当干扰从部分前导窗口进入后，稳健聚合怎样避免污染最终目标信道方向？

### 阅读顺序

- **(a) 观测。** 只画论文实际采用的 5-bin 快照。红色背景从 \(p=3\) 开始，
  表示干扰重叠，角误差随之上升。
- **(b) 动作。** 同一时间轴上，local isolation 和 robust weight 同步从约 1
  降至约 0.2。
- **(c) 结果。** 只比较与本节论点直接相关的 `5-bin unweighted mean` 和
  `5-bin robust estimate`，方向误差由 0.039° 降至 0.011°。

### 为什么删除 1/3-bin 曲线

多 bin kernel 的选择不是本图承担的主要论点。同时画 1/3/5-bin 会让读者误以为
本节重点是 kernel ablation，而不是 isolation-aware robust aggregation。

### 学术边界

这是一个选择出的实测机制案例，只能说明算法如何起作用；不能据此声称每个 pair
都获得 72% 改善。

## 12. 6.2 包内相干性

### 论文问题

在噪声作用下，同一包的前导 chirps 是否仍能提供稳定的空间方向？

### 子图设计

1. 选择一个稳定的 \(-5\) dB 实测包，展示 8 个 chirp 的方向误差；
2. 使用全部包在 \(-5\) dB 下的直方图，标出 median 2.41° 和 90th 4.35°；
3. 使用全部 SNR 点绘制 median 和 IQR，并采用 log 纵轴。

单包示例负责直觉，后两图负责总体统计，二者不混为一个结论。

## 13. 6.2 并发信道测量

### 论文问题

在受控碰撞中，FFT-bin separation 和 SIR 如何共同影响目标信道估计？

### 子图设计

- **(a) 数字热图。** 行是 SIR，列是 bin separation，每格直接写 median
  channel-direction error。颜色采用 log normalization，使 0.3°–35° 的跨度
  都有可见差异；红色表示高误差、绿色表示低误差。
- **(b) 共享趋势图。** 三个 SIR 使用同一个 log 纵轴，阴影为 IQR。绿色区域从
  4-bin 开始，展示三个 SIR 下共同的误差下降趋势。

### 数据范围

全部 200 个 measured-waveform collision trials，不挑选 pair。

### 为什么不再分成三个独立小图

独立子图容易采用不同纵轴范围，造成下降幅度不可比较。热图负责多变量总览，共享
坐标趋势图负责显示转折和不确定性，两者功能互补。

## 14. 复现

```bash
python3 real_collision_experiment/paper_experiments/render_sp_v2_clear_figures.py \
  --data-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --source-figure-dir real_usrp_outputs/sp_paper_figures \
  --out-dir real_usrp_outputs/sp_v2_publication_figures_clear
```

输出目录中的 `clear_figure_manifest.json` 记录每张图的问题、答案、数据范围和
代表性 case 选择规则。除沿用的 Figure 2(a-b) 外，其余图片均同时输出 PNG、
PDF 和 SVG。
