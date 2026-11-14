# 双通道 B210 连续采集

该目录用于真实碰撞实验的接收侧原始 IQ 采集，不依赖旧的仿真叠加代码。

```bash
python3 capture_dual_b210.py \
  --out runs/run_01000001.sc16 \
  --run-id 0x01000001 \
  --duration 45 \
  --center-freq 487700000 \
  --rate 500000 \
  --gain 15 \
  --bandwidth 200000 \
  --channels 0,1 \
  --antenna RX2 \
  --device-args 'serial=RX_B210_SERIAL'
```

输出格式为 sample-major little-endian `int16`：

```text
ch0_I, ch0_Q, ch1_I, ch1_Q, ch0_I, ch0_Q, ...
```

同名 `.sc16.json` 保存实际射频参数、首样点时间、overflow、timeout、峰值、RMS 和削顶计数。正式 run 要求 `overflow_count=0`、`timeout_count=0` 且 `clipping_count=[0,0]`。

完整操作和数据判据见 `../docs/03_接收端_双通道B210与解码.md`。
