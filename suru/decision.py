"""Otonom karar alma: görev paylaşım algoritmaları.

Ödül: her görevin bir değeri (önceliği) v vardır ve beklendikçe azalır:
    ödül = v * lambda^(varış - görünme) * rho
rho, İHA'nın o görevi başarma olasılığı/uygunluğu (kurallarla ya da yapay zekâyla kestirilir).
Böylece önemli ve yeni beliren hedeflere hızlı gidilir.

CBBA (Consensus-Based Bundle Algorithm, Choi, Brunet & How 2009):
  1) Paket kurma: her İHA, sırayla yapacağı görevlerden bir "paket" kurar. Her adımda
     rotasına en çok değer katan görevi (marjinal kazanç) en iyi sıraya ekler.
  2) Uzlaşma: komşular kazanan listelerini (kim, hangi teklifle) değiş tokuş eder.
     Choi 2009 Tablo 1'deki kurallar, zaman damgalarına bakıp hangi bilginin daha yeni
     olduğuna karar verir. Teklifi geçilen İHA o görevi ve paketinde ondan sonra gelenleri bırakır.
  Lider ya da merkez yoktur; ağ bölünse bile her parça kendi içinde çakışmasız plan üretir.
  Yakınsama için teklifler "bükülür" (bid warping, Johnson ve ark. 2012): pakete eklenen her yeni
  teklif bir öncekinden büyük olamaz (azalan marjinal kazanç koşulu).

SGA (Sequential Greedy Assignment): CBBA'nın merkezi karşılığı. Yer istasyonu tüm
  (İHA, görev) çiftleri içinden en büyük marjinal kazancı vereni sırayla atar.
"""
import os

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
AI_WEIGHTS = os.path.join(DATA, "ai_politika.npz")


# --------------------------------------------------------------- rota puanı
def path_score(p0, t0, X, V, A, R, lnlam, speed):
    """Rotanın toplam ödülü. p0: başlangıç noktası, t0: başlangıç anı, X: sıralı görev noktaları."""
    if len(X) == 0:
        return 0.0
    pts = np.vstack([p0[None, :], X])
    tau = t0 + np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1)) / speed
    return float((V * np.exp(lnlam * np.maximum(tau - A, 0.0)) * R).sum())


def best_insertion(p0, t0, PX, PV, PA, PR, CX, CV, CA, CR, lnlam, speed):
    """Her aday görev için: rotanın en iyi yerine eklenince toplam ödül ne kadar artar?

    Aday görev araya girerse sonraki görevler gecikir; bu kayıp kazançtan düşülür.
    Döndürür: (kazanç dizisi, en iyi ekleme sırası dizisi)
    """
    n, m = len(PX), len(CX)
    pts = np.vstack([p0[None, :], PX]) if n else p0[None, :]
    tau = t0 + np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1)) / speed if n else np.zeros(0)
    old = PV * np.exp(lnlam * np.maximum(tau - PA, 0.0)) * PR if n else np.zeros(0)
    best = np.full(m, -np.inf)
    pos = np.zeros(m, int)
    for q in range(n + 1):
        P = pts[q]
        tp = t0 if q == 0 else tau[q - 1]
        d1 = np.linalg.norm(CX - P, axis=1)
        gain = CV * np.exp(lnlam * np.maximum(tp + d1 / speed - CA, 0.0)) * CR
        if q < n:
            nx = PX[q]
            detour = (d1 + np.linalg.norm(CX - nx, axis=1) - np.linalg.norm(nx - P)) / speed
            later = tau[q:][None, :] + detour[:, None]
            new = (PV[q:] * np.exp(lnlam * np.maximum(later - PA[q:], 0.0)) * PR[q:]).sum(1)
            gain = gain - (old[q:].sum() - new)
        better = gain > best
        best[better] = gain[better]
        pos[better] = q
    return best, pos


# --------------------------------------------------------------- CBBA paketi
def refresh_bids(bundle, path, p0, t0, X, V, A, R, lnlam, speed):
    """Paketteki görevlerin tekliflerini güncel konumla yeniden hesaplar (paket sırasıyla
    marjinal kazanç, bükülmüş)."""
    bids, prev_s, prev_b = [], 0.0, np.inf
    for n in range(len(bundle)):
        sub = [t for t in path if t in bundle[:n + 1]]
        s = path_score(p0, t0, X[sub], V[sub], A[sub], R[sub], lnlam, speed)
        b = min(s - prev_s, prev_b)
        bids.append(b)
        prev_s, prev_b = s, b
    return bids


def build_bundle(bundle, path, bids, p0, t0, X, V, A, R, y, z, me, cand, L, lnlam, speed, margin):
    """CBBA paket kurma evresi. bundle (ekleme sırası) ve path (uçuş sırası) yerinde büyür.

    y, z: bu İHA'nın bildiği kazanan teklifler ve kazananlar. Başkasının tuttuğu bir görevi
    almak için teklifin en az 'margin' oranında daha iyi olması gerekir (gereksiz el değiştirmeyi önler).
    """
    cand = cand.copy()
    while len(bundle) < L:
        cand[bundle] = False
        idx = np.nonzero(cand)[0]
        if len(idx) == 0:
            break
        P = path
        gain, pos = best_insertion(p0, t0, X[P], V[P], A[P], R[P], X[idx], V[idx], A[idx], R[idx], lnlam, speed)
        if bids:
            gain = np.minimum(gain, bids[-1])        # teklif bükme: azalan marjinal kazanç
        held = (z[idx] >= 0) & (z[idx] != me)
        ok = np.where(held, gain > y[idx] * (1.0 + margin), gain > 1e-9)
        if not ok.any():
            break
        q = int(np.argmax(np.where(ok, gain, -np.inf)))
        t = int(idx[q])
        bundle.append(t)
        path.insert(int(pos[q]), t)
        bids.append(float(gain[q]))
    return bundle, path, bids


def cbba_merge(R, k, yk, zk, sk, Y, Z, si):
    """CBBA uzlaşma kuralları (Choi 2009, Tablo 1), k'nın mesajını alan tüm alıcılar için birlikte.

    R: alıcı İHA numaraları, k: gönderen. yk, zk: gönderenin bildiği teklifler ve kazananlar (T,).
    sk: gönderenin her İHA hakkındaki bilgisinin zamanı (N,). Y, Z: tüm İHA'ların teklif ve kazanan
    tabloları (N, T). si: alıcıların bilgi zamanları (len(R), N).
    Döndürür: (güncelle, sıfırla) maskeleri (len(R), T).
    """
    Ri = R[:, None]
    zi, yi = Z[R], Y[R]
    zk2 = np.broadcast_to(zk[None, :], zi.shape)
    gt = yk[None, :] > yi

    def s_of(s_rows, m):            # s_rows[r, m[r, t]], kazanan yoksa -inf
        mm = np.maximum(m, 0)
        v = np.take_along_axis(s_rows, mm, axis=1) if s_rows.ndim == 2 else s_rows[mm]
        return np.where(m >= 0, v, -np.inf)

    skm = s_of(sk, zk2)             # gönderenin, gönderenin kazanan dediği m hakkındaki bilgi zamanı
    sim = s_of(si, zk2)             # alıcının aynı m hakkındaki bilgi zamanı
    skn = s_of(sk, zi)              # gönderenin, alıcının kazanan dediği n hakkındaki bilgi zamanı
    sin_ = s_of(si, zi)

    k_k = zk2 == k
    k_i = zk2 == Ri
    k_0 = zk2 < 0
    k_m = ~(k_k | k_i | k_0)
    i_i = zi == Ri
    i_k = zi == k
    i_0 = zi < 0
    i_o = ~(i_i | i_k | i_0)
    same = i_o & (zi == zk2)
    i_n = i_o & ~same

    upd = np.zeros(zi.shape, bool)
    rst = np.zeros(zi.shape, bool)
    # gönderen "kazanan benim" diyor
    upd |= k_k & ((i_i & gt) | i_k | (i_o & ((skn > sin_) | gt)) | i_0)
    # gönderen "kazanan sensin" diyor
    rst |= k_i & (i_k | (i_o & (skn > sin_)))
    # gönderen "kazanan üçüncü biri (m)" diyor
    upd |= k_m & ((i_i & (skm > sim) & gt) | (i_k & (skm > sim)) | (same & (skm > sim)) | (i_0 & (skm > sim)))
    rst |= k_m & i_k & ~(skm > sim)
    upd_n = i_n & (((skm > sim) & (skn > sin_)) | ((skm > sim) & gt))
    upd |= k_m & upd_n
    rst |= k_m & i_n & ~upd_n & (skn > sin_) & (sim > skm)
    # gönderen "kazanan yok" diyor
    upd |= k_0 & (i_k | (i_o & (skn > sin_)))
    return upd, rst & ~upd


# --------------------------------------------------------------- merkezi SGA
def sga(agents, starts, t0s, X, V, A, R, open_, L, lnlam, speed):
    """Merkezi sıralı açgözlü atama. Döndürür: {İHA: uçuş sırasıyla görev listesi}."""
    plans = {int(i): [] for i in agents}
    free = open_.copy()
    best = {}

    def evaluate(i):
        idx = np.nonzero(free)[0]
        P = plans[i]
        if len(P) >= L or len(idx) == 0:
            best[i] = (-np.inf, -1, 0)
            return
        g, pos = best_insertion(starts[i], t0s[i], X[P], V[P], A[P], R[i, P], X[idx], V[idx], A[idx], R[i, idx],
                                lnlam, speed)
        q = int(np.argmax(g))
        best[i] = (float(g[q]), int(idx[q]), int(pos[q]))

    for i in plans:
        evaluate(i)
    while plans:
        i = max(best, key=lambda a: best[a][0])
        g, t, pos = best[i]
        if t < 0 or g <= 1e-9:
            break
        plans[i].insert(pos, t)
        free[t] = False
        for a in plans:
            if a == i or best[a][1] == t:
                evaluate(a)
    return plans


# --------------------------------------------------------------- yapay zekâ
AI_FEATURES = (
    "gorev_karistirmada",    # görev bilinen karıştırma hücresinde mi (0/1)
    "yol_karistirmada",      # İHA'dan göreve düz yolun karıştırma hücrelerinden geçen oranı
    "gps_yok",               # İHA'nın GPS'i kesik mi (0/1)
    "belirsizlik",           # İHA'nın konum belirsizliği / hedef yarıçapı (log ölçekli)
    "karistirma_seviyesi",   # İHA'nın aldığı karıştırma gücü (0-1)
    "uzaklik",               # göreve uzaklık / 300 m
    "deger",                 # görev değeri / 3
    "komsu",                 # son turda duyulan komşu oranı
)


class AIValue:
    """Küçük yapay sinir ağı: (İHA, görev) özelliklerinden İHA'nın o görevi başarma olasılığını
    rho in (0, 1) kestirir. CBBA, rho ile çarpılmış "beklenen ödülü" en büyütür.

    Ağ: 8 girdi -> 8 gizli nöron (tanh) -> 1 çıktı (sigmoid). Ağırlıklar deneyimden öğrenilir
    (tools/train_ai.py): sürü eğitim haritalarında uçar, her "İHA hedefe yöneldi" anının özellikleri
    ve sonucu (buldu / bulamadı) kaydedilir, ağ bu örneklerle geri yayılım ve Adam ile eğitilir.
    """
    n_in, n_hid = len(AI_FEATURES), 8
    n_params = n_in * n_hid + n_hid + n_hid + 1

    def __init__(self, theta=None):
        self.theta = np.asarray(theta if theta is not None else self.initial(), float)
        th, n_in, h = self.theta, self.n_in, self.n_hid
        self.W1 = th[:n_in * h].reshape(n_in, h)
        self.b1 = th[n_in * h:n_in * h + h]
        self.w2 = th[n_in * h + h:n_in * h + 2 * h]
        self.b2 = th[-1]

    @classmethod
    def initial(cls):
        """Başlangıç: hiçbir şey bilmeyen ağ. Çıkış ağırlıkları sıfır olduğu için her görevde rho = 0.5;
        tüm teklifleri aynı oranda ölçeklemek kararı değiştirmez, yani başlangıçta düz CBBA ile aynıdır.
        Gizli katman küçük rastgele ağırlıklarla başlar: hepsi sıfır olsaydı ağırlıklara eklenen küçük
        gürültüler çıktıyı hiç değiştirmez, ağ öğrenemezdi. Çıkış sigmoidi 0 noktasında en duyarlıdır."""
        rng = np.random.default_rng(2204)
        th = np.zeros(cls.n_params)
        th[:cls.n_in * cls.n_hid] = rng.normal(0, 1.0 / np.sqrt(cls.n_in), cls.n_in * cls.n_hid)
        return th

    @classmethod
    def load(cls, path=AI_WEIGHTS):
        if not os.path.exists(path):
            return cls()
        return cls(np.load(path)["theta"])

    def __call__(self, F):
        h = np.tanh(F @ self.W1 + self.b1)
        return 1.0 / (1.0 + np.exp(-(h @ self.w2 + self.b2)))
