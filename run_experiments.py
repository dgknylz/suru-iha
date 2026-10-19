"""Toplu deneyler: her strateji x karıştırıcı gücü x saldırgan oranı x tohum.

Aynı tohum (seed) = aynı görev haritası, yani stratejiler birebir aynı koşulda
karşılaştırılır (eşleştirilmiş deney tasarımı).

    python run_experiments.py            # tam deney (30 tekrar)
    python run_experiments.py --quick    # hızlı deneme (5 tekrar)
Sonuç: results/results.csv
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
    strategy, power, spoof, seed = job
    world = World(make_config(strategy, power, spoof, seed))
    while not world.finished():
        world.step()
    row = dict(strategy=strategy, jammer_dbm=-1 if power is None else power, spoof=spoof, seed=seed)
    row.update(world.summary())
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true")
    p.add_argument("--seeds", type=int, default=30)
    p.add_argument("--out", default="results/results.csv")
    a = p.parse_args()
    seeds = range(5 if a.quick else a.seeds)
    jobs = list(itertools.product(STRATEGIES, POWERS, SPOOFS, seeds))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    print(f"{len(jobs)} simülasyon koşulacak...")
    t0 = time.time()
    rows = []
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        for k, row in enumerate(pool.imap_unordered(run_one, jobs), 1):
            rows.append(row)
            if k % 20 == 0 or k == len(jobs):
                el = time.time() - t0
                print(f"  {k}/{len(jobs)}  ({el:.0f}s, kalan ~{el / k * (len(jobs) - k):.0f}s)")
    rows.sort(key=lambda r: (r["strategy"], r["jammer_dbm"], r["spoof"], r["seed"]))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Kaydedildi: {a.out}")


if __name__ == "__main__":
    main()
