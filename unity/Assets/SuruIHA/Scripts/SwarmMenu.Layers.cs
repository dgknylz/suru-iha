using UnityEngine;

namespace SuruIHA
{
    // "Katmanlar" paneli: sahnedeki çizgiler ve işaretler ayrı ayrı açılıp kapanır. Seçimler bilgisayarda
    // hatırlanır (PlayerPrefs); kısayol tuşlarıyla yapılan değişiklikler de kaydedilir.
    public partial class SwarmMenu
    {
        bool layersOpen;
        int savedLayers = -1;

        static readonly string[] OnOff = { "Kapalı", "Açık" };
        static readonly string[] LinkModes = { "Kapalı", "Sorunlu", "Hepsi" };

        // Bağlantılar: 0 kapalı, 1 yalnızca sorunlu (karıştırılan), 2 hepsi
        static int LinkMode(SwarmVisualizer v) => !v.showLinks ? 0 : v.onlyWeakLinks ? 1 : 2;

        static void SetLinkMode(SwarmVisualizer v, int m)
        {
            v.showLinks = m > 0;
            v.onlyWeakLinks = m == 1;
        }

        static int PackLayers(SwarmVisualizer v) =>
            LinkMode(v) | (v.showPlans ? 1 : 0) << 2 | (v.showEstimates ? 1 : 0) << 3 | (v.showJamMap ? 1 : 0) << 4 |
            (v.showTrails ? 1 : 0) << 5 | (v.showBeacons ? 1 : 0) << 6 | (v.showHeatMap ? 1 : 0) << 7;

        static int Pref(string key, int def)
        {
            try { return PlayerPrefs.GetInt(key, def); }
            catch (System.Exception) { return def; }
        }

        // Varsayılan görünüm: bağlantılar kapalı (ekran temiz); ısı haritası, planlar, hayaletler, izler ve uzak işaretler açık
        static void DefaultLayers(SwarmVisualizer v)
        {
            SetLinkMode(v, 0);
            v.showPlans = true;
            v.showEstimates = true;
            v.showJamMap = false;
            v.showHeatMap = true;
            v.showTrails = true;
            v.showBeacons = true;
        }

        void LoadLayers()
        {
            var v = SwarmVisualizer.Main;
            if (v == null) return;
            SetLinkMode(v, Mathf.Clamp(Pref("katman_baglanti", 0), 0, 2));
            v.showPlans = Pref("katman_plan", 1) == 1;
            v.showEstimates = Pref("katman_hayalet", 1) == 1;
            v.showJamMap = Pref("katman_ehharita", 0) == 1;
            v.showHeatMap = Pref("katman_isi", 1) == 1;
            v.showTrails = Pref("katman_iz", 1) == 1;
            v.showBeacons = Pref("katman_isaret", 1) == 1;
            savedLayers = PackLayers(v);
        }

        void SaveLayersIfChanged()
        {
            var v = SwarmVisualizer.Main;
            if (v == null || savedLayers < 0) return;
            int now = PackLayers(v);
            if (now == savedLayers) return;
            savedLayers = now;
            try
            {
                PlayerPrefs.SetInt("katman_baglanti", LinkMode(v));
                PlayerPrefs.SetInt("katman_plan", v.showPlans ? 1 : 0);
                PlayerPrefs.SetInt("katman_hayalet", v.showEstimates ? 1 : 0);
                PlayerPrefs.SetInt("katman_ehharita", v.showJamMap ? 1 : 0);
                PlayerPrefs.SetInt("katman_isi", v.showHeatMap ? 1 : 0);
                PlayerPrefs.SetInt("katman_iz", v.showTrails ? 1 : 0);
                PlayerPrefs.SetInt("katman_isaret", v.showBeacons ? 1 : 0);
                PlayerPrefs.Save();
            }
            catch (System.Exception ex) { Debug.LogWarning("[SuruIHA] Katman ayarları kaydedilemedi: " + ex.Message); }
        }

        // Bir katman satırı: başlık, açıklama ve sağda seçim düğmeleri; yeni seçimi döndürür
        static int LayerRow(float x, float y, float w, string title, string desc, string[] opts, int sel)
        {
            const float segW = 88f, gap = 6f;
            float segTotal = opts.Length * segW + (opts.Length - 1) * gap;
            float tw = w - segTotal - 24f;
            Ui.Label(Ui.R(x, y, tw, 22), title, 16, Ui.Ink, true);
            Ui.Label(Ui.R(x, y + 23, tw, 34), desc, 13, Ui.Ink3);
            float sx = x + w - segTotal;
            for (int i = 0; i < opts.Length; i++)
                if (Ui.Button(Ui.R(sx + i * (segW + gap), y + 6, segW, 38), opts[i], Ui.Kind.Normal, i == sel, 14.5f)) sel = i;
            return sel;
        }

        // Isı haritası açıkken sol altta renk skalası: renkler haritada göründükleri gibi (araziye karışmış) çizilir
        static readonly Color GroundTone = new Color(0.62f, 0.52f, 0.38f);

        void DrawHeatScale(float above)
        {
            var v = SwarmVisualizer.Main;
            var F = v != null && v.showHeatMap ? v.Field : null;
            if (F == null) return;
            const float w = 380f, h = 200f, x = 20f;
            float y = above - 16f - h;
            Ui.Panel(Ui.R(x, y, w, h), 14, 0.92f);
            Ui.Label(Ui.R(x + 20, y + 14, w - 40, 18), "KARIŞTIRMA ISI HARİTASI", 11.5f, Ui.Accent, true);
            Ui.Label(Ui.R(x + 20, y + 32, w - 40, 20), $"Yerden {F.agl:0} m yükseklikte karıştırma gücü", 13.5f, Ui.Ink2);

            float bx = x + 20f, bw = w - 40f, by = y + 76f, bh = 16f;
            float lo = SwarmVisualizer.HeatLow(F.detect), hi = SwarmVisualizer.HeatHigh(F.cut);
            const int n = 84;
            for (int i = 0; i < n; i++)
            {
                Color c = SwarmVisualizer.HeatColor(Mathf.Lerp(lo, hi, (i + 0.5f) / n), F.detect, F.cut);
                Ui.Fill(Ui.R(bx + bw * i / n, by, bw / n + 0.5f, bh), Color.Lerp(GroundTone, new Color(c.r, c.g, c.b), c.a));
            }
            float px(float J) => bx + bw * Mathf.InverseLerp(lo, hi, J);
            float xd = px(F.detect), xc = px(F.cut);
            var tick = new Color(1f, 0.93f, 0.9f);
            var faint = new Color(1f, 0.84f, 0.8f, 0.6f);
            Ui.Fill(Ui.R(xd - 0.5f, by - 5f, 1.2f, bh + 10f), faint);      // ince soluk: fark etme
            Ui.Fill(Ui.R(xc - 1.5f, by - 5f, 3f, bh + 10f), tick);         // kalın parlak: bağlantı kopması
            Ui.Label(Ui.R(xd - 140f, by + bh + 4f, 138f, 18f), "fark edilir", 12.5f, Ui.Ink2, false, TextAnchor.UpperRight);
            Ui.Label(Ui.R(xc + 4f, by + bh + 4f, 160f, 18f), "bağlantı kopar", 12.5f, Ui.Ink2);
            Ui.Label(Ui.R(bx, by - 21f, bw, 18f), "zayıf", 12f, Ui.Ink3);
            Ui.Label(Ui.R(bx, by - 21f, bw, 18f), "güçlü", 12f, Ui.Ink3, false, TextAnchor.UpperRight);

            float ly = by + bh + 30f;
            Ui.Fill(Ui.R(bx, ly + 8.5f, 24f, 1.2f), faint);
            Ui.Label(Ui.R(bx + 34f, ly, bw - 34f, 20f), $"İHA karıştırmayı fark eder ({F.detect:0} dBm)", 13f, Ui.Ink);
            Ui.Fill(Ui.R(bx, ly + 27.5f, 24f, 3f), tick);
            Ui.Label(Ui.R(bx + 34f, ly + 20f, bw - 34f, 20f), $"60 m'deki komşuyla bağlantı kopar ({F.cut:0} dBm)", 13f, Ui.Ink);
            Ui.Label(Ui.R(bx, ly + 44f, bw, 20f), "Tepelerin ardındaki açık boşluklar: arazi gölgesi", 12.5f, Ui.Ink3);
        }

        void DrawLayersPanel(float above)
        {
            var v = SwarmVisualizer.Main;
            if (v == null) return;
            const float w = 680f, rowH = 66f;
            float h = 54f + 7 * rowH + 66f;
            float x = 430f, y = above - 16f - h;   // soldaki bilgi panelinin yanında
            Ui.Panel(Ui.R(x, y, w, h), 14, 0.95f);
            Ui.Label(Ui.R(x + 22, y + 16, 300, 20), "GÖRÜNÜM KATMANLARI", 11.5f, Ui.Accent, true);
            if (Ui.Button(Ui.R(x + w - 48, y + 10, 32, 32), "×", Ui.Kind.Ghost, size: 18)) layersOpen = false;
            float rx = x + 22f, rw = w - 44f, ry = y + 50f;

            SetLinkMode(v, LayerRow(rx, ry, rw, "İHA bağlantıları",
                "Haberleşme çizgileri. Sorunlu: yalnızca karıştırılan, zayıflamış bağlantılar", LinkModes, LinkMode(v)));
            ry += rowH;
            v.showPlans = LayerRow(rx, ry, rw, "İHA planları", "Her İHA'nın sıradaki hedeflerine giden rota (CBBA)", OnOff, v.showPlans ? 1 : 0) == 1;
            ry += rowH;
            v.showEstimates = LayerRow(rx, ry, rw, "Konum hayaletleri", "GPS'siz İHA'nın kendini sandığı yer ve belirsizlik halkası", OnOff, v.showEstimates ? 1 : 0) == 1;
            ry += rowH;
            v.showHeatMap = LayerRow(rx, ry, rw, "Karıştırma ısı haritası", "Gerçek karıştırma gücü, tepelerin gölgesiyle (fizik modeli)", OnOff, v.showHeatMap ? 1 : 0) == 1;
            ry += rowH;
            v.showJamMap = LayerRow(rx, ry, rw, "Sürünün karıştırma haritası", "İHA'ların ölçüp paylaştığı bölgeler (sürünün bildiği)", OnOff, v.showJamMap ? 1 : 0) == 1;
            ry += rowH;
            v.showTrails = LayerRow(rx, ry, rw, "Uçuş izleri", "İHA'ların arkasında bıraktığı iz", OnOff, v.showTrails ? 1 : 0) == 1;
            ry += rowH;
            v.showBeacons = LayerRow(rx, ry, rw, "Uzak işaretler", "Uzaktan bakınca İHA'ları gösteren parlak noktalar", OnOff, v.showBeacons ? 1 : 0) == 1;
            ry += rowH + 6f;

            if (Ui.Button(Ui.R(rx, ry, 190, 44), "Hepsini kapat", Ui.Kind.Ghost, size: 15))
            {
                SetLinkMode(v, 0);
                v.showPlans = v.showEstimates = v.showJamMap = v.showHeatMap = v.showTrails = v.showBeacons = false;
            }
            if (Ui.Button(Ui.R(rx + 200, ry, 190, 44), "Varsayılan", size: 15)) DefaultLayers(v);
        }
    }
}
