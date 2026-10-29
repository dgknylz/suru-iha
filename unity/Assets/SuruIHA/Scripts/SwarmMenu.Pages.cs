using UnityEngine;

namespace SuruIHA
{
    // Sekmeler: "Nasıl çalışır?", "Kullanılanlar", "Kullanım"; ayrıca Esc menüsü ve çıkış onayı
    public partial class SwarmMenu
    {
        // Renk açıklamaları (İHA ışıkları, hedef halkaları, EH işaretleri, çizgiler) — DroneView/SwarmVisualizer ile aynı renkler
        public static readonly (string group, Color color, string text)[] Legend =
        {
            ("İHA IŞIĞI", new Color(0.15f, 1f, 0.55f), "normal"),
            ("İHA IŞIĞI", new Color(1f, 0.62f, 0.1f), "karıştırılıyor"),
            ("İHA IŞIĞI", new Color(1f, 0.18f, 0.15f), "GPS yok"),
            ("İHA IŞIĞI", new Color(0.25f, 0.6f, 1f), "spiral arama yapıyor"),
            ("İHA IŞIĞI", new Color(1f, 0.35f, 0.75f), "GPS'i aldatılıyor"),
            ("İHA IŞIĞI", new Color(1f, 0.92f, 0.25f), "aldatmayı fark etti"),
            ("İHA IŞIĞI", new Color(0.8f, 0.25f, 1f), "saldırgan"),
            ("İHA IŞIĞI", new Color(0.1f, 0.95f, 1f), "röle"),
            ("İHA IŞIĞI", new Color(1f, 0.08f, 0.3f), "radar izliyor / kilitten kaçıyor"),
            ("İHA IŞIĞI", new Color(0.92f, 0.95f, 1f), "bataryası azaldı, eve dönüyor"),
            ("İHA IŞIĞI", new Color(0.35f, 0.35f, 0.35f), "arızalı"),
            ("HEDEF HALKASI", new Color(0.85f, 0.88f, 0.95f), "açık"),
            ("HEDEF HALKASI", new Color(1f, 0.78f, 0.2f), "bir İHA yolda"),
            ("HEDEF HALKASI", new Color(0.2f, 1f, 0.45f), "tamamlandı"),
            ("HEDEF HALKASI", new Color(1f, 0.15f, 0.25f), "yanlışlıkla \"bitti\" sayıldı"),
            ("HEDEF HALKASI", new Color(0.75f, 0.3f, 1f), "yeni belirdi (mor dalga)"),
            ("ELEKTRONİK HARP", new Color(1f, 0.3f, 0.18f), "geniş bant karıştırıcı (kubbe)"),
            ("ELEKTRONİK HARP", new Color(1f, 0.7f, 0.1f), "nokta karıştırıcı"),
            ("ELEKTRONİK HARP", new Color(0.2f, 0.85f, 1f), "GPS aldatıcı"),
            ("ELEKTRONİK HARP", new Color(1f, 0.55f, 0.1f), "sürünün karıştırıcı tahmini (nişangâh)"),
            ("HAVA SAVUNMA", new Color(1f, 0.78f, 0.2f), "radarın görüşü ve tarama huzmesi"),
            ("HAVA SAVUNMA", new Color(1f, 0.08f, 0.3f), "kilit çizgisi: radar bu İHA'yı izliyor"),
            ("HAVA SAVUNMA", new Color(1f, 0.35f, 0.75f), "sürünün radar tahmini (çarpı nişangâh)"),
            ("ÇİZGİLER", new Color(0.15f, 1f, 0.55f), "haberleşme bağlantısı sağlam"),
            ("ÇİZGİLER", new Color(1f, 0.12f, 0.08f), "bağlantı karıştırılmış"),
            ("ÇİZGİLER", new Color(0.55f, 0.75f, 1f), "renkli çizgi: İHA'nın planladığı rota"),
            ("ÇİZGİLER", new Color(1f, 0.35f, 0.3f), "halka: İHA'nın sandığı konum (hayalet)"),
        };

        static readonly (string key, string what)[] Keys =
        {
            ("C", "Sinematik kamera"), ("O", "Serbest kamera (fare + WASD)"), ("F · Tab · 1-9 · 0", "İHA kamerası (TPP)"),
            ("R", "İHA kamerasının açısını sıfırla"),
            ("T", "Taktik kuşbakışı"), ("L", "Bağlantılar: kapalı → sorunlu → hepsi"), ("P", "İHA'ların planları"),
            ("G", "İHA'nın sandığı konum"), ("J", "Sürünün karıştırma haritası"), ("I", "Renklerin anlamı"),
            ("H", "Bilgi paneli"), ("Z", "Bir İHA'yı arızalandır"), ("Y", "Yeni hedef ekle"),
            ("+ / −", "Karıştırıcı gücü"), ("M", "Karıştırıcı türü"), ("U", "GPS aldatıcı"), ("X", "Saldırgan İHA'lar"),
            ("F1 · F2 · F3", "Mimari: merkezi · merkeziyetsiz · dirençli"), ("F4", "Görev paylaşım algoritması"),
            ("N", "Yeni harita"), ("V", "Düzen tipi"), ("K", "Grafik kalitesi"), ("Esc", "Menü"),
            ("← → · PageUp/Down", "Menüde sekme değiştir"),
        };

        // Renk açıklamalarını (Legend[from..to)) verilen sütuna çizer, kullanılan yüksekliği döndürür
        static float DrawLegend(float x, float y, float w, float size = 15f, int from = 0, int to = -1, bool note = true)
        {
            float y0 = y;
            string group = null;
            if (to < 0) to = Legend.Length;
            for (int k = from; k < to; k++)
            {
                var (g, c, text) = Legend[k];
                if (g != group)
                {
                    group = g;
                    y += y > y0 ? 10f : 0f;
                    Ui.Label(Ui.R(x, y, w, 20), g, 11.5f, Ui.Ink3, true);
                    y += 22f;
                }
                Ui.Dot(new Vector2((x + 7f) * Ui.S, (y + size * 0.62f) * Ui.S), 6f, c);
                Ui.Label(Ui.R(x + 22f, y, w - 22f, size + 8f), text, size, Ui.Ink);
                y += size + 9f;
            }
            if (!note) return y - y0;
            Ui.Label(Ui.R(x, y + 4, w, 40), "Hedefteki iç içe halka sayısı önceliği gösterir (1-3).", size - 1.5f, Ui.Ink3);
            return y + 30f - y0;
        }

        static float Section(float x, float y, float w, string head, string body, float size = 16.5f)
        {
            Ui.Label(Ui.R(x, y, w, 26), head, 13, Ui.Accent, true);
            float h = Ui.TextHeight(body, size, w);
            Ui.Label(Ui.R(x, y + 26, w, h + 4), body, size, Ui.Ink2);
            return 26f + h;
        }

        // Madde işaretli kısa satır; kullanılan yüksekliği döndürür
        static float Bullet(float x, float y, float w, string text, float size = 15.5f, Color? dot = null)
        {
            Ui.Dot(new Vector2((x + 4f) * Ui.S, (y + size * 0.66f) * Ui.S), 3f, dot ?? Ui.Accent);
            float h = Ui.TextHeight(text, size, w - 18f);
            Ui.Label(Ui.R(x + 16, y, w - 16, h + 4), text, size, Ui.Ink2);
            return h + 8f;
        }

        // Başlıklı kart (sütun) çerçevesi; içerik y'sini döndürür
        static float Card(float x, float y, float w, float h, string kicker, string title, Color kc)
        {
            var r = Ui.R(x, y, w, h);
            Ui.Fill(r, new Color(0.06f, 0.08f, 0.11f, 0.94f), 16);
            Ui.Outline(r, Ui.Line, 1f, 16);
            Ui.Chip(x + 22, y + 20, kicker, kc, 11.5f);
            float th = Ui.TextHeight(title, 22, w - 44, true);
            Ui.Label(Ui.R(x + 22, y + 52, w - 44, th + 4), title, 22, Ui.Ink, true);
            return y + 60 + th;
        }

        // Kutu: başlık + açıklama (şemalarda)
        static void Box(float x, float y, float w, float h, string head, string body, Color edge)
        {
            var r = Ui.R(x, y, w, h);
            Ui.Fill(r, new Color(edge.r, edge.g, edge.b, 0.08f), 10);
            Ui.Outline(r, new Color(edge.r, edge.g, edge.b, 0.55f), 1.5f, 10);
            Ui.Label(Ui.R(x + 16, y + 12, w - 32, 26), head, 18, Ui.Ink, true);
            Ui.Label(Ui.R(x + 16, y + 40, w - 32, h - 44), body, 15.5f, Ui.Ink2);
        }

        static void Arrow(float x, float y, string label = null)
        {
            Ui.Label(Ui.R(x - 20, y, 40, 26), "↓", 20, Ui.Ink3, true, TextAnchor.MiddleCenter);
            if (label != null) Ui.Label(Ui.R(x + 18, y + 3, 300, 22), label, 14.5f, Ui.Ink3);
        }

        // ---------------------------------------------------------------- Nasıl çalışır?
        void DrawNasilTab()
        {
            float x0 = 64f, gap = 26f, cw = Ui.W - 2 * x0, colW = (cw - 2 * gap) / 3f;
            float y0 = BarH + 26f, ch = Mathf.Min(Ui.H - y0 - 190f, 740f);

            // 1. sütun: sürü zekâsı — uçuş evreleri zaman çizelgesi
            float x = x0;
            float y = Card(x, y0, colW, ch, "1 · SÜRÜ ZEKÂSI", "Lider yok: her İHA kendi kararını verir", Ui.Accent);
            (string head, string body)[] phases =
            {
                ("Kalkış", "her İHA sırayla havalanır, üssün üstünde halka olur"),
                ("Düzende intikal", "V düzeni; İHA'lar sanal liderin yerinde uzlaşır (konsensüs)"),
                ("Görev", "dağılır, planladığı hedeflere gider; yeni hedefler belirir"),
                ("Toplanma", "haberini aldığı her arkadaşı gelene kadar bekler"),
                ("Düzende dönüş", "yuvalar Macar algoritmasıyla dağıtılır, yollar kesişmez"),
                ("İniş", "her İHA kendi sırasıyla iner"),
            };
            float px = x + 34f, py = y + 6f;
            Ui.Fill(Ui.R(px - 1.5f, py + 12, 3, (phases.Length - 1) * 64f), new Color(0.33f, 0.78f, 1f, 0.35f));
            foreach (var (head, body) in phases)
            {
                Ui.Dot(new Vector2(px * Ui.S, (py + 12f) * Ui.S), 7f, Ui.Accent);
                Ui.Label(Ui.R(px + 20, py, colW - 80, 26), head, 18.5f, Ui.Ink, true);
                Ui.Label(Ui.R(px + 20, py + 26, colW - 80, 26), body, 15.5f, Ui.Ink2);
                py += 64f;
            }
            py += 8f;
            py += Bullet(x + 22, py, colW - 44, "Reynolds kuralları: ayrışma, hizalanma, uyum", 17f);
            py += Bullet(x + 22, py, colW - 44, "Öngörülü çarpışma önleme: en yakın geçiş noktası hesaplanır, biri yukarı biri aşağı kaçar", 17f);
            py += Bullet(x + 22, py, colW - 44, "Düşen İHA'nın hedefleri diğerlerine geçer, düzen kalanlarla yeniden kurulur", 17f);

            // 2. sütun: otonom karar alma — CBBA döngüsü
            x = x0 + colW + gap;
            y = Card(x, y0, colW, ch, "2 · OTONOM KARAR ALMA", "CBBA: lidersiz paket planlama", Ui.Good);
            float bxw = colW - 44f, bx = x + 22f;
            Box(bx, y + 4, bxw, 98, "1 · Paket kurma", "Her İHA rotasına en çok değer katan hedefi en uygun sıraya ekler (en fazla 3 hedef).", Ui.Good);
            Arrow(bx + bxw / 2f, y + 108, "komşulara yayınla");
            Box(bx, y + 140, bxw, 98, "2 · Uzlaşma", "Komşular kazanan listelerini değiş tokuş eder; teklifi geçilen İHA o hedefi bırakır.", Ui.Good);
            Arrow(bx + bxw / 2f, y + 244, "değişiklik kalmayınca");
            Box(bx, y + 276, bxw, 76, "Çakışmasız plan", "Her hedefe tek İHA; lider ya da yer istasyonu yok.", Ui.Accent);
            py = y + 372f;
            py += Bullet(x + 22, py, colW - 44, "Hedeflerin değeri beklendikçe azalır; görev sırasında yeni hedefler belirir ve plan kendiliğinden güncellenir", 16.5f, Ui.Good);
            py += Bullet(x + 22, py, colW - 44, "Merkezi karşılık: yer istasyonu herkesi toplar, açgözlü sırayla dağıtır (SGA)", 16.5f, Ui.Good);
            py += Bullet(x + 22, py, colW - 44, "Yapay zekâ: sinir ağı her İHA'nın hedefi başarma olasılığını tahmin eder; CBBA beklenen ödülü en büyütür", 16.5f, Ui.Good);

            // 3. sütun: EH direnci — tehdit → savunma
            x = x0 + 2 * (colW + gap);
            y = Card(x, y0, colW, ch, "3 · ELEKTRONİK HARP DİRENCİ", "Beş tehdit, birbirini tamamlayan 13 savunma", Ui.Bad);
            (string threat, Color c, string defense)[] map =
            {
                ("Karıştırma", Ui.Bad, "Ortak karıştırma haritası · hedefi görmeden \"bitti\" dememe (spiral arama) · ölçümlerden karıştırıcıyı bulma · " +
                                       "komşulardan konum düzeltme · GPS'i geri alma · frekans atlama"),
                ("GPS aldatma", Ui.Cyan, "IMU ile tutarlılık testi · komşu menzil testi · \"hedef yok\" çıkarımı → İHA GPS'e güvenmeyi bırakır"),
                ("Saldırgan İHA", Ui.Violet, "Beta itibar sistemi (menzil, hız, ilerleme kanıtı) · iki bağımsız tanık kuralı · \"tamamlandı\" bilgisi kaynağıyla yayılır"),
                ("Hava savunma", Ui.Pink, "Radar ikaz alıcısı + kerteriz kestirimi · radarın görmediği rota · kilit ikazında kaçış · şemsiye altındaki hedefi bırakma"),
                ("Rüzgâr ve batarya", Ui.Warn, "Rüzgâra karşı eve dönüş enerjisi hesaplanır; gücü yetmeyen hedef alınmaz, İHA zamanında döner"),
            };
            py = y + 4f;
            foreach (var (threat, c, defense) in map)
            {
                Ui.Chip(x + 22, py, Ui.Upper(threat), c, 11.5f);
                float h = Ui.TextHeight(defense, 17f, colW - 44f);
                Ui.Label(Ui.R(x + 22, py + 32, colW - 44, h + 4), defense, 17f, Ui.Ink2);
                py += 32f + h + 24f;
            }
            Ui.Label(Ui.R(x + 22, py, colW - 44, 60), "Her savunma deneyde tek tek kapatılıp etkisi ölçüldü (Bulgular → Savunmaların katkısı).", 15f, Ui.Ink3);

            // Alt şerit: mimari
            float sy = y0 + ch + 20f, sh = Ui.H - sy - 28f;
            if (sh < 100f) return;
            sh = Mathf.Min(sh, 150f);
            var strip = Ui.R(x0, sy, cw, sh);
            Ui.Fill(strip, new Color(0.06f, 0.08f, 0.11f, 0.94f), 16);
            Ui.Outline(strip, Ui.Line, 1f, 16);
            Ui.Label(Ui.R(x0 + 22, sy + 16, 400, 20), "SİMÜLASYON MİMARİSİ", 11.5f, Ui.Ink3, true);
            float bw = (cw - 44f - 2 * 120f) / 3f, by = sy + 44f, bh = sh - 62f;
            Box(x0 + 22, by, bw, bh, "Python simülatörü", "Her İHA'nın kararı, radyo ve EH modeli, arazi (Unity ile aynı yükseklik haritası)", Ui.Accent);
            Ui.Label(Ui.R(x0 + 22 + bw, by, 120, bh), "UDP\n→", 15, Ui.Ink3, true, TextAnchor.MiddleCenter);
            Box(x0 + 22 + bw + 120, by, bw, bh, "Unity HDRP", "Yalnızca 3D görüntü: arazi, köy, İHA'lar, EH işaretleri ve bu arayüz", Ui.Accent);
            Ui.Label(Ui.R(x0 + 22 + 2 * bw + 120, by, 120, bh), "aynı kod\n→", 15, Ui.Ink3, true, TextAnchor.MiddleCenter);
            Box(x0 + 22 + 2 * bw + 240, by, bw, bh, "Deneyler (görüntüsüz)", "8 çekirdekte paralel 5976 uçuş → grafikler ve istatistik testleri", Ui.Good);
        }

        // ---------------------------------------------------------------- Kullanılanlar
        void DrawKullanilanlarTab()
        {
            float x0 = 64f, gap = 26f, cw = Ui.W - 2 * x0, colW = (cw - 2 * gap) / 3f;
            float y0 = BarH + 26f, ch = Mathf.Min(Ui.H - y0 - 30f, 900f);

            float x = x0;
            float y = Card(x, y0, colW, ch, "YAZILIM VE ARAÇLAR", "Neyle yapıldı?", Ui.Accent);
            (string name, string what)[] tools =
            {
                ("Python 3.14", "Simülasyon, deneyler ve yapay zekâ. NumPy, SciPy, pandas, Matplotlib, pytest."),
                ("Unity 6 · HDRP", "3D görselleştirme: gerçekçi ışık, gölge, sis ve bulutlar. Bütün sahne C# ile kodla kuruluyor."),
                ("Blender 5.2", "İHA, karıştırıcı aracı, yer istasyonu, köy ve bitki modelleri Python betikleriyle üretildi."),
                ("Poly Haven (CC0)", "Arazi, kaya ve ağaç kabuğu için fotoğraftan taranmış dokular; ücretsiz, serbest lisanslı."),
                ("Ses sentezi (NumPy)", "Pervane uğultusu, rüzgâr, ırmak ve arayüz tonları fizik temelli olarak kodla üretildi; kayıt ya da indirme yok."),
                ("UDP + JSON", "Python ile Unity arasında saniyede 30 kare; Unity'den komutlar geri gider."),
                ("Git", "Sürüm takibi: her aşama etiketli (v1 görsel → v17 sesler)."),
                ("PowerShell", "Derleme, uçtan uca test, arayüz testi ve video hattının otomasyonu."),
            };
            foreach (var (name, what) in tools)
            {
                Ui.Label(Ui.R(x + 22, y, colW - 44, 28), name, 20, Ui.Ink, true);
                float h = Ui.TextHeight(what, 16.5f, colW - 44f);
                Ui.Label(Ui.R(x + 22, y + 30, colW - 44, h + 4), what, 16.5f, Ui.Ink2);
                y += 30f + h + 22f;
            }

            x = x0 + colW + gap;
            y = Card(x, y0, colW, ch, "ALGORİTMA VE MODELLER", "Hangi bilimsel yöntemler?", Ui.Good);
            (string area, string list)[] algos =
            {
                ("Sürü zekâsı", "Ortalama konsensüs · Macar algoritması (Kuhn 1955) · Reynolds kuralları · en yakın geçiş (CPA) ile çarpışma önleme"),
                ("Karar alma", "CBBA (Choi vd. 2009) · merkezi SGA · zamanla azalan görev değeri · dinamik yeniden planlama"),
                ("Radyo", "Log-mesafe yol kaybı · SINR'den paket kaybı · ITU-R P.526 bıçak sırtı kırınımı (arazi gölgesi)"),
                ("Elektronik harp", "Kısıtlı en küçük kareler + k-ortalamalar (karıştırıcı bulma) · IMU tutarlılık testi · Beta itibar sistemi"),
                ("Hava savunma", "Radar denklemi ve Swerling-1 tespit olasılığı · kerteriz kestirimi (en çok olabilirlik) · Dijkstra ile en az görülen rota"),
                ("Enerji", "Döner kanatlı İHA güç modeli (Zeng vd. 2019) · rüzgâra karşı dönüş enerjisi · Ornstein-Uhlenbeck esintisi"),
                ("Yapay zekâ", "8-8-1 yapay sinir ağı · geri yayılım · Adam · erken durdurma (denetimli öğrenme)"),
                ("İstatistik", "Eşleştirilmiş deney (aynı 30 harita) · Wilcoxon işaretli sıralar · Kruskal-Wallis · ablasyon"),
            };
            foreach (var (area, list) in algos)
            {
                Ui.Label(Ui.R(x + 22, y, colW - 44, 28), area, 20, Ui.Ink, true);
                float h = Ui.TextHeight(list, 16.5f, colW - 44f);
                Ui.Label(Ui.R(x + 22, y + 30, colW - 44, h + 4), list, 16.5f, Ui.Ink2);
                y += 30f + h + 22f;
            }

            x = x0 + 2 * (colW + gap);
            y = Card(x, y0, colW, ch, "RAKAMLARLA PROJE", "Ne kadar büyük?", Ui.Warn);
            (string big, string cap)[] stats =
            {
                ("17 000+", "satır kod (Python ~7 800, C# ~10 100)"), ("5976", "deney uçuşu"),
                ("43", "otomatik test"), ("13", "savunma mekanizması"),
                ("11", "tehdit senaryosu (+ ana deney)"), ("10", "İHA, 20 hedef + beliren yeni hedefler"),
                ("~11 000", "ağaç ve çalı (3D sahne)"), ("17", "sürüm (v1 → v17)"),
            };
            float sw = (colW - 44f - 12f) / 2f, sh = 124f;
            for (int i = 0; i < stats.Length; i++)
            {
                float sx = x + 22 + (i % 2) * (sw + 12), sy = y + (i / 2) * (sh + 12);
                Ui.Stat(Ui.R(sx, sy, sw, sh), stats[i].big, stats[i].cap, Ui.Warn, 36);
            }
        }

        // ---------------------------------------------------------------- Kullanım
        void DrawKullanimTab()
        {
            float x0 = 80f, cw = Ui.W - 160f, gap = 32f, colW = (cw - 2 * gap) / 3f;
            float y = BarH + 30f;
            float top = y;

            Ui.Label(Ui.R(x0, y, colW, 24), "ADIM ADIM", 13, Ui.Accent, true);
            y += 30;
            string[] steps =
            {
                "Üstteki \"Simülasyonu başlat\"a bas ya da \"Simülasyon\" sekmesinden bir senaryo seç.",
                "Üstteki kutu, bu senaryoda neye bakman gerektiğini söyler.",
                "Sağdaki olay akışı, sürüde olanları canlı anlatır: GPS kesilmesi, karıştırıcının bulunması, yeni hedefler…",
                "Alttaki düğmelerle kamerayı değiştir, katmanları ve sesi aç-kapa, sürüye müdahale et: bir İHA'yı arızalandır, yeni hedef ekle.",
                "Görevler bitince sonuç ekranı çıkar ve aynı senaryonun 30 uçuşluk deney ortalamasıyla karşılaştırır.",
                "Esc menüyü açar. Oradan senaryo değiştirebilir ya da bu sekmelere dönebilirsin.",
            };
            for (int i = 0; i < steps.Length; i++)
            {
                Ui.Dot(new Vector2((x0 + 14f) * Ui.S, (y + 13f) * Ui.S), 14f, new Color(0.33f, 0.78f, 1f, 0.2f));
                Ui.Label(Ui.R(x0, y, 28, 26), (i + 1).ToString(), 15, Ui.Accent, true, TextAnchor.MiddleCenter);
                float h = Ui.TextHeight(steps[i], 16.5f, colW - 44f);
                Ui.Label(Ui.R(x0 + 42, y + 1, colW - 44, h + 4), steps[i], 16.5f, Ui.Ink);
                y += Mathf.Max(30f, h) + 14f;
            }
            y += 8;
            Section(x0, y, colW, "FARE",
                "Serbest kamerada (O) sol ya da sağ tuşla sürükleyerek döndür, tekerlekle yakınlaş, WASD ile kaydır " +
                "(Shift hızlı, Q/E aşağı-yukarı). Sinematik kameradayken fareyle oynamak serbest kameraya geçirir.");

            float x1 = x0 + colW + gap;
            y = top;
            Ui.Label(Ui.R(x1, y, colW, 24), "KLAVYE KISAYOLLARI", 13, Ui.Accent, true);
            y += 30;
            foreach (var (key, what) in Keys)
            {
                float kw = Ui.TextWidth(key, 13.5f, true) + 18f;
                var kr = Ui.R(x1, y, kw, 26);
                Ui.Fill(kr, new Color(1f, 1f, 1f, 0.08f), 6);
                Ui.Outline(kr, new Color(1f, 1f, 1f, 0.16f), 1f, 6);
                Ui.Label(kr, key, 13.5f, Ui.Ink, true, TextAnchor.MiddleCenter);
                Ui.Label(Ui.R(x1 + 172, y + 2, colW - 172, 24), what, 15.5f, Ui.Ink2);
                y += 32f;
            }

            float x2 = x1 + colW + gap;
            Ui.Label(Ui.R(x2, top, colW, 24), "RENKLERİN ANLAMI", 13, Ui.Accent, true);
            DrawLegend(x2, top + 30, colW, 15.5f);
        }

        // ---------------------------------------------------------------- Esc menüsü
        void DrawPause()
        {
            Dim(0.6f);
            float w = 470f, h = 488f, x = (Ui.W - w) / 2f, y = (Ui.H - h) / 2f;
            Ui.Panel(Ui.R(x, y, w, h), 18);
            Ui.Label(Ui.R(x + 28, y + 24, w - 56, 34), "Menü", 26, Ui.Ink, true);
            Ui.Label(Ui.R(x + 28, y + 60, w - 56, 24), "Simülasyon arkada çalışmaya devam ediyor.", 14.5f, Ui.Ink3);
            float by = y + 100, bw = w - 56;
            if (Ui.Button(Ui.R(x + 28, by, bw, 56), "Devam et", Ui.Kind.Primary, size: 19, icon: true)) Current = Page.Sim;
            by += 66;
            if (Ui.Button(Ui.R(x + 28, by, bw, 52), "Senaryo değiştir")) OpenMenu(Tab.Simulasyon);
            by += 60;
            if (Ui.Button(Ui.R(x + 28, by, bw, 52), "Proje ve bulgular")) OpenMenu(Tab.Proje);
            by += 60;
            if (Ui.Button(Ui.R(x + 28, by, bw, 52), "Nasıl kullanılır?")) OpenMenu(Tab.Kullanim);
            by += 60;
            if (Ui.Button(Ui.R(x + 28, by, bw, 52), "Simülasyonu durdur, ana ekrana dön")) BackToHome();
            by += 68;
            if (Ui.Button(Ui.R(x + 28, by, bw, 46), "Uygulamadan çık", Ui.Kind.Ghost, size: 16)) Go(Page.Quit);
        }

        void DrawQuit()
        {
            Dim(0.75f);
            float w = 520f, h = 210f, x = (Ui.W - w) / 2f, y = (Ui.H - h) / 2f;
            Ui.Panel(Ui.R(x, y, w, h), 18);
            Ui.Label(Ui.R(x + 28, y + 26, w - 56, 34), "Uygulamadan çıkılsın mı?", 24, Ui.Ink, true);
            Ui.Label(Ui.R(x + 28, y + 64, w - 56, 26), "Çalışan simülasyon da kapatılır.", 15, Ui.Ink2);
            if (Ui.Button(Ui.R(x + 28, y + 120, 220, 56), "Vazgeç", Ui.Kind.Ghost, size: 17)) Current = beforeQuit;
            if (Ui.Button(Ui.R(x + w - 28 - 220, y + 120, 220, 56), "Çık", Ui.Kind.Danger, size: 17))
            {
                launcher.Stop();
#if UNITY_EDITOR
                UnityEditor.EditorApplication.isPlaying = false;
#else
                Application.Quit();
#endif
            }
        }
    }
}
