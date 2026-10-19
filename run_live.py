"""Canlı simülasyon: sürüyü gerçek zamanlı koşturur ve her kareyi Unity'ye yollar.

Örnekler:
    python run_live.py                                  # dirençli sürü, 20 dBm karıştırıcı
    python run_live.py --strategy centralized --jammer 30
    python run_live.py --strategy decentralized --spoof 0.2 --speed 3
    python run_live.py --jammer off --loop

Unity'den klavyeyle senaryo değiştirilebilir (UDP 5066 komut kanalı):
    F1/F2/F3 mimari, +/- karıştırıcı gücü, X saldırgan aç/kapa, N yeni harita.
Görev bitince simülasyon yeni komut bekler (--loop verilirse yeni haritayla kendiliğinden başlar).
Çıkmak için Ctrl+C.
"""
import argparse
import json
import socket
import time

from suru import World, make_config, STRATEGY_NAMES
from suru.bridge import UnityBridge

POWER_STEPS = [None, 10.0, 20.0, 30.0]   # karıştırıcı kademeleri (None = kapalı)


def parse():
    p = argparse.ArgumentParser(description="Sürü İHA canlı simülasyon (Unity'ye yayın)")
    p.add_argument("--strategy", default="resilient", choices=list(STRATEGY_NAMES))
    p.add_argument("--jammer", default="20", help="karıştırıcı gücü dBm, ya da 'off'")
    p.add_argument("--spoof", type=float, default=0.0, help="ele geçirilmiş İHA oranı (0-1)")
    p.add_argument("--drones", type=int, default=10)
    p.add_argument("--tasks", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--speed", type=float, default=1.0, help="zaman hızlandırma çarpanı")
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--port", type=int, default=5065)
    p.add_argument("--cmd-port", type=int, default=5066, help="Unity'den komut dinlenen port")
    p.add_argument("--loop", action="store_true", help="bitince yeni tohumla yeniden başla")
    return p.parse_args()


class Controls:
    """Unity'den gelen klavye komutlarını dinler (bloklamaz)."""

    def __init__(self, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", port))
        self.sock.setblocking(False)

    def poll(self):
        cmds = []
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
                cmds.append(json.loads(data.decode("utf-8")))
            except BlockingIOError:
                return cmds
            except (ConnectionResetError, json.JSONDecodeError):
                continue


def apply(cmd, st):
    """Komutu senaryo durumuna uygular. Değişiklik olduysa True döner (dünya yeniden kurulur)."""
    c = cmd.get("cmd")
    if c == "strategy" and cmd.get("value") in STRATEGY_NAMES:
        st["strategy"] = cmd["value"]
    elif c == "jammer":
        i = POWER_STEPS.index(st["power"]) if st["power"] in POWER_STEPS else 2
        st["power"] = POWER_STEPS[max(0, min(len(POWER_STEPS) - 1, i + int(cmd.get("step", 0))))]
    elif c == "spoof":
        st["spoof"] = 0.0 if st["spoof"] > 0 else 0.2
    elif c == "restart":
        st["seed"] += 1
    else:
        return False
    return True


def describe(st):
    p = "kapalı" if st["power"] is None else f"{st['power']:.0f} dBm"
    return (f"{STRATEGY_NAMES[st['strategy']]} | karıştırıcı: {p} | "
            f"saldırgan: %{st['spoof'] * 100:.0f} | harita {st['seed']}")


def main():
    a = parse()
    st = {"strategy": a.strategy, "power": None if a.jammer.lower() == "off" else float(a.jammer),
          "spoof": a.spoof, "seed": a.seed}
    bridge = UnityBridge(port=a.port)
    try:
        ctl = Controls(a.cmd_port)
    except OSError:
        ctl = None
        print(f"Uyarı: komut portu {a.cmd_port} açılamadı, Unity'den kontrol kapalı.")
    print("Unity'de: F1/F2/F3 mimari, +/- karıştırıcı, X saldırgan, N yeni harita. Çıkış: Ctrl+C")

    while True:
        cfg = make_config(st["strategy"], st["power"], st["spoof"], st["seed"], n_drones=a.drones, n_tasks=a.tasks)
        world = World(cfg)
        print(f"\n== {describe(st)} ==")
        steps_per_frame = max(1, round(a.speed / a.fps / cfg.dt))
        last_print, done_at, changed = 0.0, None, False

        def send():
            f = world.frame()
            f["ctl"] = {"power": -1 if st["power"] is None else st["power"], "spoof": st["spoof"], "seed": st["seed"],
                        "finished": int(world.finished())}
            bridge.send(f)
            return f

        while not changed:
            t0 = time.perf_counter()
            if not world.finished():
                for _ in range(steps_per_frame):
                    world.step()
                if world.finished():
                    s = world.summary()
                    print(f"Bitti: tamamlama %{s['completion'] * 100:.0f}, süre {s['mission_time']:.0f}s, "
                          f"yanlış tamamlama {s['false_done']}, tekrar ziyaret {s['redundant']}")
                    done_at = time.perf_counter()
            elif a.loop and time.perf_counter() - done_at > 3.0:
                st["seed"] += 1
                changed = True
            f = send()
            if world.t - last_print >= 5.0 and not world.finished():
                last_print = world.t
                m = f["m"]
                print(f"t={world.t:6.1f}s  görev {m['done']}/{m['total']}  paket iletim %{m['pdr'] * 100:4.0f}"
                      f"  GPS'siz {m['gpsLost']}  konum hatası {m['locErr']:.1f} m")
            for cmd in (ctl.poll() if ctl else []):
                changed |= apply(cmd, st)
            time.sleep(max(0.0, 1.0 / a.fps - (time.perf_counter() - t0)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nÇıkıldı.")
