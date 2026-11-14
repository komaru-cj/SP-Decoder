"""Pre-decoding completeness check, shared by every measured source packet."""
import numpy as np

def check_frame_integrity(packet,cfg,noise_power,*,maximum_drop_db=10.,minimum_noise_margin_db=10.):
    positions=list(range(cfg.preamble_len+4))+[cfg.payload_start_symbols+q for q in range(cfg.payload_symbol_count)]
    powers=[]
    for position in positions:
        start=round(position*cfg.samples_per_symbol)
        window=packet[:,start:start+cfg.samples_per_symbol]
        if window.shape[1]!=cfg.samples_per_symbol:
            return dict(passed=False,reason='missing_samples')
        powers.append(float(np.mean(abs(window)**2)))
    powers=np.asarray(powers);reference=float(np.median(powers[cfg.preamble_len+4:cfg.preamble_len+4+30]))
    relative=10*np.log10(np.maximum(powers,1e-30)/max(reference,1e-30))
    noise_margin=10*np.log10(np.maximum(powers,1e-30)/max(noise_power,1e-30))
    bad=np.flatnonzero((relative < -maximum_drop_db)|(noise_margin < minimum_noise_margin_db))
    return dict(passed=bool(len(bad)==0),reason='complete' if len(bad)==0 else 'required_chirp_energy_missing_or_near_noise',
        maximum_drop_db=maximum_drop_db,minimum_noise_margin_db=minimum_noise_margin_db,
        reference_power=reference,relative_power_db=relative.tolist(),noise_margin_db=noise_margin.tolist(),
        failed_chirp_indices=bad.tolist(),failed_symbol_positions=[positions[i] for i in bad])
