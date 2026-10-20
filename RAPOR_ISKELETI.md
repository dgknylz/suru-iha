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
5. **Radyo modeli:** 2,4 GHz log-mesafe yol kaybı `PL(d) = 40 + 25·log10(d)`. SINR → paket kaybı lojistik eğrisi. Formülü rapora yaz ve ne anlama geldiğini açıkla.
6. **Elektronik harp modeli:** Karıştırıcı (0/10/20/30 dBm), GPS kesilme eşiği (−80 dBm), IMU sapması (`σ² = σ0² + q²t³/3`), sahte teklif yayan ele geçirilmiş İHA'lar (%20).
7. **Karşılaştırılan üç mimari:** Her birini bir paragrafla anlat. Dirençli mimarinin altı mekanizmasını madde madde yaz (README §2).
8. **Deney tasarımı:**
   - Ana deney: 3 strateji × 4 güç × 2 saldırgan oranı × 30 tekrar = 720 koşu.
   - Üye kaybı deneyi: 3 strateji × 2 güç × 0/2/4 düşen İHA × 30 tekrar = 540 koşu.
   - Röle deneyi: 2 strateji × röle açık/kapalı × 30 tekrar, haberleşme menzili 180 m = 120 koşu.
   - Karar alma deneyi: her uçuşta 6 yeni hedef belirir. 3 strateji × açgözlü/CBBA (dirençlide ayrıca yapay zekâ ve "kural yok" kontrolü) × 5 koşul (karıştırma yok, 20 dBm, 30 dBm, %20 saldırgan, 20 dBm + 3 arıza) × 30 tekrar = 1200 koşu; paket büyüklüğü 1/2/3/4/6 × 2 koşul × 30 = 300 koşu.
   - Yapay zekâ verisi: eğitim (360 uçuş, 10 757 deneme), doğrulama (90 uçuş), test (120 uçuş) haritaları birbirinden ve deney haritalarından ayrı.
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
Grafikleri `results/figures/` klasöründen koy: `completion_saldirgan0.png`, `completion_saldirgan20.png`, `karar_puan.png`, `karar_yol.png`, `paket_boyutu.png`, `ai_dogruluk.png`, `ai_ne_ogrendi.png`, `yapay_zeka.png`.

**Tablo 1: Görev tamamlama oranı** (ortalama ± standart sapma, n = 30)

| Koşul | Merkezi | Merkeziyetsiz | Dirençli | Wilcoxon p (Dirençli vs en iyi diğer) |
|---|---|---|---|---|
| Karıştırma yok | %100 | %100 | %100 | – |
| 10 dBm | %99,5 ± 1,5 | %99,7 ± 1,3 | %100 | 0,16 (anlamsız) |
| 20 dBm | %88,8 ± 6,1 | %88,7 ± 6,1 | %99,8 ± 0,9 | 4,5·10⁻⁶ |
| 30 dBm | %12,5 ± 7,7 | %17,3 ± 10,1 | %57,7 ± 18,8 | 2,7·10⁻⁶ |
| %20 saldırgan | %20,2 ± 3,8 | %0,0 | %100 | 7,9·10⁻⁷ |
| %20 saldırgan + 20 dBm | %22,2 ± 6,9 | %0,0 | %99,8 ± 0,9 | 1,4·10⁻⁶ |

**Tablo 2: Sürü davranışı**

| Ölçüt | Merkezi | Merkeziyetsiz | Dirençli |
|---|---|---|---|
| Düzen yuva hatası, karıştırma yok | 5,8 m | 3,8 m | 3,8 m |
| Düzen yuva hatası, 30 dBm | 129,4 m | 140,4 m | 26,2 m |
| Görev süresi, 20 dBm | 159 s | 155 s | 117 s |
| Görev süresi, 4 İHA düştü (karıştırma yok) | 126 s (96'dan) | 119 s (96'dan) | 116 s (96'dan) |
| Tamamlama, 20 dBm + 4 İHA düştü | %87,3 | %90,0 | %100 |

**Tablo 3: Röle** (menzil 180 m): bağlantılılık %74 → %81 (p < 0,001), görev süresi +64-72 s (p < 0,001).

**Tablo 4: Otonom karar alma, görev puanı** (0-100, ortalama, n = 30, her uçuşta 6 yeni hedef)

| Koşul | Mimari | Açgözlü tek görev | CBBA | Wilcoxon p |
|---|---|---|---|---|
| Karıştırma yok | Merkezi (SGA) | 73,4 | 82,9 | < 10⁻⁸ |
| Karıştırma yok | Merkeziyetsiz | 75,7 | 79,6 | < 10⁻⁶ |
| Karıştırma yok | Dirençli | 75,7 | 79,7 | < 10⁻⁷ |
| 20 dBm | Merkezi (SGA) | 59,1 | 67,7 | < 10⁻⁶ |
| 20 dBm | Merkeziyetsiz | 62,4 | 68,4 | < 10⁻⁴ |
| 20 dBm | Dirençli | 71,2 | 76,7 | < 10⁻⁸ |
| 30 dBm | Dirençli | 13,7 | 19,4 | 0,005 |
| %20 saldırgan | Dirençli | 71,6 | 76,7 | < 10⁻⁶ |
| 20 dBm + 3 arıza | Dirençli | 65,5 | 70,7 | < 10⁻⁶ |

Ek bulgular: karıştırma yokken görev alanında katedilen yol (dirençli) 6,2 → 5,1 km, merkezide 8,1 → 5,1 km. Yeni hedefe varış merkezide 29 → 13 s. Paket büyüklüğü 1 → 3: +2,1 puan (karıştırma yok), +3,7 puan (20 dBm), p < 10⁻⁵; 3'ten sonrası düz.

**Tablo 5: Yapay zekâ** (dirençli strateji, CBBA)

| | Uzman kuralı | Yapay zekâ |
|---|---|---|
| Başarı tahmini, ROC AUC (test haritaları) | 0,923 | 0,960 |
| ROC AUC, 25 dBm / 30 dBm | 0,839 / 0,737 | 0,921 / 0,795 |
| Görev puanı, karıştırma yok | 79,7 | 80,3 (p = 0,011) |
| Görev puanı, %20 saldırgan | 76,7 | 78,2 (p < 10⁻⁴) |
| Görev puanı, 20 dBm / 30 dBm / 20 dBm + arıza | 76,7 / 19,4 / 70,7 | 76,2 / 18,3 / 71,1 (anlamsız) |

Yorumlaman gereken noktalar:
- Zayıf karıştırmada (10 dBm) tamamlamada fark yok. Bu beklenen bir sonuç: sistemler zaten dayanıklı.
- 20 dBm'de diğer iki mimari "yanlış tamamlama" yaşıyor (GPS'i kesilen İHA hedefi görmeden bitti sanıyor). Dirençli sürü spiral arama ve "görmeden bitti deme" kuralıyla bunu sıfıra indiriyor. Üstelik daha hızlı bitiriyor (117 s, diğerleri 155-159 s).
- 30 dBm'de bütün alan karıştırılıyor ve GPS kalkıştan itibaren yok. Dirençli sürü %57,7 ile diğerlerinin 3-4 katı. Yine de görevlerin yarısı yapılamıyor; "her durumda üstün" deme, sınırını dürüstçe yaz. Ayrıca **düzenini koruyabilen tek sürü** (işbirlikçi konumlama).
- En çarpıcı bulgu: Korumasız merkeziyetsiz sürü saldırgana karşı **tamamen çöküyor** (%0). Merkeziyetsizlik tek başına güvenlik sağlamıyor; güven/makullük kontrolü şart.
- Lidersiz sürü üye kaybına merkeziden daha az duyarlı: 4 İHA düşünce görev süresi merkezide 30 s, dirençlide 20 s uzuyor.
- Röle bir ödünleşim: bağlantıyı artırıyor ama bir İHA'yı görevden alıyor.
- Dirençli sürünün bedeli: zayıf karıştırmada (10 dBm) biraz yavaş (115 s; diğerleri 96-97 s). Bunu dürüstçe tartış.
- **Karar alma:** Paket planlama (CBBA) her mimaride görev puanını anlamlı artırıyor. Neden: bir İHA birkaç görevi akıllı bir sırayla planlayınca yol kısalıyor, önemli ve yeni hedeflere daha hızlı gidiliyor. Merkezi SGA'da kazanç en büyük, çünkü istasyon herkesin konumunu biliyor; ama karıştırma altında merkezi mimari yine dirençli sürünün gerisinde kalıyor (67,7'ye 76,7). İyi bir algoritma, kötü bir haberleşme mimarisini kurtarmıyor.
- **Yapay zekâ:** Başarıyı uzman kuralından daha iyi tahmin ediyor ve öğrendikleri yorumlanabilir (`ai_ne_ogrendi.png`): uzman kuralı konumunu kaybetmiş İHA için fazla kötümser, karıştırma bölgesindeki göreve ise herkese gereksiz ceza veriyor. Ama görev puanına katkısı küçük ve yalnızca bazı koşullarda anlamlı. Sebebi "kural yok" kontrolünden belli: görev değerlendirme kuralı puanı az etkiliyor; sürüyü dayanıklı yapan davranış kuralları. Bu "negatif" bulguyu saklama, iyi bir bilimsel tartışma konusu.
- **İlk yapay zekâ denemesi başarısız oldu** (evrim stratejileri, `results/figures/ai_es_deneme.png`). Neden başarısız olduğunu ve yöntemi nasıl değiştirdiğini anlat; jüri araştırma sürecini görmek ister.

## Sonuç ve Tartışma
- Hipotez desteklendi mi? (Evet: 20 dBm, 30 dBm ve saldırgan koşullarında dirençli sürü anlamlı üstün, p < 10⁻⁵. Ayrıca CBBA, açgözlü yönteme göre her mimaride anlamlı üstün.)
- Hangi mekanizma en çok katkı sağladı? İstersen tek tek kapatıp deneyerek bir "ablasyon" çalışması ekleyebilirsin. Bu jüride çok iyi izlenim bırakır. ("Kural yok" kontrolü bunun ilk örneği: değerlendirme kuralının katkısı küçük çıktı.)
- Sınırlılıklar: istatistiksel radyo modeli, nokta-kütle dinamiği, gerçek uçuş testi yok, karıştırma yalnızca yazılımda, yapay zekâ simülatör verisiyle eğitildi (README §5).

## Öneriler
- Gerçek otopilot yazılımıyla (PX4/ArduPilot SITL) doğrulama
- Pekiştirmeli öğrenmeyi daha fazla hesaplama gücüyle ve davranış kararlarına (ne zaman aramayı bırakmalı, ne zaman konum düzeltmeye dönmeli) uygulamak; bu kararların puana etkisi değerlendirmeden büyük
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
- Johnson, L., Choi, H.-L., Ponda, S., & How, J. P. (2012). Allowing non-submodular score functions in distributed task allocation. *IEEE Conference on Decision and Control (CDC)*, 4702–4708.
- Salimans, T., Ho, J., Chen, X., Sidor, S., & Sutskever, I. (2017). Evolution strategies as a scalable alternative to reinforcement learning. *arXiv:1703.03864*.
- Sutton, R. S., & Barto, A. G. (2018). *Reinforcement Learning: An Introduction* (2nd ed.). MIT Press.
- Kingma, D. P., & Ba, J. (2015). Adam: A method for stochastic optimization. *International Conference on Learning Representations (ICLR)*.

> Kaynakları rapora koymadan önce en az özetlerini oku. Jüri "bu makalede ne anlatılıyor?" diye sorabilir.
