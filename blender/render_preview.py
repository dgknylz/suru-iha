"""Bir .blend modelinin stüdyo önizlemesini çeker (kalite kontrol için).

    blender -b model.blend -P blender/render_preview.py -- cikti.png [mesafe] [yükseklik] [açı] [hedef_z]
"""
import math
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
out = args[0]
dist = float(args[1]) if len(args) > 1 else 1.4
height = float(args[2]) if len(args) > 2 else 0.5
angle = math.radians(float(args[3])) if len(args) > 3 else math.radians(-35)
target_z = float(args[4]) if len(args) > 4 else 0.0

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 96
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 1280, 800
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"

# Gökyüzü benzeri dünya ışığı
world = bpy.data.worlds.new("Studyo")
scene.world = world
world.use_nodes = True
nodes = world.node_tree.nodes
bg = nodes.get("Background") or nodes.new("ShaderNodeBackground")
wout = nodes.get("World Output") or nodes.new("ShaderNodeOutputWorld")
world.node_tree.links.new(bg.outputs["Background"], wout.inputs["Surface"])
bg.inputs["Color"].default_value = (0.55, 0.62, 0.72, 1)
bg.inputs["Strength"].default_value = 0.8

# Zemin
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.215 if target_z == 0 else 0))
ground = bpy.context.active_object
gm = bpy.data.materials.new("Zemin")
gm.use_nodes = True
zb = next((n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) or gm.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
zo = next((n for n in gm.node_tree.nodes if n.type == "OUTPUT_MATERIAL"), None) or gm.node_tree.nodes.new("ShaderNodeOutputMaterial")
gm.node_tree.links.new(zb.outputs["BSDF"], zo.inputs["Surface"])
zb.inputs["Base Color"].default_value = (0.35, 0.33, 0.28, 1)
zb.inputs["Roughness"].default_value = 0.9
ground.data.materials.append(gm)

# Güneş
bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), math.radians(10), math.radians(-40)))
sun = bpy.context.active_object
sun.data.energy = 4.0
sun.data.angle = math.radians(2)

# Kamera
tgt = Vector((0, 0, target_z))
cam_pos = Vector((math.sin(angle) * dist, -math.cos(angle) * dist, target_z + height))
bpy.ops.object.camera_add(location=cam_pos)
cam = bpy.context.active_object
cam.rotation_mode = "QUATERNION"
cam.rotation_quaternion = (tgt - cam_pos).to_track_quat("-Z", "Y")
cam.data.lens = 50
scene.camera = cam

scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("Render:", out)
