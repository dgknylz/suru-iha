using System.Collections.Generic;
using UnityEngine;

namespace SuruIHA
{
    // Sol üstteki bilgi paneli: senaryo, mimari, uçuş evresi, görev ilerlemesi ve elektronik harp durumu.
    // H ile gizlenir. Ayrıntılar (bağlantı, düzen, FPS...) paneldeki düğmeyle açılır.
    // Kısayol tuşları da burada işlenir (menü açıkken susar).
    public class SwarmHud : MonoBehaviour
    {
        public SwarmVisualizer visualizer;
        public SwarmCamera cam;
        public bool visible = true;
        public bool details;

        static readonly string[] Phases = { "kalkis", "intikal", "gorev", "toplanma", "donus", "inis" };

        static string PhaseName(string p) => SwarmScenarios.PhaseTitle(p);

        void Start()
        {
            if (visualizer == null) visualizer = SwarmVisualizer.Main;
            if (cam == null) cam = FindAnyObjectByType<SwarmCamera>();
        }

        void Update()
        {
            if (Ui.Modal) return;   // menü açık: kısayollar susar
            if (SwarmInput.Down(SwarmInput.K.H)) visible = !visible;
            if (visualizer == null) return;
            if (SwarmInput.Down(SwarmInput.K.L))
            {
                // Bağlantılar: kapalı → yalnızca sorunlu → hepsi → kapalı
                if (!visualizer.showLinks) { visualizer.showLinks = true; visualizer.onlyWeakLinks = true; }
                else if (visualizer.onlyWeakLinks) visualizer.onlyWeakLinks = false;
                else visualizer.showLinks = false;
            }
            if (SwarmInput.Down(SwarmInput.K.G)) visualizer.showEstimates = !visualizer.showEstimates;
            if (SwarmInput.Down(SwarmInput.K.J)) visualizer.showJamMap = !visualizer.showJamMap;
            if (SwarmInput.Down(SwarmInput.K.B)) visualizer.showBeacons = !visualizer.showBeacons;
            if (SwarmInput.Down(SwarmInput.K.P)) visualizer.showPlans = !visualizer.showPlans;
            // Grafik kalitesi: Yüksek (hacimsel sis, bulut gölgesi) -> Dengeli -> Performans
            if (SwarmInput.Down(SwarmInput.K.K))
            {
                int n = QualitySettings.names.Length;
                QualitySettings.SetQualityLevel((QualitySettings.GetQualityLevel() + 1) % n, true);
            }

            // Senaryo komutları (Python yeniden başlatılmadan değişir)
            var rx = visualizer.Receiver;
            if (rx == null) return;
            if (SwarmInput.Down(SwarmInput.K.F1)) rx.SendCommand("{\"cmd\":\"strategy\",\"value\":\"centralized\"}");
            if (SwarmInput.Down(SwarmInput.K.F2)) rx.SendCommand("{\"cmd\":\"strategy\",\"value\":\"decentralized\"}");
            if (SwarmInput.Down(SwarmInput.K.F3)) rx.SendCommand("{\"cmd\":\"strategy\",\"value\":\"resilient\"}");
            if (SwarmInput.Down(SwarmInput.K.F4)) rx.SendCommand("{\"cmd\":\"planner\"}");
            if (SwarmInput.Down(SwarmInput.K.Y)) rx.SendCommand("{\"cmd\":\"popup\"}");
            if (SwarmInput.Down(SwarmInput.K.M)) rx.SendCommand("{\"cmd\":\"jammer_mode\"}");
            if (SwarmInput.Down(SwarmInput.K.U)) rx.SendCommand("{\"cmd\":\"gps_spoof\"}");
            if (SwarmInput.Down(SwarmInput.K.Plus)) rx.SendCommand("{\"cmd\":\"jammer\",\"step\":1}");
            if (SwarmInput.Down(SwarmInput.K.Minus)) rx.SendCommand("{\"cmd\":\"jammer\",\"step\":-1}");
            if (SwarmInput.Down(SwarmInput.K.X)) rx.SendCommand("{\"cmd\":\"spoof\"}");
            if (SwarmInput.Down(SwarmInput.K.N)) rx.SendCommand("{\"cmd\":\"restart\"}");
            if (SwarmInput.Down(SwarmInput.K.V)) rx.SendCommand("{\"cmd\":\"formation\"}");
            if (SwarmInput.Down(SwarmInput.K.Z)) rx.SendCommand("{\"cmd\":\"fail\"}");
        }

        readonly List<(string k, string v, Color c)> rows = new List<(string, string, Color)>();

        void Rows(SwarmFrame f)
        {
            rows.Clear();
            var m = f.m;
            rows.Add(("GPS'i kesilen İHA", $"{m.gpsLost}", m.gpsLost > 0 ? Ui.Warn : Ui.Ink));
            rows.Add(("Yanlış \"bitti\"", $"{m.falseDone}", m.falseDone > 0 ? Ui.Bad : Ui.Ink));
            rows.Add(("Paket iletimi", $"%{m.pdr * 100:0}", Ui.Ink));
            if (f.jammers != null && f.jammers.Length > 0)
            {
                var j0 = f.jammers[0];
                bool moving = j0.v != null && j0.v.Length > 1 && (j0.v[0] * j0.v[0] + j0.v[1] * j0.v[1]) > 0.5f;
                string kind = (f.jammers.Length > 1 ? $"{f.jammers.Length} adet · " : "") +
                              (j0.band == "nokta" ? "nokta" : "geniş bant") + (moving ? " · hareketli" : "");
                rows.Add(("Karıştırıcı", $"{j0.pw:0} dBm · {kind}", Ui.Ink));
                rows.Add(("Karıştırıcının yeri", m.jamErr >= 0 ? $"bulundu · hata {m.jamErr:0} m" : "aranıyor…",
                          m.jamErr >= 0 && m.jamErr < 80 ? Ui.Good : Ui.Ink2));
                if (f.fhss == 1) rows.Add(("Frekans atlama", "açık", Ui.Ink));
            }
            else rows.Add(("Karıştırıcı", "kapalı", Ui.Ink2));
            if (f.spoofers != null && f.spoofers.Length > 0)
                rows.Add(("GPS aldatma", $"kandırılan {m.spoofed} · fark eden {m.spoofSeen}", m.spoofed > 0 ? Ui.Pink : Ui.Ink));
            if (f.ctl != null && f.ctl.spoof > 0)
            {
                string liar = f.ctl.spoofMode == "sneaky" ? "sinsi" : "saf";
                rows.Add(("Saldırgan İHA", $"%{f.ctl.spoof * 100:0} {liar}" + (m.liars >= 0 ? $" · %{m.liars * 100:0} dışlandı" : ""), Ui.Violet));
            }
            if (!details) return;
            rows.Add(("Yeni hedef · yeniden plan", $"{m.popups} · {m.reassign}", Ui.Ink));
            rows.Add(("Ortalama konum hatası", $"{m.locErr:0.0} m", Ui.Ink));
            rows.Add(("Sürü bağlantısı", $"%{m.conn * 100:0}", Ui.Ink));
            rows.Add(("Düzen", $"{f.formation} · hata {m.formErr:0.0} m", Ui.Ink));
            rows.Add(("Uçan İHA · röle", $"{m.alive} · {m.relays}", Ui.Ink));
            rows.Add(("Gereksiz tekrar ziyaret", $"{m.redundant}", Ui.Ink));
            if (f.ctl != null) rows.Add(("Harita", $"#{f.ctl.seed}", Ui.Ink));
            string camName = cam == null ? "-" : cam.mode switch
            {
                SwarmCamera.Mode.Cinematic => "sinematik",
                SwarmCamera.Mode.Orbit => "serbest",
                SwarmCamera.Mode.Follow => $"İHA-{cam.FollowIndex + 1} (TPP)",
                _ => "taktik",
            };
            rows.Add(("Kamera", camName, Ui.Ink));
            string[] qn = { "Yüksek", "Dengeli", "Performans" };
            int ql = QualitySettings.GetQualityLevel();
            rows.Add(("Grafik [K]", $"{(ql < qn.Length ? qn[ql] : QualitySettings.names[ql])} · {1f / Mathf.Max(Time.smoothDeltaTime, 1e-4f):0} FPS", Ui.Ink));
        }

        void OnGUI()
        {
            if (!visible || visualizer == null) return;
            var menu = SwarmMenu.Instance;
            if (menu != null && menu.HidesHud) return;
            var rx = visualizer.Receiver;
            var f = visualizer.Frame;
            const float x = 20f, y0 = 20f, w = 392f, pad = 20f;
            float iw = w - 2 * pad;
            if (rx == null || !rx.Connected || f == null || f.m == null)
            {
                if (menu != null) return;   // menü kendi durum kutusunu gösterir
                Ui.Panel(Ui.R(x, y0, w, 96), 14);
                Ui.Label(Ui.R(x + pad, y0 + 16, iw, 26), "Python bağlantısı bekleniyor…", 18, Ui.Ink, true);
                Ui.Label(Ui.R(x + pad, y0 + 48, iw, 30), "Terminalde çalıştır: <color=#8fd3ff>python run_live.py</color>", 15, Ui.Ink2);
                return;
            }
            Rows(f);
            const float rowH = 25f;
            float h = 300f + rows.Count * rowH + 40f;
            Ui.Panel(Ui.R(x, y0, w, h), 16, 0.92f);
            float y = y0 + 18f;
            Ui.Label(Ui.R(x + pad, y, iw, 18), "SENARYO", 11.5f, Ui.Ink3, true);
            y += 18f;
            Ui.Label(Ui.R(x + pad, y, iw, 30), menu != null && menu.RunningTitle != null ? menu.RunningTitle : "Canlı simülasyon", 21, Ui.Ink, true);
            y += 32f;
            Ui.Label(Ui.R(x + pad, y, iw, 22), SwarmScenarios.StrategyTitle(f.strategy), 15.5f, Ui.Accent, true);
            y += 22f;
            Ui.Label(Ui.R(x + pad, y, iw, 22), SwarmScenarios.PlannerTitle(f.planner, f.strategy), 14.5f, Ui.Ink2);
            y += 34f;

            // Uçuş evresi şeridi: kalkış → intikal → görev → toplanma → dönüş → iniş
            int idx = f.phase == "indi" ? Phases.Length : System.Array.IndexOf(Phases, f.phase);
            float segW = (iw - 5 * 4f) / Phases.Length;
            for (int i = 0; i < Phases.Length; i++)
            {
                var c = i < idx ? new Color(Ui.Accent.r, Ui.Accent.g, Ui.Accent.b, 0.45f) : i == idx ? Ui.Accent : new Color(1f, 1f, 1f, 0.12f);
                Ui.Fill(Ui.R(x + pad + i * (segW + 4f), y, segW, 6), c, 3);
            }
            y += 12f;
            Ui.Label(Ui.R(x + pad, y, iw, 22), $"Evre: <b>{PhaseName(f.phase)}</b>", 14.5f, Ui.Ink2);
            y += 32f;

            var m = f.m;
            float tw = (iw - 16f) / 3f;
            Ui.Stat(Ui.R(x + pad, y, tw, 78), $"{m.done}/{m.total}", "hedef tamam", m.done == m.total && m.total > 0 ? Ui.Good : Ui.Ink, 24);
            Ui.Stat(Ui.R(x + pad + tw + 8, y, tw, 78), $"{m.score * 100:0}", "görev puanı", Ui.Accent, 24);
            Ui.Stat(Ui.R(x + pad + 2 * (tw + 8), y, tw, 78), $"{f.t:0} s", "süre", Ui.Ink, 24);
            y += 78f;
            var bar = Ui.R(x + pad, y + 8, iw, 5);
            Ui.Fill(bar, new Color(1f, 1f, 1f, 0.1f), 2.5f);
            Ui.Fill(Ui.R(x + pad, y + 8, iw * (m.total > 0 ? m.done / (float)m.total : 0f), 5), Ui.Good, 2.5f);
            y += 26f;

            foreach (var (k, v, c) in rows)
            {
                Ui.Label(Ui.R(x + pad, y, iw * 0.5f, rowH), k, 14.5f, Ui.Ink2);
                Ui.Label(Ui.R(x + pad + iw * 0.38f, y, iw * 0.62f, rowH), v, 14.5f, c, true, TextAnchor.UpperRight);
                y += rowH;
            }
            y += 8f;
            if (Ui.Button(Ui.R(x + pad, y, 150, 30), details ? "Daha az" : "Ayrıntılar", Ui.Kind.Ghost, size: 13.5f)) details = !details;
            if (f.ctl != null && f.ctl.missionDone == 1 && f.ctl.finished != 1)
                Ui.Label(Ui.R(x + pad + 160, y + 4, iw - 160, 24), "Görevler bitti, sürü dönüyor", 13.5f, Ui.Good, true);
        }
    }
}
