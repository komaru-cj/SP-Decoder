#!/usr/bin/env python3
"""Broadcast CONFIG/START LoRa frames with a dedicated USRP B210."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from protocol import (
    DEFAULT_PHY_PROFILE_ID,
    PHY_PROFILES,
    START_FRAME_SIZE,
    TRAFFIC_DUTY_CYCLES,
    RunConfig,
    active_nodes_to_mask,
    config_crc,
    encode_config,
    encode_start,
    expected_tx_schedule_ms,
    firmware_mean_idle_gap_ms,
    lora_time_on_air_ms,
    mean_idle_gap_ms,
    phy_profile,
    recommended_receiver_sample_rate_hz,
    traffic_profile_id_from_duty,
)

FREQUENCY_HZ = 487_700_000
CONTROL_SAMPLE_RATE_HZ = 1_000_000
CONTROL_BANDWIDTH_HZ = 125_000
CONTROL_SPREADING_FACTOR = 10
CODING_RATE = 1
PREAMBLE_SYMBOLS = 8
SYNC_WORD = 0x34


def parse_node_ids(value: str) -> list[int]:
    result: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise argparse.ArgumentTypeError("node range must be ascending")
            result.update(range(start, end + 1))
        else:
            result.add(int(part))
    nodes = sorted(result)
    try:
        active_nodes_to_mask(nodes)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return nodes


def parse_experiment_tag(value: str) -> tuple[str, str]:
    """Parse a manifest-only ``KEY=VALUE`` experiment annotation."""
    if "=" not in value:
        raise argparse.ArgumentTypeError("experiment tags must use KEY=VALUE")
    key, tag_value = (part.strip() for part in value.split("=", 1))
    if not key:
        raise argparse.ArgumentTypeError("experiment tag key must not be empty")
    if not all(character.isalnum() or character in "_-" for character in key):
        raise argparse.ArgumentTypeError(
            "experiment tag keys may contain only letters, digits, '_' and '-'"
        )
    if not tag_value:
        raise argparse.ArgumentTypeError("experiment tag value must not be empty")
    return key, tag_value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def save_manifest(path: Path, manifest: dict[str, object]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


class ControlTransmitter:
    def __init__(
        self,
        device_args: str,
        tx_gain_db: float,
        antenna: str,
        rf_bandwidth_hz: float,
    ) -> None:
        try:
            import pmt
            from gnuradio import gr, uhd
            import gnuradio.lora_sdr as lora_sdr
        except ImportError as exc:
            raise RuntimeError(
                "GNU Radio, UHD and gr-lora_sdr must be installed on the Ubuntu control PC"
            ) from exc

        class MessageInjector(gr.basic_block):
            def __init__(self) -> None:
                gr.basic_block.__init__(self, name="control_message_injector", in_sig=None, out_sig=None)
                self.port = pmt.intern("out")
                self.message_port_register_out(self.port)

            def send(self, payload: bytes) -> None:
                self.message_port_pub(self.port, pmt.intern(payload.hex()))

        class ControlFlowgraph(gr.top_block):
            def __init__(self) -> None:
                gr.top_block.__init__(self, "SP-Decode run controller")
                self.injector = MessageInjector()
                self.whitening = lora_sdr.whitening(True, False, ",", "packet_len")
                self.header = lora_sdr.header(False, True, CODING_RATE)
                self.add_crc = lora_sdr.add_crc(True)
                self.hamming = lora_sdr.hamming_enc(CODING_RATE, CONTROL_SPREADING_FACTOR)
                self.interleaver = lora_sdr.interleaver(
                    CODING_RATE, CONTROL_SPREADING_FACTOR, 0, CONTROL_BANDWIDTH_HZ
                )
                self.gray = lora_sdr.gray_demap(CONTROL_SPREADING_FACTOR)
                self.modulator = lora_sdr.modulate(
                    CONTROL_SPREADING_FACTOR,
                    CONTROL_SAMPLE_RATE_HZ,
                    CONTROL_BANDWIDTH_HZ,
                    [SYNC_WORD],
                    int(0.1 * CONTROL_SAMPLE_RATE_HZ),
                    PREAMBLE_SYMBOLS,
                )
                self.modulator.set_min_output_buffer(1_000_000)
                self.sink = uhd.usrp_sink(
                    device_args,
                    uhd.stream_args(cpu_format="fc32", channels=[0]),
                    "frame_len",
                )
                self.sink.set_samp_rate(CONTROL_SAMPLE_RATE_HZ)
                self.sink.set_center_freq(FREQUENCY_HZ, 0)
                self.sink.set_antenna(antenna, 0)
                self.sink.set_bandwidth(rf_bandwidth_hz, 0)
                self.sink.set_gain(tx_gain_db, 0)

                self.msg_connect((self.injector, "out"), (self.whitening, "msg"))
                self.connect(self.whitening, self.header)
                self.connect(self.header, self.add_crc)
                self.connect(self.add_crc, self.hamming)
                self.connect(self.hamming, self.interleaver)
                self.connect(self.interleaver, self.gray)
                self.connect(self.gray, self.modulator)
                self.connect(self.modulator, self.sink)

        self.flowgraph = ControlFlowgraph()
        self.injector = self.flowgraph.injector

    def start(self) -> None:
        self.flowgraph.start()
        time.sleep(1.0)

    def send(self, payload: bytes) -> None:
        self.injector.send(payload)

    def stop(self) -> None:
        self.flowgraph.stop()
        self.flowgraph.wait()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Broadcast run-level CONFIG and START frames with a USRP B210"
    )
    parser.add_argument("--run-id", type=lambda x: int(x, 0), required=True)
    parser.add_argument("--active-nodes", type=parse_node_ids, default=parse_node_ids("1-15"))
    traffic = parser.add_mutually_exclusive_group(required=True)
    traffic.add_argument(
        "--per-node-duty-cycle",
        type=float,
        choices=TRAFFIC_DUTY_CYCLES,
        help="Per-node duty cycle; new firmware supports 0.25, 0.5, or 0.75",
    )
    traffic.add_argument(
        "--offered-load",
        type=float,
        help="Compatibility input G; must imply d=G/N in {0.25,0.5,0.75}",
    )
    parser.add_argument("--phy-profile-id", type=int, choices=sorted(PHY_PROFILES), default=DEFAULT_PHY_PROFILE_ID)
    parser.add_argument("--duration-s", type=float, default=20.0)
    parser.add_argument("--warmup-s", type=float, default=2.0)
    parser.add_argument("--node-tx-power", type=int, default=16)
    parser.add_argument("--global-seed", type=lambda x: int(x, 0))
    parser.add_argument("--payload-seed", type=lambda x: int(x, 0))
    parser.add_argument("--config-repeat", type=int, default=5)
    parser.add_argument("--config-interval-s", type=float, default=1.0)
    parser.add_argument("--start-repeat", type=int, default=5)
    parser.add_argument("--start-interval-s", type=float, default=0.6)
    parser.add_argument(
        "--start-arm-delay-s",
        type=float,
        default=4.0,
        help=(
            "Delay from the first START enqueue to the shared warmup-begin target. "
            "Each START frame carries a decreasing delay so any received START arms "
            "the node for the same future time."
        ),
    )
    parser.add_argument("--pre-config-delay-s", type=float, default=5.0)
    parser.add_argument("--pre-start-delay-s", type=float, default=3.0)
    parser.add_argument("--tail-s", type=float, default=3.0)
    parser.add_argument("--device-args", default="")
    parser.add_argument("--usrp-tx-gain", type=float, default=0.0)
    parser.add_argument("--antenna", default="TX/RX")
    parser.add_argument("--rf-bandwidth", type=float, default=200_000.0)
    parser.add_argument("--manifest-dir", type=Path, default=Path("run_manifests"))
    parser.add_argument(
        "--experiment-tag",
        type=parse_experiment_tag,
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Manifest-only campaign annotation; repeat for figure, round, layout, "
            "distance, etc. Tags never affect node scheduling."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.config_repeat < 3:
        raise SystemExit("--config-repeat must be at least 3")
    config_toa_s = lora_time_on_air_ms(34) / 1000.0
    start_toa_s = lora_time_on_air_ms(START_FRAME_SIZE) / 1000.0
    if args.config_interval_s <= config_toa_s + 0.1:
        raise SystemExit(
            f"--config-interval-s must exceed CONFIG airtime ({config_toa_s:.3f} s) by 0.1 s"
        )
    if args.start_repeat < 1:
        raise SystemExit("--start-repeat must be at least 1")
    if args.start_interval_s <= start_toa_s + 0.1:
        raise SystemExit(
            f"--start-interval-s must exceed START airtime ({start_toa_s:.3f} s) by 0.1 s"
        )
    min_arm_delay_s = (args.start_repeat - 1) * args.start_interval_s + start_toa_s + 0.25
    if args.start_arm_delay_s <= min_arm_delay_s:
        raise SystemExit(
            "--start-arm-delay-s must leave the last repeated START enough time "
            f"to arrive before the shared warmup target; need > {min_arm_delay_s:.3f} s"
        )

    global_seed = args.global_seed if args.global_seed is not None else args.run_id ^ 0xA5A55A5A
    payload_seed = args.payload_seed if args.payload_seed is not None else args.run_id ^ 0x13579BDF
    active_node_count = len(args.active_nodes)
    per_node_duty = (
        float(args.per_node_duty_cycle)
        if args.per_node_duty_cycle is not None
        else float(args.offered_load) / active_node_count
    )
    try:
        traffic_profile_id = traffic_profile_id_from_duty(per_node_duty)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    data_phy = phy_profile(args.phy_profile_id)
    config = RunConfig(
        run_id=args.run_id,
        active_mask=active_nodes_to_mask(args.active_nodes),
        num_active_nodes=active_node_count,
        phy_profile_id=args.phy_profile_id,
        traffic_profile_id=traffic_profile_id,
        node_tx_power_dbm=args.node_tx_power,
        duration_ms=round(args.duration_s * 1000),
        warmup_ms=round(args.warmup_s * 1000),
        global_seed=global_seed & 0xFFFFFFFF,
        payload_seed=payload_seed & 0xFFFFFFFF,
    )
    config_frame = encode_config(config)
    config_frame_crc = config_crc(config_frame)

    experiment_tags: dict[str, str] = {}
    for key, value in args.experiment_tag:
        if key in experiment_tags:
            raise SystemExit(f"duplicate --experiment-tag key: {key}")
        experiment_tags[key] = value

    created = utc_now()
    manifest: dict[str, object] = {
        "schema": "sp_decode_real_collision_run_v1",
        "created_utc": created.isoformat(),
        "experiment": experiment_tags,
        "config": config.to_dict(),
        "active_nodes": args.active_nodes,
        "active_node_count": len(args.active_nodes),
        "radio": {
            "frequency_hz": FREQUENCY_HZ,
            "phy_profile_id": args.phy_profile_id,
            "sample_rate_hz": recommended_receiver_sample_rate_hz(args.phy_profile_id),
            "bandwidth_hz": data_phy["bandwidth_hz"],
            "spreading_factor": data_phy["sf"],
            "coding_rate": "4/5",
            "preamble_symbols": PREAMBLE_SYMBOLS,
            "explicit_header": True,
            "phy_crc": True,
            "sync_word": SYNC_WORD,
        },
        "traffic": {
            "data_payload_bytes": 20,
            "packet_airtime_ms": lora_time_on_air_ms(20, **data_phy),
            "firmware_active_node_count": active_node_count,
            "profile_offered_load": config.offered_load,
            "per_node_duty_cycle": config.per_node_duty_cycle,
            "effective_aggregate_offered_load": config.offered_load,
            "expected_per_node_rate_pps": (
                config.offered_load
                / active_node_count
                / (lora_time_on_air_ms(20, **data_phy) / 1000.0)
            ),
            "mean_idle_gap_ms": mean_idle_gap_ms(config),
            "firmware_mean_idle_gap_ms": firmware_mean_idle_gap_ms(config),
        },
        "expected_node_schedules": {
            str(node_id): {
                "tx_count": len(expected_tx_schedule_ms(config, node_id)),
                "tx_start_ms_from_traffic_begin": expected_tx_schedule_ms(config, node_id),
            }
            for node_id in args.active_nodes
        },
        "control": {
            "config_frame_hex": config_frame.hex(),
            "config_crc16": config_frame_crc,
            "config_repeat": args.config_repeat,
            "config_interval_s": args.config_interval_s,
            "start_frame_size": START_FRAME_SIZE,
            "start_airtime_s": start_toa_s,
            "start_repeat": args.start_repeat,
            "start_interval_s": args.start_interval_s,
            "start_arm_delay_s": args.start_arm_delay_s,
            "start_delay_semantics": (
                "start_delay_ms is measured from the receiver's completed START frame "
                "to the shared NODE_WARMUP begin time"
            ),
            "usrp_device_args": args.device_args,
            "usrp_tx_gain_db": args.usrp_tx_gain,
            "antenna": args.antenna,
            "control_phy": {
                "sample_rate_hz": CONTROL_SAMPLE_RATE_HZ,
                "bandwidth_hz": CONTROL_BANDWIDTH_HZ,
                "spreading_factor": CONTROL_SPREADING_FACTOR,
                "coding_rate": "4/5",
                "sync_word": SYNC_WORD,
            },
        },
        "events": [],
    }

    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest_dir / f"run_{config.run_id:08x}.json"

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Manifest: {manifest_path.resolve()}")
    save_manifest(manifest_path, manifest)
    if args.dry_run:
        manifest["dry_run"] = True
        save_manifest(manifest_path, manifest)
        return 0

    transmitter = ControlTransmitter(
        args.device_args, args.usrp_tx_gain, args.antenna, args.rf_bandwidth
    )
    try:
        transmitter.start()
        print(
            f"ARMED: start the dual-channel receiver now; CONFIG begins in {args.pre_config_delay_s:.1f} s"
        )
        time.sleep(args.pre_config_delay_s)

        for index in range(args.config_repeat):
            event_time = utc_now()
            transmitter.send(config_frame)
            manifest["events"].append(
                {"type": "CONFIG_ENQUEUED", "index": index + 1, "utc": event_time.isoformat()}
            )
            save_manifest(manifest_path, manifest)
            print(f"CONFIG {index + 1}/{args.config_repeat}: {event_time.isoformat()}")
            time.sleep(args.config_interval_s)

        print(
            f"CONFIG complete; START series in {args.pre_start_delay_s:.1f} s "
            f"({args.start_repeat} frames)"
        )
        time.sleep(args.pre_start_delay_s)
        start_series_begin = utc_now()
        warmup_begin_time = start_series_begin + timedelta(seconds=args.start_arm_delay_s)
        traffic_begin_time = warmup_begin_time + timedelta(seconds=args.warmup_s)
        manifest["expected_warmup_begin_utc"] = warmup_begin_time.isoformat()
        manifest["expected_traffic_begin_utc"] = traffic_begin_time.isoformat()
        manifest["expected_capture_end_utc"] = (
            traffic_begin_time
            + timedelta(seconds=args.duration_s + args.tail_s)
        ).isoformat()
        save_manifest(manifest_path, manifest)
        print(
            f"START target warmup begin: {warmup_begin_time.isoformat()} "
            f"(traffic begins {traffic_begin_time.isoformat()})"
        )
        for index in range(args.start_repeat):
            event_time = utc_now()
            frame_end_time = event_time + timedelta(seconds=start_toa_s)
            start_delay_s = (warmup_begin_time - frame_end_time).total_seconds()
            if start_delay_s <= 0.0:
                raise RuntimeError(
                    "START series ran late; computed non-positive start_delay_ms"
                )
            start_delay_ms = round(start_delay_s * 1000.0)
            start_frame = encode_start(
                config.run_id,
                config_frame_crc,
                start_delay_ms=start_delay_ms,
            )
            transmitter.send(start_frame)
            manifest["events"].append(
                {
                    "type": "START_ENQUEUED",
                    "index": index + 1,
                    "utc": event_time.isoformat(),
                    "start_delay_ms": int(start_delay_ms),
                    "frame_hex": start_frame.hex(),
                    "target_warmup_begin_utc": warmup_begin_time.isoformat(),
                }
            )
            save_manifest(manifest_path, manifest)
            print(
                f"START {index + 1}/{args.start_repeat}: {event_time.isoformat()} "
                f"delay_ms={start_delay_ms}"
            )
            if index + 1 < args.start_repeat:
                time.sleep(args.start_interval_s)
        print(f"Keep receiver capture running until {manifest['expected_capture_end_utc']}")
        time.sleep(start_toa_s + 1.0)
    finally:
        transmitter.stop()
        save_manifest(manifest_path, manifest)

    return 0


if __name__ == "__main__":
    sys.exit(main())
