"""İLK DENEME (öğrenemedi): evrim stratejileri (ES) ile pekiştirmeli öğrenme.

Sonuç: 25 kuşakta ağ ile uzman kuralı arasındaki fark gürültüden ayırt edilemedi
(results/ai_es_deneme.csv, results/figures/ai_es_deneme.png). İki sebep bulundu:
  1) İlk ağ tamamen sıfır ağırlıkla ve doymuş çıkışla başlıyordu; küçük gürültüler kararı neredeyse
     hiç değiştirmiyordu (düzeltildi: AIValue.initial).
  2) Görev puanı bir koşudan ötekine çok oynuyor (aynı haritada iki yöntem arasındaki farkın sapması
     0,02-0,04), görev değerlendirmesinin puana etkisi ise bundan küçük. Ödül sinyali gürültüde kayboluyor.
Bu yüzden asıl yöntem olarak başarı olasılığını kestiren denetimli öğrenmeye geçildi (tools/train_ai.py).

Sinir ağı (suru/decision.py, AIValue) her İHA-görev çifti için bir uygunluk çarpanı kestirir;
CBBA bu kestirimle plan yapar. Eğitimin her kuşağında:
  1) Ağın ağırlıklarına rastgele küçük gürültüler eklenip çıkarılır (+e ve -e, ikiz adaylar).
  2) Her aday ağla sürü, aynı birkaç senaryoda (karıştırma, arıza, yeni hedefler) görevi baştan sona yapar.
  3) Alınan görev puanı "ödül"dür. Ödülü artıran gürültü yönünde ağırlıklar güncellenir.
Türev hesabı yok, sadece deneme-yanılma ve ödül: pekiştirmeli öğrenmenin politika arama türü
(Salimans ve ark. 2017, "Evolution Strategies as a Scalable Alternative to Reinforcement Learning").

Eğitim haritaları (seed 1000+) test haritalarından (seed 0-29) ayrıdır: ağ, testte hiç görmediği
haritalarda değerlendirilir (ezber değil öğrenme).

    python tools/train_ai_es.py              # tam eğitim (~45 dk, 8 çekirdek)
    python tools/train_ai_es.py --gens 3     # hızlı deneme
Sonuç: --out ile verilen ağırlık dosyası, results/ai_es_deneme.csv, results/figures/ai_es_deneme.png
"""
import argparse
import csv
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from suru import World, make_config  # noqa: E402
from suru.decision import AI_FEATURES, AI_WEIGHTS, AIValue  # noqa: E402

# Eğitim senaryoları: (karıştırıcı gücü dBm, arıza sayısı). Hepsinde 6 yeni hedef belirir.
SCENARIOS = [(None, 0), (20.0, 0), (20.0, 3), (30.0, 0)]


def evaluate(job):
    """Bir aday ağ (theta) ya da uzman kuralıyla (theta=None) bir senaryoyu koşar, görev puanını döndürür."""
    theta, power, failures, seed = job
    if theta is None:
        cfg = make_config("resilient", power, 0.0, seed, planner="cbba", n_popup=6, failures=failures)
    else:
        cfg = make_config("resilient", power, 0.0, seed, planner="ai", ai_theta=tuple(theta), n_popup=6,
                          failures=failures)
    w = World(cfg)
    while not w.finished():
        w.step()
    return w.score()


def centered_ranks(x):
    """Ödülleri sıraya çevirir (-0.5 .. 0.5): uç değerli tek bir şanslı koşu eğitimi bozmaz."""
    r = np.empty(len(x))
    r[np.argsort(x)] = np.arange(len(x))
    return r / (len(x) - 1) - 0.5


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gens", type=int, default=25, help="kuşak sayısı")
    p.add_argument("--pairs", type=int, default=8, help="kuşak başına ikiz aday sayısı")
    p.add_argument("--sigma", type=float, default=0.2, help="gürültü büyüklüğü")
    p.add_argument("--lr", type=float, default=0.05, help="öğrenme hızı (Adam)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default=os.path.join(REPO, "results", "ai_es_agirlik.npz"))
    a = p.parse_args()

    rng = np.random.default_rng(a.seed)
    theta = AIValue.initial()
    n, K = len(theta), len(SCENARIOS)
    m, v = np.zeros(n), np.zeros(n)
    b1, b2 = 0.9, 0.999
    hist = []
    os.makedirs(os.path.join(REPO, "results", "figures"), exist_ok=True)
    print(f"ES eğitimi: {n} ağırlık, kuşak başına {2 * a.pairs + 2} aday x {K} senaryo")
    t0 = time.time()
    with Pool(min(8, max(1, (os.cpu_count() or 2) - 1))) as pool:
        for g in range(a.gens):
            seeds = 1000 + g * K + np.arange(K)            # her kuşak yeni eğitim haritaları
            eps = rng.normal(size=(a.pairs, n))
            cands = [theta + a.sigma * e for e in eps] + [theta - a.sigma * e for e in eps] + [theta, None]
            jobs = [(c, pw, f, int(s)) for c in cands for (pw, f), s in zip(SCENARIOS, seeds)]
            R = np.array(pool.map(evaluate, jobs, chunksize=1)).reshape(len(cands), K)
            F = R.mean(1)
            ranks = centered_ranks(F[:2 * a.pairs])
            grad = ((ranks[:a.pairs] - ranks[a.pairs:])[:, None] * eps).sum(0) / (2 * a.pairs * a.sigma)
            grad -= 0.005 * theta                          # ağırlıkları küçük tut (aşırı öğrenmeye karşı)
            m = b1 * m + (1 - b1) * grad
            v = b2 * v + (1 - b2) * grad ** 2
            theta = theta + a.lr * (m / (1 - b1 ** (g + 1))) / (np.sqrt(v / (1 - b2 ** (g + 1))) + 1e-8)
            row = dict(kusak=g + 1, ag_puani=round(float(F[-2]), 4), uzman_kurali=round(float(F[-1]), 4),
                       aday_ort=round(float(F[:-2].mean()), 4), aday_en_iyi=round(float(F[:-2].max()), 4),
                       sure_s=round(time.time() - t0))
            hist.append(row)
            print(f"  kuşak {g + 1:2d}/{a.gens}  ağ {row['ag_puani']:.3f}  uzman {row['uzman_kurali']:.3f}  "
                  f"aday ort {row['aday_ort']:.3f} en iyi {row['aday_en_iyi']:.3f}  ({row['sure_s']} s)", flush=True)
            np.savez(a.out, theta=theta, features=np.array(AI_FEATURES))
    with open(os.path.join(REPO, "results", "ai_es_deneme.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist[0]))
        w.writeheader()
        w.writerows(hist)
    plot(hist)
    print(f"Kaydedildi: {a.out}")


def plot(hist):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    g = [h["kusak"] for h in hist]
    ag = np.array([h["ag_puani"] for h in hist])
    uz = np.array([h["uzman_kurali"] for h in hist])
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(g, ag - uz, "o-", color="#1f77b4", label="yapay zekâ - uzman kuralı (aynı haritalar)")
    k = max(1, len(g) // 6)
    if len(g) >= k:
        smooth = np.convolve(ag - uz, np.ones(k) / k, mode="valid")
        ax.plot(g[k - 1:], smooth, "-", color="#d62728", lw=2.5, label=f"{k} kuşaklık ortalama")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("Eğitim kuşağı")
    ax.set_ylabel("Görev puanı farkı")
    ax.set_title("Yapay zekânın öğrenmesi (evrim stratejileri)")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(REPO, "results", "figures", "ai_es_deneme.png"), dpi=150)


if __name__ == "__main__":
    main()
