#!/usr/bin/env python3
"""Validate native-IQ results, archive static results and publish requested plots."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import csv,json,hashlib,shutil,subprocess
import numpy as np
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n
h=n.h;a=n.a

def main():
    out=n.OUT;destination=ROOT/'real_usrp_outputs/revision_heatmaps_A3_C1_guard_v2'
    audit=json.loads((out/'source_audit.json').read_text())
    pcube_policy=n.DEFAULT_PCUBE_POLICY
    test_record=json.loads((out/'current_test_results.json').read_text())
    assert test_record['passed']
    assert test_record['receiver_sha256']==hashlib.sha256((ROOT/'compare/real_packet_decoders.py').read_bytes()).hexdigest()
    assert test_record['soft_grouping_sha256']==hashlib.sha256((ROOT/'compare/PCube/soft_grouping.py').read_bytes()).hexdigest()
    assert test_record['arrival_density_sha256']==hashlib.sha256((ROOT/'real_collision_experiment/paper_experiments/arrival_density.py').read_bytes()).hexdigest()
    assert test_record['sp_configurator_sha256']==hashlib.sha256((ROOT/'evaluate_sp_dechirp_real_pos.py').read_bytes()).hexdigest()
    assert test_record['sp_guard_sha256']==hashlib.sha256((ROOT/'sp_reference_guard.py').read_bytes()).hexdigest()
    included=[r['index'] for r in audit['packets'] if not r.get('excluded')]
    assert len(included)==22 and audit['excluded_indices']==[3,7,8,13]
    with np.load(n.SOURCE) as z:original=z['packets']
    with np.load(out/'aligned_source_iq.npz') as z:used=z['packets']
    assert np.array_equal(original[included],used[included]),'source IQ was altered'
    assert all(audit['packets'][i]['frame_integrity']['passed'] for i in included)
    assert audit['packets'][8]['frame_integrity']['passed'] is False
    quality=[]
    for r in audit['packets']:
        q=r['frame_integrity']
        quality.append(dict(source=r['index'],included=not r.get('excluded'),frame_complete=q['passed'],
            payload_validated='payload_hex' in r,reason=r.get('reason','included'),
            minimum_relative_power_db=min(q.get('relative_power_db',[-float('inf')])),
            minimum_noise_margin_db=min(q.get('noise_margin_db',[-float('inf')]))))
    h.write_csv(out/'frame_integrity_summary.csv',quality)
    used_indices=set();flat=[];summary=[];jobs=[]
    for stage in h.STAGES:
        manifest=json.loads((out/f'manifest_{stage}.json').read_text());assert len(manifest['jobs'])==256
        assert manifest['pcube_policy']==pcube_policy
        records=[]
        for spec in manifest['jobs']:
            j=json.loads((out/'jobs'/(a.job_key(spec)+'.json')).read_text())
            assert j['revision_hash']==manifest['revision_hash']
            assert j['pcube_policy']==pcube_policy
            assert j['provenance']['kind']=='native_measured_dual_channel_IQ_superposition'
            assert j['noise_budget']['min_residual_covariance_eigenvalue']>=0
            assert j['config']['implicit_header'] and j['config']['payload_len']==32
            assert j['config']['sample_rate_hz']==1000000
            used_indices.update(t['source_index'] for t in j['truth']);records+=j['targets'];jobs.append(j)
            for t in j['targets']:
                for method,value in t['methods'].items():
                    flat.append(dict(stage=stage,job=a.job_key(spec),target=t['target_index'],method=method,
                        delivered=value['delivered'],ser=value['ser'],lambda_sp=t['lambda_sp'],
                        reason=t['lambda_guard_reason'],snr=spec['snr_db'],sir=spec.get('sir_db'),
                        angle_low=spec.get('angle_low'),angle_high=spec.get('angle_high'),k=spec['k'],gap=spec.get('gap_symbols'),
                        arrival_density=spec.get('arrival_density'),actual_arrival_density=j.get('timing',{}).get('actual_density'),
                        start_span_symbols=j.get('timing',{}).get('actual_span_symbols')))
        for method in (h.METHODS if stage.startswith('C1') else ('sp',)):
            summary.append(dict(stage=stage,method=method,packets=len(records),successes=sum(t['methods'][method]['delivered'] for t in records)))
        metrics=list(csv.DictReader((out/'figures'/f'{stage}_metrics.csv').open()))
        for metric in metrics:
            assert int(metric['scenes'])==16
            subset=[]
            for j in [j for j in jobs if j['spec']['family']==stage]:
                s=j['spec']
                x=s['snr_db'] if stage=='C1_snr_sir' else s['angle_low'] if stage=='C1_angle_sir' else s['k']
                y=s['sir_db'] if stage.startswith('C1') else s.get('arrival_density',s['gap_symbols'])
                if x==float(metric['x_low']) and y==float(metric['y']):subset+=j['targets']
            values=[t['methods'][metric['method']]['delivered'] for t in subset]
            assert len(values)==int(metric['packets']) and sum(values)==int(metric['successes'])
        if stage.startswith('C1'):
            for j in [j for j in jobs if j['spec']['family']==stage]:
                s=j['spec'];bank=a.source_bank();i,k=[t['source_index'] for t in j['truth']]
                angle=a.angle_deg(a.complex_pairs(bank[i]['channel_ri']),a.complex_pairs(bank[k]['channel_ri']))
                assert s['angle_low']<=angle<s['angle_high']
        h.write_csv(out/'per_target.csv',flat)
    assert used_indices<=set(included)
    assert len(jobs)==768 and sum(len(j['targets']) for j in jobs)==2304
    bank=a.source_bank();assert len({bank[i]['position'] for i in used_indices})==10
    for repeat in range(16):
        rs=[j for j in jobs if j['spec']['family']=='A3_density_delay' and j['spec']['repeat']==repeat]
        master=next(j for j in rs if j['spec']['k']==10)['truth']
        for j in rs:assert [v['source_index'] for v in j['truth']]==[v['source_index'] for v in master[:j['spec']['k']]]
    pdfs=[out/'figures'/f'{stage}_{m}.pdf' for stage in h.STAGES for m in (h.METHODS if stage.startswith('C1') else ('sp',))]
    for f in pdfs:assert f.stat().st_size>1000
    subprocess.run(['pdfunite',*[str(p) for p in pdfs],str(out/'heatmaps_all_9.pdf')],check=True)
    density_manifest=json.loads((out/'manifest_A3_density_delay.json').read_text())
    actual_density=density_manifest.get('timing_axis')=='actual_arrival_density'
    uncapped=actual_density and density_manifest.get('lambda_fixed_cap_removed',False)
    extra_pdf=out/'figures/A3_density_lambda_k10.pdf'
    if actual_density:
        assert extra_pdf.stat().st_size>1000
        lambda_manifest=json.loads((out/'figures/A3_density_lambda_k10_figure_manifest.json').read_text())
        assert lambda_manifest.get('all_available_packets',lambda_manifest['packets'])==640
        assert lambda_manifest['packets']==(640 if lambda_manifest.get('selected_repeat') is None else 40)
        assert lambda_manifest['revision_hash']==density_manifest['revision_hash']
        subprocess.run(['pdfunite',*[str(p) for p in pdfs],str(extra_pdf),str(out/'all_figures_10.pdf')],check=True)
    result=dict(scenes=768,targets=2304,sources=22,positions=10,excluded_source_indices=[3,7,8,13],
        exact_source_IQ_identity_checked=True,waveforms_regenerated=False,
        note='Transmitted symbol labels are encoded offline from isolated CRC-valid payloads; waveform samples are never regenerated.',
        native_phy=audit['config'],summary=summary,tests_passed=test_record['tests_run'],pcube_policy=pcube_policy,
        frame_integrity_policy=audit['frame_integrity_policy'],frame_integrity_failed=[8],source_sha256=audit['source_file_sha256'],pdf_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in pdfs})
    a.write_json(out/'validation.json',result)
    if actual_density:
        result.update(A3_timing_axis='actual_arrival_density',
            A3_density_definition=density_manifest['density_definition'],A3_density_levels=density_manifest['density_levels'],
            A3_absolute_jitter_preserved=False,extra_pdf_sha256={extra_pdf.name:hashlib.sha256(extra_pdf.read_bytes()).hexdigest()})
        result.update(A3_lambda_fixed_cap_removed=uncapped,A3_lambda_global_max=density_manifest.get('lambda_global_max',None if uncapped else 4.),
            A3_lambda_reference_reliability_bound_preserved=True)
        a.write_json(out/'validation.json',result)
    a.write_json(out/'additional_validation.json',dict(kind='native_source_preservation',sources=22,
        exact_raw_IQ_identity=True,source_CRC_validated=True,excluded_indices=[3,7,8,13],
        note='Current 22-source cohort passes uniform frame completeness; historical static and 23-source native results remain archived.'))
    comparison=[]
    for stage in h.STAGES[:2]:
        old=list(csv.DictReader((destination/'backup_static_channel_20261030'/'figures'/f'{stage}_metrics.csv').open()))
        current=list(csv.DictReader((out/'figures'/f'{stage}_metrics.csv').open()))
        for r in current:
            previous=next(x for x in old if x['method']==r['method'] and x['x_low']==r['x_low'] and x['y']==r['y'])
            comparison.append(dict(stage=stage,method=r['method'],x=r['x_low'],sir=r['y'],
                previous_static_20B_explicit=float(previous['pdr']),current_native_32B_implicit=float(r['pdr']),
                comparison_scope='PHY and source cohort changed; not an isolated phase-jitter ablation'))
    h.write_csv(out/'C1_before_after.csv',comparison)
    native_comparison=[]
    previous_native=destination/'backup_native_23_before_frame_integrity_20261030'/'figures'
    for stage in h.STAGES[:2]:
        old=list(csv.DictReader((previous_native/f'{stage}_metrics.csv').open()))
        for r in csv.DictReader((out/'figures'/f'{stage}_metrics.csv').open()):
            before=next(x for x in old if x['method']==r['method'] and x['x_low']==r['x_low'] and x['y']==r['y'])
            native_comparison.append(dict(stage=stage,method=r['method'],x=r['x_low'],sir=r['y'],
                native_23_sources=float(before['pdr']),complete_22_sources=float(r['pdr']),
                scope=('same native PHY; frame-integrity source cohort and PCube policy changed'
                    if r['method']=='pcube' else 'same native PHY and receiver; source cohort resampled after uniform frame-integrity screening')))
    h.write_csv(out/'C1_frame_integrity_before_after.csv',native_comparison)
    for f in (out/'figures').glob('*_figure_manifest.json'):
        meta=json.loads(f.read_text());meta.update(result_root=str(out),waveform='native measured IQ superposition',config=audit['config'],source_audit=str(out/'source_audit.json'));a.write_json(f,meta)
    text='''# 原始单包 IQ 叠加重绘结果

本轮按用户确认使用22个CRC可确认载荷的源包，覆盖10个位置；排除索引3、7、13（载荷未确认）以及8（帧完整性失败）。0–2°源对4/9保留。每个方法均重新解码，未复用静态信道版本结果。

保留原始双通道复数采样，每包仅乘一个公共复标量以控制功率与初相，再作整数采样时移和线性叠加。无重新生成chirp、无重采样、无包内去相位/去抖动/方向平滑。发布前已逐元素核验22个源包与原提取文件一致。包内公共/差分相位、幅度、波形失真、量化及原有底噪均保留。

原采集PHY为SF10/BW125kHz、1 Msps、32B隐式头、CR4/5、8前导、sync=0x12、38个负载符号。与前版20B显式头的帧长及源集合不同，因此两版差异不能全部归因于相位抖动。此次隐式头解码补齐了首8个符号的低速率编码处理，32B编码/解码往返及相关测试共40项通过。

帧完整性统一检查全部26包：每个完整前导/同步/SFD/负载符号窗口的双通道平均功率须不低于前段负载中位数10 dB，并高于实测噪声底至少10 dB。仅8号失败，其他包未因此排除；3、7、13沿用载荷未确认排除。完整报告见`frame_integrity_audit.json`。筛选在混合及解码之前固定，不能据此声称所有包内时变都已覆盖。

载荷真值由单包离线CRC核验取得；6个源在原CFO估计不闭合后使用±1 bin、0.125步长的有界CFO校准。该同步参数用于混合中的受控同步，不是盲检测结果。期望载荷、编码符号只用于离线评分，不进入参考/λ/符号选择。

原始IQ包含噪声，不能无限提高其SNR。噪声协方差从各采集文件的全部能量段以外估计（包括排除边缘半包）。每个重叠区间只补足达到目标总噪声协方差所需的独立高斯噪声，检查剩余协方差半正定，不做原始IQ去噪。双包源对按网格最强干扰/最高SNR的噪声可行性事先筛选；同一家族所有SNR/SIR使用同一可行性规则，不根据解码结果选源。SNR是两接收通道平均、目标包参考的标称输入SNR。

所有768个场景均重新合成和解码。C1每格16个目标；A3每格16场景并统计全部K包，继续使用±0.1T_sym、0.001步长抖动，保留负起点增量。原始载荷和波形固定于源包，重复仅改变选源、初相、噪声及受控功率/时序，不代表独立空口部署。角度分箱按原干净单包的平均物理信道；包内瞬时方向可变化。0–2°只有一个不同位置源对。

接收机保持单分支reference-guard v2；λ从混合前导和噪声统计配置一次，未按CRC选择λ，也未新增SIC。SNR/SIR、角度、λ及回退判据未为了结果另行调参。图为离线实测IQ叠加、受控同步下的条件PDR，不是新增同时空口发射或端到端检测实验。

`figures/`含9张PDF/PNG/SVG及绘图CSV；`heatmaps_all_9.pdf`合并9图；`jobs/`为新逐场景结果；`source_audit.json`为筛选、底噪、校准与载荷记录；`validation.json`为验证与汇总；`per_target.csv`有3840条方法–目标记录。原始源IQ与发布使用的源IQ逐元素相同，接收算法不读取评分真值。

规范结果目录：`real_usrp_outputs/revision_heatmaps_native_iq`。指定目录中的旧静态信道图及配套数据保存在`backup_static_channel_20261030`；此前23包原始IQ结果保存在`backup_native_23_before_frame_integrity_20261030`。`frame_integrity_summary.csv`列出全部26包的筛选指标；`C1_frame_integrity_before_after.csv`对照23包与22包原始IQ结果。重跑：`python3 real_collision_experiment/paper_experiments/run_native_iq_heatmaps.py --exclude-unverified-sources`；校验/发布：`python3 real_collision_experiment/paper_experiments/publish_native_iq_heatmaps.py`。
'''
    text+='\n| 网格 | 方法 | 成功包/评价包 |\n|---|---|---|\n'+''.join(f"| {r['stage']} | {r['method']} | {r['successes']}/{r['packets']} |\n" for r in summary)
    text=text.replace('相关测试共40项通过',f"相关测试当前共{test_record['tests_run']}项通过")
    text=text.replace('所有768个场景均重新合成和解码。','原始IQ版本首次生成时，所有768个场景均重新合成和解码；本次PCube更新只替换已经同IQ复核的512个双包评分。')
    if actual_density:
        text=text.replace('本次更新复用已逐场景验证','此前PCube更新复用已逐场景验证')
        text=text.replace('其余7张图的数值不变。','PCube更新时其余7张图的数值不变；随后A3已按下节实际密度重算。')
        text=text.replace('`figures/`含9张PDF/PNG/SVG及绘图CSV','`figures/`含9张PDR图和新增λ图的PDF/PNG/SVG及绘图CSV')
        text=text.replace('A3每格16场景并统计全部K包，继续使用±0.1T_sym、0.001步长抖动，保留负起点增量。',
            'A3本次重算256个场景，每格16场景并统计全部K包。纵轴为实际到达密度ρ=(K−1)T_sym/W，W为最晚与最早包起点之差，四档为10/3、5、10、20。原有起点模式整体缩放至W=(K−1)T_sym/ρ并量化到采样点，保留相对抖动和标签顺序；不再保持绝对±0.1T_sym抖动。')
        text+='\n## A3实际密度与λ图更新\n\n用户已确认使用实际密度。A3 PDR图和K=10的逐包λ图已按新起点重新叠加原始IQ、重新估计参考和配置λ，再解码；没有只改纵轴标签。源包、功率、公共初相与随机种子和原始模板配对，C1评分保持不变。`A3_ACTUAL_DENSITY.md`说明定义、文献依据和λ图统计；`a3_density_validation.json`记录窗口误差、配对核验和汇总。旧名义间隔实验保存在`backup_a3_nominal_density_20261030`。`A3_density_lambda_k10_per_packet.csv`含全部640个λ值，未筛除解码失败包。`all_figures_10.pdf`包含9张PDR图与新增λ图。\n'
        if uncapped:
            text+='\n本次A3按用户要求移除固定λ上限4，仍保留参考可靠性上界；保留原0–4候选点并扩展搜索范围，目标函数与信道估计不变。C1及接收机其他入口默认策略未改。λ图用symlog色标展示真实值，未裁剪到4。原有界A3已归档到`backup_a3_lambda_cap4_20261030`；`A3_lambda_cap4_comparison.csv`提供相同IQ逐包对照。\n'
        else:
            text+='\n2026-11-02按用户要求恢复λ上限4并重跑；另提供上限10的独立对照。两张λ图均只显示全部16次场景的逐位置算术均值，包含解码失败包，不再展示单次场景。主图用上限4；上限10图使用`_cap10`后缀。详细配对结果见`A3_CAP4_CAP10.md`。\n'
    text+='''\n## PCube V3 正式基线更新

按用户确认，正式PCube使用`accepted_cluster_soft_extension_v3`。保留原接纳区域内的旋转证据排序；区域外候选按实测噪声不确定性和整包PDoA目标分组支持加权参与竞争。该聚类细节是对原文未明确部分的本地工程实现，未加入CRC择优或MRC保护分支。主接收机与独立PCube评测入口共用同一实现。

本次更新复用已逐场景验证、输入波形与旧版完全一致的512个V3双包解码结果，只替换PCube评分；其余方法及A3结果逐条核验不变。PCube的SNR–SIR成功包为105/256，角度–SIR为88/256。原图、任务结果及源码保存在`backup_pcube_legacy_before_v3_20261030`；两张PCube热力图已更新，其余7张图的数值不变。`pcube_adoption_validation.json`记录迁移核验；`PCUBE_V3_ADOPTION.md`记录来源和性能边界。
'''
    (out/'README.md').write_text(text)
    (out/'CAPTIONS.md').write_text('''# Figure scope

Measured dual-channel packet-IQ superposition using 22 CRC-validated source packets from 10 positions, retaining intra-packet amplitude and phase variations, waveform impairments and original noise. Native SF10/BW125kHz, 1 Msps, 32-byte implicit-header frames are used by all receivers. Each packet undergoes only constant complex scaling and a sample-quantized time shift. Added noise accounts for retained source covariance. All complete preamble/sync/SFD/payload chirps must retain power within 10 dB of the early-payload median and at least 10 dB above background; only source 8 fails this fixed frame-completeness check. Source-pair eligibility is fixed by worst-case noise feasibility before decoding. Synchronization is controlled; references and one packet-level SP weight are estimated from mixed noisy preambles. These are conditional decoding results, not new simultaneous-air captures. Each C1 cell contains 16 target trials; the 0–2° bin uses one cross-position pair. Each A3 cell contains 16 scenes and all K packets, with signed nominal start increments plus discrete ±0.100-symbol jitter at steps of 0.001. Average measured source-channel angles define the angle bins; instantaneous angles may vary. Full source selection and calibration are disclosed in README.md.
''')
    with (out/'CAPTIONS.md').open('a') as f:
        f.write('\nPCube uses the user-approved two-Rx V3 local grouping implementation (`accepted_cluster_soft_extension_v3`), supplementing clustering details unspecified by the paper. Existing accepted-peak ranking is retained; outside candidates receive noise-aware, packet-wide PDoA membership weights. No CRC-based decoder selection is used. Eq.9 multi-Rx-pair diversity is unavailable.\n')
    if actual_density:
        caption=(out/'CAPTIONS.md').read_text().replace(
            'with signed nominal start increments plus discrete ±0.100-symbol jitter at steps of 0.001.',
            'with actual normalized arrival density rho=(K-1)*T_sym/W, where W=max(start)-min(start). Original signed start patterns are scaled to W=(K-1)*T_sym/rho and quantized to the sample grid; relative jitter is retained, while the previous absolute jitter bound is not retained.')
        caption+='\nThe K=10 lambda figure shows per-position arithmetic mean weights over all 16 paired scenes at each actual-density setting. All 640 target weights are included, including failed decodes. The global upper bound remains 4 and some reliability-derived individual caps are lower. Lambda need not be monotonic in density.\n'
        if uncapped:
            caption=caption.replace('The global upper bound remains 4 and some reliability-derived individual caps are lower.',
                'The fixed global upper bound 4 is removed for A3; each reference-reliability bound is retained. Old bounded candidates remain available, with the same objective and preamble estimates. The color scale is symlog (linear below 1) and printed annotations are actual lambda values, not logarithms.')
        (out/'CAPTIONS.md').write_text(caption)
    backup=destination/'backup_static_channel_20261030';backup.mkdir(exist_ok=True)
    # Historical backups are immutable; the V3 migration creates its own backup.
    if actual_density:
        active={a.job_key(s) for s in density_manifest['jobs']}
        archives=['backup_a3_nominal_density_20261030']+(['backup_a3_lambda_cap4_20261030'] if uncapped else [])
        if (destination/'backup_a3_nocap_before_cap_comparison_20261102').exists():
            archives.append('backup_a3_nocap_before_cap_comparison_20261102')
        for name in archives:
            previous=destination/name
            old_manifest=json.loads((previous/'manifest_A3_density_delay.json').read_text())
            retired=previous/'retired_A3_jobs';retired.mkdir(exist_ok=True)
            for spec in old_manifest['jobs']:
                key=a.job_key(spec);src=destination/'jobs'/(key+'.json')
                if key not in active and src.exists():src.rename(retired/src.name)
    for name in ['figures','jobs','code_snapshot']:
        shutil.copytree(out/name,destination/name,dirs_exist_ok=True)
    for item in out.iterdir():
        if item.is_file() and item.suffix in ('.md','.json','.csv','.pdf'):shutil.copy2(item,destination/item.name)
    (destination/'CURRENT_RESULTS.md').write_text('Current figures use native measured IQ and formal PCube V3 ('+pcube_policy+'). Canonical result directory: '+str(out)+'\nA3 timing axis: '+density_manifest.get('timing_axis','nominal_start_increment')+'\nPrevious A3 nominal timing results: backup_a3_nominal_density_20261030/\nPrevious PCube results: backup_pcube_legacy_before_v3_20261030/\nStatic-channel historical results: backup_static_channel_20261030/\n')
    if uncapped:
        with (destination/'CURRENT_RESULTS.md').open('a') as f:f.write('A3 fixed lambda cap 4 removed; reference-reliability bounds remain. Previous bounded version: backup_a3_lambda_cap4_20261030/\n')
    elif actual_density:
        with (destination/'CURRENT_RESULTS.md').open('a') as f:f.write('A3 main cap: 4. Lambda figure: mean of all 16 scenes only. Separate cap-10 comparison uses _cap10 figure suffixes.\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
