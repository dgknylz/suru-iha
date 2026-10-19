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
1. **Simülasyon ortamı:** Python. 800 m × 800 m görev alanı, 10 İHA, 20 görev noktası, 0,1 s zaman adımı, 5 Hz haberleşme.
2. **Uçuş modeli:** Hız (12 m/s) ve ivme (4 m/s²) sınırlı nokta-kütle, rüzgâr türbülansı, çarpışmadan kaçınma.
3. **Radyo modeli:** 2,4 GHz log-mesafe yol kaybı `PL(d) = 40 + 25·log10(d)`. SINR → paket kaybı lojistik eğrisi. Formülü rapora yaz ve ne anlama geldiğini açıkla.
4. **Elektronik harp modeli:** Karıştırıcı (0/10/20/30 dBm), GPS kesilme eşiği (−80 dBm), IMU sapması (`σ² = σ0² + q²t³/3`), sahte teklif yayan ele geçirilmiş İHA'lar (%20).
5. **Karşılaştırılan üç mimari:** Her birini bir paragrafla anlat. Dirençli mimarinin altı mekanizmasını madde madde yaz (README §2).
6. **Deney tasarımı:** 3 strateji × 4 güç × 2 saldırgan oranı × 30 tekrar = 720 koşu. Aynı tohumda aynı görev haritası kullanıldı (eşleştirilmiş tasarım).
7. **Ölçütler:** Görev tamamlama oranı, görev süresi, yanlış tamamlama, tekrar ziyaret, paket iletim oranı, konum hatası.
8. **İstatistik:** Kruskal-Wallis (3 grup), Wilcoxon işaretli sıralar testi (eşleştirilmiş), α = 0,05. Neden parametrik olmayan test seçtiğini açıkla: veriler normal dağılmıyor ve tavan etkisi var (%100).
9. **Görselleştirme:** Unity HDRP. Python, UDP üzerinden saniyede 30 kare yollar; modeller Blender'da kodla üretildi.

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

| Koşul | Merkezi | Merkeziyetsiz | Dirençli | Wilcoxon p (Dirençli vs en iyi diğer) |
|---|---|---|---|---|
| Karıştırma yok | %100 | %100 | %100 | – |
| 10 dBm | %99,2 ± 1,9 | %98,8 ± 2,5 | %99,8 ± 0,9 | 0,10 (anlamsız) |
| 20 dBm | %91,7 ± 5,9 | %93,8 ± 4,5 | %99,7 ± 1,3 | 2,1·10⁻⁵ |
| 30 dBm | %45,8 ± 11,2 | %48,0 ± 11,7 | %73,5 ± 12,3 | 2,5·10⁻⁶ |
| %20 saldırgan | %53,8 ± 6,0 | %0,0 | %100 | 1,4·10⁻⁶ |
| %20 saldırgan + 20 dBm | %51,2 ± 8,0 | %0,0 | %99,5 ± 1,5 | 1,6·10⁻⁶ |

Yorumlaman gereken noktalar:
- Zayıf karıştırmada (10 dBm) fark yok. Bu beklenen bir sonuç: sistemler zaten dayanıklı.
- 20 dBm'de diğer iki mimari "yanlış tamamlama" yaşıyor (GPS'i kesilen İHA hedefi görmeden bitti sanıyor). Dirençli sürü spiral arama ve "görmeden bitti deme" kuralıyla bunu sıfıra indiriyor.
- 30 dBm'de bütün alan karıştırılıyor; hiçbir yöntem %100'e ulaşamıyor ama dirençli sürü ~25 puan önde.
- En çarpıcı bulgu: Korumasız merkeziyetsiz sürü saldırgana karşı **tamamen çöküyor** (%0). Merkeziyetsizlik tek başına güvenlik sağlamıyor; güven/makullük kontrolü şart.
- Dirençli sürünün bedeli: karıştırma bölgesinde daha uzun kaldığı için ortalama konum hatası daha yüksek, görev süresi biraz daha uzun. Bunu dürüstçe tartış.

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
- Fiedler, M. (1973). Algebraic connectivity of graphs. *Czechoslovak Mathematical Journal*, 23(2), 298–305.
- Wilcoxon, F. (1945). Individual comparisons by ranking methods. *Biometrics Bulletin*, 1(6), 80–83.

> Kaynakları rapora koymadan önce en az özetlerini oku. Jüri "bu makalede ne anlatılıyor?" diye sorabilir.
