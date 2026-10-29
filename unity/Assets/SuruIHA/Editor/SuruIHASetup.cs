using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace SuruIHA.EditorTools
{
    // Menü: SürüİHA > Sahneyi Kur
    // Blender modellerinden prefab üretir, HDRP malzemelerini kurar, gerçekçi bir arazi
    // (yükseklik, doku, ağaç, kaya, toprak yol) oluşturur, gökyüzü/bulut/sis ayarlar
    // ve simülasyon nesnelerini yerleştirip sahneyi kaydeder.
    public static partial class SuruIHASetup
    {
        const string Root = "Assets/SuruIHA";
        const string ScenePath = Root + "/Scenes/SuruSahnesi.unity";
        const float TerrainSize = 2400f;
        const float TerrainHeight = 400f;
        const float BaseHeight = 20f;      // operasyon alanının arazi yüksekliği (sahnede y=0'a gelir)

        // Python'daki karıştırıcı konumu (ENU x, y) -> Unity (x, z)
        static readonly Vector2 JammerXZ = new Vector2(260f, 230f);

        [MenuItem("SürüİHA/Sahneyi Kur", priority = 0)]
        public static void BuildAll()
        {
            try
            {
                EditorUtility.DisplayProgressBar("SürüİHA", "Klasörler", 0.05f);
                Folders();
                // Terminale geçince (Python'u başlatırken) Unity simülasyonu dondurmasın
                PlayerSettings.runInBackground = true;
                EnableVolumetricClouds();
                EditorUtility.DisplayProgressBar("SürüİHA", "Malzemeler", 0.1f);
                var mats = BuildMaterials();
                EditorUtility.DisplayProgressBar("SürüİHA", "Prefab'lar", 0.2f);
                var prefabs = BuildPrefabs(mats);
                EditorUtility.DisplayProgressBar("SürüİHA", "Sahne", 0.35f);
                BuildScene(prefabs);
            }
            finally
            {
                EditorUtility.ClearProgressBar();
            }
        }

        // Komut satırı: Unity -batchmode -executeMethod SuruIHA.EditorTools.SuruIHASetup.BuildFromCommandLine
        public static void BuildFromCommandLine()
        {
            BuildAll();
            Debug.Log("[SuruIHA] Sahne kuruldu: " + ScenePath);
        }

        static void Folders()
        {
            foreach (var f in new[] { "Materials", "Prefabs", "Scenes", "Textures", "Terrain", "Settings" })
                if (!AssetDatabase.IsValidFolder($"{Root}/{f}")) AssetDatabase.CreateFolder(Root, f);
            foreach (var p in new[] { "Assets/TutorialInfo", "Assets/Readme.asset" })
                if (AssetDatabase.LoadMainAssetAtPath(p) != null) AssetDatabase.DeleteAsset(p);
        }

        // ------------------------------------------------------------------ HDRP ayarı
        static void EnableVolumetricClouds()
        {
            foreach (var guid in AssetDatabase.FindAssets("t:HDRenderPipelineAsset"))
            {
                var asset = AssetDatabase.LoadAssetAtPath<Object>(AssetDatabase.GUIDToAssetPath(guid));
                var so = new SerializedObject(asset);
                foreach (var path in new[] { "m_RenderPipelineSettings.supportVolumetricClouds",
                                             "m_RenderPipelineSettings.supportVolumetrics",
                                             "m_RenderPipelineSettings.supportSSAO",
                                             "m_RenderPipelineSettings.supportSSR",      // parlak yüzeylerde yansıma
                                             "m_RenderPipelineSettings.supportSSGI",     // gölgede yansıyan ışık
                                             "m_RenderPipelineSettings.supportWater" })  // deniz ve göl: HDRP su benzetimi
                {
                    var p = so.FindProperty(path);
                    if (p != null) p.boolValue = true;
                }
                // Güneş gölgesi: 32 bit derinlik, en yüksek kademe 4096 piksel
                var bits = so.FindProperty("m_RenderPipelineSettings.hdShadowInitParams.directionalShadowsDepthBits");
                if (bits != null) bits.intValue = 32;
                var maxRes = so.FindProperty("m_RenderPipelineSettings.hdShadowInitParams.maxDirectionalShadowMapResolution");
                if (maxRes != null) maxRes.intValue = 4096;
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            // Uzaktaki ağaç ve evler daha geç sadeleşsin (LOD sapması 2)
            var qs = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/QualitySettings.asset").FirstOrDefault();
            if (qs != null)
            {
                var so = new SerializedObject(qs);
                var levels = so.FindProperty("m_QualitySettings");
                for (int i = 0; levels != null && i < levels.arraySize; i++)
                {
                    var lod = levels.GetArrayElementAtIndex(i).FindPropertyRelative("lodBias");
                    if (lod != null && i == 0) lod.floatValue = 2f;
                }
                so.ApplyModifiedPropertiesWithoutUndo();
            }
        }

        // ------------------------------------------------------------------ malzemeler
        struct MatDef
        {
            public Color c; public float smooth, metal, emit; public bool transparent;
            public MatDef(float r, float g, float b, float rough, float metal = 0, float emit = 0)
            {
                c = new Color(r, g, b); smooth = 1f - rough; this.metal = metal; this.emit = emit; transparent = false;
            }
        }

        // Blender'daki renkler doğrusal (linear) uzaydadır; aynısını kullanıyoruz.
        static readonly Dictionary<string, MatDef> Defs = new Dictionary<string, MatDef>
        {
            ["MAT_Body"] = new MatDef(0.165f, 0.18f, 0.15f, 0.62f),
            ["MAT_Shell"] = new MatDef(0.215f, 0.232f, 0.195f, 0.5f),
            ["MAT_Carbon"] = new MatDef(0.018f, 0.018f, 0.02f, 0.3f, 0.15f),
            ["MAT_Metal"] = new MatDef(0.62f, 0.63f, 0.65f, 0.3f, 1f),
            ["MAT_MotorBell"] = new MatDef(0.05f, 0.05f, 0.055f, 0.28f, 0.9f),
            ["MAT_Accent"] = new MatDef(0.75f, 0.32f, 0.05f, 0.4f, 0.6f),
            ["MAT_Prop"] = new MatDef(0.012f, 0.012f, 0.012f, 0.35f),
            ["MAT_PropTip"] = new MatDef(0.85f, 0.85f, 0.82f, 0.4f),
            ["MAT_Rubber"] = new MatDef(0.02f, 0.02f, 0.02f, 0.92f),
            ["MAT_Glass"] = new MatDef(0.005f, 0.008f, 0.012f, 0.03f, 0.2f),
            ["MAT_Battery"] = new MatDef(0.07f, 0.072f, 0.075f, 0.7f),
            ["MAT_LED_Status"] = new MatDef(0.1f, 1f, 0.4f, 0.3f, 0, 4f),
            ["MAT_Nav_Red"] = new MatDef(1f, 0.05f, 0.03f, 0.3f, 0, 6f),
            ["MAT_Nav_Green"] = new MatDef(0.05f, 1f, 0.2f, 0.3f, 0, 6f),
            ["MAT_Nav_White"] = new MatDef(1f, 1f, 1f, 0.3f, 0, 4f),
            ["MAT_Camo"] = new MatDef(0.135f, 0.15f, 0.095f, 0.78f),
            ["MAT_Camo_Dark"] = new MatDef(0.08f, 0.09f, 0.06f, 0.8f),
            ["MAT_Tire"] = new MatDef(0.018f, 0.018f, 0.018f, 0.95f),
            ["MAT_Rim"] = new MatDef(0.11f, 0.12f, 0.085f, 0.6f, 0.4f),
            ["MAT_Black"] = new MatDef(0.02f, 0.02f, 0.022f, 0.6f),
            ["MAT_Radome"] = new MatDef(0.62f, 0.63f, 0.6f, 0.5f),
            ["MAT_Lamp"] = new MatDef(0.9f, 0.85f, 0.7f, 0.1f, 0, 0.6f),
            ["MAT_Beacon"] = new MatDef(1f, 0.08f, 0.04f, 0.3f, 0, 6f),
            ["MAT_Beacon_Blue"] = new MatDef(0.1f, 0.4f, 1f, 0.3f, 0, 6f),
            ["MAT_Stripe"] = new MatDef(0.75f, 0.6f, 0.12f, 0.6f),
            ["MAT_Sandbag"] = new MatDef(0.36f, 0.31f, 0.21f, 0.95f),
            ["MAT_Concrete"] = new MatDef(0.2f, 0.195f, 0.18f, 0.92f),
            ["MAT_Bark"] = new MatDef(0.16f, 0.11f, 0.075f, 0.95f),
            ["MAT_BarkPine"] = new MatDef(1f, 1f, 1f, 0.92f),
            ["MAT_BarkOak"] = new MatDef(1f, 1f, 1f, 0.92f),
            ["MAT_Needles"] = new MatDef(0.86f, 0.9f, 0.82f, 0.75f),     // doğal koyu çam yeşili (parlak çizgi film yeşili değil)
            ["MAT_Leaves"] = new MatDef(0.9f, 0.9f, 0.8f, 0.7f),         // kurak bölge meşesi: zeytinimsi
            ["MAT_Rock"] = new MatDef(1f, 1f, 1f, 0.88f),
            ["MAT_Flag"] = new MatDef(1f, 1f, 1f, 0.55f),
            ["MAT_GrassGreen"] = new MatDef(1.1f, 1.1f, 1.05f, 0.8f),
            ["MAT_RoofTile"] = new MatDef(0.42f, 0.15f, 0.07f, 0.75f),
            ["MAT_Frame"] = new MatDef(0.8f, 0.8f, 0.78f, 0.5f),
            ["MAT_Door"] = new MatDef(0.22f, 0.12f, 0.06f, 0.7f),
            ["MAT_Stone"] = new MatDef(0.42f, 0.39f, 0.34f, 0.9f),
            ["MAT_Lead"] = new MatDef(0.33f, 0.35f, 0.37f, 0.45f, 0.6f),
            ["MAT_Wood"] = new MatDef(0.25f, 0.17f, 0.1f, 0.85f),
            ["MAT_Plaster_A"] = new MatDef(0.72f, 0.66f, 0.55f, 0.88f),
            ["MAT_Plaster_B"] = new MatDef(0.78f, 0.76f, 0.72f, 0.88f),
            ["MAT_Plaster_C"] = new MatDef(0.70f, 0.55f, 0.40f, 0.88f),
            ["MAT_Plaster_D"] = new MatDef(0.62f, 0.64f, 0.60f, 0.88f),
            ["MAT_GrassDry"] = new MatDef(1.05f, 1.05f, 1.0f, 0.85f),
            ["MAT_Marking"] = new MatDef(0.75f, 0.76f, 0.72f, 0.6f),
            // Divriği: sarımsı kalker kesme taş, taş oyması, toprak dam, kale taşı
            ["MAT_KesmeTas"] = new MatDef(0.8f, 0.7f, 0.53f, 0.85f),
            ["MAT_Oyma"] = new MatDef(0.86f, 0.76f, 0.58f, 0.88f),
            ["MAT_Toprak"] = new MatDef(0.45f, 0.38f, 0.3f, 0.95f),
            ["MAT_KaleTas"] = new MatDef(0.55f, 0.48f, 0.4f, 0.9f),
            // Akdeniz ve Gökpınar: badana, fener kırmızısı, tekne mavisi, açık ahşap, mavi panjur
            ["MAT_BoyaBeyaz"] = new MatDef(0.86f, 0.86f, 0.83f, 0.8f),
            ["MAT_BoyaKirmizi"] = new MatDef(0.62f, 0.08f, 0.06f, 0.55f),
            ["MAT_TekneMavi"] = new MatDef(0.05f, 0.22f, 0.48f, 0.45f),
            ["MAT_AhsapAcik"] = new MatDef(0.48f, 0.34f, 0.2f, 0.7f),
            ["MAT_PanjurMavi"] = new MatDef(0.12f, 0.33f, 0.52f, 0.6f),
            // Ulu Camii: dokuları UcMap'te (renk tonu dokudan gelir)
            ["MAT_UC_Tas"] = new MatDef(1f, 1f, 1f, 0.8f),
            ["MAT_UC_TasMeydan"] = new MatDef(1f, 1f, 1f, 0.8f),
            ["MAT_UC_Oyma"] = new MatDef(1f, 1f, 1f, 0.82f),
            ["MAT_UC_Oyma2"] = new MatDef(1f, 1f, 1f, 0.82f),
            ["MAT_UC_Kursun"] = new MatDef(1f, 1f, 1f, 0.6f),
            ["MAT_UC_Doseme"] = new MatDef(1f, 1f, 1f, 0.8f),
            ["MAT_UC_Ahsap"] = new MatDef(0.2f, 0.12f, 0.07f, 0.75f),
            ["MAT_UC_Demir"] = new MatDef(0.04f, 0.04f, 0.045f, 0.55f, 0.7f),
            ["MAT_UC_Karanlik"] = new MatDef(0.012f, 0.011f, 0.01f, 0.9f),
            ["MAT_UC_Kapi"] = new MatDef(0.2f, 0.11f, 0.055f, 0.65f),
        };

        // Ulu Camii yüzeyleri: UV0 Blender'da dünya ölçekli açıldı (1 UV = döşeme ölçüsü, taş sıraları yatay); UV1 bütün
        // külliyenin tek atlası, Blender'da pişirilen ortam kapatma + yıpranma (HDRP ayrıntı haritası: taşı koyulaştırır).
        // malzeme -> (doku adı, döşeme [m], POM derinliği [cm], ayrıntı atlası)
        const string UcAtlas = "Yapi_UluCami_Detay";
        static readonly Dictionary<string, (string tex, float tile, float pomCm, bool atlas)> UcMap =
            new Dictionary<string, (string, float, float, bool)>
            {
                ["MAT_UC_Tas"] = ("UC_Tas", 8f, 0f, true),
                ["MAT_UC_Oyma"] = ("UC_Oyma", 2f, 3.5f, true),
                ["MAT_UC_Oyma2"] = ("UC_Oyma2", 2f, 2.8f, true),
                ["MAT_UC_Kursun"] = ("UC_Kursun", 4f, 0f, false),
                ["MAT_UC_Doseme"] = ("UC_Doseme", 4f, 0f, false),
                ["MAT_UC_TasMeydan"] = ("UC_Tas", 8f, 0f, false),
            };

        static Texture2D LoadLinear(string name, int maxSize, bool normal = false, bool srgb = false)
        {
            string p = $"{GenTex}/{name}.png";
            var ti = AssetImporter.GetAtPath(p) as TextureImporter;
            if (ti == null) return null;
            bool dirty = false;
            if (normal && ti.textureType != TextureImporterType.NormalMap) { ti.textureType = TextureImporterType.NormalMap; dirty = true; }
            if (!normal && ti.sRGBTexture != srgb) { ti.sRGBTexture = srgb; dirty = true; }
            if (ti.maxTextureSize != maxSize) { ti.maxTextureSize = maxSize; dirty = true; }
            if (ti.anisoLevel != 16) { ti.anisoLevel = 16; dirty = true; }
            if (ti.textureCompression != TextureImporterCompression.CompressedHQ) { ti.textureCompression = TextureImporterCompression.CompressedHQ; dirty = true; }
            if (dirty) ti.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(p);
        }

        static bool ApplyUc(Material m, (string tex, float tile, float pomCm, bool atlas) u)
        {
            var albedo = LoadLinear(u.tex, 4096, false, true);
            if (albedo == null) return false;
            m.SetColor("_BaseColor", Color.white);
            m.SetTexture("_BaseColorMap", albedo);
            m.SetTextureScale("_BaseColorMap", Vector2.one);
            m.SetFloat("_UVBase", 0f);
            var normal = LoadLinear(u.tex + "_Normal", 4096, true);
            if (normal != null) { m.SetTexture("_NormalMap", normal); m.SetFloat("_NormalScale", 1f); }
            var mask = LoadLinear(u.tex + "_Mask", 4096);
            if (mask != null)
            {
                m.SetTexture("_MaskMap", mask);
                m.SetFloat("_MetallicRemapMin", 0f); m.SetFloat("_MetallicRemapMax", 1f);
                m.SetFloat("_SmoothnessRemapMin", 0f); m.SetFloat("_SmoothnessRemapMax", 1f);
                m.SetFloat("_AORemapMin", 0f); m.SetFloat("_AORemapMax", 1f);
            }
            var height = u.pomCm > 0f ? LoadLinear(u.tex + "_Height", 2048) : null;
            if (height != null)
            {
                // Oymalarda paralaks kapatma (POM): oyukların derinliği bakış açısıyla değişir, kabartmalar birbirini örter
                m.SetTexture("_HeightMap", height);
                m.SetFloat("_DisplacementMode", 2f);
                m.SetFloat("_HeightPoMAmplitude", u.pomCm);
                m.SetFloat("_HeightAmplitude", u.pomCm * 0.01f);
                m.SetFloat("_HeightCenter", 1f);
                m.SetFloat("_PPDMinSamples", 6f);
                m.SetFloat("_PPDMaxSamples", 24f);
                m.SetFloat("_PPDLodThreshold", 6f);
                m.SetFloat("_PPDPrimitiveLength", u.tile);
                m.SetFloat("_PPDPrimitiveWidth", u.tile);
                m.SetVector("_InvPrimScale", new Vector4(1f / u.tile, 1f / u.tile, 0f, 0f));
            }
            var atlas = u.atlas ? LoadLinear(UcAtlas, 4096) : null;
            if (atlas != null)
            {
                m.SetTexture("_DetailMap", atlas);
                m.SetFloat("_UVDetail", 1f);
                m.SetVector("_UVDetailsMappingMask", new Vector4(0f, 1f, 0f, 0f));   // GUI'nin yaptığını elle: ayrıntı UV1'den okunur
                m.SetFloat("_LinkDetailsWithBase", 0f);
                m.SetTextureScale("_DetailMap", Vector2.one);
                m.SetFloat("_DetailAlbedoScale", 1f);
                m.SetFloat("_DetailNormalScale", 0f);
                m.SetFloat("_DetailSmoothnessScale", 0f);
            }
            return true;
        }

        // Malzeme -> (renk dokusu, normal dokusu, alfa kesimli yaprak mı)
        const string GenTex = Root + "/Textures/Gen";
        static readonly Dictionary<string, (string albedo, string normal, bool foliage)> TexMap =
            new Dictionary<string, (string, string, bool)>
            {
                ["MAT_BarkPine"] = ("Tex_KabukCam", "Tex_KabukCam_Normal", false),
                ["MAT_BarkOak"] = ("Tex_KabukMese", "Tex_KabukMese_Normal", false),
                ["MAT_Needles"] = ("Tex_CamIgne", null, true),
                ["MAT_Leaves"] = ("Tex_MeseYaprak", null, true),
                ["MAT_Rock"] = ("Ter_Kaya_Renk", "Ter_Kaya_Normal", false),
                ["MAT_Flag"] = ("Tex_Bayrak", null, false),
                ["MAT_GrassGreen"] = ("Tex_OtYesil", null, true),
                ["MAT_GrassDry"] = ("Tex_OtKuru", null, true),
            };

        // UV gerektirmeyen yüzey ayrıntısı: malzeme -> (doku, tekrar ölçeği [1/m], normal şiddeti)
        static readonly Dictionary<string, (string tex, float scale, float normal)> Detail =
            new Dictionary<string, (string, float, float)>
            {
                ["MAT_Body"] = ("Srf_Kompozit", 4f, 0.6f),
                ["MAT_Shell"] = ("Srf_Kompozit", 4f, 0.6f),
                ["MAT_Battery"] = ("Srf_Kompozit", 6f, 0.8f),
                ["MAT_Carbon"] = ("Srf_Karbon", 10f, 0.9f),
                ["MAT_Radome"] = ("Srf_Kompozit", 1.2f, 0.5f),
                ["MAT_Camo"] = ("Srf_BoyaYipranma", 0.45f, 0.8f),
                ["MAT_Camo_Dark"] = ("Srf_BoyaYipranma", 0.45f, 0.8f),
                ["MAT_Rim"] = ("Srf_BoyaYipranma", 1.5f, 0.6f),
                ["MAT_Plaster_A"] = ("Srf_Siva", 0.35f, 1f),
                ["MAT_Plaster_B"] = ("Srf_Siva", 0.35f, 1f),
                ["MAT_Plaster_C"] = ("Srf_Siva", 0.35f, 1f),
                ["MAT_Plaster_D"] = ("Srf_Siva", 0.35f, 1f),
                ["MAT_RoofTile"] = ("Srf_Kiremit", 0.18f, 1.2f),
                ["MAT_KesmeTas"] = ("Srf_KesmeTas", 0.25f, 1.3f),      // 4 m'de bir tekrar: 35-55 cm'lik taş sıraları
                ["MAT_Oyma"] = ("Srf_Oyma", 1.6f, 2.0f),              // 15 cm'lik yıldız geçmeleri
                ["MAT_KaleTas"] = ("Srf_KesmeTas", 0.5f, 1.8f),
                ["MAT_Toprak"] = ("Srf_Beton", 0.3f, 1.2f),
                ["MAT_BoyaBeyaz"] = ("Srf_Siva", 0.35f, 1f),
                ["MAT_Concrete"] = ("Srf_Beton", 0.3f, 0.8f),
                ["MAT_Stone"] = ("Srf_Beton", 0.5f, 1f),
                ["MAT_Sandbag"] = ("Srf_Siva", 1.2f, 1f),
                ["MAT_Frame"] = ("Srf_Siva", 0.8f, 0.4f),
            };

        // Fotoğraf tabanlı dokular (Poly Haven, CC0; tools/fetch_assets.py indirir, sync_unity.ps1 kopyalar).
        // Varsa üretilen dokuların yerine geçer. triplanar > 0: UV yerine dünya uzayında üç yönlü eşleme (1/m).
        const string PhotoTex = Root + "/Textures/Photo";
        static readonly Dictionary<string, (string id, float triplanar)> PhotoMap =
            new Dictionary<string, (string, float)>
            {
                ["MAT_BarkPine"] = ("pine_bark", 0f),
                ["MAT_BarkOak"] = ("bark_brown_02", 0f),
                ["MAT_Rock"] = ("boulder_01", 0.45f),
                ["MAT_Stone"] = ("boulder_01", 1.2f),
                ["MAT_KaleTas"] = ("boulder_01", 0.55f),      // Divriği kalesi ve ev zemin katları: yontulmamış moloz taş
            };

        static Texture2D PhotoImport(string path, bool normal, bool srgb)
        {
            var ti = AssetImporter.GetAtPath(path) as TextureImporter;
            if (ti == null) return null;
            bool dirty = false;
            if (normal && ti.textureType != TextureImporterType.NormalMap) { ti.textureType = TextureImporterType.NormalMap; dirty = true; }
            if (!normal && ti.sRGBTexture != srgb) { ti.sRGBTexture = srgb; dirty = true; }
            if (ti.maxTextureSize != 2048) { ti.maxTextureSize = 2048; dirty = true; }
            if (ti.anisoLevel != 16) { ti.anisoLevel = 16; dirty = true; }
            if (ti.textureCompression != TextureImporterCompression.CompressedHQ) { ti.textureCompression = TextureImporterCompression.CompressedHQ; dirty = true; }
            if (dirty) ti.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        // (renk, normal, HDRP maske: R metal, G ortam kapatma, B yükseklik, A pürüzsüzlük); yoksa renk null
        static (Texture2D albedo, Texture2D normal, Texture2D mask) Photo(string id)
        {
            if (string.IsNullOrEmpty(id)) return (null, null, null);
            string b = $"{PhotoTex}/{id}";
            var albedo = PhotoImport($"{b}_diff_2k.jpg", false, true);
            if (albedo == null) return (null, null, null);
            return (albedo, PhotoImport($"{b}_nor_gl_2k.jpg", true, false), PhotoImport($"{b}_mask_2k.png", false, false));
        }

        static bool ApplyPhoto(Material m, string id, float triplanar)
        {
            var (albedo, normal, mask) = Photo(id);
            if (albedo == null) return false;
            m.SetColor("_BaseColor", Color.white);
            m.SetTexture("_BaseColorMap", albedo);
            if (normal != null) { m.SetTexture("_NormalMap", normal); m.SetFloat("_NormalScale", 1f); }
            if (mask != null)
            {
                m.SetTexture("_MaskMap", mask);
                m.SetFloat("_SmoothnessRemapMin", 0f);
                m.SetFloat("_SmoothnessRemapMax", 1f);
                m.SetFloat("_AORemapMin", 0f);
                m.SetFloat("_AORemapMax", 1f);
            }
            m.SetFloat("_Metallic", 0f);
            if (triplanar > 0f)
            {
                m.SetFloat("_UVBase", 5f);                   // Triplanar
                m.SetFloat("_ObjectSpaceUVMapping", 0f);     // dünya uzayı: kayanın boyu ne olursa olsun aynı ölçek
                m.SetFloat("_TexWorldScale", triplanar);
                m.SetFloat("_InvTilingScale", 1f / triplanar);
            }
            return true;
        }

        // Yapraklar arkadan gelen güneşi geçirsin (HDRP "Foliage" yayılım profili varsa)
        static void TryFoliageTranslucency(Material m)
        {
            var guid = AssetDatabase.FindAssets("Foliage t:DiffusionProfileSettings").FirstOrDefault();
            if (guid == null) return;
            var profile = AssetDatabase.LoadAssetAtPath<Object>(AssetDatabase.GUIDToAssetPath(guid));
            var method = typeof(HDMaterial).GetMethods(BindingFlags.Public | BindingFlags.Static)
                .FirstOrDefault(mi => mi.Name == "SetDiffusionProfile" && mi.GetParameters().Length == 2);
            if (profile == null || method == null) return;
            try
            {
                m.SetFloat("_MaterialID", 5f);   // Translucent
                method.Invoke(null, new object[] { m, profile });
                m.SetFloat("_Thickness", 0.25f);
            }
            catch (Exception e) { Debug.LogWarning("[SuruIHA] Yaprak ışık geçirgenliği: " + e.Message); }
        }

        static Texture2D LoadTex(string name, bool normal, bool alpha)
        {
            if (name == null) return null;
            string p = $"{GenTex}/{name}.png";
            var ti = AssetImporter.GetAtPath(p) as TextureImporter;
            if (ti == null) return null;
            bool dirty = false;
            if (normal && ti.textureType != TextureImporterType.NormalMap) { ti.textureType = TextureImporterType.NormalMap; dirty = true; }
            if (alpha && !ti.mipMapsPreserveCoverage)
            {
                ti.alphaIsTransparency = true;
                ti.mipMapsPreserveCoverage = true;
                ti.alphaTestReferenceValue = 0.45f;
                dirty = true;
            }
            if (ti.maxTextureSize != 2048) { ti.maxTextureSize = 2048; dirty = true; }
            if (ti.anisoLevel != 8) { ti.anisoLevel = 8; dirty = true; }
            if (dirty) ti.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(p);
        }

        static Dictionary<string, Material> BuildMaterials()
        {
            var result = new Dictionary<string, Material>();
            var shader = Shader.Find("HDRP/Lit");
            foreach (var kv in Defs)
            {
                string path = $"{Root}/Materials/{kv.Key}.mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (m == null)
                {
                    m = new Material(shader);
                    AssetDatabase.CreateAsset(m, path);
                }
                var d = kv.Value;
                m.shader = shader;
                // doğrusal -> sRGB renk seçici değeri (dokulu malzemelerde ton çarpanı, 1'den büyük olabilir)
                m.SetColor("_BaseColor", TexMap.ContainsKey(kv.Key) ? new Color(d.c.r, d.c.g, d.c.b, 1f) : d.c.gamma);
                m.SetFloat("_Smoothness", d.smooth);
                m.SetFloat("_Metallic", d.metal);
                if (d.emit > 0)
                {
                    m.SetColor("_EmissiveColor", d.c * d.emit);
                    m.SetColor("_EmissiveColorLDR", d.c.gamma);
                    m.SetFloat("_EmissiveIntensity", d.emit);
                    m.SetFloat("_EmissiveExposureWeight", 0f);
                    m.SetFloat("_UseEmissiveIntensity", 0f);
                }
                if (UcMap.TryGetValue(kv.Key, out var uc) && ApplyUc(m, uc))
                {
                    m.SetFloat("_Metallic", 1f);        // maske haritasının R kanalı belirler
                }
                else if (PhotoMap.TryGetValue(kv.Key, out var ph) && ApplyPhoto(m, ph.id, ph.triplanar))
                {
                    m.enableInstancing = true;
                }
                else if (TexMap.TryGetValue(kv.Key, out var tx))
                {
                    var albedo = LoadTex(tx.albedo, false, tx.foliage);
                    var normal = LoadTex(tx.normal, true, false);
                    if (albedo != null) m.SetTexture("_BaseColorMap", albedo);
                    if (normal != null) { m.SetTexture("_NormalMap", normal); m.SetFloat("_NormalScale", 1.2f); }
                    if (kv.Key == "MAT_Rock")
                    {
                        m.SetTextureScale("_BaseColorMap", Vector2.one);
                    }
                    if (tx.foliage)
                    {
                        m.SetFloat("_AlphaCutoffEnable", 1f);
                        m.SetFloat("_AlphaCutoff", 0.45f);
                        m.SetFloat("_AlphaCutoffShadow", 0.45f);
                        m.SetFloat("_UseShadowThreshold", 1f);
                        m.SetFloat("_DoubleSidedEnable", 1f);
                        m.SetFloat("_DoubleSidedNormalMode", 2f);   // yok: özel (dışa bakan) normaller kullanılır
                        m.SetFloat("_Metallic", 0f);
                    }
                    m.enableInstancing = true;
                }
                else if (Detail.TryGetValue(kv.Key, out var dt))
                {
                    var albedo = LoadTex(dt.tex, false, false);
                    var normal = LoadTex(dt.tex + "_Normal", true, false);
                    if (albedo != null) m.SetTexture("_BaseColorMap", albedo);
                    if (normal != null) { m.SetTexture("_NormalMap", normal); m.SetFloat("_NormalScale", dt.normal); }
                    m.SetFloat("_UVBase", 5f);                 // Triplanar
                    m.SetFloat("_ObjectSpaceUVMapping", 1f);   // nesneyle birlikte hareket etsin (İHA uçarken kaymasın)
                    m.SetFloat("_TexWorldScale", dt.scale);
                    m.SetFloat("_InvTilingScale", 1f / dt.scale);
                }
                if (kv.Key == "MAT_Leaves" || kv.Key == "MAT_Needles")
                    TryFoliageTranslucency(m);
                HDMaterial.ValidateMaterial(m);
                EditorUtility.SetDirty(m);
                result[kv.Key] = m;
            }
            AssetDatabase.SaveAssets();
            return result;
        }

        // ------------------------------------------------------------------ prefab'lar
        class Prefabs
        {
            public GameObject drone, jammer, gcs, radar;
            public List<GameObject> pines = new List<GameObject>(), oaks = new List<GameObject>(),
                rocks = new List<GameObject>(), shrubs = new List<GameObject>(), grass = new List<GameObject>(),
                houses = new List<GameObject>();
            public GameObject mosque, pole;
            public readonly Dictionary<string, GameObject> named = new Dictionary<string, GameObject>();   // bütün prefab'lar adıyla
        }

        static Prefabs BuildPrefabs(Dictionary<string, Material> mats)
        {
            var p = new Prefabs();
            var fbxs = AssetDatabase.FindAssets("t:Model", new[] { Root + "/Models" })
                .Select(AssetDatabase.GUIDToAssetPath).Where(x => x.EndsWith(".fbx")).OrderBy(x => x).ToList();
            foreach (var path in fbxs)
            {
                var imp = (ModelImporter)AssetImporter.GetAtPath(path);
                imp.importAnimation = false;
                imp.importCameras = false;
                imp.importLights = false;
                imp.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
                // Projedeki MAT_* malzemelerine eşle (FBX'in kendi malzemeleri yerine)
                foreach (var kv in mats)
                {
                    imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), kv.Key), kv.Value);
                }
                imp.SaveAndReimport();

                var model = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                string name = Path.GetFileNameWithoutExtension(path).Replace("SuruIHA_", "");
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
                ReplaceMaterials(inst, mats);
                GameObject wrapper = inst;
                if (name == "Drone")
                {
                    // Modelin önü +Z'ye baksın: gimbal önde olmalı
                    var gimbal = SwarmVisualizer.FindDeep(inst.transform, "Camera_Gimbal");
                    var r = new GameObject("Drone");
                    inst.transform.SetParent(r.transform, false);
                    if (gimbal != null && gimbal.GetComponent<Renderer>() != null &&
                        gimbal.GetComponent<Renderer>().bounds.center.z < 0)
                        inst.transform.localRotation = Quaternion.Euler(0, 180, 0);
                    wrapper = r;
                }
                else if (name == "Jammer" || name == "GCS" || name == "Radar")
                {
                    var r = new GameObject(name);
                    inst.transform.SetParent(r.transform, false);
                    wrapper = r;
                }
                else if (name.StartsWith("Grass"))
                {
                    // Arazi detay mesh'i: kökte MeshFilter + MeshRenderer olmalı
                    var mf = inst.GetComponentInChildren<MeshFilter>();
                    var mr = inst.GetComponentInChildren<MeshRenderer>();
                    var d = new GameObject(name);
                    d.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
                    d.AddComponent<MeshRenderer>().sharedMaterial = mr.sharedMaterial;
                    Object.DestroyImmediate(inst);
                    wrapper = d;
                }
                else
                {
                    // Arazi ağacı olarak kullanılacak: kökte LODGroup şart
                    ConfigureLods(inst, name.StartsWith("House") || name.StartsWith("Mosque") || name.StartsWith("Pole") ? new[] { 0.002f }
                                       : name.StartsWith("Yapi") ? new[] { 0.0015f }
                                       : name.StartsWith("Tree") ? new[] { 0.07f, 0.006f }
                                       : name.StartsWith("Shrub") ? new[] { 0.012f } : new[] { 0.006f });
                }
                foreach (var rend in wrapper.GetComponentsInChildren<Renderer>())
                {
                    // Ot kartları gölge düşürmesin: birbirlerine koyu üçgenler çiziyorlar
                    rend.shadowCastingMode = name.StartsWith("Grass") ? ShadowCastingMode.Off : ShadowCastingMode.On;
                }
                string prefabPath = $"{Root}/Prefabs/{name}.prefab";
                var prefab = PrefabUtility.SaveAsPrefabAsset(wrapper, prefabPath);
                Object.DestroyImmediate(wrapper);
                Debug.Log($"[SuruIHA] Prefab: {prefabPath}  boyut={Bounds(prefab)}");

                p.named[name] = prefab;
                if (name == "Drone") p.drone = prefab;
                else if (name == "Jammer") p.jammer = prefab;
                else if (name == "GCS") p.gcs = prefab;
                else if (name == "Radar") p.radar = prefab;
                else if (name.StartsWith("Tree_Pine")) p.pines.Add(prefab);
                else if (name.StartsWith("Tree_Oak")) p.oaks.Add(prefab);
                else if (name.StartsWith("Rock")) p.rocks.Add(prefab);
                else if (name.StartsWith("Shrub")) p.shrubs.Add(prefab);
                else if (name.StartsWith("Grass")) p.grass.Add(prefab);
                else if (name.StartsWith("House")) p.houses.Add(prefab);
                else if (name.StartsWith("Mosque")) p.mosque = prefab;
                else if (name.StartsWith("Pole")) p.pole = prefab;
            }
            return p;
        }

        static void ConfigureLods(GameObject go, float[] heights)
        {
            if (!go.TryGetComponent<LODGroup>(out var lg)) lg = go.AddComponent<LODGroup>();
            var renderers = go.GetComponentsInChildren<Renderer>();
            var lods = new List<LOD>();
            for (int i = 0; i < heights.Length; i++)
            {
                var rs = renderers.Where(r => r.name.EndsWith("_LOD" + i)).ToArray();
                if (rs.Length == 0 && i == 0) rs = renderers;
                if (rs.Length == 0) continue;
                lods.Add(new LOD(heights[i], rs));
            }
            lg.SetLODs(lods.ToArray());
            lg.fadeMode = LODFadeMode.CrossFade;
            lg.animateCrossFading = true;
            lg.RecalculateBounds();
        }

        static void ReplaceMaterials(GameObject go, Dictionary<string, Material> mats)
        {
            foreach (var r in go.GetComponentsInChildren<Renderer>())
            {
                var arr = r.sharedMaterials;
                for (int i = 0; i < arr.Length; i++)
                {
                    if (arr[i] == null) continue;
                    string n = arr[i].name.Replace(" (Instance)", "");
                    int dot = n.IndexOf('.');
                    if (dot > 0) n = n.Substring(0, dot);   // Blender "MAT_X.001" kopyaları
                    if (mats.TryGetValue(n, out var m)) arr[i] = m;
                }
                r.sharedMaterials = arr;
            }
        }

        static string Bounds(GameObject g)
        {
            var rs = g.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return "-";
            var b = rs[0].bounds;
            foreach (var r in rs) b.Encapsulate(r.bounds);
            return $"{b.size.x:0.00}x{b.size.y:0.00}x{b.size.z:0.00} m, merkez {b.center}";
        }

        // ------------------------------------------------------------------ sahne
        static void BuildScene(Prefabs prefabs)
        {
            // Şablonun gökyüzü/güneş/kamera ayarlı sahnesinden başla
            if (!File.Exists(ScenePath))
                AssetDatabase.CopyAsset("Assets/OutdoorsScene.unity", ScenePath);
            var scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            foreach (var go in scene.GetRootGameObjects())
                if (go.name is "Arazi" or "SuruSistemi" or "UzakArazi" or "Koy" or "ElektrikHatti" or "KarliBolge" or "Kizilirmak"
                    or "Divrigi" or "Gokpinar" or "AkdenizKiyisi")
                    Object.DestroyImmediate(go);

            // Güneş: ikindi ışığı, uzun gölgeler
            var sun = GameObject.Find("Sun");
            if (sun != null)
            {
                sun.transform.rotation = Quaternion.Euler(31f, -42f, 0f);
                var l = sun.GetComponent<Light>();
                l.useColorTemperature = true;
                l.colorTemperature = 5300f;
                var hdl = sun.GetComponent<HDAdditionalLightData>();
                if (hdl != null)
                {
                    foreach (var (name, arg) in new (string, object)[] { ("SetShadowResolutionOverride", false), ("SetShadowResolutionLevel", 3) })
                    {
                        var mi = typeof(HDAdditionalLightData).GetMethod(name, new[] { arg.GetType() });
                        mi?.Invoke(hdl, new[] { arg });
                    }
                }
            }

            ConfigureVolume();

            EditorUtility.DisplayProgressBar("SürüİHA", "Arazi", 0.5f);
            var terrain = BuildTerrain(prefabs);
            ExportHeightmap(terrain);
            EditorUtility.DisplayProgressBar("SürüİHA", "Köy ve elektrik hattı", 0.9f);
            BuildVillage(prefabs, terrain);
            BuildPowerLine(prefabs, terrain);
            EditorUtility.DisplayProgressBar("SürüİHA", "Karlı bölge", 0.93f);
            BuildSnowRegion(prefabs);
            EditorUtility.DisplayProgressBar("SürüİHA", "Kızılırmak", 0.96f);
            BuildRiverRegion(prefabs);
            EditorUtility.DisplayProgressBar("SürüİHA", "Divriği", 0.97f);
            BuildDivrigiRegion(prefabs);
            EditorUtility.DisplayProgressBar("SürüİHA", "Gökpınar Gölü", 0.98f);
            BuildGokpinarRegion(prefabs);
            EditorUtility.DisplayProgressBar("SürüİHA", "Akdeniz kıyısı", 0.99f);
            BuildSeaRegion(prefabs);

            // Simülasyon nesneleri
            var sys = new GameObject("SuruSistemi");
            sys.AddComponent<SwarmReceiver>();
            var vis = sys.AddComponent<SwarmVisualizer>();
            vis.droneModel = prefabs.drone;
            vis.jammerModel = prefabs.jammer;
            vis.radarModel = prefabs.radar;
            vis.gcsModel = prefabs.gcs;
            vis.droneScale = 3f;
            vis.autoGroundSnap = false;   // arazi zaten y=0'da
            vis.materials = SaveRuntimeMaterials(vis.glow);

            var cam = Camera.main;
            if (cam != null)
            {
                cam.farClipPlane = 8000f;
                cam.nearClipPlane = 0.5f;
                cam.transform.position = new Vector3(-320f, 140f, -380f);
                cam.transform.LookAt(new Vector3(60f, 30f, 60f));
                if (!cam.TryGetComponent<SwarmCamera>(out var sc)) sc = cam.gameObject.AddComponent<SwarmCamera>();
                sc.visualizer = vis;
                sc.orbitDistance = 230f;
                if (!cam.TryGetComponent<SwarmHud>(out var hud)) hud = cam.gameObject.AddComponent<SwarmHud>();
                hud.visualizer = vis;
                hud.cam = sc;
                var hd = cam.GetComponent<HDAdditionalCameraData>();
                if (hd != null)
                {
                    hd.antialiasing = HDAdditionalCameraData.AntialiasingMode.TemporalAntialiasing;
                    hd.TAAQuality = HDAdditionalCameraData.TAAQualityLevel.High;
                }
            }

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
        }

        // Görselleştiricinin kodla ürettiği malzemeleri asset olarak kaydeder: böylece bağımsız
        // uygulamada (build) da doğru shader varyantlarıyla gelirler.
        static SwarmVisualizer.Materials SaveRuntimeMaterials(float glow)
        {
            string dir = $"{Root}/Materials/Runtime";
            if (!AssetDatabase.IsValidFolder(dir)) AssetDatabase.CreateFolder($"{Root}/Materials", "Runtime");
            var m = new SwarmVisualizer.Materials();
            m.FillMissing(glow);
            foreach (var f in typeof(SwarmVisualizer.Materials).GetFields())
            {
                if (f.FieldType != typeof(Material)) continue;
                var mat = (Material)f.GetValue(m);
                string path = $"{dir}/RT_{f.Name}.mat";
                // Kodla üretilen doku (ısı haritasının yer tutucusu) kayıtta düşer: önce alınır, malzemenin içine
                // alt varlık olarak eklenip yeniden bağlanır. Yoksa HDRP dokulu parlama varyantını derlemeye almaz.
                var tex = mat.HasProperty("_BaseColorMap") ? mat.GetTexture("_BaseColorMap") : null;
                AssetDatabase.DeleteAsset(path);
                AssetDatabase.CreateAsset(mat, path);
                var saved = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (tex != null && !AssetDatabase.Contains(tex))
                {
                    AssetDatabase.AddObjectToAsset(tex, path);
                    SwarmMaterials.SetOverlayTexture(saved, tex);
                    HDMaterial.ValidateMaterial(saved);
                    EditorUtility.SetDirty(saved);
                }
                f.SetValue(m, saved);
            }
            AssetDatabase.SaveAssets();
            return m;
        }

        // Python simülasyonu aynı araziyi kullansın diye yükseklik haritasını dışa aktarır.
        // Biçim: 601x601 float32 (küçük-endian), satır = kuzey (z), sütun = doğu (x), değer = dünya y'si (m).
        // origin: bölgenin dünya konumu (karlı bölge 12 km doğuda); suffix: dosya adı eki ("_kar")
        static void ExportHeightmap(Terrain t, Vector3 origin = default, string suffix = "", float floorY = float.NegativeInfinity)
        {
            const int n = 601;
            const float gridOrigin = -1200f, step = 4f;
            var buf = new byte[n * n * 4];
            for (int j = 0; j < n; j++)
            for (int i = 0; i < n; i++)
            {
                float x = gridOrigin + i * step, z = gridOrigin + j * step;
                float y = Mathf.Max(t.SampleHeight(new Vector3(origin.x + x, 0, origin.z + z)) + t.transform.position.y, floorY);
                System.Buffer.BlockCopy(BitConverter.GetBytes(y), 0, buf, (j * n + i) * 4, 4);
            }
            string dir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Arazi"));
            Directory.CreateDirectory(dir);
            File.WriteAllBytes(Path.Combine(dir, $"arazi_yukseklik{suffix}.bin"), buf);
            File.WriteAllText(Path.Combine(dir, $"arazi_yukseklik{suffix}.json"),
                $"{{\"n\": {n}, \"origin\": {gridOrigin}, \"step\": {step}}}");
            Debug.Log("[SuruIHA] Yükseklik haritası: " + dir);
        }

        // ------------------------------------------------------------------ köy ve elektrik hattı
        static float GroundY(Terrain t, float x, float z) => t.SampleHeight(new Vector3(x, 0, z)) + t.transform.position.y;

        static void BuildVillage(Prefabs p, Terrain t)
        {
            if (p.houses.Count == 0) return;
            var root = new GameObject("Koy").transform;
            var rng = new System.Random(5);
            float yaw = -14f;   // sokaklar tarlalarla aynı yönde
            if (p.mosque != null)
            {
                var c = VillageXZ + VillageU * 14f + VillageV * 16f;
                var m = (GameObject)PrefabUtility.InstantiatePrefab(p.mosque, root);
                m.transform.SetPositionAndRotation(new Vector3(c.x, GroundY(t, c.x, c.y), c.y), Quaternion.Euler(0, yaw + 180f, 0));
            }
            int n = 0;
            for (int street = 0; street < 2; street++)
            for (int side = -1; side <= 1; side += 2)
            for (int k = -5; k <= 5; k++)
            {
                if (Mathf.Abs(k) <= 1) continue;                  // meydan
                if (rng.NextDouble() < 0.18) continue;            // boş arsa
                float along = k * 15f + (float)(rng.NextDouble() - 0.5) * 4f;
                float off = side * (11f + (float)rng.NextDouble() * 4f);
                Vector2 pos = street == 0 ? VillageXZ + VillageU * along + VillageV * off
                                          : VillageXZ + VillageV * along * 0.85f + VillageU * off;
                float face = street == 0 ? (side > 0 ? 180f : 0f) : (side > 0 ? -90f : 90f);
                var h = (GameObject)PrefabUtility.InstantiatePrefab(p.houses[rng.Next(p.houses.Count)], root);
                h.transform.SetPositionAndRotation(new Vector3(pos.x, GroundY(t, pos.x, pos.y), pos.y),
                    Quaternion.Euler(0, yaw + face + (float)(rng.NextDouble() - 0.5) * 6f, 0));
                n++;
            }
            GameObjectUtility.SetStaticEditorFlags(root.gameObject, StaticEditorFlags.BatchingStatic);
            Debug.Log($"[SuruIHA] Köy: {n} ev + cami");
        }

        static void BuildPowerLine(Prefabs p, Terrain t)
        {
            if (p.pole == null) return;
            var root = new GameObject("ElektrikHatti").transform;
            var wireMat = AssetDatabase.LoadAssetAtPath<Material>($"{Root}/Materials/MAT_Black.mat");
            // Ana yolun 10 m doğusunda, her 55 m'de bir direk
            var pts = new List<Vector3>();
            for (float z = -1150f; z <= 1150f; z += 55f)
            {
                float x = RoadBX(z) + 10f;
                pts.Add(new Vector3(x, GroundY(t, x, z), z));
            }
            var poles = new List<Transform>();
            for (int i = 0; i < pts.Count; i++)
            {
                Vector3 d = (pts[Mathf.Min(i + 1, pts.Count - 1)] - pts[Mathf.Max(i - 1, 0)]);
                d.y = 0;
                var g = (GameObject)PrefabUtility.InstantiatePrefab(p.pole, root);
                g.transform.SetPositionAndRotation(pts[i], Quaternion.LookRotation(d.normalized));
                poles.Add(g.transform);
            }
            int wires = 0;
            for (int i = 0; i + 1 < poles.Count; i++)
            for (int w = 0; w < 3; w++)
            {
                var a = SwarmVisualizer.FindDeep(poles[i], "Tel_" + w);
                var b = SwarmVisualizer.FindDeep(poles[i + 1], "Tel_" + w);
                if (a == null || b == null) continue;
                var lr = new GameObject("Tel").AddComponent<LineRenderer>();
                lr.transform.SetParent(root, false);
                lr.sharedMaterial = wireMat;
                lr.widthMultiplier = 0.035f;
                lr.positionCount = 12;
                lr.useWorldSpace = true;
                lr.shadowCastingMode = ShadowCastingMode.Off;
                for (int k = 0; k < 12; k++)
                {
                    float u = k / 11f;
                    var q = Vector3.Lerp(a.position, b.position, u);
                    q.y -= 1.3f * 4f * u * (1f - u);      // sarkma (zincir eğrisine yakın parabol)
                    lr.SetPosition(k, q);
                }
                wires++;
            }
            Debug.Log($"[SuruIHA] Elektrik hattı: {poles.Count} direk, {wires} tel");
        }

        // ------------------------------------------------------------------ gökyüzü, bulut, sis
        static void ConfigureVolume()
        {
            var vol = Object.FindAnyObjectByType<Volume>();
            if (vol == null) return;
            string profPath = $"{Root}/Settings/SuruIHA_GokyuzuProfili.asset";
            var prof = AssetDatabase.LoadAssetAtPath<VolumeProfile>(profPath);
            if (prof == null)
            {
                AssetDatabase.CopyAsset(AssetDatabase.GetAssetPath(vol.sharedProfile), profPath);
                prof = AssetDatabase.LoadAssetAtPath<VolumeProfile>(profPath);
            }
            vol.sharedProfile = prof;

            var clouds = Get<VolumetricClouds>(prof);
            SetParam(clouds, "enable", true);

            var fog = Get<Fog>(prof);
            SetParam(fog, "enabled", true);
            SetParam(fog, "meanFreePath", 2400f);             // uzak tepeler hafif puslu (hava perspektifi)
            SetParam(fog, "baseHeight", 0f);
            SetParam(fog, "maximumHeight", 600f);

            SetParam(clouds, "shadows", true);                 // bulut gölgeleri araziye düşsün
            SetParam(clouds, "shadowOpacity", 0.35f);
            var exp = Get<Exposure>(prof);
            SetParam(exp, "compensation", 0.4f);
            SetParam(fog, "enableVolumetricFog", true);         // güneş huzmeleri
            SetParam(fog, "anisotropy", 0.65f);
            SetParam(fog, "depthExtent", 450f);
            SetParam(fog, "albedo", new Color(0.92f, 0.88f, 0.82f));

            var contact = Get<ContactShadows>(prof);
            SetParam(contact, "enable", true);
            SetParam(contact, "length", 0.25f);
            var micro = Get<MicroShadowing>(prof);
            SetParam(micro, "enable", true);

            var color = Get<ColorAdjustments>(prof);
            SetParam(color, "contrast", 10f);
            SetParam(color, "saturation", -6f);
            var wb = Get<WhiteBalance>(prof);
            SetParam(wb, "temperature", 4f);
            var vig = Get<Vignette>(prof);
            SetParam(vig, "intensity", 0.2f);
            SetParam(vig, "smoothness", 0.35f);
            var grain = Get<FilmGrain>(prof);
            SetParam(grain, "intensity", 0.1f);
            SetParam(grain, "response", 0.8f);
            var blur = Get<MotionBlur>(prof);
            SetParam(blur, "intensity", 0.35f);

            var bloom = Get<Bloom>(prof);
            SetParam(bloom, "intensity", 0.18f);
            SetParam(bloom, "scatter", 0.6f);

            var water = Get<WaterRendering>(prof);
            SetParam(water, "enable", true);                  // HDRP su yüzeyleri (yalnızca Akdeniz ve Gökpınar'da açık)

            var ao = Get<ScreenSpaceAmbientOcclusion>(prof);
            SetParam(ao, "intensity", 1.2f);

            var shadows = Get<HDShadowSettings>(prof);
            SetParam(shadows, "maxShadowDistance", 1600f);

            // Gerçekçilik: parlak yüzeylerde ekran uzayı yansıma, gölgelerde yansıyan ışık (SSGI)
            var ssr = Get<ScreenSpaceReflection>(prof);
            SetParam(ssr, "enabled", true);
            var ssgi = Get<GlobalIllumination>(prof);
            SetParam(ssgi, "enable", true);

            var tone = Get<Tonemapping>(prof);
            SetParam(tone, "mode", TonemappingMode.ACES);

            EditorUtility.SetDirty(prof);
        }

        static T Get<T>(VolumeProfile p) where T : VolumeComponent
        {
            if (!p.TryGet<T>(out var c))
            {
                c = p.Add<T>(true);
                c.name = typeof(T).Name;
                AssetDatabase.AddObjectToAsset(c, p);
            }
            c.active = true;
            return c;
        }

        // VolumeParameter alanlarını isimle ayarlar (HDRP sürümleri arasında daha dayanıklı)
        static void SetParam(VolumeComponent comp, string field, object value)
        {
            var f = comp.GetType().GetField(field, BindingFlags.Public | BindingFlags.Instance);
            if (f == null)
            {
                // Bazı ayarlar özelliktir (ör. VolumetricClouds.cloudPreset): doğrudan atanır
                var prop = comp.GetType().GetProperty(field, BindingFlags.Public | BindingFlags.Instance);
                if (prop != null && prop.CanWrite)
                {
                    try { prop.SetValue(comp, value); }
                    catch (Exception e) { Debug.LogWarning($"[SuruIHA] {field}: {e.Message}"); }
                    return;
                }
                Debug.LogWarning($"[SuruIHA] {comp.GetType().Name}.{field} bulunamadı");
                return;
            }
            var param = f.GetValue(comp) as VolumeParameter;
            if (param == null) return;
            param.overrideState = true;
            var valueProp = param.GetType().GetProperty("value");
            try { valueProp?.SetValue(param, value); }
            catch (Exception e) { Debug.LogWarning($"[SuruIHA] {field}: {e.Message}"); }
        }

        // ------------------------------------------------------------------ arazi
        static Terrain BuildTerrain(Prefabs prefabs)
        {
            int res = 1025;
            var td = new TerrainData { heightmapResolution = res };
            td.size = new Vector3(TerrainSize, TerrainHeight, TerrainSize);
            // Önce asset olarak kaydet: aksi halde karışım (splat) dokuları diske yazılmaz
            Directory.CreateDirectory(Root + "/Terrain");
            string tdPath = $"{Root}/Terrain/AraziVerisi.asset";
            AssetDatabase.DeleteAsset(tdPath);
            AssetDatabase.CreateAsset(td, tdPath);
            var heights = new float[res, res];
            for (int j = 0; j < res; j++)
            for (int i = 0; i < res; i++)
            {
                float x = (i / (float)(res - 1) - 0.5f) * TerrainSize;
                float z = (j / (float)(res - 1) - 0.5f) * TerrainSize;
                heights[j, i] = HeightAt(x, z) / TerrainHeight;
            }
            td.SetHeights(0, 0, heights);

            // Doku katmanları: 0 çimen, 1 bozkır, 2 sürülmüş tarla, 3 anız, 4 kaya, 5 çakıl, 6 toprak (tepelerde iri lekeler)
            var layers = new[]
            {
                // Fotoğraf dokusu varsa o kullanılır (döşeme boyu gerçek boyuna yakın; havadan bakınca tekrar seçilmesin)
                Layer("Cimen", "Ter_Cimen", new Color(0.29f, 0.36f, 0.16f), new Color(0.2f, 0.27f, 0.1f), 6f, 0.05f, 1, "aerial_grass_rock", 15f),
                Layer("Bozkir", "Ter_Bozkir", new Color(0.55f, 0.5f, 0.31f), new Color(0.4f, 0.36f, 0.21f), 7f, 0.04f, 2, "withered_grass", 7f,
                      new Color(0.68f, 0.68f, 0.53f)),    // kuru ot: zeytinimsi gri yeşil, kum gibi açık durmasın
                Layer("Tarla", "Ter_Tarla", new Color(0.42f, 0.34f, 0.24f), new Color(0.3f, 0.24f, 0.17f), 9f, 0.06f, 3, "farm_soil", 5f),
                Layer("Aniz", "Ter_Aniz", new Color(0.7f, 0.6f, 0.4f), new Color(0.55f, 0.46f, 0.3f), 7f, 0.05f, 5, "withered_grass", 4f,
                      new Color(1f, 0.88f, 0.62f)),       // biçilmiş ekin: altın sarısı saman
                Layer("Kaya", "Ter_Kaya", new Color(0.47f, 0.46f, 0.44f), new Color(0.3f, 0.3f, 0.29f), 22f, 0.12f, 4, "aerial_rocks_02", 40f),
                Layer("Cakil", "Ter_Cakil", new Color(0.55f, 0.52f, 0.46f), new Color(0.4f, 0.38f, 0.33f), 5f, 0.08f, 6, "gravelly_sand", 4f),
                Layer("Toprak", "Ter_Tarla", new Color(0.45f, 0.36f, 0.25f), new Color(0.32f, 0.25f, 0.17f), 9f, 0.05f, 7, "dirt_aerial_02", 25f,
                      new Color(0.9f, 0.88f, 0.84f)),
            };
            td.terrainLayers = layers;
            int amRes = 2048;
            td.alphamapResolution = amRes;
            var am = new float[amRes, amRes, layers.Length];
            var roads = Roads();
            var w = new float[layers.Length];
            var fw = new float[layers.Length];
            for (int j = 0; j < amRes; j++)
            for (int i = 0; i < amRes; i++)
            {
                float u = i / (float)(amRes - 1), v = j / (float)(amRes - 1);
                float x = (u - 0.5f) * TerrainSize, z = (v - 0.5f) * TerrainSize;
                float h = HeightAt(x, z);
                float slope = td.GetSteepness(u, v);
                float r = new Vector2(x, z).magnitude;
                Array.Clear(w, 0, w.Length);

                // Tepeler: bozkır, nemli çukurlarda ve orman altında çimen
                float moist = Fbm(x * 0.003f + 11f, z * 0.003f - 7f, 4);
                float forest = Fbm(x * 0.0035f + 100f, z * 0.0035f - 50f, 4);
                w[1] = 1f;
                w[0] = Mathf.Clamp01((moist - 0.52f) * 4f) + Mathf.Clamp01((forest - 0.55f) * 4f) * 0.8f;
                // Kuzeye bakan yamaçlar daha az güneş alır, nemli kalır: yeşil (Anadolu bozkırında belirgin)
                var nrm = td.GetInterpolatedNormal(u, v);
                w[0] += Mathf.Clamp01(nrm.z * 3f) * Mathf.Clamp01((slope - 5f) / 10f) * (0.6f + 0.6f * moist);
                // Bahar bozkırı: tepelerde kuru otun arasında geniş yeşil çayır lekeleri (tek renk kum tepesi gibi durmasın)
                w[0] += 0.35f + 0.9f * Mathf.Clamp01((Fbm(x * 0.0075f - 51f, z * 0.0075f + 17f, 4) - 0.42f) * 2.5f);
                // Tepelerde iri toprak lekeleri (aşınmış yamaçlar): uzaktan tek renk kum tepesi gibi görünmesin
                if (w.Length > 6) w[6] = Mathf.Clamp01((Fbm(x * 0.006f - 33f, z * 0.006f + 21f, 4) - 0.52f) * 3f) * 0.9f;

                // Ova: tarla parselleri (ova kenarına doğru bozkıra karışır)
                float plain = (1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(650f, 980f, r))) * (1f - VillageMask(x, z));
                if (plain > 0f && slope < 8f)
                {
                    int type = FieldType(x, z, out float edge);
                    Array.Clear(fw, 0, fw.Length);
                    fw[type] = 1f;
                    float border = Mathf.Clamp01(1f - edge / 2.2f);          // parsel sınırında ot şeridi
                    for (int k = 0; k < w.Length; k++)
                        w[k] = Mathf.Lerp(w[k], Mathf.Lerp(fw[k], k == 1 ? 1f : 0f, border), plain);
                }
                // Kaya: dik yamaç ve sırtlar
                float rock = Mathf.Clamp01((slope - 27f) / 12f) * (0.55f + 0.45f * moist) + Mathf.Clamp01((h - 175f) / 40f) * 0.6f;
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - Mathf.Clamp01(rock);
                w[4] += Mathf.Clamp01(rock);
                // Çakıl yollar ve tesis alanları
                float rd = RoadDistance(roads, new Vector2(x, z));
                float road = Mathf.Clamp01(1f - (rd - 2.8f) / 1.8f);
                float pad = Mathf.Clamp01(1f - ((new Vector2(x, z) - new Vector2(-30f, -4f)).magnitude - 16f) / 4f)
                          + Mathf.Clamp01(1f - ((new Vector2(x, z) - JammerXZ).magnitude - 12f) / 4f);
                float g = Mathf.Clamp01(road + pad);
                for (int k = 0; k < w.Length; k++) w[k] *= 1f - g;
                w[5] += g;
                float sum = 0f;
                foreach (var a in w) sum += a;
                for (int k = 0; k < w.Length; k++) am[j, i, k] = w[k] / Mathf.Max(sum, 1e-4f);
            }
            td.SetAlphamaps(0, 0, am);

            // Ağaçlar, çalılar ve kayalar
            var protos = new List<TreePrototype>();
            foreach (var g in prefabs.pines.Concat(prefabs.oaks).Concat(prefabs.shrubs).Concat(prefabs.rocks))
                protos.Add(new TreePrototype { prefab = g, bendFactor = 0f });
            td.treePrototypes = protos.ToArray();
            td.SetTreeInstances(Scatter(td, prefabs, roads), true);
            PaintGrass(td, prefabs, am, amRes);

            EditorUtility.SetDirty(td);
            AssetDatabase.SaveAssets();

            var go = Terrain.CreateTerrainGameObject(td);
            go.name = "Arazi";
            go.transform.position = new Vector3(-TerrainSize / 2, -BaseHeight, -TerrainSize / 2);
            var t = go.GetComponent<Terrain>();
            t.treeDistance = 2500f;
            t.treeBillboardDistance = 2500f;
            t.heightmapPixelError = 1.5f;     // tepe siluetleri keskin
            t.basemapDistance = 20000f;   // basemap (uzak, önceden pişmiş doku) HDRP'de siyah çıkıyor; hep tam doku
            t.drawInstanced = true;
            t.detailObjectDistance = 220f;
            t.detailObjectDensity = 1f;
            GameObjectUtility.SetStaticEditorFlags(go, StaticEditorFlags.BatchingStatic | StaticEditorFlags.ContributeGI);
            EditorUtility.DisplayProgressBar("SürüİHA", "Uzak dağlar", 0.8f);
            BuildFarTiles(t, layers, prefabs);
            return t;
        }

        // Ot öbekleri: çimen ve bozkır alanlarında, lekeler halinde; tarla, kaya ve yolda yok
        static void PaintGrass(TerrainData td, Prefabs prefabs, float[,,] am, int amRes)
        {
            if (prefabs.grass.Count == 0) return;
            const int dr = 2048;                 // ~1.2 m hücre: öbekler sıra sıra değil, dağınık görünsün
            var rng = new System.Random(77);
            int Stochastic(float x) => (int)x + (rng.NextDouble() < x - (int)x ? 1 : 0);
            td.SetDetailResolution(dr, 32);
            // Değerler hücre başına öbek ADEDİ olsun (yeni arazilerde varsayılan "kapsama" modudur)
            td.SetDetailScatterMode(DetailScatterMode.InstanceCountMode);
            td.detailPrototypes = prefabs.grass.Select(g => new DetailPrototype
            {
                prototype = g, usePrototypeMesh = true, useInstancing = true, renderMode = DetailRenderMode.VertexLit,
                minWidth = 0.6f, maxWidth = 1.6f, minHeight = 0.5f, maxHeight = 1.5f, noiseSpread = 0.8f,
                healthyColor = Color.white, dryColor = Color.white,
            }).ToArray();
            var green = new int[dr, dr];
            var dry = new int[dr, dr];
            for (int j = 0; j < dr; j++)
            for (int i = 0; i < dr; i++)
            {
                int aj = j * amRes / dr, ai = i * amRes / dr;
                float x = (i / (float)(dr - 1) - 0.5f) * TerrainSize, z = (j / (float)(dr - 1) - 0.5f) * TerrainSize;
                float patch = Mathf.Clamp01((Fbm(x * 0.03f + 5f, z * 0.03f - 9f, 3) - 0.3f) * 2.2f);
                green[j, i] = Stochastic((am[aj, ai, 0] * 6f * patch + am[aj, ai, 3] * 0.6f) * 0.26f);
                dry[j, i] = Stochastic(am[aj, ai, 1] * 5f * patch * 0.26f);
            }
            td.SetDetailLayer(0, 0, 0, green);
            if (prefabs.grass.Count > 1) td.SetDetailLayer(0, 0, 1, dry);
        }

        // Ana arazinin çevresine 8 parça: ufka uzanan, kenarları kesintisiz birleşen dağlar
        static void BuildFarTiles(Terrain center, TerrainLayer[] layers, Prefabs prefabs)
        {
            const int res = 257;
            const float H = 900f;
            var parent = new GameObject("UzakArazi").transform;
            var grid = new Terrain[3, 3];
            grid[1, 1] = center;
            var rng = new System.Random(7);
            for (int dz = -1; dz <= 1; dz++)
            for (int dx = -1; dx <= 1; dx++)
            {
                if (dx == 0 && dz == 0) continue;
                var td = new TerrainData { heightmapResolution = res };
                td.size = new Vector3(TerrainSize, H, TerrainSize);
                string path = $"{Root}/Terrain/Uzak_{dx + 1}{dz + 1}.asset";
                AssetDatabase.DeleteAsset(path);
                AssetDatabase.CreateAsset(td, path);
                float ox = dx * TerrainSize - TerrainSize / 2, oz = dz * TerrainSize - TerrainSize / 2;
                var hm = new float[res, res];
                for (int j = 0; j < res; j++)
                for (int i = 0; i < res; i++)
                    hm[j, i] = Mathf.Clamp01(FarHeightAt(ox + i / (float)(res - 1) * TerrainSize, oz + j / (float)(res - 1) * TerrainSize) / H);
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
                    float moist = Fbm(x * 0.003f + 11f, z * 0.003f - 7f, 4);
                    float g = Mathf.Clamp01((moist - 0.36f) * 2.2f);       // uzak tepeler de yeşil-haki karışık
                    float r = Mathf.Clamp01((slope - 30f) / 12f);
                    am[j, i, 0] = g * (1 - r);
                    am[j, i, 1] = (1 - g) * (1 - r);
                    am[j, i, 4] = r;
                }
                td.SetAlphamaps(0, 0, am);
                var protos = new List<TreePrototype>();
                foreach (var g in prefabs.pines.Concat(prefabs.oaks).Concat(prefabs.shrubs).Concat(prefabs.rocks))
                    protos.Add(new TreePrototype { prefab = g, bendFactor = 0f });
                td.treePrototypes = protos.ToArray();
                var trees = new List<TreeInstance>();
                int nPine = prefabs.pines.Count, nOak = prefabs.oaks.Count;
                for (int k = 0; k < 30000 && trees.Count < 1400 && nPine > 0; k++)
                {
                    float u = (float)rng.NextDouble(), v = (float)rng.NextDouble();
                    float x = ox + u * TerrainSize, z = oz + v * TerrainSize;
                    float forest = Fbm(x * 0.0035f + 100f, z * 0.0035f - 50f, 4);
                    if (forest < 0.52f || rng.NextDouble() > (forest - 0.45f) * 2f) continue;
                    if (td.GetSteepness(u, v) > 32f) continue;
                    float s = 0.8f + (float)rng.NextDouble() * 0.6f;
                    int proto = rng.NextDouble() < 0.85 || nOak == 0 ? rng.Next(nPine) : nPine + rng.Next(nOak);
                    trees.Add(new TreeInstance { prototypeIndex = proto, position = new Vector3(u, 0, v), widthScale = s, heightScale = s,
                                                 rotation = (float)rng.NextDouble() * 6.28f, color = Color.white, lightmapColor = Color.white });
                }
                td.SetTreeInstances(trees.ToArray(), true);
                EditorUtility.SetDirty(td);
                var go = Terrain.CreateTerrainGameObject(td);
                go.name = $"Uzak_{dx}_{dz}";
                go.transform.SetParent(parent, false);
                go.transform.position = new Vector3(ox, -BaseHeight, oz);
                var t = go.GetComponent<Terrain>();
                t.heightmapPixelError = 8f;
                t.basemapDistance = 20000f;   // basemap (uzak, önceden pişmiş doku) HDRP'de siyah çıkıyor; hep tam doku
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

        // Ana arazinin yükseklik fonksiyonu + uzaklaştıkça yükselen dağ silsilesi (kenarda süreklidir)
        static float FarHeightAt(float x, float z)
        {
            float m = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z));
            float ridge = 1f - Mathf.Abs(Fbm(x * 0.0009f + 33f, z * 0.0009f - 21f, 5) * 2f - 1f);
            return HeightAt(x, z) + Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(1200f, 2800f, m)) * (160f + 320f * ridge);
        }

        // Ortada düz bir operasyon ovası, dışarıda tepeler, kuzeyde dağ silsilesi
        public static float HeightAt(float x, float z)
        {
            float r = new Vector2(x, z).magnitude;
            float plain = BaseHeight + 2.2f * (Fbm(x * 0.006f, z * 0.006f, 3) - 0.5f) * 2f;
            float w = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(480f, 950f, r));
            float hills = 95f * Mathf.Pow(Fbm(x * 0.0018f + 40f, z * 0.0018f + 17f, 5), 1.7f) * 2.2f;
            float ridge = 1f - Mathf.Abs(Fbm(x * 0.0012f - 9f, z * 0.0012f + 3f, 4) * 2f - 1f);
            float north = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(500f, 1150f, z)) * 120f * ridge;
            float edge = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(900f, 1200f, Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)))) * 40f;
            return plain + w * (hills + north + edge);
        }

        static float Fbm(float x, float y, int oct)
        {
            float a = 0.5f, s = 0f, n = 0f;
            for (int o = 0; o < oct; o++)
            {
                s += a * Mathf.PerlinNoise(x, y);
                n += a;
                x = x * 2.03f + 17.1f;
                y = y * 2.03f - 9.3f;
                a *= 0.5f;
            }
            return s / n;
        }

        // Toprak yollar: istasyondan doğuya karıştırıcıya, bir de ovayı kuzey-güney kesen yol
        static List<Vector2[]> Roads()
        {
            var a = new List<Vector2>();
            for (int k = 0; k <= 40; k++)
            {
                float t = k / 40f;
                var p = Vector2.Lerp(new Vector2(-60f, -20f), JammerXZ + new Vector2(-12f, -8f), t);
                p += new Vector2(0, Mathf.Sin(t * 5f) * 30f * (1 - t) * t * 4f);
                a.Add(p);
            }
            var b = new List<Vector2>();
            for (int k = 0; k <= 60; k++)
            {
                float t = k / 60f;
                float z = Mathf.Lerp(-1200f, 1200f, t);
                b.Add(new Vector2(RoadBX(z), z));
            }
            var c = new List<Vector2>();
            for (int k = 0; k <= 20; k++)
            {
                float t = k / 20f;
                c.Add(Vector2.Lerp(new Vector2(-60f, -20f), new Vector2(-150f + Mathf.Sin(-20f * 0.004f) * 80f, -40f), t));
            }
            // Köy: iki ana sokak + ana yola bağlantı
            Vector2 R(float u, float w) => VillageXZ + VillageU * u + VillageV * w;
            var s1 = new[] { R(-90, 0), R(90, 0) };
            var s2 = new[] { R(0, -70), R(0, 70) };
            var conn = new List<Vector2>();
            for (int k = 0; k <= 12; k++)
            {
                float t = k / 12f;
                conn.Add(Vector2.Lerp(R(90, 0), new Vector2(RoadBX(-560f + 160f), -560f + 160f), t) + new Vector2(0, Mathf.Sin(t * 3f) * 10f));
            }
            return new List<Vector2[]> { a.ToArray(), b.ToArray(), c.ToArray(), s1, s2, conn.ToArray() };
        }

        static float RoadBX(float z) => -150f + Mathf.Sin(z * 0.004f) * 80f + Mathf.Sin(z * 0.011f) * 20f;

        // Köy merkezi ve sokak eksenleri (tarlalarla aynı 14° yönelim)
        static readonly Vector2 VillageXZ = new Vector2(-380f, -560f);
        static readonly Vector2 VillageU = new Vector2(Mathf.Cos(14f * Mathf.Deg2Rad), -Mathf.Sin(14f * Mathf.Deg2Rad));
        static readonly Vector2 VillageV = new Vector2(Mathf.Sin(14f * Mathf.Deg2Rad), Mathf.Cos(14f * Mathf.Deg2Rad));
        static float VillageMask(float x, float z) => Mathf.Clamp01(1f - ((new Vector2(x, z) - VillageXZ).magnitude - 115f) / 35f);

        static float RoadDistance(List<Vector2[]> roads, Vector2 p)
        {
            float best = float.MaxValue;
            foreach (var r in roads)
                for (int k = 0; k + 1 < r.Length; k++)
                {
                    Vector2 a = r[k], b = r[k + 1], ab = b - a;
                    // Hızlı eleme: bu parçaya çok uzaksa hesaplama
                    if (Mathf.Abs(p.x - a.x) > ab.magnitude + best || Mathf.Abs(p.y - a.y) > ab.magnitude + best) continue;
                    float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / ab.sqrMagnitude);
                    best = Mathf.Min(best, (a + ab * t - p).magnitude);
                }
            return best;
        }

        static float Hash(int a, int b)
        {
            unchecked
            {
                uint h = (uint)(a * 73856093) ^ (uint)(b * 19349663);
                h ^= h >> 13;
                h *= 0x5bd1e995;
                h ^= h >> 15;
                return (h & 0xFFFFFF) / 16777215f;
            }
        }

        // Ova tarlaları: hafif döndürülmüş, şerit şerit farklı genişlikte parseller.
        // Dönüş: katman (3 anız, 2 sürülmüş, 0 yeşil ekin, 1 nadas/bozkır), edge = sınıra uzaklık (m)
        static int FieldType(float x, float z, out float edge)
        {
            float a = 14f * Mathf.Deg2Rad;
            float px = x * Mathf.Cos(a) - z * Mathf.Sin(a);
            float pz = x * Mathf.Sin(a) + z * Mathf.Cos(a);
            const float ch = 72f;
            int row = Mathf.FloorToInt(pz / ch);
            float wRow = 80f + 90f * Hash(row, 3);
            float cx = px + Hash(row, 7) * wRow;
            int col = Mathf.FloorToInt(cx / wRow);
            float fx = cx / wRow - col, fz = pz / ch - row;
            edge = Mathf.Min(Mathf.Min(fx, 1 - fx) * wRow, Mathf.Min(fz, 1 - fz) * ch);
            float t = Hash(row * 31 + 5, col);
            return t < 0.38f ? 3 : t < 0.62f ? 2 : t < 0.8f ? 0 : 1;
        }

        static TreeInstance[] Scatter(TerrainData td, Prefabs p, List<Vector2[]> roads)
        {
            var rng = new System.Random(42);
            var list = new List<TreeInstance>();
            int nPine = p.pines.Count, nOak = p.oaks.Count, nShrub = p.shrubs.Count, nRock = p.rocks.Count;
            int oak0 = nPine, shrub0 = nPine + nOak, rock0 = nPine + nOak + nShrub;
            float R() => (float)rng.NextDouble();

            void Add(int proto, float x, float z, float s)
            {
                list.Add(new TreeInstance
                {
                    prototypeIndex = proto,
                    position = new Vector3(x / TerrainSize + 0.5f, 0f, z / TerrainSize + 0.5f),
                    widthScale = s, heightScale = s * (0.9f + 0.2f * R()),
                    rotation = R() * Mathf.PI * 2f,
                    color = Color.white,
                    lightmapColor = Color.white,
                });
            }

            bool Blocked(float x, float z, float margin = 7f)
            {
                var v = new Vector2(x, z);
                if ((v - new Vector2(-30f, -4f)).magnitude < 40f) return true;      // yer istasyonu
                if ((v - JammerXZ).magnitude < 30f) return true;                    // karıştırıcı
                if (v.magnitude < 35f) return true;                                 // kalkış alanı
                if ((v - VillageXZ).magnitude < 120f) return true;                  // köy
                return RoadDistance(roads, v) < margin;
            }

            bool InFields(float x, float z, out float edge)
            {
                edge = 99f;
                float r = new Vector2(x, z).magnitude;
                if (r > 900f) return false;
                if (td.GetSteepness(x / TerrainSize + 0.5f, z / TerrainSize + 0.5f) > 8f) return false;
                FieldType(x, z, out edge);
                return r < 650f || R() < Mathf.InverseLerp(900f, 650f, r);
            }

            float Rand(float lim) => (R() - 0.5f) * lim;

            // Ekili tarlanın içi mi? (splat haritasıyla aynı kural, rastgelelik yok)
            bool FieldInterior(float x, float z)
            {
                if (new Vector2(x, z).magnitude > 815f || VillageMask(x, z) > 0f) return false;
                if (td.GetSteepness(x / TerrainSize + 0.5f, z / TerrainSize + 0.5f) > 8f) return false;
                FieldType(x, z, out float e);
                return e > 3f;
            }

            // 1) Tepelerde karaçam ormanları (yer yer meşe)
            for (int k = 0; k < 90000 && list.Count < 5200; k++)
            {
                float x = Rand(TerrainSize - 40f), z = Rand(TerrainSize - 40f);
                if (Blocked(x, z)) continue;
                float r = new Vector2(x, z).magnitude;
                if (r < 620f) continue;
                float forest = Fbm(x * 0.0035f + 100f, z * 0.0035f - 50f, 4);
                float h = HeightAt(x, z);
                if (h > 185f || forest < 0.5f || R() > (forest - 0.45f) * 2.6f) continue;
                if (FieldInterior(x, z)) continue;
                if (R() < 0.85f) Add(rng.Next(nPine), x, z, 0.75f + R() * 0.6f);
                else if (nOak > 0) Add(oak0 + rng.Next(nOak), x, z, 0.8f + R() * 0.5f);
            }
            // 2) Tarla sınırlarında meşe sıraları (tipik Anadolu tarlası)
            int oaks = 0;
            for (int k = 0; k < 120000 && oaks < 650 && nOak > 0; k++)
            {
                float x = Rand(1800f), z = Rand(1800f);
                if (Blocked(x, z) || !InFields(x, z, out float edge)) continue;
                if (edge > 2.0f || R() > 0.35f) continue;
                Add(oak0 + rng.Next(nOak), x, z, 0.7f + R() * 0.6f);
                oaks++;
            }
            // 3) Bozkır ve yamaçlarda çalılar
            int shrubs = 0;
            for (int k = 0; k < 160000 && shrubs < 4200 && nShrub > 0; k++)
            {
                float x = Rand(TerrainSize - 40f), z = Rand(TerrainSize - 40f);
                if (Blocked(x, z, 4f)) continue;
                if (FieldInterior(x, z)) continue;                    // ekili tarlanın içinde çalı olmaz
                float n = Fbm(x * 0.008f - 30f, z * 0.008f + 12f, 3);
                if (R() > (n - 0.35f) * 1.3f) continue;
                Add(shrub0 + rng.Next(nShrub), x, z, 0.7f + R() * 0.9f);
                shrubs++;
            }
            // 4) Kayalar: yamaçlarda kümeler halinde
            for (int k = 0; k < 12000 && nRock > 0; k++)
            {
                float x = Rand(TerrainSize - 40f), z = Rand(TerrainSize - 40f);
                if (Blocked(x, z)) continue;
                float slope = td.GetSteepness(x / TerrainSize + 0.5f, z / TerrainSize + 0.5f);
                float n = Fbm(x * 0.01f + 7f, z * 0.01f + 3f, 3);
                if (slope < 12f && n < 0.64f) continue;
                if (InFields(x, z, out _)) continue;
                if (R() > 0.14f) continue;
                Add(rock0 + rng.Next(nRock), x, z, 0.5f + R() * 1.6f);
            }
            Debug.Log($"[SuruIHA] Arazi süsü: {list.Count} (meşe sırası {oaks}, çalı {shrubs})");
            return list.ToArray();
        }

        // ------------------------------------------------------------------ dokular
        // Python'un ürettiği dokular (tools/gen_textures.py) varsa onları kullanır, yoksa kendisi üretir.
        // tint: fotoğraf dokusunun renk çarpanı (aynı doku farklı katmanlarda farklı görünebilsin)
        // floor: dokunun en koyu tonunun yükseltildiği oran (0: değişmez; karda koyu izler tekrar deseni yapmasın)
        static TerrainLayer Layer(string name, string gen, Color a, Color b, float tile, float smooth, int seed,
                                  string photo = null, float photoTile = 0f, Color? tint = null, float floor = 0f)
        {
            var (pa, pn, pm) = Photo(photo);
            if (pa != null)
            {
                string pp = $"{Root}/Terrain/{name}.terrainlayer";
                var pl = AssetDatabase.LoadAssetAtPath<TerrainLayer>(pp);
                if (pl == null)
                {
                    pl = new TerrainLayer();
                    AssetDatabase.CreateAsset(pl, pp);
                }
                pl.diffuseTexture = pa;
                pl.normalMapTexture = pn;
                pl.maskMapTexture = pm;
                pl.normalScale = 1f;
                pl.tileSize = new Vector2(photoTile, photoTile);
                pl.diffuseRemapMin = new Vector4((tint ?? Color.white).r * floor, (tint ?? Color.white).g * floor, (tint ?? Color.white).b * floor, 0f);
                var tc = tint ?? Color.white;
                pl.diffuseRemapMax = new Vector4(tc.r, tc.g, tc.b, 1f);
                pl.smoothness = smooth;
                pl.metallic = 0f;
                EditorUtility.SetDirty(pl);
                return pl;
            }
            string albedo = $"{GenTex}/{gen}_Renk.png", normal = $"{GenTex}/{gen}_Normal.png";
            if (AssetDatabase.LoadAssetAtPath<Texture2D>(albedo) == null)
            {
                albedo = $"{Root}/Textures/{name}_Renk.png";
                normal = $"{Root}/Textures/{name}_Normal.png";
                MakeFallbackTextures(albedo, normal, a, b, seed);
            }
            LoadTex(Path.GetFileNameWithoutExtension(normal), true, false);   // normal map olarak işaretle (Gen klasöründeyse)
            var nti = AssetImporter.GetAtPath(normal) as TextureImporter;
            if (nti != null && nti.textureType != TextureImporterType.NormalMap)
            {
                nti.textureType = TextureImporterType.NormalMap;
                nti.SaveAndReimport();
            }
            var ati = AssetImporter.GetAtPath(albedo) as TextureImporter;
            if (ati != null && ati.anisoLevel != 8) { ati.anisoLevel = 8; ati.SaveAndReimport(); }

            string lp = $"{Root}/Terrain/{name}.terrainlayer";
            var layer = AssetDatabase.LoadAssetAtPath<TerrainLayer>(lp);
            if (layer == null)
            {
                layer = new TerrainLayer();
                AssetDatabase.CreateAsset(layer, lp);
            }
            layer.diffuseTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(albedo);
            layer.normalMapTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(normal);
            layer.normalScale = 1f;
            layer.tileSize = new Vector2(tile, tile);
            layer.smoothness = smooth;
            layer.metallic = 0f;
            EditorUtility.SetDirty(layer);
            return layer;
        }

        static void MakeFallbackTextures(string albedo, string normal, Color a, Color b, int seed)
        {
            int N = 1024;
            var h = new float[N, N];
            var col = new Color[N * N];
            for (int y = 0; y < N; y++)
            for (int x = 0; x < N; x++)
            {
                float u = x / (float)N, v = y / (float)N;
                float n = TileFbm(u, v, 8, 6, seed);
                float fine = TileFbm(u, v, 64, 3, seed + 50);
                h[y, x] = n * 0.6f + fine * 0.4f;
                var c = Color.Lerp(b, a, Mathf.Clamp01(n * 1.2f - 0.1f)) * (0.82f + 0.36f * fine);
                c.a = 1f;
                col[y * N + x] = c;
            }
            WritePng(albedo, col, N);
            var nm = new Color[N * N];
            for (int y = 0; y < N; y++)
            for (int x = 0; x < N; x++)
            {
                float dx = h[y, (x + 1) % N] - h[y, (x - 1 + N) % N];
                float dy = h[(y + 1) % N, x] - h[(y - 1 + N) % N, x];
                var n = new Vector3(-dx * 6f, -dy * 6f, 1f).normalized;
                nm[y * N + x] = new Color(n.x * 0.5f + 0.5f, n.y * 0.5f + 0.5f, n.z * 0.5f + 0.5f, 1f);
            }
            WritePng(normal, nm, N);
            AssetDatabase.ImportAsset(albedo);
            AssetDatabase.ImportAsset(normal);
        }

        static void WritePng(string assetPath, Color[] px, int n)
        {
            var tex = new Texture2D(n, n, TextureFormat.RGBA32, false, false);
            tex.SetPixels(px);
            tex.Apply();
            File.WriteAllBytes(assetPath, tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
        }

        // Kenarları birleşen (dikişsiz) değer gürültüsü
        static float TileFbm(float u, float v, int period, int oct, int seed)
        {
            float s = 0, a = 0.5f, n = 0;
            for (int o = 0; o < oct; o++)
            {
                s += a * TileNoise(u * period, v * period, period, seed + o * 31);
                n += a;
                period *= 2;
                a *= 0.5f;
            }
            return s / n;
        }

        static float TileNoise(float x, float y, int period, int seed)
        {
            int x0 = Mathf.FloorToInt(x), y0 = Mathf.FloorToInt(y);
            float fx = x - x0, fy = y - y0;
            fx = fx * fx * (3 - 2 * fx);
            fy = fy * fy * (3 - 2 * fy);
            float H(int i, int j)
            {
                i = ((i % period) + period) % period;
                j = ((j % period) + period) % period;
                uint h = (uint)(i * 374761393 + j * 668265263 + seed * 2147483647);
                h = (h ^ (h >> 13)) * 1274126177u;
                return ((h ^ (h >> 16)) & 0xFFFF) / 65535f;
            }
            float a = Mathf.Lerp(H(x0, y0), H(x0 + 1, y0), fx);
            float b = Mathf.Lerp(H(x0, y0 + 1), H(x0 + 1, y0 + 1), fx);
            return Mathf.Lerp(a, b, fy);
        }
    }
}
