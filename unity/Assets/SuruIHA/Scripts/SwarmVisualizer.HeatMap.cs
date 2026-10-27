using UnityEngine;
using UnityEngine.Rendering;

namespace SuruIHA
{
    // Karıştırma ısı haritası: Python'un İHA'larla aynı fizikle (yol kaybı + arazi gölgesi) hesapladığı
    // karıştırma gücü, araziye serilmiş yarı saydam bir örtü olarak çizilir. Tek renk tonu: açık kırmızı
    // zayıf, koyu kırmızı güçlü karıştırma. İnce soluk çizgi: İHA karıştırmayı fark eder; kalın parlak çizgi:
    // 60 m'deki komşusuyla bağlantının paketlerinin yarısı kaybolur. Harita kenarda yumuşakça söner. Tepelerin arkasındaki açık renkli boşluklar
    // arazi gölgesidir.
    public partial class SwarmVisualizer
    {
        const int FieldUp = 6;       // dokuda her nokta aralığına düşen piksel (eş güç çizgileri ince ve düzgün çıksın)
        const int FieldSub = 2;      // örtüde her nokta aralığına düşen köşe (arazinin kıvrımına otursun)
        const float FieldLift = 1.5f;

        // Son gelen harita (renk skalası kartı eşik değerlerini buradan okur); karıştırıcı yoksa boş
        public JamFieldState Field { get; private set; }

        // Son biten uçuşun raporu ("Uçuş raporu" sekmesi): yeni uçuşun raporu gelene kadar kalır. O uçuşun son
        // karesi (hedefler, karıştırıcılar, metrikler) ve ısı haritası da birlikte saklanır.
        public FlightReport Report { get; private set; }
        public SwarmFrame ReportFrame { get; private set; }
        public JamFieldState ReportField { get; private set; }
        public int ReportVersion { get; private set; }

        void ApplyReport(SwarmFrame f)
        {
            var r = f.report;
            if (r == null || r.drones == null || r.drones.Length == 0) return;
            // Aynı rapor ara ara yeniden gelir: aynı uçuşsa yenisi sayılmaz
            if (Report != null && ReportFrame?.ctl != null && f.ctl != null && f.ctl.seed == ReportFrame.ctl.seed &&
                Mathf.Approximately(r.t, Report.t) && f.strategy == ReportFrame.strategy) return;
            Report = r;
            ReportFrame = f;
            ReportField = Field;
            ReportVersion++;
        }

        // Yerel (x doğu, z kuzey) noktadaki arazi yüksekliği (rapor haritasının gölgelemesi için)
        public float GroundHeight(float x, float z) => HeatGround(Terrain.activeTerrains, x, z);

        // Verilen bölgedeki yerel noktanın arazi yüksekliği; kök o bölgede olmasa da ("Kendi senaryon" haritası)
        public float RegionGroundHeight(Vector3 regionOrigin, float x, float z)
        {
            var w = new Vector3(regionOrigin.x + x, 0f, regionOrigin.z + z);
            foreach (var t in Terrain.activeTerrains)
                if (Covers(t, w)) return t.SampleHeight(w) + t.transform.position.y - transform.position.y;
            return 0f;
        }

        GameObject fieldGo;
        Mesh fieldMesh;
        Material fieldMat;
        Texture2D fieldTex, fieldEmit;
        string fieldQ, fieldGeom;
        Vector3 fieldBuiltPos;
        float[] fieldVals;
        Color32[] fieldPx, fieldEmitPx;

        void ApplyHeatMap(SwarmFrame f)
        {
            var F = f.jamField;
            if (F != null && F.nx > 1 && F.ny > 1 && !string.IsNullOrEmpty(F.q) && F.q != fieldQ)
            {
                byte[] q = null;
                try { q = System.Convert.FromBase64String(F.q); }
                catch (System.FormatException) { }
                if (q != null && q.Length == F.nx * F.ny)
                {
                    fieldQ = F.q;
                    Field = F;
                    string geom = $"{F.x0}|{F.y0}|{F.step}|{F.nx}|{F.ny}";
                    if (geom != fieldGeom || (transform.position - fieldBuiltPos).sqrMagnitude > 0.01f)
                    {
                        BuildHeatMesh(F);
                        fieldGeom = geom;
                    }
                    PaintHeatMap(F, q);
                }
            }
            if (f.jammers == null || f.jammers.Length == 0)
            {
                Field = null;      // karıştırıcı kapatıldı; açılınca aynı harita gelse de yeniden çizilsin
                fieldQ = null;
            }
            // Kök zemine sonradan oturtulduysa ya da başka bölgeye taşındıysa örtü yeniden serilir
            if (Field != null && fieldGo != null && (transform.position - fieldBuiltPos).sqrMagnitude > 0.01f) BuildHeatMesh(Field);
            if (fieldGo != null) fieldGo.SetActive(showHeatMap && Field != null);
        }

        void BuildHeatMesh(JamFieldState F)
        {
            if (fieldGo == null)
            {
                fieldGo = new GameObject("KaristirmaIsiHaritasi");
                fieldGo.transform.SetParent(ewRoot, false);
                fieldMesh = new Mesh { name = "IsiHaritasi", indexFormat = IndexFormat.UInt32 };
                fieldGo.AddComponent<MeshFilter>().sharedMesh = fieldMesh;
                var mr = fieldGo.AddComponent<MeshRenderer>();
                mr.shadowCastingMode = ShadowCastingMode.Off;
                fieldMat = new Material(Mats.HeatMap) { name = "IsiHaritasi" };
                // Dokulu parlama yoksa düz parlama bütün örtüyü beyaz bir perdeye çevirir: o durumda parlama kapatılır
                bool emitMap = !SwarmMaterials.IsHdrp || fieldMat.IsKeywordEnabled("_EMISSIVE_COLOR_MAP");
                if (!emitMap) SwarmMaterials.SetEmission(fieldMat, Color.black, 0f);
                Debug.Log($"[SuruIHA] Isı haritası: dokulu parlama {(emitMap ? "var" : "yok")}");
                mr.sharedMaterial = fieldMat;
            }
            int vx = (F.nx - 1) * FieldSub + 1, vy = (F.ny - 1) * FieldSub + 1;
            int W = (F.nx - 1) * FieldUp + 1, H = (F.ny - 1) * FieldUp + 1;
            float d = F.step / FieldSub;
            var verts = new Vector3[vx * vy];
            var uv = new Vector2[vx * vy];
            var terrains = Terrain.activeTerrains;   // orta arazi + çevre parçaları
            for (int j = 0, k = 0; j < vy; j++)
            for (int i = 0; i < vx; i++, k++)
            {
                float x = F.x0 + i * d, z = F.y0 + j * d;
                verts[k] = new Vector3(x, HeatGround(terrains, x, z) + FieldLift, z);
                // Doku pikselinin ortası verinin noktasına denk gelsin
                uv[k] = new Vector2(((float)i / FieldSub * FieldUp + 0.5f) / W, ((float)j / FieldSub * FieldUp + 0.5f) / H);
            }
            var tris = new int[(vx - 1) * (vy - 1) * 6];
            for (int j = 0, t = 0; j < vy - 1; j++)
            for (int i = 0; i < vx - 1; i++)
            {
                int a = j * vx + i;
                tris[t++] = a; tris[t++] = a + vx; tris[t++] = a + 1;
                tris[t++] = a + 1; tris[t++] = a + vx; tris[t++] = a + vx + 1;
            }
            fieldMesh.Clear();
            fieldMesh.vertices = verts;
            fieldMesh.uv = uv;
            fieldMesh.triangles = tris;
            fieldMesh.RecalculateNormals();
            fieldMesh.RecalculateBounds();
            fieldBuiltPos = transform.position;
        }

        // Arazi yüksekliği (yerel): noktanın üstünde durduğu arazi parçasından (binalara, araçlara takılmaz)
        Terrain lastTerrain;

        float HeatGround(Terrain[] ts, float x, float z)
        {
            var w = transform.TransformPoint(new Vector3(x, 0f, z));
            var t = Covers(lastTerrain, w) ? lastTerrain : null;
            for (int i = 0; t == null && i < ts.Length; i++)
                if (Covers(ts[i], w)) t = ts[i];
            if (t == null) return LocalGround(x, z);
            lastTerrain = t;
            return t.SampleHeight(w) + t.transform.position.y - transform.position.y;
        }

        static bool Covers(Terrain t, Vector3 w)
        {
            if (t == null || t.terrainData == null) return false;
            Vector3 p = t.transform.position, s = t.terrainData.size;
            return w.x >= p.x && w.x <= p.x + s.x && w.z >= p.z && w.z <= p.z + s.z;
        }

        void PaintHeatMap(JamFieldState F, byte[] q)
        {
            int nx = F.nx, ny = F.ny;
            int W = (nx - 1) * FieldUp + 1, H = (ny - 1) * FieldUp + 1;
            if (fieldTex == null || fieldTex.width != W || fieldTex.height != H)
            {
                SafeDestroy(fieldTex);
                SafeDestroy(fieldEmit);
                fieldTex = NewHeatTexture(W, H, "IsiHaritasi");
                fieldEmit = NewHeatTexture(W, H, "IsiHaritasiParlama");
                SwarmMaterials.SetOverlayTexture(fieldMat, fieldTex, fieldEmit);
                fieldVals = new float[W * H];
                fieldPx = new Color32[W * H];
                fieldEmitPx = new Color32[W * H];
            }
            // Veri noktaları arasında çift doğrusal aradeğerleme (dBm)
            for (int b = 0, k = 0; b < H; b++)
            {
                float gy = (float)b / FieldUp;
                int j0 = Mathf.Min((int)gy, ny - 2);
                float fy = gy - j0;
                for (int a = 0; a < W; a++, k++)
                {
                    float gx = (float)a / FieldUp;
                    int i0 = Mathf.Min((int)gx, nx - 2);
                    float fx = gx - i0;
                    int r0 = j0 * nx + i0, r1 = r0 + nx;
                    float v = (q[r0] * (1 - fx) + q[r0 + 1] * fx) * (1 - fy) + (q[r1] * (1 - fx) + q[r1 + 1] * fx) * fy;
                    fieldVals[k] = F.db0 + v * F.dbStep;
                }
            }
            float detect = F.detect < 0 ? F.detect : -82f, cut = F.cut < 0 ? F.cut : -74.5f;
            var cutLine = new Color32(255, 232, 222, 205);
            var detectLine = new Color32(255, 214, 204, 115);
            float fade = 6f * FieldUp;    // kenarda 6 nokta aralığı boyunca söner (harita dikdörtgen gibi bitmesin)
            for (int b = 0, k = 0; b < H; b++)
            for (int a = 0; a < W; a++, k++)
            {
                // Eş güç çizgileri: bağlantı kopması kalın ve parlak (eşiğin iki yanı), fark etme ince ve soluk (yalnız iç yanı)
                Color32 c = Crosses(k, a, b, W, H, cut, false) ? cutLine
                          : Crosses(k, a, b, W, H, detect, true) ? detectLine
                          : HeatColor(fieldVals[k], detect, cut);
                float e = Mathf.Clamp01(Mathf.Min(Mathf.Min(a, W - 1 - a), Mathf.Min(b, H - 1 - b)) / fade);
                c.a = (byte)(c.a * e * e * (3f - 2f * e));
                fieldPx[k] = c;
                // Parlama saydamlıkla çarpılır (HDRP parlamayı saydamlıktan bağımsız ekler; yoksa soluk yerler de parlar)
                fieldEmitPx[k] = new Color32((byte)(c.r * c.a / 255), (byte)(c.g * c.a / 255), (byte)(c.b * c.a / 255), 255);
            }
            fieldTex.SetPixels32(fieldPx);
            fieldTex.Apply(false);
            fieldEmit.SetPixels32(fieldEmitPx);
            fieldEmit.Apply(false);
        }

        static Texture2D NewHeatTexture(int w, int h, string name) =>
            new Texture2D(w, h, TextureFormat.RGBA32, false, false)
                { name = name, wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, anisoLevel = 4 };

        // Eşik bu piksel ile bir komşusu arasından geçiyor mu; innerOnly: yalnızca eşiğin üstündeki piksel (ince çizgi)
        bool Crosses(int k, int a, int b, int W, int H, float level, bool innerOnly)
        {
            bool s = fieldVals[k] >= level;
            if (innerOnly && !s) return false;
            if (a + 1 < W && (fieldVals[k + 1] >= level) != s) return true;
            if (a > 0 && (fieldVals[k - 1] >= level) != s) return true;
            if (b + 1 < H && (fieldVals[k + W] >= level) != s) return true;
            if (b > 0 && (fieldVals[k - W] >= level) != s) return true;
            return false;
        }

        // Tek tonlu (kırmızı) sıralı renk skalası: zayıf karıştırma açık ve neredeyse saydam, güçlü karıştırma
        // koyu ve daha örtücü. Duraklar anlamlı eşiklerde: fark etme (detect) ve bağlantı kopması (cut).
        static readonly Color HeatLight = new Color32(255, 179, 168, 255);
        static readonly Color HeatDetect = new Color32(244, 119, 106, 255);
        static readonly Color HeatCut = new Color32(217, 59, 48, 255);
        static readonly Color HeatStrong = new Color32(122, 15, 20, 255);

        public static float HeatLow(float detect) => detect - 6f;
        public static float HeatHigh(float cut) => cut + 20f;

        public static Color32 HeatColor(float J, float detect, float cut)
        {
            float lo = HeatLow(detect), hi = HeatHigh(cut);
            if (J <= lo) return new Color32(0, 0, 0, 0);
            Color c;
            float alpha;
            if (J < detect)
            {
                float t = (J - lo) / (detect - lo);
                c = Color.Lerp(HeatLight, HeatDetect, t);
                alpha = 0.22f * t * t * (3f - 2f * t);
            }
            else if (J < cut)
            {
                float t = (J - detect) / Mathf.Max(cut - detect, 0.1f);
                c = Color.Lerp(HeatDetect, HeatCut, t);
                alpha = Mathf.Lerp(0.22f, 0.36f, t);
            }
            else
            {
                float t = Mathf.Clamp01((J - cut) / Mathf.Max(hi - cut, 0.1f));
                c = Color.Lerp(HeatCut, HeatStrong, t);
                alpha = Mathf.Lerp(0.36f, 0.56f, t);
            }
            c.a = alpha;
            return c;
        }
    }
}
