"""Deney sonuçlarını analiz eder: grafikler + istatistiksel testler.

    python analyze.py          # results/results.csv ve (varsa) results/swarm.csv okunur
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

from suru import STRATEGIES, STRATEGY_NAMES

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


def wilcoxon_line(a, b, label):
    d = a - b
    if len(d) < 2 or not (d != 0).any():
        return f"  {label}: fark yok"
    w, p = stats.wilcoxon(a, b)
    return f"  {label}: fark {d.mean():+.3f}, Wilcoxon p={p:.4g} {'(anlamlı)' if p < 0.05 else '(anlamsız)'}"


def statistics(df, sw):
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
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="results/results.csv")
    p.add_argument("--swarm", default="results/swarm.csv")
    a = p.parse_args()
    df = pd.read_csv(a.csv)
    sw = pd.read_csv(a.swarm) if os.path.exists(a.swarm) else None
    outdir = os.path.join(os.path.dirname(a.csv), "figures")
    os.makedirs(outdir, exist_ok=True)
    plot_main(df, outdir)
    if sw is not None:
        plot_swarm(sw, outdir)
    report = statistics(df, sw)
    path = os.path.join(os.path.dirname(a.csv), "istatistik.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\nGrafikler: {outdir}\nRapor: {path}")


if __name__ == "__main__":
    main()
