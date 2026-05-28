"""
Blender Python 标准化修复脚本库。

阶段一核心资产: 积累可复用的Blender修复脚本模板，
供LLM TECH_ANALYST 参考生成缺陷专属修复方案。

脚本模板列表:
  1. fill_small_holes      — 小孔洞填充（<128边）
  2. fix_normals           — 法线方向一致性修正
  3. merge_by_distance      — 重合顶点合并（去重）
  4. decimate               — 减面优化（保持50%面数）
  5. export_glb             — GLB格式导出

使用方式:
  from app.services.scripts.blender_scripts import REPAIR_SCRIPT_TEMPLATES
  script = REPAIR_SCRIPT_TEMPLATES["fill_small_holes"]
"""
# flake8: noqa  (Blender脚本包含 bpy. 引用，在非Blender环境下无法lint)

REPAIR_SCRIPT_TEMPLATES: dict[str, str] = {
    "fill_small_holes": """
import bpy
import bmesh

def fill_small_holes(max_edges=128):
    \"\"\"填充边界边数 <= max_edges 的小孔洞\"\"\"
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
    \"\"\"统一所有面的法线方向（朝外）\"\"\"
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
    \"\"\"合并在 distance 范围内的重合顶点\"\"\"
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
    \"\"\"对面数进行按比例减面\"\"\"
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
    \"\"\"导出当前场景为GLB格式\"\"\"
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
