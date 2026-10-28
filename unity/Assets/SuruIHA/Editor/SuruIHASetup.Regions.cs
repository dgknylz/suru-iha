using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using Object = UnityEngine.Object;

namespace SuruIHA.EditorTools
{
    // Divriği, Gökpınar Gölü ve Akdeniz kıyısı bölgelerinin ortak kurulumu: merkez arazi (yükseklik, katman boyama,
    // ağaçlar, ot), ufka uzanan 8 parça, dere şeridi, HDRP su yüzeyi, bölgeye özel hava (yerel hacim) ve yapı yerleştirme.
    public static partial class SuruIHASetup
    {
        // Ağaç dikici: çam, meşe, çalı ve kaya prototipleri sırayla; kavak ve söğüt meşe modelinden ölçeklenir
        class Planter
        {
            public readonly List<TreeInstance> trees = new List<TreeInstance>();
            public readonly System.Random rng;
            public readonly TreePrototype[] protos;
            readonly int pine0, pines, oak0, oaks, shrub0, shrubs, rock0, rocks;
            public float ox = -TerrainSize / 2, oz = -TerrainSize / 2;      // parçanın köşesi (yerel)

            public Planter(Prefabs p, int seed)
            {
                rng = new System.Random(seed);
                pines = p.pines.Count;
                oak0 = pines;
                oaks = p.oaks.Count;
                shrub0 = oak0 + oaks;
                shrubs = p.shrubs.Count;
                rock0 = shrub0 + shrubs;
                rocks = p.rocks.Count;
                protos = p.pines.Concat(p.oaks).Concat(p.shrubs).Concat(p.rocks)
                    .Select(g => new TreePrototype { prefab = g, bendFactor = 0f }).ToArray();
            }

            public float R() => (float)rng.NextDouble();
            public int Count => trees.Count;

            void Add(int proto, float x, float z, float ws, float hs) => trees.Add(new TreeInstance
            {
                prototypeIndex = proto, position = new Vector3((x - ox) / TerrainSize, 0f, (z - oz) / TerrainSize),
                widthScale = ws, heightScale = hs, rotation = R() * 6.28f, color = Color.white, lightmapColor = Color.white,
            });

            public void Pine(float x, float z, float s = 1f) { if (pines > 0) Add(rng.Next(pines), x, z, s, s); }
            public void Oak(float x, float z, float w = 1f, float h = 1f) { if (oaks > 0) Add(oak0 + rng.Next(oaks), x, z, w, h); }
            public void Poplar(float x, float z, float s = 1f) => Oak(x, z, 0.42f * s, 1.85f * s);
            public void Willow(float x, float z, float s = 1f) => Oak(x, z, 1.2f * s, 0.8f * s);
            public void Shrub(float x, float z, float s = 1f) { if (shrubs > 0) Add(shrub0 + rng.Next(shrubs), x, z, s, s); }
            public void Rock(float x, float z, float s = 1f) { if (rocks > 0) Add(rock0 + rng.Next(rocks), x, z, s, s * (0.7f + 0.6f * R())); }
        }

        // Merkez arazi (2,4 km): yükseklik işlevi, katman boyama (x, z, eğim -> ağırlıklar), ağaçlar ve ot.
        // exportFloor: Python'a giden yükseklik haritasında en düşük dünya y'si (Akdeniz'de deniz yüzeyi);
        // baseH: üssün arazi yüksekliği (sahnede y=0'a gelir; Akdeniz'de deniz dibi derin olsun diye daha yüksek)
        static Terrain BuildRegionTerrain(string name, Transform root, Vector3 origin, string suffix, Func<float, float, float> height,
                                          TerrainLayer[] layers, Action<float, float, float, float[]> paint, Action<Planter, TerrainData> plant,
                                          Prefabs prefabs, int seed, float exportFloor = float.NegativeInfinity, float baseH = BaseHeight)
        {
            const int res = 1025;
            var td = new TerrainData { heightmapResolution = res };
            td.size = new Vector3(TerrainSize, TerrainHeight, TerrainSize);
            string tdPath = $"{Root}/Terrain/{name}AraziVerisi.asset";
            AssetDatabase.DeleteAsset(tdPath);
            AssetDatabase.CreateAsset(td, tdPath);
            var hm = new float[res, res];
            for (int j = 0; j < res; j++)
            for (int i = 0; i < res; i++)
            {
                float x = (i / (float)(res - 1) - 0.5f) * TerrainSize, z = (j / (float)(res - 1) - 0.5f) * TerrainSize;
                hm[j, i] = Mathf.Clamp01(height(x, z) / TerrainHeight);
            }
            td.SetHeights(0, 0, hm);

            td.terrainLayers = layers;
            const int amRes = 2048;
            td.alphamapResolution = amRes;
            var am = new float[amRes, amRes, layers.Length];
            var w = new float[layers.Length];
            for (int j = 0; j < amRes; j++)
            for (int i = 0; i < amRes; i++)
            {
                float u = i / (float)(amRes - 1), v = j / (float)(amRes - 1);
                Array.Clear(w, 0, w.Length);
                paint((u - 0.5f) * TerrainSize, (v - 0.5f) * TerrainSize, td.GetSteepness(u, v), w);
                float sum = 0f;
                foreach (float a in w) sum += a;
                if (sum < 1e-4f) { w[0] = 1f; sum = 1f; }
                for (int k = 0; k < w.Length; k++) am[j, i, k] = w[k] / sum;
            }
            td.SetAlphamaps(0, 0, am);

            var pl = new Planter(prefabs, seed);
            td.treePrototypes = pl.protos;
            plant(pl, td);
            td.SetTreeInstances(pl.trees.ToArray(), true);
            PaintGrass(td, prefabs, am, amRes);
            EditorUtility.SetDirty(td);
            AssetDatabase.SaveAssets();

            var go = Terrain.CreateTerrainGameObject(td);
            go.name = name + "Arazi";
            go.transform.SetParent(root, false);
            go.transform.position = origin + new Vector3(-TerrainSize / 2, -baseH, -TerrainSize / 2);
            var t = go.GetComponent<Terrain>();
            t.treeDistance = 2500f;
            t.treeBillboardDistance = 2500f;
            t.heightmapPixelError = 1.5f;
            t.basemapDistance = 20000f;
            t.drawInstanced = true;
            t.detailObjectDistance = 220f;
            t.detailObjectDensity = 1f;
            GameObjectUtility.SetStaticEditorFlags(go, StaticEditorFlags.BatchingStatic | StaticEditorFlags.ContributeGI);
            ExportHeightmap(t, origin, suffix, exportFloor);
            Debug.Log($"[SuruIHA] {name}: {pl.Count} ağaç, çalı ve kaya, {layers.Length} katman");
            return t;
        }

        // Çevredeki 8 parça (yükseklik 900 m'ye kadar): kenarları merkezle kesintisiz birleşir
        static void BuildRegionFarTiles(string name, Transform root, Vector3 origin, Terrain center, TerrainLayer[] layers,
                                        Func<float, float, float> height, Action<float, float, float, float[]> paint,
                                        Action<Planter, float, float, float> plant, Prefabs prefabs, int seed, int maxTrees = 1000,
                                        float baseH = BaseHeight)
        {
            const int res = 257, ar = 256;
            const float H = 900f;
            var grid = new Terrain[3, 3];
            grid[1, 1] = center;
            var w = new float[layers.Length];
            for (int dz = -1; dz <= 1; dz++)
            for (int dx = -1; dx <= 1; dx++)
            {
                if (dx == 0 && dz == 0) continue;
                var td = new TerrainData { heightmapResolution = res };
                td.size = new Vector3(TerrainSize, H, TerrainSize);
                string path = $"{Root}/Terrain/{name}Uzak_{dx + 1}{dz + 1}.asset";
                AssetDatabase.DeleteAsset(path);
                AssetDatabase.CreateAsset(td, path);
                float ox = dx * TerrainSize - TerrainSize / 2, oz = dz * TerrainSize - TerrainSize / 2;
                var hm = new float[res, res];
                for (int j = 0; j < res; j++)
                for (int i = 0; i < res; i++)
                    hm[j, i] = Mathf.Clamp01(height(ox + i / (float)(res - 1) * TerrainSize, oz + j / (float)(res - 1) * TerrainSize) / H);
                td.SetHeights(0, 0, hm);
                td.terrainLayers = layers;
                td.alphamapResolution = ar;
                var am = new float[ar, ar, layers.Length];
                for (int j = 0; j < ar; j++)
                for (int i = 0; i < ar; i++)
                {
                    float u = i / (float)(ar - 1), v = j / (float)(ar - 1);
                    Array.Clear(w, 0, w.Length);
                    paint(ox + u * TerrainSize, oz + v * TerrainSize, td.GetSteepness(u, v), w);
                    float sum = 0f;
                    foreach (float a in w) sum += a;
                    if (sum < 1e-4f) { w[0] = 1f; sum = 1f; }
                    for (int k = 0; k < w.Length; k++) am[j, i, k] = w[k] / sum;
                }
                td.SetAlphamaps(0, 0, am);
                var pl = new Planter(prefabs, seed + dx * 7 + dz * 13) { ox = ox, oz = oz };
                td.treePrototypes = pl.protos;
                for (int k = 0; k < 40000 && pl.Count < maxTrees; k++)
                {
                    float u = pl.R(), v = pl.R();
                    plant(pl, ox + u * TerrainSize, oz + v * TerrainSize, td.GetSteepness(u, v));
                }
                td.SetTreeInstances(pl.trees.ToArray(), true);
                EditorUtility.SetDirty(td);
                var go = Terrain.CreateTerrainGameObject(td);
                go.name = $"{name}Uzak_{dx}_{dz}";
                go.transform.SetParent(root, false);
                go.transform.position = origin + new Vector3(ox, -baseH, oz);
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

        // Prefab'ı araziye oturtur (dünya konumu, yön); bulunamazsa sessizce geçer
        static GameObject PlaceOn(Prefabs p, string prefab, Transform parent, Terrain t, Vector3 world, float yaw, float sink = 0f)
        {
            if (!p.named.TryGetValue(prefab, out var pf) || pf == null) return null;
            var g = (GameObject)PrefabUtility.InstantiatePrefab(pf, parent);
            g.transform.SetPositionAndRotation(new Vector3(world.x, t.SampleHeight(world) + t.transform.position.y - sink, world.z),
                                               Quaternion.Euler(0f, yaw, 0f));
            return g;
        }

        // Dere şeridi: orta çizgi (yerel x, z) boyunca su yüzeyi; açık, berrak, hafif dalgacıklı
        static void BuildCreek(string name, Transform root, Vector3 origin, IList<Vector2> line, float half, Func<Vector2, float> level, Material mat)
        {
            var verts = new List<Vector3>();
            var uvs = new List<Vector2>();
            var tris = new List<int>();
            float len = 0f;
            for (int i = 0; i < line.Count; i++)
            {
                var c = line[i];
                if (i > 0) len += (c - line[i - 1]).magnitude;
                var tng = (line[Mathf.Min(i + 1, line.Count - 1)] - line[Mathf.Max(i - 1, 0)]).normalized;
                var nrm = new Vector2(-tng.y, tng.x);
                float y = level(c);
                foreach (int s in new[] { -1, 1 })
                {
                    var p = c + nrm * (s * half);
                    verts.Add(new Vector3(p.x, y, p.y));
                    uvs.Add(new Vector2((s + 1) * half / 8f, len / 8f));
                }
                int n = verts.Count;
                if (n >= 4) tris.AddRange(new[] { n - 4, n - 3, n - 2, n - 3, n - 1, n - 2 });
            }
            // tng (ileri) ve nrm (sola) seçimi Kızılırmak'tan ters olabilir: üçgenler yukarı bakmıyorsa çevir
            var mesh = new Mesh { name = name, indexFormat = IndexFormat.UInt32 };
            mesh.SetVertices(verts);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateNormals();
            if (mesh.normals.Length > 0 && mesh.normals[0].y < 0f)
            {
                for (int i = 0; i < tris.Count; i += 3) (tris[i + 1], tris[i + 2]) = (tris[i + 2], tris[i + 1]);
                mesh.SetTriangles(tris, 0);
                mesh.RecalculateNormals();
            }
            mesh.RecalculateTangents();
            mesh.RecalculateBounds();
            string meshPath = $"{Root}/Terrain/{name}.asset";
            AssetDatabase.DeleteAsset(meshPath);
            AssetDatabase.CreateAsset(mesh, meshPath);
            var go = new GameObject(name);
            go.transform.SetParent(root, false);
            go.transform.position = origin;
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = ShadowCastingMode.Off;
            go.AddComponent<SwarmWater>();
        }

        static Material ClearWaterMaterial(string name, Color color, float normal = 0.45f)
        {
            string path = $"{Root}/Materials/{name}.mat";
            AssetDatabase.DeleteAsset(path);
            var m = new Material(Shader.Find("HDRP/Lit")) { name = name };
            m.SetColor("_BaseColor", color);
            m.SetFloat("_Smoothness", 0.96f);
            m.SetFloat("_Metallic", 0f);
            m.SetFloat("_CoatMask", 1f);
            var nm = WaterNormalTexture();
            if (nm != null)
            {
                m.SetTexture("_NormalMap", nm);
                m.SetFloat("_NormalScale", normal);
            }
            HDMaterial.ValidateMaterial(m);
            AssetDatabase.CreateAsset(m, path);
            return m;
        }

        // HDRP su yüzeyi (gerçek dalga benzetimi, köpük, kostik ışık). Kapalı kaydedilir: yalnızca kendi bölgesinde açılır
        static WaterSurface BuildWaterSurface(string name, string region, Transform root, Vector3 pos, WaterSurfaceType type, Vector2 size)
        {
            var go = new GameObject(name);
            go.transform.SetParent(root, false);
            go.transform.position = pos;
            var tag = go.AddComponent<SwarmRegionObject>();
            tag.region = region;
            var ws = go.AddComponent<WaterSurface>();
            ws.surfaceType = type;
            if (type == WaterSurfaceType.OceanSeaLake && size == Vector2.zero)
                ws.geometryType = WaterGeometryType.Infinite;
            else
            {
                ws.geometryType = WaterGeometryType.Quad;
                go.transform.localScale = new Vector3(size.x, 1f, size.y);
            }
            go.SetActive(false);
            return ws;
        }

        // Bölgeye özel hava: ana gökyüzü ayarının üstüne yalnızca verilen ayarlar yazılır (ezmesiz bileşenler)
        static void BuildRegionVolume(string name, Transform root, Vector3 origin, Action<VolumeProfile> fill)
        {
            string profPath = $"{Root}/Settings/SuruIHA_{name}Profili.asset";
            AssetDatabase.DeleteAsset(profPath);
            var prof = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(prof, profPath);
            fill(prof);
            EditorUtility.SetDirty(prof);
            var go = new GameObject(name + "Havasi");
            go.transform.SetParent(root, false);
            go.transform.position = origin + Vector3.up * 1500f;
            var box = go.AddComponent<BoxCollider>();
            box.isTrigger = true;
            box.size = new Vector3(3 * TerrainSize + 400f, 5000f, 3 * TerrainSize + 400f);
            var vol = go.AddComponent<Volume>();
            vol.isGlobal = false;
            vol.priority = 5f;
            vol.blendDistance = 600f;
            vol.sharedProfile = prof;
        }

        // Yumuşak düzleştirme: dikdörtgen alanın (yerel, dönük) içinde arazi sabit yüksekliğe çekilir, kenarda harmanlanır
        static float Terrace(float x, float z, Vector2 c, Vector2 half, float yawDeg, float blend, float h, float target)
        {
            float a = yawDeg * Mathf.Deg2Rad;
            float dx = x - c.x, dz = z - c.y;
            float lx = dx * Mathf.Cos(a) - dz * Mathf.Sin(a), lz = dx * Mathf.Sin(a) + dz * Mathf.Cos(a);
            float ex = Mathf.Max(0f, Mathf.Abs(lx) - half.x), ez = Mathf.Max(0f, Mathf.Abs(lz) - half.y);
            float k = 1f - Mathf.SmoothStep(0f, 1f, Mathf.Sqrt(ex * ex + ez * ez) / blend);
            return Mathf.Lerp(h, target, k);
        }
    }
}
