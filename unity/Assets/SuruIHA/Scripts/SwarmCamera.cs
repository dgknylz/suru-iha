using UnityEngine;

namespace SuruIHA
{
    // Kamera modları:
    //   C  sinematik: sürünün etrafında yavaş, belgesel tarzı dönüş (açılışta bu)
    //   O  serbest yörünge: fareyle döndür, tekerlekle yakınlaş, WASD ile kaydır
    //   F  İHA kamerası (üçüncü şahıs, TPP): seçili İHA'nın arkasından ve üstünden izler. Fareyle etrafında
    //      döndür, tekerlekle yakınlaş, R ile sıfırla. Tab sıradaki İHA, 1-9 ve 0 (İHA-10) doğrudan seçer.
    //   T  taktik: kuşbakışı harita görünümü
    public class SwarmCamera : MonoBehaviour
    {
        public enum Mode { Cinematic, Orbit, Follow, Top }

        public SwarmVisualizer visualizer;
        public Mode mode = Mode.Cinematic;
        public float orbitDistance = 230f;
        public float rotateSpeed = 4f;
        public float panSpeed = 120f;
        public float topHeight = 650f;      // taktik görünümün yüksekliği (film modu çekime göre değiştirir)

        public int FollowIndex { get; private set; }

        public void SetFollow(int index) => FollowIndex = Mathf.Max(0, index);

        // Üçüncü şahıs (TPP) İHA kamerası: açı ve uzaklık fareyle değişir, R ile sıfırlanır.
        // Yan yana ekranda sağdaki sürü RigB ile aynı açıdan izlenir.
        public const float DefaultTppPitch = 12f, DefaultTppDistance = 11f;
        public float TppYaw, TppPitch = DefaultTppPitch, TppDistance = DefaultTppDistance;
        public readonly TppRig RigB = new TppRig();
        readonly TppRig rig = new TppRig();
        bool rigActive;

        public void ResetTpp()
        {
            TppYaw = 0f;
            TppPitch = DefaultTppPitch;
            TppDistance = DefaultTppDistance;
        }

        Vector3 pivot;
        float yaw = 35f, pitch = 28f;
        bool freePivot;
        float cineT;
        Vector3 smoothPos;
        Quaternion smoothRot;

        void Start()
        {
            if (visualizer == null) visualizer = FindAnyObjectByType<SwarmVisualizer>();
            smoothPos = transform.position;
            smoothRot = transform.rotation;
        }

        void LateUpdate()
        {
            if (visualizer == null) return;
            HandleKeys();
            Vector3 swarm = visualizer.Drones.Count > 0 ? visualizer.Centroid : visualizer.transform.position + Vector3.up * 40f;
            if (!freePivot) pivot = Vector3.Lerp(pivot, swarm, 1f - Mathf.Exp(-1.5f * Time.deltaTime));

            Vector3 pos;
            Quaternion rot;
            if (mode != Mode.Follow) rigActive = false;
            switch (mode)
            {
                case Mode.Follow when visualizer.Drones.Count > 0:
                {
                    FollowIndex = Mathf.Clamp(FollowIndex, 0, visualizer.Drones.Count - 1);
                    if (!Ui.PointerBlocked)
                    {
                        // Fareyle İHA'nın etrafında dön, tekerlekle yakınlaş
                        if (SwarmInput.MouseHeld(0) || SwarmInput.MouseHeld(1))
                        {
                            var md = SwarmInput.MouseDelta();
                            TppYaw += md.x * rotateSpeed;
                            TppPitch = Mathf.Clamp(TppPitch - md.y * rotateSpeed, -5f, 75f);
                        }
                        TppDistance = Mathf.Clamp(TppDistance * (1f - SwarmInput.Scroll() * 0.1f), 6f, 90f);
                    }
                    if (cut) { rig.Snap(); cut = false; }
                    if (!rigActive) rig.Begin(transform.position, transform.rotation);
                    rigActive = true;
                    var (p, r) = rig.Step(visualizer, visualizer.Drones[FollowIndex], Time.deltaTime, TppYaw, TppPitch, TppDistance);
                    smoothPos = p;
                    smoothRot = r;
                    transform.SetPositionAndRotation(p, r);
                    return;
                }

                case Mode.Top:
                    pos = pivot + Vector3.up * topHeight + Vector3.back * 1f;
                    rot = Quaternion.Euler(89.9f, 0, 0);
                    Blend(pos, rot, 2.5f);
                    return;

                case Mode.Cinematic:
                    cineT += Time.deltaTime;
                    yaw += 4f * Time.deltaTime;
                    pitch = 18f + 10f * Mathf.Sin(cineT * 0.11f);
                    float dist = orbitDistance * (0.75f + 0.25f * Mathf.Sin(cineT * 0.07f));
                    rot = Quaternion.Euler(pitch, yaw, 0);
                    pos = pivot - rot * Vector3.forward * dist;
                    Blend(pos, rot, 1.2f);
                    return;

                default:
                    bool mouseFree = !Ui.PointerBlocked;   // fare bir panelin üstündeyse sahne dönmesin
                    if (mouseFree && (SwarmInput.MouseHeld(0) || SwarmInput.MouseHeld(1)))
                    {
                        var md = SwarmInput.MouseDelta();
                        yaw += md.x * rotateSpeed;
                        pitch = Mathf.Clamp(pitch - md.y * rotateSpeed, 3f, 88f);
                    }
                    if (mouseFree) orbitDistance = Mathf.Clamp(orbitDistance * (1f - SwarmInput.Scroll() * 0.1f), 15f, 2500f);
                    Vector3 move = Vector3.zero;
                    if (Ui.Modal) { rot = Quaternion.Euler(pitch, yaw, 0); pos = pivot - rot * Vector3.forward * orbitDistance; Blend(pos, rot, 10f); return; }
                    if (SwarmInput.Held(SwarmInput.K.W)) move += Vector3.forward;
                    if (SwarmInput.Held(SwarmInput.K.S)) move += Vector3.back;
                    if (SwarmInput.Held(SwarmInput.K.A)) move += Vector3.left;
                    if (SwarmInput.Held(SwarmInput.K.D)) move += Vector3.right;
                    if (SwarmInput.Held(SwarmInput.K.E)) move += Vector3.up;
                    if (SwarmInput.Held(SwarmInput.K.Q)) move += Vector3.down;
                    if (move != Vector3.zero)
                    {
                        freePivot = true;
                        float boost = SwarmInput.Held(SwarmInput.K.Shift) ? 3f : 1f;
                        pivot += Quaternion.Euler(0, yaw, 0) * move * panSpeed * boost * Time.deltaTime;
                    }
                    rot = Quaternion.Euler(pitch, yaw, 0);
                    pos = pivot - rot * Vector3.forward * orbitDistance;
                    Blend(pos, rot, 10f);
                    return;
            }
        }

        bool cut;

        // Film modu: bir sonraki karede yumuşatmadan doğrudan yeni açıya geç (sahne kesmesi)
        public void Cut(float yawDeg = float.NaN)
        {
            cut = true;
            if (!float.IsNaN(yawDeg)) yaw = yawDeg;
            if (visualizer != null && visualizer.Drones.Count > 0) pivot = visualizer.Centroid;
        }

        void Blend(Vector3 pos, Quaternion rot, float sharpness)
        {
            float k = cut ? 1f : 1f - Mathf.Exp(-sharpness * Time.deltaTime);
            cut = false;
            smoothPos = Vector3.Lerp(smoothPos, pos, k);
            smoothRot = Quaternion.Slerp(smoothRot, rot, k);
            transform.SetPositionAndRotation(smoothPos, smoothRot);
        }

        void HandleKeys()
        {
            if (Ui.Modal) return;   // menü açık: kamera kısayolları susar
            if (SwarmInput.Down(SwarmInput.K.C)) mode = Mode.Cinematic;
            if (SwarmInput.Down(SwarmInput.K.O)) mode = Mode.Orbit;
            if (SwarmInput.Down(SwarmInput.K.T)) mode = Mode.Top;
            if (SwarmInput.Down(SwarmInput.K.F)) mode = Mode.Follow;
            if (SwarmInput.Down(SwarmInput.K.R))
            {
                freePivot = false;
                if (mode == Mode.Follow) ResetTpp();
            }
            if (SwarmInput.Down(SwarmInput.K.Tab) && visualizer.Drones.Count > 0)
            {
                FollowIndex = (FollowIndex + 1) % visualizer.Drones.Count;
                mode = Mode.Follow;
            }
            int digit = SwarmInput.DigitDown();
            if (digit > 0 && digit <= visualizer.Drones.Count)
            {
                FollowIndex = digit - 1;
                mode = Mode.Follow;
            }
            // Sinematik moddayken fareyle oynamak serbest yörüngeye geçirir
            if (mode == Mode.Cinematic && !Ui.PointerBlocked && (SwarmInput.MouseHeld(1) || Mathf.Abs(SwarmInput.Scroll()) > 0.01f))
            {
                var e = transform.rotation.eulerAngles;
                yaw = e.y;
                pitch = e.x > 180 ? e.x - 360 : e.x;
                orbitDistance = Vector3.Distance(transform.position, pivot);
                mode = Mode.Orbit;
            }
        }
    }

    // Üçüncü şahıs (TPP) kamera düzeneği: İHA'nın arkasında ve biraz üstünde durur, uçuş yönünü yumuşakça
    // izler, araziye girmez. Kendi yumuşatma durumunu tutar; yan yana ekranda her sürüye bir tane.
    public class TppRig
    {
        Vector3 pos;
        Quaternion rot;
        float heading;
        bool init, headingInit;

        // Kameranın şu anki yerinden başla: İHA'ya doğru süzülerek gelir
        public void Begin(Vector3 p, Quaternion r)
        {
            pos = p;
            rot = r;
            init = true;
            headingInit = false;
        }

        // Film kesmesi: bir sonraki adımda doğrudan yerine geç
        public void Snap() => init = headingInit = false;

        public (Vector3, Quaternion) Step(SwarmVisualizer vis, DroneView d, float dt, float yawOff, float pitch, float dist)
        {
            Vector3 v = d.Velocity;
            v.y = 0f;
            float target = v.sqrMagnitude > 1f ? Mathf.Atan2(v.x, v.z) * Mathf.Rad2Deg : headingInit ? heading : d.transform.eulerAngles.y;
            heading = headingInit ? Mathf.LerpAngle(heading, target, 1f - Mathf.Exp(-2.5f * dt)) : target;
            headingInit = true;

            float s = vis.droneScale;
            Vector3 focus = d.transform.position + Vector3.up * 0.25f * s;
            Quaternion orbit = Quaternion.Euler(pitch, heading + yawOff, 0f);
            Vector3 want = focus - orbit * Vector3.forward * dist;
            float ground = vis.GroundAt(want) + 2.5f;      // kamera araziye girmesin
            if (want.y < ground) want.y = ground;
            // İHA ekranın alt üçte birinde dursun: odağın biraz üstüne bak
            Quaternion look = Quaternion.LookRotation(focus + Vector3.up * dist * 0.12f - want);
            if (!init)
            {
                pos = want;
                rot = look;
                init = true;
            }
            else
            {
                pos = Vector3.Lerp(pos, want, 1f - Mathf.Exp(-10f * dt));
                rot = Quaternion.Slerp(rot, look, 1f - Mathf.Exp(-12f * dt));
            }
            return (pos, rot);
        }
    }
}
