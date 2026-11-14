# 从仿真叠加切换到十五节点真实碰撞

当前接收代码不能原样作为最终真机结果使用。仿真叠加通常隐含了干净包边界、可控分数时延以及 oracle CFO/信道，而连续真机 IQ 会同时出现噪声底变化、B210 两通道不一致、真实 CFO/STO/SFO、漏检、重复候选和 USB overflow。

## 前端必须改动

1. 输入改为连续双通道 `sc16` IQ，明确交织格式、通道顺序、缩放系数和首样点时间；遇到 overflow、时间戳跳变或文件长度不整齐时标记该 run 无效。
2. 关闭硬件 AGC，整次 run 固定 RX gain。每次布置后采集无发射噪声段，估计并保存两通道 DC、增益/相位偏差和噪声协方差，检测与 SP-Decode 前先做校准和 whitening。
3. 包检测从“已知窗口”改为连续流高召回检测。至少并行检测单通道能量/相关流和双通道 PCA 主方向流，再用重复前导轨迹、sync word 与 SFD 结构筛选候选。
4. 对每个候选独立细化 packet start、CFO 和整数/分数 STO。oracle 参数只能保留为诊断模式，不能进入最终性能曲线。
5. 对重叠候选做去重，保留检测来源、置信度、开始样点和估计参数；不得因为同一前导被多个投影发现而重复计包。
6. 从目标前导的双通道快照鲁棒估计信道方向，再计算论文中的目标投影、正交投影和 signed spectrum。两根接收天线必须来自同一台 B210 的同步 RX 通道。

## 后端必须改动

1. PHY 参数改为 SF10、BW125 kHz、CR4/5、前导 8、explicit header、PHY CRC on、sync word 0x34、Fs 1 MHz。
2. 解码成功后解析固定 20 字节 payload：`run_id/node_id/sequence/profile/PRBS/application CRC16`。可直接复用 `control_usrp/protocol.py` 的 `decode_data_payload()`。
3. 分开统计 `detected`、`header decoded`、`PHY CRC pass`、`application CRC pass`，不要把四类结果混成一个成功率。
4. 用 `(run_id, node_id, sequence)` 与 UART ground truth 匹配。UART 日志只用于离线评价，不得向检测器或解码器提供真实起点、CFO 或信道方向。
5. 保留旧的 trace-overlay 流程作为单元测试和 oracle 上界，与真实碰撞结果分表报告。

## 每个候选建议输出

```text
run_id, candidate_id, start_sample, start_time_s, detector,
cfo_hz, sto_samples, direction_quality, rssi_ch0, rssi_ch1,
header_ok, phy_crc_ok, app_crc_ok, node_id, sequence,
decoder_mode, lambda, decoded_payload_hex
```

当前 VMware Ubuntu 接收端源码不在本工作区，因此本次没有直接改动它。把该源码目录放入当前工作区后，下一步应按上述接口逐文件接入，而不是重写已经工作的 SP-Decode 主体。
