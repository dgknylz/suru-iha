"""Sürü zekâsının geometri ve grafik araçları.

Düzen (formasyon) uçuşu lidersizdir: gerçek bir lider İHA yoktur. Her İHA, düzenin
merkezindeki "sanal lider"in rota üzerindeki ilerlemesini (s) kendisi tahmin eder ve
komşularıyla uzlaşma (konsensüs) yaparak bu tahmini ortaklaştırır:

    s_i  <-  s_i + g * ortalama_j( s_j - s_i )      (j: i'nin duyduğu komşular)

Sonra kendi yuvasına (sanal lider + düzendeki sabit konumu) uçar. Haberleşme
karıştırılırsa uzlaşma bozulur, tahminler ayrışır ve düzen dağılır: bu, elektronik
harbin sürü davranışına etkisini doğrudan gösterir.

Ayrıca Reynolds (1987) sürü kuralları uygulanır:
    ayrışma   : çok yaklaşan komşudan uzaklaş (çarpışma önleme)
    hizalanma : komşuların ortalama hızına uy
    uyum      : komşuların ortasına doğru hafifçe çekil
"""
import numpy as np

FORMATIONS = ("V", "hat", "kol", "halka")
FORMATION_NAMES = {"V": "V (kama)", "hat": "hat", "kol": "kol", "halka": "halka"}


def formation_offsets(kind, n, spacing):
    """Düzendeki yuvalar: her satır (ileri, sağ) metre. Düzenin ortası (0, 0)'dadır."""
    off = np.zeros((n, 2))
    for k in range(n):
        if kind == "V":
            r = (k + 1) // 2
            side = 1.0 if k % 2 else -1.0
            off[k] = (-0.8 * r * spacing, side * r * spacing)
        elif kind == "hat":
            off[k] = (0.0, (k - (n - 1) / 2) * spacing)
        elif kind == "kol":
            off[k] = (-k * spacing, 0.0)
        else:
            radius = max(15.0, spacing * n / (2 * np.pi))
            a = 2 * np.pi * k / max(n, 1)
            off[k] = (radius * np.cos(a), radius * np.sin(a))
    if kind in ("V", "kol"):
        off[:, 0] -= off[:, 0].mean()       # düzenin ağırlık merkezi sanal liderde olsun
    return off


def place(center, heading, offsets):
    """Düzen yuvalarını dünyaya yerleştirir. center (2,), heading (2,) birim vektör."""
    fwd = np.asarray(heading, float)
    right = np.array([fwd[1], -fwd[0]])
    return center[None, :] + offsets[:, :1] * fwd[None, :] + offsets[:, 1:] * right[None, :]


class Path:
    """Doğru parçalarından oluşan rota. s: rota üzerindeki mesafe (m)."""

    def __init__(self, points):
        self.p = np.asarray(points, float)
        seg = np.linalg.norm(np.diff(self.p, axis=0), axis=1)
        self.cum = np.concatenate([[0.0], np.cumsum(seg)])
        self.length = float(self.cum[-1])

    def at(self, s):
        s = float(np.clip(s, 0.0, self.length))
        k = int(np.clip(np.searchsorted(self.cum, s, side="right") - 1, 0, len(self.p) - 2))
        d = self.p[k + 1] - self.p[k]
        n = np.linalg.norm(d)
        u = d / n if n > 1e-9 else np.array([0.0, 1.0])
        return self.p[k] + u * (s - self.cum[k]), u


def connected(adj):
    """Komşuluk matrisi (bool, NxN) tek parça mı? (genişlik öncelikli arama)"""
    n = len(adj)
    if n <= 1:
        return True
    seen = np.zeros(n, bool)
    seen[0] = True
    frontier = [0]
    while frontier:
        nxt = np.nonzero(adj[frontier].any(axis=0) & ~seen)[0]
        seen[nxt] = True
        frontier = list(nxt)
    return bool(seen.all())


def largest_component(adj):
    """En büyük bağlı grubun düğüm oranı (1.0 = herkes tek ağda)."""
    n = len(adj)
    if n == 0:
        return 1.0
    left = np.ones(n, bool)
    best = 0
    while left.any():
        start = int(np.argmax(left))
        seen = np.zeros(n, bool)
        seen[start] = True
        frontier = [start]
        while frontier:
            nxt = np.nonzero(adj[frontier].any(axis=0) & ~seen)[0]
            seen[nxt] = True
            frontier = list(nxt)
        best = max(best, int(seen.sum()))
        left &= ~seen
    return best / n


def reynolds(pos, vel, mask, radius, w_align, w_cohesion):
    """Hizalanma + uyum katkısı (yatay, m/s). pos/vel: (N, 2), mask: kurala katılanlar."""
    out = np.zeros_like(pos)
    d = np.linalg.norm(pos[:, None] - pos[None, :], axis=2)
    nb = (d < radius) & mask[None, :] & mask[:, None]
    np.fill_diagonal(nb, False)
    cnt = nb.sum(1)
    has = cnt > 0
    if has.any():
        mean_v = (nb[has] @ vel) / cnt[has, None]
        mean_p = (nb[has] @ pos) / cnt[has, None]
        out[has] = w_align * (mean_v - vel[has]) + w_cohesion * (mean_p - pos[has])
    return out
