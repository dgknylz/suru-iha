using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace SuruIHA.EditorTools
{
    // Divriği (Sivas): ana araziden 12 km kuzeyde dördüncü harita. Çaltı Çayı vadisine inen yamaçta tarihî kent: tepede kayalık
    // kale (yıkık burçlar ve surlar), yamacın ortasında Ulu Camii ve Darüşşifası (taraça üstünde, kuzey taç kapısı vadiye
    // bakar), çevresinde bahçeli Divriği evleri; vadide kavak sıraları ve bahçeler, kuzeyde demir yüklü kızıl dağlar.
    // Python bu bölgenin yükseklik haritasını arazi_yukseklik_divrigi.bin olarak okur (--region divrigi).
    public static partial class SuruIHASetup
    {
        static Vector3 DivrigiOrigin => SwarmRegions.DivrigiOffset;
        static readonly Vector2 KaleXZ = new Vector2(170f, 250f);       // kale tepesi
        static readonly Vector2 UluCamiXZ = new Vector2(-110f, 450f);   // külliyenin merkezi (kuzey taç kapısı +z'ye bakar)

        // Çaltı Çayı: batıdan doğuya, vadinin ortasından
        static float CaltiZ(float x) => 900f + 45f * Mathf.Sin(x * 0.0042f + 1f) + 18f * Mathf.Sin(x * 0.013f + 0.3f);

        static float DivrigiSlope(float x, float z)
        {
            // Üsten (güney) vadiye (kuzey) inen yamaç; yamaçta hafif sırtlar
            float s = BaseHeight + 4f - 0.042f * Mathf.Max(0f, z - 60f) + 4f * (Fbm(x * 0.004f + 3f, z * 0.004f, 3) - 0.5f);
            return Mathf.Max(s, BaseHeight - 15f);
        }

        public static float HeightAtDivrigi(float x, float z)
        {
            float h = DivrigiSlope(x, z);
            // Vadi tabanı ve çay yatağı
            float dr = z - CaltiZ(x);
            float valley = BaseHeight - 16f + 1.5f * (Fbm(x * 0.008f, z * 0.008f + 2f, 2) - 0.5f);
            // çayın güneyinde yamaç vadiye yumuşakça iner; kuzeyi vadi tabanından başlar (dağlar aşağıda eklenir)
            h = Mathf.Lerp(h, valley, 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(60f, 220f, Mathf.Abs(dr))) * (dr < 0 ? 1f : 0f));
            h -= 2.5f * (1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(5f, 10f, Mathf.Abs(dr))));
            // Kuzeyde demirli kızıl dağlar (çayın 120 m ötesinden dik yükselir)
            float ridge = 1f - Mathf.Abs(Fbm(x * 0.0025f + 17f, z * 0.0025f - 5f, 4) * 2f - 1f);
            h += Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(110f, 420f, dr)) * (150f + 140f * ridge);
            // Güneyde üssün arkasında yükselen tepeler, doğu ve batıda dağ yamaçları
            h += 110f * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(-250f, -1100f, z)) * (0.6f + 0.8f * Fbm(x * 0.003f, z * 0.003f + 9f, 3));
            h += Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(800f, 1180f, Mathf.Abs(x))) * 120f * (0.5f + ridge) * (dr < 60f ? 1f : 0.6f);
            // Kale tepesi: dik yamaçlı, kayalık
            float dk = (new Vector2(x, z) - KaleXZ).magnitude;
            h += 95f * Mathf.Exp(-Mathf.Pow(dk / 135f, 2.4f)) * (0.92f + 0.16f * Fbm(x * 0.02f, z * 0.02f, 3));
            // Külliyenin taraçası: yamaca oyulmuş düz alan
            float t0 = DivrigiSlope(UluCamiXZ.x, UluCamiXZ.y);
            h = Terrace(x, z, UluCamiXZ, new Vector2(25f, 40f), 0f, 22f, h, t0);
            return Mathf.Clamp(h, 1f, TerrainHeight - 5f);
        }

        static float FarHeightAtDivrigi(float x, float z)
        {
            float o = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) - TerrainSize / 2;      // merkez parçanın dışına uzaklık
            float dr = Mathf.Abs(z - CaltiZ(x));
            float ridge = 1f - Mathf.Abs(Fbm(x * 0.0009f + 31f, z * 0.0009f - 13f, 5) * 2f - 1f);
            float up = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0f, 700f, o)) * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(150f, 900f, dr));
            return HeightAtDivrigi(x, z) + up * (200f + 420f * ridge);
        }

        // Katmanlar: 0 çayır, 1 bozkır, 2 bahçe/tarla, 3 anız, 4 kızıl (demirli) toprak, 5 kaya, 6 sokak ve yol
        static TerrainLayer[] DivrigiLayers() => new[]
        {
            Layer("DCayir", "Ter_Cimen", new Color(0.29f, 0.36f, 0.16f), new Color(0.2f, 0.27f, 0.1f), 6f, 0.05f, 41, "aerial_grass_rock", 15f),
            Layer("DBozkir", "Ter_Bozkir", new Color(0.55f, 0.5f, 0.31f), new Color(0.4f, 0.36f, 0.21f), 7f, 0.04f, 42, "withered_grass", 7f,
                  new Color(0.78f, 0.72f, 0.6f)),
            Layer("DBahce", "Ter_Tarla", new Color(0.42f, 0.34f, 0.24f), new Color(0.3f, 0.24f, 0.17f), 9f, 0.06f, 43, "farm_soil", 5f),
            Layer("DAniz", "Ter_Aniz", new Color(0.7f, 0.6f, 0.4f), new Color(0.55f, 0.46f, 0.3f), 7f, 0.05f, 44, "withered_grass", 4f,
                  new Color(1f, 0.88f, 0.62f)),
            Layer("DKizil", "Ter_Tarla", new Color(0.55f, 0.27f, 0.17f), new Color(0.4f, 0.2f, 0.12f), 8f, 0.05f, 45, "red_laterite_soil_stones", 7f,
                  new Color(0.95f, 0.85f, 0.8f)),
            Layer("DKaya", "Ter_Kaya", new Color(0.5f, 0.45f, 0.4f), new Color(0.4f, 0.36f, 0.3f), 20f, 0.1f, 46, "aerial_rocks_02", 30f,
                  new Color(0.95f, 0.85f, 0.75f)),
            Layer("DYol", "Ter_Cakil", new Color(0.55f, 0.5f, 0.42f), new Color(0.4f, 0.36f, 0.3f), 5f, 0.08f, 47, "dirt_aerial_02", 5f),
        };

        static List<Vector2[]> DivrigiRoads()
        {
            // Üsten kale tepesinin batısından kente, külliyenin önünden vadiye inen yol; vadide çay boyunca yol;
            // kentte iki kıvrımlı sokak
            var main = new List<Vector2> { new Vector2(-30f, -10f), new Vector2(-40f, 120f), new Vector2(-20f, 260f), new Vector2(-30f, 380f),
                                           new Vector2(-60f, 520f), new Vector2(-90f, 640f), new Vector2(-70f, 780f), new Vector2(-40f, CaltiZ(-40f) - 40f) };
            var valley = new List<Vector2>();
            for (float x = -1180f; x <= 1180f; x += 60f) valley.Add(new Vector2(x, CaltiZ(x) - 55f + 10f * Mathf.Sin(x * 0.01f)));
            var s1 = new List<Vector2> { new Vector2(-420f, 540f), new Vector2(-300f, 560f), new Vector2(-150f, 520f), new Vector2(-30f, 560f),
                                         new Vector2(90f, 600f), new Vector2(240f, 560f), new Vector2(360f, 600f) };
            var s2 = new List<Vector2> { new Vector2(-380f, 680f), new Vector2(-220f, 700f), new Vector2(-90f, 660f), new Vector2(60f, 720f),
                                         new Vector2(200f, 700f) };
            var kale = new List<Vector2> { new Vector2(-20f, 260f), new Vector2(40f, 300f), new Vector2(90f, 290f), KaleXZ + new Vector2(-50f, 10f) };
            var jam = new List<Vector2>();
            for (int k = 0; k <= 30; k++) jam.Add(Vector2.Lerp(new Vector2(-30f, -10f), JammerXZ + new Vector2(-12f, -8f), k / 30f));
            return new List<Vector2[]> { Dense(main), Dense(valley), Dense(s1), Dense(s2), Dense(kale), jam.ToArray() };
        }

        static bool InTown(float x, float z) => x > -470f && x < 380f && z > 330f && z < 790f;

        static void BuildDivrigiRegion(Prefabs prefabs)
        {
            var root = new GameObject("Divrigi").transform;
            var roads = DivrigiRoads();
            var layers = DivrigiLayers();
            var fw = new float[layers.Length];
            void Paint(float x, float z, float slope, float[] w)
            {
                float dr = z - CaltiZ(x);
                w[1] = 1f;
                // vadide ve çay boyunca çayır; vadi tabanında tarlalar ve bahçeler
                float wet = 1f - Mathf.InverseLerp(25f, 120f, Mathf.Abs(dr));
                w[0] = wet + Mathf.Clamp01((Fbm(x * 0.004f + 2f, z * 0.004f - 3f, 4) - 0.55f) * 3f) * 0.5f;
                float floor = (1f - Mathf.InverseLerp(60f, 200f, -dr)) * (dr < 100f ? 1f : 0f) * Mathf.InverseLerp(22f, 40f, Mathf.Abs(dr));
                if (floor > 0f && slope < 8f)
                {
                    int type = FieldType(x, z, out float edge);
                    System.Array.Clear(fw, 0, fw.Length);
                    fw[type] = 1f;
                    for (int k = 0; k < w.Length; k++) w[k] = Mathf.Lerp(w[k], Mathf.Lerp(fw[k], k == 0 ? 1f : 0f, Mathf.Clamp01(1f - edge / 2f)), floor);
                }
                // kentin bahçeleri: yeşil ve sürülmüş yamalar
                if (InTown(x, z) && slope < 14f)
                {
                    float g = Fbm(x * 0.02f + 7f, z * 0.02f, 2);
                    w[0] += g > 0.55f ? 1.2f : 0f;
                    w[2] += g < 0.38f ? 0.9f : 0f;
                }
                // kızıl demirli toprak: dağ yamaçlarında; kaya: dik yerler ve kale tepesi
                float red = Mathf.Clamp01((slope - 12f) / 12f) * (dr > 90f || Mathf.Abs(x) > 700f || z < -200f ? 1f : 0.35f)
                          + Mathf.Clamp01((Fbm(x * 0.005f - 11f, z * 0.005f + 4f, 3) - 0.62f) * 3f) * (dr > 120f ? 1f : 0f);
                float rock = Mathf.Clamp01((slope - 30f) / 8f)
                           + Mathf.Clamp01(1f - ((new Vector2(x, z) - KaleXZ).magnitude - 70f) / 40f) * Mathf.Clamp01((slope - 14f) / 10f);
                red = Mathf.Clamp01(red);
                rock = Mathf.Clamp01(rock);
                for (int k = 0; k < w.Length; k++) w[k] *= (1f - red) * (1f - rock);
                w[4] += red * (1f - rock);
                w[5] += rock;
                // yollar, sokaklar, külliyenin taş meydanı
                float rd = RoadDistance(roads, new Vector2(x, z));
                float road = Mathf.Clamp01(1f - (rd - (InTown(x, z) ? 2.5f : 3f)) / 1.8f);
                float plaza = Mathf.Clamp01(1f - Mathf.Max(Mathf.Abs(x - UluCamiXZ.x) - 28f, Mathf.Abs(z - UluCamiXZ.y) - 44f) / 5f);
                float pad = Mathf.Clamp01(1f - ((new Vector2(x, z) - new Vector2(-30f, -4f)).magnitude - 16f) / 4f)
                          + Mathf.Clamp01(1f - ((new Vector2(x, z) - JammerXZ).magnitude - 12f) / 4f);
                float gr = Mathf.Clamp01(road + plaza + pad);
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - gr;
                w[6] += gr;
            }
            bool Free(float x, float z) => RoadDistance(roads, new Vector2(x, z)) > 6f && new Vector2(x, z).magnitude > 90f
                                           && (Mathf.Abs(x - UluCamiXZ.x) > 32f || Mathf.Abs(z - UluCamiXZ.y) > 48f)
                                           && (new Vector2(x, z) - JammerXZ).magnitude > 30f;
            void Plant(Planter pl, TerrainData td)
            {
                // çay boyunca kavak ve söğüt
                for (float x = -1180f; x < 1180f; x += 6f)
                for (int side = -1; side <= 1; side += 2)
                {
                    if (pl.R() < 0.3f) continue;
                    float z = CaltiZ(x) + side * (12f + pl.R() * 22f);
                    if (!Free(x, z)) continue;
                    if (pl.R() < 0.65f) pl.Poplar(x, z, 0.85f + 0.35f * pl.R());
                    else pl.Willow(x, z, 0.85f + 0.3f * pl.R());
                }
                // vadide meyve bahçeleri (sıra sıra küçük yuvarlak ağaçlar) ve tarla kenarlarında kavaklar
                for (int k = 0; k < 80000 && pl.Count < 6500; k++)
                {
                    float x = (pl.R() - 0.5f) * 2300f, z = (pl.R() - 0.5f) * 2300f;
                    float dr = z - CaltiZ(x);
                    if (!Free(x, z)) continue;
                    float sl = td.GetSteepness(x / TerrainSize + 0.5f, z / TerrainSize + 0.5f);
                    if (dr < 90f && dr > -220f && Mathf.Abs(dr) > 30f && sl < 8f)
                    {
                        FieldType(x, z, out float edge);
                        if (edge < 2.5f && pl.R() < 0.5f) pl.Poplar(x, z, 0.85f + 0.3f * pl.R());
                        else if (Fbm(x * 0.01f, z * 0.01f + 4f, 2) > 0.58f && pl.R() < 0.6f)
                            pl.Oak(Mathf.Round(x / 8f) * 8f, Mathf.Round(z / 8f) * 8f, 0.55f + 0.15f * pl.R(), 0.5f + 0.12f * pl.R());
                    }
                    else if (InTown(x, z) && sl < 16f && pl.R() < 0.3f)
                        pl.Oak(x, z, 0.65f + 0.3f * pl.R(), 0.6f + 0.3f * pl.R());          // bahçelerde ceviz ve dut
                    else if (sl < 34f && pl.R() < 0.08f)
                    {
                        if (pl.R() < 0.7f) pl.Shrub(x, z, 0.7f + 0.5f * pl.R());
                        else pl.Rock(x, z, 0.6f + pl.R());
                    }
                }
                // kale tepesinde kaya
                for (int k = 0; k < 220; k++)
                {
                    float a = pl.R() * 6.28f, r = 60f + pl.R() * 110f;
                    pl.Rock(KaleXZ.x + Mathf.Cos(a) * r, KaleXZ.y + Mathf.Sin(a) * r, 0.8f + 1.2f * pl.R());
                }
            }
            var t = BuildRegionTerrain("Divrigi", root, DivrigiOrigin, "_divrigi", HeightAtDivrigi, layers, Paint, Plant, prefabs, 1228);

            // Çaltı Çayı
            var line = new List<Vector2>();
            for (float x = -1200f; x <= 1200f; x += 6f) line.Add(new Vector2(x, CaltiZ(x)));
            BuildCreek("CaltiCayi_Su", root, DivrigiOrigin, line, 7.5f, c => HeightAtDivrigiWater(c.x) - BaseHeight,
                       ClearWaterMaterial("MAT_DereSu", new Color(0.16f, 0.2f, 0.17f)));

            BuildDivrigiTown(prefabs, root, t, roads);
            BuildDivrigiCastle(prefabs, root, t);
            BuildRegionFarTiles("Divrigi", root, DivrigiOrigin, t, layers, FarHeightAtDivrigi, Paint,
                (pl, x, z, sl) =>
                {
                    float dr = Mathf.Abs(z - CaltiZ(x));
                    if (dr < 40f && pl.R() < 0.5f) pl.Poplar(x, z, 0.9f);
                    else if (sl < 30f && pl.R() < 0.03f) pl.Shrub(x, z, 1.2f);
                }, prefabs, 1229, 900);
        }

        // Su yüzeyi: vadi tabanının biraz altında (yatağın içinde)
        static float HeightAtDivrigiWater(float x) => HeightAtDivrigi(x, CaltiZ(x) + 12f) - 1.2f;

        // Ulu Camii ve Darüşşifası ile Divriği evleri
        static void BuildDivrigiTown(Prefabs p, Transform root, Terrain t, List<Vector2[]> roads)
        {
            var town = new GameObject("DivrigiKenti").transform;
            town.SetParent(root, false);
            var cami = PlaceOn(p, "Yapi_UluCami", town, t, DivrigiOrigin + new Vector3(UluCamiXZ.x, 0f, UluCamiXZ.y), 0f);
            if (cami != null) cami.name = "UluCamiVeDarussifa";
            var rng = new System.Random(1229);
            float R() => (float)rng.NextDouble();
            var placed = new List<Vector2>();
            int n = 0;
            for (int k = 0; k < 4000 && n < 58; k++)
            {
                var c = new Vector2(Mathf.Lerp(-460f, 370f, R()), Mathf.Lerp(330f, 800f, R()));
                if ((c - KaleXZ).magnitude < 150f || RoadDistance(roads, c) < 9f) continue;
                if (Mathf.Abs(c.x - UluCamiXZ.x) < 38f && Mathf.Abs(c.y - UluCamiXZ.y) < 54f) continue;
                if (c.y > CaltiZ(c.x) - 70f) continue;
                if (t.terrainData.GetSteepness((c.x) / TerrainSize + 0.5f, c.y / TerrainSize + 0.5f) > 15f) continue;
                bool near = false;
                foreach (var q in placed) if ((q - c).sqrMagnitude < 17f * 17f) { near = true; break; }
                if (near) continue;
                // evler kümelenir: kentin ortasında sık, kenarlarda seyrek
                float dense = 1f - Mathf.Clamp01(((c - new Vector2(-60f, 560f)).magnitude - 120f) / 330f);
                if (R() > 0.25f + 0.75f * dense) continue;
                placed.Add(c);
                // cumbalı cephe vadiye (kuzeye) bakar
                PlaceOn(p, $"Yapi_DivrigiEv_{rng.Next(4)}", town, t, DivrigiOrigin + new Vector3(c.x, 0f, c.y), (R() - 0.5f) * 24f, 0.3f);
                n++;
            }
            GameObjectUtility.SetStaticEditorFlags(town.gameObject, StaticEditorFlags.BatchingStatic);
            Debug.Log($"[SuruIHA] Divriği: Ulu Camii {(cami != null ? "yerinde" : "YOK")}, {n} ev");
        }

        // Kale: tepenin çevresinde yıkık sur, köşelerde yuvarlak ve kare burçlar
        static void BuildDivrigiCastle(Prefabs p, Transform root, Terrain t)
        {
            var kale = new GameObject("DivrigiKalesi").transform;
            kale.SetParent(root, false);
            const int N = 11;
            var ring = new Vector2[N];
            for (int i = 0; i < N; i++)
            {
                float a = i * Mathf.PI * 2f / N;
                float r = 1f + 0.12f * Mathf.Sin(a * 3f + 1f);
                var e = new Vector2(Mathf.Cos(a) * 88f * r, Mathf.Sin(a) * 62f * r);
                float rot = 20f * Mathf.Deg2Rad;
                ring[i] = KaleXZ + new Vector2(e.x * Mathf.Cos(rot) - e.y * Mathf.Sin(rot), e.x * Mathf.Sin(rot) + e.y * Mathf.Cos(rot));
            }
            float Ground(Vector2 c) => t.SampleHeight(DivrigiOrigin + new Vector3(c.x, 0f, c.y)) + t.transform.position.y;
            for (int i = 0; i < N; i++)
            {
                var a = ring[i];
                var b = ring[(i + 1) % N];
                if (i == 7) continue;                                                         // yıkılmış sur aralığı
                var d = b - a;
                int segs = Mathf.Max(1, Mathf.RoundToInt(d.magnitude / 12f));
                for (int s = 0; s < segs; s++)
                {
                    var c = Vector2.Lerp(a, b, (s + 0.5f) / segs);
                    float y = Mathf.Min(Ground(c - d.normalized * 6f), Ground(c), Ground(c + d.normalized * 6f));
                    if (!p.named.TryGetValue("Yapi_KaleSur", out var pf)) break;
                    var g = (GameObject)PrefabUtility.InstantiatePrefab(pf, kale);
                    g.transform.SetPositionAndRotation(DivrigiOrigin + new Vector3(c.x, y - 0.6f, c.y),
                                                       Quaternion.Euler(0f, Mathf.Atan2(-d.y, d.x) * Mathf.Rad2Deg, 0f));
                    g.transform.localScale = new Vector3(d.magnitude / segs / 12f, 1f, 1f);
                }
                PlaceOn(p, i % 3 == 0 ? "Yapi_KaleBurc" : "Yapi_KaleKule", kale, t, DivrigiOrigin + new Vector3(a.x, 0f, a.y), i * 33f, 1.0f);
            }
            GameObjectUtility.SetStaticEditorFlags(kale.gameObject, StaticEditorFlags.BatchingStatic);
        }
    }
}
