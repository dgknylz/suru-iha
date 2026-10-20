"""Belirli bir anda simülasyon karesini JSON olarak kaydeder (Unity önizleme render'ı için).

    python tools/dump_frame.py cikti.json [saniye] [strateji] [karistirici_dBm]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from suru import World, make_config  # noqa: E402

out = sys.argv[1]
t_end = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
strategy = sys.argv[3] if len(sys.argv) > 3 else "resilient"
power = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0
w = World(make_config(strategy, power, 0.0, 1, n_popup=4))
while w.t < t_end and not w.finished():
    w.step()
with open(out, "w", encoding="utf-8") as f:
    json.dump(w.frame(), f)
print("kare:", out, "t=", round(w.t, 1))
