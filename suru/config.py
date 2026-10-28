"""Simülasyon parametreleri.

Deneylerde değiştirdiğimiz her şey (strateji, karıştırıcı gücü, saldırgan oranı...)
bu dosyadaki SimConfig sınıfında durur. Böylece her deney tek bir nesneyle tanımlanır.
"""
from dataclasses import dataclass, field

# Karşılaştırdığımız üç karar alma mimarisi
STRATEGIES = ("centralized", "decentralized", "resilient")
STRATEGY_NAMES = {
    "centralized": "Merkezi (yer istasyonu)",
    "decentralized": "Merkeziyetsiz",
    "resilient": "Merkeziyetsiz + EH direnci",
}

# Görev paylaşım (planlama) algoritmaları
PLANNERS = ("greedy", "cbba", "ai")
PLANNER_NAMES = {
    "greedy": "Açgözlü tek görev",
    "cbba": "CBBA paket planlama",
    "ai": "CBBA + yapay zekâ",
}


@dataclass
class SimConfig:
    # --- genel ---
    seed: int = 0
    n_drones: int = 10
    n_tasks: int = 20
    dt: float = 0.1                 # fizik adımı (s)
    comm_every: int = 2             # kaç fizik adımında bir mesajlaşma (0.2 s -> 5 Hz)
    max_time: float = 360.0         # görev süresi sınırı (s), kalkış ve intikal dahil

    # --- görev alanı ve arazi ---
    # Üs (yer istasyonu) (0, 0)'da. Görev alanı üssün kuzeyinde; kuzey ucu tepelik.
    area_center: tuple = (0.0, 380.0)
    area_half: float = 330.0        # görev alanının yarı kenarı (m)
    terrain: bool = True            # Unity'den aktarılan gerçek arazi (False = düz zemin)
    region: str = "ova"             # harita: ova, kar (karlı dağlar), nehir (Kızılırmak), divrigi, gokpinar, deniz (Akdeniz)
    agl: float = 40.0               # yerden uçuş yüksekliği (m)
    lookahead: float = 4.0          # arazi takibinde ileriye bakma süresi (s)
    max_climb: float = 5.0          # azami tırmanma/alçalma hızı (m/s)

    # --- uçuş ---
    max_speed: float = 12.0         # m/s
    max_accel: float = 4.0          # m/s^2
    sep_dist: float = 10.0          # çarpışmadan kaçınma mesafesi (m)
    layer_step: float = 6.0         # görevde çarpışma önleyici irtifa katmanları arası fark (m)
    task_radius: float = 6.0        # görev: hedefin bu yarıçap içine gelmek (m)
    search_detect: float = 15.0     # (dirençli) spiral aramada kamera hedefi bu mesafeden tanır (m)
    recover_sigma: float = 25.0     # (dirençli) konum belirsizliği bunu aşan İHA görevi bırakıp GPS'i geri almaya gider (m)

    # --- sürü zekâsı ---
    formation: str = "V"            # intikal ve dönüş düzeni: V | hat | kol | halka
    form_spacing: float = 16.0      # düzende komşu İHA'lar arası mesafe (m)
    transit_speed: float = 9.0      # sanal liderin hızı (m/s)
    takeoff_time: float = 15.0      # kalkış ve havada toplanma süresi (s)
    consensus_gain: float = 0.35    # sanal lider uzlaşma (konsensüs) kazancı
    neighbor_radius: float = 60.0   # Reynolds kuralları için komşuluk yarıçapı (m)
    w_align: float = 0.25           # hizalanma ağırlığı
    w_cohesion: float = 0.04        # uyum ağırlığı
    regroup_wait: float = 8.0       # bu kadar boşta kalan İHA toplanma noktasına gider (s)
    regroup_hold: float = 25.0      # toplanmada en fazla bu kadar bekle, sonra eve dön (s)
    relay: bool = False             # bağlantı koruma rölesi (merkeziyetsiz stratejilerde kullanılabilir)
    relay_after: float = 5.0        # bu kadar duyulmayan arkadaş "kopmuş" sayılır (s)
    max_relays: int = 2             # aynı anda en fazla kaç İHA röle olabilir
    failures: int = 0               # görev sırasında arızalanıp düşecek İHA sayısı

    # --- karar alma ---
    strategy: str = "resilient"     # "centralized" | "decentralized" | "resilient"
    claim_ttl: float = 3.0          # duyulmayan görev sahiplenmesi kaç saniyede geçersiz olur
    claim_ttl_jam: float = 30.0     # (dirençli) karıştırma bölgesindeki görevler için bekleme süresi
    jam_penalty: float = 150.0      # (dirençli) karıştırma bölgesindeki göreve teklif cezası (m)
    retry_cooldown: float = 30.0    # (dirençli) bulunamayan göreve aynı İHA'nın tekrar deneme beklemesi
    idle_stop: float = 40.0         # tüm sürü bu kadar boşta kalırsa görev biter
    gcs_timeout: float = 5.0        # (merkezi) yer istasyonu bu kadar duyulmazsa üsse dön
    gcs_release: float = 20.0       # (merkezi) bu kadar duyulmayan İHA'nın görevi başkasına verilir

    # --- otonom karar alma ---
    # greedy: her İHA en yakın tek görevi açık artırmayla alır (eski yöntem, karşılaştırma için)
    # cbba  : her İHA birkaç görevlik paket planlar, komşularla uzlaşır (merkezide: SGA)
    # ai    : cbba + görevlerin uygunluğunu yapay sinir ağı kestirir
    planner: str = "cbba"
    bundle_size: int = 3            # (cbba) bir İHA'nın aynı anda planladığı en fazla görev
    discount: float = 0.99          # görev değerinin saniyelik azalma çarpanı (lambda)
    outbid_margin: float = 0.03     # başkasının görevini almak için gereken en az teklif üstünlüğü
    gcs_replan: float = 1.0         # (merkezi) yer istasyonu planı kaç saniyede bir yeniler
    priorities: bool = True         # görev değerleri 1-3 (False: hepsi 1)
    n_popup: int = 0                # görev sırasında beliren yeni hedef sayısı
    popup_window: tuple = (60.0, 100.0)  # yeni hedeflerin belirdiği zaman aralığı (s)
    detect_range: float = 120.0     # İHA sensörü yeni hedefi bu mesafeden görür (m)
    live_reserve: int = 0           # (canlı) elle eklenebilecek yedek hedef sayısı
    ew_valuation: bool = True       # (dirençli) görev değerlendirmede EH kuralları (karıştırma cezası, belirsizlik maliyeti)
    ai_weights: str = ""            # yapay zekâ ağırlık dosyası (boş: suru/data/ai_politika.npz)
    ai_theta: tuple = ()            # (eğitim) ağ ağırlıkları doğrudan verilirse dosya yerine bunlar kullanılır
    log_attempts: bool = False      # (eğitim verisi) her görev denemesinin özelliklerini ve sonucunu kaydet

    # --- radyo: 2.4 GHz, log-mesafe yol kaybı modeli ---
    tx_power_dbm: float = 20.0      # İHA verici gücü (100 mW)
    gcs_gain_db: float = 10.0       # yer istasyonu anten kazancı
    noise_dbm: float = -95.0        # alıcı gürültü tabanı
    pl_d0_db: float = 40.0          # 1 m'deki yol kaybı
    pl_exponent: float = 2.5        # yol kaybı üssü (2 = boş uzay)
    comm_range: float = 300.0       # İHA-İHA azami menzil (m)
    sinr_threshold_db: float = 10.0 # paketlerin yarısının kaybolduğu SINR
    per_slope: float = 0.8          # paket hata eğrisinin dikliği

    # --- elektronik harp ---
    # Karıştırıcı: pos = (x, y, antenin yerden yüksekliği), band = "genis" (haberleşme + GPS) ya da
    # "nokta" (yalnızca haberleşme kanalı, gücü tek kanala yığılır), route + speed verilirse hareket eder.
    jammers: list = field(default_factory=lambda: [{"pos": (260.0, 230.0, 15.0), "power_dbm": 20.0}])
    jammer_mode: str = "sabit"      # (kayıt için) karıştırıcı senaryosu: sabit | hareketli | iki | nokta | tepe | sirt
    terrain_radio: bool = True      # arazi radyo sinyalini keser (tek bıçak sırtı kırınımı, ITU-R P.526)
    gps_jam_dbm: float = -80.0      # bu güçten fazla karıştırma alan İHA GPS'i kaybeder
    jam_detect_dbm: float = -82.0   # (dirençli) İHA'nın "karıştırılıyorum" dediği eşik
    jam_cell_ttl: float = 90.0      # (dirençli) karıştırma hücresi bu kadar teyit edilmezse unutulur (hareketli karıştırıcı)
    imu_drift: float = 0.15         # GPS yokken IMU hız sapmasının büyüme hızı (m/s / sqrt(s))
    spoof_fraction: float = 0.0     # sahte bilgi yayan ele geçirilmiş İHA oranı
    spoof_mode: str = "naive"       # saldırgan davranışı: naive (her görevi ister) | sneaky (sinsi, bkz. ew.py)
    spoof_period: float = 10.0      # saldırganın sahte "tamamlandı" raporu aralığı (s)
    gps_spoof: str = ""             # (kayıt için) GPS aldatma senaryosu: "" | hizli | yavas
    gps_spoofers: list = field(default_factory=list)   # {"pos": (x, y), "radius": m, "drag": m/s, "dir_deg": derece}

    # --- dirençli stratejinin mekanizmaları (ablasyon: tek tek kapatıp katkısını ölçmek için) ---
    ew_jam_map: bool = True         # karıştırmayı algılama ve ortak karıştırma haritası
    ew_long_ttl: bool = True        # karıştırma bölgesindeki sessiz arkadaşı "meşgul" sayma (uzun TTL)
    ew_avoid: bool = True           # karıştırma bölgesinden transit geçmeme
    ew_coop_loc: bool = True        # GPS'siz İHA'nın komşulardan işbirlikçi konum düzeltmesi
    ew_search: bool = True          # hedefte spiral arama, görmeden "bitti" dememe
    ew_recover: bool = True         # GPS kurtarma (konumunu kaybeden İHA GPS'i geri almaya gider)
    ew_trust: bool = True           # makullük kontrolü ve güven sistemi (sahte bilgiye karşı)
    ew_localize: bool = True        # karıştırıcının yerini bulma ve karıştırma alanını önceden kestirme
    ew_fhss: bool = True            # frekans atlamalı haberleşme (nokta karıştırmaya karşı)
    ew_spoof_detect: bool = True    # GPS aldatma tespiti (IMU tutarlılığı + komşu menzil ölçümü)

    def relay_enabled(self):
        return bool(self.relay) and self.strategy != "centralized"


# Karıştırıcı senaryoları (güç P dBm). Hareketli karıştırıcı görev alanının çevresinde 5 m/s ile devriye gezer.
def jammer_scenario(mode, P):
    P = float(P)
    if mode == "sabit":
        return [{"pos": (260.0, 230.0, 15.0), "power_dbm": P}]
    if mode == "hareketli":
        route = [(280.0, 150.0), (280.0, 480.0), (-250.0, 480.0), (-250.0, 150.0), (280.0, 150.0)]
        return [{"pos": (280.0, 150.0, 15.0), "power_dbm": P, "route": route, "speed": 5.0}]
    if mode == "iki":
        return [{"pos": (260.0, 230.0, 15.0), "power_dbm": P}, {"pos": (-230.0, 520.0, 15.0), "power_dbm": P}]
    if mode == "nokta":
        return [{"pos": (260.0, 230.0, 15.0), "power_dbm": P, "band": "nokta"}]
    if mode == "tepe":                    # tepenin üstünde: yüksekten her yeri görür
        return [{"pos": (-60.0, 760.0, 15.0), "power_dbm": P}]
    if mode == "sirt":                    # sırtın arkasında: tepeler sinyalinin bir kısmını keser (arazi kalkanı)
        return [{"pos": (-150.0, 925.0, 15.0), "power_dbm": P}]
    raise ValueError(f"bilinmeyen karıştırıcı senaryosu: {mode}")


# GPS aldatıcı senaryoları: yerdeki verici 250 m içindeki İHA'ların GPS'ini ele geçirip konumlarını doğuya sürükler
GPS_SPOOF_MODES = {
    "hizli": [{"pos": (-150.0, 420.0), "radius": 250.0, "drag": 2.0, "dir_deg": 0.0}],
    "yavas": [{"pos": (-150.0, 420.0), "radius": 250.0, "drag": 0.5, "dir_deg": 0.0}],
}


def make_config(strategy="resilient", jammer_power=20.0, spoof=0.0, seed=0, jammer_mode="sabit", gps_spoof="",
                jammer_xy=None, jammer_band="genis", spoofer_xy=None, **kw):
    """Deney betikleri için kısayol. jammer_power=None -> karıştırıcı yok.
    jammer_xy: [(x, y), ...] verilirse karıştırıcılar bu noktalara konur (Unity'de "Kendi senaryon");
    spoofer_xy: (x, y) verilirse GPS aldatıcı oraya taşınır."""
    if jammer_power is None:
        jammers = []
    elif jammer_xy:
        jammers = [{"pos": (float(x), float(y), 15.0), "power_dbm": float(jammer_power), "band": jammer_band}
                   for x, y in jammer_xy]
        jammer_mode = "ozel"
    else:
        jammers = jammer_scenario(jammer_mode, jammer_power)
    spoofers = GPS_SPOOF_MODES[gps_spoof] if gps_spoof else []
    if spoofers and spoofer_xy is not None:
        spoofers = [dict(s, pos=(float(spoofer_xy[0]), float(spoofer_xy[1]))) for s in spoofers]
    return SimConfig(strategy=strategy, jammers=jammers, spoof_fraction=spoof, seed=seed, jammer_mode=jammer_mode,
                     gps_spoof=gps_spoof, gps_spoofers=spoofers, **kw)


def parse_points(spec):
    """'x,y;x,y' -> [(x, y), ...] (Unity'deki "Kendi senaryon" ekranından gelir). Boşsa None."""
    pts = [tuple(float(v) for v in part.split(",")) for part in (spec or "").split(";") if part.strip()]
    if any(len(p) != 2 for p in pts):
        raise ValueError(f"nokta listesi 'x,y;x,y' biçiminde olmalı: {spec}")
    return pts or None
