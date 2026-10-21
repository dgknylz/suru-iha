using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace SuruIHA
{
    // Film modu (tanıtım videosu): "-suruFilm <senaryo.json>" ile açılınca, Python'un kaydettiği uçuşları
    // (tools/record_film.py) kare kare oynatır ve her kareyi JPG olarak kaydeder. Oyun zamanı sabit
    // adımlıdır (Time.captureFramerate), yani render ne kadar yavaş olursa olsun video akıcıdır.
    // Alt yazılar ve kartlar Blender'da eklenir (tools/make_video.py).
    public class SwarmFilm : MonoBehaviour
    {
        [Serializable]
        public class Shot
        {
            public string a;          // sol / tek sürü kayıt dosyası
            public string b;          // (isteğe bağlı) sağ sürü: ekran ikiye bölünür
            public int from, to;      // kare aralığı (dahil, hariç)
            public string cam;        // sinematik | takip | tepe | yorunge
            public int follow;        // takip edilecek İHA
            public float yaw = float.NaN;
            public float height = 650f;   // tepe kamerasının yüksekliği (m)
            public bool plans = true, links = true, ghosts = true;
        }

        // Her çekimden önce kaydedilmeyen ısınma kareleri: otomatik pozlama ve kamera yerine otursun
        // (ilk çekimde pozlama sıfırdan başladığı için daha uzun).
        const int PrerollFirst = 90, Preroll = 20;

        [Serializable]
        public class Plan
        {
            public string outDir;
            public int width = 1920, height = 1080, fps = 30;
            public Shot[] shots;
        }

        Plan plan;
        string root;
        readonly Dictionary<string, string[]> cache = new Dictionary<string, string[]>();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            var args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, "-suruFilm");
            if (i < 0 || i + 1 >= args.Length) return;
            var go = new GameObject("Film");
            var f = go.AddComponent<SwarmFilm>();
            f.root = Path.GetDirectoryName(args[i + 1]);
            f.plan = JsonUtility.FromJson<Plan>(File.ReadAllText(args[i + 1]));
            Debug.Log($"[SuruIHA] Film modu: {f.plan.shots.Length} çekim");
        }

        string[] Lines(string name)
        {
            if (!cache.TryGetValue(name, out var l))
                cache[name] = l = File.ReadAllLines(Path.Combine(root, name));
            return l;
        }

        IEnumerator Start()
        {
            Application.runInBackground = true;
            QualitySettings.SetQualityLevel(0, true);
            Time.captureFramerate = plan.fps;
            var vis = SwarmVisualizer.Main;
            var cam = FindAnyObjectByType<SwarmCamera>();
            var hud = FindAnyObjectByType<SwarmHud>();
            var cmp = SwarmCompare.Instance;
            var camera = cam.GetComponent<Camera>();
            var rt = new RenderTexture(plan.width, plan.height, 24, RenderTextureFormat.ARGB32);
            camera.targetTexture = rt;
            var tex = new Texture2D(plan.width, plan.height, TextureFormat.RGB24, false);
            string outDir = string.IsNullOrEmpty(plan.outDir) ? Path.Combine(root, "kareler") : plan.outDir;
            Directory.CreateDirectory(outDir);
            yield return null;
            if (hud != null) hud.visible = false;
            int n = 0;
            var log = new System.Text.StringBuilder();
            foreach (var s in plan.shots)
            {
                cam.mode = s.cam switch
                {
                    "takip" => SwarmCamera.Mode.Follow,
                    "tepe" => SwarmCamera.Mode.Top,
                    "yorunge" => SwarmCamera.Mode.Orbit,
                    _ => SwarmCamera.Mode.Cinematic,
                };
                cam.SetFollow(s.follow);
                cam.topHeight = s.height;
                var la = Lines(s.a);
                var lb = string.IsNullOrEmpty(s.b) ? null : Lines(s.b);
                log.AppendLine($"çekim {s.a}{(lb != null ? " + " + s.b : "")} {s.from}-{s.to} kamera={s.cam} ilk_kare={n}");
                int pre = s == plan.shots[0] ? PrerollFirst : Preroll;
                for (int k = s.from - pre; k < s.to && k < la.Length; k++)
                {
                    int kk = Mathf.Max(k, s.from);       // ısınmada çekimin ilk karesi bekletilir
                    vis.showPlans = s.plans;
                    vis.showLinks = s.links;
                    vis.showEstimates = s.ghosts;
                    vis.Receiver.Feed(JsonUtility.FromJson<SwarmFrame>(la[kk]));
                    if (cmp != null)
                    {
                        if (lb != null && kk < lb.Length) cmp.B.Receiver.Feed(JsonUtility.FromJson<SwarmFrame>(lb[kk]));
                        else cmp.B.Receiver.Disconnect();
                    }
                    if (k == s.from - pre)
                    {
                        vis.Snap();
                        if (cmp != null) cmp.B.Snap();
                        cam.Cut(s.yaw);
                    }
                    if (k < s.from)
                    {
                        yield return null;
                        continue;
                    }
                    yield return new WaitForEndOfFrame();
                    var prev = RenderTexture.active;
                    RenderTexture.active = rt;
                    tex.ReadPixels(new Rect(0, 0, plan.width, plan.height), 0, 0);
                    tex.Apply(false);
                    RenderTexture.active = prev;
                    File.WriteAllBytes(Path.Combine(outDir, $"kare_{n:00000}.jpg"), tex.EncodeToJPG(92));
                    n++;
                    if (n % 300 == 0) Debug.Log($"[SuruIHA] film: {n} kare");
                }
            }
            log.AppendLine($"toplam {n} kare");
            File.WriteAllText(Path.Combine(outDir, "film_rapor.txt"), log.ToString());
            Debug.Log($"[SuruIHA] Film bitti: {n} kare -> {outDir}");
            yield return null;
#if UNITY_EDITOR
            UnityEditor.EditorApplication.Exit(0);
#else
            Application.Quit();
#endif
        }
    }
}
