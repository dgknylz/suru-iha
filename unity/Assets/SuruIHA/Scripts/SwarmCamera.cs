using UnityEngine;

namespace SuruIHA
{
    // Kamera modları:
    //   C  sinematik: sürünün etrafında yavaş, belgesel tarzı dönüş (açılışta bu)
    //   O  serbest yörünge: fareyle döndür, tekerlekle yakınlaş, WASD ile kaydır
    //   F  takip: seçili İHA'nın arkasından (Tab ile sıradaki, 1-9 ile doğrudan seç)
    //   T  taktik: kuşbakışı harita görünümü
    public class SwarmCamera : MonoBehaviour
    {
        public enum Mode { Cinematic, Orbit, Follow, Top }

        public SwarmVisualizer visualizer;
        public Mode mode = Mode.Cinematic;
        public float orbitDistance = 230f;
        public float rotateSpeed = 4f;
        public float panSpeed = 120f;

        public int FollowIndex { get; private set; }

        public void SetFollow(int index) => FollowIndex = Mathf.Max(0, index);

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
            switch (mode)
            {
                case Mode.Follow when visualizer.Drones.Count > 0:
                    FollowIndex = Mathf.Clamp(FollowIndex, 0, visualizer.Drones.Count - 1);
                    var d = visualizer.Drones[FollowIndex];
                    Vector3 v = d.Velocity;
                    v.y = 0;
                    Vector3 back = v.sqrMagnitude > 1f ? -v.normalized : -d.transform.forward;
                    float s = visualizer.droneScale;
                    pos = d.transform.position + back * (5f * s) + Vector3.up * (1.6f * s);
                    rot = Quaternion.LookRotation(d.transform.position + Vector3.up * 0.3f * s - back * 2f * s - pos);   // biraz önüne bak
                    Blend(pos, rot, 4f);
                    return;

                case Mode.Top:
                    pos = pivot + Vector3.up * 650f + Vector3.back * 1f;
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
                    if (SwarmInput.MouseHeld(0) || SwarmInput.MouseHeld(1))
                    {
                        var md = SwarmInput.MouseDelta();
                        yaw += md.x * rotateSpeed;
                        pitch = Mathf.Clamp(pitch - md.y * rotateSpeed, 3f, 88f);
                    }
                    orbitDistance = Mathf.Clamp(orbitDistance * (1f - SwarmInput.Scroll() * 0.1f), 15f, 2500f);
                    Vector3 move = Vector3.zero;
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

        void Blend(Vector3 pos, Quaternion rot, float sharpness)
        {
            float k = 1f - Mathf.Exp(-sharpness * Time.deltaTime);
            smoothPos = Vector3.Lerp(smoothPos, pos, k);
            smoothRot = Quaternion.Slerp(smoothRot, rot, k);
            transform.SetPositionAndRotation(smoothPos, smoothRot);
        }

        void HandleKeys()
        {
            if (SwarmInput.Down(SwarmInput.K.C)) mode = Mode.Cinematic;
            if (SwarmInput.Down(SwarmInput.K.O)) mode = Mode.Orbit;
            if (SwarmInput.Down(SwarmInput.K.T)) mode = Mode.Top;
            if (SwarmInput.Down(SwarmInput.K.F)) mode = Mode.Follow;
            if (SwarmInput.Down(SwarmInput.K.R)) freePivot = false;
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
            if (mode == Mode.Cinematic && (SwarmInput.MouseHeld(1) || Mathf.Abs(SwarmInput.Scroll()) > 0.01f))
            {
                var e = transform.rotation.eulerAngles;
                yaw = e.y;
                pitch = e.x > 180 ? e.x - 360 : e.x;
                orbitDistance = Vector3.Distance(transform.position, pivot);
                mode = Mode.Orbit;
            }
        }
    }
}
