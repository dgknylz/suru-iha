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
    // Karlı bölge: ana araziden 12 km doğuda ikinci harita. Karla kaplı geniş bir vadi (üs ve görev alanı aynı
    // yerel koordinatlarda: üs (0, 0), görev alanı kuzeyde), yamaçlarda karlı çam ormanları, çevresi sarp dağlar.
    // Python bu bölgenin yükseklik haritasını arazi_yukseklik_kar.bin olarak okur (--region kar).
    public static partial class SuruIHASetup
    {
        const float SnowHeight = 700f;
        static Vector3 SnowOrigin => SwarmRegions.SnowOffset;

        // Vadi tabanı yumuşak tümsekli, üs düz; görev alanının çevresinden itibaren sarp, sivri dağlar
        public static float HeightAtKar(float x, float z)
        {
            float valley = new Vector2(x, (z - 330f) * 0.8f).magnitude;                 // görev alanı merkezli elips
            float floor = BaseHeight + 3f * (Fbm(x * 0.005f + 3f, z * 0.005f - 8f, 3) - 0.5f) * 2f;
            float rolling = 30f * Mathf.Pow(Fbm(x * 0.0032f + 61f, z * 0.0032f + 9f, 4), 1.4f)
                            * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(120f, 380f, new Vector2(x, z).magnitude));
            float w = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(560f, 1050f, valley));
            float ridged = 1f - Mathf.Abs(Fbm(x * 0.0011f - 17f, z * 0.0011f + 5f, 4) * 2f - 1f);
            float mountains = 330f * Mathf.Pow(ridged, 1.7f) + 90f * Fbm(x * 0.002f + 90f, z * 0.002f, 3);
            float edge = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(900f, 1200f, Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)))) * 80f;
            float h = floor + rolling * (1f - w) + w * (mountains + edge);
            // donmuş göl: düz, sığ çanak (buz yüzeyi BuildFrozenLake'te)
            float lr = FrozenR(x, z);
            float lake0 = BaseHeight + 3f * (Fbm(FrozenXZ.x * 0.005f + 3f, FrozenXZ.y * 0.005f - 8f, 3) - 0.5f) * 2f;
            h = Mathf.Lerp(lake0 - 1.4f, h, Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(1.0f, 1.14f, lr)));   // dik kıyı: buzun kenarı toprağın altında kalsın
            return h;
        }

        static readonly Vector2 FrozenXZ = new Vector2(-300f, 560f);
        const float FrozenA = 125f, FrozenB = 62f, FrozenYaw = 15f;
        static readonly Vector2 SnowVillageXZ = new Vector2(-250f, 150f);

        static float FrozenR(float x, float z)
        {
            float a = FrozenYaw * Mathf.Deg2Rad;
            float dx = x - FrozenXZ.x, dz = z - FrozenXZ.y;
            float u = dx * Mathf.Cos(a) + dz * Mathf.Sin(a), v = -dx * Mathf.Sin(a) + dz * Mathf.Cos(a);
            return Mathf.Sqrt(u * u / (FrozenA * FrozenA) + v * v / (FrozenB * FrozenB));
        }

        static float FarHeightAtKar(float x, float z)
        {
            float m = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z));
            float ridge = 1f - Mathf.Abs(Fbm(x * 0.0008f + 71f, z * 0.0008f - 13f, 5) * 2f - 1f);
            return HeightAtKar(x, z) + Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(1200f, 2800f, m)) * (220f + 480f * ridge);
        }

        // Katmanlar: 0-1 taze kar (aynı doku iki ölçekte, iri lekelerle karışır: tekrar deseni seçilmesin),
        // 2 yer yer bitkisi görünen kar (vadide), 3 kaya (yalnızca sarp yüz), 4 tekerlek izli karlı yol
        static readonly Color SnowTint = new Color(1.36f, 1.37f, 1.42f);  // kar parlak (gerçek kar ışığın %80'inden fazlasını yansıtır)
        static TerrainLayer[] SnowLayers()
        {
            var L = SnowLayerList();
            // Taze kar pürüzsüzdür: fotoğraftaki iz ve tümsekler yumuşatılır (havadan bakınca damga gibi tekrar etmesin)
            L[0].normalScale = 0.35f;
            L[1].normalScale = 0.35f;
            L[2].normalScale = 0.5f;
            foreach (var l in L) EditorUtility.SetDirty(l);
            return L;
        }

        static TerrainLayer[] SnowLayerList() => new[]
        {
            Layer("Kar", "Ter_Aniz", Color.white, new Color(0.92f, 0.93f, 0.95f), 6f, 0.35f, 11, "snow_02", 9f, SnowTint, 0.72f),
            Layer("KarIri", "Ter_Aniz", Color.white, new Color(0.92f, 0.93f, 0.95f), 6f, 0.35f, 16, "snow_02", 23f, SnowTint, 0.72f),
            Layer("KarDoga", "Ter_Aniz", Color.white, new Color(0.9f, 0.9f, 0.92f), 7f, 0.3f, 12, "snow_field_aerial", 60f,
                  new Color(1.1f, 1.1f, 1.14f)),
            Layer("KarKaya", "Ter_Kaya", new Color(0.47f, 0.46f, 0.44f), new Color(0.3f, 0.3f, 0.29f), 22f, 0.12f, 14, "aerial_rocks_02", 40f,
                  new Color(0.62f, 0.65f, 0.72f)),     // soğuk, kar tozlu gri: yosun yeşili ve kahve bastırılsın
            Layer("KarYol", "Ter_Cakil", new Color(0.8f, 0.8f, 0.8f), new Color(0.6f, 0.6f, 0.6f), 5f, 0.2f, 15, "snow_04", 6f),
        };

        static List<Vector2[]> SnowRoads()
        {
            // Güneyden gelen vadi yolu üsse, oradan karıştırıcı alanına ve görev alanının içinden kuzeye
            var a = new List<Vector2>();
            for (int k = 0; k <= 60; k++)
            {
                float t = k / 60f;
                var p = Vector2.Lerp(new Vector2(-80f, -1150f), new Vector2(-40f, -30f), t);
                p.x += Mathf.Sin(t * 7f) * 45f * (1f - t);
                a.Add(p);
            }
            var b = new List<Vector2>();
            for (int k = 0; k <= 50; k++)
            {
                float t = k / 50f;
                var p = Vector2.Lerp(new Vector2(-40f, -30f), new Vector2(40f, 1100f), t);
                p.x += Mathf.Sin(t * 9f) * 60f * Mathf.Sin(t * Mathf.PI);
                b.Add(p);
            }
            var c = new List<Vector2>();
            for (int k = 0; k <= 30; k++)
                c.Add(Vector2.Lerp(new Vector2(-30f, -10f), JammerXZ + new Vector2(-12f, -8f), k / 30f));
            return new List<Vector2[]> { a.ToArray(), b.ToArray(), c.ToArray() };
        }

        static void BuildSnowRegion(Prefabs prefabs)
        {
            var root = new GameObject("KarliBolge").transform;
            var pines = SnowyPines(prefabs);
            var rocks = prefabs.rocks;

            int res = 1025;
            var td = new TerrainData { heightmapResolution = res };
            td.size = new Vector3(TerrainSize, SnowHeight, TerrainSize);
            string tdPath = $"{Root}/Terrain/KarAraziVerisi.asset";
            AssetDatabase.DeleteAsset(tdPath);
            AssetDatabase.CreateAsset(td, tdPath);
            var heights = new float[res, res];
            for (int j = 0; j < res; j++)
            for (int i = 0; i < res; i++)
            {
                float x = (i / (float)(res - 1) - 0.5f) * TerrainSize;
                float z = (j / (float)(res - 1) - 0.5f) * TerrainSize;
                heights[j, i] = HeightAtKar(x, z) / SnowHeight;
            }
            td.SetHeights(0, 0, heights);

            var layers = SnowLayers();
            td.terrainLayers = layers;
            int amRes = 2048;
            td.alphamapResolution = amRes;
            var am = new float[amRes, amRes, layers.Length];
            var roads = SnowRoads();
            var w = new float[layers.Length];
            for (int j = 0; j < amRes; j++)
            for (int i = 0; i < amRes; i++)
            {
                float u = i / (float)(amRes - 1), v = j / (float)(amRes - 1);
                float x = (u - 0.5f) * TerrainSize, z = (v - 0.5f) * TerrainSize;
                float slope = td.GetSteepness(u, v);
                System.Array.Clear(w, 0, w.Length);
                float hRel = HeightAtKar(x, z) - BaseHeight;
                float mix = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((Fbm(x * 0.006f - 7f, z * 0.006f + 31f, 3) - 0.35f) * 3.3f));
                w[0] = 1f - mix;
                w[1] = mix;
                // Vadide seyrek, karın altından çıkan bitki (yükseldikçe kar kesintisiz)
                w[2] = Mathf.Clamp01((Fbm(x * 0.0035f + 5f, z * 0.0035f - 2f, 4) - 0.6f) * 2.5f) * 0.3f
                     * (1f - Mathf.InverseLerp(30f, 150f, hRel));
                // Kaya yalnızca kar tutmayan çok sarp yüzlerde; orada da oluklarda kar şeritleri kalır
                float streak = Mathf.Clamp01((Fbm(x * 0.03f + 9f, z * 0.012f - 4f, 3) - 0.4f) * 2.5f);
                float rock = Mathf.Clamp01((slope - 50f) / 12f) * (1f - 0.6f * streak);
                for (int k = 0; k < 3; k++) w[k] *= 1f - rock;
                w[3] += rock;
                float rd = RoadDistance(roads, new Vector2(x, z));
                float road = Mathf.Clamp01(1f - (rd - 3.2f) / 2f);
                float pad = Mathf.Clamp01(1f - ((new Vector2(x, z) - new Vector2(-30f, -4f)).magnitude - 16f) / 4f)
                          + Mathf.Clamp01(1f - ((new Vector2(x, z) - JammerXZ).magnitude - 12f) / 4f);
                float g = Mathf.Clamp01(road + pad);
                for (int k = 0; k < 4; k++) w[k] *= 1f - g;
                w[4] += g;
                float sum = 0f;
                foreach (var a in w) sum += a;
                for (int k = 0; k < w.Length; k++) am[j, i, k] = w[k] / Mathf.Max(sum, 1e-4f);
            }
            td.SetAlphamaps(0, 0, am);

            // Ağaçlar: yamaçlarda sık, vadi tabanında seyrek karlı çamlar; ağaç sınırının üstünde ve sarp kayada yok
            var protos = pines.Concat(rocks).Select(g => new TreePrototype { prefab = g, bendFactor = 0f }).ToArray();
            td.treePrototypes = protos;
            var rng = new System.Random(4242);
            float R() => (float)rng.NextDouble();
            var trees = new List<TreeInstance>();
            for (int k = 0; k < 260000 && trees.Count < 6500 && pines.Count > 0; k++)
            {
                float u = R(), v = R();
                float x = (u - 0.5f) * TerrainSize, z = (v - 0.5f) * TerrainSize;
                if (td.GetSteepness(u, v) > 30f) continue;
                float hRel = HeightAtKar(x, z) - BaseHeight;
                if (hRel > 330f || new Vector2(x, z).magnitude < 120f) continue;
                if (FrozenR(x, z) < 1.25f || (new Vector2(x, z) - SnowVillageXZ).magnitude < 110f) continue;
                if (RoadDistance(roads, new Vector2(x, z)) < 9f) continue;
                float forest = Fbm(x * 0.004f + 200f, z * 0.004f - 77f, 4);
                float p = Mathf.Clamp01((forest - 0.42f) * 3f) * (0.2f + 0.8f * Mathf.InverseLerp(0f, 60f, hRel));
                if (R() > p) continue;
                float s = 0.8f + 0.6f * R();
                trees.Add(new TreeInstance
                {
                    prototypeIndex = rng.Next(pines.Count), position = new Vector3(u, 0f, v), widthScale = s,
                    heightScale = s * (0.9f + 0.2f * R()), rotation = R() * 6.28f, color = Color.white, lightmapColor = Color.white,
                });
            }
            for (int k = 0; k < 40000 && rocks.Count > 0 && trees.Count < 7000; k++)
            {
                float u = R(), v = R();
                float sl = td.GetSteepness(u, v);
                if (sl < 18f || sl > 42f) continue;
                float s = 0.6f + 1.2f * R();
                trees.Add(new TreeInstance
                {
                    prototypeIndex = pines.Count + rng.Next(rocks.Count), position = new Vector3(u, 0f, v), widthScale = s,
                    heightScale = s, rotation = R() * 6.28f, color = Color.white, lightmapColor = Color.white,
                });
            }
            td.SetTreeInstances(trees.ToArray(), true);
            EditorUtility.SetDirty(td);
            AssetDatabase.SaveAssets();

            var go = Terrain.CreateTerrainGameObject(td);
            go.name = "KarArazi";
            go.transform.SetParent(root, false);
            go.transform.position = SnowOrigin + new Vector3(-TerrainSize / 2, -BaseHeight, -TerrainSize / 2);
            var t = go.GetComponent<Terrain>();
            t.treeDistance = 2500f;
            t.treeBillboardDistance = 2500f;
            t.heightmapPixelError = 1.5f;
            t.basemapDistance = 20000f;
            t.drawInstanced = true;
            GameObjectUtility.SetStaticEditorFlags(go, StaticEditorFlags.BatchingStatic | StaticEditorFlags.ContributeGI);
            ExportHeightmap(t, SnowOrigin, "_kar");
            BuildSnowFarTiles(t, layers, pines, root);
            BuildSnowVolume(root);
            BuildFrozenLake(root);
            BuildSnowVillage(prefabs, root, t);
            Debug.Log($"[SuruIHA] Karlı bölge: {trees.Count} ağaç ve kaya, {layers.Length} katman");
        }

        // Donmuş göl: vadideki çanağın üstünde parlak, mavimsi buz (gök ve dağlar yansır; ince çatlak dokusu)
        static void BuildFrozenLake(Transform root)
        {
            const int N = 72;
            var verts = new List<Vector3> { Vector3.zero };
            var uvs = new List<Vector2> { new Vector2(0.5f, 0.5f) };
            var tris = new List<int>();
            float a = FrozenYaw * Mathf.Deg2Rad;
            for (int i = 0; i <= N; i++)
            {
                float t = i * Mathf.PI * 2f / N;
                float u = Mathf.Cos(t) * FrozenA * 1.02f, v = Mathf.Sin(t) * FrozenB * 1.02f;
                verts.Add(new Vector3(u * Mathf.Cos(a) - v * Mathf.Sin(a), 0f, u * Mathf.Sin(a) + v * Mathf.Cos(a)));
                uvs.Add(new Vector2(u / 40f, v / 40f));
                if (i > 0) tris.AddRange(new[] { 0, i + 1, i });
            }
            var mesh = new Mesh { name = "DonmusGol" };
            mesh.SetVertices(verts);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateNormals();
            if (mesh.normals[1].y < 0f)
            {
                for (int i = 0; i < tris.Count; i += 3) (tris[i + 1], tris[i + 2]) = (tris[i + 2], tris[i + 1]);
                mesh.SetTriangles(tris, 0);
                mesh.RecalculateNormals();
            }
            mesh.RecalculateTangents();
            string mp = $"{Root}/Terrain/DonmusGol.asset";
            AssetDatabase.DeleteAsset(mp);
            AssetDatabase.CreateAsset(mesh, mp);
            float lake0 = 3f * (Fbm(FrozenXZ.x * 0.005f + 3f, FrozenXZ.y * 0.005f - 8f, 3) - 0.5f) * 2f;
            var go = new GameObject("DonmusGol");
            go.transform.SetParent(root, false);
            go.transform.position = SnowOrigin + new Vector3(FrozenXZ.x, lake0 - 0.95f, FrozenXZ.y);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.shadowCastingMode = ShadowCastingMode.Off;
            string matPath = $"{Root}/Materials/MAT_Buz.mat";
            AssetDatabase.DeleteAsset(matPath);
            var m = new Material(Shader.Find("HDRP/Lit")) { name = "MAT_Buz" };
            m.SetColor("_BaseColor", new Color(0.66f, 0.78f, 0.86f));
            m.SetFloat("_Smoothness", 0.86f);
            m.SetFloat("_CoatMask", 1f);
            var nm = WaterNormalTexture();
            if (nm != null) { m.SetTexture("_NormalMap", nm); m.SetFloat("_NormalScale", 0.18f); }
            HDMaterial.ValidateMaterial(m);
            AssetDatabase.CreateAsset(m, matPath);
            mr.sharedMaterial = m;
        }

        // Dağ köyü: karlı çatılı evler (çatı malzemesi kar), bacalardan duman tüter (SwarmRegions karlı bölgede açar)
        static void BuildSnowVillage(Prefabs p, Transform root, Terrain t)
        {
            if (p.houses.Count == 0) return;
            var v = new GameObject("KarKoyu").transform;
            v.SetParent(root, false);
            string matPath = $"{Root}/Materials/MAT_KarCati.mat";
            var snowRoof = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            if (snowRoof == null)
            {
                snowRoof = new Material(Shader.Find("HDRP/Lit")) { name = "MAT_KarCati" };
                AssetDatabase.CreateAsset(snowRoof, matPath);
            }
            snowRoof.SetColor("_BaseColor", new Color(0.93f, 0.95f, 0.98f));
            snowRoof.SetFloat("_Smoothness", 0.4f);
            HDMaterial.ValidateMaterial(snowRoof);
            EditorUtility.SetDirty(snowRoof);
            var rng = new System.Random(1959);
            var placed = new List<Vector2>();
            for (int k = 0; k < 400 && placed.Count < 14; k++)
            {
                var c = SnowVillageXZ + new Vector2(((float)rng.NextDouble() - 0.5f) * 170f, ((float)rng.NextDouble() - 0.5f) * 140f);
                bool near = false;
                foreach (var q in placed) if ((q - c).sqrMagnitude < 18f * 18f) { near = true; break; }
                if (near) continue;
                placed.Add(c);
                var world = SnowOrigin + new Vector3(c.x, 0f, c.y);
                var h = (GameObject)PrefabUtility.InstantiatePrefab(p.houses[rng.Next(p.houses.Count)], v);
                h.transform.SetPositionAndRotation(new Vector3(world.x, t.SampleHeight(world) + t.transform.position.y, world.z),
                    Quaternion.Euler(0f, 20f + 90f * rng.Next(4) + (float)(rng.NextDouble() - 0.5) * 12f, 0f));
                foreach (var r in h.GetComponentsInChildren<Renderer>())
                {
                    var ms = r.sharedMaterials;
                    bool changed = false;
                    for (int i = 0; i < ms.Length; i++)
                        if (ms[i] != null && ms[i].name.StartsWith("MAT_RoofTile")) { ms[i] = snowRoof; changed = true; }
                    if (changed) r.sharedMaterials = ms;
                }
            }
            GameObjectUtility.SetStaticEditorFlags(v.gameObject, StaticEditorFlags.BatchingStatic);
        }

        // Karlı çam prefab'ları: iğne dokusuna kar öbekleri eklenmiş malzemeyle
        static List<GameObject> SnowyPines(Prefabs prefabs)
        {
            var src = AssetDatabase.LoadAssetAtPath<Material>($"{Root}/Materials/MAT_Needles.mat");
            if (src == null) return prefabs.pines;
            string mp = $"{Root}/Materials/MAT_NeedlesKar.mat";
            AssetDatabase.DeleteAsset(mp);
            var snowMat = new Material(src) { name = "MAT_NeedlesKar" };
            snowMat.SetColor("_BaseColor", new Color(0.9f, 0.93f, 0.95f));    // karın arasındaki iğneler biraz koyu kalsın
            var tex = SnowyNeedleTexture(src.GetTexture("_BaseColorMap") as Texture2D);
            if (tex != null) snowMat.SetTexture("_BaseColorMap", tex);
            HDMaterial.ValidateMaterial(snowMat);
            AssetDatabase.CreateAsset(snowMat, mp);

            var result = new List<GameObject>();
            foreach (var p in prefabs.pines)
            {
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(p);
                PrefabUtility.UnpackPrefabInstance(inst, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
                foreach (var r in inst.GetComponentsInChildren<Renderer>())
                {
                    var ms = r.sharedMaterials;
                    for (int k = 0; k < ms.Length; k++)
                        if (ms[k] == src) ms[k] = snowMat;
                    r.sharedMaterials = ms;
                }
                string path = $"{Root}/Prefabs/{p.name}_Kar.prefab";
                result.Add(PrefabUtility.SaveAsPrefabAsset(inst, path));
                Object.DestroyImmediate(inst);
            }
            return result;
        }

        // İğne kartlarına öbek öbek kar: dokunun piksellerine gürültü maskesiyle beyaz karıştırılır (alfa korunur)
        static Texture2D SnowyNeedleTexture(Texture2D src)
        {
            if (src == null) return null;
            string srcPath = AssetDatabase.GetAssetPath(src);
            if (string.IsNullOrEmpty(srcPath) || !File.Exists(srcPath)) return null;
            var tex = new Texture2D(2, 2, TextureFormat.RGBA32, false);
            if (!tex.LoadImage(File.ReadAllBytes(srcPath))) return null;
            var px = tex.GetPixels32();
            int n = tex.width, m = tex.height;
            var snow = new Color(0.93f, 0.95f, 1f);
            for (int j = 0; j < m; j++)
            for (int i = 0; i < n; i++)
            {
                int k = j * n + i;
                if (px[k].a < 8) continue;
                float u = i / (float)n, v = j / (float)m;
                // Dalların üstü kar yükü: iğnelerin çoğu karla örtülü, arada koyu yeşil kalır
                float s = Mathf.SmoothStep(0.2f, 0.46f, Mathf.PerlinNoise(u * 7f + 3.1f, v * 7f - 1.7f) * 0.8f + v * 0.35f);
                Color c = px[k];
                Color o = Color.Lerp(c, snow, s * 0.97f);
                o.a = c.a;
                px[k] = o;
            }
            tex.SetPixels32(px);
            tex.Apply();
            string outPath = $"{GenTex}/Tex_CamIgne_Kar.png";
            File.WriteAllBytes(outPath, tex.EncodeToPNG());
            AssetDatabase.ImportAsset(outPath);
            var ti = AssetImporter.GetAtPath(outPath) as TextureImporter;
            if (ti != null)
            {
                ti.alphaIsTransparency = true;
                ti.mipMapsPreserveCoverage = true;
                ti.alphaTestReferenceValue = 0.45f;
                ti.maxTextureSize = 2048;
                ti.SaveAndReimport();
            }
            return AssetDatabase.LoadAssetAtPath<Texture2D>(outPath);
        }

        // Karlı bölgenin çevresine 8 parça: ufka uzanan karlı dağlar
        static void BuildSnowFarTiles(Terrain center, TerrainLayer[] layers, List<GameObject> pines, Transform root)
        {
            const int res = 257;
            const float H = 1200f;
            var grid = new Terrain[3, 3];
            grid[1, 1] = center;
            var rng = new System.Random(17);
            for (int dz = -1; dz <= 1; dz++)
            for (int dx = -1; dx <= 1; dx++)
            {
                if (dx == 0 && dz == 0) continue;
                var td = new TerrainData { heightmapResolution = res };
                td.size = new Vector3(TerrainSize, H, TerrainSize);
                string path = $"{Root}/Terrain/KarUzak_{dx + 1}{dz + 1}.asset";
                AssetDatabase.DeleteAsset(path);
                AssetDatabase.CreateAsset(td, path);
                float ox = dx * TerrainSize - TerrainSize / 2, oz = dz * TerrainSize - TerrainSize / 2;
                var hm = new float[res, res];
                for (int j = 0; j < res; j++)
                for (int i = 0; i < res; i++)
                    hm[j, i] = Mathf.Clamp01(FarHeightAtKar(ox + i / (float)(res - 1) * TerrainSize, oz + j / (float)(res - 1) * TerrainSize) / H);
                td.SetHeights(0, 0, hm);
                td.terrainLayers = layers;
                const int ar = 256;
                td.alphamapResolution = ar;
                var am = new float[ar, ar, layers.Length];
                for (int j = 0; j < ar; j++)
                for (int i = 0; i < ar; i++)
                {
                    float slope = td.GetSteepness(i / (float)(ar - 1), j / (float)(ar - 1));
                    float fx = ox + i / (float)(ar - 1) * TerrainSize, fz = oz + j / (float)(ar - 1) * TerrainSize;
                    float streak = Mathf.Clamp01((Fbm(fx * 0.03f + 9f, fz * 0.012f - 4f, 3) - 0.4f) * 2.5f);
                    float r = Mathf.Clamp01((slope - 50f) / 14f) * (1f - 0.6f * streak);
                    am[j, i, 1] = 1f - r;
                    am[j, i, 3] = r;
                }
                td.SetAlphamaps(0, 0, am);
                td.treePrototypes = pines.Select(g => new TreePrototype { prefab = g, bendFactor = 0f }).ToArray();
                var trees = new List<TreeInstance>();
                for (int k = 0; k < 30000 && trees.Count < 1000 && pines.Count > 0; k++)
                {
                    float u = (float)rng.NextDouble(), v = (float)rng.NextDouble();
                    float x = ox + u * TerrainSize, z = oz + v * TerrainSize;
                    if (td.GetSteepness(u, v) > 30f || FarHeightAtKar(x, z) - BaseHeight > 420f) continue;
                    float forest = Fbm(x * 0.0035f + 300f, z * 0.0035f - 90f, 4);
                    if (forest < 0.5f || rng.NextDouble() > (forest - 0.45f) * 2f) continue;
                    float s = 0.8f + (float)rng.NextDouble() * 0.6f;
                    trees.Add(new TreeInstance { prototypeIndex = rng.Next(pines.Count), position = new Vector3(u, 0, v), widthScale = s,
                                                 heightScale = s, rotation = (float)rng.NextDouble() * 6.28f, color = Color.white,
                                                 lightmapColor = Color.white });
                }
                td.SetTreeInstances(trees.ToArray(), true);
                EditorUtility.SetDirty(td);
                var go = Terrain.CreateTerrainGameObject(td);
                go.name = $"KarUzak_{dx}_{dz}";
                go.transform.SetParent(root, false);
                go.transform.position = SnowOrigin + new Vector3(ox, -BaseHeight, oz);
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

        static T GetLocal<T>(VolumeProfile p) where T : VolumeComponent
        {
            var c = p.Add<T>(false);
            c.name = typeof(T).Name;
            AssetDatabase.AddObjectToAsset(c, p);
            return c;
        }

        // Kış havası: yalnızca karlı bölgede geçerli yerel hacim (pus, soğuk ve soluk renkler, kar için pozlama)
        static void BuildSnowVolume(Transform root)
        {
            string profPath = $"{Root}/Settings/SuruIHA_KarProfili.asset";
            AssetDatabase.DeleteAsset(profPath);
            var prof = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(prof, profPath);

            // Bileşenler "ezmesiz" eklenir: yalnızca burada atanan ayarlar ana gökyüzü ayarının üstüne yazılır
            // (hepsi ezilirse ör. pozlama "sabit 0 EV"ye düşer ve görüntü bembeyaz olur)
            var fog = GetLocal<Fog>(prof);
            SetParam(fog, "enabled", true);
            SetParam(fog, "meanFreePath", 1300f);
            SetParam(fog, "maximumHeight", 1200f);
            SetParam(fog, "albedo", new Color(0.92f, 0.95f, 1f));
            var wb = GetLocal<WhiteBalance>(prof);
            SetParam(wb, "temperature", -10f);
            var color = GetLocal<ColorAdjustments>(prof);
            SetParam(color, "saturation", -10f);
            SetParam(color, "contrast", 6f);
            var exp = GetLocal<Exposure>(prof);
            SetParam(exp, "compensation", 1.4f);       // kar parlak: otomatik pozlama griye çekmesin (+1,4 EV)
            EditorUtility.SetDirty(prof);

            var go = new GameObject("KarHavasi");
            go.transform.SetParent(root, false);
            go.transform.position = SnowOrigin + Vector3.up * 1500f;
            var box = go.AddComponent<BoxCollider>();
            box.isTrigger = true;
            box.size = new Vector3(3 * TerrainSize + 400f, 5000f, 3 * TerrainSize + 400f);
            var vol = go.AddComponent<Volume>();
            vol.isGlobal = false;
            vol.priority = 5f;
            vol.blendDistance = 600f;
            vol.sharedProfile = prof;
        }
    }
}
