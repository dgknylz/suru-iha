"""Toplu deneyler.

Aynı tohum (seed) = aynı görev haritası, yani stratejiler birebir aynı koşulda
karşılaştırılır (eşleştirilmiş deney tasarımı).

    python run_experiments.py              # ana deney: strateji x karıştırıcı x saldırgan x 30 tekrar
    python run_experiments.py --swarm      # sürü deneyleri: İHA arızası ve röle
    python run_experiments.py --decision   # karar alma deneyleri: açgözlü / CBBA / yapay zekâ, yeni hedefler
    python run_experiments.py --quick      # hızlı deneme (5 tekrar)
Sonuç: results/results.csv, results/swarm.csv, results/decision.csv
"""
import argparse
import csv
import itertools
import os
import time
from multiprocessing import Pool

from suru import World, make_config, STRATEGIES

POWERS = [None, 10, 20, 30]   # None = karıştırıcı yok
SPOOFS = [0.0, 0.2]
# Karar alma deneylerinin koşulları: (karıştırıcı gücü, saldırgan oranı, arıza sayısı)
DECISION_CONDS = [(None, 0.0, 0), (20.0, 0.0, 0), (30.0, 0.0, 0), (None, 0.2, 0), (20.0, 0.0, 3)]
N_POPUP = 6                   # karar alma deneylerinde görev sırasında beliren yeni hedef sayısı


def run_one(job):
    exp, strategy, power, spoof, seed, extra = job
    world = World(make_config(strategy, power, spoof, seed, **extra))
    while not world.finished():
        world.step()
    c = world.cfg
    row = dict(experiment=exp, strategy=strategy, planner=c.planner, jammer_dbm=-1 if power is None else power,
               spoof=spoof, seed=seed, failures_cfg=c.failures, relay=int(bool(c.relay)), comm_range=c.comm_range,
               bundle_size=c.bundle_size, n_popup=c.n_popup)
    row.update(world.summary())
    return row


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
                    rows.append({k: (float(v) if k not in ("experiment", "strategy", "planner") else v)
                                 for k, v in r.items()})
    with Pool(min(workers, max(1, (os.cpu_count() or 2) - 1))) as pool:
        for k, row in enumerate(pool.imap_unordered(run_one, jobs), 1):
            rows.append(row)
            if k % 40 == 0 or k == len(jobs):
                el = time.time() - t0
                print(f"  {k}/{len(jobs)}  ({el:.0f}s, kalan ~{el / k * (len(jobs) - k):.0f}s)")
    rows.sort(key=lambda r: (r["experiment"], r["strategy"], r["planner"], r["jammer_dbm"], r["spoof"],
                             r["failures_cfg"], r["relay"], r["bundle_size"], r["seed"]))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Kaydedildi: {out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true")
    p.add_argument("--swarm", action="store_true", help="sürü deneyleri (arıza, röle)")
    p.add_argument("--decision", action="store_true", help="karar alma deneyleri (planlama, yeni hedefler)")
    p.add_argument("--no-ai", action="store_true", help="karar alma deneylerinde yapay zekâyı atla")
    p.add_argument("--ai-only", action="store_true",
                   help="yalnızca yapay zekâyı koş, sonucu mevcut karar alma dosyasına ekle (yeniden eğitim sonrası)")
    p.add_argument("--out", default=None, help="sonuç dosyası (varsayılanın yerine)")
    p.add_argument("--seeds", type=int, default=30)
    p.add_argument("--workers", type=int, default=8, help="paralel işlem sayısı")
    a = p.parse_args()
    seeds = range(5 if a.quick else a.seeds)
    if a.decision:
        run(jobs_decision(seeds, ai=not a.no_ai, ai_only=a.ai_only), a.out or "results/decision.csv", a.workers,
            merge=a.ai_only)
    elif a.swarm:
        run(jobs_swarm(seeds), a.out or "results/swarm.csv", a.workers)
    else:
        run(jobs_main(seeds), a.out or "results/results.csv", a.workers)


if __name__ == "__main__":
    main()
