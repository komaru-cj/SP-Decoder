#!/usr/bin/env python3
"""Rebuild 24 frozen six-packet native-IQ scenes and export mechanism evidence."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/sp_six_packet_mpl')
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
from pathlib import Path
import sys, json, csv, hashlib, argparse
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from real_collision_experiment.paper_experiments import run_boundary_fairness as b
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image, ImageOps

OUT = ROOT / 'real_usrp_outputs/six_packet_fig1_fig3_20261104'


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def rank(values, index):
    # Match np.argmax's first-index tie breaking.
    return int(1 + np.sum(values > values[index]) + np.sum(values[:index] == values[index]))


def scene(spec):
    samples, truth, noise = b.synthesize(spec)
    n = b.n
    physical, white, estimates, sigma, W, cal = n.a.controlled_inputs(samples, truth, n.CFG)
    configured = b.attach_sp_reliability_and_lambda(
        white, estimates, n.CFG, noise_sigma2=sigma, gamma=.05,
        reference_guard=True, physical_samples=physical, whitener=W, multiuser_lambda_cap=4.)
    physical = np.asarray(physical, dtype=np.complex64)
    cache = b.IntegerPayloadCache()
    context = b.PaperComparisonContext(physical, estimates, n.CFG,
        frontend_method='mrc', payload_spectrum_cache=cache)
    products = []
    for u in spec['focus']:
        e = configured[u]
        spectra = np.asarray([cache.spectra_for(physical, e, n.CFG, j)
                              for j in range(n.CFG.payload_symbol_count)])
        white_fft = np.einsum('ab,sbk->sak', W, spectra)
        h = n.a.complex_pairs(e['channel_sp']); h /= np.linalg.norm(h)
        orth = np.array([-np.conj(h[1]), np.conj(h[0])])
        p = abs(np.einsum('a,sak->sk', h.conj(), white_fft)) ** 2
        q = abs(np.einsum('a,sak->sk', orth.conj(), white_fft)) ** 2
        score = p - e['lambda_sp'] * q
        sp_bins = np.argmax(score, axis=1).tolist()
        original = n.a.projected_decisions(white, e, n.CFG)[0]
        assert original == sp_bins, 'SP spectrum reconstruction differs from receiver'
        mrc_bins = context.decode_mrc(estimates[u])['symbol_bins']
        mh, _, _ = b.physical_preamble_measurements(physical, estimates[u], n.CFG)
        mh /= np.linalg.norm(mh)
        mrc_power = abs(np.einsum('a,sak->sk', mh.conj(), spectra)) ** 2
        assert np.argmax(mrc_power, axis=1).tolist() == mrc_bins
        products.append((p, q, score, mrc_power, sp_bins, mrc_bins))
    return samples, truth, noise, configured, products


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=['equal', 'strong'], default='equal')
    parser.add_argument('--render-only', action='store_true')
    args = parser.parse_args()
    if args.profile == 'strong': OUT = OUT / 'strong_interference'
    OUT.mkdir(parents=True, exist_ok=True)
    b.initialize()
    if args.render_only:
        summary = json.loads((OUT / 'summary.json').read_text())
        symbols = list(csv.DictReader((OUT / 'all_symbols.csv').open()))
        for row in symbols:
            for key in ('full_payloads', 'rank_mrc', 'rank_support', 'rank_sp'):
                row[key] = int(row[key])
            for key in ('mrc_correct', 'sp_correct', 'support_correct'):
                row[key] = row[key] == 'True'
            for key in ('eta_true', 'eta_mrc_winner'):
                row[key] = float(row[key])
        packets = list(csv.DictReader((OUT / 'all_packets.csv').open()))
        with np.load(OUT / 'selected_scene_and_spectra.npz') as arrays:
            render(summary, symbols, packets, arrays['support'], arrays['orthogonal'], arrays['signed_score'])
        return
    manifest = json.loads((b.OUT / 'manifest.json').read_text())
    if args.profile == 'equal':
        specs = [s for s in manifest['jobs'] if s['family'] == 'temporal'
                 and s['k'] == 6 and s['width_ratio'] == .05]
        assert len(specs) == 24
    else:
        specs = [s for s in manifest['jobs'] if s['family'] == 'geometry'
                 and s['k'] == 6 and s['individual_sir_db'] == -5.]
        assert len(specs) == 192
    population = ('24 equal-power scenes; all six targets' if args.profile == 'equal' else
                  '192 strong-interference scenes; designated target in each; all six supported angle strata, 32 scenes each')
    b.n.a.write_json(OUT / 'input_manifest.json', dict(
        source_manifest=str(b.OUT / 'manifest.json'), revision=manifest['revision'], specs=specs,
        evidence='Native measured-IQ superposition; controlled start/CFO; not simultaneous-air capture',
        population=population,
        qualifying_rule='Entire target FFT window lies inside the payload intervals of all six frames',
        example_rule='Median support-rank improvement among full-six-payload windows where physical MRC and support both fail, and online SP is correct; ties by repeat,target,symbol',
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    symbols, packets = [], []
    for scene_index, spec in enumerate(specs):
        key = b.n.a.job_key(spec)
        frozen = json.loads((b.OUT / 'jobs' / (key + '.json')).read_text())
        samples, truth, noise, configured, products = scene(spec)
        payload_starts = np.array([v['start_sample'] for v in truth]) + b.n.CFG.payload_start_symbols * b.n.CFG.samples_per_symbol
        frame_ends = np.array([v['start_sample'] for v in truth]) + b.n.CFG.frame_samples
        for u, (p, q, score, mrc_power, spbins, mrcbins) in zip(spec['focus'], products):
            e = configured[u]; target = truth[u]
            old = next(v for v in frozen['targets'] if v['target_index'] == u)
            assert abs(e['lambda_sp'] - old['lambda_sp']) < 1e-9
            metrics = {m: b.n.h.payload_metric(v, target, b.n.CFG)
                       for m, v in [('sp', spbins), ('mrc', mrcbins)]}
            for method in metrics:
                assert metrics[method]['delivered'] == old['methods'][method]['delivered']
                assert abs(metrics[method]['ser'] - old['methods'][method]['ser']) < 1e-12
            packets.append(dict(job=key, repeat=spec['repeat'], target=u, position=target['position'],
                lambda_sp=e['lambda_sp'], sp_delivered=metrics['sp']['delivered'],
                mrc_delivered=metrics['mrc']['delivered'], sp_ser=metrics['sp']['ser'], mrc_ser=metrics['mrc']['ser']))
            for j, true in enumerate(target['symbol_bins']):
                left = payload_starts[u] + j * b.n.CFG.samples_per_symbol
                right = left + b.n.CFG.samples_per_symbol
                full = int(np.sum((payload_starts <= left) & (frame_ends >= right)))
                wrong = mrcbins[j]; support_bin = int(np.argmax(p[j]))
                symbols.append(dict(job=key, repeat=spec['repeat'], target=u, symbol=j,
                    full_payloads=full, true_bin=true, physical_mrc_bin=wrong, support_bin=support_bin,
                    sp_bin=spbins[j], lambda_sp=e['lambda_sp'], mrc_correct=wrong == true,
                    support_correct=support_bin == true, sp_correct=spbins[j] == true,
                    rank_mrc=rank(mrc_power[j], true), rank_support=rank(p[j], true), rank_sp=rank(score[j], true),
                    eta_true=float(q[j, true] / max(p[j, true] + q[j, true], 1e-30)),
                    eta_mrc_winner=float(q[j, wrong] / max(p[j, wrong] + q[j, wrong], 1e-30))))
        print(f"Rebuilt and matched {scene_index + 1}/{len(specs)} scenes", flush=True)
    write_csv(OUT / 'all_symbols.csv', symbols)
    write_csv(OUT / 'all_packets.csv', packets)
    full = [r for r in symbols if r['full_payloads'] == 6]
    eligible = [r for r in full if not r['mrc_correct'] and not r['support_correct'] and r['sp_correct']]
    eligible.sort(key=lambda r: (r['rank_support'] - r['rank_sp'], r['repeat'], r['target'], r['symbol']))
    assert eligible, 'No qualifying rescue example; preserve statistics and inspect actual results'
    selected = eligible[len(eligible) // 2]
    spec = next(s for s in specs if b.n.a.job_key(s) == selected['job'])
    samples, truth, noise, configured, products = scene(spec)
    u, j = selected['target'], selected['symbol']
    p, q, score = [v[j] for v in products[spec['focus'].index(u)][:3]]
    np.savez_compressed(OUT / 'selected_scene_and_spectra.npz', samples=samples,
                        support=p, orthogonal=q, signed_score=score)
    write_csv(OUT / 'selected_spectrum.csv', [dict(fft_bin=i, support=float(p[i]),
        orthogonal=float(q[i]), penalty=float(selected['lambda_sp'] * q[i]), signed_score=float(score[i])) for i in range(len(p))])
    counts = [sum(r['mrc_correct'] and r['sp_correct'] for r in full),
              sum(not r['mrc_correct'] and r['sp_correct'] for r in full),
              sum(r['mrc_correct'] and not r['sp_correct'] for r in full),
              sum(not r['mrc_correct'] and not r['sp_correct'] for r in full)]
    summary = dict(scenes=len(specs), packets=len(packets), all_symbol_windows=len(symbols),
        full_six_payload_windows=len(full), illustrative_rescue_candidates=len(eligible),
        selected_example=selected, selected_spec=spec, selected_truth=truth,
        all_four_outcomes=dict(zip(['both_correct', 'rescued', 'harmed', 'both_wrong'], counts)),
        sp_packet_successes=sum(r['sp_delivered'] for r in packets),
        mrc_packet_successes=sum(r['mrc_delivered'] for r in packets),
        profile=args.profile, population=population,
        checks=dict(all_packets_match_frozen_results=True, all_sp_bins_match_receiver=True,
                    physical_mrc_spectrum_argmax_matches_decoder=True,
                    selected_all_six_payloads_cover_entire_fft_window=selected['full_payloads'] == 6),
        evidence='Measured native-IQ replay, not six simultaneous over-air transmitters',
        interpretation='Illustration is selected conditional on rescue; aggregate statistics retain all qualifying windows including harm. No new independent channel deployment.')
    b.n.a.write_json(OUT / 'summary.json', summary)
    render(summary, symbols, packets, p, q, score)


def render(summary, symbols, packets, p, q, score):
    selected = summary['selected_example']
    full = [r for r in symbols if r['full_payloads'] == 6]
    counts = [summary['all_four_outcomes'][k] for k in ('both_correct', 'rescued', 'harmed', 'both_wrong')]
    specs = range(summary['scenes'])
    population = summary.get('population', '24 equal-power scenes; all six targets')
    condition_label = ('each interferer +5 dB' if summary.get('profile') == 'strong' else 'equal received power')
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    figs = []
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.45))
    scale = float(max(p.max(), q.max(), abs(score).max()))
    x = np.arange(len(p)); true = selected['true_bin']; wrong = selected['physical_mrc_bin']
    for ax, y, title, color in zip(axes, [p, q, score],
        ['(a) Target support $|P[k]|^2$', '(b) Orthogonal evidence $|Q[k]|^2$',
         '(c) Signed score $|P[k]|^2-\\lambda|Q[k]|^2$'], ['#2878b5', '#d88418', '#16856a']):
        ax.plot(x, y / scale, color=color, lw=.9)
        ax.axvline(true, color='#16856a', ls='--', lw=1, label=f'Target bin {true}')
        ax.axvline(wrong, color='#b83b63', ls=':', lw=1, label=f'MRC wrong bin {wrong}')
        ax.scatter([true, wrong], y[[true, wrong]] / scale, c=['#16856a', '#b83b63'], s=23, zorder=5)
        ax.set(xlim=(0, len(p)-1), xlabel='FFT bin', ylabel='Value / common energy scale', title=title)
        ax.grid(alpha=.15); ax.legend(fontsize=8, loc='upper right')
    axes[2].axhline(0, color='.5', lw=.6)
    fig.suptitle(f'Six measured packet IQ traces | {condition_label} | online $\\lambda$={selected["lambda_sp"]:.3g} | target rank {selected["rank_support"]} → {selected["rank_sp"]}', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .92)); figs.append(('fig1_six_packet_spectra', fig))
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.45))
    error = [r for r in full if not r['mrc_correct']]
    for field, label, color in [('eta_true', 'True target bin', '#16856a'), ('eta_mrc_winner', 'MRC wrong bin', '#b83b63')]:
        values = np.sort([r[field] for r in error])
        axes[0].step(np.maximum(values, 1e-12), np.arange(1, len(values)+1)/len(values), where='post', label=label, color=color)
    axes[0].set(xscale='log', xlim=(1e-5, 1), xlabel='$\\eta=|Q|^2/(|P|^2+|Q|^2)$', ylabel='Empirical CDF', title=f'(a) MRC errors (n={len(error):,})')
    # Any values below the display limit remain counted in the CDF and CSV.
    for field, label, color, ls in [('rank_mrc', 'Physical MRC', '#d88418', '--'),
        ('rank_support', 'SP support only', '#2878b5', ':'), ('rank_sp', 'Online SP', '#16856a', '-')]:
        values = np.array([r[field] for r in full]); grid = np.arange(1, b.n.CFG.m+1)
        axes[1].step(grid, [np.mean(values <= k) for k in grid], where='post', color=color, ls=ls, label=label)
    axes[1].set(xscale='log', xlim=(1, b.n.CFG.m), xlabel='True target rank (1 = best)', ylabel='Empirical CDF', title=f'(b) All windows (n={len(full):,})')
    axes[2].bar(range(4), np.array(counts)/len(full), color=['#9ca3af', '#16856a', '#b83b63', '#555555'])
    axes[2].set_xticks(range(4), ['Both\ncorrect', 'SP\nrescues', 'SP\nharms', 'Both\nwrong'])
    axes[2].set(ylabel='Fraction of all full-overlap windows', title='(c) Physical MRC → online SP')
    for i, value in enumerate(counts):axes[2].text(i, value/len(full)+.025, f'{value/len(full):.1%}', ha='center', fontsize=9)
    for ax in axes:
        ax.set_ylim(0, 1.05); ax.grid(alpha=.15, axis='y')
    for ax in axes[:2]:ax.legend(fontsize=8, loc='lower right')
    fig.suptitle(f'Six-packet statistics | {condition_label} | {len(specs)} scenes, {len(packets)} target packets', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .92)); figs.append(('fig3_six_packet_statistics', fig))
    with PdfPages(OUT / 'fig1_fig3_six_packet.pdf') as pdf:
        for name, fig in figs:
            for ext in ('pdf', 'svg', 'png'):fig.savefig(OUT / f'{name}.{ext}', dpi=220, bbox_inches='tight')
            pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)
    ims = [Image.open(OUT / f'{name}.png').convert('RGB') for name, _ in figs]
    canvas = Image.new('RGB', (max(im.width for im in ims), sum(im.height for im in ims)+20), 'white')
    y = 0
    for im in ims:canvas.paste(im, (0,y)); y += im.height+20
    canvas.save(OUT / 'overview.png')
    (OUT / 'README.md').write_text(
        '# 六包 Fig.1 / Fig.3\n\n'
        f'来源：{len(specs)}个冻结的K=6、W/Tpayload=0.05、SNR10dB场景；{len(packets)}个目标包。配置：{population}。原始实测IQ数字叠加，受控起点/CFO，混合前导估计参考，正式guard-v2单次配置λ、上限4。不是六节点同时空口采集。\n\n'
        f'全体{len(symbols)}个目标符号中，{len(full)}个窗口完全落在全部六包的payload区间内；所有统计包含损伤和失败。Fig.3(a)仅在物理MRC错误的{len(error)}个窗口上比较η，(b)(c)以全部合格窗口为分母。\n\n'
        'Fig.1是明确选取的救回示例：在物理MRC和SP支持分支均失败、在线SP成功的六包窗口中，取支持排名改善的中位例子；它不估计总体成功率。Fig.1三个面板使用一个共同能量归一化尺度；反证项是抑制竞争峰、改善相对排名，不声称绝对放大目标能量。Fig.1的支持投影属于SP白化参考，不能直接等同物理MRC；图中另标物理MRC的错误bin，Fig.3(b)分别给出两者。\n\n'
        f'Fig.3(c)依次为：双方正确{counts[0]}、SP救回{counts[1]}、SP损伤{counts[2]}、双方错误{counts[3]}。包成功SP={summary["sp_packet_successes"]}/{len(packets)}，MRC={summary["mrc_packet_successes"]}/{len(packets)}。\n\n'
        f'验证：{len(packets)}包的SP/MRC成功与SER均匹配冻结结果；全部SP符号匹配原接收机；物理MRC谱argmax匹配其解码器。CSV、示例IQ、谱、选择规则和源manifest均附带。重复噪声与初相不代表独立部署。\n', encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('selected_truth','selected_spec')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
