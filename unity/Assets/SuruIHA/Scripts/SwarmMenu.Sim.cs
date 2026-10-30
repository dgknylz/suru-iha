using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
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

        bool Tpp => cam != null && cam.mode == SwarmCamera.Mode.Follow;

        void DrawSim()
        {
            float top = CompareOn ? 128f : 20f;
            bool tpp = Tpp;
            // Dünyadaki İHA etiketleri en altta çizilir (paneller üstlerini örtsün)
            if (cam != null && cam.mode == SwarmCamera.Mode.Top) DrawDroneNumbers();
            else if (tpp) DrawFollowLabels();
            DrawBanner(top);
            // Yan yana İHA kamerasında sağdaki kart olay akışının yerini alır; akış kartın altına iner
            bool cardRight = tpp && CompareOn;
            float feedTop = cardRight ? top + 50f + 132f + 14f : top, below = feedTop;
            if (feedOpen) below = DrawFeed(feedTop, cardRight || (chartsOpen && !legendOpen) ? 3 : legendOpen ? 4 : 6) + 12f;
            if (tpp) DrawDroneCards(top + 50f);
            float tbTop = DrawToolbar();
            if (replayOn) tbTop = DrawReplayBar(tbTop);
            float above = tbTop;
            if (tpp) above = DrawDroneSelector(tbTop);
            DrawHeatScale(above);
            if (chartsOpen && !legendOpen) DrawLiveCharts(Ui.W - 450f, below, 430f, above - 16f - below);   // akışın altında
            if (legendOpen) DrawLegendPanel(above);
            if (layersOpen) DrawLayersPanel(above);
            if (!replayOn) DrawResults();
            if (tip != null) DrawTip(above);
        }

        // ------------------------------------------------------------ İHA kamerası (TPP)
        // İzlenen İHA'nın bilgi kartı (yan yana ekranda her yarıya bir kart, aynı numaralı İHA)
        void DrawDroneCards(float y)
        {
            var vis = SwarmVisualizer.Main;
            if (vis == null || vis.Drones.Count == 0) return;
            int i = Mathf.Clamp(cam.FollowIndex, 0, vis.Drones.Count - 1);
            if (CompareOn)
            {
                float half = Ui.W / 2f, w = 600f;
                DroneCard(vis.Drones[i].State, $"İHA-{i + 1}", "korumasız sürü", (half - w) / 2f, y, w);
                var b = SwarmCompare.Instance.B;
                if (i < b.Drones.Count) DroneCard(b.Drones[i].State, $"İHA-{i + 1}", "dirençli sürü", half + (half - w) / 2f, y, w);
            }
            else DroneCard(vis.Drones[i].State, $"İHA-{i + 1}", null, (Ui.W - 780f) / 2f, y, 780f);
        }

        static void DroneCard(DroneState s, string name, string side, float x, float y, float w)
        {
            if (s == null) return;
            const float h = 132f;
            Ui.Panel(Ui.R(x, y, w, h), 14, 0.9f);
            Color c = DroneView.StatusColor(s);
            if (s.mode == 4) c = new Color(0.45f, 0.45f, 0.45f);
            Ui.Dot(new Vector2((x + 30f) * Ui.S, (y + 30f) * Ui.S), 9f, c);
            Ui.Label(Ui.R(x + 48, y + 13, 160, 34), name, 24, Ui.Ink, true);
            float nx = x + 48 + Ui.TextWidth(name, 24, true) + 14f;
            Ui.Chip(nx, y + 19, Ui.Upper(DroneView.StatusName(s)), c, 12f);
            string ph = DroneView.PhaseName(s.phase) + " evresi";
            Ui.Label(Ui.R(x + w - 300, y + 20, 280, 22), side != null ? $"{side} · {ph}" : ph, 14.5f, Ui.Ink2, false, TextAnchor.UpperRight);

            (string k, string v, Color col)[] fields =
            {
                ("GPS", s.gps == 1 ? "var" : "yok", s.gps == 1 ? Ui.Good : Ui.Bad),
                ("Konum belirsizliği", $"{s.sigma:0} m", s.sigma > 15f ? Ui.Warn : Ui.Ink),
                ("Karıştırma", $"%{s.jam * 100f:0}", s.jam > 0.35f ? Ui.Warn : Ui.Ink),
                ("Şimdiki hedef", s.task >= 0 ? $"#{s.task + 1}" : "yok", Ui.Ink),
                ($"Batarya · {s.pw} W", $"%{s.bat * 100f:0}", s.bat < 0.15f ? Ui.Bad : s.bat < 0.3f ? Ui.Warn : Ui.Ink),
            };
            float fw = (w - 44f) / fields.Length;
            for (int k = 0; k < fields.Length; k++)
            {
                float fx = x + 22 + k * fw;
                Ui.Label(Ui.R(fx, y + 54, fw - 8, 18), fields[k].k, 12.5f, Ui.Ink3);
                Ui.Label(Ui.R(fx, y + 72, fw - 8, 26), fields[k].v, 18, fields[k].col, true);
            }
            string plan = s.plan != null && s.plan.Length > 0 ? "Plan: " + string.Join(" → ", System.Array.ConvertAll(s.plan, t => "#" + (t + 1))) : "Plan: boş";
            if (s.relay >= 0) plan += $"  ·  röle: İHA-{s.relay + 1} ile bağlantıyı koruyor";
            Ui.Label(Ui.R(x + 22, y + 104, w - 44, 22), plan, 14.5f, Ui.Ink2);
        }

        // Alttaki İHA seçici: her düğmenin altındaki çizgi İHA'nın durum rengidir
        float DrawDroneSelector(float tbTop)
        {
            var vis = SwarmVisualizer.Main;
            int n = vis != null ? vis.Drones.Count : 0;
            if (n == 0) return tbTop;
            const float bw = 92f, gap = 6f, labelW = 96f;
            const string hint = "fare: döndür · tekerlek: yakınlaş · R: sıfırla";
            float hintW = Ui.TextWidth(hint, 13.5f) + 24f;
            float total = labelW + n * (bw + gap) - gap + hintW;
            float x = (Ui.W - total) / 2f, y = tbTop - 12f - 60f;
            Ui.Panel(Ui.R(x - 14, y, total + 28, 60), 14, 0.9f);
            Ui.Label(Ui.R(x, y, labelW, 60), "İHA SEÇ", 12, Ui.Ink3, true, TextAnchor.MiddleLeft);
            for (int i = 0; i < n; i++)
            {
                var st = vis.Drones[i].State;
                Color c = st != null ? DroneView.StatusColor(st) : Ui.Ink3;
                if (st != null && st.mode == 4) c = new Color(0.45f, 0.45f, 0.45f);
                float bx = x + labelW + i * (bw + gap);
                var r = Ui.R(bx, y + 9, bw, 42);
                if (r.Contains(Event.current.mousePosition) && st != null) tip = $"İHA-{i + 1}: {DroneView.StatusName(st)} · {DroneView.PhaseName(st.phase)} evresi";
                if (Ui.Button(r, $"İHA-{i + 1}", Ui.Kind.Normal, i == cam.FollowIndex, 15)) cam.SetFollow(i);
                Ui.Fill(Ui.R(bx + 16, y + 9 + 42 - 7, bw - 32, 3), c, 1.5f);
            }
            Ui.Label(Ui.R(x + total - hintW + 12, y, hintW, 60), hint, 13.5f, Ui.Ink3, false, TextAnchor.MiddleLeft);
            return y;
        }

        // Dünyadaki bir noktanın üstüne küçük etiket; tıklanabilir ise tıklanınca true
        static bool WorldChip(Camera c, Vector3 world, string text, Color col, bool clickable)
        {
            if (c == null) return false;
            Vector3 sp = c.WorldToScreenPoint(world);
            if (sp.z <= 0f || !c.pixelRect.Contains(new Vector2(sp.x, sp.y))) return false;
            float w = (Ui.TextWidth(text, 13.5f, true) + 22f) * Ui.S, h = 26f * Ui.S;
            var r = new Rect(sp.x - w / 2f, Screen.height - sp.y - h - 8f * Ui.S, w, h);
            bool hover = clickable && r.Contains(Event.current.mousePosition);
            Ui.Fill(r, new Color(0.03f, 0.05f, 0.07f, hover ? 0.95f : 0.82f), 13f);
            Ui.Outline(r, col, hover ? 2f : 1.5f, 13f);
            GUI.Label(r, text, Ui.Style(13.5f, Ui.Ink, true, TextAnchor.MiddleCenter, false));
            if (!clickable) return false;
            Ui.Block(r);
            return Ui.Click(r);
        }

        static Color ChipColor(DroneView d)
        {
            if (d.State == null) return Ui.Ink3;
            return d.State.mode == 4 ? new Color(0.45f, 0.45f, 0.45f) : DroneView.StatusColor(d.State);
        }

        // İHA kamerasında izlenen İHA'nın üstünde adı (yan yana ekranda iki tarafta da)
        void DrawFollowLabels()
        {
            var vis = SwarmVisualizer.Main;
            if (vis.Drones.Count == 0) return;
            int i = Mathf.Clamp(cam.FollowIndex, 0, vis.Drones.Count - 1);
            float up = 0.5f * vis.droneScale;   // İHA'nın hemen üstü
            var main = cam.GetComponent<Camera>();
            WorldChip(main, vis.Drones[i].transform.position + Vector3.up * up, $"İHA-{i + 1}", ChipColor(vis.Drones[i]), false);
            var cmp = SwarmCompare.Instance;
            if (CompareOn && i < cmp.B.Drones.Count)
                WorldChip(cmp.CamB, cmp.B.Drones[i].transform.position + Vector3.up * up, $"İHA-{i + 1}", ChipColor(cmp.B.Drones[i]), false);
        }

        // Taktik görünümde her İHA'nın numarası; tıklanınca kamera o İHA'ya geçer
        void DrawDroneNumbers()
        {
            var vis = SwarmVisualizer.Main;
            var main = cam.GetComponent<Camera>();
            for (int i = 0; i < vis.Drones.Count; i++)
                if (WorldChip(main, vis.Drones[i].transform.position, (i + 1).ToString(), ChipColor(vis.Drones[i]), true))
                {
                    cam.SetFollow(i);
                    cam.mode = SwarmCamera.Mode.Follow;
                }
            var cmp = SwarmCompare.Instance;
            if (!CompareOn) return;
            for (int i = 0; i < cmp.B.Drones.Count; i++)
                if (WorldChip(cmp.CamB, cmp.B.Drones[i].transform.position, (i + 1).ToString(), ChipColor(cmp.B.Drones[i]), true))
                {
                    cam.SetFollow(i);
                    cam.mode = SwarmCamera.Mode.Follow;
                }
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
                if (Ui.Button(Ui.R(x + 234, top + 82, 200, 38), "Senaryo seç", size: 15)) OpenMenu(Tab.Simulasyon);
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
                Ui.Label(Ui.R(x + 36 + cx, top + 12, w - 120 - cx, 32), RunTitle, 22, Ui.Ink, true);
                if (Ui.Button(Ui.R(x + w - 52, top + 12, 34, 34), "×", Ui.Kind.Ghost, size: 20)) bannerOpen = false;
                string arch = f == null ? "" : runCompare
                    ? $"Solda {SwarmScenarios.StrategyTitle(f.strategy)}, sağda EH dirençli sürü · {SwarmScenarios.PlannerTitle(f.planner, "resilient")}"
                    : $"{SwarmScenarios.StrategyTitle(f.strategy)} · {SwarmScenarios.PlannerTitle(f.planner, f.strategy)}";
                Ui.Label(Ui.R(x + 24, top + 50, tw, 22), arch, 14, Ui.Ink3);
                Ui.Label(Ui.R(x + 24, top + 76, tw, wh + 4), watch, 16.5f, Ui.Ink);
            }
            else
            {
                string s = "Ne izlemeliyim?  ·  " + RunTitle;
                float pw = Ui.TextWidth(s, 15, true) + 44f;
                if (Ui.Button(Ui.R((Ui.W - pw) / 2f, top, pw, 38), s, size: 15))
                {
                    bannerOpen = true;
                    bannerUntil = Time.unscaledTime + 20f;
                }
            }
        }

        // ------------------------------------------------------------ olay akışı
        // Olay akışı kartı; alt kenarını döndürür (altına canlı grafikler gelir)
        float DrawFeed(float top, int max)
        {
            var ev = SwarmEvents.Instance;
            if (ev == null || !SimConnected) return top;
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
            return top + ph;
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
        static float ToolW(string label) => Mathf.Max(50f, Ui.TextWidth(label, 15f, true) + 40f);

        float DrawToolbar()
        {
            var vis = SwarmVisualizer.Main;
            if (hud == null && cam != null) hud = cam.GetComponent<SwarmHud>();
            bool cmpOn = CompareOn;
            var heatTool = new Tool("Isı haritası", "Karıştırma ısı haritası: karıştırıcının uçuş yüksekliğindeki gücü, tepelerin gölgesiyle. " +
                                                    "Açık kırmızı zayıf, koyu kırmızı güçlü; kalın çizgide bağlantı kopar.",
                                    vis.showHeatMap, () => vis.showHeatMap = !vis.showHeatMap);
            var groups = new (string name, Tool[] tools)[]
            {
                ("KAMERA", new[]
                {
                    new Tool("Sinematik", "Sinematik kamera [C]: sürünün etrafında yavaşça döner.", cam.mode == SwarmCamera.Mode.Cinematic,
                             () => cam.mode = SwarmCamera.Mode.Cinematic),
                    new Tool("Serbest", "Serbest kamera [O]: sürükleyerek döndür, tekerlekle yakınlaş, WASD ile kaydır.", cam.mode == SwarmCamera.Mode.Orbit,
                             () => cam.mode = SwarmCamera.Mode.Orbit),
                    new Tool("İHA kamerası", "İHA kamerası [F]: seçili İHA'yı arkasından izle (üçüncü şahıs). Alttan İHA seç ya da 1-9 / 0; " +
                                             "taktik görünümde İHA numarasına tıkla.",
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
                    heatTool,
                    new Tool("Katmanlar", "Görünüm katmanları: İHA bağlantıları, ısı haritası, planlar, hayaletler, izler. Her biri ayrı açılıp kapanır.",
                             layersOpen, () => layersOpen = !layersOpen),
                    new Tool("Renkler", "Renklerin anlamı [I]", legendOpen, () => legendOpen = !legendOpen),
                    new Tool("Olaylar", "Sağdaki olay akışını göster ya da gizle.", feedOpen, () => feedOpen = !feedOpen),
                    new Tool("Grafikler", "Canlı grafikler: paket iletimi, GPS'siz uçan İHA ve görev puanı uçuş boyunca. Üstüne gelince o anın değeri.",
                             chartsOpen, () => chartsOpen = !chartsOpen),
                } : new[]
                {
                    heatTool,
                    new Tool("Katmanlar", "Görünüm katmanları: İHA bağlantıları, ısı haritası, planlar, hayaletler, izler. Her biri ayrı açılıp kapanır.",
                             layersOpen, () => layersOpen = !layersOpen),
                    new Tool("Renkler", "Renklerin anlamı [I]", legendOpen, () => legendOpen = !legendOpen),
                    new Tool("Olaylar", "Sağdaki olay akışını göster ya da gizle.", feedOpen, () => feedOpen = !feedOpen),
                    new Tool("Grafikler", "Canlı grafikler: paket iletimi, GPS'siz uçan İHA ve görev puanı uçuş boyunca. Üstüne gelince o anın değeri.",
                             chartsOpen, () => chartsOpen = !chartsOpen),
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
                    new Tool("Tekrar", "Uçuşu baştan tekrar izle: zaman çubuğuyla ileri geri sar, yavaşlat ya da hızlandır. " +
                                       "Canlı simülasyon arkada bekler.", replayOn, ToggleReplay),
                    new Tool("Ses", "Sesi aç ya da kapat: pervane uğultusu, rüzgâr, ırmak ve olaylarda yumuşak bir ton. " +
                                    "Seviye Simülasyon sekmesinde (Kısık / Normal).", SwarmAudio.On, SwarmAudio.Toggle),
                    new Tool("Menü", "Menü [Esc]: senaryo değiştir, proje bilgisi, ana ekran.", false, () => Go(Page.Pause)),
                }),
            };

            const float bh = 42f;
            float gapB = 6f, gapG = 18f, fs = 15f;
            float total = -gapG;
            foreach (var g in groups)
            {
                total += gapG - gapB;
                foreach (var t in g.tools) total += ToolW(t.label) + gapB;
            }
            // Ekrana sığmazsa düğmeler orantılı daralır
            float k = Mathf.Min(1f, (Ui.W - 72f) / total);
            gapB *= k;
            gapG *= k;
            fs *= Mathf.Max(k, 0.9f);
            total *= k;
            float x = (Ui.W - total) / 2f, y = Ui.H - 20f - 14f - bh;
            float panelTop = y - 34f;
            Ui.Panel(Ui.R(x - 16, panelTop, total + 32, bh + 48), 16, 0.9f);
            foreach (var g in groups)
            {
                if (g.name.Length > 0) Ui.Label(Ui.R(x, y - 24, 200, 18), g.name, 11, Ui.Ink3, true);
                foreach (var t in g.tools)
                {
                    float bw = ToolW(t.label) * k;
                    var r = Ui.R(x, y, bw, bh);
                    if (r.Contains(Event.current.mousePosition)) tip = t.tip;
                    if (Ui.Button(r, t.label, t.label == "Menü" ? Ui.Kind.Ghost : Ui.Kind.Normal, t.sel, fs)) t.act();
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
            float w = 760f, colW = 340f, h = 630f;
            float x = Ui.W - w - 20f, y = tbTop - 16f - h;
            Ui.Panel(Ui.R(x, y, w, h), 14, 0.92f);
            Ui.Label(Ui.R(x + 22, y + 14, 300, 20), "RENKLERİN ANLAMI", 11.5f, Ui.Accent, true);
            if (Ui.Button(Ui.R(x + w - 48, y + 10, 32, 32), "×", Ui.Kind.Ghost, size: 18)) legendOpen = false;
            int eh = System.Array.FindIndex(Legend, e => e.group == "ELEKTRONİK HARP");   // İHA ışığı + hedef halkası solda
            DrawLegend(x + 22, y + 44, colW, 14.5f, 0, eh, false);
            DrawLegend(x + 22 + colW + 30, y + 44, colW, 14.5f, eh, Legend.Length, true);
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

            float w = 1180f, h = cmpOn ? 470f : 500f;
            float x = (Ui.W - w) / 2f, y = (Ui.H - h) / 2f - 40f;
            Ui.Panel(Ui.R(x, y, w, h), 18, 0.97f);
            float px = x + 30f, pw = w - 60f;
            bool all = f.m.done == f.m.total;
            var cv = SwarmHud.Convoy(f);
            Ui.Chip(px, y + 24, "UÇUŞ BİTTİ", Ui.Good, 11.5f);
            string title = cmpOn ? "Aynı saldırı, iki sürü: sonuç"
                         : cv != null ? (cv.arrived == 1 ? (cv.lost == 0 ? "Konvoy kayıpsız hedefe ulaştı" : "Konvoy hedefe ulaştı, araç kaybı var")
                                                         : "Konvoy hedefe ulaşamadı")
                         : all ? "Görev tamamlandı" : "Sürü indi, bazı hedefler yapılamadı";
            Ui.Label(Ui.R(px, y + 52, pw, 36), title, 27, Ui.Ink, true);
            Ui.Label(Ui.R(px, y + 90, pw, 24), (RunTitle ?? "Canlı simülasyon") + " · harita #" + f.ctl.seed, 15, Ui.Ink3);
            float sy = y + 126f;

            if (!cmpOn && cv != null)
            {
                // Konvoy görevi: ölçüt araçlar, tehditler ve sürünün kaybı
                float sw = (pw - 3 * 12f) / 4f;
                int n = cv.v.Length / 5, found = 0, nt = cv.threats?.Length ?? 0;
                if (cv.threats != null) foreach (var t in cv.threats) found += t.f;
                int kam = f.radars != null ? System.Array.FindAll(f.radars, r => r.dead == 1).Length : 0;
                Ui.Stat(Ui.R(px, sy, sw, 112), $"{n - cv.lost}/{n}", cv.arrived == 1 ? "İKA sağlam, konvoy hedefte" : "İKA sağlam, konvoy hedefe varamadı",
                        cv.lost == 0 && cv.arrived == 1 ? Ui.Good : Ui.Bad);
                Ui.Stat(Ui.R(px + (sw + 12), sy, sw, 112), $"{found}/{nt}", "gizli tehdit bulundu (mayın, pusu)", found == nt ? Ui.Good : Ui.Warn);
                Ui.Stat(Ui.R(px + 2 * (sw + 12), sy, sw, 112), $"{f.m.falseDone}", "yol parçası taranmadan \"temiz\" sayıldı",
                        f.m.falseDone == 0 ? Ui.Good : Ui.Bad);
                Ui.Stat(Ui.R(px + 3 * (sw + 12), sy, sw, 112), $"{f.m.shot + kam}", kam > 0 ? $"kaybedilen İHA (füze {f.m.shot}, radara dalan kamikaze {kam})"
                        : $"kaybedilen İHA (füze {f.m.shot})", f.m.shot == 0 ? Ui.Good : Ui.Bad);
                sy += 128f;
                Ui.Label(Ui.R(px, sy, pw, 24), kam > 0 ? "HSS radarı imha edildi: sürü şemsiyenin altındaki yolu da taradı." : "HSS radarı ayakta kaldı.",
                         15.5f, Ui.Ink2);
                sy += 34f;
                if (running != null && !running.Custom)
                {
                    var rb = Ui.R(px, sy, pw, 74);
                    Ui.Fill(rb, new Color(1f, 1f, 1f, 0.05f), 12);
                    Ui.Label(Ui.R(px + 16, sy + 10, pw - 32, 22), "Aynı senaryoda 30 deney uçuşunun ortalaması (konvoyun hedefe varması):", 14, Ui.Ink3);
                    string R(int s, float v, string name) => s == runStrategy ? $"<b><color=#ffffff>{name} %{Pct(v)}</color></b>" : $"{name} %{Pct(v)}";
                    Ui.Label(Ui.R(px + 16, sy + 36, pw - 32, 28),
                             R(2, running.RefResilient, "EH dirençli") + "   ·   " + R(1, running.RefDecentral, "merkeziyetsiz") + "   ·   " +
                             R(0, running.RefCentral, "merkezi") + (running.RefText != null ? "   ·   " + running.RefText.Replace("Deneyde ", "") : ""),
                             17, Ui.Ink2);
                }
            }
            else if (!cmpOn)
            {
                float sw = (pw - 3 * 12f) / 4f;
                float doneAt = SwarmEvents.Instance != null && SwarmEvents.Instance.MissionDoneAt > 0f ? SwarmEvents.Instance.MissionDoneAt : f.t;
                Ui.Stat(Ui.R(px, sy, sw, 112), $"%{100f * f.m.done / Mathf.Max(1, f.m.total):0}", $"tamamlanan hedef ({f.m.done}/{f.m.total})", all ? Ui.Good : Ui.Warn);
                Ui.Stat(Ui.R(px + (sw + 12), sy, sw, 112), $"{f.m.score * 100f:0}", "görev puanı (100 üzerinden; geç yapılan hedef daha az değerli)", Ui.Accent);
                Ui.Stat(Ui.R(px + 2 * (sw + 12), sy, sw, 112), $"{doneAt:0} s", all ? "kalkıştan son hedefe kadar süre" : "uçuş süresi", Ui.Ink);
                bool threats = (f.radars != null && f.radars.Length > 0) || f.m.depleted > 0 || f.m.rtb > 0;
                if (threats)
                    Ui.Stat(Ui.R(px + 3 * (sw + 12), sy, sw, 112), $"{f.m.shot + f.m.depleted}",
                            $"düşen İHA (hava savunma {f.m.shot}, batarya {f.m.depleted})", f.m.shot + f.m.depleted == 0 ? Ui.Good : Ui.Bad);
                else
                    Ui.Stat(Ui.R(px + 3 * (sw + 12), sy, sw, 112), $"{f.m.falseDone}", "yanlış \"bitti\": İHA hedefi bulduğunu sandı ama bulamadı",
                            f.m.falseDone == 0 ? Ui.Good : Ui.Bad);
                sy += 128f;
                string detail = Detail(f);
                if (detail.Length > 0)
                {
                    Ui.Label(Ui.R(px, sy, pw, 24), detail, 15.5f, Ui.Ink2);
                    sy += 34f;
                }
                if (running != null && !running.Custom)
                {
                    var rb = Ui.R(px, sy, pw, 74);
                    Ui.Fill(rb, new Color(1f, 1f, 1f, 0.05f), 12);
                    Ui.Label(Ui.R(px + 16, sy + 10, pw - 32, 22), "Aynı senaryoda 30 deney uçuşunun ortalaması (görev tamamlama):", 14, Ui.Ink3);
                    string R(int s, float v, string name) => s == runStrategy ? $"<b><color=#ffffff>{name} %{Pct(v)}</color></b>" : $"{name} %{Pct(v)}";
                    Ui.Label(Ui.R(px + 16, sy + 36, pw - 32, 28),
                             R(2, running.RefResilient, "EH dirençli") + "   ·   " + R(1, running.RefDecentral, "merkeziyetsiz") + "   ·   " +
                             R(0, running.RefCentral, "merkezi") + (running.RefText != null ? "   ·   " + running.RefText.Replace("Deneyde ", "") : ""),
                             17, Ui.Ink2);
                }
            }
            else
            {
                float cw2 = (pw - 24f) / 2f;
                Side(px, sy, cw2, $"Solda: {SwarmScenarios.StrategyTitle(f.strategy)}", f, Ui.Warn);
                Side(px + cw2 + 24, sy, cw2, "Sağda: EH dirençli sürü", fb, Ui.Good);
            }

            float by = y + h - 82f;
            if (Ui.Button(Ui.R(px, by, 210, 54), "Uçuş raporu", Ui.Kind.Primary, size: 17, enabled: SwarmVisualizer.Main.Report != null))
            {
                resultsClosedFor = key;
                reportSide = 0;
                OpenMenu(Tab.Rapor);
            }
            if (Ui.Button(Ui.R(px + 224, by, 170, 54), "Tekrar izle", size: 17, enabled: SwarmVisualizer.Main.Receiver.RecCount > 20))
            {
                resultsClosedFor = key;
                StartReplay();
            }
            if (Ui.Button(Ui.R(px + 408, by, 170, 54), "Yeni harita", size: 17))
            {
                resultsClosedFor = key;
                Send("{\"cmd\":\"restart\"}");
            }
            if (Ui.Button(Ui.R(px + 592, by, 180, 54), "Başka senaryo", size: 17)) { resultsClosedFor = key; OpenMenu(Tab.Simulasyon); }
            if (!cmpOn && running != null && Ui.Button(Ui.R(px + 786, by, 170, 54), "Yan yana izle", size: 17))
            {
                useCustom = running.Custom;
                if (!useCustom) scenario = Array.IndexOf(SwarmScenarios.All, running);
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
            var cv = SwarmHud.Convoy(f);
            if (cv != null)
            {
                int n = cv.v.Length / 5, kam = f.radars != null ? System.Array.FindAll(f.radars, r => r.dead == 1).Length : 0;
                Ui.Stat(Ui.R(x, y + 32, sw, 112), $"{n - cv.lost}/{n}", cv.arrived == 1 ? "İKA sağlam, hedefte" : "İKA sağlam, varamadı",
                        cv.lost == 0 && cv.arrived == 1 ? Ui.Good : Ui.Bad);
                Ui.Stat(Ui.R(x + sw + 12, y + 32, sw, 112), $"{f.m.shot + kam}", "kaybedilen İHA", c);
                Ui.Stat(Ui.R(x + 2 * (sw + 12), y + 32, sw, 112), $"{f.m.falseDone}", "taranmadan \"temiz\"", f.m.falseDone == 0 ? Ui.Good : Ui.Bad);
                return;
            }
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
            // Kare hızı: 4 saniyede çizilen kare sayısı (dikey eşitleme açık: en fazla ekran tazeleme hızı)
            IEnumerator Fps(string view)
            {
                yield return Wait(0.5f);          // ekran görüntüsünün kaydı ölçüme karışmasın
                int f0 = Time.frameCount;
                float t0 = Time.realtimeSinceStartup, worst = 0f;
                while (Time.realtimeSinceStartup - t0 < 4f)
                {
                    worst = Mathf.Max(worst, Time.unscaledDeltaTime);
                    yield return null;
                }
                float fps = (Time.frameCount - f0) / (Time.realtimeSinceStartup - t0);
                log.AppendLine($"kare hızı ({view}): {fps:0} fps, en yavaş kare {worst * 1000f:0} ms, {Screen.width}x{Screen.height}");
            }

            IEnumerator Until(Func<bool> cond, float max)
            {
                float t = Time.realtimeSinceStartup + max;
                while (!cond() && Time.realtimeSinceStartup < t) yield return null;
            }

            log.AppendLine($"simülasyon klasörü: {launcher.RepoPath ?? "-"} python: {launcher.PythonPath ?? "-"} durum: {launcher.Status}");
            yield return Wait(6f);
            yield return Shot("01_sekme_proje");
            string[] tabShots = { "02_sekme_nasil_calisir", "03_sekme_kullanilanlar" };
            for (int k = 0; k < tabShots.Length; k++)
            {
                OpenMenu((Tab)(k + 1));
                yield return Wait(1f);
                yield return Shot(tabShots[k]);
            }
            OpenMenu(Tab.Bulgular);
            string[] findShots = { "04_bulgu_eh", "05_bulgu_karar", "06_bulgu_yapay_zeka", "07_bulgu_ablasyon", "08_bulgu_olcekleme",
                                   "08b_bulgu_tehditler", "08c_bulgu_konvoy" };
            for (int k = 0; k < findShots.Length; k++)
            {
                finding = k;
                yield return Wait(1f);
                yield return Shot(findShots[k]);
            }
            finding = 0;
            OpenMenu(Tab.Simulasyon);
            yield return Wait(1f);
            yield return Shot("09_sekme_simulasyon");
            OpenMenu(Tab.Kullanim);
            yield return Wait(1f);
            yield return Shot("10_sekme_kullanim");
            OpenMenu(Tab.Rapor);                   // henüz biten uçuş yok: boş rapor sekmesi
            yield return Wait(1f);
            yield return Shot("10b_sekme_rapor_bos");
            OpenMenu(Tab.Ozel);
            yield return Wait(1.5f);
            yield return Shot("10c_sekme_kendi_senaryon");
            OpenMenu(Tab.Proje);

            fast = true;
            QuickStart();
            float t0 = Time.realtimeSinceStartup;
            yield return Shot("11_baslatiliyor");
            yield return Until(() => SimConnected, 45f);
            log.AppendLine($"bağlantı: {(SimConnected ? "var" : "YOK")} {Time.realtimeSinceStartup - t0:0.0} s, durum={launcher.Status} {launcher.LastError}");
            yield return Wait(6f);
            yield return Shot("12_senaryo_kutusu");
            var hf = SwarmVisualizer.Main.Field;
            log.AppendLine(hf != null ? $"ısı haritası: {hf.nx}x{hf.ny} nokta, aralık {hf.step:0.#} m, eşikler {hf.detect:0} / {hf.cut:0.0} dBm"
                                      : "ısı haritası: GELMEDİ");
            // Ses: dinleyicinin duyduğu karışım kaydedilir (hoparlör testte susar)
            var snd = SwarmAudio.Instance;
            void Rec(string file, float s, string label)
            {
                if (snd != null) StartCoroutine(snd.Record(Path.Combine(dir, file), s, label, log));
                else log.AppendLine($"ses ({label}): SwarmAudio YOK");
            }
            Rec("ses_1_sinematik.wav", 10f, "sinematik");
            yield return Wait(14f);
            yield return Shot("13_gorevde");
            yield return Fps("sinematik");
            SetLinkMode(SwarmVisualizer.Main, 1);  // sürü karıştırma bölgesindeyken yalnızca karıştırılan bağlantılar
            cam.mode = SwarmCamera.Mode.Top;
            yield return Wait(2f);
            yield return Shot("13a_sorunlu_baglantilar");
            DefaultLayers(SwarmVisualizer.Main);
            cam.SetFollow(2);                      // İHA kamerası (TPP): İHA-3
            cam.mode = SwarmCamera.Mode.Follow;
            Rec("ses_2_iha_kamerasi.wav", 8f, "İHA kamerası");
            yield return Wait(3f);
            yield return Shot("13b_iha_kamerasi");
            yield return Wait(5.5f);
            cam.mode = SwarmCamera.Mode.Top;       // taktik görünümde tıklanabilir İHA numaraları
            yield return Wait(2.5f);
            yield return Shot("13c_taktik_numaralar");
            yield return Fps("taktik");
            layersOpen = true;
            yield return Wait(1f);
            yield return Shot("13d_katmanlar");
            layersOpen = false;
            cam.mode = SwarmCamera.Mode.Cinematic;
            legendOpen = true;
            yield return Wait(1f);
            yield return Shot("14_renkler");
            legendOpen = false;
            Go(Page.Pause);
            yield return Wait(1f);
            yield return Shot("15_esc_menu");
            OpenMenu(Tab.Bulgular);          // simülasyon arkada sürerken sekmelere dönüş
            yield return Wait(1f);
            yield return Shot("16_sim_acikken_sekmeler");
            Current = Page.Sim;
            cam.mode = SwarmCamera.Mode.Top;
            yield return Until(() => SwarmVisualizer.Main.Frame?.ctl?.finished == 1, 150f);
            yield return Wait(2f);
            yield return Shot("17_sonuc");
            OpenMenu(Tab.Rapor);                   // uçuş raporu: harita, İHA tablosu, öne çıkanlar
            yield return Wait(1.5f);
            yield return Shot("17b_ucus_raporu");
            var rp = SwarmVisualizer.Main.Report;
            log.AppendLine(rp != null ? $"uçuş raporu: {rp.drones.Length} İHA, iz {rp.drones.Sum(d => d.st.Length)} nokta, hedef {rp.drones.Sum(d => d.done)}"
                                      : "uçuş raporu: GELMEDİ");
            if (rp != null)
            {
                reportSel = Array.IndexOf(rp.drones, rp.drones.OrderByDescending(d => d.nogps + d.jam + 30f * d.search).First());
                yield return Wait(0.8f);
                yield return Shot("17c_ucus_raporu_secili_iha");
                reportSel = -1;
            }
            Current = Page.Sim;
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
            yield return Shot("18_yan_yana");
            cam.SetFollow(4);                      // yan yana İHA kamerası: iki sürüde de İHA-5
            cam.mode = SwarmCamera.Mode.Follow;
            yield return Wait(3f);
            yield return Shot("19_yan_yana_iha_kamerasi");

            log.AppendLine("olay akışı (yan yana, sağdaki sürü):");
            foreach (var e in SwarmEvents.Instance.Items) log.AppendLine($"  t={e.sim:0} {e.text}");

            scenario = 5;                          // sırt arkasında karıştırıcı: ısı haritasında arazi gölgesi
            strategy = 2;
            compare = false;
            Launch();
            yield return Until(() => !CompareOn && SwarmVisualizer.Main.Field != null && SwarmVisualizer.Main.Frame?.strategy == "resilient", 60f);
            log.AppendLine($"sırt senaryosu ısı haritası: {(SwarmVisualizer.Main.Field != null ? "var" : "YOK")}");
            bannerOpen = false;
            yield return Until(() => SwarmVisualizer.Main.Frame?.t > 80f, 40f);   // sürü görev alanında
            cam.mode = SwarmCamera.Mode.Top;
            float th = cam.topHeight;
            cam.topHeight = 1150f;                 // bütün görev alanı ve sırt görünsün
            yield return Wait(4f);
            yield return Shot("20_isi_haritasi_tepeden");
            cam.topHeight = th;
            cam.mode = SwarmCamera.Mode.Cinematic;
            yield return Wait(4f);
            yield return Shot("21_isi_haritasi_sinematik");

            // Kendi senaryon: iki karıştırıcı + GPS aldatıcı, 8 İHA, 10 hedef, 1 arıza (kayıtlı seçimlere dokunmaz)
            var saved = custom;
            custom = new CustomSetup
            {
                jammers = new List<Vector2> { new Vector2(-220f, 520f), new Vector2(240f, 250f) },
                spoofer = true, spooferPos = new Vector2(60f, 640f), drones = 1, tasks = 0, failures = 1,
            };
            compare = false;
            strategy = 2;
            OpenMenu(Tab.Ozel);
            yield return Wait(1f);
            yield return Shot("22_kendi_senaryon_kurulu");
            useCustom = true;
            Launch();
            yield return Until(() => SwarmVisualizer.Main.Frame?.drones?.Length == 8 && SwarmVisualizer.Main.Frame.t > 60f, 60f);
            var cf = SwarmVisualizer.Main.Frame;
            log.AppendLine($"kendi senaryon: İHA {cf?.drones?.Length} · karıştırıcı {cf?.jammers?.Length} · aldatıcı {cf?.spoofers?.Length} · " +
                           $"hedef {cf?.m?.total} · ısı haritası {(SwarmVisualizer.Main.Field != null ? "var" : "YOK")}");
            bannerOpen = false;
            cam.mode = SwarmCamera.Mode.Top;
            float th2 = cam.topHeight;
            cam.topHeight = 1150f;
            yield return Wait(4f);
            yield return Shot("23_kendi_senaryon_ucus");
            cam.topHeight = th2;
            custom = saved;

            // Karlı bölge: temel görev (karıştırıcısız: kar örtüsü ısı haritasının altında kalmasın)
            region = 1;
            scenario = 0;
            strategy = 2;
            compare = false;
            useCustom = false;
            Launch();
            yield return Until(() => SwarmVisualizer.Main.Frame?.region == "kar" && SwarmVisualizer.Main.Frame.t > 70f, 60f);
            var kf = SwarmVisualizer.Main.Frame;
            log.AppendLine($"karlı bölge: bölge={kf?.region} kök={SwarmVisualizer.Main.transform.position} İHA {kf?.drones?.Length} " +
                           $"ısı haritası {(SwarmVisualizer.Main.Field != null ? "var" : "YOK")}");
            bannerOpen = false;
            cam.mode = SwarmCamera.Mode.Cinematic;
            Rec("ses_3_karli_bolge.wav", 8f, "karlı bölge");
            yield return Wait(4f);
            yield return Shot("24_karli_bolge_sinematik");
            yield return Fps("karlı bölge");
            cam.SetFollow(2);
            cam.mode = SwarmCamera.Mode.Follow;
            yield return Wait(3f);
            yield return Shot("25_karli_bolge_iha_kamerasi");
            cam.mode = SwarmCamera.Mode.Top;
            cam.topHeight = 1150f;
            yield return Wait(4f);
            yield return Shot("26_karli_bolge_tepeden");
            cam.topHeight = th2;

            // Kızılırmak (Sivas): karıştırıcılı senaryo nehir vadisinde
            region = 2;
            scenario = 1;
            Launch();
            yield return Until(() => SwarmVisualizer.Main.Frame?.region == "nehir" && SwarmVisualizer.Main.Frame.t > 70f, 60f);
            var nf = SwarmVisualizer.Main.Frame;
            log.AppendLine($"Kızılırmak: bölge={nf?.region} kök={SwarmVisualizer.Main.transform.position} İHA {nf?.drones?.Length} " +
                           $"görev {nf?.m?.done}/{nf?.m?.total}");
            bannerOpen = false;
            cam.mode = SwarmCamera.Mode.Cinematic;
            Rec("ses_4_kizilirmak.wav", 8f, "Kızılırmak");
            yield return Wait(4f);
            yield return Shot("27_kizilirmak_sinematik");
            yield return Fps("Kızılırmak");
            cam.SetFollow(4);
            cam.mode = SwarmCamera.Mode.Follow;
            yield return Wait(3f);
            yield return Shot("28_kizilirmak_iha_kamerasi");
            cam.mode = SwarmCamera.Mode.Top;
            cam.topHeight = 1150f;
            yield return Wait(4f);
            yield return Shot("29_kizilirmak_tepeden");
            cam.topHeight = th2;

            // Divriği, Gökpınar Gölü ve Akdeniz kıyısı: aynı senaryo, her birinde üç görünüm
            var extra = new (int idx, string id, string shot, int follow)[]
            {
                (3, "divrigi", "30_divrigi", 2), (4, "gokpinar", "33_gokpinar", 5), (5, "deniz", "36_akdeniz", 6),
            };
            foreach (var (idx, id, shot, follow) in extra)
            {
                region = idx;
                Launch();
                yield return Until(() => SwarmVisualizer.Main.Frame?.region == id && SwarmVisualizer.Main.Frame.t > 70f, 60f);
                var ef = SwarmVisualizer.Main.Frame;
                log.AppendLine($"{SwarmRegions.Titles[idx]}: bölge={ef?.region} kök={SwarmVisualizer.Main.transform.position} İHA {ef?.drones?.Length} " +
                               $"görev {ef?.m?.done}/{ef?.m?.total}");
                bannerOpen = false;
                cam.mode = SwarmCamera.Mode.Cinematic;
                if (id == "deniz") Rec("ses_5_akdeniz.wav", 8f, "Akdeniz");
                yield return Wait(5f);
                yield return Shot(shot + "_sinematik");
                yield return Fps(SwarmRegions.ShortTitles[idx]);
                cam.SetFollow(follow);
                cam.mode = SwarmCamera.Mode.Follow;
                yield return Wait(3f);
                yield return Shot(shot + "_iha_kamerasi");
                cam.mode = SwarmCamera.Mode.Top;
                cam.topHeight = 1150f;
                yield return Wait(4f);
                yield return Shot(shot + "_tepeden");
                cam.topHeight = th2;
            }
            // Yeni tehditler (ova): hava savunma radarı, yan yana karşılaştırma, lodos ve yarı dolu bataryalar, uçuş tekrarı
            region = 0;
            scenario = Array.FindIndex(SwarmScenarios.All, s => s.Id == "radar");
            strategy = 2;
            compare = false;
            useCustom = false;
            Launch();
            yield return Until(() => SwarmVisualizer.Main.Frame?.region == "ova" && SwarmVisualizer.Main.Frame?.radars?.Length > 0 &&
                                     SwarmVisualizer.Main.Frame.t > 55f, 60f);
            bannerOpen = false;
            cam.mode = SwarmCamera.Mode.Cinematic;
            yield return Wait(4f);
            yield return Shot("40_hava_savunma_sinematik");
            cam.mode = SwarmCamera.Mode.Top;
            cam.topHeight = 1500f;
            yield return Wait(4f);
            yield return Shot("41_hava_savunma_tepeden");
            yield return Until(() => SwarmVisualizer.Main.Frame?.t > 92f, 40f);   // pusu radarı 80. saniyede açıldı
            yield return Wait(1f);
            yield return Shot("42_pusu_radari_bulundu");
            cam.topHeight = th2;
            var radarGo = GameObject.Find("Radar_0");
            if (radarGo != null)
            {
                cam.LookAt(radarGo.transform.position + new Vector3(3f, 3f, 1f), 24f, 205f, 12f);
                yield return Wait(3f);
                yield return Shot("43_radar_yakin");
            }
            var rf0 = SwarmVisualizer.Main.Frame;
            log.AppendLine($"hava savunma: radar {rf0?.radars?.Length} (açık {rf0?.radars?.Count(r => r.on == 1)}) · düşen {rf0?.m?.shot} · " +
                           $"radar kestirimi hatası {rf0?.m?.radarErr:0} m · görüş haritası {(SwarmVisualizer.Main.RadarField != null ? "var" : "YOK")} · " +
                           $"görev {rf0?.m?.done}/{rf0?.m?.total}");
            yield return Until(() => SwarmVisualizer.Main.Frame?.ctl?.finished == 1, 150f);
            var rf1 = SwarmVisualizer.Main.Frame;
            log.AppendLine($"hava savunma (dirençli) uçuş sonu: düşen {rf1?.m?.shot} · görev {rf1?.m?.done}/{rf1?.m?.total} · t={rf1?.t:0}");
            yield return Wait(1.5f);
            yield return Shot("44_hava_savunma_sonuc");
            // Uçuş tekrarı: baştan oynat, ortasına sar
            StartReplay();
            var rrx = SwarmVisualizer.Main.Receiver;
            log.AppendLine($"uçuş tekrarı: {rrx.RecCount} kare, {rrx.RecStart:0}-{rrx.RecEnd:0} s");
            replayT = rrx.RecStart + 0.45f * (rrx.RecEnd - rrx.RecStart);
            replayPlaying = true;
            cam.mode = SwarmCamera.Mode.Cinematic;
            yield return Wait(3f);
            yield return Shot("45_ucus_tekrari");
            StopReplay();

            strategy = 1;                          // yan yana: korumasız sürü radarı bilmeden şemsiyeye girer
            compare = true;
            Launch();
            yield return Until(() => SimConnected && CompareOn, 45f);
            yield return Until(() => SwarmVisualizer.Main.Frame?.t > 100f, 60f);
            bannerOpen = false;
            cam.mode = SwarmCamera.Mode.Top;
            cam.topHeight = 1500f;
            yield return Wait(3f);
            yield return Shot("46_hava_savunma_yan_yana");
            cam.topHeight = th2;
            var cl = SwarmVisualizer.Main.Frame;
            var cr = SwarmCompare.Instance != null && SwarmCompare.Instance.B != null ? SwarmCompare.Instance.B.Frame : null;
            log.AppendLine($"hava savunma yan yana: solda düşen {cl?.m?.shot}, sağda düşen {cr?.m?.shot}");
            log.AppendLine("olay akışı (hava savunma, sağdaki sürü):");
            foreach (var e in SwarmEvents.Instance.Items) log.AppendLine($"  t={e.sim:0} {e.text}");

            scenario = Array.FindIndex(SwarmScenarios.All, s => s.Id == "batarya");
            strategy = 1;
            compare = true;
            Launch();
            yield return Until(() => SimConnected && CompareOn && SwarmVisualizer.Main.Frame?.wind?.Length == 2 && SwarmVisualizer.Main.Frame.t > 60f, 60f);
            bannerOpen = false;
            cam.mode = SwarmCamera.Mode.Cinematic;
            yield return Wait(3f);
            yield return Shot("47_lodos_batarya_yan_yana");
            var bf = SwarmVisualizer.Main.Frame;
            int low = 0;
            if (bf?.drones != null)
                for (int k = 1; k < bf.drones.Length; k++) if (bf.drones[k].bat < bf.drones[low].bat) low = k;
            cam.SetFollow(low);
            cam.mode = SwarmCamera.Mode.Follow;
            yield return Wait(3f);
            yield return Shot("48_batarya_iha_kamerasi");
            yield return Until(() => SwarmVisualizer.Main.Frame?.ctl?.finished == 1 &&
                                     (SwarmCompare.Instance?.B?.Frame?.ctl?.finished ?? 1) == 1, 150f);
            yield return Wait(1.5f);
            yield return Shot("49_lodos_batarya_sonuc");
            var bl = SwarmVisualizer.Main.Frame;
            var br = SwarmCompare.Instance != null && SwarmCompare.Instance.B != null ? SwarmCompare.Instance.B.Frame : null;
            log.AppendLine($"lodos ve batarya: solda bataryası biten {bl?.m?.depleted} · eve dönen {bl?.m?.rtb}; sağda biten {br?.m?.depleted} · eve dönen {br?.m?.rtb}");

            // Konvoy koruma (dirençli): yola çıkış, pusu, HSS bastırma, radarın imhası, varış; sonra yan yana
            scenario = Array.FindIndex(SwarmScenarios.All, s => s.Id == "konvoy");
            strategy = 2;
            compare = false;
            useCustom = false;
            Launch();
            yield return Until(() => !CompareOn && SwarmHud.Convoy(SwarmVisualizer.Main.Frame) != null && SwarmVisualizer.Main.Frame.t > 45f, 60f);
            bannerOpen = false;
            var ika = GameObject.Find("IKA_1");
            if (ika != null) cam.LookAt(ika.transform.position + Vector3.up * 2f, 150f, 200f, 24f);   // konvoy, yol ve sürü birlikte
            yield return Wait(3f);
            yield return Shot("50_konvoy_sinematik");
            if (ika != null)
            {
                cam.LookAt(ika.transform.position + Vector3.up * 2f, 34f, 215f, 16f);
                yield return Wait(3f);
                yield return Shot("51_konvoy_yakin");
            }
            cam.mode = SwarmCamera.Mode.Top;
            cam.topHeight = 1400f;
            yield return Wait(3f);
            yield return Shot("52_konvoy_tepeden");
            cam.topHeight = th2;
            yield return Until(() => SwarmVisualizer.Main.Frame?.sead?.Any(s => s.st == "saldırı") == true ||
                                     SwarmVisualizer.Main.Frame?.radars?.Any(r => r.dead == 1) == true, 150f);
            var rd = GameObject.Find("Radar_0");
            var lead = GameObject.Find("IKA_1");
            if (rd != null && lead != null)
            {
                // Radar ile konvoyun arası: roller, huzme ve dalış çizgileri aynı karede
                var mid = Vector3.Lerp(rd.transform.position, lead.transform.position, 0.4f);
                cam.LookAt(mid, 620f, 160f, 58f);
            }
            yield return Wait(1.5f);
            yield return Shot("53_hss_bastirma");
            yield return Until(() => SwarmVisualizer.Main.Frame?.radars?.Any(r => r.dead == 1) == true, 40f);
            if (rd != null)
            {
                cam.LookAt(rd.transform.position + Vector3.up * 3f, 60f, 160f, 14f);
                yield return Wait(2.5f);
                yield return Shot("54_radar_imha");
            }
            yield return Until(() => SwarmVisualizer.Main.Frame?.convoy?.threats?.Length > 3 &&
                                     SwarmVisualizer.Main.Frame.convoy.threats.Any(t => t.k == "pusu" && t.m == 1), 120f);
            var pu = GameObject.Find("Tehdit_3_pusu") ?? GameObject.Find("Tehdit_1_pusu");
            if (pu != null)
            {
                cam.LookAt(pu.transform.position + Vector3.up * 2f, 70f, 120f, 22f);
                yield return Wait(2.5f);
                yield return Shot("55_pusu_isaretleme");
            }
            yield return Until(() => SwarmVisualizer.Main.Frame?.convoy?.arrived == 1 || SwarmVisualizer.Main.Frame?.ctl?.finished == 1, 200f);
            var ika2 = GameObject.Find("IKA_1");
            if (ika2 != null) cam.LookAt(ika2.transform.position + Vector3.up * 2f, 60f, 30f, 25f);
            yield return Wait(2f);
            yield return Shot("56_konvoy_vardi");
            var kvf = SwarmVisualizer.Main.Frame;
            log.AppendLine($"konvoy (dirençli): vardı {kvf?.convoy?.arrived} · kaybedilen araç {kvf?.convoy?.lost} · " +
                           $"bulunan tehdit {kvf?.convoy?.threats?.Count(t => t.f == 1)}/{kvf?.convoy?.threats?.Length} · " +
                           $"radar imha {kvf?.radars?.Count(r => r.dead == 1)} · t={kvf?.t:0}");
            log.AppendLine("olay akışı (konvoy):");
            foreach (var e in SwarmEvents.Instance.Items) log.AppendLine($"  t={e.sim:0} {e.text}");

            strategy = 1;                          // yan yana: korumasız sürü karıştırmada yolu taramadan "temiz" der
            compare = true;
            Launch();
            yield return Until(() => SimConnected && CompareOn && SwarmVisualizer.Main.Frame?.t > 150f, 90f);
            bannerOpen = false;
            cam.mode = SwarmCamera.Mode.Top;
            cam.topHeight = 1400f;
            yield return Wait(3f);
            yield return Shot("57_konvoy_yan_yana");
            cam.topHeight = th2;
            var kl = SwarmVisualizer.Main.Frame;
            var kr = SwarmCompare.Instance != null && SwarmCompare.Instance.B != null ? SwarmCompare.Instance.B.Frame : null;
            log.AppendLine($"konvoy yan yana (t={kl?.t:0}): solda kaybedilen araç {kl?.convoy?.lost}, sağda {kr?.convoy?.lost}");
            compare = false;
            strategy = 2;
            scenario = 1;

            region = 0;
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
