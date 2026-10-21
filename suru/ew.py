"""Elektronik harp: karıştırıcılar, GPS aldatıcılar ve sürünün karıştırıcıyı bulması.

Karıştırıcı türleri
  genis : 2,4 GHz bandının tamamına (83,5 MHz) ve GPS L1'e gürültü basar ("barrage").
  nokta : gücünü haberleşme kanalına (20 MHz) yığar, kanalda 10*log10(83,5/20) = 6,2 dB daha
          güçlüdür; GPS'e dokunmaz. Frekans atlamalı (FHSS) haberleşmede paketlerin yalnızca
          20/83,5 = %24'ü karıştırılan kanala düşer. Geniş banda karşı FHSS işe yaramaz.

GPS aldatıcı (spoofer)
  Yerdeki verici, yarıçapı içine giren İHA'nın GPS alıcısını sahte ama inandırıcı bir sinyalle
  ele geçirir ve bildirdiği konumu yavaşça bir yöne sürükler ("drag-off" saldırısı). Alıcı
  "GPS sağlam" sanır; İHA gerçekte başka yerdeyken kendini hedefte zanneder.
  Tespit (dirençli strateji):
    1) IMU tutarlılığı: İHA son 10 s'de ne kadar yer değiştirdiğini kendi ataletsel ölçeriyle bilir.
       GPS'in söylediği yer değiştirme bundan IMU hatasının 3 katından fazla saparsa GPS'e güvenmez.
       Hızlı sürükleme birkaç saniyede yakalanır; yavaş sürükleme IMU hatasının içinde kalır.
    2) Komşu menzili: İHA'lar birbirine olan uzaklığı telsizle ölçer (iki yönlü menzil, ±1 m).
       GPS konumlarından hesaplanan uzaklıklar ölçülenle tutmuyorsa (komşuların çoğunda) GPS sahtedir.

Karıştırıcı konum bulma
  Her İHA ölçtüğü karıştırma gücünü (konum, dBm) kaydeder, ölçümler dedikoduyla yayılır.
  Model: ölçülen = P - PL(mesafe). Her aday konum için en iyi P kapalı formda bulunur
  (dB'de ortalama), kalan hata en küçük olan aday seçilir (ızgara araması + ince ayar).
  Tek kaynak modeli kötü uyarsa iki kaynaklı model denenir (güçler mW'da toplanır).
"""
import numpy as np

from .swarm import Path

SPOT_GAIN_DB = 10.0 * np.log10(83.5 / 20.0)   # nokta karıştırıcının kanaldaki fazladan gücü
FHSS_HIT = 20.0 / 83.5                        # FHSS'te karıştırılan kanala düşen paket oranı


class Jammer:
    def __init__(self, d, terrain):
        p = tuple(d["pos"])
        self.power = float(d["power_dbm"])
        self.band = d.get("band", "genis")
        self.agl = float(p[2]) if len(p) > 2 else 15.0
        self.speed = float(d.get("speed", 0.0))
        self.path = Path(d["route"]) if d.get("route") else None
        self.closed = bool(self.path) and np.allclose(d["route"][0], d["route"][-1])
        self.s, self.dir = 0.0, 1.0
        self.xy = np.array(p[:2], float)
        self.vel = np.zeros(3)
        self.terrain = terrain
        self.pos = np.r_[self.xy, terrain.height(*self.xy) + self.agl]

    @property
    def moving(self):
        return self.path is not None and self.speed > 0

    @property
    def comm_power(self):
        """Haberleşme kanalına düşen güç (dBm)."""
        return self.power + (SPOT_GAIN_DB if self.band == "nokta" else 0.0)

    def step(self, dt):
        if not self.moving:
            return
        L = self.path.length
        self.s += self.speed * dt * self.dir
        if self.closed:
            self.s %= L                          # kapalı rota: tur atar
        elif self.s >= L or self.s <= 0:         # açık rota: sonunda geri döner (devriye)
            self.s = float(np.clip(self.s, 0, L))
            self.dir *= -1
        p, u = self.path.at(self.s)
        self.xy = np.asarray(p, float)
        self.vel = np.r_[np.asarray(u) * self.speed * self.dir, 0.0]
        self.pos = np.r_[self.xy, self.terrain.height(*self.xy) + self.agl]


class GpsSpoofer:
    def __init__(self, d):
        self.xy = np.array(d["pos"][:2], float)
        self.radius = float(d["radius"])
        self.drag = float(d["drag"])
        a = np.radians(d.get("dir_deg", 0.0))
        self.dir = np.array([np.cos(a), np.sin(a), 0.0])
        self.max_offset = float(d.get("max_offset", 250.0))

    def covers(self, pos):
        return np.linalg.norm(pos[:, :2] - self.xy, axis=1) < self.radius


# --------------------------------------------------------------- karıştırıcı konum bulma
def _pl(d, cfg):
    return cfg.pl_d0_db + 10.0 * cfg.pl_exponent * np.log10(np.maximum(d, 1.0))


P_MAX = 33.0   # taktik karıştırıcının gücü en fazla ~2 W kabul edilir (uzakta çok güçlü tek kaynak çözümünü önler)


def _fit_one(cand, X, R, cfg, dz):
    """Her aday konum için dB'de en iyi güç (P <= P_MAX, kısıtlı en küçük kareler) ve kalan hata kareleri ortalaması."""
    d2 = ((cand[:, None, :] - X[None, :, :]) ** 2).sum(-1) + dz * dz
    pl = cfg.pl_d0_db + 5.0 * cfg.pl_exponent * np.log10(d2)          # 10 n log10(d) = 5 n log10(d^2)
    y = R[None, :] + pl
    P = np.minimum(y.mean(1), P_MAX)
    return P, ((y - P[:, None]) ** 2).mean(1)


def _grid(center, half, step):
    g = np.arange(-half, half + 1e-6, step)
    gx, gy = np.meshgrid(center[0] + g, center[1] + g)
    return np.c_[gx.ravel(), gy.ravel()]


def localize(X, R, cfg, dz=25.0, two=True):
    """Ölçümlerden (X: (M,2) konum, R: (M,) dBm) karıştırıcı(lar)ı bulur.
    Döndürür: [(xy, güç dBm), ...] ve ortalama kalan hata (dB). Yetersiz veri: ([], inf)."""
    if len(R) < 6 or np.ptp(X, axis=0).max() < 40.0:
        return [], np.inf
    c0 = X.mean(0)
    half = max(np.ptp(X, axis=0).max(), 200.0) + 300.0
    cand = _grid(c0, half, 50.0)                                       # kaba -> orta -> ince ızgara
    P, cost = _fit_one(cand, X, R, cfg, dz)
    for h, s in ((50.0, 10.0), (10.0, 2.0)):
        cand = _grid(cand[int(np.argmin(cost))], h, s)
        P, cost = _fit_one(cand, X, R, cfg, dz)
    k = int(np.argmin(cost))
    best = [(cand[k], float(P[k]))]
    rms1 = float(np.sqrt(cost[k]))
    # Tek kaynak çözümü şüpheliyse iki kaynak denenir: hata ölçüm gürültüsünden (~2 dB) belirgin büyük,
    # güç sınıra dayanmış ya da kaynak ölçülen bölgenin çok dışında
    far = np.min(np.linalg.norm(X - best[0][0], axis=1)) > 400.0
    if not two or len(R) < 14 or not (rms1 > 2.5 or best[0][1] >= P_MAX - 0.1 or far):
        return best, rms1
    # Tek kaynak kötü uyuyor: iki karıştırıcı olabilir. En güçlü ölçümler iki kümeye ayrılır
    # (k-ortalamalar), kümelerin merkezinden başlanıp kaynaklar dönüşümlü aranır (güçler mW'da toplanır).
    top = X[R >= np.percentile(R, 60)]
    a, b = top[np.argmax(((top - top.mean(0)) ** 2).sum(1))], None
    b = top[np.argmax(((top - a) ** 2).sum(1))]
    for _ in range(10):
        lab = ((top - a) ** 2).sum(1) > ((top - b) ** 2).sum(1)
        if lab.all() or (~lab).all():
            return best, rms1
        a, b = top[~lab].mean(0), top[lab].mean(0)
    Rm = 10 ** (R / 10.0)
    w2 = 1.0 / np.maximum(Rm, 1e-30) ** 2                                  # göreli hata (dB'ye yakın)

    def gains(q):
        d2 = ((np.atleast_2d(q)[:, None, :] - X[None, :, :]) ** 2).sum(-1) + dz * dz
        return 10 ** (-(cfg.pl_d0_db + 5.0 * cfg.pl_exponent * np.log10(d2)) / 10.0)

    q = [a, b]
    rms2, P12 = np.inf, (1e-9, 1e-9)
    for it in range(8):
        fix, k = q[(it + 1) % 2], it % 2
        g1 = gains(fix)[0]
        steps = ((300.0, 30.0), (40.0, 8.0)) if it < 4 else ((40.0, 8.0), (8.0, 2.0))
        for h, s in steps:
            G2 = gains(_grid(q[k], h, s))                                  # (C, M)
            pmax = 10 ** (P_MAX / 10.0)
            W = np.broadcast_to(w2, G2.shape)
            for _ in range(2):                    # yeniden ağırlıklandırılmış en küçük kareler (dB hatasına yakın)
                a11 = (g1[None, :] * g1[None, :] * W).sum(1)
                a12 = (G2 * g1[None, :] * W).sum(1)
                a22 = (G2 * G2 * W).sum(1)
                b1 = (g1[None, :] * Rm[None, :] * W).sum(1)
                b2 = (G2 * Rm[None, :] * W).sum(1)
                det = np.maximum(a11 * a22 - a12 * a12, 1e-300)
                p1 = np.clip((b1 * a22 - a12 * b2) / det, 1e-15, pmax)
                p2 = np.clip((a11 * b2 - a12 * b1) / det, 1e-15, pmax)
                pred = p1[:, None] * g1[None, :] + p2[:, None] * G2
                W = 1.0 / pred ** 2
            err = ((10 * np.log10(pred) - R[None, :]) ** 2).mean(1)
            j = int(np.argmin(err))
            q[k] = _grid(q[k], h, s)[j]
            rms2, P12 = float(np.sqrt(err[j])), (p1[j], p2[j]) if k == 1 else (p2[j], p1[j])
    P1, P2 = 10 * np.log10(P12[0]), 10 * np.log10(P12[1])
    # İkinci kaynak gerçekten gerekli mi: hata düşmeli, kaynaklar ayrık ve ikisi de anlamlı güçte olmalı.
    # Tek kaynak çözümü güç sınırına dayandıysa (uzakta "aşırı güçlü" kaynak) fiziksel olarak şüphelidir.
    limit = 1.05 if best[0][1] >= P_MAX - 0.1 else 0.9
    if rms2 < limit * rms1 and np.linalg.norm(q[0] - q[1]) > 150.0 and abs(P1 - P2) < 15.0:
        return [(q[0], float(P1)), (q[1], float(P2))], rms2
    return best, rms1


def predicted_jam_dbm(points, estimates, cfg, dz=25.0):
    """Kestirilen karıştırıcılardan noktalara ulaşacak güç (dBm)."""
    total = np.zeros(len(points))
    for q, P in estimates:
        d = np.sqrt(((points - q) ** 2).sum(-1) + dz * dz)
        total += 10 ** ((P - _pl(d, cfg)) / 10.0)
    return 10 * np.log10(np.maximum(total, 1e-30))
