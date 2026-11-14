"""Sample-quantized packet start spans for controlled arrival density."""
import numpy as np


def scaled_starts(offsets_symbols, density, samples_per_symbol, prefix_symbols=3):
    offsets=np.asarray(offsets_symbols,dtype=float)
    if offsets.size<2 or density<=0 or samples_per_symbol<=0:
        raise ValueError('Positive density and at least two starts are required')
    width=float(np.ptp(offsets))
    if width<=0:raise ValueError('Cannot rescale a zero-width start pattern')
    requested_span=(offsets.size-1)/density
    starts=np.rint((prefix_symbols+(offsets-offsets.min())/width*requested_span)*samples_per_symbol).astype(int)
    actual_span=float(np.ptp(starts)/samples_per_symbol)
    if actual_span<=0:raise ValueError('Requested span is below sample resolution')
    return starts,dict(definition='rho=(K-1)*T_sym/(max(start)-min(start))',
        requested_density=float(density),actual_density=float((offsets.size-1)/actual_span),
        requested_span_symbols=float(requested_span),actual_span_symbols=actual_span,
        original_span_symbols=width,scale=float(requested_span/width),
        sample_quantization=True,absolute_jitter_preserved=False,
        relative_start_pattern_preserved_up_to_sample_quantization=True)
