using System.Collections.Generic;
using UnityEngine;

namespace SuruIHA
{
    // Arayüzün ortak parçaları: ölçek, yazı tipi, renkler, yuvarlak köşeli paneller ve düğmeler.
    // Her şey 1920x1080 referansına göre çizilir ve ekran boyutuna göre ölçeklenir.
    public static class Ui
    {
        public static readonly Color Ink = new Color(0.94f, 0.96f, 0.98f);
        public static readonly Color Ink2 = new Color(0.72f, 0.77f, 0.82f);
        public static readonly Color Ink3 = new Color(0.6f, 0.65f, 0.7f);
        public static readonly Color PanelBg = new Color(0.035f, 0.05f, 0.066f, 0.9f);
        public static readonly Color Line = new Color(1f, 1f, 1f, 0.1f);
        public static readonly Color Accent = new Color(0.33f, 0.78f, 1f);
        public static readonly Color Good = new Color(0.27f, 0.88f, 0.56f);
        public static readonly Color Warn = new Color(1f, 0.72f, 0.26f);
        public static readonly Color Bad = new Color(1f, 0.4f, 0.34f);
        public static readonly Color Violet = new Color(0.78f, 0.45f, 1f);
        public static readonly Color Pink = new Color(1f, 0.42f, 0.78f);
        public static readonly Color Cyan = new Color(0.25f, 0.88f, 1f);

        // Ekranı kaplayan bir menü açık mı (açıksa kamera ve kısayollar susar)
        public static bool Modal;
        static int pointerFrame = -10;
        // Fare son karede bir panelin üstündeydi: kamera fareyle dönmesin
        public static bool PointerBlocked => Modal || Time.frameCount - pointerFrame <= 1;

        public static float S => Mathf.Clamp(Mathf.Min(Screen.width / 1920f, Screen.height / 1080f), 0.5f, 3f);
        public static float W => Screen.width / S;     // referans birimiyle ekran genişliği
        public static float H => Screen.height / S;

        static Font font;
        static readonly Dictionary<int, GUIStyle> styles = new Dictionary<int, GUIStyle>();
        static Texture2D gradient, play;

        // Tek yazı tipi; kalınlık FontStyle ile verilir. (Unity "Segoe UI Semibold" adını bulamıyor: o yazı tipiyle
        // her karede hata yazıp yavaşlıyor, kalın yazılar da bir önceki yazının görüntüsünü gösteriyordu.)
        static void Fonts()
        {
            if (font == null) font = Font.CreateDynamicFontFromOSFont(new[] { "Segoe UI", "Arial" }, 16);
        }

        // Yazı biçimi (boyut referans birimiyle verilir)
        public static GUIStyle Style(float size, Color color, bool isBold = false, TextAnchor anchor = TextAnchor.UpperLeft, bool wrap = true)
        {
            Fonts();
            int px = Mathf.Max(8, Mathf.RoundToInt(size * S));
            int key = px * 64 + (isBold ? 1 : 0) * 32 + (int)anchor * 2 + (wrap ? 1 : 0);
            if (!styles.TryGetValue(key, out var st))
            {
                st = new GUIStyle
                {
                    font = font, fontSize = px, fontStyle = isBold ? FontStyle.Bold : FontStyle.Normal,
                    alignment = anchor, wordWrap = wrap, richText = true,
                    // Satır kaydırılan yazı alttan kırpılmasın (yükseklik ölçümü bir satır eksik çıkabiliyor);
                    // tek satırlık yazı (düğmeler) kutusundan taşmasın
                    clipping = wrap ? TextClipping.Overflow : TextClipping.Clip,
                };
                styles[key] = st;
            }
            st.normal.textColor = color;
            return st;
        }

        // Referans birimindeki dikdörtgeni ekran pikseline çevir
        public static Rect R(float x, float y, float w, float h) => new Rect(x * S, y * S, w * S, h * S);

        public static void Fill(Rect r, Color c, float radius = 0f) =>
            GUI.DrawTexture(r, Texture2D.whiteTexture, ScaleMode.StretchToFill, true, 0f, c, 0f, radius * S);

        public static void Outline(Rect r, Color c, float width = 1f, float radius = 0f) =>
            GUI.DrawTexture(r, Texture2D.whiteTexture, ScaleMode.StretchToFill, true, 0f, c, Mathf.Max(1f, width * S), radius * S);

        public static void Dot(Vector2 center, float radius, Color c) =>
            Fill(new Rect(center.x - radius * S, center.y - radius * S, 2 * radius * S, 2 * radius * S), c, radius);

        // İçi boş halka (grafiklerde ikinci işaret türü: renk körlüğünde de ayırt edilsin)
        public static void Ring(Vector2 center, float radius, Color c, float width = 2.5f)
        {
            var r = new Rect(center.x - radius * S, center.y - radius * S, 2 * radius * S, 2 * radius * S);
            Fill(r, new Color(0.035f, 0.05f, 0.066f, 1f), radius);
            Outline(r, c, width, radius);
        }

        public static void Panel(Rect r, float radius = 14f, float alpha = 1f)
        {
            var bg = PanelBg;
            bg.a *= alpha;
            Fill(r, bg, radius);
            Outline(r, Line, 1f, radius);
            Block(r);
        }

        // Bu alan fareyi yakalar (altındaki 3D sahne fareyle dönmez)
        public static void Block(Rect r)
        {
            if (r.Contains(Event.current.mousePosition)) pointerFrame = Time.frameCount;
        }

        public static void Label(Rect r, string text, float size, Color color, bool isBold = false, TextAnchor anchor = TextAnchor.UpperLeft) =>
            GUI.Label(r, text, Style(size, color, isBold, anchor));

        public static float TextHeight(string text, float size, float width, bool isBold = false) =>
            Style(size, Ink, isBold).CalcHeight(new GUIContent(text), width * S) / S;

        public static float TextWidth(string text, float size, bool isBold = false) =>
            Style(size, Ink, isBold, TextAnchor.UpperLeft, false).CalcSize(new GUIContent(text)).x / S;

        // Soldan sağa kararan geçiş (menünün arkasındaki 3D sahne okunur kalsın)
        public static void Gradient(Rect r, Color c)
        {
            if (gradient == null)
            {
                gradient = new Texture2D(256, 1, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
                for (int i = 0; i < 256; i++)
                {
                    float t = i / 255f;
                    gradient.SetPixel(i, 0, new Color(1, 1, 1, Mathf.Clamp01(1.25f - 1.25f * t * t)));
                }
                gradient.Apply();
            }
            GUI.DrawTexture(r, gradient, ScaleMode.StretchToFill, true, 0f, c, 0f, 0f);
        }

        // Oynat simgesi (yazı tipinde ▶ olmayabilir; üçgeni kendimiz çizeriz)
        public static void PlayIcon(Rect r, Color c)
        {
            if (play == null)
            {
                const int n = 64;
                play = new Texture2D(n, n, TextureFormat.RGBA32, false);
                for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float fy = Mathf.Abs(y - (n - 1) / 2f) / (n / 2f);
                    float edge = 1f - fy;                       // üçgenin bu satırdaki genişliği
                    float a = Mathf.Clamp01((edge * n - x) * 0.7f) * Mathf.Clamp01((x + 1) * 0.7f);
                    play.SetPixel(x, y, new Color(1, 1, 1, a));
                }
                play.Apply();
            }
            GUI.DrawTexture(r, play, ScaleMode.ScaleToFit, true, 0f, c, 0f, 0f);
        }

        public enum Kind { Primary, Normal, Ghost, Danger }

        // Düğme: üstüne gelince açılır, seçiliyse vurgulanır. Tıklanınca true döner.
        public static bool Button(Rect r, string text, Kind kind = Kind.Normal, bool selected = false, float size = 17f,
                                  bool enabled = true, string sub = null, bool icon = false)
        {
            bool hover = enabled && r.Contains(Event.current.mousePosition);
            Block(r);
            Color fill, border, ink;
            switch (kind)
            {
                case Kind.Primary:
                    fill = hover ? new Color(0.45f, 0.84f, 1f) : Accent;
                    border = fill;
                    ink = new Color(0.02f, 0.06f, 0.1f);
                    break;
                case Kind.Danger:
                    fill = hover ? new Color(0.5f, 0.12f, 0.1f, 0.95f) : new Color(0.25f, 0.07f, 0.07f, 0.9f);
                    border = new Color(1f, 0.4f, 0.34f, 0.6f);
                    ink = Ink;
                    break;
                case Kind.Ghost:
                    fill = hover ? new Color(1f, 1f, 1f, 0.1f) : new Color(1f, 1f, 1f, 0f);
                    border = new Color(1f, 1f, 1f, hover ? 0.25f : 0.14f);
                    ink = Ink2;
                    break;
                default:
                    fill = selected ? new Color(0.33f, 0.78f, 1f, 0.22f)
                         : hover ? new Color(0.16f, 0.21f, 0.26f, 0.96f) : new Color(0.09f, 0.12f, 0.15f, 0.92f);
                    border = selected ? Accent : new Color(1f, 1f, 1f, hover ? 0.28f : 0.12f);
                    ink = selected ? Ink : Ink;
                    break;
            }
            if (!enabled) { fill.a *= 0.4f; border.a *= 0.4f; ink = Ink3; }
            float rad = Mathf.Min(10f, r.height / S / 2f);
            Fill(r, fill, rad);
            Outline(r, border, selected ? 2f : 1f, rad);
            float pad = Mathf.Min(18f * S, r.width * 0.16f);   // küçük düğmede (×, +) yazıya yer kalsın
            var tr = new Rect(r.x + pad, r.y, r.width - 2 * pad, r.height);
            if (icon)
            {
                float ih = r.height * 0.34f;
                PlayIcon(new Rect(r.x + pad, r.y + (r.height - ih) / 2f, ih * 0.9f, ih), ink);
                tr.x += ih + 12f * S;
                tr.width -= ih + 12f * S;
            }
            var anchor = kind == Kind.Primary || icon || sub != null ? TextAnchor.MiddleLeft : TextAnchor.MiddleCenter;
            if (sub != null)
            {
                var top = new Rect(tr.x, r.y + r.height * 0.14f, tr.width, r.height * 0.46f);
                var bot = new Rect(tr.x, r.y + r.height * 0.52f, tr.width, r.height * 0.4f);
                GUI.Label(top, text, Style(size, ink, true, TextAnchor.MiddleLeft, false));
                var subInk = kind == Kind.Primary ? new Color(0.05f, 0.15f, 0.22f) : Ink2;
                GUI.Label(bot, sub, Style(Mathf.Max(13.5f, size * 0.76f), subInk, false, TextAnchor.MiddleLeft, false));
            }
            else
                GUI.Label(tr, text, Style(size, ink, kind == Kind.Primary || selected, anchor, false));
            return enabled && GUI.Button(r, GUIContent.none, GUIStyle.none);
        }

        // Küçük renkli etiket (senaryo türü gibi)
        public static float Chip(float x, float y, string text, Color c, float size = 12f)
        {
            float w = TextWidth(text, size, true) + 20f;
            var r = R(x, y, w, size + 12f);
            Fill(r, new Color(c.r, c.g, c.b, 0.16f), (size + 12f) / 2f);
            Label(r, text, size, c, true, TextAnchor.MiddleCenter);
            return w;
        }

        // Üst üste binen iki satırlık bilgi kutusu (büyük sayı + açıklama)
        public static void Stat(Rect r, string big, string caption, Color c, float bigSize = 30f)
        {
            Fill(r, new Color(1f, 1f, 1f, 0.05f), 12f);
            float pad = 14f * S;
            GUI.Label(new Rect(r.x + pad, r.y + 8f * S, r.width - 2 * pad, (bigSize + 8f) * S), big, Style(bigSize, c, true, TextAnchor.UpperLeft, false));
            GUI.Label(new Rect(r.x + pad, r.y + (bigSize + 14f) * S, r.width - 2 * pad, r.height - (bigSize + 18f) * S), caption, Style(13.5f, Ink2));
        }
    }
}
