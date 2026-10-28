using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using Object = UnityEngine.Object;

namespace SuruIHA.EditorTools
{
    // Kızılırmak (Sivas): ana araziden 12 km batıda üçüncü harita. Sivas platosunda geniş bir vadi; ortasından
    // kıvrılarak akan kızıl-kahve, alüvyonlu Kızılırmak. Kuzey yakada nehre adını veren kızıl kil yarlar ve plato,
    // güney yakada üs ve sulu tarlalar; kıyılarda kavak ve söğüt sıraları, çakıllı kum adacıkları, bir köprü ve
    // küçük bir köy. Görev alanı nehrin iki yakasını da kapsar. Python bu bölgenin yükseklik haritasını
    // arazi_yukseklik_nehir.bin olarak okur (--region nehir).
    public static partial class SuruIHASetup
    {
        static Vector3 RiverOrigin => SwarmRegions.RiverOffset;
        const float RiverHalf = 26f;             // nehir yatağının yarı genişliği (m)
        const float RiverDepth = 6f;             // yatağın ova tabanına göre derinliği (m)
        const float WaterLevel = SwarmRegions.WaterLevel;
        static readonly Vector2 HamletXZ = new Vector2(-560f, 140f);   // kıyıdaki köy

        // Nehrin orta çizgisi (ırmak sesiyle ortak: SwarmRegions)
        public static float RiverZ(float x) => SwarmRegions.RiverZ(x);

        // Nehre yatay uzaklık (z yönünde; menderesler yumuşak olduğu için yeterli yaklaşıklık)
        static float RiverDist(float x, float z) => z - RiverZ(x);

        // Kuzeydeki kızıl yarın eteği: nehrin kıvrımlarından bağımsız (yukarıdan ikinci bir nehir gibi görünmesin);
        // nehrin yara yaklaştığı yerlerde nehir yarı oyar, gerçek Kızılırmak gibi
        static float BluffZ(float x) => 790f + 70f * Mathf.Sin(x * 0.0021f + 0.7f) + 40f * (Fbm(x * 0.004f + 7f, 3.3f, 3) - 0.5f) * 2f;

        public static float HeightAtNehir(float x, float z)
        {
            float d = RiverDist(x, z);
            float floor = BaseHeight + 1.2f * (Fbm(x * 0.006f + 13f, z * 0.006f - 4f, 3) - 0.5f) * 2f;
            // Yatak: ortada tam derinlik, kıyıya doğru yumuşak şev
            float bed = -RiverDepth * (1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(RiverHalf - 6f, RiverHalf + 10f, Mathf.Abs(d))));
            // Kuzey yakada kızıl yar: 30-45 m'lik dik yamaç, üstünde dalgalı plato
            float db = z - BluffZ(x);
            float bluff = (34f + 10f * Fbm(x * 0.01f, 9.1f, 2)) * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0f, 45f, db));
            float plateau = 30f * Mathf.Pow(Fbm(x * 0.003f + 40f, z * 0.003f - 9f, 4), 1.5f) * Mathf.InverseLerp(45f, 400f, db);
            // Güney yakada üsten sonra hafifçe yükselen bozkır
            float south = 22f * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(-120f, -700f, d + 470f)) * (0.6f + 0.8f * Fbm(x * 0.004f, z * 0.004f + 5f, 3));
            // Kenarda tepeler (ufka doğru)
            float m = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z - 300f));
            float hills = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(900f, 1250f, m)) * 70f * Fbm(x * 0.002f + 5f, z * 0.002f, 4);
            return floor + bed + bluff + plateau + south + hills;
        }

        // Uzak parçalar: vadi nehir boyunca ufka uzanır, iki yanında yükselen tepeler
        static float FarHeightAtNehir(float x, float z)
        {
            float away = Mathf.Abs(RiverDist(x, z));
            float ridge = 1f - Mathf.Abs(Fbm(x * 0.0009f + 51f, z * 0.0009f - 3f, 5) * 2f - 1f);
            return HeightAtNehir(x, z) + Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(900f, 2600f, away)) * (120f + 260f * ridge);
        }

        // Katmanlar: 0 çayır, 1 bozkır, 2 sürülmüş tarla, 3 anız, 4 kızıl toprak (yar), 5 nehir çakılı, 6 köy yolu
        static TerrainLayer[] RiverLayers() => new[]
        {
            Layer("NCayir", "Ter_Cimen", new Color(0.29f, 0.36f, 0.16f), new Color(0.2f, 0.27f, 0.1f), 6f, 0.05f, 21, "aerial_grass_rock", 15f),
            Layer("NBozkir", "Ter_Bozkir", new Color(0.55f, 0.5f, 0.31f), new Color(0.4f, 0.36f, 0.21f), 7f, 0.04f, 22, "withered_grass", 7f,
                  new Color(0.74f, 0.71f, 0.6f)),
            Layer("NTarla", "Ter_Tarla", new Color(0.42f, 0.34f, 0.24f), new Color(0.3f, 0.24f, 0.17f), 9f, 0.06f, 23, "farm_soil", 5f),
            Layer("NAniz", "Ter_Aniz", new Color(0.7f, 0.6f, 0.4f), new Color(0.55f, 0.46f, 0.3f), 7f, 0.05f, 24, "withered_grass", 4f,
                  new Color(1f, 0.88f, 0.62f)),
            Layer("NKizil", "Ter_Tarla", new Color(0.55f, 0.27f, 0.17f), new Color(0.4f, 0.2f, 0.12f), 8f, 0.05f, 25, "red_laterite_soil_stones", 6f),
            Layer("NKiyi", "Ter_Cakil", new Color(0.55f, 0.52f, 0.46f), new Color(0.4f, 0.38f, 0.33f), 5f, 0.08f, 26, "river_small_rocks", 5f),
            Layer("NYol", "Ter_Cakil", new Color(0.45f, 0.35f, 0.3f), new Color(0.35f, 0.27f, 0.22f), 5f, 0.08f, 27, "terrain_red_01", 4f),
        };

        static List<Vector2[]> RiverRoads()
        {
            // Üsten kuzeye: köprüden geçip yarın arasından platoya çıkan yol; batıya köye giden yol
            var a = new List<Vector2>();
            for (int k = 0; k <= 60; k++)
            {
                float t = k / 60f;
                var p = Vector2.Lerp(new Vector2(-40f, -1150f), new Vector2(-40f, -30f), t);
                p.x += Mathf.Sin(t * 6f) * 40f * (1f - t);
                a.Add(p);
            }
            float zc = RiverZ(BridgeX);
            var b = new List<Vector2>
            {
                new Vector2(-40f, -30f), new Vector2(-20f, 150f), new Vector2(BridgeX, zc - 90f), new Vector2(BridgeX, zc - 46f),
            };
            var b2 = new List<Vector2> { new Vector2(BridgeX, zc + 46f), new Vector2(BridgeX + 10f, zc + 140f), new Vector2(60f, zc + 330f),
                                         new Vector2(120f, zc + 480f), new Vector2(160f, 1150f) };
            var c = new List<Vector2>();
            for (int k = 0; k <= 30; k++) c.Add(Vector2.Lerp(new Vector2(-30f, -10f), JammerXZ + new Vector2(-12f, -8f), k / 30f));
            var v = new List<Vector2> { new Vector2(-40f, -30f), new Vector2(-240f, 40f), new Vector2(-420f, 110f), HamletXZ };
            return new List<Vector2[]> { Dense(a), Dense(b), Dense(b2), c.ToArray(), Dense(v) };
        }

        const float BridgeX = -10f;

        // Seyrek noktalı yolu 5 m aralıklı noktalara böler (yol uzaklığı noktalardan hesaplanır)
        static Vector2[] Dense(List<Vector2> pts)
        {
            var o = new List<Vector2>();
            for (int i = 0; i + 1 < pts.Count; i++)
            {
                int n = Mathf.Max(1, Mathf.CeilToInt((pts[i + 1] - pts[i]).magnitude / 5f));
                for (int k = 0; k < n; k++) o.Add(Vector2.Lerp(pts[i], pts[i + 1], k / (float)n));
            }
            o.Add(pts[pts.Count - 1]);
            return o.ToArray();
        }

        static void BuildRiverRegion(Prefabs prefabs)
        {
            var root = new GameObject("Kizilirmak").transform;
            int res = 1025;
            var td = new TerrainData { heightmapResolution = res };
            td.size = new Vector3(TerrainSize, TerrainHeight, TerrainSize);
            string tdPath = $"{Root}/Terrain/NehirAraziVerisi.asset";
            AssetDatabase.DeleteAsset(tdPath);
            AssetDatabase.CreateAsset(td, tdPath);
            var heights = new float[res, res];
            for (int j = 0; j < res; j++)
            for (int i = 0; i < res; i++)
            {
                float x = (i / (float)(res - 1) - 0.5f) * TerrainSize;
                float z = (j / (float)(res - 1) - 0.5f) * TerrainSize;
                heights[j, i] = Mathf.Clamp01(HeightAtNehir(x, z) / TerrainHeight);
            }
            td.SetHeights(0, 0, heights);

            var layers = RiverLayers();
            td.terrainLayers = layers;
            int amRes = 2048;
            td.alphamapResolution = amRes;
            var am = new float[amRes, amRes, layers.Length];
            var roads = RiverRoads();
            var w = new float[layers.Length];
            var fw = new float[layers.Length];
            for (int j = 0; j < amRes; j++)
            for (int i = 0; i < amRes; i++)
            {
                float u = i / (float)(amRes - 1), v = j / (float)(amRes - 1);
                float x = (u - 0.5f) * TerrainSize, z = (v - 0.5f) * TerrainSize;
                float slope = td.GetSteepness(u, v);
                float d = RiverDist(x, z);
                System.Array.Clear(w, 0, w.Length);
                // Taban: bozkır; nehre yakın nemli çayırlar
                w[1] = 1f;
                float wet = 1f - Mathf.InverseLerp(40f, 160f, Mathf.Abs(d));
                w[0] = Mathf.Clamp01(wet * (0.6f + 0.6f * Fbm(x * 0.01f, z * 0.01f, 3)))
                     + Mathf.Clamp01((Fbm(x * 0.003f + 11f, z * 0.003f - 7f, 4) - 0.56f) * 3f) * 0.6f;
                // Nehir ovası (nehirle yar arasında, güneyde üsse kadar): sulu tarlalar
                float plainN = 1f - Mathf.InverseLerp(-60f, -20f, z - BluffZ(x));
                float plainS = Mathf.InverseLerp(-560f, -420f, d);
                float plain = Mathf.Clamp01(Mathf.Min(plainN, plainS)) * Mathf.InverseLerp(55f, 90f, Mathf.Abs(d))
                            * (1f - Mathf.Clamp01(1f - ((new Vector2(x, z) - HamletXZ).magnitude - 90f) / 40f));
                if (plain > 0f && slope < 8f)
                {
                    int type = FieldType(x, z, out float edge);
                    System.Array.Clear(fw, 0, fw.Length);
                    fw[type] = 1f;
                    float border = Mathf.Clamp01(1f - edge / 2.2f);
                    for (int k = 0; k < w.Length; k++)
                        w[k] = Mathf.Lerp(w[k], Mathf.Lerp(fw[k], k == 1 ? 1f : 0f, border), plain);
                }
                // Kızıl toprak: yar yüzleri ve aşınmış yamaçlar (Kızılırmak adını bu topraktan alır)
                float red = Mathf.Clamp01((slope - 16f) / 10f)
                          + Mathf.Clamp01((Fbm(x * 0.006f - 21f, z * 0.006f + 33f, 3) - 0.6f) * 3f) * Mathf.InverseLerp(-10f, 40f, z - BluffZ(x)) * 0.7f;
                red = Mathf.Clamp01(red);
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - red;
                w[4] += red;
                // Kıyı: yatak ve şev çakıllı; iç kıvrımlarda kum-çakıl adacıkları
                float bank = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(RiverHalf + 2f, RiverHalf + 14f + 10f * Fbm(x * 0.02f, 1.7f, 2), Mathf.Abs(d)));
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - bank;
                w[5] += bank;
                // Yollar ve tesis alanları
                float rd = RoadDistance(roads, new Vector2(x, z));
                float road = Mathf.Clamp01(1f - (rd - 3f) / 1.8f);
                float pad = Mathf.Clamp01(1f - ((new Vector2(x, z) - new Vector2(-30f, -4f)).magnitude - 16f) / 4f)
                          + Mathf.Clamp01(1f - ((new Vector2(x, z) - JammerXZ).magnitude - 12f) / 4f);
                float g = Mathf.Clamp01(road + pad);
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - g;
                w[6] += g;
                float sum = 0f;
                foreach (var a in w) sum += a;
                for (int k = 0; k < w.Length; k++) am[j, i, k] = w[k] / Mathf.Max(sum, 1e-4f);
            }
            td.SetAlphamaps(0, 0, am);

            // Ağaçlar: kıyılarda kavak sıraları (meşe modeli ince ve uzun ölçeklenir) ve söğütler, tarla sınırlarında
            // kavaklar, bozkırda seyrek meşe ve çalı; yarlarda ve yatakta ağaç yok
            var oaks = prefabs.oaks;
            var protos = oaks.Concat(prefabs.shrubs).Concat(prefabs.rocks).Select(g => new TreePrototype { prefab = g, bendFactor = 0f }).ToArray();
            td.treePrototypes = protos;
            int shrub0 = oaks.Count, rock0 = oaks.Count + prefabs.shrubs.Count;
            var rng = new System.Random(1919);
            float R() => (float)rng.NextDouble();
            var trees = new List<TreeInstance>();
            void Add(int proto, float x, float z, float ws, float hs)
            {
                trees.Add(new TreeInstance
                {
                    prototypeIndex = proto, position = new Vector3(x / TerrainSize + 0.5f, 0f, z / TerrainSize + 0.5f),
                    widthScale = ws, heightScale = hs, rotation = R() * 6.28f, color = Color.white, lightmapColor = Color.white,
                });
            }
            bool Free(float x, float z) => RoadDistance(roads, new Vector2(x, z)) > 7f && new Vector2(x, z).magnitude > 90f
                                           && (new Vector2(x, z) - HamletXZ).magnitude > 70f;
            if (oaks.Count > 0)
            {
                // Kıyı boyunca kavak ve söğüt (iki yaka)
                for (float x = -1180f; x < 1180f; x += 7f)
                for (int side = -1; side <= 1; side += 2)
                {
                    if (R() < 0.35f) continue;
                    float z = RiverZ(x) + side * (RiverHalf + 16f + R() * 26f);
                    if (!Free(x, z) || Mathf.Abs(x - BridgeX) < 25f) continue;
                    bool poplar = R() < 0.65f;
                    float s = 0.8f + 0.4f * R();
                    Add(rng.Next(oaks.Count), x, z, poplar ? 0.42f * s : 1.15f * s, poplar ? 1.85f * s : 0.85f * s);
                }
                // Tarla sınırlarında kavak sıraları
                for (int k = 0; k < 60000 && trees.Count < 5200; k++)
                {
                    float x = (R() - 0.5f) * 2300f, z = (R() - 0.5f) * 2300f;
                    float d = RiverDist(x, z);
                    if (z > BluffZ(x) - 40f || d < -540f || Mathf.Abs(d) < 60f || !Free(x, z)) continue;
                    FieldType(x, z, out float edge);
                    if (edge > 2.5f || R() > 0.5f) continue;
                    float s = 0.85f + 0.35f * R();
                    Add(rng.Next(oaks.Count), x, z, 0.4f * s, 1.9f * s);
                }
            }
            // Bozkır ve plato: seyrek meşe, çalı, kaya
            for (int k = 0; k < 80000 && trees.Count < 8000; k++)
            {
                float u = R(), v = R();
                float x = (u - 0.5f) * TerrainSize, z = (v - 0.5f) * TerrainSize;
                float d = RiverDist(x, z), sl = td.GetSteepness(u, v);
                if (Mathf.Abs(d) < 60f || sl > 30f || !Free(x, z)) continue;
                bool steppe = z > BluffZ(x) + 40f || d < -560f || Mathf.Max(Mathf.Abs(x), Mathf.Abs(z - 300f)) > 900f;
                if (!steppe || R() > 0.35f) continue;
                float r = R();
                if (r < 0.25f && oaks.Count > 0) Add(rng.Next(oaks.Count), x, z, 0.7f + 0.4f * R(), 0.7f + 0.4f * R());
                else if (r < 0.8f && prefabs.shrubs.Count > 0) Add(shrub0 + rng.Next(prefabs.shrubs.Count), x, z, 0.8f + 0.5f * R(), 0.8f + 0.5f * R());
                else if (prefabs.rocks.Count > 0) Add(rock0 + rng.Next(prefabs.rocks.Count), x, z, 0.5f + R(), 0.5f + R());
            }
            td.SetTreeInstances(trees.ToArray(), true);
            PaintGrass(td, prefabs, am, amRes);
            EditorUtility.SetDirty(td);
            AssetDatabase.SaveAssets();

            var go = Terrain.CreateTerrainGameObject(td);
            go.name = "NehirArazi";
            go.transform.SetParent(root, false);
            go.transform.position = RiverOrigin + new Vector3(-TerrainSize / 2, -BaseHeight, -TerrainSize / 2);
            var t = go.GetComponent<Terrain>();
            t.treeDistance = 2500f;
            t.treeBillboardDistance = 2500f;
            t.heightmapPixelError = 1.5f;
            t.basemapDistance = 20000f;
            t.drawInstanced = true;
            t.detailObjectDistance = 220f;
            t.detailObjectDensity = 1f;
            GameObjectUtility.SetStaticEditorFlags(go, StaticEditorFlags.BatchingStatic | StaticEditorFlags.ContributeGI);
            ExportHeightmap(t, RiverOrigin, "_nehir");

            BuildWater(root);
            BuildBridge(root, t);
            BuildHamlet(prefabs, root, t);
            BuildRiverFarTiles(t, layers, prefabs, root);
            Debug.Log($"[SuruIHA] Kızılırmak: {trees.Count} ağaç, çalı ve kaya, {layers.Length} katman");
        }

        // Su yüzeyi: nehir boyunca şerit örgü; kızıl-kahve alüvyonlu, parlak, dalgacıklı (dalgacıklar akar: SwarmWater)
        static void BuildWater(Transform root)
        {
            var verts = new List<Vector3>();
            var uvs = new List<Vector2>();
            var tris = new List<int>();
            float len = 0f, half = RiverHalf + 3f;
            Vector2 prev = Vector2.zero;
            const float x0 = -SwarmRegions.RiverHalfLength, x1 = SwarmRegions.RiverHalfLength, step = 6f;
            for (float x = x0; x <= x1 + 0.01f; x += step)
            {
                var c = new Vector2(x, RiverZ(x));
                if (x > x0) len += (c - prev).magnitude;
                prev = c;
                var tng = new Vector2(1f, (RiverZ(x + 1f) - RiverZ(x - 1f)) / 2f).normalized;
                var nrm = new Vector2(-tng.y, tng.x);
                foreach (int s in new[] { -1, 1 })
                {
                    var p = c + nrm * (s * half);
                    verts.Add(new Vector3(p.x, WaterLevel, p.y));
                    uvs.Add(new Vector2((s + 1) * half / 16f, len / 16f));    // 16 m'de bir doku tekrarı
                }
                int n = verts.Count;
                // Üçgenler yukarı baksın (Unity'de ön yüz saat yönünde): ters dizilirse yüzey üstten görünmez
                if (n >= 4) tris.AddRange(new[] { n - 4, n - 3, n - 2, n - 3, n - 1, n - 2 });
            }
            var mesh = new Mesh { name = "Kizilirmak_Su", indexFormat = IndexFormat.UInt32 };
            mesh.SetVertices(verts);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateNormals();
            mesh.RecalculateTangents();
            mesh.RecalculateBounds();
            string meshPath = $"{Root}/Terrain/Kizilirmak_Su.asset";
            AssetDatabase.DeleteAsset(meshPath);
            AssetDatabase.CreateAsset(mesh, meshPath);

            var go = new GameObject("Kizilirmak_Su");
            go.transform.SetParent(root, false);
            go.transform.position = RiverOrigin;
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = WaterMaterial();
            mr.shadowCastingMode = ShadowCastingMode.Off;
            go.AddComponent<SwarmWater>();
        }

        static Material WaterMaterial()
        {
            string path = $"{Root}/Materials/MAT_Kizilirmak.mat";
            AssetDatabase.DeleteAsset(path);
            var m = new Material(Shader.Find("HDRP/Lit")) { name = "MAT_Kizilirmak" };
            m.SetColor("_BaseColor", new Color(0.5f, 0.33f, 0.22f));      // kızıl-kahve alüvyonlu (sütlü kahve) su
            m.SetFloat("_Smoothness", 0.97f);
            m.SetFloat("_Metallic", 0f);
            m.SetFloat("_CoatMask", 1f);                                    // şeffaf cila katmanı: gök ve kıyı yansısın
            var nm = WaterNormalTexture();
            if (nm != null)
            {
                m.SetTexture("_NormalMap", nm);
                m.SetFloat("_NormalScale", 0.35f);                          // sakin akan su: ince dalgacık
            }
            HDMaterial.ValidateMaterial(m);
            AssetDatabase.CreateAsset(m, path);
            return m;
        }

        // Dikişsiz su dalgacığı normal haritası (akış yönünde uzamış dalgacıklar)
        static Texture2D WaterNormalTexture()
        {
            string path = $"{Root}/Textures/Tex_SuDalga_Normal.png";
            if (AssetDatabase.LoadAssetAtPath<Texture2D>(path) == null)
            {
                const int N = 512;
                var h = new float[N, N];
                for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float u = x / (float)N, v = y / (float)N;
                    h[y, x] = TileFbm(u, v, 6, 5, 91) * 0.7f + TileFbm(u, v, 24, 3, 92) * 0.3f;
                }
                var nm = new Color[N * N];
                for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float dx = h[y, (x + 1) % N] - h[y, (x - 1 + N) % N];
                    float dy = h[(y + 1) % N, x] - h[(y - 1 + N) % N, x];
                    var n = new Vector3(-dx * 5f, -dy * 5f, 1f).normalized;
                    nm[y * N + x] = new Color(n.x * 0.5f + 0.5f, n.y * 0.5f + 0.5f, n.z * 0.5f + 0.5f, 1f);
                }
                WritePng(path, nm, N);
                AssetDatabase.ImportAsset(path);
            }
            var ti = AssetImporter.GetAtPath(path) as TextureImporter;
            if (ti != null && ti.textureType != TextureImporterType.NormalMap)
            {
                ti.textureType = TextureImporterType.NormalMap;
                ti.SaveAndReimport();
            }
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        // Köprü: yoldaki geçişte beton tabliye, ayaklar ve korkuluk
        static void BuildBridge(Transform root, Terrain t)
        {
            var mat = AssetDatabase.LoadAssetAtPath<Material>($"{Root}/Materials/MAT_Concrete.mat");
            var br = new GameObject("Kopru").transform;
            br.SetParent(root, false);
            float zc = RiverZ(BridgeX);
            float deck = BaseHeight - BaseHeight + 2.6f;                    // ova tabanının 2,6 m üstü (yerel)
            br.position = RiverOrigin + new Vector3(BridgeX, deck, zc);
            float tng = (RiverZ(BridgeX + 1f) - RiverZ(BridgeX - 1f)) / 2f;
            br.rotation = Quaternion.Euler(0f, -Mathf.Atan(tng) * Mathf.Rad2Deg, 0f);    // tabliye nehre dik
            void Box(Vector3 p, Vector3 s)
            {
                var g = GameObject.CreatePrimitive(PrimitiveType.Cube);
                Object.DestroyImmediate(g.GetComponent<Collider>());
                g.transform.SetParent(br, false);
                g.transform.localPosition = p;
                g.transform.localScale = s;
                if (mat != null) g.GetComponent<Renderer>().sharedMaterial = mat;
            }
            const float L = 2f * RiverHalf + 40f;
            Box(Vector3.zero, new Vector3(9f, 0.8f, L));                    // tabliye
            Box(new Vector3(-4.3f, 0.75f, 0f), new Vector3(0.3f, 0.7f, L)); // korkuluk
            Box(new Vector3(4.3f, 0.75f, 0f), new Vector3(0.3f, 0.7f, L));
            foreach (float z in new[] { -RiverHalf + 6f, 0f, RiverHalf - 6f })
                Box(new Vector3(0f, -4.5f, z), new Vector3(7f, 8.5f, 1.4f)); // ayaklar
            GameObjectUtility.SetStaticEditorFlags(br.gameObject, StaticEditorFlags.BatchingStatic);
        }

        // Kıyıdaki küçük köy (ova köyünün ev modelleri)
        static void BuildHamlet(Prefabs p, Transform root, Terrain t)
        {
            if (p.houses.Count == 0) return;
            var hr = new GameObject("NehirKoyu").transform;
            hr.SetParent(root, false);
            var rng = new System.Random(58);
            int n = 0;
            for (int k = 0; k < 14; k++)
            {
                float a = k * 0.9f + (float)rng.NextDouble() * 0.4f, r = 18f + 9f * k * 0.55f;
                var pos = HamletXZ + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r;
                if (Mathf.Abs(RiverDist(pos.x, pos.y)) < RiverHalf + 30f) continue;
                var world = RiverOrigin + new Vector3(pos.x, 0f, pos.y);
                var h = (GameObject)PrefabUtility.InstantiatePrefab(p.houses[rng.Next(p.houses.Count)], hr);
                h.transform.SetPositionAndRotation(new Vector3(world.x, t.SampleHeight(world) + t.transform.position.y, world.z),
                    Quaternion.Euler(0f, -14f + 90f * rng.Next(4) + (float)(rng.NextDouble() - 0.5) * 8f, 0f));
                n++;
            }
            GameObjectUtility.SetStaticEditorFlags(hr.gameObject, StaticEditorFlags.BatchingStatic);
        }

        // Çevredeki 8 parça: vadi nehir boyunca ufka uzanır
        static void BuildRiverFarTiles(Terrain center, TerrainLayer[] layers, Prefabs prefabs, Transform root)
        {
            const int res = 257;
            const float H = 900f;
            var grid = new Terrain[3, 3];
            grid[1, 1] = center;
            var rng = new System.Random(29);
            for (int dz = -1; dz <= 1; dz++)
            for (int dx = -1; dx <= 1; dx++)
            {
                if (dx == 0 && dz == 0) continue;
                var td = new TerrainData { heightmapResolution = res };
                td.size = new Vector3(TerrainSize, H, TerrainSize);
                string path = $"{Root}/Terrain/NehirUzak_{dx + 1}{dz + 1}.asset";
                AssetDatabase.DeleteAsset(path);
                AssetDatabase.CreateAsset(td, path);
                float ox = dx * TerrainSize - TerrainSize / 2, oz = dz * TerrainSize - TerrainSize / 2;
                var hm = new float[res, res];
                for (int j = 0; j < res; j++)
                for (int i = 0; i < res; i++)
                    hm[j, i] = Mathf.Clamp01(FarHeightAtNehir(ox + i / (float)(res - 1) * TerrainSize, oz + j / (float)(res - 1) * TerrainSize) / H);
                td.SetHeights(0, 0, hm);
                td.terrainLayers = layers;
                const int ar = 256;
                td.alphamapResolution = ar;
                var am = new float[ar, ar, layers.Length];
                for (int j = 0; j < ar; j++)
                for (int i = 0; i < ar; i++)
                {
                    float u = i / (float)(ar - 1), v = j / (float)(ar - 1);
                    float x = ox + u * TerrainSize, z = oz + v * TerrainSize;
                    float slope = td.GetSteepness(u, v);
                    float d = Mathf.Abs(RiverDist(x, z));
                    float red = Mathf.Clamp01((slope - 16f) / 10f);
                    float bank = 1f - Mathf.InverseLerp(RiverHalf, RiverHalf + 20f, d);
                    float green = (1f - Mathf.InverseLerp(40f, 200f, d)) * (1f - red) * (1f - bank);
                    am[j, i, 0] = green;
                    am[j, i, 1] = (1f - green) * (1f - red) * (1f - bank);
                    am[j, i, 4] = red * (1f - bank);
                    am[j, i, 5] = bank;
                }
                td.SetAlphamaps(0, 0, am);
                var oaks = prefabs.oaks;
                td.treePrototypes = oaks.Select(g => new TreePrototype { prefab = g, bendFactor = 0f }).ToArray();
                var trees = new List<TreeInstance>();
                for (int k = 0; k < 20000 && trees.Count < 900 && oaks.Count > 0; k++)
                {
                    float u = (float)rng.NextDouble(), v = (float)rng.NextDouble();
                    float x = ox + u * TerrainSize, z = oz + v * TerrainSize;
                    float d = Mathf.Abs(RiverDist(x, z));
                    bool riverside = d > RiverHalf + 14f && d < RiverHalf + 60f;
                    if (!riverside && rng.NextDouble() > 0.08) continue;
                    if (td.GetSteepness(u, v) > 25f) continue;
                    float s = 0.8f + (float)rng.NextDouble() * 0.4f;
                    trees.Add(new TreeInstance { prototypeIndex = rng.Next(oaks.Count), position = new Vector3(u, 0, v),
                                                 widthScale = riverside ? 0.42f * s : s, heightScale = riverside ? 1.85f * s : s,
                                                 rotation = (float)rng.NextDouble() * 6.28f, color = Color.white, lightmapColor = Color.white });
                }
                td.SetTreeInstances(trees.ToArray(), true);
                EditorUtility.SetDirty(td);
                var go = Terrain.CreateTerrainGameObject(td);
                go.name = $"NehirUzak_{dx}_{dz}";
                go.transform.SetParent(root, false);
                go.transform.position = RiverOrigin + new Vector3(ox, -BaseHeight, oz);
                var t = go.GetComponent<Terrain>();
                t.heightmapPixelError = 8f;
                t.basemapDistance = 20000f;
                t.treeDistance = 4000f;
                t.treeBillboardDistance = 4000f;
                t.drawInstanced = true;
                grid[dx + 1, dz + 1] = t;
            }
            for (int z = 0; z < 3; z++)
            for (int x = 0; x < 3; x++)
                grid[x, z].SetNeighbors(x > 0 ? grid[x - 1, z] : null, z < 2 ? grid[x, z + 1] : null,
                                        x < 2 ? grid[x + 1, z] : null, z > 0 ? grid[x, z - 1] : null);
            AssetDatabase.SaveAssets();
        }
    }
}
