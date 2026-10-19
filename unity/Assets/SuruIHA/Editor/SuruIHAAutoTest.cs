using System;
using UnityEditor;
using UnityEditor.SceneManagement;

namespace SuruIHA.EditorTools
{
    // Unity "-suruAutoPlay <klasör>" ile açılınca sahneyi açıp Play'e basar.
    // Ekran görüntülerini runtime tarafındaki SwarmAutoCapture alır ve editörü kapatır.
    [InitializeOnLoad]
    public static class SuruIHAAutoTest
    {
        static double readyAt;

        static double nextWatchLog;

        static SuruIHAAutoTest()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-suruAutoPlay") < 0) return;
            EditorApplication.update -= Watch;
            EditorApplication.update += Watch;
            if (EditorApplication.isPlayingOrWillChangePlaymode || SessionState.GetBool("SuruAutoStarted", false)) return;
            readyAt = EditorApplication.timeSinceStartup + 3.0;
            EditorApplication.update -= Tick;
            EditorApplication.update += Tick;
        }

        // Play modu bir sebeple duraklarsa (ör. Error Pause) devam ettir ve durumu günlüğe yaz
        static void Watch()
        {
            if (EditorApplication.isPlaying && EditorApplication.isPaused)
            {
                UnityEngine.Debug.Log("[SuruIHA] Play duraklatılmıştı, devam ettiriliyor");
                EditorApplication.isPaused = false;
            }
            if (EditorApplication.timeSinceStartup > nextWatchLog)
            {
                nextWatchLog = EditorApplication.timeSinceStartup + 10.0;
                UnityEngine.Debug.Log($"[SuruIHA] editör: oynuyor={EditorApplication.isPlaying} duraklatıldı={EditorApplication.isPaused}");
            }
        }

        // Derleme ve içe aktarma bitip editör sakinleşince bir kez çalışır
        static void Tick()
        {
            if (EditorApplication.isCompiling || EditorApplication.isUpdating) { readyAt = EditorApplication.timeSinceStartup + 3.0; return; }
            if (EditorApplication.timeSinceStartup < readyAt) return;
            EditorApplication.update -= Tick;
            if (SessionState.GetBool("SuruAutoStarted", false)) return;
            SessionState.SetBool("SuruAutoStarted", true);
            PlayerSettings.runInBackground = true;
            EditorSceneManager.OpenScene("Assets/SuruIHA/Scenes/SuruSahnesi.unity");
            EditorApplication.EnterPlaymode();
        }
    }
}
