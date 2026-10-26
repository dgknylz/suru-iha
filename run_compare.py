"""Yan yana karşılaştırma: aynı harita ve aynı elektronik harp senaryosunda iki sürüyü birlikte uçurur.
Sol ekran korumasız sürü (merkeziyetsiz ya da merkezi), sağ ekran EH dirençli sürü. Unity ekranı
otomatik olarak ikiye böler.

Örnekler:
    python run_compare.py                                   # 20 dBm sabit karıştırıcı
    python run_compare.py --jammer off --gps-spoof hizli    # GPS aldatma
    python run_compare.py --jammer off --spoof 0.2 --spoof-mode sneaky
    python run_compare.py --left centralized --jammer-mode hareketli

Unity kısayolları run_live.py ile aynıdır; F1/F2 sol tarafın mimarisini değiştirir (sağ hep dirençli).
Z arızası ve Y yeni hedefi iki tarafa birebir aynı uygulanır (aynı İHA düşer, hedef aynı yerde belirir).
Sol sürü UDP 5065'ten, sağ sürü 5067'den yayınlanır.
"""
import argparse
import time

from run_live import (Controls, GPS_SPOOFS, JAMMER_MODES, PLANNERS, PLANNER_NAMES, STRATEGY_NAMES, add_custom_args,
                      apply, custom_kw, custom_state, describe)
from suru import World, make_config
from suru.bridge import UnityBridge


def parse():
    p = argparse.ArgumentParser(description="Sürü İHA yan yana karşılaştırma (Unity'ye iki yayın)")
    p.add_argument("--left", default="decentralized", choices=["centralized", "decentralized"],
                   help="sol ekrandaki korumasız mimari")
    p.add_argument("--jammer", default="20", help="karıştırıcı gücü dBm, ya da 'off'")
    p.add_argument("--jammer-mode", default="sabit", choices=JAMMER_MODES)
    p.add_argument("--gps-spoof", default="", choices=GPS_SPOOFS)
    p.add_argument("--spoof", type=float, default=0.0)
    p.add_argument("--spoof-mode", default="naive", choices=["naive", "sneaky"])
    p.add_argument("--planner", default="cbba", choices=list(PLANNERS))
    p.add_argument("--popups", type=int, default=4)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--loop", action="store_true")
    p.add_argument("--formation", default="V", choices=["V", "hat", "kol", "halka"])
    p.add_argument("--drones", type=int, default=10)
    p.add_argument("--tasks", type=int, default=20)
    p.add_argument("--failures", type=int, default=0, help="görev sırasında arızalanacak İHA sayısı (iki tarafta aynı)")
    add_custom_args(p)
    return p.parse_args()


def make_world(st, strategy, a):
    return World(make_config(strategy, st["power"], st["spoof"], st["seed"], formation=st["formation"],
                             planner=st["planner"], n_popup=a.popups, live_reserve=8, jammer_mode=st["jammer_mode"],
                             gps_spoof=st["gps_spoof"], spoof_mode=st["spoof_mode"], n_drones=a.drones,
                             n_tasks=a.tasks, failures=a.failures, **custom_kw(st)))


def main():
    a = parse()
    st = {"strategy": a.left, "power": None if a.jammer.lower() == "off" else float(a.jammer), "spoof": a.spoof,
          "seed": a.seed, "planner": a.planner, "jammer_mode": a.jammer_mode, "gps_spoof": a.gps_spoof,
          "spoof_mode": a.spoof_mode, "formation": a.formation, **custom_state(a)}
    left, right = UnityBridge(port=5065), UnityBridge(port=5067)
    try:
        ctl = Controls(5066)
    except OSError:
        ctl = None
        print("Uyarı: komut portu 5066 açılamadı, Unity'den kontrol kapalı.")
    print("Karşılaştırma: sol korumasız, sağ EH dirençli. Unity ekranı ikiye böler. Çıkış: Ctrl+C")

    while True:
        if st["strategy"] == "resilient":            # sol taraf dirençli olamaz
            st["strategy"] = a.left
        worlds = [make_world(st, st["strategy"], a), make_world(st, "resilient", a)]
        print(f"\n== sol: {STRATEGY_NAMES[st['strategy']]} | sağ: {STRATEGY_NAMES['resilient']} | "
              f"{describe(st).split(' | ', 1)[1]} ==")
        steps = max(1, round(a.speed / a.fps / worlds[0].cfg.dt))
        done_at, changed, reported = None, False, [False, False]
        while not changed:
            t0 = time.perf_counter()
            over = [w.flight_over() for w in worlds]
            for k, w in enumerate(worlds):
                if not over[k]:
                    for _ in range(steps):
                        w.step()
                if w.finished() and not reported[k]:
                    reported[k] = True
                    s = w.summary()
                    print(f"{'Sol' if k == 0 else 'Sağ'} ({STRATEGY_NAMES[w.cfg.strategy]}) görev bitti: "
                          f"tamamlama %{s['completion'] * 100:.0f}, puan {s['score'] * 100:.0f}/100, "
                          f"süre {s['mission_time']:.0f}s, yanlış tamamlama {s['false_done']}")
            if all(over):
                done_at = done_at or time.perf_counter()
                if a.loop and time.perf_counter() - done_at > 3.0:
                    st["seed"] += 1
                    changed = True
            for k, (w, b) in enumerate(zip(worlds, (left, right))):
                f = w.frame()
                f["ctl"] = {"power": -1 if st["power"] is None else st["power"], "spoof": st["spoof"],
                            "spoofMode": st["spoof_mode"], "seed": st["seed"], "finished": int(w.flight_over()),
                            "missionDone": int(w.finished()), "side": "sol" if k == 0 else "sag"}
                b.send(f)
            for cmd in (ctl.poll() if ctl else []):
                c = cmd.get("cmd")
                if c == "fail":                          # iki tarafta aynı İHA düşer
                    cand = [i for i in range(worlds[0].N) if worlds[0].alive[i] and worlds[1].alive[i]
                            and not worlds[0].spoofer[i] and worlds[0].phase[i] != 6]
                    if len(cand) > 1:
                        i = int(worlds[0].rng.choice(cand))
                        for w in worlds:
                            w.fail_drone(i)
                        print(f"  İHA-{i + 1} iki tarafta da arızalandı")
                elif c == "popup":                       # hedef iki tarafta aynı yerde belirir
                    t = worlds[0].add_popup()
                    if t >= 0:
                        worlds[1].add_popup(xy=worlds[0].tasks[t, :2].copy())
                        print(f"  yeni hedef eklendi (#{t})")
                elif c == "formation":
                    for w in worlds:
                        w.cycle_formation()
                    st["formation"] = worlds[0].form_kind
                elif c == "strategy" and cmd.get("value") == "resilient":
                    continue                             # sağ zaten dirençli
                else:
                    changed |= apply(cmd, st, worlds[0])
            time.sleep(max(0.0, 1.0 / a.fps - (time.perf_counter() - t0)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nÇıkıldı.")
