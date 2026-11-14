"""PCube diagnostic driver using the formal two-Rx V3 decoder.

This legacy SER-based harness shares preamble estimation, candidate extraction
and PDoA grouping with PaperComparisonContext. The author's multi-Rx-pair Eq.9
gain is unavailable with two antennas; V3 is a disclosed local grouping choice.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / 'compare', ROOT / 'real_collision_experiment/node01_sp_receiver'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from common_compare import base_arg_parser, evaluate_decoder, get_estimates, load_experiment, write_report
from compare.real_packet_decoders import DEFAULT_PCUBE_POLICY, PaperComparisonContext, PhysicalEvidencePayloadCache


def decode_pcube(samples, truth, est, ref, cfg, *, context=None) -> list[int]:
    # truth and ref belong only to the scoring harness and never reach decoder.
    if context is None:
        context = PaperComparisonContext(samples, [est], cfg, frontend_method='pcube')
    return context.decode_pcube(est)['symbol_bins']


def main() -> None:
    args = base_arg_parser(__doc__ or '').parse_args()
    samples, meta, cfg, refs = load_experiment(args)
    modes = get_estimates(args, samples, meta, cfg, refs)
    results = {}
    for mode, estimates in modes.items():
        context = PaperComparisonContext(samples, estimates, cfg, frontend_method='pcube',
            payload_spectrum_cache=PhysicalEvidencePayloadCache())

        def decode_packet(samples, truth, est, ref, cfg):
            return decode_pcube(samples, truth, est, ref, cfg, context=context)

        results[mode] = evaluate_decoder('PCube-PDoA', args, samples, meta, cfg, refs, estimates, decode_packet)
    write_report(args, dict(method='PCube-1RxPair',
        paper='PCube: Scaling LoRa Concurrent Transmissions with Reception Diversities',
        adaptation='two Rx antennas; V3 local PDoA grouping; multi-pair diversity unavailable',
        grouping_policy=DEFAULT_PCUBE_POLICY,
        decoder_implementation='compare.real_packet_decoders.PaperComparisonContext.decode_pcube',
        input=str(args.synth), modes=results))


if __name__ == '__main__':
    main()
