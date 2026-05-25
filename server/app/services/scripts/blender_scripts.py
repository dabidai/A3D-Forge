"""
Blender Python 标准化修复脚本库。
阶段一积累的修复脚本在此归档，供LLM参考和复用。
"""

REPAIR_SCRIPT_TEMPLATES = {
    "fill_small_holes": """
import bpy
import bmesh

def fill_small_holes(max_edges=128):
    obj = bpy.context.active_object
    if obj is None or obj.type != 'MESH':
        return
    bm = bmesh.from_edit_mesh(obj.data)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.fill_holes(sides=max_edges)
    bmesh.update_edit_mesh(obj.data)

fill_small_holes()
""",
    "fix_normals": """
import bpy

def fix_normals():
    obj = bpy.context.active_object
    if obj is None or obj.type != 'MESH':
        return
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

fix_normals()
""",
    "merge_by_distance": """
import bpy

def merge_duplicate_vertices(distance=0.0001):
    obj = bpy.context.active_object
    if obj is None or obj.type != 'MESH':
        return
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=distance)
    bpy.ops.object.mode_set(mode='OBJECT')

merge_duplicate_vertices()
""",
    "decimate": """
import bpy

def decimate_model(ratio=0.5):
    obj = bpy.context.active_object
    if obj is None or obj.type != 'MESH':
        return
    modifier = obj.modifiers.new(name="Decimate", type='DECIMATE')
    modifier.ratio = ratio
    bpy.ops.object.modifier_apply(modifier="Decimate")

decimate_model(ratio=0.5)
""",
    "export_glb": """
import bpy

def export_glb(filepath):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
    )

export_glb("{filepath}")
""",
}
