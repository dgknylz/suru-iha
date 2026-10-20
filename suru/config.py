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
    agl: float = 40.0               # yerden uçuş yüksekliği (m)
    lookahead: float = 4.0          # arazi takibinde ileriye bakma süresi (s)
    max_climb: float = 5.0          # azami tırmanma/alçalma hızı (m/s)

    # --- uçuş ---
    max_speed: float = 12.0         # m/s
    max_accel: float = 4.0          # m/s^2
    sep_dist: float = 10.0          # çarpışmadan kaçınma mesafesi (m)
    layer_step: float = 6.0         # görevde çarpışma önleyici irtifa katmanları arası fark (m)
    task_radius: float = 6.0        # kamera hedefi bu yarıçap içinde görür (m)

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
    jammers: list = field(default_factory=lambda: [{"pos": (260.0, 230.0, 15.0), "power_dbm": 20.0}])
    gps_jam_dbm: float = -80.0      # bu güçten fazla karıştırma alan İHA GPS'i kaybeder
    jam_detect_dbm: float = -82.0   # (dirençli) İHA'nın "karıştırılıyorum" dediği eşik
    imu_drift: float = 0.15         # GPS yokken IMU hız sapmasının büyüme hızı (m/s / sqrt(s))
    spoof_fraction: float = 0.0     # sahte bilgi yayan ele geçirilmiş İHA oranı
    spoof_period: float = 10.0      # (merkezi) saldırganın sahte "tamamlandı" raporu aralığı (s)

    def relay_enabled(self):
        return bool(self.relay) and self.strategy != "centralized"


def make_config(strategy="resilient", jammer_power=20.0, spoof=0.0, seed=0, **kw):
    """Deney betikleri için kısayol. jammer_power=None -> karıştırıcı yok."""
    jammers = [] if jammer_power is None else [{"pos": (260.0, 230.0, 15.0), "power_dbm": float(jammer_power)}]
    return SimConfig(strategy=strategy, jammers=jammers, spoof_fraction=spoof, seed=seed, **kw)
