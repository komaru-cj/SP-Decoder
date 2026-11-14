# SP-Decoder v2 机制与信道测量图

## 一键复现

在仓库根目录运行：

```bash
python3 real_collision_experiment/paper_experiments/generate_sp_v2_mechanism_figures.py \
  --out-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --seed 20260808 \
  --finite-scenes 240 \
  --dense-points 4001 \
  --coherence-noise-trials 8 \
  --channel-pair-trials 40
```

若只需重跑并发信道的 SIR/FFT-bin 扫描：

```bash
python3 real_collision_experiment/paper_experiments/generate_sp_v2_mechanism_figures.py \
  --out-dir real_usrp_outputs/sp_v2_mechanism_figures \
  --seed 20260808 \
  --channel-pair-trials 40 \
  --channel-offset-symbols 1.0 \
  --only-air-concurrent
```

每张图同时保存 PNG、PDF 和 CSV/JSON 侧车。总清单为
`real_usrp_outputs/sp_v2_mechanism_figures/experiment_manifest.json`。

## 统一定义

- 信道方向误差采用复射影角
  \[
  d(\mathbf h_1,\mathbf h_2)=
  \arccos\frac{|\mathbf h_1^H\mathbf h_2|}
  {\|\mathbf h_1\|\|\mathbf h_2\|},
  \]
  因而不受不可观测公共复相位影响。
- 每个实测包的 continuous CFO 由相邻重复前导快照的相位增量估计；旧
  trace 元数据中的整数 CFO 只保留给 Figure 2(a--c) 的原 symbol-truth
  replay。
- Figure 6 的 dense reference 是同一个 truth-free
  \(G_u(\lambda)\) 上的 4,001 点离线搜索，不是利用真实 symbol/SER
  反选的 oracle。
- PRR 仅在标准显式头 LoRa PHY 上统计，成功要求 FEC 后 PHY CRC 通过且
  payload 完全一致。

## 图与论文论点

| 文件 | 论文位置 | 证据 |
|---|---|---|
| `fig2_sp_motivation` | 2.5 | 单个 MRC 错误、配对 \(\Delta\eta\) CDF、固定 \(\lambda\) repair/damage、前导 proxy |
| `fig4_reliability_geometry` | 4.3 | 实测 easy/near-collinear pair 的 \(L_u,U_{uv}\) 几何 |
| `fig5_overlap_and_pair_risks` | 4.4 | 时间区间构造 \(\mathcal I_u\)，每个重叠竞争包一条 \(R_{uv}(\lambda)\) |
| `fig6_finite_vs_dense` | 4.4 | objective gap、权重差异、SER/PRR 影响 |
| `fig7_finite_packet_configuration` | 4.4 | 边界、flip/peak、自适应中点、固定覆盖点、下包络切换与最终权重 |
| `candidate_winner_share_three_checkpoints` | 第六章补充实验 | 30,000 个受控碰撞中，生产有限候选集的赢家来源占比 |
| `candidate_winner_share_10000_checkpoints` | 第六章补充实验 | 将三个固定点替换为 10,000 个固定点后的赢家来源占比 |
| `fig8_robust_packet_statistics` | 5.3 | 1/3/5-bin 快照、isolation/角残差权重和最终 \(\widehat{\mathbf h}\) |
| `fig_air_within_packet_coherence` | 6.2 | isolated clean corpus 中 \(-20\) dB 的 50.25-symbol 轨迹，以及 \(-20/-10/0\) dB 的同形误差分布 |
| `fig_air_concurrent_channel_estimation` | 6.2 | \(\Delta\tau=0.2T_s\)、零额外 FFT-bin 分离下，\(-20/-10/0\) dB SIR 的 50.25-symbol 轨迹与误差分布 |
| `fig_air_collision_ser_heatmap` | 6.2 | \(\Delta\tau=0.2T_s\) 的固定 300 组随机实测波形碰撞，在每个 SNR×SIR 格点重放；颜色为 SER |

## 当前正式结果摘要

- 5,794 个 MRC 错误符号中，99.12% 满足
  \(\eta_{\rm wrong}>\eta_{\rm target}\)。
- 前导方向离散度与 payload target-bin 正交泄漏的 Spearman
  \(\rho_s=0.634\)，\(p=5.03\times10^{-4}\)。
- 240 个正式 PHY 碰撞场景中，有限候选相对 dense reference 的
  95th-percentile objective loss 为 0.163%，两者 PRR 均为 60.42%。
- 30,000 个不读取 payload/CRC 的受控多包碰撞中，生产有限集的赢家来源为：
  区间端点 53.64%、pair flip/peak 38.64%、自适应中点 0.36%、三个常数
  检查点 7.36%。把三个常数点替换为 10,000 个后，pair flip/peak 仍为
  36.03%，而密集常数点为 11.79%；详细计数见
  `candidate_winner_share_summary.json` 与 `candidate_winner_share.csv`。
- 在 \(-5\) dB 注入 SNR 下，chirp-to-packet-mean 角偏差中位数为
  2.41°，90th percentile 为 4.35°。

## Figure 8 的解释边界

Figure 8 是一个可审计的机制案例，不应被表述为“稳健加权对所有 pair
都优于普通均值”。一次独立的 26×25 pair 扫描表明，在固定
SIR=-6 dB、\(\Delta\tau=3.35T_s\) 条件下，当前稳健权重约在 23.4%
的 pair 上降低方向误差。正式图选择的 pair 同时保持方向与幅度合理：
5-bin mean/robust 的方向误差分别为 0.039°/0.011°，归一化幅度分别为
1.000/1.004。若正文要声称总体收益，需要将全 pair 消融作为独立结果，
不能由这一案例外推。
