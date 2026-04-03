import bpy
import sys

print("=== Blender version:", bpy.app.version_string)
print("=== Python version:", sys.version)

print("=== Testing fast64 availability...")
try:
    import fast64
    print("fast64 imported OK, module:", fast64)
except Exception as e:
    print("fast64 import FAILED:", e)

print("=== Testing sm64_obj_type on Object...")
try:
    obj = bpy.data.objects.new("TestObj", None)
    bpy.context.scene.collection.objects.link(obj)
    val = obj.sm64_obj_type
    print("sm64_obj_type =", val)
except Exception as e:
    print("sm64_obj_type access FAILED:", e)

print("=== Testing createF3DMat...")
try:
    from fast64.fast64_internal.f3d.f3d_material import createF3DMat
    print("createF3DMat imported OK")
    mesh = bpy.data.meshes.new("TestMesh")
    mesh_obj = bpy.data.objects.new("TestMesh", mesh)
    bpy.context.scene.collection.objects.link(mesh_obj)
    mat = createF3DMat(mesh_obj, "Shaded Solid")
    print("createF3DMat returned:", mat)
except Exception as e:
    print("createF3DMat FAILED:", e)

print("=== Testing scene.fast64.sm64 properties...")
try:
    scene = bpy.context.scene
    sm64 = scene.fast64.sm64
    sm64.export_type = "C"
    ce = sm64.combined_export
    ce.non_decomp_level = True
    print("non_decomp_level =", ce.non_decomp_level)
    print("sm64 props OK")
except Exception as e:
    print("sm64 props FAILED:", e)

print("=== Test complete")
sys.exit(0)
