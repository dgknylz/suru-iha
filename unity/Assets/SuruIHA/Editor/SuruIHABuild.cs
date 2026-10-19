using System;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace SuruIHA.EditorTools
{
    // Menü: SürüİHA > Windows Uygulaması Derle
    // Jüriye Unity açmadan gösterilebilecek bağımsız SuruIHA.exe üretir.
    public static class SuruIHABuild
    {
        [MenuItem("SürüİHA/Windows Uygulaması Derle", priority = 20)]
        public static void BuildWindows() => Build("C:/SuruIHA/Build/SuruIHA.exe");

        public static void BuildFromCommandLine()
        {
            var args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, "-out");
            Build(i >= 0 && i + 1 < args.Length ? args[i + 1] : "C:/SuruIHA/Build/SuruIHA.exe");
        }

        static void Build(string path)
        {
            PlayerSettings.runInBackground = true;
            PlayerSettings.productName = "Sürü İHA - Elektronik Harp Simülasyonu";
            PlayerSettings.companyName = "TUBITAK 2204";
            PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
            PlayerSettings.defaultScreenWidth = 1920;
            PlayerSettings.defaultScreenHeight = 1080;
            PlayerSettings.resizableWindow = true;
            var opts = new BuildPlayerOptions
            {
                scenes = new[] { "Assets/SuruIHA/Scenes/SuruSahnesi.unity" },
                locationPathName = path,
                target = BuildTarget.StandaloneWindows64,
                options = BuildOptions.None,
            };
            var report = BuildPipeline.BuildPlayer(opts);
            Debug.Log($"[SuruIHA] Derleme: {report.summary.result}, {report.summary.totalSize / 1048576} MB, " +
                      $"{report.summary.totalTime.TotalMinutes:0.0} dk, hata={report.summary.totalErrors} -> {path}");
            if (Application.isBatchMode)
                EditorApplication.Exit(report.summary.result == BuildResult.Succeeded ? 0 : 1);
        }
    }
}
