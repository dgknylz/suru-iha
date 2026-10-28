using System.Collections.Generic;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace SuruIHA.EditorTools
{
    // Gökpınar Gölü (Gürün, Sivas): ana araziden 12 km güneyde beşinci harita. 1500 m'lik bozkır platosunun ortasında
    // yerin derinliklerinden kaynayan, dibi görünen turkuaz karstik göl ("bozkırın nazar boncuğu"): kıyıda sığ ve açık
    // turkuaz, ortada 17 m'ye inen huni gibi koyu mavi. Gölden çıkan dere kuzeydoğuya akar; dere boyunca çayır, kavak ve
    // söğüt, alabalık havuzları; batıda kalker sırt, güneydoğuda köy. Göl kıyısında ahşap kameriye ve yürüyüş iskelesi.
    // Göl suyu HDRP su yüzeyidir (havuz türü: dalgacık, kostik ışık, dibe kadar berrak). --region gokpinar
    public static partial class SuruIHASetup
    {
        static Vector3 GokpinarOrigin => SwarmRegions.GokpinarOffset;
        static readonly Vector2 LakeXZ = new Vector2(-140f, 430f);
        const float LakeA = 72f, LakeB = 32f, LakeYaw = 25f;          // elips yarı eksenleri (m), uzun eksenin açısı
        const float LakeDepth = 17f;

        // Göl elipsine göre normalleştirilmiş uzaklık (1 = kıyı)
        static float LakeR(float x, float z)
        {
            float a = LakeYaw * Mathf.Deg2Rad;
            float dx = x - LakeXZ.x, dz = z - LakeXZ.y;
            float u = dx * Mathf.Cos(a) + dz * Mathf.Sin(a), v = -dx * Mathf.Sin(a) + dz * Mathf.Cos(a);
            return Mathf.Sqrt(u * u / (LakeA * LakeA) + v * v / (LakeB * LakeB));
        }

        static Vector2 LakeTip => LakeXZ + new Vector2(Mathf.Cos(LakeYaw * Mathf.Deg2Rad), Mathf.Sin(LakeYaw * Mathf.Deg2Rad)) * (LakeA - 4f);

        // Gölden çıkan dere: doğu ucundan kuzeydoğuya kıvrılarak
        static readonly List<Vector2> CreekLine = MakeCreek();

        static List<Vector2> MakeCreek()
        {
            var pts = new List<Vector2>();
            var p = LakeTip;
            var dir = new Vector2(0.75f, 0.66f).normalized;
            for (int i = 0; i < 300; i++)
            {
                pts.Add(p);
                float wig = 0.45f * Mathf.Sin(i * 0.11f) + 0.2f * Mathf.Sin(i * 0.31f + 1f);
                var d = new Vector2(dir.x * Mathf.Cos(wig) - dir.y * Mathf.Sin(wig), dir.x * Mathf.Sin(wig) + dir.y * Mathf.Cos(wig));
                p += d * 6f;
                if (Mathf.Abs(p.x) > 1200f || Mathf.Abs(p.y) > 1200f) break;
            }
            return pts;
        }

        static float CreekDist(float x, float z)
        {
            float best = float.MaxValue;
            var q = new Vector2(x, z);
            for (int i = 0; i < CreekLine.Count; i += 2) best = Mathf.Min(best, (CreekLine[i] - q).sqrMagnitude);
            return Mathf.Sqrt(best);
        }

        static float GokpinarPlateau(float x, float z) =>
            BaseHeight + 7f * (Fbm(x * 0.0025f + 4f, z * 0.0025f - 2f, 4) - 0.5f) - 0.004f * Mathf.Max(0f, z - 200f);

        static float LakeLevelY => GokpinarPlateau(LakeXZ.x, LakeXZ.y) - BaseHeight - 0.7f;

        public static float HeightAtGokpinar(float x, float z)
        {
            float h = GokpinarPlateau(x, z);
            // batıda kalker sırt, kuzeyde ve güneyde yumuşak tepeler
            float ridge = 1f - Mathf.Abs(Fbm(x * 0.003f + 21f, z * 0.003f, 4) * 2f - 1f);
            h += Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(-430f, -900f, x)) * (60f + 70f * ridge);
            h += 26f * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(-300f, -1100f, z)) * Fbm(x * 0.003f, z * 0.003f + 7f, 3);
            h += Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(850f, 1180f, Mathf.Max(Mathf.Abs(x), Mathf.Abs(z - 200f)))) * 90f * ridge;
            // gölün çevresi düz, içinde sığ kıyı şeridi ve derin huni
            float lr = LakeR(x, z);
            float lake0 = GokpinarPlateau(LakeXZ.x, LakeXZ.y);
            h = Mathf.Lerp(lake0, h, Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(1.15f, 2.6f, lr)));
            if (lr < 1.05f)
            {
                float shelf = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(1.05f, 0.78f, lr)) * 2.2f;
                float funnel = Mathf.Pow(Mathf.Clamp01(1f - lr / 0.78f), 0.75f) * (LakeDepth - 2.2f);
                h -= 0.7f + shelf + funnel;
            }
            // dere yatağı
            float cd = CreekDist(x, z);
            if (lr > 0.9f) h -= 1.4f * (1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(2.5f, 7f, cd)));
            return Mathf.Clamp(h, 1f, TerrainHeight - 5f);
        }

        static float FarHeightAtGokpinar(float x, float z)
        {
            float o = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) - TerrainSize / 2;
            float ridge = 1f - Mathf.Abs(Fbm(x * 0.0008f + 61f, z * 0.0008f - 23f, 5) * 2f - 1f);
            return HeightAtGokpinar(x, z) + Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0f, 900f, o)) * (140f + 420f * ridge);
        }

        // Katmanlar: 0 çayır, 1 bozkır, 2 tarla, 3 anız, 4 kalker kaya, 5 göl dibi (beyaz kalker kumu), 6 toprak yol
        static TerrainLayer[] GokpinarLayers() => new[]
        {
            Layer("GCayir", "Ter_Cimen", new Color(0.29f, 0.36f, 0.16f), new Color(0.2f, 0.27f, 0.1f), 6f, 0.05f, 51, "aerial_grass_rock", 15f),
            Layer("GBozkir", "Ter_Bozkir", new Color(0.55f, 0.5f, 0.31f), new Color(0.4f, 0.36f, 0.21f), 7f, 0.04f, 52, "withered_grass", 7f,
                  new Color(0.76f, 0.71f, 0.58f)),
            Layer("GTarla", "Ter_Tarla", new Color(0.42f, 0.34f, 0.24f), new Color(0.3f, 0.24f, 0.17f), 9f, 0.06f, 53, "farm_soil", 5f),
            Layer("GAniz", "Ter_Aniz", new Color(0.7f, 0.6f, 0.4f), new Color(0.55f, 0.46f, 0.3f), 7f, 0.05f, 54, "withered_grass", 4f,
                  new Color(1f, 0.88f, 0.62f)),
            Layer("GKaya", "Ter_Kaya", new Color(0.62f, 0.6f, 0.55f), new Color(0.5f, 0.48f, 0.44f), 20f, 0.1f, 55, "aerial_rocks_02", 30f,
                  new Color(1.15f, 1.12f, 1.05f)),
            Layer("GGolDibi", "Ter_Cakil", new Color(0.85f, 0.85f, 0.8f), new Color(0.7f, 0.7f, 0.65f), 4f, 0.1f, 56, "gravelly_sand", 4f,
                  new Color(1.35f, 1.35f, 1.3f), 0.35f),
            Layer("GYol", "Ter_Cakil", new Color(0.55f, 0.5f, 0.42f), new Color(0.4f, 0.36f, 0.3f), 5f, 0.08f, 57, "dirt_aerial_02", 5f),
        };

        static readonly Vector2 GVillageXZ = new Vector2(430f, 150f);
        static readonly Vector2 TroutXZ = new Vector2(250f, 720f);

        static List<Vector2[]> GokpinarRoads()
        {
            var a = new List<Vector2> { new Vector2(-30f, -10f), new Vector2(-60f, 160f), new Vector2(-90f, 300f), LakeXZ + new Vector2(10f, -60f) };
            var b = new List<Vector2> { new Vector2(-30f, -10f), new Vector2(140f, 40f), new Vector2(300f, 110f), GVillageXZ };
            var c = new List<Vector2> { LakeXZ + new Vector2(10f, -60f), new Vector2(60f, 470f), new Vector2(170f, 620f), TroutXZ + new Vector2(-30f, -30f) };
            var jam = new List<Vector2>();
            for (int k = 0; k <= 30; k++) jam.Add(Vector2.Lerp(new Vector2(-30f, -10f), JammerXZ + new Vector2(-12f, -8f), k / 30f));
            return new List<Vector2[]> { Dense(a), Dense(b), Dense(c), jam.ToArray() };
        }

        static void BuildGokpinarRegion(Prefabs prefabs)
        {
            var root = new GameObject("Gokpinar").transform;
            var roads = GokpinarRoads();
            var layers = GokpinarLayers();
            var fw = new float[layers.Length];
            void Paint(float x, float z, float slope, float[] w)
            {
                w[1] = 1f;
                float lr = LakeR(x, z), cd = CreekDist(x, z);
                // gölün ve derenin çevresi yeşil; uzakta bozkır, köyün çevresinde tarlalar
                float green = Mathf.Clamp01(1f - (lr - 1.2f) / 1.4f) + Mathf.Clamp01(1f - (cd - 8f) / 45f)
                            + Mathf.Clamp01((Fbm(x * 0.004f - 9f, z * 0.004f + 3f, 4) - 0.6f) * 3f) * 0.4f;
                w[0] = Mathf.Clamp01(green) * 1.5f;
                float fields = Mathf.Clamp01(1f - ((new Vector2(x, z) - GVillageXZ).magnitude - 160f) / 140f);
                if (fields > 0f && slope < 7f)
                {
                    int type = FieldType(x, z, out float edge);
                    System.Array.Clear(fw, 0, fw.Length);
                    fw[type] = 1f;
                    for (int k = 0; k < w.Length; k++) w[k] = Mathf.Lerp(w[k], Mathf.Lerp(fw[k], k == 1 ? 1f : 0f, Mathf.Clamp01(1f - edge / 2f)), fields);
                }
                float rock = Mathf.Clamp01((slope - 20f) / 10f) + Mathf.Clamp01((Fbm(x * 0.01f, z * 0.01f - 6f, 3) - 0.66f) * 4f) * (x < -400f ? 1f : 0.15f);
                rock = Mathf.Clamp01(rock);
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - rock;
                w[4] += rock;
                // göl dibi: beyaz kalker kumu (turkuaz renk buradan gelir)
                float bed = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.98f, 1.12f, lr));
                bed = Mathf.Max(bed, 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(2.5f, 4.5f, cd)) * (lr > 0.9f ? 1f : 0f));
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - bed;
                w[5] += bed;
                float rd = RoadDistance(roads, new Vector2(x, z));
                float road = Mathf.Clamp01(1f - (rd - 2.6f) / 1.6f);
                float park = Mathf.Clamp01(1f - ((new Vector2(x, z) - (LakeXZ + new Vector2(10f, -78f))).magnitude - 16f) / 4f);
                float pad = Mathf.Clamp01(1f - ((new Vector2(x, z) - new Vector2(-30f, -4f)).magnitude - 16f) / 4f)
                          + Mathf.Clamp01(1f - ((new Vector2(x, z) - JammerXZ).magnitude - 12f) / 4f)
                          + Mathf.Clamp01(1f - Mathf.Max(Mathf.Abs(x - TroutXZ.x) - 46f, Mathf.Abs(z - TroutXZ.y) - 30f) / 4f);
                float g = Mathf.Clamp01(road + park + pad);
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - g;
                w[6] += g;
            }
            bool Free(float x, float z) => RoadDistance(roads, new Vector2(x, z)) > 6f && new Vector2(x, z).magnitude > 90f
                                           && (new Vector2(x, z) - GVillageXZ).magnitude > 75f && (new Vector2(x, z) - JammerXZ).magnitude > 30f
                                           && (Mathf.Abs(x - TroutXZ.x) > 52f || Mathf.Abs(z - TroutXZ.y) > 36f);
            void Plant(Planter pl, TerrainData td)
            {
                // gölün çevresinde söğüt halkası ve kavaklar (kıyıdan 6-30 m geride)
                for (int k = 0; k < 140; k++)
                {
                    float a = pl.R() * 6.28f, rr = 1.12f + pl.R() * 0.5f;
                    float ca = Mathf.Cos(LakeYaw * Mathf.Deg2Rad), sa = Mathf.Sin(LakeYaw * Mathf.Deg2Rad);
                    float u = Mathf.Cos(a) * LakeA * rr, v = Mathf.Sin(a) * LakeB * rr * 1.25f;
                    float x = LakeXZ.x + u * ca - v * sa, z = LakeXZ.y + u * sa + v * ca;
                    if (!Free(x, z) || (new Vector2(x, z) - (LakeXZ + new Vector2(10f, -78f))).magnitude < 24f) continue;
                    if (pl.R() < 0.55f) pl.Willow(x, z, 0.8f + 0.35f * pl.R());
                    else pl.Poplar(x, z, 0.85f + 0.3f * pl.R());
                }
                // dere boyunca kavak sıraları ve söğütler
                for (int i = 4; i < CreekLine.Count; i++)
                {
                    var c = CreekLine[i];
                    var d = (CreekLine[Mathf.Min(i + 1, CreekLine.Count - 1)] - CreekLine[i - 1]).normalized;
                    var n = new Vector2(-d.y, d.x);
                    for (int side = -1; side <= 1; side += 2)
                    {
                        if (pl.R() < 0.45f) continue;
                        var q = c + n * side * (7f + pl.R() * 14f);
                        if (!Free(q.x, q.y)) continue;
                        if (pl.R() < 0.7f) pl.Poplar(q.x, q.y, 0.85f + 0.35f * pl.R());
                        else pl.Willow(q.x, q.y, 0.8f + 0.3f * pl.R());
                    }
                }
                // bozkırda seyrek çalı ve kaya, sırtta kaya; köy çevresinde birkaç ağaç
                for (int k = 0; k < 60000 && pl.Count < 6000; k++)
                {
                    float x = (pl.R() - 0.5f) * 2300f, z = (pl.R() - 0.5f) * 2300f;
                    if (!Free(x, z) || LakeR(x, z) < 1.12f || CreekDist(x, z) < 6f) continue;
                    float sl = td.GetSteepness(x / TerrainSize + 0.5f, z / TerrainSize + 0.5f);
                    float vd = (new Vector2(x, z) - GVillageXZ).magnitude;
                    if (vd < 220f && pl.R() < 0.06f) pl.Poplar(x, z, 0.9f);
                    else if (sl < 30f && pl.R() < (x < -420f ? 0.12f : 0.045f))
                    {
                        if (pl.R() < 0.6f) pl.Shrub(x, z, 0.7f + 0.5f * pl.R());
                        else pl.Rock(x, z, 0.6f + pl.R() * (x < -420f ? 1.8f : 0.8f));
                    }
                }
            }
            var t = BuildRegionTerrain("Gokpinar", root, GokpinarOrigin, "_gokpinar", HeightAtGokpinar, layers, Paint, Plant, prefabs, 1500);

            // Göl suyu: HDRP havuz yüzeyi (kostik ışık, dibe kadar berrak, kıyıda turkuaz, ortada koyu mavi)
            var lake = BuildWaterSurface("GokpinarGolu_Su", "gokpinar", root, GokpinarOrigin + new Vector3(LakeXZ.x, LakeLevelY, LakeXZ.y),
                                         WaterSurfaceType.Pool, new Vector2(2f * LakeA + 30f, 2f * LakeB + 30f));
            ApplyPreset(lake, "ApplyWaterPoolPreset");
            lake.geometryType = WaterGeometryType.Quad;
            lake.transform.rotation = Quaternion.Euler(0f, -LakeYaw, 0f);
            lake.underWater = false;
            lake.refractionColor = new Color(0.25f, 0.92f, 0.88f).linear;
            lake.scatteringColor = new Color(0.05f, 0.8f, 0.78f).linear;
            lake.absorptionDistance = 18f;                // çok berrak: dip 15 m'den görünür
            lake.maxRefractionDistance = 2.5f;
            lake.ambientScattering = 0.85f;
            lake.heightScattering = 0f;
            lake.directLightBodyScattering = 0.55f;
            lake.caustics = true;
            lake.causticsIntensity = 0.7f;
            lake.ripplesWindSpeed = 4f;
            lake.startSmoothness = 0.96f;
            lake.endSmoothness = 0.92f;

            // Dere ve alabalık havuzları
            BuildCreek("GokpinarDeresi_Su", root, GokpinarOrigin, CreekLine, 3.2f,
                       c => HeightAtGokpinar(c.x + 6f, c.y) - BaseHeight - 0.5f, ClearWaterMaterial("MAT_GolSuyu", new Color(0.05f, 0.32f, 0.33f), 0.35f));
            BuildTroutFarm(prefabs, root, t);
            BuildGokpinarLakeside(prefabs, root, t);
            BuildGokpinarVillage(prefabs, root, t);
            BuildRegionFarTiles("Gokpinar", root, GokpinarOrigin, t, layers, FarHeightAtGokpinar, Paint,
                (pl, x, z, sl) => { if (sl < 28f && pl.R() < 0.025f) pl.Shrub(x, z, 1.2f); }, prefabs, 1501, 700);
        }

        static void ApplyPreset(WaterSurface ws, string method)
        {
            var t = typeof(WaterSurface).Assembly.GetType("UnityEngine.Rendering.HighDefinition.WaterSurfacePresets");
            var m = t?.GetMethod(method, BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
            try { m?.Invoke(null, new object[] { ws }); }
            catch (System.Exception e) { Debug.LogWarning("[SuruIHA] Su ön ayarı: " + e.Message); }
        }

        // Alabalık çiftliği: beton kenarlı dikdörtgen havuzlar ve küçük bina
        static void BuildTroutFarm(Prefabs p, Transform root, Terrain t)
        {
            var farm = new GameObject("AlabalikCiftligi").transform;
            farm.SetParent(root, false);
            var concrete = AssetDatabase.LoadAssetAtPath<Material>($"{Root}/Materials/MAT_Concrete.mat");
            var water = ClearWaterMaterial("MAT_HavuzSuyu", new Color(0.04f, 0.2f, 0.2f), 0.25f);
            var c0 = GokpinarOrigin + new Vector3(TroutXZ.x, 0f, TroutXZ.y);
            float y = t.SampleHeight(c0) + t.transform.position.y;
            void Box(Vector3 local, Vector3 size, Material m)
            {
                var g = GameObject.CreatePrimitive(PrimitiveType.Cube);
                Object.DestroyImmediate(g.GetComponent<Collider>());
                g.transform.SetParent(farm, false);
                g.transform.position = c0 + local + Vector3.up * y;
                g.transform.localScale = size;
                g.GetComponent<Renderer>().sharedMaterial = m;
            }
            for (int col = 0; col < 2; col++)
            for (int row = 0; row < 4; row++)
            {
                var c = new Vector3(-20f + col * 40f, 0f, -21f + row * 14f);
                Box(c + new Vector3(0f, -0.4f, 0f), new Vector3(32f, 1.6f, 10f), concrete);          // havuz kenarı
                Box(c + new Vector3(0f, 0.42f, 0f), new Vector3(30.6f, 0.05f, 8.6f), water);           // su
            }
            Box(new Vector3(0f, -0.3f, -42f), new Vector3(70f, 0.8f, 6f), concrete);                 // kanal kenarı
            PlaceOn(p, "House_1", farm, t, c0 + new Vector3(52f, 0f, -38f), 90f);
        }

        // Göl kıyısı: ahşap kameriye, yürüyüş iskelesi, otopark kenarında ağaçlar
        static void BuildGokpinarLakeside(Prefabs p, Transform root, Terrain t)
        {
            var side = new GameObject("GolKiyisi").transform;
            side.SetParent(root, false);
            float a = LakeYaw * Mathf.Deg2Rad;
            Vector2 OnShore(float ang, float rr) =>
                LakeXZ + new Vector2(Mathf.Cos(ang) * LakeA * rr * Mathf.Cos(a) - Mathf.Sin(ang) * LakeB * rr * Mathf.Sin(a),
                                     Mathf.Cos(ang) * LakeA * rr * Mathf.Sin(a) + Mathf.Sin(ang) * LakeB * rr * Mathf.Cos(a));
            var k = OnShore(1.9f, 1.45f);
            PlaceOn(p, "Yapi_Kameriye", side, t, GokpinarOrigin + new Vector3(k.x, 0f, k.y), 20f, 0.2f);
            var k2 = OnShore(0.9f, 1.5f);
            PlaceOn(p, "Yapi_Kameriye", side, t, GokpinarOrigin + new Vector3(k2.x, 0f, k2.y), -10f, 0.2f);
            // güney kıyısında suyun üstünden geçen ahşap iskele (göl yüzeyinin 0,5 m üstünde)
            if (p.named.TryGetValue("Yapi_AhsapIskele", out var pf))
            {
                for (int i = 0; i < 6; i++)
                {
                    float ang = -1.25f - i * 0.26f;
                    var c = OnShore(ang, 1.0f);
                    var c2 = OnShore(ang - 0.26f, 1.0f);
                    var d = c2 - c;
                    var g = (GameObject)PrefabUtility.InstantiatePrefab(pf, side);
                    var mid = (c + c2) / 2f;
                    g.transform.SetPositionAndRotation(GokpinarOrigin + new Vector3(mid.x, LakeLevelY - 0.1f, mid.y),
                                                       Quaternion.Euler(0f, Mathf.Atan2(-d.y, d.x) * Mathf.Rad2Deg, 0f));
                    g.transform.localScale = new Vector3(d.magnitude / 10f + 0.05f, 1f, 1f);
                }
            }
            GameObjectUtility.SetStaticEditorFlags(side.gameObject, StaticEditorFlags.BatchingStatic);
        }

        static void BuildGokpinarVillage(Prefabs p, Transform root, Terrain t)
        {
            if (p.houses.Count == 0) return;
            var v = new GameObject("GokpinarKoyu").transform;
            v.SetParent(root, false);
            var rng = new System.Random(58);
            for (int k = 0; k < 16; k++)
            {
                float a = k * 1.1f + (float)rng.NextDouble() * 0.5f, r = 20f + 7f * k;
                var pos = GVillageXZ + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r * 0.7f;
                var world = GokpinarOrigin + new Vector3(pos.x, 0f, pos.y);
                var h = (GameObject)PrefabUtility.InstantiatePrefab(p.houses[rng.Next(p.houses.Count)], v);
                h.transform.SetPositionAndRotation(new Vector3(world.x, t.SampleHeight(world) + t.transform.position.y, world.z),
                    Quaternion.Euler(0f, 10f + 90f * rng.Next(4) + (float)(rng.NextDouble() - 0.5) * 10f, 0f));
            }
            GameObjectUtility.SetStaticEditorFlags(v.gameObject, StaticEditorFlags.BatchingStatic);
        }
    }
}
