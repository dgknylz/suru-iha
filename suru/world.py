"""Sürü dünyası: İHA'lar, görevler, karıştırıcılar, karar alma ve sürü zekâsı.

Koordinatlar metre cinsinden: x = doğu, y = kuzey, z = yukarı. Üs (yer istasyonu) (0, 0)'da,
görev alanı üssün kuzeyinde. Arazi yüksekliği Unity'deki 3D araziyle birebir aynıdır.

Görev akışı (her İHA kendi evresini yürütür, lider yoktur):
  kalkış -> intikal (düzende) -> görev (dağılıp görev paylaşımı) -> toplanma -> dönüş (düzende) -> iniş

Üç karar alma mimarisi karşılaştırılır:
  centralized   : Yer istasyonu görevleri dağıtır. İHA'lar sadece istasyonla konuşur.
  decentralized : İHA'lar komşularıyla konuşur, görevleri açık artırma + dedikodu
                  (gossip) ile kendi aralarında paylaşır. Lider yok.
  resilient     : decentralized + elektronik harp direnci:
                  1) karıştırmayı algılama ve ortak karıştırma haritası
                  2) karıştırma bölgesindeki arkadaşın sessizliğini "meşgul" sayma (uzun TTL)
                  3) karıştırma bölgesinden transit geçmeme ve bu görevlere ceza
                  4) GPS yokken komşulardan işbirlikçi konum düzeltmesi
                  5) görmediği hedefe "bitti" dememe, hedefte spiral arama
                  6) GPS kurtarma: konumunu kaybeden İHA GPS'i geri almaya gider
                  7) güven sistemi: makul olmayan teklif, konum yalanı ve sahte "tamamlandı"ya karşı
                  8) karıştırıcıyı bulma ve karıştırma alanını önceden kestirme
                  9) frekans atlama (FHSS) ve GPS aldatma tespiti (suru/ew.py)
                  10) radar ikaz alıcısı, radarın yerini kerteriz kestirimiyle bulma, radar görüşünden
                      kaçan rota (A*/Dijkstra) ve kilit ikazında arazinin arkasına kaçma (suru/threat.py)
                  11) enerji farkında karar: rüzgâra karşı eve dönüş enerjisini hesaplayıp görev seçme
                      ve zamanında dönme (suru/energy.py)
                  (isteğe bağlı) bağlantı koruma: kopan arkadaşa ulaşmak için kendiliğinden röle olma
                  Her mekanizma ayrı bir ayarla kapatılabilir (ablasyon deneyi).

Sürü zekâsı (suru/swarm.py): lidersiz düzen uçuşu (konsensüs), Reynolds kuralları,
arazi takibi, röle ile bağlantı koruma, üye kaybında görev ve düzenin yeniden dağıtımı.

Otonom karar alma (suru/decision.py): görevlerin değeri (önceliği) vardır ve beklendikçe azalır.
Görev sırasında yeni hedefler belirir (yer istasyonu ihbarı ya da İHA sensörü). Görev paylaşımı
CBBA (merkeziyetsiz paket planlama ve uzlaşma), SGA (merkezi) ya da eski açgözlü yöntemle yapılır.
"""
import base64
import itertools
from types import SimpleNamespace

import numpy as np
from scipy.optimize import linear_sum_assignment

from . import decision, energy, ew, radio, threat
from .config import SimConfig
from .swarm import FORMATIONS, Path, formation_offsets, largest_component, place, reynolds
from .terrain import Terrain

CELL = 50.0  # karıştırma haritası hücre boyu (m)
GRID_O, GRID_N = -1200.0, 48  # karıştırma haritası ızgarası: başlangıç köşesi (m) ve hücre sayısı

# Karıştırma ısı haritası (yalnızca görselleştirme; simülasyonu etkilemez)
FIELD_STEP = 10.0             # nokta aralığı (m)
FIELD_MAX = 128               # bir kenardaki en fazla nokta (geniş alanda aralık büyür)
FIELD_DB0, FIELD_DB_STEP = -100.0, 0.25   # bayt = (dBm - (-100)) / 0,25  ->  -100 ... -36 dBm
FIELD_RESEND = 2.0            # değişmese de kaç saniyede bir yeniden gönderilir (s)
_FIELD_REV = itertools.count(1)   # her yeni harita farklı numara alır (dünya yeniden kurulsa da)
TRACK_MAX = 120               # uçuş raporunda İHA başına en fazla iz noktası

# Uçuş evreleri
TAKEOFF, TRANSIT, TASK, REGROUP, RETURN, LAND, LANDED = range(7)
RTB_FLAG = -2                 # sürü durum tablosunda (st_relay) "bataryası azaldı, eve dönüyor" işareti
RADAR_RESEND = 3.0            # radar görüş haritası değişmese de kaç saniyede bir yeniden gönderilir (s)
PHASE_NAMES = ("kalkis", "intikal", "gorev", "toplanma", "donus", "inis", "indi")
AIRBORNE = (TAKEOFF, TRANSIT, TASK, REGROUP, RETURN, LAND)


def phase_mask(*phases):
    """Evre numarasından hızlı bakış tablosu: M[self.phase] -> bu evrelerde mi? (np.isin'den hızlı)"""
    m = np.zeros(7, bool)
    m[list(phases)] = True
    return m


M_FORM = phase_mask(TRANSIT, RETURN)            # düzende uçuş
M_GROUND = phase_mask(TAKEOFF, LAND, LANDED)    # üs üstünde
M_EARLY = phase_mask(TAKEOFF, TRANSIT)
M_WORK = phase_mask(TASK, REGROUP)              # görev alanında
M_CRUISE = phase_mask(TRANSIT, TASK, REGROUP, RETURN)

_TERRAIN_CACHE = {}


def cell_of(p):
    return (int(np.floor(p[0] / CELL)), int(np.floor(p[1] / CELL)))


def cell_idx(x, y):
    """Konumun karıştırma haritası ızgarasındaki hücresi (ix, iy)."""
    ix = np.clip(np.floor((np.asarray(x, float) - GRID_O) / CELL).astype(int), 0, GRID_N - 1)
    iy = np.clip(np.floor((np.asarray(y, float) - GRID_O) / CELL).astype(int), 0, GRID_N - 1)
    return ix, iy


def cell_centers(grid):
    ix, iy = np.nonzero(grid)
    return np.c_[ix, iy].astype(float) * CELL + GRID_O + CELL / 2


def shared_terrain(flat, region="ova"):
    """Arazi dosyası bir kez yüklenir, tüm simülasyonlar paylaşır."""
    key = (flat, region)
    if key not in _TERRAIN_CACHE:
        _TERRAIN_CACHE[key] = Terrain(flat=flat, region=region)
    return _TERRAIN_CACHE[key]


class World:
    def __init__(self, cfg: SimConfig):
        self.cfg = c = cfg
        self.rng = rng = np.random.default_rng(c.seed)
        self.N, self.T = N, T = c.n_drones, c.n_tasks
        self.t, self.k = 0.0, 0
        self.resilient = c.strategy == "resilient"
        self.central = c.strategy == "centralized"
        self.relay_on = c.relay_enabled()
        self.terrain = shared_terrain(not c.terrain, c.region)
        self.cbba = c.planner in ("cbba", "ai")
        self.ai = None
        if c.planner == "ai":
            self.ai = (decision.AIValue(c.ai_theta) if len(c.ai_theta)
                       else decision.AIValue.load(c.ai_weights or decision.AI_WEIGHTS))
        self.lnlam = float(np.log(c.discount))
        self.cruise = 0.9 * c.max_speed           # plan yaparken kullanılan seyir hızı tahmini
        # Dirençli stratejinin mekanizmaları (her biri ablasyon için ayrı kapatılabilir)
        R = self.resilient
        self.ew = SimpleNamespace(**{k: R and getattr(c, "ew_" + k) for k in (
            "jam_map", "long_ttl", "avoid", "coop_loc", "search", "recover", "trust", "localize", "fhss",
            "spoof_detect", "valuation", "radar", "energy")})
        self.sneaky = c.spoof_mode == "sneaky"

        # Görevler ve saldırganlar aynı tohumla önce çekilir: aynı seed'de
        # üç strateji de AYNI görev haritasıyla karşılaşır (eşleştirilmiş deney).
        ac, h = np.asarray(c.area_center, float), c.area_half
        txy = np.c_[rng.uniform(ac[0] - h + 30, ac[0] + h - 30, T), rng.uniform(ac[1] - h + 30, ac[1] + h - 30, T)]
        # Görev değerleri ve yeni beliren hedefler ayrı bir rastgele akıştan çekilir: diğer
        # ayarlar (arıza, saldırgan...) değişse de aynı seed'de aynı kalırlar.
        rng2 = np.random.default_rng([c.seed, 7])
        P, Rv = c.n_popup, c.live_reserve
        v_static = rng2.choice([1.0, 2.0, 3.0], c.n_tasks, p=[0.5, 0.3, 0.2])
        pxy = np.c_[rng2.uniform(ac[0] - h + 30, ac[0] + h - 30, P), rng2.uniform(ac[1] - h + 30, ac[1] + h - 30, P)]
        v_pop = rng2.choice([2.0, 3.0], P)          # yeni hedefler genelde acil
        t_pop = np.sort(rng2.uniform(*c.popup_window, P))
        txy = np.vstack([txy, pxy, np.tile(ac, (Rv, 1))])
        self.T = T = T + P + Rv
        self.n_popup = P
        self.value = np.ones(T)
        if c.priorities:
            self.value[:c.n_tasks] = v_static
            self.value[c.n_tasks:c.n_tasks + P] = v_pop
        self.value[c.n_tasks + P:] = 3.0
        self.appear = np.zeros(T)
        self.appear[c.n_tasks:c.n_tasks + P] = t_pop
        self.appear[c.n_tasks + P:] = np.inf      # yedek hedefler: ancak elle eklenince belirir
        self.popup = np.zeros(T, bool)
        self.popup[c.n_tasks:] = True
        # Ödülün azalmaya başladığı an: baştaki görevler için sürünün alana vardığı an
        t_area = c.takeoff_time + float(np.linalg.norm(ac)) / c.transit_speed
        self.ref_t = np.where(self.popup, self.appear, t_area)
        self.task_ground = self.terrain.height(txy[:, 0], txy[:, 1])
        self.tasks = np.c_[txy, self.task_ground + c.agl]
        self.task_ix, self.task_iy = cell_idx(self.tasks[:, 0], self.tasks[:, 1])
        self.spoofer = np.zeros(N, bool)
        n_sp = int(round(c.spoof_fraction * N))
        if n_sp:
            self.spoofer[rng.choice(N, n_sp, replace=False)] = True
        # Arızalar (en son çekilir; eski deneylerle aynı görev haritası korunur)
        self.alive = np.ones(N, bool)
        self.fail_at = np.full(N, np.inf)
        if c.failures:
            cand = np.nonzero(~self.spoofer)[0]
            who = rng.choice(cand, min(c.failures, len(cand)), replace=False)
            # görev evresinde: sürü alana vardıktan 3-35 s sonra
            t_area = c.takeoff_time + float(np.linalg.norm(c.area_center)) / c.transit_speed
            self.fail_at[who] = rng.uniform(t_area + 3, t_area + 35, len(who))

        self.home = np.zeros(2)
        self.rally = ac.copy()                       # toplanma noktası: görev alanının ortası
        g0 = float(self.terrain.height(0.0, 0.0))
        self.gcs = np.array([0.0, 0.0, g0 + 10.0])
        ang = np.linspace(0, 2 * np.pi, N, endpoint=False)
        self.pos = np.c_[12 * np.cos(ang), 12 * np.sin(ang), np.full(N, g0 + 0.3)]
        self.vel = np.zeros((N, 3))
        self.est = self.pos.copy()          # İHA'nın kendi konum kestirimi
        self.bias = np.zeros((N, 3))        # GPS yokken biriken IMU hatası
        self.dr_t = np.zeros(N)             # son konum düzeltmesinden beri geçen süre
        self.sig0 = np.full(N, 1.5)         # son düzeltmedeki konum belirsizliği (m)

        # Elektronik harp
        self.jammers = [ew.Jammer(j, self.terrain) for j in c.jammers]
        self.spot = any(j.band == "nokta" for j in self.jammers)
        self.gps_spoofers = [ew.GpsSpoofer(s) for s in c.gps_spoofers]
        self.jrx = np.full(N, -300.0)       # haberleşme kanalına düşen karıştırma (dBm)
        self.jrx_bar = np.full(N, -300.0)   # yalnızca geniş bant karıştırma (GPS'i ve FHSS'i de etkiler)
        self._field, self._field_key = None, None           # karıştırma ısı haritası (bkz. jam_field)
        self._field_sent, self._field_sent_t = 0, -np.inf

        # Hava savunma tehdidi (suru/threat.py). Radar, rüzgâr ve batarya kendi rastgele akışlarını kullanır:
        # bunlar yokken eski deneylerin sonuçları birebir aynı kalır.
        self.rng_r = np.random.default_rng([c.seed, 13])
        self.radars = [threat.Radar(d, self.terrain, N, k) for k, d in enumerate(c.radars)]
        self.missiles = []
        self._mid = itertools.count()                    # füze numarası (Unity füzeleri bununla eşler)
        self.MR = 600                                    # kerteriz ölçümü halka tamponu
        self.rw_xy = np.zeros((self.MR, 2))              # ölçümün yapıldığı yer (İHA'nın kestirdiği konum)
        self.rw_b = np.zeros(self.MR)                    # ölçülen kerteriz (pusula, radyan)
        self.rw_t = np.full(self.MR, -np.inf)
        self.rw_e = np.full(self.MR, -1)                 # radar imzası (hangi radar)
        self.rw_n = 0
        self.rw_k = np.zeros((N, self.MR), bool)         # rw_k[i, m]: i, m ölçümünü biliyor (dedikoduyla yayılır)
        self.rw_lit = np.full(N, -np.inf)                # radar ikaz alıcısının son ikazı
        self.rw_lock = np.zeros(N, bool)                 # kilit ikazı: bir radar bu İHA'yı izliyor
        self.rw_lock_by = np.full(N, -1)                 # kilitleyen radar (imzasından tanınır)
        self.rd_est = [dict() for _ in range(N)]         # İHA'nın bildiği radarlar: radar no -> (konum, hata)
        for R in self.radars:                            # istihbarat: bilinen radarların yeri görev emrinde gelir
            if R.known:
                e = R.xy + self.rng_r.normal(0, c.intel_err / np.sqrt(2.0), 2)
                for i in range(N):
                    self.rd_est[i][R.id] = (e.copy(), float(c.intel_err))
        self.tmaps = {}                                  # tehdit haritası önbelleği (aynı bilgiyle aynı harita)
        self.route = [None] * N                          # tehdit farkında rota (Path) ya da düz
        self.route_goal = np.full((N, 2), np.inf)
        self.route_key = [None] * N
        self.route_t = np.full(N, -np.inf)
        self.evade_until = np.full(N, -np.inf)           # kilit ikazında arazinin arkasına kaçış
        self.evade_to = np.zeros((N, 2))
        self.low = np.zeros(N, bool)                     # tehdit bölgesinde alçak uçuş
        self.rd_err_log = []                             # (t, hata) sürünün radar konum kestirimi
        self.t_radar_fix = np.nan
        self.radar_track_t = np.zeros(N)                 # İHA'nın radar tarafından izlendiği süre
        self._rfield, self._rfield_key, self._rfield_sent, self._rfield_sent_t = None, None, 0, -np.inf
        self._plan_key = None

        # Enerji ve rüzgâr (suru/energy.py)
        self.wind = energy.Wind(c.wind_speed, c.wind_from, c.gust, np.random.default_rng([c.seed, 11]))
        soc = energy.BATTERY_MODES.get(c.battery)
        soc0 = np.ones(N) if soc is None else np.resize(np.asarray(soc, float), N)
        if soc is not None:
            np.random.default_rng([c.seed, 12]).shuffle(soc0)
        self.bat = soc0 * energy.CAPACITY_WH             # bataryada kalan enerji (Wh)
        self.bat0 = self.bat.copy()
        self.power = np.zeros(N)                         # anlık çekilen güç (W)
        self.energy_on = self.wind.on or soc is not None
        self.rtb = np.zeros(N, bool)                     # bataryası azaldığı için eve dönüyor
        self.unaffordable = np.zeros(N, bool)            # açık görev var ama hiçbirine gidip dönmeye enerjisi yetmiyor
        # Uçuş raporu (yalnızca gösterim, bkz. report): İHA başına sayaçlar, süreler ve 3 s'de bir iz
        self.r = SimpleNamespace(
            done=np.zeros(N, int), wrong=np.zeros(N, int), search=np.zeros(N, int), recover=np.zeros(N, int),
            dist=np.zeros(N), nogps=np.zeros(N), jam=np.zeros(N), relay=np.zeros(N), spoofed=np.zeros(N),
            seen=np.zeros(N, bool), fail_t=np.full(N, np.nan), track=[[] for _ in range(N)],
            task_by=np.full(self.T, -1), cause=[""] * N, wh=np.zeros(N), rtb=np.full(N, np.nan))
        self._report_frames = 0
        self.gps_rx = np.ones(N, bool)      # alıcı GPS çözümü üretiyor mu (gerçek ya da sahte)
        self.gps_trust = np.ones(N, bool)   # İHA GPS'ine güveniyor mu (aldatma tespit edilince hayır)
        self.gps_ok = np.ones(N, bool)      # İHA konumu için GPS kullanıyor mu (= alıyor ve güveniyor)
        self.spoofed = np.zeros(N, bool)    # gerçek durum: GPS'i aldatıcı tarafından ele geçirilmiş
        self.spoof_off = np.zeros((N, 3))   # aldatıcının İHA'nın GPS konumuna eklediği kayma
        self.gps_hist = np.full((N, 12, 4), np.nan)   # IMU tutarlılık testi: 1 Hz (GPS x, y, gerçek x, y)
        self.peer_bad = np.zeros(N, int)    # komşu menzil testinde art arda tutarsızlık sayısı
        self.peer_good = np.zeros(N, int)
        self.m_spoof_detect = []            # aldatma tespit süreleri (ele geçirilmeden tespite, s)
        self.spoof_log = []                 # (t, İHA, sebep, gerçekten aldatılıyor mu, sigma)
        self.captured_at = np.full(N, np.nan)
        self.last_spoofed = np.full(N, -np.inf)
        # Karıştırıcı konum bulma: her İHA 1 Hz'de ölçtüğü karıştırma gücünü kaydeder (halka tampon)
        self.MB = 60
        self.meas_t = np.full((N, self.MB), -np.inf)
        self.meas_xy = np.zeros((N, self.MB, 2))
        self.meas_db = np.zeros((N, self.MB))
        self.meas_n = np.zeros(N, int)
        self.loc_est = [[] for _ in range(N)]   # her İHA'nın kestirdiği karıştırıcılar [(xy, dBm)]
        self.loc_err_log = []                   # (t, hata) sürünün en iyi kestirimi
        self.t_locate = np.nan

        self.done = np.zeros(T, bool)       # gerçek durum
        self.done_time = np.full(T, np.nan)

        # Her İHA'nın kafasındaki dünya
        self.known_task = np.zeros((N, T), bool)     # İHA bu hedefin varlığını biliyor mu
        self.known_task[:, ~self.popup] = True       # baştaki hedefler görev emrinde bildirildi
        self.known_done = np.zeros((N, T), bool)
        self.cl_bid = np.full((N, T), -np.inf)   # bildiği en iyi teklif
        self.cl_id = np.full((N, T), -1)         # o teklifi veren İHA
        self.cl_time = np.full((N, T), -np.inf)  # teklifin zaman damgası
        self.my_task = np.full(N, -1)
        self.task_since = np.zeros(N)            # şimdiki hedefe ne zamandan beri gidiliyor
        self.bundle = [[] for _ in range(N)]     # (cbba) paket: görevler eklenme sırasıyla
        self.path = [[] for _ in range(N)]       # (cbba) rota: görevler uçuş sırasıyla; ilki my_task
        self.search = np.zeros(N)                # spiral arama açısı (0 = arama yok)
        self.search_r = np.zeros(N)              # aramanın biteceği yarıçap (m)
        self.search_sig = np.zeros(N)            # aramaya başlarkenki konum belirsizliği
        self.recover = np.zeros(N, bool)         # (dirençli) GPS'i geri almaya gidiyor
        self.recover_to = np.zeros((N, 2))       # GPS'i geri almak için gidilen nokta
        self.recover_block = np.zeros(N)         # bu andan önce yeniden kurtarma denenmez
        self.last_fix = self.pos[:, :2].copy()   # son GPS alınan nokta
        self.distrust = np.zeros((N, N), bool)   # distrust[j, i]: j, i'ye güvenmiyor
        # Güven sistemi (Beta itibarı): olumlu ve olumsuz kanıt sayıları; güven = (a+1)/(a+b+2)
        self.tr_a = np.zeros((N, N))
        self.tr_b = np.zeros((N, N))
        self.hard_bad = np.zeros((N, N), bool)   # kesin kanıt (makul olmayan teklif)
        self.soft_bad = np.zeros((N, N), bool)   # itibarı düşük
        self.own_bad = np.zeros((N, N), bool)    # kendi kanıtıyla güvenmedikleri
        self.hold_task = np.full((N, N), -1)
        self.sneaky_hold = [[] for _ in range(N)]
        self.accuse = np.zeros((N, N, N), bool)  # accuse[i, k, w]: i, w'nin k'yi suçladığını biliyor
        self.done_by = np.full((N, T), -1)       # done_by[i, t]: i'ye t'nin yapıldığını bildiren (kaynak) İHA
        self.st_sig = np.zeros((N, N))           # i'nin bildiği k'nın konum belirsizliği
        self.prev_claim = np.full((N, N, 3), np.nan)   # i'nin k'den en son duyduğu konum (hız kontrolü)
        self.prev_claim_t = np.full((N, N), -np.inf)
        self.hold_since = np.full((N, N), np.inf)      # i'ye göre k ne zamandan beri görev tutuyor
        self.hold_dist = np.full((N, N), np.inf)       # o andaki hedefe uzaklığı
        self.next_fake_done = np.full(N, c.takeoff_time + 60.0)
        # Karıştırma haritası: her hücrenin en son karıştırıldığı görülen an (hareketli karıştırıcı için eskir)
        self.jam_t = np.full((N, GRID_N, GRID_N), -np.inf)
        gx, gy = np.meshgrid(np.arange(GRID_N), np.arange(GRID_N), indexing="ij")
        self._cell_xy = np.c_[gx.ravel(), gy.ravel()].astype(float) * CELL + GRID_O + CELL / 2
        self.jam_grid = np.zeros((N, GRID_N, GRID_N), bool)   # şu an geçerli karıştırma hücreleri
        self.spf_t = np.full((N, GRID_N, GRID_N), -np.inf)   # GPS aldatma görülen hücreler
        self.link_q = np.zeros((N, N))
        self.heard = np.zeros((N, N), bool)
        self.cooldown = np.zeros((N, T))         # (dirençli) i, t'yi bu andan önce tekrar deneyemez

        # Sürü durumu: her İHA, arkadaşları hakkında bildiği en yeni bilgiyi tutar (dedikodu ile yayılır)
        self.st_t = np.full((N, N), -np.inf)     # st_t[i, k]: i'nin k hakkındaki bilgisinin zamanı
        self.st_pos = np.zeros((N, N, 3))
        self.st_task = np.full((N, N), -1)
        self.st_phase = np.zeros((N, N), int)
        self.st_relay = np.full((N, N), -1)      # k kimin için röle (-1: değil)

        # Evreler, düzen uçuşu ve röle
        self.phase = np.full(N, TAKEOFF)
        self.phase_t = np.zeros(N)
        self.idle_t = np.zeros(N)
        self.lead_s = np.zeros(N)                # sanal liderin rota üzerindeki ilerlemesi (her İHA'nın tahmini)
        self.form_kind = c.formation
        self.paths = {TRANSIT: Path([self.home, self.rally]), RETURN: Path([self.rally, self.home])}
        self.slot_err = np.zeros(N)
        self.slot_err_true = np.zeros(N)
        self.slot = np.arange(N)                 # düzendeki yuva numarası
        self.group = np.full(N, -1)              # hangi düzen grubunda (yuva ataması için)
        self.next_assign = 0.0
        self.relay_for = np.full(N, -1)
        self.relay_pos = np.zeros((N, 2))
        self.relay_since = np.zeros(N)

        # Merkezi mimari
        self.gcs_done = np.zeros(T, bool)
        self.gcs_assign = np.full(N, -1)
        self.gcs_plan = {}                    # (cbba) SGA planı: İHA -> görev listesi
        self.next_gcs_plan = 0.0
        self.gcs_pos = np.full((N, 3), np.nan)
        self.gcs_seen = np.full(N, -np.inf)   # istasyon İHA'yı en son ne zaman duydu
        self.last_gcs = np.zeros(N)           # İHA istasyonu en son ne zaman duydu
        self.gcs_up = np.zeros(N, bool)
        self.gcs_return_t = np.inf            # istasyonun "eve dön" emri verdiği an
        self.next_spoof = np.full(N, c.spoof_period)

        self.m = dict(redundant=0, false_done=0, retries=0, near_miss=0, pdr_sum=0.0, pdr_n=0,
                      locerr_sum=0.0, locerr_n=0, lam2_sum=0.0, lam2_n=0, msgs=0,
                      conn_sum=0.0, conn_n=0, form_sum=0.0, form_n=0, min_agl=np.inf, low_agl=0,
                      relay_time=0.0, failures=0, reassign=0, task_dist=0.0, spoof_false_alarm=0)
        self.last_pdr = 1.0
        self.last_conn = 1.0
        self.finished_t = np.nan
        self.idle_since = np.nan

        # Yapay zekâ eğitim verisi: her "İHA hedefe yöneldi" denemesinin özellikleri ve sonucu
        self.attempts = []                       # (özellikler, sonuç 1/0, uzman kuralının rho'su)
        self.att_task = np.full(N, -1)
        self.att_feat = [None] * N

        # (Dirençli) bilinen radarlara göre toplanma noktası, intikal ve dönüş rotası
        if self.ew.radar and self.radars:
            self._plan_threat_paths()

    # ------------------------------------------------------------------ deneme kaydı
    def _log_attempts(self):
        """Görev evresinde yeni bir hedefe yönelen İHA için deneme açar; hedefi başka sebeple
        değişen (teklifi geçildi, başkası yaptı, düştü) denemeler sayılmadan kapanır."""
        for i in range(self.N):
            t = self.my_task[i] if (self.alive[i] and not self.spoofer[i] and self.phase[i] == TASK) else -1
            if self.att_task[i] == t:
                continue
            self.att_task[i] = -1                # önceki deneme sonuçsuz kapanır
            if t >= 0:
                self.att_task[i] = t
                rule = np.exp(self.lnlam * (self.cfg.jam_penalty / self.cruise * float(self._tasks_in_jam(i)[t])
                                            + self._search_time(i)))
                self.att_feat[i] = (self._ai_features(i)[t].copy(), float(rule))

    def _close_attempt(self, i, success):
        if self.cfg.log_attempts and self.att_task[i] >= 0:
            f, rule = self.att_feat[i]
            self.attempts.append((f, int(success), rule))
        self.att_task[i] = -1

    # ------------------------------------------------------------------ döngü
    def step(self):
        c = self.cfg
        self.t += c.dt
        self.k += 1
        self._failures()
        self.wind.step(c.dt)
        for j in self.jammers:
            j.step(c.dt)
        if self.jammers:
            self.jrx = radio.jam_power_dbm(self.pos, self.jammers, c, self.terrain, band="comm")
            self.jrx_bar = radio.jam_power_dbm(self.pos, self.jammers, c, self.terrain, band="gps")
        self.gps_rx = self.jrx_bar < c.gps_jam_dbm
        if self.gps_spoofers:
            self._gps_spoofing()
        self.gps_ok = self.gps_rx & self.gps_trust
        if self.k % c.comm_every == 0:
            self._communicate()
            self._decide()
            self._swarm_logic()
        if self.k % 10 == 0:                     # 1 Hz: ölçümler, aldatma testi, karıştırıcı konum bulma
            self._ew_1hz()
        self._navigate()
        self._update_estimates()
        if self.radars:
            self._radar_step()
        self._energy_step()
        self._check_arrivals()
        if c.log_attempts:
            self._log_attempts()
        self._metrics()
        if np.isnan(self.finished_t) and self.all_done():
            self.finished_t = self.t
        # Sürü "iş bitti" dedi mi? Tüm canlı dürüst İHA'lar boşta kaldıysa görev biter.
        busy = (self.my_task >= 0) | (self.phase <= TRANSIT) | self.recover
        idle = not (busy & ~self.spoofer & self.alive).any()
        if not idle:
            self.idle_since = np.nan
        elif np.isnan(self.idle_since):
            self.idle_since = self.t

    def finished(self):
        """Görev bitti mi? (deneyler burada durur)"""
        c = self.cfg
        stalled = not np.isnan(self.idle_since) and self.t - self.idle_since > c.idle_stop
        return self.all_done() or self.t >= c.max_time or stalled

    def all_done(self):
        """Planlanan tüm hedefler (henüz belirmemiş yeni hedefler dahil) yapıldı mı?"""
        return bool(self.done[np.isfinite(self.appear)].all())

    def flight_over(self):
        """Uçuş bitti mi? (canlı gösterimde dönüş ve iniş de izlenir)"""
        flying = self.alive & (self.phase != LANDED)
        return not flying.any() or self.t >= self.cfg.max_time + 240

    def mission_time(self):
        """Görevin bittiği an: hepsi yapıldıysa o an, sürü boşta kaldıysa boşta kaldığı an."""
        if not np.isnan(self.finished_t):
            return float(self.finished_t)
        if not np.isnan(self.idle_since) and self.t - self.idle_since > self.cfg.idle_stop:
            return float(self.idle_since)
        return float(self.t)

    # ------------------------------------------------------------ yardımcılar
    def sigma(self, i):
        """İHA'nın kendi konum belirsizliği tahmini (m). IMU sapması rastgele yürüyüş
        olduğu için hata t^1.5 ile büyür: sigma^2 = sigma0^2 + q^2 t^3 / 3"""
        q = self.cfg.imu_drift
        return float(np.sqrt(self.sig0[i] ** 2 + q * q * self.dr_t[i] ** 3 / 3))

    def _tasks_in_jam(self, j):
        return self.jam_grid[j, self.task_ix, self.task_iy]

    def _ttl(self, j):
        ttl = np.full(self.T, self.cfg.claim_ttl)
        if self.ew.long_ttl:
            ttl[self._tasks_in_jam(j)] = self.cfg.claim_ttl_jam
        return ttl

    def _ttl_all(self):
        """Tüm İHA'lar için görev sahiplenme geçerlilik süreleri (N, T)."""
        if not self.ew.long_ttl:
            return np.full((self.N, self.T), self.cfg.claim_ttl)
        return np.where(self.jam_grid[:, self.task_ix, self.task_iy], self.cfg.claim_ttl_jam, self.cfg.claim_ttl)

    def _plan_start(self, i, pos=None):
        """Planın başladığı yer ve an. İntikaldeki İHA görev alanına varınca başlar."""
        c = self.cfg
        if self.phase[i] in (TAKEOFF, TRANSIT):
            rest = self.paths[TRANSIT].length - self.lead_s[i]
            return self.rally.copy(), self.t + max(c.takeoff_time - self.t, 0.0) + rest / c.transit_speed
        return (self.est[i, :2] if pos is None else pos[:2]).copy(), self.t

    def _rho(self, i):
        """İHA i'nin her görevi başarma çarpanı (0-1). Düz CBBA: hepsi 1.
        Dirençli (uzman kuralı): karıştırma bölgesindeki görev 'jam_penalty' metre daha uzakmış gibi,
        konum belirsizliği de beklenen arama süresi kadar gecikme gibi değerlendirilir.
        Yapay zekâ: sinir ağı başarı olasılığını kestirir.
        (Radar tehdidi değere katılmaz: İHA'ların tehdit haritaları biraz farklı olduğundan teklifler tutarsızlaşır,
        uzlaşma salınır. Radar, görev adaylarını süzen kesin bir kuralla hesaba katılır: _allowed.)"""
        if self.ai is not None:
            rho = self.ai(self._ai_features(i))
        else:
            rho = np.ones(self.T)
            if self.ew.valuation:
                rho[self._tasks_in_jam(i)] = np.exp(self.lnlam * self.cfg.jam_penalty / self.cruise)
                rho *= np.exp(self.lnlam * self._search_time(i))
        return rho

    def _search_time(self, i):
        """Konum belirsizliğinin zaman maliyeti: hedefte beklenen spiral arama süresi (s).
        Arşimet spirali yarıçapı R olan daireyi ~ R^2 / (2 b v) saniyede tarar."""
        c = self.cfg
        sig = self.sigma(i)
        if sig <= c.task_radius / 2:
            return 0.0
        R = min(2.5 * sig + 10.0, 100.0)
        return R * R / (2 * c.search_detect / np.pi * 9.0)

    def _ai_features(self, i):
        """Yapay zekânın her görev için gördüğü özellikler (decision.AI_FEATURES sırasıyla)."""
        c, T = self.cfg, self.T
        p = self.est[i, :2]
        F = np.zeros((T, len(decision.AI_FEATURES)))
        grid = self.jam_grid[i]
        F[:, 0] = grid[self.task_ix, self.task_iy]
        if grid.any():
            s = np.linspace(0.0, 1.0, 6)[None, :, None]
            pts = p[None, None, :] + s * (self.tasks[:, None, :2] - p[None, None, :])
            ix, iy = cell_idx(pts[..., 0], pts[..., 1])
            F[:, 1] = grid[ix, iy].mean(1)
        F[:, 2] = float(not self.gps_ok[i])
        F[:, 3] = np.log1p(self.sigma(i) / c.task_radius)
        F[:, 4] = float(np.clip((self.jrx[i] + 100.0) / 30.0, 0, 1))
        F[:, 5] = np.linalg.norm(self.tasks[:, :2] - p, axis=1) / 300.0
        F[:, 6] = self.value / 3.0
        F[:, 7] = float(self.heard[:, i].mean())
        return F

    def _set_task(self, i):
        """Rotadaki ilk görev şimdiki görevdir."""
        new = self.path[i][0] if self.path[i] else -1
        old = self.my_task[i]
        if new != old:
            # Yarım bırakılan hedef (yeniden planlama). Yeni hedef belirince birkaç İHA aynı anda
            # teklif verir, uzlaşma bir iki turda kazananı seçer; bu kısa ihale anları sayılmaz.
            if old >= 0 and new >= 0 and not self.known_done[i, old] and self.phase[i] == TASK \
                    and self.t - self.task_since[i] >= 2.0:
                self.m["reassign"] += 1
            self.my_task[i], self.search[i] = new, 0
            self.task_since[i] = self.t

    def _drop(self, i, t):
        """Görevi İHA'nın paketinden ve rotasından çıkarır."""
        if t in self.bundle[i]:
            self.bundle[i].remove(t)
        if t in self.path[i]:
            self.path[i].remove(t)
        self.my_task[i] = -1
        self.search[i] = 0
        self._set_task(i)

    def _clear_plan(self, i):
        self.bundle[i], self.path[i] = [], []
        self.my_task[i], self.search[i] = -1, 0

    def _bids(self, j):
        """Teklif = -(göreve uzaklık). Yakın olan kazanır."""
        b = -np.linalg.norm(self.tasks[:, :2] - self.est[j, :2], axis=1)
        if self.ew.valuation:
            b = b - self.cfg.jam_penalty * self._tasks_in_jam(j)
        return b

    def _set_phase(self, i, ph):
        if self.phase[i] != ph:
            self.phase[i] = ph
            self.phase_t[i] = self.t
            if ph in (TRANSIT, RETURN):
                # Düzene geç katılan, duyduğu arkadaşların ilerlemesinden başlar
                nb = self.heard[:, i] & self.alive & (self.phase == ph)
                nb[i] = False
                self.lead_s[i] = float(self.lead_s[nb].max()) if nb.any() else 0.0

    def _release_claim(self, i):
        mine = self.cl_id[i] == i
        self.cl_bid[i, mine], self.cl_id[i, mine], self.cl_time[i, mine] = -np.inf, -1, -np.inf
        self._clear_plan(i)

    # ----------------------------------------------------------- arızalar
    def _failures(self):
        for i in np.nonzero(self.alive & (self.t >= self.fail_at))[0]:
            self.fail_drone(i)

    def fail_drone(self, i=None, cause="ariza"):
        """İHA'yı arızalandırır. i verilmezse rastgele dürüst bir İHA.
        cause: ariza (motor arızası), radar (hava savunma düşürdü), batarya (bataryası bitti)."""
        if i is None:
            cand = np.nonzero(self.alive & ~self.spoofer & (self.phase != LANDED))[0]
            if len(cand) <= 1:
                return
            i = int(self.rng.choice(cand))
        self.alive[i] = False
        self.r.fail_t[i] = self.t
        self.r.cause[i] = cause
        self._track_point(i)
        self._clear_plan(i)
        self.relay_for[i], self.recover[i] = -1, False
        self.m["failures"] += 1

    # ----------------------------------------------------------- haberleşme
    def _communicate(self):
        c, N = self.cfg, self.N
        self.jam_grid = self.jam_t > self.t - c.jam_cell_ttl
        self.tl_dd = radio.terrain_loss_db(self.pos, self.pos, self.terrain) if c.terrain_radio else None
        per = self._per(self.pos, self.pos, self.jrx, self.jrx_bar, extra=self.tl_dd)
        np.fill_diagonal(per, 1.0)
        dead = ~self.alive
        per[dead, :] = 1.0
        per[:, dead] = 1.0
        self.link_q = 1.0 - per
        heard = self.rng.random((N, N)) > per          # heard[i, j]: j, i'nin mesajını aldı
        self.heard = heard
        in_range = radio.dist_matrix(self.pos) < c.comm_range
        np.fill_diagonal(in_range, False)
        in_range &= self.alive[:, None] & self.alive[None, :]
        if in_range.any():
            self.last_pdr = float(heard[in_range].mean())
            self.m["pdr_sum"] += self.last_pdr
            self.m["pdr_n"] += 1
        self.m["msgs"] += int(self.alive.sum())

        self._discover()
        if self.central:
            self._gcs_link()
        else:
            if self.n_popup or np.isfinite(self.appear[self.popup]).any():
                self._gcs_broadcast()
            self._gossip(heard)
        if self.ew.coop_loc:
            self._coop_localize(heard)
        if self.ew.radar and self.rw_n:
            # Kerteriz ölçümleri dedikoduyla yayılır (güvenilmeyen ve saldırgan İHA'nın ölçümü alınmaz)
            H = heard & ~self.distrust.T & ~self.spoofer[:, None]
            self.rw_k |= (H.T.astype(np.int32) @ self.rw_k.astype(np.int32)) > 0

    def _per(self, tx, rx, jam_all, jam_bar, gain=0.0, max_range=None, extra=None):
        """Paket kaybı olasılığı. Nokta karıştırıcı varken frekans atlamalı (FHSS) İHA'nın paketlerinin
        yalnızca %24'ü karıştırılan kanala düşer; geri kalanı yalnızca geniş bant karıştırmayı görür."""
        c = self.cfg
        per, _ = radio.link_per(tx, rx, jam_all, c, gain_db=gain, max_range=max_range, extra_loss_db=extra)
        if self.spot and self.ew.fhss:
            miss, _ = radio.link_per(tx, rx, jam_bar, c, gain_db=gain, max_range=max_range, extra_loss_db=extra)
            per = ew.FHSS_HIT * per + (1 - ew.FHSS_HIT) * miss
        return per

    def _gcs_terrain(self):
        return radio.terrain_loss_db(self.gcs, self.pos, self.terrain) if self.cfg.terrain_radio else None

    def _discover(self):
        """Yeni beliren hedefi, yakınından geçen İHA'nın sensörü görür."""
        new = (self.appear <= self.t) & self.popup
        if not new.any():
            return
        idx = np.nonzero(new)[0]
        d = np.linalg.norm(self.pos[:, None, :2] - self.tasks[None, idx, :2], axis=2)
        seen = (d < self.cfg.detect_range) & (self.alive & ~self.spoofer)[:, None]
        self.known_task[:, idx] |= seen

    def _gcs_broadcast(self):
        """Merkeziyetsiz stratejilerde yer istasyonu sadece yeni hedef ihbarını yayınlar;
        görev dağıtmaz. Karıştırılan İHA ihbarı duyamayabilir (komşusundan öğrenir)."""
        c = self.cfg
        per_dn = self._per(self.gcs, self.pos, self.jrx, self.jrx_bar, c.gcs_gain_db, np.inf, self._gcs_terrain())
        dn = (self.rng.random(self.N) > per_dn[0]) & self.alive
        self.known_task[dn] |= (self.appear <= self.t)[None, :]

    def _gossip(self, heard):
        c, N, now = self.cfg, self.N, self.t
        # 1) Herkes kendi durumunu tablosuna yazar
        for i in np.nonzero(self.alive)[0]:
            self.st_t[i, i], self.st_pos[i, i] = now, self.est[i]
            self.st_task[i, i], self.st_phase[i, i] = self.my_task[i], self.phase[i]
            self.st_relay[i, i] = RTB_FLAG if self.rtb[i] else self.relay_for[i]
            self.st_sig[i, i] = self.sigma(i)
            if self.spoofer[i]:
                if self.sneaky:
                    self._sneaky_lies(i)
                else:
                    # Saf saldırgan: tüm açık görevleri "ben tam oradayım" diye en yüksek teklifle sahiplenir
                    open_ = ~self.known_done[i] & self.known_task[i]
                    top = self.value[open_] if self.cbba else 0.0
                    self.cl_bid[i, open_], self.cl_id[i, open_], self.cl_time[i, open_] = top, i, now
                continue
            t = self.my_task[i]
            if t >= 0 and not self.cbba:
                self.cl_bid[i, t], self.cl_id[i, t], self.cl_time[i, t] = self._bids(i)[t], i, now
            # Karıştırma algılama: alıcıdaki gürültü tabanı yükseldi ya da GPS kesildi
            if self.ew.jam_map and (not self.gps_rx[i] or self.jrx[i] + self.rng.normal(0, 2) > c.jam_detect_dbm):
                ix, iy = cell_idx(self.est[i, 0], self.est[i, 1])
                self.jam_t[i, ix, iy] = now
        if self.ew.trust:
            self._trust_update(heard)

        # 2) Mesajlar: herkes, duyduğu komşuların (gönderim anındaki) tablosunu birleştirir.
        # Her gönderen için tüm alıcılar birlikte işlenir (alıcı başına sıra, gönderen numarasıyla aynı).
        snap_b, snap_id, snap_t = self.cl_bid.copy(), self.cl_id.copy(), self.cl_time.copy()
        snap_done, snap_known, snap_est = self.known_done.copy(), self.known_task.copy(), self.est.copy()
        snap_by = self.done_by.copy()
        snap_jt, snap_sp = self.jam_t.copy(), self.spf_t.copy()
        snap_own = self.own_bad.copy()
        sn_t, sn_pos, sn_task = self.st_t.copy(), self.st_pos.copy(), self.st_task.copy()
        sn_phase, sn_relay, sn_sig = self.st_phase.copy(), self.st_relay.copy(), self.st_sig.copy()
        ttl_all = self._ttl_all()
        implausible = self._implausible(snap_b, snap_id, snap_t, snap_est) if self.ew.trust else None
        for k in np.nonzero(self.alive)[0]:
            R = np.nonzero(heard[k] & self.alive)[0]
            R = R[~self.distrust[R, k]]
            if len(R) == 0:
                continue
            # Sürü durum tablosu: daha yeni bilgiyi al
            st_before = self.st_t[R].copy()
            newer = sn_t[k][None, :] > st_before
            if newer.any():
                self.st_t[R] = np.where(newer, sn_t[k][None, :], st_before)
                self.st_pos[R] = np.where(newer[..., None], sn_pos[k][None], self.st_pos[R])
                self.st_task[R] = np.where(newer, sn_task[k][None, :], self.st_task[R])
                self.st_phase[R] = np.where(newer, sn_phase[k][None, :], self.st_phase[R])
                self.st_relay[R] = np.where(newer, sn_relay[k][None, :], self.st_relay[R])
                self.st_sig[R] = np.where(newer, sn_sig[k][None, :], self.st_sig[R])
            keep = ~self.spoofer[R]
            R, st_before = R[keep], st_before[keep]
            if len(R) == 0:
                continue
            if self.ew.trust:
                if implausible[k]:
                    # Makul olmayan teklif veren gönderene artık güvenme (kesin kanıt)
                    for r in R:
                        self._mark_bad(r, k)
                    continue
                # Güvenilen gönderenin "kime güvenmiyorum" görüşü (iki bağımsız tanık kuralı için)
                self.accuse[R, :, k] = snap_own[k][None, :]
            if self.ew.jam_map:
                self.jam_t[R] = np.maximum(self.jam_t[R], snap_jt[k][None])
            if self.ew.spoof_detect:
                self.spf_t[R] = np.maximum(self.spf_t[R], snap_sp[k][None])
            # "Tamamlandı" bilgisi kaynağıyla (ilk bildiren İHA) birlikte yayılır; dirençli İHA,
            # güvenmediği kaynaktan gelen tamamlandı bilgisini almaz
            src = np.where(snap_by[k] >= 0, snap_by[k], k)
            new = snap_done[k][None, :] & ~self.known_done[R]
            if self.ew.trust:
                new &= ~self.distrust[R][:, src]
            self.known_done[R] |= new
            self.done_by[R] = np.where(new, src[None, :], self.done_by[R])
            self.known_task[R] |= snap_known[k]
            if self.cbba:
                self._merge_cbba(R, k, snap_b[k], snap_id[k], snap_t[k], sn_t[k], st_before)
            else:
                fresh = snap_t[k][None, :] > now - ttl_all[R]
                better = fresh & ((snap_b[k][None, :] > self.cl_bid[R]) |
                                  ((snap_id[k][None, :] == self.cl_id[R]) & (snap_t[k][None, :] > self.cl_time[R])))
                self.cl_bid[R] = np.where(better, snap_b[k][None, :], self.cl_bid[R])
                self.cl_id[R] = np.where(better, snap_id[k][None, :], self.cl_id[R])
                self.cl_time[R] = np.where(better, snap_t[k][None, :], self.cl_time[R])
        if self.ew.trust:
            self._refresh_distrust()

    # ----------------------------------------------------------- güven sistemi
    def _sneaky_lies(self, i):
        """Sinsi saldırgan: (1) kendine yakın en fazla 2 görevi, konumuyla tutarlı (makul) en yüksek
        teklifle sahiplenir ama oraya gitmez (görevi kilitler); (2) her 10 s'de bir açık görevi
        "tamamladım" diye yayar ve o anda kendini hedefin üstünde gösterir (konum yalanı)."""
        c, now = self.cfg, self.t
        open_ = np.nonzero(self.known_task[i] & ~self.known_done[i])[0]
        held = [t for t in self.sneaky_hold[i] if t in open_]
        rest = [t for t in open_ if t not in held]
        if len(held) < 2 and rest:
            d = np.linalg.norm(self.tasks[rest, :2] - self.est[i, :2], axis=1)
            held += [rest[j] for j in np.argsort(d)[:2 - len(held)]]
        self.sneaky_hold[i] = held
        for t in held:
            d = float(np.linalg.norm(self.tasks[t, :2] - self.est[i, :2]))
            if self.cbba:
                late = max(now + d / c.max_speed - self.ref_t[t], 0.0)      # makullük sınırının hemen altı
                bid = self.value[t] * np.exp(self.lnlam * late)
            else:
                bid = -d + 25.0
            self.cl_bid[i, t], self.cl_id[i, t], self.cl_time[i, t] = bid, i, now
        self.st_task[i, i] = held[0] if held else -1                       # "oraya gidiyorum" der
        rest = [t for t in open_ if t not in held]
        if now >= self.next_fake_done[i] and self.phase[i] == TASK and rest:
            self.next_fake_done[i] = now + c.spoof_period
            t = int(self.rng.choice(rest))
            self.known_done[i, t], self.done_by[i, t] = True, i
            self.st_pos[i, i] = self.tasks[t]                              # konum yalanı

    def _trust_update(self, heard):
        """Doğrudan duyulan komşular hakkında kanıt toplar (Beta itibarı):
        - menzil: komşunun bildirdiği konum, telsizle ölçülen uzaklıkla tutuyor mu?
        - hız: bildirdiği konum bir öncekine göre uçamayacağı kadar mı sıçradı?
        - ilerleme: görev evresinde "gidiyorum" dediği hedefe 30 s'dir yaklaşmıyor mu?
        Kendi konumu bozuk olan (ör. GPS'i aldatılmış) İHA herkesi suçlamasın diye, bir komşu ancak
        diğer komşulara göre aykırıysa suçlanır."""
        c, now = self.cfg, self.t
        for i in np.nonzero(self.alive & ~self.spoofer)[0]:
            K = np.nonzero(heard[:, i] & self.alive)[0]
            K = K[K != i]
            if len(K) == 0:
                continue
            claim = self.st_pos[K, K]                                          # komşuların kendi bildirdiği konum
            meas = np.linalg.norm(self.pos[K] - self.pos[i], axis=1) + self.rng.normal(0, 1.0, len(K))
            err = np.abs(np.linalg.norm(claim[:, :2] - self.est[i, :2], axis=1) - meas)
            tol = 15.0 + 2.5 * (self.sigma(i) + self.st_sig[K, K])
            med = float(np.median(err))
            neg = np.zeros(len(K))
            outlier = err > np.maximum(tol, 3.0 * med)
            neg += np.where(outlier & (err > 3 * tol), 5.0, np.where(outlier, 1.0, 0.0))
            seen = np.isfinite(self.prev_claim_t[i, K])
            dt = now - self.prev_claim_t[i, K]
            jump = np.linalg.norm(claim - self.prev_claim[i, K], axis=1)
            neg += np.where(seen & (jump > c.max_speed * 1.5 * dt + 20.0 + 3.0 * self.st_sig[K, K]), 5.0, 0.0)
            self.prev_claim[i, K], self.prev_claim_t[i, K] = claim, now
            for n, k in enumerate(K):
                t = self.st_task[k, k]
                if t < 0 or self.st_phase[k, k] != TASK:
                    self.hold_task[i, k] = -1
                    continue
                d = float(np.linalg.norm(claim[n, :2] - self.tasks[t, :2]))
                if self.hold_task[i, k] != t or d < self.hold_dist[i, k] - 20.0 or d < 120.0:
                    self.hold_task[i, k], self.hold_since[i, k], self.hold_dist[i, k] = t, now, d
                elif now - self.hold_since[i, k] > 30.0:
                    neg[n] += 3.0
                    self.hold_since[i, k] = now
            self.tr_b[i, K] += neg
            self.tr_a[i, K] += np.where(neg == 0, 0.05, 0.0)

    def _mark_bad(self, r, k):
        self.hard_bad[r, k] = True

    def _refresh_distrust(self):
        """Güvenmeme = kendi kanıtı (kesin ya da itibar < 0.35) VEYA güvendiği en az iki ayrı
        arkadaşının güvenmemesi (iki bağımsız tanık; tek bir yalancı kimseyi karalayamaz)."""
        E = (self.tr_a + 1.0) / (self.tr_a + self.tr_b + 2.0)
        self.soft_bad = np.where(E < 0.35, True, np.where(E > 0.6, False, self.soft_bad))
        own = self.hard_bad | self.soft_bad
        np.fill_diagonal(own, False)
        self.own_bad = own
        votes = (self.accuse & ~own[:, None, :]).sum(2)
        dis = own | (votes >= 2)
        np.fill_diagonal(dis, False)
        dis[self.spoofer] = False
        newly = dis & ~self.distrust
        self.distrust = dis
        for i, x in zip(*np.nonzero(newly)):
            mine = self.cl_id[i] == x
            self.cl_bid[i, mine], self.cl_id[i, mine], self.cl_time[i, mine] = -np.inf, -1, -np.inf
            fake = self.done_by[i] == x
            self.known_done[i, fake], self.done_by[i, fake] = False, -1    # onun "tamamlandı"larını geri al

    def _implausible(self, snap_b, snap_id, snap_t, snap_est):
        """Makullük kontrolü: gönderenin bu turda kendi adına verdiği teklif, bildirdiği
        konumdan göreve olan uzaklıkla tutarlı mı? (sahte bilgiye karşı)"""
        now = self.t
        bad = np.zeros(self.N, bool)
        for k in np.nonzero(self.alive)[0]:
            own = (snap_id[k] == k) & (snap_t[k] >= now)
            if not own.any():
                continue
            d = np.linalg.norm(self.tasks[own, :2] - snap_est[k, :2], axis=1)
            if self.cbba:
                # En iyi ihtimalle azami hızla dümdüz gitse bile alabileceği ödülden fazlası olamaz
                late = np.maximum(now + d / self.cfg.max_speed - self.ref_t[own], 0.0)
                ub = self.value[own] * np.exp(self.lnlam * late) * 1.02 + 1e-6
            else:
                ub = -d + 30.0
            bad[k] = bool((snap_b[k, own] > ub).any())
        return bad

    def _merge_cbba(self, R, k, yk, zk, tk, sk, st_before):
        """CBBA uzlaşması: k'nın kazanan listesini alıcılarınkiyle Choi kurallarına göre birleştir."""
        zk = zk.copy()
        yk = yk.copy()
        upd, rst = decision.cbba_merge(R, k, yk, zk, sk, self.cl_bid, self.cl_id, st_before)
        # Alıcının güvenmediği İHA'yı kazanan gösteren bilgi alınmaz
        if self.ew.trust:
            dz = np.maximum(zk, 0)
            untrusted = (zk[None, :] >= 0) & self.distrust[R][:, dz]
            upd &= ~untrusted
        rows = np.broadcast_to(R[:, None], upd.shape)
        if upd.any():
            r, t = rows[upd], np.nonzero(upd)[1]
            self.cl_bid[r, t], self.cl_id[r, t], self.cl_time[r, t] = yk[t], zk[t], tk[t]
        if rst.any():
            r, t = rows[rst], np.nonzero(rst)[1]
            self.cl_bid[r, t], self.cl_id[r, t], self.cl_time[r, t] = -np.inf, -1, -np.inf

    def _gcs_link(self):
        c, N, now = self.cfg, self.N, self.t
        if self.jammers:
            gj = radio.jam_power_dbm(self.gcs, self.jammers, c, self.terrain, band="comm")
            gjb = radio.jam_power_dbm(self.gcs, self.jammers, c, self.terrain, band="gps")
        else:
            gj = gjb = np.array([-300.0])
        tl = self._gcs_terrain()
        per_up = self._per(self.pos, self.gcs, gj, gjb, c.gcs_gain_db, np.inf, None if tl is None else tl.T)
        per_dn = self._per(self.gcs, self.pos, self.jrx, self.jrx_bar, c.gcs_gain_db, np.inf, tl)
        up = (self.rng.random(N) > per_up[:, 0]) & self.alive
        dn = (self.rng.random(N) > per_dn[0]) & self.alive
        self.gcs_up = up & dn

        # Yukarı bağlantı: konum ve tamamlanan görevler istasyona gider
        for i in np.nonzero(up)[0]:
            self.gcs_seen[i] = now
            self.gcs_pos[i] = self.est[i]
            if self.spoofer[i]:
                # Saldırgan arada bir sahte "tamamlandı" raporu yollar
                if now >= self.next_spoof[i]:
                    self.next_spoof[i] = now + c.spoof_period
                    open_ = np.nonzero(~self.gcs_done)[0]
                    if len(open_):
                        self.gcs_done[self.rng.choice(open_)] = True
            else:
                self.gcs_done |= self.known_done[i]

        # İstasyon yeni hedefleri ihbar anında bilir; İHA'ların sensörüyle gördüklerini de yukarı bağlantıdan alır
        gcs_known = (self.appear <= now) | self.known_task[up].any(0)
        # Uzun süredir duyulmayan İHA'nın görevi serbest kalır
        self.gcs_assign[now - self.gcs_seen > c.gcs_release] = -1
        if self.cbba:
            if now >= self.next_gcs_plan:
                self.next_gcs_plan = now + c.gcs_replan
                self._gcs_sga(gcs_known)
        else:
            # Açgözlü atama: boştaki her İHA'ya en yakın sahipsiz görev
            for i in np.nonzero(dn & ~np.isnan(self.gcs_pos[:, 0]))[0]:
                a = self.gcs_assign[i]
                if a >= 0 and not self.gcs_done[a]:
                    continue
                taken = set(self.gcs_assign[self.gcs_assign >= 0])
                free = [t for t in range(self.T) if gcs_known[t] and not self.gcs_done[t] and t not in taken]
                if free:
                    d = np.linalg.norm(self.tasks[free, :2] - self.gcs_pos[i, :2], axis=1)
                    self.gcs_assign[i] = free[int(np.argmin(d))]
                else:
                    self.gcs_assign[i] = -1
        # Bilinen tüm görevler yapıldıysa istasyon "eve dön" emri verir
        if np.isinf(self.gcs_return_t) and self.gcs_done[gcs_known].all():
            self.gcs_return_t = now
        # Aşağı bağlantı: görev emri, yeni hedef ihbarı ve düzen ilerlemesi İHA'ya ulaşır
        for i in np.nonzero(dn)[0]:
            self.last_gcs[i] = now
            self.known_done[i] |= self.gcs_done
            self.known_task[i] |= gcs_known
            if self.phase[i] == TRANSIT:
                self.lead_s[i] = max(self.lead_s[i], c.transit_speed * (now - c.takeoff_time))
            if self.spoofer[i]:
                continue
            if self.cbba:
                self.path[i] = [t for t in self.gcs_plan.get(int(i), []) if not self.known_done[i, t]]
                self.bundle[i] = list(self.path[i])
                self._set_task(i)
            else:
                self.path[i] = [self.gcs_assign[i]] if self.gcs_assign[i] >= 0 else []
                self._set_task(i)

    def _gcs_sga(self, gcs_known):
        """Merkezi plan: istasyonun bildiği konumlarla sıralı açgözlü atama (SGA)."""
        c, now = self.cfg, self.t
        agents = np.nonzero((now - self.gcs_seen <= c.gcs_release) & ~np.isnan(self.gcs_pos[:, 0])
                            & (self.phase < RETURN))[0]
        open_ = gcs_known & ~self.gcs_done
        if len(agents) == 0:
            self.gcs_plan = {}
            return
        starts, t0s = np.zeros((self.N, 2)), np.zeros(self.N)
        for i in agents:
            starts[i], t0s[i] = self._plan_start(i, self.gcs_pos[i])
        rho = np.ones((self.N, self.T))
        for i, plan in self.gcs_plan.items():
            if plan and i in agents:
                rho[i, plan[0]] = 1.05          # şu an gidilen hedefi gereksiz yere değiştirme
        self.gcs_plan = decision.sga(agents, starts, t0s, self.tasks[:, :2], self.value, self.ref_t, rho, open_,
                                     c.bundle_size, self.lnlam, self.cruise)
        for i in range(self.N):
            p = self.gcs_plan.get(i, [])
            self.gcs_assign[i] = p[0] if p else -1

    def _coop_localize(self, heard):
        """GPS'i olmayan İHA, GPS'i sağlam en az 3 komşusunu duyuyorsa onlara
        olan menzil ölçümleriyle (UWB benzeri) konumunu düzeltir."""
        for j in np.nonzero(~self.gps_ok & self.alive)[0]:
            helpers = np.nonzero(heard[:, j] & self.gps_ok & ~self.distrust[j] & ~self.spoofer)[0]
            if len(helpers) >= 3:
                # Menzil ölçümleriyle konum: yardımcıların kendi konum hataları (ör. fark edilmemiş GPS
                # aldatması) düzeltmeye taşınır
                carried = (self.est[helpers] - self.pos[helpers]).mean(0)
                fix = self.pos[j] + carried + self.rng.normal(0, 3.0, 3) * [1, 1, 0.3]
                self.est[j] += 0.5 * (fix - self.est[j])
                self.bias[j] = 0
                self.dr_t[j], self.sig0[j] = 0.0, 3.0

    # ----------------------------------------------------------- karar alma
    def _decide(self):
        for j in range(self.N):
            if not self.alive[j]:
                continue
            if self.energy_on and not self.spoofer[j] and self._battery_rtb(j):
                continue
            if self.phase[j] >= RETURN:
                if self.path[j] or self.bundle[j]:
                    self._clear_plan(j)
                continue
            if self.spoofer[j] or self.relay_for[j] >= 0:
                self._clear_plan(j)
                continue
            if self.ew.recover and self._gps_recovery(j):
                continue
            done = [t for t in self.path[j] if self.known_done[j, t]]
            for t in done:
                self._drop(j, t)
            if self.central:
                continue
            if self.cbba:
                self._decide_cbba(j)
                continue
            # Açgözlü tek görev açık artırması (eski yöntem)
            ttl = self._ttl(j)
            valid = (self.cl_time[j] > self.t - ttl) & (self.cl_id[j] >= 0)
            bids = self._bids(j)
            t = self.my_task[j]
            # Görevimi benden iyi teklif veren biri aldıysa bırakırım
            if t >= 0 and valid[t] and self.cl_id[j, t] != j and self.cl_bid[j, t] > bids[t]:
                self._drop(j, t)
            if self.my_task[j] < 0:
                free = self.known_task[j] & ~self.known_done[j] & (~valid | (self.cl_id[j] == j) | (self.cl_bid[j] < bids))
                free &= self.cooldown[j] <= self.t
                free &= self._allowed(j, free)
                if free.any():
                    t = int(np.argmax(np.where(free, bids, -np.inf)))
                    self.path[j] = [t]
                    self._set_task(j)
                    self.cl_bid[j, t], self.cl_id[j, t], self.cl_time[j, t] = bids[t], j, self.t

    def _allowed(self, j, cand, keep=False):
        """Dirençli İHA'nın kendi kendine koyduğu sınırlar (görev adaylarını süzer):
        - hava savunma şemsiyesinin içindeki hedef: ancak radarın görmediği yerden kısa bir dalışla (50 m,
          birkaç saniye) ulaşılabiliyorsa alınır. Daha derindeki hedefte radar İHA'yı izleyip füze atmaya
          yetecek kadar uzun görür: İHA'yı kaybetme riski hedefin değerinden büyüktür, bilerek bırakılır;
        - enerji: hedefe gidip rüzgâra karşı eve dönmeye bataryası yetmeyen hedef alınmaz.
        keep=True: paketteki görevi tutmak için daha gevşek eşik (kestirim titreyince görev el değiştirmesin)."""
        ok = np.ones(self.T, bool)
        if self.ew.radar and self.rd_est[j]:
            ok &= self._tmap(j).escape_at(self.tasks[:, :2]) <= (1.8 if keep else 1.0) * threat.DASH
        if self.ew.energy and self.energy_on:
            aff = self._affordable(j)
            self.unaffordable[j] = bool((cand & ok).any() and not (cand & ok & aff).any())
            ok &= aff
        return ok

    def _affordable(self, j):
        """Bu hedefe gidip eve dönmeye bataryası yetiyor mu (rüzgâr dahil, %20 pay ve iniş yedeğiyle)."""
        c, X = self.cfg, self.tasks[:, :2]
        p0, _ = self._plan_start(j)
        w, v = self.wind.mean, c.max_speed
        need = energy.leg_energy_wh(np.broadcast_to(p0, X.shape), X, w, v) + energy.home_energy_wh(X, self.home, w, v)
        if self.path[j]:                      # rotasındaki hedeflere gitmenin enerjisi de düşülür
            pts = np.vstack([p0, X[self.path[j]]])
            need = need + float(energy.leg_energy_wh(pts[:-1], pts[1:], w, v).sum())
        avail = self.bat[j] - energy.RESERVE * energy.CAPACITY_WH
        if self.phase[j] in (TAKEOFF, TRANSIT):
            avail -= float(energy.leg_energy_wh(self.est[j:j + 1, :2], p0[None, :], w, c.transit_speed)[0])
        return 1.2 * need < avail

    def _battery_rtb(self, j):
        """Batarya dönüşü. Standart emniyet (her mimaride): batarya %10'a inince eve dön.
        Enerji farkında (dirençli): bulunduğu yerden rüzgâra karşı eve dönüş enerjisi, iniş yedeğiyle birlikte
        bataryaya yaklaşınca ya da açık hedeflerin hiçbirine enerjisi yetmiyorsa eve dön.
        Döndürür: İHA eve dönüyor mu."""
        if self.rtb[j]:
            return True
        if self.phase[j] not in (TRANSIT, TASK, REGROUP):
            return False
        cap = energy.CAPACITY_WH
        if self.ew.energy:
            need = float(energy.home_energy_wh(self.est[j, :2], self.home, self.wind.mean, self.cfg.max_speed)[0])
            go = self.bat[j] - energy.RESERVE * cap < 1.15 * need
            go |= self.unaffordable[j] and self.my_task[j] < 0 and self.phase[j] in (TASK, REGROUP)
        else:
            go = self.bat[j] <= energy.FAILSAFE * cap
        if go:
            self.rtb[j] = True
            self.r.rtb[j] = self.t
            self._close_attempt(j, False)
            self._release_claim(j)
            self.recover[j], self.relay_for[j] = False, -1
            self._set_phase(j, RETURN)
        return bool(go)

    def _gps_recovery(self, j):
        """(Dirençli) GPS kurtarma: konumunu çok kaybeden İHA görevlerini bırakır, son GPS aldığı
        noktaya döner; GPS ya da komşu düzeltmesi gelince göreve döner. O nokta çok uzaksa ya da
        varınca da GPS yoksa (her yer karıştırılıyor) kurtarmayı bir süre denemez.
        Döndürür: İHA şu an kurtarmada mı."""
        now, c = self.t, self.cfg
        sig = self.sigma(j)
        if not self.recover[j]:
            self.recover_to[j] = self._recover_point(j)
        back = float(np.linalg.norm(self.est[j, :2] - self.recover_to[j]))
        if self.recover[j]:
            if sig < 5.0:
                self.recover[j] = False
            elif back < 15.0:
                self.recover[j] = False
                self.recover_block[j] = now + 60.0
        elif (sig > c.recover_sigma and self.search[j] == 0 and now >= self.recover_block[j]
              and back < 300.0 and self.phase[j] == TASK):
            self.recover[j] = True
            self.r.recover[j] += 1
            self._close_attempt(j, False)        # konumunu kaybedip görevi bıraktı: başarısız deneme
            self._release_claim(j)
        return bool(self.recover[j])

    def _recover_point(self, j):
        """GPS'i geri almak için gidilecek nokta:
        - GPS aldatması tespit edildiyse bilinen aldatma bölgesinden dışarı,
        - karıştırıcının yeri kestirildiyse GPS'in kesildiği dairenin en yakın kenarının biraz dışı,
        - yoksa son GPS alınan nokta."""
        c, p = self.cfg, self.est[j, :2]
        sp = self.spf_t[j] > self.t - 120.0
        if not self.gps_trust[j] and sp.any():
            u = p - cell_centers(sp).mean(0)
            return p + u / max(np.linalg.norm(u), 1.0) * 200.0
        if self.ew.localize and self.loc_est[j]:
            q, P = min(self.loc_est[j], key=lambda e: np.linalg.norm(e[0] - p))
            r = 10 ** ((P - c.gps_jam_dbm - c.pl_d0_db) / (10 * c.pl_exponent))
            u = p - q
            return q + u / max(np.linalg.norm(u), 1.0) * (r + 40.0)
        return self.last_fix[j].copy()

    def _decide_cbba(self, j):
        """CBBA: geçersiz teklifleri sil, teklifi geçilen görevi bırak, paketi yeniden doldur."""
        c, now = self.cfg, self.t
        z = self.cl_id[j]
        # 1) Kazananı uzun süredir duyulmayan (düşmüş ya da kopmuş) ya da güvenilmeyen teklifler geçersiz
        other = (z >= 0) & (z != j)
        if other.any():
            zz = np.maximum(z, 0)
            stale = other & ((now - self.st_t[j, zz] > self._ttl(j)) | self.distrust[j, zz])
            self.cl_bid[j, stale], self.cl_id[j, stale], self.cl_time[j, stale] = -np.inf, -1, -np.inf
        # 2) Teklifi geçilen ilk görevden sonrasını bırak (sonrakiler ona göre hesaplanmıştı). Artık izin
        #    verilmeyen görev de (yeni bulunan radarın şemsiyesinde kaldı, enerjisi yetmiyor) bırakılır.
        cand = self.known_task[j] & ~self.known_done[j] & (self.cooldown[j] <= now)
        keep = self._allowed(j, cand, keep=True) & (self.cooldown[j] <= now)
        b = self.bundle[j]
        for n, t in enumerate(b):
            if self.cl_id[j, t] != j or not keep[t]:
                for t2 in b[n:]:
                    if self.cl_id[j, t2] == j:
                        self.cl_bid[j, t2], self.cl_id[j, t2], self.cl_time[j, t2] = -np.inf, -1, -np.inf
                b = b[:n]
                break
        path = [t for t in self.path[j] if t in b]
        # 3) Tekliflerini güncelle ve paketi doldur
        p0, t0 = self._plan_start(j)
        X, V, A = self.tasks[:, :2], self.value, self.ref_t
        rho = self._rho(j)
        bids = decision.refresh_bids(b, path, p0, t0, X, V, A, rho, self.lnlam, self.cruise)
        cand &= self._allowed(j, cand)
        b, path, bids = decision.build_bundle(list(b), path, bids, p0, t0, X, V, A, rho, self.cl_bid[j], self.cl_id[j],
                                              j, cand, c.bundle_size, self.lnlam, self.cruise, c.outbid_margin)
        for t, y in zip(b, bids):
            self.cl_bid[j, t], self.cl_id[j, t], self.cl_time[j, t] = y, j, now
        self.bundle[j], self.path[j] = b, path
        self._set_task(j)

    # ----------------------------------------------------------- sürü zekâsı
    def _swarm_logic(self):
        c, now = self.cfg, self.t
        dt = c.dt * c.comm_every
        for i in np.nonzero(self.alive)[0]:
            ph = self.phase[i]
            if ph == TAKEOFF and now >= c.takeoff_time:
                self._set_phase(i, TRANSIT)
            elif ph == TRANSIT and self.lead_s[i] >= self.paths[TRANSIT].length - 1.0:
                self._set_phase(i, TASK)
            elif ph == TASK:
                if self.spoofer[i]:
                    # Gizli saldırgan sürüye uyar: arkadaşların çoğu toplanınca o da toplanır
                    known = (self.st_t[i] > now - 10.0)
                    known[i] = False
                    if known.sum() and (self.st_phase[i, known] >= REGROUP).mean() > 0.5:
                        self._set_phase(i, REGROUP)
                    continue
                idle = self.my_task[i] < 0 and self.relay_for[i] < 0 and not self.recover[i]
                self.idle_t[i] = self.idle_t[i] + dt if idle else 0.0
                if self.idle_t[i] >= c.regroup_wait:
                    self._set_phase(i, REGROUP)
            elif ph == REGROUP:
                if self.my_task[i] >= 0:
                    self.idle_t[i] = 0.0
                    self._set_phase(i, TASK)
                elif self._ready_to_return(i):
                    self._set_phase(i, RETURN)
            elif ph == RETURN and self.rtb[i]:
                if np.linalg.norm(self.est[i, :2] - self.home) < 12.0:
                    self._set_phase(i, LAND)
            elif ph == RETURN and self.lead_s[i] >= self.paths[RETURN].length - 1.0:
                self._set_phase(i, LAND)
            elif ph == LAND and self.pos[i, 2] - self.terrain.height(self.pos[i, 0], self.pos[i, 1]) < 0.6:
                self._set_phase(i, LANDED)

        if self.relay_on:
            self._relay_logic()
        if not self.central:
            self._leader_consensus()

    def _ready_to_return(self, i):
        """Dönüşe geçiş: toplanma noktasına vardım ve (bildiğim herkes de toplandı ya da çok bekledim)."""
        now, near = self.t, 60.0
        if np.linalg.norm(self.est[i, :2] - self.rally) > near:
            self.phase_t[i] = now          # bekleme süresi ancak noktaya varınca işlemeye başlar
            return False
        waited = now - self.phase_t[i]
        if waited < 3.0:
            return False
        if waited > 150.0:
            return True                    # emniyet: sonsuza dek bekleme
        if self.central:
            return (now >= self.gcs_return_t and now - self.last_gcs[i] < 3.0) or \
                (waited >= self.cfg.regroup_hold and now - self.last_gcs[i] > self.cfg.gcs_timeout)
        known = (self.st_t[i] > now - 10.0) & ~self.distrust[i] & (self.st_relay[i] != RTB_FLAG)
        known[i] = False
        working = known & (self.st_phase[i] == TASK) & ((self.st_task[i] >= 0) | (self.st_relay[i] >= 0))
        if working.any():
            return False                   # görevi süren arkadaşı bekle
        # Haberini aldığım herkes toplanma noktasına gelene kadar beklerim (haber alınamayanlar sayılmaz)
        gathered = np.linalg.norm(self.st_pos[i, known, :2] - self.rally, axis=1) < near + 15.0
        return bool(((self.st_phase[i, known] >= REGROUP) & gathered).all())

    def _leader_consensus(self):
        """Sanal lider ilerlemesi için uzlaşma: s_i <- s_i + g * ortalama(s_j - s_i)."""
        g = self.cfg.consensus_gain
        s = self.lead_s.copy()
        for i in np.nonzero(self.alive & M_FORM[self.phase])[0]:
            nb = self.heard[:, i] & self.alive & (self.phase == self.phase[i]) & ~self.distrust[i]
            if nb.any():
                self.lead_s[i] = s[i] + g * float(np.mean(s[nb] - s[i]))

    def _relay_logic(self):
        """Bağlantı koruma: kopan bir arkadaş varsa, ona en uygun İHA (en yakın ve tercihen boşta)
        aradaki noktaya giderek röle olur. Herkes aynı bilgiyle aynı seçimi yapar, lider gerekmez."""
        c, now, R = self.cfg, self.t, self.cfg.comm_range
        for i in np.nonzero(self.alive & ~self.spoofer & (self.phase == TASK))[0]:
            fresh = (self.st_t[i] > now - 2.0) & ~self.distrust[i]
            fresh[i] = True
            k = self.relay_for[i]
            if k >= 0:
                if self._relay_finished(i, k, fresh):
                    self.relay_for[i] = -1
                else:
                    self.relay_pos[i] = self._relay_point(i, k, fresh)
                    self.m["relay_time"] += c.dt * c.comm_every
                continue
            age = now - self.st_t[i]
            lost = (age > c.relay_after) & (age < 60.0) & ~self.distrust[i]
            lost &= (self.st_phase[i] == TASK) & (self.st_task[i] >= 0) & (self.st_relay[i] < 0)
            lost[i] = False
            if lost.any() and self.jam_grid[i].any():
                ix, iy = cell_idx(self.st_pos[i, :, 0], self.st_pos[i, :, 1])
                lost &= ~self.jam_grid[i, ix, iy]
            if not lost.any():
                continue
            relaying = fresh & (self.st_relay[i] >= 0)
            relaying[i] = False
            taken = set(self.st_relay[i, relaying].tolist())
            if relaying.sum() >= c.max_relays:
                continue
            for k in np.nonzero(lost)[0]:
                if k in taken:
                    continue
                p = self._relay_point(i, k, fresh)
                cand = np.nonzero(fresh & (self.st_phase[i] == TASK) & (self.st_relay[i] < 0))[0]
                cand = cand[cand != k]
                if len(cand) == 0:
                    continue
                pos = self.st_pos[i, cand, :2].copy()
                pos[cand == i] = self.est[i, :2]
                score = np.linalg.norm(pos - p, axis=1) + 150.0 * (self.st_task[i, cand] >= 0)
                if cand[int(np.argmin(score))] == i:
                    self._release_claim(i)
                    self.relay_for[i], self.relay_pos[i], self.relay_since[i] = k, p, now
                    break

    def _relay_point(self, i, k, fresh):
        R = self.cfg.comm_range
        lost = self.st_pos[i, k, :2]
        anchors = fresh & (self.st_relay[i] < 0)
        anchors[k] = False
        anchors[i] = False
        pts = np.vstack([self.st_pos[i, anchors, :2], self.home[None, :]]) if anchors.any() else self.home[None, :]
        a = pts[int(np.argmin(np.linalg.norm(pts - lost, axis=1)))]
        d = float(np.linalg.norm(lost - a))
        if d <= 1.2 * R:
            return (a + lost) / 2
        return a + (lost - a) / max(d, 1e-6) * 0.6 * R

    def _relay_finished(self, i, k, fresh):
        now, R = self.t, self.cfg.comm_range
        age = now - self.st_t[i, k]
        if age > 60.0 or now - self.relay_since[i] > 120.0:
            return True
        if self.st_phase[i, k] != TASK or self.st_task[i, k] < 0:
            return True
        if age < 2.0:
            anchors = fresh & (self.st_relay[i] < 0)
            anchors[k] = anchors[i] = False
            if anchors.any():
                d = np.linalg.norm(self.st_pos[i, anchors, :2] - self.st_pos[i, k, :2], axis=1).min()
                return bool(d < 0.6 * R)
        return False

    # ----------------------------------------------------------- hareket
    def _navigate(self):
        c, N = self.cfg, self.N
        dt = c.dt
        alive = self.alive
        ranks = np.cumsum(alive) - 1
        n_alive = int(alive.sum())
        target = self.est[:, :2].copy()
        ff = np.zeros((N, 2))                   # sanal liderin hızı (ileri besleme)
        formation = np.zeros(N, bool)
        ring = formation_offsets("halka", max(n_alive, 1), c.form_spacing)
        offs = formation_offsets(self.form_kind, max(n_alive, 1), c.form_spacing)

        # Düzen grupları: 0 üste halka (kalkış/iniş), 1 toplanma noktasında halka (toplanma + boştakiler),
        # 2 intikal düzeni, 3 dönüş düzeni, -1 düzende değil (görev, röle, saldırgan)
        idle = (self.my_task < 0) & (self.relay_for < 0) & ~self.spoofer & ~self.recover
        lost_link = self.central & (self.t - self.last_gcs > c.gcs_timeout)
        group = np.full(N, -1)
        group[M_GROUND[self.phase]] = 0
        group[(self.phase == REGROUP) | ((self.phase == TASK) & idle & ~lost_link)] = 1
        group[self.phase == TRANSIT] = 2
        group[self.phase == RETURN] = 3
        group[self.rtb & (self.phase == RETURN)] = -1     # batarya dönüşü: düzene girmeden doğrudan eve
        group[~alive] = -1

        # Sanal lider ilerlemesi (intikal/dönüş): düzen hatası büyüyünce yavaşlar ki geride kalanlar yetişsin
        for i in np.nonzero(alive & M_FORM[self.phase])[0]:
            v = self._lead_speed(i)
            self.lead_s[i] = min(self.lead_s[i] + v * dt, self.paths[self.phase[i]].length)

        def slots_of(g, s_lead):
            if g == 0:
                return self.home + ring
            if g == 1:
                return self.rally + ring
            p, u = self.paths[TRANSIT if g == 2 else RETURN].at(s_lead)
            return place(p, u, offs)

        # Yuva ataması: her saniye (ya da grup değişince) toplam uzaklığı en aza indiren eşleme
        # (Macar algoritması). Böylece düzen değişirken İHA'ların yolları kesişmez.
        if self.t >= self.next_assign or (group != self.group).any():
            self.next_assign = self.t + 1.0
            for g in (0, 1, 2, 3):
                idx = np.nonzero(group == g)[0]
                if len(idx) == 0:
                    continue
                S = slots_of(g, float(np.mean(self.lead_s[idx])))
                cost = ((self.est[idx, None, :2] - S[None, :, :]) ** 2).sum(-1)
                rows, cols = linear_sum_assignment(cost)
                self.slot[idx[rows]] = cols
        self.group = group

        for i in np.nonzero(alive)[0]:
            g = group[i]
            if g >= 0:
                k = self.slot[i] % max(n_alive, 1)
                if g in (2, 3):
                    p, u = self.paths[self.phase[i]].at(self.lead_s[i])
                    target[i] = place(p, u, offs[k:k + 1])[0]
                    lead_v = self._lead_speed(i)
                    ff[i] = u * (lead_v if self.lead_s[i] < self.paths[self.phase[i]].length else 0.0)
                else:
                    target[i] = slots_of(g, 0.0)[k]
                formation[i] = True
                continue
            t = self.my_task[i]
            if self.rtb[i]:
                target[i] = self.home            # bataryası azaldı: doğrudan eve
            elif self.recover[i]:
                target[i] = self.recover_to[i]   # GPS'i geri almak için karıştırma/aldatma dışına
            elif self.relay_for[i] >= 0:
                target[i] = self.relay_pos[i]
            elif self.spoofer[i]:
                a = 0.05 * self.t + i
                target[i] = self.rally + [80 * np.cos(a), 80 * np.sin(a)]
            elif t >= 0:
                target[i] = self.tasks[t, :2]
                if self.search[i] > 0:   # Arşimet spirali: r = b * açı, tur aralığı = kameranın tarama genişliği
                    r = c.search_detect / np.pi * self.search[i]
                    target[i] = self.tasks[t, :2] + [r * np.cos(self.search[i]), r * np.sin(self.search[i])]
            else:
                target[i] = self.home            # merkezi, bağlantı kaybı: istasyona doğru dön

        # Dirençli: radar görüşünden kaçan rota, kilit ikazında arazinin arkasına kaçış, alçak uçuş
        if self.ew.radar and self.radars:
            self._threat_nav(target, formation, group)

        # --- yatay hız isteği
        to = target - self.est[:, :2]
        dist = np.linalg.norm(to, axis=1, keepdims=True)
        self.slot_err = np.where(formation, dist[:, 0], 0.0)                     # İHA'nın bildiği hata (kontrol için)
        self.slot_err_true = np.where(formation, np.linalg.norm(target - self.pos[:, :2], axis=1), 0.0)   # gerçek hata (ölçüm için)
        desired = np.zeros((N, 3))
        task_mode = ~formation
        speed = np.minimum(c.max_speed, 0.6 * dist)
        desired[:, :2] = np.where(task_mode[:, None], to / np.maximum(dist, 1e-6) * speed, ff + 0.6 * to)

        # Reynolds: düzen uçuşunda hizalanma + uyum (komşular yakın mesafe sensörüyle algılanır)
        desired[:, :2] += reynolds(self.pos[:, :2], self.vel[:, :2], formation & alive,
                                   c.neighbor_radius, c.w_align, c.w_cohesion)

        # Reynolds: ayrışma (çarpışmadan kaçınma), tüm evrelerde
        D = radio.dist_matrix(self.pos)
        np.fill_diagonal(D, np.inf)
        flying = alive & (self.phase != LANDED)
        D[~flying, :] = np.inf
        D[:, ~flying] = np.inf
        self.m["near_miss"] += int(np.triu(D < 2.0).sum())
        for i, j in zip(*np.nonzero(D < c.sep_dist)):
            away = (self.pos[i] - self.pos[j]) / max(D[i, j], 0.1)
            w = (c.sep_dist - D[i, j]) / c.sep_dist
            closing = max(0.0, -float(np.dot(self.vel[i] - self.vel[j], away)))   # yaklaşma hızı
            desired[i] += away * (w * 1.5 * c.max_speed + closing)

        # Öngörülü çarpışma önleme: iki İHA'nın en yakın yaklaşma noktası (CPA) 5 s içinde ayrışma
        # mesafesinin altına inecekse biri yükselir, diğeri alçalır ve yana açılırlar. (Kafa kafaya 24 m/s
        # yaklaşan iki İHA, 10 m kala fark etse ivme sınırı yüzünden kaçamaz; erken davranmak gerekir.)
        avoid_dz = np.zeros(N)
        agl_true = self.pos[:, 2] - self.terrain.height(self.pos[:, 0], self.pos[:, 1])
        air = flying & (agl_true > 5.0)
        idx = np.nonzero(air)[0]
        if len(idx) > 1:
            dp = self.pos[idx][None, :, :] - self.pos[idx][:, None, :]          # i'den j'ye
            dv = self.vel[idx][None, :, :] - self.vel[idx][:, None, :]
            vv = np.maximum((dv ** 2).sum(-1), 1e-6)
            tc = -(dp * dv).sum(-1) / vv
            miss = dp + dv * tc[..., None]
            dm = np.linalg.norm(miss, axis=-1)
            risk = (tc > 0) & (tc < 5.0) & (dm < c.sep_dist) & (np.linalg.norm(dp, axis=-1) < 80.0)
            np.fill_diagonal(risk, False)
            for a, b in zip(*np.nonzero(risk)):
                i, j = idx[a], idx[b]
                up = 1.0 if (self.pos[i, 2] > self.pos[j, 2] + 0.5 or (abs(self.pos[i, 2] - self.pos[j, 2]) <= 0.5 and i > j)) else -1.0
                avoid_dz[i] = up * 8.0
                side = -miss[a, b, :2] / max(dm[a, b], 0.5)
                desired[i, :2] += side * c.max_speed * 0.5 * (1.0 - tc[a, b] / 5.0)

        # Dirençli: hedefim karıştırma bölgesinde değilse oradan transit geçme
        if self.ew.avoid:
            for i in np.nonzero(alive & (self.phase == TASK))[0]:
                grid = self.jam_grid[i]
                t = self.my_task[i]
                if self.spoofer[i] or not grid.any() or (t >= 0 and grid[self.task_ix[t], self.task_iy[t]]):
                    continue
                ctr = cell_centers(grid)
                v = self.est[i, :2] - ctr
                d = np.linalg.norm(v, axis=1, keepdims=True)
                w = np.clip((90.0 - d) / 90.0, 0, None)
                desired[i, :2] += (v / np.maximum(d, 1.0) * w * 8.0).sum(0)

        # --- dikey: arazi takibi (yükseklik haritası + ileriye bakış), iniş ve kalkış
        h = np.linalg.norm(desired[:, :2], axis=1, keepdims=True)
        desired[:, :2] *= np.minimum(1.0, c.max_speed / np.maximum(h, 1e-6))
        here = self.terrain.height(self.est[:, 0], self.est[:, 1])
        ahead = self.terrain.max_along(self.est[:, :2], self.est[:, :2] + self.vel[:, :2] * c.lookahead)
        at_tgt = self.terrain.height(target[:, 0], target[:, 1])
        # Görevde her İHA kendi irtifa katmanında uçar (çapraz geçişlerde dikey ayrım)
        layer = np.where(formation, 0.0, ((np.arange(N) % 3) - 1) * c.layer_step)
        agl = np.where(self.low, c.agl_low, c.agl) if self.radars else c.agl   # tehdit bölgesinde alçak uçuş
        z_goal = np.maximum.reduce([here, ahead, at_tgt]) + agl + layer + avoid_dz
        ground_true = self.terrain.height(self.pos[:, 0], self.pos[:, 1])
        agl_now = self.pos[:, 2] - ground_true                                   # telemetre (radar altimetre)
        # Emniyet: konum kestirimi kaysa bile (GPS yok) gerçek yere olan yükseklik korunur
        z_goal = np.maximum(z_goal, ground_true + 0.75 * agl)
        landing = self.phase == LAND
        near_pad = dist[:, 0] < 4.0
        z_goal = np.where(landing, np.where(near_pad, at_tgt + 0.3, self.pos[:, 2] + avoid_dz), z_goal)
        vz = np.clip(0.8 * (z_goal - self.pos[:, 2]), -c.max_climb, c.max_climb)
        vz = np.where(landing, np.maximum(vz, -2.5), vz)
        # Yere yakınken (kalkış) önce yüksel, sonra yatay hareket et
        low = (agl_now < 8.0) & M_EARLY[self.phase]
        desired[low, :2] *= 0.15
        desired[:, 2] = vz

        acc = (desired - self.vel) / 1.0
        an = np.linalg.norm(acc, axis=1, keepdims=True)
        acc *= np.minimum(1.0, c.max_accel / np.maximum(an, 1e-6))
        turb = 0.3 * (1.0 + float(np.linalg.norm(self.wind.vec)) / 5.0) if self.wind.on else 0.3
        acc += self.rng.normal(0, turb, acc.shape) * (agl_now[:, None] > 1.0)   # rüzgâr türbülansı
        acc[~alive] = 0.0
        self.vel += acc * dt
        if self.wind.on:
            # Hız sınırı havaya göredir: karşı rüzgârda İHA yere göre yavaşlar, arkadan esende hızlanamaz
            # (kontrolcü yere göre hız ister); dikey hız ayrıca sınırlanır.
            w = np.r_[self.wind.vec, 0.0]
            air = self.vel - w
            a = np.linalg.norm(air, axis=1, keepdims=True)
            self.vel = w + air * np.minimum(1.0, c.max_speed / np.maximum(a, 1e-6))
            sp = np.linalg.norm(self.vel, axis=1, keepdims=True)
            self.vel *= np.minimum(1.0, (c.max_speed + float(np.linalg.norm(w))) / np.maximum(sp, 1e-6))
        else:
            sp = np.linalg.norm(self.vel, axis=1, keepdims=True)
            self.vel *= np.minimum(1.0, c.max_speed / np.maximum(sp, 1e-6))

        # Yerdekiler kıpırdamaz; arızalananlar düşer
        parked = alive & (self.phase == LANDED)
        self.vel[parked] = 0.0
        dead = ~alive
        if dead.any():
            self.vel[dead, :2] *= 0.98
            self.vel[dead, 2] -= 9.81 * dt
        self.pos += self.vel * dt
        ground = self.terrain.height(self.pos[:, 0], self.pos[:, 1])
        hit = self.pos[:, 2] < ground + 0.3
        self.pos[hit, 2] = ground[hit] + 0.3
        self.vel[hit & dead] = 0.0
        self.vel[hit & ~dead, 2] = np.maximum(self.vel[hit & ~dead, 2], 0.0)

    def _lead_speed(self, i):
        """Sanal liderin hızı: düzen hatası büyüyünce yavaşlar ki geride kalanlar yetişsin.
        Rüzgârda, karşı rüzgâra rağmen yere göre tutturulabilecek hızı aşmaz."""
        c = self.cfg
        v = c.transit_speed * float(np.clip(1.0 - (self.slot_err[i] - 6.0) / 20.0, 0.3, 1.0))
        if self.wind.on:
            _, u = self.paths[self.phase[i]].at(self.lead_s[i])
            v = min(v, 0.8 * float(energy.ground_speed(u, self.wind.mean, c.max_speed)[0]))
        return max(v, 0.5)

    # ----------------------------------------------------------- hava savunma tehdidi (suru/threat.py)
    def _tmap(self, i):
        """İHA i'nin bildiği radarlardan tehdit haritası (aynı bilgiye sahip İHA'lar aynı haritayı paylaşır)."""
        key = self._rd_key(i)
        tm = self.tmaps.get(key)
        if tm is None:
            if len(self.tmaps) > 24:
                self.tmaps.clear()
            tm = self.tmaps[key] = threat.ThreatMap([np.array(k[1:], float) * 40.0 for k in key], self.terrain,
                                                    self.cfg.agl_low, r50=[self.radars[k[0]].r50 for k in key])
        return tm

    def _rd_key(self, i):
        """İHA'nın radar bilgisinin özeti (40 m'ye yuvarlanmış konumlar): aynı özet = aynı tehdit haritası."""
        return tuple(sorted((k, int(round(q[0] / 40.0)), int(round(q[1] / 40.0))) for k, (q, _) in self.rd_est[i].items()))

    def _radar_view(self):
        """Radarlar hakkında en çok şey bilen dürüst İHA (sürünün kestirimi olarak gösterilir), yoksa -1."""
        cand = [i for i in range(self.N) if self.alive[i] and not self.spoofer[i]]
        if not cand:
            return -1
        return max(cand, key=lambda i: (len(self.rd_est[i]), int(self.rw_k[i].sum())))

    def _plan_threat_paths(self):
        """(Dirençli) Radarlara göre toplanma noktası, intikal ve dönüş rotası: sürü düzende radar görüşüne
        girmeden uçar, toplanmayı radarın görmediği yerde yapar. Düzen geniş olduğu için harita 40 m genişletilir."""
        c = self.cfg
        i = self._radar_view()
        if i < 0 or not self.rd_est[i]:
            return
        key = self._rd_key(i)
        if key == self._plan_key:
            return
        self._plan_key = key
        wide = threat.ThreatMap([q for q, _ in self.rd_est[i].values()], self.terrain, c.agl,
                                r50=[self.radars[k].r50 for k in self.rd_est[i]], dilate=2)
        returning = (self.alive & (self.phase >= RETURN) & ~self.rtb).any()
        if not returning:
            ac = np.asarray(c.area_center, float)
            thr = 0.03 if self.t < c.takeoff_time else 0.15  # eşik farkı: kestirim iyileşince nokta boşuna oynamasın
            if float(wide.pd_at(self.rally)[0]) > thr:
                for rad in (220.0, 330.0, 450.0):            # görev alanına yakın, radarın görmediği yer
                    self.rally = wide.safest_near(ac, rad)
                    if float(wide.pd_at(self.rally)[0]) <= 0.02:
                        break
            back = wide.route(self.rally, self.home)
            self.paths[RETURN] = back if back is not None else Path([self.rally, self.home])
        if self.t < c.takeoff_time:
            out = wide.route(self.home, self.rally)
            self.paths[TRANSIT] = out if out is not None else Path([self.home, self.rally])
        else:
            # İntikal sürüyorsa: sanal liderin şimdiki yerinden yeni toplanma noktasına yeni rota
            tr = np.nonzero(self.alive & (self.phase == TRANSIT))[0]
            if len(tr):
                s0 = float(self.lead_s[tr].mean())
                p0, _ = self.paths[TRANSIT].at(s0)
                rest = [p0] + [q for q, cs in zip(self.paths[TRANSIT].p, self.paths[TRANSIT].cum) if cs > s0]
                danger = max(wide.line_pd(a, b) for a, b in zip(rest[:-1], rest[1:])) if len(rest) > 1 else 0.0
                moved = np.linalg.norm(self.paths[TRANSIT].p[-1] - self.rally) > 30.0
                if (danger > 0.25 or moved) and np.linalg.norm(p0 - self.rally) > 30.0:
                    out = wide.route(p0, self.rally)
                    self.paths[TRANSIT] = out if out is not None else Path([p0, self.rally])
                    self.lead_s[tr] = 0.0

    def _threat_nav(self, target, formation, group):
        """Dirençli İHA radar biliyorsa: hedefe radarın en az gördüğü rotadan gider (Dijkstra ağacı, saf takip),
        tehdit bölgesinde alçalır (arazi maskeleme); kilit ikazı alırsa radarın görmediği en yakın yere kaçar.
        Toplanma halkasındaki (boştaki) İHA'lar da kaçar; intikal ve dönüş düzeni rotası zaten radardan uzak planlanır."""
        now = self.t
        self.low[:] = False
        # Düzendeki (intikal, dönüş) İHA kilit ikazı alırsa düzeni bozup kaçar, sonra yuvasına döner
        for i in np.nonzero(self.alive & ((group == 2) | (group == 3)) & ~self.spoofer)[0]:
            if self.rw_lock[i] and now >= self.evade_until[i]:
                self.evade_until[i] = now + 6.0
                R = self.radars[int(self.rw_lock_by[i])]
                b = threat.compass(*(R.xy - self.pos[i, :2]))
                perp = np.array([np.cos(b), -np.sin(b)])
                if perp @ self.vel[i, :2] < 0:
                    perp = -perp
                self.evade_to[i] = self.est[i, :2] + 150.0 * perp
            if now < self.evade_until[i]:
                target[i] = self.evade_to[i]
                formation[i] = False
                self.low[i] = True
        for i in np.nonzero(self.alive & ((group == -1) | (group == 1)) & ~self.spoofer)[0]:
            if not self.rd_est[i] or self.phase[i] not in (TASK, REGROUP, RETURN):
                self.route[i] = None
                continue
            tm = self._tmap(i)
            p = self.est[i, :2]
            here = float(tm.pd_at(p)[0])
            if self.rw_lock[i] and now >= self.evade_until[i]:
                self.evade_until[i] = now + 6.0
                t = self.my_task[i]
                if t >= 0:
                    # Bu hedefe giderken radar kilitlendi: hedef sürüce "riskli" ilan edilir (yayınlanır), denenmez
                    self.cooldown[:, t] = np.inf
                    self.cl_bid[i, t], self.cl_id[i, t], self.cl_time[i, t] = -np.inf, -1, -np.inf
                    self._drop(i, t)
                k = int(self.rw_lock_by[i])
                if k in self.rd_est[i]:
                    self.evade_to[i] = tm.safest_near(p, 220.0)     # radarın görmediği en yakın yer (tepe arkası)
                else:
                    # Radarın yeri henüz bilinmiyor, yalnızca yönü (kerteriz): radara dik uç. Radyal hız sıfıra
                    # yaklaşınca Doppler süzgeci yankıyı zayıflatır, iz kopabilir ("beaming").
                    R = self.radars[k]
                    b = threat.compass(*(R.xy - self.pos[i, :2])) + self.rng_r.normal(0.0, threat.BEARING_SIGMA)
                    perp = np.array([np.cos(b), -np.sin(b)])
                    if perp @ self.vel[i, :2] < 0:
                        perp = -perp
                    self.evade_to[i] = p + 150.0 * perp
            if now < self.evade_until[i]:
                target[i] = self.evade_to[i]
                formation[i] = False
                self.low[i] = True
                continue
            t = self.my_task[i]
            goal = self.tasks[t, :2] if (t >= 0 and not self.rtb[i] and not self.recover[i]) else target[i]
            if np.linalg.norm(goal - p) < 60.0:
                self.route[i] = None
            else:
                key = id(tm)
                if (np.linalg.norm(goal - self.route_goal[i]) > 25.0 or key != self.route_key[i]
                        or now - self.route_t[i] > 4.0):
                    self.route[i] = tm.route(p, goal)
                    self.route_goal[i], self.route_key[i], self.route_t[i] = goal, key, now
                if self.route[i] is not None:
                    q, rest = threat.pursue(self.route[i], p, 40.0)
                    if rest > 30.0:
                        target[i] = q
            self.low[i] = here > 0.02 or self.route[i] is not None

    def _radar_step(self):
        """Radarlar döner ve tarar; izlenen İHA'ya füze atılır; dirençli İHA'ların radar ikaz alıcısı huzmeyi
        duyar, kerteriz ölçer, izlenince kilit ikazı verir. Füzeler komutla güdülür."""
        c, dt, now = self.cfg, self.cfg.dt, self.t
        agl = self.pos[:, 2] - self.terrain.height(self.pos[:, 0], self.pos[:, 1])
        flying = self.alive & (self.phase != LANDED) & (agl > 3.0)
        rwr = self.alive & ~self.spoofer if self.ew.radar else np.zeros(self.N, bool)
        targeted = {M.target for M in self.missiles if M.state == 0}
        lock_by = np.full(self.N, -1)
        for R in self.radars:
            R.track &= self.alive
            if not R.active(now):
                continue
            a0 = R.az
            sweep = 2.0 * np.pi * dt / R.period
            R.az = (a0 + sweep) % (2.0 * np.pi)
            rel = self.pos[:, :2] - R.xy
            phi = threat.compass(rel[:, 0], rel[:, 1])
            idx = np.nonzero(flying & (((phi - a0) % (2.0 * np.pi)) < sweep))[0]
            if len(idx):
                d3 = self.pos[idx] - R.pos
                rng = np.linalg.norm(d3, axis=1)
                if self.terrain.flat:
                    L = np.zeros(len(idx))
                else:
                    L = radio.terrain_loss_db(R.pos[None, :], self.pos[idx], self.terrain, lam=threat.LAMBDA_X, samples=40)[0]
                radial = (self.vel[idx] * d3).sum(1) / np.maximum(rng, 1.0)
                pd = threat.detect_prob(rng, L, R.r50, radial)
                hit = self.rng_r.random(len(idx)) < pd
                h = np.roll(R.hist[idx], -1, axis=1)
                h[:, -1] = hit
                R.hist[idx] = h
                trk = h.sum(1) >= threat.TRACK_M
                R.track_since[idx[trk & ~R.track[idx]]] = now
                R.track_since[idx[~trk]] = np.inf
                R.track[idx] = trk
                R.lit[idx] = now
                # Radar ikaz alıcısı: huzme tek yönlü yol alır, radarın menzilinin çok ötesinden duyulur
                hear = rwr[idx] & (rng < threat.RWR_RANGE) & (L < threat.RWR_MAX_LOSS)
                for i, r in zip(idx[hear], rng[hear]):
                    self.rw_lit[i] = now
                    if self.sigma(i) < 10.0:                 # konumundan emin değilse ölçüm kaydetmez
                        b = threat.compass(R.xy[0] - self.pos[i, 0], R.xy[1] - self.pos[i, 1])
                        m = self.rw_n % self.MR
                        self.rw_xy[m] = self.est[i, :2]
                        self.rw_b[m] = b + self.rng_r.normal(0.0, threat.BEARING_SIGMA)
                        self.rw_t[m], self.rw_e[m] = now, R.id
                        self.rw_k[:, m] = False
                        self.rw_k[i, m] = True
                        self.rw_n += 1
            lock_by[R.track] = R.id
            self.radar_track_t[R.track] += dt
            # Angajman: iz yeterince uzun korunduysa füze (atış arası ve füze sayısı sınırlı)
            if R.missiles > 0 and now >= R.next_fire:
                ready = R.track & self.alive & (now - R.track_since >= threat.ENGAGE_AFTER)
                cand = [i for i in np.nonzero(ready)[0] if i not in targeted]
                if cand:
                    i = min(cand, key=lambda k: R.track_since[k])
                    p0 = R.pos + [0.0, 0.0, 2.0]
                    d = self.pos[i] - p0
                    M = threat.Missile(R.id, i, p0, d / max(np.linalg.norm(d), 1.0) * threat.MISSILE_SPEED, now)
                    M.id = next(self._mid)
                    self.missiles.append(M)
                    R.missiles -= 1
                    R.fired += 1
                    R.next_fire = now + threat.RELOAD
                    targeted.add(i)
        self.rw_lock = (lock_by >= 0) & rwr
        self.rw_lock_by = np.where(self.rw_lock, lock_by, -1)
        self._missile_step()

    def _missile_step(self):
        """Füze: radar izi sürdükçe hedefin önüne doğru güdülür (komut güdümü); iz koparsa düz gider.
        Bir adımda hedefe en yakın geçişi yakınlık tapası mesafesinden azsa PK olasılıkla vurur."""
        dt, now = self.cfg.dt, self.t
        for M in self.missiles:
            if M.state != 0:
                continue
            R, i = self.radars[M.radar], M.target
            tgt = self.pos[i]
            if R.track[i] and self.alive[i]:
                d = tgt - M.pos
                aim = tgt + self.vel[i] * float(np.linalg.norm(d)) / threat.MISSILE_SPEED - M.pos
                M.vel = aim / max(np.linalg.norm(aim), 1e-6) * threat.MISSILE_SPEED
            p0 = M.pos.copy()
            M.pos = M.pos + M.vel * dt
            r0, r1 = p0 - (tgt - self.vel[i] * dt), M.pos - tgt
            dr = r1 - r0
            s = float(np.clip(-(r0 @ dr) / max(dr @ dr, 1e-9), 0.0, 1.0))
            miss = float(np.linalg.norm(r0 + s * dr))
            if miss < threat.KILL_DIST and self.alive[i]:
                if self.rng_r.random() < threat.PK:
                    M.state = 1
                    self.fail_drone(i, cause="radar")
                else:
                    M.state = 2
                M.t_end = now
            elif now - M.t0 > threat.MISSILE_LIFE or M.pos[2] < self.terrain.height(M.pos[0], M.pos[1]):
                M.state, M.t_end = 2, now
        self.missiles = [M for M in self.missiles if M.state == 0 or now - M.t_end < 2.0]

    def _radar_fix_tick(self):
        """(1 Hz) Dirençli İHA bildiği kerteriz ölçümlerinden radarların yerini bulur (son 120 s). Aynı ölçümleri
        bilen İHA'lar aynı sonucu bulur (bir kez hesaplanır). Hatası 150 m'den büyük kestirim kullanılmaz;
        konum, yalnızca belirgin biçimde iyileşince ya da kayınca güncellenir (harita boşuna değişmesin)."""
        now = self.t
        recent = self.rw_t > now - 120.0
        solved = {}
        for i in np.nonzero(self.alive & ~self.spoofer)[0]:
            know = self.rw_k[i] & recent
            if know.sum() < 3:
                continue
            for e in np.unique(self.rw_e[know]):
                sel = know & (self.rw_e == e)
                if sel.sum() < 3:
                    continue
                key = (int(e), sel.tobytes())
                if key not in solved:
                    idx = np.nonzero(sel)[0]
                    idx = idx[np.argsort(self.rw_t[idx])]
                    solved[key] = threat.bearing_fix(self.rw_xy[idx], self.rw_b[idx], rng=self.rng_r)
                fix = solved[key]
                if fix is None or fix[1] > 150.0:
                    continue
                q, err = fix
                old = self.rd_est[i].get(int(e))
                if old is None or err < 0.75 * old[1] or np.linalg.norm(q - old[0]) > max(2.0 * old[1], 40.0):
                    self.rd_est[i][int(e)] = (q, err)
        j = self._radar_view()
        if j >= 0 and self.rd_est[j]:
            truth = {R.id: R.xy for R in self.radars}
            err = float(np.mean([np.linalg.norm(q - truth[k]) for k, (q, _) in self.rd_est[j].items()]))
            self.rd_err_log.append((now, err))
            found = [k for k in self.rd_est[j] if not self.radars[k].known]
            if found and np.isnan(self.t_radar_fix) and err < 60.0:
                self.t_radar_fix = now
        self._plan_threat_paths()

    # ----------------------------------------------------------- enerji
    def _energy_step(self):
        """Her İHA'nın çektiği güç (havaya göre hızıyla, Zeng 2019) bataryadan düşülür; biterse İHA düşer."""
        c = self.cfg
        air = self.alive & (self.phase != LANDED)
        v_air = np.linalg.norm(self.vel[:, :2] - (self.wind.vec if self.wind.on else 0.0), axis=1)
        P = energy.power_w(v_air, self.vel[:, 2]) * air
        self.power = P
        used = P * c.dt / 3600.0
        self.bat = np.maximum(self.bat - used, 0.0)
        self.r.wh += used
        if self.energy_on:
            for i in np.nonzero(air & (self.bat <= 0.0))[0]:
                self.fail_drone(i, cause="batarya")

    def _update_estimates(self):
        """Basit tümleşik seyrüsefer: IMU ile tahmin, GPS varsa düzelt."""
        c = self.cfg
        lost = ~self.gps_ok
        n_lost = int(lost.sum())
        if n_lost:
            self.bias[lost] += self.rng.normal(0, c.imu_drift * np.sqrt(c.dt), (n_lost, 3)) * [1, 1, 0.2]
        self.est += (self.vel + self.bias) * c.dt
        ok = self.gps_ok
        gps = self.pos[ok] + self.spoof_off[ok] + self.rng.normal(0, 1.5, (int(ok.sum()), 3)) * [1, 1, 0.5]
        self.est[ok] += 0.3 * (gps - self.est[ok])
        self.last_fix[ok] = self.est[ok, :2]
        self.bias[ok] = 0
        self.dr_t = np.where(ok, 0.0, self.dr_t + c.dt)
        self.sig0[ok] = 1.5

    # ----------------------------------------------------------- elektronik harp (1 Hz)
    def _gps_spoofing(self):
        """GPS aldatıcı, yarıçapındaki İHA'nın (GPS'i karıştırılmıyorsa) alıcısını ele geçirir ve bildirilen
        konumu sürükler. Bölgeden çıkınca alıcı gerçek uydulara döner (kayma sıfırlanır)."""
        dt = self.cfg.dt
        covered = np.zeros(self.N, bool)
        for s in self.gps_spoofers:
            cov = s.covers(self.pos) & self.alive & self.gps_rx & ~covered
            if cov.any():
                off = self.spoof_off[cov] + s.dir * s.drag * dt
                n = np.linalg.norm(off, axis=1, keepdims=True)
                self.spoof_off[cov] = off * np.minimum(1.0, s.max_offset / np.maximum(n, 1e-9))
            covered |= cov
        new = covered & ~self.spoofed
        self.captured_at[new] = self.t
        self.spoof_off[~covered] = 0.0
        self.spoofed = covered
        self.last_spoofed[covered] = self.t

    def _spoof_flag(self, i, size=None, why=""):
        """İHA GPS'ine artık güvenmez: IMU ile devam eder, belirsizliğini büyütür, bölgeyi paylaşır."""
        if not self.gps_trust[i]:
            return
        self.spoof_log.append((round(self.t, 1), int(i), why, bool(self.spoofed[i]), round(self.sigma(i), 1)))
        self.gps_trust[i] = False
        self.gps_ok[i] = False
        self.sig0[i] = max(self.sigma(i), (size or 20.0) + 10.0)
        self.dr_t[i] = 0.0
        self.peer_good[i] = 0
        ix, iy = cell_idx(self.est[i, 0], self.est[i, 1])
        self.spf_t[i, max(ix - 1, 0):ix + 2, max(iy - 1, 0):iy + 2] = self.t
        if self.spoofed[i] and np.isfinite(self.captured_at[i]):
            self.m_spoof_detect.append(self.t - self.captured_at[i])
        elif self.t - self.last_spoofed[i] > 15.0:
            self.m["spoof_false_alarm"] += 1     # (bölgeden yeni çıkınca GPS'in geri sıçramasını yakalamak yanlış alarm değil)

    def _ew_1hz(self):
        c, now, N = self.cfg, self.t, self.N
        # IMU tutarlılık testi için GPS okuması ve (IMU'nun bildiği) gerçek yer değiştirme geçmişi
        reading = self.pos[:, :2] + self.spoof_off[:, :2] + self.rng.normal(0, 1.5, (N, 2))
        self.gps_hist = np.roll(self.gps_hist, -1, axis=1)
        self.gps_hist[:, -1, :2] = np.where(self.gps_rx[:, None], reading, np.nan)
        self.gps_hist[:, -1, 2:] = self.pos[:, :2]
        if self.ew.spoof_detect:
            self._spoof_tests()
        if self.ew.trust:
            self.tr_a *= 0.98                     # eski kanıt yavaş unutulur
            self.tr_b *= 0.98
        if self.ew.localize and self.jammers:
            self._localize_tick()
        if self.ew.radar and self.radars:
            self._radar_fix_tick()

    def _spoof_tests(self):
        c, now = self.cfg, self.t
        W = 10
        sw = c.imu_drift * np.sqrt(W ** 3 / 3.0)                      # IMU'nun 10 s'lik konum hatası (m)
        thr = 5.0 * np.sqrt(sw ** 2 + 2 * 1.5 ** 2)                   # test başına yanlış alarm ~ 4/1 000 000
        old, new = self.gps_hist[:, -1 - W], self.gps_hist[:, -1]
        e = (new[:, :2] - old[:, :2]) - (new[:, 2:] - old[:, 2:]) + self.rng.normal(0, sw, (self.N, 2))
        en = np.linalg.norm(e, axis=1)
        valid = np.isfinite(en) & self.alive & ~self.spoofer
        sp_cells = self.spf_t > now - 120.0
        for i in np.nonzero(valid)[0]:
            if self.gps_trust[i] and en[i] > thr:
                self._spoof_flag(i, en[i], "imu")                      # 1) IMU ile tutmuyor
        # 2) Komşu menzil testi: GPS'ten hesaplanan uzaklıklar telsizle ölçülenle tutuyor mu?
        H = self.heard
        for i in np.nonzero(self.alive & ~self.spoofer)[0]:
            K = np.nonzero(H[:, i] & self.alive & ~self.distrust[i] & (self.st_t[i] > now - 1.5))[0]
            K = K[K != i]
            if len(K) < 3:
                continue
            meas = np.linalg.norm(self.pos[K] - self.pos[i], axis=1) + self.rng.normal(0, 1.0, len(K))
            pred = np.linalg.norm(self.st_pos[i, K, :2] - self.est[i, :2], axis=1)
            tol = 6.0 + 2.5 * (self.sigma(i) + self.st_sig[i, K])
            bad = float(np.median(np.abs(pred - meas) / tol)) > 1.0
            if self.gps_trust[i]:
                self.peer_bad[i] = self.peer_bad[i] + 1 if bad else 0
                if self.peer_bad[i] >= 3:
                    self._spoof_flag(i, why="komsu")
            else:
                # Güveni geri kazanma: aldatma bölgesinin dışında ve GPS hem IMU hem komşularla tutarlı
                ix, iy = cell_idx(self.est[i, 0], self.est[i, 1])
                calm = (np.isfinite(en[i]) and en[i] < thr / 2) and not sp_cells[i, ix, iy] and self.gps_rx[i]
                self.peer_good[i] = self.peer_good[i] + 1 if (calm and not bad) else 0
                if self.peer_good[i] >= 10:
                    self.gps_trust[i] = True
                    self.peer_bad[i] = 0

    def _localize_tick(self):
        """Dirençli İHA'lar karıştırma gücü ölçer; her İHA 2 s'de bir bildiği ölçümlerle karıştırıcıyı bulur
        ve kestirilen karıştırma alanını haritasına işler (henüz girmediği karıştırılan hücreler dahil)."""
        c, now, N = self.cfg, self.t, self.N
        honest = self.alive & ~self.spoofer
        # Konumundan emin olmayan (GPS'siz, sigma büyük) İHA ölçüm kaydetmez: yanlış yerde ölçüm kestirimi bozar
        sig = np.array([self.sigma(i) for i in range(N)])
        rec = honest & (self.jrx > c.noise_dbm + 3.0) & (sig < 8.0)
        for i in np.nonzero(rec)[0]:
            k = self.meas_n[i] % self.MB
            self.meas_t[i, k], self.meas_xy[i, k] = now, self.est[i, :2]
            self.meas_db[i, k] = self.jrx[i] + self.rng.normal(0, 2.0)       # gölgeleme / ölçüm hatası
            self.meas_n[i] += 1
        tick = int(round(now))
        errs = []
        active = np.nonzero(honest & (self.phase >= TRANSIT) & (self.phase <= REGROUP))[0]
        if len(active) == 0:
            return
        turn = set(active[(tick * 2 + np.arange(2)) % len(active)].tolist())   # her saniye sırayla 2 İHA
        for i in active:
            if i not in turn:
                continue
            know = np.maximum(self.st_t[i], -np.inf)
            know[i] = now
            # Son 20 s (hareketli karıştırıcıyı izlemek için); ölçüm azsa pencere 60 s'ye genişler
            known = (self.meas_t <= know[:, None]) & ~self.distrust[i][:, None]
            ok = known & (self.meas_t >= now - 20.0)
            if ok.sum() < 40:
                ok = known & (self.meas_t >= now - 60.0)
            if ok.sum() < 6:
                continue
            X, Rm = self.meas_xy[ok], self.meas_db[ok]
            if len(Rm) > 60:                                                # hesap yükü için alt örnekle
                sel = self.rng.choice(len(Rm), 60, replace=False)
                X, Rm = X[sel], Rm[sel]
            est, _ = ew.localize(X, Rm, c)
            self.loc_est[i] = est
            if est and self.ew.jam_map:
                pred = ew.predicted_jam_dbm(self._cell_xy, est, c).reshape(GRID_N, GRID_N)
                self.jam_t[i][pred > c.jam_detect_dbm] = now
            if est:
                errs.append(self._loc_error(est))
        if errs:
            err = float(np.median(errs))
            self.loc_err_log.append((now, err))
            if np.isnan(self.t_locate) and err < 50.0:
                self.t_locate = now

    def _loc_error(self, est):
        """Kestirimin hatası: her gerçek karıştırıcının en yakın kestirime uzaklığının ortalaması."""
        q = np.array([e[0] for e in est])
        return float(np.mean([np.linalg.norm(q - j.xy, axis=1).min() for j in self.jammers]))

    def _check_arrivals(self):
        c = self.cfg
        for i in range(self.N):
            t = self.my_task[i]
            if t < 0 or self.spoofer[i] or not self.alive[i] or self.phase[i] not in (TRANSIT, TASK, REGROUP):
                continue
            d_true = np.linalg.norm(self.pos[i, :2] - self.tasks[t, :2])
            if d_true < c.task_radius or (self.search[i] > 0 and d_true < c.search_detect):
                # Kamera hedefi gerçekten gördü (aramada tanıyınca görsel güdümle üstüne gelir)
                if self.done[t]:
                    self.m["redundant"] += 1
                else:
                    self.done[t], self.done_time[t] = True, self.t
                    self.r.done[i] += 1
                    self.r.task_by[t] = i
                self.known_done[i, t], self.done_by[i, t] = True, i
                if self.att_task[i] == t:
                    self._close_attempt(i, True)
                self._drop(i, t)
                continue
            if self.phase[i] != TASK:
                continue
            if self.search[i] > 0:
                b = c.search_detect / np.pi
                self.search[i] += 9.0 / max(b * self.search[i], 5.0) * c.dt
                if b * self.search[i] > self.search_r[i]:
                    # Dirençli İHA görmediği hedefe "bitti" demez: bırakır, GPS'i geri
                    # kazanınca (kendisi ya da bir arkadaşı) yeniden dener.
                    self.m["retries"] += 1
                    if self.att_task[i] == t:
                        self._close_attempt(i, False)
                    self.cooldown[i, t] = self.t + self.cfg.retry_cooldown
                    self.cl_bid[i, t], self.cl_id[i, t], self.cl_time[i, t] = -np.inf, -1, -np.inf
                    self._drop(i, t)
                    # Konumundan emin olduğu (GPS sağlam) hâlde hedefi bulamadı: GPS yalan söylüyor olabilir
                    if self.ew.spoof_detect and self.search_sig[i] < 8.0 and self.gps_ok[i]:
                        self._spoof_flag(i, why="arama")
            elif np.linalg.norm(self.est[i, :2] - self.tasks[t, :2]) < 0.4 * c.task_radius:
                # "Vardım" sanıyor ama hedef kamerada yok: konum kestirimi yanlış
                sig = self.sigma(i)
                if self.ew.search:
                    # Dirençli: görmediği hedefe "bitti" demez; belirsizlik çemberini (2.5 sigma)
                    # kapsayan spiral arama yapar
                    self.search[i] = 1.0
                    self.r.search[i] += 1
                    self.search_r[i] = min(2.5 * sig + 10.0, 100.0)
                    self.search_sig[i] = sig
                else:
                    self._give_up(i, t)

    def _give_up(self, i, t):
        """İHA görevi bitti sanar ama aslında bitmedi -> yanlış tamamlanma."""
        if not self.done[t]:
            self.m["false_done"] += 1
            self.r.wrong[i] += 1
        if self.att_task[i] == t:
            self._close_attempt(i, False)
        self.known_done[i, t], self.done_by[i, t] = True, i
        self._drop(i, t)

    # ----------------------------------------------------------- ölçümler
    def _metrics(self):
        c = self.cfg
        honest = ~self.spoofer & self.alive
        self._report_step()
        self.m["locerr_sum"] += float(np.linalg.norm(self.est[honest] - self.pos[honest], axis=1).mean())
        self.m["locerr_n"] += 1
        # Görev alanında katedilen yol (enerji göstergesi)
        work = honest & M_WORK[self.phase]
        self.m["task_dist"] += float(np.linalg.norm(self.vel[work, :2], axis=1).sum()) * c.dt
        # Arazi açıklığı: düzen ve görev uçuşu sırasında yerden yükseklik
        cruise = self.alive & M_CRUISE[self.phase]
        if cruise.any():
            agl = self.pos[cruise, 2] - self.terrain.height(self.pos[cruise, 0], self.pos[cruise, 1])
            self.m["min_agl"] = min(self.m["min_agl"], float(agl.min()))
            self.m["low_agl"] += int((agl < 10.0).sum())
        # Düzen hatası: intikal ve dönüşte yuvaya uzaklık
        fm = self.alive & M_FORM[self.phase]
        if fm.any():
            self.m["form_sum"] += float(self.slot_err_true[fm].mean())
            self.m["form_n"] += 1
        if self.k % c.comm_every == 0:
            A = (self.link_q > 0.5) & (self.link_q.T > 0.5)
            idx = np.nonzero(self.alive)[0]
            sub = A[np.ix_(idx, idx)].astype(float)
            if len(idx) > 1:
                L = np.diag(sub.sum(1)) - sub
                self.m["lam2_sum"] += float(np.sort(np.linalg.eigvalsh(L))[1])
                self.m["lam2_n"] += 1
            # Bağlantılılık: görev evresinde dürüst İHA'lar tek ağ mı?
            ti = np.nonzero(honest & M_WORK[self.phase])[0]
            if len(ti) >= 2:
                self.last_conn = largest_component(A[np.ix_(ti, ti)])
                self.m["conn_sum"] += self.last_conn
                self.m["conn_n"] += 1

    def score(self):
        """Görev puanı (0-1): yapılan görevlerin zamanla azalan değerlerinin toplamı / tüm değerler.
        1 = her görev belirdiği an yapıldı. Yapılmayan görev 0 puan."""
        sched = np.isfinite(self.appear)
        late = np.maximum(np.nan_to_num(self.done_time, nan=0.0) - self.ref_t, 0.0)
        got = np.where(self.done & sched, self.value * np.exp(self.lnlam * late), 0.0)
        return float(got.sum() / max(self.value[sched].sum(), 1e-9))

    def _trust_stats(self):
        """Dürüst İHA'ların saldırganları dışlama oranı ve dürüst bir arkadaşı yanlışlıkla dışlama oranı."""
        hon = np.nonzero(self.alive & ~self.spoofer)[0]
        sp = np.nonzero(self.spoofer)[0]
        caught = float(self.distrust[np.ix_(hon, sp)].mean()) if len(hon) and len(sp) else np.nan
        others = self.distrust[np.ix_(hon, hon)]
        wrong = float(others.sum() / max(len(hon) * (len(hon) - 1), 1)) if len(hon) > 1 else 0.0
        return caught, wrong

    def _frame_jam_est(self):
        """Sürünün kestirdiği karıştırıcılar (en çok ölçüm yapmış dürüst İHA'nın kestirimi)."""
        cand = [i for i in range(self.N) if self.alive[i] and not self.spoofer[i] and self.loc_est[i]]
        if not cand:
            return []
        i = max(cand, key=lambda k: self.meas_n[k])
        return [{"p": [round(float(q[0]), 1), round(float(q[1]), 1), round(float(self.terrain.height(*q)), 1)],
                 "pw": round(P, 1), "r": round(radio.jam_radius(P, self.cfg), 1)} for q, P in self.loc_est[i]]

    # ----------------------------------------------------------- uçuş raporu
    def _mode(self, i):
        """İHA'nın Unity'deki durumu: 0 normal, 1 spiral arama, 2 saldırgan, 3 röle, 4 arızalı, 5 GPS kurtarma,
        6 GPS'i aldatılıyor (fark etmedi), 7 aldatmayı fark etti, 8 batarya dönüşü, 9 radardan kaçıyor."""
        return (4 if not self.alive[i] else 2 if self.spoofer[i] else 8 if self.rtb[i]
                else 9 if self.t < self.evade_until[i] else 3 if self.relay_for[i] >= 0
                else 1 if self.search[i] > 0 else 5 if self.recover[i]
                else 7 if not self.gps_trust[i] else 6 if self.spoofed[i] else 0)

    def _status(self, i):
        """İzin rengi için tek harflik durum: Unity'deki ışık rengiyle aynı öncelik (DroneView.StatusColor).
        n normal, j karıştırılıyor, g GPS yok, s spiral arama, r röle, a saldırgan, p aldatılıyor, y fark etti, f arızalı,
        b batarya dönüşü, k radardan kaçıyor, t radar izliyor"""
        m = self._mode(i)
        if m in (4, 2, 8, 9, 3, 7, 6):
            return {4: "f", 2: "a", 8: "b", 9: "k", 3: "r", 7: "y", 6: "p"}[m]
        if any(R.track[i] for R in self.radars):
            return "t"
        if not self.gps_ok[i]:
            return "g"
        return "s" if m == 1 else "j" if self.jrx[i] > -89.5 else "n"

    def _track_point(self, i):
        self.r.track[i].append((int(round(self.pos[i, 0])), int(round(self.pos[i, 1])), self._status(i)))

    def _report_step(self):
        """Rapor sayaçları: her adımda süreler ve yol, 3 s'de bir iz noktası (uçan İHA'lar)."""
        c, r = self.cfg, self.r
        air = self.alive & ~M_GROUND[self.phase]
        r.dist[self.alive] += np.linalg.norm(self.vel[self.alive], axis=1) * c.dt
        r.nogps[air & ~self.gps_ok] += c.dt
        r.jam[air & (self.jrx > c.jam_detect_dbm)] += c.dt
        r.relay[self.relay_for >= 0] += c.dt
        r.spoofed[air & self.spoofed] += c.dt
        r.seen |= self.alive & ~self.gps_trust
        if self.k % 30 == 1:
            for i in np.nonzero(self.alive & (self.phase != LANDED))[0]:
                self._track_point(i)

    def report(self):
        """Uçuş raporu (Unity'deki "Uçuş raporu" sekmesi): her İHA'nın ne yaptığı ve uçtuğu iz."""
        r = self.r
        drones = []
        for i in range(self.N):
            tr = list(r.track[i])
            if self.alive[i]:
                tr.append((int(round(self.pos[i, 0])), int(round(self.pos[i, 1])), self._status(i)))
            if len(tr) > TRACK_MAX:                  # uzun uçuşta iz seyreltilir (kare UDP sınırını aşmasın)
                tr = [tr[k] for k in np.linspace(0, len(tr) - 1, TRACK_MAX).round().astype(int)]
            drones.append({
                "id": i, "done": int(r.done[i]), "wrong": int(r.wrong[i]), "search": int(r.search[i]),
                "recover": int(r.recover[i]), "dist": round(float(r.dist[i]), 1), "nogps": round(float(r.nogps[i]), 1),
                "jam": round(float(r.jam[i]), 1), "relay": round(float(r.relay[i]), 1),
                "spoofed": round(float(r.spoofed[i]), 1), "seen": int(r.seen[i]), "liar": int(self.spoofer[i]),
                "fail": round(float(r.fail_t[i]), 1) if np.isfinite(r.fail_t[i]) else -1.0,
                "cause": r.cause[i], "wh": round(float(r.wh[i]), 2), "bat0": round(float(self.bat0[i] / energy.CAPACITY_WH), 2),
                "bat": round(float(self.bat[i] / energy.CAPACITY_WH), 2), "radar": round(float(self.radar_track_t[i]), 1),
                "rtb": round(float(r.rtb[i]), 1) if np.isfinite(r.rtb[i]) else -1.0,
                "xy": [v for p in tr for v in p[:2]], "st": "".join(p[2] for p in tr),
            })
        return {"t": round(self.t, 1), "mission": round(float(self.mission_time()), 1), "drones": drones,
                "taskBy": [int(x) for x in r.task_by]}

    def _field_axes(self):
        """Isı haritasının kapsadığı alan: üs, görev alanı ve karıştırıcıların (rotalarıyla) çevresi."""
        c = self.cfg
        ac, h = np.asarray(c.area_center, float), c.area_half + 200.0
        pts = [ac - h, ac + h, self.home - 200.0, self.home + 200.0]
        for d in c.jammers:
            for p in [d["pos"][:2]] + list(d.get("route") or []):
                pts += [np.asarray(p, float) - 300.0, np.asarray(p, float) + 300.0]
        for d in c.radars:
            pts += [np.asarray(d["pos"][:2], float) - 150.0, np.asarray(d["pos"][:2], float) + 150.0]
        lo, hi = np.min(pts, axis=0), np.max(pts, axis=0)
        if not self.terrain.flat:
            edge = self.terrain.origin + (self.terrain.n - 1) * self.terrain.step
            lo, hi = np.maximum(lo, self.terrain.origin), np.minimum(hi, edge)
        step = max(FIELD_STEP, float((hi - lo).max()) / (FIELD_MAX - 1))
        return np.arange(lo[0], hi[0] + 1e-6, step), np.arange(lo[1], hi[1] + 1e-6, step), step

    def jam_field(self):
        """Karıştırma ısı haritası: uçuş yüksekliğinde haberleşme kanalına düşen karıştırma gücü.
        Karıştırıcı bir ızgara aralığı kadar yer değiştirmedikçe yeniden hesaplanmaz. Karıştırıcı yoksa None."""
        if not self.jammers:
            return None
        xs, ys, step = self._field_axes() if self._field is None else self._field["axes"]
        key = np.round(np.array([j.xy for j in self.jammers]) / step)
        if self._field is None or not np.array_equal(key, self._field_key):
            J = radio.jam_field_dbm(xs, ys, self.jammers, self.cfg, self.terrain, self.cfg.agl)
            q = np.clip(np.round((J - FIELD_DB0) / FIELD_DB_STEP), 0, 255).astype(np.uint8)
            self._field_key = key
            self._field = {"axes": (xs, ys, step), "msg": {
                "rev": next(_FIELD_REV), "x0": round(float(xs[0]), 2), "y0": round(float(ys[0]), 2),
                "step": round(step, 3), "nx": len(xs), "ny": len(ys), "agl": self.cfg.agl,
                "db0": FIELD_DB0, "dbStep": FIELD_DB_STEP,
                # Haritadaki eş güç çizgileri: İHA karıştırmayı fark eder / 60 m'deki komşuyla bağlantı kopar
                "detect": self.cfg.jam_detect_dbm, "cut": round(radio.jam_tolerance_dbm(self.cfg, 60.0), 2),
                "q": base64.b64encode(q.tobytes()).decode("ascii"),   # satır = kuzey (y), sütun = doğu (x)
            }}
        return self._field["msg"]

    def radar_field(self):
        """Radar görüş haritası (görselleştirme): uçuş yüksekliğinde açık radarların bir taramada İHA'yı
        görme olasılığı (0-1 -> 0-255 bayt), arazi gölgesiyle. Radar açılıp kapanınca yeniden hesaplanır."""
        on = [R for R in self.radars if R.active(self.t)]
        if not self.radars:
            return None
        key = tuple(R.id for R in on)
        if self._rfield is None or key != self._rfield_key:
            xs, ys, step = self._field_axes() if self._field is None else self._field["axes"]
            gx, gy = np.meshgrid(xs, ys)
            pts = np.c_[gx.ravel(), gy.ravel(), self.terrain.height(gx.ravel(), gy.ravel()) + self.cfg.agl]
            miss = np.ones(len(pts))
            for R in on:
                miss *= 1.0 - threat.coverage(R.pos, pts, self.terrain, R.r50)
            q = np.clip(np.round((1.0 - miss) * 255.0), 0, 255).astype(np.uint8)
            self._rfield_key = key
            self._rfield = {"rev": next(_FIELD_REV), "x0": round(float(xs[0]), 2), "y0": round(float(ys[0]), 2),
                            "step": round(step, 3), "nx": len(xs), "ny": len(ys), "agl": self.cfg.agl,
                            "q": base64.b64encode(q.tobytes()).decode("ascii")}
        return self._rfield

    def _ew_summary(self):
        errs = [e for _, e in self.loc_err_log]
        tail = [e for t, e in self.loc_err_log if t >= self.t - 60.0]
        caught, wrong = self._trust_stats()
        honest = ~self.spoofer
        return dict(
            jam_loc_err=float(np.mean(errs)) if errs else np.nan,          # karıştırıcı konum hatası (m)
            jam_loc_err_end=float(np.mean(tail)) if tail else np.nan,
            t_locate=float(self.t_locate),                                 # 50 m'den iyi bulunduğu an (s)
            spoof_captured=int(np.isfinite(self.captured_at[honest]).sum()),
            spoof_detect_time=float(np.mean(self.m_spoof_detect)) if self.m_spoof_detect else np.nan,
            spoof_detected=len(self.m_spoof_detect),
            spoof_false_alarm=self.m["spoof_false_alarm"],
            liars_caught=caught,                                           # saldırganları dışlama oranı
            honest_excluded=wrong,                                         # dürüst arkadaşı yanlış dışlama
        )

    def _threat_summary(self):
        """Radar ve enerji ölçümleri (yalnızca bu tehditler varken)."""
        out = {}
        if self.radars:
            errs = [e for _, e in self.rd_err_log]
            honest = ~self.spoofer
            out.update(
                shot_down=int(sum(1 for i in range(self.N) if self.r.cause[i] == "radar")),
                missiles=int(sum(R.fired for R in self.radars)),
                radar_track=float(self.radar_track_t[honest].sum()),          # İHA'ların izlendiği toplam süre (s)
                radar_loc_err=float(errs[-1]) if errs else np.nan,           # radar konum kestirimi hatası (m)
                t_radar_fix=float(self.t_radar_fix),
            )
        if self.energy_on:
            out.update(
                depleted=int(sum(1 for i in range(self.N) if self.r.cause[i] == "batarya")),
                rtb=int(np.isfinite(self.r.rtb).sum()),
                energy_wh=float(self.r.wh[~self.spoofer].mean()),
                min_soc=float((self.bat[~self.spoofer] / energy.CAPACITY_WH).min()),
            )
        return out

    def summary(self):
        m = self.m
        sched = np.isfinite(self.appear)
        pop = self.popup & sched & self.done
        hi = sched & self.done & (self.value >= 3)
        return dict(
            completion=float(self.done[sched].mean()),
            score=self.score(),
            popup_done=float(self.done[self.popup & sched].mean()) if (self.popup & sched).any() else np.nan,
            popup_resp=float(np.mean(self.done_time[pop] - self.appear[pop])) if pop.any() else np.nan,
            high_time=float(np.mean(self.done_time[hi] - self.ref_t[hi])) if hi.any() else np.nan,
            reassign=m["reassign"],
            task_dist=m["task_dist"],
            **self._ew_summary(),
            finish_time=float(self.finished_t),
            mean_task_time=float(np.nanmean(self.done_time)) if self.done.any() else np.nan,
            redundant=m["redundant"],
            false_done=m["false_done"],
            retries=m["retries"],
            mission_time=self.mission_time(),
            near_miss=m["near_miss"],
            pdr=m["pdr_sum"] / max(m["pdr_n"], 1),
            loc_err=m["locerr_sum"] / max(m["locerr_n"], 1),
            lam2=m["lam2_sum"] / max(m["lam2_n"], 1),
            connectivity=m["conn_sum"] / max(m["conn_n"], 1),
            formation_err=m["form_sum"] / max(m["form_n"], 1),
            min_agl=m["min_agl"],
            relay_time=m["relay_time"],
            failures=m["failures"],
            sim_time=self.t,
            **self._threat_summary(),
        )

    # ----------------------------------------------------------- canlı komutlar
    def cycle_formation(self):
        k = FORMATIONS.index(self.form_kind) if self.form_kind in FORMATIONS else -1
        self.form_kind = FORMATIONS[(k + 1) % len(FORMATIONS)]

    def add_popup(self, xy=None):
        """Canlı gösterim: yedek hedeflerden birini şimdi belirtir (yer istasyonu ihbarı). Görev
        alanında rastgele bir yer seçilir. Döndürür: hedef numarası (yedek kalmadıysa -1)."""
        free = np.nonzero(np.isinf(self.appear))[0]
        if len(free) == 0:
            return -1
        t = int(free[0])
        if xy is None:
            ac, h = np.asarray(self.cfg.area_center, float), self.cfg.area_half - 40
            xy = ac + self.rng.uniform(-h, h, 2)
        g = float(self.terrain.height(xy[0], xy[1]))
        self.tasks[t] = [xy[0], xy[1], g + self.cfg.agl]
        self.task_ground[t] = g
        self.task_ix[t], self.task_iy[t] = cell_idx(xy[0], xy[1])
        self.appear[t] = self.ref_t[t] = self.t
        self.finished_t = np.nan
        # Görev bitip sürü dönüşe geçtiyse, dönen İHA'lar görev alanına geri çağrılır
        self.gcs_return_t = np.inf
        for i in np.nonzero(self.alive & (self.phase == RETURN))[0]:
            self._set_phase(i, TASK)
            self.idle_t[i] = 0.0
        return t

    # ----------------------------------------------------------- Unity karesi
    def frame(self):
        """Unity'ye gönderilen anlık durum. Koordinatlar ENU (x doğu, y kuzey, z yukarı)."""
        c = self.cfg
        r = lambda v: [round(float(x), 2) for x in v]
        claimed = set(int(t) for t in self.my_task if t >= 0)
        believed = self.known_done[~self.spoofer].any(0) | self.gcs_done
        known = self.known_task[self.alive & ~self.spoofer].any(0)
        tasks = []
        for t in range(self.T):
            if self.appear[t] > self.t:
                s = -1                                   # henüz belirmedi
            else:
                s = 2 if self.done[t] else 3 if believed[t] else 1 if t in claimed else 0
            tasks.append({"p": r(self.tasks[t]), "s": s, "v": int(self.value[t]),
                          "age": round(float(self.t - self.appear[t]), 1) if self.popup[t] and s >= 0 else -1.0,
                          "k": int(known[t])})
        drones = []
        for i in range(self.N):
            mode = self._mode(i)
            plan = [int(t) for t in self.path[i]] if self.alive[i] and not self.spoofer[i] else []
            d = {
                "id": i, "p": r(self.pos[i]), "e": r(self.est[i]), "v": r(self.vel[i]),
                "jam": round(float(np.clip((self.jrx[i] + 100.0) / 30.0, 0, 1)), 3),
                "gps": int(self.gps_ok[i]), "task": int(self.my_task[i]), "mode": mode,
                "sigma": round(self.sigma(i), 1), "phase": int(self.phase[i]),
                "relay": int(self.relay_for[i]), "plan": plan,
                "bat": round(float(self.bat[i] / energy.CAPACITY_WH), 3), "pw": int(round(float(self.power[i]))),
            }
            if self.radars:
                d["trk"] = int(any(R.track[i] for R in self.radars))
                d["rw"] = 2 if self.rw_lock[i] else 1 if self.t - self.rw_lit[i] < 3.0 else 0
                if self.route[i] is not None and self.alive[i]:
                    d["route"] = [int(round(float(v))) for v in self.route[i].p.ravel()]
            drones.append(d)
        links = []
        for i in range(self.N):
            for j in range(i + 1, self.N):
                q = 0.5 * (self.link_q[i, j] + self.link_q[j, i])
                if q > 0.05:
                    links += [i, j, round(float(q), 3)]
        ctr = cell_centers(self.jam_grid.any(0)) if self.ew.jam_map else np.zeros((0, 2))
        jam_cells = [round(float(v), 1) for v in ctr.ravel()]
        live = self.phase[self.alive]
        dominant = int(np.bincount(live, minlength=7).argmax()) if len(live) else LANDED
        fm = self.alive & M_FORM[self.phase]
        sched = np.isfinite(self.appear) & (self.appear <= self.t)
        out = {
            "t": round(self.t, 2),
            "strategy": c.strategy,
            "region": c.region,
            "planner": c.planner,
            "phase": PHASE_NAMES[dominant],
            "formation": self.form_kind,
            "drones": drones,
            "links": links,
            "tasks": tasks,
            "jammers": [{"p": r(j.pos), "pw": j.power, "r": round(radio.jam_radius(j.comm_power, c), 1),
                         "band": j.band, "v": r(j.vel)} for j in self.jammers],
            "jamEst": self._frame_jam_est(),
            "spoofers": [{"p": r(np.r_[s.xy, float(self.terrain.height(*s.xy))]), "r": s.radius}
                         for s in self.gps_spoofers],
            "fhss": int(self.ew.fhss),
            "wind": [round(float(v), 2) for v in (self.wind.vec if self.wind.on else (0.0, 0.0))],
            "radars": [{"p": r(R.pos), "az": round(float(np.degrees(R.az)), 1), "on": int(R.active(self.t)),
                        "r": R.r50, "known": int(R.known), "n": R.missiles,
                        "trk": [int(i) for i in np.nonzero(R.track)[0]]} for R in self.radars],
            "missiles": [{"id": M.id, "p": r(M.pos), "v": r(M.vel), "st": M.state, "tgt": int(M.target), "r": M.radar}
                         for M in self.missiles],
            "radarEst": self._frame_radar_est(),
            "gcs": {"p": r(self.gcs), "on": int(self.central), "up": [int(x) for x in self.gcs_up]},
            "cell": CELL,
            "jamCells": jam_cells,
            "m": {
                "done": int(self.done.sum()), "total": int(sched.sum()),
                "score": round(self.score(), 3), "reassign": self.m["reassign"],
                "popups": int((sched & self.popup).sum()),
                "falseDone": self.m["false_done"], "redundant": self.m["redundant"],
                "pdr": round(self.last_pdr, 3),
                "locErr": round(float(np.linalg.norm(self.est[self.alive] - self.pos[self.alive], axis=1).mean()), 2)
                if self.alive.any() else 0.0,
                "gpsLost": int((~self.gps_ok & self.alive).sum()),
                "conn": round(self.last_conn, 2),
                "formErr": round(float(self.slot_err_true[fm].mean()), 1) if fm.any() else 0.0,
                "relays": int((self.relay_for >= 0).sum()),
                "alive": int(self.alive.sum()),
                "jamErr": round(self.loc_err_log[-1][1], 1) if self.loc_err_log else -1.0,
                "spoofed": int((self.spoofed & self.alive).sum()),
                "spoofSeen": int((~self.gps_trust & self.alive).sum()),
                "liars": round(float(np.nan_to_num(self._trust_stats()[0], nan=-1.0)), 2),
                "bat": round(float((self.bat[self.alive] / energy.CAPACITY_WH).mean()), 3) if self.alive.any() else 0.0,
                "shot": int(sum(1 for x in self.r.cause if x == "radar")),
                "depleted": int(sum(1 for x in self.r.cause if x == "batarya")),
                "rtb": int(self.rtb.sum()),
                "radarErr": round(self.rd_err_log[-1][1], 1) if self.rd_err_log else -1.0,
            },
        }
        # Uçuş raporu: iniş bitince ilk karede ve sonra 60 karede bir (Unity sonradan bağlanırsa diye)
        if self.flight_over():
            self._report_frames += 1
            if self._report_frames % 60 == 1:
                out["report"] = self.report()
        # Isı haritası büyük (~16 KB): yalnızca değişince ve ara ara (Unity sonradan bağlanırsa diye) eklenir.
        # Raporla aynı kareye konmaz (ikisi birden kareyi UDP sınırına yaklaştırır); bir sonraki kareye kalır.
        field = self.jam_field()
        if (field is not None and "report" not in out
                and (field["rev"] != self._field_sent or self.t - self._field_sent_t >= FIELD_RESEND)):
            out["jamField"] = field
            self._field_sent, self._field_sent_t = field["rev"], self.t
        # Radar görüş haritası: aynı kuralla, ısı haritasıyla ve raporla aynı kareye konmaz
        rf = self.radar_field()
        if (rf is not None and "report" not in out and "jamField" not in out
                and (rf["rev"] != self._rfield_sent or self.t - self._rfield_sent_t >= RADAR_RESEND)):
            out["radarField"] = rf
            self._rfield_sent, self._rfield_sent_t = rf["rev"], self.t
        return out

    def _frame_radar_est(self):
        """Sürünün bildiği radarlar (en çok bilen dürüst İHA'nın kestirimi)."""
        j = self._radar_view() if self.radars else -1
        if j < 0:
            return []
        return [{"p": [round(float(q[0]), 1), round(float(q[1]), 1), round(float(self.terrain.height(*q)), 1)],
                 "e": round(float(err), 1), "id": int(k), "intel": int(self.radars[k].known and err >= self.cfg.intel_err - 1e-6)}
                for k, (q, err) in self.rd_est[j].items()]
