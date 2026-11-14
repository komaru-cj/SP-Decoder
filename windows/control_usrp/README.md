# Ubuntu 控制 USRP B210

> 协议 V2 / PHY profile 5 实验请使用
> [`../automation/PHY5_20S_OFFLINE_MANUAL.md`](../automation/PHY5_20S_OFFLINE_MANUAL.md)。
> 下文旧命令仅用于归档的协议 V1 数据。

`usrp_run_controller.py` 使用单独一台 B210 发送运行级 `CONFIG` 和 `START`。它与 F103 固件使用相同的二进制协议，并为每次运行生成 JSON manifest。

## 环境

Ubuntu 控制机需要：

- GNU Radio 3.10 或兼容版本
- UHD 和可正常识别的 USRP B210
- 已安装 `gr-lora_sdr`，Python 中能执行 `import gnuradio.lora_sdr`

先检查：

```bash
uhd_find_devices
python3 -c 'import gnuradio.lora_sdr as lora_sdr; print("gr-lora_sdr OK")'
```

## 只生成协议和 manifest

该模式不需要连接 USRP：

```bash
python3 usrp_run_controller.py \
  --run-id 0x20260719 \
  --active-nodes 1-15 \
  --offered-load 1.0 \
  --duration-s 120 \
  --warmup-s 5 \
  --node-tx-power 16 \
  --experiment-tag campaign=fig9_12_duty_v4 \
  --experiment-tag figure=fig9_10 \
  --experiment-tag round=1 \
  --dry-run
```

`--experiment-tag KEY=VALUE` 可重复使用，只写入 manifest，不改变节点调度。批量论文实验应至少记录 campaign、figure、round 和 layout，距离实验再记录节点距离与位置编号。

`--offered-load` 是本轮全部活跃节点的聚合负载 `G`，单节点占空比为
`d=G/N`。CONFIG 中的 `numActiveNodes` 始终等于 active mask 的置位数；控制端会拒绝
任何节点数不一致的配置。正式 v4 campaign 使用扩展后的固件 profile 表，在
`N={3,6,9,12,15}` 下精确实现单节点 `d={0.05,0.15,0.25}`。
traffic profile ID 16--19 另外编码聚合负载 `G={4.5,6,7.5,1.4}`，供
Fig. 9/10 的单节点 `d=0.5` 和 Fig. 12 的单节点 `d=0.7` 离线活动使用。

## 真正发射

```bash
python3 usrp_run_controller.py \
  --run-id 0x20260719 \
  --active-nodes 1-15 \
  --offered-load 1.0 \
  --duration-s 120 \
  --warmup-s 5 \
  --node-tx-power 16 \
  --usrp-tx-gain 0 \
  --device-args 'serial=CONTROL_B210_SERIAL'
```

程序先等待 5 秒，再发送 5 次 CONFIG；随后等待 3 秒并发送 5 次 START。每个 START
都带有递减的 `start_delay_ms`，指向同一个 future warm-up 起点，避免不同节点因收到
不同 START 副本而错开业务开始时间。双通道接收 B210 必须在 CONFIG 开始前连续采集。
程序打印的 `expected_capture_end_utc` 是接收端最早停止时间，实际建议再保留 2 到 3
秒尾部数据。

注意：当前控制端要求节点固件支持 18 字节 START 帧：
`SP/version/type/size/flags/run_id/config_crc/start_delay_ms/crc16`。旧固件只支持 14
字节 START，会拒绝新 START。

控制 USRP 的 `--usrp-tx-gain` 与节点的 `--node-tx-power` 是两个不同参数。第一次台架测试从低增益开始，确认所有节点都能稳定收到控制帧且接收 B210 不饱和后再固定该值。

## 协议自检

```bash
python3 -m unittest -v test_protocol.py
```

`protocol.py` 也提供 `decode_data_payload()`。后端解码器拿到 20 字节 payload 后应调用它，只有 PHY CRC 和应用 CRC16 都通过的包才计为成功恢复。
