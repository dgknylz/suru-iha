"""Simülatörün doğruluk testleri.

    python -m pytest tests -q

Her test, simülatörün temel bir özelliğini doğrular: radyo fiziği mantıklı mı, sürü
düzende uçabiliyor mu, araziye çarpmıyor mu, birbirine çarpmıyor mu, arızaya dayanıyor mu...
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from suru import World, make_config, radio  # noqa: E402
from suru.config import SimConfig  # noqa: E402
from suru.swarm import Path, formation_offsets, largest_component  # noqa: E402
from suru.world import LANDED, TRANSIT  # noqa: E402


def fly(cfg, until="finished"):
    w = World(cfg)
    stop = w.finished if until == "finished" else w.flight_over
    while not stop():
        w.step()
    return w


# ------------------------------------------------------------------ radyo
def test_paket_kaybi_mesafeyle_artar():
    cfg = SimConfig()
    d = np.array([[50.0, 0, 0], [150.0, 0, 0], [280.0, 0, 0]])
    per, _ = radio.link_per(np.zeros((1, 3)), d, np.full(3, -300.0), cfg)
    assert per[0, 0] < per[0, 1] < per[0, 2]


def test_karistirma_sinr_dusurur():
    cfg = SimConfig()
    tx, rx = np.zeros((1, 3)), np.array([[100.0, 0, 0]])
    _, temiz = radio.link_per(tx, rx, np.array([-300.0]), cfg)
    _, kirli = radio.link_per(tx, rx, np.array([-70.0]), cfg)
    assert kirli[0, 0] < temiz[0, 0] - 10


# ------------------------------------------------------------------ sürü geometrisi
@pytest.mark.parametrize("kind", ["V", "hat", "kol", "halka"])
def test_duzen_yuvalari_ayrik(kind):
    off = formation_offsets(kind, 10, 16.0)
    d = np.linalg.norm(off[:, None] - off[None, :], axis=2)
    np.fill_diagonal(d, np.inf)
    assert d.min() >= 12.0          # iki yuva birbirine çarpışma mesafesinden yakın olamaz


def test_rota_uzunlugu():
    p = Path([[0, 0], [0, 300], [400, 300]])
    assert p.length == pytest.approx(700.0)
    q, u = p.at(500)
    assert q == pytest.approx([200, 300]) and u == pytest.approx([1, 0])


def test_en_buyuk_bagli_grup():
    a = np.zeros((4, 4), bool)
    a[0, 1] = a[1, 0] = True
    assert largest_component(a) == pytest.approx(0.5)


# ------------------------------------------------------------------ uçuş
def test_karistirmasiz_tum_gorevler_biter():
    w = fly(make_config("resilient", None, 0.0, 3))
    assert w.done.all()


def test_tam_ucus_kalkis_duzen_inis():
    w = fly(make_config("decentralized", None, 0.0, 4), until="flight")
    s = w.summary()
    assert (w.phase == LANDED).all(), "tüm İHA'lar üsse inmeli"
    assert np.linalg.norm(w.pos[:, :2], axis=1).max() < 60, "iniş üs pistinde olmalı"
    assert s["formation_err"] < 8.0, "düzen uçuşunda ortalama yuva hatası küçük olmalı"
    assert s["near_miss"] == 0, "iki İHA hiç 2 m'den fazla yaklaşmamalı"


def test_arazi_takibi_tepeye_carpmaz():
    w = fly(make_config("resilient", 20.0, 0.0, 5))
    assert w.summary()["min_agl"] > 20.0


def test_duzen_konsensusu_karistirmada_bozulur():
    """Elektronik harbin sürü davranışına etkisi: karıştırma uzlaşmayı bozar, düzen hatası artar."""
    temiz = fly(make_config("decentralized", None, 0.0, 6)).summary()["formation_err"]
    kirli = fly(make_config("decentralized", 30.0, 0.0, 6)).summary()["formation_err"]
    assert kirli > temiz


def test_ariza_sonrasi_sürü_gorevleri_paylasir():
    w = fly(make_config("decentralized", None, 0.0, 7, failures=3))
    assert w.m["failures"] == 3
    assert w.done.mean() >= 0.95, "düşen İHA'ların görevleri diğerlerine geçmeli"


def test_aynı_seed_ayni_harita():
    a, b = World(make_config("centralized", 20.0, 0.0, 11)), World(make_config("resilient", 20.0, 0.0, 11))
    assert np.allclose(a.tasks, b.tasks), "eşleştirilmiş deney: stratejiler aynı haritayı görmeli"
