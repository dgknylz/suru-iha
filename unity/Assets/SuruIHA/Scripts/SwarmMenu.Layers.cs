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
            (v.showTrails ? 1 : 0) << 5 | (v.showBeacons ? 1 : 0) << 6;

        static int Pref(string key, int def)
        {
            try { return PlayerPrefs.GetInt(key, def); }
            catch (System.Exception) { return def; }
        }

        // Varsayılan görünüm: bağlantılar kapalı (ekran temiz); planlar, hayaletler, izler ve uzak işaretler açık
        static void DefaultLayers(SwarmVisualizer v)
        {
            SetLinkMode(v, 0);
            v.showPlans = true;
            v.showEstimates = true;
            v.showJamMap = false;
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

        void DrawLayersPanel(float above)
        {
            var v = SwarmVisualizer.Main;
            if (v == null) return;
            const float w = 680f, rowH = 66f;
            float h = 54f + 6 * rowH + 66f;
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
            v.showJamMap = LayerRow(rx, ry, rw, "Karıştırma haritası", "Sürünün ölçüp paylaştığı karıştırma bölgeleri", OnOff, v.showJamMap ? 1 : 0) == 1;
            ry += rowH;
            v.showTrails = LayerRow(rx, ry, rw, "Uçuş izleri", "İHA'ların arkasında bıraktığı iz", OnOff, v.showTrails ? 1 : 0) == 1;
            ry += rowH;
            v.showBeacons = LayerRow(rx, ry, rw, "Uzak işaretler", "Uzaktan bakınca İHA'ları gösteren parlak noktalar", OnOff, v.showBeacons ? 1 : 0) == 1;
            ry += rowH + 6f;

            if (Ui.Button(Ui.R(rx, ry, 190, 44), "Hepsini kapat", Ui.Kind.Ghost, size: 15))
            {
                SetLinkMode(v, 0);
                v.showPlans = v.showEstimates = v.showJamMap = v.showTrails = v.showBeacons = false;
            }
            if (Ui.Button(Ui.R(rx + 200, ry, 190, 44), "Varsayılan", size: 15)) DefaultLayers(v);
        }
    }
}
