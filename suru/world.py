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
                  5) belirsizlik büyükse hedefte spiral arama
                  6) makul olmayan teklifleri yayan İHA'ya güvenmeme (sahte bilgiye karşı)
                  7) bağlantı koruma: kopan arkadaşa ulaşmak için kendiliğinden röle olma

Sürü zekâsı (suru/swarm.py): lidersiz düzen uçuşu (konsensüs), Reynolds kuralları,
arazi takibi, röle ile bağlantı koruma, üye kaybında görev ve düzenin yeniden dağıtımı.

Otonom karar alma (suru/decision.py): görevlerin değeri (önceliği) vardır ve beklendikçe azalır.
Görev sırasında yeni hedefler belirir (yer istasyonu ihbarı ya da İHA sensörü). Görev paylaşımı
CBBA (merkeziyetsiz paket planlama ve uzlaşma), SGA (merkezi) ya da eski açgözlü yöntemle yapılır.
"""
import numpy as np
from scipy.optimize import linear_sum_assignment

from . import decision, radio
from .config import SimConfig
from .swarm import FORMATIONS, Path, formation_offsets, largest_component, place, reynolds
from .terrain import Terrain

CELL = 50.0  # karıştırma haritası hücre boyu (m)
GRID_O, GRID_N = -1200.0, 48  # karıştırma haritası ızgarası: başlangıç köşesi (m) ve hücre sayısı

# Uçuş evreleri
TAKEOFF, TRANSIT, TASK, REGROUP, RETURN, LAND, LANDED = range(7)
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


def shared_terrain(flat):
    """Arazi dosyası bir kez yüklenir, tüm simülasyonlar paylaşır."""
    if flat not in _TERRAIN_CACHE:
        _TERRAIN_CACHE[flat] = Terrain(flat=flat)
    return _TERRAIN_CACHE[flat]


class World:
    def __init__(self, cfg: SimConfig):
        self.cfg = c = cfg
        self.rng = rng = np.random.default_rng(c.seed)
        self.N, self.T = N, T = c.n_drones, c.n_tasks
        self.t, self.k = 0.0, 0
        self.resilient = c.strategy == "resilient"
        self.central = c.strategy == "centralized"
        self.relay_on = c.relay_enabled()
        self.terrain = shared_terrain(not c.terrain)
        self.cbba = c.planner in ("cbba", "ai")
        self.ai = None
        if c.planner == "ai":
            self.ai = (decision.AIValue(c.ai_theta) if len(c.ai_theta)
                       else decision.AIValue.load(c.ai_weights or decision.AI_WEIGHTS))
        self.lnlam = float(np.log(c.discount))
        self.cruise = 0.9 * c.max_speed           # plan yaparken kullanılan seyir hızı tahmini

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
        self.gps_ok = np.ones(N, bool)
        self.dr_t = np.zeros(N)             # son konum düzeltmesinden beri geçen süre
        self.sig0 = np.full(N, 1.5)         # son düzeltmedeki konum belirsizliği (m)
        self.jammers = [(np.asarray(j["pos"], float), float(j["power_dbm"])) for j in c.jammers]
        self.jrx = np.full(N, -300.0)

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
        self.recover = np.zeros(N, bool)         # (dirençli) GPS'i geri almaya gidiyor
        self.recover_block = np.zeros(N)         # bu andan önce yeniden kurtarma denenmez
        self.last_fix = self.pos[:, :2].copy()   # son GPS alınan nokta
        self.distrust = np.zeros((N, N), bool)   # distrust[j, i]: j, i'ye güvenmiyor
        self.jam_grid = np.zeros((N, GRID_N, GRID_N), bool)   # her İHA'nın karıştırma haritası
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
                      relay_time=0.0, failures=0, reassign=0, task_dist=0.0)
        self.last_pdr = 1.0
        self.last_conn = 1.0
        self.finished_t = np.nan
        self.idle_since = np.nan

        # Yapay zekâ eğitim verisi: her "İHA hedefe yöneldi" denemesinin özellikleri ve sonucu
        self.attempts = []                       # (özellikler, sonuç 1/0, uzman kuralının rho'su)
        self.att_task = np.full(N, -1)
        self.att_feat = [None] * N

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
        if self.jammers:
            self.jrx = radio.jam_power_dbm(self.pos, self.jammers, c)
        self.gps_ok = self.jrx < c.gps_jam_dbm
        if self.k % c.comm_every == 0:
            self._communicate()
            self._decide()
            self._swarm_logic()
        self._navigate()
        self._update_estimates()
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
        if self.resilient:
            ttl[self._tasks_in_jam(j)] = self.cfg.claim_ttl_jam
        return ttl

    def _ttl_all(self):
        """Tüm İHA'lar için görev sahiplenme geçerlilik süreleri (N, T)."""
        if not self.resilient:
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
        Yapay zekâ: sinir ağı başarı olasılığını kestirir."""
        if self.ai is not None:
            return self.ai(self._ai_features(i))
        rho = np.ones(self.T)
        if self.resilient and self.cfg.ew_valuation:
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
        if self.resilient:
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

    def fail_drone(self, i=None):
        """İHA'yı arızalandırır (motor/batarya). i verilmezse rastgele dürüst bir İHA."""
        if i is None:
            cand = np.nonzero(self.alive & ~self.spoofer & (self.phase != LANDED))[0]
            if len(cand) <= 1:
                return
            i = int(self.rng.choice(cand))
        self.alive[i] = False
        self._clear_plan(i)
        self.relay_for[i], self.recover[i] = -1, False
        self.m["failures"] += 1

    # ----------------------------------------------------------- haberleşme
    def _communicate(self):
        c, N = self.cfg, self.N
        per, _ = radio.link_per(self.pos, self.pos, self.jrx, c)
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
        if self.resilient:
            self._coop_localize(heard)

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
        per_dn, _ = radio.link_per(self.gcs, self.pos, self.jrx, c, gain_db=c.gcs_gain_db, max_range=np.inf)
        dn = (self.rng.random(self.N) > per_dn[0]) & self.alive
        self.known_task[dn] |= (self.appear <= self.t)[None, :]

    def _gossip(self, heard):
        c, N, now = self.cfg, self.N, self.t
        # 1) Herkes kendi durumunu tablosuna yazar
        for i in np.nonzero(self.alive)[0]:
            self.st_t[i, i], self.st_pos[i, i] = now, self.est[i]
            self.st_task[i, i], self.st_phase[i, i], self.st_relay[i, i] = self.my_task[i], self.phase[i], self.relay_for[i]
            if self.spoofer[i]:
                # Saldırgan: tüm açık görevleri "ben tam oradayım" diye en yüksek teklifle sahiplenir
                open_ = ~self.known_done[i] & self.known_task[i]
                top = self.value[open_] if self.cbba else 0.0
                self.cl_bid[i, open_], self.cl_id[i, open_], self.cl_time[i, open_] = top, i, now
                continue
            t = self.my_task[i]
            if t >= 0 and not self.cbba:
                self.cl_bid[i, t], self.cl_id[i, t], self.cl_time[i, t] = self._bids(i)[t], i, now
            # Karıştırma algılama: alıcıdaki gürültü tabanı yükseldi ya da GPS kesildi
            if self.resilient and (not self.gps_ok[i] or self.jrx[i] + self.rng.normal(0, 2) > c.jam_detect_dbm):
                ix, iy = cell_idx(self.est[i, 0], self.est[i, 1])
                self.jam_grid[i, ix, iy] = True

        # 2) Mesajlar: herkes, duyduğu komşuların (gönderim anındaki) tablosunu birleştirir.
        # Her gönderen için tüm alıcılar birlikte işlenir (alıcı başına sıra, gönderen numarasıyla aynı).
        snap_b, snap_id, snap_t = self.cl_bid.copy(), self.cl_id.copy(), self.cl_time.copy()
        snap_done, snap_known, snap_est = self.known_done.copy(), self.known_task.copy(), self.est.copy()
        snap_grid = self.jam_grid.copy()
        sn_t, sn_pos, sn_task = self.st_t.copy(), self.st_pos.copy(), self.st_task.copy()
        sn_phase, sn_relay = self.st_phase.copy(), self.st_relay.copy()
        ttl_all = self._ttl_all()
        implausible = self._implausible(snap_b, snap_id, snap_t, snap_est) if self.resilient else None
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
            keep = ~self.spoofer[R]
            R, st_before = R[keep], st_before[keep]
            if len(R) == 0:
                continue
            if self.resilient:
                if implausible[k]:
                    # Makul olmayan teklif veren gönderene artık güvenme, onun tekliflerini sil
                    self.distrust[R, k] = True
                    bad = self.cl_id[R] == k
                    rows = np.broadcast_to(R[:, None], bad.shape)
                    self.cl_bid[rows[bad], np.nonzero(bad)[1]] = -np.inf
                    self.cl_id[rows[bad], np.nonzero(bad)[1]] = -1
                    self.cl_time[rows[bad], np.nonzero(bad)[1]] = -np.inf
                    continue
                self.jam_grid[R] |= snap_grid[k]
            self.known_done[R] |= snap_done[k]
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
        if self.resilient:
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
        gcs_jam = radio.jam_power_dbm(self.gcs, self.jammers, c) if self.jammers else np.array([-300.0])
        per_up, _ = radio.link_per(self.pos, self.gcs, gcs_jam, c, gain_db=c.gcs_gain_db, max_range=np.inf)
        per_dn, _ = radio.link_per(self.gcs, self.pos, self.jrx, c, gain_db=c.gcs_gain_db, max_range=np.inf)
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
            helpers = np.nonzero(heard[:, j] & self.gps_ok & ~self.distrust[j])[0]
            if len(helpers) >= 3:
                fix = self.pos[j] + self.rng.normal(0, 3.0, 3) * [1, 1, 0.3]
                self.est[j] += 0.5 * (fix - self.est[j])
                self.bias[j] = 0
                self.dr_t[j], self.sig0[j] = 0.0, 3.0

    # ----------------------------------------------------------- karar alma
    def _decide(self):
        for j in range(self.N):
            if not self.alive[j]:
                continue
            if self.phase[j] >= RETURN:
                if self.path[j] or self.bundle[j]:
                    self._clear_plan(j)
                continue
            if self.spoofer[j] or self.relay_for[j] >= 0:
                self._clear_plan(j)
                continue
            if self.resilient and self._gps_recovery(j):
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
                if free.any():
                    t = int(np.argmax(np.where(free, bids, -np.inf)))
                    self.path[j] = [t]
                    self._set_task(j)
                    self.cl_bid[j, t], self.cl_id[j, t], self.cl_time[j, t] = bids[t], j, self.t

    def _gps_recovery(self, j):
        """(Dirençli) GPS kurtarma: konumunu çok kaybeden İHA görevlerini bırakır, son GPS aldığı
        noktaya döner; GPS ya da komşu düzeltmesi gelince göreve döner. O nokta çok uzaksa ya da
        varınca da GPS yoksa (her yer karıştırılıyor) kurtarmayı bir süre denemez.
        Döndürür: İHA şu an kurtarmada mı."""
        now, c = self.t, self.cfg
        sig = self.sigma(j)
        back = float(np.linalg.norm(self.est[j, :2] - self.last_fix[j]))
        if self.recover[j]:
            if sig < 5.0:
                self.recover[j] = False
            elif back < 15.0:
                self.recover[j] = False
                self.recover_block[j] = now + 60.0
        elif (sig > c.recover_sigma and self.search[j] == 0 and now >= self.recover_block[j]
              and back < 300.0 and self.phase[j] == TASK):
            self.recover[j] = True
            self._close_attempt(j, False)        # konumunu kaybedip görevi bıraktı: başarısız deneme
            self._release_claim(j)
        return bool(self.recover[j])

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
        # 2) Teklifi geçilen ilk görevden sonrasını bırak (sonrakiler ona göre hesaplanmıştı)
        b = self.bundle[j]
        for n, t in enumerate(b):
            if self.cl_id[j, t] != j:
                for t2 in b[n + 1:]:
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
        cand = self.known_task[j] & ~self.known_done[j] & (self.cooldown[j] <= now)
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
        known = (self.st_t[i] > now - 10.0) & ~self.distrust[i]
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
        group[~alive] = -1

        # Sanal lider ilerlemesi (intikal/dönüş): düzen hatası büyüyünce yavaşlar ki geride kalanlar yetişsin
        for i in np.nonzero(alive & M_FORM[self.phase])[0]:
            v = c.transit_speed * float(np.clip(1.0 - (self.slot_err[i] - 6.0) / 20.0, 0.3, 1.0))
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
                    lead_v = c.transit_speed * float(np.clip(1.0 - (self.slot_err[i] - 6.0) / 20.0, 0.3, 1.0))
                    ff[i] = u * (lead_v if self.lead_s[i] < self.paths[self.phase[i]].length else 0.0)
                else:
                    target[i] = slots_of(g, 0.0)[k]
                formation[i] = True
                continue
            t = self.my_task[i]
            if self.recover[i]:
                target[i] = self.last_fix[i]     # GPS'i geri almak için son GPS alınan noktaya
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

        # Dirençli: hedefim karıştırma bölgesinde değilse oradan transit geçme
        if self.resilient:
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
        z_goal = np.maximum.reduce([here, ahead, at_tgt]) + c.agl + layer
        ground_true = self.terrain.height(self.pos[:, 0], self.pos[:, 1])
        agl_now = self.pos[:, 2] - ground_true                                   # telemetre (radar altimetre)
        # Emniyet: konum kestirimi kaysa bile (GPS yok) gerçek yere olan yükseklik korunur
        z_goal = np.maximum(z_goal, ground_true + 0.75 * c.agl)
        landing = self.phase == LAND
        near_pad = dist[:, 0] < 4.0
        z_goal = np.where(landing, np.where(near_pad, at_tgt + 0.3, self.pos[:, 2]), z_goal)
        vz = np.clip(0.8 * (z_goal - self.pos[:, 2]), -c.max_climb, c.max_climb)
        vz = np.where(landing, np.maximum(vz, -2.5), vz)
        # Yere yakınken (kalkış) önce yüksel, sonra yatay hareket et
        low = (agl_now < 8.0) & M_EARLY[self.phase]
        desired[low, :2] *= 0.15
        desired[:, 2] = vz

        acc = (desired - self.vel) / 1.0
        an = np.linalg.norm(acc, axis=1, keepdims=True)
        acc *= np.minimum(1.0, c.max_accel / np.maximum(an, 1e-6))
        acc += self.rng.normal(0, 0.3, acc.shape) * (agl_now[:, None] > 1.0)   # rüzgâr türbülansı
        acc[~alive] = 0.0
        self.vel += acc * dt
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

    def _update_estimates(self):
        """Basit tümleşik seyrüsefer: IMU ile tahmin, GPS varsa düzelt."""
        c = self.cfg
        lost = ~self.gps_ok
        n_lost = int(lost.sum())
        if n_lost:
            self.bias[lost] += self.rng.normal(0, c.imu_drift * np.sqrt(c.dt), (n_lost, 3)) * [1, 1, 0.2]
        self.est += (self.vel + self.bias) * c.dt
        ok = self.gps_ok
        gps = self.pos[ok] + self.rng.normal(0, 1.5, (int(ok.sum()), 3)) * [1, 1, 0.5]
        self.est[ok] += 0.3 * (gps - self.est[ok])
        self.last_fix[ok] = self.est[ok, :2]
        self.bias[ok] = 0
        self.dr_t = np.where(ok, 0.0, self.dr_t + c.dt)
        self.sig0[ok] = 1.5

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
                self.known_done[i, t] = True
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
            elif np.linalg.norm(self.est[i, :2] - self.tasks[t, :2]) < 0.4 * c.task_radius:
                # "Vardım" sanıyor ama hedef kamerada yok: konum kestirimi yanlış
                sig = self.sigma(i)
                if self.resilient and sig > c.task_radius / 2:
                    # Dirençli: belirsizlik çemberini (2.5 sigma) kapsayan spiral arama
                    self.search[i] = 1.0
                    self.search_r[i] = min(2.5 * sig + 10.0, 100.0)
                else:
                    self._give_up(i, t)

    def _give_up(self, i, t):
        """İHA görevi bitti sanar ama aslında bitmedi -> yanlış tamamlanma."""
        if not self.done[t]:
            self.m["false_done"] += 1
        if self.att_task[i] == t:
            self._close_attempt(i, False)
        self.known_done[i, t] = True
        self._drop(i, t)

    # ----------------------------------------------------------- ölçümler
    def _metrics(self):
        c = self.cfg
        honest = ~self.spoofer & self.alive
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
            mode = (4 if not self.alive[i] else 2 if self.spoofer[i] else 3 if self.relay_for[i] >= 0
                    else 1 if self.search[i] > 0 else 5 if self.recover[i] else 0)
            plan = [int(t) for t in self.path[i]] if self.alive[i] and not self.spoofer[i] else []
            drones.append({
                "id": i, "p": r(self.pos[i]), "e": r(self.est[i]), "v": r(self.vel[i]),
                "jam": round(float(np.clip((self.jrx[i] + 100.0) / 30.0, 0, 1)), 3),
                "gps": int(self.gps_ok[i]), "task": int(self.my_task[i]), "mode": mode,
                "sigma": round(self.sigma(i), 1), "phase": int(self.phase[i]),
                "relay": int(self.relay_for[i]), "plan": plan,
            })
        links = []
        for i in range(self.N):
            for j in range(i + 1, self.N):
                q = 0.5 * (self.link_q[i, j] + self.link_q[j, i])
                if q > 0.05:
                    links += [i, j, round(float(q), 3)]
        ctr = cell_centers(self.jam_grid.any(0)) if self.resilient else np.zeros((0, 2))
        jam_cells = [round(float(v), 1) for v in ctr.ravel()]
        live = self.phase[self.alive]
        dominant = int(np.bincount(live, minlength=7).argmax()) if len(live) else LANDED
        fm = self.alive & M_FORM[self.phase]
        sched = np.isfinite(self.appear) & (self.appear <= self.t)
        return {
            "t": round(self.t, 2),
            "strategy": c.strategy,
            "planner": c.planner,
            "phase": PHASE_NAMES[dominant],
            "formation": self.form_kind,
            "drones": drones,
            "links": links,
            "tasks": tasks,
            "jammers": [{"p": r(p), "pw": pw, "r": round(radio.jam_radius(pw, c), 1)} for p, pw in self.jammers],
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
            },
        }
