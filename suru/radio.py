"""Radyo ve elektronik harp fiziği.

Her bağlantı için sinyal / (gürültü + karıştırma) oranı (SINR) hesaplanır,
paket kaybı olasılığı (PER) bu orandan bulunur:

    alınan güç (dBm) = verici gücü + anten kazancı - yol kaybı(d)
    yol kaybı(d)     = PL(1 m) + 10 * n * log10(d)
    SINR (dB)        = sinyal - 10*log10(gürültü_mW + karıştırma_mW)
    PER              = 1 / (1 + exp(eğim * (SINR - eşik)))

Arazi gölgesi (tek bıçak sırtı kırınımı, ITU-R P.526): verici ile alıcı arasındaki görüş hattını en
çok kesen tepe bulunur. Tepenin hattın ne kadar üstüne çıktığı (h), Fresnel parametresi
v = h * sqrt(2 d / (lambda d1 d2)) ile ölçülür ve ek kayıp J(v) dB eklenir:
    J(v) = 6.9 + 20 log10( sqrt((v - 0.1)^2 + 1) + v - 0.1 )   (v > -0.78, değilse 0)
Hat tepeyi rahatça aşıyorsa kayıp 0, tepe hattı tam kesiyorsa ~6 dB, arkasında kalmışsa 15-30 dB.
"""
import numpy as np

LAMBDA = 0.125          # 2,4 GHz dalga boyu (m)
SHADOW_SAMPLES = 16     # görüş hattı boyunca arazi örneği


def mw(dbm):
    """dBm -> miliwatt"""
    return 10.0 ** (np.asarray(dbm, dtype=float) / 10.0)


def dbm(milliwatt):
    """miliwatt -> dBm"""
    return 10.0 * np.log10(np.maximum(milliwatt, 1e-30))


def path_loss_db(d, cfg):
    return cfg.pl_d0_db + 10.0 * cfg.pl_exponent * np.log10(np.maximum(d, 1.0))


def dist_matrix(a, b=None):
    b = a if b is None else b
    return np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)


def knife_edge_db(v):
    """ITU-R P.526 tek bıçak sırtı kırınım kaybı (dB)."""
    v = np.asarray(v, float)
    out = np.zeros_like(v)
    m = v > -0.78
    w = v[m] - 0.1
    out[m] = 6.9 + 20.0 * np.log10(np.sqrt(w * w + 1.0) + w)
    return out


def terrain_loss_db(tx, rx, terrain, lam=LAMBDA, samples=SHADOW_SAMPLES):
    """Vericiler (A,3) -> alıcılar (B,3) için arazinin görüş hattını kesmesinden doğan ek kayıp (A,B) dB.
    lam: dalga boyu (m; radar için X bandı), samples: görüş hattı boyunca arazi örneği."""
    tx, rx = np.atleast_2d(tx), np.atleast_2d(rx)
    if terrain is None or terrain.flat:
        return np.zeros((len(tx), len(rx)))
    t = np.linspace(0.0, 1.0, samples + 2)[1:-1]                       # uç noktalar hariç
    a, b = tx[:, None, None, :], rx[None, :, None, :]
    pts = a + (b - a) * t[None, None, :, None]                         # (A, B, K, 3)
    ground = terrain.height(pts[..., 0], pts[..., 1])
    h = ground - pts[..., 2]                                            # tepenin görüş hattından yüksekliği
    D = np.maximum(np.linalg.norm((b - a)[..., :2], axis=-1), 1.0)     # (A, B, 1) yatay mesafe
    d1, d2 = D * t, D * (1 - t)
    v = h * np.sqrt(2.0 * D / (lam * d1 * d2))
    return knife_edge_db(v.max(axis=2))


def jam_power_dbm(points, jammers, cfg, terrain=None, band="comm"):
    """Her noktaya ulaşan toplam karıştırma gücü (dBm). Karıştırıcı yoksa ~ -300 dBm.
    jammers: (konum, güç) çiftleri ya da ew.Jammer nesneleri.
    band="comm": haberleşme kanalına düşen güç (nokta karıştırıcı +6,2 dB);
    band="gps": GPS'e etki eden güç (yalnızca geniş bant karıştırıcılar)."""
    points = np.atleast_2d(points)
    total = np.zeros(len(points))
    for j in jammers:
        if hasattr(j, "pos"):
            if band == "gps" and j.band != "genis":
                continue
            jpos, jpow = j.pos, (j.comm_power if band == "comm" else j.power)
        else:
            jpos, jpow = j
        d = np.linalg.norm(points - jpos, axis=1)
        loss = path_loss_db(d, cfg)
        if terrain is not None and cfg.terrain_radio:
            loss = loss + terrain_loss_db(np.asarray(jpos, float)[None, :], points, terrain)[0]
        total += mw(jpow - loss)
    return dbm(total)


def jam_field_dbm(xs, ys, jammers, cfg, terrain, agl):
    """Karıştırma ısı haritası: (xs, ys) ızgarasında, yerden `agl` metre yükseklikte haberleşme
    kanalına düşen karıştırma gücü (dBm), boyut (len(ys), len(xs)). İHA'ların uçuşta ölçtüğüyle
    aynı model (yol kaybı + arazi gölgesi), yani haritadaki her renk o noktadaki İHA'nın gerçekte yaşadığıdır."""
    gx, gy = np.meshgrid(xs, ys)
    ground = terrain.height(gx, gy) if terrain is not None else np.zeros_like(gx)
    pts = np.c_[gx.ravel(), gy.ravel(), np.ravel(ground) + agl]
    return jam_power_dbm(pts, jammers, cfg, terrain, band="comm").reshape(gx.shape)


def per_from_sinr(sinr_db, cfg):
    return 1.0 / (1.0 + np.exp(cfg.per_slope * (sinr_db - cfg.sinr_threshold_db)))


def link_per(tx_pos, rx_pos, rx_jam_dbm, cfg, gain_db=0.0, max_range=None, extra_loss_db=None):
    """Vericiler (A,3) -> alıcılar (B,3) için paket kaybı olasılığı ve SINR, ikisi de (A,B).
    extra_loss_db: (A,B) ek kayıp (ör. arazi gölgesi, terrain_loss_db ile bir kez hesaplanır)."""
    d = dist_matrix(np.atleast_2d(tx_pos), np.atleast_2d(rx_pos))
    signal = cfg.tx_power_dbm + gain_db - path_loss_db(d, cfg)
    if extra_loss_db is not None:
        signal = signal - extra_loss_db
    interference = dbm(mw(cfg.noise_dbm) + mw(rx_jam_dbm))[None, :]
    sinr = signal - interference
    per = per_from_sinr(sinr, cfg)
    max_range = cfg.comm_range if max_range is None else max_range
    per[d > max_range] = 1.0
    return per, sinr


def jam_tolerance_dbm(cfg, link_len=60.0):
    """`link_len` uzunluğundaki bir bağlantının paketlerinin yarısını kaybettiği karıştırma gücü (dBm)."""
    signal = cfg.tx_power_dbm - path_loss_db(link_len, cfg)
    return float(dbm(max(mw(signal - cfg.sinr_threshold_db) - mw(cfg.noise_dbm), 1e-30)))


def jam_radius(jammer_power_dbm, cfg, link_len=60.0):
    """Karıştırıcının etkili yarıçapı: bu mesafede `link_len` uzunluğundaki
    bir bağlantının SINR'ı eşiğe iner (paketlerin yarısı kaybolur). Görselleştirme için."""
    signal = cfg.tx_power_dbm - path_loss_db(link_len, cfg)
    needed_mw = mw(signal - cfg.sinr_threshold_db) - mw(cfg.noise_dbm)
    if needed_mw <= 0:
        return 0.0
    pl = jammer_power_dbm - dbm(needed_mw)
    return float(10 ** ((pl - cfg.pl_d0_db) / (10 * cfg.pl_exponent)))
