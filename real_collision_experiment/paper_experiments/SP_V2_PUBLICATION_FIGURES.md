# SP-Decoder v2 论文图视觉重构说明

绘图脚本读取
`real_usrp_outputs/sp_v2_mechanism_figures` 中已经核验过的 CSV/JSON sidecar，
并将论文图输出到 `real_usrp_outputs/sp_v2_publication_figures`。

机制图允许挑选视觉反差最大的代表性 case，但图题或正文必须说明
`representative/selected case`。承担总体性能结论的图保留全量样本。
每张图的选择规则也写入
`publication_figure_manifest.json`，便于复现和审稿核查。

## 每张图只保留一个视觉结论

| 论文位置 | 新图 | 实验目标 | 视觉重心 | 数据选择 |
|---|---|---|---|---|
| 2.5 Figure 2(a) | `fig2a_trace_sp_core_observation` | 用一个真实错误符号解释支持谱、反证谱和 signed 排名变化 | target/wrong 两个 bin 的排名翻转 | 直接采用作者指定的 `fig1_sp_core_observation` |
| 2.5 Figure 2(b) | `fig2b_wrong_bin_counter_evidence` | 证明错误峰通常暴露更强目标正交反证 | wrong-bin 与 target-bin 的 \(\eta\) 中位数相差多个数量级 | 直接采用作者指定的 `fig3_eta_distribution` |
| 2.5 Figure 2(c) | `fig2c_packet_dependent_lambda` | 说明不同包的最低 SER 区间不重合且过大 \(\lambda\) 会反向损伤 | 单面板展示 \(0\)–\(10\)、步长 0.25 的四条完整曲线；图例直接标注 SIR、相对起点和方向偏移 | 四个机制案例只用于解释包相关工作点，不在图中强调候选池统计 |
| 2.5 Figure 2(d) | `fig2d_preamble_predicts_payload_risk` | 验证方向估计存在偏差时候选区间内仍常有可用权重 | 仅展示全部648个彩色小圆点，不标记best-case | 72个碰撞按方向误差均衡，不按SER筛选 |
| 4.3 Figure 4 | `fig4_reliability_geometry` | 说明同一目标为何不能对所有竞争包使用相同权重 | 固定 \(L_u=0.999\) 时，\(U_{uv}\) 从 0.014 跳到 1.000，形成 73× 风险差 | 同一实测目标的最易分离与最共线竞争包 |
| 4.4 Figure 5(a) | `fig5a_interval_derived_overlap_set` | 解释如何由时间区间构造 \(\mathcal I_u\) | 蓝色 target payload 带只收纳真正相交的 7 个包 | 完整场景，同时显示一个最近但被排除的包 |
| 4.4 Figure 5(b) | `fig5b_pair_risk_landscape` | 说明每个 overlap 产生不同的 \(R_{uv}(\lambda)\) | 两个 flip 点与始终低于零的近共线 pair | 7 条曲线中选 4 条形状和 \(U_{uv}\) 反差最大的曲线 |
| 4.4 Figure 6 | `fig6_finite_candidates_match_dense_search` | 验证有限候选点逼近高分辨率搜索 | 95% objective loss ≤0.163%、权重差 ≤0.713%、PRR 差 0.00 pp | 全部 240 个碰撞场景，不筛选 |
| 4.4 Figure 7 | `fig7_finite_packet_configuration` | 展示单包在线配置全过程 | $v_3\!\to\!v_1\!\to\!v_2$ 依次主导下包络，两个切换贴近 coverage 点，红色星号落在 active pair peak | 受控四包碰撞：实测方向/可靠性锥加声明 SIR，只按曲线几何构造 |
| 5.3 Figure 8 | `fig8_robust_packet_statistics` | 展示局部 isolation 与角残差如何抑制污染前导 | 干扰从 \(p=3\) 开始后 isolation/weight 同步下降，最终误差缩小 72% | 挑选稳健聚合改善最明显的代表性实测 pair |
| 6.2 包内相干性 | `fig_air_within_packet_coherence` | 对齐展示 isolated clean corpus 的 50.25-symbol 信道方向误差 | \(-20\) dB 单包轨迹；\(-20/-10/0\) dB 三个同形误差分布 | 每档 SNR 从预先按 clean-frame 稳定性选定的 8 包池中选最稳定代表 |
| 6.2 并发信道测量 | `fig_air_concurrent_channel_estimation` | 对齐展示 0.2-symbol 碰撞下的 50.25-symbol 信道方向误差 | \(-20\) dB SIR 单包轨迹；\(-20/-10/0\) dB SIR 三个同形误差分布 | 每档 SIR 在 10 个随机碰撞中选绝对前导误差最接近中位数的代表 |
| 6.2 随机碰撞 SER | `fig_air_collision_ser_heatmap` | 量化 SNR 与 SIR 的联合影响 | 横轴 SNR \(-20/-10/0/10\) dB、纵轴 SIR \(-20/-10/0/10\) dB，颜色为 SER | 固定同一批 300 组随机碰撞，在每个格点重放，以支持配对的 SIR 横向比较 |

## 复现命令

```bash
python3 real_collision_experiment/paper_experiments/render_sp_v2_publication_figures.py \
  --data-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --source-figure-dir real_usrp_outputs/sp_paper_figures \
  --out-dir real_usrp_outputs/sp_v2_publication_figures
```

每张新图同时输出 PNG、PDF 和 SVG。Figure 2(a-b) 采用已有的 PNG/SVG
原图，其余图均输出三种格式。
