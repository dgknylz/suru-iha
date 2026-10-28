using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace SuruIHA
{
    // "Uçuş raporu" sekmesi: son biten uçuşta sürünün ve her İHA'nın ne yaptığı. Solda harita: arazi gölgelemesi,
    // karıştırma ısı haritası, İHA izleri (her parça İHA'nın o anki durum renginde), hedefler, karıştırıcı ve
    // sürünün tahmini. Sağda özet sayılar, İHA tablosu ve öne çıkanlar. Tablodaki bir İHA'nın üstüne gelince ya da
    // tıklayınca izi haritada öne çıkar, yaptığı hedefler işaretlenir.
    public partial class SwarmMenu
    {
        int reportSide;                         // yan yana uçuşta 0: soldaki, 1: sağdaki sürü
        int reportSel = -1, reportHover = -1;   // tıklanan ve üstüne gelinen İHA
        int seenReport = -1;
        string reportTitle;
        bool reportCompare;
        Texture2D mapBase, mapTracks;
        Color32[] trackPx;
        int mapBaseKey = int.MinValue, mapTrackKey = int.MinValue;
        Vector2 mapMin;                         // haritanın sol alt köşesi (x doğu, y kuzey, m)
        float mapSize;                          // haritanın kenarı (m)
        List<string> highlights;
        int highlightsKey = int.MinValue;
        const int MapBaseRes = 384, MapTrackRes = 768;

        // Yeni rapor gelince o uçuşun senaryo adı saklanır (sekmenin başlığı)
        void NoteReport()
        {
            var v = SwarmVisualizer.Main;
            if (v == null || v.ReportVersion == seenReport) return;
            seenReport = v.ReportVersion;
            reportTitle = RunTitle;
            reportCompare = runCompare;
            reportSel = reportHover = -1;
            if (!reportCompare) reportSide = 0;
        }

        SwarmVisualizer ReportSource()
        {
            var b = SwarmCompare.Instance != null ? SwarmCompare.Instance.B : null;
            if (reportSide == 1 && reportCompare && b != null && b.Report != null) return b;
            return SwarmVisualizer.Main;
        }

        // İz durumları (suru/world.py _status): renkler simülasyondaki İHA ışıklarıyla aynı
        const string StatusOrder = "njgsrpyaf";

        static Color StatusCol(char c) => c switch
        {
            'j' => DroneView.ColJammed, 'g' => DroneView.ColNoGps, 's' => DroneView.ColSearch, 'r' => DroneView.ColRelay,
            'a' => DroneView.ColSpoof, 'p' => DroneView.ColGpsSpoofed, 'y' => DroneView.ColSpoofSeen,
            'f' => new Color(0.45f, 0.45f, 0.45f), _ => DroneView.ColNormal,
        };

        // spoofing: senaryoda GPS aldatıcı var mı (yoksa "GPS'e güvenmiyor" durumu bir yanlış alarmdır)
        static string StatusText(char c, bool spoofing) => c switch
        {
            'j' => "karıştırılıyor", 'g' => "GPS yok", 's' => "spiral arama", 'r' => "röle", 'a' => "saldırgan",
            'p' => "GPS'i aldatılıyor", 'y' => spoofing ? "aldatmayı fark etti" : "GPS'e güvenmiyor", 'f' => "arızalı", _ => "normal",
        };

        static bool Spoofing(SwarmFrame f) => f.spoofers != null && f.spoofers.Length > 0;

        static string Km(float m) => (m / 1000f).ToString("0.0").Replace('.', ',');

        // ------------------------------------------------------------------ sekme
        void DrawRaporTab()
        {
            var v = ReportSource();
            var rep = v != null ? v.Report : null;
            var f = v != null ? v.ReportFrame : null;
            if (rep == null || f == null || f.m == null)
            {
                DrawReportEmpty();
                return;
            }
            float W = Ui.W, H = Ui.H, x0 = 60f, top = BarH + 24f;

            Ui.Chip(x0, top, "UÇUŞ RAPORU", Ui.Accent, 11.5f);
            Ui.Label(Ui.R(x0, top + 26, 1000, 36), reportTitle ?? "Canlı simülasyon", 28, Ui.Ink, true);
            int pi = Array.IndexOf(SwarmScenarios.Planners, f.planner);
            string sub = $"{SwarmScenarios.StrategyTitle(f.strategy)} · {(pi >= 0 ? SwarmScenarios.PlannerTitles[pi] : f.planner)} · " +
                         $"harita #{f.ctl?.seed} · uçuş {rep.t:0} s";
            var now = v.Frame;
            if (now != null && now != f && now.ctl != null && now.ctl.finished != 1) sub += " · şu an yeni bir uçuş sürüyor";
            Ui.Label(Ui.R(x0, top + 64, 1200, 22), sub, 15, Ui.Ink3);

            var b = SwarmCompare.Instance != null ? SwarmCompare.Instance.B : null;
            if (reportCompare && b != null)
            {
                const float bw = 270f;
                float bx = W - 60f - 2 * bw - 8f;
                string left = "Soldaki: " + SwarmScenarios.StrategyTitle(SwarmVisualizer.Main.ReportFrame?.strategy ?? "");
                if (Ui.Button(Ui.R(bx, top + 24, bw, 44), left, Ui.Kind.Normal, reportSide == 0, 15)) SetSide(0);
                if (Ui.Button(Ui.R(bx + bw + 8, top + 24, bw, 44), "Sağdaki: EH dirençli", Ui.Kind.Normal, reportSide == 1, 15,
                              b.Report != null)) SetSide(1);
            }

            float my = top + 104f;
            float M = Mathf.Clamp(H - my - 96f, 360f, 660f);
            BuildMap(v, rep, f);
            int active = reportHover >= 0 ? reportHover : reportSel;
            BuildTracks(rep, active);
            var mr = Ui.R(x0, my, M, M);
            GUI.DrawTexture(mr, mapBase);
            GUI.DrawTexture(mr, mapTracks);
            DrawMapMarks(mr, M, rep, f, active);
            Ui.Outline(mr, Ui.Line, 1f);
            DrawMapLegend(x0, my + M + 12f, M, rep, f, v.ReportField != null);

            float rx = x0 + M + 36f, rw = W - rx - 60f;
            DrawReportStats(rx, my, rw, rep, f);
            float ty = my + 112f;
            float th = DrawDroneTable(rx, ty, rw, rep, Spoofing(f));
            float hy = ty + th + 14f, hw = rw * 0.56f;
            DrawHighlights(rx, hy, hw, H - 24f - hy, rep, f, v);
            DrawReportCharts(rx + hw + 14f, hy, rw - hw - 14f, H - 24f - hy, v);
        }

        void SetSide(int s)
        {
            reportSide = s;
            reportSel = reportHover = -1;
        }

        void DrawReportEmpty()
        {
            float W = Ui.W, H = Ui.H, w = 780f, h = 320f;
            float x = (W - w) / 2f, y = BarH + (H - BarH - h) / 2f;
            Ui.Panel(Ui.R(x, y, w, h), 18, 0.95f);
            Ui.Chip(x + 30, y + 28, "UÇUŞ RAPORU", Ui.Accent, 11.5f);
            bool live = SimRunning;
            Ui.Label(Ui.R(x + 30, y + 58, w - 60, 36), live ? "Uçuş sürüyor" : "Henüz biten bir uçuş yok", 27, Ui.Ink, true);
            const string text = "Sürü inince burada uçuşun raporu çıkar: ısı haritası üstünde her İHA'nın izi (o anki durum " +
                                "renginde), hangi İHA'nın hangi hedefi yaptığı, kimin GPS'ini kaybettiği, kimin röle olduğu ve " +
                                "uçuşun öne çıkanları.";
            float th = Ui.TextHeight(text, 16.5f, w - 60);
            Ui.Label(Ui.R(x + 30, y + 104, w - 60, th), text, 16.5f, Ui.Ink2);
            if (Ui.Button(Ui.R(x + 30, y + h - 86, 320, 58), live ? "Simülasyona dön" : "Simülasyonu başlat", Ui.Kind.Primary,
                          size: 18, icon: true, enabled: live || launcher.CanLaunch))
            {
                if (live) Current = Page.Sim;
                else QuickStart();
            }
        }

        // ------------------------------------------------------------------ özet ve tablo
        void DrawReportStats(float x, float y, float w, FlightReport rep, SwarmFrame f)
        {
            float sw = (w - 4 * 12f) / 5f;
            bool all = f.m.done == f.m.total;
            Ui.Stat(Ui.R(x, y, sw, 96), $"%{100f * f.m.done / Mathf.Max(1, f.m.total):0}", $"tamamlanan hedef ({f.m.done}/{f.m.total})",
                    all ? Ui.Good : Ui.Warn, 28);
            Ui.Stat(Ui.R(x + (sw + 12), y, sw, 96), $"{f.m.score * 100f:0}", "görev puanı (100 üzerinden)", Ui.Accent, 28);
            Ui.Stat(Ui.R(x + 2 * (sw + 12), y, sw, 96), $"{rep.mission:0} s", all ? "son hedefin yapıldığı an" : "görevin bittiği an",
                    Ui.Ink, 28);
            Ui.Stat(Ui.R(x + 3 * (sw + 12), y, sw, 96), $"{Km(rep.drones.Sum(d => d.dist))} km", "sürünün toplam uçtuğu yol", Ui.Ink, 28);
            Ui.Stat(Ui.R(x + 4 * (sw + 12), y, sw, 96), $"{f.m.falseDone}", "yanlış \"bitti\"", f.m.falseDone == 0 ? Ui.Good : Ui.Bad, 28);
        }

        static readonly string[] TableHeads = { "İHA", "Hedef", "Yol", "GPS'siz", "Karıştırmada", "Ne yaptı?" };
        static readonly float[] TableCols = { 0f, 118f, 196f, 290f, 390f, 520f };

        float DrawDroneTable(float x, float y, float w, FlightReport rep, bool spoofing)
        {
            const float rowH = 38f;
            for (int c = 0; c < TableHeads.Length; c++)
                Ui.Label(Ui.R(x + 14 + TableCols[c], y, 220, 20), Ui.Upper(TableHeads[c]), 11.5f, Ui.Ink3, true);
            float ry = y + 26f;
            int hover = -1;
            for (int i = 0; i < rep.drones.Length; i++)
            {
                var d = rep.drones[i];
                var r = Ui.R(x, ry, w, rowH - 4);
                bool hov = r.Contains(Event.current.mousePosition), sel = reportSel == i;
                if (hov) hover = i;
                Ui.Fill(r, sel ? new Color(0.33f, 0.78f, 1f, 0.16f) : hov ? new Color(1f, 1f, 1f, 0.08f)
                         : new Color(1f, 1f, 1f, i % 2 == 0 ? 0.035f : 0f), 8);
                if (sel) Ui.Outline(r, Ui.Accent, 1.5f, 8);
                float cy = ry + (rowH - 4) / 2f;
                Ui.Dot(new Vector2((x + 22) * Ui.S, cy * Ui.S), 5f, DroneColor(d));
                var mid = TextAnchor.MiddleLeft;
                Ui.Label(Ui.R(x + 36, ry, 90, rowH - 4), $"İHA-{d.id + 1}", 15, Ui.Ink, true, mid);
                Ui.Label(Ui.R(x + 14 + TableCols[1], ry, 70, rowH - 4), d.liar == 1 ? "—" : d.done.ToString(), 15, Ui.Ink, d.done > 0, mid);
                Ui.Label(Ui.R(x + 14 + TableCols[2], ry, 90, rowH - 4), Km(d.dist) + " km", 15, Ui.Ink2, false, mid);
                Ui.Label(Ui.R(x + 14 + TableCols[3], ry, 90, rowH - 4), d.nogps > 0.5f ? $"{d.nogps:0} s" : "—", 15,
                         d.nogps > 0.5f ? DroneView.ColNoGps : Ui.Ink3, false, mid);
                Ui.Label(Ui.R(x + 14 + TableCols[4], ry, 120, rowH - 4), d.jam > 0.5f ? $"{d.jam:0} s" : "—", 15,
                         d.jam > 0.5f ? DroneView.ColJammed : Ui.Ink3, false, mid);
                float ww = w - TableCols[5] - 28f;
                Ui.Label(Ui.R(x + 14 + TableCols[5], ry, ww, rowH - 4), Fit(DroneSummary(d, spoofing), 14f, ww), 14f, Ui.Ink2, false, mid);
                if (Ui.Click(r)) reportSel = sel ? -1 : i;
                ry += rowH;
            }
            if (Event.current.type == EventType.Repaint) reportHover = hover;
            Ui.Label(Ui.R(x + 14, ry + 2, w, 18), "Bir İHA'nın üstüne gel ya da tıkla: izi ve yaptığı hedefler haritada öne çıkar.", 12.5f, Ui.Ink3);
            return ry + 24f - y;
        }

        static Color DroneColor(DroneReport d) =>
            d.liar == 1 ? DroneView.ColSpoof : d.fail >= 0f ? new Color(0.45f, 0.45f, 0.45f)
            : d.nogps > 0.5f ? DroneView.ColNoGps : d.jam > 0.5f ? DroneView.ColJammed : DroneView.ColNormal;

        static string DroneSummary(DroneReport d, bool spoofing)
        {
            var parts = new List<string>();
            if (d.liar == 1) parts.Add("saldırgan İHA: sahte teklif ve sahte \"bitti\" yaydı");
            if (d.fail >= 0f) parts.Add($"{d.fail:0}. saniyede arızalandı, hedefleri diğerlerine geçti");
            if (d.wrong > 0) parts.Add($"{d.wrong} yanlış \"bitti\"");
            if (d.search > 0) parts.Add($"{d.search} kez hedefi göremeyip spiral aradı");
            if (d.recover > 0) parts.Add($"{d.recover} kez GPS'i geri almaya gitti");
            if (d.relay > 0.5f) parts.Add($"{d.relay:0} s röle oldu");
            if (d.seen == 1) parts.Add(spoofing ? "GPS aldatmasını fark etti" : "GPS'inden şüphelenip bir süre güvenmedi (yanlış alarm)");
            else if (d.spoofed > 0.5f) parts.Add($"GPS'i {d.spoofed:0} s aldatıldı, fark etmedi");
            if (parts.Count == 0)
                parts.Add(d.nogps > 0.5f ? "GPS'siz kaldı, konumunu tahminle bulup görevini sürdürdü"
                          : d.jam > 0.5f ? "karıştırmaya rağmen sorunsuz uçtu" : "sorunsuz uçtu");
            return string.Join(" · ", parts);
        }

        // Sığmayan yazı "…" ile kısaltılır
        static string Fit(string s, float size, float w)
        {
            if (Ui.TextWidth(s, size) <= w) return s;
            int n = s.Length;
            while (n > 4 && Ui.TextWidth(s.Substring(0, n) + "…", size) > w) n -= 2;
            return s.Substring(0, n).TrimEnd(' ', '·') + "…";
        }

        void DrawHighlights(float x, float y, float w, float h, FlightReport rep, SwarmFrame f, SwarmVisualizer v)
        {
            if (h < 80f) return;
            int key = v.GetInstanceID() * 31 + v.ReportVersion;
            if (highlights == null || key != highlightsKey)
            {
                highlights = Highlights(rep, f);
                highlightsKey = key;
            }
            Ui.Fill(Ui.R(x, y, w, h), new Color(1f, 1f, 1f, 0.04f), 14);
            Ui.Label(Ui.R(x + 20, y + 14, w - 40, 20), "ÖNE ÇIKANLAR", 11.5f, Ui.Accent, true);
            float ly = y + 42f;
            foreach (var line in highlights)
            {
                float lh = Ui.TextHeight(line, 14.5f, w - 64f);
                if (ly + lh > y + h - 10f) break;
                Ui.Dot(new Vector2((x + 26) * Ui.S, (ly + 11) * Ui.S), 3f, Ui.Accent);
                Ui.Label(Ui.R(x + 40, ly, w - 64, lh), line, 14.5f, Ui.Ink);
                ly += lh + 6f;
            }
        }

        static List<string> Highlights(FlightReport rep, SwarmFrame f)
        {
            var L = new List<string>();
            var D = rep.drones;
            int done = f.m.done, total = f.m.total;
            L.Add(done == total ? $"Sürü {total} hedefin hepsini {rep.mission:0}. saniyede tamamladı (görev puanı {f.m.score * 100f:0})."
                                : $"Sürü {total} hedefin {done} tanesini yaptı, {total - done} hedef yapılamadı (görev puanı {f.m.score * 100f:0}).");
            var honest = D.Where(d => d.liar == 0).ToArray();
            if (honest.Length > 0)
            {
                int most = honest.Max(d => d.done);
                var top = honest.Where(d => d.done == most).Select(d => $"İHA-{d.id + 1}").ToArray();
                L.Add(top.Length == 1 ? $"En çok hedefi {top[0]} yaptı ({most} hedef)."
                                      : $"En çok hedefi {string.Join(", ", top)} yaptı (her biri {most} hedef).");
            }
            var far = D.OrderByDescending(d => d.dist).First();
            L.Add($"İHA'lar toplam {Km(D.Sum(d => d.dist))} km uçtu; en uzun yolu İHA-{far.id + 1} katetti ({Km(far.dist)} km).");
            foreach (var d in D.Where(d => d.fail >= 0f))
                L.Add($"İHA-{d.id + 1} {d.fail:0}. saniyede arızalandı; hedefleri sürüdeki diğer İHA'lara geçti.");
            bool jammed = f.jammers != null && f.jammers.Length > 0;
            var jm = D.Where(d => d.jam > 0.5f).ToArray();
            if (jammed && jm.Length > 0)
            {
                var m = jm.OrderByDescending(d => d.jam).First();
                L.Add($"{jm.Length} İHA karıştırma alanına girdi; en uzun karıştırılan İHA-{m.id + 1} ({m.jam:0} s).");
            }
            var ng = D.Where(d => d.nogps > 0.5f).ToArray();
            if (ng.Length > 0)
            {
                var m = ng.OrderByDescending(d => d.nogps).First();
                L.Add($"{ng.Length} İHA GPS'ini kaybedip konumunu tahminle buldu; en uzun GPS'siz kalan İHA-{m.id + 1} ({m.nogps:0} s).");
            }
            if (jammed)
                L.Add(f.m.jamErr >= 0f ? $"Sürü, İHA'ların ölçümlerinden karıştırıcının yerini {f.m.jamErr:0} m hatayla buldu."
                                       : "Sürü karıştırıcının yerini bulamadı.");
            int searches = D.Sum(d => d.search);
            if (searches > 0) L.Add($"İHA'lar {searches} kez hedefi kamerada göremeyince \"bitti\" demek yerine spiral arama yaptı.");
            int wrong = D.Sum(d => d.wrong);
            if (wrong > 0) L.Add($"{wrong} kez yanlış \"bitti\": İHA hedefe vardığını sandı ama konumu yanlıştı, hedef orada değildi.");
            int rec = D.Sum(d => d.recover);
            if (rec > 0) L.Add($"Konum belirsizliği büyüyen İHA'lar {rec} kez görevi bırakıp GPS'i geri almaya gitti.");
            var rl = D.Where(d => d.relay > 0.5f).Select(d => $"İHA-{d.id + 1}").ToArray();
            if (rl.Length > 0) L.Add($"{string.Join(", ", rl)} röle olup kopan arkadaşlarıyla bağlantıyı korudu.");
            int seen = D.Count(d => d.seen == 1), fooled = D.Count(d => d.spoofed > 0.5f && d.seen == 0 && d.liar == 0);
            if (seen > 0)
                L.Add(Spoofing(f) ? $"{seen} İHA GPS aldatmasını fark edip GPS'ine güvenmeyi bıraktı."
                                  : $"{seen} İHA GPS'inden şüphelenip bir süre ona güvenmedi (aldatıcı yoktu: yanlış alarm, görev etkilenmedi).");
            if (fooled > 0) L.Add($"{fooled} İHA GPS'inin aldatıldığını fark etmedi.");
            int liars = D.Count(d => d.liar == 1);
            if (liars > 0)
                L.Add(f.m.liars >= 0f ? $"Sürüde {liars} saldırgan İHA vardı; dürüst İHA'lar onları %{f.m.liars * 100f:0} oranında dışladı."
                                      : $"Sürüde {liars} saldırgan İHA vardı.");
            return L;
        }

        // ------------------------------------------------------------------ harita
        // Arazi gölgelemesi + ısı haritası (rapor başına bir kez)
        void BuildMap(SwarmVisualizer v, FlightReport rep, SwarmFrame f)
        {
            int key = v.GetInstanceID() * 31 + v.ReportVersion;
            if (mapBase != null && key == mapBaseKey) return;
            mapBaseKey = key;
            mapTrackKey = int.MinValue;

            float minX = float.MaxValue, minY = float.MaxValue, maxX = float.MinValue, maxY = float.MinValue;
            void Add(float x, float y)
            {
                minX = Mathf.Min(minX, x); maxX = Mathf.Max(maxX, x);
                minY = Mathf.Min(minY, y); maxY = Mathf.Max(maxY, y);
            }
            foreach (var d in rep.drones)
                if (d.xy != null)
                    for (int k = 0; k + 1 < d.xy.Length; k += 2) Add(d.xy[k], d.xy[k + 1]);
            if (f.tasks != null) foreach (var t in f.tasks) if (t.s >= 0 && t.p != null && t.p.Length >= 2) Add(t.p[0], t.p[1]);
            if (f.jammers != null) foreach (var j in f.jammers) if (j.p != null && j.p.Length >= 2) Add(j.p[0], j.p[1]);
            if (f.gcs?.p != null && f.gcs.p.Length >= 2) Add(f.gcs.p[0], f.gcs.p[1]);
            if (minX > maxX) { minX = -300f; maxX = 300f; minY = -100f; maxY = 700f; }
            mapSize = Mathf.Max(Mathf.Max(maxX - minX, maxY - minY) + 160f, 500f);
            mapMin = new Vector2((minX + maxX - mapSize) / 2f, (minY + maxY - mapSize) / 2f);

            const int N = MapBaseRes;
            float cell = mapSize / N;
            var h = new float[N * N];
            for (int j = 0, k = 0; j < N; j++)
            for (int i = 0; i < N; i++, k++)
                h[k] = v.GroundHeight(mapMin.x + (i + 0.5f) * cell, mapMin.y + (j + 0.5f) * cell);

            var F = v.ReportField;
            byte[] q = null;
            if (F != null && !string.IsNullOrEmpty(F.q) && F.nx > 1 && F.ny > 1)
            {
                try { q = Convert.FromBase64String(F.q); }
                catch (FormatException) { }
                if (q != null && q.Length != F.nx * F.ny) q = null;
            }
            float[] J = null;
            if (q != null)
            {
                J = new float[N * N];
                for (int j = 0, k = 0; j < N; j++)
                for (int i = 0; i < N; i++, k++)
                    J[k] = FieldAt(F, q, mapMin.x + (i + 0.5f) * cell, mapMin.y + (j + 0.5f) * cell);
            }

            var px = new Color32[N * N];
            var light = new Vector3(-0.6f, 1.1f, 0.6f).normalized;     // kuzeybatıdan ışık
            var low = new Color(0.13f, 0.13f, 0.12f);
            var high = new Color(0.56f, 0.51f, 0.42f);
            for (int j = 0, k = 0; j < N; j++)
            for (int i = 0; i < N; i++, k++)
            {
                float dx = (h[j * N + Mathf.Min(i + 1, N - 1)] - h[j * N + Mathf.Max(i - 1, 0)]) / (2f * cell);
                float dz = (h[Mathf.Min(j + 1, N - 1) * N + i] - h[Mathf.Max(j - 1, 0) * N + i]) / (2f * cell);
                float shade = Mathf.Clamp01(Vector3.Dot(new Vector3(-dx, 1f, -dz).normalized, light));
                Color c = Color.Lerp(low, high, shade);
                if (J != null)
                {
                    Color hc = SwarmVisualizer.HeatColor(J[k], F.detect, F.cut);
                    float a = Mathf.Clamp01(hc.a * 1.3f);
                    c = Color.Lerp(c, new Color(hc.r, hc.g, hc.b), a);
                    // Bağlantının koptuğu eş güç çizgisi
                    bool s = J[k] >= F.cut;
                    if ((i + 1 < N && (J[k + 1] >= F.cut) != s) || (j + 1 < N && (J[k + N] >= F.cut) != s))
                        c = Color.Lerp(c, new Color(1f, 0.92f, 0.88f), 0.85f);
                }
                c.a = 1f;
                px[k] = c;
            }
            if (mapBase == null)
                mapBase = new Texture2D(N, N, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear };
            mapBase.SetPixels32(px);
            mapBase.Apply(false);
        }

        static float FieldAt(JamFieldState F, byte[] q, float x, float y)
        {
            float gx = (x - F.x0) / F.step, gy = (y - F.y0) / F.step;
            if (gx < 0f || gy < 0f || gx > F.nx - 1 || gy > F.ny - 1) return -999f;
            int i0 = Mathf.Min((int)gx, F.nx - 2), j0 = Mathf.Min((int)gy, F.ny - 2);
            float fx = gx - i0, fy = gy - j0;
            int r0 = j0 * F.nx + i0, r1 = r0 + F.nx;
            float v = (q[r0] * (1 - fx) + q[r0 + 1] * fx) * (1 - fy) + (q[r1] * (1 - fx) + q[r1 + 1] * fx) * fy;
            return F.db0 + v * F.dbStep;
        }

        // İzler (seçim değişince yeniden): her parça İHA'nın o anki durum renginde, koyu kenarlıklı
        void BuildTracks(FlightReport rep, int active)
        {
            int key = mapBaseKey * 64 + active + 1;
            if (mapTracks != null && key == mapTrackKey) return;
            mapTrackKey = key;
            const int N = MapTrackRes;
            if (trackPx == null) trackPx = new Color32[N * N];
            else Array.Clear(trackPx, 0, trackPx.Length);
            for (int pass = 0; pass < 2; pass++)
            for (int i = 0; i < rep.drones.Length; i++)
            {
                bool isActive = i == active;
                if ((pass == 1) != isActive) continue;           // seçili İHA en üstte çizilir
                var d = rep.drones[i];
                if (d.xy == null || d.st == null) continue;
                int n = Mathf.Min(d.st.Length, d.xy.Length / 2);
                float alpha = active < 0 || isActive ? 1f : 0.2f;
                int r = isActive ? 2 : 1;
                for (int layer = 0; layer < 2; layer++)
                for (int k = 0; k + 1 < n; k++)
                {
                    Vector2 a = MapTex(d.xy[2 * k], d.xy[2 * k + 1]), b = MapTex(d.xy[2 * k + 2], d.xy[2 * k + 3]);
                    Color c = layer == 0 ? new Color(0f, 0f, 0f, 0.6f * alpha) : StatusCol(d.st[k]);
                    if (layer == 1) c.a = alpha;
                    Segment(a, b, layer == 0 ? r + 1 : r, c);
                }
            }
            if (mapTracks == null)
                mapTracks = new Texture2D(N, N, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear };
            mapTracks.SetPixels32(trackPx);
            mapTracks.Apply(false);
        }

        Vector2 MapTex(float x, float y) => new Vector2((x - mapMin.x) / mapSize * MapTrackRes, (y - mapMin.y) / mapSize * MapTrackRes);

        void Segment(Vector2 a, Vector2 b, int r, Color c)
        {
            Color32 c32 = c;
            int steps = Mathf.Max(1, Mathf.CeilToInt(Mathf.Max(Mathf.Abs(b.x - a.x), Mathf.Abs(b.y - a.y))));
            for (int s = 0; s <= steps; s++)
            {
                var p = Vector2.Lerp(a, b, (float)s / steps);
                int cx = Mathf.RoundToInt(p.x), cy = Mathf.RoundToInt(p.y);
                for (int y = cy - r; y <= cy + r; y++)
                for (int x = cx - r; x <= cx + r; x++)
                    if (x >= 0 && y >= 0 && x < MapTrackRes && y < MapTrackRes) trackPx[y * MapTrackRes + x] = c32;
            }
        }

        // Hedefler, karıştırıcı, sürünün tahmini, üs, seçili İHA, ölçek ve kuzey
        void DrawMapMarks(Rect mr, float M, FlightReport rep, SwarmFrame f, int active)
        {
            Vector2 P(float x, float y) => new Vector2(mr.x + (x - mapMin.x) / mapSize * mr.width,
                                                       mr.y + (1f - (y - mapMin.y) / mapSize) * mr.height);
            if (f.gcs?.p != null && f.gcs.p.Length >= 2)
            {
                var g = P(f.gcs.p[0], f.gcs.p[1]);
                Ui.Fill(new Rect(g.x - 6 * Ui.S, g.y - 6 * Ui.S, 12 * Ui.S, 12 * Ui.S), Ui.Accent, 2);
                GUI.Label(new Rect(g.x + 9 * Ui.S, g.y - 10 * Ui.S, 60 * Ui.S, 20 * Ui.S), "Üs", Ui.Style(13, Ui.Accent, true));
            }
            if (f.tasks != null)
                for (int t = 0; t < f.tasks.Length; t++)
                {
                    var tk = f.tasks[t];
                    if (tk.s < 0 || tk.p == null || tk.p.Length < 2) continue;
                    var p = P(tk.p[0], tk.p[1]);
                    if (active >= 0 && rep.taskBy != null && t < rep.taskBy.Length && rep.taskBy[t] == active)
                        Ui.Ring(p, 11f, Ui.Accent, 2.5f);
                    if (tk.s == 2) Ui.Dot(p, 4.5f, Ui.Good);
                    else Ui.Ring(p, 5f, tk.s == 3 ? Ui.Bad : Ui.Ink2, 2f);
                }
            if (f.jammers != null)
                foreach (var j in f.jammers)
                {
                    if (j.p == null || j.p.Length < 2) continue;
                    var p = P(j.p[0], j.p[1]);
                    Ui.Ring(p, 8f, Ui.Bad, 3f);
                    Ui.Dot(p, 3.5f, Ui.Bad);
                }
            if (f.jamEst != null)
                foreach (var e in f.jamEst)
                {
                    if (e.p == null || e.p.Length < 2) continue;
                    var p = P(e.p[0], e.p[1]);
                    var o = new Color(1f, 0.6f, 0.15f);
                    Ui.Fill(new Rect(p.x - 10 * Ui.S, p.y - 1.5f * Ui.S, 20 * Ui.S, 3 * Ui.S), o);
                    Ui.Fill(new Rect(p.x - 1.5f * Ui.S, p.y - 10 * Ui.S, 3 * Ui.S, 20 * Ui.S), o);
                }
            if (active >= 0 && active < rep.drones.Length)
            {
                var d = rep.drones[active];
                int n = d.xy != null ? d.xy.Length / 2 : 0;
                if (n > 0)
                {
                    var p = P(d.xy[2 * n - 2], d.xy[2 * n - 1]);
                    string text = $"İHA-{d.id + 1}" + (d.fail >= 0f ? " · arıza" : "");
                    float w = (Ui.TextWidth(text, 13.5f, true) + 22f) * Ui.S, hh = 26f * Ui.S;
                    var r = new Rect(p.x - w / 2f, p.y - hh - 10f * Ui.S, w, hh);
                    Ui.Fill(r, new Color(0.03f, 0.05f, 0.07f, 0.92f), 13f);
                    Ui.Outline(r, Ui.Accent, 2f, 13f);
                    GUI.Label(r, text, Ui.Style(13.5f, Ui.Ink, true, TextAnchor.MiddleCenter, false));
                }
            }

            // Ölçek çubuğu ve kuzey
            float target = mapSize * 170f / M;      // ~170 birimlik çubuğa en yakın yuvarlak uzunluk
            float len = target >= 1000f ? 1000f : target >= 500f ? 500f : target >= 250f ? 250f : target >= 200f ? 200f : 100f;
            float bw = len / mapSize * mr.width;
            var sb = new Rect(mr.x + 16 * Ui.S, mr.yMax - 22 * Ui.S, bw, 3 * Ui.S);
            Ui.Fill(new Rect(sb.x - 6 * Ui.S, sb.y - 22 * Ui.S, bw + 12 * Ui.S, 34 * Ui.S), new Color(0.02f, 0.03f, 0.04f, 0.6f), 6);
            Ui.Fill(sb, Ui.Ink);
            GUI.Label(new Rect(sb.x, sb.y - 21 * Ui.S, bw, 18 * Ui.S), $"{len:0} m", Ui.Style(12.5f, Ui.Ink, true));
            var nr = new Rect(mr.xMax - 46 * Ui.S, mr.y + 10 * Ui.S, 36 * Ui.S, 36 * Ui.S);
            Ui.Fill(nr, new Color(0.02f, 0.03f, 0.04f, 0.6f), 18);
            GUI.Label(nr, "K\n↑", Ui.Style(12f, Ui.Ink, true, TextAnchor.MiddleCenter));
        }

        void DrawMapLegend(float x, float y, float w, FlightReport rep, SwarmFrame f, bool heat)
        {
            var seen = new HashSet<char>();
            foreach (var d in rep.drones) if (d.st != null) foreach (char c in d.st) seen.Add(c);
            float cx = x, cy = y;
            void Item(Action<float, float> icon, string text)
            {
                float iw = 26f + Ui.TextWidth(text, 13f) + 18f;
                if (cx + iw > x + w) { cx = x; cy += 24f; }
                icon(cx, cy + 10f);
                Ui.Label(Ui.R(cx + 26f, cy, iw, 20), text, 13f, Ui.Ink2);
                cx += iw;
            }
            Ui.Label(Ui.R(x, cy, 80, 20), "İz rengi:", 13f, Ui.Ink3, true);
            cx += 70f;
            foreach (char c in StatusOrder)
                if (seen.Contains(c))
                {
                    var col = StatusCol(c);
                    Item((ix, iy) => Ui.Fill(Ui.R(ix, iy - 2f, 20f, 4f), col, 2f), StatusText(c, Spoofing(f)));
                }
            cx = x;
            cy += 26f;
            Item((ix, iy) => Ui.Dot(new Vector2((ix + 10f) * Ui.S, iy * Ui.S), 4.5f, Ui.Good), "yapılan hedef");
            Item((ix, iy) => Ui.Ring(new Vector2((ix + 10f) * Ui.S, iy * Ui.S), 5f, Ui.Ink2, 2f), "yapılamayan");
            if (f.tasks != null && f.tasks.Any(t => t.s == 3))
                Item((ix, iy) => Ui.Ring(new Vector2((ix + 10f) * Ui.S, iy * Ui.S), 5f, Ui.Bad, 2f), "yanlış \"bitti\"");
            if (f.jammers != null && f.jammers.Length > 0)
            {
                Item((ix, iy) => Ui.Ring(new Vector2((ix + 10f) * Ui.S, iy * Ui.S), 7f, Ui.Bad, 3f), "karıştırıcı");
                if (f.jamEst != null && f.jamEst.Length > 0)
                    Item((ix, iy) =>
                    {
                        var o = new Color(1f, 0.6f, 0.15f);
                        Ui.Fill(Ui.R(ix + 2f, iy - 1.5f, 16f, 3f), o);
                        Ui.Fill(Ui.R(ix + 8.5f, iy - 8f, 3f, 16f), o);
                    }, "sürünün tahmini");
            }
            if (heat) Item((ix, iy) => Ui.Fill(Ui.R(ix, iy - 7f, 20f, 14f), new Color(0.85f, 0.3f, 0.25f), 3f), "karıştırma gücü");
        }
    }
}
