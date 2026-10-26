using System;
using System.Reflection;
using UnityEngine;
using UnityEngine.Rendering;

namespace SuruIHA
{
    // Malzemeleri kodla üretir. HDRP, URP ve Built-in boru hatlarının üçünde de çalışır,
    // böylece projede elle malzeme oluşturmak zorunda kalmazsın.
    public static class SwarmMaterials
    {
        static string PipelineName =>
            GraphicsSettings.currentRenderPipeline == null ? "" : GraphicsSettings.currentRenderPipeline.GetType().Name;

        public static bool IsHdrp => PipelineName.Contains("HDRenderPipeline");
        public static bool IsUrp => PipelineName.Contains("Universal");

        static Shader LitShader()
        {
            string name = IsHdrp ? "HDRP/Lit" : IsUrp ? "Universal Render Pipeline/Lit" : "Standard";
            return Shader.Find(name) ?? Shader.Find("Standard");
        }

        public static Material Lit(Color color, float metallic = 0.2f, float smoothness = 0.5f)
        {
            var m = new Material(LitShader());
            SetColor(m, color);
            if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", metallic);
            if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", smoothness);
            if (m.HasProperty("_Glossiness")) m.SetFloat("_Glossiness", smoothness);
            Validate(m);
            return m;
        }

        // Kendi ışığını yayan (parlayan) malzeme: LED, bağlantı çizgileri, işaretler
        public static Material Glow(Color color, float intensity)
        {
            var m = Lit(color * 0.25f, 0f, 0.3f);
            SetEmission(m, color, intensity);
            Validate(m);
            return m;
        }

        // Yarı saydam malzeme: karıştırma kubbesi, pervane bulanıklığı, hayalet konum
        public static Material Transparent(Color color, float emission = 0f)
        {
            var m = Lit(color, 0f, 0.25f);
            if (IsHdrp)
            {
                m.SetFloat("_SurfaceType", 1f);
                m.SetFloat("_BlendMode", 0f);
                m.SetFloat("_DoubleSidedEnable", 1f);
                m.SetFloat("_ZWrite", 0f);
                m.SetFloat("_TransparentZWrite", 0f);
            }
            else if (IsUrp)
            {
                m.SetFloat("_Surface", 1f);
                m.SetFloat("_Blend", 0f);
                m.SetFloat("_Cull", 0f);
                m.SetOverrideTag("RenderType", "Transparent");
                m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
                m.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
                m.SetFloat("_ZWrite", 0f);
                m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                m.renderQueue = (int)RenderQueue.Transparent;
            }
            else
            {
                m.SetFloat("_Mode", 3f);
                m.SetOverrideTag("RenderType", "Transparent");
                m.SetInt("_SrcBlend", (int)BlendMode.One);
                m.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
                m.SetInt("_ZWrite", 0);
                m.EnableKeyword("_ALPHAPREMULTIPLY_ON");
                m.renderQueue = (int)RenderQueue.Transparent;
            }
            if (emission > 0f) SetEmission(m, color, emission);
            Validate(m);
            return m;
        }

        // Dokulu yarı saydam örtü (karıştırma ısı haritası): renk ve saydamlık dokudan gelir, doku hafifçe
        // parlar (gölgede de okunsun). Doku çalışma anında değişir; buradaki beyaz doku yer tutucudur ve
        // HDRP'nin dokulu varyantı seçmesini sağlar (Sahneyi Kur malzemeyle birlikte kaydeder).
        public static Material Overlay(float emission)
        {
            var m = Transparent(Color.white);
            var tex = new Texture2D(4, 4, TextureFormat.RGBA32, false) { name = "YerTutucu" };
            var px = new Color32[16];
            for (int i = 0; i < px.Length; i++) px[i] = new Color32(255, 255, 255, 255);
            tex.SetPixels32(px);
            tex.Apply();
            SetOverlayTexture(m, tex);
            SetEmission(m, Color.white, emission);
            Validate(m);
            return m;
        }

        // Renk + saydamlık dokusu ve parlama dokusu (parlama verilmezse renk dokusu kullanılır)
        public static void SetOverlayTexture(Material m, Texture tex, Texture emission = null)
        {
            foreach (var p in new[] { "_BaseColorMap", "_MainTex", "_BaseMap" })
                if (m.HasProperty(p)) m.SetTexture(p, tex);
            foreach (var p in new[] { "_EmissiveColorMap", "_EmissionMap" })
                if (m.HasProperty(p)) m.SetTexture(p, emission != null ? emission : tex);
        }

        public static void SetColor(Material m, Color c)
        {
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            if (m.HasProperty("_Color")) m.SetColor("_Color", c);
        }

        public static void SetEmission(Material m, Color c, float intensity)
        {
            if (IsHdrp)
            {
                m.SetColor("_EmissiveColor", c * intensity);
                // 0 = parlaklık kamera pozlamasından etkilenmez; gündüz sahnesinde de net görünür
                if (m.HasProperty("_EmissiveExposureWeight")) m.SetFloat("_EmissiveExposureWeight", 0f);
            }
            else
            {
                m.EnableKeyword("_EMISSION");
                m.SetColor("_EmissionColor", c * intensity);
            }
        }

        // Çalışma anında renk değiştirmek için (malzemeyi kopyalamadan)
        public static void SetBlock(MaterialPropertyBlock b, Color baseColor, Color emission)
        {
            b.SetColor("_BaseColor", baseColor);
            b.SetColor("_Color", baseColor);
            b.SetColor("_EmissiveColor", emission);
            b.SetColor("_EmissionColor", emission);
        }

        // HDRP, kodla değiştirilen malzemenin anahtar kelimelerini yeniden hesaplamalı.
        // HDRP paketine doğrudan bağımlı olmamak için yansıma (reflection) ile çağırıyoruz.
        static MethodInfo validateMethod;
        static bool searched;

        static void Validate(Material m)
        {
            if (!IsHdrp) return;
            if (!searched)
            {
                searched = true;
                var type = Type.GetType("UnityEngine.Rendering.HighDefinition.HDMaterial, Unity.RenderPipelines.HighDefinition.Runtime");
                validateMethod = type?.GetMethod("ValidateMaterial", BindingFlags.Public | BindingFlags.Static);
            }
            validateMethod?.Invoke(null, new object[] { m });
        }
    }
}
