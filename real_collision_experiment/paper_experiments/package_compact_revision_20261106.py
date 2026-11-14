#!/usr/bin/env python3
"""Validate frozen rerun records and package figures, tables, provenance, and reports."""
from pathlib import Path
import sys,json,csv,hashlib,subprocess,shutil,zipfile,collections
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from real_collision_experiment.paper_experiments import run_compact_revision_20261106 as c
OUT=c.OUT

def table(rows,keys,headers):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(keys))+'|',*['|'+'|'.join(str(row[k]) for k in keys)+'|' for row in rows]])

def main():
    c.b.initialize();man=json.loads((OUT/'manifest_main.json').read_text());summary=json.loads((OUT/'results_summary.json').read_text())
    counts={};paired={};profiles={}
    for stage in ('pilot','main','blind','blind_calibration'):
        manifest=json.loads((OUT/f'manifest_{stage}.json').read_text());folder='blind_jobs' if stage.startswith('blind') else 'jobs'
        records=[]
        for spec in manifest['specs']:
            j=json.loads((OUT/folder/(c.key(spec)+'.json')).read_text());assert j['spec']==spec
            assert all(u in c.b.CHANNELS for u in spec['sources'])
            assert len({c.b.POSITIONS[u] for u in spec['sources']})==spec['k']
            assert j['noise_budget']['min_residual_eigenvalue']>=-1e-8*j['noise_budget']['variance']
            if stage in ('pilot','main'):
                assert len(j['reference'])==38
                assert all(0<=v['delta_deg']<=90.000001 for v in j['reference'])
                for metric in j['metrics'].values():assert 0<=metric['ser']<=1
            if stage=='main':
                assert set(j['metrics'])==set(c.METHODS)
                if j['lambda_sp']==0:
                    assert j['metrics']['sp']['delivered']==j['metrics']['mrc']['delivered']
                    assert j['metrics']['sp']['ser']==j['metrics']['mrc']['ser']
                pair=(spec['family'],spec['angle_low'],spec['repeat'])
                invariant=[spec[k] for k in ('sources','seed','phases','relative_offsets','width_ratio')]
                if pair in paired:assert paired[pair]==invariant
                paired[pair]=invariant
            records.append(j)
        counts[stage]=len(records);profiles[stage]=records
    assert counts==dict(pilot=968,main=4400,blind=120,blind_calibration=44)
    for record in profiles['blind']:
        paired_control=json.loads((OUT/'blind_controlled_jobs'/(c.key(record['spec'])+'.json')).read_text())
        assert paired_control['spec']==record['spec']
        assert len(paired_control['targets'])==len(record['targets'])
    for name,sha in man['code_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    source=c.b.n.OUT/'aligned_source_iq.npz';source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    assert source_sha==c.b.CAL['source_iq_sha256']
    assert len({c.b.n.AUDIT['packets'][u]['payload_hex'] for u in c.b.CHANNELS})==22
    for item in summary['figures']:
        for ext in ('png','pdf','svg'):assert (OUT/'figures'/f'{item}.{ext}').stat().st_size>1000
    v=dict(complete=True,counts=counts,paired_conditions_verified=len(paired),all_source_hashes_match=True,
           all_zero_lambda_decisions_match_mrc=True,all_noise_budgets_valid=True,blind_matched_control_scenes=120,
           raw_source_iq=str(source),raw_source_iq_sha256=source_sha,
           scope='Existing fixed development source pool; controlled mixtures and blind replay are separate; no new simultaneous over-air acquisition.')
    c.write(OUT/'validation.json',v)
    # Keep original six-packet work as an explicitly identified companion.
    six=ROOT/'real_usrp_outputs/six_packet_fig1_fig3_20261104/strong_interference/fig1_fig3_six_packet.pdf'
    subprocess.run(['pdfunite',str(six),str(OUT/'all_new_figures.pdf'),str(OUT/'all_figures_with_six_packet_mechanism.pdf')],check=True)
    main_paths=[six,*[OUT/'figures'/f'{name}.pdf' for name in ('fig12_main_robustness','fig13_main_collision_boundary','fig10_11_main_reference_cdf','tables_T12_T13')]]
    subprocess.run(['pdfunite',*[str(p) for p in main_paths],str(OUT/'main_text_candidate_figures.pdf')],check=True)
    for filename in ('cell_summary.csv','spatial_gain_summary.csv'):
        shutil.copy2(c.b.OUT/filename,OUT/'tables'/('boundary_source_'+filename))
    for name in ('run_compact_revision_20261106.py','run_compact_aux_20261106.py','render_compact_revision_20261106.py','package_compact_revision_20261106.py','FIGURE_PANEL_PLAN_20261104.md','FIGURE_DATA_READINESS_20261106.md'):
        shutil.copy2(Path(__file__).with_name(name),OUT/'code_snapshot'/name)
    rr=profiles['main'];total=len(rr)
    method_counts={method:sum(r['metrics'][method]['delivered'] for r in rr) for method in c.METHODS}
    rescue=sum(r['metrics']['sp']['delivered'] and not r['metrics']['mrc']['delivered'] for r in rr)
    harm=sum(r['metrics']['mrc']['delivered'] and not r['metrics']['sp']['delivered'] for r in rr)
    text=['# 重跑结果与范围','',f'本次完成968次单包标定、4400次双包测试、120个盲碰撞场景及44个盲单包对照。Fig.13复用已核验矩阵，未假称重新采集。','',
          f'标定规则给出s0={man["s0"]}dB，s_good={man["s_good"]}dB；s0是该网格首个单包MRC PDR≥90%的点，不是精确或通用LoRa灵敏度。每个正式双包格100次。','',
          '## Fig.12','',f'全部正式网格SP/MRC/PCube/MaLoRaGW成功数分别为{method_counts}，分母{total}。相对MRC救回{rescue}包、额外损失{harm}包。整体池化只作审计，正式结论使用逐条件图，不能把均匀网格当作实际部署条件分布。','']
    t12=[]
    for row in summary['T12']:
        t12.append({**row,**{k:f'{100*row[k]:.2f}%' for k in ('sp_pdr','mrc_pdr','rescue_rate','harm_rate','fallback_rate')}})
    text+=[table(t12,['condition','n','sp_pdr','mrc_pdr','rescue_rate','harm_rate','fallback_rate'],['条件','N','SP','MRC','救回','损失','回退']),'',
           '## 信道参考与同步','',
           '正式条件解码参考和λ均从混合前导估计；共同输入已知数字起点、源包单包标定CFO与确认候选。盲诊断则仅输入混合IQ，使用SP实际匿名检测与同步后比较SP-core、固定λ同步细化SP及共享该前端的MRC；不声称测试了三个完全独立前端。','',
           '参考稳定性重算使用全部合格源，未沿用旧稳定性筛选池。偏差指标为已知真实payload bin的混合双通道向量相对物理混合前导参考的非负射影角：这是离线观察一致性，不是干净目标信道估计误差。CDF包含全部38个payload符号，轨迹阴影为10–90%数据分位带而非置信区间。','',
           '## 盲前端','']
    bt=list(csv.DictReader((OUT/'tables/blind_frontend_diagnostic.csv').open()));bc=summary['blind_isolated_controls']
    for row in bc:text.append(f'- 单包盲对照SNR={row["snr"]}dB：{row["targets"]}目标，起点/CFO门匹配率{row["matched_track_fraction"]:.1%}，SP-core {row["sp_core_pdr"]:.1%}，SP同步细化 {row["sp_refined_pdr"]:.1%}，共享前端MRC {row["mrc_shared_frontend_pdr"]:.1%}。')
    text+=['','相同混合IQ、相同噪声/DC/白化处理的准确起点/CFO对照如下；此处按全部五档起点跨度池化，逐格结果仍完整保留。','',
           '|SNR|K|目标数|轨道门匹配率|盲SP-core|盲SP细化|已知起点SP|已知起点MRC|',
           '|---|---|---|---|---|---|---|---|']
    for snr in (man['s0'],man['s_good']):
        for k in (2,4,6):
            rr=[r for r in bt if float(r['snr'])==snr and int(r['k'])==k];n=sum(int(r['targets']) for r in rr)
            values=[sum(float(r[field])*int(r['targets']) for r in rr)/n for field in ('matched_track_fraction','sp_core_pdr','sp_refined_pdr','known_acquisition_sp_pdr','known_acquisition_mrc_pdr')]
            text.append('|'+ '|'.join([str(snr),str(k),str(n),*[f'{v:.1%}' for v in values]])+'|')
    text+=['','完整碰撞条件见tables/blind_frontend_diagnostic.csv，每格只有4场景，属于定位问题的小规模诊断。轨道率按离线时间/CFO门作一对一匹配，是门限相关诊断；交付独立按全候选中唯一CRC有效且字节相同的载荷评分，不依赖该匹配，也不把未匹配包从分母删除。','',
           '## 候选搜索与时延','',f'有限候选与8192点对数网格（加入端点和有限候选）比较的最大归一化代理目标差为{summary["finite_candidate_audit"]["max_relative_gap"]:.6g}。比较的是保护前的提议目标；保护策略可以主动选择λ=0，不能把这一行为当作搜索错误。不是PDR最优证明。',
           f'候选数量最小/中位/P90/最大分别为{summary["finite_candidate_audit"]["candidate_count_quantiles"]}（含只保留零权重的平凡配置）。逐配置验证见tables/finite_candidate_audit.csv；配置耗时见T13_serial_latency.csv的median_configuration_ms，包含信道/参数配置，不单独冒称纯搜索耗时。','',
           'T13为最终实现单线程串行、每K首轮预热后的7个burst；每burst包含全部K目标的参考/参数估计和FFT/FEC/CRC，含失败目标，共同检测和DC/白化排除。不同方法新建上下文、无跨方法FFT缓存。它是本机软件计时，不是实时接收吞吐量。','',
           '## 不应超出的结论','',
           '- 源库仍为10位置22包；0–2°只有一个物理位置对。Monte Carlo区间仅反映固定库条件，不能代表独立部署。已有开发库不是新留出验证。',
           '- Fig.13使用既有SNR10dB矩阵，Fig.12使用本轮门限附近工作点；不能混称同一SNR。固定每干扰者功率意味着总SIR随K下降。',
           '- 32次/格的观察90%不是可靠概率下界保证；无几何支持格留N/A。',
           '- 小角度、低SNR、多用户的不利结果保留；双包回退结论不能推广到所有高阶碰撞。',
           '- Fig.1/3机制附带图来源为上一轮同库重放；所选例子仅解释救回机制，统计图保留损伤和失败。',
           '- 未生成新三场景室外PDR、24节点公平性或新部署地图；这些仍需要对应真实采集。','']
    harms=collections.Counter()
    for r in profiles['main']:
        if r['metrics']['mrc']['delivered'] and not r['metrics']['sp']['delivered']:
            s=r['spec'];harms[(s['family'],s['snr_db'],s['individual_sir_db'],s['angle_low'])]+=1
    text+=['## 额外损失分布','', '|网格|SNR|SIR|角度档下界|损失包数（每格100）|','|---|---|---|---|---|']
    for values,n in sorted(harms.items()):text.append('|'+ '|'.join([*[str(v) for v in values],str(n)])+'|')
    (OUT/'RESULTS.md').write_text('\n'.join(text),encoding='utf8')
    (OUT/'README.md').write_text('''# 紧凑改稿重跑交付\n\n- `main_text_candidate_figures.pdf`：正文候选，含六包Fig.1/3、Fig.12、Fig.13、合并参考稳定性和T12/T13。\n- `all_figures_with_six_packet_mechanism.pdf`：全部新图及六包机制。\n- `overview.png`：本轮11页图/表预览。\n- `RESULTS.md`：实际结果、范围及问题说明。\n- `tables/`：逐包、逐格、参考、候选、时延和盲诊断CSV。\n- `jobs/`与`blind_jobs/`：全部新离线结果；manifest固定条件与种子。\n- `validation.json`：完整性、输入配对、源指纹及版本检查。\n\n原始164MB源IQ不重复放入压缩包；位置和SHA见validation.json及旧源库审计。代码快照和重跑入口一并保留。\n''',encoding='utf8')
    files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip']
    with zipfile.ZipFile(OUT/'all_figures_tables_and_raw_results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(OUT))
    with zipfile.ZipFile(OUT/'all_figures_tables_and_raw_results.zip') as z:assert z.testzip() is None
    print(json.dumps(dict(validation=v,successes=method_counts,rescued=rescue,harmed=harm,packaged_files=len(files)),indent=2))

if __name__=='__main__':main()
