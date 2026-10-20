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
- Soru: Karar alma mimarisi (merkezi / merkeziyetsiz / EH dirençli merkeziyetsiz) karıştırma ve sahte bilgi altında görev başarısını nasıl etkiler?
- Hedef: Elektronik harp koşullarında görev başarısını koruyan, lidersiz bir sürü karar alma yöntemi geliştirmek ve bunu simülasyonda ölçmek.

## Giriş
- Sürü robotiğinin kısa tarihi: Reynolds'ın Boids modeli (1987), sürü İHA'larının bugünkü kullanım alanları (arama-kurtarma, keşif, tarım).
- Görev paylaşımı: merkezi ve dağıtık yaklaşımlar; konsensüs tabanlı açık artırma (CBBA, Choi vd. 2009).
- Elektronik harp: haberleşme karıştırma (jamming), GPS karıştırma ve aldatma (spoofing); SINR kavramı.
- Literatürdeki boşluk: Çalışmaların çoğu ya görev paylaşımını ya da karıştırmayı ayrı inceliyor. Bu projede ikisi birlikte, aynı deney düzeninde karşılaştırılıyor.
- **Hipotez:** Karıştırma algısı, ortak karıştırma haritası, işbirlikçi konumlama ve makullük kontrolüyle güçlendirilmiş merkeziyetsiz sürü, karıştırma ve aldatma altında merkezi ve korumasız merkeziyetsiz mimarilerden anlamlı olarak daha yüksek görev tamamlama oranına ulaşır.

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
4. **Radyo modeli:** 2,4 GHz log-mesafe yol kaybı `PL(d) = 40 + 25·log10(d)`. SINR → paket kaybı lojistik eğrisi. Formülü rapora yaz ve ne anlama geldiğini açıkla.
5. **Elektronik harp modeli:** Karıştırıcı (0/10/20/30 dBm), GPS kesilme eşiği (−80 dBm), IMU sapması (`σ² = σ0² + q²t³/3`), sahte teklif yayan ele geçirilmiş İHA'lar (%20).
6. **Karşılaştırılan üç mimari:** Her birini bir paragrafla anlat. Dirençli mimarinin altı mekanizmasını madde madde yaz (README §2).
7. **Deney tasarımı:**
   - Ana deney: 3 strateji × 4 güç × 2 saldırgan oranı × 30 tekrar = 720 koşu.
   - Üye kaybı deneyi: 3 strateji × 2 güç × 0/2/4 düşen İHA × 30 tekrar = 540 koşu.
   - Röle deneyi: 2 strateji × röle açık/kapalı × 30 tekrar, haberleşme menzili 180 m = 120 koşu.
   - Aynı tohumda aynı görev haritası kullanıldı (eşleştirilmiş tasarım).
8. **Ölçütler:** Görev tamamlama oranı, görev süresi (kalkış ve intikal dahil), yanlış tamamlama, tekrar ziyaret, paket iletim oranı, konum hatası, sürü bağlantılılığı (en büyük bağlı grubun oranı), düzen yuva hatası, en düşük yerden yükseklik, yakın geçiş sayısı.
9. **Doğrulama:** `tests/test_suru.py` içinde 14 otomatik test var (radyo fiziği, düzen geometrisi, tam uçuş, arazi takibi, arıza). Raporda "simülatörün doğru çalıştığını nasıl kontrol ettin?" sorusunun cevabı bu.
10. **İstatistik:** Kruskal-Wallis (3 grup), Wilcoxon işaretli sıralar testi (eşleştirilmiş), α = 0,05. Neden parametrik olmayan test seçtiğini açıkla: veriler normal dağılmıyor ve tavan etkisi var (%100).
11. **Görselleştirme:** Unity HDRP. Python, UDP üzerinden saniyede 30 kare yollar; modeller Blender'da kodla üretildi.

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
Grafikleri `results/figures/` klasöründen koy (özellikle `completion_saldirgan0.png` ve `completion_saldirgan20.png`).

**Tablo 1: Görev tamamlama oranı** (ortalama ± standart sapma, n = 30)

| Koşul | Merkezi | Merkeziyetsiz | Dirençli | Wilcoxon p (Dirençli vs en iyi diğer) |
|---|---|---|---|---|
| Karıştırma yok | %100 | %100 | %100 | – |
| 10 dBm | %99,2 ± 1,9 | %99,7 ± 1,3 | %99,8 ± 0,9 | 0,32 (anlamsız) |
| 20 dBm | %86,8 ± 8,7 | %88,0 ± 5,8 | %99,0 ± 2,0 | 2,3·10⁻⁶ |
| 30 dBm | %4,2 ± 4,7 | %16,8 ± 11,4 | %20,7 ± 14,8 | 0,096 (anlamsız) |
| %20 saldırgan | %17,0 ± 4,1 | %0,0 | %100 | 1,1·10⁻⁶ |
| %20 saldırgan + 20 dBm | %23,0 ± 5,3 | %0,0 | %98,8 ± 2,5 | 1,2·10⁻⁶ |

**Tablo 2: Sürü davranışı**

| Ölçüt | Merkezi | Merkeziyetsiz | Dirençli |
|---|---|---|---|
| Düzen yuva hatası, karıştırma yok | 5,8 m | 3,8 m | 3,8 m |
| Düzen yuva hatası, 30 dBm | 134,6 m | 123,4 m | 26,2 m |
| Görev süresi, 4 İHA düştü (karıştırma yok) | 152 s (130'dan) | 121 s (113'ten) | 121 s (113'ten) |
| Tamamlama, 20 dBm + 4 İHA düştü | %86,5 | %84,5 | %98,3 |

**Tablo 3: Röle** (menzil 180 m): bağlantılılık %80 → %85 (p < 0,001), görev süresi +23-27 s (p < 0,001).

Yorumlaman gereken noktalar:
- Zayıf karıştırmada (10 dBm) fark yok. Bu beklenen bir sonuç: sistemler zaten dayanıklı.
- 20 dBm'de diğer iki mimari "yanlış tamamlama" yaşıyor (GPS'i kesilen İHA hedefi görmeden bitti sanıyor). Dirençli sürü spiral arama ve "görmeden bitti deme" kuralıyla bunu sıfıra indiriyor.
- 30 dBm'de bütün alan karıştırılıyor ve GPS tüm görev boyunca yok; hiçbir yöntem başarılı değil. Dirençli sürünün tamamlama farkı anlamsız ama **düzenini koruyabilen tek sürü** (işbirlikçi konumlama). Bu, "dirençli sürü her durumda üstün" demeni engeller; dürüstçe yaz.
- En çarpıcı bulgu: Korumasız merkeziyetsiz sürü saldırgana karşı **tamamen çöküyor** (%0). Merkeziyetsizlik tek başına güvenlik sağlamıyor; güven/makullük kontrolü şart.
- Lidersiz sürü üye kaybına merkeziden daha az duyarlı: 4 İHA düşünce görev süresi merkezide 22 s, merkeziyetsizde 8 s uzuyor.
- Röle bir ödünleşim: bağlantıyı artırıyor ama bir İHA'yı görevden alıyor.
- Dirençli sürünün bedeli: karıştırma altında görev daha uzun sürüyor (20 dBm'de 202 s; diğerleri 176-190 s). Bunu dürüstçe tartış.

## Sonuç ve Tartışma
- Hipotez desteklendi mi? (Evet, 20 ve 30 dBm ile saldırgan koşullarında p < 0,001.)
- Hangi mekanizma en çok katkı sağladı? İstersen tek tek kapatıp deneyerek bir "ablasyon" çalışması ekleyebilirsin. Bu jüride çok iyi izlenim bırakır.
- Sınırlılıklar: istatistiksel radyo modeli, nokta-kütle dinamiği, gerçek uçuş testi yok, karıştırma yalnızca yazılımda (README §5).

## Öneriler
- Gerçek otopilot yazılımıyla (PX4/ArduPilot SITL) doğrulama
- Pekiştirmeli öğrenme ile karıştırmaya uyum
- Frekans atlamalı (FHSS) haberleşme modeli
- Küçük kara robotlarıyla (ESP32) fiziksel deney; paket kaybı yazılımla verilir

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

> Kaynakları rapora koymadan önce en az özetlerini oku. Jüri "bu makalede ne anlatılıyor?" diye sorabilir.
