# TÜBİTAK 2204-A Proje Raporu İskeleti

> Bu dosya bir **iskelettir**, hazır rapor değildir. Her bölümde ne anlatman gerektiği ve
> kullanabileceğin gerçek sayılar var. Cümleleri kendin kur: jüri raporu ve kodu senin
> anlayıp anlamadığını sorgular. Sayılar `results/istatistik.txt` dosyasından geliyor.
> Deneyi yeniden çalıştırırsan oradan güncelle.

**Proje adı:** Sürü İHA'larda Otonom Sürü Zekâsı ile Karar Alma ve Elektronik Harp Direnci

---

## Amaç
Tek paragraf. İçinde şunlar olsun:
- Problem: İHA sürüleri haberleşmeye ve GPS'e bağımlıdır; elektronik harp (karıştırma, aldatma) bu bağımlılığı hedef alır.
- Soru: Karar alma mimarisi (merkezi / merkeziyetsiz / EH dirençli merkeziyetsiz) ve görev paylaşım algoritması (açgözlü / CBBA / yapay zekâ destekli CBBA) karıştırma ve sahte bilgi altında görev başarısını nasıl etkiler?
- Hedef: Elektronik harp koşullarında görev başarısını koruyan, lidersiz bir sürü karar alma yöntemi geliştirmek ve bunu simülasyonda ölçmek.

## Giriş
- Sürü robotiğinin kısa tarihi: Reynolds'ın Boids modeli (1987), sürü İHA'larının bugünkü kullanım alanları (arama-kurtarma, keşif, tarım).
- Görev paylaşımı: merkezi ve dağıtık yaklaşımlar; konsensüs tabanlı açık artırma (CBBA, Choi vd. 2009).
- Elektronik harp: haberleşme karıştırma (jamming), GPS karıştırma ve aldatma (spoofing); SINR kavramı.
- Literatürdeki boşluk: Çalışmaların çoğu ya görev paylaşımını ya da karıştırmayı ayrı inceliyor. Bu projede ikisi birlikte, aynı deney düzeninde karşılaştırılıyor.
- **Hipotez 1:** Karıştırma algısı, ortak karıştırma haritası, işbirlikçi konumlama ve makullük kontrolüyle güçlendirilmiş merkeziyetsiz sürü, karıştırma ve aldatma altında merkezi ve korumasız merkeziyetsiz mimarilerden anlamlı olarak daha yüksek görev tamamlama oranına ulaşır.
- **Hipotez 2:** Görev değerlerinin zamanla azaldığı ve yeni hedeflerin belirdiği dinamik bir görevde, paket planlama ve uzlaşma (CBBA) açgözlü tek görev yöntemine göre anlamlı olarak daha yüksek görev puanı sağlar; deneyimden öğrenen bir yapay zekâ, görev başarısını elle yazılmış kuraldan daha iyi tahmin eder.

## Yöntem
1. **Simülasyon ortamı:** Python. Üssün 50 m kuzeyinden başlayan 660 m × 660 m görev alanı, 10 İHA, 20 görev noktası, 0,1 s zaman adımı, 5 Hz haberleşme. Arazi Unity'deki 3D araziyle birebir aynı (4 m çözünürlüklü yükseklik haritası); alanın kuzeyi 60 m'ye yükselen tepelik.
2. **Uçuş modeli:** Hız (12 m/s) ve ivme (4 m/s²) sınırlı nokta-kütle, rüzgâr türbülansı, yerden 40 m yükseklikte arazi takibi (4 s ileriye bakış + radar altimetre emniyeti), görevde ±6 m irtifa katmanları.
3. **Sürü zekâsı (başlığın "otonom sürü zekâsı" kısmı):** Bunu ayrı bir alt bölüm olarak yaz:
   - **Görev akışı:** kalkış → düzende intikal → dağılıp görev → toplanma → düzende dönüş → iniş. Her İHA kendi evresine kendi karar verir; lider yok.
   - **Lidersiz düzen uçuşu:** V, hat, kol ve halka düzenleri. Her İHA "sanal liderin" rota üzerindeki ilerlemesini tahmin eder ve komşularıyla uzlaşır: `s_i ← s_i + g · ortalama(s_j − s_i)`. Bu, ortalama uzlaşma (average consensus) algoritmasıdır. Geride kalan olursa sanal lider yavaşlar.
   - **Yuva ataması:** Düzen değişirken İHA'ların yolları kesişmesin diye yuvalar her saniye "toplam uzaklık en küçük" olacak şekilde Macar algoritmasıyla (Kuhn, 1955) yeniden dağıtılır.
   - **Reynolds kuralları:** ayrışma (çarpışma önleme, yaklaşma hızını da sönümler), hizalanma, uyum.
   - **Toplanma kararı:** Bir İHA, haberini aldığı tüm arkadaşları toplanma noktasına gelmeden dönüşe geçmez; görevi süren arkadaşını bekler.
   - **Üye kaybı:** Arızalanıp düşen İHA'nın görevleri teklif süresi dolunca diğerlerine geçer, düzen kalan İHA'larla yeniden kurulur.
   - **Bağlantı koruma rölesi (isteğe bağlı):** Kopan bir arkadaş varsa, herkes aynı bilgiyle aynı seçimi yaparak en uygun İHA'yı röle olarak aradaki noktaya gönderir.
4. **Otonom karar alma (başlığın "karar alma" kısmı):** Bunu da ayrı bir alt bölüm olarak yaz:
   - **Görev modeli:** Her hedefin önceliği (1-3) var ve değeri beklendikçe azalıyor: `ödül = değer · λ^(varış − görünme)`, λ = 0,99/s. Görev sırasında 6 yeni hedef beliriyor (yer istasyonu ihbarı ya da İHA sensörü, 120 m). Bu, "dinamik ortam" demek: plan sürekli güncellenmeli.
   - **CBBA (Choi vd. 2009):** İki evre. *Paket kurma:* her İHA rotasına en çok değer katan görevi en uygun sıraya ekler (en fazla 3 görev); eklenen görevin geciktirdiği diğer görevlerin kaybı kazançtan düşülür (marjinal kazanç). *Uzlaşma:* komşular kazanan listelerini değiş tokuş eder; zaman damgalarına göre hangi bilginin daha yeni olduğuna karar veren kural tablosu uygulanır. Teklifi geçilen İHA o görevi ve paketinde ondan sonrakileri bırakır. Yakınsamayı garanti etmek için "teklif bükme" (Johnson vd. 2012) kullanıldı. Kural tablosunu rapora koy, bir örnekle anlat.
   - **SGA (merkezi karşılık):** Yer istasyonu her saniye tüm (İHA, görev) çiftlerinden en büyük kazancı vereni sırayla atar.
   - **Karşılaştırma yöntemi:** Açgözlü tek görev açık artırması (her İHA en yakın tek görevi alır).
   - **Dinamik yeniden planlama:** Yeni hedef, İHA kaybı (sessizlik teklif süresini aşınca) ya da daha iyi teklif gelince paketler kendiliğinden yeniden kurulur.
   - **Yapay zekâ:** 8 girdili, 8 gizli nöronlu bir sinir ağı her İHA-görev çifti için **görev başarı olasılığını** kestirir; CBBA beklenen ödülü (olasılık × değer × zaman azalması) en büyütür. Ağ deneyimden öğrenir (denetimli öğrenme): sürü eğitim haritalarında (seed 1000-1059) 6 farklı karıştırma/arıza koşulunda 360 uçuş yapar, her "İHA hedefe yöneldi" anı 8 özellikle kaydedilir ve sonucu "buldu / bulamadı" diye etiketlenir (10 757 örnek). Lojistik kayıp, geri yayılım, Adam (Kingma ve Ba 2015), doğrulama haritalarında (seed 1100-1114) erken durdurma. Test (seed 1200-1219) ve plan deneyi haritaları (seed 0-29) eğitimde hiç görülmedi: ezber değil genelleme ölçülüyor. Uzman kuralıyla (dirençli strateji: karıştırma cezası + belirsizliğin zaman maliyeti) iki düzeyde karşılaştır: (1) başarıyı ne kadar iyi tahmin ediyor (ROC AUC), (2) görev puanını artırıyor mu.
   - **İlk deneme ve neden değiştirildi (tartışmada anlat):** Önce ağı evrim stratejileriyle (Salimans vd. 2017), yani pekiştirmeli öğrenmeyle doğrudan görev puanını artıracak şekilde eğittik. 25 kuşakta (yaklaşık 1800 uçuş) öğrenemedi. Sebepler: ağırlıkların sıfırdan başlatılması küçük gürültülerin kararı değiştirmesini engelliyordu, ve aynı haritada bile görev puanı koşudan koşuya ±0,02-0,04 oynuyor; görev değerlendirmenin puana etkisi bundan küçük. Bu "ödül gürültüsü" pekiştirmeli öğrenmenin bilinen zorluğudur (Sutton ve Barto 2018). Başarı olasılığını tahmin etmek her denemeden doğrudan bir öğrenme sinyali verdiği için çok daha verimli.
5. **Radyo modeli:** 2,4 GHz log-mesafe yol kaybı `PL(d) = 40 + 25·log10(d)`. SINR → paket kaybı lojistik eğrisi. **Arazi gölgesi:** görüş hattını en çok kesen tepe için ITU-R P.526 tek bıçak sırtı kırınım kaybı (`v = h·√(2d/(λd1d2))`, `J(v)` dB). Formülleri rapora yaz ve ne anlama geldiklerini bir şekille açıkla.
6. **Elektronik harp modeli (Aşama 3):** Bunu da ayrı bir alt bölüm yap:
   - **Karıştırıcılar:** geniş bant (haberleşme + GPS) ya da nokta (yalnızca haberleşme kanalı, +6,2 dB); sabit, hareketli (5 m/s devriye), iki adet ya da tepede. GPS kesilme eşiği −80 dBm, IMU sapması `σ² = σ0² + q²t³/3`.
   - **Frekans atlama (FHSS):** nokta karıştırıcı paketlerin yalnızca %24'üne denk gelir; geniş banda karşı işe yaramaz (Poisel 2011).
   - **Karıştırıcıyı bulma:** alınan güç ölçümlerinden kısıtlı en küçük kareler (güç ≤ 2 W); tek kaynak şüpheliyse k-ortalamalar başlangıçlı iki kaynak modeli. Bulunan karıştırıcıdan karıştırma alanı önceden kestirilir.
   - **GPS aldatma:** 250 m yarıçapta alıcıyı ele geçirip konumu 2 m/s (hızlı) ya da 0,5 m/s (yavaş) sürükleyen aldatıcı (Tippenhauer vd. 2011). Tespit: IMU tutarlılığı (10 s pencere, 5σ eşik), komşu menzil ölçümü ve "hedef yok" çıkarımı.
   - **Saldırgan İHA'lar (%20):** saf (her görevi ister) ya da sinsi (2 görevi makul tekliflerle kilitler, sahte "tamamlandı" yayar ve konum yalanı söyler). Savunma: Beta itibar sistemi (Jøsang ve Ismail 2002), menzil/hız/ilerleme kanıtı, iki bağımsız tanık kuralı, "tamamlandı" bilgisinin kaynağıyla yayılması ve geri alınması.
6b. **Hava savunma ve enerji (yeni tehditler):** Ayrı bir alt bölüm yap:
   - **Radar:** X bandı arama radarı, radar denklemi (`SNR ∝ R⁻⁴`), Swerling-1 tespit olasılığı `Pd = Pfa^(1/(1+SNR))`
     (Skolnik 2008), arazi gölgesi iki yönlü bıçak sırtı kırınımı, Doppler süzgeci. Son 3 taramanın 2'sinde görülen İHA
     izlenir, iz 4 s korunursa füze atılır (komut güdümlü: iz koparsa ıskalar).
   - **Radar ikaz alıcısı ve kerteriz kestirimi:** İHA radarın yönünü ölçer (±3°), ölçümler dedikoduyla yayılır; radarın yeri
     açı hatalarının karelerini en küçük yapan nokta olarak bulunur (en çok olabilirlik). Hata Fisher bilgisinden; kısa
     tabanlı (paralel) ölçümler reddedilir. Bir şekille anlat: farklı İHA'lardan çizilen kerteriz çizgileri radarda kesişir.
   - **Tehdit farkında rota:** radar görüşü 20 m'lik ızgarada çizgeye çevrilir, kenar maliyeti `uzunluk · (1 + 40·Pd)`;
     hedeften geriye Dijkstra en kısa yol ağacı (Dijkstra 1959). Risk/ödül kuralı: radarın görmediği yerden 50 m'den derine
     dalış gerektiren hedef alınmaz.
   - **Enerji:** döner kanatlı İHA güç modeli (Zeng vd. 2019), rüzgâr (ortalama + Ornstein-Uhlenbeck esintisi), hız sınırı
     havaya göre. Standart emniyet (%10'da eve dön) ile enerji farkında karar (rüzgâra karşı dönüş enerjisi) karşılaştırıldı.
7. **Karşılaştırılan üç mimari:** Her birini bir paragrafla anlat. Dirençli mimarinin mekanizmalarını madde madde yaz (README §2): karıştırma haritası, uzun TTL, bölgeden kaçınma, işbirlikçi konum, spiral arama, GPS kurtarma, güven sistemi, karıştırıcı bulma, FHSS, aldatma tespiti, görev değerlendirme. Ayrıca öngörülü çarpışma önlemeyi (CPA) sürü zekâsı bölümüne ekle.
8. **Deney tasarımı:**
   - Ana deney: 3 strateji × 4 güç × 2 saldırgan oranı × 30 tekrar = 720 koşu.
   - Üye kaybı deneyi: 3 strateji × 2 güç × 0/2/4 düşen İHA × 30 tekrar = 540 koşu.
   - Röle deneyi: 2 strateji × röle açık/kapalı × 30 tekrar, haberleşme menzili 180 m = 120 koşu.
   - Karar alma deneyi: her uçuşta 6 yeni hedef belirir. 3 strateji × açgözlü/CBBA (dirençlide ayrıca yapay zekâ ve "kural yok" kontrolü) × 5 koşul (karıştırma yok, 20 dBm, 30 dBm, %20 saldırgan, 20 dBm + 3 arıza) × 30 tekrar = 1200 koşu; paket büyüklüğü 1/2/3/4/6 × 2 koşul × 30 = 300 koşu.
   - Yapay zekâ verisi: eğitim (360 uçuş), doğrulama (90 uçuş), test (120 uçuş) haritaları birbirinden ve deney haritalarından ayrı.
   - **Elektronik harp deneyi (Aşama 3):** 8 senaryo (sabit, hareketli, iki, nokta, tepede karıştırıcı; hızlı ve yavaş GPS aldatma; %20 sinsi saldırgan) × 3 strateji × 30 tekrar = 720 koşu; ayrıca arazi gölgesi kapalı karşılaştırma (2 senaryo × 3 × 30 = 180).
   - **Parametre ayarı (Aşama 4):** dirençli stratejinin 4 parametresi (karıştırmada bekleme, GPS kurtarma eşiği, karıştırma cezası, harita unutma süresi) teker teker 3 değerde, 3 senaryoda, **ayrı ayar haritalarında** (seed 500-519) denendi = 540 koşu. Test haritaları (seed 0-29) ayar sırasında hiç kullanılmadı.
   - **Ablasyon (Aşama 4):** tam dirençli sistemden her mekanizma tek tek çıkarıldı (11 mekanizma + tam + korumasız) × 6 senaryo × 12 tekrar = 936 koşu.
   - **Ölçekleme (Aşama 4):** 5 / 10 / 20 İHA (görev = 2 × İHA) × 3 strateji × 3 koşul × 20 tekrar = 540 koşu; hesap yükü de ölçüldü.
   - **Yeni tehditler:** hava savunma (yeri bilinen radar + 80. saniyede açılan pusu radarı) ve 8 m/s lodos + karışık
     batarya × 3 strateji × 30 tekrar = 180 koşu (`run_experiments.py --threats`).
   - Aynı tohumda aynı görev haritası kullanıldı (eşleştirilmiş tasarım).
9. **Ölçütler:** Görev tamamlama oranı, **görev puanı** (yapılan görevlerin zamanla azalan değerlerinin toplamı / tüm değerler, 0-100), yeni hedefe tepki süresi, görev alanında katedilen yol, yeniden planlama sayısı, görev süresi (kalkış ve intikal dahil), yanlış tamamlama, tekrar ziyaret, paket iletim oranı, konum hatası, sürü bağlantılılığı (en büyük bağlı grubun oranı), düzen yuva hatası, en düşük yerden yükseklik, yakın geçiş sayısı.
10. **Doğrulama:** `tests/test_suru.py` içinde 23 otomatik test var (radyo fiziği, düzen geometrisi, tam uçuş, arazi takibi, arıza; karar alma için en iyi ekleme hesabının kaba kuvvetle karşılaştırılması, Choi uzlaşma kuralları, CBBA'nın çakışmasız plana yakınsaması, yeni hedeflerin yapılması, yapay zekâ ağı). Yapay zekânın geri yayılım türevleri sayısal türevle karşılaştırıldı (göreli hata 10⁻⁹). Raporda "simülatörün doğru çalıştığını nasıl kontrol ettin?" sorusunun cevabı bu.
11. **İstatistik:** Kruskal-Wallis (3 grup), Wilcoxon işaretli sıralar testi (eşleştirilmiş), α = 0,05. Neden parametrik olmayan test seçtiğini açıkla: veriler normal dağılmıyor ve tavan etkisi var (%100).
12. **Görselleştirme:** Unity HDRP. Python, UDP üzerinden saniyede 30 kare yollar; modeller Blender'da kodla üretildi.

## Proje İş-Zaman Çizelgesi
| İş | Ay 1 | Ay 2 | Ay 3 | Ay 4 |
|---|---|---|---|---|
| Literatür taraması | X | | | |
| Simülasyon ve radyo modeli | X | X | | |
| Karar alma algoritmaları | | X | | |
| EH direnç mekanizmaları | | X | X | |
| Deneyler ve istatistik | | | X | |
| 3D görselleştirme | | X | X | |
| Rapor | | | X | X |

(Kendi gerçek tarihlerine göre düzenle.)

## Bulgular
Grafikleri `results/figures/` klasöründen koy: `completion_saldirgan0.png`, `completion_saldirgan20.png`, `eh_senaryolar.png`, `eh_arazi_golgesi.png`, `karar_puan.png`, `karar_yol.png`, `paket_boyutu.png`, `ai_dogruluk.png`, `ai_ne_ogrendi.png`, `yapay_zeka.png`, `ayar_duyarlilik.png`, `ablasyon.png`, `olcekleme.png`. Bütün sayılar `results/istatistik.txt` dosyasında.

**Tablo 1: Görev tamamlama oranı** (ortalama ± standart sapma, n = 30)

| Koşul | Merkezi | Merkeziyetsiz | Dirençli | Wilcoxon p (Dirençli vs en iyi diğer) |
|---|---|---|---|---|
| Karıştırma yok | %100 | %100 | %100 | – |
| 10 dBm | %99,3 ± 2,2 | %99,7 ± 1,3 | %100 | 0,16 (anlamsız) |
| 20 dBm | %87,3 ± 7,8 | %87,5 ± 8,9 | %100 | 7,5·10⁻⁶ |
| 30 dBm | %12,3 ± 7,2 | %16,7 ± 10,5 | %66,5 ± 19,4 | 1,7·10⁻⁶ |
| %20 saldırgan | %20,7 ± 3,7 | %0,0 | %100 | 9,6·10⁻⁷ |
| %20 saldırgan + 20 dBm | %22,7 ± 7,2 | %0,0 | %100 | 1,4·10⁻⁶ |

**Tablo 2: Elektronik harp senaryoları** (tamamlama, n = 30, her uçuşta 6 yeni hedef; dirençli diğerlerinden hepsinde p < 10⁻⁶)

| Senaryo | Merkezi | Merkeziyetsiz | Dirençli | Dirençlinin özel ölçüsü |
|---|---|---|---|---|
| Sabit 20 dBm | %86,9 | %89,4 | %100 | karıştırıcı ~30 s'de bulunuyor, son hata 40 m |
| Hareketli 20 dBm | %83,7 | %85,9 | %100 | takip hatası ortalama 136 m |
| İki karıştırıcı 20 dBm | %40,4 | %39,4 | %99,5 | ortalama hata 362 m (zor) |
| Nokta 25 dBm | %74,5 | %99,9 | %100 | frekans atlama |
| Tepede 25 dBm | %73,7 | %79,0 | %100 | |
| Sırt arkasında 30 dBm | %91,5 | %92,1 | %100 | arazi kalkanı (Tablo 3) |
| GPS aldatma hızlı | %51,9 | %50,5 | %98,6 | tespit 9,4 s, yanlış alarm 0,03/uçuş |
| GPS aldatma yavaş | %61,2 | %61,4 | %99,1 | tespit 52 s |
| Sinsi saldırgan %20 | %32,4 | %86,8 | %100 | saldırganların %100'ü dışlandı, dürüstlerin %0,1'i |

**Tablo 3: Arazi gölgesi** (tamamlama, arazi hesaba katılınca / katılmayınca): ovadaki karıştırıcıda fark yok. Sırt arkasındaki 30 dBm karıştırıcıda merkezi %91,5 / %67,4, merkeziyetsiz %92,1 / %64,6, dirençli %100 / %99,9 (puan farkı p < 10⁻⁷).

**Tablo 4: Sürü davranışı**

| Ölçüt | Merkezi | Merkeziyetsiz | Dirençli |
|---|---|---|---|
| Düzen yuva hatası, karıştırma yok | 5,9 m | 3,8 m | 3,8 m |
| Düzen yuva hatası, 30 dBm | 145,4 m | 125,8 m | 38,7 m |
| Görev süresi, 20 dBm | 169 s | 145 s | 113 s |
| Görev süresi, 4 İHA düştü (karıştırma yok) | 124 s (95'ten) | 116 s (97'den) | 118 s (97'den) |
| Tamamlama, 20 dBm + 4 İHA düştü | %86,2 | %88,3 | %100 |

Röle (menzil 180 m): bağlantılılık %74-75 → %81 (p < 10⁻⁵), görev süresi +69-74 s.

**Tablo 5: Otonom karar alma, görev puanı** (0-100, ortalama, n = 30, her uçuşta 6 yeni hedef)

| Koşul | Mimari | Açgözlü tek görev | CBBA | Wilcoxon p |
|---|---|---|---|---|
| Karıştırma yok | Merkezi (SGA) | 73,3 | 83,0 | < 10⁻⁸ |
| Karıştırma yok | Merkeziyetsiz | 75,5 | 79,6 | < 10⁻⁶ |
| Karıştırma yok | Dirençli | 75,4 | 79,5 | < 10⁻⁶ |
| 20 dBm | Merkezi (SGA) | 58,5 | 66,9 | < 10⁻⁷ |
| 20 dBm | Merkeziyetsiz | 63,9 | 70,6 | < 10⁻⁵ |
| 20 dBm | Dirençli | 72,5 | 77,8 | < 10⁻⁷ |
| 30 dBm | Dirençli | 24,5 | 26,8 | 0,17 (anlamsız) |
| %20 saldırgan | Dirençli | 71,5 | 77,0 | < 10⁻⁷ |
| 20 dBm + 3 arıza | Dirençli | 69,8 | 73,5 | < 10⁻⁴ |

Ek: karıştırma yokken katedilen yol dirençlide 6,3 → 5,2 km, merkezide 8,1 → 5,1 km; yeni hedefe varış merkezide 29 → 13 s. Paket büyüklüğü 1 → 3: +1,7 puan (karıştırma yok), +3,1 puan (20 dBm), p < 10⁻³; 3'ten sonrası düz.

**Tablo 6: Yapay zekâ** (dirençli strateji, CBBA)

| | Uzman kuralı | Yapay zekâ |
|---|---|---|
| Başarı tahmini, ROC AUC (test haritaları) | 0,948 | 0,978 |
| ROC AUC, 25 dBm / 30 dBm | 0,914 / 0,760 | 0,966 / 0,880 |
| Doğruluk ("hep başarır" demek %73,2) | – | %92,8 |
| Görev puanı, karıştırma yok | 79,5 | 80,1 (p = 0,017) |
| Görev puanı, %20 saldırgan | 77,0 | 77,9 (p = 0,002) |
| Görev puanı, 20 dBm / 30 dBm / 20 dBm + arıza | 77,8 / 26,8 / 73,5 | 77,7 / 26,2 / 73,3 (anlamsız) |

**Tablo 7: Ablasyon** (mekanizma kapatılınca görev puanı farkı, n = 12; yalnızca anlamlı olanlar, p < 0,05)

| Mekanizma | Hangi tehditte önemli |
|---|---|
| Spiral arama | hızlı GPS aldatma −26,7; 30 dBm −14,1; hareketli −6,8; sabit 20 dBm −5,9 |
| Aldatma tespiti | hızlı GPS aldatma −19,3 |
| İşbirlikçi konum | hızlı GPS aldatma −16,6 |
| Karıştırıcı bulma | 30 dBm −16,0; hareketli −3,4; nokta −1,4 |
| Güven sistemi | sinsi saldırgan −6,5 |
| Uzun TTL | hareketli −1,9 |
| Bölgeden kaçınma | sabit 20 dBm **+1,4** (kapatınca daha iyi!) |
| Hepsi (korumasız) | −6,1 ile −27,5 arası, hepsi p < 0,001 |

**Parametre ayarı:** 4 parametre ayrı ayar haritalarında (seed 500-519) tarandı; hiçbir alternatif kullanılan değerden anlamlı iyi değil (fark ≤ 0,6 puan, p ≥ 0,31). Sonuçlar parametre seçimine duyarsız.

**Tablo 8: Ölçekleme** (tamamlama / puan, n = 20, görev = 2 × İHA)

| Koşul | İHA | Merkezi | Merkeziyetsiz | Dirençli |
|---|---|---|---|---|
| 20 dBm | 5 | %90,3 / 67,4 | %92,2 / 67,2 | %100 / 73,0 |
| 20 dBm | 10 | %86,2 / 66,4 | %90,0 / 70,3 | %100 / 76,7 |
| 20 dBm | 20 | %86,4 / 66,4 | %81,1 / 65,1 | %100 / 78,5 |
| %20 saldırgan | 5 / 10 / 20 | ~%30-35 | %0 | %100 (puan 70,8 / 76,7 / 79,2) |

Hesap yükü İHA sayısıyla yaklaşık doğrusal artıyor (dirençli: 66 → 111 → 208 ms / simülasyon saniyesi).

Yorumlaman gereken noktalar:
- Zayıf karıştırmada (10 dBm) tamamlamada fark yok; bu beklenen bir sonuç.
- 20 dBm'de diğer iki mimari "yanlış tamamlama" yaşıyor; dirençli sürü spiral arama ve "görmeden bitti deme" kuralıyla bunu sıfıra indiriyor ve üstelik daha hızlı bitiriyor.
- 30 dBm'de bütün alan GPS'siz; dirençli sürü %66,5 ile diğerlerinin 4-5 katı ama görevlerin üçte biri yine yapılamıyor. "Her durumda üstün" deme, sınırını dürüstçe yaz.
- **GPS aldatma** en yıkıcı saldırılardan biri: korumasız İHA'lar "GPS sağlam" sandıkları için hedefe vardıklarını zannediyor (uçuş başına 10-13 yanlış "bitti"). Üç tespit yolu birlikte çalışıyor; yavaş sürükleme IMU'yu atlatıyor ama "hedef yok" çıkarımına takılıyor.
- **Sinsi saldırgan** ilginç bir ödünleşim gösteriyor: saf saldırgan korumasız sürüyü tamamen çökertirken (%0), sinsi saldırgan daha az zarar veriyor (%87) ama fark edilmiyor. Güven sistemi ikisini de dışlıyor.
- **Arazi kalkanı:** sırt arkasındaki karıştırıcıya karşı tepeler korumasız sürüleri %65-67'den %92'ye taşıyor. Bu, arazi modelinin sonucu değiştirdiğini ve gerçekçi modellemenin önemini gösteriyor.
- **Karar alma:** paket planlama (CBBA) her mimaride anlamlı iyi; ama iyi bir algoritma kötü bir haberleşme mimarisini kurtarmıyor (20 dBm'de merkezi SGA 66,9, dirençli CBBA 77,8).
- **Yapay zekâ:** başarıyı daha iyi tahmin ediyor ama puana katkısı küçük; çünkü görev değerlendirmenin puana etkisi zaten küçük (uzman kuralı bile kuralsızdan anlamlı farklı değil). Asıl farkı davranış kuralları yaratıyor; ablasyon bunu doğruluyor.
- **Ablasyon:** her tehdide karşı farklı mekanizmalar önemli; tek bir "sihirli" mekanizma yok, dayanıklılık birbirini tamamlayan mekanizmalardan geliyor. "Bölgeden kaçınma"nın zararlı çıkması dürüst bir bulgu: fazla temkinli kural yolu uzatıyor.
- **Ölçekleme:** dirençli sürü İHA sayısı arttıkça daha iyi; korumasız sürü 20 İHA'da karıştırma altında kötüleşiyor (kalabalık ağda karıştırılan bağlantı sayısı artıyor).
- İlk yapay zekâ denemesinin (evrim stratejileri) başarısızlığını ve yöntemi neden değiştirdiğini anlat; jüri araştırma sürecini görmek ister.
- **Hava savunma:** korumasız sürüler radarın şemsiyesine girip uçuş başına 5 İHA kaybetti (10 İHA'dan); dirençli sürü 0,7
  (Wilcoxon p < 0,00001). Pusu radarı açılışından ortalama 4 s sonra ~33 m hatayla bulundu. Bedeli: dirençli sürü şemsiyenin
  tam altındaki hedefleri bilerek bıraktı (%65,7 tamamlama). Bunu bir risk/ödül kararı olarak tartış: hedefin değeri ile
  İHA'nın değeri arasındaki oran değişirse doğru karar da değişir.
- **Enerji:** sabit %10 emniyeti rüzgârı bilmediği için korumasız sürülerde uçuş başına 0,9-1,3 İHA eve varamadan düştü;
  enerji farkında sürüde hiç düşmedi, hedeflerin hepsi yapıldı. Görev puanı biraz düştü (düşük bataryalı İHA erken döndü).
- **Tasarım süreci (dürüstçe anlat):** radar riskini görev değerine katmak İHA'ların biraz farklı tehdit haritaları yüzünden
  uzlaşmayı (CBBA) salındırdı; kesin bir kurala (kısa dalış) geçildi. Kerteriz kestiriminde ilk yöntem (çizgilere dik uzaklık,
  ağırlıklı en küçük kareler) birbirine yakın ölçümlerde radarı yüzlerce metre yanlış yere koyup "eminim" diyordu; en çok
  olabilirlik ızgarası ve Fisher bilgisiyle hata payı doğru hesaplanınca bu kestirimler reddedildi.

## Sonuç ve Tartışma
- Hipotez 1 desteklendi mi? (Evet: 20 dBm, 30 dBm, hareketli/iki/tepede karıştırıcı, GPS aldatma ve saldırgan koşullarında dirençli sürü anlamlı üstün, p < 10⁻⁶.)
- Hipotez 2 desteklendi mi? (CBBA kısmı evet, 30 dBm hariç. Yapay zekâ kısmı tahmin düzeyinde evet, görev puanı düzeyinde yalnızca bazı koşullarda.)
- Hangi mekanizma en çok katkı sağladı? Ablasyon tablosunu yorumla: spiral arama ve "görmeden bitti dememe" neredeyse her EH tehdidinde en önemlisi.
- Sınırlılıklar: istatistiksel radyo modeli, nokta-kütle dinamiği, gerçek uçuş testi yok, karıştırma yalnızca yazılımda, karıştırıcı bulma araziyi hesaba katmıyor, GPS aldatma modeli basit, yapay zekâ simülatör verisiyle eğitildi (README §5).

## Öneriler
- Gerçek otopilot yazılımıyla (PX4/ArduPilot SITL) doğrulama
- Karıştırıcı bulmaya arazi gölgesini eklemek (sırt arkasındaki karıştırıcı için)
- Hareketli karıştırıcıyı hız modeliyle izlemek (Kalman süzgeci)
- Pekiştirmeli öğrenmeyi daha fazla hesaplama gücüyle davranış kararlarına (ne zaman aramayı bırakmalı, ne zaman konum düzeltmeye dönmeli) uygulamak; ablasyon bu kararların puana etkisinin büyük olduğunu gösteriyor
- "Bölgeden kaçınma" kuralını kazanç-maliyet hesabıyla akıllandırmak
- Küçük kara robotlarıyla (ESP32) fiziksel deney; paket kaybı yazılımla verilir
- Hava savunmada hedef değeri ile İHA değerini aynı ölçüde tartan bir karar (beklenen kayıp); radarı bastırma görevi (SEAD)
- Enerjide batarya değişimi / şarj istasyonu ve rüzgârın araziyle değişmesi

## Kaynaklar
- Reynolds, C. W. (1987). Flocks, herds and schools: A distributed behavioral model. *ACM SIGGRAPH Computer Graphics*, 21(4), 25–34.
- Choi, H.-L., Brunet, L., & How, J. P. (2009). Consensus-based decentralized auctions for robust task allocation. *IEEE Transactions on Robotics*, 25(4), 912–926.
- LeBlanc, H. J., Zhang, H., Koutsoukos, X., & Sundaram, S. (2013). Resilient asymptotic consensus in robust networks. *IEEE Journal on Selected Areas in Communications*, 31(4), 766–781.
- Olfati-Saber, R. (2006). Flocking for multi-agent dynamic systems: Algorithms and theory. *IEEE Transactions on Automatic Control*, 51(3), 401–420.
- Chung, S.-J., Paranjape, A. A., Dames, P., Shen, S., & Kumar, V. (2018). A survey on aerial swarm robotics. *IEEE Transactions on Robotics*, 34(4), 837–855.
- Pelechrinis, K., Iliofotou, M., & Krishnamurthy, S. V. (2011). Denial of service attacks in wireless networks: The case of jammers. *IEEE Communications Surveys & Tutorials*, 13(2), 245–257.
- Rappaport, T. S. (2002). *Wireless Communications: Principles and Practice* (2nd ed.). Prentice Hall.
- Kuhn, H. W. (1955). The Hungarian method for the assignment problem. *Naval Research Logistics Quarterly*, 2(1–2), 83–97.
- Olfati-Saber, R., Fax, J. A., & Murray, R. M. (2007). Consensus and cooperation in networked multi-agent systems. *Proceedings of the IEEE*, 95(1), 215–233.
- Ren, W., & Beard, R. W. (2008). *Distributed Consensus in Multi-vehicle Cooperative Control*. Springer.
- Fiedler, M. (1973). Algebraic connectivity of graphs. *Czechoslovak Mathematical Journal*, 23(2), 298–305.
- Wilcoxon, F. (1945). Individual comparisons by ranking methods. *Biometrics Bulletin*, 1(6), 80–83.
- Johnson, L., Choi, H.-L., Ponda, S., & How, J. P. (2012). Allowing non-submodular score functions in distributed task allocation. *IEEE Conference on Decision and Control (CDC)*, 4702–4708.
- Salimans, T., Ho, J., Chen, X., Sidor, S., & Sutskever, I. (2017). Evolution strategies as a scalable alternative to reinforcement learning. *arXiv:1703.03864*.
- Sutton, R. S., & Barto, A. G. (2018). *Reinforcement Learning: An Introduction* (2nd ed.). MIT Press.
- Kingma, D. P., & Ba, J. (2015). Adam: A method for stochastic optimization. *International Conference on Learning Representations (ICLR)*.
- ITU-R (2019). *Recommendation P.526-15: Propagation by diffraction*. International Telecommunication Union.
- Tippenhauer, N. O., Pöpper, C., Rasmussen, K. B., & Čapkun, S. (2011). On the requirements for successful GPS spoofing attacks. *ACM Conference on Computer and Communications Security (CCS)*, 75–86.
- Jøsang, A., & Ismail, R. (2002). The Beta reputation system. *15th Bled Electronic Commerce Conference*.
- Poisel, R. A. (2011). *Modern Communications Jamming Principles and Techniques* (2nd ed.). Artech House.
- Skolnik, M. I. (2008). *Radar Handbook* (3rd ed.). McGraw-Hill. (radar denklemi, Swerling hedef modelleri)
- Dijkstra, E. W. (1959). A note on two problems in connexion with graphs. *Numerische Mathematik*, 1, 269–271.
- Zeng, Y., Xu, J., & Zhang, R. (2019). Energy minimization for wireless communication with rotary-wing UAV.
  *IEEE Transactions on Wireless Communications*, 18(4), 2329–2345.
- Uhlenbeck, G. E., & Ornstein, L. S. (1930). On the theory of the Brownian motion. *Physical Review*, 36(5), 823–841.

> Kaynakları rapora koymadan önce en az özetlerini oku. Jüri "bu makalede ne anlatılıyor?" diye sorabilir.
