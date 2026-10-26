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
from suru import World, decision, make_config, radio  # noqa: E402
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
    c = World(make_config("resilient", 20.0, 0.0, 11, n_popup=5, planner="greedy", failures=2))
    assert np.allclose(a.tasks, c.tasks[:20]) and np.allclose(a.value, c.value[:20]), \
        "yeni hedef, arıza ve planlayıcı ayarı baştaki görevleri değiştirmemeli"


# ------------------------------------------------------------------ otonom karar alma
def test_ekleme_kazanci_rota_puanina_esit():
    """En iyi ekleme hesabı, rotayı baştan puanlamakla aynı sonucu vermeli."""
    rng = np.random.default_rng(0)
    X, V, A = rng.uniform(0, 400, (6, 2)), rng.choice([1.0, 2.0, 3.0], 6), rng.uniform(0, 30, 6)
    R, lnlam, sp, p0 = np.ones(6), np.log(0.99), 10.0, np.zeros(2)
    path, cand = [0, 1, 2], [3, 4, 5]
    gain, pos = decision.best_insertion(p0, 5.0, X[path], V[path], A[path], R[path], X[cand], V[cand], A[cand],
                                        R[cand], lnlam, sp)
    base = decision.path_score(p0, 5.0, X[path], V[path], A[path], R[path], lnlam, sp)
    for c, g, q in zip(cand, gain, pos):
        brute = []
        for k in range(len(path) + 1):
            p = path[:k] + [c] + path[k:]
            brute.append(decision.path_score(p0, 5.0, X[p], V[p], A[p], R[p], lnlam, sp) - base)
        assert g == pytest.approx(max(brute)) and q == int(np.argmax(brute))


def test_cbba_uzlasma_kurallari():
    """Choi 2009 tablosundan örnekler (alıcı 0, gönderen 1, üçüncü İHA 2)."""
    R, k = np.array([0]), 1
    Y = np.array([[0.5, 0.9, 0.4, -np.inf], [0, 0, 0, 0], [0, 0, 0, 0.0]])
    Z = np.array([[0, 1, 2, -1], [-1, -1, -1, -1], [-1, -1, -1, -1]])
    yk = np.array([0.7, 0.3, 0.6, 0.2])
    zk = np.array([1, 0, 2, 1])
    sk = np.array([0.0, 10.0, 9.0])          # gönderen 2 hakkında daha yeni bilgiye sahip
    si = np.array([[10.0, 8.0, 5.0]])
    upd, rst = decision.cbba_merge(R, k, yk, zk, sk, Y, Z, si)
    assert upd[0, 0], "gönderen daha yüksek teklifle kazanıyorsa alıcı güncellemeli"
    assert rst[0, 1], "gönderen 'kazanan sensin' derken alıcı gönderenin kazandığını sanıyorsa sıfırlamalı"
    assert upd[0, 2], "üçüncü İHA hakkında daha yeni bilgi gelirse güncellenmeli"
    assert upd[0, 3], "alıcı kazanan bilmiyorsa gönderenin bilgisini almalı"


def test_cbba_cakismasiz_plan():
    """Bağlantı tamken CBBA uzlaşır: hiçbir görev iki İHA'nın paketinde olmaz, herkes kazananda hemfikir."""
    w = World(make_config("decentralized", None, 0.0, 2, planner="cbba"))
    while w.t < 40.0:                         # intikal sırasında (herkes birbirini duyuyor) planlama
        w.step()
    owners = {}
    for i, b in enumerate(w.bundle):
        for t in b:
            assert t not in owners, f"görev {t} hem {owners[t]} hem {i} paketinde"
            owners[t] = i
    assert len(owners) == w.T, "10 İHA x 3 görevlik paket 20 görevin hepsini kapsamalı"
    for t, i in owners.items():
        assert (w.cl_id[:, t] == i).all(), "tüm İHA'lar aynı kazananı bilmeli"


def test_cbba_acgozluden_iyi():
    """Aynı haritalarda CBBA'nın görev puanı açgözlü tek görev yönteminden yüksek, yolu kısa olmalı."""
    sc, ds = {}, {}
    for pl in ("greedy", "cbba"):
        runs = [fly(make_config("resilient", None, 0.0, s, planner=pl, n_popup=4)).summary() for s in (20, 21, 22)]
        sc[pl] = np.mean([r["score"] for r in runs])
        ds[pl] = np.mean([r["task_dist"] for r in runs])
    assert sc["cbba"] > sc["greedy"] and ds["cbba"] < ds["greedy"]


@pytest.mark.parametrize("strategy", ["centralized", "decentralized"])
def test_yeni_hedefler_yapilir(strategy):
    w = fly(make_config(strategy, None, 0.0, 8, n_popup=5))
    assert w.done.all(), "görev sırasında beliren hedefler de yapılmalı"
    assert w.summary()["popup_resp"] < 60.0


def test_canli_hedef_ekleme():
    w = World(make_config("resilient", None, 0.0, 9, live_reserve=2))
    while w.t < 90.0:
        w.step()
    t = w.add_popup()
    assert t >= 0 and w.appear[t] == pytest.approx(90.0, abs=0.2)
    while not w.finished():
        w.step()
    assert w.done[t], "elle eklenen hedef de yapılmalı"
    assert not w.done[-1] and np.isinf(w.appear[-1]), "kullanılmayan yedek hedef görünmemeli"
    # Sürü dönüşteyken eklenen hedef için İHA'lar geri döner
    while not (w.phase[w.alive] == 4).any():
        w.step()
    t2 = w.add_popup()
    while not w.flight_over():
        w.step()
    assert w.done[t2], "dönüşteyken eklenen hedef de yapılmalı (sürü geri çağrılır)"


def test_cbba_sahte_teklife_dayanir():
    w = fly(make_config("resilient", None, 0.2, 10, planner="cbba"))
    assert w.done.mean() >= 0.95, "dirençli CBBA sahte teklif yayan İHA'yı dışlamalı"


# ------------------------------------------------------------------ elektronik harp (Aşama 3)
def test_arazi_golgesi_kirinim():
    """Bıçak sırtı kırınımı: düz arazide kayıp yok, tepenin arkası birkaç dB'den fazla kayıplı."""
    assert radio.knife_edge_db(np.array([0.0]))[0] == pytest.approx(6.0, abs=0.1)
    assert radio.knife_edge_db(np.array([-1.0]))[0] == 0.0

    class Tepe:
        flat = False

        def height(self, x, y):
            return np.where(np.abs(np.asarray(x) - 500.0) < 50.0, 80.0, 0.0)
    a, b = np.array([[0.0, 0.0, 20.0]]), np.array([[1000.0, 0.0, 20.0]])
    assert radio.terrain_loss_db(a, b, Tepe())[0, 0] > 20.0
    assert radio.terrain_loss_db(a, b + [0, 0, 300.0], Tepe())[0, 0] == 0.0


def test_nokta_karistirici_ve_fhss():
    from suru import ew
    cfg = SimConfig()
    terrain = World(make_config("resilient", None, 0.0, 0)).terrain
    j = ew.Jammer({"pos": (0.0, 0.0, 15.0), "power_dbm": 20.0, "band": "nokta"}, terrain)
    p = np.array([[100.0, 0.0, 40.0]])
    assert radio.jam_power_dbm(p, [j], cfg, band="gps")[0] < -200, "nokta karıştırıcı GPS'e dokunmaz"
    w = World(make_config("resilient", 25.0, 0.0, 0, jammer_mode="nokta"))
    w2 = World(make_config("resilient", 25.0, 0.0, 0, jammer_mode="nokta", ew_fhss=False))
    for x in (w, w2):
        x.jrx = radio.jam_power_dbm(x.pos, x.jammers, x.cfg, band="comm")
        x.jrx_bar = radio.jam_power_dbm(x.pos, x.jammers, x.cfg, band="gps")
    tx, rx = np.array([[200.0, 200.0, 40.0]]), np.array([[300.0, 200.0, 40.0]])
    jam = radio.jam_power_dbm(rx, w.jammers, w.cfg, band="comm")
    per_fhss = w._per(tx, rx, jam, np.array([-300.0]))[0, 0]
    per_sabit = w2._per(tx, rx, jam, np.array([-300.0]))[0, 0]
    assert per_fhss < per_sabit, "frekans atlama nokta karıştırmaya karşı paket kaybını azaltmalı"


def test_hareketli_karistirici_yol_alir():
    w = World(make_config("resilient", 20.0, 0.0, 0, jammer_mode="hareketli"))
    p0 = w.jammers[0].xy.copy()
    for _ in range(100):
        w.step()
    assert np.linalg.norm(w.jammers[0].xy - p0) == pytest.approx(50.0, abs=1.0)   # 5 m/s x 10 s


def test_karistirma_isi_haritasi():
    """Isı haritası İHA'ların ölçtüğüyle aynı: haritadaki değer, o noktada uçan İHA'nın aldığı karıştırma."""
    import base64
    w = World(make_config("resilient", 20.0, 0.0, 0, jammer_mode="sirt"))
    f = w.frame()["jamField"]
    q = np.frombuffer(base64.b64decode(f["q"]), np.uint8).reshape(f["ny"], f["nx"])
    J = f["db0"] + f["dbStep"] * q.astype(float)
    xs, ys = f["x0"] + f["step"] * np.arange(f["nx"]), f["y0"] + f["step"] * np.arange(f["ny"])
    for iy, ix in [(f["ny"] // 3, f["nx"] // 2), (f["ny"] * 3 // 4, f["nx"] // 4), (f["ny"] - 5, f["nx"] // 2)]:
        x, y = xs[ix], ys[iy]
        p = np.array([[x, y, w.terrain.height(x, y) + w.cfg.agl]])
        beklenen = np.clip(radio.jam_power_dbm(p, w.jammers, w.cfg, w.terrain)[0], -100.0, -36.25)
        assert J[iy, ix] == pytest.approx(beklenen, abs=0.2)
    assert "jamField" not in w.frame(), "değişmeyen harita her karede gönderilmemeli"
    assert "jamField" not in World(make_config("resilient", None, 0.0, 0)).frame(), "karıştırıcı yoksa harita yok"


def test_kendi_senaryon():
    """Unity'deki "Kendi senaryon": karıştırıcılar ve GPS aldatıcı verilen noktalara konur."""
    from suru.config import parse_points
    assert parse_points("-150,300;200.5,500") == [(-150.0, 300.0), (200.5, 500.0)]
    assert parse_points("") is None
    w = World(make_config("resilient", 25.0, 0.0, 1, gps_spoof="hizli", jammer_xy=[(-150.0, 300.0), (200.0, 500.0)],
                          jammer_band="nokta", spoofer_xy=(100.0, 400.0), n_drones=8, n_tasks=12))
    assert [tuple(j.xy) for j in w.jammers] == [(-150.0, 300.0), (200.0, 500.0)]
    assert all(j.band == "nokta" and j.power == 25.0 for j in w.jammers) and w.cfg.jammer_mode == "ozel"
    assert tuple(w.gps_spoofers[0].xy) == (100.0, 400.0) and w.N == 8
    assert World(make_config("resilient", None, 0.0, 1, jammer_xy=[(0.0, 0.0)])).jammers == [], "güç kapalıysa karıştırıcı yok"


def test_ucus_raporu():
    """Uçuş raporu iniş bitince gelir; İHA'ların yaptığı hedefler toplamı tamamlanan hedef sayısına eşittir."""
    w = World(make_config("resilient", 20.0, 0.0, 3, n_popup=4, failures=1))
    assert "report" not in w.frame(), "uçuş sürerken rapor gönderilmez"
    while not w.flight_over():
        w.step()
    f = w.frame()
    r = f["report"]
    assert "jamField" not in f, "rapor ve ısı haritası aynı kareye konmaz (UDP sınırı)"
    assert sum(d["done"] for d in r["drones"]) == int(w.done.sum())
    assert sum(1 for x in r["taskBy"] if x >= 0) == int(w.done.sum())
    assert sum(d["fail"] >= 0 for d in r["drones"]) == 1, "arızalanan İHA raporda görünmeli"
    for d in r["drones"]:
        assert len(d["xy"]) == 2 * len(d["st"]) and 2 <= len(d["st"]) <= 120
        assert d["dist"] > 300.0 and d["nogps"] >= 0.0
    assert any(d["jam"] > 0 for d in r["drones"]), "karıştırma alanına giren İHA olmalı"


def test_karistirici_konum_bulma():
    from suru import ew
    cfg, rng = SimConfig(), np.random.default_rng(3)

    def olc(X, J):
        tot = sum(10 ** ((P - (40 + 25 * np.log10(np.sqrt(((X - q) ** 2).sum(1) + 625)))) / 10) for q, P in J)
        return 10 * np.log10(tot) + rng.normal(0, 2, len(X))
    X = np.c_[rng.uniform(-330, 330, 60), rng.uniform(80, 680, 60)]
    for J in ([(np.array([260.0, 230.0]), 20.0)],
              [(np.array([260.0, 230.0]), 20.0), (np.array([-230.0, 520.0]), 20.0)]):
        est, _ = ew.localize(X, olc(X, J), cfg)
        assert len(est) == len(J), "karıştırıcı sayısı doğru bulunmalı"
        q = np.array([e[0] for e in est])
        assert max(np.linalg.norm(q - j[0], axis=1).min() for j in J) < 40.0


def test_gps_aldatma_tespit_edilir():
    korumasiz = fly(make_config("decentralized", None, 0.0, 1, gps_spoof="hizli")).summary()
    direncli = fly(make_config("resilient", None, 0.0, 1, gps_spoof="hizli")).summary()
    assert korumasiz["false_done"] > 3, "aldatılan korumasız İHA hedefe vardığını sanmalı"
    assert direncli["spoof_detected"] > 0 and direncli["spoof_detect_time"] < 20.0
    assert direncli["false_done"] == 0 and direncli["completion"] >= 0.9


def test_sinsi_saldirgan_dislanir():
    s = fly(make_config("resilient", None, 0.2, 2, spoof_mode="sneaky")).summary()
    assert s["liars_caught"] == 1.0, "dürüst İHA'lar sinsi saldırganları dışlamalı"
    assert s["honest_excluded"] < 0.05, "dürüst arkadaşlar yanlışlıkla dışlanmamalı"
    assert s["completion"] >= 0.95


def test_yapay_zeka_agi():
    net = decision.AIValue()
    F = np.random.default_rng(1).uniform(0, 1, (7, len(decision.AI_FEATURES)))
    rho = net(F)
    assert rho.shape == (7,) and np.allclose(rho, 0.5), "eğitimsiz ağ her göreve aynı değeri vermeli (düz CBBA)"
    th = decision.AIValue.initial()
    th[decision.AIValue.n_in * decision.AIValue.n_hid + decision.AIValue.n_hid:-1] += 0.3   # çıkış ağırlıkları
    assert np.ptp(decision.AIValue(th)(F)) > 0.01, "çıkış ağırlıkları değişince karar değişmeli (öğrenme sinyali)"
    rho = decision.AIValue.load()(F)
    assert ((rho > 0) & (rho < 1)).all()
    w = fly(make_config("resilient", 20.0, 0.0, 12, planner="ai"))
    assert w.done.mean() >= 0.9
