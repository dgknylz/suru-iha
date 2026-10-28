using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;

namespace SuruIHA
{
    // Sesler: her İHA'nın pervane uğultusu (3B: yaklaştıkça artar, uzaklaştıkça hem kısılır hem boğuklaşır;
    // pervaneler gibi kalkışta hızlanır, inince ya da arızada durur), bölgeye göre rüzgâr, Kızılırmak'ta akan su,
    // olay akışının önemli anlarında yumuşak bir ton ve düğmelerde hafif bir tık. Sesler tools/make_sounds.py ile
    // sentezlenir (Resources/Ses). Kulak yormasın diye seviyeler ölçülü, tonlar seyrek (yalnızca önemli olaylarda,
    // en az 2,5 s arayla, aynı ton 6 s'de bir) ve menüdeyken ortam sesleri kısılır.
    public class SwarmAudio : MonoBehaviour
    {
        public enum Level { Kapali, Kisik, Normal }
        public static readonly string[] LevelTitles = { "Kapalı", "Kısık", "Normal" };
        static readonly float[] LevelGain = { 0f, 0.4f, 1f };

        public static SwarmAudio Instance { get; private set; }
        static Level level = Level.Normal, lastOn = Level.Normal;

        public static Level Setting
        {
            get => level;
            set
            {
                level = value;
                if (value != Level.Kapali) lastOn = value;
                PlayerPrefs.SetInt("ses", (int)level);
                PlayerPrefs.SetInt("ses_son", (int)lastOn);
            }
        }
        public static bool On => level != Level.Kapali;
        public static void Toggle() => Setting = On ? Level.Kapali : lastOn;

        class Rotor
        {
            public AudioSource src;
            public SwarmAudioTap tap;
            public float spool, detune;
        }

        AudioClip rotorClip, windClip, windSnowClip, riverClip, surfClip, tik, olumlu, uyari, tamam;
        AudioSource wind, river, ui;
        readonly Dictionary<DroneView, Rotor> rotors = new Dictionary<DroneView, Rotor>();
        readonly Dictionary<AudioClip, float> lastByClip = new Dictionary<AudioClip, float>();
        Transform listener;
        SwarmAudioTap listenerTap;
        float gain, duck = 1f, windFade, riverGain, lastCue = -10f, seenEvent = -1f;
        bool automated;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (SwarmVisualizer.Main == null) return;
            new GameObject("Sesler").AddComponent<SwarmAudio>();
        }

        void Awake()
        {
            Instance = this;
            level = (Level)Mathf.Clamp(PlayerPrefs.GetInt("ses", (int)Level.Normal), 0, 2);
            lastOn = (Level)Mathf.Clamp(PlayerPrefs.GetInt("ses_son", (int)Level.Normal), 1, 2);
            // Otomatik testte ve film çekiminde hoparlör susar (karışım yine kaydedilebilir)
            var args = Environment.GetCommandLineArgs();
            automated = args.Contains("-suruUiTest") || args.Contains("-suruAutoPlay") || args.Contains("-suruFilm");

            rotorClip = Load("pervane");
            windClip = Load("ruzgar");
            windSnowClip = Load("ruzgar_kar");
            riverClip = Load("irmak");
            surfClip = Load("dalga");
            tik = Load("tik");
            olumlu = Load("olumlu");
            uyari = Load("uyari");
            tamam = Load("tamam");

            wind = gameObject.AddComponent<AudioSource>();
            wind.loop = true;
            wind.spatialBlend = 0f;
            wind.playOnAwake = false;
            wind.priority = 10;
            wind.volume = 0f;

            // Irmak ve deniz: dinleyiciye en yakın kıyı noktasında 3B kaynak (uzaklaştıkça kısılır)
            river = new GameObject("IrmakSesi").AddComponent<AudioSource>();
            river.transform.SetParent(transform, false);
            river.clip = riverClip;
            river.loop = true;
            river.playOnAwake = false;
            river.spatialBlend = 1f;
            river.rolloffMode = AudioRolloffMode.Logarithmic;
            river.minDistance = 60f;
            river.maxDistance = 2000f;
            river.spread = 120f;          // geniş bir ırmak: ses tek noktadan değil, kıyı boyunca gelir
            river.dopplerLevel = 0f;
            river.priority = 20;
            river.volume = 0f;

            ui = gameObject.AddComponent<AudioSource>();
            ui.spatialBlend = 0f;
            ui.playOnAwake = false;
            ui.priority = 0;

            Ui.Clicked += OnClick;
        }

        void OnDestroy() => Ui.Clicked -= OnClick;

        static AudioClip Load(string name)
        {
            var c = Resources.Load<AudioClip>("Ses/" + name);
            if (c == null) Debug.LogWarning($"[SuruIHA] Ses bulunamadı: Resources/Ses/{name} (tools/make_sounds.py)");
            return c;
        }

        void OnClick()
        {
            if (tik != null) ui.PlayOneShot(tik, 0.7f);
        }

        void Update()
        {
            float dt = Time.unscaledDeltaTime;
            if (listener == null)
            {
                var al = FindAnyObjectByType<AudioListener>();
                if (al != null)
                {
                    listener = al.transform;
                    listenerTap = al.GetComponent<SwarmAudioTap>();
                    if (listenerTap == null) listenerTap = al.gameObject.AddComponent<SwarmAudioTap>();
                    listenerTap.muteOutput = automated;
                }
            }
            var menu = SwarmMenu.Instance;
            bool inSim = menu == null || menu.Current == SwarmMenu.Page.Sim;
            duck = Mathf.MoveTowards(duck, inSim ? 1f : 0.35f, dt * 1.5f);
            gain = Mathf.MoveTowards(gain, LevelGain[(int)level], dt * 2f);     // aç/kapa yumuşak (tık sesi olmasın)
            AudioListener.volume = gain;

            UpdateRotors(dt);
            UpdateAmbience(dt);
            UpdateCues();
        }

        // ------------------------------------------------------------ pervaneler
        void UpdateRotors(float dt)
        {
            var vis = SwarmVisualizer.Main;
            if (vis == null || rotorClip == null) return;
            if (rotors.Count > vis.Drones.Count)
                foreach (var dead in rotors.Keys.Where(k => k == null).ToList()) rotors.Remove(dead);
            foreach (var d in vis.Drones)
            {
                if (d == null) continue;
                if (!rotors.TryGetValue(d, out var r)) rotors[d] = r = MakeRotor(d);
                // Pervanelerin dönüşüyle aynı: 0 duruyor, ~0,4 yerde rölanti, 1 havada
                float target = d.Rpm / 2400f;
                r.spool = Mathf.MoveTowards(r.spool, target, dt * (target > r.spool ? 0.8f : 1.5f));
                Vector3 v = d.Velocity;
                float speed = new Vector2(v.x, v.z).magnitude;
                float climb = Mathf.Clamp(v.y * 0.006f, -0.03f, 0.05f);    // tırmanırken motorlar zorlanır
                r.src.pitch = r.detune * (0.55f + 0.45f * r.spool) * (1f + Mathf.Min(speed * 0.0012f, 0.05f) + climb);
                r.src.volume = 0.6f * Mathf.Pow(r.spool, 0.8f) * duck;
                if (listener != null)
                {
                    float dist = Vector3.Distance(listener.position, d.transform.position);
                    float far = Mathf.InverseLerp(Mathf.Log(15f), Mathf.Log(600f), Mathf.Log(Mathf.Max(dist, 1f)));
                    r.tap.cutoff = Mathf.Lerp(5500f, 800f, far);
                }
                bool audible = r.src.volume > 0.0005f;
                if (audible && !r.src.isPlaying)
                {
                    r.src.Play();
                    r.src.timeSamples = UnityEngine.Random.Range(0, rotorClip.samples);   // İHA'lar aynı anda aynı sesi çalmasın
                }
                else if (!audible && r.src.isPlaying) r.src.Stop();
            }
        }

        Rotor MakeRotor(DroneView d)
        {
            var s = d.gameObject.AddComponent<AudioSource>();
            s.clip = rotorClip;
            s.loop = true;
            s.playOnAwake = false;
            s.spatialBlend = 1f;
            s.rolloffMode = AudioRolloffMode.Logarithmic;
            s.minDistance = 20f;
            s.maxDistance = 900f;
            s.dopplerLevel = 0.3f;
            s.priority = 64;
            s.volume = 0f;
            var tap = d.gameObject.AddComponent<SwarmAudioTap>();
            // Her İHA'nın devri biraz farklı: sürü tek bir ton değil, gerçekteki gibi hafif dalgalanan bir uğultu
            float detune = 1f + ((d.Id * 7) % 9 - 4) * 0.008f + UnityEngine.Random.Range(-0.003f, 0.003f);
            return new Rotor { src = s, tap = tap, detune = detune };
        }

        // ------------------------------------------------------------ rüzgâr ve ırmak
        void UpdateAmbience(float dt)
        {
            string region = SwarmRegions.Current;
            var want = region == "kar" ? windSnowClip : windClip;
            if (want != null)
            {
                // Bölge değişince rüzgâr kısılır, yeni bölgeninkiyle yeniden açılır
                if (wind.clip != want)
                {
                    windFade = Mathf.MoveTowards(windFade, 0f, dt * 2f);
                    if (windFade <= 0f || !wind.isPlaying)
                    {
                        wind.clip = want;
                        wind.Play();
                        wind.time = UnityEngine.Random.Range(0f, want.length * 0.9f);
                    }
                }
                else windFade = Mathf.MoveTowards(windFade, 1f, dt * 0.6f);
                // Kamera yükseldikçe rüzgâr biraz artar
                float alt = 0.3f;
                var vis = SwarmVisualizer.Main;
                if (listener != null && vis != null) alt = Mathf.Clamp01((listener.position.y - vis.GroundAt(listener.position)) / 400f);
                float baseVol = region == "kar" ? 0.75f : region == "nehir" ? 0.52f : 0.7f;
                wind.volume = baseVol * Mathf.Lerp(0.75f, 1.25f, alt) * windFade * duck;
            }

            // Kızılırmak'ta ırmak, Akdeniz'de kıyıya vuran dalgalar (bölge değişince ses kısılıp kaynak değişir)
            var waterClip = region == "nehir" ? riverClip : region == "deniz" ? surfClip : null;
            bool riverOn = waterClip != null && listener != null && river.clip == waterClip;
            riverGain = Mathf.MoveTowards(riverGain, riverOn ? 1f : 0f, dt * 0.6f);
            if (riverGain <= 0f && waterClip != null && river.clip != waterClip)
            {
                river.Stop();
                river.clip = waterClip;
            }
            river.volume = (region == "deniz" ? 1f : 0.9f) * riverGain * duck;
            if (riverOn) river.transform.position = region == "deniz" ? NearestCoastPoint(listener.position) : NearestRiverPoint(listener.position);
            if (riverGain > 0f && !river.isPlaying) river.Play();
            else if (riverGain <= 0f && river.isPlaying) river.Stop();
        }

        static Vector3 NearestRiverPoint(Vector3 p)
        {
            Vector3 o = SwarmRegions.RiverOffset;
            float lx = p.x - o.x, lz = p.z - o.z, best = float.MaxValue, bx = lx;
            for (float x = lx - 400f; x <= lx + 400f; x += 8f)
            {
                float cx = Mathf.Clamp(x, -SwarmRegions.RiverHalfLength, SwarmRegions.RiverHalfLength);
                float dx = lx - cx, dz = lz - SwarmRegions.RiverZ(cx);
                float d = dx * dx + dz * dz;
                if (d < best) { best = d; bx = cx; }
            }
            return new Vector3(o.x + bx, o.y + SwarmRegions.WaterLevel, o.z + SwarmRegions.RiverZ(bx));
        }

        static Vector3 NearestCoastPoint(Vector3 p)
        {
            Vector3 o = SwarmRegions.SeaOffset;
            float lx = p.x - o.x, lz = p.z - o.z, best = float.MaxValue, bx = lx;
            for (float x = lx - 500f; x <= lx + 500f; x += 10f)
            {
                float dx = lx - x, dz = lz - SwarmRegions.SeaCoastZ(x);
                float d = dx * dx + dz * dz;
                if (d < best) { best = d; bx = x; }
            }
            return new Vector3(o.x + bx, o.y + SwarmRegions.SeaLevel, o.z + SwarmRegions.SeaCoastZ(bx));
        }

        // ------------------------------------------------------------ olay tonları
        void UpdateCues()
        {
            var ev = SwarmEvents.Instance;
            if (ev == null) return;
            foreach (var e in ev.Items)
            {
                if (e.real <= seenEvent) continue;
                seenEvent = e.real;
                // Yalnızca önemli anlar: görev bitti; uyarı (kırmızı: GPS karıştırıldı, arıza, yanlış "bitti");
                // olumlu (hedefler tamamlandı, karıştırıcı bulundu, saldırganlar dışlandı). "GPS geri geldi" gibi
                // sık ve küçük haberler sessiz geçer.
                var c = e.text.StartsWith("Bütün hedefler tamam") ? tamam
                      : e.color == Ui.Bad ? uyari
                      : e.color == Ui.Good && (e.text.Contains("hedef tamamlandı") || e.text.Contains("yerini ölçümlerden") ||
                                               e.text.Contains("dışlıyor")) ? olumlu
                      : null;
                if (c != null) Cue(c);
            }
        }

        void Cue(AudioClip c)
        {
            float now = Time.unscaledTime;
            if (c != tamam && (now - lastCue < 2.5f || (lastByClip.TryGetValue(c, out float t) && now - t < 6f))) return;
            lastCue = now;
            lastByClip[c] = now;
            ui.PlayOneShot(c, 0.55f * Mathf.Lerp(0.5f, 1f, duck));
        }

        // ------------------------------------------------------------ test kaydı
        // Dinleyicinin duyduğu karışımı WAV olarak kaydeder ve seviyesini rapora yazar (arayüz testi)
        public IEnumerator Record(string path, float seconds, string label, StringBuilder log)
        {
            float wait = Time.realtimeSinceStartup + 5f;
            while (listenerTap == null && Time.realtimeSinceStartup < wait) yield return null;
            if (listenerTap == null)
            {
                log.AppendLine($"ses ({label}): dinleyici YOK");
                yield break;
            }
            listenerTap.BeginRecord();
            float end = Time.realtimeSinceStartup + seconds;
            while (Time.realtimeSinceStartup < end) yield return null;
            var data = listenerTap.EndRecord(out int ch, out int rate);
            WriteWav(path, data, ch, rate);
            double sum = 0;
            float peak = 0f;
            foreach (float s in data)
            {
                sum += s * s;
                peak = Mathf.Max(peak, Mathf.Abs(s));
            }
            float rms = data.Length > 0 ? Mathf.Sqrt((float)(sum / data.Length)) : 0f;
            log.AppendLine($"ses ({label}): {data.Length / Mathf.Max(ch, 1) / (float)rate:0.0} s, " +
                           $"RMS {20f * Mathf.Log10(rms + 1e-9f):0.0} dBFS, tepe {20f * Mathf.Log10(peak + 1e-9f):0.0} dBFS, " +
                           $"çalan İHA sesi {rotors.Values.Count(r => r.src != null && r.src.isPlaying)}");
        }

        static void WriteWav(string path, float[] data, int ch, int rate)
        {
            using var w = new BinaryWriter(File.Create(path));
            int bytes = data.Length * 2;
            w.Write(Encoding.ASCII.GetBytes("RIFF"));
            w.Write(36 + bytes);
            w.Write(Encoding.ASCII.GetBytes("WAVEfmt "));
            w.Write(16);
            w.Write((short)1);
            w.Write((short)ch);
            w.Write(rate);
            w.Write(rate * ch * 2);
            w.Write((short)(ch * 2));
            w.Write((short)16);
            w.Write(Encoding.ASCII.GetBytes("data"));
            w.Write(bytes);
            foreach (float s in data) w.Write((short)Mathf.Clamp(Mathf.RoundToInt(s * 32767f), -32768, 32767));
        }
    }
}
