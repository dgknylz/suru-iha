"""Sürü dünyası: İHA'lar, görevler, karıştırıcılar ve karar alma.

Koordinatlar metre cinsinden: x = doğu, y = kuzey, z = yukarı. Yer istasyonu (0, 0)'da.

Üç strateji karşılaştırılır:
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
"""
import numpy as np

from . import radio
from .config import SimConfig

CELL = 50.0  # karıştırma haritası hücre boyu (m)


def cell_of(p):
    return (int(np.floor(p[0] / CELL)), int(np.floor(p[1] / CELL)))


class World:
    def __init__(self, cfg: SimConfig):
        self.cfg = c = cfg
        self.rng = rng = np.random.default_rng(c.seed)
        self.N, self.T = N, T = c.n_drones, c.n_tasks
        self.t, self.k = 0.0, 0
        self.resilient = c.strategy == "resilient"
        self.central = c.strategy == "centralized"
        half = c.world_size / 2

        # Görevler ve saldırganlar aynı tohumla önce çekilir: aynı seed'de
        # üç strateji de AYNI görev haritasıyla karşılaşır (eşleştirilmiş deney).
        self.tasks = np.c_[rng.uniform(-half + 40, half - 40, (T, 2)), np.full(T, c.cruise_alt)]
        self.task_cells = [cell_of(p) for p in self.tasks]
        self.spoofer = np.zeros(N, bool)
        n_sp = int(round(c.spoof_fraction * N))
        if n_sp:
            self.spoofer[rng.choice(N, n_sp, replace=False)] = True

        self.gcs = np.array([0.0, 0.0, 10.0])
        self.home = np.array([0.0, 0.0, c.cruise_alt])
        ang = np.linspace(0, 2 * np.pi, N, endpoint=False)
        self.pos = np.c_[15 * np.cos(ang), 15 * np.sin(ang), np.full(N, 0.5)]
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

        # Merkezi mimari
        self.gcs_done = np.zeros(T, bool)
        self.gcs_assign = np.full(N, -1)
        self.gcs_pos = np.full((N, 3), np.nan)
        self.gcs_seen = np.full(N, -np.inf)   # istasyon İHA'yı en son ne zaman duydu
        self.last_gcs = np.zeros(N)           # İHA istasyonu en son ne zaman duydu
        self.gcs_up = np.zeros(N, bool)
        self.next_spoof = np.full(N, c.spoof_period)

        self.m = dict(redundant=0, false_done=0, retries=0, near_miss=0, pdr_sum=0.0, pdr_n=0,
                      locerr_sum=0.0, locerr_n=0, lam2_sum=0.0, lam2_n=0, msgs=0)
        self.last_pdr = 1.0
        self.finished_t = np.nan
        self.idle_since = np.nan
        self.cooldown = np.zeros((N, T))         # (dirençli) i, t'yi bu andan önce tekrar deneyemez

    # ------------------------------------------------------------------ döngü
    def step(self):
        c = self.cfg
        self.t += c.dt
        self.k += 1
        if self.jammers:
            self.jrx = radio.jam_power_dbm(self.pos, self.jammers, c)
        self.gps_ok = self.jrx < c.gps_jam_dbm
        if self.k % c.comm_every == 0:
            self._communicate()
            self._decide()
        self._navigate()
        self._update_estimates()
        self._check_arrivals()
        self._metrics()
        if np.isnan(self.finished_t) and self.done.all():
            self.finished_t = self.t
        # Sürü "iş bitti" dedi mi? Tüm dürüst İHA'lar boşta kaldıysa görev biter.
        idle = (self.my_task[~self.spoofer] < 0).all()
        if not idle:
            self.idle_since = np.nan
        elif np.isnan(self.idle_since):
            self.idle_since = self.t

    def finished(self):
        c = self.cfg
        stalled = not np.isnan(self.idle_since) and self.t - self.idle_since > c.idle_stop
        return self.done.all() or self.t >= c.max_time or stalled

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

    # ----------------------------------------------------------- haberleşme
    def _communicate(self):
        c, N = self.cfg, self.N
        per, _ = radio.link_per(self.pos, self.pos, self.jrx, c)
        np.fill_diagonal(per, 1.0)
        self.link_q = 1.0 - per
        heard = self.rng.random((N, N)) > per          # heard[i, j]: j, i'nin mesajını aldı
        in_range = radio.dist_matrix(self.pos) < c.comm_range
        np.fill_diagonal(in_range, False)
        if in_range.any():
            self.last_pdr = float(heard[in_range].mean())
            self.m["pdr_sum"] += self.last_pdr
            self.m["pdr_n"] += 1
        self.m["msgs"] += N

        if self.central:
            self._gcs_link()
        else:
            self._gossip(heard)
        if self.resilient:
            self._coop_localize(heard)

    def _gossip(self, heard):
        c, N, now = self.cfg, self.N, self.t
        # 1) Herkes kendi durumunu tablosuna yazar
        for i in range(N):
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
        for j in range(N):
            if self.spoofer[j]:
                continue
            ttl = self._ttl(j)
            for i in np.nonzero(heard[:, j])[0]:
                if self.distrust[j, i]:
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
        up = self.rng.random(N) > per_up[:, 0]
        dn = self.rng.random(N) > per_dn[0]
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
        # Aşağı bağlantı: görev emri İHA'ya ulaşır
        for i in np.nonzero(dn)[0]:
            self.last_gcs[i] = now
            self.known_done[i] |= self.gcs_done
            if not self.spoofer[i]:
                if self.my_task[i] != self.gcs_assign[i]:
                    self.search[i] = 0
                self.my_task[i] = self.gcs_assign[i]

    def _coop_localize(self, heard):
        """GPS'i olmayan İHA, GPS'i sağlam en az 3 komşusunu duyuyorsa onlara
        olan menzil ölçümleriyle (UWB benzeri) konumunu düzeltir."""
        for j in np.nonzero(~self.gps_ok)[0]:
            helpers = np.nonzero(heard[:, j] & self.gps_ok & ~self.distrust[j])[0]
            if len(helpers) >= 3:
                fix = self.pos[j] + self.rng.normal(0, 3.0, 3) * [1, 1, 0.3]
                self.est[j] += 0.5 * (fix - self.est[j])
                self.bias[j] = 0
                self.dr_t[j], self.sig0[j] = 0.0, 3.0

    # ----------------------------------------------------------- karar alma
    def _decide(self):
        for j in range(self.N):
            if self.spoofer[j]:
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

    # ----------------------------------------------------------- hareket
    def _navigate(self):
        c, N = self.cfg, self.N
        target = np.tile(self.home, (N, 1))
        for i in range(N):
            t = self.my_task[i]
            if self.spoofer[i]:
                a = 0.05 * self.t + i
                target[i] = self.home + [80 * np.cos(a), 80 * np.sin(a), 10]
            elif t >= 0:
                target[i] = self.tasks[t]
                if self.search[i] > 0:   # Arşimet spirali: r = b * açı, tur aralığı ~10 m
                    r = 1.6 * self.search[i]
                    target[i] = self.tasks[t] + [r * np.cos(self.search[i]), r * np.sin(self.search[i]), 0]

        to = target - self.est
        dist = np.linalg.norm(to, axis=1, keepdims=True)
        speed = np.minimum(c.max_speed, 0.6 * dist)
        desired = to / np.maximum(dist, 1e-6) * speed

        # Ayrışma: çok yaklaşan İHA'lar birbirini iter (gerçek konum = yakın mesafe sensörü)
        D = radio.dist_matrix(self.pos)
        np.fill_diagonal(D, np.inf)
        close = D < c.sep_dist
        self.m["near_miss"] += int(np.triu(D < 2.0).sum())
        for i, j in zip(*np.nonzero(close)):
            away = (self.pos[i] - self.pos[j]) / max(D[i, j], 0.1)
            desired[i] += away * (c.sep_dist - D[i, j]) / c.sep_dist * c.max_speed

        # Dirençli: hedefim karıştırma bölgesinde değilse oradan transit geçme
        if self.resilient:
            for i in range(N):
                cells = self.jam_cells[i]
                t = self.my_task[i]
                if not cells or self.spoofer[i] or (t >= 0 and self.task_cells[t] in cells):
                    continue
                ctr = (np.array(list(cells), float) + 0.5) * CELL
                v = self.est[i, :2] - ctr
                d = np.linalg.norm(v, axis=1, keepdims=True)
                w = np.clip((90.0 - d) / 90.0, 0, None)
                desired[i, :2] += (v / np.maximum(d, 1.0) * w * 8.0).sum(0)

        acc = (desired - self.vel) / 1.0
        an = np.linalg.norm(acc, axis=1, keepdims=True)
        acc *= np.minimum(1.0, c.max_accel / np.maximum(an, 1e-6))
        acc += self.rng.normal(0, 0.3, acc.shape)       # rüzgâr türbülansı
        self.vel += acc * c.dt
        sp = np.linalg.norm(self.vel, axis=1, keepdims=True)
        self.vel *= np.minimum(1.0, c.max_speed / np.maximum(sp, 1e-6))
        self.pos += self.vel * c.dt
        self.pos[:, 2] = np.maximum(self.pos[:, 2], 0.5)

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
            if t < 0 or self.spoofer[i]:
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
        honest = ~self.spoofer
        self.m["locerr_sum"] += float(np.linalg.norm(self.est[honest] - self.pos[honest], axis=1).mean())
        self.m["locerr_n"] += 1
        if self.k % self.cfg.comm_every == 0:
            A = ((self.link_q > 0.5) & (self.link_q.T > 0.5)).astype(float)
            L = np.diag(A.sum(1)) - A
            self.m["lam2_sum"] += float(np.sort(np.linalg.eigvalsh(L))[1])
            self.m["lam2_n"] += 1

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
            sim_time=self.t,
        )

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
            mode = 2 if self.spoofer[i] else 1 if self.search[i] > 0 else 0
            drones.append({
                "id": i, "p": r(self.pos[i]), "e": r(self.est[i]), "v": r(self.vel[i]),
                "jam": round(float(np.clip((self.jrx[i] + 100.0) / 30.0, 0, 1)), 3),
                "gps": int(self.gps_ok[i]), "task": int(self.my_task[i]), "mode": mode,
                "sigma": round(self.sigma(i), 1),
            })
        links = []
        for i in range(self.N):
            for j in range(i + 1, self.N):
                q = 0.5 * (self.link_q[i, j] + self.link_q[j, i])
                if q > 0.05:
                    links += [i, j, round(float(q), 3)]
        cells = set().union(*self.jam_cells) if self.resilient else set()
        jam_cells = [v for cx, cy in cells for v in ((cx + 0.5) * CELL, (cy + 0.5) * CELL)]
        return {
            "t": round(self.t, 2),
            "strategy": c.strategy,
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
                "locErr": round(float(np.linalg.norm(self.est - self.pos, axis=1).mean()), 2),
                "gpsLost": int((~self.gps_ok).sum()),
            },
        }
