# Sürü İHA'larda Otonom Sürü Zekâsı ile Karar Alma ve Elektronik Harp Direnci

TÜBİTAK 2204-A projesi. Bir İHA sürüsünün elektronik harp (haberleşme karıştırma, GPS karıştırma,
sahte mesaj) altında görevlerini nasıl paylaştığını ve ne kadar dayanıklı olduğunu inceleyen
**Python simülasyonu** ve sonuçları gerçekçi şekilde gösteren **Unity HDRP 3D görselleştirmesi**.

```
Python (beyin)                         Unity HDRP (göz)
 suru/world.py  ── fizik, karar, EH ─┐
 suru/decision.py ─ CBBA, SGA, YZ    │
 suru/swarm.py  ── sürü zekâsı       │
 suru/terrain.py ── Unity arazisi ◄──┼─────────────── yükseklik haritası (sahne kurulumunda)
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

**Bir uçuşta ne görürsün:** Sürü üsten kalkar ve havada halka olur. V düzeninde kuzeydeki görev
alanına uçar. Daha yoldayken her İHA'nın planı (renkli çizgi: İHA → 1. hedef → 2. hedef → 3. hedef)
belirir. Alana varınca dağılıp planlarını uygular. Görev sırasında yeni hedefler belirir (mor dalga).
Sürü bunları birkaç saniyede kendi arasında yeniden paylaşır. Görevler bitince toplanma noktasında
yeniden halka olur, V düzeninde üsse döner ve iner. Toplam yaklaşık 3,5 dakika sürer.

**Sunum ipucu:** `python run_live.py` bir kez başlatıldıktan sonra her şeyi Unity'den yönetebilirsin.
F1/F2/F3 ile mimariyi, F4 ile planlama algoritmasını, +/- ile karıştırıcıyı, X ile saldırganı değiştir.
V ile düzeni değiştir. Z ile bir İHA'yı düşür ve planların nasıl yeniden dağıldığını göster. Y ile görev
alanına yeni bir hedef ekle ve sürünün kendi kendine kimin gideceğine karar vermesini izlet.
Aynı haritada mimarilerin ve algoritmaların farkını jüriye canlı gösterebilirsin. Sürü inince
simülasyon bekler, N ile yeni harita başlar.

**Performans:** RTX 4060 dizüstünde ölçüldü (sinematik kamera): Yüksek kalitede ~45 FPS (hacimsel sis, bulut gölgeleri, hareket bulanıklığı açık), Dengeli kalitede ~73 FPS. GPU ısınınca biraz düşer; bellek sabit, sızıntı yok. Sunumdan önce bilgisayarı prize tak, takılma olursa K ile Dengeli'ye geç.

### Canlı simülasyon seçenekleri

| Komut | Ne yapar |
|---|---|
| `python run_live.py` | Dirençli sürü, 20 dBm karıştırıcı |
| `python run_live.py --strategy centralized --jammer 30` | Merkezi mimari, güçlü karıştırma |
| `python run_live.py --strategy decentralized --spoof 0.2` | Saldırgan İHA'lı senaryo |
| `python run_live.py --jammer off --speed 3 --loop` | Karıştırıcısız, 3x hızlı, sürekli tekrar |
| `python run_live.py --formation hat --failures 2` | Hat düzeninde intikal, görevde 2 İHA arızası |
| `python run_live.py --strategy decentralized --relay` | Bağlantı koruma rölesi açık |
| `python run_live.py --planner greedy` | Eski yöntem: her İHA en yakın tek görevi alır (karşılaştırma için) |
| `python run_live.py --planner ai --jammer 30` | CBBA + yapay zekâ, güçlü karıştırma |
| `python run_live.py --popups 0` | Görev sırasında yeni hedef belirmesin (varsayılan 4) |

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
| **P** | İHA'ların planlı rotalarını göster/gizle |
| **F1 / F2 / F3** | Senaryo: merkezi / merkeziyetsiz / dirençli mimari (Python'u yeniden başlatmadan) |
| **F4** | Planlama algoritması: açgözlü tek görev → CBBA → CBBA + yapay zekâ |
| **Y** | Görev alanına yeni bir hedef ekle (en fazla 8; yer istasyonu ihbarı gibi) |
| **+ / -** | Karıştırıcı gücü: kapalı → 10 → 20 → 30 dBm |
| **X** | Saldırgan (sahte bilgi yayan) İHA'ları aç/kapat (%20) |
| **N** | Yeni harita (farklı görev noktaları) |
| **V** | Düzen tipi: V → hat → kol → halka (uçuşu yeniden başlatmadan) |
| **Z** | Rastgele bir İHA'yı arızalandır (düşer, sürü görevlerini ve düzeni yeniden dağıtır) |
| **K** | Grafik kalitesi: Yüksek → Dengeli → Performans (panelde FPS görünür) |
| **Esc** | Uygulamadan çık (yalnızca SuruIHA.exe) |
| **H** | Bilgi panelini gizle |

**Renkler:** İHA ışığı yeşil = normal, turuncu = karıştırılıyor, kırmızı = GPS yok, mavi = spiral
arama yapıyor, mor = saldırgan, camgöbeği = röle (koruduğu arkadaşına çizgiyle bağlı), sönük = arızalı. Bağlantı çizgisi yeşilden kırmızıya sinyal kalitesini gösterir.
Görev halkası beyaz = açık, sarı = bir İHA yolda, yeşil = tamamlandı, kırmızı = yanlış tamamlandı,
yanıp sönen mor = yeni belirdi ama sürü henüz bilmiyor. İç içe halka sayısı görevin önceliğidir (1-3).
Renkli çizgiler her İHA'nın planıdır: ilk hedefe giden kısım kalın, sonrakiler ince.

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
1. **Merkezi:** Görevleri yer istasyonu dağıtır (SGA). İHA'lar yalnızca istasyonla konuşur.
2. **Merkeziyetsiz:** İHA'lar komşularıyla dedikodu (gossip) protokolüyle konuşur, görevleri
   **CBBA** ile kendi aralarında paylaşır. Lider yok.
3. **Merkeziyetsiz + EH direnci** (projenin özgün katkısı):
   - karıştırmayı algılama ve **ortak karıştırma haritası**
   - karıştırma bölgesindeki arkadaşın sessizliğini "kayıp" değil "meşgul" sayma (uzun TTL)
   - karıştırma bölgesinden transit geçmeme, oradaki görevleri sona bırakma
   - GPS'i olmayan İHA'nın GPS'li komşulardan **işbirlikçi konum düzeltmesi**
   - konum belirsizliği büyükse hedefte **spiral arama** (kamera 15 m'den tanır, görsel güdümle
     üstüne gelir), bulamazsa "bitti" demeyip yeniden deneme
   - **GPS kurtarma:** konum belirsizliği 25 m'yi aşan İHA görevini bırakıp son GPS aldığı noktaya
     döner, konumu düzelince geri gelir (her yer karıştırılıyorsa denemez)
   - konum belirsizliğinin zaman maliyetini (beklenen arama süresi) tekliflere katma
   - teklifi konumuyla tutarsız olan İHA'ya güvenmeme (**makullük kontrolü**, sahte bilgiye karşı)

### Otonom karar alma (`suru/decision.py`)
- **Görev değeri ve aciliyet:** Her hedefin bir önceliği (1-3) vardır, değeri beklendikçe azalır:
  `ödül = değer · 0.99^(varış − görünme)`. Görev puanı (0-100) = alınan ödül / toplam değer.
- **Yeni beliren hedefler:** Görev sırasında yeni hedefler belirir. Yer istasyonu ihbarı (radyo
  bağlantısı varsa) ya da yakından geçen İHA'nın sensörü (120 m) ile öğrenilir, dedikoduyla yayılır.
- **CBBA (Consensus-Based Bundle Algorithm, Choi ve ark. 2009):** Her İHA 3 görevlik bir **paket**
  planlar. Her adımda rotasına en çok değer katan görevi en uygun sıraya ekler (geciktirdiği görevlerin
  kaybı düşülür). Komşular kazanan listelerini değiş tokuş eder; Choi'nin uzlaşma kuralları zaman
  damgalarına bakıp hangi bilginin daha yeni olduğuna karar verir. Teklifi geçilen İHA o görevi ve
  paketinde ondan sonra gelenleri bırakır. Yakınsama için teklifler "bükülür" (azalan marjinal kazanç).
- **SGA (merkezi):** Yer istasyonu her saniye tüm (İHA, görev) çiftleri içinden en büyük kazancı
  vereni sırayla atar. Bağlantı tamken CBBA ile aynı kaliteye yakınsar.
- **Açgözlü tek görev (eski yöntem):** Her İHA en yakın tek görevi açık artırmayla alır. Karşılaştırma
  için korunmuştur (`--planner greedy`).
- **Dinamik yeniden planlama:** Yeni hedef belirince, bir İHA düşünce (sessizliği teklif süresini
  aşınca) ya da bir İHA daha iyi teklif verince paketler kendiliğinden yeniden kurulur.
- **Yapay zekâ (`--planner ai`):** Küçük bir sinir ağı (8 girdi → 8 gizli nöron → 1 çıktı) her İHA-görev
  çifti için **görev başarı olasılığını** kestirir. CBBA da **beklenen ödülü** (olasılık × değer × zaman
  azalması) en büyütür. Girdiler: görev ve yol karıştırma bölgesinde mi, İHA'nın GPS'i ve konum
  belirsizliği, aldığı karıştırma gücü, uzaklık, görev değeri, komşu sayısı.
  Ağ **deneyimden öğrenir** (denetimli öğrenme, `tools/train_ai.py`). Sürü eğitim haritalarında
  (seed 1000+) 360 görev uçuşu yapar, her "İHA hedefe yöneldi" anı kaydedilir (~10 700 örnek), sonucu
  "buldu / bulamadı" olarak etiketlenir. Ağ geri yayılım ve Adam yöntemiyle eğitilir, doğrulama
  haritalarında erken durdurulur. Hiç görmediği test haritalarında ölçülür.
- **İlk deneme (dürüst not):** Ağı önce evrim stratejileriyle (pekiştirmeli öğrenme) doğrudan görev
  puanını artıracak şekilde eğitmeyi denedik (`tools/train_ai_es.py`). 25 kuşakta öğrenemedi. Sebepleri:
  ağın başlatılma biçimi (düzeltildi) ve görev puanının koşudan koşuya oynamasının görev
  değerlendirmenin etkisinden büyük olması. Başarı olasılığını kestirmek çok daha güçlü bir öğrenme sinyali veriyor.

### Sürü zekâsı (`suru/swarm.py`, `suru/world.py`)
- **Görev akışı:** kalkış → düzende intikal → dağılıp görev → toplanma → düzende dönüş → iniş.
  Her İHA kendi evresine kendisi karar verir, lider yoktur.
- **Lidersiz düzen uçuşu (V, hat, kol, halka):** Her İHA, düzenin ortasındaki "sanal liderin" rota
  üzerindeki ilerlemesini tahmin eder ve komşularıyla **uzlaşır** (ortalama konsensüs):
  `s_i ← s_i + g · ortalama(s_j − s_i)`. Geride kalan olursa sanal lider yavaşlar.
  Karıştırma uzlaşmayı bozar; elektronik harbin sürü davranışına etkisi böylece doğrudan görülür.
- **Yuva ataması:** Düzen değişirken yollar kesişmesin diye yuvalar her saniye "toplam uzaklık en
  küçük" olacak şekilde **Macar algoritmasıyla** yeniden dağıtılır.
- **Reynolds kuralları:** ayrışma (yaklaşma hızını da sönümleyen çarpışma önleme), hizalanma, uyum.
  Görevde İHA'lar ±6 m'lik irtifa katmanlarında uçar.
- **Arazi takibi:** Unity'deki arazi birebir simülasyona aktarılır (4 m çözünürlüklü yükseklik
  haritası). İHA'lar 4 s ileriye bakarak tepelerden önce yükselir. GPS gidip konum kayarsa
  radar altimetre emniyeti devreye girer.
- **Toplanma kararı:** Bir İHA, haberini aldığı tüm arkadaşları toplanma noktasına gelmeden
  dönüşe geçmez; görevi süren arkadaşını bekler (dedikoduyla yayılan sürü durum tablosu).
- **Üye kaybı:** Düşen İHA'nın görevleri teklif süresi dolunca diğerlerine geçer; düzen kalan
  İHA'larla yeniden kurulur.
- **Bağlantı koruma rölesi (isteğe bağlı, `--relay`):** Kopan arkadaş varsa, herkes aynı bilgiyle
  aynı seçimi yapar ve en uygun İHA aradaki noktaya giderek röle olur.

### Ölçülen metrikler
Görev tamamlama oranı, **görev puanı** (zamanla azalan görev değerleri, 0-100), görev süresi (kalkış ve
intikal dahil), **yeni hedefe tepki süresi**, **görev alanında katedilen yol** (enerji göstergesi),
**yeniden planlama** (en az 2 s izlenmiş hedefin bırakılması), yanlış tamamlama (İHA bitti sandı ama
hedef görülmedi), gereksiz tekrar ziyaret, paket iletim oranı, ortalama konum hatası, sürü
bağlantılılığı (en büyük bağlı grubun oranı), düzen yuva hatası (gerçek konumla), en düşük yerden
yükseklik, yakın geçiş (iki İHA'nın 2 m'den fazla yaklaşması).

### Doğrulama
```bash
.venv\Scripts\python.exe -m pytest tests -q
```
23 otomatik test: radyo fiziği, düzen geometrisi, tam uçuş (kalkıştan inişe), arazi takibi,
karıştırmanın düzeni bozması, İHA arızası sonrası görev paylaşımı, eşleştirilmiş deney.
Karar alma için: en iyi ekleme hesabının kaba kuvvetle aynı sonucu vermesi, Choi uzlaşma kuralları,
CBBA'nın çakışmasız ve ortak plana yakınsaması, CBBA'nın açgözlü yöntemden iyi olması, yeni ve
elle eklenen hedeflerin yapılması, sahte teklife dayanıklılık, yapay zekâ ağı.

---

## 3. Deneyler

```bash
.venv\Scripts\python.exe run_experiments.py
```
```bash
.venv\Scripts\python.exe run_experiments.py --swarm
```
```bash
.venv\Scripts\python.exe tools/train_ai.py
```
```bash
.venv\Scripts\python.exe run_experiments.py --decision
```
```bash
.venv\Scripts\python.exe analyze.py
```

- **Ana deney:** 3 strateji × 4 karıştırıcı gücü (kapalı, 10, 20, 30 dBm) × 2 saldırgan oranı
  (%0, %20) × 30 tekrar = **720 simülasyon** (~20 dakika, 8 işlem).
- **Sürü deneyleri (`--swarm`):** üye kaybı (0/2/4 İHA düşer) ve röle (menzil 180 m, açık/kapalı)
  = **660 simülasyon**.
- **Karar alma deneyleri (`--decision`):** her uçuşta 6 yeni hedef belirir. 3 strateji × planlama
  algoritması (açgözlü / CBBA / dirençlide ayrıca yapay zekâ ve kuralsız kontrol) × 5 koşul
  (karıştırma yok, 20 dBm, 30 dBm, %20 saldırgan, 20 dBm + 3 arıza) × 30 tekrar, ayrıca paket
  büyüklüğü 1/2/3/4/6 = **1500 simülasyon**.
- **Yapay zekâ eğitimi (`tools/train_ai.py`):** 570 uçuştan ~17 000 görev denemesi (eğitim / doğrulama /
  test haritaları ayrı). Deney haritalarından (seed 0-29) da ayrı.
- Aynı tohum (seed) = aynı görev haritası olduğu için stratejiler birebir aynı koşulda
  karşılaştırılır (eşleştirilmiş deney → Wilcoxon testi).

Çıktılar: `results/results.csv`, `results/swarm.csv`, `results/decision.csv`, `results/ai_egitim.txt`,
`results/figures/*.png`, `results/istatistik.txt`

### Öne çıkan bulgular: elektronik harp (görev tamamlama oranı, ortalama ± std, n=30)

| Koşul | Merkezi | Merkeziyetsiz | **Dirençli** |
|---|---|---|---|
| Karıştırıcı yok | %100 | %100 | **%100** |
| 10 dBm karıştırma | %99,5 ± 1,5 | %99,7 ± 1,3 | **%100** |
| 20 dBm karıştırma | %88,8 ± 6,1 | %88,7 ± 6,1 | **%99,8 ± 0,9** |
| 30 dBm karıştırma | %12,5 ± 7,7 | %17,3 ± 10,1 | **%57,7 ± 18,8** |
| %20 saldırgan, karıştırma yok | %20,2 ± 3,8 | %0,0 | **%100** |
| %20 saldırgan + 20 dBm | %22,2 ± 6,9 | %0,0 | **%99,8 ± 0,9** |
| 20 dBm + görevde 4 İHA düşer | %87,3 ± 9,9 | %90,0 ± 5,3 | **%100** |

- **20 dBm, 30 dBm ve saldırgan koşullarında** dirençli sürü diğer ikisinden anlamlı şekilde iyi
  (Wilcoxon, hepsinde p < 10⁻⁵). 10 dBm'de fark anlamsız (sistemler zaten dayanıklı).
- **20 dBm'de dirençli sürü hem daha başarılı hem daha hızlı:** görev süresi 117 s, diğerleri 155-159 s.
  Yanlış "bitti" sayısı 0 (diğerlerinde 2,5-3,1).
- **30 dBm'de** bütün alan karıştırılıyor ve GPS kalkıştan itibaren yok. Merkezi ve korumasız sürüler
  %12-17'de kalırken dirençli sürü %57,7'ye ulaşıyor (p < 10⁻⁵). Bunu sağlayanlar: arama ile "görmeden
  bitti dememe" ve 15 m'lik kamera taramasına göre ayarlanmış spiral. Düzenini koruyan tek sürü de o:
  gerçek yuva hatası 26 m, diğerlerinde 129-140 m (işbirlikçi konum düzeltmesi).
- **Saldırı altında korumasız merkeziyetsiz sürü tamamen çöküyor (%0)**, merkezi mimariden bile kötü.
  Merkeziyetsizlik tek başına yetmiyor, **güven mekanizması** şart.
- **Üye kaybı:** Karıştırma yokken 4 İHA düşse bile üç mimari de görevlerin hepsini bitiriyor. Görev
  süresi merkezide 96 → 126 s, merkeziyetsizde 96 → 119 s, dirençlide 96 → 116 s uzuyor. 20 dBm'de
  4 İHA düşünce de dirençli sürü %100 bitiriyor.
- **Röle:** Kısa menzilde (180 m) bağlantılılığı %74'ten %81'e çıkarıyor (p < 0,001) ama görevi
  64-72 s uzatıyor (röle İHA paketini bırakıp görev yapamıyor). Görevler zaten %100 bitiyor; röle,
  sürekli bağlantı gereken görevlerde (canlı video gibi) anlamlı. Bu bir **ödünleşim** olarak raporlanmalı.
- **Bedel:** Dirençli sürü zayıf karıştırmada (10 dBm) biraz yavaş: 115 s, diğerleri 96-97 s. Karıştırma
  algısı oradaki görevlere teklif süresini uzatıyor ve konumdan emin olmayan İHA hedefte arama yapıyor.

### Öne çıkan bulgular: otonom karar alma (görev puanı 0-100, n=30, 6 yeni hedef)

| Koşul | Mimari | Açgözlü | **CBBA** | Fark (p) |
|---|---|---|---|---|
| Karıştırma yok | Merkezi (SGA) | 73,4 | **82,9** | +9,6 (p < 10⁻⁸) |
| Karıştırma yok | Merkeziyetsiz | 75,7 | **79,6** | +3,9 (p < 10⁻⁶) |
| Karıştırma yok | Dirençli | 75,7 | **79,7** | +4,0 (p < 10⁻⁷) |
| 20 dBm | Merkezi (SGA) | 59,1 | **67,7** | +8,6 (p < 10⁻⁶) |
| 20 dBm | Dirençli | 71,2 | **76,7** | +5,5 (p < 10⁻⁸) |
| 30 dBm | Dirençli | 13,7 | **19,4** | +5,7 (p = 0,005) |
| %20 saldırgan | Dirençli | 71,6 | **76,7** | +5,1 (p < 10⁻⁶) |
| 20 dBm + 3 arıza | Dirençli | 65,5 | **70,7** | +5,3 (p < 10⁻⁶) |

- **CBBA paket planlama**, açgözlü tek görev yöntemine göre görev puanını her mimaride ve
  karıştırma altında da anlamlı artırıyor. Karıştırma yokken görev alanında katedilen yol 6,2 km'den
  5,1 km'ye, görev süresi 121 s'den 110 s'ye iniyor. Merkezi SGA'da kazanç en büyük (yol 8,1 → 5,1 km).
  Tek istisna, korumasız merkeziyetsiz sürünün 30 dBm'de zaten çöktüğü durum (fark anlamsız).
- **Yeni hedefe tepki:** Karıştırma yokken yeni beliren hedefe ortalama varış süresi merkezide 29 → 13 s,
  dirençlide 21 → 18 s.
- **Paket büyüklüğü:** 1 görevlik paketten 3'e çıkınca puan anlamlı artıyor (karıştırma yok +2,1;
  20 dBm +3,7 puan, p < 10⁻⁵). 3'ten sonrası düz. Kullanılan değer 3.
- **Yeniden planlama:** CBBA'da bir İHA uçuş başına ~10-18 kez yarım kalan hedefini bırakıyor:
  yeni hedef beliriyor, daha yakın bir arkadaş teklifi geçiyor ya da biri düşüyor.
  Bu, dinamik ortama uyumun bedeli; açgözlü yöntem hiç değiştirmiyor ama daha kötü sonuç alıyor.
- **Yapay zekâ:** Görev başarısını uzman kuralından daha iyi tahmin ediyor. Test haritalarında ROC AUC
  0,960, uzman kuralında 0,923. 25 dBm'de 0,921'e 0,839, 30 dBm'de 0,795'e 0,737. Kestirimleri
  iyi kalibre: 25 dBm'de gerçek başarı %70,0, kestirim %69,8. Görev puanına etkisi ise sınırlı.
  Karıştırma yokken +0,6 puan (p = 0,011), %20 saldırganla +1,5 puan (p < 10⁻⁴) anlamlı iyi.
  20 dBm, 30 dBm ve arızada uzman kuralından farkı anlamsız. Sebep: görev değerlendirmenin puana
  etkisi küçük. Uzman kuralının kuralsız CBBA'ya üstünlüğü bile yalnızca 20 dBm'de anlamlı
  (+1,1 puan). Sürüyü dayanıklı yapan şey değerlendirme değil davranış kuralları (GPS kurtarma,
  arama, makullük kontrolü).
- **Yapay zekâ ne öğrendi** (`results/figures/ai_ne_ogrendi.png`): Konum belirsizliği 12 m'yi aşınca
  uzman kuralı başarı şansını 0,3'e kadar düşürüyor. Ağ ise spiral arama sayesinde başarının ~%80
  sürdüğünü öğrenmiş (uzman kuralı fazla kötümser). Karıştırma bölgesindeki göreve uzman kuralı
  herkese ceza veriyor. Ağ ise "İHA'nın şu an GPS'i varsa oraya gidip başarır" diyor.

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

- Radyo modeli istatistiksel bir yaklaşımdır: çok yollu yayılım ve arazi gölgelemesi yoktur
  (tepeler İHA'ların uçuşunu etkiler ama sinyali henüz kesmez).
- Uçuş dinamiği nokta-kütle modelidir (ivme ve hız sınırlı). Motor ve aerodinamik modellenmemiştir.
- Karıştırma **yalnızca yazılımda** modellenmiştir. Gerçek RF yayını yapılmamıştır ve yapılmamalıdır.
- Sonuçlar simülasyon ortamına aittir. Gerçek uçuş testiyle doğrulanmamıştır.
- Sürü durum tablosu ve yuva ataması "herkes aynı bilgiyle aynı hesabı yapar" varsayımına dayanır;
  bilgiler farklıysa iki İHA aynı yuvayı seçebilir (ayrışma kuralı çarpışmayı önler).
- İHA'lar uzaktan görünsün diye 3D sahnede 3 kat büyük çizilir; bilimsel hesaplar gerçek boyutla yapılır.
- CBBA'da İHA'lar konumları değiştikçe tekliflerini günceller. Bu, klasik CBBA'nın yakınsama
  ispatının dışındadır. Pratikte yeni hedef belirdiğinde 0,2-1 s süren kısa "teklif savaşları" görülür
  (uzlaşma bunları hep çözdü, testler çakışmasız plana yakınsamayı doğruluyor).
- Makullük kontrolü yalnızca gönderenin o turda kendi adına verdiği teklifleri denetler. Zaman damgasıyla
  oynayan daha kurnaz bir saldırgan bunu atlatabilir (sıradaki aşamada güven sistemiyle ele alınacak).
- Yapay zekâ bu simülatörün verisiyle eğitildi. Gerçek İHA'da yeniden eğitilmesi gerekir. Görev puanına
  katkısı küçük; asıl katkısı başarıyı daha doğru tahmin etmesi.

---

## 6. Klasör yapısı

```
suru/                 Python simülasyon paketi (config, radio, world, decision, swarm, terrain, bridge)
suru/data/            Unity'den aktarılan arazi yükseklik haritası, eğitilmiş yapay zekâ ağırlıkları
tests/                Otomatik doğrulama testleri (pytest)
run_live.py           Unity'ye canlı yayın
run_experiments.py    Toplu deney
analyze.py            Grafik ve istatistik
results/              Deney çıktıları
gorseller/            Sunum ve rapor için ekran görüntüleri
RAPOR_ISKELETI.md     TÜBİTAK 2204 rapor iskeleti (sayılar ve kaynaklar)
blender/              Blender model betikleri
tools/                Doku üretici, Unity eşitleme, kare dökümü, yapay zekâ eğitimi (train_ai.py)
unity/Assets/SuruIHA/ Unity C# scriptleri (asıl kopya burada, sync_unity.ps1 projeye kopyalar)
```
