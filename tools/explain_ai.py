"""Yapay zekâ ne öğrendi? Eğitilmiş ağın başarı olasılığı kestirimini tek tek özelliklere göre çizer ve uzman
kuralıyla (dirençli strateji) karşılaştırır. Diğer özellikler tipik değerlerde sabit tutulur.

    python tools/explain_ai.py
Sonuç: results/figures/ai_ne_ogrendi.png
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from suru.config import SimConfig  # noqa: E402
from suru.decision import AI_FEATURES, AIValue  # noqa: E402

c = SimConfig()
net = AIValue.load()
lnlam = np.log(c.discount)
cruise = 0.9 * c.max_speed
# Tipik durum: GPS var, karıştırma yok, 300 m uzakta orta değerli görev, komşuların çoğu duyuluyor
BASE = dict(gorev_karistirmada=0.0, yol_karistirmada=0.0, gps_yok=0.0, belirsizlik=np.log1p(1.5 / c.task_radius),
            karistirma_seviyesi=0.1, uzaklik=1.0, deger=2 / 3, komsu=0.9)


def feats(**kw):
    d = dict(BASE, **kw)
    n = max(np.size(v) for v in d.values())
    return np.stack([np.broadcast_to(np.asarray(d[k], float), (n,)) for k in AI_FEATURES], axis=1)


def expert_search(sig):
    """Uzman kuralı: belirsizliğin zaman maliyeti (World._search_time ile aynı)."""
    R = np.minimum(2.5 * sig + 10.0, 100.0)
    t = np.where(sig > c.task_radius / 2, R * R / (2 * c.search_detect / np.pi * 9.0), 0.0)
    return np.exp(lnlam * t)


fig, axes = plt.subplots(1, 3, figsize=(13, 3.9), dpi=150)
# 1) Konum belirsizliği (GPS kesik)
sig = np.linspace(1.5, 60, 80)
ax = axes[0]
ax.plot(sig, net(feats(belirsizlik=np.log1p(sig / c.task_radius), gps_yok=1.0, karistirma_seviyesi=0.7)),
        lw=2.5, color="#B5359A", label="yapay zekâ")
ax.plot(sig, expert_search(sig), "--", lw=2, color="#378ADD", label="uzman kuralı")
ax.set_xlabel("İHA'nın konum belirsizliği σ (m), GPS kesik")
ax.set_ylabel("Başarı olasılığı / çarpan ρ")
ax.set_title("GPS'siz İHA'nın teklifi", fontsize=10)
# 2) Görev / yol karıştırma bölgesinde
ax = axes[1]
labels = ["görev temiz\nyol temiz", "görev temiz\nyol karışık", "görev karıştırmada"]
ai = [net(feats())[0], net(feats(yol_karistirmada=0.6))[0], net(feats(gorev_karistirmada=1.0, yol_karistirmada=0.6))[0]]
pen = np.exp(lnlam * c.jam_penalty / cruise)
ex = [1.0, 1.0, pen]
x = np.arange(3)
ax.bar(x - 0.2, ai, 0.38, color="#B5359A", label="yapay zekâ")
ax.bar(x + 0.2, ex, 0.38, color="#378ADD", label="uzman kuralı")
ax.set_xticks(x, labels, fontsize=8)
ax.set_title("Karıştırma bölgesi", fontsize=10)
# 3) Uzaklık ve görev değeri
ax = axes[2]
d = np.linspace(0, 2.2, 60)
for v, ls in ((1 / 3, ":"), (2 / 3, "-"), (1.0, "--")):
    ax.plot(d * 300, net(feats(uzaklik=d, deger=v)), ls, lw=2, color="#B5359A", label=f"YZ, değer {round(v * 3)}")
ax.axhline(1.0, color="#378ADD", lw=2, ls="--", label="uzman kuralı")
ax.set_xlabel("Göreve uzaklık (m)")
ax.set_title("Uzaklık ve öncelik", fontsize=10)
for ax in axes:
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
fig.suptitle("Yapay zekâ ne öğrendi? (kestirilen görev başarı olasılığı; uzman kuralı elle seçilmiş çarpan)", fontsize=10)
fig.tight_layout()
out = os.path.join(REPO, "results", "figures", "ai_ne_ogrendi.png")
fig.savefig(out)
print("Kaydedildi:", out)
for k, v in zip(AI_FEATURES, feats()[0]):
    print(f"  tipik {k:20s} = {v:.2f}")
print("  tipik durumda rho =", round(float(net(feats())[0]), 3))
