"""MRC comparison baseline on the shared real USRP collision scenes."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "compare") not in sys.path:
    sys.path.insert(0, str(ROOT / "compare"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common_compare import base_arg_parser, evaluate_decoder, get_estimates, load_experiment, write_report  # noqa: E402
from evaluate_sp_dechirp_real_pos import mrc_decode_bins  # noqa: E402


def decode_mrc(samples, truth, est, ref, cfg) -> list[int]:
    h = np.asarray([complex(r, i) for r, i in est["channel"]], dtype=np.complex128)
    bins, _ = mrc_decode_bins(
        samples,
        float(est["start_sample"]),
        float(est["cfo_bins"]),
        float(est.get("sto_samples", 0.0)),
        h,
        cfg,
    )
    return [int(x) for x in bins]


def main() -> None:
    parser = base_arg_parser(__doc__ or "")
    args = parser.parse_args()
    samples, meta, cfg, refs = load_experiment(args)
    modes = get_estimates(args, samples, meta, cfg, refs)
    report = {
        "method": "MRC",
        "paper_model": "maximum-ratio combining baseline",
        "input": str(args.synth),
        "modes": {
            mode: evaluate_decoder("MRC", args, samples, meta, cfg, refs, estimates, decode_mrc)
            for mode, estimates in modes.items()
        },
    }
    write_report(args, report)


if __name__ == "__main__":
    main()
