"""Deney sonuçlarını analiz eder: grafikler + istatistiksel testler.

    python analyze.py          # results/results.csv ve (varsa) results/swarm.csv, results/decision.csv okunur
Çıktılar: results/figures/*.png ve results/istatistik.txt
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from suru import PLANNER_NAMES, STRATEGIES, STRATEGY_NAMES

PLANNER_COLORS = {"greedy": "#9a9890", "cbba": "#378ADD", "ai": "#B5359A"}
# Karar alma deneyinin koşulları (run_experiments.DECISION_CONDS ile aynı sıra)
DEC_CONDS = [(-1, 0.0, 0, "Karıştırma yok"), (20, 0.0, 0, "20 dBm"), (30, 0.0, 0, "30 dBm"),
             (-1, 0.2, 0, "%20 saldırgan"), (20, 0.0, 3, "20 dBm + 3 arıza")]

METRICS = {
    "completion": ("Görev tamamlama oranı (%)", 100),
    "mission_time": ("Görev süresi (s)", 1),
    "false_done": ("Yanlış tamamlanan görev sayısı", 1),
    "redundant": ("Gereksiz tekrar ziyaret sayısı", 1),
    "pdr": ("Paket iletim oranı (%)", 100),
    "loc_err": ("Ortalama konum hatası (m)", 1),
    "connectivity": ("Sürü bağlantılılığı (%)", 100),
    "formation_err": ("Düzen uçuşu yuva hatası (m)", 1),
}
COLORS = {"centralized": "#D85A30", "decentralized": "#378ADD", "resilient": "#1D9E75"}
POWER_LABEL = {-1: "Kapalı", 10: "10 dBm", 20: "20 dBm", 30: "30 dBm"}


def errbar(ax, x, sub, col, scale, s):
    g = sub.groupby(x)[col]
    keys = sorted(sub[x].unique())
    mean, sem = g.mean().reindex(keys) * scale, g.sem().reindex(keys) * scale
    ax.errorbar(range(len(keys)), mean, yerr=1.96 * sem, marker="o", capsize=4, lw=2,
                color=COLORS[s], label=STRATEGY_NAMES[s])
    return keys


def plot_main(df, outdir):
    for spoof in sorted(df.spoof.unique()):
        sub = df[df.spoof == spoof]
        for col, (label, scale) in METRICS.items():
            fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=150)
            for s in STRATEGIES:
                keys = errbar(ax, "jammer_dbm", sub[sub.strategy == s], col, scale, s)
            ax.set_xticks(range(len(keys)), [POWER_LABEL.get(p, p) for p in keys])
            ax.set_xlabel("Karıştırıcı gücü")
            ax.set_ylabel(label)
            ax.set_title(f"{label} — saldırgan oranı %{spoof * 100:.0f}", fontsize=10)
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(os.path.join(outdir, f"{col}_saldirgan{int(spoof * 100)}.png"))
            plt.close(fig)


def plot_swarm(sw, outdir):
    ar = sw[sw.experiment == "ariza"]
    for power in sorted(ar.jammer_dbm.unique()):
        sub = ar[ar.jammer_dbm == power]
        fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=150)
        for s in STRATEGIES:
            keys = errbar(ax, "failures_cfg", sub[sub.strategy == s], "completion", 100, s)
        ax.set_xticks(range(len(keys)), [f"{k} İHA" for k in keys])
        ax.set_xlabel("Görev sırasında düşen İHA sayısı")
        ax.set_ylabel("Görev tamamlama oranı (%)")
        ax.set_title(f"Üye kaybına dayanıklılık — karıştırıcı {POWER_LABEL.get(power, power)}", fontsize=10)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, f"ariza_karistirici{int(power)}.png"))
        plt.close(fig)
    ro = sw[sw.experiment == "role"]
    if len(ro):
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), dpi=150)
        for ax, (col, label, scale) in zip(axes, (("connectivity", "Sürü bağlantılılığı (%)", 100),
                                                  ("mission_time", "Görev süresi (s)", 1))):
            for k, s in enumerate(("decentralized", "resilient")):
                for j, r in enumerate((0, 1)):
                    x = ro[(ro.strategy == s) & (ro.relay == r)][col] * scale
                    ax.bar(k * 2.6 + j, x.mean(), yerr=1.96 * x.sem(), capsize=4,
                           color=COLORS[s], alpha=0.45 if r == 0 else 1.0,
                           label=f"{STRATEGY_NAMES[s]} · röle {'açık' if r else 'kapalı'}")
            ax.set_xticks([0.5, 3.1], [STRATEGY_NAMES["decentralized"], STRATEGY_NAMES["resilient"]], fontsize=7)
            ax.set_ylabel(label)
            ax.grid(alpha=0.3, axis="y")
        axes[0].legend(fontsize=6)
        fig.suptitle("Röle etkisi (haberleşme menzili 180 m, karıştırma yok)", fontsize=10)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, "role_etkisi.png"))
        plt.close(fig)


def cond_rows(df, power, spoof, fails):
    return df[(df.jammer_dbm == power) & (np.isclose(df.spoof, spoof)) & (df.failures_cfg == fails)]


def valuation_variants(dc):
    """Dirençli CBBA'nın görev değerlendirme türleri: kural yok / uzman kuralı / yapay zekâ."""
    pl = dc[(dc.experiment == "plan") & (dc.strategy == "resilient")]
    out = {}
    if (dc.experiment == "degerleme").any():
        out["Kural yok"] = dc[dc.experiment == "degerleme"]
    if (pl.planner == "cbba").any():
        out["Uzman kuralı"] = pl[pl.planner == "cbba"]
    if (pl.planner == "ai").any():
        out["Yapay zekâ"] = pl[pl.planner == "ai"]
    return out


def plot_decision(dc, outdir):
    pl = dc[dc.experiment == "plan"]
    x = np.arange(len(DEC_CONDS))
    for col, label, scale, name in (("score", "Görev puanı (0-100)", 100, "karar_puan"),
                                    ("completion", "Görev tamamlama oranı (%)", 100, "karar_tamamlama"),
                                    ("task_dist", "Görev alanında katedilen yol (km)", 0.001, "karar_yol"),
                                    ("popup_resp", "Yeni hedefe tepki süresi (s)", 1, "karar_yeni_hedef")):
        fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), dpi=150, sharey=True)
        for ax, s in zip(axes, STRATEGIES):
            planners = [p for p in PLANNER_NAMES if ((pl.strategy == s) & (pl.planner == p)).any()]
            w = 0.8 / max(len(planners), 1)
            for j, p in enumerate(planners):
                sub = pl[(pl.strategy == s) & (pl.planner == p)]
                vals = [cond_rows(sub, pw, sp, f)[col].dropna() * scale for pw, sp, f, _ in DEC_CONDS]
                ax.bar(x + (j - (len(planners) - 1) / 2) * w, [v.mean() if len(v) else np.nan for v in vals], w * 0.92,
                       yerr=[1.96 * v.sem() if len(v) > 1 else 0 for v in vals], capsize=2,
                       color=PLANNER_COLORS[p], label=PLANNER_NAMES[p], error_kw=dict(lw=0.8))
            ax.set_xticks(x, [c[3] for c in DEC_CONDS], rotation=25, fontsize=7)
            ax.set_title(STRATEGY_NAMES[s], fontsize=9)
            ax.grid(alpha=0.3, axis="y")
            ax.legend(fontsize=7)
        axes[0].set_ylabel(label)
        fig.suptitle(f"Otonom karar alma: {label.split(' (')[0].lower()}", fontsize=10)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, f"{name}.png"))
        plt.close(fig)

    variants = valuation_variants(dc)
    if len(variants) > 1:
        fig, axes = plt.subplots(1, 2, figsize=(12, 4), dpi=150)
        cols = {"Kural yok": "#9a9890", "Uzman kuralı": "#378ADD", "Yapay zekâ": "#B5359A"}
        for ax, (col, label) in zip(axes, (("score", "Görev puanı (0-100)"), ("completion", "Görev tamamlama oranı (%)"))):
            w = 0.8 / len(variants)
            for j, (name, sub) in enumerate(variants.items()):
                vals = [cond_rows(sub, pw, sp, f)[col] * 100 for pw, sp, f, _ in DEC_CONDS]
                ax.bar(x + (j - (len(variants) - 1) / 2) * w, [v.mean() for v in vals], w * 0.92,
                       yerr=[1.96 * v.sem() for v in vals], capsize=2, color=cols[name], label=name,
                       error_kw=dict(lw=0.8))
            ax.set_xticks(x, [c[3] for c in DEC_CONDS], rotation=20, fontsize=7)
            ax.set_ylabel(label)
            ax.grid(alpha=0.3, axis="y")
            ax.legend(fontsize=7)
        fig.suptitle("Görev değerlendirme: kural yok / uzman kuralı / yapay zekâ (dirençli strateji, CBBA, test haritaları)",
                     fontsize=10)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, "yapay_zeka.png"))
        plt.close(fig)

    pk = dc[dc.experiment == "paket"]
    if len(pk):
        fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8), dpi=150)
        for ax, (col, label, scale) in zip(axes, (("score", "Görev puanı (0-100)", 100),
                                                  ("task_dist", "Katedilen yol (km)", 0.001))):
            for power, c in ((-1, "#1D9E75"), (20, "#D85A30")):
                sub = pk[pk.jammer_dbm == power]
                g = sub.groupby("bundle_size")[col]
                keys = sorted(sub.bundle_size.unique())
                ax.errorbar(keys, g.mean().reindex(keys) * scale, yerr=1.96 * g.sem().reindex(keys) * scale,
                            marker="o", capsize=4, lw=2, color=c, label=f"karıştırıcı {POWER_LABEL.get(power, power)}")
            ax.set_xlabel("Paket büyüklüğü (bir İHA'nın planladığı görev sayısı)")
            ax.set_ylabel(label)
            ax.set_xticks(keys)
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.suptitle("CBBA paket büyüklüğünün etkisi (dirençli strateji, 6 yeni hedef)", fontsize=10)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, "paket_boyutu.png"))
        plt.close(fig)


def wilcoxon_line(a, b, label):
    ok = ~(np.isnan(np.asarray(a, float)) | np.isnan(np.asarray(b, float)))
    a, b = np.asarray(a, float)[ok], np.asarray(b, float)[ok]
    d = a - b
    if len(d) < 2 or not (d != 0).any():
        return f"  {label}: fark yok"
    w, p = stats.wilcoxon(a, b)
    return f"  {label}: fark {d.mean():+.3f}, Wilcoxon p={p:.4g} {'(anlamlı)' if p < 0.05 else '(anlamsız)'}"


def decision_statistics(dc):
    lines = ["\n##### KARAR ALMA DENEYİ: açgözlü tek görev / CBBA paket planlama / CBBA + yapay zekâ #####",
             "(her koşulda 6 yeni hedef görev sırasında belirir; puan = zamanla azalan görev değerleri, 0-100)"]
    pl = dc[dc.experiment == "plan"]
    for pw, sp, f, name in DEC_CONDS:
        sub = cond_rows(pl, pw, sp, f)
        if not len(sub):
            continue
        lines.append(f"\n=== {name} ===")
        for s in STRATEGIES:
            for p in PLANNER_NAMES:
                x = sub[(sub.strategy == s) & (sub.planner == p)]
                if not len(x):
                    continue
                lines.append(f"  {STRATEGY_NAMES[s]:28s} {PLANNER_NAMES[p]:20s} puan {x.score.mean() * 100:5.1f} ± "
                             f"{x.score.std() * 100:4.1f}  tamamlama %{x.completion.mean() * 100:5.1f}  süre "
                             f"{x.mission_time.mean():5.0f} s  yol {x.task_dist.mean() / 1000:5.2f} km  yeni hedef tepkisi "
                             f"{x.popup_resp.mean():5.1f} s  yeniden plan {x.reassign.mean():4.1f}  (n={len(x)})")
            piv = sub[sub.strategy == s].pivot_table(index="seed", columns="planner", values=["score", "task_dist"])
            if ("score", "cbba") in piv and ("score", "greedy") in piv:
                lines.append(wilcoxon_line(piv["score"]["cbba"], piv["score"]["greedy"], "  CBBA - açgözlü (puan)"))
                lines.append(wilcoxon_line(piv["task_dist"]["cbba"], piv["task_dist"]["greedy"], "  CBBA - açgözlü (yol, m)"))
            if ("score", "ai") in piv and ("score", "cbba") in piv:
                lines.append(wilcoxon_line(piv["score"]["ai"], piv["score"]["cbba"], "  Yapay zekâ - uzman kuralı (puan)"))
    variants = valuation_variants(dc)
    if len(variants) > 1:
        lines.append("\n##### GÖREV DEĞERLENDİRME: kural yok / uzman kuralı / yapay zekâ (dirençli, CBBA) #####")
        for pw, sp, f, name in DEC_CONDS:
            lines.append(f"\n=== {name} ===")
            piv = {}
            for vname, sub in variants.items():
                x = cond_rows(sub, pw, sp, f)
                piv[vname] = x.set_index("seed")
                lines.append(f"  {vname:14s} puan {x.score.mean() * 100:5.1f} ± {x.score.std() * 100:4.1f}  tamamlama "
                             f"%{x.completion.mean() * 100:5.1f}  süre {x.mission_time.mean():5.0f} s  (n={len(x)})")
            for a, b in (("Uzman kuralı", "Kural yok"), ("Yapay zekâ", "Kural yok"), ("Yapay zekâ", "Uzman kuralı")):
                if a in piv and b in piv:
                    j = piv[a].join(piv[b], lsuffix="_a", rsuffix="_b", how="inner")
                    lines.append(wilcoxon_line(j.score_a, j.score_b, f"{a} - {b} (puan)"))
        tr = os.path.join("results", "ai_egitim.txt")
        if os.path.exists(tr):
            with open(tr, encoding="utf-8") as f:
                lines.append("\n" + f.read())
        es = os.path.join("results", "ai_es_deneme.csv")
        if os.path.exists(es):
            h = pd.read_csv(es)
            d = h.ag_puani - h.uzman_kurali
            lines.append(f"\n  İlk deneme, evrim stratejileri ({len(h)} kuşak): ağ - uzman puan farkı ilk 5 kuşak "
                         f"{d.head(5).mean():+.3f}, son 5 kuşak {d.tail(5).mean():+.3f} (öğrenemedi)")
    pk = dc[dc.experiment == "paket"]
    if len(pk):
        lines.append("\n##### PAKET BÜYÜKLÜĞÜ (dirençli strateji) #####")
        for power, sub in pk.groupby("jammer_dbm"):
            lines.append(f"\n=== Karıştırıcı: {POWER_LABEL.get(power, power)} ===")
            for L, x in sub.groupby("bundle_size"):
                lines.append(f"  paket {L}: puan {x.score.mean() * 100:5.1f} ± {x.score.std() * 100:4.1f}  süre "
                             f"{x.mission_time.mean():5.0f} s  yol {x.task_dist.mean() / 1000:5.2f} km  (n={len(x)})")
            piv = sub.pivot_table(index="seed", columns="bundle_size", values="score")
            if 1 in piv and 3 in piv:
                lines.append(wilcoxon_line(piv[3], piv[1], "Paket 3 - paket 1 (puan)"))
    return lines


def statistics(df, sw, dc=None):
    lines = ["İSTATİSTİK RAPORU (ortalama ± standart sapma; n = tekrar sayısı; Wilcoxon: aynı haritada eşleştirilmiş test)\n",
             "\n##### ANA DENEY: karıştırma ve sahte bilgi #####"]
    for (power, spoof), sub in df.groupby(["jammer_dbm", "spoof"]):
        lines.append(f"\n=== Karıştırıcı: {POWER_LABEL.get(power, power)} | saldırgan %{spoof * 100:.0f} ===")
        for s in STRATEGIES:
            x = sub[sub.strategy == s]
            lines.append(f"  {STRATEGY_NAMES[s]:30s} tamamlama %{x.completion.mean() * 100:5.1f} ± {x.completion.std() * 100:4.1f}"
                         f"  süre {x.mission_time.mean():5.0f} s  yanlış {x.false_done.mean():4.1f}"
                         f"  bağlantı %{x.connectivity.mean() * 100:3.0f}  düzen hatası {x.formation_err.mean():4.1f} m"
                         f"  (n={len(x)})")
        groups = [sub[sub.strategy == s].completion.values for s in STRATEGIES]
        if all(len(g) > 1 for g in groups) and np.ptp(np.concatenate(groups)) > 0:
            h, p = stats.kruskal(*groups)
            lines.append(f"  Kruskal-Wallis: H={h:.2f}, p={p:.4g}")
        piv = sub.pivot_table(index="seed", columns="strategy", values="completion")
        for other in ("decentralized", "centralized"):
            lines.append(wilcoxon_line(piv["resilient"], piv[other], f"Dirençli vs {STRATEGY_NAMES[other]} (tamamlama)"))
    if sw is not None:
        lines.append("\n##### SÜRÜ DENEYİ 1: üye kaybı (görev sırasında İHA arızası) #####")
        ar = sw[sw.experiment == "ariza"]
        for (power, f), sub in ar.groupby(["jammer_dbm", "failures_cfg"]):
            lines.append(f"\n=== Karıştırıcı: {POWER_LABEL.get(power, power)} | düşen İHA: {f} ===")
            for s in STRATEGIES:
                x = sub[sub.strategy == s]
                lines.append(f"  {STRATEGY_NAMES[s]:30s} tamamlama %{x.completion.mean() * 100:5.1f} ± {x.completion.std() * 100:4.1f}"
                             f"  süre {x.mission_time.mean():5.0f} s  (n={len(x)})")
        lines.append("\n##### SÜRÜ DENEYİ 2: bağlantı koruma rölesi (menzil 180 m, karıştırma yok) #####")
        ro = sw[sw.experiment == "role"]
        for s in ("decentralized", "resilient"):
            sub = ro[ro.strategy == s]
            piv_c = sub.pivot_table(index="seed", columns="relay", values="connectivity")
            piv_t = sub.pivot_table(index="seed", columns="relay", values="mission_time")
            lines.append(f"\n=== {STRATEGY_NAMES[s]} ===")
            for r in (0, 1):
                x = sub[sub.relay == r]
                lines.append(f"  röle {'açık ' if r else 'kapalı'}: bağlantılılık %{x.connectivity.mean() * 100:5.1f}"
                             f"  süre {x.mission_time.mean():5.1f} s  röle süresi {x.relay_time.mean():5.1f} İHA·s"
                             f"  tamamlama %{x.completion.mean() * 100:5.1f}")
            if 0 in piv_c and 1 in piv_c:
                lines.append(wilcoxon_line(piv_c[1], piv_c[0], "Bağlantılılık (açık - kapalı)"))
                lines.append(wilcoxon_line(piv_t[1], piv_t[0], "Görev süresi (açık - kapalı)"))
    if dc is not None:
        lines += decision_statistics(dc)
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="results/results.csv")
    p.add_argument("--swarm", default="results/swarm.csv")
    p.add_argument("--decision", default="results/decision.csv")
    a = p.parse_args()
    df = pd.read_csv(a.csv)
    sw = pd.read_csv(a.swarm) if os.path.exists(a.swarm) else None
    dc = pd.read_csv(a.decision) if os.path.exists(a.decision) else None
    outdir = os.path.join(os.path.dirname(a.csv), "figures")
    os.makedirs(outdir, exist_ok=True)
    plot_main(df, outdir)
    if sw is not None:
        plot_swarm(sw, outdir)
    if dc is not None:
        plot_decision(dc, outdir)
    report = statistics(df, sw, dc)
    path = os.path.join(os.path.dirname(a.csv), "istatistik.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\nGrafikler: {outdir}\nRapor: {path}")


if __name__ == "__main__":
    main()
