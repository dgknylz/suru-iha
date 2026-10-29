using UnityEngine;

namespace SuruIHA
{
    // Uçuş tekrarı: alıcı canlı uçuşun karelerini saklar (SwarmReceiver.Record). "Tekrar izle" uçuşu baştan oynatır;
    // alttaki zaman çubuğuyla ileri geri sarılır, durdurulur, yavaşlatılır ya da hızlandırılır. Tekrar sırasında
    // Python'dan gelen kareler ekrana uygulanmaz (simülasyon arkada sürer ya da bekler); "Canlıya dön" kaldığı yere döner.
    // Yan yana karşılaştırmada iki sürü aynı simülasyon saniyesinde birlikte oynatılır.
    public partial class SwarmMenu
    {
        bool replayOn, replayPlaying, replayDrag;
        float replayT;
        int replaySpeed = 1;
        int replayA = -1, replayB = -1;
        static readonly float[] ReplaySpeeds = { 1f, 3f, 6f, 12f };
        static readonly string[] ReplaySpeedNames = { "1×", "3×", "6×", "12×" };

        public bool ReplayOn => replayOn;

        void ToggleReplay()
        {
            if (replayOn) StopReplay();
            else StartReplay();
        }

        void StartReplay()
        {
            var rx = SwarmVisualizer.Main != null ? SwarmVisualizer.Main.Receiver : null;
            if (rx == null || rx.RecCount < 10) return;
            replayOn = replayPlaying = true;
            replayT = rx.RecStart;
            replayA = replayB = -1;
            SwarmReceiver.Replaying = true;
            SnapAll();
        }

        void StopReplay()
        {
            replayOn = replayPlaying = replayDrag = false;
            SwarmReceiver.Replaying = false;
            SnapAll();
        }

        static void SnapAll()
        {
            var v = SwarmVisualizer.Main;
            if (v != null) v.Snap();
            var c = SwarmCompare.Instance;
            if (c != null && c.B != null) c.B.Snap();
        }

        void UpdateReplay()
        {
            if (!replayOn) return;
            var main = SwarmVisualizer.Main;
            var rx = main != null ? main.Receiver : null;
            if (rx == null || rx.RecCount < 2) { StopReplay(); return; }
            if (replayPlaying && !replayDrag) replayT += Time.unscaledDeltaTime * ReplaySpeeds[replaySpeed];
            if (replayT >= rx.RecEnd)
            {
                replayT = rx.RecEnd;
                replayPlaying = false;
            }
            replayT = Mathf.Clamp(replayT, rx.RecStart, rx.RecEnd);
            FeedReplay(main, ref replayA);
            var c = SwarmCompare.Instance;
            if (c != null && c.Active && c.B != null) FeedReplay(c.B, ref replayB);
        }

        void FeedReplay(SwarmVisualizer v, ref int last)
        {
            var rx = v.Receiver;
            if (rx == null || rx.RecCount == 0) return;
            int k = rx.RecIndexAt(replayT);
            if (k < 0 || k == last) return;
            bool jump = last < 0 || Mathf.Abs(k - last) > 4;     // sarma: İHA'lar kayarak değil, doğrudan yerine geçsin
            last = k;
            var f = rx.RecFrame(k);
            if (f == null) return;
            rx.Feed(f);
            if (jump) v.Snap();
        }

        // Alttaki zaman çubuğu: oynat/durdur, hız, sarma çubuğu, süre, "Canlıya dön"
        float DrawReplayBar(float tbTop)
        {
            var rx = SwarmVisualizer.Main != null ? SwarmVisualizer.Main.Receiver : null;
            if (rx == null || rx.RecCount < 2) return tbTop;
            const float h = 74f;
            float w = Mathf.Min(1280f, Ui.W - 120f), x = (Ui.W - w) / 2f, y = tbTop - 12f - h;
            Ui.Panel(Ui.R(x, y, w, h), 16, 0.94f);
            Ui.Chip(x + 18, y + 12, "UÇUŞ TEKRARI", Ui.Violet, 11.5f);
            Ui.Label(Ui.R(x + 18, y + 36, 200, 24), $"{replayT:0} s / {rx.RecEnd:0} s", 16, Ui.Ink, true);

            float bx = x + 190f;
            if (Ui.Button(Ui.R(bx, y + 16, 110, 42), replayPlaying ? "Durdur" : "Oynat", Ui.Kind.Primary, size: 16))
            {
                if (!replayPlaying && replayT >= rx.RecEnd - 0.05f) replayT = rx.RecStart;   // sondaysa baştan
                replayPlaying = !replayPlaying;
            }
            bx += 120f;
            for (int i = 0; i < ReplaySpeeds.Length; i++)
            {
                var r = Ui.R(bx + i * 62f, y + 16, 56, 42);
                if (r.Contains(Event.current.mousePosition)) tip = "Tekrar hızı: simülasyon saniyesi / gerçek saniye";
                if (Ui.Button(r, ReplaySpeedNames[i], Ui.Kind.Normal, i == replaySpeed, 15)) replaySpeed = i;
            }
            bx += ReplaySpeeds.Length * 62f + 18f;

            // Sarma çubuğu: tıkla ya da sürükle
            float liveW = 150f;
            float sw = x + w - 18f - liveW - 18f - bx;
            var track = Ui.R(bx, y + 31, sw, 12);
            Ui.Fill(track, new Color(1f, 1f, 1f, 0.1f), 6);
            float span = Mathf.Max(rx.RecEnd - rx.RecStart, 0.1f);
            float u = Mathf.Clamp01((replayT - rx.RecStart) / span);
            Ui.Fill(Ui.R(bx, y + 31, sw * u, 12), Ui.Violet, 6);
            Ui.Dot(new Vector2((bx + sw * u) * Ui.S, (y + 37) * Ui.S), 9f, Color.white);
            // Önemli anlar: görevlerin bittiği saniye (yeşil çizgi)
            var ev = SwarmEvents.Instance;
            if (ev != null && ev.MissionDoneAt > rx.RecStart)
            {
                float m = Mathf.Clamp01((ev.MissionDoneAt - rx.RecStart) / span);
                Ui.Fill(Ui.R(bx + sw * m - 1.5f, y + 25, 3, 24), Ui.Good, 1.5f);
            }
            Ui.Label(Ui.R(bx, y + 48, 200, 20), $"{rx.RecStart:0} s", 12.5f, Ui.Ink3);
            Ui.Label(Ui.R(bx + sw - 200, y + 48, 200, 20), "son", 12.5f, Ui.Ink3, false, TextAnchor.UpperRight);
            var e = Event.current;
            var hit = Ui.R(bx - 8, y + 18, sw + 16, 38);
            if (hit.Contains(e.mousePosition))
            {
                tip = "Tıkla ya da sürükle: o ana git";
                if (e.type == EventType.MouseDown && e.button == 0) { replayDrag = true; e.Use(); }
            }
            if (replayDrag)
            {
                float mx = e.mousePosition.x / Ui.S;
                replayT = rx.RecStart + Mathf.Clamp01((mx - bx) / sw) * span;
                if (e.type == EventType.MouseUp || e.rawType == EventType.MouseUp) replayDrag = false;
            }
            Ui.Block(hit);

            if (Ui.Button(Ui.R(x + w - 18f - liveW, y + 16, liveW, 42), "Canlıya dön", Ui.Kind.Ghost, size: 15)) StopReplay();
            return y;
        }
    }
}
