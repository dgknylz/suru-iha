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
"""
import numpy as np
from scipy.optimize import linear_sum_assignment

from . import radio
from .config import SimConfig
from .swarm import FORMATIONS, Path, formation_offsets, largest_component, place, reynolds
from .terrain import Terrain

CELL = 50.0  # karıştırma haritası hücre boyu (m)

# Uçuş evreleri
TAKEOFF, TRANSIT, TASK, REGROUP, RETURN, LAND, LANDED = range(7)
PHASE_NAMES = ("kalkis", "intikal", "gorev", "toplanma", "donus", "inis", "indi")
AIRBORNE = (TAKEOFF, TRANSIT, TASK, REGROUP, RETURN, LAND)

_TERRAIN_CACHE = {}


def cell_of(p):
    return (int(np.floor(p[0] / CELL)), int(np.floor(p[1] / CELL)))


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

        # Görevler ve saldırganlar aynı tohumla önce çekilir: aynı seed'de
        # üç strateji de AYNI görev haritasıyla karşılaşır (eşleştirilmiş deney).
        ac, h = np.asarray(c.area_center, float), c.area_half
        txy = np.c_[rng.uniform(ac[0] - h + 30, ac[0] + h - 30, T), rng.uniform(ac[1] - h + 30, ac[1] + h - 30, T)]
        self.task_ground = self.terrain.height(txy[:, 0], txy[:, 1])
        self.tasks = np.c_[txy, self.task_ground + c.agl]
        self.task_cells = [cell_of(p) for p in self.tasks]
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
            self.fail_at[who] = rng.uniform(c.takeoff_time + 50, c.takeoff_time + 100, len(who))   # görev evresinde

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
        self.known_done = np.zeros((N, T), bool)
        self.cl_bid = np.full((N, T), -np.inf)   # bildiği en iyi teklif
        self.cl_id = np.full((N, T), -1)         # o teklifi veren İHA
        self.cl_time = np.full((N, T), -np.inf)  # teklifin zaman damgası
        self.my_task = np.full(N, -1)
        self.search = np.zeros(N)                # spiral arama açısı (0 = arama yok)
        self.search_r = np.zeros(N)              # aramanın biteceği yarıçap (m)
        self.distrust = np.zeros((N, N), bool)   # distrust[j, i]: j, i'ye güvenmiyor
        self.jam_cells = [set() for _ in range(N)]
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
        self.gcs_pos = np.full((N, 3), np.nan)
        self.gcs_seen = np.full(N, -np.inf)   # istasyon İHA'yı en son ne zaman duydu
        self.last_gcs = np.zeros(N)           # İHA istasyonu en son ne zaman duydu
        self.gcs_up = np.zeros(N, bool)
        self.gcs_return_t = np.inf            # istasyonun "eve dön" emri verdiği an
        self.next_spoof = np.full(N, c.spoof_period)

        self.m = dict(redundant=0, false_done=0, retries=0, near_miss=0, pdr_sum=0.0, pdr_n=0,
                      locerr_sum=0.0, locerr_n=0, lam2_sum=0.0, lam2_n=0, msgs=0,
                      conn_sum=0.0, conn_n=0, form_sum=0.0, form_n=0, min_agl=np.inf, low_agl=0,
                      relay_time=0.0, failures=0)
        self.last_pdr = 1.0
        self.last_conn = 1.0
        self.finished_t = np.nan
        self.idle_since = np.nan

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
        self._metrics()
        if np.isnan(self.finished_t) and self.done.all():
            self.finished_t = self.t
        # Sürü "iş bitti" dedi mi? Tüm canlı dürüst İHA'lar boşta kaldıysa görev biter.
        busy = (self.my_task >= 0) | (self.phase <= TRANSIT)
        idle = not (busy & ~self.spoofer & self.alive).any()
        if not idle:
            self.idle_since = np.nan
        elif np.isnan(self.idle_since):
            self.idle_since = self.t

    def finished(self):
        """Görev bitti mi? (deneyler burada durur)"""
        c = self.cfg
        stalled = not np.isnan(self.idle_since) and self.t - self.idle_since > c.idle_stop
        return self.done.all() or self.t >= c.max_time or stalled

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
        cells = self.jam_cells[j]
        return np.array([tc in cells for tc in self.task_cells]) if cells else np.zeros(self.T, bool)

    def _ttl(self, j):
        ttl = np.full(self.T, self.cfg.claim_ttl)
        if self.resilient:
            ttl[self._tasks_in_jam(j)] = self.cfg.claim_ttl_jam
        return ttl

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
        self.my_task[i], self.search[i] = -1, 0

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
        self.my_task[i], self.relay_for[i], self.search[i] = -1, -1, 0
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

        if self.central:
            self._gcs_link()
        else:
            self._gossip(heard)
        if self.resilient:
            self._coop_localize(heard)

    def _gossip(self, heard):
        c, N, now = self.cfg, self.N, self.t
        # 1) Herkes kendi durumunu tablosuna yazar
        for i in np.nonzero(self.alive)[0]:
            self.st_t[i, i], self.st_pos[i, i] = now, self.est[i]
            self.st_task[i, i], self.st_phase[i, i], self.st_relay[i, i] = self.my_task[i], self.phase[i], self.relay_for[i]
            if self.spoofer[i]:
                # Saldırgan: tüm açık görevleri "ben buradayım" (teklif 0) diye sahiplenir
                open_ = ~self.known_done[i]
                self.cl_bid[i, open_], self.cl_id[i, open_], self.cl_time[i, open_] = 0.0, i, now
                continue
            t = self.my_task[i]
            if t >= 0:
                self.cl_bid[i, t], self.cl_id[i, t], self.cl_time[i, t] = self._bids(i)[t], i, now
            # Karıştırma algılama: alıcıdaki gürültü tabanı yükseldi ya da GPS kesildi
            if self.resilient and (not self.gps_ok[i] or self.jrx[i] + self.rng.normal(0, 2) > c.jam_detect_dbm):
                self.jam_cells[i].add(cell_of(self.est[i]))

        # 2) Mesajlar: herkes, duyduğu komşuların (gönderim anındaki) tablosunu birleştirir
        snap_b, snap_id, snap_t = self.cl_bid.copy(), self.cl_id.copy(), self.cl_time.copy()
        snap_done, snap_est = self.known_done.copy(), self.est.copy()
        snap_cells = [set(s) for s in self.jam_cells]
        sn_t, sn_pos, sn_task = self.st_t.copy(), self.st_pos.copy(), self.st_task.copy()
        sn_phase, sn_relay = self.st_phase.copy(), self.st_relay.copy()
        for j in np.nonzero(self.alive)[0]:
            ttl = self._ttl(j)
            for i in np.nonzero(heard[:, j])[0]:
                if self.distrust[j, i]:
                    continue
                # Sürü durum tablosu: daha yeni bilgiyi al
                newer = sn_t[i] > self.st_t[j]
                if newer.any():
                    self.st_t[j, newer], self.st_pos[j, newer] = sn_t[i, newer], sn_pos[i, newer]
                    self.st_task[j, newer], self.st_phase[j, newer] = sn_task[i, newer], sn_phase[i, newer]
                    self.st_relay[j, newer] = sn_relay[i, newer]
                if self.spoofer[j]:
                    continue
                if self.resilient:
                    # Makullük kontrolü: i'nin kendi adına verdiği teklif, bildirdiği
                    # konumdan göreve olan uzaklıkla tutarlı mı?
                    own = (snap_id[i] == i) & (snap_t[i] >= now)   # i'nin bu turda verdiği teklifler
                    if own.any():
                        plausible = -np.linalg.norm(self.tasks[own, :2] - snap_est[i, :2], axis=1) + 30.0
                        if (snap_b[i, own] > plausible).any():
                            self.distrust[j, i] = True
                            bad = self.cl_id[j] == i
                            self.cl_bid[j, bad], self.cl_id[j, bad], self.cl_time[j, bad] = -np.inf, -1, -np.inf
                            continue
                    self.jam_cells[j] |= snap_cells[i]
                self.known_done[j] |= snap_done[i]
                fresh = snap_t[i] > now - ttl
                better = fresh & ((snap_b[i] > self.cl_bid[j]) |
                                  ((snap_id[i] == self.cl_id[j]) & (snap_t[i] > self.cl_time[j])))
                self.cl_bid[j, better] = snap_b[i, better]
                self.cl_id[j, better] = snap_id[i, better]
                self.cl_time[j, better] = snap_t[i, better]

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

        # Uzun süredir duyulmayan İHA'nın görevi serbest kalır
        self.gcs_assign[now - self.gcs_seen > c.gcs_release] = -1
        # Açgözlü atama: boştaki her İHA'ya en yakın sahipsiz görev
        for i in np.nonzero(dn & ~np.isnan(self.gcs_pos[:, 0]))[0]:
            a = self.gcs_assign[i]
            if a >= 0 and not self.gcs_done[a]:
                continue
            taken = set(self.gcs_assign[self.gcs_assign >= 0])
            free = [t for t in range(self.T) if not self.gcs_done[t] and t not in taken]
            if free:
                d = np.linalg.norm(self.tasks[free, :2] - self.gcs_pos[i, :2], axis=1)
                self.gcs_assign[i] = free[int(np.argmin(d))]
            else:
                self.gcs_assign[i] = -1
        # Hiç açık görev yoksa istasyon "eve dön" emri verir
        if np.isinf(self.gcs_return_t) and self.gcs_done.all():
            self.gcs_return_t = now
        # Aşağı bağlantı: görev emri ve düzen ilerlemesi İHA'ya ulaşır
        for i in np.nonzero(dn)[0]:
            self.last_gcs[i] = now
            self.known_done[i] |= self.gcs_done
            if self.phase[i] == TRANSIT:
                self.lead_s[i] = max(self.lead_s[i], c.transit_speed * (now - c.takeoff_time))
            if not self.spoofer[i]:
                if self.my_task[i] != self.gcs_assign[i]:
                    self.search[i] = 0
                self.my_task[i] = self.gcs_assign[i]

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
            if not self.alive[j] or self.phase[j] >= RETURN:
                continue
            if self.spoofer[j] or self.relay_for[j] >= 0:
                self.my_task[j] = -1
                continue
            t = self.my_task[j]
            if t >= 0 and self.known_done[j, t]:
                self.my_task[j], self.search[j] = -1, 0
            if self.central:
                continue
            ttl = self._ttl(j)
            valid = (self.cl_time[j] > self.t - ttl) & (self.cl_id[j] >= 0)
            bids = self._bids(j)
            t = self.my_task[j]
            # Görevimi benden iyi teklif veren biri aldıysa bırakırım
            if t >= 0 and valid[t] and self.cl_id[j, t] != j and self.cl_bid[j, t] > bids[t]:
                self.my_task[j], self.search[j] = -1, 0
            if self.my_task[j] < 0:
                free = ~self.known_done[j] & (~valid | (self.cl_id[j] == j) | (self.cl_bid[j] < bids))
                free &= self.cooldown[j] <= self.t
                if free.any():
                    t = int(np.argmax(np.where(free, bids, -np.inf)))
                    self.my_task[j] = t
                    self.cl_bid[j, t], self.cl_id[j, t], self.cl_time[j, t] = bids[t], j, self.t

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
                idle = self.my_task[i] < 0 and self.relay_for[i] < 0
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
        for i in np.nonzero(self.alive & np.isin(self.phase, (TRANSIT, RETURN)))[0]:
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
            if self.jam_cells[i]:
                for k in np.nonzero(lost)[0]:
                    if cell_of(self.st_pos[i, k]) in self.jam_cells[i]:
                        lost[k] = False
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
        idle = (self.my_task < 0) & (self.relay_for < 0) & ~self.spoofer
        lost_link = self.central & (self.t - self.last_gcs > c.gcs_timeout)
        group = np.full(N, -1)
        group[np.isin(self.phase, (TAKEOFF, LAND, LANDED))] = 0
        group[(self.phase == REGROUP) | ((self.phase == TASK) & idle & ~lost_link)] = 1
        group[self.phase == TRANSIT] = 2
        group[self.phase == RETURN] = 3
        group[~alive] = -1

        # Sanal lider ilerlemesi (intikal/dönüş): düzen hatası büyüyünce yavaşlar ki geride kalanlar yetişsin
        for i in np.nonzero(alive & np.isin(self.phase, (TRANSIT, RETURN)))[0]:
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
            if self.relay_for[i] >= 0:
                target[i] = self.relay_pos[i]
            elif self.spoofer[i]:
                a = 0.05 * self.t + i
                target[i] = self.rally + [80 * np.cos(a), 80 * np.sin(a)]
            elif t >= 0:
                target[i] = self.tasks[t, :2]
                if self.search[i] > 0:   # Arşimet spirali: r = b * açı, tur aralığı ~10 m
                    r = 1.6 * self.search[i]
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
                cells = self.jam_cells[i]
                t = self.my_task[i]
                if not cells or self.spoofer[i] or (t >= 0 and self.task_cells[t] in cells):
                    continue
                ctr = (np.array(list(cells), float) + 0.5) * CELL
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
        low = (agl_now < 8.0) & np.isin(self.phase, (TAKEOFF, TRANSIT))
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
        self.bias[ok] = 0
        self.dr_t = np.where(ok, 0.0, self.dr_t + c.dt)
        self.sig0[ok] = 1.5

    def _check_arrivals(self):
        c = self.cfg
        for i in range(self.N):
            t = self.my_task[i]
            if t < 0 or self.spoofer[i] or not self.alive[i] or self.phase[i] not in (TRANSIT, TASK, REGROUP):
                continue
            if np.linalg.norm(self.pos[i, :2] - self.tasks[t, :2]) < c.task_radius:
                # Kamera hedefi gerçekten gördü
                if self.done[t]:
                    self.m["redundant"] += 1
                else:
                    self.done[t], self.done_time[t] = True, self.t
                self.known_done[i, t] = True
                self.my_task[i], self.search[i] = -1, 0
                continue
            if self.phase[i] != TASK:
                continue
            if self.search[i] > 0:
                self.search[i] += 8.0 / max(1.6 * self.search[i], 5.0) * c.dt
                if 1.6 * self.search[i] > self.search_r[i]:
                    # Dirençli İHA görmediği hedefe "bitti" demez: bırakır, GPS'i geri
                    # kazanınca (kendisi ya da bir arkadaşı) yeniden dener.
                    self.m["retries"] += 1
                    self.cooldown[i, t] = self.t + self.cfg.retry_cooldown
                    self.cl_bid[i, t], self.cl_id[i, t], self.cl_time[i, t] = -np.inf, -1, -np.inf
                    self.my_task[i], self.search[i] = -1, 0
            elif np.linalg.norm(self.est[i, :2] - self.tasks[t, :2]) < 0.4 * c.task_radius:
                # "Vardım" sanıyor ama hedef kamerada yok: konum kestirimi yanlış
                sig = self.sigma(i)
                if self.resilient and sig > c.task_radius / 2:
                    # Dirençli: belirsizlik çemberini (2.5 sigma) kapsayan spiral arama
                    self.search[i] = 1.0
                    self.search_r[i] = min(2.5 * sig + 10.0, 120.0)
                else:
                    self._give_up(i, t)

    def _give_up(self, i, t):
        """İHA görevi bitti sanar ama aslında bitmedi -> yanlış tamamlanma."""
        if not self.done[t]:
            self.m["false_done"] += 1
        self.known_done[i, t] = True
        self.my_task[i], self.search[i] = -1, 0

    # ----------------------------------------------------------- ölçümler
    def _metrics(self):
        c = self.cfg
        honest = ~self.spoofer & self.alive
        self.m["locerr_sum"] += float(np.linalg.norm(self.est[honest] - self.pos[honest], axis=1).mean())
        self.m["locerr_n"] += 1
        # Arazi açıklığı: düzen ve görev uçuşu sırasında yerden yükseklik
        cruise = self.alive & np.isin(self.phase, (TRANSIT, TASK, REGROUP, RETURN))
        if cruise.any():
            agl = self.pos[cruise, 2] - self.terrain.height(self.pos[cruise, 0], self.pos[cruise, 1])
            self.m["min_agl"] = min(self.m["min_agl"], float(agl.min()))
            self.m["low_agl"] += int((agl < 10.0).sum())
        # Düzen hatası: intikal ve dönüşte yuvaya uzaklık
        fm = self.alive & np.isin(self.phase, (TRANSIT, RETURN))
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
            ti = np.nonzero(honest & np.isin(self.phase, (TASK, REGROUP)))[0]
            if len(ti) >= 2:
                self.last_conn = largest_component(A[np.ix_(ti, ti)])
                self.m["conn_sum"] += self.last_conn
                self.m["conn_n"] += 1

    def summary(self):
        m = self.m
        return dict(
            completion=float(self.done.mean()),
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

    # ----------------------------------------------------------- Unity karesi
    def frame(self):
        """Unity'ye gönderilen anlık durum. Koordinatlar ENU (x doğu, y kuzey, z yukarı)."""
        c = self.cfg
        r = lambda v: [round(float(x), 2) for x in v]
        claimed = set(int(t) for t in self.my_task if t >= 0)
        believed = self.known_done[~self.spoofer].any(0) | self.gcs_done
        tasks = []
        for t in range(self.T):
            s = 2 if self.done[t] else 3 if believed[t] else 1 if t in claimed else 0
            tasks.append({"p": r(self.tasks[t]), "s": s})
        drones = []
        for i in range(self.N):
            mode = (4 if not self.alive[i] else 2 if self.spoofer[i] else 3 if self.relay_for[i] >= 0
                    else 1 if self.search[i] > 0 else 0)
            drones.append({
                "id": i, "p": r(self.pos[i]), "e": r(self.est[i]), "v": r(self.vel[i]),
                "jam": round(float(np.clip((self.jrx[i] + 100.0) / 30.0, 0, 1)), 3),
                "gps": int(self.gps_ok[i]), "task": int(self.my_task[i]), "mode": mode,
                "sigma": round(self.sigma(i), 1), "phase": int(self.phase[i]),
                "relay": int(self.relay_for[i]),
            })
        links = []
        for i in range(self.N):
            for j in range(i + 1, self.N):
                q = 0.5 * (self.link_q[i, j] + self.link_q[j, i])
                if q > 0.05:
                    links += [i, j, round(float(q), 3)]
        cells = set().union(*self.jam_cells) if self.resilient else set()
        jam_cells = [v for cx, cy in cells for v in ((cx + 0.5) * CELL, (cy + 0.5) * CELL)]
        live = self.phase[self.alive]
        dominant = int(np.bincount(live, minlength=7).argmax()) if len(live) else LANDED
        fm = self.alive & np.isin(self.phase, (TRANSIT, RETURN))
        return {
            "t": round(self.t, 2),
            "strategy": c.strategy,
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
                "done": int(self.done.sum()), "total": self.T,
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
