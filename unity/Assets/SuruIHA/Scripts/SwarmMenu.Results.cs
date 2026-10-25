using UnityEngine;

namespace SuruIHA
{
    // "Bulgular" sekmesi: deney sonuçları uygulamanın içinde çizilen grafiklerle.
    // Sayılar results/istatistik.txt'den (30 uçuşun ortalaması; ablasyon n=12, ölçekleme n=20).
    public partial class SwarmMenu
    {
        static readonly string[] Findings = { "Elektronik harp", "Karar alma (CBBA)", "Yapay zekâ", "Savunmaların katkısı", "Ölçekleme" };
        int finding;

        static readonly Color CMerkezi = new Color(1f, 0.6f, 0.35f);
        static readonly Color CMerkeziyetsiz = new Color(0.55f, 0.68f, 0.92f);
        static Color CDirencli => Ui.Good;

        // Görev tamamlama (%): merkezi, merkeziyetsiz, dirençli — diğer mimarilerin en zor senaryosu üstte
        static readonly (string name, float m, float d, float r)[] EhRows =
        {
            ("İki karıştırıcı 20 dBm", 40.4f, 39.4f, 99.5f), ("GPS aldatma hızlı", 51.9f, 50.5f, 98.6f),
            ("GPS aldatma yavaş", 61.2f, 61.4f, 99.1f), ("Tepede 25 dBm", 73.7f, 79.0f, 100f),
            ("Hareketli 20 dBm", 83.7f, 85.9f, 100f), ("Sinsi saldırgan %20", 32.4f, 86.8f, 100f),
            ("Sabit 20 dBm", 86.9f, 89.4f, 100f), ("Sırt arkasında 30 dBm", 91.5f, 92.1f, 100f),
            ("Nokta 25 dBm", 74.5f, 99.9f, 100f),
        };

        static float Map(float v, float min, float max, float x, float w) => x + (v - min) / (max - min) * w;

        static string F1(float v) => v.ToString(v % 1f < 0.05f ? "0" : "0.0").Replace('.', ',');

        // Dikey ızgara çizgileri ve alttaki eksen yazıları
        static void Grid(float px, float pw, float top, float bottom, float min, float max, float[] ticks, string fmt)
        {
            foreach (float t in ticks)
            {
                float gx = Map(t, min, max, px, pw);
                Ui.Fill(Ui.R(gx, top, 1, bottom - top), new Color(1f, 1f, 1f, 0.08f));
                Ui.Label(Ui.R(gx - 40, bottom + 6, 80, 22), Mathf.Approximately(t, 0f) ? "0" : string.Format(fmt, F1(t)), 14.5f, Ui.Ink2, false, TextAnchor.UpperCenter);
            }
        }

        static float LegendItem(float x, float y, string text, Color c, bool ring = false, float r = 6f)
        {
            var center = new Vector2((x + r) * Ui.S, (y + 10f) * Ui.S);
            if (ring) Ui.Ring(center, r, c);
            else Ui.Dot(center, r, c);
            Ui.Label(Ui.R(x + 2 * r + 8, y, 260, 22), text, 14.5f, Ui.Ink);
            return 2 * r + 8 + Ui.TextWidth(text, 14.5f) + 26f;
        }

        void DrawBulgularTab()
        {
            float x0 = 64f, cw = Ui.W - 2 * x0;
            float y = BarH + 24f;
            float tx = x0;
            for (int i = 0; i < Findings.Length; i++)
            {
                float bw = Ui.TextWidth(Findings[i], 16, true) + 44f;
                if (Ui.Button(Ui.R(tx, y, bw, 44), Findings[i], Ui.Kind.Normal, i == finding, 16)) finding = i;
                tx += bw + 8f;
            }
            y += 62f;
            float sideW = 470f, gap = 24f, chartW = cw - sideW - gap;
            float h = Mathf.Min(Ui.H - y - 32f, 860f);
            var panel = Ui.R(x0, y, chartW, h);
            Ui.Fill(panel, new Color(0.06f, 0.08f, 0.11f, 0.94f), 16);
            Ui.Outline(panel, Ui.Line, 1f, 16);
            var side = Ui.R(x0 + chartW + gap, y, sideW, h);
            Ui.Fill(side, new Color(0.06f, 0.08f, 0.11f, 0.94f), 16);
            Ui.Outline(side, Ui.Line, 1f, 16);

            float cx = x0 + 28f, cy = y + 24f, cwi = chartW - 56f, chi = h - 48f;
            float sx = x0 + chartW + gap + 26f, sy = y + 24f, swi = sideW - 52f;
            switch (finding)
            {
                case 0: ChartEh(cx, cy, cwi, chi); SideEh(sx, sy, swi); break;
                case 1: ChartKarar(cx, cy, cwi, chi); SideKarar(sx, sy, swi); break;
                case 2: ChartYz(cx, cy, cwi, chi); SideYz(sx, sy, swi); break;
                case 3: ChartAblasyon(cx, cy, cwi, chi); SideAblasyon(sx, sy, swi); break;
                default: ChartOlcek(cx, cy, cwi, chi); SideOlcek(sx, sy, swi); break;
            }
        }

        static float ChartTitle(float x, float y, float w, string title, string sub)
        {
            float th = Ui.TextHeight(title, 24, w, true);
            Ui.Label(Ui.R(x, y, w, th + 4), title, 24, Ui.Ink, true);
            Ui.Label(Ui.R(x, y + th + 6, w, 22), sub, 14.5f, Ui.Ink3);
            return y + th + 40f;
        }

        static float SideText(float x, float y, float w, string head, string body)
        {
            Ui.Label(Ui.R(x, y, w, 22), head, 13, Ui.Accent, true);
            float h = Ui.TextHeight(body, 17f, w);
            Ui.Label(Ui.R(x, y + 26, w, h + 4), body, 17f, Ui.Ink2);
            return y + 26f + h + 22f;
        }

        // ------------------------------------------------------------ 1. elektronik harp
        void ChartEh(float x, float y, float w, float h)
        {
            float yEnd = y + h;
            y = ChartTitle(x, y, w, "Dirençli sürü 9 EH senaryosunun hepsinde %98,6-100 tamamladı",
                           "Görev tamamlama oranı · her nokta 30 uçuşun ortalaması · diğer mimariler için en zor senaryo üstte");
            float lx = x + 270f;
            lx += LegendItem(lx, y, "Merkezi", CMerkezi, true);
            lx += LegendItem(lx, y, "Merkeziyetsiz (korumasız)", CMerkeziyetsiz);
            LegendItem(lx, y, "EH dirençli", CDirencli, false, 8f);
            y += 40f;
            float labelW = 260f, valW = 80f, px = x + labelW, pw = w - labelW - valW;
            float rowH = Mathf.Clamp((yEnd - y - 40f) / EhRows.Length, 40f, 60f);   // eksen yazılarına yer kalsın
            float top = y, bottom = y + rowH * EhRows.Length;
            Grid(px, pw, top, bottom, 0, 100, new float[] { 0, 25, 50, 75, 100 }, "%{0}");
            for (int i = 0; i < EhRows.Length; i++)
            {
                var (name, m, d, r) = EhRows[i];
                float ry = top + i * rowH, my = ry + rowH / 2f;
                Ui.Label(Ui.R(x, ry, labelW - 20, rowH), name, 16, Ui.Ink, false, TextAnchor.MiddleRight);
                float lo = Mathf.Min(m, Mathf.Min(d, r)), hi = Mathf.Max(m, Mathf.Max(d, r));
                Ui.Fill(Ui.R(Map(lo, 0, 100, px, pw), my - 1.5f, Map(hi, 0, 100, px, pw) - Map(lo, 0, 100, px, pw), 3), new Color(1f, 1f, 1f, 0.18f), 1.5f);
                Ui.Dot(new Vector2(Map(d, 0, 100, px, pw) * Ui.S, my * Ui.S), 7f, CMerkeziyetsiz);
                Ui.Ring(new Vector2(Map(m, 0, 100, px, pw) * Ui.S, my * Ui.S), 7f, CMerkezi);
                Ui.Dot(new Vector2(Map(r, 0, 100, px, pw) * Ui.S, my * Ui.S), 9f, CDirencli);
                Ui.Label(Ui.R(px + pw + 18, ry, valW, rowH), "%" + F1(r), 16, Ui.Ink, true, TextAnchor.MiddleLeft);
            }
        }

        void SideEh(float x, float y, float w)
        {
            y = SideText(x, y, w, "NE GÖRÜYORUZ?",
                "Korumasız sürüler iki karıştırıcıda ve GPS aldatmada hedeflerin yarısını bile bitiremiyor; dirençli sürü hepsinde " +
                "neredeyse tamamını yapıyor. Merkezi sürü sinsi saldırgana karşı en kötüsü (%32): yer istasyonu yalancının tekliflerine güveniyor.");
            y = SideText(x, y, w, "ARAZİ GÖLGESİ",
                "Sırt arkasındaki karıştırıcıda tepeler kalkan oluyor. Arazi hesaba katılmasa korumasız sürü %65'te kalırdı; gerçekçi model sonucu değiştiriyor.");
            SideText(x, y, w, "NASIL ÖLÇÜLDÜ?",
                "Üç mimari aynı 30 haritada uçtu, her uçuşta 6 yeni hedef belirdi. Dirençli sürünün farkı her senaryoda anlamlı (Wilcoxon p < 0,000001).");
        }

        // ------------------------------------------------------------ 2. karar alma
        void ChartKarar(float x, float y, float w, float h)
        {
            float yEnd = y + h;
            y = ChartTitle(x, y, w, "CBBA görev puanını her mimaride artırdı",
                           "Görev puanı (0-100, geç yapılan hedef daha az değerli) · 30 uçuş, her birinde 6 yeni hedef");
            float lx = x + 230f;
            lx += LegendItem(lx, y, "Açgözlü tek görev", Ui.Ink2, true);
            LegendItem(lx, y, "CBBA paket planlama (merkezide SGA)", Ui.Ink, false, 7f);
            y += 44f;
            (string group, (string name, float g, float c, Color col)[] rows)[] data =
            {
                ("KARIŞTIRMA YOK", new[] { ("Merkezi", 73.3f, 83.0f, CMerkezi), ("Merkeziyetsiz", 75.5f, 79.6f, CMerkeziyetsiz), ("EH dirençli", 75.4f, 79.5f, CDirencli) }),
                ("20 dBm KARIŞTIRMA", new[] { ("Merkezi", 58.5f, 66.9f, CMerkezi), ("Merkeziyetsiz", 63.9f, 70.6f, CMerkeziyetsiz), ("EH dirençli", 72.5f, 77.8f, CDirencli) }),
            };
            float labelW = 220f, px = x + labelW, pw = w - labelW - 40f;
            float rowH = Mathf.Clamp((yEnd - y - 2 * 30f - 20f - 50f) / 6f, 56f, 84f);
            float top = y, bottom = y + 2 * 30f + 6 * rowH + 20f;
            Grid(px, pw, top, bottom, 50, 90, new float[] { 50, 60, 70, 80, 90 }, "{0}");
            float ry = top;
            foreach (var (group, rows) in data)
            {
                Ui.Label(Ui.R(x, ry + 4, labelW, 22), group, 12.5f, Ui.Ink3, true);
                ry += 30f;
                foreach (var (name, g, c, col) in rows)
                {
                    float my = ry + rowH / 2f, gx = Map(g, 50, 90, px, pw), cxp = Map(c, 50, 90, px, pw);
                    Ui.Label(Ui.R(x, ry, labelW - 20, rowH), name, 16.5f, Ui.Ink, false, TextAnchor.MiddleRight);
                    Ui.Fill(Ui.R(gx, my - 1.5f, cxp - gx, 3), new Color(col.r, col.g, col.b, 0.5f), 1.5f);
                    Ui.Ring(new Vector2(gx * Ui.S, my * Ui.S), 7f, Ui.Ink2);
                    Ui.Dot(new Vector2(cxp * Ui.S, my * Ui.S), 9f, col);
                    Ui.Label(Ui.R(gx - 90, ry, 74, rowH), F1(g), 14.5f, Ui.Ink3, false, TextAnchor.MiddleRight);
                    Ui.Label(Ui.R(cxp + 16, ry, 120, rowH), $"{F1(c)}  <color=#7ff0a8>+{F1(c - g)}</color>", 16, Ui.Ink, true, TextAnchor.MiddleLeft);
                    ry += rowH;
                }
                ry += 20f;
            }
        }

        void SideKarar(float x, float y, float w)
        {
            y = SideText(x, y, w, "NE GÖRÜYORUZ?",
                "Paket planlama her mimaride ve iki koşulda da görev puanını anlamlı artırdı (+4 ile +10 puan). Katedilen yol %17-37 kısaldı; " +
                "merkezi sürü yeni bir hedefe 29 s yerine 13 s'de vardı.");
            y = SideText(x, y, w, "ÖNEMLİ DERS",
                "İyi bir algoritma kötü bir haberleşme mimarisini kurtarmıyor: 20 dBm'de merkezi SGA 66,9, dirençli CBBA 77,8 puan aldı.");
            SideText(x, y, w, "NASIL ÖLÇÜLDÜ?",
                "Aynı 30 haritada iki yöntem karşılaştırıldı; farklar Wilcoxon testiyle anlamlı (p < 0,0001). Paket büyüklüğü 3'ten sonra puan artmıyor.");
        }

        // ------------------------------------------------------------ 3. yapay zekâ
        void ChartYz(float x, float y, float w, float h)
        {
            float yEnd = y + h;
            y = ChartTitle(x, y, w, "Yapay zekâ görev başarısını uzman kuralından daha iyi tahmin etti",
                           "ROC AUC (1 = kusursuz, 0,5 = yazı-tura) · eğitimde hiç görülmemiş test haritaları");
            float lx = x + 230f;
            lx += LegendItem(lx, y, "Uzman kuralı (elle yazıldı)", Ui.Ink3);
            LegendItem(lx, y, "Yapay zekâ (sinir ağı)", Ui.Accent);
            y += 46f;
            (string name, float uzman, float yz)[] rows = { ("Bütün test uçuşları", 0.948f, 0.978f), ("25 dBm karıştırma", 0.914f, 0.966f), ("30 dBm karıştırma", 0.760f, 0.880f) };
            float labelW = 220f, px = x + labelW, pw = w - labelW - 90f;
            float rowH = Mathf.Clamp((yEnd - y - 190f) / rows.Length, 100f, 150f), barH = Mathf.Min(44f, (rowH - 30f) / 2f);
            float top = y, bottom = y + rows.Length * rowH;
            Grid(px, pw, top, bottom, 0.5f, 1f, new[] { 0.5f, 0.6f, 0.7f, 0.8f, 0.9f, 1f }, "{0}");
            for (int i = 0; i < rows.Length; i++)
            {
                var (name, uz, yz) = rows[i];
                float ry = top + i * rowH + 12f;
                Ui.Label(Ui.R(x, ry, labelW - 20, 2 * barH + 8), name, 16.5f, Ui.Ink, false, TextAnchor.MiddleRight);
                Ui.Fill(Ui.R(px, ry, Map(uz, 0.5f, 1f, 0, pw), barH), new Color(Ui.Ink3.r, Ui.Ink3.g, Ui.Ink3.b, 0.75f), 4);
                Ui.Label(Ui.R(px + Map(uz, 0.5f, 1f, 0, pw) + 10, ry, 80, barH), uz.ToString("0.000").Replace('.', ','), 15, Ui.Ink2, false, TextAnchor.MiddleLeft);
                Ui.Fill(Ui.R(px, ry + barH + 8, Map(yz, 0.5f, 1f, 0, pw), barH), Ui.Accent, 4);
                Ui.Label(Ui.R(px + Map(yz, 0.5f, 1f, 0, pw) + 10, ry + barH + 8, 80, barH), yz.ToString("0.000").Replace('.', ','), 15, Ui.Ink, true, TextAnchor.MiddleLeft);
            }
            float sw = 260f;
            Ui.Stat(Ui.R(x + labelW, bottom + 46, sw, 96), "%92,8", "doğruluk (\"hep başarır\" demek %73,2)", Ui.Accent, 28);
            Ui.Stat(Ui.R(x + labelW + sw + 16, bottom + 46, sw, 96), "12 638", "eğitim örneği (360 uçuştan)", Ui.Ink, 28);
        }

        void SideYz(float x, float y, float w)
        {
            y = SideText(x, y, w, "NE GÖRÜYORUZ?",
                "Sinir ağı, bir İHA'nın hedefi bulup bulamayacağını elle yazılmış kuraldan daha iyi tahmin ediyor; fark en zor koşulda (30 dBm) en büyük. " +
                "Görev puanına katkısı ise küçük (+0,6 ile +0,9 puan): asıl farkı davranış kuralları yaratıyor.");
            y = SideText(x, y, w, "NASIL EĞİTİLDİ?",
                "8 girdi (karıştırma, GPS, belirsizlik, uzaklık…) → 8 gizli nöron → başarı olasılığı. Denetimli öğrenme; doğrulama ve test haritaları ayrı.");
            SideText(x, y, w, "İLK DENEME BAŞARISIZDI",
                "Önce ağı doğrudan görev puanıyla (evrim stratejileri) eğittik; öğrenemedi, çünkü uçuştan uçuşa puan gürültüsü öğrenme sinyalinden büyüktü. Yöntemi değiştirdik.");
        }

        // ------------------------------------------------------------ 4. ablasyon
        void ChartAblasyon(float x, float y, float w, float h)
        {
            float yEnd = y + h;
            y = ChartTitle(x, y, w, "Her tehdide karşı başka bir savunma işe yarıyor",
                           "Savunma tek başına kapatılınca görev puanı kaybı · en çok etkilediği senaryoda · n = 12 uçuş, hepsi anlamlı");
            (string name, string scen, float loss)[] rows =
            {
                ("Spiral arama", "hızlı GPS aldatma", 26.7f), ("Aldatma tespiti", "hızlı GPS aldatma", 19.3f),
                ("İşbirlikçi konum", "hızlı GPS aldatma", 16.6f), ("Karıştırıcı bulma", "30 dBm karıştırma", 16.0f),
                ("Güven sistemi", "sinsi saldırgan", 6.5f), ("Uzun bekleme (TTL)", "hareketli karıştırıcı", 1.9f),
            };
            float labelW = 250f, px = x + labelW, pw = w - labelW - 110f, barH = 34f;
            float rowH = Mathf.Clamp((yEnd - y - 180f) / rows.Length, 64f, 90f);
            float top = y + 10f, bottom = top + rows.Length * rowH;
            Grid(px, pw, top, bottom, 0, 30, new float[] { 0, 10, 20, 30 }, "−{0}");
            for (int i = 0; i < rows.Length; i++)
            {
                var (name, scen, loss) = rows[i];
                float ry = top + i * rowH;
                float by = ry + (rowH - barH) / 2f;
                Ui.Label(Ui.R(x, by - 6, labelW - 20, 26), name, 17.5f, Ui.Ink, true, TextAnchor.UpperRight);
                Ui.Label(Ui.R(x, by + 20, labelW - 20, 22), scen, 14f, Ui.Ink3, false, TextAnchor.UpperRight);
                Ui.Fill(Ui.R(px, by, Map(loss, 0, 30, 0, pw), barH), Ui.Good, 4);
                Ui.Label(Ui.R(px + Map(loss, 0, 30, 0, pw) + 12, by, 100, barH), "−" + loss.ToString("0.0").Replace('.', ','), 17, Ui.Ink, true, TextAnchor.MiddleLeft);
            }
            float ny = bottom + 40f;
            var note = Ui.R(x, ny, w, 84);
            Ui.Fill(note, new Color(Ui.Warn.r, Ui.Warn.g, Ui.Warn.b, 0.08f), 12);
            Ui.Label(Ui.R(x + 18, ny + 12, w - 36, 24), "Dürüst bir bulgu: \"bölgeden kaçınma\" zararlı çıktı (+1,4 puan)", 16.5f, Ui.Warn, true);
            Ui.Label(Ui.R(x + 18, ny + 40, w - 36, 40), "Karıştırma bölgesinden uzak durmaya çalışan kural yolu uzatıyor; kapatınca sürü daha iyi. " +
                                                       "Bütün savunmalar kapalıyken (korumasız sürü) kayıp 6 ile 27,5 puan arası.", 14.5f, Ui.Ink2);
        }

        void SideAblasyon(float x, float y, float w)
        {
            y = SideText(x, y, w, "NE GÖRÜYORUZ?",
                "Tek bir \"sihirli\" mekanizma yok: dayanıklılık birbirini tamamlayan savunmalardan geliyor. En önemlisi spiral arama — GPS'i kesilen ya da " +
                "aldatılan İHA hedefi görmeden \"bitti\" demiyor.");
            y = SideText(x, y, w, "ABLASYON NEDİR?",
                "Tam sistemden bir mekanizmayı çıkarıp aynı uçuşları tekrarlamak. Puan ne kadar düşerse o mekanizma o kadar önemli.");
            SideText(x, y, w, "PARAMETRELER",
                "Dört ayar parametresi ayrı haritalarda tarandı; hiçbir alternatif anlamlı daha iyi değil. Sonuçlar ayar seçimine duyarsız.");
        }

        // ------------------------------------------------------------ 5. ölçekleme
        void ChartOlcek(float x, float y, float w, float h)
        {
            float yEnd = y + h;
            y = ChartTitle(x, y, w, "Dirençli sürü büyüdükçe daha iyi; korumasız sürü 20 İHA'da geriliyor",
                           "Görev puanı · 20 dBm karıştırma · hedef sayısı = 2 × İHA sayısı · 20 uçuşun ortalaması");
            float lx = x + 170f;
            lx += LegendItem(lx, y, "Merkezi", CMerkezi, true);
            lx += LegendItem(lx, y, "Merkeziyetsiz (korumasız)", CMerkeziyetsiz);
            LegendItem(lx, y, "EH dirençli", CDirencli, false, 8f);
            y += 46f;
            (string n, float m, float d, float r, string tam)[] rows =
            {
                ("5 İHA", 67.4f, 67.2f, 73.0f, "tamamlama: %90 · %92 · %100"),
                ("10 İHA", 66.4f, 70.3f, 76.7f, "tamamlama: %86 · %90 · %100"),
                ("20 İHA", 66.4f, 65.1f, 78.5f, "tamamlama: %86 · %81 · %100"),
            };
            float labelW = 160f, px = x + labelW, pw = w - labelW - 90f;
            float rowH = Mathf.Clamp((yEnd - y - 60f) / rows.Length, 110f, 180f);
            float top = y, bottom = y + rows.Length * rowH;
            Grid(px, pw, top, bottom, 60, 82, new float[] { 60, 65, 70, 75, 80 }, "{0}");
            for (int i = 0; i < rows.Length; i++)
            {
                var (n, m, d, r, tam) = rows[i];
                float ry = top + i * rowH, my = ry + rowH / 2f - 8f;
                Ui.Label(Ui.R(x, ry, labelW - 20, rowH - 16), n, 18, Ui.Ink, true, TextAnchor.MiddleRight);
                float lo = Mathf.Min(m, Mathf.Min(d, r)), hi = Mathf.Max(m, Mathf.Max(d, r));
                Ui.Fill(Ui.R(Map(lo, 60, 82, px, pw), my - 1.5f, Map(hi, 60, 82, px, pw) - Map(lo, 60, 82, px, pw), 3), new Color(1f, 1f, 1f, 0.18f), 1.5f);
                Ui.Dot(new Vector2(Map(d, 60, 82, px, pw) * Ui.S, my * Ui.S), 8f, CMerkeziyetsiz);
                Ui.Ring(new Vector2(Map(m, 60, 82, px, pw) * Ui.S, my * Ui.S), 8f, CMerkezi);
                Ui.Dot(new Vector2(Map(r, 60, 82, px, pw) * Ui.S, my * Ui.S), 10f, CDirencli);
                Ui.Label(Ui.R(Map(r, 60, 82, px, pw) + 18, my - 12, 80, 24), F1(r), 16, Ui.Ink, true);
                var tr = Ui.R(px + 8, my + 22, Ui.TextWidth(tam + "  (merkezi · merkeziyetsiz · dirençli)", 14.5f) + 20, 26);
                Ui.Fill(tr, new Color(0.06f, 0.08f, 0.11f, 0.95f), 6);
                Ui.Label(tr, tam + "  (merkezi · merkeziyetsiz · dirençli)", 14.5f, Ui.Ink2, false, TextAnchor.MiddleCenter);
            }
        }

        void SideOlcek(float x, float y, float w)
        {
            y = SideText(x, y, w, "NE GÖRÜYORUZ?",
                "Dirençli sürünün puanı İHA sayısıyla artıyor (73 → 77 → 79) ve her boyutta hedeflerin hepsini yapıyor. Korumasız merkeziyetsiz sürü " +
                "20 İHA'da geriliyor, çünkü kalabalık ağda karıştırılan bağlantı sayısı artıyor.");
            y = SideText(x, y, w, "HESAP YÜKÜ",
                "Simülasyon saniyesi başına 66 → 111 → 208 ms: İHA sayısıyla yaklaşık doğrusal. Yöntem daha büyük sürülere de uygulanabilir.");
            SideText(x, y, w, "SALDIRGANA KARŞI",
                "%20 saldırgan İHA'da korumasız merkeziyetsiz sürü her boyutta %0, dirençli sürü her boyutta %100 tamamladı.");
        }
    }
}
