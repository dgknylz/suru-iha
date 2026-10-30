"""Konvoy koruma görevi: İKA (insansız kara aracı) konvoyu, yol taraması, pusu, mayın ve HSS bastırma.

Görev
  Üsten çıkan 4 İKA'lık konvoy, verilen rota boyunca hedefe ilerler (5 m/s, araçlar arası 25 m). Sürünün
  görevi konvoyun önünü açmak:
  - Yol taraması: rota 60 m'lik parçalara bölünür; her parçanın ortasında bir "tarama" görevi vardır. Konvoy
    yaklaştıkça (350 m önü) görevler belirir. İHA tarama noktasına gerçekten varırsa kamerası çevredeki gizli
    tehditleri görür (mayın 45 m, pusu 150 m). İHA konumunu yanlış biliyorsa (GPS karıştırma, aldatma) noktaya
    vardığını sanır ama tarayamaz: sürü yolu temiz sanar, konvoy gizli tehdide girer.
  - Konvoy kuralı: konvoy yalnızca taranmış yolda ilerler; taranmamış parçanın 40 m gerisinde, bilinen ama
    etkisiz hâle getirilmemiş pusunun menzili dışında bekler.
  - Pusu: yol kenarında gizli düşman mevzisi (160 m menzil). Etkisiz hâle getirilmemişse menzile giren konvoya
    10 s'de bir ateş eder (isabet 0,7). Bulunan pusu için "işaretleme" görevi doğar: İHA mevziye varıp işaretler,
    3 s sonra topçu ateşiyle imha edilir.
  - Mayın: yolda gizli patlayıcı. Bulunmazsa üstünden geçen araç kaybedilir; bulunursa konvoy yavaşlayıp dolanır.
  - HSS bastırma (dirençli sürü, SEAD): radarın yeri bulunduğunda ve şemsiyesi taranacak yolu kesiyorsa sürü
      rolleri kendisi dağıtır (herkes aynı bilgiyle aynı seçimi yapar, lider yok; her rol için o noktaya en yakın
      boştaki İHA):
        karıştırıcı : menzil dışında nöbet tutar, radarın alıcısını karıştırır (radarın gördüğü yankı 10 dB zayıflar)
        yem         : radar kesit alanı büyütülmüş (Luneburg merceği) İHA; saldırıda radara doğru koşar, radar en
                      büyük hedefe öncelik verdiği için füzeleri üstüne çeker
        kamikaze ×2 : radardan 250 m'de iki ayrı yönde bekler; yem koşunca 4 s sonra iki yönden alçaktan
                      25 m/s ile dalar (radar iki atış arasında 6 s bekler: ikisini birden durduramaz)
      Hepsi yerini alınca saldırı başlar. Ölen rolün yerine yenisi seçilir. Radar susunca roller biter, sürü
      şemsiyenin altındaki yolu da tarar.
"""
import numpy as np

from .swarm import Path

SEG = 60.0                 # tarama parçası (m)
LOOKAHEAD = 350.0          # konvoyun bu kadar önündeki tarama görevleri belirir (m)
STOP_GAP = 40.0            # konvoy taranmamış yolun bu kadar gerisinde durur (m)
CONVOY_SPEED = 5.0         # m/s
CONVOY_GAP = 25.0          # araçlar arası (m)
CONVOY_START = 20.0        # konvoyun yola çıktığı an (s)
MINE_DETECT = 45.0         # tarama noktasından mayının görüldüğü uzaklık (m)
AMBUSH_DETECT = 150.0      # tarama noktasından pusunun görüldüğü uzaklık (m; araç büyük, kamera 40 m yüksekte)
AMBUSH_RANGE = 160.0       # pusunun konvoya ateş menzili (m)
AMBUSH_PERIOD = 10.0       # pusunun atış aralığı (s)
AMBUSH_PK = 0.7
MARK_DELAY = 3.0           # işaretlenen pusunun imha edilmesi (topçu) (s)
MINE_HIT = 5.0             # aracın mayına bu kadar yaklaşması (m)
DECOY_RCS = 10.0           # yem İHA'nın radar kesit alanı çarpanı
JAM_SNR = 0.1              # karıştırıcı yerindeyken radarın gördüğü yankı (−10 dB)
STRIKE_DETECT = 60.0       # kamikazenin kamerası radarı bu uzaklıktan tanır (m)

# Görev türleri (World.ttype)
T_NORMAL, T_SCAN, T_MARK = range(3)
TYPE_NAMES = ("hedef", "tarama", "işaretleme")
# HSS bastırma rolleri (World.role)
R_NONE, R_DECOY, R_JAM, R_STRIKE = range(4)
ROLE_NAMES = ("", "yem", "karıştırıcı", "kamikaze")
DASH_SPEED = 25.0          # kamikazenin son dalış hızı (m/s)
STRIKE_HIT = 30.0          # kamikaze radara bu kadar yaklaşınca vurur (m)
ATTACK_DELAY = 4.0         # yem koşmaya başladıktan sonra kamikazelerin dalışa geçmesi (s)

# Ova haritasında konvoy senaryosu: düz vadide 721 m'lik rota (en dik yer %11), gizli tehditler ve vadinin kuzeybatısındaki
# yamaçtan yolun son kısmını koruyan HSS radarı. İkinci pusu yolun üstündeki yamaçta, radarın şemsiyesinin altında.
CONVOY_ROUTE = [(-30.0, -40.0), (-20.0, 150.0), (40.0, 330.0), (20.0, 450.0), (-60.0, 520.0), (-170.0, 545.0)]
CONVOY_THREATS = [
    {"kind": "mayin", "s": 225.0},
    {"kind": "pusu", "pos": (135.0, 400.0)},
    {"kind": "mayin", "s": 560.0},
    {"kind": "pusu", "pos": (-110.0, 650.0)},
]
CONVOY_RADAR = {"pos": (-420.0, 640.0), "known": False, "missiles": 6, "r50": 380.0}
CONVOY_JAMMER = {"pos": (220.0, 470.0, 15.0), "power_dbm": 20.0}


class Threat:
    """Gizli yer tehdidi: mayın (yolun üstünde) ya da pusu (yol kenarında mevzi)."""

    def __init__(self, kind, xy, idx):
        self.kind, self.xy, self.id = kind, np.asarray(xy, float), idx
        self.found = False          # sürü gerçekten gördü (gerçek)
        self.found_t = np.nan
        self.marked_t = np.inf      # işaretlendiği an (pusu); MARK_DELAY sonra imha
        self.dead = False           # imha edildi (pusu) ya da patladı (mayın)
        self.next_fire = 0.0
        self.task = -1              # işaretleme görevi


class Convoy:
    def __init__(self, route, threats, n_vehicles, terrain):
        self.path = Path(route)
        self.n = n_vehicles
        self.s = np.array([-k * CONVOY_GAP for k in range(n_vehicles)])   # araçların rota üzerindeki yeri
        self.alive = np.ones(n_vehicles, bool)
        self.lost_t = np.full(n_vehicles, np.nan)
        self.lost_by = [""] * n_vehicles
        self.speed = 0.0
        self.wait = "hazır"           # konvoyun durumu (Unity'de yazılır)
        self.arrived_t = np.nan
        self.terrain = terrain
        self.threats = []
        for k, d in enumerate(threats):
            xy = self.path.at(d["s"])[0] if "s" in d else d["pos"]
            self.threats.append(Threat(d["kind"], xy, k))

    @property
    def lead(self):
        """Öndeki canlı aracın rota üzerindeki yeri."""
        s = self.s[self.alive]
        return float(s.max()) if len(s) else 0.0

    def xy(self, k):
        p, u = self.path.at(max(self.s[k], 0.0))
        if self.s[k] < 0:                      # henüz yola çıkmamış araç: başlangıcın gerisinde bekler
            p = p + u * self.s[k]
        return p, u

    @property
    def done(self):
        return np.isfinite(self.arrived_t) or not self.alive.any()

    def s_of(self, xy):
        """Noktanın rotaya en yakın olduğu yer (rota üzerindeki mesafe)."""
        P = self.path.p
        best, sb = np.inf, 0.0
        for k in range(len(P) - 1):
            a, b = P[k], P[k + 1]
            ab = b - a
            L2 = float(ab @ ab)
            u = 0.0 if L2 < 1e-9 else float(np.clip((np.asarray(xy) - a) @ ab / L2, 0.0, 1.0))
            d = float(np.linalg.norm(a + u * ab - xy))
            if d < best:
                best, sb = d, self.path.cum[k] + u * np.sqrt(L2)
        return sb

    def first_in_range(self, xy, r, step=5.0):
        """Rotada noktaya r'den yakın ilk yer (yoksa None)."""
        for s in np.arange(0.0, self.path.length, step):
            if np.linalg.norm(self.path.at(s)[0] - xy) < r:
                return float(s)
        return None

    def positions(self):
        out = []
        for k in range(self.n):
            p, u = self.xy(k)
            out.append((p, u))
        return out
