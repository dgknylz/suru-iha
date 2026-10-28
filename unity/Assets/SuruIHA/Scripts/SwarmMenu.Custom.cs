using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using UnityEngine;

namespace SuruIHA
{
    // "Kendi senaryon" sekmesi: kullanıcı haritaya tıklayarak karıştırıcı (en fazla 3) ve GPS aldatıcı koyar,
    // İHA ve hedef sayısı, arıza, saldırgan gibi ayarları seçip başlatır. Seçimler bilgisayarda hatırlanır.
    // Python'a run_live.py / run_compare.py seçenekleri olarak gider (--jammers, --spoofer, --drones...).
    public partial class SwarmMenu
    {
        [Serializable]
        class CustomSetup
        {
            public List<Vector2> jammers = new List<Vector2> { new Vector2(260f, 230f) };   // (doğu, kuzey) m
            public bool spoofer;
            public Vector2 spooferPos = new Vector2(-150f, 420f);
            public int power = 1;       // PowerSteps
            public int band;            // 0 geniş bant, 1 nokta
            public int spoofSpeed;      // 0 hızlı, 1 yavaş
            public int drones = 2;      // DroneSteps
            public int tasks = 1;       // TaskSteps
            public int popups = 1;      // PopupSteps
            public int failures;        // 0, 1, 2
            public int liars;           // 0 yok, 1 saf, 2 sinsi
        }

        static readonly int[] PowerSteps = { 10, 20, 30 };
        static readonly int[] DroneSteps = { 6, 8, 10, 12 };
        static readonly int[] TaskSteps = { 10, 20, 30 };
        static readonly int[] PopupSteps = { 0, 4, 8 };
        const int MaxJammers = 3;
        const string CustomKey = "ozel_senaryo";

        // Haritanın kapsadığı alan (m) ve görev alanı (suru/config.py: area_center (0, 380), area_half 330)
        static readonly Vector2 CustomMapMin = new Vector2(-700f, -250f);
        const float CustomMapSize = 1400f;
        static readonly Rect MissionArea = new Rect(-330f, 50f, 660f, 660f);
        const float SpooferRadius = 250f;

        CustomSetup custom = new CustomSetup();
        bool useCustom;             // son başlatma kendi senaryon ile mi
        int placeTool;              // 0 karıştırıcı, 1 GPS aldatıcı
        Texture2D customMap;
        int customMapRegion = -1;

        void LoadCustom()
        {
            try
            {
                string json = PlayerPrefs.GetString(CustomKey, "");
                if (json.Length > 0) custom = JsonUtility.FromJson<CustomSetup>(json) ?? new CustomSetup();
            }
            catch (Exception) { custom = new CustomSetup(); }
            custom.jammers ??= new List<Vector2>();
        }

        void SaveCustom()
        {
            try
            {
                PlayerPrefs.SetString(CustomKey, JsonUtility.ToJson(custom));
                PlayerPrefs.Save();
            }
            catch (Exception ex) { Debug.LogWarning("[SuruIHA] Kendi senaryon kaydedilemedi: " + ex.Message); }
        }

        // ------------------------------------------------------------------ senaryo
        static string Num(float v) => Mathf.RoundToInt(v).ToString(CultureInfo.InvariantCulture);

        string CustomSummary()
        {
            var c = custom;
            var parts = new List<string>();
            parts.Add(c.jammers.Count == 0 ? "karıştırıcı yok"
                      : $"{c.jammers.Count} karıştırıcı ({PowerSteps[c.power]} dBm, {(c.band == 1 ? "nokta" : "geniş bant")})");
            if (c.spoofer) parts.Add($"GPS aldatıcı ({(c.spoofSpeed == 0 ? "hızlı" : "yavaş")} sürükleme)");
            parts.Add($"{DroneSteps[c.drones]} İHA");
            parts.Add($"{TaskSteps[c.tasks]} hedef" + (PopupSteps[c.popups] > 0 ? $" + {PopupSteps[c.popups]} yeni" : ""));
            if (c.failures > 0) parts.Add($"{c.failures} arıza");
            if (c.liars > 0) parts.Add(c.liars == 2 ? "%20 sinsi saldırgan" : "%20 saf saldırgan");
            return string.Join(" · ", parts);
        }

        Scenario BuildCustom()
        {
            var c = custom;
            var a = new List<string>();
            if (c.jammers.Count > 0)
            {
                a.Add($"--jammer {PowerSteps[c.power]}");
                // Negatif sayılar seçenek sanılmasın diye "=" ile yazılır
                a.Add("--jammers=" + string.Join(";", c.jammers.Select(p => $"{Num(p.x)},{Num(p.y)}")));
                if (c.band == 1) a.Add("--jammer-band nokta");
            }
            else a.Add("--jammer off");
            if (c.spoofer)
            {
                a.Add("--gps-spoof " + (c.spoofSpeed == 0 ? "hizli" : "yavas"));
                a.Add($"--spoofer={Num(c.spooferPos.x)},{Num(c.spooferPos.y)}");
            }
            a.Add($"--drones {DroneSteps[c.drones]} --tasks {TaskSteps[c.tasks]} --popups {PopupSteps[c.popups]}");
            if (c.failures > 0) a.Add($"--failures {c.failures}");
            if (c.liars > 0) a.Add($"--spoof 0.2 --spoof-mode {(c.liars == 2 ? "sneaky" : "naive")}");
            string sum = CustomSummary();
            return new Scenario
            {
                Id = "ozel", Tag = "KENDİ SENARYON", TagColor = Ui.Accent, Title = "Kendi senaryon", Short = sum,
                Watch = $"Senin kurduğun senaryo: {sum}. Isı haritası karıştırıcıların gerçek etkisini tepelerin gölgesiyle " +
                        "gösterir; uçuş bitince Uçuş raporu'nda her İHA'nın ne yaptığını görürsün.",
                Args = string.Join(" ", a), Custom = true,
            };
        }

        void LaunchCustom()
        {
            SaveCustom();
            useCustom = true;
            Launch();
        }

        // ------------------------------------------------------------------ sekme
        void DrawOzelTab()
        {
            float W = Ui.W, H = Ui.H, x0 = 60f, top = BarH + 24f;
            Ui.Chip(x0, top, "KENDİ SENARYON", Ui.Accent, 11.5f);
            Ui.Label(Ui.R(x0, top + 26, 1200, 36), "Kendi senaryonu kur", 28, Ui.Ink, true);
            Ui.Label(Ui.R(x0, top + 64, 1400, 22), "Haritaya tıklayarak karıştırıcı ve GPS aldatıcı koy (aynı yere tekrar tıklayınca kalkar), " +
                                                  "sağdan ayarları seç ve başlat. Seçimlerin bu bilgisayarda hatırlanır.", 15, Ui.Ink3);

            float my = top + 156f;
            float M = Mathf.Clamp(H - my - 110f, 360f, 640f);
            DrawPlacementTools(x0, top + 104f, M);
            DrawCustomMap(x0, my, M);
            DrawCustomLegend(x0, my + M + 12f, M);

            float rx = x0 + M + 44f;
            DrawCustomSettings(rx, top + 104f, W - rx - 60f, H);
        }

        void DrawPlacementTools(float x, float y, float w)
        {
            const float bh = 40f;
            float b1 = 230f, b2 = 200f;
            if (Ui.Button(Ui.R(x, y, b1, bh), $"Karıştırıcı koy ({custom.jammers.Count}/{MaxJammers})", Ui.Kind.Normal, placeTool == 0, 15))
                placeTool = 0;
            if (Ui.Button(Ui.R(x + b1 + 8, y, b2, bh), custom.spoofer ? "GPS aldatıcıyı taşı" : "GPS aldatıcı koy", Ui.Kind.Normal,
                          placeTool == 1, 15))
                placeTool = 1;
            if (Ui.Button(Ui.R(x + w - 120f, y, 120f, bh), "Temizle", Ui.Kind.Ghost, size: 15))
            {
                custom.jammers.Clear();
                custom.spoofer = false;
            }
        }

        // Haritanın arka planı: arazi gölgelemesi (bir kez)
        void BuildCustomMap()
        {
            var v = SwarmVisualizer.Main;
            if ((customMap != null && customMapRegion == region) || v == null) return;
            customMapRegion = region;
            var origin = SwarmRegions.Offset(SwarmRegions.Ids[region]);
            const int N = 320;
            float cell = CustomMapSize / N;
            var h = new float[N * N];
            for (int j = 0, k = 0; j < N; j++)
            for (int i = 0; i < N; i++, k++)
                h[k] = v.RegionGroundHeight(origin, CustomMapMin.x + (i + 0.5f) * cell, CustomMapMin.y + (j + 0.5f) * cell);
            var px = new Color32[N * N];
            var light = new Vector3(-0.6f, 1.1f, 0.6f).normalized;
            var low = new Color(0.13f, 0.13f, 0.12f);
            var high = new Color(0.56f, 0.51f, 0.42f);
            for (int j = 0, k = 0; j < N; j++)
            for (int i = 0; i < N; i++, k++)
            {
                float dx = (h[j * N + Mathf.Min(i + 1, N - 1)] - h[j * N + Mathf.Max(i - 1, 0)]) / (2f * cell);
                float dz = (h[Mathf.Min(j + 1, N - 1) * N + i] - h[Mathf.Max(j - 1, 0) * N + i]) / (2f * cell);
                Color c = Color.Lerp(low, high, Mathf.Clamp01(Vector3.Dot(new Vector3(-dx, 1f, -dz).normalized, light)));
                c.a = 1f;
                px[k] = c;
            }
            if (customMap == null)
                customMap = new Texture2D(N, N, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear };
            customMap.SetPixels32(px);
            customMap.Apply(false);
        }

        // Karıştırıcının etki yarıçapları (düz arazi varsayımı; suru/radio.py ile aynı model):
        // 60 m'lik bağlantının paketlerinin yarısının koptuğu yer ve GPS'in kesildiği yer (yalnız geniş bant)
        static float LinkCutRadius(float commDbm)
        {
            const float tx = 20f, pl0 = 40f, n = 2.5f, sinrTh = 10f, noise = -95f;
            float signal = tx - (pl0 + 10f * n * Mathf.Log10(60f));
            float needed = Mathf.Pow(10f, (signal - sinrTh) / 10f) - Mathf.Pow(10f, noise / 10f);
            return Mathf.Pow(10f, (commDbm - 10f * Mathf.Log10(needed) - pl0) / (10f * n));
        }

        static float GpsLossRadius(float dbm) => Mathf.Pow(10f, (dbm + 80f - 40f) / 25f);   // -80 dBm'de GPS kesilir

        void DrawCustomMap(float x, float y, float M)
        {
            BuildCustomMap();
            var mr = Ui.R(x, y, M, M);
            if (customMap != null) GUI.DrawTexture(mr, customMap);
            else Ui.Fill(mr, new Color(0.1f, 0.1f, 0.1f));
            Ui.Block(mr);
            float s = mr.width / CustomMapSize;    // piksel / m
            Vector2 P(Vector2 w) => new Vector2(mr.x + (w.x - CustomMapMin.x) * s, mr.y + (1f - (w.y - CustomMapMin.y) / CustomMapSize) * mr.height);
            Vector2 World(Vector2 p) => new Vector2(CustomMapMin.x + (p.x - mr.x) / s, CustomMapMin.y + (1f - (p.y - mr.y) / mr.height) * CustomMapSize);
            void Circle(Vector2 c, float rM, Color fill, Color edge, float width)
            {
                float r = rM * s;
                var rr = new Rect(c.x - r, c.y - r, 2 * r, 2 * r);
                if (fill.a > 0f) GUI.DrawTexture(rr, Texture2D.whiteTexture, ScaleMode.StretchToFill, true, 0f, fill, 0f, r);
                GUI.DrawTexture(rr, Texture2D.whiteTexture, ScaleMode.StretchToFill, true, 0f, edge, width * Ui.S, r);
            }

            GUI.BeginClip(mr);
            mr = new Rect(0, 0, mr.width, mr.height);   // kırpma içinde yerel koordinat
            // Görev alanı ve üs
            var a0 = P(new Vector2(MissionArea.xMin, MissionArea.yMax));
            var a1 = P(new Vector2(MissionArea.xMax, MissionArea.yMin));
            var ar = Rect.MinMaxRect(a0.x, a0.y, a1.x, a1.y);
            GUI.DrawTexture(ar, Texture2D.whiteTexture, ScaleMode.StretchToFill, true, 0f, new Color(1f, 1f, 1f, 0.05f), 0f, 0f);
            GUI.DrawTexture(ar, Texture2D.whiteTexture, ScaleMode.StretchToFill, true, 0f, new Color(1f, 1f, 1f, 0.45f), 1.5f * Ui.S, 0f);
            GUI.Label(new Rect(ar.x + 8 * Ui.S, ar.y + 6 * Ui.S, 200 * Ui.S, 20 * Ui.S), "görev alanı", Ui.Style(13, Ui.Ink2, true));
            var g = P(Vector2.zero);
            Ui.Fill(new Rect(g.x - 6 * Ui.S, g.y - 6 * Ui.S, 12 * Ui.S, 12 * Ui.S), Ui.Accent, 2);
            GUI.Label(new Rect(g.x + 9 * Ui.S, g.y - 10 * Ui.S, 60 * Ui.S, 20 * Ui.S), "Üs", Ui.Style(13, Ui.Accent, true));

            // GPS aldatıcı
            var cyan = new Color(0.1f, 0.75f, 1f);
            if (custom.spoofer)
            {
                var sp = P(custom.spooferPos);
                Circle(sp, SpooferRadius, new Color(cyan.r, cyan.g, cyan.b, 0.12f), cyan, 2f);
                Ui.Dot(sp, 5f, cyan);
            }
            // Karıştırıcılar: düz arazide GPS'in kesildiği alan (geniş bant) ve bağlantının koptuğu alan
            float comm = PowerSteps[custom.power] + (custom.band == 1 ? 6.2f : 0f);
            for (int i = 0; i < custom.jammers.Count; i++)
            {
                var jp = P(custom.jammers[i]);
                if (custom.band == 0) Circle(jp, GpsLossRadius(PowerSteps[custom.power]), new Color(1f, 0.3f, 0.2f, 0.08f), new Color(1f, 0.45f, 0.35f, 0.7f), 1.5f);
                Circle(jp, LinkCutRadius(comm), new Color(1f, 0.2f, 0.12f, 0.2f), new Color(1f, 0.92f, 0.88f, 0.9f), 2f);
                Ui.Dot(jp, 7f, Ui.Bad);
                GUI.Label(new Rect(jp.x - 10 * Ui.S, jp.y - 10 * Ui.S, 20 * Ui.S, 20 * Ui.S), (i + 1).ToString(),
                          Ui.Style(12.5f, Color.white, true, TextAnchor.MiddleCenter, false));
            }

            // Tıklama: yakındaki işareti kaldırır, boş yere yenisini koyar
            var e = Event.current;
            if (e.type == EventType.MouseDown && e.button == 0 && mr.Contains(e.mousePosition))
            {
                Vector2 w = World(e.mousePosition);
                float near = 18f * Ui.S / s;      // 18 piksel (m cinsinden)
                if (placeTool == 0)
                {
                    int hit = custom.jammers.FindIndex(j => (j - w).magnitude < near);
                    if (hit >= 0) custom.jammers.RemoveAt(hit);
                    else if (custom.jammers.Count < MaxJammers) custom.jammers.Add(new Vector2(Mathf.Round(w.x), Mathf.Round(w.y)));
                }
                else
                {
                    if (custom.spoofer && (custom.spooferPos - w).magnitude < near) custom.spoofer = false;
                    else { custom.spoofer = true; custom.spooferPos = new Vector2(Mathf.Round(w.x), Mathf.Round(w.y)); }
                }
                e.Use();
            }
            if (mr.Contains(e.mousePosition))
                tip = placeTool == 0 ? (custom.jammers.Count < MaxJammers ? "Tıkla: karıştırıcı koy · üstüne tıkla: kaldır"
                                                                        : "En fazla 3 karıştırıcı · üstüne tıklayıp birini kaldır")
                                     : "Tıkla: GPS aldatıcıyı buraya koy · üstüne tıkla: kaldır";
            GUI.EndClip();
            Ui.Outline(Ui.R(x, y, M, M), Ui.Line, 1f);
            if (tip != null && Ui.R(x, y, M, M).Contains(Event.current.mousePosition))
                Ui.Label(Ui.R(x + 12, y + M - 34, M - 24, 24), tip, 13.5f, Ui.Ink, true);
        }

        void DrawCustomLegend(float x, float y, float w)
        {
            float cx = x;
            void Item(Color fill, Color edge, string text)
            {
                var r = Ui.R(cx, y + 2, 16, 16);
                Ui.Fill(r, fill, 8);
                Ui.Outline(r, edge, 1.5f, 8);
                Ui.Label(Ui.R(cx + 22, y, 300, 20), text, 13f, Ui.Ink2);
                cx += 22f + Ui.TextWidth(text, 13f) + 18f;
            }
            Item(new Color(1f, 0.2f, 0.12f, 0.35f), new Color(1f, 0.92f, 0.88f), "bağlantı kopar");
            if (custom.band == 0) Item(new Color(1f, 0.3f, 0.2f, 0.15f), new Color(1f, 0.45f, 0.35f), "GPS kesilir");
            Item(new Color(0.1f, 0.75f, 1f, 0.2f), new Color(0.1f, 0.75f, 1f), "GPS aldatıcı (250 m)");
            Ui.Label(Ui.R(x, y + 24, w, 20), "Daireler düz arazi içindir; tepelerin gölgesi uçuşta ısı haritasında görünür.", 12.5f, Ui.Ink3);
        }

        void DrawCustomSettings(float x, float y, float w, float H)
        {
            const float labelW = 210f, rowH = 46f;
            float sx = x + labelW, segW = Mathf.Min(150f, (w - labelW - 18f) / 4f);
            int Row(string label, string[] items, int sel, Func<int, bool> enabled = null)
            {
                Ui.Label(Ui.R(x, y + 11, labelW, 24), label, 16, Ui.Ink2, true);
                sel = Segments(sx, y, segW, items, sel, enabled);
                y += rowH;
                return sel;
            }
            bool jam = custom.jammers.Count > 0;
            custom.power = Row("Karıştırıcı gücü", new[] { "10 dBm", "20 dBm", "30 dBm" }, custom.power, _ => jam);
            custom.band = Row("Karıştırıcı türü", new[] { "Geniş bant", "Nokta" }, custom.band, _ => jam);
            custom.spoofSpeed = Row("GPS aldatma", new[] { "Hızlı", "Yavaş" }, custom.spoofSpeed, _ => custom.spoofer);
            custom.drones = Row("İHA sayısı", DroneSteps.Select(n => n.ToString()).ToArray(), custom.drones);
            custom.tasks = Row("Hedef sayısı", TaskSteps.Select(n => n.ToString()).ToArray(), custom.tasks);
            custom.popups = Row("Görevde yeni hedef", new[] { "Yok", "4", "8" }, custom.popups);
            custom.failures = Row("Arızalanan İHA", new[] { "Yok", "1", "2" }, custom.failures);
            custom.liars = Row("Saldırgan İHA", new[] { "Yok", "Saf", "Sinsi" }, custom.liars);
            y += 8f;
            // Bölge: altı harita iki sıra halinde
            Ui.Label(Ui.R(x, y + 11, labelW, 24), "Bölge", 16, Ui.Ink2, true);
            for (int i = 0; i < SwarmRegions.Ids.Length; i++)
                if (Ui.Button(Ui.R(sx + (i % 3) * (segW + 6), y + (i / 3) * 48f, segW, 44), SwarmRegions.ShortTitles[i], Ui.Kind.Normal, i == region, 16))
                    region = i;
            y += rowH + 48f;
            int view = Row("Görünüm", new[] { "Tek sürü", "Yan yana" }, compare ? 1 : 0);
            if (view == 1 && !compare && strategy == 2) strategy = 1;
            compare = view == 1;
            strategy = Row(compare ? "Soldaki sürü" : "Karar mimarisi", new[] { "Merkezi", "Merkeziyetsiz", "Dirençli" }, strategy,
                           i => !compare || i < 2);
            planner = Row("Görev paylaşımı", new[] { "Açgözlü", "CBBA", "CBBA + YZ" }, planner);
            fast = Row("Hız", new[] { "Normal", "Hızlı" }, fast ? 1 : 0) == 1;

            y += 6f;
            string sum = CustomSummary();
            float bw = 260f;
            float tw = w - bw - 24f;
            float th = Mathf.Max(Ui.TextHeight(sum, 15.5f, tw - 32f), 22f);
            Ui.Fill(Ui.R(x, y, tw, th + 50f), new Color(1f, 1f, 1f, 0.05f), 12);
            Ui.Label(Ui.R(x + 16, y + 12, tw - 32, 18), "SENARYON", 11.5f, Ui.Accent, true);
            Ui.Label(Ui.R(x + 16, y + 34, tw - 32, th), sum, 15.5f, Ui.Ink);
            if (Ui.Button(Ui.R(x + w - bw, y, bw, 62), "Başlat", Ui.Kind.Primary, size: 21, icon: true,
                          enabled: launcher.CanLaunch || launcher.Status == SimLauncher.State.External))
                LaunchCustom();
            if (Ui.Button(Ui.R(x + w - bw, y + 70, bw, 40), "Varsayılana dön", Ui.Kind.Ghost, size: 14))
                custom = new CustomSetup();
        }
    }
}
