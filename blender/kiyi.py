"""Akdeniz kıyısı ve Gökpınar Gölü yapıları: deniz feneri, balıkçı tekneleri, kıyı evleri, ahşap kameriye ve iskele.

    blender -b --factory-startup -P blender/kiyi.py -- <çıktı_klasörü>
Çıktı: SuruIHA_Yapi_Fener.fbx, SuruIHA_Yapi_Tekne_0..1.fbx, SuruIHA_Yapi_SahilEv_0..2.fbx,
       SuruIHA_Yapi_Kameriye.fbx, SuruIHA_Yapi_AhsapIskele.fbx
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)


def mats():
    return dict(
        white=C.mat("MAT_BoyaBeyaz", (0.86, 0.86, 0.83), rough=0.8),
        red=C.mat("MAT_BoyaKirmizi", (0.62, 0.08, 0.06), rough=0.55),
        blue=C.mat("MAT_TekneMavi", (0.05, 0.22, 0.48), rough=0.45),
        wood=C.mat("MAT_Wood", (0.25, 0.17, 0.1), rough=0.85),
        lightwood=C.mat("MAT_AhsapAcik", (0.48, 0.34, 0.2), rough=0.7),
        glass=C.mat("MAT_Glass", (0.01, 0.014, 0.018), rough=0.04, metal=0.3),
        metal=C.mat("MAT_Metal", (0.5, 0.51, 0.52), rough=0.38, metal=1.0),
        black=C.mat("MAT_Black", (0.02, 0.02, 0.022), rough=0.6),
        lamp=C.mat("MAT_Lamp", (0.9, 0.85, 0.7), rough=0.1, emission=(1.0, 0.9, 0.7), strength=3.0),
        stone=C.mat("MAT_KaleTas", (0.55, 0.48, 0.4), rough=0.9),
        roof=C.mat("MAT_RoofTile", (0.42, 0.15, 0.07), rough=0.75),
        frame=C.mat("MAT_Frame", (0.8, 0.8, 0.78), rough=0.5),
        door=C.mat("MAT_Door", (0.22, 0.12, 0.06), rough=0.7),
        shutter=C.mat("MAT_PanjurMavi", (0.12, 0.33, 0.52), rough=0.6),
    )


def lighthouse():
    """Kayalık burundaki deniz feneri: beyaz konik kule, kırmızı fener odası ve kubbe, balkon korkuluğu,
    yanında kırmızı kiremitli bekçi evi. Fener camının içinde yanan lamba."""
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_Fener")
    p = [C.cyl("Kaide", 3.6, 3.0, (0, 0, -0.5), M["stone"], verts=24),
         C.cone("Kule", 2.6, 1.75, 15.0, (0, 0, 8.5), M["white"], verts=32)]
    for z in (6.0, 11.0):
        p.append(C.cone(f"Bant{z}", 2.6 - (z - 1.0) / 15.0 * 0.85 + 0.03, 2.6 - (z + 1.2 - 1.0) / 15.0 * 0.85 + 0.03, 1.2,
                        (0, 0, z + 0.6), M["red"], verts=32))
    p.append(C.cyl("BalkonAlti", 2.4, 0.35, (0, 0, 16.2), M["white"], verts=32))
    p.append(C.cyl("Balkon", 2.5, 0.15, (0, 0, 16.45), M["metal"], verts=32))
    for k in range(24):
        a = 2 * math.pi * k / 24
        p.append(C.cyl(f"Dikme{k}", 0.03, 1.0, (math.cos(a) * 2.42, math.sin(a) * 2.42, 17.0), M["metal"], verts=6))
    bpy.ops.mesh.primitive_torus_add(major_radius=2.42, minor_radius=0.04, major_segments=48, minor_segments=6, location=(0, 0, 17.5))
    t = bpy.context.active_object
    t.data.materials.append(M["metal"])
    p.append(t)
    p.append(C.cyl("FenerOdasiAlt", 1.45, 0.8, (0, 0, 16.9), M["red"], verts=24))
    p.append(C.cyl("FenerCam", 1.3, 2.0, (0, 0, 18.3), M["glass"], verts=24))
    for k in range(8):
        a = 2 * math.pi * k / 8
        p.append(C.box(f"CamKayit{k}", (0.08, 0.08, 2.0), (math.cos(a) * 1.31, math.sin(a) * 1.31, 18.3), M["red"]))
    p.append(C.sphere("Lamba", 0.55, (0, 0, 18.3), M["lamp"], segs=16, rings=8))
    p.append(C.cyl("KubbeAlti", 1.5, 0.25, (0, 0, 19.42), M["red"], verts=24))
    p.append(C.sphere("Kubbe", 1.45, (0, 0, 19.5), M["red"], scale=(1, 1, 0.7), segs=24, rings=12))
    p.append(C.cyl("Paratoner", 0.04, 1.6, (0, 0, 21.2), M["metal"], verts=6))
    p.append(C.box("Kapi", (1.0, 0.2, 2.1), (0, -2.55, 2.0), M["door"]))
    for z in (5.0, 9.0, 13.0):
        p.append(C.box(f"Pencere{z}", (0.5, 0.2, 0.9), (0, -2.6 + (z - 1.0) / 15.0 * 0.85, z), M["glass"]))
    C.join(p, "Kule").parent = root
    # bekçi evi
    h = [C.box("Ev", (7.0, 5.0, 3.2), (7.0, 1.0, 1.1), M["white"]),
         C.box("EvTemel", (7.4, 5.4, 2.5), (7.0, 1.0, -1.0), M["stone"]),
         C.box("EvKapi", (1.0, 0.1, 2.1), (6.0, -1.52, 1.05), M["door"])]
    for x in (4.6, 8.4, 9.6):
        h.append(C.box(f"EvPen{x}", (0.9, 0.08, 1.1), (x, -1.52, 1.6), M["glass"]))
        h.append(C.box(f"EvPanjur{x}", (1.4, 0.06, 1.2), (x, -1.5, 1.6), M["shutter"]))
    C.join(h, "BekciEvi").parent = root
    bm = bmesh.new()
    W, D, z, hh = 4.0, 3.0, 2.7, 1.3
    v = [bm.verts.new(q) for q in ((3.0, -2.0, z), (11.0, -2.0, z), (11.0, 4.0, z), (3.0, 4.0, z))]
    a, b = bm.verts.new((4.5, 1.0, z + hh)), bm.verts.new((9.5, 1.0, z + hh))
    bm.faces.new((v[0], v[1], b, a))
    bm.faces.new((v[1], v[2], b))
    bm.faces.new((v[2], v[3], a, b))
    bm.faces.new((v[3], v[0], a))
    bm.faces.new(list(reversed(v)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    C.mesh_object("EvCati", bm, M["roof"], root, smooth=False)
    C.stats(root)
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_Fener.fbx"), root)


def hull(name, L, B, D, sheer, mat, n=24, m=12):
    """Balıkçı teknesi gövdesi: boy boyunca kesitlerden örülen U kesitli tekne (baş sivri, kıç dolgun)."""
    bm = bmesh.new()
    rows = []
    for i in range(n + 1):
        t = i / n                                  # 0 kıç, 1 baş
        x = (t - 0.5) * L
        half = B / 2 * (math.sin(math.pi * min(1.0, 0.18 + 0.95 * t)) ** 0.55 if t > 0.05 else 0.82)
        half = max(half, 0.05)
        depth = D * (0.75 + 0.25 * math.sin(math.pi * t))
        top = sheer * (2 * t - 1) ** 2 * (1.4 if t > 0.5 else 0.6)
        ring = []
        for j in range(m + 1):
            a = math.pi * j / m                    # 0: sancak güverte, π: iskele güverte
            yy = math.cos(a) * half
            zz = top - math.sin(a) ** 0.8 * depth
            ring.append(bm.verts.new((x, yy, zz)))
        rows.append(ring)
    for i in range(n):
        for j in range(m):
            bm.faces.new((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]))
    # güverte (üstü kapalı) ve kıç ayna
    for i in range(n):
        bm.faces.new((rows[i][m], rows[i + 1][m], rows[i + 1][0], rows[i][0]))
    bm.faces.new([rows[0][j] for j in range(m + 1)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return C.mesh_object(name, bm, mat, smooth=True)


def boat(idx):
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty(f"SuruIHA_Yapi_Tekne_{idx}")
    L, B = (9.0, 3.0) if idx == 0 else (12.0, 3.8)
    body = hull("Govde", L, B, 1.3, 0.45, M["white"])
    body.parent = root
    stripe = hull("Serit", L * 1.003, B * 1.01, 0.32, 0.45, M["blue"])
    stripe.location.z = 0.02
    stripe.parent = root
    deck = [C.box("Kamara", (2.4, B * 0.62, 1.7), (-L * 0.12, 0, 0.95), M["white"]),
            C.box("KamaraCati", (2.7, B * 0.7, 0.12), (-L * 0.12, 0, 1.86), M["blue"])]
    for sx in (-1, 1):
        deck.append(C.box(f"KamaraPen{sx}", (1.6, 0.05, 0.55), (-L * 0.12, sx * B * 0.311, 1.35), M["glass"]))
    deck.append(C.box("KamaraOnPen", (0.05, B * 0.5, 0.5), (-L * 0.12 + 1.21, 0, 1.4), M["glass"]))
    deck.append(C.cyl("Direk", 0.08, 5.5 if idx else 4.2, (L * 0.18, 0, 2.8 if idx else 2.2), M["wood"], verts=8))
    deck.append(C.cyl("Bum", 0.05, 3.0, (L * 0.05, 0, 1.6), M["wood"], verts=8, rot=(0, math.pi / 2 - 0.25, 0)))
    deck.append(C.box("Kupeste", (L * 0.9, B * 0.96, 0.18), (0, 0, 0.42), M["lightwood"]))
    deck.append(C.cyl("Makara", 0.3, 0.5, (L * 0.28, 0, 0.75), M["metal"], verts=12, rot=(math.pi / 2, 0, 0)))
    for k in range(4):
        deck.append(C.box(f"Kasa{k}", (0.5, 0.4, 0.3), (L * 0.05 + k * 0.6 - 1.2, B * 0.2 * (1 if k % 2 else -1), 0.65), M["blue"]))
    deck.append(C.box("Bayrak", (0.04, 0.9, 0.6), (L * 0.18, 0.45, 4.6 if idx else 3.9), M["red"]))
    C.join(deck, "Ust").parent = root
    C.export_fbx(os.path.join(OUT, f"SuruIHA_Yapi_Tekne_{idx}.fbx"), root)


def coast_house(idx, rnd):
    """Akdeniz kıyı evi: beyaz badanalı kübik ev, mavi panjurlar, düz damda teras korkuluğu (ya da kiremit),
    bir yanda asma çardağı."""
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty(f"SuruIHA_Yapi_SahilEv_{idx}")
    w, d = rnd.uniform(7, 10), rnd.uniform(6, 8)
    floors = 1 + idx % 2
    H = 3.0 * floors
    p = [C.box("Temel", (w + 0.4, d + 0.4, 2.4), (0, 0, -0.9), M["stone"]),
         C.box("Duvar", (w, d, H), (0, 0, H / 2 + 0.3), M["white"], bevel=0.05, segments=2)]
    for fl in range(floors):
        z = 0.3 + fl * 3.0 + 1.6
        for side in (-1, 1):
            for k in range(max(2, int(w // 2.6))):
                x = -w / 2 + (k + 0.5) * w / max(2, int(w // 2.6))
                p.append(C.box(f"Pen{fl}{side}{k}", (0.8, 0.06, 1.1), (x, side * (d / 2 + 0.01), z), M["glass"]))
                for sx in (-1, 1):
                    p.append(C.box(f"Panjur{fl}{side}{k}{sx}", (0.42, 0.05, 1.15), (x + sx * 0.64, side * (d / 2 + 0.03), z), M["shutter"]))
    p.append(C.box("Kapi", (1.0, 0.1, 2.1), (w * 0.25, -d / 2 - 0.02, 1.35), M["shutter"]))
    body = C.join(p, "Ev")
    body.parent = root
    top = 0.3 + H
    if idx == 2:
        bm = bmesh.new()
        W, D, hh = w / 2 + 0.4, d / 2 + 0.4, 1.4
        v = [bm.verts.new(q) for q in ((-W, -D, top), (W, -D, top), (W, D, top), (-W, D, top))]
        a, b = bm.verts.new((-W + D, 0, top + hh)), bm.verts.new((W - D, 0, top + hh))
        bm.faces.new((v[0], v[1], b, a))
        bm.faces.new((v[1], v[2], b))
        bm.faces.new((v[2], v[3], a, b))
        bm.faces.new((v[3], v[0], a))
        bm.faces.new(list(reversed(v)))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        C.mesh_object("Cati", bm, M["roof"], root, smooth=False)
    else:
        C.box("Parapet", (w + 0.1, d + 0.1, 0.6), (0, 0, top + 0.3), M["white"], root)
        C.box("Dam", (w - 0.3, d - 0.3, 0.1), (0, 0, top + 0.35), M["frame"], root)
        C.cyl("SuDeposu", 0.5, 1.2, (w * 0.3, d * 0.2, top + 1.2), M["white"], root, verts=16, rot=(0, math.pi / 2, 0))
    # asma çardağı (ahşap kirişler)
    pg = []
    for k in range(4):
        pg.append(C.cyl(f"CardakDikme{k}", 0.08, 2.6, (-w / 2 + 0.6 + (k % 2) * 2.6, -d / 2 - 0.5 - (k // 2) * 2.4, 1.6), M["wood"], verts=8))
    for k in range(5):
        pg.append(C.box(f"CardakKiris{k}", (3.2, 0.1, 0.1), (-w / 2 + 1.9, -d / 2 - 0.5 - k * 0.6, 2.9), M["wood"]))
    C.join(pg, "Cardak").parent = root
    C.export_fbx(os.path.join(OUT, f"SuruIHA_Yapi_SahilEv_{idx}.fbx"), root)


def gazebo():
    """Gökpınar Gölü kıyısında sekizgen ahşap kameriye."""
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_Kameriye")
    r = 2.6
    p = [C.cyl("Zemin", r + 0.2, 0.5, (0, 0, 0.05), M["stone"], verts=8, smooth=False),
         C.cyl("Doseme", r, 0.1, (0, 0, 0.35), M["lightwood"], verts=8, smooth=False)]
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        p.append(C.box(f"Dikme{k}", (0.16, 0.16, 2.6), (math.cos(a) * (r - 0.15), math.sin(a) * (r - 0.15), 1.65), M["wood"]))
        if k != 0:
            a2 = 2 * math.pi * (k + 1) / 8
            mid = ((math.cos(a) + math.cos(a2)) / 2 * (r - 0.2), (math.sin(a) + math.sin(a2)) / 2 * (r - 0.2))
            p.append(C.box(f"Korkuluk{k}", (2 * r * math.sin(math.pi / 8) - 0.1, 0.08, 0.08), (mid[0], mid[1], 1.25), M["wood"],
                           rot=(0, 0, (a + a2) / 2 + math.pi / 2)))
            p.append(C.box(f"Oturak{k}", (2 * r * math.sin(math.pi / 8) - 0.3, 0.4, 0.06), (mid[0] * 0.88, mid[1] * 0.88, 0.8), M["lightwood"],
                           rot=(0, 0, (a + a2) / 2 + math.pi / 2)))
    p.append(C.cyl("Masa", 0.7, 0.06, (0, 0, 1.15), M["lightwood"], verts=16))
    p.append(C.cyl("MasaAyak", 0.08, 0.75, (0, 0, 0.75), M["wood"], verts=8))
    C.join(p, "Govde").parent = root
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=r + 0.7, radius2=0.12, depth=1.9, location=(0, 0, 3.9), rotation=(0, 0, math.pi / 8))
    roof = bpy.context.active_object
    roof.name = "Cati"
    roof.data.materials.append(M["roof"])
    roof.parent = root
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_Kameriye.fbx"), root)


def boardwalk():
    """Ahşap iskele/yürüyüş yolu parçası (10 m): kazıklar üstünde tahta döşeme ve korkuluk."""
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_AhsapIskele")
    p = []
    for k in range(25):
        p.append(C.box(f"Tahta{k}", (0.36, 2.2, 0.06), (-5 + 0.2 + k * 0.4, 0, 0.6), M["lightwood"]))
    for x in (-4.8, -1.6, 1.6, 4.8):
        for y in (-1.0, 1.0):
            p.append(C.cyl(f"Kazik{x}{y}", 0.1, 2.6, (x, y, -0.7), M["wood"], verts=8))
            p.append(C.box(f"KorkulukDikme{x}{y}", (0.08, 0.08, 1.0), (x, y * 1.05, 1.1), M["wood"]))
    for y in (-1.05, 1.05):
        p.append(C.box(f"Kupeste{y}", (10.0, 0.08, 0.08), (0, y, 1.6), M["wood"]))
        p.append(C.box(f"Kiris{y}", (10.0, 0.12, 0.2), (0, y * 0.9, 0.48), M["wood"]))
    C.join(p, "Iskele").parent = root
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_AhsapIskele.fbx"), root)


if __name__ == "__main__":
    lighthouse()
    boat(0)
    boat(1)
    rnd = random.Random(7)
    for i in range(3):
        coast_house(i, rnd)
    gazebo()
    boardwalk()
