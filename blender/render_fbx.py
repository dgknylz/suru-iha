"""Bir veya birkaç FBX'i içe aktarıp yan yana dizer ve önizleme çeker.

    blender -b --factory-startup -P blender/render_fbx.py -- cikti.png mesafe yukseklik aci hedef_z a.fbx [b.fbx ...]
"""
import os
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
out, rest, files = args[0], args[1:5], args[5:]
bpy.ops.wm.read_factory_settings(use_empty=True)
x = 0.0
for i, f in enumerate(files):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=f)
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None]
    for r in roots:
        r.location.x += (i - (len(files) - 1) / 2) * float(os.environ.get("SPACING", "12"))
    # Uzak LOD'ları gizle
    for o in new:
        if "_LOD1" in o.name or "_LOD2" in o.name:
            o.hide_render = True
# Önizlemede dokuları bağla (Unity'deki eşlemenin aynısı)
TEX = os.environ.get("TEXDIR")
TEXMAP = {"MAT_Needles": "Tex_CamIgne", "MAT_Leaves": "Tex_MeseYaprak",
          "MAT_BarkPine": "Tex_KabukCam", "MAT_BarkOak": "Tex_KabukMese", "MAT_Rock": "Ter_Kaya_Renk"}
if TEX:
    for m in bpy.data.materials:
        key = next((k for k in TEXMAP if m.name.startswith(k)), None)
        if key is None:
            continue
        m.use_nodes = True
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        img = nt.nodes.new("ShaderNodeTexImage")
        img.image = bpy.data.images.load(os.path.join(TEX, TEXMAP[key] + ".png"))
        nt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
        if key in ("MAT_Needles", "MAT_Leaves"):
            nt.links.new(img.outputs["Alpha"], bsdf.inputs["Alpha"])
sys.argv = [sys.argv[0], "--", out] + rest
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_preview.py"), encoding="utf-8").read())
