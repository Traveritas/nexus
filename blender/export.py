"""把当前打开的 .blend 导出成 public/scenes/<文件名>.glb
运行：node scripts/blender.cjs export <名字>   （即 blender -b blender/<名字>.blend --python blender/export.py）
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nx  # noqa: E402

name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
nx.export(name)
