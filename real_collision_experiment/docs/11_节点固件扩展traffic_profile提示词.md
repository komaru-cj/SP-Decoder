# 节点固件修改提示词：5% / 15% / 25% 单节点占空比

将下面提示词完整交给负责 STM32 节点固件的电脑：

```text
请修改 STM32 LoRa 实验节点固件，使它与控制端的扩展 traffic profile 协议完全一致，
从而在 N={3,6,9,12,15} 时实现固定的单节点占空比 d={0.05,0.15,0.25}。

相关文件：
- experiment_protocol.h
- experiment_protocol.c
- main.c（现有调度公式正确时无需修改）

问题背景：
CONFIG v1 只发送 activeMask、numActiveNodes 和 trafficProfileId。固件会检查
popcount(activeMask)==numActiveNodes。这个检查必须保留；旧控制方案让两者不同，
导致 CONFIG 被固件拒绝，节点不会在 START 后发送业务包。

本次不要使用“参考节点数”，也不要放宽 activeCount 校验。每轮都使用真实活跃节点数，
通过扩展 trafficProfileId -> G_milli 表实现 G=N*d。

必须采用下面唯一映射；ID 0--5 保持旧含义，确保向后兼容：

ID  0 -> G_milli=250
ID  1 -> G_milli=500
ID  2 -> G_milli=1000
ID  3 -> G_milli=1500
ID  4 -> G_milli=2000
ID  5 -> G_milli=3000
ID  6 -> G_milli=150
ID  7 -> G_milli=300
ID  8 -> G_milli=450
ID  9 -> G_milli=600
ID 10 -> G_milli=750
ID 11 -> G_milli=900
ID 12 -> G_milli=1350
ID 13 -> G_milli=1800
ID 14 -> G_milli=2250
ID 15 -> G_milli=3750
ID 16 -> G_milli=4500
ID 17 -> G_milli=6000
ID 18 -> G_milli=7500
ID 19 -> G_milli=1400

experiment_protocol.h：
将 EXP_TRAFFIC_PROFILE_COUNT 从 6U 改为 20U。

experiment_protocol.c：
将 ExperimentTrafficLoadMilli() 的表改为：

static const uint16_t loadsMilli[EXP_TRAFFIC_PROFILE_COUNT] =
{
    250U, 500U, 1000U, 1500U, 2000U, 3000U,
    150U, 300U, 450U, 600U, 750U,
    900U, 1350U, 1800U, 2250U, 3750U,
    4500U, 6000U, 7500U, 1400U
};

不要修改：
- 协议版本（仍为1）
- CONFIG帧34字节长度及字段位置
- START帧格式
- CRC16算法
- 20字节业务payload格式
- activeCount == numActiveNodes 检查
- activeMask只允许节点1--15
- LoRa PHY参数
- CONFIG中的txPowerDbm控制节点发射功率
- PRNG和指数间隔调度逻辑

main.c 中现有公式应继续保留：

MeanGapMs = PacketTimeOnAirMs *
            (numActiveNodes * 1000 - G_milli) / G_milli;

并继续检查：
G_milli > 0 且 G_milli < numActiveNodes * 1000。

所需矩阵如下，确认每一项都能由上表精确编码：

N=3:  d=5% -> G=0.15(ID6);  d=15% -> G=0.45(ID8);  d=25% -> G=0.75(ID10)
N=6:  d=5% -> G=0.30(ID7);  d=15% -> G=0.90(ID11); d=25% -> G=1.50(ID3)
N=9:  d=5% -> G=0.45(ID8);  d=15% -> G=1.35(ID12); d=25% -> G=2.25(ID14)
N=12: d=5% -> G=0.60(ID9);  d=15% -> G=1.80(ID13); d=25% -> G=3.00(ID5)
N=15: d=5% -> G=0.75(ID10); d=15% -> G=2.25(ID14); d=25% -> G=3.75(ID15)

新 Fig.9/10 单轮离线活动的 d=50% 还需要 G=4.5/6/7.5，对应
trafficProfileId=16/17/18。新 Fig.12 使用 N=2、d=70%，因此 G=1.4、
trafficProfileId=19。

至少完成并报告以下验证：
1. N=3、activeMask含3位、ID6：CONFIG_OK打印 G_milli=150，平均单节点占空比5%。
2. N=9、activeMask含9位、ID12：CONFIG_OK打印 G_milli=1350，平均单节点占空比15%。
3. N=15、activeMask含15位、ID15：CONFIG_OK打印 G_milli=3750，平均单节点占空比25%。
4. N=15、activeMask含15位、ID18：CONFIG_OK打印 G_milli=7500，平均单节点占空比50%。
5. N=2、activeMask含2位、ID19：CONFIG_OK打印 G_milli=1400，平均单节点占空比70%。
6. activeMask只有3位但numActiveNodes=15时仍然拒绝CONFIG。
7. 合法CONFIG后节点进入NODE_WAIT_START；收到匹配START后持续发送业务包。
8. 编译无错误、无新增警告。

完成后返回：
- 修改后的 experiment_protocol.h
- 修改后的 experiment_protocol.c
- main.c（仅当实际改动过）
- 编译日志
- 上述验证结果或串口日志

所有15个节点必须烧录这套完全相同的协议表，仅节点ID的编译配置不同。
```
