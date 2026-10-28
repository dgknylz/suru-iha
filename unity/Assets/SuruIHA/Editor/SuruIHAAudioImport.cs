using UnityEditor;
using UnityEngine;

namespace SuruIHA.EditorTools
{
    // Sentezlenen sesler (Resources/Ses, tools/make_sounds.py): döngüler dikişsiz kalsın diye sıkıştırılmaz (PCM),
    // tek kanal ve açılışta belleğe açılır (hepsi birlikte ~10 MB).
    class SuruIHAAudioImport : AssetPostprocessor
    {
        void OnPreprocessAudio()
        {
            if (!assetPath.Replace('\\', '/').Contains("/Resources/Ses/")) return;
            var imp = (AudioImporter)assetImporter;
            imp.forceToMono = true;
            imp.loadInBackground = false;
            var s = imp.defaultSampleSettings;
            s.loadType = AudioClipLoadType.DecompressOnLoad;
            s.compressionFormat = AudioCompressionFormat.PCM;
            s.sampleRateSetting = AudioSampleRateSetting.PreserveSampleRate;
            imp.defaultSampleSettings = s;
        }
    }
}
