"""Enerji ve rüzgâr: döner kanatlı İHA güç modeli, batarya ve esintili rüzgâr.

Güç modeli (Zeng, Xu, Zhang 2019, "Energy minimization for wireless communication with rotary-wing UAV",
IEEE Trans. Wireless Commun.): havaya göre V hızında yatay uçuşta gereken güç üç terimin toplamıdır:
    P(V) = P0 (1 + 3V²/U²)                                   kanat profil gücü
         + Pi (sqrt(1 + V⁴/(4 v0⁴)) - V²/(2 v0²))^(1/2)      indüklenmiş güç (taşıma)
         + 1/2 d0 ρ s A V³                                  gövde sürükleme gücü
Askıda (V = 0) P0 + Pi = 168 W harcanır; ~10 m/s'de en düşüktür (~125 W), hız arttıkça sürükleme büyür.
Tırmanırken ağırlık * dikey hız kadar fazladan güç gerekir. Önemli olan yere göre değil havaya göre hızdır:
karşıdan esen rüzgârda İHA yerinde dururken bile hızlı uçuyor gibi güç harcar ve yere göre yavaş ilerler.

Rüzgâr: ortalama rüzgâr + esinti. Esinti, Ornstein-Uhlenbeck süreci (zaman sabiti 8 s): ani değişen ama
ortalamaya dönen rastgele bir hız.

Batarya: 4S 3000 mAh lityum polimer, 44,4 Wh (askıda ~16 dakika). Her otopilot gibi batarya %10'a inince İHA eve döner
(standart emniyet). Enerji farkında karar (dirençli sürü): İHA, bulunduğu yerden rüzgâra karşı eve dönmenin
enerjisini hesaplar. Görev seçerken "bu hedefe gidip eve dönebilir miyim?" diye bakar, dönüş enerjisi
yedekle birlikte bataryaya yaklaşınca görevini bırakıp döner. Sabit %10 kuralı mesafeyi ve rüzgârı bilmez:
uzakta, karşı rüzgârda kalan İHA eve varamadan bataryası biter.
"""
import numpy as np

# Zeng ve ark. (2019) Tablo I
P0, PI, U_TIP, V0, D0, RHO, SOLIDITY, AREA = 79.86, 88.63, 120.0, 4.03, 0.6, 1.225, 0.05, 0.503
WEIGHT = 20.0                    # N (~2 kg)
CAPACITY_WH = 44.4               # 4S 3000 mAh (14,8 V): askıda ~16 dakika
FAILSAFE = 0.10                  # standart emniyet: batarya bu orana inince eve dön
RESERVE = 0.06                   # enerji farkında karar: inişte bataryada kalacak pay
LAND_S = 25.0                    # iniş ve pist üstünde bekleme (s, askıda güç)
GUST_TAU = 8.0                   # esinti zaman sabiti (s)

# Batarya senaryoları: İHA'ların kalkıştaki doluluk oranları (sırası tohuma göre karıştırılır)
BATTERY_MODES = {
    "tam": None,
    "karisik": [0.95, 0.9, 0.82, 0.7, 0.55, 0.42, 0.33, 0.27, 0.23, 0.2],
    "dusuk": [0.55, 0.5, 0.46, 0.42, 0.4, 0.37, 0.35, 0.33, 0.31, 0.29],
}


def power_w(v_air, vz=0.0):
    """Havaya göre yatay hız v_air (m/s) ve dikey hız vz'de çekilen güç (W)."""
    v = np.asarray(v_air, float)
    blade = P0 * (1.0 + 3.0 * v * v / U_TIP ** 2)
    induced = PI * np.sqrt(np.maximum(np.sqrt(1.0 + v ** 4 / (4.0 * V0 ** 4)) - v * v / (2.0 * V0 * V0), 0.0))
    parasite = 0.5 * D0 * RHO * SOLIDITY * AREA * v ** 3
    return blade + induced + parasite + WEIGHT * np.maximum(np.asarray(vz, float), 0.0)


HOVER_W = float(power_w(0.0))


def ground_speed(u, wind, v_air):
    """Rüzgârda u yönünde (birim vektörler, (K,2)) havaya göre v_air ile uçulunca yere göre hız (m/s).
    |g u - w| = v_air  ->  g = u.w + sqrt(v_air² - |w|² + (u.w)²). Rüzgâr hava hızından güçlüyse 0."""
    u = np.atleast_2d(u)
    uw = u @ wind
    disc = v_air * v_air - float(wind @ wind) + uw * uw
    return np.where(disc > 0, uw + np.sqrt(np.maximum(disc, 0.0)), 0.0)


def leg_energy_wh(a, b, wind, v_air):
    """a (K,2) -> b (K,2) yolunu havaya göre v_air hızla uçmanın enerjisi (Wh); rüzgâr karşıdaysa uzar."""
    d = np.asarray(b, float) - np.asarray(a, float)
    L = np.linalg.norm(d, axis=-1)
    u = d / np.maximum(L, 1e-9)[..., None]
    g = ground_speed(u.reshape(-1, 2), wind, v_air).reshape(L.shape)
    t = np.where(g > 0.3, L / np.maximum(g, 0.3), np.inf)
    t = np.where(L < 1.0, 0.0, t)
    return t * float(power_w(v_air)) / 3600.0


def home_energy_wh(xy, home, wind, v_air):
    """Bulunduğu yerden eve dönüp inmenin enerjisi (Wh)."""
    xy = np.atleast_2d(xy)
    return leg_energy_wh(xy, np.broadcast_to(home, xy.shape), wind, v_air) + LAND_S * HOVER_W / 3600.0


class Wind:
    """Ortalama rüzgâr + esinti. from_deg: rüzgârın estiği yön (meteoroloji: 0 kuzeyden, 180 güneyden)."""

    def __init__(self, speed, from_deg, gust, rng):
        a = np.radians(from_deg)
        self.mean = -float(speed) * np.array([np.sin(a), np.cos(a)])     # esme yönü (doğu, kuzey)
        self.sigma = float(gust)
        self.g = np.zeros(2)
        self.rng = rng
        self.speed = float(speed)
        self.from_deg = float(from_deg)

    @property
    def on(self):
        return self.speed > 0 or self.sigma > 0

    @property
    def vec(self):
        return self.mean + self.g

    def step(self, dt):
        if self.sigma <= 0:
            return
        k = dt / GUST_TAU
        self.g += -self.g * k + self.sigma * np.sqrt(2.0 * k) * self.rng.normal(size=2)
