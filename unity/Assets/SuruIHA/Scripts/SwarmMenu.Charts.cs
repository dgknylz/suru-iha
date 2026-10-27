using System;
using System.Collections.Generic;
using UnityEngine;
using Sample = SuruIHA.SwarmVisualizer.MetricSample;

namespace SuruIHA
{
    // Canlı grafikler: uçuş boyunca paket iletimi, GPS'siz uçan İHA sayısı ve görev puanı. Simülasyon sırasında
    // sağda olay akışının altında, uçuş raporunda "Uçuş boyunca" bölümünde. Yan yana uçuşta iki sürü aynı grafikte
    // (solda korumasız, sağda dirençli). Çizgiler kenarı yumuşatılmış olarak küçük bir dokuya çizilir (IMGUI'de çizgi
    // yok) ve yalnızca yeni ölçüm gelince yenilenir; üstüne gelince o anın değeri okunur.
    public partial class SwarmMenu
    {
        bool chartsOpen = true;

        static readonly Color SeriesSingle = Ui.Accent;
        static readonly Color SeriesLeft = new Color(1f, 0.62f, 0.26f);     // yan yana: korumasız (üst başlığın rengi)
        static readonly Color SeriesRight = Ui.Good;                        // yan yana: EH dirençli

        struct ChartDef
        {
            public string title;
            public Func<Sample, float> val;
            public Func<float, string> fmt;
            public float yMax;
        }

        static ChartDef[] Charts(int drones) => new[]
        {
            new ChartDef { title = "Paket iletimi", val = s => s.pdr * 100f, fmt = v => $"%{v:0}", yMax = 100f },
            // GPS'i karıştırılan ya da aldatmayı fark edip GPS'e güvenmeyen: konumunu GPS'siz bulan İHA
            new ChartDef { title = "GPS'siz uçan İHA", val = s => s.gpsLost, fmt = v => $"{v:0}", yMax = Mathf.Max(drones, 1) },
            new ChartDef { title = "Görev puanı", val = s => s.score * 100f, fmt = v => $"{v:0}", yMax = 100f },
        };

        // Simülasyon ekranındaki kart; çizdiği yüksekliği döndürür (yer yoksa çizmez)
        float DrawLiveCharts(float x, float y, float w, float maxH)
        {
            var A = SwarmVisualizer.Main;
            if (A == null || A.History.Count < 2) return 0f;
            var B = CompareOn ? SwarmCompare.Instance.B : null;
            if (B != null && B.History.Count < 2) B = null;
            const float head = 40f, ch = 70f, gap = 8f, axis = 18f;
            float h = head + 3 * ch + 2 * gap + axis + 12f;
            if (h > maxH) return 0f;
            Ui.Panel(Ui.R(x, y, w, h), 14, 0.86f);
            Ui.Label(Ui.R(x + 18, y + 14, w - 36, 18), "CANLI GRAFİKLER", 11.5f, Ui.Ink3, true);
            if (B != null) ChartLegend(x + w - 18f, y + 12f);
            float tMax = Mathf.Max(60f, Last(A.History).t, B != null ? Last(B.History).t : 0f);
            int ver = A.HistoryVersion * 7919 + (B != null ? B.HistoryVersion : 0);
            var defs = Charts(Mathf.Max(A.DroneCount, B != null ? B.DroneCount : 0));
            float cy = y + head;
            for (int i = 0; i < defs.Length; i++)
            {
                MiniChart($"canli{i}", x + 18f, cy, w - 36f, ch, defs[i], tMax, ver, i == defs.Length - 1,
                          A.History, B != null ? SeriesLeft : SeriesSingle, B?.History, SeriesRight);
                cy += ch + gap;
            }
            return h;
        }

        // Uçuş raporundaki "Uçuş boyunca" bölümü (raporun kendi kopyası; yan yana uçuşta seçili sürü)
        void DrawReportCharts(float x, float y, float w, float h, SwarmVisualizer v)
        {
            var hist = v.ReportHistory;
            Ui.Fill(Ui.R(x, y, w, h), new Color(1f, 1f, 1f, 0.04f), 14);
            Ui.Label(Ui.R(x + 20, y + 14, w - 40, 20), "UÇUŞ BOYUNCA", 11.5f, Ui.Accent, true);
            if (hist == null || hist.Count < 2)
            {
                Ui.Label(Ui.R(x + 20, y + 44, w - 40, 40), "Bu uçuşun ölçümleri kaydedilmedi (uygulama uçuşun ortasında açıldı).", 14f, Ui.Ink3);
                return;
            }
            const float head = 42f, axis = 18f, gap = 8f;
            float ch = Mathf.Max(48f, (h - head - axis - 2 * gap - 10f) / 3f);
            float tMax = Mathf.Max(60f, Last(hist).t);
            var defs = Charts(v.DroneCount);
            float cy = y + head;
            for (int i = 0; i < defs.Length; i++)
            {
                MiniChart($"rapor{i}", x + 20f, cy, w - 40f, ch, defs[i], tMax, v.ReportVersion * 31 + v.GetInstanceID(),
                          i == defs.Length - 1, hist, SeriesSingle, null, default);
                cy += ch + gap;
            }
        }

        void ChartLegend(float right, float y)
        {
            float x = right;
            foreach (var (text, col) in new[] { ("sağda dirençli", SeriesRight), ("solda korumasız", SeriesLeft) })
            {
                float tw = Ui.TextWidth(text, 12.5f);
                x -= tw;
                Ui.Label(Ui.R(x, y, tw + 4, 18), text, 12.5f, Ui.Ink2);
                x -= 22f;
                Ui.Fill(Ui.R(x, y + 8f, 16f, 3f), col, 1.5f);
                x -= 14f;
            }
        }

        static Sample Last(List<Sample> s) => s[s.Count - 1];

        // Bir grafik: başlık ve anlık değer(ler), ızgara, seriler; axis: altta zaman ekseni yazısı
        void MiniChart(string id, float x, float y, float w, float h, ChartDef def, float tMax, int version, bool axis,
                       List<Sample> a, Color ca, List<Sample> b, Color cb)
        {
            Ui.Label(Ui.R(x, y, w * 0.6f, 18), def.title, 13f, Ui.Ink2);
            // Anlık değer: yazı mürekkep renginde, yanında serinin rengi (renk tek başına kimlik taşımasın)
            float vx = x + w;
            foreach (var (s, c) in b != null ? new[] { (b, cb), (a, ca) } : new[] { (a, ca) })
            {
                string vt = def.fmt(def.val(Last(s)));
                float tw = Ui.TextWidth(vt, 15f, true);
                vx -= tw;
                Ui.Label(Ui.R(vx, y - 2f, tw + 4, 20), vt, 15f, Ui.Ink, true);
                vx -= 16f;
                if (b != null) Ui.Fill(Ui.R(vx, y + 7f, 10f, 3f), c, 1.5f);
                vx -= 12f;
            }
            float py = y + 20f, ph = h - 22f;
            var plot = Ui.R(x, py, w, ph);
            Ui.Fill(plot, new Color(1f, 1f, 1f, 0.025f), 4);
            Ui.Fill(Ui.R(x, py + ph * 0.5f, w, 1f), new Color(1f, 1f, 1f, 0.06f));     // orta çizgi
            Ui.Fill(Ui.R(x, py + ph - 1f, w, 1f), new Color(1f, 1f, 1f, 0.12f));       // taban
            Ui.Label(Ui.R(x + 4f, py + 1f, 80, 14), def.fmt(def.yMax), 10.5f, Ui.Ink3);
            var tex = ChartTexture(id, Mathf.Max(8, Mathf.RoundToInt(plot.width)), Mathf.Max(8, Mathf.RoundToInt(plot.height)),
                                   version, def, tMax, a, ca, b, cb);
            GUI.DrawTexture(plot, tex);
            if (axis)
            {
                Ui.Label(Ui.R(x, py + ph + 2f, 80, 14), "0 s", 10.5f, Ui.Ink3);
                Ui.Label(Ui.R(x + w - 120f, py + ph + 2f, 120, 14), $"{tMax:0} s", 10.5f, Ui.Ink3, false, TextAnchor.UpperRight);
            }
            // Üstüne gelince: dikey çizgi ve o anın değeri
            var mp = Event.current.mousePosition;
            if (plot.Contains(mp))
            {
                float t = (mp.x - plot.x) / plot.width * tMax;
                Ui.Fill(new Rect(mp.x, plot.y, Mathf.Max(1f, Ui.S), plot.height), new Color(1f, 1f, 1f, 0.5f));
                string tip = $"t = {t:0} s · " + def.fmt(def.val(At(a, t))) + (b != null ? " / " + def.fmt(def.val(At(b, t))) : "");
                float tw = (Ui.TextWidth(tip, 12.5f) + 16f) * Ui.S;
                var r = new Rect(Mathf.Min(mp.x + 8f * Ui.S, plot.xMax - tw), plot.y + 2f * Ui.S, tw, 20f * Ui.S);
                Ui.Fill(r, new Color(0.03f, 0.05f, 0.07f, 0.92f), 6f);
                GUI.Label(r, tip, Ui.Style(12.5f, Ui.Ink, false, TextAnchor.MiddleCenter, false));
            }
        }

        static Sample At(List<Sample> s, float t)
        {
            int lo = 0, hi = s.Count - 1;
            while (lo < hi)
            {
                int mid = (lo + hi) / 2;
                if (s[mid].t < t) lo = mid + 1; else hi = mid;
            }
            return s[lo];
        }

        class ChartCache
        {
            public Texture2D tex;
            public Color32[] px;
            public int key;
        }

        readonly Dictionary<string, ChartCache> chartCache = new Dictionary<string, ChartCache>();

        // Serileri dokuya çizer: her piksel sütununda değer aradeğerlenir, sütunlar arası dikey parça 2 piksel kalın,
        // uçları kenar yumuşatmalı. Sabit veride doku yeniden üretilmez.
        Texture2D ChartTexture(string id, int pw, int ph, int version, ChartDef def, float tMax,
                               List<Sample> a, Color ca, List<Sample> b, Color cb)
        {
            if (!chartCache.TryGetValue(id, out var c)) chartCache[id] = c = new ChartCache();
            int key = ((version * 397) ^ (pw * 7 + ph)) * 31 + Mathf.RoundToInt(tMax);
            if (c.tex != null && c.tex.width == pw && c.tex.height == ph && c.key == key) return c.tex;
            if (c.tex == null || c.tex.width != pw || c.tex.height != ph)
            {
                if (c.tex != null) Destroy(c.tex);
                c.tex = new Texture2D(pw, ph, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear };
                c.px = new Color32[pw * ph];
            }
            else Array.Clear(c.px, 0, c.px.Length);
            c.key = key;
            if (b != null) PlotSeries(c.px, pw, ph, b, cb, def, tMax);
            PlotSeries(c.px, pw, ph, a, ca, def, tMax);
            c.tex.SetPixels32(c.px);
            c.tex.Apply(false);
            return c.tex;
        }

        static void PlotSeries(Color32[] px, int pw, int ph, List<Sample> s, Color col, ChartDef def, float tMax)
        {
            if (s == null || s.Count < 2) return;
            float tEnd = Last(s).t;
            int xEnd = Mathf.Min(pw - 1, Mathf.FloorToInt(tEnd / tMax * (pw - 1)));
            float prev = float.NaN;
            int k = 0;
            float Y(float v) => Mathf.Clamp(v / def.yMax, 0f, 1f) * (ph - 3) + 1.5f;   // doku: alt satır 0
            for (int x = 0; x <= xEnd; x++)
            {
                float t = x / (float)(pw - 1) * tMax;
                while (k + 1 < s.Count && s[k + 1].t < t) k++;
                float v;
                if (k + 1 < s.Count)
                {
                    var s0 = s[k];
                    var s1 = s[k + 1];
                    float f = s1.t > s0.t ? Mathf.Clamp01((t - s0.t) / (s1.t - s0.t)) : 0f;
                    v = Mathf.Lerp(def.val(s0), def.val(s1), f);
                }
                else v = def.val(s[k]);
                float y = Y(v);
                float y0 = float.IsNaN(prev) ? y : prev;
                float lo = Mathf.Min(y0, y) - 1f, hi = Mathf.Max(y0, y) + 1f;     // 2 piksel kalınlık
                int ylo = Mathf.Max(0, Mathf.FloorToInt(lo)), yhi = Mathf.Min(ph - 1, Mathf.CeilToInt(hi));
                for (int yy = ylo; yy <= yhi; yy++)
                {
                    float cover = Mathf.Clamp01(Mathf.Min(yy + 1f, hi) - Mathf.Max(yy, lo));
                    if (cover <= 0f) continue;
                    int i = yy * pw + x;
                    var o = px[i];
                    byte al = (byte)Mathf.Max(o.a, Mathf.RoundToInt(255f * cover));
                    px[i] = new Color32((byte)(col.r * 255f), (byte)(col.g * 255f), (byte)(col.b * 255f), al);
                }
                prev = y;
            }
        }
    }
}
