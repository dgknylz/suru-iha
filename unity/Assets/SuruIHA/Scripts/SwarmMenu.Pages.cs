using UnityEngine;

namespace SuruIHA
{
    // "Bu proje nedir?", "Nasıl kullanılır?", Esc menüsü ve çıkış onayı
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
            ("ÇİZGİLER", new Color(0.15f, 1f, 0.55f), "haberleşme bağlantısı sağlam"),
            ("ÇİZGİLER", new Color(1f, 0.12f, 0.08f), "bağlantı karıştırılmış"),
            ("ÇİZGİLER", new Color(0.55f, 0.75f, 1f), "renkli çizgi: İHA'nın planladığı rota"),
            ("ÇİZGİLER", new Color(1f, 0.35f, 0.3f), "halka: İHA'nın sandığı konum (hayalet)"),
        };

        static readonly (string key, string what)[] Keys =
        {
            ("C", "Sinematik kamera"), ("O", "Serbest kamera (fare + WASD)"), ("F · Tab · 1-9", "İHA takip kamerası"),
            ("T", "Taktik kuşbakışı"), ("L", "Haberleşme bağlantıları"), ("P", "İHA'ların planları"),
            ("G", "İHA'nın sandığı konum"), ("J", "Sürünün karıştırma haritası"), ("I", "Renklerin anlamı"),
            ("H", "Bilgi paneli"), ("Z", "Bir İHA'yı arızalandır"), ("Y", "Yeni hedef ekle"),
            ("+ / −", "Karıştırıcı gücü"), ("M", "Karıştırıcı türü"), ("U", "GPS aldatıcı"), ("X", "Saldırgan İHA'lar"),
            ("F1 · F2 · F3", "Mimari: merkezi · merkeziyetsiz · dirençli"), ("F4", "Görev paylaşım algoritması"),
            ("N", "Yeni harita"), ("V", "Düzen tipi"), ("K", "Grafik kalitesi"), ("Esc", "Menü"),
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

        void PageHeader(float x0, ref float y, string title, string sub)
        {
            Ui.Label(Ui.R(x0, y, 1400, 46), title, 34, Ui.Ink, true);
            if (sub != null) Ui.Label(Ui.R(x0, y + 48, Ui.W - 2 * x0, 28), sub, 17, Ui.Ink2);
            y += sub != null ? 96f : 64f;
        }

        void CloseButtons(float y)
        {
            float x = Ui.W - 80f - 410f;
            if (Ui.Button(Ui.R(x, y, 150, 56), "Geri", Ui.Kind.Ghost, size: 17)) Current = back;
            if (back == Page.Home)
            {
                if (Ui.Button(Ui.R(x + 166, y, 244, 56), "Simülasyonu başlat", Ui.Kind.Primary, size: 18, icon: true)) QuickStart();
            }
            else if (Ui.Button(Ui.R(x + 166, y, 244, 56), "Simülasyona dön", Ui.Kind.Primary, size: 18, icon: true))
                Current = Page.Sim;
        }

        void DrawAbout()
        {
            Dim(0.93f);
            float x0 = 80f, cw = Ui.W - 160f, gap = 28f, colW = (cw - 2 * gap) / 3f;
            float y = Mathf.Max(36f, (Ui.H - 1000f) / 2f);
            PageHeader(x0, ref y, "Bu proje nedir?",
                       "Sürü İHA'ların elektronik harp altında lidersiz karar alıp görevini sürdürebilmesi üzerine bir simülasyon çalışması.");
            float top = y;

            // 1. sütun: problem ve soru
            float h = Section(x0, y, colW, "PROBLEM",
                "İHA sürüleri arama-kurtarma, keşif ve afet bölgelerinde kullanılıyor. Ama bir sürü iki şeye bağımlıdır: " +
                "birbiriyle haberleşmeye ve GPS'e. Elektronik harp tam olarak bunları hedef alır: karıştırıcı haberleşmeyi ve " +
                "GPS'i keser, aldatıcı sahte konum verir, ele geçirilmiş bir İHA da sürüye yalan söyler.");
            y += h + 22;
            h = Section(x0, y, colW, "SORU",
                "Lideri olmayan bir sürü bu saldırılar altında görevini nasıl sürdürür? Karar alma mimarisi (merkezi, " +
                "merkeziyetsiz, EH dirençli) ve görev paylaşım algoritması sonucu ne kadar değiştirir?");
            y += h + 22;
            Section(x0, y, colW, "NASIL DOĞRULADIK?",
                "Yaklaşık 6000 deney uçuşu. Her mimari aynı 30 haritada uçtu (eşleştirilmiş deney) ve farklar Wilcoxon testiyle " +
                "sınandı. Her savunma mekanizması tek tek kapatılıp etkisi ölçüldü (ablasyon). 29 otomatik test simülatörü denetliyor.");

            // 2. sütun: yöntem
            float x1 = x0 + colW + gap;
            y = top;
            h = Section(x1, y, colW, "1 · SÜRÜ ZEKÂSI",
                "Lider yok. Her İHA görev evresine kendisi karar verir, düzen uçuşunda komşularıyla uzlaşır (konsensüs), " +
                "çarpışmaları önceden kestirip önler. Düşen bir İHA'nın görevleri diğerlerine geçer.");
            y += h + 22;
            h = Section(x1, y, colW, "2 · OTONOM KARAR ALMA",
                "CBBA ile her İHA 3 hedeflik bir rota planlar ve komşularıyla çakışmasız bir plana uzlaşır. Görev sırasında " +
                "yeni hedefler belirir; sürü yeniden plan yapar. Bir yapay sinir ağı, her İHA'nın hedefi başarma olasılığını tahmin eder.");
            y += h + 22;
            h = Section(x1, y, colW, "3 · ELEKTRONİK HARP DİRENCİ",
                "Dirençli sürüye 11 savunma eklendi: ortak karıştırma haritası, hedefi görmeden \"bitti\" dememe (spiral arama), " +
                "ölçümlerden karıştırıcıyı bulma, komşulardan konum düzeltme, GPS aldatma tespiti, güven sistemi, frekans atlama…");
            y += h + 22;
            Section(x1, y, colW, "SİMÜLATÖR",
                "Python'da sıfırdan yazıldı. Radyo modeli arazinin sinyali gölgelemesini (ITU-R P.526 kırınım) hesaba katar. " +
                "Unity yalnızca gösterir; kararları Python'daki her İHA kendisi verir.");

            // 3. sütun: bulgular
            float x2 = x1 + colW + gap;
            y = top;
            Ui.Label(Ui.R(x2, y, colW, 24), "NE BULDUK?", 13, Ui.Accent, true);
            y += 28;
            float sw = (colW - 12f) / 2f;
            Ui.Stat(Ui.R(x2, y, sw, 108), "%100", "20 dBm karıştırmada görev tamamlama (diğerleri %87)", Ui.Good);
            Ui.Stat(Ui.R(x2 + sw + 12, y, sw, 108), "%66,5", "30 dBm: alan GPS'siz (diğerleri %12-17)", Ui.Good);
            y += 120;
            Ui.Stat(Ui.R(x2, y, sw, 108), "%99", "GPS aldatmada (diğerleri %51-61)", Ui.Good);
            Ui.Stat(Ui.R(x2 + sw + 12, y, sw, 108), "%100", "%20 saldırgan İHA'ya karşı (korumasız %0)", Ui.Good);
            y += 126;
            h = Section(x2, y, colW, "KARAR ALMA",
                "CBBA görev puanını her mimaride 4-10 puan artırdı ve katedilen yolu %17-37 kısalttı. Yapay zekâ görev " +
                "başarısını uzman kuralından daha iyi tahmin etti (ROC AUC 0,978'e karşı 0,948).");
            y += h + 22;
            h = Section(x2, y, colW, "EN ÖNEMLİ DERS",
                "Merkeziyetsizlik tek başına yetmiyor: korumasız lidersiz sürü saldırgana karşı %0'a düştü. Dayanıklılık tek bir " +
                "\"sihirli\" mekanizmadan değil, birbirini tamamlayan savunmalardan geliyor.");
            y += h + 22;
            Section(x2, y, colW, "SINIRLILIKLAR",
                "Gerçek uçuş yok, yalnızca simülasyon. Karıştırma yazılımda modellendi; gerçek bir radyo yayını yapılmadı. " +
                "Tepenin arkasındaki karıştırıcıyı sürü bulamıyor, çünkü yer bulma yöntemi araziyi hesaba katmıyor.", 15.5f);

            CloseButtons(Ui.H - 92f);
        }

        void DrawHelp()
        {
            Dim(0.93f);
            float x0 = 80f, cw = Ui.W - 160f, gap = 32f, colW = (cw - 2 * gap) / 3f;
            float y = Mathf.Max(36f, (Ui.H - 1000f) / 2f);
            PageHeader(x0, ref y, "Nasıl kullanılır?", null);
            float top = y;

            Ui.Label(Ui.R(x0, y, colW, 24), "ADIM ADIM", 13, Ui.Accent, true);
            y += 30;
            string[] steps =
            {
                "Ana ekranda \"Simülasyonu başlat\"a bas ya da \"Senaryo seç\" ile bir tehdit seç.",
                "Üstteki kutu, bu senaryoda neye bakman gerektiğini söyler.",
                "Sağdaki olay akışı, sürüde olanları canlı anlatır: GPS kesilmesi, karıştırıcının bulunması, yeni hedefler…",
                "Alttaki düğmelerle kamerayı değiştir, katmanları aç-kapa ve sürüye müdahale et: bir İHA'yı arızalandır, yeni hedef ekle.",
                "Görevler bitince sonuç ekranı çıkar ve aynı senaryonun 30 uçuşluk deney ortalamasıyla karşılaştırır.",
                "Esc menüyü açar. Oradan senaryo değiştirebilir ya da ana ekrana dönebilirsin.",
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
                Ui.Label(Ui.R(x1 + 150, y + 2, colW - 150, 24), what, 15.5f, Ui.Ink2);
                y += 33f;
            }

            float x2 = x1 + colW + gap;
            Ui.Label(Ui.R(x2, top, colW, 24), "RENKLERİN ANLAMI", 13, Ui.Accent, true);
            DrawLegend(x2, top + 30, colW, 15.5f);

            CloseButtons(Ui.H - 92f);
        }

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
            if (Ui.Button(Ui.R(x + 28, by, bw, 52), "Senaryo değiştir")) Go(Page.Scenarios);
            by += 60;
            if (Ui.Button(Ui.R(x + 28, by, bw, 52), "Bu proje nedir?")) Go(Page.About);
            by += 60;
            if (Ui.Button(Ui.R(x + 28, by, bw, 52), "Nasıl kullanılır?")) Go(Page.Help);
            by += 60;
            if (Ui.Button(Ui.R(x + 28, by, bw, 52), "Ana ekrana dön")) BackToHome();
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
