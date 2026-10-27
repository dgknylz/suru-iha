"""Arazi yüksekliği: Unity'deki 3D arazinin birebir aynısı.

Unity sahne kurulumu (SuruIHASetup) yükseklik haritasını suru/data/arazi_yukseklik.bin olarak
dışa aktarır. Böylece İHA'lar Python simülasyonunda da tepeleri "görür": araziyi takip eder,
görev noktaları yerden belli yükseklikte olur. Dosya yoksa arazi düz (0 m) kabul edilir.

Koordinatlar: x = doğu, y = kuzey (m). Dönen değer: arazinin z yüksekliği (m).
"""
import json
import os

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


REGIONS = {"ova": "arazi_yukseklik.bin", "kar": "arazi_yukseklik_kar.bin"}   # Unity'deki bölgeler


class Terrain:
    def __init__(self, path=None, flat=False, region="ova"):
        if region not in REGIONS:
            raise ValueError(f"bilinmeyen bölge: {region} (seçenekler: {', '.join(REGIONS)})")
        path = path or os.path.join(DATA, REGIONS[region])
        if region != "ova" and not flat and not os.path.exists(path):
            raise FileNotFoundError(f"{path} yok: Unity'de sahneyi kurup yükseklik haritasını kopyalayın (tools/full_build.ps1)")
        meta = os.path.splitext(path)[0] + ".json"
        if flat or not os.path.exists(path):
            self.h = None
            return
        m = json.load(open(meta, encoding="utf-8"))
        self.n, self.origin, self.step = int(m["n"]), float(m["origin"]), float(m["step"])
        self.h = np.fromfile(path, dtype="<f4").reshape(self.n, self.n).astype(np.float64)

    @property
    def flat(self):
        return self.h is None

    def height(self, x, y):
        """Çift doğrusal (bilinear) aradeğerleme. x, y skaler ya da dizi olabilir."""
        if self.h is None:
            return np.zeros(np.broadcast(x, y).shape) if np.ndim(x) or np.ndim(y) else 0.0
        u = np.clip((np.asarray(x, float) - self.origin) / self.step, 0, self.n - 1.001)
        v = np.clip((np.asarray(y, float) - self.origin) / self.step, 0, self.n - 1.001)
        i, j = np.floor(u).astype(int), np.floor(v).astype(int)
        fu, fv = u - i, v - j
        h = self.h
        top = h[j, i] * (1 - fu) + h[j, i + 1] * fu
        bot = h[j + 1, i] * (1 - fu) + h[j + 1, i + 1] * fu
        return top * (1 - fv) + bot * fv

    def max_along(self, p0, p1, samples=8):
        """İki nokta arasındaki en yüksek arazi (her satır bir İHA). p0, p1: (N, 2)."""
        t = np.linspace(0, 1, samples)[None, :, None]
        pts = p0[:, None, :] * (1 - t) + p1[:, None, :] * t
        return self.height(pts[..., 0], pts[..., 1]).max(axis=1)
