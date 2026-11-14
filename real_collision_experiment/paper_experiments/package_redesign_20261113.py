#!/usr/bin/env python3
from pathlib import Path
import sys,json,csv,hashlib,shutil,zipfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from real_collision_experiment.paper_experiments import audit_redesign_20261113 as a
OUT=a.OUT;c=a.c;b=a.b

def main():
    a.initialize();m=json.loads((OUT/'manifest_extreme.json').read_text());summary=json.loads((OUT/'summary.json').read_text());timing=json.loads((OUT/'timing_matched.json').read_text())
    rows=[];pairs={}
    for spec in m['specs']:
        r=json.loads((OUT/'jobs'/(c.key(spec)+'.json')).read_text());assert r['spec']==spec
        assert len(spec['sources'])==2 and all(u in b.CHANNELS for u in spec['sources'])
        assert 10<=r['physical_angle']<60
        assert r['noise_budget']['min_residual_eigenvalue']>=-1e-8*r['noise_budget']['variance']
        key=spec['repeat'];inv=[spec[k] for k in ('sources','seed','phases','relative_offsets','width_ratio')]
        if key in pairs:assert pairs[key]==inv
        pairs[key]=inv
        if r['lambda_sp']==0:assert r['metrics']['sp']==r['metrics']['mrc']
        rows.append(r)
    assert len(rows)==800 and len(pairs)==100
    nested_counts={}
    for filename in ('manifest_nested.json','manifest_nested_moderate.json'):
        mm=json.loads((OUT/filename).read_text());invariants={}
        for spec in mm['specs']:
            r=json.loads((OUT/'jobs'/(c.key(spec)+'.json')).read_text());assert r['spec']==spec
            assert all(u in b.CHANNELS for u in spec['sources'])
            nearest=min(b.n.a.angle_deg(b.CHANNELS[spec['sources'][0]],b.CHANNELS[v]) for v in spec['sources'][1:])
            assert abs(nearest-spec['fixed_minimum_angle'])<1e-9
            assert r['noise_budget']['min_residual_eigenvalue']>=-1e-8*r['noise_budget']['variance']
            inv=[spec[field][0] for field in ('sources','relative_offsets','phases','powers')]+[nearest]
            if spec['master_job'] in invariants:assert inv==invariants[spec['master_job']]
            invariants[spec['master_job']]=inv
        assert len(mm['specs'])==128 and len(invariants)==32
        nested_counts[filename]=128
    assert summary['old_main_algorithm_hashes_match'] and timing['verified_packet_method_results']==480
    for name in summary['figures']:
        for ext in ('png','pdf','svg'):assert (OUT/'figures'/f'{name}.{ext}').stat().st_size>1000
    for name in ('recommended_main_figures.pdf','main_with_mechanism.pdf','redesigned_figures.pdf','all_with_mechanism.pdf'):
        s=subprocess.check_output(['pdfinfo',str(OUT/name)],text=True);assert 'Pages:' in s
    source=b.n.OUT/'aligned_source_iq.npz';sha=hashlib.sha256(source.read_bytes()).hexdigest();assert sha==b.CAL['source_iq_sha256']
    c.write(OUT/'validation.json',dict(complete=True,new_extreme_trials=800,new_nested_trials=nested_counts,paired_extreme_master_draws=100,source_iq_sha256=sha,
        source_pool='22 intact traces / 10 positions',no_receiver_algorithm_change=True,
        all_target_reference_estimated_from_mixture=True,known_timing_cfo_control=True,
        matched_timing_packet_method_parity=480,old_T13_superseded=True,raw_performance_results_unchanged=True))
    (OUT/'code_snapshot').mkdir(exist_ok=True)
    for name in ('audit_redesign_20261113.py','redraw_operating_regions_20261113.py','package_redesign_20261113.py'):
        shutil.copy2(Path(__file__).with_name(name),OUT/'code_snapshot'/name)
    for name in ('manifest_main.json','manifest_pilot.json'):
        shutil.copy2(ROOT/'real_usrp_outputs/compact_revision_20261106'/name,OUT/'data'/('previous_'+name))
    shutil.copy2(b.OUT/'cell_summary.csv',OUT/'data/boundary_source_cells.csv')
    oldharm=11;newharm=sum(r['metrics']['mrc']['delivered'] and not r['metrics']['sp']['delivered'] for r in rows)
    rankratios=[];totals=[]
    import numpy as np
    for k in b.KS:
        rr=[r for r in timing['records'] if r['k']==k and not r['warmup']]
        ratio=float(np.median([r['methods']['sp']['micro_ms']/r['methods']['mrc']['micro_ms'] for r in rr]));rankratios.append(ratio)
        totals.append((k,float(np.median([r['methods']['mrc']['total_ms'] for r in rr])),float(np.median([r['methods']['sp']['total_ms'] for r in rr])),ratio))
    text=['# 为什么旧图与新图观感不同，以及本次改图结果','',
          '## 先看哪几张','',
          '- `recommended_main_figures.pdf`：正文建议的3页替换图，仅P3适用范围、P5参考一致性、T12救回与损伤；没有热力图。',
          '- `main_with_mechanism.pdf`：加入已完成六包机制后共5页，比上一版正文候选少1页。',
          '- `P4_advantage_failure_scenarios`：六场景的分行点区间图，明确比较各方法在不同场景的结果；适合作为P3的替代形式或放附录，不建议两张都占正文。',
          '- `T13_audited_overhead`：替换旧时延表的排名成本与分阶段柱状图，建议附录。',
          '- `redesigned_figures.pdf`：全部6页，包括完整两档SNR极端扫描，不再堆热力图。','',
          '## 条件确实变过，算法并未在11月6日这轮被改差','',
          '上一版正文的SNR折线固定SIR=0dB，本意是检验安全回退；但它无法展示强干扰抑制优势。SNR点又集中在−23至−11dB的灵敏度附近，SNR切片角度收窄为20–40°。旧热力图还覆盖SIR=−20dB、SNR=0dB、10–60°等条件，正文折线没有保留这些切片。这是条件选择与展示侧重变化，不是折线本身使PDR降低。',
          '当前生产算法与11月6日冻结哈希逐项一致。另一方面，最早的revision_heatmaps_A3_C1目录使用重新生成的静态信道波形、20B显式头和旧策略；后来的guard-v2目录使用原始IQ、32B隐式头和当前保护策略。这两版不能用同名热图直接等同。',
          '本次补跑800次：SNR={−10,0}dB，SIR={−20,−10,0,+10}dB，角度10–60°，0.2符号起点差，每格100次。全部八个条件共用配对源/初相/种子，先检查最强干扰处的源噪声可行性，没有按解码结果筛源。原始IQ源库与算法保持一致。',
          '在SNR0/SIR−10dB处，旧原始IQ热图SP为87.5%（16次），本次为88%（100次），MRC两次均为0；优势仍存在。在本次同一条件下PCube69%、MaLoRaGW79%。SIR−20dB处SP66%、MaLoRaGW68%，完整保留，不声称SP所有条件第一。不同批次抽样组合与重复数不同，不能将各格差值全归因于单一因素。','',
          '## 图3/4：用少量图说明适用范围','',
          'P3只保留三张有明确条件的压力曲线：(a)固定SNR0、两包与角度10–60°，扫描全部四档SIR；(b,c)固定SNR10和每干扰者SIR−5，分别在最小角度20–40°及40–90°的两类固定源组上扫描K=2/4/6/8。每个K扫描均固定目标和最近干扰者、保留源包/初相/实际起点，只逐步增加其他干扰者，共两组各128次。这修正了原曲线不同K使用不同目标组合的问题。噪声预算按各混合补偿，相同种子不意味着跨K噪声样本逐点相同。K10的大角度组合无实测支持，不外插。',
          '审查发现：在大角度嵌套扫描中，PCube在各受测K的PDR均可高于SP；保留该曲线，并补中等角度的同类嵌套扫描。后者SP各点估计较高，但高K绝对PDR仍然很低。不能只保留有利角度，不能把两类不同源组的差异称为纯角度因果效应。',
          'P4让四种方法各占一行，避免相同PDR的曲线互相覆盖。六个面板依次是噪声受限、近共线失效、双包中等角度（MaLoRaGW的优势场景）、强干扰恢复（SP优势）、中等角度六包恢复和大角度高阶碰撞（PCube可领先）。这些是基于已观测数据设计的事后机制示例，不是预注册的部署频率或通用阈值；完整扫描随附。',
          '图中给出实际PDR和条件区间，而不只画增益。区间仅描述固定源库条件下的重复，不能代表独立部署；0–2°仍只有一个位置对。','',
          '## 图5：直接回答参考在何时可复用','',
          '原CDF横轴放到90°，主要概率质量挤在左侧，多条SIR曲线又几乎重合。本次(a)用全部11档单包SNR的中位数/P90直接显示噪声对一致性的影响；(b)在可靠SNR−8dB下对比单包与强干扰碰撞的包内中位数/P90轨迹，显示波动范围和位置依赖，而非要求稳定的曲线人为分开。',
          '观测偏差使用离线已知真实bin中的混合双通道向量相对混合前导参考的非负射影角。它不是干净信道估计误差；该图目前限于单包/双包条件，不能证明多用户稳健参考分支在所有K下均准确，也不能证明前导重叠时参考总能建立。完整CDF/其他SIR分布仍在上一轮数据中。','',
          '## T12：PDR折线 + 救回柱，损伤只在非零条件显示','',
          f'旧表前三个子集的harm确实为零，但全4400次共有{oldharm}个损失包（0.25%）；本次额外800次中损失包数为{newharm}。不能把零损失子集写成总体保证。',
          '新图(a)是近灵敏度扫描，SP/MRC用折线，救回用柱，harm全零所以不画损伤柱。(b)是SIR扫描，仍用折线+柱，在SIR0处保留3%救回和−3%损伤；全图共用图例，避免遮挡点和柱。两者抵消，因而SP/MRC的绝对PDR相同；PDR相等不等于没有包被伤害。所有比例分母都是该格全部100个目标。身份恒等式ΔPDR=救回率−损伤率逐格核对。','',
          '## T13：旧表撤回，计时口径已修正','',
          '旧计时虽都叫参数估计+解码，代码路径却不对称：MRC每个符号经_physical_mixed重复生成dechirp，SP每包生成一次；MRC还计算Top-2裕量、候选分组和诊断封装，SP路径主要返回Top-1符号。这使旧表混入了无关实现开销，不能据此推断SP固有计算量小于MRC。旧表已标为过时。',
          '本次两者使用同一个整数窗口/CFO/dechirp/FFT缓存实现、同一个打分/argmax函数、同一个PHY解码器。480个方法–目标结果逐包与原始冻结记录核对，SP符号也核对原接收机。每K首轮预热，后7个burst计时，顺序交替，不共享另一方法已算好的FFT。',
          f'单独固定FFT和投影系数时，SP有符号排名耗时约为MRC的{min(rankratios):.2f}–{max(rankratios):.2f}倍，符合额外正交投影和减法带来的成本。全流程还包含不同的参考估计器：MRC是CFO补偿前导物理估计，SP多用户分支是稳健前导估计，因此总时间不能强制要求每个K都严格排序。',
          '新图左侧显示同FFT条件下的排名微基准（阴影P10–P90，不是置信区间）；右侧为参考配置、同构FFT、排名、FEC/CRC四阶段中位数的堆叠柱。阶段中位数之和不是总时间中位数；原始逐burst总时间另存。两者均不代表实际空口吞吐量或整个盲前端实时能力。','',
          '|K|MRC总时间中位数(ms)|SP总时间中位数(ms)|SP/MRC排名时间比|','|---|---|---|---|']
    for k,mr,sp,ratio in totals:text.append(f'|{k}|{mr:.2f}|{sp:.2f}|{ratio:.2f}|')
    text+=['','## 本轮没有改动的实验前提','',
           '正式条件解码仍向所有方法提供相同起点与单包标定CFO，参考和λ从混合前导估计；真载荷仅评分。本次是已有实测源的数字叠加，不是新空口采集。没有调整SP/基线算法来制造优势，原始负结果和新扫描各格均保留。','']
    (OUT/'RESULTS_AND_DESIGN.md').write_text('\n'.join(text),encoding='utf8')
    (OUT/'README.md').write_text('# 2026-11-13 紧凑适用区间改图\n\n先看 `main_with_mechanism.pdf`（正文精简候选5页）和`RESULTS_AND_DESIGN.md`。`P4_advantage_failure_scenarios`可替代P3或放附录，T13建议附录，不必所有新图都加入正文。`redesigned_figures.pdf`共6页，`all_with_mechanism.pdf`共8页；所有图没有热力图。\n\n800次新增强干扰扫描、256次固定目标嵌套扫描、480个计时方法–目标一致性核对均通过。数据与脚本附带，原始源IQ仍在既有规范源库，以指纹引用。\n',encoding='utf8')
    # Paired uncertainty review, including inconvenient comparisons.
    from scipy.stats import beta
    def difference(group,method):
        n=len(group);gain=sum(r['metrics']['sp']['delivered'] and not r['metrics'][method]['delivered'] for r in group);loss=sum(not r['metrics']['sp']['delivered'] and r['metrics'][method]['delivered'] for r in group)
        low_gain=0 if gain==0 else beta.ppf(.0125,gain,n-gain+1);high_gain=1 if gain==n else beta.ppf(.9875,gain+1,n-gain)
        low_loss=0 if loss==0 else beta.ppf(.0125,loss,n-loss+1);high_loss=1 if loss==n else beta.ppf(.9875,loss+1,n-loss)
        return dict(baseline=method,n=n,rescued=gain,harmed=loss,delta_pp=100*(gain-loss)/n,ci_low_pp=100*(low_gain-high_loss),ci_high_pp=100*(high_gain-low_loss))
    selected=[r for r in rows if r['spec']['snr_db']==0 and r['spec']['individual_sir_db']==-10]
    paired=[difference(selected,method) for method in ('mrc','pcube','maloragw')]
    with (OUT/'data/paired_advantage_review.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
    review=['# 出图后的审慎复核','',
       '结论：P3对SP的强干扰恢复和条件适用范围有意义；P4是解释性的备选图，不建议与P3重复放正文。P5只支持观测一致性，不能升级为盲前端参考准确性证明。T12避免了“PDR相同就没有伤害”的误读；T13撤回旧不对称计时，重新展示净增排名成本。','',
       '## 没通过首版检查、已修正的地方','',
       '1. 原正文切片集中在SIR0、低SNR，不能承担展示强干扰优势的任务。补全两档SNR×四档SIR，共800次，而不只跑效果最好的一格。',
       '2. 原不同K曲线混有源组合变化。补两种角度条件各32个固定主场景的嵌套K扫描；对SP不利的大角度扫描照样保留。',
       '3. 原图按十余英寸画布出图，缩入双栏论文后字体偏小。正文新图按7.2英寸宽、8pt基本字体导出；场景点图改2×3分面，避免五个狭长面板。',
       '4. PDR坐标统一0–100%；时间微基准从0开始；没有用截断轴夸大差距。阴影分位带、PDR条件区间、配对差值区间各自标清含义。',
       '5. 参考CDF大段空白、SIR曲线重叠，不能一眼回答问题。改用噪声方向分位数与包内位置轨迹，保留当前源库范围的限制。',
       '6. T12损伤非全零：只在真正非零的SIR条件画负柱，零损伤面板不画损伤柱；共享图例放在图外以免遮挡。完整4400次仍报告11次损伤。','',
       '## 强干扰优势的证据强度','',
       'SNR0/SIR−10/角度10–60°、100个目标，同观测配对差值如下。区间用救回/损伤概率的97.5%Clopper–Pearson区间经Bonferroni组合为保守95%差值区间；只反映固定源库条件，未对全部事后比较作全局多重性校正。','',
       '|对照|SP增益(pp)|保守区间(pp)|救回/损伤|','|---|---|---|---|']
    for r in paired:review.append(f'|{r["baseline"]}|{r["delta_pp"]:.1f}|[{r["ci_low_pp"]:.1f}, {r["ci_high_pp"]:.1f}]|{r["rescued"]}/{r["harmed"]}|')
    review+=['','相对MRC与PCube的增益在该条件下有支持；相对MaLoRaGW的区间跨零，只能写观测点估计较高。高K低PDR不能写成可靠隔离；中等角度与大角度两组源不同，不声称纯角度因果阈值。','',
             '图的正文取舍：优先P3适用范围、P5参考一致性、T12配对恢复；P4可替代P3或用于讨论/附录，T13放附录。可读性检查和实验重复不能替代新部署验证，当前结论依旧限于实测源重放。','']
    (OUT/'SELF_REVIEW.md').write_text('\n'.join(review),encoding='utf8')
    oldroot=ROOT/'real_usrp_outputs/compact_revision_20261106'
    (oldroot/'TIMING_SUPERSEDED_20261113.md').write_text('旧T13参数+解码总时间混入不对称实现开销，撤回其“SP比MRC计算更少”的解释。请使用 ../figure_redesign_20261113/figures/T13_audited_overhead.pdf 及 RESULTS_AND_DESIGN.md；原记录保留供审计。\n',encoding='utf8')
    oldreadme=oldroot/'README.md';previous=oldreadme.read_text()
    if 'TIMING_SUPERSEDED_20261113.md' not in previous:
        oldreadme.write_text('> 2026-11-13：本目录旧T13的算法快慢解释已撤回，计时已重做；见 [计时更正](TIMING_SUPERSEDED_20261113.md)。新版图在 `../figure_redesign_20261113/`。\n\n'+previous,encoding='utf8')
    files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip']
    with zipfile.ZipFile(OUT/'figures_data_audit.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(OUT))
    with zipfile.ZipFile(OUT/'figures_data_audit.zip') as z:assert z.testzip() is None
    print(json.dumps(dict(complete=True,new_extreme_trials=800,new_nested_trials=256,parity=480,rank_ratio_range=[min(rankratios),max(rankratios)],packaged_files=len(files)),indent=2))

if __name__=='__main__':main()
