# 15 节点真实碰撞实验文档索引

本目录是当前真实 LoRa 碰撞实验的统一说明。实验采用保留控制模式：控制端 B210 广播 `CONFIG` 和 `START`，15 个 STM32F103C8T6 + SX1276 节点按配置产生随机业务，接收端 B210 双通道连续采集真实空口 IQ，随后由前端检测和 SP-Decode 后端处理。

## 阅读顺序

1. [00_总体实验设计.md](00_总体实验设计.md)：研究问题、系统结构、变量、实验矩阵和有效性标准。
2. [01_控制端_USRP_B210.md](01_控制端_USRP_B210.md)：控制协议、G 的设置、Ubuntu 命令和 manifest。
3. [02_LoRa节点_STM32F103.md](02_LoRa节点_STM32F103.md)：节点固件、引脚、15 份固件、LED 无串口判断和 CRC。
4. [03_接收端_双通道B210与解码.md](03_接收端_双通道B210与解码.md)：双通道采集、文件格式、前端/后端迁移和结果检查。
5. [04_实验执行SOP.md](04_实验执行SOP.md)：从单节点到 15 节点的逐步操作顺序。
6. [05_实验记录模板.md](05_实验记录模板.md)：每个 run 必须保存的记录。
7. [09_Fig9-12实验计划与Windows控制.md](09_Fig9-12实验计划与Windows控制.md)：Fig. 9--12 矩阵、Windows PowerShell/SSH 控制、数据复制与检查。
8. [10_Fig9-12逐轮采集命令.md](10_Fig9-12逐轮采集命令.md)：手动逐轮采集命令；正式批量执行优先使用 `automation/` 的握手脚本。
9. [11_室外Fig13-15操作手册.md](11_室外Fig13-15操作手册.md)：室外 Fig.13--15 的采集、严格中间 5 秒全局匿名建库与解码、AWGN SNR 建构和画图。

## 代码入口

| 部分 | 文件 |
|---|---|
| 控制端协议与载荷复现 | `real_collision_experiment/control_usrp/protocol.py` |
| 控制 B210 发射程序 | `real_collision_experiment/control_usrp/usrp_run_controller.py` |
| 控制协议单元测试 | `real_collision_experiment/control_usrp/test_protocol.py` |
| F103 节点状态机 | `LoraSTMacH7_2026.07.19_移植STM32f103c8t6_实现classA_通用版(Branch4)/apps/main.c` |
| 节点控制协议 | `.../apps/experiment_protocol.c`、`experiment_protocol.h` |
| 接收 B210 双通道采集 | `real_collision_experiment/receiver_usrp/capture_dual_b210.py` |
| Fig. 9--12 campaign/PowerShell 生成 | `real_collision_experiment/paper_experiments/plan_fig9_12_campaign.py` |
| Fig. 9--12 数据完整性检查 | `real_collision_experiment/paper_experiments/validate_fig9_12_artifacts.py` |
| 双机自动握手采集 | `real_collision_experiment/automation/receiver_campaign_server.py`、`controller_campaign_client.py` |

## 当前约束

- 节点必须收到合法 `CONFIG` 后再收到匹配的 `START` 才开始业务发送，上电不会直接发数据。
- 没有 USB-TTL 时，用板载 PC13 LED 判断控制流程；它不能证明每一包都 `TX_DONE`。
- 控制端 manifest 中的发送时刻是按固件同一 PRNG 算法生成的期望时刻，不是实际空口真值。
- 正式实验是否成功，最终以接收 IQ 完整性、解码出的节点/序号/CRC 和统计结果为准。
