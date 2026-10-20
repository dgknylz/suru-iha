"""Toplu deneyler.

Aynı tohum (seed) = aynı görev haritası, yani stratejiler birebir aynı koşulda
karşılaştırılır (eşleştirilmiş deney tasarımı).

    python run_experiments.py              # ana deney: strateji x karıştırıcı x saldırgan x 30 tekrar
    python run_experiments.py --swarm      # sürü deneyleri: İHA arızası ve röle
    python run_experiments.py --quick      # hızlı deneme (5 tekrar)
Sonuç: results/results.csv, results/swarm.csv
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


def run_one(job):
    exp, strategy, power, spoof, seed, extra = job
    world = World(make_config(strategy, power, spoof, seed, **extra))
    while not world.finished():
        world.step()
    row = dict(experiment=exp, strategy=strategy, jammer_dbm=-1 if power is None else power, spoof=spoof, seed=seed,
               failures_cfg=extra.get("failures", 0), relay=int(bool(extra.get("relay", False))),
               comm_range=extra.get("comm_range", 300.0))
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


def run(jobs, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print(f"{len(jobs)} simülasyon koşulacak -> {out}")
    t0 = time.time()
    rows = []
    with Pool(min(8, max(1, (os.cpu_count() or 2) - 1))) as pool:   # her işlem ~400 MB bellek kullanır
        for k, row in enumerate(pool.imap_unordered(run_one, jobs), 1):
            rows.append(row)
            if k % 40 == 0 or k == len(jobs):
                el = time.time() - t0
                print(f"  {k}/{len(jobs)}  ({el:.0f}s, kalan ~{el / k * (len(jobs) - k):.0f}s)")
    rows.sort(key=lambda r: (r["experiment"], r["strategy"], r["jammer_dbm"], r["spoof"], r["failures_cfg"],
                             r["relay"], r["seed"]))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Kaydedildi: {out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true")
    p.add_argument("--swarm", action="store_true", help="sürü deneyleri (arıza, röle)")
    p.add_argument("--seeds", type=int, default=30)
    a = p.parse_args()
    seeds = range(5 if a.quick else a.seeds)
    if a.swarm:
        run(jobs_swarm(seeds), "results/swarm.csv")
    else:
        run(jobs_main(seeds), "results/results.csv")


if __name__ == "__main__":
    main()
