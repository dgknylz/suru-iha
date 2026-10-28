"""Canlı simülasyon: sürüyü gerçek zamanlı koşturur ve her kareyi Unity'ye yollar.

Örnekler:
    python run_live.py                                  # dirençli sürü, 20 dBm karıştırıcı
    python run_live.py --strategy centralized --jammer 30
    python run_live.py --strategy decentralized --spoof 0.2 --speed 3
    python run_live.py --jammer off --loop
    python run_live.py --planner greedy --popups 0      # eski yöntem, yeni hedef yok

Unity'den klavyeyle senaryo değiştirilebilir (UDP 5066 komut kanalı):
    F1/F2/F3 mimari, F4 planlama algoritması (açgözlü / CBBA / yapay zekâ), +/- karıştırıcı gücü,
    M karıştırıcı türü (sabit / hareketli / iki / nokta / tepe), U GPS aldatıcı (yok / hızlı / yavaş),
    X saldırgan (yok / saf / sinsi), N yeni harita, V düzen tipi (V / hat / kol / halka),
    Z bir İHA'yı arızalandır, Y görev alanına yeni bir hedef ekle.

Kendi senaryon (Unity'deki "Kendi senaryon" sekmesi; negatif sayılar için = ile yazılır):
    python run_live.py --jammer 20 --jammers=-150,300;200,500 --jammer-band nokta
    python run_live.py --jammer off --gps-spoof hizli --spoofer=100,400 --drones 8 --tasks 15 --failures 1
Sürü kalkar, düzende intikal eder, görevleri paylaşır, toplanır, düzende döner ve iner.
İniş bitince simülasyon yeni komut bekler (--loop verilirse yeni haritayla kendiliğinden başlar).
Çıkmak için Ctrl+C.
"""
import argparse
import json
import socket
import time

from suru import World, make_config, PLANNERS, PLANNER_NAMES, STRATEGY_NAMES
from suru.config import parse_points
from suru.bridge import UnityBridge

POWER_STEPS = [None, 10.0, 20.0, 30.0]   # karıştırıcı kademeleri (None = kapalı)
JAMMER_MODES = ["sabit", "hareketli", "iki", "nokta", "tepe", "sirt"]
GPS_SPOOFS = ["", "hizli", "yavas"]
SPOOF_STEPS = [(0.0, "naive"), (0.2, "naive"), (0.2, "sneaky")]   # saldırgan: yok -> saf -> sinsi


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
    p.add_argument("--formation", default="V", choices=["V", "hat", "kol", "halka"], help="intikal düzeni")
    p.add_argument("--failures", type=int, default=0, help="görev sırasında arızalanacak İHA sayısı")
    p.add_argument("--relay", action="store_true", help="bağlantı koruma rölesini aç (merkeziyetsiz)")
    p.add_argument("--planner", default="cbba", choices=list(PLANNERS), help="görev paylaşım algoritması")
    p.add_argument("--popups", type=int, default=4, help="görev sırasında beliren yeni hedef sayısı")
    p.add_argument("--jammer-mode", default="sabit", choices=JAMMER_MODES, help="karıştırıcı senaryosu")
    p.add_argument("--gps-spoof", default="", choices=GPS_SPOOFS, help="GPS aldatıcı: '' | hizli | yavas")
    p.add_argument("--spoof-mode", default="naive", choices=["naive", "sneaky"], help="saldırgan davranışı")
    add_custom_args(p)
    return p.parse_args()


def add_custom_args(p):
    """Kendi senaryon: karıştırıcıların ve GPS aldatıcının yeri (run_compare.py de kullanır)."""
    p.add_argument("--jammers", default="", help="karıştırıcıların yeri 'x,y;x,y' (m); verilirse --jammer-mode yok sayılır")
    p.add_argument("--jammer-band", default="genis", choices=["genis", "nokta"], help="özel karıştırıcıların türü")
    p.add_argument("--spoofer", default="", help="GPS aldatıcının yeri 'x,y' (m); --gps-spoof ile birlikte")
    p.add_argument("--region", default="ova", choices=["ova", "kar", "nehir", "divrigi", "gokpinar", "deniz"],
                   help="harita: Orta Anadolu ovası, karlı dağlar, Kızılırmak (Sivas), Divriği (Sivas), Gökpınar Gölü (Gürün), Akdeniz kıyısı")


def custom_state(a):
    sp = parse_points(a.spoofer)
    return {"jammer_xy": parse_points(a.jammers), "jammer_band": a.jammer_band, "spoofer_xy": sp[0] if sp else None,
            "region": a.region}


def custom_kw(st):
    return {"jammer_xy": st.get("jammer_xy"), "jammer_band": st.get("jammer_band", "genis"),
            "spoofer_xy": st.get("spoofer_xy"), "region": st.get("region", "ova")}


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


def apply(cmd, st, world):
    """Komutu uygular. Senaryo değiştiyse True döner (dünya yeniden kurulur).
    Düzen ve arıza komutları uçuşu yeniden başlatmadan, çalışan dünyaya uygulanır."""
    c = cmd.get("cmd")
    if c == "formation":
        world.cycle_formation()
        st["formation"] = world.form_kind
        print(f"  düzen: {world.form_kind}")
        return False
    if c == "fail":
        world.fail_drone()
        print("  bir İHA arızalandı")
        return False
    if c == "popup":
        t = world.add_popup()
        print(f"  yeni hedef eklendi (#{t})" if t >= 0 else "  yedek hedef kalmadı")
        return False
    if c == "strategy" and cmd.get("value") in STRATEGY_NAMES:
        st["strategy"] = cmd["value"]
    elif c == "planner":
        st["planner"] = PLANNERS[(PLANNERS.index(st["planner"]) + 1) % len(PLANNERS)]
    elif c == "jammer":
        i = POWER_STEPS.index(st["power"]) if st["power"] in POWER_STEPS else 2
        st["power"] = POWER_STEPS[max(0, min(len(POWER_STEPS) - 1, i + int(cmd.get("step", 0))))]
    elif c == "spoof":
        k = SPOOF_STEPS.index((st["spoof"], st["spoof_mode"])) if (st["spoof"], st["spoof_mode"]) in SPOOF_STEPS else 0
        st["spoof"], st["spoof_mode"] = SPOOF_STEPS[(k + 1) % len(SPOOF_STEPS)]
    elif c == "jammer_mode":
        if st.get("jammer_xy"):              # özel yerleşimden hazır senaryolara geçilir
            st["jammer_xy"] = None
        else:
            st["jammer_mode"] = JAMMER_MODES[(JAMMER_MODES.index(st["jammer_mode"]) + 1) % len(JAMMER_MODES)]
        if st["power"] is None:
            st["power"] = 20.0
    elif c == "gps_spoof":
        st["gps_spoof"] = GPS_SPOOFS[(GPS_SPOOFS.index(st["gps_spoof"]) + 1) % len(GPS_SPOOFS)]
    elif c == "restart":
        st["seed"] += 1
    else:
        return False
    return True


def describe(st):
    mode = f"özel ({len(st['jammer_xy'])} karıştırıcı)" if st.get("jammer_xy") else st["jammer_mode"]
    p = "kapalı" if st["power"] is None else f"{st['power']:.0f} dBm {mode}"
    g = f" | GPS aldatma: {st['gps_spoof']}" if st["gps_spoof"] else ""
    sp = f"%{st['spoof'] * 100:.0f} {'sinsi' if st['spoof_mode'] == 'sneaky' else 'saf'}" if st["spoof"] else "yok"
    return (f"{STRATEGY_NAMES[st['strategy']]} | {PLANNER_NAMES[st['planner']]} | karıştırıcı: {p}{g} | "
            f"saldırgan: {sp} | harita {st['seed']}")


def main():
    a = parse()
    st = {"strategy": a.strategy, "power": None if a.jammer.lower() == "off" else float(a.jammer),
          "spoof": a.spoof, "seed": a.seed, "planner": a.planner, "jammer_mode": a.jammer_mode,
          "gps_spoof": a.gps_spoof, "spoof_mode": a.spoof_mode, **custom_state(a)}
    bridge = UnityBridge(port=a.port)
    try:
        ctl = Controls(a.cmd_port)
    except OSError:
        ctl = None
        print(f"Uyarı: komut portu {a.cmd_port} açılamadı, Unity'den kontrol kapalı.")
    print("Unity'de: F1/F2/F3 mimari, F4 planlama, +/- karıştırıcı gücü, M karıştırıcı türü, U GPS aldatıcı, "
          "X saldırgan, N yeni harita, V düzen, Z arıza, Y yeni hedef. Çıkış: Ctrl+C")
    st["formation"] = a.formation

    while True:
        cfg = make_config(st["strategy"], st["power"], st["spoof"], st["seed"], n_drones=a.drones, n_tasks=a.tasks,
                          formation=st["formation"], failures=a.failures, relay=a.relay, planner=st["planner"],
                          n_popup=a.popups, live_reserve=8, jammer_mode=st["jammer_mode"],
                          gps_spoof=st["gps_spoof"], spoof_mode=st["spoof_mode"], **custom_kw(st))
        world = World(cfg)
        print(f"\n== {describe(st)} ==")
        steps_per_frame = max(1, round(a.speed / a.fps / cfg.dt))
        last_print, done_at, changed, reported = 0.0, None, False, False

        def send():
            f = world.frame()
            f["ctl"] = {"power": -1 if st["power"] is None else st["power"], "spoof": st["spoof"],
                        "spoofMode": st["spoof_mode"], "seed": st["seed"],
                        "finished": int(world.flight_over()), "missionDone": int(world.finished())}
            bridge.send(f)
            return f

        while not changed:
            t0 = time.perf_counter()
            if not world.flight_over():
                for _ in range(steps_per_frame):
                    world.step()
                if world.finished() and not reported:
                    reported = True
                    s = world.summary()
                    print(f"Görev bitti: tamamlama %{s['completion'] * 100:.0f}, puan {s['score'] * 100:.0f}/100, "
                          f"süre {s['mission_time']:.0f}s, yanlış tamamlama {s['false_done']}, "
                          f"tekrar ziyaret {s['redundant']}. Sürü üsse dönüyor...")
                if world.flight_over():
                    print(f"Sürü indi (t={world.t:.0f}s).")
                    done_at = time.perf_counter()
            elif a.loop and time.perf_counter() - done_at > 3.0:
                st["seed"] += 1
                changed = True
            f = send()
            if world.t - last_print >= 5.0 and not world.flight_over():
                last_print = world.t
                m = f["m"]
                print(f"t={world.t:6.1f}s  {f['phase']:9s} görev {m['done']}/{m['total']}  puan {m['score'] * 100:3.0f}"
                      f"  paket %{m['pdr'] * 100:3.0f}"
                      f"  bağlantı %{m['conn'] * 100:3.0f}  düzen hatası {m['formErr']:4.1f} m  GPS'siz {m['gpsLost']}")
            for cmd in (ctl.poll() if ctl else []):
                changed |= apply(cmd, st, world)
            time.sleep(max(0.0, 1.0 / a.fps - (time.perf_counter() - t0)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nÇıkıldı.")
