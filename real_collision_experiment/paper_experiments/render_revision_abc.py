#!/usr/bin/env python3
"""Render auditable A/B/C figures from measured-channel simulation jobs."""
from __future__ import annotations

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ.setdefault("MPLCONFIGDIR", "/tmp/revision_abc_matplotlib")
import argparse
from collections import defaultdict
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from real_collision_experiment.paper_experiments.run_revision_abc import (
    DEFAULT_OUT, LABELS, METHODS, default_cfg, evaluate, job_key, source_bank,
    write_json, complex_pairs, angle_deg,
)

COLORS = dict(mrc="#777777", mrc_cic="#D89022", mrc_cora="#B2457D", pcube="#417FB0", maloragw="#8D6DB0", sp="#158B73")
MARKERS = dict(mrc="o", mrc_cic="^", mrc_cora="X", pcube="s", maloragw="D", sp="*")


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def save(fig, out, name):
    fig.tight_layout()
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(out / f"{name}.{suffix}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def condition(spec):
    return tuple((k, v) for k, v in spec.items() if k not in ("seed", "repeat", "focus", "methods"))


def interval(values):
    a = np.asarray(values, dtype=float)
    mean = float(np.mean(a))
    if len(a) < 2:
        return mean, mean, mean
    rng = np.random.default_rng(945)
    means = rng.choice(a, size=(4000, len(a)), replace=True).mean(axis=1)
    low, high = np.quantile(means, [.025, .975])
    return mean, float(low), float(high)


def rescore_C_truth_channels(job):
    """User-authorized offline channel-assisted identity pairing.

    The nearest eligible true channel labels each hypothesis. Aliases cannot
    fill a different identity just to maximize coverage. Receiver confidence,
    rather than minimum direction error, chooses among aliases of one label.
    CRC-based payload delivery is preserved independently of this pairing.
    """
    if job["spec"]["family"] != "C":
        return job
    result = copy.deepcopy(job)
    cfg = default_cfg()
    whitener = np.asarray([[complex(*v) for v in row] for row in job["calibration"]["whitener"]])
    truth, candidates = job["truth"], job["candidate_estimates"]
    labelled = defaultdict(list)
    for j, estimate in enumerate(candidates):
        start = estimate["start_sample"] + estimate.get("sto_samples",0.)
        cfo = estimate.get("continuous_cfo_bins",estimate["cfo_bins"])
        h = complex_pairs(estimate["channel_sp"])
        eligible = []
        for i, target in enumerate(truth):
            dt = abs(start-target["start_sample"])/cfg.samples_per_symbol
            df = abs(cfo-(start-target["start_sample"])/cfg.osr-target["cfo_bins"])
            if dt<=.125 and df<=.75:
                error = angle_deg(h,whitener@complex_pairs(target["channel"]))
                eligible.append((error,dt/.125+df/.75,i))
        if eligible:
            _,_,label = min(eligible)
            labelled[label].append(j)
    assignment = {}
    for label, indices in labelled.items():
        assignment[label] = max(indices,key=lambda j:(bool(candidates[j].get("structure_certified",False)),float(candidates[j].get("confidence",0.)),float(candidates[j].get("preamble_ratio",0.)),-j))
    for target in result["targets"]:
        i = target["target_index"]
        target["timing_cfo_only_track_established"] = target["track_established"]
        target["offline_pairing"] = "truth_channel_identity_then_receiver_confidence_alias_selection"
        j = assignment.get(i)
        target["track_established"] = j is not None
        target["matched_candidate"] = j
        target["same_identity_candidate_count"] = len(labelled.get(i,[]))
        target.pop("core_rescued_symbols", None)
        target.pop("core_harmed_symbols", None)
        estimate = candidates[j] if j is not None else None
        target["direction_error_deg"] = angle_deg(complex_pairs(estimate["channel_sp"]),whitener@complex_pairs(truth[i]["channel"])) if estimate else None
        target["lambda"] = estimate["lambda_sp"] if estimate else None
        target["lambda_cap"] = estimate["lambda_cap_sp"] if estimate else None
        target["theta_deg"] = float(np.degrees(estimate["theta_total"])) if estimate else None
    result["offline_pairing"] = "truth_channel_identity_then_receiver_confidence_alias_selection"
    return result


def summarize(jobs):
    grouped = defaultdict(list)
    for job in jobs:
        spec = dict(job["spec"])
        if spec["family"] == "B_angle":
            # Score geometric separability in SP's actual coordinate system;
            # retain physical selection bins unchanged in raw provenance.
            angle = job["effective_whitened_angle_deg"]
            edges = (0., 2., 5., 10., 20., 40., 90.000001)
            low, high = next((a,b) for a,b in zip(edges[:-1],edges[1:]) if a<=angle<b)
            spec["angle_low"], spec["angle_high"] = low, min(high,90.)
            spec["angle_coordinate"] = "SP_noise_whitened_true_channel"
        grouped[condition(spec)].append(job)
    rows, diagnostics, targets = [], [], []
    for key, scenes in grouped.items():
        spec = dict(key)
        for method in scenes[0]["targets"][0]["methods"]:
            pdrs = [np.mean([t["methods"][method]["delivered"] for t in s["targets"]]) for s in scenes]
            sers = [np.mean([t["methods"][method]["ser"] for t in s["targets"]]) for s in scenes] if spec["family"]!="C" else []
            mean, low, high = interval(pdrs)
            rows.append({**spec, "method": method, "method_label": LABELS[method], "scenes": len(scenes), "packets": sum(len(s["targets"]) for s in scenes), "pdr": mean, "pdr_mc_low": low, "pdr_mc_high": high, "ser": float(np.mean(sers)) if sers else None, "decoder_work_s_mean": float(np.mean([s["decoder_work_s"][method] for s in scenes]))})
        all_targets = [t for s in scenes for t in s["targets"]]
        tracked = [t for t in all_targets if t["track_established"]]
        errors = [t["direction_error_deg"] for t in tracked]
        rescue = [int(not t["methods"]["mrc"]["delivered"] and t["methods"]["sp"]["delivered"]) for t in all_targets]
        harm = [int(t["methods"]["mrc"]["delivered"] and not t["methods"]["sp"]["delivered"]) for t in all_targets]
        diag = {**spec, "scenes": len(scenes), "packets": len(all_targets), "track_rate": len(tracked) / len(all_targets), "direction_error_median_deg": float(np.median(errors)) if errors else None, "direction_error_p90_deg": float(np.quantile(errors, .9)) if errors else None, "direction_error_sample_count": len(errors), "lambda_median": float(np.median([t["lambda"] for t in tracked])) if tracked else None, "lambda_zero_fraction": float(np.mean([t["lambda"] == 0 for t in tracked])) if tracked else None, "lambda_cap_median": float(np.median([t["lambda_cap"] for t in tracked])) if tracked else None, "rescue_rate": float(np.mean(rescue)), "harm_rate": float(np.mean(harm)), "net_pdr_gain": float(np.mean(rescue) - np.mean(harm)), "effective_angle_median_deg": float(np.median([s["effective_whitened_angle_deg"] for s in scenes if s["effective_whitened_angle_deg"] is not None])) if scenes[0]["effective_whitened_angle_deg"] is not None else None}
        diag["uncertainty_proxy_coverage"] = float(np.mean([t["direction_error_deg"] <= t["theta_deg"] for t in tracked])) if tracked else None
        direct_gain = np.mean([t["methods"]["sp"]["delivered"] - int(t["methods"]["mrc"]["delivered"]) for t in all_targets])
        if not np.isclose(diag["net_pdr_gain"], direct_gain):
            raise AssertionError("paired rescue/harm identity failed")
        diagnostics.append(diag)
        for s in scenes:
            for target in s["targets"]:
                row = {**s["spec"], "job": job_key(s["spec"]), **{k: v for k, v in target.items() if k != "methods"}}
                row["physical_pair_angle_deg"] = s["physical_angle_deg"]
                row["effective_whitened_pair_angle_deg"] = s["effective_whitened_angle_deg"]
                row.pop("methods", None)
                row.pop("focus", None)
                for m, values in target["methods"].items():
                    row[f"{m}_delivered"] = values["delivered"]
                    row[f"{m}_ser"] = values["ser"] if s["spec"]["family"]!="C" else None
                targets.append(row)
    return rows, diagnostics, targets


def draw_grid(rows, out, metric):
    data = [r for r in rows if r["family"] == "B_grid"]
    if not data:
        return
    snrs = sorted({r["snr_db"] for r in data})
    sirs = sorted({r["sir_db"] for r in data})
    groups = sorted({(r["angle_low"], r["angle_high"]) for r in data})
    fig, axes = plt.subplots(len(groups), len(METHODS), figsize=(17.5, 6.0), squeeze=False)
    for i, group in enumerate(groups):
        for j, method in enumerate(METHODS):
            ax = axes[i, j]
            values = {(r["snr_db"], r["sir_db"]): r[metric] for r in data if r["method"] == method and (r["angle_low"], r["angle_high"]) == group}
            matrix = np.array([[values[(snr, sir)] for snr in snrs] for sir in sirs])
            im = ax.imshow(matrix, vmin=0, vmax=1, origin="lower", aspect="auto", cmap="viridis_r" if metric == "ser" else "viridis")
            for y in range(len(sirs)):
                for x in range(len(snrs)):
                    ax.text(x, y, f"{matrix[y,x]:.3f}", ha="center", va="center", fontsize=7, color="white" if ((matrix[y,x] > .45) == (metric == "ser")) else "black")
            ax.set_xticks(range(len(snrs)), [f"{v:g}" for v in snrs], rotation=45)
            ax.set_yticks(range(len(sirs)), [f"{v:g}" for v in sirs])
            ax.set_title(LABELS[method], fontsize=10)
            ax.set_xlabel("SNR (dB)")
            if j == 0:
                ax.set_ylabel(f"{group[0]:g}–{group[1]:g}°\nSIR (dB)")
    fig.subplots_adjust(right=.94, wspace=.3, hspace=.6)
    cax = fig.add_axes([.955, .16, .012, .68])
    fig.colorbar(im, cax=cax, label=metric.upper())
    # Manual colorbar axes are excluded from tight_layout.
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(out / f"B_grid_{metric}.{suffix}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def draw_slice(rows, out, family, filename):
    data = [r for r in rows if r["family"] == family]
    if not data:
        return
    snrs = sorted({r["snr_db"] for r in data})
    fig, axes = plt.subplots(1, len(snrs), figsize=(10.8, 4), squeeze=False, sharey=True)
    for ax, snr in zip(axes[0], snrs):
        if family == "B_angle":
            ticks = sorted({(r["angle_low"], r["angle_high"]) for r in data})
            ticklabels = [f"{a:g}–{b:g}" for a,b in ticks]
            getx = lambda r: ticks.index((r["angle_low"], r["angle_high"]))
            ax.set_xticks(range(len(ticks)), ticklabels)
            ax.set_xlabel("Channel-angle bin in SP's whitened coordinates (°)")
        else:
            ticks = sorted({r["k"] for r in data})
            getx = lambda r: r["k"]
            ax.set_xticks(ticks)
            ax.set_xlabel("Colliding packets (per-packet power fixed)")
        for method in METHODS:
            selected = sorted([r for r in data if r["snr_db"] == snr and r["method"] == method], key=getx)
            x = [getx(r) for r in selected]
            y = np.array([r["pdr"] for r in selected])
            low = np.array([r["pdr_mc_low"] for r in selected])
            high = np.array([r["pdr_mc_high"] for r in selected])
            ax.errorbar(x, y, yerr=np.maximum(np.vstack([y - low, high - y]), 0), color=COLORS[method], marker=MARKERS[method], label=LABELS[method], capsize=2, linewidth=1.5, markersize=5)
        ax.set_title(f"SNR {snr:g} dB")
        ax.set_ylim(-.03, 1.03)
        ax.grid(alpha=.2)
    axes[0,0].set_ylabel("PDR (controlled synchronization)")
    axes[0,-1].legend(fontsize=8, ncol=2)
    save(fig, out, filename)


def draw_diagnostics(diagnostics, out):
    data = [r for r in diagnostics if r["family"] == "B_angle"]
    if not data:
        return
    bins = sorted({(r["angle_low"], r["angle_high"]) for r in data})
    snrs = sorted({r["snr_db"] for r in data})
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for snr, color in zip(snrs, ("#417FB0", "#158B73")):
        selected = sorted([r for r in data if r["snr_db"] == snr], key=lambda r:r["angle_low"])
        x = np.arange(len(selected))
        axes[0].plot(x, [r["lambda_median"] for r in selected], "o-", color=color, label=f"{snr:g} dB")
        axes[0].plot(x, [r["lambda_cap_median"] for r in selected], "--", color=color, alpha=.6, label=f"cap, {snr:g} dB")
        axes[1].plot(x, [r["lambda_zero_fraction"] for r in selected], "o-", color=color, label=f"{snr:g} dB")
        axes[2].plot(x, [r["rescue_rate"] for r in selected], "o-", color=color, label=f"rescue, {snr:g} dB")
        axes[2].plot(x, [r["harm_rate"] for r in selected], "x--", color=color, label=f"harm, {snr:g} dB")
    for ax, label in zip(axes, ("Median selected λ", "Fraction with λ = 0", "Paired packet fraction")):
        ax.set_ylabel(label)
        ax.set_xlabel("Channel-angle bin in SP's whitened coordinates (°)")
        ax.set_xticks(range(len(bins)), [f"{a:g}–{b:g}" for a,b in bins])
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    axes[1].set_ylim(-.03,1.03)
    axes[2].set_ylim(-.03,1.03)
    save(fig, out, "B_lambda_rescue_harm")


def draw_C(rows, diagnostics, out):
    data = [r for r in diagnostics if r["family"] == "C"]
    if not data:
        return
    ks = sorted({r["k"] for r in data})
    widths = sorted({r["w_symbols"] for r in data})
    snrs = sorted({r["snr_db"] for r in data})
    fig, axes = plt.subplots(3, len(ks), figsize=(12, 9), squeeze=False)
    for col, k in enumerate(ks):
        for snr, color in zip(snrs, ("#417FB0", "#158B73")):
            selected = sorted([r for r in data if r["k"] == k and r["snr_db"] == snr], key=lambda r:r["w_symbols"])
            x = np.arange(len(widths))
            axes[0,col].plot(x, [r["track_rate"] for r in selected], "o-", color=color, label=f"SNR {snr:g} dB")
            axes[1,col].plot(x, [r["direction_error_median_deg"] for r in selected], "o-", color=color, label=f"median, {snr:g} dB")
            axes[1,col].plot(x, [r["direction_error_p90_deg"] for r in selected], "x--", color=color, label=f"p90, {snr:g} dB")
            for method in ("mrc", "sp"):
                points = sorted([r for r in rows if r["family"] == "C" and r["k"] == k and r["snr_db"] == snr and r["method"] == method], key=lambda r:r["w_symbols"])
                axes[2,col].plot(x, [r["pdr"] for r in points], marker=MARKERS[method], linestyle="-" if method=="sp" else "--", color=color, label=f"{LABELS[method]}, {snr:g} dB")
        axes[0,col].set_title(f"K = {k}")
        for row in range(3):
            axes[row,col].set_xticks(range(len(widths)), [f"{w:g}" for w in widths])
            axes[row,col].set_xlabel("Start-time window W / Tsym")
            axes[row,col].grid(alpha=.2)
        axes[0,col].set_ylim(-.03,1.03)
        axes[2,col].set_ylim(-.03,1.03)
        axes[1,col].set_ylim(0,90)
    axes[0,0].set_ylabel("Correct tracks / transmitted frames")
    axes[1,0].set_ylabel("Direction error on matched tracks (°)")
    axes[2,0].set_ylabel("End-to-end PDR / transmitted frames")
    for ax in axes[:,-1]:
        ax.legend(fontsize=7)
    save(fig, out, "C_preamble_overlap")


def draw_A(jobs, out):
    data = [s for s in jobs if s["spec"]["family"] == "A"]
    if not data:
        return None
    seven = [(s, r) for s in data for r in s["mechanism_symbols"] if r["overlap_frames"]==7]
    rescued = [(s,r) for s,r in seven if r["rank_before"]>1 and r["rank_after"]==1]
    if not rescued:
        raise ValueError("no seven-overlap rescue window; inspect aggregate before choosing a mechanism example")
    # Pick a median rank improvement among qualifying windows, not the largest.
    rescued.sort(key=lambda x:(x[1]["rank_before"]-x[1]["rank_after"], job_key(x[0]["spec"]), x[1]["target"], x[1]["symbol"]))
    selected, symbol = rescued[len(rescued)//2]
    reproduced, (samples, spectra) = evaluate(selected["spec"], source_bank(), default_cfg(), mechanism=True,
        noise_competition=selected.get("lambda_policy") == "pair_and_noise_max_v1")
    target, q = symbol["target"], symbol["symbol"]
    expected_lambda = selected["candidate_estimates"][target]["lambda_sp"]
    if abs(reproduced["candidate_estimates"][target]["lambda_sp"] - expected_lambda) > 1e-9:
        raise ValueError("current selector differs from the frozen A example; use its recorded generation revision")
    support, orthogonal, score = [x[q] for x in spectra[target]]
    penalty = symbol["lambda_sp"] * orthogonal
    normalizer = float(max(np.max(support), np.max(penalty)))
    x = np.arange(len(support))
    true, wrong = symbol["true_bin"], symbol["mrc_bin"]
    fig, axes = plt.subplots(1,3,figsize=(14,3.9))
    axes[0].plot(x,support/normalizer,label="Support |P|²",color="#417FB0",linewidth=.9)
    axes[0].plot(x,penalty/normalizer,label="Penalty λ|Q|²",color="#D89022",linewidth=.9)
    axes[1].plot(x,score/normalizer,color="#158B73",linewidth=.9)
    axes[1].axhline(0,color="gray",linewidth=.6)
    for ax in axes[:2]:
        ax.axvline(true,color="#158B73",linestyle="--",label=f"True bin {true}")
        ax.axvline(wrong,color="#B2457D",linestyle=":",label=f"Support winner {wrong}")
        ax.set_xlabel("FFT bin")
        ax.set_ylabel("Score / common energy scale")
        ax.set_ylim(min(0., float(np.min(score))/normalizer)-.05, 1.05)
        ax.grid(alpha=.15)
        ax.legend(fontsize=7)
    axes[0].set_title("Seven overlapping generated frames")
    axes[1].set_title(f"Signed score, λ = {symbol['lambda_sp']:.2f}")
    n=len(seven)
    counts=[sum(r["rank_before"]==1 and r["rank_after"]==1 for _,r in seven),sum(r["rank_before"]>1 and r["rank_after"]==1 for _,r in seven),sum(r["rank_before"]==1 and r["rank_after"]>1 for _,r in seven),sum(r["rank_before"]>1 and r["rank_after"]>1 for _,r in seven)]
    axes[2].bar(range(4),np.array(counts)/n,color=["#AAAAAA","#158B73","#B2457D","#555555"])
    axes[2].set_xticks(range(4),["Both\ncorrect","Rescued","Harmed","Both\nwrong"])
    axes[2].set_ylabel("Fraction of seven-overlap symbol windows")
    axes[2].set_ylim(0,1)
    axes[2].set_title(f"All {n:,} qualifying windows")
    for i,c in enumerate(counts):
        axes[2].text(i,c/n+.015,f"{c/n:.1%}",ha="center",fontsize=9)
    save(fig,out,"A_seven_packet_mechanism")
    write_csv(out/"A_selected_spectrum.csv",[dict(fft_bin=int(i),support=float(support[i]),weighted_orthogonal=float(penalty[i]),signed_score=float(score[i]),common_scale=normalizer,true_bin=true,mrc_bin=wrong) for i in x])
    write_json(out/"A_selected_example.json",dict(selection_rule="median rank improvement among all seven-overlap MRC-error/SP-correct windows",spec=selected["spec"],symbol=symbol,truth=reproduced["truth"],calibration=reproduced["calibration"],evidence=reproduced["evidence"]))
    np.savez_compressed(out/"A_selected_scene.npz",samples=samples)
    return dict(scenes=len(data),seven_overlap_symbols=n,rescued=counts[1],harmed=counts[2],rescue_fraction=counts[1]/n,harm_fraction=counts[2]/n,selected=symbol)


def write_report(jobs, rows, diagnostics, mechanism, out):
    by_family=defaultdict(list)
    for job in jobs:
        by_family[job["spec"]["family"]].append(job)
    text=["# A/B/C 实验结果与使用说明", "",
          "所有图均来自实测信道/CFO驱动的显式头波形仿真。原始实测波形、源记录噪声和硬件时变效应未直接叠加；这些结果不作为新增真实同时发射证据。", "",
          "配置：SF10、BW125 kHz、750 ksample/s、CR4/5、8个前导符号、显式头、20字节载荷、PHY CRC。空间方向来自26个单包/10个位置；载荷、公共相位和噪声按固定种子生成。", "",
          "A/B固定受控起点/CFO，空间参考与λ仍从带碰撞、带噪声的前导码估计。C先运行生产接收机的匿名检测/SFD补充，MRC与SP共用这些候选；SP保留有界同步细化。PDR包含共享前端的漏检，不代表两套独立检测器的比较。评估真值只参与离线评分。", "",
          "## 数据量", "", "| 实验 | 场景数 |", "|---|---:|"]
    for family, scenes in sorted(by_family.items()):
        text.append(f"| {family} | {len(scenes)} |")
    text += ["", "16次/8次等重复指固定实测信道库上的Monte Carlo重复，不代表同等数量的独立部署。误差棒为场景重采样得到的95% Monte Carlo区间。", ""]
    if any(job.get("lambda_policy") == "pair_and_noise_max_v1" for job in jobs):
        text += ["## 本轮选择器与重放口径", "",
                 "本目录是加入噪声最大值竞争的单次包级λ实验版。去掉额外固定上限4，保留参考可靠性上限；每包只配置一次λ，不使用载荷真值或CRC选λ。噪声最大值模型采用每符号α=0.05，该模型界不等于整包PDR保证。", "",
                 "本轮重建同一批波形并重算SP，逐场景验证真值、前导信道和不确定性统计重现；其他解码器结果直接复用冻结原结果。C复用原匿名检测候选和校准，再运行新的SP及原有同步细化。检测覆盖不受本轮λ改动影响，PDR仍包含原共享检测器的漏检。此处不是一次重新采集、重新检测或重新计时的完整接收实验。", "",
                 "该版本在低SIR双包条件改善，但7包A场景从旧版79.46%退化至62.95%，不能作为全面改进的正式结论。多包混合目标bin不满足纯目标加热噪声模型，需要继续讨论。旧结果保存在revision_abc目录。", ""]
    if "pilot" in by_family:
        text += ["## 无碰撞 SNR 预试验", "", "| SNR (dB) | MRC PDR | SP PDR |", "|---:|---:|---:|"]
        for snr in sorted({r["snr_db"] for r in rows if r["family"]=="pilot"}):
            lookup={r["method"]:r["pdr"] for r in rows if r["family"]=="pilot" and r["snr_db"]==snr}
            text.append(f"| {snr:g} | {lookup['mrc']:.3f} | {lookup['sp']:.3f} |")
        text += ["", "该预试验使用已知同步，表征载荷恢复开始退化的区域；C的完整检测门限可能更高。C采用−20和0 dB两组条件。", ""]
    if "A" in by_family:
        targets=[t for s in by_family["A"] for t in s["targets"]]
        text += ["## A：7包机制与总体统计", "", "[机制组合图](A_seven_packet_mechanism.pdf)", "", "| 解码器 | PDR |", "|---|---:|"]
        for method in METHODS:
            pdr=np.mean([t["methods"][method]["delivered"] for t in targets])
            text.append(f"| {LABELS[method]} | {pdr:.3f} |")
        if mechanism:
            text += ["", f"在全部 {mechanism['seven_overlap_symbols']} 个7包重叠符号窗口中，使用同一SP空间参考比较支持排序和签名排序，救回 {mechanism['rescued']} 个（{mechanism['rescue_fraction']:.2%}），伤害 {mechanism['harmed']} 个（{mechanism['harm_fraction']:.2%}）。",
                     "这里的符号级支持排序与最终PDR表中的独立MRC前导估计器有所区别，二者分别回答λ的排序作用和完整载荷恢复表现。示例从救回窗口中按排名改善的中位数选取，总体统计保留所有窗口。", ""]
    grid=[r for r in rows if r["family"]=="B_grid" and r["snr_db"]==0 and r["sir_db"]==0]
    if grid:
        text += ["## B：鲁棒性与增益边界", "", "[SNR–SIR SER图](B_grid_ser.pdf) · [SNR–SIR PDR图](B_grid_pdr.pdf) · [小夹角PDR](B_small_angle_pdr.pdf) · [碰撞阶数PDR](B_collision_density_pdr.pdf) · [λ及救回/伤害](B_lambda_rescue_harm.pdf)", "",
                 "A/B的受控PDR要求指定目标轨道恢复对应载荷；SNR–SIR网格每个场景评估一个目标，另一个包提供干扰，其余A/B切片评估全部目标。SNR–SIR切片在同一空间组内复用源、载荷和噪声种子。以下为 SNR=SIR=0 dB 的条件结果：", "", "| 源夹角组 | 解码器 | PDR | SER |", "|---|---|---:|---:|"]
        for r in sorted(grid,key=lambda r:(r["angle_low"],METHODS.index(r["method"]))):
            text.append(f"| {r['angle_low']:g}–{r['angle_high']:g}° | {r['method_label']} | {r['pdr']:.3f} | {r['ser']:.3f} |")
        text += ["", "小夹角曲线按SP实际白化坐标中的重建真信道夹角重新分组，原始物理夹角和选样分组仍保存在逐场景与逐包CSV中。0–2°物理源包对只有1组，不将其重复仿真当作多个独立位置。", "",
                 "碰撞阶数扫描保持每个包平均接收功率不变，因此总干扰随K上升；它展示这套异步负载配置的性能边界，不单独归因于碰撞数量。实际起点与CFO全部保留在场景日志中。", ""]
        negative=[r for r in diagnostics if r["family"].startswith("B_") and r["net_pdr_gain"] < -1e-12]
        text += [f"在 {sum(r['family'].startswith('B_') for r in diagnostics)} 个B统计条件中，SP相对MRC有 {len(negative)} 个条件的PDR增量为负。以下保留负增益最大的条件：", "",
                 "| 切片 | K | SNR | SIR | 夹角组 | SP−MRC PDR | 救回率 | 伤害率 |", "|---|---:|---:|---:|---|---:|---:|---:|"]
        for r in sorted(negative,key=lambda r:r["net_pdr_gain"])[:12]:
            angle=f"{r['angle_low']:g}–{r['angle_high']:g}°" if "angle_low" in r else "—"
            text.append(f"| {r['family']} | {r['k']} | {r['snr_db']:g} | {r.get('sir_db',0):g} | {angle} | {r['net_pdr_gain']:+.3f} | {r['rescue_rate']:.3f} | {r['harm_rate']:.3f} |")
        text += ["", "救回率减伤害率已逐条件核对等于PDR差。λ=0候选和保护上限均有记录；`uncertainty_proxy_coverage`统计实际参考误差是否落入前导变化代理范围。这些机制不构成实际性能无条件不劣于独立MRC的保证。", ""]
    c=[r for r in diagnostics if r["family"]=="C"]
    if c:
        text += ["## C：前导码重叠与完整接收链路", "", "[前导码重叠组合图](C_preamble_overlap.pdf)", "",
                 "PDR以全部生成发送帧为分母，按任一检测候选恢复的唯一精确CRC有效载荷计成功。正确建轨按解码前种子的时频门限及真值信道辅助身份配对评分，方向误差仅在匹配成功的轨道上计算，并给出覆盖包数。同步细化可继续修正种子，因此后端交付率与初始正确种子率不要求逐场景相等。", "",
                 "| K | W/Tsym | SNR | 正确轨道率 | 方向误差中位数° | 方向误差样本/发送包 | MRC PDR | SP PDR |", "|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for r in sorted(c,key=lambda r:(r["k"],r["snr_db"],r["w_symbols"])):
            rates={x["method"]:x["pdr"] for x in rows if x["family"]=="C" and x["k"]==r["k"] and x["snr_db"]==r["snr_db"] and x["w_symbols"]==r["w_symbols"]}
            err=f"{r['direction_error_median_deg']:.2f}" if r["direction_error_median_deg"] is not None else "—"
            text.append(f"| {r['k']} | {r['w_symbols']:g} | {r['snr_db']:g} | {r['track_rate']:.3f} | {err} | {r['direction_error_sample_count']}/{r['packets']} | {rates['mrc']:.3f} | {rates['sp']:.3f} |")
        text += ["", "同起点时在既定时频门限内，用已知生成信道方向辅助离线身份配对；同身份的多个候选由接收机结构置信度选择代表。该规则经用户确认，只用于建轨与参考评分，不进入接收机。方向误差按此真值辅助配对计算，可能受配对规则影响；不将同一身份的多个候选强配给其他包。C不报告重新配对后的SER，PDR仍按唯一精确CRC载荷计数。", ""]
    text += ["## 使用边界与复现", "",
             "- 当前验证的是固定实测空间方向、常数CFO和AWGN下的算法行为；原始射频失真、采样钟漂移、包内信道变化及远距传播效果需由真实采集支撑。",
             "- 本轮新增图中的单天线类对照均为MRC+CIC、MRC+CoRa。旧论文的实采聚合结果仍须用新基线重新处理，不能仅改图例。",
             "- 并行工作进程中的耗时字段仅用于执行诊断，不用来宣称串行解码速度优势；正式耗时比较须在统一串行计时条件下重测。",
             "- `all_metrics.csv`、`diagnostics.csv`、`per_target.csv`和上一层`jobs/`保存条件、分母、失败、估计参考、λ、实际起点、CFO及源包标识。",
             "- `figure_manifest.json`记录代码指纹、完整性和统计口径；`A_selected_scene.npz`及其JSON/CSV可复查示例。", ""]
    (out/"RESULTS.md").write_text("\n".join(text)+"\n")

    inserts=["# Draft evaluation text and captions", "",
             "## Controlled waveform experiment setup", "",
             "We generate CRC-valid, explicit-header LoRa waveforms using the complex two-channel spatial directions and preamble CFO estimates obtained from 26 measured packets at ten positions. Each generated frame uses SF10, BW125 kHz, CR4/5, eight preamble chirps, and a 20-byte payload at 750 ksample/s. Packet identities, common phases, offsets, and AWGN realizations are reproducible from saved seeds. The measured spatial directions and CFOs are held fixed within each frame. These experiments are measured-channel-driven waveform simulations; they do not superimpose original measured packet IQ or reproduce all RF impairments.", "",
             "The robustness slices supply controlled timing and CFO to all methods, while their spatial references and SP weights are estimated from the noisy collided preambles. MRC+CIC and MRC+CoRa apply packet-specific fixed MRC before the original scalar decoder cores. CIC RSSI and CoRa peak-magnitude references are computed in the combined domain. All methods receive the same scene and noise realization. Collision-order experiments hold per-packet received power fixed, so total interference increases with collision order.", ""]
    if mechanism and "A" in by_family:
        targets=[t for s in by_family["A"] for t in s["targets"]]
        mr=np.mean([t['methods']['mrc']['delivered'] for t in targets])
        sp=np.mean([t['methods']['sp']['delivered'] for t in targets])
        co=np.mean([t['methods']['mrc_cora']['delivered'] for t in targets])
        inserts += ["## A: mechanism evidence", "",
                    f"Across {len(by_family['A'])} controlled seven-frame collisions ({len(targets)} transmitted frames), SP-Decoder recovers {sp:.1%} of packets, compared with {mr:.1%} for MRC and {co:.1%} for MRC+CoRa. Among {mechanism['seven_overlap_symbols']:,} symbol windows containing seven active frames, signed ranking corrects {mechanism['rescued']} support-only errors and introduces {mechanism['harmed']} errors under the same spatial reference. This isolates the contribution of counter-evidence separately from the independently estimated MRC baseline.", "",
                    "**Figure A caption.** Signed spatial ranking in a controlled seven-frame collision generated from measured spatial directions and CFOs. Support, weighted orthogonal penalty, and signed score use the same linear energy scale. A competing bin loses more score than the target, improving the target's relative margin. The example is selected at the median rank improvement among rescued seven-overlap windows; the transition panel includes all qualifying windows and retains harmed cases.", ""]
    inserts += ["## B: robustness slices", "",
                "The SNR–SIR grid compares MRC, MRC+CIC, MRC+CoRa, PCube, MaLoRaGW, and SP on identical mixtures, including a near-collinear source group and a wider-angle source group. Additional slices examine channel angles below 10 degrees and collision orders 2, 4, 6, 8, and 10. Small-angle analysis uses the true reconstructed directions in SP's estimated noise-whitened coordinate system. Physical source angles remain in the audit data. Packet rescue and harm fractions are paired against MRC; their difference equals the PDR difference. Selected weights, protection caps, zero-weight frequency, and empirical coverage of the preamble uncertainty proxy are reported without assuming that the presence of a zero-weight candidate guarantees non-degradation relative to an independently estimated MRC receiver.", "",
                "**Figure B captions.** (1) Conditional SER/PDR over the SNR–SIR grid, using shared controlled timing/CFO and preamble-estimated references. (2) Conditional PDR versus measured-channel angle and collision order; intervals are empirical scene-bootstrap intervals over Monte Carlo repetitions of a fixed measured channel pool. (3) Selected weights, zero-weight frequency, and paired packet rescue/harm rates. Source repetitions are not counted as independent deployments.", "",
                "## C: preamble overlap", "",
                "We generate K=2, 4, or 6 frames whose start times are uniformly drawn within a window of width W, with W/Tsym in {0, 0.1, 0.25, 0.5, 1, 2}. Each condition has eight Monte Carlo scenes at SNRs -20 and 0 dB. Sources occupy distinct measured positions with pairwise physical channel angles of at least 10 degrees, keeping a separable spatial condition for this timing-overlap experiment. The complete anonymous preamble/SFD acquisition, reference estimation, and payload decoder run on the mixture; SP additionally retains its production bounded synchronization refinement. Both payload decoders receive the same anonymously detected candidates, and PDR includes misses of this shared front end. No source timing, channel, CFO, or payload truth is supplied to that receiver path. End-to-end PDR credits unique exact CRC-valid transmitted payloads over all transmitted frames, including detection and establishment failures.", "",
                "For offline establishment and reference scoring, timing/CFO gates account for the CSS coupling between a shifted window and apparent CFO. The known reconstructed channel directions disambiguate candidate identities; receiver structural confidence selects among aliases of one identity. Direction-error statistics are conditional on this truth-assisted pairing and report their coverage. This pairing does not change decoding or payload-delivery counts.", "",
                "**Figure C caption.** Complete reception under overlapping preambles. Rows show initial correctly paired track coverage, projective channel-direction error on paired tracks, and end-to-end PDR. Each point contains 16, 32, or 48 transmitted frames for K=2, 4, or 6. Reference-error coverage is given with the track and per-condition statistics. The two SNRs span a reliable controlled-reference condition and the onset of isolated payload-decoder degradation; acquisition can impose a higher effective threshold.", ""]
    if any(job.get("lambda_policy") == "pair_and_noise_max_v1" for job in jobs):
        inserts = ["# Experimental selector — not a validated replacement", "",
                   "This version adds a noise-maximum competitor to preamble-only, once-per-packet weight selection. Under white Gaussian noise, the empty-bin score has tail exp(-t/n)/(1+lambda) for nonnegative t; a union bound over M-1 bins with alpha=0.05 defines a noise threshold. The standardized target-to-threshold margin enters the max-min objective alongside packet-pair margins. The reference-reliability cap remains; the additional cap of four is removed. Neither CRC nor payload truth selects lambda.", "",
                   "Only SP is recomputed on regenerated identical waveforms; unchanged baseline outputs, calibration, and anonymous detector hypotheses are reused from the frozen experiment. Production SP synchronization refinement is rerun for C. Detector coverage is inherited, and the timing data are not a fresh end-to-end runtime measurement. The first version regresses seven-packet reception and must not be described as a uniform improvement.", ""] + inserts
    (out/"PAPER_INSERTS.md").write_text("\n".join(inserts)+"\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=DEFAULT_OUT)
    parser.add_argument("--allow-partial",action="store_true")
    args=parser.parse_args()
    manifests=[json.loads(p.read_text()) for p in sorted(args.input.glob("manifest_*.json"))]
    if not manifests:
        raise ValueError("no experiment manifests")
    revisions={m["revision_hash"] for m in manifests}
    if len(revisions)!=1:
        raise ValueError("manifests use different code revisions; rerun stale stages")
    revision=next(iter(revisions))
    expected={job_key(spec) for m in manifests for spec in m["jobs"]}
    jobs=[]
    for key in sorted(expected):
        path=args.input/"jobs"/f"{key}.json"
        if path.exists():
            job=json.loads(path.read_text())
            if job.get("revision_hash")==revision:
                jobs.append(rescore_C_truth_channels(job))
    if len(jobs)!=len(expected) and not args.allow_partial:
        raise ValueError(f"only {len(jobs)}/{len(expected)} current-revision jobs available")
    out=args.input/"figures"
    out.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size":9,"pdf.fonttype":42,"svg.fonttype":"none"})
    rows,diagnostics,targets=summarize(jobs)
    write_csv(out/"all_metrics.csv",rows)
    write_csv(out/"diagnostics.csv",diagnostics)
    write_csv(out/"per_target.csv",targets)
    draw_grid(rows,out,"ser")
    draw_grid(rows,out,"pdr")
    draw_slice(rows,out,"B_angle","B_small_angle_pdr")
    draw_slice(rows,out,"B_density","B_collision_density_pdr")
    draw_diagnostics(diagnostics,out)
    draw_C(rows,diagnostics,out)
    mechanism=draw_A(jobs,out)
    write_report(jobs, rows, diagnostics, mechanism, out)
    counts={family:sum(s["spec"]["family"]==family for s in jobs) for family in sorted({s["spec"]["family"] for s in jobs})}
    dependency_paths=("compare/mrc_input.py","compare/real_packet_decoders.py","compare/native_frontends.py","compare/CoRa/cora_detector.py","compare/CoRa/tnb_bec.py","lora_mrc_sp_core.py","sp_detection_frontend.py","usrp_b210_lora_tx.py","evaluate_sp_dechirp_real_pos.py","real_collision_experiment/paper_experiments/build_fig11_trace_runtime.py","real_collision_experiment/paper_experiments/simulate_sp_mechanisms.py","real_collision_experiment/node01_sp_receiver/real_sp_frontend.py","real_collision_experiment/node01_sp_receiver/sp_node01_receiver.py","real_collision_experiment/node01_sp_receiver/lora_phy_decode.py")
    dependency_paths += ("sp_noise_competition.py",)
    write_json(out/"figure_manifest.json",dict(revision_hash=revision,renderer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),dependency_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in dependency_paths},C_frontend=dict(max_candidates=24,candidates_per_window=16,threshold=3.,cfo_min=-40.,cfo_max=8.,scan_phase_count=8,sp_sync_max_trials=32),C_offline_pairing="truth_channel_identity_then_receiver_confidence_alias_selection",complete=len(jobs)==len(expected),jobs=len(jobs),expected_jobs=len(expected),families=counts,mechanism=mechanism,confidence_interval="95% scene-bootstrap Monte Carlo interval on a fixed measured channel pool; not independent deployment uncertainty",figures=sorted(p.name for p in out.glob("*.pdf"))))
    snapshot = args.input / "generation_code_snapshot.json"
    if snapshot.exists():
        generated = json.loads(snapshot.read_text())
        if generated["revision_hash"] != revision:
            raise ValueError("generation code snapshot does not match experiment revision")
        manifest_path = out / "figure_manifest.json"
        figure_manifest = json.loads(manifest_path.read_text())
        figure_manifest.update(generation_dependency_sha256=generated["dependency_sha256"],
            generation_code_snapshot="../code_snapshot",
            lambda_policy=generated["policy"],
            validation_status="experimental; low-SIR gains and high-concurrency regression",
            replay_scope="SP re-evaluated; frozen baselines, calibration and anonymous candidates reused")
        write_json(manifest_path, figure_manifest)
    print(json.dumps(dict(jobs=len(jobs),expected=len(expected),families=counts,mechanism=mechanism),indent=2))


if __name__=="__main__":
    main()
