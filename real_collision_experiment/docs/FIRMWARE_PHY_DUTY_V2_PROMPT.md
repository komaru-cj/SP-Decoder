# 固件修改提示词：多 PHY + 固定单节点占空比（协议 V2）

请在 STM32F103 + SX1276 的实验节点工程中修改以下三个核心文件，并保持现有板级驱动、节点 ID 编译方式、LED 行为、五次 START 对齐逻辑和 34/18/20 字节帧长度不变：

- `main.c`
- `experiment_protocol.h`
- `experiment_protocol.c`

目标是一次性生成可刷到 Node01–Node15 的统一功能固件（每块板仍通过 `EXPERIMENT_NODE_ID=1..15` 区分）。请直接实现并给出完整 diff，同时做边界检查和可在主机侧复核的确定性测试。

## 1. 协议版本及兼容边界

1. 将 `EXP_PROTOCOL_VERSION` 从 1 改为 2。CONFIG、START 和节点数据 payload 均发送版本 2。
2. CONFIG 帧仍为 34 字节，字段偏移完全不变：`phyProfileId` 仍在 byte 13，`trafficProfileId` 仍在 byte 14；START 仍为 18 字节；数据 payload 仍为 20 字节。
3. CRC16-CCITT、大小端、magic `SP`、runId、activeMask、seed、payload 内容和五次 START 的处理方式不变。
4. 固件只接受协议 V2，避免把新 duty profile 误解释为旧版 aggregate-G profile。

## 2. 新增 PHY profile

让 `phyProfileId` 支持下面 1–9：

| phyProfileId | 数据 PHY |
|---:|---|
| 1 | SF8 / BW125 kHz / CR4/5 |
| 2 | SF10 / BW125 kHz / CR4/5 |
| 3 | SF12 / BW125 kHz / CR4/5 |
| 4 | SF8 / BW250 kHz / CR4/5 |
| 5 | SF10 / BW250 kHz / CR4/5 |
| 6 | SF12 / BW250 kHz / CR4/5 |
| 7 | SF8 / BW500 kHz / CR4/5 |
| 8 | SF10 / BW500 kHz / CR4/5 |
| 9 | SF12 / BW500 kHz / CR4/5 |

实现一个显式查表函数，例如：

```c
bool ExperimentGetPhyProfile(uint8_t id, uint8_t *bandwidthIndex,
                             uint8_t *spreadingFactor);
```

SX1276 驱动参数按现有 Semtech API 使用：BW125 对应 bandwidth index 0，BW250 对应 index 1，BW500 对应 index 2；SF 分别为 8、10、12。CR 固定 1（4/5），前导码 8，显式头、PHY CRC、sync word 0x34、频率 487.7 MHz、IQ 不反转均不变。

控制帧接收 PHY 必须始终保持 SF10/BW125，这样节点上电后一定能接收 CONFIG/START。只有实验数据发送时，才按照已接受 CONFIG 的 `phyProfileId` 设置 `Radio.SetTxConfig`。每次发送数据前继续重新设置 TX PHY，不能让 `StartControlRx()` 意外覆盖数据 PHY。

SF12/BW125 的 ToA 较长，请把 TX timeout 调整到至少 5000 ms。用 `Radio.TimeOnAir(MODEM_LORA, 20)` 在选定数据 PHY 后计算真实 `PacketTimeOnAirMs`，不要写死 SF10/BW125 的 ToA。

## 3. trafficProfileId 改为单节点占空比

废弃旧版“trafficProfileId 对应 aggregate G 表”的解释。协议 V2 定义：

| trafficProfileId | 单节点占空比 d | dutyMilli |
|---:|---:|---:|
| 1 | 0.25 | 250 |
| 2 | 0.50 | 500 |
| 3 | 0.75 | 750 |

只接受 1、2、3，拒绝 0 和其他值。建议把旧的 `ExperimentTrafficLoadMilli()` 替换为 `ExperimentTrafficDutyMilli()`。

节点数 N 只决定聚合负载 `G=N*d`，不再参与单节点平均间隔计算。使用当前“发完一个包后再等待指数 gap”的调度语义：

```text
meanGapMs = PacketTimeOnAirMs * (1000 - dutyMilli) / dutyMilli
meanPeriodMs = PacketTimeOnAirMs + meanGapMs
```

计算必须使用 `uint64_t` 中间量；`meanGapMs` 最小为 1 ms。初始随机延迟和后续指数随机 gap、8 倍均值截断、PRNG/seed 算法保持不变。因此相同 PHY 和 duty 下，N=1–15 的每个节点具有相同平均发包速率，而聚合 G 随 N 线性增加。

## 4. CONFIG 校验及日志

1. `ExperimentDecodeConfig()` 校验 `phyProfileId` 必须为 1–9、`trafficProfileId` 必须为 1–3、activeMask popcount 必须等于 N、N 必须为 1–15、duration 必须为 1 s–1 h、warmup 不超过 60 s、功率为 -4 至 20 dBm。
2. 删除旧的 `G < N` 查表校验，改为 `dutyMilli < 1000`；新表天然满足。
3. `CONFIG_OK` 日志同时打印：profile ID、SF、BW Hz、traffic profile ID、`duty_milli`、`G_milli=N*duty_milli`、实际 ToA、mean gap、20 秒 duration 等。
4. `TX_START/TX_DONE/RUN_COMPLETE` 保持 run/node/sequence/timestamp 信息不变。

## 5. 五次 START 的幂等性

保留目前控制端连续发送五次 START 的能力：

- 节点在 `NODE_WAIT_START` 或 `NODE_ARMED` 接受同一 runId/configCRC 的重复 START；
- 每个 START 携带递减 delay，所有有效 START 必须对齐到同一个未来 warmup 起点；
- 重复 START 可以重新 arm，但不能提前发包、不能把同一轮变成五轮、不能让 sequence 在业务开始后反复清零；
- 一旦进入 `NODE_WARMUP`/业务发送阶段，迟到 START 不得重启该轮。

## 6. 必须完成的测试

请至少给出以下测试结果：

1. 9 个 PHY profile 查表全部正确，并验证 7=4、8=5、9=6。
2. duty 1/2/3 分别得到 250/500/750 milli。
3. profile 5、20-byte payload 的 `Radio.TimeOnAir` 与主机公式约 185.344 ms 一致（固件整数值允许按驱动取整）。
4. profile 3 和 6 的低速率优化/ToA 由 SX1276 驱动正确配置，TX timeout 不触发。
5. N=1、3、6、9、12、15 时，同一 duty 的 mean gap 不随 N 改变；日志里的 G=N*d 正确。
6. CONFIG/START 长度及 CRC 测试；版本 1、phy=0、traffic=0、未知 profile 必须拒绝。
7. 五个 START 只产生一轮 20 秒业务，sequence 从 0 单调增加。

完成后请把修改后的 `main.c`、`experiment_protocol.h`、`experiment_protocol.c` 发回给我做主机控制协议逐字节对照。
