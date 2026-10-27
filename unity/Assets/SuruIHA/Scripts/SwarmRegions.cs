using UnityEngine;

namespace SuruIHA
{
    // Bölgeler (haritalar): her bölge sahnede ayrı bir arazidir. Seçilen bölgeye simülasyon kökü (SuruSistemi),
    // kamera ve İHA'lar birlikte kaydırılır; Python da o bölgenin yükseklik haritasıyla uçar (--region).
    // Karlı bölgede güneş alçalır ve kar yağar; sis ve renkler bölgenin yerel hacim ayarından (Volume) gelir.
    public static class SwarmRegions
    {
        public static readonly string[] Ids = { "ova", "kar", "nehir" };
        public static readonly string[] Titles = { "Orta Anadolu ovası", "Karlı dağlar", "Kızılırmak (Sivas)" };
        public static readonly Vector3 SnowOffset = new Vector3(12000f, 0f, 0f);    // ana araziden 12 km doğu
        public static readonly Vector3 RiverOffset = new Vector3(-12000f, 0f, 0f);  // ana araziden 12 km batı

        public static string Current { get; private set; } = "ova";

        public static int Index(string id)
        {
            int i = System.Array.IndexOf(Ids, id);
            return i < 0 ? 0 : i;
        }

        public static string Title(string id) => Titles[Index(id)];
        public static Vector3 Offset(string id) => id == "kar" ? SnowOffset : id == "nehir" ? RiverOffset : Vector3.zero;

        static Light sun;
        static Quaternion sunRot;
        static float sunTemp, sunIntensity;
        static ParticleSystem snow;

        public static void Apply(string id)
        {
            id = Ids[Index(id)];
            var vis = SwarmVisualizer.Main;
            if (vis == null) return;
            Current = id;
            Vector3 target = Offset(id), now = vis.transform.position;
            var delta = new Vector3(target.x - now.x, 0f, target.z - now.z);
            if (delta.sqrMagnitude > 1f)
            {
                vis.transform.position += delta;
                foreach (var d in vis.Drones) d.Snap();
                var cmp = SwarmCompare.Instance;          // ikinci sürü ana sürünün yerini izler
                if (cmp != null && cmp.B != null)
                {
                    cmp.B.transform.position += delta;
                    foreach (var d in cmp.B.Drones) d.Snap();
                    if (cmp.CamB != null) cmp.CamB.transform.position += delta;
                }
                var cam = Object.FindAnyObjectByType<SwarmCamera>();
                if (cam != null) cam.Shift(delta);
            }
            ApplySun(id);
            if (id == "kar")
            {
                if (snow == null) snow = MakeSnow(vis.Mats.Snow);
                if (!snow.isPlaying) snow.Play();
            }
            else if (snow != null) snow.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        }

        // Kış güneşi: daha alçak, daha soğuk renkli ve biraz zayıf
        static void ApplySun(string id)
        {
            if (sun == null)
            {
                var go = GameObject.Find("Sun");
                if (go == null || !go.TryGetComponent(out sun)) return;
                sunRot = sun.transform.rotation;
                sunTemp = sun.colorTemperature;
                sunIntensity = sun.intensity;
            }
            bool kar = id == "kar";
            sun.transform.rotation = kar ? Quaternion.Euler(22f, -58f, 0f) : sunRot;
            sun.colorTemperature = kar ? 6600f : sunTemp;
            sun.intensity = kar ? sunIntensity * 0.8f : sunIntensity;
        }

        // Kamerayı izleyen kar yağışı: kameranın çevresinde 160 m'lik kutudan yavaşça düşen, rüzgârla kayan taneler
        static ParticleSystem MakeSnow(Material baseMat)
        {
            var go = new GameObject("KarYagisi");
            go.AddComponent<SnowFollow>();
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true;
            main.playOnAwake = false;
            main.startLifetime = 14f;
            main.startSpeed = 0f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.12f, 0.28f);
            main.maxParticles = 5000;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var em = ps.emission;
            em.rateOverTime = 350f;
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Box;
            sh.scale = new Vector3(110f, 1f, 110f);     // kameranın yakınında (uzaktakiler zaten seçilmez)
            var vel = ps.velocityOverLifetime;
            vel.enabled = true;
            vel.space = ParticleSystemSimulationSpace.World;
            vel.x = new ParticleSystem.MinMaxCurve(0.4f, 1.2f);      // hafif rüzgâr
            vel.y = new ParticleSystem.MinMaxCurve(-1.4f, -2.2f);
            vel.z = new ParticleSystem.MinMaxCurve(-0.3f, 0.3f);
            var noise = ps.noise;
            noise.enabled = true;
            noise.strength = 0.5f;
            noise.frequency = 0.25f;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            var mat = new Material(baseMat) { name = "KarTanesi" };
            mat.SetTexture("_BaseColorMap", FlakeTexture());           // yuvarlak, kenarı yumuşak tane
            mat.SetTexture("_MainTex", FlakeTexture());
            r.sharedMaterial = mat;
            return ps;
        }

        static Texture2D flake;

        static Texture2D FlakeTexture()
        {
            if (flake != null) return flake;
            const int n = 32;
            flake = new Texture2D(n, n, TextureFormat.RGBA32, false) { name = "KarTanesi", wrapMode = TextureWrapMode.Clamp };
            var px = new Color32[n * n];
            for (int j = 0; j < n; j++)
            for (int i = 0; i < n; i++)
            {
                float d = new Vector2(i + 0.5f - n / 2f, j + 0.5f - n / 2f).magnitude / (n / 2f);
                byte a = (byte)(255f * Mathf.Clamp01(1f - d * d) * Mathf.Clamp01(1f - d));
                px[j * n + i] = new Color32(255, 255, 255, a);
            }
            flake.SetPixels32(px);
            flake.Apply();
            return flake;
        }

        class SnowFollow : MonoBehaviour
        {
            void LateUpdate()
            {
                var c = Camera.main;
                if (c != null) transform.position = c.transform.position + Vector3.up * 22f;
            }
        }
    }
}
