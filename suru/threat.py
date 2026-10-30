"""Hava savunma tehdidi: radar, radar ikaz alıcısı (RWR) ve tehdit farkında rota planlama.

Radar (X bandı, 9,4 GHz, dalga boyu 3,2 cm), anteni 2 s'de bir tur atar
  Radar denklemi: alınan yankı mesafenin 4. kuvvetiyle azalır (gidiş + dönüş):
      SNR = SNR50 * (R50 / R)^4 * 10^(-2 L / 10)
  R50: küçük bir İHA'nın (radar kesit alanı ~0,05 m²) taramaların yarısında görüldüğü menzil. L: arazinin
  görüş hattını kesmesinden doğan tek yön kayıp (ITU-R P.526 bıçak sırtı kırınımı, X bandında). Dalga boyu
  kısa olduğu için tepenin arkası neredeyse tam gölgedir; yankı iki kez geçtiği için kayıp ikiyle çarpılır.
  Tek taramada tespit olasılığı (Swerling-1 hedef, yanlış alarm olasılığı Pfa = 1e-6):
      Pd = Pfa ^ (1 / (1 + SNR))
  Doppler (MTI) süzgeci: radara göre radyal hızı 3 m/s'den küçük hedefin yankısı yer yankısıyla karışır,
  4 kat (6 dB) zayıflar ("beaming": radara dik uçmak izi koparır).
  İzleme: son 3 taramanın en az 2'sinde görülen İHA izlenir (M/N izleme). İz 4 s korunursa hava
  savunma füzesi atılır. Füze komutla güdümlüdür: radar izi koparsa güdümsüz kalır ve ıskalar.

Radar ikaz alıcısı (RWR, dirençli sürü)
  Radar huzmesi İHA'nın üstünden geçtiğinde sinyal tek yönlü yol aldığı için radarın kendi menzilinin
  çok ötesinden duyulur. İHA radarın geliş yönünü (kerteriz, ±3°) ölçer ve radarı imzasından tanır.
  İz alınınca "kilit ikazı" verir. Kerteriz ölçümleri dedikoduyla yayılır; sürü farklı yerlerden ölçülen
  kerteriz çizgilerinin kesişiminden radarın yerini en küçük karelerle bulur (kerteriz kestirimi).

Tehdit farkında rota planlama
  Bilinen ve bulunan radarların görüş alanı ızgaraya çıkarılır: her hücrede, alçak uçuş yüksekliğinde
  tespit olasılığı. Izgara bir çizge sayılır; kenar maliyeti = uzunluk * (1 + W * Pd). Hedeften geriye
  Dijkstra en kısa yol ağacı kurulur (aynı hedefe giden herkes paylaşır), İHA ağaçtan rotasını okur:
  vadilerden, tepelerin arkasından, radar görüşünden en az kalarak uçar. Tehdit bölgesinde alçalır.
"""
import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

from .radio import terrain_loss_db
from .swarm import Path

LAMBDA_X = 0.032                 # X bandı dalga boyu (m)
PFA = 1e-6                       # yanlış alarm olasılığı
SNR50 = float(np.log(PFA) / np.log(0.5) - 1.0)   # Pd = 0,5 için gereken SNR (Swerling-1): ~18,9 (12,8 dB)
R50 = 420.0                      # küçük İHA'nın taramaların yarısında görüldüğü menzil (m)
MAST = 8.0                       # radar anten yüksekliği (m)
PERIOD = 2.0                     # anten tur süresi (s)
NOTCH_V = 3.0                    # Doppler süzgecinin kör hız aralığı (m/s)
NOTCH_GAIN = 0.25                # o aralıktaki yankının gücü (6 dB zayıflama)
TRACK_M, TRACK_N = 2, 3          # son N taramanın M'sinde görülen İHA izlenir
ENGAGE_AFTER = 4.0               # iz bu kadar korunursa füze atılır (s)
RELOAD = 6.0                     # iki atış arası (s)
MISSILE_SPEED = 180.0            # m/s
MISSILE_LIFE = 9.0               # füzenin en uzun uçuşu (s)
PK = 0.85                        # yakınından geçen füzenin İHA'yı düşürme olasılığı
KILL_DIST = 8.0                  # yakınlık tapası mesafesi (m)
RWR_RANGE = 1500.0               # radar ikaz alıcısının radarı duyduğu menzil (m)
RWR_MAX_LOSS = 25.0              # bu kadar arazi kaybından sonra huzme duyulmaz (dB)
BEARING_SIGMA = np.radians(3.0)  # kerteriz ölçüm hatası

# Tehdit haritası ızgarası (görev alanı, üs ve çevresi)
TG_O = np.array([-800.0, -400.0])
TG_STEP = 20.0
TG_N = 80
EXPOSURE_W = 40.0                # rota maliyetinde radar görüşünün ağırlığı
SAFE_PD = 0.2                    # bu tespit olasılığının altı "güvenli" sayılır
DASH = 50.0                      # hedefe kısa dalış: güvenli bölgeden en fazla bu kadar içeri girilir (m)


def detect_prob(rng_m, loss_one_way_db, r50=R50, radial=None):
    """Tek taramada tespit olasılığı (Swerling-1). rng_m: menzil (m), loss: tek yön arazi kaybı (dB)."""
    R = np.maximum(np.asarray(rng_m, float), 1.0)
    snr = SNR50 * (r50 / R) ** 4 * 10.0 ** (-2.0 * np.asarray(loss_one_way_db, float) / 10.0)
    if radial is not None:
        snr = np.where(np.abs(radial) < NOTCH_V, snr * NOTCH_GAIN, snr)
    return PFA ** (1.0 / (1.0 + snr))


def coverage(radar_pos, pts, terrain, r50=R50):
    """Radarın noktaları (M,3) görme olasılığı (taramada Pd). Arazi gölgesi X bandında hesaplanır."""
    pts = np.atleast_2d(pts)
    R = np.linalg.norm(pts - radar_pos, axis=1)
    far = R > 4.0 * r50
    pd = np.zeros(len(pts))
    near = ~far
    if near.any():
        L = terrain_loss_db(np.asarray(radar_pos)[None, :], pts[near], terrain, lam=LAMBDA_X, samples=40)[0]
        pd[near] = detect_prob(R[near], L, r50)
    return pd


def compass(dx, dy):
    """Pusula açısı (radyan): 0 kuzey, saat yönünde."""
    return np.arctan2(dx, dy) % (2 * np.pi)


class Radar:
    """Dönen antenli arama/izleme radarı ve ona bağlı kısa menzilli hava savunma."""

    def __init__(self, d, terrain, n, rid):
        self.id = rid
        self.xy = np.array(d["pos"][:2], float)
        self.pos = np.r_[self.xy, float(terrain.height(*self.xy)) + float(d.get("mast", MAST))]
        self.r50 = float(d.get("r50", R50))
        self.period = float(d.get("period", PERIOD))
        self.on_at = float(d.get("on_at", 0.0))       # pusu: radar bu anda açılır
        self.known = bool(d.get("known", True))       # istihbarat: yeri görevden önce biliniyor mu
        self.missiles = int(d.get("missiles", 3))
        self.az = float(d.get("az0", 0.0))            # anten yönü (pusula, radyan)
        self.hist = np.zeros((n, TRACK_N), bool)      # son taramalarda tespit
        self.track = np.zeros(n, bool)
        self.track_since = np.full(n, np.inf)
        self.lit = np.full(n, -np.inf)                # huzme İHA'nın üstünden en son ne zaman geçti
        self.next_fire = 0.0
        self.fired = 0
        self.alive = True                             # kamikaze İHA vurunca False (HSS bastırma)
        self.dead_t = np.nan

    def active(self, t):
        return t >= self.on_at and self.alive


class Missile:
    def __init__(self, radar, target, pos, vel, t):
        self.radar, self.target = radar, target
        self.pos, self.vel = np.array(pos, float), np.array(vel, float)
        self.t0, self.state, self.t_end = t, 0, np.inf   # 0 uçuyor, 1 vurdu, 2 ıskaladı


def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def bearing_fix(P, B, sigma=BEARING_SIGMA, span=RWR_RANGE, rng=None):
    """Kerteriz kestirimi: P (K,2) ölçüm noktaları, B (K,) pusula kerterizleri -> (konum, hata yarıçapı) ya da None.
    En çok olabilirlik: her aday konum için "o konumdaki radar hangi kerterizlerde görünürdü" hesaplanır, ölçülen
    kerterizlerle açı farklarının karelerinin toplamı en küçük aday seçilir (kaba ızgara, sonra ince ızgara).
    Hata, Fisher bilgisinden: kerteriz hatası uzakta daha büyük yanal hata yapar, ölçüm noktaları birbirine
    yakınsa (kısa taban) uzaklık belirsiz kalır ve hata büyük çıkar; o durumda kestirim reddedilir."""
    if len(B) < 3:
        return None
    if len(B) > 32:                                   # hesap yükü: en yeni 16 + rastgele 16 ölçüm
        r = rng if rng is not None else np.random.default_rng(len(B))
        keep = np.r_[np.arange(len(B) - 16, len(B)), r.choice(len(B) - 16, 16, replace=False)]
        P, B = P[keep], B[keep]
    cap = (4.0 * sigma) ** 2

    def cost(Q):
        d = Q[:, None, :] - P[None, :, :]
        r = _wrap(B[None, :] - compass(d[..., 0], d[..., 1]))
        return np.minimum(r * r, cap).sum(1)

    ctr = P.mean(0)
    g = np.arange(-span, span + 1e-6, 60.0)
    Q = ctr + np.c_[np.repeat(g, len(g)), np.tile(g, len(g))]
    q = Q[int(np.argmin(cost(Q)))]
    for step in (15.0, 4.0):
        g = np.arange(-4, 5) * step
        Q = q + np.c_[np.repeat(g, len(g)), np.tile(g, len(g))]
        q = Q[int(np.argmin(cost(Q)))]
    # Uzaklık gözlenebilir mi: kestirimi ölçüm noktalarından 1,6 kat uzağa ya da yakına kaydırınca açı hatası
    # belirgin artmalı; artmıyorsa (kerteriz çizgileri neredeyse paralel) yalnızca yön bilinir, konum bilinmez
    c0 = cost(q[None, :])[0]
    probe = np.array([ctr + (q - ctr) * 1.6, ctr + (q - ctr) / 1.6])
    if (cost(probe) - c0).min() < 9.0 * sigma * sigma:
        return None
    d = q - P
    dist = np.maximum(np.linalg.norm(d, axis=1), 30.0)
    b = compass(d[:, 0], d[:, 1])
    good = np.abs(_wrap(B - b)) < 4.0 * sigma
    if good.sum() < 3:
        return None
    n = np.c_[np.cos(b), -np.sin(b)][good] / dist[good, None]       # kerteriz çizgisine dik, 1/uzaklık
    J = n.T @ n
    if np.linalg.eigvalsh(J)[0] <= 1e-12:
        return None
    err = float(np.sqrt(np.trace(np.linalg.inv(J))) * sigma)
    return q, max(err, 5.0)


class ThreatMap:
    """Bilinen radarlardan tehdit haritası ve rota ağacı (Dijkstra). Aynı radar bilgisine sahip İHA'lar paylaşır."""

    _cache = {}                                    # (arazi, yükseklik, radar konumu) -> görüş ızgarası

    def __init__(self, radars, terrain, agl, r50=R50, dilate=0):
        """radars: konumlar; r50: hepsi için tek menzil ya da radar başına liste (radar ikaz alıcısı radarın
        türünü imzasından tanır, türün menzili bilinir)."""
        r50s = list(r50) if np.ndim(r50) else [r50] * len(radars)
        g = TG_O[None, :] + (np.c_[np.indices((TG_N, TG_N)).reshape(2, -1).T] + 0.5) * TG_STEP   # (ix, iy) sırası
        self.xy = g
        miss = np.ones(len(g))
        for q, r50 in zip(radars, r50s):
            q = np.asarray(q, float)
            key = (id(terrain), float(agl), float(r50), round(float(q[0]), 1), round(float(q[1]), 1))
            pd1 = ThreatMap._cache.get(key)
            if pd1 is None:
                if len(ThreatMap._cache) > 256:
                    ThreatMap._cache.clear()
                rp = np.r_[q[:2], float(terrain.height(*q[:2])) + MAST]
                pts = np.c_[g, terrain.height(g[:, 0], g[:, 1]) + agl]
                pd1 = ThreatMap._cache[key] = coverage(rp, pts, terrain, r50)
            miss *= 1.0 - pd1
        pd = (1.0 - miss).reshape(TG_N, TG_N)
        for _ in range(dilate):                       # düzen uçuşu için: kanatlardaki İHA'lar da güvende kalsın
            p = np.pad(pd, 1, mode="edge")
            pd = np.max([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]], axis=0)
        self.pd = pd
        # Her hücreden radarın görmediği (güvenli) en yakın hücreye uzaklık: hedefe dalıp çıkmanın süresi
        self.escape = distance_transform_edt(pd >= SAFE_PD) * TG_STEP
        self._graph = None
        self._trees = {}

    def cell(self, xy):
        ij = np.floor((np.asarray(xy, float) - TG_O) / TG_STEP).astype(int)
        return np.clip(ij, 0, TG_N - 1)

    def pd_at(self, xy):
        ij = self.cell(np.atleast_2d(xy))
        return self.pd[ij[:, 0], ij[:, 1]]

    def escape_at(self, xy):
        ij = self.cell(np.atleast_2d(xy))
        return self.escape[ij[:, 0], ij[:, 1]]

    def line_pd(self, a, b, step=20.0):
        """Doğru parça boyunca en yüksek tespit olasılığı."""
        L = float(np.linalg.norm(np.asarray(b) - np.asarray(a)))
        s = np.linspace(0, 1, max(2, int(L / step) + 1))[:, None]
        return float(self.pd_at(np.asarray(a)[None, :] * (1 - s) + np.asarray(b)[None, :] * s).max())

    def _build_graph(self):
        n = TG_N
        idx = np.arange(n * n).reshape(n, n)
        c = 1.0 + EXPOSURE_W * self.pd
        rows, cols, w = [], [], []
        for di, dj in ((1, 0), (0, 1), (1, 1), (1, -1)):
            a = idx[max(0, -di):n - max(0, di), max(0, -dj):n - max(0, dj)]
            b = idx[max(0, di):n - max(0, -di) or None, max(0, dj):n - max(0, -dj) or None]
            ca = c.ravel()[a.ravel()]
            cb = c.ravel()[b.ravel()]
            L = TG_STEP * np.hypot(di, dj)
            rows += [a.ravel(), b.ravel()]
            cols += [b.ravel(), a.ravel()]
            w += [L * 0.5 * (ca + cb)] * 2
        self._graph = coo_matrix((np.concatenate(w), (np.concatenate(rows), np.concatenate(cols))),
                                 shape=(n * n, n * n)).tocsr()

    def route(self, start, goal):
        """start -> goal en az görülen rota (Path), ya da düz yol yeterliyse None."""
        start, goal = np.asarray(start, float)[:2], np.asarray(goal, float)[:2]
        if self.line_pd(start, goal) < 0.08:
            return None
        if self._graph is None:
            self._build_graph()
        gi = self.cell(goal)
        g = int(gi[0] * TG_N + gi[1])
        if g not in self._trees:
            if len(self._trees) > 64:
                self._trees.clear()
            self._trees[g] = dijkstra(self._graph, indices=g, return_predecessors=True)[1]
        pred = self._trees[g]
        si = self.cell(start)
        k = int(si[0] * TG_N + si[1])
        cells = [k]
        while k != g and k >= 0 and len(cells) < 4 * TG_N:
            k = int(pred[k])
            cells.append(k)
        if k != g:
            return None
        pts = self.xy[cells]
        pts[0], pts[-1] = start, goal
        return Path(simplify(pts, 12.0))

    def safest_near(self, xy, radius, prefer=None):
        """xy'ye `radius` içinde, görülme olasılığı en düşük hücre (yakın olanı tercih eder)."""
        d = np.linalg.norm(self.xy - np.asarray(xy, float)[:2], axis=1)
        cost = self.pd.ravel() + d / (radius * 8.0)
        if prefer is not None:
            cost = cost + 0.02 * (np.linalg.norm(self.xy - prefer, axis=1) > radius)
        cost[d > radius] = np.inf
        return self.xy[int(np.argmin(cost))].copy()


def simplify(pts, tol):
    """Ramer-Douglas-Peucker: çizgiyi `tol` metreden fazla bozmadan köşe sayısını azaltır."""
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    ab = b - a
    L = np.linalg.norm(ab)
    if L < 1e-9:
        d = np.linalg.norm(pts - a, axis=1)
    else:
        d = np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / L
    k = int(np.argmax(d))
    if d[k] <= tol:
        return np.array([a, b])
    left = simplify(pts[:k + 1], tol)
    right = simplify(pts[k:], tol)
    return np.vstack([left[:-1], right])


def pursue(path, xy, look=40.0):
    """Rota üzerinde İHA'nın izdüşümünden `look` metre ilerideki nokta (saf takip)."""
    P = path.p
    best, s_best = np.inf, 0.0
    for k in range(len(P) - 1):
        a, b = P[k], P[k + 1]
        ab = b - a
        L2 = float(ab @ ab)
        u = 0.0 if L2 < 1e-9 else float(np.clip((xy - a) @ ab / L2, 0, 1))
        q = a + u * ab
        d = float(np.linalg.norm(xy - q))
        if d < best:
            best, s_best = d, path.cum[k] + u * np.sqrt(L2)
    p, _ = path.at(s_best + look)
    return p, path.length - s_best
