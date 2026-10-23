using System;
using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;

namespace SuruIHA
{
    // Simülasyon sırasındaki arayüz: senaryo kutusu, olay akışı, araç çubuğu, renk açıklamaları, görev sonu ekranı.
    // Ayrıca "-suruUiTest <klasör>" ile bütün ekranları gezip görüntü alan otomatik test.
    public partial class SwarmMenu
    {
        SwarmHud hud;

        bool CompareOn
        {
            get
            {
                var c = SwarmCompare.Instance;
                return c != null && c.Active;
            }
        }

        void DrawSim()
        {
            float top = CompareOn ? 128f : 20f;
            DrawBanner(top);
            if (feedOpen) DrawFeed(top, legendOpen ? 4 : 6);
            float tbTop = DrawToolbar();
            if (legendOpen) DrawLegendPanel(tbTop);
            DrawResults();
            if (tip != null) DrawTip(tbTop);
        }

        // ------------------------------------------------------------ senaryo kutusu
        void DrawBanner(float top)
        {
            float w = 860f, x = (Ui.W - w) / 2f;
            var st = launcher != null ? launcher.Status : SimLauncher.State.External;
            if (st == SimLauncher.State.Starting)
            {
                Ui.Panel(Ui.R(x, top, w, 76), 14);
                string dots = new string('.', 1 + (int)(Time.unscaledTime * 2f) % 3);
                Ui.Label(Ui.R(x + 24, top + 12, w - 48, 30), "Simülasyon başlatılıyor" + dots, 21, Ui.Ink, true);
                Ui.Label(Ui.R(x + 24, top + 44, w - 48, 24), "Python simülasyonu açılıyor; sürü birkaç saniye içinde görünecek.", 15, Ui.Ink2);
                return;
            }
            if (st == SimLauncher.State.Crashed || (!SimConnected && st != SimLauncher.State.Running))
            {
                Ui.Panel(Ui.R(x, top, w, 132), 14);
                Ui.Label(Ui.R(x + 24, top + 14, w - 48, 30), "Simülasyon çalışmıyor", 21, Ui.Bad, true);
                string msg = st == SimLauncher.State.Crashed ? launcher.LastError : "Bir senaryo seçip başlat.";
                Ui.Label(Ui.R(x + 24, top + 46, w - 48, 40), msg, 14.5f, Ui.Ink2);
                if (Ui.Button(Ui.R(x + 24, top + 82, 200, 38), "Tekrar dene", size: 15, enabled: launcher != null && launcher.CanLaunch)) Launch();
                if (Ui.Button(Ui.R(x + 234, top + 82, 200, 38), "Senaryo seç", size: 15)) Go(Page.Scenarios);
                if (Ui.Button(Ui.R(x + 444, top + 82, 200, 38), "Ana ekran", Ui.Kind.Ghost, size: 15)) BackToHome();
                return;
            }
            if (running == null) return;
            var f = SwarmVisualizer.Main.Frame;
            if (bannerOpen)
            {
                float tw = w - 48f;
                string watch = "<b>Ne izlemelisin?</b> " + running.Watch;
                float wh = Ui.TextHeight(watch, 16.5f, tw);
                float h = 96f + wh;
                Ui.Panel(Ui.R(x, top, w, h), 14);
                float cx = Ui.Chip(x + 24, top + 18, runCompare ? "YAN YANA" : "SENARYO", Ui.Accent, 11.5f);
                Ui.Label(Ui.R(x + 36 + cx, top + 12, w - 120 - cx, 32), running.Title, 22, Ui.Ink, true);
                if (Ui.Button(Ui.R(x + w - 52, top + 12, 34, 34), "×", Ui.Kind.Ghost, size: 20)) bannerOpen = false;
                string arch = f == null ? "" : runCompare
                    ? $"Solda {SwarmScenarios.StrategyTitle(f.strategy)}, sağda EH dirençli sürü · {SwarmScenarios.PlannerTitle(f.planner, "resilient")}"
                    : $"{SwarmScenarios.StrategyTitle(f.strategy)} · {SwarmScenarios.PlannerTitle(f.planner, f.strategy)}";
                Ui.Label(Ui.R(x + 24, top + 50, tw, 22), arch, 14, Ui.Ink3);
                Ui.Label(Ui.R(x + 24, top + 76, tw, wh + 4), watch, 16.5f, Ui.Ink);
            }
            else
            {
                string s = "Ne izlemeliyim?  ·  " + running.Title;
                float pw = Ui.TextWidth(s, 15, true) + 44f;
                if (Ui.Button(Ui.R((Ui.W - pw) / 2f, top, pw, 38), s, size: 15))
                {
                    bannerOpen = true;
                    bannerUntil = Time.unscaledTime + 20f;
                }
            }
        }

        // ------------------------------------------------------------ olay akışı
        void DrawFeed(float top, int max)
        {
            var ev = SwarmEvents.Instance;
            if (ev == null || !SimConnected) return;
            float w = 430f, x = Ui.W - w - 20f, tw = w - 56f;
            int n = Mathf.Min(max, ev.Items.Count);
            float ph = 46f;
            var hs = new float[n];
            for (int k = 0; k < n; k++)
            {
                hs[k] = Ui.TextHeight(ev.Items[ev.Items.Count - 1 - k].text, 15f, tw);
                ph += hs[k] + 30f;
            }
            if (n == 0) ph += 26f;
            Ui.Panel(Ui.R(x, top, w, ph), 14, 0.86f);
            Ui.Label(Ui.R(x + 18, top + 14, w - 36, 18), CompareOn ? "OLAY AKIŞI · SAĞDAKİ DİRENÇLİ SÜRÜ" : "OLAY AKIŞI", 11.5f, Ui.Ink3, true);
            float y = top + 40f;
            if (n == 0) Ui.Label(Ui.R(x + 18, y, tw, 22), "Olaylar burada anlatılacak…", 15, Ui.Ink3);
            for (int k = 0; k < n; k++)
            {
                var e = ev.Items[ev.Items.Count - 1 - k];
                float age = Time.unscaledTime - e.real;
                float a = Mathf.Clamp01(age / 0.5f) * (age > 60f ? 0.55f : 1f);
                Ui.Dot(new Vector2((x + 22f) * Ui.S, (y + 9f) * Ui.S), 5f, new Color(e.color.r, e.color.g, e.color.b, a));
                Ui.Label(Ui.R(x + 36, y, 200, 18), $"t = {e.sim:0} s", 12.5f, new Color(Ui.Ink2.r, Ui.Ink2.g, Ui.Ink2.b, 0.8f * a));
                Ui.Label(Ui.R(x + 36, y + 17, tw, hs[k] + 4), e.text, 15, new Color(Ui.Ink.r, Ui.Ink.g, Ui.Ink.b, a));
                y += hs[k] + 30f;
            }
        }

        // ------------------------------------------------------------ araç çubuğu
        struct Tool
        {
            public string label, tip;
            public bool sel;
            public Action act;
            public Tool(string label, string tip, bool sel, Action act) { this.label = label; this.tip = tip; this.sel = sel; this.act = act; }
        }

        // Düğme genişliği: kalın yazının genişliği + iki yandaki boşluk (seçilince yazı kalınlaşır, kesilmesin)
        static float ToolW(string label) => Mathf.Max(52f, Ui.TextWidth(label, 15f, true) + 44f);

        float DrawToolbar()
        {
            var vis = SwarmVisualizer.Main;
            if (hud == null && cam != null) hud = cam.GetComponent<SwarmHud>();
            bool cmpOn = CompareOn;
            var groups = new (string name, Tool[] tools)[]
            {
                ("KAMERA", new[]
                {
                    new Tool("Sinematik", "Sinematik kamera [C]: sürünün etrafında yavaşça döner.", cam.mode == SwarmCamera.Mode.Cinematic,
                             () => cam.mode = SwarmCamera.Mode.Cinematic),
                    new Tool("Serbest", "Serbest kamera [O]: sürükleyerek döndür, tekerlekle yakınlaş, WASD ile kaydır.", cam.mode == SwarmCamera.Mode.Orbit,
                             () => cam.mode = SwarmCamera.Mode.Orbit),
                    new Tool("Takip", "Takip kamerası [F]: bir İHA'nın arkasından izle. Tekrar basınca sıradaki İHA'ya geçer.",
                             cam.mode == SwarmCamera.Mode.Follow, () =>
                             {
                                 if (cam.mode == SwarmCamera.Mode.Follow && vis.Drones.Count > 0)
                                     cam.SetFollow((cam.FollowIndex + 1) % vis.Drones.Count);
                                 cam.mode = SwarmCamera.Mode.Follow;
                             }),
                    new Tool("Taktik", "Taktik kuşbakışı [T]: bütün görev alanını yukarıdan gör.", cam.mode == SwarmCamera.Mode.Top,
                             () => cam.mode = SwarmCamera.Mode.Top),
                }),
                ("GÖSTER", cmpOn ? new[]
                {
                    new Tool("Bağlantılar", "Haberleşme bağlantıları [L]: yeşil sağlam, kırmızı karıştırılmış.", vis.showLinks, () => vis.showLinks = !vis.showLinks),
                    new Tool("Planlar", "İHA'ların planları [P]: her İHA'nın sıradaki hedeflerine giden rota.", vis.showPlans, () => vis.showPlans = !vis.showPlans),
                    new Tool("Hayaletler", "İHA'nın sandığı konum [G]: GPS'siz İHA kendini nerede sanıyor (halka).", vis.showEstimates, () => vis.showEstimates = !vis.showEstimates),
                    new Tool("EH haritası", "Sürünün ortak karıştırma haritası [J]: İHA'ların karıştırma ölçtüğü bölgeler.", vis.showJamMap, () => vis.showJamMap = !vis.showJamMap),
                    new Tool("Renkler", "Renklerin anlamı [I]", legendOpen, () => legendOpen = !legendOpen),
                    new Tool("Olaylar", "Sağdaki olay akışını göster ya da gizle.", feedOpen, () => feedOpen = !feedOpen),
                } : new[]
                {
                    new Tool("Bağlantılar", "Haberleşme bağlantıları [L]: yeşil sağlam, kırmızı karıştırılmış.", vis.showLinks, () => vis.showLinks = !vis.showLinks),
                    new Tool("Planlar", "İHA'ların planları [P]: her İHA'nın sıradaki hedeflerine giden rota.", vis.showPlans, () => vis.showPlans = !vis.showPlans),
                    new Tool("Hayaletler", "İHA'nın sandığı konum [G]: GPS'siz İHA kendini nerede sanıyor (halka).", vis.showEstimates, () => vis.showEstimates = !vis.showEstimates),
                    new Tool("EH haritası", "Sürünün ortak karıştırma haritası [J]: İHA'ların karıştırma ölçtüğü bölgeler.", vis.showJamMap, () => vis.showJamMap = !vis.showJamMap),
                    new Tool("Renkler", "Renklerin anlamı [I]", legendOpen, () => legendOpen = !legendOpen),
                    new Tool("Olaylar", "Sağdaki olay akışını göster ya da gizle.", feedOpen, () => feedOpen = !feedOpen),
                    new Tool("Panel", "Soldaki bilgi paneli [H]", hud != null && hud.visible, () => { if (hud != null) hud.visible = !hud.visible; }),
                }),
                ("MÜDAHALE", new[]
                {
                    new Tool("Arıza", "Rastgele bir İHA'yı arızalandır [Z]: düşer, görevleri diğer İHA'lara geçer.", false,
                             () => Send("{\"cmd\":\"fail\"}")),
                    new Tool("Yeni hedef", "Görev alanına yeni bir hedef ekle [Y]: sürü kimin gideceğine kendisi karar verir.", false,
                             () => Send("{\"cmd\":\"popup\"}")),
                    new Tool("Yeni harita", "Farklı görev noktalarıyla yeni bir uçuş başlat [N].", false,
                             () => Send("{\"cmd\":\"restart\"}")),
                }),
                ("KARIŞTIRICI", new[]
                {
                    new Tool("−", "Karıştırıcı gücünü azalt [−]: 30 → 20 → 10 dBm → kapalı. Uçuş yeniden başlar.", false,
                             () => Send("{\"cmd\":\"jammer\",\"step\":-1}")),
                    new Tool("+", "Karıştırıcı gücünü artır [+]: kapalı → 10 → 20 → 30 dBm. Uçuş yeniden başlar.", false,
                             () => Send("{\"cmd\":\"jammer\",\"step\":1}")),
                }),
                ("", new[]
                {
                    new Tool("Menü", "Menü [Esc]: senaryo değiştir, proje bilgisi, ana ekran.", false, () => Go(Page.Pause)),
                }),
            };

            const float bh = 42f, gapB = 6f, gapG = 22f, fs = 15f;
            float total = -gapG;
            foreach (var g in groups)
            {
                total += gapG - gapB;
                foreach (var t in g.tools) total += ToolW(t.label) + gapB;
            }
            float x = (Ui.W - total) / 2f, y = Ui.H - 20f - 14f - bh;
            float panelTop = y - 34f;
            Ui.Panel(Ui.R(x - 16, panelTop, total + 32, bh + 48), 16, 0.9f);
            foreach (var g in groups)
            {
                if (g.name.Length > 0) Ui.Label(Ui.R(x, y - 24, 200, 18), g.name, 11, Ui.Ink3, true);
                foreach (var t in g.tools)
                {
                    float bw = ToolW(t.label);
                    var r = Ui.R(x, y, bw, bh);
                    if (r.Contains(Event.current.mousePosition)) tip = t.tip;
                    if (Ui.Button(r, t.label, g.name.Length == 0 ? Ui.Kind.Ghost : Ui.Kind.Normal, t.sel, fs)) t.act();
                    x += bw + gapB;
                }
                x += gapG - gapB;
            }
            return panelTop;
        }

        void DrawTip(float tbTop)
        {
            float w = Mathf.Min(Ui.TextWidth(tip, 15) + 36f, 1000f);
            var r = Ui.R((Ui.W - w) / 2f, tbTop - 52f, w, 40);
            Ui.Fill(r, new Color(0.08f, 0.11f, 0.14f, 0.96f), 10);
            Ui.Outline(r, Ui.Line, 1f, 10);
            Ui.Label(r, tip, 15, Ui.Ink, false, TextAnchor.MiddleCenter);
        }

        void DrawLegendPanel(float tbTop)
        {
            float w = 760f, colW = 340f, h = 452f;
            float x = Ui.W - w - 20f, y = tbTop - 16f - h;
            Ui.Panel(Ui.R(x, y, w, h), 14, 0.92f);
            Ui.Label(Ui.R(x + 22, y + 14, 300, 20), "RENKLERİN ANLAMI", 11.5f, Ui.Accent, true);
            if (Ui.Button(Ui.R(x + w - 48, y + 10, 32, 32), "×", Ui.Kind.Ghost, size: 18)) legendOpen = false;
            DrawLegend(x + 22, y + 44, colW, 14.5f, 0, 14, false);
            DrawLegend(x + 22 + colW + 30, y + 44, colW, 14.5f, 14, Legend.Length, true);
        }

        // ------------------------------------------------------------ görev sonu
        void DrawResults()
        {
            var f = SwarmVisualizer.Main.Frame;
            if (f?.ctl == null || f.m == null || f.ctl.finished != 1) return;
            bool cmpOn = CompareOn;
            var fb = cmpOn ? SwarmCompare.Instance.B.Frame : null;
            if (cmpOn && (fb?.ctl == null || fb.ctl.finished != 1 || fb.m == null)) return;
            int key = f.ctl.seed * 100000 + Mathf.RoundToInt(f.t * 10f);
            if (resultsClosedFor == key) return;

            float w = cmpOn ? 960f : 860f, h = cmpOn ? 470f : 500f;
            float x = (Ui.W - w) / 2f, y = (Ui.H - h) / 2f - 40f;
            Ui.Panel(Ui.R(x, y, w, h), 18, 0.97f);
            float px = x + 30f, pw = w - 60f;
            bool all = f.m.done == f.m.total;
            Ui.Chip(px, y + 24, "UÇUŞ BİTTİ", Ui.Good, 11.5f);
            string title = cmpOn ? "Aynı saldırı, iki sürü: sonuç" : all ? "Görev tamamlandı" : "Sürü indi, bazı hedefler yapılamadı";
            Ui.Label(Ui.R(px, y + 52, pw, 36), title, 27, Ui.Ink, true);
            Ui.Label(Ui.R(px, y + 90, pw, 24), (running?.Title ?? "Canlı simülasyon") + " · harita #" + f.ctl.seed, 15, Ui.Ink3);
            float sy = y + 126f;

            if (!cmpOn)
            {
                float sw = (pw - 3 * 12f) / 4f;
                float doneAt = SwarmEvents.Instance != null && SwarmEvents.Instance.MissionDoneAt > 0f ? SwarmEvents.Instance.MissionDoneAt : f.t;
                Ui.Stat(Ui.R(px, sy, sw, 112), $"%{100f * f.m.done / Mathf.Max(1, f.m.total):0}", $"tamamlanan hedef ({f.m.done}/{f.m.total})", all ? Ui.Good : Ui.Warn);
                Ui.Stat(Ui.R(px + (sw + 12), sy, sw, 112), $"{f.m.score * 100f:0}", "görev puanı (100 üzerinden; geç yapılan hedef daha az değerli)", Ui.Accent);
                Ui.Stat(Ui.R(px + 2 * (sw + 12), sy, sw, 112), $"{doneAt:0} s", all ? "kalkıştan son hedefe kadar süre" : "uçuş süresi", Ui.Ink);
                Ui.Stat(Ui.R(px + 3 * (sw + 12), sy, sw, 112), $"{f.m.falseDone}", "yanlış \"bitti\": İHA hedefi bulduğunu sandı ama bulamadı",
                        f.m.falseDone == 0 ? Ui.Good : Ui.Bad);
                sy += 128f;
                string detail = Detail(f);
                if (detail.Length > 0)
                {
                    Ui.Label(Ui.R(px, sy, pw, 24), detail, 15.5f, Ui.Ink2);
                    sy += 34f;
                }
                if (running != null)
                {
                    var rb = Ui.R(px, sy, pw, 74);
                    Ui.Fill(rb, new Color(1f, 1f, 1f, 0.05f), 12);
                    Ui.Label(Ui.R(px + 16, sy + 10, pw - 32, 22), "Aynı senaryoda 30 deney uçuşunun ortalaması (görev tamamlama):", 14, Ui.Ink3);
                    string R(int s, float v, string name) => s == runStrategy ? $"<b><color=#ffffff>{name} %{Pct(v)}</color></b>" : $"{name} %{Pct(v)}";
                    Ui.Label(Ui.R(px + 16, sy + 36, pw - 32, 28),
                             R(2, running.RefResilient, "EH dirençli") + "   ·   " + R(1, running.RefDecentral, "merkeziyetsiz") + "   ·   " +
                             R(0, running.RefCentral, "merkezi"), 17, Ui.Ink2);
                }
            }
            else
            {
                float cw2 = (pw - 24f) / 2f;
                Side(px, sy, cw2, $"Solda: {SwarmScenarios.StrategyTitle(f.strategy)}", f, Ui.Warn);
                Side(px + cw2 + 24, sy, cw2, "Sağda: EH dirençli sürü", fb, Ui.Good);
            }

            float by = y + h - 82f;
            if (Ui.Button(Ui.R(px, by, 240, 54), "Yeni haritada tekrar", Ui.Kind.Primary, size: 17))
            {
                resultsClosedFor = key;
                Send("{\"cmd\":\"restart\"}");
            }
            if (Ui.Button(Ui.R(px + 254, by, 190, 54), "Başka senaryo", size: 17)) { resultsClosedFor = key; Go(Page.Scenarios); }
            if (!cmpOn && running != null && Ui.Button(Ui.R(px + 458, by, 180, 54), "Yan yana izle", size: 17))
            {
                scenario = Array.IndexOf(SwarmScenarios.All, running);
                compare = true;
                if (strategy == 2) strategy = 1;
                Launch();
            }
            if (Ui.Button(Ui.R(x + w - 30 - 130, by, 130, 54), "Kapat", Ui.Kind.Ghost, size: 17)) resultsClosedFor = key;
        }

        static string Detail(SwarmFrame f)
        {
            var sb = new StringBuilder();
            if (f.jammers != null && f.jammers.Length > 0)
                sb.Append(f.m.jamErr >= 0f ? $"Karıştırıcının yeri {f.m.jamErr:0} m hatayla bulundu" : "Karıştırıcının yeri bulunamadı");
            if (f.spoofers != null && f.spoofers.Length > 0)
                sb.Append(sb.Length > 0 ? " · " : "").Append($"GPS aldatmayı fark eden İHA: {f.m.spoofSeen}");
            if (f.m.liars >= 0f)
                sb.Append(sb.Length > 0 ? " · " : "").Append($"saldırganları dışlama: %{f.m.liars * 100f:0}");
            return sb.ToString();
        }

        static void Side(float x, float y, float w, string title, SwarmFrame f, Color c)
        {
            Ui.Label(Ui.R(x, y, w, 26), title, 17, c, true);
            float sw = (w - 24f) / 3f;
            Ui.Stat(Ui.R(x, y + 32, sw, 112), $"%{100f * f.m.done / Mathf.Max(1, f.m.total):0}", $"tamamlanan hedef ({f.m.done}/{f.m.total})", c);
            Ui.Stat(Ui.R(x + sw + 12, y + 32, sw, 112), $"{f.m.score * 100f:0}", "görev puanı", c);
            Ui.Stat(Ui.R(x + 2 * (sw + 12), y + 32, sw, 112), $"{f.m.falseDone}", "yanlış \"bitti\"", f.m.falseDone == 0 ? Ui.Good : Ui.Bad);
        }

        // ------------------------------------------------------------ otomatik arayüz testi
        IEnumerator UiTest(string dir)
        {
            Directory.CreateDirectory(dir);
            Application.runInBackground = true;
            var log = new StringBuilder();
            IEnumerator Wait(float s)
            {
                float t = Time.realtimeSinceStartup + s;
                while (Time.realtimeSinceStartup < t) yield return null;
            }
            IEnumerator Shot(string name)
            {
                yield return new WaitForEndOfFrame();
                var tex = ScreenCapture.CaptureScreenshotAsTexture();
                File.WriteAllBytes(Path.Combine(dir, name + ".png"), tex.EncodeToPNG());
                Destroy(tex);
                log.AppendLine($"çekim {name}: sayfa={Current} durum={launcher.Status}");
            }
            IEnumerator Until(Func<bool> cond, float max)
            {
                float t = Time.realtimeSinceStartup + max;
                while (!cond() && Time.realtimeSinceStartup < t) yield return null;
            }

            log.AppendLine($"simülasyon klasörü: {launcher.RepoPath ?? "-"} python: {launcher.PythonPath ?? "-"} durum: {launcher.Status}");
            yield return Wait(5f);
            yield return Shot("01_ana_ekran");
            Go(Page.Scenarios);
            yield return Wait(1f);
            yield return Shot("02_senaryo_sec");
            Current = Page.Home;
            Go(Page.About);
            yield return Wait(1f);
            yield return Shot("03_proje_nedir");
            Current = Page.Home;
            Go(Page.Help);
            yield return Wait(1f);
            yield return Shot("04_nasil_kullanilir");
            Current = Page.Home;

            fast = true;
            QuickStart();
            float t0 = Time.realtimeSinceStartup;
            yield return Shot("05_baslatiliyor");
            yield return Until(() => SimConnected, 45f);
            log.AppendLine($"bağlantı: {(SimConnected ? "var" : "YOK")} {Time.realtimeSinceStartup - t0:0.0} s, durum={launcher.Status} {launcher.LastError}");
            yield return Wait(6f);
            yield return Shot("06_senaryo_kutusu");
            yield return Wait(18f);
            yield return Shot("07_gorevde");
            legendOpen = true;
            yield return Wait(1f);
            yield return Shot("08_renkler");
            legendOpen = false;
            Go(Page.Pause);
            yield return Wait(1f);
            yield return Shot("09_menu");
            Current = Page.Sim;
            cam.mode = SwarmCamera.Mode.Top;
            yield return Until(() => SwarmVisualizer.Main.Frame?.ctl?.finished == 1, 150f);
            yield return Wait(2f);
            yield return Shot("10_sonuc");
            var f = SwarmVisualizer.Main.Frame;
            log.AppendLine($"uçuş sonu: bitti={f?.ctl?.finished} görev={f?.m?.done}/{f?.m?.total} puan={f?.m?.score:0.00} t={f?.t:0}");
            log.AppendLine("olay akışı (tek sürü):");
            foreach (var e in SwarmEvents.Instance.Items) log.AppendLine($"  t={e.sim:0} {e.text}");

            scenario = 6;
            strategy = 1;
            compare = true;
            Launch();
            yield return Until(() => SimConnected && CompareOn, 45f);
            log.AppendLine($"yan yana: {(CompareOn ? "açık" : "AÇILMADI")} durum={launcher.Status} {launcher.LastError}");
            yield return Wait(25f);
            yield return Shot("11_yan_yana");

            log.AppendLine("olay akışı (yan yana, sağdaki sürü):");
            foreach (var e in SwarmEvents.Instance.Items) log.AppendLine($"  t={e.sim:0} {e.text}");
            launcher.Stop();
            File.WriteAllText(Path.Combine(dir, "rapor.txt"), log.ToString());
            yield return Wait(1f);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }
    }
}
