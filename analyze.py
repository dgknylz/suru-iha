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


MECH_NAMES = {
    "jam_map": "karıştırma haritası", "long_ttl": "uzun bekleme (TTL)", "avoid": "bölgeden kaçınma",
    "coop_loc": "işbirlikçi konum", "search": "spiral arama", "recover": "GPS kurtarma", "trust": "güven sistemi",
    "localize": "karıştırıcı bulma", "fhss": "frekans atlama", "spoof_detect": "aldatma tespiti",
    "valuation": "görev değerlendirme",
}


def plot_ew(ew, outdir):
    sub = ew[ew.experiment == "eh"]
    names = list(dict.fromkeys(sub.tag))
    x = np.arange(len(names))
    fig, axes = plt.subplots(2, 1, figsize=(12, 7.5), dpi=150, sharex=True)
    for ax, (col, label) in zip(axes, (("completion", "Görev tamamlama (%)"), ("score", "Görev puanı (0-100)"))):
        for j, s in enumerate(STRATEGIES):
            vals = [sub[(sub.tag == n) & (sub.strategy == s)][col] * 100 for n in names]
            ax.bar(x + (j - 1) * 0.27, [v.mean() for v in vals], 0.25, yerr=[1.96 * v.sem() for v in vals],
                   capsize=2, color=COLORS[s], label=STRATEGY_NAMES[s], error_kw=dict(lw=0.8))
        ax.set_ylabel(label)
        ax.grid(alpha=0.3, axis="y")
    axes[0].legend(fontsize=8, ncol=3)
    axes[1].set_xticks(x, names, rotation=20, fontsize=8)
    fig.suptitle("Elektronik harp senaryoları (her uçuşta 6 yeni hedef, n=30)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "eh_senaryolar.png"))
    plt.close(fig)

    ar = ew[ew.experiment == "arazi"]
    if len(ar):
        fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
        k = 0
        ticks = []
        for name in dict.fromkeys(ar.tag):
            for s in STRATEGIES:
                on = sub[(sub.tag == name) & (sub.strategy == s)].completion * 100
                off = ar[(ar.tag == name) & (ar.strategy == s)].completion * 100
                ax.bar(k - 0.2, on.mean(), 0.38, color=COLORS[s], yerr=1.96 * on.sem(), capsize=2)
                ax.bar(k + 0.2, off.mean(), 0.38, color=COLORS[s], alpha=0.35, yerr=1.96 * off.sem(), capsize=2)
                ticks.append((k, f"{name}\n{STRATEGY_NAMES[s].split(' ')[0]}"))
                k += 1
            k += 0.6
        ax.set_xticks([t for t, _ in ticks], [n for _, n in ticks], fontsize=6)
        ax.set_ylabel("Görev tamamlama (%)")
        ax.set_title("Arazi gölgesi: koyu = tepeler sinyali keser (gerçekçi), açık = arazi yok sayılır", fontsize=9)
        ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, "eh_arazi_golgesi.png"))
        plt.close(fig)


def plot_tune(tu, outdir):
    rows = tu.tag.str.split("|", expand=True)
    tu = tu.assign(cond=rows[0], setting=rows[1])
    params = [p for p in ("claim_ttl_jam", "recover_sigma", "jam_penalty", "jam_cell_ttl")]
    labels = {"claim_ttl_jam": "Karıştırmada bekleme süresi (s)", "recover_sigma": "GPS kurtarma eşiği σ (m)",
              "jam_penalty": "Karıştırma cezası (m)", "jam_cell_ttl": "Harita unutma süresi (s)"}
    from suru import SimConfig
    d = SimConfig()
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.8), dpi=150, sharey=True)
    for ax, p in zip(axes, params):
        for cond, c in zip(dict.fromkeys(tu.cond), ("#1D9E75", "#D85A30", "#378ADD")):
            vals = {}
            for _, r in tu[tu.cond == cond].iterrows():
                if r.setting == "varsayılan":
                    v = getattr(d, p)
                elif r.setting.startswith(p + "="):
                    v = float(r.setting.split("=")[1])
                else:
                    continue
                vals.setdefault(v, []).append(r.score * 100)
            ks = sorted(vals)
            ax.errorbar(ks, [np.mean(vals[k]) for k in ks], yerr=[1.96 * np.std(vals[k]) / np.sqrt(len(vals[k])) for k in ks],
                        marker="o", capsize=3, color=c, label=cond)
        ax.axvline(getattr(d, p), color="k", ls=":", lw=1)
        ax.set_xlabel(labels[p])
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Görev puanı (0-100)")
    axes[0].legend(fontsize=7)
    fig.suptitle("Parametre duyarlılığı (ayar haritaları seed 500-519; noktalı çizgi = kullanılan değer)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "ayar_duyarlilik.png"))
    plt.close(fig)


def ablation_table(ab):
    rows = ab.tag.str.split("|", expand=True)
    ab = ab.assign(cond=rows[0], variant=rows[1])
    conds = list(dict.fromkeys(ab.cond))
    variants = ["hiçbiri"] + [f"-{m}" for m in MECH_NAMES]
    D = np.full((len(variants), len(conds)), np.nan)
    P = np.full_like(D, np.nan)
    for j, cond in enumerate(conds):
        full = ab[(ab.cond == cond) & (ab.variant == "tam")].set_index("seed").score
        for i, v in enumerate(variants):
            x = ab[(ab.cond == cond) & (ab.variant == v)].set_index("seed").score
            k = full.index.intersection(x.index)
            if len(k) < 2:
                continue
            d = (x[k] - full[k]).values
            D[i, j] = d.mean() * 100
            P[i, j] = stats.wilcoxon(x[k], full[k]).pvalue if (d != 0).any() else 1.0
    return conds, variants, D, P


def plot_ablation(ab, outdir):
    conds, variants, D, P = ablation_table(ab)
    fig, ax = plt.subplots(figsize=(1.6 * len(conds) + 3, 0.45 * len(variants) + 1.8), dpi=150)
    lim = np.nanmax(np.abs(D)) if np.isfinite(D).any() else 1
    im = ax.imshow(D, cmap="RdBu", vmin=-lim, vmax=lim, aspect="auto")
    for i in range(len(variants)):
        for j in range(len(conds)):
            if np.isfinite(D[i, j]):
                star = "***" if P[i, j] < 0.001 else "**" if P[i, j] < 0.01 else "*" if P[i, j] < 0.05 else ""
                ax.text(j, i, f"{D[i, j]:+.1f}{star}", ha="center", va="center", fontsize=7,
                        color="white" if abs(D[i, j]) > 0.6 * lim else "black")
    ax.set_xticks(range(len(conds)), conds, rotation=20, fontsize=8)
    ax.set_yticks(range(len(variants)),
                  ["hiçbiri (korumasız)"] + [f"– {MECH_NAMES[v[1:]]}" for v in variants[1:]], fontsize=8)
    fig.colorbar(im, ax=ax, label="Puan farkı (mekanizma kapalı − tam sistem)")
    ax.set_title(f"Ablasyon: her mekanizma kapatılınca görev puanı ne kadar düşüyor? (* p<0,05, n={ab.seed.nunique()})", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "ablasyon.png"))
    plt.close(fig)


def plot_scaling(sc, outdir):
    sc = sc.assign(cond=np.where(sc.spoof > 0, "%20 saldırgan", np.where(sc.jammer_dbm > 0, "20 dBm", "karıştırma yok")))
    conds = ["karıştırma yok", "20 dBm", "%20 saldırgan"]
    fig, axes = plt.subplots(1, 4, figsize=(16, 3.8), dpi=150)
    for ax, cond in zip(axes, conds):
        for s in STRATEGIES:
            sub = sc[(sc.cond == cond) & (sc.strategy == s)]
            g = sub.groupby("n_drones").score
            ks = sorted(sub.n_drones.unique())
            ax.errorbar(ks, g.mean().reindex(ks) * 100, yerr=1.96 * g.sem().reindex(ks) * 100, marker="o", capsize=3,
                        color=COLORS[s], label=STRATEGY_NAMES[s])
        ax.set_title(cond, fontsize=9)
        ax.set_xlabel("İHA sayısı (görev = 2 x İHA)")
        ax.set_xticks([5, 10, 20])
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Görev puanı (0-100)")
    axes[0].legend(fontsize=7)
    ax = axes[3]
    for s in STRATEGIES:
        sub = sc[sc.strategy == s]
        g = (sub.wall_s / sub.sim_time * 1000).groupby(sub.n_drones)
        ks = sorted(sub.n_drones.unique())
        ax.plot(ks, g.mean().reindex(ks), "o-", color=COLORS[s], label=STRATEGY_NAMES[s])
    ax.set_title("Hesap yükü", fontsize=9)
    ax.set_xlabel("İHA sayısı")
    ax.set_ylabel("Simülasyon saniyesi başına ms")
    ax.set_xticks([5, 10, 20])
    ax.grid(alpha=0.3)
    fig.suptitle(f"Ölçeklenebilirlik (n={sc.seed.nunique()}, her uçuşta 6 yeni hedef)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "olcekleme.png"))
    plt.close(fig)


def ew_statistics(ew, tu, ab, sc):
    lines = []
    if ew is not None:
        lines.append("\n##### ELEKTRONİK HARP SENARYOLARI (her uçuşta 6 yeni hedef) #####")
        sub = ew[ew.experiment == "eh"]
        for name in dict.fromkeys(sub.tag):
            x = sub[sub.tag == name]
            lines.append(f"\n=== {name} ===")
            for s in STRATEGIES:
                y = x[x.strategy == s]
                lines.append(f"  {STRATEGY_NAMES[s]:28s} tamamlama %{y.completion.mean() * 100:5.1f} ± "
                             f"{y.completion.std() * 100:4.1f}  puan {y.score.mean() * 100:5.1f}  süre {y.mission_time.mean():5.0f} s"
                             f"  yanlış {y.false_done.mean():4.1f}  (n={len(y)})")
            piv = x.pivot_table(index="seed", columns="strategy", values="score")
            for other in ("decentralized", "centralized"):
                if "resilient" in piv and other in piv:
                    lines.append(wilcoxon_line(piv["resilient"], piv[other], f"Dirençli - {STRATEGY_NAMES[other]} (puan)"))
            r = x[x.strategy == "resilient"]
            if r.jam_loc_err.notna().any():
                lines.append(f"  Karıştırıcı bulma (dirençli): ortalama hata {r.jam_loc_err.mean():5.0f} m, görev sonu "
                             f"{r.jam_loc_err_end.mean():5.0f} m, 50 m'den iyi bulunduğu uçuş %{r.t_locate.notna().mean() * 100:3.0f}"
                             f" (ortalama {r.t_locate.mean():4.0f}. saniyede)")
            if r.spoof_captured.sum() > 0:
                lines.append(f"  GPS aldatma (dirençli): ele geçen {r.spoof_captured.mean():4.1f} İHA, tespit "
                             f"{r.spoof_detected.mean():4.1f}, tespit süresi {r.spoof_detect_time.mean():4.1f} s, "
                             f"yanlış alarm {r.spoof_false_alarm.mean():4.2f}")
            if r.liars_caught.notna().any():
                lines.append(f"  Güven sistemi (dirençli): saldırganları dışlama %{r.liars_caught.mean() * 100:5.1f}, "
                             f"dürüst arkadaşı yanlış dışlama %{r.honest_excluded.mean() * 100:4.1f}")
        ar = ew[ew.experiment == "arazi"]
        for name in dict.fromkeys(ar.tag):
            lines.append(f"\n=== Arazi gölgesi açık/kapalı: {name} ===")
            for s in STRATEGIES:
                on = sub[(sub.tag == name) & (sub.strategy == s)].set_index("seed")
                off = ar[(ar.tag == name) & (ar.strategy == s)].set_index("seed")
                lines.append(f"  {STRATEGY_NAMES[s]:28s} tamamlama açık %{on.completion.mean() * 100:5.1f} / kapalı "
                             f"%{off.completion.mean() * 100:5.1f}  paket iletimi %{on.pdr.mean() * 100:4.1f} / %{off.pdr.mean() * 100:4.1f}")
                k = on.index.intersection(off.index)
                lines.append(wilcoxon_line(on.score[k], off.score[k], "  açık - kapalı (puan)"))
    if tu is not None:
        lines.append("\n##### PARAMETRE AYARI (ayar haritaları, seed 500-519; testten ayrı) #####")
        rows = tu.tag.str.split("|", expand=True)
        t2 = tu.assign(cond=rows[0], setting=rows[1])
        for setting, x in t2.groupby("setting"):
            lines.append(f"  {setting:24s} puan {x.score.mean() * 100:5.1f}  tamamlama %{x.completion.mean() * 100:5.1f}"
                         f"  (n={len(x)})")
    if ab is not None:
        lines.append(f"\n##### ABLASYON (dirençli strateji; puan farkı = mekanizma kapalı - tam sistem, n={ab.seed.nunique()}) #####")
        conds, variants, D, P = ablation_table(ab)
        lines.append("  " + " | ".join(f"{c[:18]:>18s}" for c in conds))
        for i, v in enumerate(variants):
            name = "hiçbiri (korumasız)" if v == "hiçbiri" else "- " + MECH_NAMES[v[1:]]
            cells = " | ".join(f"{D[i, j]:+7.1f} (p={P[i, j]:.3f})" if np.isfinite(D[i, j]) else f"{'':18s}"
                               for j in range(len(conds)))
            lines.append(f"  {name:24s} {cells}")
    if sc is not None:
        lines.append(f"\n##### ÖLÇEKLEME (görev sayısı = 2 x İHA, 6 yeni hedef, n={sc.seed.nunique()}) #####")
        sc2 = sc.assign(cond=np.where(sc.spoof > 0, "%20 saldırgan", np.where(sc.jammer_dbm > 0, "20 dBm", "karıştırma yok")))
        for (cond, n), x in sc2.groupby(["cond", "n_drones"]):
            parts = []
            for s in STRATEGIES:
                y = x[x.strategy == s]
                parts.append(f"{STRATEGY_NAMES[s].split(' ')[0]} %{y.completion.mean() * 100:5.1f}/{y.score.mean() * 100:4.1f}")
            ms = (x.wall_s / x.sim_time * 1000).mean()
            lines.append(f"  {cond:15s} {int(n):2d} İHA: " + "  ".join(parts) + f"  (tamamlama/puan; {ms:4.0f} ms/sim-s)")
    return lines


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


def statistics(df, sw, dc=None, extra=None):
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
    if extra is not None:
        lines += ew_statistics(*extra)
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="results/results.csv")
    p.add_argument("--swarm", default="results/swarm.csv")
    p.add_argument("--decision", default="results/decision.csv")
    a = p.parse_args()
    df = pd.read_csv(a.csv)
    rd = os.path.dirname(a.csv)

    def opt(name):
        path = os.path.join(rd, name)
        return pd.read_csv(path) if os.path.exists(path) else None
    sw = pd.read_csv(a.swarm) if os.path.exists(a.swarm) else None
    dc = pd.read_csv(a.decision) if os.path.exists(a.decision) else None
    ew, tu, ab, sc = opt("ew.csv"), opt("tune.csv"), opt("ablation.csv"), opt("scaling.csv")
    outdir = os.path.join(rd, "figures")
    os.makedirs(outdir, exist_ok=True)
    plot_main(df, outdir)
    if sw is not None:
        plot_swarm(sw, outdir)
    if dc is not None:
        plot_decision(dc, outdir)
    if ew is not None:
        plot_ew(ew, outdir)
    if tu is not None:
        plot_tune(tu, outdir)
    if ab is not None:
        plot_ablation(ab, outdir)
    if sc is not None:
        plot_scaling(sc, outdir)
    report = statistics(df, sw, dc, (ew, tu, ab, sc))
    path = os.path.join(os.path.dirname(a.csv), "istatistik.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\nGrafikler: {outdir}\nRapor: {path}")


if __name__ == "__main__":
    main()
