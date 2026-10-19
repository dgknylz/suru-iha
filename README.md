# Sürü İHA'larda Otonom Sürü Zekâsı ile Karar Alma ve Elektronik Harp Direnci

TÜBİTAK 2204-A projesi. Bir İHA sürüsünün elektronik harp (haberleşme karıştırma, GPS karıştırma,
sahte mesaj) altında görevlerini nasıl paylaştığını ve ne kadar dayanıklı olduğunu inceleyen
**Python simülasyonu** ve sonuçları gerçekçi şekilde gösteren **Unity HDRP 3D görselleştirmesi**.

```
Python (beyin)                         Unity HDRP (göz)
 suru/world.py  ── fizik, karar, EH ─┐
 suru/radio.py  ── SINR, paket kaybı │  UDP 5065 (JSON, 30 kare/s)
 run_live.py    ── canlı yayın ──────┴──────────────► SwarmReceiver → SwarmVisualizer
 run_experiments.py → results.csv → analyze.py → grafikler + istatistik
```

Ekran görüntüleri `gorseller/` klasöründe; TÜBİTAK rapor iskeleti `RAPOR_ISKELETI.md` dosyasında.

![Yer istasyonu ve sürü](gorseller/01_yer_istasyonu_ve_suru.jpg)

---

## 1. Hızlı başlangıç

### Python

```bash
py -3.14 -m venv .venv
```
```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Unity projesi

Unity projesi **`C:\SuruIHA\SuruIHA_Unity`** konumunda (Unity 6000.3.1f1, HDRP).
OneDrive dışında tutuldu, çünkü Unity'nin binlerce önbellek dosyasını OneDrive'ın eşitlemeye
çalışması projeyi bozar. Ayrıca Unity Türkçe karakterli yollarda (ğ, ı, ü) sorun çıkarabiliyor.

1. Unity Hub → **Add project from disk** → `C:\SuruIHA\SuruIHA_Unity`
2. `Assets/SuruIHA/Scenes/SuruSahnesi.unity` sahnesini aç.
3. **Play**'e bas. Ekranda "Python bağlantısı bekleniyor" yazacak.
4. Terminalde simülasyonu başlat:

```bash
.venv\Scripts\python.exe run_live.py
```

### Unity açmadan: hazır Windows uygulaması

`C:\SuruIHA\Build\SuruIHA.exe` derlenmiş, bağımsız uygulamadır. Jüriye Unity açmadan gösterebilirsin:
1. `SuruIHA.exe`'yi çift tıkla (tam ekran açılır; Alt+Enter pencereye alır, Esc kapatır).
2. Terminalde `python run_live.py` çalıştır. Sürü birkaç saniye içinde görünür.

Uygulama arka planda da çalışmaya devam eder, yani terminale geçince donmaz.

**Sunum ipucu:** `python run_live.py` bir kez başlatıldıktan sonra her şeyi Unity'den yönetebilirsin.
F1/F2/F3 ile mimariyi, +/- ile karıştırıcıyı, X ile saldırganı değiştir. Aynı haritada üç mimarinin
farkını jüriye canlı gösterebilirsin. Görev bitince simülasyon bekler, N ile yeni harita başlar.

**Performans:** RTX 4060 dizüstünde ölçüldü (sinematik kamera): Yüksek kalitede ~45 FPS (hacimsel sis, bulut gölgeleri, hareket bulanıklığı açık), Dengeli kalitede ~73 FPS. GPU ısınınca biraz düşer; bellek sabit, sızıntı yok. Sunumdan önce bilgisayarı prize tak, takılma olursa K ile Dengeli'ye geç.

### Canlı simülasyon seçenekleri

| Komut | Ne yapar |
|---|---|
| `python run_live.py` | Dirençli sürü, 20 dBm karıştırıcı |
| `python run_live.py --strategy centralized --jammer 30` | Merkezi mimari, güçlü karıştırma |
| `python run_live.py --strategy decentralized --spoof 0.2` | Saldırgan İHA'lı senaryo |
| `python run_live.py --jammer off --speed 3 --loop` | Karıştırıcısız, 3x hızlı, sürekli tekrar |

### Unity kısayolları

| Tuş | İşlev |
|---|---|
| **C** | Sinematik kamera (açılışta bu) |
| **O** | Serbest kamera: fare ile döndür, tekerlekle yakınlaş, WASD/QE ile kaydır, Shift hızlı |
| **F**, **Tab**, **1-9** | İHA takip kamerası |
| **T** | Taktik kuşbakışı |
| **L** | Haberleşme bağlantılarını göster/gizle |
| **G** | "İHA'nın sandığı konum" hayaletlerini göster/gizle |
| **J** | Dirençli sürünün ortak karıştırma haritası |
| **B** | Uzaktan görünen İHA işaretleri (durum renginde parlayan noktalar) |
| **F1 / F2 / F3** | Senaryo: merkezi / merkeziyetsiz / dirençli mimari (Python'u yeniden başlatmadan) |
| **+ / -** | Karıştırıcı gücü: kapalı → 10 → 20 → 30 dBm |
| **X** | Saldırgan (sahte bilgi yayan) İHA'ları aç/kapat (%20) |
| **N** | Yeni harita (farklı görev noktaları) |
| **K** | Grafik kalitesi: Yüksek → Dengeli → Performans (panelde FPS görünür) |
| **Esc** | Uygulamadan çık (yalnızca SuruIHA.exe) |
| **H** | Bilgi panelini gizle |

**Renkler:** İHA ışığı yeşil = normal, turuncu = karıştırılıyor, kırmızı = GPS yok, mavi = spiral
arama yapıyor, mor = saldırgan. Bağlantı çizgisi yeşilden kırmızıya sinyal kalitesini gösterir.
Görev halkası beyaz = açık, sarı = bir İHA yolda, yeşil = tamamlandı, kırmızı = yanlış tamamlandı.

---

## 2. Bilimsel model

### Radyo ve elektronik harp (`suru/radio.py`)
- 2.4 GHz, log-mesafe yol kaybı: `PL(d) = 40 + 10·2.5·log10(d)` dB
- Her bağlantı için **SINR** = sinyal − (gürültü + karıştırma); paket kaybı olasılığı lojistik eğri:
  `PER = 1 / (1 + e^(0.8·(SINR − 10)))`
- Karıştırıcı gücü her alıcıda mesafeye göre hesaplanır. İrtifa ve mesafe gerçekten önemlidir.
- **GPS karıştırma:** Alınan karıştırma gücü −80 dBm'yi aşarsa GPS kesilir. İHA IMU ile ölü hesap
  yapar, hata rastgele yürüyüşle `σ² = σ0² + q²t³/3` şeklinde büyür.
- **Sahte bilgi (spoofing):** Ele geçirilmiş İHA'lar sahte görev teklifi yayar (merkezi mimaride
  istasyona sahte "tamamlandı" raporu gönderir).

### Karşılaştırılan üç karar alma mimarisi (`suru/world.py`)
1. **Merkezi:** Görevleri yer istasyonu dağıtır. İHA'lar yalnızca istasyonla konuşur.
2. **Merkeziyetsiz:** İHA'lar komşularıyla dedikodu (gossip) protokolüyle konuşur, görevleri
   açık artırmayla (konsensüs tabanlı, CBBA benzeri) paylaşır. Lider yok.
3. **Merkeziyetsiz + EH direnci** (projenin özgün katkısı):
   - karıştırmayı algılama ve **ortak karıştırma haritası**
   - karıştırma bölgesindeki arkadaşın sessizliğini "kayıp" değil "meşgul" sayma (uzun TTL)
   - karıştırma bölgesinden transit geçmeme, oradaki görevleri sona bırakma
   - GPS'i olmayan İHA'nın GPS'li komşulardan **işbirlikçi konum düzeltmesi**
   - konum belirsizliği büyükse hedefte **spiral arama**, bulamazsa "bitti" demeyip yeniden deneme
   - teklifi konumuyla tutarsız olan İHA'ya güvenmeme (**makullük kontrolü**, sahte bilgiye karşı)

### Ölçülen metrikler
Görev tamamlama oranı, görev süresi, yanlış tamamlama (İHA bitti sandı ama hedef görülmedi),
gereksiz tekrar ziyaret, paket iletim oranı, ortalama konum hatası, ağ bağlantılılığı (λ2).

---

## 3. Deneyler

```bash
.venv\Scripts\python.exe run_experiments.py
```
```bash
.venv\Scripts\python.exe analyze.py
```

3 strateji × 4 karıştırıcı gücü (kapalı, 10, 20, 30 dBm) × 2 saldırgan oranı (%0, %20) × 30 tekrar
= **720 simülasyon** (~2 dakika, 15 çekirdek). Aynı tohum (seed) = aynı görev haritası olduğu
için stratejiler birebir aynı koşulda karşılaştırılır (eşleştirilmiş deney → Wilcoxon testi).

Çıktılar: `results/results.csv`, `results/figures/*.png`, `results/istatistik.txt`

### Öne çıkan bulgular (görev tamamlama oranı, ortalama ± std, n=30)

| Koşul | Merkezi | Merkeziyetsiz | **Dirençli** |
|---|---|---|---|
| Karıştırıcı yok | %100 | %100 | **%100** |
| 20 dBm karıştırma | %91.7 ± 5.9 | %93.8 ± 4.5 | **%99.7 ± 1.3** |
| 30 dBm karıştırma | %45.8 ± 11.2 | %48.0 ± 11.7 | **%73.5 ± 12.3** |
| %20 saldırgan, karıştırma yok | %53.8 ± 6.0 | %0.0 | **%100** |
| %20 saldırgan + 20 dBm | %51.2 ± 8.0 | %0.0 | **%99.5 ± 1.5** |

Dirençli sürü, karıştırma veya saldırgan olan tüm koşullarda diğer ikisinden anlamlı şekilde
iyidir (Wilcoxon, p < 0.001). İlginç bir bulgu: Saldırı altında korumasız merkeziyetsiz sürü
merkezi mimariden bile kötü sonuç veriyor. Merkeziyetsizlik tek başına yetmiyor, **güven
mekanizması** şart.

---

## 4. 3D modeller ve sahne

Tüm modeller ve dokular kodla üretilir (hazır model veya dış kaynaklı doku yok):

| Dosya | İçerik |
|---|---|
| `blender/drone.py` | Taktik quadcopter: aerodinamik gövde, katlanır karbon kollar, kanatlı motorlar, bükümlü pervaneler, gimbal kamera, stereo sensörler, GPS, anten, bayrak ve yazı |
| `blender/jammer.py` | 6x6 elektronik harp aracı, ekipman kabini, teleskopik direk, panel ve LPDA antenler |
| `blender/gcs.py` | Yer kontrol istasyonu: konteyner, kafes direk, takip anteni, jeneratör, kum torbaları |
| `blender/village.py` | Orta Anadolu köyü: kiremit kırma çatılı sıvalı evler (güneş enerjili su ısıtıcılı), revaklı kubbeli minareli cami, ahşap elektrik direği |
| `blender/nature.py` | Karaçam (genç/yaşlı), meşe, çalı (alfa kesimli yaprak kartları, LOD'lu), kayalar, ot öbekleri |
| `tools/gen_textures.py` | Dikişsiz dokular: çimen, bozkır, sürülmüş tarla, anız, kaya, çakıl, kabuk, iğne, yaprak, ot, Türk bayrağı |
| `unity/Assets/SuruIHA/Editor/SuruIHASetup.cs` | **SürüİHA → Sahneyi Kur** menüsü: malzemeler, prefab'lar, 2,4 km ana arazi (tarla parselleri, bozkır tepeler, çam ormanı, tarla sınırında meşeler, çakıl yollar, 1,6 milyon ot öbeği), 24 evli köy ve cami, ana yol boyunca 42 direkli elektrik hattı, ufka uzanan 8 parça dağ silsilesi, gökyüzü, hacimsel bulutlar, sis |

### Modelleri yeniden üretmek

```bash
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup -P blender/drone.py -- C:\SuruIHA\models
```
```bash
.venv\Scripts\python.exe tools/gen_textures.py C:\SuruIHA\models\textures
```
```bash
powershell -File tools/sync_unity.ps1
```
Sonra Unity'de menüden **SürüİHA → Sahneyi Kur**, uygulama için **SürüİHA → Windows Uygulaması Derle**.

Hepsini tek komutla (eşitle → sahne → önizleme → uygulama → uçtan uca test):
```bash
powershell -File tools/full_build.ps1
```
Uçtan uca test (`tools/autotest.ps1`) Python'u ve uygulamayı birlikte başlatır, farklı kamera
modlarında ekran görüntüsü alır ve `C:\SuruIHA\autotest\rapor.txt` dosyasına kare sayısı, FPS
ve görev durumunu yazar.

---

## 5. Sınırlılıklar (jüriye dürüstçe söylenecekler)

- Radyo modeli istatistiksel bir yaklaşımdır: çok yollu yayılım ve arazi gölgelemesi yoktur.
- Uçuş dinamiği nokta-kütle modelidir (ivme ve hız sınırlı). Motor ve aerodinamik modellenmemiştir.
- Karıştırma **yalnızca yazılımda** modellenmiştir. Gerçek RF yayını yapılmamıştır ve yapılmamalıdır.
- Sonuçlar simülasyon ortamına aittir. Gerçek uçuş testiyle doğrulanmamıştır.

---

## 6. Klasör yapısı

```
suru/                 Python simülasyon paketi (config, radio, world, bridge)
run_live.py           Unity'ye canlı yayın
run_experiments.py    Toplu deney
analyze.py            Grafik ve istatistik
results/              Deney çıktıları
gorseller/            Sunum ve rapor için ekran görüntüleri
RAPOR_ISKELETI.md     TÜBİTAK 2204 rapor iskeleti (sayılar ve kaynaklar)
blender/              Blender model betikleri
tools/                Doku üretici, Unity eşitleme, kare dökümü
unity/Assets/SuruIHA/ Unity C# scriptleri (asıl kopya burada, sync_unity.ps1 projeye kopyalar)
```
