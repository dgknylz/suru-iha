using System;
using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;

namespace SuruIHA
{
    // Otomatik uçtan uca test (yalnızca Unity "-suruAutoPlay <klasör>" argümanıyla açıldığında çalışır):
    // Python'dan canlı kare gelmesini bekler, farklı kamera modlarında ekran görüntüsü alır,
    // bir rapor yazar ve editörü kapatır. Normal kullanımda hiçbir etkisi yoktur.
    public class SwarmAutoCapture : MonoBehaviour
    {
        string outDir;
        float nextLog;

        void Update()
        {
            if (Time.realtimeSinceStartup < nextLog) return;
            nextLog = Time.realtimeSinceStartup + 5f;
            Debug.Log($"[SuruIHA] nabız: kare={Time.frameCount} fps={1f / Mathf.Max(Time.smoothDeltaTime, 1e-4f):0}");
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            var args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, "-suruAutoPlay");
            if (i < 0) return;
            var go = new GameObject("OtoTest");
            var c = go.AddComponent<SwarmAutoCapture>();
            c.outDir = i + 1 < args.Length ? args[i + 1] : "AutoTest";
            Debug.Log("[SuruIHA] Otomatik test başladı: " + c.outDir);
        }

        IEnumerator Start()
        {
            Application.runInBackground = true;
            Directory.CreateDirectory(outDir);
            var log = new StringBuilder();
            var vis = FindAnyObjectByType<SwarmVisualizer>();
            var cam = FindAnyObjectByType<SwarmCamera>();
            float t0 = Time.realtimeSinceStartup;
            while (vis.Receiver == null || !vis.Receiver.Connected)
            {
                if (Time.realtimeSinceStartup - t0 > 60f) { log.AppendLine("Python bağlantısı yok!"); break; }
                yield return null;
            }
            log.AppendLine($"Bağlandı: {Time.realtimeSinceStartup - t0:0.0}s");
            Debug.Log("[SuruIHA] " + log);

            // Dayanıklılık testi: sabit kamerayla N saniye çalış, FPS ve bellek eğilimini yaz
            var args = Environment.GetCommandLineArgs();
            int si = Array.IndexOf(args, "-suruSoak");
            if (si >= 0 && si + 1 < args.Length && float.TryParse(args[si + 1], out float soak))
            {
                cam.mode = SwarmCamera.Mode.Top;
                float end = Time.realtimeSinceStartup + soak, next = 0f;
                int frames = 0;
                float t1 = Time.realtimeSinceStartup;
                while (Time.realtimeSinceStartup < end)
                {
                    frames++;
                    if (Time.realtimeSinceStartup > next)
                    {
                        float dt = Time.realtimeSinceStartup - t1;
                        if (dt > 0.5f)
                            log.AppendLine($"soak t={Time.realtimeSinceStartup - (end - soak):0}s fps={frames / dt:0} " +
                                           $"bellek={GC.GetTotalMemory(false) / 1048576}MB nesne={FindObjectsByType<Transform>(FindObjectsSortMode.None).Length}");
                        frames = 0;
                        t1 = Time.realtimeSinceStartup;
                        next = Time.realtimeSinceStartup + 10f;
                    }
                    yield return null;
                }
                File.WriteAllText(Path.Combine(outDir, "rapor.txt"), log.ToString());
#if UNITY_EDITOR
                UnityEditor.EditorApplication.Exit(0);
#else
                Application.Quit();
#endif
                yield break;
            }
            var shots = new (string name, SwarmCamera.Mode mode, float wait, int follow)[]
            {
                ("a_sinematik", SwarmCamera.Mode.Cinematic, 14f, 0),
                ("b_takip", SwarmCamera.Mode.Follow, 7f, 0),
                ("c_taktik", SwarmCamera.Mode.Top, 7f, 0),
                ("d_takip2", SwarmCamera.Mode.Follow, 7f, 4),
                ("e_sinematik2", SwarmCamera.Mode.Cinematic, 14f, 0),
                ("f_takip3", SwarmCamera.Mode.Follow, 7f, 7),
            };
            int shotNo = 0;
            foreach (var s in shots)
            {
                if (shotNo++ == 2)
                {
                    // Y komutu (görev evresinde): yeni hedef ekle, belirme dalgası ve yeniden planlama kuşbakışı görünsün
                    int popBefore = vis.Frame?.m?.popups ?? 0;
                    vis.Receiver.SendCommand("{\"cmd\":\"popup\"}");
                    cam.mode = SwarmCamera.Mode.Top;
                    float untilPop = Time.realtimeSinceStartup + 1.6f;
                    while (Time.realtimeSinceStartup < untilPop) yield return null;
                    Capture(cam.GetComponent<Camera>(), Path.Combine(outDir, "i_yeni_hedef.png"));
                    log.AppendLine($"komut testi (Y yeni hedef): yeni hedef {popBefore} -> {vis.Frame?.m?.popups} " +
                                   $"planlayici={vis.Frame?.planner} puan={vis.Frame?.m?.score:0.00} t={vis.Frame?.t:0.0}s");
                }
                cam.mode = s.mode;
                cam.SetFollow(s.follow);
                float until = Time.realtimeSinceStartup + s.wait;
                while (Time.realtimeSinceStartup < until) yield return null;
                // Game view'a bağlı kalmamak için kamerayı doğrudan dokuya çiz
                Capture(cam.GetComponent<Camera>(), Path.Combine(outDir, s.name + ".png"));
                var f = vis.Frame;
                string line = $"{s.name}: sim t={f?.t:0.0}s kare={vis.Receiver.FramesReceived} iha={vis.Drones.Count} " +
                              $"gorev={f?.m?.done}/{f?.m?.total} pdr={f?.m?.pdr:0.00} gpsYok={f?.m?.gpsLost} fps={1f / Time.smoothDeltaTime:0}";
                log.AppendLine(line);
                Debug.Log("[SuruIHA] " + line);
            }
            // Grafik kalitesi kademelerinde FPS (aynı sinematik kamera)
            cam.mode = SwarmCamera.Mode.Cinematic;
            for (int q = 0; q < QualitySettings.names.Length; q++)
            {
                QualitySettings.SetQualityLevel(q, true);
                float qs = Time.realtimeSinceStartup + 2f;
                while (Time.realtimeSinceStartup < qs) yield return null;
                int fr = 0;
                float q0 = Time.realtimeSinceStartup;
                while (Time.realtimeSinceStartup - q0 < 5f) { fr++; yield return null; }
                log.AppendLine($"kalite {QualitySettings.names[q]}: {fr / (Time.realtimeSinceStartup - q0):0} FPS");
            }
            QualitySettings.SetQualityLevel(0, true);

            // Unity -> Python komut kanalı: merkezi mimariye geç ve sonucu doğrula
            vis.Receiver.SendCommand("{\"cmd\":\"strategy\",\"value\":\"centralized\"}");
            float until3 = Time.realtimeSinceStartup + 4f;
            while (Time.realtimeSinceStartup < until3) yield return null;
            log.AppendLine($"komut testi (F1 merkezi): gelen strateji={vis.Frame?.strategy} t={vis.Frame?.t:0.0}s");
            vis.Receiver.SendCommand("{\"cmd\":\"strategy\",\"value\":\"resilient\"}");
            string plBefore = vis.Frame?.planner;
            vis.Receiver.SendCommand("{\"cmd\":\"planner\"}");
            float until4 = Time.realtimeSinceStartup + 4f;
            while (Time.realtimeSinceStartup < until4) yield return null;
            log.AppendLine($"komut testi (F4 planlama): {plBefore} -> {vis.Frame?.planner} t={vis.Frame?.t:0.0}s");

            // Elektronik harp: M (hareketli karıştırıcı) + U (hızlı GPS aldatıcı), sürü görev alanına varınca çekim
            vis.Receiver.SendCommand("{\"cmd\":\"jammer_mode\"}");
            vis.Receiver.SendCommand("{\"cmd\":\"gps_spoof\"}");
            float untilEw = Time.realtimeSinceStartup + 40f;
            while (Time.realtimeSinceStartup < untilEw) yield return null;
            cam.mode = SwarmCamera.Mode.Top;
            float untilTop = Time.realtimeSinceStartup + 3f;
            while (Time.realtimeSinceStartup < untilTop) yield return null;
            Capture(cam.GetComponent<Camera>(), Path.Combine(outDir, "j_eh_kusbakisi.png"));
            var fe = vis.Frame;
            log.AppendLine($"komut testi (M/U elektronik harp): karistirici={fe?.jammers?.Length} tur={fe?.jammers?[0].band} " +
                           $"tahmin={fe?.jamEst?.Length} hata={fe?.m?.jamErr:0}m aldatici={fe?.spoofers?.Length} " +
                           $"ele_gecen={fe?.m?.spoofed} fark_eden={fe?.m?.spoofSeen} t={fe?.t:0.0}s");
            cam.mode = SwarmCamera.Mode.Cinematic;
            float untilCine = Time.realtimeSinceStartup + 8f;
            while (Time.realtimeSinceStartup < untilCine) yield return null;
            Capture(cam.GetComponent<Camera>(), Path.Combine(outDir, "k_eh_sinematik.png"));

            // Yer seviyesinden bir çekim (ot öbekleri ve arazi ayrıntısı için)
            var camComp = cam.GetComponent<Camera>();
            var arazi = GameObject.Find("Arazi");
            if (arazi != null && arazi.TryGetComponent<Terrain>(out var terrain))
            {
                cam.enabled = false;
                Vector3 G(float x, float z, float up) =>
                    new Vector3(x, terrain.SampleHeight(new Vector3(x, 0, z)) + terrain.transform.position.y + up, z);
                foreach (var (name, from, to) in new[] { ("g_zemin_bozkir", G(-640, 250, 2.2f), G(-560, 330, 3f)),
                                                         ("h_zemin_ova", G(-60, -40, 1.8f), G(40, 40, 25f)) })
                {
                    camComp.transform.position = from;
                    camComp.transform.LookAt(to);
                    float until2 = Time.realtimeSinceStartup + 3f;
                    while (Time.realtimeSinceStartup < until2) yield return null;
                    Capture(camComp, Path.Combine(outDir, name + ".png"));
                    log.AppendLine(name);
                }
                cam.enabled = true;
            }
            File.WriteAllText(Path.Combine(outDir, "rapor.txt"), log.ToString());
            yield return null;
#if UNITY_EDITOR
            UnityEditor.EditorApplication.Exit(0);
#else
            Application.Quit();
#endif
        }

        static void Capture(Camera cam, string path)
        {
            const int w = 1920, h = 1080;
            var rt = RenderTexture.GetTemporary(w, h, 24, RenderTextureFormat.ARGB32);
            var prev = cam.targetTexture;
            cam.targetTexture = rt;
            cam.Render();
            cam.Render();
            var active = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            File.WriteAllBytes(path, tex.EncodeToPNG());
            RenderTexture.active = active;
            cam.targetTexture = prev;
            RenderTexture.ReleaseTemporary(rt);
            Destroy(tex);
        }
    }
}
