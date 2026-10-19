"""Taktik keşif quadcopter'i (X düzen, ~0.9 m motor-motor, 15" pervane).

Çalıştırma:
    blender -b -P blender/drone.py -- <çıktı_klasörü>
Çıktı: SuruIHA_Drone.fbx  (+ önizleme render'ı)

Unity'de isimle bulunan parçalar:
    Prop_FL / Prop_FR / Prop_RL / Prop_RR  -> dönen pervaneler (merkezleri motor ekseninde)
    LED_Status                              -> durum ışığı (rengi koddan değişir)
    NavLight_L / NavLight_R                 -> seyrüsefer ışıkları (sol kırmızı, sağ yeşil)
    Camera_Gimbal                           -> önde, gövde altında (yön kontrolü için)
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(os.path.abspath(__file__))

C.reset_scene()

# ------------------------------------------------------------------ malzemeler
M_BODY = C.mat("MAT_Body", (0.165, 0.18, 0.15), rough=0.62)            # mat zeytin yeşili kompozit
M_SHELL = C.mat("MAT_Shell", (0.215, 0.232, 0.195), rough=0.55)
M_CARBON = C.mat("MAT_Carbon", (0.018, 0.018, 0.02), rough=0.32, metal=0.15)
M_METAL = C.mat("MAT_Metal", (0.62, 0.63, 0.65), rough=0.3, metal=1.0)
M_BELL = C.mat("MAT_MotorBell", (0.05, 0.05, 0.055), rough=0.28, metal=0.9)
M_ACCENT = C.mat("MAT_Accent", (0.75, 0.32, 0.05), rough=0.45, metal=0.6)  # turuncu eloksal halka
M_PROP = C.mat("MAT_Prop", (0.012, 0.012, 0.012), rough=0.38)
M_PROPTIP = C.mat("MAT_PropTip", (0.85, 0.85, 0.82), rough=0.4)
M_RUBBER = C.mat("MAT_Rubber", (0.02, 0.02, 0.02), rough=0.92)
M_GLASS = C.mat("MAT_Glass", (0.005, 0.008, 0.012), rough=0.03, metal=0.2)
M_BATT = C.mat("MAT_Battery", (0.07, 0.072, 0.075), rough=0.7)
M_LED = C.mat("MAT_LED_Status", (0.1, 1.0, 0.4), emission=(0.1, 1.0, 0.4), strength=8.0)
M_NAVR = C.mat("MAT_Nav_Red", (1.0, 0.05, 0.03), emission=(1.0, 0.05, 0.03), strength=10.0)
M_NAVG = C.mat("MAT_Nav_Green", (0.05, 1.0, 0.2), emission=(0.05, 1.0, 0.2), strength=10.0)
M_NAVW = C.mat("MAT_Nav_White", (1.0, 1.0, 1.0), emission=(1.0, 1.0, 1.0), strength=8.0)

root = C.empty("SuruIHA_Drone")

# Ön -Y yönünde. Sağ taraf -X, sol taraf +X.
MOTOR_R = 0.32                                           # motor merkezinin x/y uzaklığı
MOTORS = {"FL": (+1, -1), "FR": (-1, -1), "RL": (+1, +1), "RR": (-1, +1)}

# ------------------------------------------------------------------ gövde
def loft(name, stations, n=40, power=2.7):
    """Önden arkaya kesitlerden örülen gövde. Kesit: süperelips (köşeleri yuvarlatılmış dikdörtgen).
    stations: (y, yarı_genişlik, yarı_yükseklik, z_merkez)"""
    bm = bmesh.new()
    rings = []
    for (y, a, b, zc) in stations:
        ring = []
        for j in range(n):
            t = j / n * math.tau
            c, s = math.cos(t), math.sin(t)
            x = a * math.copysign(abs(c) ** (2 / power), c)
            z = zc + b * math.copysign(abs(s) ** (2 / power), s)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for j in range(n):
            bm.faces.new((r0[j], r0[(j + 1) % n], r1[(j + 1) % n], r1[j]))
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        ctr = bm.verts.new(sum((v.co for v in ring), Vector()) / len(ring))
        for j in range(n):
            f = (ring[j], ring[(j + 1) % n], ctr)
            bm.faces.new(tuple(reversed(f)) if rev else f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = C.mesh_object(name, bm, None, smooth=True)
    m = o.modifiers.new("Sub", "SUBSURF")
    m.levels = 2
    C.apply_modifiers(o)
    return o


def split_z(o, z, gap, top_mat, bottom_mat, name):
    """Gövdeyi z düzleminde iki kabuğa ayırır (üst kapak / alt gövde), arada ince panel boşluğu."""
    top = o.copy()
    top.data = o.data.copy()
    bpy.context.collection.objects.link(top)
    for obj, keep_top in ((top, True), (o, False)):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, z),
                                     plane_no=(0, 0, 1), clear_inner=keep_top, clear_outer=not keep_top)
        edges = [e for e in bm.edges if e.is_boundary]
        bmesh.ops.holes_fill(bm, edges=edges)
        bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0, 0, gap / 2 if keep_top else -gap / 2))
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.materials.clear()
        obj.data.materials.append(top_mat if keep_top else bottom_mat)
        C.shade_smooth(obj, 50)
    top.name, o.name = name + "_Kapak", name + "_Alt"
    return top, o


parts = []
# Aerodinamik gövde: burun (-Y) yuvarlak ve alçak, ortası dolgun, kuyruk incelen
STATIONS = [
    (-0.222, 0.018, 0.016, -0.004), (-0.212, 0.048, 0.034, -0.002), (-0.19, 0.072, 0.048, 0.003),
    (-0.15, 0.088, 0.057, 0.008), (-0.08, 0.098, 0.062, 0.012), (0.02, 0.1, 0.062, 0.012),
    (0.11, 0.095, 0.056, 0.009), (0.17, 0.083, 0.046, 0.005), (0.205, 0.066, 0.034, 0.002),
    (0.222, 0.04, 0.02, 0.0),
]
hull = loft("Govde", STATIONS)
cap, low = split_z(hull, 0.018, 0.0025, M_SHELL, M_BODY, "Govde")
parts += [cap, low]
# Burunda stereo engel algılama kameraları ve altında mesafe sensörü
for sx in (-1, 1):
    parts.append(C.cyl(f"Stereo_Halka_{sx}", 0.011, 0.012, (sx * 0.032, -0.206, 0.006), M_CARBON, verts=24, rot=(math.pi / 2, 0, 0)))
    parts.append(C.cyl(f"Stereo_Cam_{sx}", 0.0075, 0.004, (sx * 0.032, -0.2125, 0.006), M_GLASS, verts=24, rot=(math.pi / 2, 0, 0)))
parts.append(C.box("ToF_Sensor", (0.03, 0.012, 0.01), (0, -0.2, -0.03), M_GLASS, bevel=0.002, rot=(math.radians(-30), 0, 0)))
# Yan havalandırma ızgaraları (gövde yüzeyine gömülü)
for sx in (-1, 1):
    for k in range(6):
        parts.append(C.box(f"Izgara_{sx}_{k}", (0.006, 0.045, 0.004), (sx * 0.097, 0.05, -0.022 + k * 0.008), M_CARBON))
# Batarya (üstte, gövde kabuğunun arkasında) ve kayışı
parts.append(C.box("Batarya", (0.11, 0.14, 0.04), (0, 0.075, 0.088), M_BATT, bevel=0.008, segments=3))
parts.append(C.box("Batarya_Etiket", (0.06, 0.05, 0.001), (0, 0.075, 0.1085), M_ACCENT))
parts.append(C.box("Batarya_Kayis", (0.115, 0.018, 0.043), (0, 0.04, 0.089), M_RUBBER, bevel=0.003))
parts.append(C.box("Batarya_Kayis2", (0.115, 0.018, 0.043), (0, 0.11, 0.089), M_RUBBER, bevel=0.003))
parts.append(C.box("Batarya_Ray", (0.12, 0.16, 0.006), (0, 0.075, 0.068), M_CARBON, bevel=0.002))
# Kol bağlantı kelepçeleri
for key, (sx, sy) in MOTORS.items():
    parts.append(C.box(f"Kelepce_{key}", (0.05, 0.05, 0.04), (sx * 0.075, sy * 0.13, 0.0), M_CARBON,
                       bevel=0.006, rot=(0, 0, math.radians(45 * sx * sy))))
    parts.append(C.cyl(f"Mentese_{key}", 0.012, 0.05, (sx * 0.1, sy * 0.155, 0.0), M_METAL, verts=20,
                       rot=(0, 0, 0)))
body = C.join(parts, "Govde")
body.parent = root

# ------------------------------------------------------------------ kollar ve motorlar
for key, (sx, sy) in MOTORS.items():
    mx, my = sx * MOTOR_R, sy * MOTOR_R
    arm = C.tube_between(f"Kol_{key}", (sx * 0.085, sy * 0.14, 0.0), (mx, my, 0.0), 0.014, M_CARBON, root, verts=20)
    # Kol ortasında katlanma eklemi
    a = Vector((sx * 0.085, sy * 0.14, 0.0))
    b = Vector((mx, my, 0.0))
    d = (b - a).normalized()
    j = a + (b - a) * 0.35
    hinge = C.tube_between(f"Eklem_{key}", j - d * 0.022, j + d * 0.022, 0.019, M_METAL, root, verts=24)
    lock = C.box(f"EklemKilit_{key}", (0.012, 0.03, 0.012), (j.x, j.y, 0.02), M_ACCENT, root, bevel=0.003,
                 rot=(0, 0, math.atan2(d.y, d.x) + math.pi / 2))
    # Kol ucunda motor altı ESC kutusu
    esc = C.box(f"ESC_{key}", (0.05, 0.022, 0.014), tuple(b - d * 0.07 + Vector((0, 0, -0.018))), M_BODY, root,
                bevel=0.003, rot=(0, 0, math.atan2(d.y, d.x)))

    # Motor: alt montaj + stator gövdesi + soğutma kanatlı çan + üst kapak
    mp = []
    mp.append(C.box(f"MotorMontaj_{key}", (0.05, 0.05, 0.012), (mx, my, -0.008), M_CARBON, bevel=0.004))
    mp.append(C.cyl(f"MotorTaban_{key}", 0.036, 0.016, (mx, my, 0.006), M_BELL, verts=40, bevel=0.002))
    mp.append(C.cyl(f"MotorCan_{key}", 0.038, 0.028, (mx, my, 0.03), M_BELL, verts=40, bevel=0.003))
    for f in range(16):
        a = f * math.tau / 16
        mp.append(C.box(f"Kanat_{key}_{f}", (0.006, 0.0025, 0.022), (mx + math.cos(a) * 0.039, my + math.sin(a) * 0.039, 0.03),
                        M_BELL, rot=(0, 0, a)))
    mp.append(C.cyl(f"MotorHalka_{key}", 0.0385, 0.004, (mx, my, 0.044), M_ACCENT, verts=40))
    mp.append(C.cyl(f"MotorKapak_{key}", 0.02, 0.008, (mx, my, 0.05), M_METAL, verts=32, bevel=0.002))
    motor = C.join(mp, f"Motor_{key}")
    motor.parent = root

    # Motor altı seyrüsefer ışıkları: önde sol kırmızı, sağ yeşil; arkada beyaz
    if sy < 0:
        nm, nname = (M_NAVR, "NavLight_L") if sx > 0 else (M_NAVG, "NavLight_R")
    else:
        nm, nname = M_NAVW, f"NavLight_Rear_{key}"
    C.sphere(nname, 0.011, (mx, my, -0.02), nm, root, scale=(1, 1, 0.6), segs=16, rings=8)


# ------------------------------------------------------------------ pervaneler
def blade_mesh(ccw):
    """Bükümlü (twist), daralan, profilli tek pervane kanadı. +X boyunca uzanır."""
    bm = bmesh.new()
    r0, R = 0.022, 0.19
    n_sec, n_pts = 16, 12
    rings = []
    for s in range(n_sec + 1):
        u = s / n_sec
        r = r0 + (R - r0) * u
        chord = 0.028 + 0.022 * math.sin(math.pi * min(u * 1.25, 1.0)) * (1 - 0.55 * u)
        chord *= (1.0 - 0.6 * max(0.0, u - 0.85) / 0.15)       # uçta yuvarlanma
        thick = 0.11 * chord * (1 - 0.5 * u)
        twist = math.radians(28 - 18 * u)                      # kökte 28°, uçta 10°
        if ccw:
            twist = -twist
        ring = []
        for p in range(n_pts):
            t = p / n_pts * math.tau
            # İnce kamburlu profil (elips + kambur)
            x = 0.5 * chord * math.cos(t)
            z = 0.5 * thick * math.sin(t) + 0.04 * chord * (1 - (2 * x / chord) ** 2)
            y = x * math.cos(twist) - z * math.sin(twist)
            zz = x * math.sin(twist) + z * math.cos(twist)
            ring.append(bm.verts.new((r, y, zz)))
        rings.append(ring)
    for s, (a, b) in enumerate(zip(rings[:-1], rings[1:])):
        tip = s >= n_sec - 2          # son iki dilim beyaz uç şeridi (malzeme 1)
        for p in range(n_pts):
            q = (p + 1) % n_pts
            f = bm.faces.new((a[p], a[q], b[q], b[p]))
            f.material_index = 1 if tip else 0
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1]).material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


for key, (sx, sy) in MOTORS.items():
    mx, my = sx * MOTOR_R, sy * MOTOR_R
    ccw = (sx * sy) > 0          # çapraz motorlar ters döner
    blades = []
    for k in range(2):
        b = C.mesh_object(f"Kanat_{key}_{k}", blade_mesh(ccw), M_PROP)
        b.data.materials.append(M_PROPTIP)
        b.data.transform(Matrix.Rotation(k * math.pi, 4, "Z"))
        blades.append(b)
    blades.append(C.cyl(f"PervaneGobek_{key}", 0.016, 0.014, (0, 0, 0), M_METAL, verts=32, bevel=0.002))
    blades.append(C.cone(f"PervaneSomun_{key}", 0.01, 0.003, 0.014, (0, 0, 0.013), M_ACCENT, verts=24))
    # Pervane tek parça; pivotu motor ekseninde (Unity Y ekseni etrafında döndürür)
    p = C.join(blades, f"Prop_{key}")
    C.apply_transform(p)
    p.location = (mx, my, 0.062)
    p.parent = root

# ------------------------------------------------------------------ iniş takımı
gear = []
for sx in (-1, 1):
    for sy in (-1, 1):
        gear.append(C.tube_between(f"Bacak_{sx}_{sy}", (sx * 0.07, sy * 0.09, -0.03), (sx * 0.13, sy * 0.1, -0.2), 0.008, M_CARBON, verts=12))
    gear.append(C.tube_between(f"Kizak_{sx}", (sx * 0.13, -0.17, -0.2), (sx * 0.13, 0.17, -0.2), 0.009, M_CARBON, verts=14))
    for sy in (-1, 1):
        gear.append(C.sphere(f"KizakUcu_{sx}_{sy}", 0.012, (sx * 0.13, sy * 0.17, -0.2), M_RUBBER, segs=12, rings=8))
        gear.append(C.cyl(f"Takoz_{sx}_{sy}", 0.014, 0.03, (sx * 0.13, sy * 0.1, -0.2), M_RUBBER, verts=16,
                          rot=(math.pi / 2, 0, 0)))
landing = C.join(gear, "InisTakimi")
landing.parent = root

# ------------------------------------------------------------------ gimbal kamera (önde, altta)
gm = []
gm.append(C.box("Gimbal_Montaj", (0.06, 0.05, 0.012), (0, -0.12, -0.042), M_CARBON, bevel=0.004))
gm.append(C.cyl("Gimbal_Sonumleyici", 0.008, 0.016, (0.02, -0.12, -0.055), M_RUBBER, verts=12))
gm.append(C.cyl("Gimbal_Sonumleyici2", 0.008, 0.016, (-0.02, -0.12, -0.055), M_RUBBER, verts=12))
gm.append(C.box("Gimbal_Catal_L", (0.008, 0.03, 0.05), (0.048, -0.125, -0.085), M_BODY, bevel=0.003))
gm.append(C.box("Gimbal_Catal_R", (0.008, 0.03, 0.05), (-0.048, -0.125, -0.085), M_BODY, bevel=0.003))
gm.append(C.box("Gimbal_Ust", (0.104, 0.03, 0.01), (0, -0.125, -0.062), M_BODY, bevel=0.003))
gm.append(C.sphere("Gimbal_Kure", 0.042, (0, -0.125, -0.1), M_SHELL, segs=40, rings=20))
gm.append(C.cyl("Lens_Halka", 0.02, 0.012, (0.012, -0.165, -0.1), M_METAL, verts=32, rot=(math.pi / 2, 0, 0), bevel=0.002))
gm.append(C.cyl("Lens_Cam", 0.016, 0.004, (0.012, -0.171, -0.1), M_GLASS, verts=32, rot=(math.pi / 2, 0, 0)))
gm.append(C.cyl("Termal_Halka", 0.012, 0.01, (-0.018, -0.163, -0.1), M_METAL, verts=24, rot=(math.pi / 2, 0, 0)))
gm.append(C.cyl("Termal_Cam", 0.009, 0.004, (-0.018, -0.168, -0.1), M_GLASS, verts=24, rot=(math.pi / 2, 0, 0)))
gm.append(C.cyl("Lazer_Mesafe", 0.005, 0.006, (0.0, -0.166, -0.075), M_GLASS, verts=16, rot=(math.pi / 2, 0, 0)))
gimbal = C.join(gm, "Camera_Gimbal")
gimbal.parent = root

# ------------------------------------------------------------------ anten, GPS, durum ışığı
top = []
top.append(C.cyl("GPS_Direk", 0.006, 0.07, (0, 0.14, 0.13), M_CARBON, verts=12))
top.append(C.cyl("GPS_Kutu", 0.034, 0.014, (0, 0.14, 0.17), M_SHELL, verts=40, bevel=0.004))
top.append(C.sphere("GPS_Kubbe", 0.03, (0, 0.14, 0.177), M_SHELL, scale=(1, 1, 0.3), segs=32, rings=12))
for sx in (-1, 1):
    a, b = (sx * 0.06, 0.16, 0.03), (sx * 0.1, 0.22, 0.17)
    top.append(C.tube_between(f"Anten_{sx}", a, b, 0.0035, M_RUBBER, verts=10))
    top.append(C.cyl(f"AntenTaban_{sx}", 0.008, 0.015, (sx * 0.06, 0.16, 0.03), M_METAL, verts=16))
    top.append(C.sphere(f"AntenUc_{sx}", 0.005, b, M_RUBBER, segs=10, rings=6))
top.append(C.box("DurumIsigi_Yuva", (0.03, 0.012, 0.012), (0, 0.172, 0.01), M_CARBON, bevel=0.003))
antennas = C.join(top, "Antenler")
antennas.parent = root
led = C.box("LED_Status", (0.022, 0.006, 0.006), (0, 0.178, 0.01), M_LED, bevel=0.002)
led.parent = root
led2 = C.box("LED_Status_Ust", (0.03, 0.03, 0.004), (0, -0.05, 0.091), M_LED, bevel=0.003)
led2.parent = root

# ------------------------------------------------------------------ işaretler: bayrak ve yazı
M_FLAG = C.mat("MAT_Flag", (0.8, 0.05, 0.08), rough=0.55)
M_MARK = C.mat("MAT_Marking", (0.75, 0.76, 0.72), rough=0.6)


def flag_quad(name, side, yc, zc, w, h):
    """Gövde yanına bayrak çıkartması; gönder (ay-yıldız tarafı) her iki yanda öne bakar."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    x = side * 0.1015
    y0, y1, z0, z1 = yc - w / 2, yc + w / 2, zc - h / 2, zc + h / 2
    vs = [bm.verts.new(p) for p in ((x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1))]
    uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
    if side < 0:
        vs, uvs = vs[::-1], uvs[::-1]
    f = bm.faces.new(vs)
    for loop, uv in zip(f.loops, uvs):
        loop[uvl].uv = uv
    return C.mesh_object(name, bm, M_FLAG, root, smooth=False)


def text_mesh(name, body, side, yc, zc, size):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.extrude = 0.0003
    for f in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"):
        if os.path.exists(f):
            cu.font = bpy.data.fonts.load(f)
            break
    o = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(o)
    # Yazının x ekseni okuyucunun sağına, normali gövdenin dışına
    if side > 0:
        M = Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0)))       # sütunlar: x->+Y, y->+Z, z->+X
    else:
        M = Matrix(((0, 0, -1), (-1, 0, 0), (0, 1, 0)))     # x->-Y, y->+Z, z->-X
    o.matrix_world = Matrix.Translation((side * 0.1012, yc, zc)) @ M.to_4x4()
    C.select_only(o)
    bpy.ops.object.convert(target="MESH")
    o = bpy.context.active_object
    o.name = name
    o.data.materials.clear()
    o.data.materials.append(M_MARK)
    o.parent = root
    return o


for side in (-1, 1):
    flag_quad(f"Bayrak_{'L' if side > 0 else 'R'}", side, 0.075, -0.002, 0.054, 0.036)
    text_mesh(f"Yazi_{'L' if side > 0 else 'R'}", "SÜRÜ İHA", side, -0.075, -0.004, 0.019)

C.stats(root)
os.makedirs(OUT, exist_ok=True)
C.export_fbx(os.path.join(OUT, "SuruIHA_Drone.fbx"), root)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "SuruIHA_Drone.blend"))
