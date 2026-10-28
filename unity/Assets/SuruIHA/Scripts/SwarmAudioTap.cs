using System.Collections.Generic;
using UnityEngine;

namespace SuruIHA
{
    // Ses sinyaline doğrudan dokunan küçük bileşen (ses iş parçacığında çalışır).
    // İHA'da: uzaklığa göre alçak geçiren süzgeç (havada yol alan sesin tizleri söner, uzaktaki İHA boğuk duyulur).
    // Kamerada (dinleyici): otomatik testlerde karışımın kaydı ve hoparlörün susturulması.
    public class SwarmAudioTap : MonoBehaviour
    {
        public volatile float cutoff = 22000f;   // Hz; 18 kHz üstünde süzgeç devre dışı
        public volatile bool muteOutput;

        readonly float[] s1 = new float[8], s2 = new float[8];
        readonly List<float> rec = new List<float>();
        volatile bool recording;
        int channels = 2, rate = 48000;

        void Awake() => rate = AudioSettings.outputSampleRate;

        public void BeginRecord()
        {
            lock (rec) rec.Clear();
            recording = true;
        }

        public float[] EndRecord(out int ch, out int sampleRate)
        {
            recording = false;
            ch = channels;
            sampleRate = rate;
            lock (rec) return rec.ToArray();
        }

        void OnAudioFilterRead(float[] data, int ch)
        {
            float c = cutoff;
            if (c < 18000f)
            {
                // iki kademeli tek kutuplu süzgeç (12 dB/oktav)
                float a = 1f - Mathf.Exp(-2f * Mathf.PI * c / rate);
                int n = Mathf.Min(ch, 8);
                for (int i = 0; i < data.Length; i += ch)
                    for (int k = 0; k < n; k++)
                    {
                        s1[k] += a * (data[i + k] - s1[k]);
                        s2[k] += a * (s1[k] - s2[k]);
                        data[i + k] = s2[k];
                    }
            }
            if (recording)
                lock (rec)
                {
                    channels = ch;
                    rec.AddRange(data);
                }
            if (muteOutput) System.Array.Clear(data, 0, data.Length);
        }
    }
}
