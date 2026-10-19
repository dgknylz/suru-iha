"""Deney sonuçlarını analiz eder: grafikler + istatistiksel testler.

    python analyze.py                      # results/results.csv okunur
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
}
COLORS = {"centralized": "#D85A30", "decentralized": "#378ADD", "resilient": "#1D9E75"}
POWER_LABEL = {-1: "Kapalı", 10: "10 dBm", 20: "20 dBm", 30: "30 dBm"}


def plot(df, outdir):
    powers = sorted(df.jammer_dbm.unique())
    for spoof in sorted(df.spoof.unique()):
        sub = df[df.spoof == spoof]
        for col, (label, scale) in METRICS.items():
            fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=150)
            for s in STRATEGIES:
                g = sub[sub.strategy == s].groupby("jammer_dbm")[col]
                mean, sem = g.mean() * scale, g.sem() * scale
                ax.errorbar(range(len(powers)), mean.reindex(powers), yerr=1.96 * sem.reindex(powers),
                            marker="o", capsize=4, lw=2, color=COLORS[s], label=STRATEGY_NAMES[s])
            ax.set_xticks(range(len(powers)), [POWER_LABEL.get(p, p) for p in powers])
            ax.set_xlabel("Karıştırıcı gücü")
            ax.set_ylabel(label)
            ax.set_title(f"{label} — saldırgan oranı %{spoof * 100:.0f}", fontsize=10)
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(os.path.join(outdir, f"{col}_saldirgan{int(spoof * 100)}.png"))
            plt.close(fig)


def statistics(df):
    lines = ["İSTATİSTİK RAPORU (ortalama ± standart sapma; n = tekrar sayısı; Wilcoxon: aynı haritada eşleştirilmiş test)\n"]
    for (power, spoof), sub in df.groupby(["jammer_dbm", "spoof"]):
        lines.append(f"\n=== Karıştırıcı: {POWER_LABEL.get(power, power)} | saldırgan %{spoof * 100:.0f} ===")
        for s in STRATEGIES:
            x = sub[sub.strategy == s].completion * 100
            lines.append(f"  {STRATEGY_NAMES[s]:30s} tamamlama %{x.mean():5.1f} ± {x.std():4.1f}  (n={len(x)})")
        groups = [sub[sub.strategy == s].completion.values for s in STRATEGIES]
        if all(len(g) > 1 for g in groups) and np.ptp(np.concatenate(groups)) > 0:
            h, p = stats.kruskal(*groups)
            lines.append(f"  Kruskal-Wallis: H={h:.2f}, p={p:.4g}")
        # Eşleştirilmiş karşılaştırma (aynı seed = aynı harita): Wilcoxon işaretli sıralar testi
        piv = sub.pivot_table(index="seed", columns="strategy", values="completion")
        for other in ("decentralized", "centralized"):
            d = piv["resilient"] - piv[other]
            if (d != 0).any():
                w, p = stats.wilcoxon(piv["resilient"], piv[other])
                lines.append(f"  Dirençli vs {STRATEGY_NAMES[other]:24s}: fark %{d.mean() * 100:+5.1f}, "
                             f"Wilcoxon p={p:.4g} {'(anlamlı)' if p < 0.05 else ''}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="results/results.csv")
    a = p.parse_args()
    df = pd.read_csv(a.csv)
    outdir = os.path.join(os.path.dirname(a.csv), "figures")
    os.makedirs(outdir, exist_ok=True)
    plot(df, outdir)
    report = statistics(df)
    path = os.path.join(os.path.dirname(a.csv), "istatistik.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\nGrafikler: {outdir}\nRapor: {path}")


if __name__ == "__main__":
    main()
