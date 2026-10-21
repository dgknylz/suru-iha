"""Tanıtım videosu 1/3: uçuşları kaydeder, çekim senaryosunu ve kartları üretir.

    python tools/record_film.py [--out C:/SuruIHA/film] [--hazirlayan "Ad Soyad"]

1) Üç uçuş kare kare kaydedilir (her kare = 0,1 s simülasyon; video 30 kare/s -> 3x hızlı):
     ana       : EH dirençli sürü, 20 dBm karıştırıcı, görev sırasında 4 yeni hedef
     aldatma   : yan yana, korumasız (sol) vs dirençli (sağ), hızlı GPS aldatma
     iki       : yan yana, korumasız (sol) vs dirençli (sağ), iki karıştırıcı
2) Kayıtlardaki önemli anlar (alana varış, yeni hedef, GPS kaybı ve arama, karıştırıcının bulunması,
   dönüş) otomatik bulunur, çekimler bunlara göre kurulur.
3) film.json (Unity film modu için) ve kurgu.json (Blender kurgusu için) yazılır.
4) Başlık, sonuç ve kapanış kartları (1920x1080 PNG) results/*.csv verisinden çizilir.
Sonra: tools/render_film.ps1 (Unity'de kareleri çeker) ve tools/make_video.py (Blender'da MP4).
"""
import argparse
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from suru import World, make_config  # noqa: E402
from suru.world import PHASE_NAMES  # noqa: E402

FPS = 30


def record(cfgs, path_names, out, reuse=False):
    """Dünyaları adım adım birlikte koşturur, her kareyi JSON satırı olarak yazar. Döndürür: kare listeleri.
    reuse: kayıtlar zaten varsa yeniden uçurmadan okur (simülasyon belirlenimci, aynı tohum = aynı uçuş)."""
    paths = [os.path.join(out, p) for p in path_names]
    if reuse and all(os.path.exists(p) for p in paths):
        return [[json.loads(l) for l in open(p, encoding="utf-8")] for p in paths], None
    worlds = [World(c) for c in cfgs]
    files = [open(os.path.join(out, p), "w", encoding="utf-8") for p in path_names]
    frames = [[] for _ in worlds]
    while not all(w.flight_over() for w in worlds):
        for w, f, fr in zip(worlds, files, frames):
            if not w.flight_over():
                w.step()
            d = w.frame()
            d["ctl"] = {"power": -1, "spoof": w.cfg.spoof_fraction, "spoofMode": w.cfg.spoof_mode, "seed": w.cfg.seed,
                        "finished": int(w.flight_over()), "missionDone": int(w.finished())}
            f.write(json.dumps(d, separators=(",", ":")) + "\n")
            fr.append(d)
    for f in files:
        f.close()
    return frames, worlds


def first(frames, cond, start=0):
    for k in range(start, len(frames)):
        if cond(frames[k]):
            return k
    return None


def events(fr):
    ph = lambda name: (lambda f: f["phase"] == name)
    e = {"transit": first(fr, ph("intikal")) or 0, "area": first(fr, ph("gorev")) or 0}
    e["popup"] = first(fr, lambda f: any(0 <= t["age"] < 0.15 for t in f["tasks"]), e["area"])
    e["search"] = first(fr, lambda f: any(d["mode"] == 1 for d in f["drones"]), e["area"])
    e["search_drone"] = next((d["id"] for d in fr[e["search"]]["drones"] if d["mode"] == 1), 0) if e["search"] else 0
    e["gpsloss"] = first(fr, lambda f: any(d["gps"] == 0 and d["phase"] == 2 for d in f["drones"]), e["area"])
    e["locate"] = first(fr, lambda f: 0 <= f["m"].get("jamErr", -1) < 80)
    e["back"] = first(fr, ph("donus"), e["area"]) or len(fr) - 400
    e["end"] = len(fr)
    return e


def shot(a, k0, k1, cam, caption, b=None, follow=0, yaw=None, labels=None, **kw):
    # tepe kamerası: tek sürüde tüm alan görünsün, ikiye bölünmüş ekranda İHA'lar seçilebilsin diye daha alçak
    s = {"a": a, "from": int(max(k0, 0)), "to": int(k1), "cam": cam, "follow": int(follow), "caption": caption,
         "height": 450.0 if b else 600.0}
    if b:
        s["b"] = b
        s["labels"] = labels or ["Korumasız", "EH dirençli"]
    if yaw is not None:
        s["yaw"] = float(yaw)
    s.update(kw)
    return s


def cards(out, hazirlayan):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    os.makedirs(os.path.join(out, "kartlar"), exist_ok=True)
    BG, FG, ACC = "#0b1218", "#e8eef3", "#4fd1a0"
    COL = {"centralized": "#D85A30", "decentralized": "#378ADD", "resilient": "#1D9E75"}
    NAMES = {"centralized": "Merkezi", "decentralized": "Merkeziyetsiz (korumasız)", "resilient": "EH dirençli"}

    def canvas():
        fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
        return fig

    def save(fig, name):
        fig.savefig(os.path.join(out, "kartlar", name), facecolor=BG)
        plt.close(fig)

    fig = canvas()
    fig.text(0.5, 0.62, "Sürü İHA'larda Otonom Sürü Zekâsı ile\nKarar Alma ve Elektronik Harp Direnci",
             ha="center", va="center", fontsize=54, color=FG, fontweight="bold", linespacing=1.3)
    fig.text(0.5, 0.40, "TÜBİTAK 2204-A Lise Öğrencileri Araştırma Projeleri", ha="center", fontsize=28, color=ACC)
    fig.text(0.5, 0.31, "Python simülasyonu  ·  Unity HDRP 3D görselleştirme  ·  yaklaşık 6000 deney uçuşu",
             ha="center", fontsize=22, color="#9fb3c2")
    if hazirlayan:
        fig.text(0.5, 0.18, f"Hazırlayan: {hazirlayan}", ha="center", fontsize=24, color=FG)
    save(fig, "baslik.png")

    ew = pd.read_csv(os.path.join(REPO, "results", "ew.csv"))
    ew = ew[ew.experiment == "eh"]
    names = list(dict.fromkeys(ew.tag))
    fig = canvas()
    ax = fig.add_axes([0.07, 0.2, 0.9, 0.62], facecolor=BG)
    x = np.arange(len(names))
    for j, s in enumerate(("centralized", "decentralized", "resilient")):
        v = [ew[(ew.tag == n) & (ew.strategy == s)].completion.mean() * 100 for n in names]
        ax.bar(x + (j - 1) * 0.27, v, 0.25, color=COL[s], label=NAMES[s])
    ax.set_xticks(x, [n.replace(" ", "\n", 1) for n in names], fontsize=15, color=FG)
    ax.tick_params(colors=FG, labelsize=15)
    ax.set_ylabel("Görev tamamlama (%)", fontsize=20, color=FG)
    ax.set_ylim(0, 105)
    for sp in ax.spines.values():
        sp.set_color("#3a4a56")
    ax.grid(axis="y", alpha=0.2)
    ax.legend(fontsize=17, loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=3, frameon=False, labelcolor=FG)
    fig.text(0.5, 0.93, "Elektronik harp altında görev başarısı (her biri 30 uçuşun ortalaması)", ha="center",
             fontsize=30, color=FG, fontweight="bold")
    fig.text(0.5, 0.04, "Dirençli sürü 9 senaryonun hepsinde %98-100 tamamlıyor; puan farkı her senaryoda anlamlı (Wilcoxon p < 0,000001)",
             ha="center", fontsize=19, color=ACC)
    save(fig, "sonuc_eh.png")

    ab = pd.read_csv(os.path.join(REPO, "results", "ablation.csv"))
    sys.path.insert(0, REPO)
    from analyze import MECH_NAMES, ablation_table
    conds, variants, D, P = ablation_table(ab)
    fig = canvas()
    ax = fig.add_axes([0.24, 0.12, 0.62, 0.72])
    lim = np.nanmax(np.abs(D))
    ax.imshow(D, cmap="RdBu", vmin=-lim, vmax=lim, aspect="auto")
    for i in range(len(variants)):
        for j in range(len(conds)):
            if np.isfinite(D[i, j]):
                star = "*" if P[i, j] < 0.05 else ""
                v = int(round(D[i, j]))
                ax.text(j, i, (f"{v:+d}" if v else "0") + star, ha="center", va="center", fontsize=15,
                        color="white" if abs(D[i, j]) > 0.5 * lim else "black")
    ax.set_xticks(range(len(conds)), conds, fontsize=14, color=FG, rotation=12)
    ax.set_yticks(range(len(variants)), ["hepsi kapalı (korumasız)"] + [MECH_NAMES[v[1:]] for v in variants[1:]],
                  fontsize=15, color=FG)
    fig.text(0.5, 0.93, "Ablasyon: hangi mekanizma hangi saldırıya karşı işe yarıyor?", ha="center", fontsize=30,
             color=FG, fontweight="bold")
    fig.text(0.5, 0.88, "Mekanizma kapatılınca görev puanı kaç puan düşüyor (kırmızı = önemli, * = anlamlı)", ha="center",
             fontsize=19, color="#9fb3c2")
    save(fig, "sonuc_ablasyon.png")

    dc = pd.read_csv(os.path.join(REPO, "results", "decision.csv"))
    pl = dc[(dc.experiment == "plan") & (dc.jammer_dbm == -1) & (dc.spoof == 0) & (dc.failures_cfg == 0)]
    fig = canvas()
    ax = fig.add_axes([0.08, 0.2, 0.4, 0.58], facecolor=BG)
    for j, s in enumerate(("centralized", "decentralized", "resilient")):
        g = pl[(pl.strategy == s) & (pl.planner == "greedy")].score.mean() * 100
        c = pl[(pl.strategy == s) & (pl.planner == "cbba")].score.mean() * 100
        ax.bar(j - 0.2, g, 0.38, color="#6b7680", label="açgözlü tek görev" if j == 0 else None)
        ax.bar(j + 0.2, c, 0.38, color=COL[s], label="CBBA paket planlama" if j == 0 else None)
    ax.set_xticks(range(3), ["Merkezi\n(SGA)", "Merkeziyetsiz", "EH dirençli"], fontsize=17, color=FG)
    ax.set_ylim(60, 86)
    ax.tick_params(colors=FG, labelsize=15)
    ax.set_ylabel("Görev puanı (0-100)", fontsize=19, color=FG)
    for sp in ax.spines.values():
        sp.set_color("#3a4a56")
    ax.legend(fontsize=15, frameon=False, labelcolor=FG, loc="upper left")
    txt = ("Otonom karar alma\n\n"
           "• CBBA: her İHA 3 hedeflik rota planlar,\n   komşularıyla lidersiz uzlaşır\n"
           "• Görev puanı her mimaride anlamlı artıyor\n   (karıştırma yokken +4 ile +10 puan)\n"
           "• Katedilen yol %17-37 kısalıyor\n\n"
           "Yapay zekâ\n\n"
           "• Sinir ağı görev başarısını tahmin ediyor\n"
           "• ROC AUC 0,978 (uzman kuralı 0,948)\n"
           "• Doğruluk %92,8")
    fig.text(0.55, 0.78, txt, fontsize=22, color=FG, va="top", linespacing=1.45)
    fig.text(0.5, 0.92, "Karar alma: paket planlama ve yapay zekâ (30 uçuşun ortalaması)", ha="center", fontsize=30,
             color=FG, fontweight="bold")
    save(fig, "sonuc_karar.png")

    fig = canvas()
    fig.text(0.5, 0.78, "Sonuç", ha="center", fontsize=48, color=FG, fontweight="bold")
    lines = ["Lidersiz sürü zekâsı + CBBA ile otonom karar alma + birbirini tamamlayan EH savunmaları",
             "20 dBm karıştırmada %100 (diğerleri %87)  ·  30 dBm'de %67 (diğerleri %12-17)",
             "GPS aldatmada %99 (diğerleri %51-61)  ·  sinsi saldırganların %100'ü dışlandı",
             "Merkeziyetsizlik tek başına yetmiyor: korumasız sürü saldırgana karşı %0'a düşüyor"]
    for i, l in enumerate(lines):
        fig.text(0.5, 0.62 - i * 0.09, l, ha="center", fontsize=25, color=FG if i else ACC)
    fig.text(0.5, 0.14, "Tüm kod, veriler ve deneyler açık: python run_experiments.py · analyze.py", ha="center",
             fontsize=19, color="#9fb3c2")
    save(fig, "kapanis.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"C:\SuruIHA\film")
    ap.add_argument("--hazirlayan", default="")
    ap.add_argument("--reuse", action="store_true", help="var olan uçuş kayıtlarını kullan, yalnızca senaryo ve kartları yaz")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    print("1/3 ana uçuş kaydediliyor (dirençli, 20 dBm)...", flush=True)
    (fa,), _ = record([make_config("resilient", 20.0, 0.0, 3, n_popup=4)], ["ana.jsonl"], a.out, a.reuse)
    e = events(fa)
    print("   olaylar:", e, flush=True)
    print("2/3 GPS aldatma karşılaştırması kaydediliyor...", flush=True)
    (gl, gr), _ = record([make_config(s, None, 0.0, 2, n_popup=4, gps_spoof="hizli")
                          for s in ("decentralized", "resilient")], ["aldatma_sol.jsonl", "aldatma_sag.jsonl"], a.out, a.reuse)
    eg = events(gr)
    print("3/3 iki karıştırıcı karşılaştırması kaydediliyor...", flush=True)
    (il, ir), _ = record([make_config(s, 20.0, 0.0, 4, n_popup=4, jammer_mode="iki")
                          for s in ("decentralized", "resilient")], ["iki_sol.jsonl", "iki_sag.jsonl"], a.out, a.reuse)
    ei = events(ir)

    A = "ana.jsonl"
    sk = e["search"] or e["gpsloss"] or e["area"] + 300
    shots = [
        shot(A, 0, e["transit"] + 120, "sinematik", "Sürü üsten kalkar ve havada toplanır. Lider yok: her İHA kendi kararını verir.",
             yaw=200, plans=False),
        shot(A, e["transit"] + 120, e["area"] - 30, "sinematik",
             "V düzeninde intikal: İHA'lar sanal liderin konumunda uzlaşır (konsensüs), yuvalar Macar algoritmasıyla dağıtılır.",
             yaw=120),
        shot(A, e["area"] - 30, e["area"] + 240, "tepe",
             "CBBA: her İHA 3 hedeflik rotasını planlar ve komşularıyla uzlaşır. Renkli çizgiler = planlar, halka sayısı = öncelik."),
    ]
    if e["popup"]:
        shots.append(shot(A, e["popup"] - 15, e["popup"] + 165, "tepe",
                          "Yeni hedef belirdi (mor dalga): sürü saniyeler içinde kimin gideceğine kendi karar verir."))
    shots.append(shot(A, sk - 120, sk + 240, "takip",
                      "Karıştırıcı GPS'i keser (kırmızı ışık). Dirençli İHA hedefi görmeden 'bitti' demez, spiral çizerek arar.",
                      follow=e["search_drone"], ghosts=True))
    if e["locate"]:
        k = max(e["locate"], e["area"] + 60)
        shots.append(shot(A, k, k + 180, "tepe",
                          "Sürü, ölçtüğü karıştırma gücünden karıştırıcının yerini bulur (turuncu nişangâh) ve kesilecek bölgeyi önceden bilir."))
    shots.append(shot(A, e["back"] - 60, min(e["back"] + 330, e["end"]), "sinematik",
                      "Görevler bitince sürü toplanma noktasında halka olur, V düzeninde üsse döner ve iner.", yaw=330))
    shots.append(shot("aldatma_sol.jsonl", eg["area"] - 90, eg["area"] + 240, "sinematik",
                      "Aynı harita, aynı GPS aldatıcı (mavi kubbe). Solda korumasız sürü, sağda EH dirençli sürü.",
                      b="aldatma_sag.jsonl", yaw=60))
    shots.append(shot("aldatma_sol.jsonl", eg["area"] + 240, eg["area"] + 600, "tepe",
                      "Korumasız İHA'lar (pembe) sahte konuma inanıp hedefi bulduğunu sanıyor. Dirençli İHA'lar aldatmayı fark ediyor (sarı).",
                      b="aldatma_sag.jsonl"))
    shots.append(shot("iki_sol.jsonl", ei["area"] + 60, ei["area"] + 450, "tepe",
                      "İki karıştırıcı: korumasız sürü görevlerin %39'unu, dirençli sürü %99,5'ini yapıyor (30 uçuşun ortalaması).",
                      b="iki_sag.jsonl"))
    film = {"outDir": os.path.join(a.out, "kareler"), "width": 1920, "height": 1080, "fps": FPS,
            "shots": [{k: v for k, v in s.items() if k not in ("caption", "labels")} for s in shots]}
    with open(os.path.join(a.out, "film.json"), "w", encoding="utf-8") as f:
        json.dump(film, f, ensure_ascii=False, indent=1)
    kurgu = {"fps": FPS, "frames": os.path.join(a.out, "kareler"), "cards": os.path.join(a.out, "kartlar"),
             "before": [["baslik.png", 5.0]],
             "shots": [{"frames": s["to"] - s["from"], "caption": s["caption"], "labels": s.get("labels")}
                       for s in shots],
             "after": [["sonuc_eh.png", 7.0], ["sonuc_karar.png", 7.0], ["sonuc_ablasyon.png", 7.0], ["kapanis.png", 6.0]],
             "out": os.path.join(REPO, "sunum", "tanitim_videosu.mp4")}
    with open(os.path.join(a.out, "kurgu.json"), "w", encoding="utf-8") as f:
        json.dump(kurgu, f, ensure_ascii=False, indent=1)
    cards(a.out, a.hazirlayan)
    n = sum(s["to"] - s["from"] for s in shots)
    print(f"Hazır: {len(shots)} çekim, {n} kare ({n / FPS:.0f} s) + kartlar -> {a.out}")


if __name__ == "__main__":
    main()
