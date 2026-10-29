using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace SuruIHA.EditorTools
{
    // Akdeniz kıyısı: ana araziden 12 km kuzeydoğuda altıncı harita. Kuzeyde açık deniz (HDRP okyanus benzetimi: dalga,
    // köpük, kıyıda turkuaz sığlık, açıkta koyu lacivert), güneyde kızılçam ormanlı tepeler. Ortada kumlu bir koy ve küçük
    // balıkçı limanı (mendirek, iskele, tekneler), iki yanda kalker yalıyarlar, doğudaki burunda deniz feneri, koyun
    // üstündeki yamaçta beyaz badanalı kıyı evleri ve zeytinlikler. Görev alanının kuzey yarısı denizin üstündedir:
    // Python'a giden yükseklik haritası deniz yüzeyinin altına inmez (İHA'lar suyun üstünde kalır). --region deniz
    public static partial class SuruIHASetup
    {
        static Vector3 SeaOrigin => SwarmRegions.SeaOffset;
        const float SeaBase = 60f;                                  // bu bölgede üssün arazi yüksekliği (deniz dibi derin olsun)
        static float SeaY => SwarmRegions.SeaLevel;                 // deniz yüzeyi (dünya y'si, bölgenin tabanına göre)

        // Kıyı çizgisi: batıda koy (kumsal), doğuda burun
        static float CoastZ(float x) => SwarmRegions.SeaCoastZ(x);   // dalga sesiyle ortak

        static float Cliffness(float x) => Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(150f, 260f, Mathf.Abs(x + 120f)));

        // y (dünya, bölge tabanına göre) -> arazi yüksekliği
        public static float HeightAtDeniz(float x, float z)
        {
            float d = CoastZ(x) - z;                                // >0 kara, <0 deniz
            // kıyı düzlüğü: üs (0, 0) y=0 civarında; içerilere doğru hafifçe yükselir
            float plateau = 0.5f + 7f * (Fbm(x * 0.003f + 8f, z * 0.003f - 1f, 4) - 0.5f) + 0.02f * Mathf.Max(0f, d - 520f);
            float c = Cliffness(x);
            float y;
            if (d >= 0f)
            {
                float beach = Mathf.Lerp(SeaY - 0.4f, plateau, Mathf.SmoothStep(0f, 1f, d / 170f));
                float top = plateau + 2f + 14f * Fbm(x * 0.006f + 2f, 5f, 3);       // yalıyar yer yer alçalır, yer yer yükselir
                float cliff = Mathf.Lerp(SeaY - 0.8f, top, Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(1.5f, 10f + 16f * Fbm(x * 0.02f, 3f, 2), d)));
                y = Mathf.Lerp(beach, cliff, c);
                // güneyde kızılçam ormanlı tepeler
                y += 160f * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(-250f, -1150f, z)) * (0.55f + 0.9f * Fbm(x * 0.0028f, z * 0.0028f + 9f, 4));
                y += Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(820f, 1180f, Mathf.Abs(x))) * 90f * Fbm(x * 0.003f + 3f, z * 0.003f, 3) * Mathf.Clamp01(d / 200f);
            }
            else
            {
                // deniz dibi: koyda sığ ve kumlu (turkuaz), yalıyarların önünde hızla derinleşir
                float depth = Mathf.Lerp(0.6f + 0.055f * -d, 5f + 0.13f * -d, c) + 1.5f * (Fbm(x * 0.01f, z * 0.01f, 2) - 0.5f);
                y = SeaY - Mathf.Min(depth, 52f);
            }
            return Mathf.Clamp(y + SeaBase, 1f, TerrainHeight - 5f);
        }

        static float FarHeightAtDeniz(float x, float z)
        {
            float o = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) - TerrainSize / 2;
            float d = CoastZ(x) - z;
            float ridge = 1f - Mathf.Abs(Fbm(x * 0.0009f + 41f, z * 0.0009f - 7f, 5) * 2f - 1f);
            float up = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0f, 800f, o)) * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(150f, 900f, d));
            return Mathf.Max(HeightAtDeniz(x, z) + up * (220f + 520f * ridge), 1f);   // Toroslar güneyde
        }

        // Katmanlar: 0 maki, 1 kuru ot, 2 orman toprağı, 3 anız, 4 kalker kaya, 5 kum ve çakıl, 6 yol
        static TerrainLayer[] SeaLayers() => new[]
        {
            Layer("AMaki", "Ter_Cimen", new Color(0.29f, 0.36f, 0.16f), new Color(0.2f, 0.27f, 0.1f), 6f, 0.05f, 61, "aerial_grass_rock", 15f,
                  new Color(0.9f, 0.98f, 0.85f)),
            Layer("AKuruOt", "Ter_Bozkir", new Color(0.55f, 0.5f, 0.31f), new Color(0.4f, 0.36f, 0.21f), 7f, 0.04f, 62, "withered_grass", 7f,
                  new Color(0.85f, 0.78f, 0.6f)),
            Layer("AOrman", "Ter_Tarla", new Color(0.42f, 0.3f, 0.2f), new Color(0.3f, 0.22f, 0.15f), 9f, 0.06f, 63, "dry_ground_01", 8f,
                  new Color(0.95f, 0.78f, 0.62f)),
            Layer("AAniz", "Ter_Aniz", new Color(0.7f, 0.6f, 0.4f), new Color(0.55f, 0.46f, 0.3f), 7f, 0.05f, 64, "withered_grass", 4f,
                  new Color(1f, 0.88f, 0.62f)),
            Layer("AKaya", "Ter_Kaya", new Color(0.66f, 0.63f, 0.58f), new Color(0.5f, 0.48f, 0.44f), 20f, 0.1f, 65, "aerial_rocks_02", 26f,
                  new Color(1.12f, 1.12f, 1.1f)),     // gri kalker (Toroslar): kumlu kahve görünmesin
            Layer("AKum", "Ter_Cakil", new Color(0.85f, 0.78f, 0.62f), new Color(0.7f, 0.64f, 0.5f), 4f, 0.08f, 66, "gravelly_sand", 4f,
                  new Color(1.3f, 1.18f, 0.98f), 0.3f),
            Layer("AYol", "Ter_Cakil", new Color(0.55f, 0.5f, 0.42f), new Color(0.4f, 0.36f, 0.3f), 5f, 0.08f, 67, "dirt_aerial_02", 5f),
        };

        static readonly Vector2 SeaVillageXZ = new Vector2(-150f, 250f);

        static List<Vector2[]> SeaRoads()
        {
            var coast = new List<Vector2>();
            for (float x = -1180f; x <= 1180f; x += 40f) coast.Add(new Vector2(x, Mathf.Min(CoastZ(x) - 130f, 420f) + 15f * Mathf.Sin(x * 0.008f)));
            var down = new List<Vector2> { new Vector2(-30f, -10f), new Vector2(-60f, 140f), SeaVillageXZ, new Vector2(-90f, CoastZ(-90f) - 30f) };
            var lh = new List<Vector2> { new Vector2(300f, CoastZ(300f) - 120f), new Vector2(390f, CoastZ(390f) - 60f), new Vector2(430f, CoastZ(430f) - 30f) };
            var jam = new List<Vector2>();
            for (int k = 0; k <= 30; k++) jam.Add(Vector2.Lerp(new Vector2(-30f, -10f), JammerXZ + new Vector2(-12f, -8f), k / 30f));
            return new List<Vector2[]> { Dense(coast), Dense(down), Dense(lh), jam.ToArray() };
        }

        static void BuildSeaRegion(Prefabs prefabs)
        {
            var root = new GameObject("AkdenizKiyisi").transform;
            var roads = SeaRoads();
            var layers = SeaLayers();
            float H(float x, float z) => HeightAtDeniz(x, z) - SeaBase;      // dünya y'si
            void Paint(float x, float z, float slope, float[] w)
            {
                float d = CoastZ(x) - z, y = H(x, z);
                // kara: kızılçam ormanı toprağı ve maki, açıklıklarda kuru ot
                float forest = Mathf.Clamp01((Fbm(x * 0.004f + 5f, z * 0.004f - 8f, 4) - 0.38f) * 3f) * Mathf.InverseLerp(60f, 160f, d);
                // Sarp yamaçta çam azalır, toprağı maki (yeşil çalı) örter: dağ çıplak kum tepesi gibi durmasın
                float steep = Mathf.Clamp01((slope - 16f) / 12f);
                w[2] = forest * (1f - 0.8f * steep);
                w[0] = (1f - forest) * (0.6f + 0.6f * Fbm(x * 0.012f, z * 0.012f + 3f, 3)) + forest * 0.8f * steep * 1.3f;
                w[1] = (1f - forest) * 0.5f;
                if ((new Vector2(x, z) - SeaVillageXZ).magnitude < 200f && slope < 12f) w[3] += 0.6f * Fbm(x * 0.02f, z * 0.02f, 2);
                // Kalker kaya yalnızca çok sarp yerde ve yer yer çıkıntılarda; sarp yamacın gerisini maki örter
                float rock = Mathf.Clamp01((slope - 36f) / 12f) * (0.6f + 0.4f * Fbm(x * 0.02f + 4f, z * 0.02f, 3))
                           + Mathf.Clamp01((Fbm(x * 0.008f, z * 0.008f - 2f, 3) - 0.68f) * 4f) * 0.5f;
                rock = Mathf.Clamp01(rock);
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - rock;
                w[4] += rock;
                // kıyı: koyda kum, yalıyar diplerinde çakıl ve kaya; deniz dibi kum (sığlıkta turkuaz)
                float sand = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(SeaY + 1.5f, SeaY + 4f, y));
                float cl = Cliffness(x);
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - sand;
                w[5] += sand * (1f - 0.5f * cl);
                w[4] += sand * 0.5f * cl;
                float rd = RoadDistance(roads, new Vector2(x, z));
                float road = Mathf.Clamp01(1f - (rd - 2.8f) / 1.6f) * (d > 20f ? 1f : 0f);
                float pad = Mathf.Clamp01(1f - ((new Vector2(x, z) - new Vector2(-30f, -4f)).magnitude - 16f) / 4f)
                          + Mathf.Clamp01(1f - ((new Vector2(x, z) - JammerXZ).magnitude - 12f) / 4f);
                float g = Mathf.Clamp01(road + pad);
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - g;
                w[6] += g;
            }
            bool Free(float x, float z) => RoadDistance(roads, new Vector2(x, z)) > 6f && new Vector2(x, z).magnitude > 90f
                                           && (new Vector2(x, z) - JammerXZ).magnitude > 30f && (new Vector2(x, z) - SeaVillageXZ).magnitude > 70f;
            void Plant(Planter pl, TerrainData td)
            {
                for (int k = 0; k < 140000 && pl.Count < 9000; k++)
                {
                    float x = (pl.R() - 0.5f) * 2300f, z = (pl.R() - 0.5f) * 2300f;
                    float d = CoastZ(x) - z;
                    if (d < 14f || !Free(x, z)) continue;
                    float sl = td.GetSteepness(x / TerrainSize + 0.5f, z / TerrainSize + 0.5f);
                    if (sl > 36f) continue;
                    float forest = Mathf.Clamp01((Fbm(x * 0.004f + 5f, z * 0.004f - 8f, 4) - 0.38f) * 3f) * Mathf.InverseLerp(60f, 160f, d);
                    float vd = (new Vector2(x, z) - SeaVillageXZ).magnitude;
                    if (vd < 260f && sl < 12f && pl.R() < 0.25f)
                        pl.Oak(Mathf.Round(x / 9f) * 9f, Mathf.Round(z / 9f) * 9f, 0.7f + 0.15f * pl.R(), 0.55f + 0.1f * pl.R());   // zeytinlik
                    else if (pl.R() < forest * 0.9f) pl.Pine(x, z, 0.8f + 0.45f * pl.R());                                          // kızılçam
                    else if (pl.R() < 0.18f) pl.Shrub(x, z, 0.7f + 0.6f * pl.R());                                                 // maki
                    else if (pl.R() < 0.02f) pl.Rock(x, z, 0.6f + pl.R());
                }
                // yalıyar diplerinde iri kayalar
                for (float x = -1150f; x < 1150f; x += 9f)
                {
                    if (Cliffness(x) < 0.5f || pl.R() < 0.4f) continue;
                    float z = CoastZ(x) + 1f + pl.R() * 7f;                          // denize düşmüş kayalar (dipte, suyun içinde)
                    pl.Rock(x, z, 1.1f + 1.6f * pl.R());
                }
            }
            var t = BuildRegionTerrain("Akdeniz", root, SeaOrigin, "_deniz", HeightAtDeniz, layers, Paint, Plant, prefabs, 1453,
                                       SeaOrigin.y + SeaY, SeaBase);

            // Deniz: HDRP okyanus (sonsuz yüzey, gerçek dalga ve köpük); kıyıda sığlık turkuaz, açıkta lacivert
            var sea = BuildWaterSurface("AkdenizSuyu", "deniz", root, SeaOrigin + Vector3.up * SeaY, WaterSurfaceType.OceanSeaLake, Vector2.zero);
            ApplyPreset(sea, "ApplyWaterOceanPreset");
            sea.geometryType = WaterGeometryType.Infinite;
            sea.largeWindSpeed = 16f;                 // hafif rüzgâr: kısa, yumuşak dalgalar
            sea.largeChaos = 0.85f;
            sea.ripplesWindSpeed = 9f;
            sea.refractionColor = new Color(0.0f, 0.52f, 0.62f).linear;
            sea.scatteringColor = new Color(0.0f, 0.3f, 0.38f).linear;
            sea.absorptionDistance = 7f;
            sea.maxRefractionDistance = 1.2f;
            sea.caustics = true;
            sea.causticsIntensity = 0.5f;
            sea.foam = true;
            sea.simulationFoamAmount = 0.25f;

            BuildSeaVillage(prefabs, root, t);
            BuildHarbor(prefabs, root, t);
            var lx = 430f;
            PlaceOn(prefabs, "Yapi_Fener", root, t, SeaOrigin + new Vector3(lx, 0f, CoastZ(lx) - 26f), 160f, 0.3f);
            BuildRegionVolume("Akdeniz", root, SeaOrigin, prof =>
            {
                var fog = GetLocal<Fog>(prof);
                SetParam(fog, "enabled", true);
                SetParam(fog, "meanFreePath", 3200f);
                SetParam(fog, "albedo", new Color(0.86f, 0.93f, 1f));     // deniz pusu
                var wb = GetLocal<WhiteBalance>(prof);
                SetParam(wb, "temperature", 2f);
                var color = GetLocal<ColorAdjustments>(prof);
                SetParam(color, "saturation", 6f);
            });
            BuildRegionFarTiles("Akdeniz", root, SeaOrigin, t, layers, FarHeightAtDeniz,
                (x, z, sl, w) => Paint(x, z, sl, w),
                (pl, x, z, sl) =>
                {
                    if (CoastZ(x) - z > 60f && sl < 40f && pl.R() < 0.65f) pl.Pine(x, z, 1.1f);   // kızılçam sarp yamaçta da tutunur
                }, prefabs, 1454, 1400, SeaBase);
        }

        // Koyun üstündeki yamaçta kıyı evleri (kat kat)
        static void BuildSeaVillage(Prefabs p, Transform root, Terrain t)
        {
            var v = new GameObject("KiyiKoyu").transform;
            v.SetParent(root, false);
            var rng = new System.Random(34);
            var placed = new List<Vector2>();
            for (int k = 0; k < 600 && placed.Count < 22; k++)
            {
                var c = SeaVillageXZ + new Vector2(((float)rng.NextDouble() - 0.5f) * 300f, ((float)rng.NextDouble() - 0.5f) * 180f);
                if (CoastZ(c.x) - c.y < 45f) continue;
                if (t.terrainData.GetSteepness(c.x / TerrainSize + 0.5f, c.y / TerrainSize + 0.5f) > 16f) continue;
                bool near = false;
                foreach (var q in placed) if ((q - c).sqrMagnitude < 15f * 15f) { near = true; break; }
                if (near) continue;
                placed.Add(c);
                // evler denize (kuzeye) bakar
                PlaceOn(p, $"Yapi_SahilEv_{rng.Next(3)}", v, t, SeaOrigin + new Vector3(c.x, 0f, c.y), ((float)rng.NextDouble() - 0.5f) * 20f, 0.3f);
            }
            GameObjectUtility.SetStaticEditorFlags(v.gameObject, StaticEditorFlags.BatchingStatic);
        }

        // Balıkçı limanı: kumsalın doğusunda taş mendirek, beton iskele, demirli tekneler
        static void BuildHarbor(Prefabs p, Transform root, Terrain t)
        {
            var h = new GameObject("BalikciLimani").transform;
            h.SetParent(root, false);
            var concrete = AssetDatabase.LoadAssetAtPath<Material>($"{Root}/Materials/MAT_Concrete.mat");
            float sy = SeaOrigin.y + SeaY;
            // iskele: kıyıdan denize 45 m
            float px = -20f, pz0 = CoastZ(px) - 6f;
            var pier = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Object.DestroyImmediate(pier.GetComponent<Collider>());
            pier.name = "Iskele";
            pier.transform.SetParent(h, false);
            pier.transform.position = SeaOrigin + new Vector3(px, SeaY + 0.2f, pz0 + 25f);
            pier.transform.localScale = new Vector3(6f, 2.6f, 52f);
            pier.GetComponent<Renderer>().sharedMaterial = concrete;
            // mendirek: iri kayalardan kavisli set
            if (p.rocks.Count > 0)
            {
                var rng = new System.Random(5);
                for (int i = 0; i < 70; i++)
                {
                    float s = i / 69f;
                    float x = 60f - 110f * s, z = CoastZ(60f) - 4f + 150f * Mathf.Sin(s * 1.4f);
                    var r = (GameObject)PrefabUtility.InstantiatePrefab(p.rocks[rng.Next(p.rocks.Count)], h);
                    r.transform.SetPositionAndRotation(SeaOrigin + new Vector3(x + (float)rng.NextDouble() * 4f, SeaY - 1.2f, z + (float)rng.NextDouble() * 4f),
                                                       Quaternion.Euler(0f, (float)rng.NextDouble() * 360f, 0f));
                    r.transform.localScale = Vector3.one * (3.2f + 2.2f * (float)rng.NextDouble());
                }
                var tip = SeaOrigin + new Vector3(-50f, sy + 0.5f, CoastZ(60f) - 4f + 150f * Mathf.Sin(1.4f));
                var beacon = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                Object.DestroyImmediate(beacon.GetComponent<Collider>());
                beacon.name = "MendirekFeneri";
                beacon.transform.SetParent(h, false);
                beacon.transform.position = tip + Vector3.up * 3f;
                beacon.transform.localScale = new Vector3(1.6f, 3.5f, 1.6f);
                var red = AssetDatabase.LoadAssetAtPath<Material>($"{Root}/Materials/MAT_BoyaKirmizi.mat");
                if (red != null) beacon.GetComponent<Renderer>().sharedMaterial = red;
            }
            // tekneler: iskele boyunca ve açıkta
            var spots = new (Vector3 pos, float yaw, int kind)[]
            {
                (new Vector3(px - 7f, 0f, pz0 + 18f), 90f, 0), (new Vector3(px + 7.5f, 0f, pz0 + 30f), 92f, 1), (new Vector3(px - 7.5f, 0f, pz0 + 38f), 85f, 0),
                (new Vector3(-280f, 0f, CoastZ(-280f) + 160f), 30f, 1), (new Vector3(220f, 0f, CoastZ(220f) + 320f), -60f, 1),
                (new Vector3(-80f, 0f, CoastZ(-80f) + 90f), 120f, 0),
            };
            foreach (var s in spots)
            {
                if (!p.named.TryGetValue($"Yapi_Tekne_{s.kind}", out var pf)) continue;
                var b = (GameObject)PrefabUtility.InstantiatePrefab(pf, h);
                b.transform.SetPositionAndRotation(SeaOrigin + new Vector3(s.pos.x, SeaY - 0.35f, s.pos.z), Quaternion.Euler(0f, s.yaw, 0f));
            }
        }
    }
}
