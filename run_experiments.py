"""Toplu deneyler.

Aynı tohum (seed) = aynı görev haritası, yani stratejiler birebir aynı koşulda
karşılaştırılır (eşleştirilmiş deney tasarımı).

    python run_experiments.py              # ana deney: strateji x karıştırıcı x saldırgan x 30 tekrar
    python run_experiments.py --swarm      # sürü deneyleri: İHA arızası ve röle
    python run_experiments.py --decision   # karar alma deneyleri: açgözlü / CBBA / yapay zekâ, yeni hedefler
    python run_experiments.py --ew         # elektronik harp: hareketli/iki/nokta/tepe karıştırıcı, GPS aldatma, sinsi saldırgan
    python run_experiments.py --tune       # ayar: parametre duyarlılığı (AYRI ayar haritalarında, seed 500+)
    python run_experiments.py --ablation   # ablasyon: dirençli mekanizmaları tek tek kapatıp katkısını ölçmek
    python run_experiments.py --scaling    # ölçekleme: 5 / 10 / 20 İHA
    python run_experiments.py --quick      # hızlı deneme (5 tekrar)
Sonuç: results/results.csv, swarm.csv, decision.csv, ew.csv, tune.csv, ablation.csv, scaling.csv
"""
import argparse
import csv
import itertools
import os
import time
from multiprocessing import Pool

from suru import SimConfig, World, make_config, STRATEGIES

POWERS = [None, 10, 20, 30]   # None = karıştırıcı yok
SPOOFS = [0.0, 0.2]
# Karar alma deneylerinin koşulları: (karıştırıcı gücü, saldırgan oranı, arıza sayısı)
DECISION_CONDS = [(None, 0.0, 0), (20.0, 0.0, 0), (30.0, 0.0, 0), (None, 0.2, 0), (20.0, 0.0, 3)]
N_POPUP = 6                   # karar alma deneylerinde görev sırasında beliren yeni hedef sayısı
# Elektronik harp senaryoları: ad -> (karıştırıcı gücü, saldırgan oranı, ek ayarlar)
EW_SCENARIOS = {
    "sabit 20 dBm": (20.0, 0.0, {}),
    "hareketli 20 dBm": (20.0, 0.0, {"jammer_mode": "hareketli"}),
    "iki karıştırıcı 20 dBm": (20.0, 0.0, {"jammer_mode": "iki"}),
    "nokta 25 dBm": (25.0, 0.0, {"jammer_mode": "nokta"}),
    "tepede 25 dBm": (25.0, 0.0, {"jammer_mode": "tepe"}),
    "sırt arkasında 30 dBm": (30.0, 0.0, {"jammer_mode": "sirt"}),
    "GPS aldatma hızlı": (None, 0.0, {"gps_spoof": "hizli"}),
    "GPS aldatma yavaş": (None, 0.0, {"gps_spoof": "yavas"}),
    "sinsi saldırgan %20": (None, 0.2, {"spoof_mode": "sneaky"}),
}
# Ablasyonda kapatılan dirençli mekanizmalar
MECHANISMS = ("jam_map", "long_ttl", "avoid", "coop_loc", "search", "recover", "trust", "localize", "fhss",
              "spoof_detect", "valuation")
ABLATION_CONDS = ("sabit 20 dBm", "hareketli 20 dBm", "nokta 25 dBm", "GPS aldatma hızlı", "sinsi saldırgan %20")
TUNE_SEEDS = range(500, 520)  # ayar haritaları: test haritalarından (0-29) ayrı


def run_one(job):
    exp, strategy, power, spoof, seed, extra = job
    extra = dict(extra)
    tag = extra.pop("_tag", "")
    t0 = time.time()
    world = World(make_config(strategy, power, spoof, seed, **extra))
    while not world.finished():
        world.step()
    c = world.cfg
    row = dict(experiment=exp, tag=tag, strategy=strategy, planner=c.planner,
               jammer_dbm=-1 if power is None else power, jammer_mode=c.jammer_mode if power is not None else "",
               gps_spoof=c.gps_spoof, spoof=spoof, spoof_mode=c.spoof_mode if spoof else "", seed=seed,
               n_drones=c.n_drones, failures_cfg=c.failures, relay=int(bool(c.relay)), comm_range=c.comm_range,
               bundle_size=c.bundle_size, n_popup=c.n_popup, terrain_radio=int(c.terrain_radio))
    row.update(world.summary())
    row["wall_s"] = round(time.time() - t0, 2)
    return row


def jobs_ew(seeds):
    jobs = []
    for (name, (p, sp, kw)), s, seed in itertools.product(EW_SCENARIOS.items(), STRATEGIES, seeds):
        jobs.append(("eh", s, p, sp, seed, dict(kw, n_popup=N_POPUP, _tag=name)))
    # Arazinin radyoya etkisi: aynı senaryolar arazi gölgesi kapalıyken
    for name, s, seed in itertools.product(("sabit 20 dBm", "tepede 25 dBm", "sırt arkasında 30 dBm"), STRATEGIES,
                                           seeds):
        p, sp, kw = EW_SCENARIOS[name]
        jobs.append(("arazi", s, p, sp, seed, dict(kw, n_popup=N_POPUP, terrain_radio=False, _tag=name)))
    return jobs


def jobs_tune(seeds=TUNE_SEEDS):
    """Parametre duyarlılığı: biri değişirken diğerleri varsayılan. Ayar haritalarında koşulur."""
    grid = {"claim_ttl_jam": (10.0, 30.0, 60.0), "recover_sigma": (15.0, 25.0, 40.0),
            "jam_penalty": (0.0, 150.0, 300.0), "jam_cell_ttl": (45.0, 90.0, 180.0)}
    conds = ("sabit 20 dBm", "hareketli 20 dBm", "GPS aldatma hızlı")
    default = SimConfig()
    jobs = []
    for name, seed in itertools.product(conds, seeds):
        p, sp, kw = EW_SCENARIOS[name]
        jobs.append(("ayar", "resilient", p, sp, seed, dict(kw, n_popup=N_POPUP, _tag=f"{name}|varsayılan")))
        for param, values in grid.items():
            for v in values:
                if v != getattr(default, param):
                    jobs.append(("ayar", "resilient", p, sp, seed, dict(kw, n_popup=N_POPUP, **{param: v},
                                                                        _tag=f"{name}|{param}={v:g}")))
    return jobs


def jobs_ablation(seeds):
    jobs = []
    for name, seed in itertools.product(ABLATION_CONDS + ("sabit 30 dBm",), seeds):
        p, sp, kw = EW_SCENARIOS.get(name, (30.0, 0.0, {}))
        base = dict(kw, n_popup=N_POPUP)
        jobs.append(("ablasyon", "resilient", p, sp, seed, dict(base, _tag=f"{name}|tam")))
        jobs.append(("ablasyon", "decentralized", p, sp, seed, dict(base, _tag=f"{name}|hiçbiri")))
        for mech in MECHANISMS:
            jobs.append(("ablasyon", "resilient", p, sp, seed, dict(base, **{"ew_" + mech: False},
                                                                    _tag=f"{name}|-{mech}")))
    return jobs


def jobs_scaling(seeds):
    jobs = []
    for n, s, (p, sp), seed in itertools.product((5, 10, 20), STRATEGIES, ((None, 0.0), (20.0, 0.0), (None, 0.2)),
                                                 seeds):
        jobs.append(("olcek", s, p, sp, seed, {"n_drones": n, "n_tasks": 2 * n, "n_popup": 6}))
    return jobs


def jobs_main(seeds):
    return [("ana", s, p, sp, seed, {}) for s, p, sp, seed in itertools.product(STRATEGIES, POWERS, SPOOFS, seeds)]


def jobs_swarm(seeds):
    jobs = []
    # 1) Üye kaybı: görev sırasında 0 / 2 / 4 İHA arızalanıp düşer
    for s, p, f, seed in itertools.product(STRATEGIES, (None, 20.0), (0, 2, 4), seeds):
        jobs.append(("ariza", s, p, 0.0, seed, {"failures": f}))
    # 2) Bağlantı koruma rölesi: kısa haberleşme menzilinde aç / kapa
    for s, r, seed in itertools.product(("decentralized", "resilient"), (False, True), seeds):
        jobs.append(("role", s, None, 0.0, seed, {"relay": r, "comm_range": 180.0}))
    return jobs


def jobs_decision(seeds, ai=True, ai_only=False):
    jobs = []
    # 1) Planlama algoritması: açgözlü tek görev / CBBA (merkezide SGA) / CBBA + yapay zekâ
    planners = ("ai",) if ai_only else ("greedy", "cbba", "ai") if ai else ("greedy", "cbba")
    for s, pl, (p, sp, f), seed in itertools.product(STRATEGIES, planners, DECISION_CONDS, seeds):
        if pl == "ai" and s != "resilient":
            continue
        jobs.append(("plan", s, p, sp, seed, {"planner": pl, "n_popup": N_POPUP, "failures": f}))
    # Kontrol: görev değerlendirmede hiçbir EH kuralı yok (uzman kuralı ve yapay zekâ bununla kıyaslanır)
    if ai or ai_only:
        for (p, sp, f), seed in itertools.product(DECISION_CONDS, seeds):
            jobs.append(("degerleme", "resilient", p, sp, seed, {"planner": "cbba", "n_popup": N_POPUP, "failures": f,
                                                                  "ew_valuation": False}))
    if ai_only:
        return jobs
    # 2) Paket büyüklüğü (CBBA'da bir İHA'nın aynı anda planladığı görev sayısı); 1 = tek görevli CBBA
    for L, p, seed in itertools.product((1, 2, 3, 4, 6), (None, 20.0), seeds):
        jobs.append(("paket", "resilient", p, 0.0, seed, {"planner": "cbba", "n_popup": N_POPUP, "bundle_size": L}))
    return jobs


def run(jobs, out, workers=8, merge=False):
    """merge=True: dosyadaki eski satırları korur, yalnızca bu koşuların planlayıcısına ait satırları değiştirir
    (ör. yapay zekâ yeniden eğitilince sadece onu yeniden test etmek için)."""
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print(f"{len(jobs)} simülasyon koşulacak -> {out}")
    t0 = time.time()
    rows = []
    if merge and os.path.exists(out):
        new = {(j[0], j[5].get("planner")) for j in jobs}
        with open(out, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if (r["experiment"], r["planner"]) not in new:
                    rows.append({k: _num(v) for k, v in r.items()})
    with Pool(min(workers, max(1, (os.cpu_count() or 2) - 1))) as pool:
        for k, row in enumerate(pool.imap_unordered(run_one, jobs), 1):
            rows.append(row)
            if k % 40 == 0 or k == len(jobs):
                el = time.time() - t0
                print(f"  {k}/{len(jobs)}  ({el:.0f}s, kalan ~{el / k * (len(jobs) - k):.0f}s)")
    rows.sort(key=lambda r: (r["experiment"], str(r.get("tag", "")), r["strategy"], r["planner"], r["jammer_dbm"],
                             r["spoof"], r["n_drones"], r["failures_cfg"], r["relay"], r["bundle_size"], r["seed"]))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Kaydedildi: {out}")


def _num(v):
    try:
        return float(v)
    except ValueError:
        return v


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true")
    p.add_argument("--swarm", action="store_true", help="sürü deneyleri (arıza, röle)")
    p.add_argument("--decision", action="store_true", help="karar alma deneyleri (planlama, yeni hedefler)")
    p.add_argument("--no-ai", action="store_true", help="karar alma deneylerinde yapay zekâyı atla")
    p.add_argument("--ai-only", action="store_true",
                   help="yalnızca yapay zekâyı koş, sonucu mevcut karar alma dosyasına ekle (yeniden eğitim sonrası)")
    p.add_argument("--ew", action="store_true", help="elektronik harp senaryoları")
    p.add_argument("--tune", action="store_true", help="parametre duyarlılığı (ayar haritaları)")
    p.add_argument("--ablation", action="store_true", help="dirençli mekanizmaların ablasyonu")
    p.add_argument("--scaling", action="store_true", help="5 / 10 / 20 İHA")
    p.add_argument("--out", default=None, help="sonuç dosyası (varsayılanın yerine)")
    p.add_argument("--seeds", type=int, default=30)
    p.add_argument("--workers", type=int, default=8, help="paralel işlem sayısı")
    a = p.parse_args()
    seeds = range(5 if a.quick else a.seeds)
    if a.ew:
        run(jobs_ew(seeds), a.out or "results/ew.csv", a.workers)
    elif a.tune:
        run(jobs_tune(TUNE_SEEDS[:5] if a.quick else TUNE_SEEDS), a.out or "results/tune.csv", a.workers)
    elif a.ablation:
        run(jobs_ablation(range(5 if a.quick else min(a.seeds, 12))), a.out or "results/ablation.csv", a.workers)
    elif a.scaling:
        run(jobs_scaling(range(5 if a.quick else min(a.seeds, 20))), a.out or "results/scaling.csv", a.workers)
    elif a.decision:
        run(jobs_decision(seeds, ai=not a.no_ai, ai_only=a.ai_only), a.out or "results/decision.csv", a.workers,
            merge=a.ai_only)
    elif a.swarm:
        run(jobs_swarm(seeds), a.out or "results/swarm.csv", a.workers)
    else:
        run(jobs_main(seeds), a.out or "results/results.csv", a.workers)


if __name__ == "__main__":
    main()
