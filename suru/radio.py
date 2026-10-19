"""Radyo ve elektronik harp fiziği.

Her bağlantı için sinyal / (gürültü + karıştırma) oranı (SINR) hesaplanır,
paket kaybı olasılığı (PER) bu orandan bulunur:

    alınan güç (dBm) = verici gücü + anten kazancı - yol kaybı(d)
    yol kaybı(d)     = PL(1 m) + 10 * n * log10(d)
    SINR (dB)        = sinyal - 10*log10(gürültü_mW + karıştırma_mW)
    PER              = 1 / (1 + exp(eğim * (SINR - eşik)))
"""
import numpy as np


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


def jam_power_dbm(points, jammers, cfg):
    """Her noktaya ulaşan toplam karıştırma gücü (dBm). Karıştırıcı yoksa ~ -300 dBm."""
    points = np.atleast_2d(points)
    total = np.zeros(len(points))
    for jpos, jpow in jammers:
        d = np.linalg.norm(points - jpos, axis=1)
        total += mw(jpow - path_loss_db(d, cfg))
    return dbm(total)


def per_from_sinr(sinr_db, cfg):
    return 1.0 / (1.0 + np.exp(cfg.per_slope * (sinr_db - cfg.sinr_threshold_db)))


def link_per(tx_pos, rx_pos, rx_jam_dbm, cfg, gain_db=0.0, max_range=None):
    """Vericiler (A,3) -> alıcılar (B,3) için paket kaybı olasılığı ve SINR, ikisi de (A,B)."""
    d = dist_matrix(np.atleast_2d(tx_pos), np.atleast_2d(rx_pos))
    signal = cfg.tx_power_dbm + gain_db - path_loss_db(d, cfg)
    interference = dbm(mw(cfg.noise_dbm) + mw(rx_jam_dbm))[None, :]
    sinr = signal - interference
    per = per_from_sinr(sinr, cfg)
    max_range = cfg.comm_range if max_range is None else max_range
    per[d > max_range] = 1.0
    return per, sinr


def jam_radius(jammer_power_dbm, cfg, link_len=60.0):
    """Karıştırıcının etkili yarıçapı: bu mesafede `link_len` uzunluğundaki
    bir bağlantının SINR'ı eşiğe iner (paketlerin yarısı kaybolur). Görselleştirme için."""
    signal = cfg.tx_power_dbm - path_loss_db(link_len, cfg)
    needed_mw = mw(signal - cfg.sinr_threshold_db) - mw(cfg.noise_dbm)
    if needed_mw <= 0:
        return 0.0
    pl = jammer_power_dbm - dbm(needed_mw)
    return float(10 ** ((pl - cfg.pl_d0_db) / (10 * cfg.pl_exponent)))
