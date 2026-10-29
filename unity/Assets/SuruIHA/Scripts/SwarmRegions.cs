using UnityEngine;

namespace SuruIHA
{
    // Bölgeler (haritalar): her bölge sahnede ayrı bir arazidir. Seçilen bölgeye simülasyon kökü (SuruSistemi),
    // kamera ve İHA'lar birlikte kaydırılır; Python da o bölgenin yükseklik haritasıyla uçar (--region).
    // Karlı bölgede güneş alçalır ve kar yağar; sis ve renkler bölgenin yerel hacim ayarından (Volume) gelir.
    public static class SwarmRegions
    {
        public static readonly string[] Ids = { "ova", "kar", "nehir", "divrigi", "gokpinar", "deniz" };
        public static readonly string[] Titles =
            { "Orta Anadolu ovası", "Karlı dağlar", "Kızılırmak (Sivas)", "Divriği (Sivas)", "Gökpınar Gölü (Gürün)", "Akdeniz kıyısı" };
        public static readonly string[] ShortTitles = { "Ova", "Karlı dağlar", "Kızılırmak", "Divriği", "Gökpınar", "Akdeniz" };
        public static readonly Vector3 SnowOffset = new Vector3(12000f, 0f, 0f);    // ana araziden 12 km doğu
        public static readonly Vector3 RiverOffset = new Vector3(-12000f, 0f, 0f);  // ana araziden 12 km batı
        public static readonly Vector3 DivrigiOffset = new Vector3(0f, 0f, 12000f);     // 12 km kuzey
        public static readonly Vector3 GokpinarOffset = new Vector3(0f, 0f, -12000f);   // 12 km güney
        public static readonly Vector3 SeaOffset = new Vector3(12000f, 0f, 12000f);     // 12 km kuzeydoğu
        public const float SeaLevel = -18f;            // Akdeniz: deniz yüzeyi, üssün 18 m altında

        public static string Current { get; private set; } = "ova";

        // Kızılırmak'ın orta çizgisi (bölgenin yerel koordinatında): batıdan doğuya akar, görev alanının ortasından
        // menderes çizerek geçer. Sahne kurulumu (yatak, su, köprü) ve ırmak sesi aynı çizgiyi kullanır.
        public const float WaterLevel = -2.4f;          // su yüzeyi: ova tabanının 2,4 m altında
        public const float RiverHalfLength = 3600f;     // su yüzeyi x = -3600 … 3600 m
        // Akdeniz kıyı çizgisi (bölgenin yerel koordinatında): batıda kumlu koy, doğuda fenerli burun; kuzeyi deniz.
        // Sahne kurulumu ve dalga sesi aynı çizgiyi kullanır.
        public static float SeaCoastZ(float x) => 480f + 100f * Mathf.Sin(x * 0.0035f + 0.6f) + 40f * Mathf.Sin(x * 0.011f + 2f)
            - 160f * Mathf.Exp(-Mathf.Pow((x + 120f) / 170f, 2f)) + 150f * Mathf.Exp(-Mathf.Pow((x - 430f) / 90f, 2f));

        public static float RiverZ(float x) =>
            470f + 95f * Mathf.Sin(x * 0.0045f) + 38f * Mathf.Sin(x * 0.011f + 1.3f) + 14f * Mathf.Sin(x * 0.027f + 0.4f);

        public static int Index(string id)
        {
            int i = System.Array.IndexOf(Ids, id);
            return i < 0 ? 0 : i;
        }

        public static string Title(string id) => Titles[Index(id)];
        public static Vector3 Offset(string id) => id switch
        {
            "kar" => SnowOffset, "nehir" => RiverOffset, "divrigi" => DivrigiOffset, "gokpinar" => GokpinarOffset, "deniz" => SeaOffset,
            _ => Vector3.zero,
        };

        // Su yüzeyi zemin sayılır: Akdeniz'de hedef işaretleri ve ısı haritası deniz dibine değil suyun üstüne oturur
        public static float WaterFloor => Current == "deniz" ? SeaOffset.y + SeaLevel : float.NegativeInfinity;

        // Yalnızca kendi bölgesinde açık nesneler (HDRP deniz suyu sonsuza uzanır: başka bölgeyi su basmasın)
        static void ApplyRegionObjects(string id)
        {
            foreach (var o in Object.FindObjectsByType<SwarmRegionObject>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                if (o.gameObject.activeSelf != (o.region == id)) o.gameObject.SetActive(o.region == id);
        }

        static Vector2 wind;

        // Simülasyondaki rüzgâr (doğu, kuzey m/s): kar taneleri ve baca dumanı onunla savrulur
        public static void SetWind(Vector2 w)
        {
            if ((w - wind).sqrMagnitude < 0.04f) return;
            wind = w;
            if (snow != null) WindSnow(snow);
            foreach (var ps in smoke)
            {
                if (ps == null) continue;
                var vel = ps.velocityOverLifetime;
                vel.x = new ParticleSystem.MinMaxCurve(0.5f + 0.6f * w.x, 1.1f + 0.8f * w.x);
                vel.z = new ParticleSystem.MinMaxCurve(0.6f * w.y - 0.2f, 0.8f * w.y + 0.2f);
            }
        }

        static void WindSnow(ParticleSystem ps)
        {
            var vel = ps.velocityOverLifetime;
            vel.x = new ParticleSystem.MinMaxCurve(0.4f + 0.85f * wind.x, 1.2f + 1.05f * wind.x);
            vel.z = new ParticleSystem.MinMaxCurve(-0.3f + 0.85f * wind.y, 0.3f + 1.05f * wind.y);
            var noise = ps.noise;
            noise.strength = 0.5f + 0.12f * wind.magnitude;    // esinti: rüzgâr güçlendikçe taneler daha çok savrulur
        }

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
            ApplyRegionObjects(id);
            if (id == "kar")
            {
                if (snow == null) { snow = MakeSnow(vis.Mats.Snow); WindSnow(snow); }
                if (!snow.isPlaying) snow.Play();
            }
            else if (snow != null) snow.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            ApplySmoke(id == "kar", vis.Mats.Snow);
        }

        static readonly System.Collections.Generic.List<ParticleSystem> smoke = new System.Collections.Generic.List<ParticleSystem>();

        // Karlı dağ köyünde bacalardan tüten ince duman (yalnızca karlı bölgede)
        static void ApplySmoke(bool on, Material baseMat)
        {
            if (on && smoke.Count == 0)
            {
                var village = GameObject.Find("KarKoyu");
                if (village != null)
                    foreach (var t in village.GetComponentsInChildren<Transform>())
                    {
                        if (!t.name.StartsWith("Baca_Kapak")) continue;
                        var r = t.GetComponent<Renderer>();
                        var top = r != null ? r.bounds.center + Vector3.up * (r.bounds.extents.y + 0.2f) : t.position;
                        smoke.Add(MakeSmoke(top, baseMat));
                    }
            }
            foreach (var ps in smoke)
            {
                if (ps == null) continue;
                if (on && !ps.isPlaying) ps.Play();
                else if (!on && ps.isPlaying) ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            }
        }

        static ParticleSystem MakeSmoke(Vector3 pos, Material baseMat)
        {
            var go = new GameObject("BacaDumani");
            go.transform.position = pos;
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true;
            main.playOnAwake = false;
            main.startLifetime = new ParticleSystem.MinMaxCurve(7f, 10f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.5f, 0.9f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.9f, 1.4f);
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, 6.28f);
            main.maxParticles = 60;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var em = ps.emission;
            em.rateOverTime = 4.5f;
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Cone;
            sh.angle = 7f;
            sh.radius = 0.12f;
            sh.rotation = new Vector3(-90f, 0f, 0f);
            var vel = ps.velocityOverLifetime;
            vel.enabled = true;
            vel.space = ParticleSystemSimulationSpace.World;
            vel.x = new ParticleSystem.MinMaxCurve(0.5f, 1.1f);       // kar yağışıyla aynı yönde hafif rüzgâr
            vel.y = new ParticleSystem.MinMaxCurve(0.2f, 0.45f);
            vel.z = new ParticleSystem.MinMaxCurve(-0.2f, 0.2f);
            // HDRP Lit parçacık rengini kullanmaz: duman genişleyip incelir, sonunda küçülerek kaybolur (birden sönmesin)
            var size = ps.sizeOverLifetime;
            size.enabled = true;
            size.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0f, 0.6f), new Keyframe(0.65f, 3.2f), new Keyframe(1f, 0f)));
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var mat = new Material(baseMat) { name = "BacaDumani" };
            mat.SetColor("_BaseColor", new Color(0.62f, 0.62f, 0.66f, 0.2f));
            mat.SetTexture("_BaseColorMap", SmokeTexture());
            r.sharedMaterial = mat;
            return ps;
        }

        static Texture2D smokeTex;

        // Yumuşak, kenarı düzensiz duman topağı
        static Texture2D SmokeTexture()
        {
            if (smokeTex != null) return smokeTex;
            const int n = 64;
            smokeTex = new Texture2D(n, n, TextureFormat.RGBA32, false) { name = "Duman", wrapMode = TextureWrapMode.Clamp };
            var px = new Color32[n * n];
            for (int j = 0; j < n; j++)
            for (int i = 0; i < n; i++)
            {
                float dx = (i + 0.5f) / n - 0.5f, dy = (j + 0.5f) / n - 0.5f;
                float d = Mathf.Sqrt(dx * dx + dy * dy) * 2f;
                float wob = 0.85f + 0.15f * Mathf.PerlinNoise(i * 0.15f, j * 0.15f);
                byte a = (byte)(255f * Mathf.Clamp01(1f - d / wob) * Mathf.Clamp01(1f - d / wob));
                px[j * n + i] = new Color32(255, 255, 255, a);
            }
            smokeTex.SetPixels32(px);
            smokeTex.Apply();
            return smokeTex;
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
            bool kar = id == "kar", deniz = id == "deniz";
            // Akdeniz: daha yüksek, sıcak ve parlak güneş (denizde parıltı için güneye bakan kıyı)
            sun.transform.rotation = kar ? Quaternion.Euler(30f, -58f, 0f) : deniz ? Quaternion.Euler(38f, -24f, 0f) : sunRot;
            sun.colorTemperature = kar ? 6600f : deniz ? 5600f : sunTemp;
            sun.intensity = kar ? sunIntensity * 0.8f : deniz ? sunIntensity * 1.08f : sunIntensity;
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
            main.startSize = new ParticleSystem.MinMaxCurve(0.14f, 0.34f);
            main.maxParticles = 16000;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var em = ps.emission;
            em.rateOverTime = 1000f;                    // yoğun kar yağışı
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Box;
            sh.scale = new Vector3(150f, 1f, 150f);     // kameranın yakınında (uzaktakiler zaten seçilmez)
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
