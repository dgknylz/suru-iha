"""Blender model betikleri için ortak yardımcılar (bpy).

Tüm ölçüler metre. Blender'da Z yukarı; modellerin önü -Y yönüne bakar.
FBX, Unity'de önü +Z, yukarısı +Y olacak şekilde dışa aktarılır.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


_materials = {}


def principled(m):
    """Malzemenin Principled BSDF düğümünü döndürür, yoksa kurar (Blender sürümünden bağımsız)."""
    if hasattr(m, "use_nodes"):
        try:
            m.use_nodes = True
        except Exception:
            pass
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    if not out.inputs["Surface"].is_linked:
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf


def mat(name, color, rough=0.5, metal=0.0, emission=None, strength=0.0, alpha=1.0):
    """Principled BSDF malzemesi. Unity tarafında aynı isimle HDRP malzemesine eşlenir."""
    if name in _materials:
        return _materials[name]
    m = bpy.data.materials.new(name)
    bsdf = principled(m)
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*color, alpha)
    _materials[name] = m
    return m


def _finish(obj, name, material, parent, smooth):
    obj.name = name
    obj.data.name = name
    if material is not None:
        obj.data.materials.clear()
        obj.data.materials.append(material)
    if parent is not None:
        obj.parent = parent
    if smooth:
        shade_smooth(obj)
    return obj


def shade_smooth(obj, angle=35.0):
    for p in obj.data.polygons:
        p.use_smooth = True
    # Keskin kenarları korumak için "Smooth by Angle" modifier'ı yerine kenar işaretleme
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    lim = math.radians(angle)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0) > lim:
            e.smooth = False
    bm.to_mesh(obj.data)
    bm.free()


def box(name, size, loc, material=None, parent=None, bevel=0.0, segments=3, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = size
    apply_transform(o, location=False, rotation=False)
    if bevel > 0:
        add_bevel(o, bevel, segments)
    return _finish(o, name, material, parent, smooth=bevel > 0)


def cyl(name, r, depth, loc, material=None, parent=None, verts=32, rot=(0, 0, 0), bevel=0.0, segments=2, smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    if bevel > 0:
        add_bevel(o, bevel, segments)
    return _finish(o, name, material, parent, smooth)


def cone(name, r1, r2, depth, loc, material=None, parent=None, verts=32, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=depth, location=loc, rotation=rot)
    return _finish(bpy.context.active_object, name, material, parent, True)


def sphere(name, r, loc, material=None, parent=None, scale=(1, 1, 1), segs=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=rings, radius=r, location=loc)
    o = bpy.context.active_object
    o.scale = scale
    apply_transform(o, location=False, rotation=False)
    return _finish(o, name, material, parent, True)


def tube_between(name, a, b, r, material=None, parent=None, verts=16):
    """a ve b noktaları arasında silindir (boru)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d.length, location=(a + b) / 2)
    o = bpy.context.active_object
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return _finish(o, name, material, parent, True)


def empty(name, loc=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.empty_display_size = 0.1
    if parent is not None:
        o.parent = parent
    return o


def add_bevel(o, width, segments=3):
    m = o.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.harden_normals = False
    apply_modifiers(o)


def apply_modifiers(o):
    select_only(o)
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def select_only(o):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def apply_transform(o, location=True, rotation=True, scale=True):
    select_only(o)
    bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)


def join(objs, name):
    """Aynı malzemeyi paylaşmayan parçalar da birleşebilir (malzeme yuvaları korunur)."""
    objs = [o for o in objs if o is not None]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = name
    o.data.name = name
    return o


def mesh_object(name, bm, material=None, parent=None, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    return _finish(o, name, material, parent, smooth)


def mirror_x(o, name):
    """Nesnenin X'e göre aynalanmış kopyası."""
    c = o.copy()
    c.data = o.data.copy()
    bpy.context.collection.objects.link(c)
    c.name = name
    c.data.name = name
    c.data.transform(Matrix.Scale(-1, 4, (1, 0, 0)))
    c.data.flip_normals()
    c.location.x = -o.location.x
    return c


def export_fbx(path, root):
    # Mesh'lerin dönüş/ölçeğini veriye uygula: Unity'de tüm parçalar sıfır dönüşle gelsin
    for o in root.children_recursive:
        if o.type == "MESH" and (o.rotation_mode != "XYZ" or any(abs(a) > 1e-6 for a in o.rotation_euler)
                                 or o.rotation_mode == "QUATERNION" or any(abs(s - 1) > 1e-6 for s in o.scale)):
            o.data.transform(o.matrix_basis.to_3x3().to_4x4())
            o.rotation_mode = "XYZ"
            o.rotation_euler = (0, 0, 0)
            o.rotation_quaternion = (1, 0, 0, 0)
            o.scale = (1, 1, 1)
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"EMPTY", "MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=True,
        mesh_smooth_type="OFF",          # yalnız normaller (özel yaprak normalleri korunur)
        use_mesh_modifiers=True,
        add_leaf_bones=False,
        path_mode="AUTO",
    )
    print("FBX yazıldı:", path)


def stats(root):
    objs = [root] + list(root.children_recursive)
    tris = 0
    for o in objs:
        if o.type == "MESH":
            o.data.calc_loop_triangles()
            tris += len(o.data.loop_triangles)
    print(f"{root.name}: {len(objs)} nesne, {tris} üçgen")
