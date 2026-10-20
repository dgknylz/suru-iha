"""Yapay zekâ eğitimi: İHA'nın bir görevi başarma olasılığını kestiren sinir ağı (denetimli öğrenme).

1) Deneyim toplama: Dirençli sürü, eğitim haritalarında (seed 1000+) farklı karıştırma ve arıza
   koşullarında görev yapar. Bir İHA bir hedefe her yöneldiğinde 8 özellik kaydedilir (GPS, konum
   belirsizliği, karıştırma, uzaklık...). Sonuç: hedefi buldu (1) ya da bulamadı (0: arama tükendi,
   konumunu kaybedip bıraktı ya da yanlış "bitti" dedi). Başka İHA'ya devredilen denemeler sayılmaz.
2) Eğitim: 8 girdi -> 8 gizli nöron (tanh) -> 1 çıktı (sigmoid) ağ, lojistik kayıpla, Adam
   yöntemiyle eğitilir. Doğrulama haritalarındaki kayıp artmaya başlayınca durulur (aşırı öğrenmeye karşı).
3) Değerlendirme: Hiç görmediği test haritalarında ROC AUC ve doğruluk; uzman kuralının (karıştırma
   cezası + belirsizlik maliyeti) aynı işi ne kadar iyi yaptığıyla kıyaslanır.
Uçuşta (planner="ai") CBBA, kestirilen olasılıkla "beklenen ödülü" en büyütür:
    beklenen ödül = başarı olasılığı x değer x 0.99^(varış - görünme)

    python tools/train_ai.py              # veri toplama + eğitim (~10 dk, 8 çekirdek)
    python tools/train_ai.py --reuse      # kayıtlı veriyle sadece eğitim
Sonuç: suru/data/ai_politika.npz, results/ai_veri.npz, results/ai_egitim.csv, results/ai_egitim.txt,
       results/figures/ai_ogrenme.png, results/figures/ai_dogruluk.png
"""
import argparse
import csv
import itertools
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from suru import World, make_config  # noqa: E402
from suru.decision import AI_FEATURES, AI_WEIGHTS, AIValue  # noqa: E402

# Deneyim toplanan koşullar: (karıştırıcı gücü dBm, arıza sayısı). Hepsinde 6 yeni hedef belirir.
SCENARIOS = [(None, 0), (15.0, 0), (20.0, 0), (20.0, 3), (25.0, 0), (30.0, 0)]
# Verinin çeşitli olması için deneyimi üç farklı karar verici toplar
POLICIES = [dict(planner="cbba"), dict(planner="cbba", ew_valuation=False), dict(planner="greedy")]
SPLITS = {"egitim": range(1000, 1060), "dogrulama": range(1100, 1115), "test": range(1200, 1220)}
OUT = os.path.join(REPO, "results")


def collect(job):
    power, failures, seed, pol = job
    w = World(make_config("resilient", power, 0.0, seed, n_popup=6, failures=failures, log_attempts=True,
                          **POLICIES[pol]))
    while not w.finished():
        w.step()
    if not w.attempts:
        return np.zeros((0, len(AI_FEATURES))), np.zeros(0), np.zeros(0), np.zeros(0)
    F = np.array([a[0] for a in w.attempts])
    y = np.array([a[1] for a in w.attempts], float)
    rule = np.array([a[2] for a in w.attempts])
    return F, y, rule, np.full(len(y), -1.0 if power is None else power)


def gather(pool):
    data = {}
    for name, seeds in SPLITS.items():
        jobs = [(p, f, s, s % len(POLICIES)) for (p, f), s in itertools.product(SCENARIOS, seeds)]
        t0 = time.time()
        res = pool.map(collect, jobs, chunksize=1)
        data[name] = tuple(np.concatenate([r[k] for r in res]) for k in range(4))
        print(f"  {name}: {len(jobs)} uçuş, {len(data[name][1])} deneme, başarı %{data[name][1].mean() * 100:.1f} "
              f"({time.time() - t0:.0f} s)", flush=True)
    return data


# --------------------------------------------------------------- sinir ağı eğitimi (numpy)
def forward(th, F):
    net = AIValue(th)
    h = np.tanh(F @ net.W1 + net.b1)
    p = 1.0 / (1.0 + np.exp(-(h @ net.w2 + net.b2)))
    return net, h, np.clip(p, 1e-6, 1 - 1e-6)


def loss(th, F, y, l2):
    _, _, p = forward(th, F)
    n_w = AIValue.n_in * AIValue.n_hid
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)) + l2 * (th[:n_w] ** 2).sum())


def grad(th, F, y, l2):
    """Geri yayılım (backpropagation): kaybın her ağırlığa göre türevi."""
    net, h, p = forward(th, F)
    n = len(y)
    dz2 = (p - y) / n
    dw2, db2 = h.T @ dz2, dz2.sum()
    dz1 = np.outer(dz2, net.w2) * (1 - h ** 2)
    dW1, db1 = F.T @ dz1, dz1.sum(0)
    g = np.concatenate([dW1.ravel(), db1, dw2, [db2]])
    g[:AIValue.n_in * AIValue.n_hid] += 2 * l2 * th[:AIValue.n_in * AIValue.n_hid]
    return g


def auc(score, y):
    """ROC eğrisinin altındaki alan: rastgele seçilen bir başarılı deneme, rastgele seçilen bir
    başarısızdan daha yüksek puan alıyor mu? 0.5 = yazı tura, 1 = kusursuz."""
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    ranks[order] = np.arange(1, len(order) + 1)
    # eşit puanlara ortalama sıra
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):
        m = allv == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def train(data, epochs=1500, lr=0.01, l2=1e-4):
    Ftr, ytr = data["egitim"][0], data["egitim"][1]
    Fva, yva = data["dogrulama"][0], data["dogrulama"][1]
    th = AIValue.initial()
    m, v = np.zeros_like(th), np.zeros_like(th)
    best, best_th, hist, wait = np.inf, th.copy(), [], 0
    for e in range(1, epochs + 1):
        g = grad(th, Ftr, ytr, l2)
        m = 0.9 * m + 0.1 * g
        v = 0.999 * v + 0.001 * g * g
        th = th - lr * (m / (1 - 0.9 ** e)) / (np.sqrt(v / (1 - 0.999 ** e)) + 1e-8)
        if e % 10 == 0 or e == 1:
            lt, lv = loss(th, Ftr, ytr, 0), loss(th, Fva, yva, 0)
            hist.append(dict(tur=e, egitim_kaybi=round(lt, 5), dogrulama_kaybi=round(lv, 5),
                             dogrulama_auc=round(auc(forward(th, Fva)[2], yva), 4)))
            if lv < best - 1e-5:
                best, best_th, wait = lv, th.copy(), 0
            else:
                wait += 1
                if wait >= 30:                   # 300 turdur iyileşmiyor: erken durdur
                    break
    return best_th, hist


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reuse", action="store_true", help="results/ai_veri.npz varsa simülasyonu tekrar koşma")
    a = p.parse_args()
    os.makedirs(os.path.join(OUT, "figures"), exist_ok=True)
    path = os.path.join(OUT, "ai_veri.npz")
    if a.reuse and os.path.exists(path):
        z = np.load(path)
        data = {k: tuple(z[f"{k}_{i}"] for i in range(4)) for k in SPLITS}
    else:
        print("Deneyim toplanıyor (dirençli sürü, eğitim/doğrulama/test haritaları)...")
        with Pool(min(8, max(1, (os.cpu_count() or 2) - 1))) as pool:
            data = gather(pool)
        np.savez(path, **{f"{k}_{i}": data[k][i] for k in SPLITS for i in range(4)})

    th, hist = train(data)
    Fte, yte, rule_te, pw_te = data["test"]
    p_ai = forward(th, Fte)[2]
    res = dict(
        n_egitim=len(data["egitim"][1]), n_dogrulama=len(data["dogrulama"][1]), n_test=len(yte),
        basari_orani_test=float(yte.mean()),
        auc_yapay_zeka=auc(p_ai, yte), auc_uzman_kurali=auc(rule_te, yte),
        dogruluk_yapay_zeka=float(((p_ai > 0.5) == yte).mean()),
        dogruluk_hep_basarili=float(yte.mean()),
        kayip_yapay_zeka=loss(th, Fte, yte, 0), brier_yapay_zeka=float(((p_ai - yte) ** 2).mean()),
    )
    np.savez(AI_WEIGHTS, theta=th, features=np.array(AI_FEATURES))
    with open(os.path.join(OUT, "ai_egitim.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist[0]))
        w.writeheader()
        w.writerows(hist)
    lines = ["YAPAY ZEKÂ: görev başarı olasılığı kestirimi (test haritaları, eğitimde hiç görülmedi)", ""]
    lines += [f"  {k:24s} {v:.4f}" if isinstance(v, float) else f"  {k:24s} {v}" for k, v in res.items()]
    lines.append("\n  Koşula göre test (gerçek başarı / yapay zekânın ortalama kestirimi / AUC yapay zekâ / AUC uzman):")
    for pw in np.unique(pw_te):
        mk = pw_te == pw
        name = "karıştırma yok" if pw < 0 else f"{pw:.0f} dBm"
        lines.append(f"    {name:15s} n={mk.sum():4d}  gerçek %{yte[mk].mean() * 100:5.1f}  kestirim "
                     f"%{p_ai[mk].mean() * 100:5.1f}  AUC {auc(p_ai[mk], yte[mk]):.3f} / {auc(rule_te[mk], yte[mk]):.3f}")
    report = "\n".join(lines)
    with open(os.path.join(OUT, "ai_egitim.txt"), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    plot(hist, p_ai, rule_te, yte)
    print(f"Kaydedildi: {AI_WEIGHTS}")


def roc(score, y):
    thr = np.unique(score)[::-1]
    tpr = [((score >= t) & (y == 1)).sum() / max((y == 1).sum(), 1) for t in thr]
    fpr = [((score >= t) & (y == 0)).sum() / max((y == 0).sum(), 1) for t in thr]
    return np.r_[0, fpr, 1], np.r_[0, tpr, 1]


def plot(hist, p_ai, rule, y):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    e = [h["tur"] for h in hist]
    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    ax.plot(e, [h["egitim_kaybi"] for h in hist], lw=2, color="#378ADD", label="eğitim haritaları")
    ax.plot(e, [h["dogrulama_kaybi"] for h in hist], lw=2, color="#D85A30", label="doğrulama haritaları")
    ax.set_xlabel("Eğitim turu")
    ax.set_ylabel("Kayıp (lojistik, düşük = iyi)")
    ax.set_title("Yapay zekânın öğrenmesi: görev başarı olasılığı", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figures", "ai_ogrenme.png"))
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), dpi=150)
    ax = axes[0]
    for s, name, c in ((p_ai, "yapay zekâ", "#B5359A"), (rule, "uzman kuralı", "#378ADD")):
        fx, fy = roc(s, y)
        ax.plot(fx, fy, lw=2, color=c, label=f"{name} (AUC {auc(s, y):.2f})")
    ax.plot([0, 1], [0, 1], "k:", lw=1, label="yazı tura (AUC 0.50)")
    ax.set_xlabel("Yanlış alarm oranı (başarısızı başarılı sanma)")
    ax.set_ylabel("Doğru yakalama oranı")
    ax.set_title("ROC eğrisi (test haritaları)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax = axes[1]
    bins = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(p_ai, bins) - 1, 0, 9)
    xs, ys, ns = [], [], []
    for b in range(10):
        m = idx == b
        if m.sum() >= 5:
            xs.append(p_ai[m].mean())
            ys.append(y[m].mean())
            ns.append(m.sum())
    ax.plot([0, 1], [0, 1], "k:", lw=1, label="kusursuz kestirim")
    ax.scatter(xs, ys, s=[10 + n / 4 for n in ns], color="#B5359A", label="yapay zekâ (nokta boyu = örnek sayısı)")
    ax.set_xlabel("Kestirilen başarı olasılığı")
    ax.set_ylabel("Gerçekleşen başarı oranı")
    ax.set_title("Kalibrasyon: kestirim gerçekle örtüşüyor mu?", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figures", "ai_dogruluk.png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
