
# ========================================================================
# C3_background.py

# LICENSE:
# SPDX-License-Identifier: MIT
# Copyright (c)  2026 Natalie Sokalska

# Code creates the background for the dynamic glacier visualization 
# Must be executed in Blender's built-in Python console (Scripting workspace).
# uses Shader, Geometry nodes - software Blender

# INPUTS: background DSM, background satelite scene, binary mask with the same extent as the other files (cutout for glacier area)

# OUTPUT: creates Blender object in the project



# ====== READ THIS BEFORE EXECUTING ======================================
# There is a strict policy in which order (in  Blender) the codes C3 and C4 have to be executed
# C3_background.py runs first, after that, the C4_glacier.py code must be executed, otherwise the functions would not work
# ========================================================================



import bpy
import math

# ========================================================================
# 1. USER SETTINGS
# ========================================================================


# replace with your own filepaths
BG_DEM_FILE   = "background_DSM.tif"   # digital surface model
BG_COLOR_FILE = "background_color.tif" # satelite image


# Replace with your mask file
# Glacier outline mask: BLACK = glacier hole (transparent), WHITE = surrounding terrain 
# Set INVERT_MASK = True below if your mask has swithed colors
BG_MASK_FILE  = "MASK_BGROUND.tif"
INVERT_MASK = False   

# ── SIZING ───────────────────────────────────────────────────────────────
# Compute from your DSM extent in ArcGIS or other software:
#   BG_SIZE_X = (Right - Left)   / 1000   [m → km]
#   BG_SIZE_Y = (Top   - Bottom) / 1000   [m → km]

## Replace with the values measured for your own background DEM.
# numbers for Belvedere glacier kept as a example, switch them for yours
BG_SIZE_X    = 11.010   # width  in km (= Blender units)
BG_SIZE_Y    = 11.040   # height in km (= Blender units)
BG_RESOLUTION = 512     # Grid subdivisions — increase for finer terrain detail


BG_Z_SCALE = 0.001    # do not change z scale, only if you need to exagerate some height details,
BG_ROTATION_Z = 0.0   # Keep 0.0 to share True North with the glacier, possible change if you neeed to rotate

# ── ALIGNMENT OFFSETS ────────────────────────────────────────────────────
# Shifts the background so its geographic centre aligns with the glacier
# Compute as: (background_centre - glacier_centre) / 1000  [m >> km]
#   background_centre = ((Left + Right) / 2,  (Bottom + Top) / 2)
#   glacier_centre    = geographic centre of your glacier study area
OFFSET_X = 0.804   # km east  of glacier centre
OFFSET_Y = 1.440   # km north of glacier centre


# ========================================================================
# 1.5 CLEANUP OLD BACKGROUND
# ========================================================================
print("Cleaning up old background versions...")
for obj_name in ["Background_Valley", "Glacier_Hole_Cutter"]:
    if obj_name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[obj_name], do_unlink=True)


# ========================================================================
# 2. CREATE THE BACKGROUND GRID
# ========================================================================
print("Generating Background Valley...")
bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=BG_RESOLUTION,
    y_subdivisions=BG_RESOLUTION,
    size=1,
    calc_uvs=True
)
bg_mesh = bpy.context.active_object
bg_mesh.name = "Background_Valley"

# Scale to true geographic dimensions 
bg_mesh.scale = (BG_SIZE_X, BG_SIZE_Y, 1.0)

# Shift so the background DEM centre aligns with the glacier at world origin
bg_mesh.location = (OFFSET_X, OFFSET_Y, 0.0)
bg_mesh.rotation_euler[2] = math.radians(BG_ROTATION_Z)

bpy.ops.object.shade_smooth()


# ========================================================================
# 3. SETUP 3D DISPLACEMENT - ELEVATION
# ========================================================================
dem_img = bpy.data.images.load(BG_DEM_FILE)
dem_img.colorspace_settings.name = 'Non-Color'

dem_tex = bpy.data.textures.new("BG_DEM_Tex", type='IMAGE')
dem_tex.image     = dem_img
dem_tex.extension = 'EXTEND'

mod_disp = bg_mesh.modifiers.new(name="BG_Displace", type='DISPLACE')
mod_disp.texture        = dem_tex
mod_disp.direction      = 'Z'
mod_disp.mid_level      = 0.0
mod_disp.texture_coords = 'UV'
mod_disp.strength       = BG_Z_SCALE  


# ========================================================================
# 4. SETUP SATELLITE MATERIAL & ALPHA MASK CUTOUT
# ========================================================================

bg_mat = bpy.data.materials.new(name="Background_Color_Mat")
bg_mat.use_nodes = True

# ALPHA_BLEND: makes the mask's transparent region an actual hole in the mesh.
# CLIP: prevents the transparent region from casting an opaque shadow on the glacier.
# Removed in Blender 4.2+ (transparency is handled automatically via the Alpha connection).
if bpy.app.version < (4, 2, 0):
    bg_mat.blend_method  = 'ALPHA_BLEND'
    bg_mat.shadow_method = 'CLIP'

nodes = bg_mat.node_tree.nodes
links = bg_mat.node_tree.links

bsdf = nodes.get("Principled BSDF")
bsdf.inputs['Roughness'].default_value = 0.8

# UV Coordinate node — stretches both textures to exactly fill the mesh
node_uv = nodes.new(type='ShaderNodeTexCoord')
node_uv.location = (-600, 0)

# Satellite colour texture
color_img  = bpy.data.images.load(BG_COLOR_FILE)
color_node = nodes.new(type='ShaderNodeTexImage')
color_node.location = (-300, 100)
color_node.image    = color_img
links.new(node_uv.outputs['UV'], color_node.inputs['Vector'])
links.new(color_node.outputs['Color'], bsdf.inputs['Base Color'])

# Alpha mask (the glacier-shaped hole)
mask_img  = bpy.data.images.load(BG_MASK_FILE)
mask_img.colorspace_settings.name = 'Non-Color'
mask_node = nodes.new(type='ShaderNodeTexImage')
mask_node.location  = (-300, -200)
mask_node.image     = mask_img
mask_node.extension = 'EXTEND'
links.new(node_uv.outputs['UV'], mask_node.inputs['Vector'])

#Optional invert — controlled by INVERT_MASK at the top of the script
invert_node = nodes.new(type='ShaderNodeInvert')
invert_node.location = (-50, -200)
invert_node.inputs['Fac'].default_value = 1.0 if INVERT_MASK else 0.0
links.new(mask_node.outputs['Color'], invert_node.inputs['Color'])
links.new(invert_node.outputs['Color'], bsdf.inputs['Alpha'])

bg_mesh.data.materials.append(bg_mat)

# Switch to Material Preview so the alpha cutout is immediately visible
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'

print(" Background Valley created with alpha cutout.")
print()
print("=" * 60)
print("ALIGNMENT DIAGNOSTIC")
print("=" * 60)
print(f"  Background size      : {BG_SIZE_X} x {BG_SIZE_Y} km")
print(f"  Background centre    : ({OFFSET_X:.3f}, {OFFSET_Y:.3f}) BU")
print(f"  Background X extent  : {OFFSET_X - BG_SIZE_X/2:.3f}  ->  {OFFSET_X + BG_SIZE_X/2:.3f} BU")
print(f"  Background Y extent  : {OFFSET_Y - BG_SIZE_Y/2:.3f}  ->  {OFFSET_Y + BG_SIZE_Y/2:.3f} BU")
print()
uv_x = 0.5 + OFFSET_X / BG_SIZE_X
uv_y = 0.5 + OFFSET_Y / BG_SIZE_Y
print(f"  Glacier centre in background UV space: ({uv_x:.4f}, {uv_y:.4f})")
print(f"  The glacier hole in your mask should be centred at U={uv_x:.2f}, V={uv_y:.2f}.")
print("=" * 60)
