"""Divriği (Sivas): Ulu Camii ve Darüşşifası (1228-29, Mengücekli), kale burçları ve surları, Divriği evleri.

    blender -b --factory-startup -P blender/divrigi.py -- <çıktı_klasörü> [önizleme.blend]
Çıktı: SuruIHA_Yapi_UluCami.fbx, SuruIHA_Yapi_KaleKule.fbx, SuruIHA_Yapi_KaleBurc.fbx, SuruIHA_Yapi_KaleSur.fbx,
       SuruIHA_Yapi_DivrigiEv_0..3.fbx

Ulu Camii yayımlanmış tasvirlere göre kodla kuruldu (ölçüler yaklaşık): 32 x 64 m'lik kesme taş külliye, kuzeyde beş
sahınlı, 25 bölümlü cami, güneyde (kıble duvarına bitişik) iki katlı darüşşifa. Dışta: caminin kuzey taç kapısı
(duvardan yükselen, derin sivri kemerli niş, mukarnas kavsara, iki gömme sütun, yüksek kabartma madalyonlar, tepede altıgen
motif), batı kapısı (dokuma gibi sık geometrik oyma, yuvarlak kemer, mukarnaslı kavsara), doğuda Şah Mahfili kapısı,
darüşşifanın batı cephesinde iki iç içe sivri kemerli taç kapısı (kapı üstünde pencere, iki yanda hilal çerçeveli büyük
madalyon). Damda: mihrap önü kubbesinin sekizgen külahı, türbenin altıgen külahı, caminin ve darüşşifanın fenerleri.
Kuzeybatı köşesinde payandanın üstünde silindir minare (1523). Blender'da önü (kuzey) -Y yönüne bakar.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else os.path.dirname(os.path.abspath(__file__))
BLEND = ARGS[1] if len(ARGS) > 1 else None
os.makedirs(OUT, exist_ok=True)


def mats():
    return dict(
        stone=C.mat("MAT_KesmeTas", (0.8, 0.7, 0.53), rough=0.85),
        carve=C.mat("MAT_Oyma", (0.8, 0.7, 0.53), rough=0.88),
        earth=C.mat("MAT_Toprak", (0.45, 0.38, 0.3), rough=0.95),
        lead=C.mat("MAT_Lead", (0.33, 0.35, 0.37), rough=0.45, metal=0.6),
        door=C.mat("MAT_Door", (0.22, 0.12, 0.06), rough=0.7),
        wood=C.mat("MAT_Wood", (0.25, 0.17, 0.1), rough=0.85),
        glass=C.mat("MAT_Glass", (0.01, 0.014, 0.018), rough=0.04, metal=0.3),
        black=C.mat("MAT_Black", (0.02, 0.02, 0.022), rough=0.6),
        metal=C.mat("MAT_Metal", (0.5, 0.51, 0.52), rough=0.38, metal=1.0),
        castle=C.mat("MAT_KaleTas", (0.55, 0.48, 0.4), rough=0.9),
        roof=C.mat("MAT_RoofTile", (0.42, 0.15, 0.07), rough=0.75),
        frame=C.mat("MAT_Frame", (0.8, 0.8, 0.78), rough=0.5),
    )


# ---------------------------------------------------------------------------- geometri yardımcıları
def arch_outline(w, spring, pointed=True, n=14):
    """Kemer dış çizgisi (XZ düzleminde, tabanı z=0, ortası x=0): sivri (iki merkezli) ya da yuvarlak."""
    pts = [(-w / 2, 0.0), (-w / 2, spring)]
    if pointed:
        R = 0.8 * w
        cx = -w / 2 + R                             # sol yayın merkezi (sağda)
        th0, th1 = math.pi, math.acos(-cx / R)
        for i in range(1, n):
            t = th0 + (th1 - th0) * i / n
            pts.append((cx + R * math.cos(t), spring + R * math.sin(t)))
        apex = spring + R * math.sin(th1)
        pts.append((0.0, apex))
        right = [(-x, z) for x, z in reversed(pts[2:-1])]
        pts += right
    else:
        r = w / 2
        for i in range(1, 2 * n):
            t = math.pi - math.pi * i / (2 * n)
            pts.append((r * math.cos(t), spring + r * math.sin(t)))
    pts += [(w / 2, spring), (w / 2, 0.0)]
    return pts


def arch_top(w, spring, pointed=True):
    if not pointed:
        return spring + w / 2
    R = 0.8 * w
    cx = -w / 2 + R
    return spring + R * math.sin(math.acos(-cx / R))


def prism_xz(name, outline, y0, depth, material=None):
    """XZ düzlemindeki çokgeni y0'dan +Y yönünde depth kadar uzatır (duvara gömülü niş, kemer kesici...)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y0, z)) for x, z in outline]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    moved = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=(0, depth, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return C.mesh_object(name, bm, material, smooth=False)


def cut(target, cutter):
    """Boolean fark: target'tan cutter'ı oyar, cutter silinir."""
    m = target.modifiers.new("Oy", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.object = cutter
    try:
        m.solver = "EXACT"
    except Exception:
        pass
    C.apply_modifiers(target)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return target


def arch_ring(name, w_out, s_out, w_in, s_in, y0, depth, material, pointed=True):
    """Kemer çerçevesi (archivolt): dış kemer prizması eksi iç kemer prizması."""
    o = prism_xz(name, arch_outline(w_out, s_out, pointed), y0, depth, material)
    c = prism_xz(name + "_ic", arch_outline(w_in, s_in, pointed), y0 - 0.5, depth + 1.0)
    return cut(o, c)


def rect_ring(name, w, h, band, y0, depth, z0, material):
    """Dikdörtgen bordür: dört kenar kutusu (ön yüz y0, -Y'ye doğru depth kadar çıkıntı)."""
    yc = y0 - depth / 2
    parts = [C.box(name + "_a", (w, depth, band), (0, yc, z0 + band / 2), material),
             C.box(name + "_u", (w, depth, band), (0, yc, z0 + h - band / 2), material),
             C.box(name + "_s", (band, depth, h - 2 * band), (-w / 2 + band / 2, yc, z0 + h / 2), material),
             C.box(name + "_r", (band, depth, h - 2 * band), (w / 2 - band / 2, yc, z0 + h / 2), material)]
    return C.join(parts, name)


def polygon_prism(name, sides, r, z0, z1, loc, material, rot=0.0):
    o = C.cyl(name, r, z1 - z0, (loc[0], loc[1], (z0 + z1) / 2), material, verts=sides, smooth=False,
              rot=(0, 0, rot))
    return o


def polygon_pyramid(name, sides, r, z0, h, loc, material, rot=0.0):
    bpy.ops.mesh.primitive_cone_add(vertices=sides, radius1=r, radius2=0.0, depth=h, location=(loc[0], loc[1], z0 + h / 2),
                                    rotation=(0, 0, rot))
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(material)
    return o


def medallion(name, r, loc, M, petals=12, depth=0.28, crescent=False):
    """Yüksek kabartma madalyon (-Y'ye bakar): disk, iki sıra yaprak, göbek; istenirse hilal çerçeve."""
    x, y, z = loc
    parts = [C.cyl(name + "_disk", r, depth, (x, y - depth / 2, z), M["carve"], verts=40, rot=(math.pi / 2, 0, 0))]
    parts.append(C.cyl(name + "_kenar", r * 1.08, depth * 0.5, (x, y - depth * 0.25, z), M["stone"], verts=40,
                       rot=(math.pi / 2, 0, 0)))
    for ring, (rr, n, sc) in enumerate([(0.62, petals, 0.34), (0.32, petals // 2 + 2, 0.24)]):
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * ring) / n
            px, pz = x + math.cos(a) * r * rr, z + math.sin(a) * r * rr
            p = C.sphere(f"{name}_y{ring}_{k}", 1.0, (px, y - depth - 0.06 * (ring + 1), pz), M["carve"],
                         scale=(r * sc * 0.42, 0.11 + 0.05 * ring, r * sc), segs=10, rings=6)
            p.rotation_euler = (0, -a + math.pi / 2, 0)
            C.apply_transform(p, location=False)
            parts.append(p)
    parts.append(C.sphere(name + "_gobek", r * 0.16, (x, y - depth - 0.12, z), M["carve"], scale=(1, 0.8, 1), segs=16, rings=8))
    if crescent:
        bpy.ops.mesh.primitive_torus_add(major_radius=r * 1.32, minor_radius=r * 0.1, major_segments=36, minor_segments=8,
                                         location=(x, y - 0.12, z), rotation=(math.pi / 2, 0, 0))
        t = bpy.context.active_object
        t.name = name + "_hilal"
        t.data.materials.append(M["carve"])
        parts.append(t)
    return C.join(parts, name)


def muqarnas(name, w, z0, z1, y_back, M, tiers=5):
    """Mukarnas kavsara: nişin tepesinde, plânda yarım çember üzerinde kademe kademe sarkan küçük hücreler
    (her hücre bir kutu ve altında sarkıt), üst kademelere doğru daralır."""
    parts = []
    for k in range(tiers):
        t = k / tiers
        rr = (w / 2) * (1 - 0.82 * t)
        zc = z0 + (z1 - z0) * t
        n = 2 * (tiers - k) + 3
        cell = math.pi * rr / n
        for i in range(n):
            a = math.pi * (i + 0.5) / n                  # 0..π: nişin içinde yarım çember
            px, py = -math.cos(a) * rr, y_back - math.sin(a) * rr * 0.75
            hgt = (z1 - z0) / tiers
            b = C.box(f"{name}_{k}_{i}", (cell * 0.9, 0.22, hgt * 0.75), (px, py, zc + hgt * 0.62), M["carve"],
                      rot=(0, 0, -(a - math.pi / 2)))
            parts.append(b)
            s = C.cone(f"{name}_s{k}_{i}", cell * 0.35, 0.0, hgt * 0.35, (px, py, zc + hgt * 0.07), M["carve"], verts=4,
                       rot=(math.pi, 0, 0))
            parts.append(s)
    return C.join(parts, name)


def mirror_for_unity(root):
    """FBX'ten Unity'ye geçişte Blender'ın -X'i doğuya düşer: çizimde batı = -X kabul edildiği için bütün parçalar
    X'te aynalanır (normaller çevrilir). Böylece minare ve batı kapıları Unity'de gerçekten batıda kalır."""
    for o in root.children_recursive:
        if o.type != "MESH":
            continue
        o.data.transform(Matrix.Translation(o.location))
        o.location = (0, 0, 0)
        o.data.transform(Matrix.Scale(-1, 4, (1, 0, 0)))
        o.data.flip_normals()


def place(obj, rot_z, offset):
    """Yerel çizilen parçayı döndürüp (Z ekseni) yerine taşır (veriye uygular). Önce nesnenin konumu veriye
    katılır: dönüş nesnenin kendi merkezi değil, yerel çizimin sıfır noktası etrafında olsun."""
    obj.data.transform(Matrix.Translation(obj.location))
    obj.location = (0, 0, 0)
    obj.data.transform(Matrix.Translation(Vector(offset)) @ Matrix.Rotation(rot_z, 4, "Z"))
    return obj


# ---------------------------------------------------------------------------- taç kapılar (yerel: duvar yüzü y=0, kapı -Y'ye bakar)
def north_portal(M):
    """Kuzey taç kapısı: 11 x 15 m, duvardan 2 m çıkıntılı ve duvarın üstüne taşan; derin sivri kemerli niş."""
    W, H, P = 11.0, 15.2, 2.0
    parts = []
    block = C.box("KK_Govde", (W, P, H), (0, -P / 2 + 0.01, H / 2), M["stone"])
    niche_w, niche_s = 4.4, 7.2
    top = arch_top(niche_w, niche_s)
    cut(block, prism_xz("KK_Nis", arch_outline(niche_w, niche_s), -P - 0.5, P - 0.35 + 0.5))
    parts.append(block)
    # bordürler: dışta geniş oymalı bant, içte ince, kemer etrafında iki archivolt
    parts.append(rect_ring("KK_Bordur1", W - 0.2, H - 0.4, 0.62, -P, 0.14, 0.2, M["carve"]))
    parts.append(rect_ring("KK_Bordur2", W - 1.9, H - 2.0, 0.34, -P, 0.08, 0.6, M["carve"]))
    parts.append(arch_ring("KK_Kemer1", niche_w + 2.4, niche_s, niche_w + 1.2, niche_s, -P - 0.18, 0.2, M["carve"]))
    parts.append(arch_ring("KK_Kemer2", niche_w + 1.2, niche_s, niche_w + 0.3, niche_s, -P - 0.08, 0.1, M["stone"]))
    # gömme sütunlar (başlık ve kaideyle)
    for sx in (-1, 1):
        x = sx * (niche_w / 2 + 0.75)
        parts.append(C.cyl(f"KK_Sutun{sx}", 0.3, niche_s - 0.9, (x, -P - 0.22, 0.6 + (niche_s - 0.9) / 2), M["carve"], verts=20))
        parts.append(C.box(f"KK_Kaide{sx}", (0.85, 0.7, 0.6), (x, -P - 0.15, 0.3), M["stone"]))
        parts.append(C.box(f"KK_Baslik{sx}", (0.9, 0.75, 0.55), (x, -P - 0.17, niche_s - 0.02), M["carve"]))
    # yüksek kabartma madalyonlar (kemerin iki omzunda) ve tepede altıgen motif
    for sx in (-1, 1):
        parts.append(medallion(f"KK_Madalyon{sx}", 1.05, (sx * 3.7, -P - 0.15, top + 0.4), M, petals=14))
        parts.append(medallion(f"KK_KucukMadalyon{sx}", 0.5, (sx * 3.95, -P - 0.15, 3.0), M, petals=10, depth=0.18))
    hexa = C.cyl("KK_Altigen", 0.85, 0.3, (0, -P - 0.25, H - 1.55), M["carve"], verts=6, rot=(math.pi / 2, 0, 0), smooth=False)
    parts.append(hexa)
    parts.append(C.cyl("KK_AltigenIc", 0.5, 0.45, (0, -P - 0.3, H - 1.55), M["carve"], verts=6, rot=(math.pi / 2, 0, math.pi / 6),
                       smooth=False))
    # kitabe şeridi ve kapının taş çerçevesi, ahşap kapı
    parts.append(C.box("KK_Kitabe", (niche_w + 2.4, 0.18, 0.55), (0, -P - 0.1, top + 1.55), M["carve"]))
    parts.append(rect_ring("KK_KapiCerceve", 3.5, 5.3, 0.35, -0.35, 0.12, 0.0, M["carve"]))
    parts.append(C.box("KK_Kapi", (2.8, 0.14, 4.95), (0, -0.33, 2.47), M["door"]))
    parts.append(C.box("KK_Kapi_Orta", (0.06, 0.18, 4.9), (0, -0.4, 2.45), M["black"]))
    parts.append(C.box("KK_Alinlik", (3.0, 0.1, niche_s - 5.3), (0, -0.4, 5.3 + (niche_s - 5.3) / 2), M["carve"]))
    parts.append(muqarnas("KK_Mukarnas", niche_w - 0.1, niche_s, top - 0.05, -0.35, M))
    # tepe silmesi ve basamaklar
    parts.append(C.box("KK_Silme", (W + 0.3, P + 0.3, 0.35), (0, -P / 2, H + 0.17), M["stone"]))
    for k in range(3):
        parts.append(C.box(f"KK_Basamak{k}", (6.0 - k * 0.6, 0.45, 0.2), (0, -P - 0.9 + k * 0.45, 0.1 + k * 0.2 - 0.2), M["stone"]))
    return C.join(parts, "KuzeyTacKapi")


def west_portal(M):
    """Batı kapısı: dokuma gibi sık oyma kaplı dikdörtgen yüz, yuvarlak kemerli kapı, mukarnaslı kavsara,
    iki yanda duvara bağlanan çapraz duvarlar."""
    W, H, P = 7.4, 11.4, 1.4
    parts = []
    block = C.box("BK_Govde", (W, P, H), (0, -P / 2 + 0.01, H / 2), M["stone"])
    niche_w, niche_s = 2.9, 4.6
    top = arch_top(niche_w, niche_s, pointed=False)
    cut(block, prism_xz("BK_Nis", arch_outline(niche_w, niche_s, pointed=False), -P - 0.5, P - 0.3 + 0.5))
    parts.append(block)
    # yüzün tamamı oymalı pano (ortası açık) + çerçeveler
    pano = C.box("BK_Pano", (W - 0.8, 0.1, H - 1.2), (0, -P - 0.05, H / 2 + 0.2), M["carve"])
    cut(pano, prism_xz("BK_PanoNis", arch_outline(niche_w + 0.9, niche_s, pointed=False), -P - 0.5, 1.2))
    parts.append(pano)
    parts.append(rect_ring("BK_Bordur", W - 0.1, H - 0.3, 0.42, -P, 0.16, 0.1, M["carve"]))
    parts.append(arch_ring("BK_Kemer", niche_w + 0.9, niche_s, niche_w + 0.1, niche_s, -P - 0.16, 0.2, M["carve"], pointed=False))
    parts.append(muqarnas("BK_Mukarnas", niche_w - 0.1, niche_s, top - 0.05, -0.3, M, tiers=5))
    parts.append(C.box("BK_Kapi", (1.9, 0.12, 3.6), (0, -0.28, 1.8), M["door"]))
    parts.append(C.box("BK_Alinlik", (2.2, 0.1, niche_s - 3.6), (0, -0.32, 3.6 + (niche_s - 3.6) / 2), M["carve"]))
    for sx in (-1, 1):
        # çapraz duvarlar (köşelerde kuş figürlü mukarnas nişleri yerine sade kademeli konsollar)
        d = C.box(f"BK_Capraz{sx}", (1.6, 0.9, H - 2.0), (sx * (W / 2 + 0.45), -0.42, (H - 2.0) / 2), M["stone"],
                  rot=(0, 0, sx * math.radians(38)))
        parts.append(d)
        parts.append(medallion(f"BK_Madalyon{sx}", 0.42, (sx * (niche_w / 2 + 1.05), -P - 0.1, top + 1.4), M, petals=10, depth=0.16))
    parts.append(C.box("BK_Silme", (W + 0.2, P + 0.2, 0.3), (0, -P / 2, H + 0.15), M["stone"]))
    return C.join(parts, "BatiKapi")


def shah_portal(M):
    """Doğuda Şah Mahfili kapısı: küçük, sivri kemerli, sade bordürlü."""
    W, H, P = 5.2, 8.6, 1.0
    block = C.box("SK_Govde", (W, P, H), (0, -P / 2 + 0.01, H / 2), M["stone"])
    cut(block, prism_xz("SK_Nis", arch_outline(2.2, 4.4), -P - 0.5, P - 0.25 + 0.5))
    parts = [block,
             rect_ring("SK_Bordur", W - 0.2, H - 0.3, 0.38, -P, 0.12, 0.1, M["carve"]),
             arch_ring("SK_Kemer", 3.0, 4.4, 2.3, 4.4, -P - 0.12, 0.15, M["carve"]),
             C.box("SK_Kapi", (1.6, 0.12, 3.2), (0, -0.24, 1.6), M["door"]),
             muqarnas("SK_Mukarnas", 2.1, 4.4, arch_top(2.2, 4.4) - 0.05, -0.25, M, tiers=4),
             C.box("SK_Silme", (W + 0.2, P + 0.2, 0.28), (0, -P / 2, H + 0.14), M["stone"])]
    return C.join(parts, "SahKapisi")


def hospital_portal(M):
    """Darüşşifa taç kapısı: iç içe iki sivri kemer, ortada kapı, kapının üstünde dikdörtgen pencere,
    iki yanda hilal çerçeveli büyük madalyonlar."""
    W, H, P = 9.6, 14.0, 1.6
    parts = []
    block = C.box("DK_Govde", (W, P, H), (0, -P / 2 + 0.01, H / 2), M["stone"])
    niche_w, niche_s = 4.4, 7.4
    top = arch_top(niche_w, niche_s)
    cut(block, prism_xz("DK_Nis", arch_outline(niche_w, niche_s), -P - 0.5, P - 0.35 + 0.5))
    parts.append(block)
    parts.append(arch_ring("DK_DisKemer", niche_w + 2.8, niche_s + 0.4, niche_w + 1.8, niche_s + 0.4, -P - 0.2, 0.22, M["carve"]))
    parts.append(arch_ring("DK_IcKemer", niche_w + 1.2, niche_s, niche_w + 0.3, niche_s, -P - 0.12, 0.14, M["carve"]))
    parts.append(rect_ring("DK_Bordur", W - 0.1, H - 0.3, 0.5, -P, 0.14, 0.1, M["carve"]))
    for sx in (-1, 1):
        parts.append(medallion(f"DK_Madalyon{sx}", 1.0, (sx * 3.35, -P - 0.15, top + 1.0), M, petals=16, crescent=True))
    parts.append(C.box("DK_Kapi", (2.2, 0.12, 3.7), (0, -0.38, 1.85), M["door"]))
    parts.append(rect_ring("DK_KapiCerceve", 2.8, 4.1, 0.3, -0.36, 0.1, 0.0, M["carve"]))
    parts.append(C.box("DK_Pencere", (1.5, 0.1, 1.7), (0, -0.4, 5.3), M["glass"]))
    parts.append(rect_ring("DK_PencereCerceve", 2.0, 2.2, 0.25, -0.38, 0.1, 4.2, M["carve"]))
    for k in range(5):                                  # pencere demirleri
        parts.append(C.box(f"DK_Demir{k}", (0.03, 0.05, 1.7), (-0.6 + k * 0.3, -0.47, 5.3), M["metal"]))
    parts.append(muqarnas("DK_Mukarnas", niche_w - 0.1, niche_s, top - 0.05, -0.35, M, tiers=4))
    parts.append(C.box("DK_Silme", (W + 0.3, P + 0.3, 0.32), (0, -P / 2, H + 0.16), M["stone"]))
    return C.join(parts, "DarussifaTacKapisi")


def window(name, w, h, z, M, depth=0.5, pointed=True):
    """Duvara gömülü sivri kemerli küçük pencere (yerel: duvar yüzü y=0): koyu cam, demir parmaklık, oymalı çerçeve."""
    parts = [arch_ring(name + "_c", w + 0.5, h - w / 2, w, h - w / 2, -0.12, 0.14, M["carve"], pointed)]
    g = prism_xz(name + "_cam", arch_outline(w, h - w / 2, pointed), -0.02, 0.05, M["glass"])
    parts.append(g)
    for k in range(3):
        parts.append(C.box(f"{name}_d{k}", (0.03, 0.04, h * 0.9), (-w / 3 + k * w / 3, -0.06, h * 0.45), M["metal"]))
    o = C.join(parts, name)
    o.data.transform(Matrix.Translation(o.location + Vector((0, 0, z))))
    o.location = (0, 0, 0)
    return o


# ---------------------------------------------------------------------------- külliye
def ulu_cami():
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_UluCami")
    WX = 16.0                                   # yarı genişlik (doğu-batı)
    YN, YQ, YS = -32.0, 8.0, 32.0               # kuzey duvarı, kıble duvarı (cami/darüşşifa sınırı), güney duvarı
    HM, HD = 10.6, 12.6                         # cami ve darüşşifa beden duvarı yüksekliği
    parts = []
    # temel ve teras (eğimli arazide boşluk kalmasın diye 6 m aşağı iner)
    parts.append(C.box("Temel", (2 * WX + 4.0, YS - YN + 6.0, 6.4), (0, (YN + YS) / 2 - 1.0, -2.8), M["stone"]))
    parts.append(C.box("Cami", (2 * WX, YQ - YN, HM), (0, (YN + YQ) / 2, HM / 2 + 0.4), M["stone"]))
    parts.append(C.box("Darussifa", (2 * WX, YS - YQ, HD), (0, (YQ + YS) / 2, HD / 2 + 0.4), M["stone"]))
    # dam: toprak örtü, taş parapet ve saçak silmesi
    for nm, y0, y1, h in (("Cami", YN, YQ, HM), ("Darussifa", YQ, YS, HD)):
        z = h + 0.4
        parts.append(C.box(f"{nm}_Dam", (2 * WX - 1.2, y1 - y0 - 1.2, 0.25), (0, (y0 + y1) / 2, z + 0.05), M["earth"]))
        for side in (-1, 1):
            parts.append(C.box(f"{nm}_ParapetX{side}", (0.6, y1 - y0, 0.7), (side * (WX - 0.3), (y0 + y1) / 2, z + 0.35), M["stone"]))
            parts.append(C.box(f"{nm}_ParapetY{side}", (2 * WX - 1.24, 0.6, 0.7), (0, (y0 if side < 0 else y1) - side * 0.3, z + 0.35),
                               M["stone"]))
        parts.append(C.box(f"{nm}_Silme", (2 * WX + 0.36, y1 - y0 + 0.36, 0.3), (0, (y0 + y1) / 2, z - 0.35), M["stone"]))
        # saçak altında taş konsol dizisi (her 0,9 m'de bir)
        for k in range(int(2 * WX / 0.9)):
            x = -WX + 0.45 + k * 0.9
            for yy, sgn in ((y0, -1), (y1, 1)):
                if nm == "Cami" and sgn > 0:
                    continue                               # kıble duvarı darüşşifaya bitişik
                parts.append(C.box(f"{nm}_KonsolX{k}{sgn}", (0.32, 0.3, 0.34), (x, yy + sgn * 0.15, z - 0.67), M["stone"]))
        for k in range(int((y1 - y0) / 0.9)):
            y = y0 + 0.45 + k * 0.9
            for side in (-1, 1):
                parts.append(C.box(f"{nm}_KonsolY{k}{side}", (0.3, 0.32, 0.34), (side * (WX + 0.15), y, z - 0.67), M["stone"]))
    # su basman silmesi (duvarın dibinde çıkıntılı taş kuşak)
    parts.append(C.box("Subasman", (2 * WX + 0.5, YS - YN + 0.5, 0.9), (0, (YN + YS) / 2, 0.85), M["stone"]))
    # payandalar (sahın ve bölüm aksında) ve çörtenler
    for x in (-9.6, -3.2, 3.2, 9.6):
        if abs(x) > 2:
            parts.append(C.box(f"Payanda_K{x}", (1.2, 1.0, HM - 1.6), (x, YN - 0.5, (HM - 1.6) / 2 + 0.4), M["stone"]))
    for y in (-24.0, -16.0, -8.0, 0.0):
        for side in (-1, 1):
            if side < 0 and -26.5 < y < -17.5:
                continue                               # batı kapısının yeri
            parts.append(C.box(f"Payanda_Y{side}{y}", (1.0, 1.2, HM - 1.6), (side * (WX + 0.5), y, (HM - 1.6) / 2 + 0.4), M["stone"]))
    for x in (-12.8, -6.4, 6.4, 12.8):
        parts.append(C.box(f"Corten_K{x}", (0.28, 1.1, 0.26), (x, YN - 0.5, HM + 0.1), M["stone"]))
    for y in (-26.0, -14.0, -2.0, 14.0, 26.0):
        for side in (-1, 1):
            parts.append(C.box(f"Corten_Y{side}{y}", (1.1, 0.28, 0.26), (side * (WX + 0.5), y, (HM if y < YQ else HD) + 0.1), M["stone"]))
    body = C.join(parts, "Govde")
    body.parent = root

    # taç kapılar
    nk = north_portal(M)
    place(nk, 0.0, (0, YN, 0.4))
    nk.parent = root
    bk = west_portal(M)
    place(bk, -math.pi / 2, (-WX, -22.0, 0.4))      # batı duvarı: kapı -X'e bakar
    bk.parent = root
    sk = shah_portal(M)
    place(sk, math.pi / 2, (WX, -2.0, 0.4))          # doğu duvarı
    sk.parent = root
    dk = hospital_portal(M)
    place(dk, -math.pi / 2, (-WX, 20.0, 0.4))       # darüşşifanın batı cephesi
    dk.parent = root

    # pencereler: kuzeyde iki sıra, yanlarda bölüm aksında; darüşşifada iki kat
    wins = []
    for x in (-12.8, -6.4, 6.4, 12.8):
        w = window(f"PK{x}", 1.1, 2.4, 3.2, M)
        place(w, 0.0, (x, YN, 0.4))
        wins.append(w)
        w2 = window(f"PK2{x}", 0.8, 1.6, 7.4, M)
        place(w2, 0.0, (x, YN, 0.4))
        wins.append(w2)
    for y in (-28.0, -12.0, -4.0, 4.0):
        for side in (-1, 1):
            if side < 0 and y == -28.0:
                continue
            w = window(f"PY{side}{y}", 1.0, 2.2, 3.6, M)
            place(w, side * math.pi / 2, (side * WX, y, 0.4))
            wins.append(w)
    for y in (12.0, 28.0):
        for side in (-1, 1):
            for fl, z in enumerate((2.6, 7.6)):
                if side < 0 and 14 < y < 26:
                    continue
                w = window(f"PD{side}{y}{fl}", 0.9, 1.9, z, M)
                place(w, side * math.pi / 2, (side * WX, y, 0.4))
                wins.append(w)
    for x in (-10.0, -3.5, 3.5, 10.0):
        for fl, z in enumerate((2.6, 7.6)):
            w = window(f"PG{x}{fl}", 0.9, 1.9, z, M)
            place(w, math.pi, (x, YS, 0.4))
            wins.append(w)
    C.join(wins, "Pencereler").parent = root

    roofs = []
    # mihrap önü kubbesinin sekizgen kasnağı ve külahı (külliyenin en yüksek noktası, ~25 m)
    mx, my, zr = 0.0, YQ - 4.4, HM + 0.4
    roofs.append(polygon_prism("Mihrap_Kasnak", 8, 4.3, zr, zr + 5.0, (mx, my), M["stone"], rot=math.pi / 8))
    roofs.append(polygon_prism("Mihrap_KasnakSilme", 8, 4.62, zr + 5.0, zr + 5.45, (mx, my), M["stone"], rot=math.pi / 8))
    roofs.append(polygon_pyramid("Mihrap_Kulah", 8, 4.75, zr + 5.45, 7.4, (mx, my), M["stone"], rot=math.pi / 8))
    for k in range(8):
        a = math.pi / 8 + k * math.pi / 4 + math.pi / 8
        if k % 2 == 0:
            w = window(f"MK_P{k}", 0.75, 1.7, zr + 1.4, M, pointed=True)
            place(w, a + math.pi / 2, (mx + math.cos(a) * 4.0, my + math.sin(a) * 4.0, 0))
            roofs.append(w)
    roofs.append(C.cyl("Mihrap_Alem", 0.06, 1.4, (mx, my, zr + 12.85 + 0.7), M["metal"], verts=8))
    roofs.append(C.sphere("Mihrap_AlemTop", 0.18, (mx, my, zr + 13.2), M["metal"], segs=12, rings=8))
    # caminin orta feneri ve darüşşifa feneri
    for nm, x, y, z, r in (("CamiFener", 0.0, -12.0, HM + 0.4, 2.3), ("DarussifaFener", 0.0, 20.0, HD + 0.4, 2.8)):
        roofs.append(polygon_prism(nm + "_Kasnak", 8, r, z, z + 2.2, (x, y), M["stone"], rot=math.pi / 8))
        roofs.append(polygon_prism(nm + "_Silme", 8, r + 0.25, z + 2.2, z + 2.5, (x, y), M["stone"], rot=math.pi / 8))
        roofs.append(polygon_pyramid(nm + "_Kulah", 8, r + 0.32, z + 2.5, r * 0.9, (x, y), M["lead"], rot=math.pi / 8))
        for k in range(8):
            a = math.pi / 8 + k * math.pi / 4 + math.pi / 8
            roofs.append(C.box(f"{nm}_Pen{k}", (0.6, 0.12, 1.1), (x + math.cos(a) * (r - 0.02), y + math.sin(a) * (r - 0.02), z + 1.2),
                               M["glass"], rot=(0, 0, a + math.pi / 2)))
    # türbenin altıgen külahı (darüşşifada, kıble duvarı dibinde)
    tx, ty, tz = 9.0, YQ + 4.0, HD + 0.4
    roofs.append(polygon_prism("Turbe_Kasnak", 6, 2.7, tz, tz + 3.0, (tx, ty), M["stone"]))
    roofs.append(polygon_prism("Turbe_Silme", 6, 2.95, tz + 3.0, tz + 3.3, (tx, ty), M["stone"]))
    roofs.append(polygon_pyramid("Turbe_Kulah", 6, 3.05, tz + 3.3, 4.1, (tx, ty), M["stone"]))
    C.join(roofs, "Ortu").parent = root

    # minare: kuzeybatı köşesinde silindir payanda üstünde (1523, Kanuni dönemi)
    mx, my = -WX - 1.2, YN - 1.0
    mp = [C.cyl("Minare_Payanda", 2.7, 11.2, (mx, my, 0.4 + 5.6 - 0.6), M["stone"], verts=40)]
    mp.append(C.cyl("Minare_PayandaSilme", 2.9, 0.4, (mx, my, 11.0), M["stone"], verts=40))
    mp.append(C.cyl("Minare_Kursu", 1.55, 1.6, (mx, my, 12.0), M["stone"], verts=32))
    mp.append(C.cyl("Minare_Govde", 1.3, 8.6, (mx, my, 12.8 + 4.3), M["stone"], verts=32))
    for z in (14.6, 17.4):
        mp.append(C.cyl(f"Minare_Bilezik{z}", 1.38, 0.22, (mx, my, z), M["carve"], verts=32))
    mp.append(C.cone("Minare_SerefeAlti", 1.3, 1.95, 0.9, (mx, my, 21.85), M["carve"], verts=32))
    mp.append(C.cyl("Minare_Serefe", 1.95, 0.18, (mx, my, 22.39), M["stone"], verts=32))
    korkuluk = C.cyl("Minare_Korkuluk", 1.92, 0.95, (mx, my, 22.95), M["carve"], verts=32)
    cut(korkuluk, C.cyl("Minare_KorkulukIc", 1.75, 1.2, (mx, my, 23.0), None, verts=32))
    mp.append(korkuluk)
    mp.append(C.cyl("Minare_Petek", 1.0, 3.0, (mx, my, 23.98), M["stone"], verts=28))
    mp.append(C.cone("Minare_Kulah", 1.15, 0.0, 3.4, (mx, my, 27.18), M["lead"], verts=28))
    mp.append(C.cyl("Minare_Alem", 0.05, 1.2, (mx, my, 29.3), M["metal"], verts=8))
    mp.append(C.sphere("Minare_AlemTop", 0.14, (mx, my, 29.5), M["metal"], segs=12, rings=8))
    C.join(mp, "Minare").parent = root
    mirror_for_unity(root)
    C.stats(root)
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_UluCami.fbx"), root)
    if BLEND:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)


# ---------------------------------------------------------------------------- kale
def crenels(name, length, thick, z, M, rnd, broken=0.25, width=0.9, gap=0.7, h=1.2):
    """Mazgallı siper dişleri (bir kısmı yıkık)."""
    parts = []
    x = -length / 2 + gap
    k = 0
    while x + width < length / 2:
        if rnd.random() > broken:
            hh = h * (0.55 + 0.45 * rnd.random()) if rnd.random() < 0.3 else h
            parts.append(C.box(f"{name}_{k}", (width, thick, hh), (x + width / 2, 0, z + hh / 2), M["castle"]))
        x += width + gap
        k += 1
    return parts


def castle_pieces():
    rnd = random.Random(1228)
    # yuvarlak burç: aşağı doğru genişleyen gövde, yıkık siper
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_KaleKule")
    parts = [C.cone("Kule_Etek", 5.2, 4.3, 4.0, (0, 0, -1.0), M["castle"], verts=28),
             C.cyl("Kule_Govde", 4.3, 9.0, (0, 0, 5.5), M["castle"], verts=28),
             C.cyl("Kule_Silme", 4.5, 0.4, (0, 0, 10.2), M["castle"], verts=28)]
    for k in range(14):
        if rnd.random() < 0.3:
            continue
        a = 2 * math.pi * k / 14
        hh = 1.3 if rnd.random() > 0.3 else 0.7
        parts.append(C.box(f"Kule_Dis{k}", (1.2, 0.8, hh), (math.cos(a) * 4.05, math.sin(a) * 4.05, 10.4 + hh / 2), M["castle"],
                           rot=(0, 0, a + math.pi / 2)))
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.4
        parts.append(C.box(f"Kule_Mazgal{k}", (0.25, 0.4, 1.4), (math.cos(a) * 4.31, math.sin(a) * 4.31, 6.0 + k), M["black"],
                           rot=(0, 0, a + math.pi / 2)))
    C.join(parts, "Kule").parent = root
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_KaleKule.fbx"), root)

    # kare burç
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_KaleBurc")
    parts = [C.box("Burc_Etek", (8.6, 8.6, 4.0), (0, 0, -1.0), M["castle"]),
             C.box("Burc_Govde", (7.4, 7.4, 11.0), (0, 0, 6.5), M["castle"]),
             C.box("Burc_Silme", (7.8, 7.8, 0.4), (0, 0, 12.2), M["castle"])]
    for side in range(4):
        rot = side * math.pi / 2
        for c in crenels(f"Burc_Dis{side}", 7.4, 0.7, 12.4, M, rnd):
            place(c, rot, (math.cos(rot - math.pi / 2) * 3.35, math.sin(rot - math.pi / 2) * 3.35, 0))
            parts.append(c)
        parts.append(place(C.box(f"Burc_Mazgal{side}", (0.3, 0.2, 1.5), (0, -3.72, 7.5), M["black"]), rot, (0, 0, 0)))
    C.join(parts, "Burc").parent = root
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_KaleBurc.fbx"), root)

    # sur parçası: 12 m, kalın, dişleri yer yer yıkık; tabanı aşağı uzar (eğimde boşluk kalmasın)
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_KaleSur")
    parts = [C.box("Sur_Govde", (12.4, 2.4, 11.0), (0, 0, 2.5), M["castle"]),
             C.box("Sur_Yuruyus", (12.4, 0.5, 1.0), (0, 1.0, 8.5), M["castle"])]
    parts += [place(c, 0.0, (0, -0.85, 0)) for c in crenels("Sur_Dis", 12.4, 0.7, 8.0, M, rnd, broken=0.3)]
    C.join(parts, "Sur").parent = root
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_KaleSur.fbx"), root)


# ---------------------------------------------------------------------------- Divriği evleri
def divrigi_house(idx, rnd):
    """Geleneksel Divriği evi: taş zemin kat, üstte ahşap karkas sıvalı kat ve ahşap konsollu cumba,
    çok pencereli cephe, geniş saçaklı kırma kiremit çatı (ya da toprak dam)."""
    C.reset_scene()
    C._materials.clear()
    M = mats()
    plasters = [("MAT_Plaster_A", (0.72, 0.66, 0.55)), ("MAT_Plaster_B", (0.78, 0.76, 0.72)),
                ("MAT_Plaster_C", (0.70, 0.55, 0.40))]
    pm = C.mat(plasters[idx % 3][0], plasters[idx % 3][1], rough=0.88)
    root = C.empty(f"SuruIHA_Yapi_DivrigiEv_{idx}")
    w, d = rnd.uniform(9, 12), rnd.uniform(7.5, 9.5)
    g, u = 3.0, 3.0                           # zemin ve üst kat yüksekliği
    parts = [C.box("Temel", (w + 0.4, d + 0.4, 3.0), (0, 0, -1.2), M["castle"]),
             C.box("ZeminKat", (w, d, g), (0, 0, g / 2 + 0.3), M["castle"]),
             C.box("UstKat", (w + 0.3, d + 0.3, u), (0, 0, g + 0.3 + u / 2), pm),
             C.box("KatSilmesi", (w + 0.5, d + 0.5, 0.18), (0, 0, g + 0.3), M["wood"])]
    # ahşap karkas izleri (dikmeler)
    for k in range(int(w // 1.6) + 1):
        x = -w / 2 - 0.15 + k * (w + 0.3) / int(w // 1.6)
        parts.append(C.box(f"Dikme{k}", (0.12, d + 0.36, u), (x, 0, g + 0.3 + u / 2), M["wood"]))
    # cumba: ön cephede, konsollar üstünde
    cw = rnd.uniform(3.2, 4.4)
    cx = rnd.uniform(-w / 2 + cw / 2 + 0.6, w / 2 - cw / 2 - 0.6)
    parts.append(C.box("Cumba", (cw, 1.0, u - 0.2), (cx, -d / 2 - 0.65, g + 0.3 + u / 2), pm))
    for k in range(3):
        parts.append(C.box(f"Konsol{k}", (0.14, 0.9, 0.5), (cx - cw / 2 + 0.3 + k * (cw - 0.6) / 2, -d / 2 - 0.5, g + 0.05), M["wood"],
                           rot=(math.radians(-30), 0, 0)))
    nwin = max(3, int(cw // 0.9))
    for k in range(nwin):
        x = cx - cw / 2 + (k + 0.5) * cw / nwin
        parts.append(C.box(f"CumbaPen{k}", (cw / nwin - 0.25, 0.06, 1.35), (x, -d / 2 - 1.16, g + 0.3 + 1.55), M["glass"]))
        parts.append(C.box(f"CumbaKasa{k}", (cw / nwin - 0.1, 0.05, 1.5), (x, -d / 2 - 1.14, g + 0.3 + 1.55), M["frame"]))
    for side in (-1, 1):
        for k in range(int(w // 2.4)):
            x = -w / 2 + (k + 0.5) * w / int(w // 2.4)
            if side < 0 and abs(x - cx) < cw / 2 + 0.3:
                continue
            parts.append(C.box(f"Pen{side}{k}", (0.8, 0.06, 1.2), (x, side * (d / 2 + 0.16), g + 0.3 + 1.6), M["glass"]))
            parts.append(C.box(f"Kasa{side}{k}", (0.95, 0.05, 1.35), (x, side * (d / 2 + 0.15), g + 0.3 + 1.6), M["frame"]))
            if rnd.random() < 0.5:
                parts.append(C.box(f"ZPen{side}{k}", (0.6, 0.06, 0.8), (x, side * (d / 2 + 0.01), 1.9), M["black"]))
    parts.append(C.box("Kapi", (1.3, 0.12, 2.3), (-cx * 0.5, -d / 2 - 0.02, 1.45), M["door"]))
    parts.append(C.box("KapiSundurma", (2.0, 1.1, 0.1), (-cx * 0.5, -d / 2 - 0.5, 2.9), M["wood"], rot=(math.radians(-10), 0, 0)))
    body = C.join(parts, "Ev")
    body.parent = root
    top = g + 0.3 + u
    if idx == 3:
        # toprak damlı ev: düz dam, ahşap saçak kirişleri
        C.box("Dam", (w + 0.9, d + 0.9, 0.35), (0, 0, top + 0.17), M["earth"], root)
        C.box("DamSacak", (w + 1.0, d + 1.0, 0.12), (0, 0, top + 0.02), M["wood"], root)
    else:
        bm = bmesh.new()
        W, D, oh = (w + 0.3) / 2 + 0.8, (d + 0.3) / 2 + 0.8, 0.0
        h = min(w, d) * 0.22
        ridge = max(0.0, W - D)
        cs = [Vector((-W, -D, top)), Vector((W, -D, top)), Vector((W, D, top)), Vector((-W, D, top))]
        v = [bm.verts.new(p) for p in cs]
        a, b = bm.verts.new((-ridge, 0, top + h)), bm.verts.new((ridge, 0, top + h))
        bm.faces.new((v[0], v[1], b, a))
        bm.faces.new((v[1], v[2], b))
        bm.faces.new((v[2], v[3], a, b))
        bm.faces.new((v[3], v[0], a))
        bm.faces.new(list(reversed(v)))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        C.mesh_object("Cati", bm, M["roof"], root, smooth=False)
        C.box("Baca", (0.5, 0.5, 1.4), (w * 0.28, d * 0.12, top + h * 0.6 + 0.4), pm, root)
    C.export_fbx(os.path.join(OUT, f"SuruIHA_Yapi_DivrigiEv_{idx}.fbx"), root)


if __name__ == "__main__":
    only = ARGS[2:] if len(ARGS) > 2 else []
    if not only or "cami" in only:
        ulu_cami()
    if not only or "kale" in only:
        castle_pieces()
    if not only or "ev" in only:
        rnd = random.Random(1229)
        for i in range(4):
            divrigi_house(i, rnd)
