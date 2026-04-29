
# ========================================================================
# C4_glacier.py

# LICENSE:
# SPDX-License-Identifier: MIT
# Copyright (c)  2026 sokalskn

# Code computes 3D dynamic glacier visualization 
# Must be executed in Blender's built-in Python console (Scripting workspace).
# uses Shader, Geometry nodes - software Blender


# INPUTS: the raster outputs from C2_iceVelocity.ipynb, binary mask with the same extent as the raster files (cutout for glacier area)

# OUTPUT: creates Blender object in the Blender project


# ====== READ THIS BEFORE EXECUTING ======================================
# There is a strict policy in which order (in  Blender) the codes C3 and C4 have to be executed
# C3_background.py runs first, after that, the C4_glacier.py code must be executed, otherwise the functions would not work
# ========================================================================



import bpy
import os

# Load a GeoTIFF as a Non-Color image (no gamma correction).
def load_image(filepath):
    img = bpy.data.images.load(filepath, check_existing=True)
    img.colorspace_settings.name = 'Non-Color'
    return img

# ========================================================================
# 1. USER SETTINGS START
# ========================================================================


#change for your surface, flow, thickness files - generated from code C2_iceVelocity
SURFACE_FILES = [
    "SURFACE_RAW_2015.tif",
    "SURFACE_RAW_2016.tif",
    "SURFACE_RAW_2017.tif",
    "SURFACE_RAW_2018.tif",
    "SURFACE_RAW_2019.tif",
    "SURFACE_RAW_2021.tif",
    "SURFACE_RAW_2022.tif",
    "SURFACE_RAW_2023.tif",
]

FLOW_FILES = [
    "FLOW_2015.tif",
    "FLOW_2016.tif",
    "FLOW_2017.tif",
    "FLOW_2018.tif",
    "FLOW_2019.tif",
    "FLOW_2021.tif",
    "FLOW_2022.tif",
    "FLOW_2023.tif"
]

UNIQUE_MASK_FILES = [
    "THICKNESS_2015.tif",
    "THICKNESS_2018.tif",
    "THICKNESS_2021.tif",
    "THICKNESS_2023.tif"
]

# "fake" thickness raster that was generated with the universal (buffer) outline  
# - possible to run code C2_iceVelocity and change specific year outline for universal buffer outline - the thickness generated will be this mask
MASTER_OUTLINE = "THICKNESS_MASTER.tif"

# For each outline in UNIQUE_MASK_FILES, give the index of the matching
# year in SURFACE_FILES (0 = first , 1 = second,...)
MASK_KEY_INDICES = [0, 3, 5, 7]

# set resolution - should be same as the other scripts
GRID_RES       = 1024
ANIMATION_LENGTH = 193  # Total frames in the timeline.
                         # Formula: 1 + (number of calendar years spanned) × (frames per year).
                         # Multi-year gaps between observations receive proportionally more frames.

TRUE_GLACIER_WIDTH  = 1.604061029   # km - needs to be changed (right now, it uses Belvedere glacier values)
TRUE_GLACIER_HEIGHT = 2.8986786     # km - needs to be changed
GLACIER_WIDTH_M     = TRUE_GLACIER_WIDTH  * 1000  # convert km → metres
GLACIER_HEIGHT_M    = TRUE_GLACIER_HEIGHT * 1000  # convert km → metres
ASPECT_RATIO        = GLACIER_HEIGHT_M / GLACIER_WIDTH_M


# This is a list of the dates of each glacier survey
# change for your glacier, list has example values for Belvedere glacier
# Fractional acquisition years — October (+9.5/12) for 2015-2017, July (+6.5/12) for 2018-2023

YEARS = [
    2015 + 9.5/12,   # October 2015
    2016 + 9.5/12,   # October 2016
    2017 + 9.5/12,   # October 2017
    2018 + 6.5/12,   # July 2018
    2019 + 6.5/12,   # July 2019
    2021 + 6.5/12,   # July 2021
    2022 + 6.5/12,   # July 2022
    2023 + 6.5/12,   # July 2023
]


# ========================================================================
# USER SETTINGS END
# ========================================================================



# ── Proportional frame timing ─────────────────────────────────────────────
# The timeline is divided proportionally by calendar year. Multi-year gaps between
# observations automatically receive proportionally more frames
total_real_years     = YEARS[-1] - YEARS[0]
frames_per_real_year = (ANIMATION_LENGTH - 1) / total_real_years
YEAR_FRAMES = [1 + round((y - YEARS[0]) * frames_per_real_year) for y in YEARS]

# ── Flow speed conversion factor ─────────────────────────────────────────
# Converts velocity (m yr⁻¹) to UV offset per frame.
# In one full year: UV_offset = V / GLACIER_WIDTH_M
# Therefore: FLOW_SPEED = 1 / (frames_per_real_year × GLACIER_WIDTH_M)
# This factor applies directly to the X (East) component only.
#       The Y (North) component is divided by ASPECT_RATIO in the shader
#       (see node_div_k1 / node_div_k2), which effectively replaces
#       GLACIER_WIDTH_M with GLACIER_HEIGHT_M for the vertical axis.
FLOW_SPEED = 1.0 / (frames_per_real_year * GLACIER_WIDTH_M)

Z_SCALE  = 0.001      # possible to change for exaggeration, but should stay 0.001 
Z_OFFSET = 0.0001     # Lifts the glacier mesh slightly above the background to prevent z-fighting

# ── Sanity checks ────────────────────────────────────────────────────────
if len(SURFACE_FILES) != len(FLOW_FILES):
    raise ValueError("ERROR: You must have the same number of SURFACE and FLOW files!")
if len(UNIQUE_MASK_FILES) != len(MASK_KEY_INDICES):
    raise ValueError("ERROR: Your unique masks must match your key indices!")
if len(SURFACE_FILES) != len(YEARS):
    raise ValueError("ERROR: YEARS list must have one entry per SURFACE file!")
for _i in range(len(YEAR_FRAMES) - 1):
    if YEAR_FRAMES[_i + 1] <= YEAR_FRAMES[_i]:
        raise ValueError(f"ERROR: YEAR_FRAMES[{_i}] and [{_i+1}] collide ({YEAR_FRAMES[_i]}) — increase ANIMATION_LENGTH!")

num_years = len(SURFACE_FILES)

print(f"  YEAR_FRAMES : {YEAR_FRAMES}")
print(f"  FLOW_SPEED  : {FLOW_SPEED:.8f}")

# ========================================================================
# CLEANUP OLD 
# ========================================================================
print("Cleaning up old glacier...")
if "Glacier_Visualization" in bpy.data.objects:
    old_obj = bpy.data.objects["Glacier_Visualization"]
    bpy.data.objects.remove(old_obj, do_unlink=True)

# Remove stale displacement textures from previous runs 
for tex in list(bpy.data.textures):
    if tex.name.startswith("Year_"):
        bpy.data.textures.remove(tex)

# Remove stale glacier material from previous runs
if "Glacier_Flow_Mat" in bpy.data.materials:
    bpy.data.materials.remove(bpy.data.materials["Glacier_Flow_Mat"])

# Remove stale HUD text material from previous runs
if "Text_Outline_Mat" in bpy.data.materials:
    bpy.data.materials.remove(bpy.data.materials["Text_Outline_Mat"])

# Remove stale geometry node group from previous runs
for ng in list(bpy.data.node_groups):
    if ng.name.startswith("GeoCutTree"):
        bpy.data.node_groups.remove(ng)

# Remove stale images loaded by previous runs (surface, flow, mask, outline)
managed_image_paths = {
    os.path.normpath(p)
    for p in list(SURFACE_FILES) + list(FLOW_FILES) + list(UNIQUE_MASK_FILES) + [MASTER_OUTLINE]
}
for img in list(bpy.data.images):
    if os.path.normpath(img.filepath) in managed_image_paths:
        bpy.data.images.remove(img)


# ========================================================================
# CREATE THE GLACIER GRID
# ========================================================================
print("Generating Grid")
bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=GRID_RES,
    y_subdivisions=round(GRID_RES * ASPECT_RATIO),
    size=1,
    calc_uvs=True
)
glacier_obj = bpy.context.active_object
glacier_obj.name = "Glacier_Visualization"
bpy.ops.object.shade_smooth()

# Apply true real world geographic scales
glacier_obj.scale[0] = TRUE_GLACIER_WIDTH
glacier_obj.scale[1] = TRUE_GLACIER_HEIGHT

# Apply the X/Y scale to the mesh so all modifiers and exports see consistent
# world space geometry. 
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# Lift the glacier slightly so it sits cleanly above the background rock
glacier_obj.location = (0.0, 0.0, Z_OFFSET)


# ========================================================================
# PHYSICALLY CUT THE GRID (GEOMETRY NODES)
# ========================================================================
print("Cutting the glacier grid to glacier outline using the master thickness mask")

geo_mask_img = load_image(MASTER_OUTLINE)

mod_gn = glacier_obj.modifiers.new(name="Cut_Invisible_Corners", type='NODES')
gn_tree = bpy.data.node_groups.new(name="GeoCutTree", type='GeometryNodeTree')
mod_gn.node_group = gn_tree

gn_nodes = gn_tree.nodes
gn_links = gn_tree.links

# in_out='INPUT' defines a modifier input (data source), 'OUTPUT' defines the modifier output (result).
node_in = gn_nodes.new(type='NodeGroupInput')
gn_tree.interface.new_socket(name="Geometry", in_out='INPUT',  socket_type='NodeSocketGeometry')
node_in.location = (-400, 0)

node_out = gn_nodes.new(type='NodeGroupOutput')
gn_tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
node_out.location = (400, 0)

#Delete-Geometry node
node_del = gn_nodes.new(type='GeometryNodeDeleteGeometry')
node_del.domain   = 'FACE'
node_del.location = (200, 0)
gn_links.new(node_in.outputs[0], node_del.inputs[0])
gn_links.new(node_del.outputs[0], node_out.inputs[0])

# Image texture (the thickness map)
node_tex = gn_nodes.new(type='GeometryNodeImageTexture')
if hasattr(node_tex, 'image'):                            
    node_tex.image = geo_mask_img
if 'Image' in node_tex.inputs:                            
    node_tex.inputs['Image'].default_value = geo_mask_img
node_tex.extension    = 'EXTEND'
node_tex.interpolation = 'Closest'
node_tex.location = (-200, -200)

#UV-map input
gn_node_uv = gn_nodes.new(type='GeometryNodeInputNamedAttribute')
gn_node_uv.data_type = 'FLOAT_VECTOR'
gn_node_uv.inputs[0].default_value = 'UVMap'
gn_node_uv.location = (-400, -200)
gn_links.new(gn_node_uv.outputs[0], node_tex.inputs['Vector'])

# Compare node
node_compare = gn_nodes.new(type='FunctionNodeCompare')
node_compare.data_type = 'FLOAT'
node_compare.operation = 'LESS_THAN'
node_compare.inputs[1].default_value = 0.05   # delete faces with thickness < 5 cm (0.05 m)
node_compare.location = (0, -200)

# Separate the color into channels so the R value reaches the Float input of
# FunctionNodeCompare explicitly. 
_compare_input = node_compare.inputs[0]
_sep_color_node = None
for _sep_type in ('FunctionNodeSeparateColor', 'GeometryNodeSeparateColor', 'ShaderNodeSeparateColor'):
    try:
        _sep_color_node = gn_nodes.new(type=_sep_type)
        break
    except RuntimeError:
        pass

if _sep_color_node is not None:
    _sep_color_node.location = (-50, -200)
    gn_links.new(node_tex.outputs['Color'],       _sep_color_node.inputs['Color'])
    gn_links.new(_sep_color_node.outputs['Red'],  _compare_input)
else:
    gn_links.new(node_tex.outputs['Color'],       _compare_input)
gn_links.new(node_compare.outputs['Result'],    node_del.inputs['Selection'])


# ========================================================================
# SETUP DISPLACEMENT TIMELINE
# ========================================================================
print("Building 3D Surface Transitions")
for i, filepath in enumerate(SURFACE_FILES):
    year_name = f"Year_{i}"

    img = load_image(filepath)

    tex = bpy.data.textures.new(year_name, type='IMAGE')
    tex.image     = img
    tex.extension = 'EXTEND'

    mod = glacier_obj.modifiers.new(name=year_name, type='DISPLACE')
    mod.texture       = tex
    mod.direction     = 'Z'
    mod.mid_level     = 0.0
    mod.texture_coords = 'UV'
    mod.uv_layer      = 'UVMap'
    frame_peak = YEAR_FRAMES[i]

    # Keyframe pattern: 0 at YEAR_FRAMES[i-1] >> peak at YEAR_FRAMES[i] >> 0 at YEAR_FRAMES[i+1].
    # Year 0 has no preceding keyframe, Blender holds the initial value constant before frame 1.
    mod.strength = 0.0
    if i > 0:
        mod.keyframe_insert(data_path="strength", frame=YEAR_FRAMES[i - 1])

    mod.strength = Z_SCALE
    mod.keyframe_insert(data_path="strength", frame=frame_peak)

    if i < (num_years - 1):
        mod.strength = 0.0
        mod.keyframe_insert(data_path="strength", frame=YEAR_FRAMES[i + 1])

# Enforce LINEAR interpolation on all displacement keyframes
if glacier_obj.animation_data and glacier_obj.animation_data.action:
    for fcurve in glacier_obj.animation_data.action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'LINEAR'


# ========================================================================
# SETUP THE DYNAMIC FLOW and MASK SHADER ENGINE
# ========================================================================
print("Building Dynamic Flow Shader Engine")
mat   = bpy.data.materials.new(name="Glacier_Flow_Mat")
mat.use_nodes = True
mat_nodes = mat.node_tree.nodes
mat_links = mat.node_tree.links
mat_nodes.clear()

node_output = mat_nodes.new(type='ShaderNodeOutputMaterial')
node_output.location = (2700, 0)

node_principled = mat_nodes.new(type='ShaderNodeBsdfPrincipled')
node_principled.location = (2450, 0)
mat_links.new(node_principled.outputs[0], node_output.inputs[0])

# UV coordinates — used by both the ice extent mask and the Lagrangian flow engine
node_uv = mat_nodes.new(type='ShaderNodeTexCoord')
node_uv.location = (-1000, 0)

# ------------------------------------------------------------------------
# CONTINUOUS SMOOTH MASK CHAIN
#    Crossfades the key year thickness masks (for Belvedere: 2015, 2018, 2021, 2023).
#    Uses YEAR_FRAMES so the 2019>>2021 transition takes proportionally longer.
# ------------------------------------------------------------------------
mask_nodes = []
for i, filepath in enumerate(UNIQUE_MASK_FILES):
    mask_img = load_image(filepath)

    node = mat_nodes.new(type='ShaderNodeTexImage')
    node.location = (-1000, 300 + (i * 300))
    node.image    = mask_img
    node.extension = 'EXTEND'
    mat_links.new(node_uv.outputs['UV'], node.inputs['Vector'])
    mask_nodes.append(node)

last_mask_output = mask_nodes[0].outputs[0]

for i in range(1, len(UNIQUE_MASK_FILES)):
    mask_mix = mat_nodes.new(type='ShaderNodeMix')
    mask_mix.data_type = 'RGBA'
    mask_mix.location = (-700 + (i * 200), 400)
    # clamp_factor restricts the Factor to [0, 1], 
    mask_mix.clamp_factor = True

    mat_links.new(last_mask_output,        mask_mix.inputs[6])
    mat_links.new(mask_nodes[i].outputs[0], mask_mix.inputs[7])

    idx_start  = MASK_KEY_INDICES[i - 1]
    idx_end    = MASK_KEY_INDICES[i]
    frame_start = YEAR_FRAMES[idx_start]
    frame_end   = YEAR_FRAMES[idx_end]

    # Anchor keyframes at frame 1 and ANIMATION_LENGTH hold the factor at 0 before
    # frame_start and at 1 after frame_end. Without them, LINEAR extrapolation
    # produces large negative values at frame 1, corrupting the mask
    mask_mix.inputs[0].default_value = 0.0
    mask_mix.inputs[0].keyframe_insert(data_path="default_value", frame=1)
    if frame_start > 1:
        mask_mix.inputs[0].keyframe_insert(data_path="default_value", frame=frame_start)
    mask_mix.inputs[0].default_value = 1.0
    mask_mix.inputs[0].keyframe_insert(data_path="default_value", frame=frame_end)
    if frame_end < ANIMATION_LENGTH:
        mask_mix.inputs[0].keyframe_insert(data_path="default_value", frame=ANIMATION_LENGTH)

    last_mask_output = mask_mix.outputs[2]

# Set all mask blend keyframes to LINEAR — must match the displacement modifier interpolation
if mat.node_tree.animation_data and mat.node_tree.animation_data.action:
    for fcurve in mat.node_tree.animation_data.action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'LINEAR'

# Separate the R channel explicitly — THICKNESS TIFFs are single band but
# last_mask_output is a Color socket
node_mask_sep = mat_nodes.new(type='ShaderNodeSeparateColor')
node_mask_sep.location = (500, 300)
mat_links.new(last_mask_output, node_mask_sep.inputs['Color'])

# Map Range: 0 m ice thickness >> mask 0.0, 5 m >> mask 1.0 (linear, clamped)
node_mask_smooth = mat_nodes.new(type='ShaderNodeMapRange')
node_mask_smooth.location = (700, 300)
node_mask_smooth.clamp = True
node_mask_smooth.inputs['From Min'].default_value = 0.0
node_mask_smooth.inputs['From Max'].default_value = 5.0
node_mask_smooth.inputs['To Min'].default_value   = 0.0
node_mask_smooth.inputs['To Max'].default_value   = 1.0
mat_links.new(node_mask_sep.outputs['Red'], node_mask_smooth.inputs[0])

# ------------------------------------------------------------------------
# semi-LAGRANGIAN FLOW ENGINE — RK2 (midpoint) backward integration
#
# Uses the 2nd order Runge-Kutta midpoint method for each annual backward step
# Each year requires two flow texture samples (k1 and k2).
#
#   uv_backward = UV₀
#   for i from N-2 down to 0:
#   k1        = V_i(uv_backward)                                     # velocity at end-of-year position
#   uv_half   = uv_backward − k1 × (duration/2) × FLOW_SPEED         # half-step to midpoint
#   k2        = V_i(uv_half)                                         # velocity at midpoint position
#   contrib_i = k2 × clamp(frame − YEAR_FRAMES[i], 0, duration_i) × FLOW_SPEED
#   uv_backward −= k2 × duration_i × FLOW_SPEED                      # full step using midpoint velocity
#
#   total_offset = Σᵢ contrib_i
#   noise UV = UV₀ − total_offset
# ------------------------------------------------------------------------

# Global frame driver (ine node that solves frma time)
node_frame = mat_nodes.new(type='ShaderNodeValue')
node_frame.location = (-2000, -800)
node_frame.outputs[0].driver_add("default_value").driver.expression = "frame"

node_total_offset = None   # will accumulate ADD nodes

# Reversed loop: most-recent year first (i = N-2 down to 0).
# uv_backward starts at UV₀ (the current screen pixel (= 2023 position)) and 
# walks upstream one full year per iteration.  
uv_backward = node_uv.outputs['UV']

for layout_row, i in enumerate(range(num_years - 2, -1, -1)):
    # i counts down: 6 (2022), 5 (2021), … 0 (2015)
    duration_i = float(YEAR_FRAMES[i + 1] - YEAR_FRAMES[i])
    lr = layout_row * 2200   # vertical base offset for this year's node band

    # Timing: clamp(frame − YEAR_FRAMES[i], 0, duration_i) 
    node_elapsed = mat_nodes.new(type='ShaderNodeMath')
    node_elapsed.operation = 'SUBTRACT'
    node_elapsed.location  = (-5000, -lr)
    node_elapsed.inputs[1].default_value = float(YEAR_FRAMES[i])
    mat_links.new(node_frame.outputs[0], node_elapsed.inputs[0])

    # Floor at 0  (before this year started)
    node_max0 = mat_nodes.new(type='ShaderNodeMath')
    node_max0.operation = 'MAXIMUM'
    node_max0.location  = (-4800, -lr)
    node_max0.inputs[1].default_value = 0.0
    mat_links.new(node_elapsed.outputs[0], node_max0.inputs[0])

    # Cap at duration_i: stop accumulating once this year has fully played
    node_clamped = mat_nodes.new(type='ShaderNodeMath')
    node_clamped.operation = 'MINIMUM'
    node_clamped.location  = (-4600, -lr)
    node_clamped.inputs[1].default_value = duration_i
    mat_links.new(node_max0.outputs[0], node_clamped.inputs[0])

    # Multiply by FLOW_SPEED: convert clamped frames into UV displacement
    node_time_factor = mat_nodes.new(type='ShaderNodeMath')
    node_time_factor.operation = 'MULTIPLY'
    node_time_factor.location  = (-4400, -lr)
    node_time_factor.inputs[1].default_value = FLOW_SPEED
    mat_links.new(node_clamped.outputs[0], node_time_factor.inputs[0])

    # α = clamped / duration_i  (0 at interval start >> 1 at interval end)
    # Drives the temporal blend: α=0 >> pure FLOW[i], α=1 >> pure FLOW[i+1].
    node_alpha = mat_nodes.new(type='ShaderNodeMath')
    node_alpha.operation = 'DIVIDE'
    node_alpha.location  = (-4200, -lr)
    node_alpha.inputs[1].default_value = duration_i
    mat_links.new(node_clamped.outputs[0], node_alpha.inputs[0])

    # α/2 — sample velocity at the temporal midpoint of [0, α] so that
    # V(α/2) × t equals the correct integral ∫₀ᵗ V(τ/D) dτ for linear V.
    node_alpha_half = mat_nodes.new(type='ShaderNodeMath')
    node_alpha_half.operation = 'MULTIPLY'
    node_alpha_half.location  = (-4100, -lr)
    node_alpha_half.inputs[1].default_value = 0.5
    mat_links.new(node_alpha.outputs[0], node_alpha_half.inputs[0])

    # Load start (FLOW[i]) and end (FLOW[i+1]) snapshots 
    # FLOW tiff channels: R = Vx (East, m/yr), G = Vy (North, m/yr).
    flow_img_start = load_image(FLOW_FILES[i])
    flow_img_end   = load_image(FLOW_FILES[i + 1])

    # RK2 k1: sample both snapshots at uv_backward, blend by α 
    node_flow_k1_s = mat_nodes.new(type='ShaderNodeTexImage')
    node_flow_k1_s.location  = (-4000, -lr - 300)
    node_flow_k1_s.image     = flow_img_start
    node_flow_k1_s.extension = 'EXTEND'
    mat_links.new(uv_backward, node_flow_k1_s.inputs['Vector'])

    # Sample end-of-year flow (FLOW[i+1]) at uv_backward
    node_flow_k1_e = mat_nodes.new(type='ShaderNodeTexImage')
    node_flow_k1_e.location  = (-4000, -lr - 500)
    node_flow_k1_e.image     = flow_img_end
    node_flow_k1_e.extension = 'EXTEND'
    mat_links.new(uv_backward, node_flow_k1_e.inputs['Vector'])

    # Blend : start and endof year flow 
    node_mix_k1 = mat_nodes.new(type='ShaderNodeMix')
    node_mix_k1.data_type = 'RGBA'
    node_mix_k1.location = (-3700, -lr - 400)
    mat_links.new(node_alpha_half.outputs[0],  node_mix_k1.inputs[0])
    mat_links.new(node_flow_k1_s.outputs[0],  node_mix_k1.inputs[6])
    mat_links.new(node_flow_k1_e.outputs[0],  node_mix_k1.inputs[7])

    # Split k1 into Vx (R channel) and Vy (G channel) for per-axis correction
    node_sep_k1 = mat_nodes.new(type='ShaderNodeSeparateColor')
    node_sep_k1.location = (-3500, -lr - 400)
    mat_links.new(node_mix_k1.outputs[2], node_sep_k1.inputs[0])

    # Aspect-ratio correction on Vy 
    node_div_k1 = mat_nodes.new(type='ShaderNodeMath')
    node_div_k1.operation = 'DIVIDE'
    node_div_k1.location  = (-3300, -lr - 450)
    node_div_k1.inputs[1].default_value = ASPECT_RATIO
    mat_links.new(node_sep_k1.outputs[1], node_div_k1.inputs[0])

    # Recombine corrected (Vx, Vy/aspect) into a 2D velocity vector
    node_comb_k1 = mat_nodes.new(type='ShaderNodeCombineXYZ')
    node_comb_k1.location = (-3100, -lr - 400)
    mat_links.new(node_sep_k1.outputs[0], node_comb_k1.inputs[0])
    mat_links.new(node_div_k1.outputs[0], node_comb_k1.inputs[1])

    # RK2 half-step (animation): uv_half = uv_backward − k1 × (time_factor/2) ──
    node_time_factor_half = mat_nodes.new(type='ShaderNodeMath')
    node_time_factor_half.operation = 'MULTIPLY'
    node_time_factor_half.location = (-2900, -lr - 650)
    node_time_factor_half.inputs[1].default_value = 0.5
    mat_links.new(node_time_factor.outputs[0], node_time_factor_half.inputs[0])

    # Half-step UV displacement: k1 × (time_factor / 2)
    node_half_contrib = mat_nodes.new(type='ShaderNodeVectorMath')
    node_half_contrib.operation = 'SCALE'
    node_half_contrib.location  = (-2900, -lr - 550)
    mat_links.new(node_comb_k1.outputs[0], node_half_contrib.inputs[0])
    mat_links.new(node_time_factor_half.outputs[0], node_half_contrib.inputs['Scale'])

    # uv_half = uv_backward − half step displacement (midpoint position)
    node_uv_half = mat_nodes.new(type='ShaderNodeVectorMath')
    node_uv_half.operation = 'SUBTRACT'
    node_uv_half.location  = (-2700, -lr - 550)
    mat_links.new(uv_backward,                  node_uv_half.inputs[0])
    mat_links.new(node_half_contrib.outputs[0], node_uv_half.inputs[1])

    # RK2 k2 (animation): sample both snapshots at uv_half, blend by α 
    node_flow_k2_s = mat_nodes.new(type='ShaderNodeTexImage')
    node_flow_k2_s.location  = (-2500, -lr - 400)
    node_flow_k2_s.image     = flow_img_start
    node_flow_k2_s.extension = 'EXTEND'
    mat_links.new(node_uv_half.outputs[0], node_flow_k2_s.inputs['Vector'])

    # Sample end of year flow (FLOW[i+1]) at uv_half (midpoint position)
    node_flow_k2_e = mat_nodes.new(type='ShaderNodeTexImage')
    node_flow_k2_e.location  = (-2500, -lr - 600)
    node_flow_k2_e.image     = flow_img_end
    node_flow_k2_e.extension = 'EXTEND'
    mat_links.new(node_uv_half.outputs[0], node_flow_k2_e.inputs['Vector'])

    # Blend start and end of year flow by alpha_half >> k2 (velocity at uv_half)
    node_mix_k2 = mat_nodes.new(type='ShaderNodeMix')
    node_mix_k2.data_type = 'RGBA'
    node_mix_k2.location = (-2200, -lr - 500)
    mat_links.new(node_alpha_half.outputs[0],  node_mix_k2.inputs[0])
    mat_links.new(node_flow_k2_s.outputs[0],  node_mix_k2.inputs[6])
    mat_links.new(node_flow_k2_e.outputs[0],  node_mix_k2.inputs[7])

    # Split k2 into Vx (R) and Vy (G) for per axis correctio
    node_sep_k2 = mat_nodes.new(type='ShaderNodeSeparateColor')
    node_sep_k2.location = (-2000, -lr - 500)
    mat_links.new(node_mix_k2.outputs[2], node_sep_k2.inputs[0])

    # Aspect-ratio correction on Vy
    node_div_k2 = mat_nodes.new(type='ShaderNodeMath')
    node_div_k2.operation = 'DIVIDE'
    node_div_k2.location  = (-1800, -lr - 550)
    node_div_k2.inputs[1].default_value = ASPECT_RATIO
    mat_links.new(node_sep_k2.outputs[1], node_div_k2.inputs[0])

  # Recombine corrected (Vx, Vy/aspect)
    node_comb_k2 = mat_nodes.new(type='ShaderNodeCombineXYZ')
    node_comb_k2.location = (-1600, -lr - 500)
    mat_links.new(node_sep_k2.outputs[0], node_comb_k2.inputs[0])
    mat_links.new(node_div_k2.outputs[0], node_comb_k2.inputs[1])

    # Frame dependent contribution using blended midpoint velocity k2
    node_contrib = mat_nodes.new(type='ShaderNodeVectorMath')
    node_contrib.operation = 'SCALE'
    node_contrib.location  = (-1400, -lr - 500)
    mat_links.new(node_comb_k2.outputs[0],     node_contrib.inputs[0])
    mat_links.new(node_time_factor.outputs[0], node_contrib.inputs['Scale'])

    # ── Accumulate into total offset ──────────────────────────────────────
    if node_total_offset is None:
        node_total_offset = node_contrib
    else:
        node_add = mat_nodes.new(type='ShaderNodeVectorMath')
        node_add.operation = 'ADD'
        node_add.location  = (-1200, -lr - 500)
        mat_links.new(node_total_offset.outputs[0], node_add.inputs[0])
        mat_links.new(node_contrib.outputs[0],      node_add.inputs[1])
        node_total_offset = node_add

    # ── Full year uv_backward step,  separate RK2 with α=0.5 (time-average) 
    # Uses a fixed midpoint blend so the baked displacement reflects the
    # true average velocity over the whole interval, not the frame-varying α.
    
    if i > 0:
        # k1_step: reuse k1_s/k1_e texture outputs, blend at 0.5
        node_mix_k1_step = mat_nodes.new(type='ShaderNodeMix')
        node_mix_k1_step.data_type = 'RGBA'
        node_mix_k1_step.location = (-3700, -lr - 900)
        node_mix_k1_step.inputs[0].default_value = 0.5
        mat_links.new(node_flow_k1_s.outputs[0], node_mix_k1_step.inputs[6])
        mat_links.new(node_flow_k1_e.outputs[0], node_mix_k1_step.inputs[7])

       # Split k1_step into Vx (R) and Vy (G)
        node_sep_k1_step = mat_nodes.new(type='ShaderNodeSeparateColor')
        node_sep_k1_step.location = (-3500, -lr - 900)
        mat_links.new(node_mix_k1_step.outputs[2], node_sep_k1_step.inputs[0])

        # Aspect-ratio correction on Vy
        node_div_k1_step = mat_nodes.new(type='ShaderNodeMath')
        node_div_k1_step.operation = 'DIVIDE'
        node_div_k1_step.location  = (-3300, -lr - 950)
        node_div_k1_step.inputs[1].default_value = ASPECT_RATIO
        mat_links.new(node_sep_k1_step.outputs[1], node_div_k1_step.inputs[0])
       
        # Recombine corrected (Vx, Vy/aspect) 
        node_comb_k1_step = mat_nodes.new(type='ShaderNodeCombineXYZ')
        node_comb_k1_step.location = (-3100, -lr - 900)
        mat_links.new(node_sep_k1_step.outputs[0], node_comb_k1_step.inputs[0])
        mat_links.new(node_div_k1_step.outputs[0], node_comb_k1_step.inputs[1])

        # uv_half_step (separate from animation uv_half — different k1 blend)
        node_half_contrib_step = mat_nodes.new(type='ShaderNodeVectorMath')
        node_half_contrib_step.operation = 'SCALE'
        node_half_contrib_step.location  = (-2900, -lr - 1050)
        mat_links.new(node_comb_k1_step.outputs[0], node_half_contrib_step.inputs[0])
        node_half_contrib_step.inputs['Scale'].default_value = (duration_i / 2.0) * FLOW_SPEED

        # uv_half_step  (midpoint position)
        node_uv_half_step = mat_nodes.new(type='ShaderNodeVectorMath')
        node_uv_half_step.operation = 'SUBTRACT'
        node_uv_half_step.location  = (-2700, -lr - 1050)
        mat_links.new(uv_backward,                       node_uv_half_step.inputs[0])
        mat_links.new(node_half_contrib_step.outputs[0], node_uv_half_step.inputs[1])

        # k2_step: sample both snapshots at uv_half_step, blend at 0.5
        node_flow_k2_step_s = mat_nodes.new(type='ShaderNodeTexImage')
        node_flow_k2_step_s.location  = (-2500, -lr - 900)
        node_flow_k2_step_s.image     = flow_img_start
        node_flow_k2_step_s.extension = 'EXTEND'
        mat_links.new(node_uv_half_step.outputs[0], node_flow_k2_step_s.inputs['Vector'])

        # Sample end of year flow at uv_half_step
        node_flow_k2_step_e = mat_nodes.new(type='ShaderNodeTexImage')
        node_flow_k2_step_e.location  = (-2500, -lr - 1100)
        node_flow_k2_step_e.image     = flow_img_end
        node_flow_k2_step_e.extension = 'EXTEND'
        mat_links.new(node_uv_half_step.outputs[0], node_flow_k2_step_e.inputs['Vector'])

        # Mix start/end
        node_mix_k2_step = mat_nodes.new(type='ShaderNodeMix')
        node_mix_k2_step.data_type = 'RGBA'
        node_mix_k2_step.location = (-2200, -lr - 1000)
        node_mix_k2_step.inputs[0].default_value = 0.5
        mat_links.new(node_flow_k2_step_s.outputs[0], node_mix_k2_step.inputs[6])
        mat_links.new(node_flow_k2_step_e.outputs[0], node_mix_k2_step.inputs[7])

       # Split k2_step into Vx (R) and Vy (G)
        node_sep_k2_step = mat_nodes.new(type='ShaderNodeSeparateColor')
        node_sep_k2_step.location = (-2000, -lr - 1000)
        mat_links.new(node_mix_k2_step.outputs[2], node_sep_k2_step.inputs[0])

        #correction on Vy
        node_div_k2_step = mat_nodes.new(type='ShaderNodeMath')
        node_div_k2_step.operation = 'DIVIDE'
        node_div_k2_step.location  = (-1800, -lr - 1050)
        node_div_k2_step.inputs[1].default_value = ASPECT_RATIO
        mat_links.new(node_sep_k2_step.outputs[1], node_div_k2_step.inputs[0])
        
        # Recombine corrected
        node_comb_k2_step = mat_nodes.new(type='ShaderNodeCombineXYZ')
        node_comb_k2_step.location = (-1600, -lr - 1000)
        mat_links.new(node_sep_k2_step.outputs[0], node_comb_k2_step.inputs[0])
        mat_links.new(node_div_k2_step.outputs[0], node_comb_k2_step.inputs[1])

       # Full-year displacement
        node_full_contrib = mat_nodes.new(type='ShaderNodeVectorMath')
        node_full_contrib.operation = 'SCALE'
        node_full_contrib.location  = (-1400, -lr - 1000)
        mat_links.new(node_comb_k2_step.outputs[0], node_full_contrib.inputs[0])
        node_full_contrib.inputs['Scale'].default_value = duration_i * FLOW_SPEED

        # uv_prev = uv_backward − full-year displacement
        node_uv_prev = mat_nodes.new(type='ShaderNodeVectorMath')
        node_uv_prev.operation = 'SUBTRACT'
        node_uv_prev.location  = (-1200, -lr - 1000)
        mat_links.new(uv_backward,                  node_uv_prev.inputs[0])
        mat_links.new(node_full_contrib.outputs[0], node_uv_prev.inputs[1])

        uv_backward = node_uv_prev.outputs[0]   # now holds position at start of year i

# Subtract total accumulated offset  to scroll the noise with the ice
node_scroll_uv = mat_nodes.new(type='ShaderNodeVectorMath')
node_scroll_uv.operation = 'SUBTRACT'
node_scroll_uv.location  = (200, -800)
mat_links.new(node_uv.outputs['UV'],        node_scroll_uv.inputs[0])
mat_links.new(node_total_offset.outputs[0], node_scroll_uv.inputs[1])

# Pre squish UV so noise features look isotropic on the real glacier
node_noise_scale = mat_nodes.new(type='ShaderNodeVectorMath')
node_noise_scale.operation = 'MULTIPLY'
node_noise_scale.location  = (400, -800)
node_noise_scale.inputs[1].default_value = (1.0, ASPECT_RATIO, 1.0)
mat_links.new(node_scroll_uv.outputs[0], node_noise_scale.inputs[0])

# Single noise texture — scrolls continuously with no backward motion
node_noise = mat_nodes.new(type='ShaderNodeTexNoise')
node_noise.location = (600, -800)
node_noise.inputs['Scale'].default_value  = 20.0   # cca 50 m features at glacier scale
node_noise.inputs['Detail'].default_value = 5.0    # fractal octaves for fine grain
mat_links.new(node_noise_scale.outputs[0], node_noise.inputs['Vector'])

# ------------------------------------------------------------------------
# COLOR AND GLACIER BED
# ------------------------------------------------------------------------
# Color Ramp: maps noise to sandy ice colours
node_ramp = mat_nodes.new(type='ShaderNodeValToRGB')
node_ramp.location = (1800, -100)
node_ramp.color_ramp.elements[0].position = 0.42   # narrow contrast band (0.42–0.58) for sharp debris streaks
node_ramp.color_ramp.elements[0].color    = (0.28, 0.25, 0.22, 1.0)   # dark debris (near-black dark brown)
node_ramp.color_ramp.elements[1].position = 0.58
node_ramp.color_ramp.elements[1].color    = (0.95, 0.88, 0.72, 1.0)   # sandy surface (bright warm sand)
mat_links.new(node_noise.outputs[0], node_ramp.inputs[0])

# Solid colour for exposed bedrock (shown where ice has melted away)
node_bed = mat_nodes.new(type='ShaderNodeRGB')
node_bed.location = (1800, 100)
node_bed.outputs[0].default_value = (0.2, 0.18, 0.15, 1.0)

# Mix ice and bedrock using the animated thickness mask
node_mix_final = mat_nodes.new(type='ShaderNodeMix')
node_mix_final.data_type = 'RGBA'
node_mix_final.location = (2100, 0)
mat_links.new(node_mask_smooth.outputs[0], node_mix_final.inputs[0])   # mask factor
mat_links.new(node_bed.outputs[0],         node_mix_final.inputs[6])   # no ice >> bedrock
mat_links.new(node_ramp.outputs[0],        node_mix_final.inputs[7])   # has ice >> ice colour

mat_links.new(node_mix_final.outputs[2], node_principled.inputs['Base Color'])

glacier_obj.data.materials.append(mat)


# ========================================================================
# FINALISE TIMELINE AND VIEWPORT
# ========================================================================
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end   = ANIMATION_LENGTH
bpy.context.view_layer.update()

if bpy.context.screen is not None:
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'MATERIAL'


# ========================================================================
# PROCEDURALLY SNAP BACKGROUND TO GLACIER 
# ========================================================================
print("conecting background to glacier")

if "Background_Valley" in bpy.data.objects:
    bg_obj = bpy.data.objects["Background_Valley"]

    for mod_name in ["Auto_Blend_Weight", "Auto_Blend_Snap"]:
        if mod_name in bg_obj.modifiers:
            bg_obj.modifiers.remove(bg_obj.modifiers[mod_name])

    # group to hold the proximity weights
    vg_name = "Glacier_Seam"
    if vg_name in bg_obj.vertex_groups:
        bg_obj.vertex_groups.remove(bg_obj.vertex_groups[vg_name])
    vg = bg_obj.vertex_groups.new(name=vg_name)
    vg.add(range(len(bg_obj.data.vertices)), 0.0, 'REPLACE')

    # Vertex Weight Proximity: assigns weight 1 near the glacier edge, 0 far away
    mod_prox = bg_obj.modifiers.new(name="Auto_Blend_Weight", type='VERTEX_WEIGHT_PROXIMITY')
    mod_prox.vertex_group    = vg_name
    mod_prox.target          = glacier_obj
    mod_prox.proximity_mode  = 'GEOMETRY'
    mod_prox.proximity_geometry = {'FACE'}
    mod_prox.falloff_type    = 'LINEAR'
    mod_prox.min_dist = 0.0   # weight=1 right at the glacier edge
    mod_prox.max_dist = 0.01   # # weight fades to 0 at 10 m from glacier edge

    # Shrinkwrap: pulls background vertices along Z to match the glacier surface
    mod_shrink = bg_obj.modifiers.new(name="Auto_Blend_Snap", type='SHRINKWRAP')
    mod_shrink.target              = glacier_obj
    mod_shrink.vertex_group        = vg_name
    mod_shrink.wrap_method         = 'PROJECT'
    mod_shrink.use_project_z       = True
    mod_shrink.use_negative_direction = True
    mod_shrink.use_positive_direction = True

    print("terrain blend complete.")
else:
    print("WARNING: Background_Valley not found — run blender_background_code.py first.")


# ========================================================================
# 7. DYNAMIC HUD (HEADS-UP DISPLAY) FOR THE TIMELINE
# ========================================================================
print("Building Dynamic Year HUD")

camera_obj = bpy.context.scene.camera
if camera_obj is None:
    raise RuntimeError("No active camera found in the scene. "
                       "Assign a camera before running this script.")

if "Year_Display" in bpy.data.objects:
    _old_text_obj = bpy.data.objects["Year_Display"]
    _old_curve    = _old_text_obj.data
    bpy.data.objects.remove(_old_text_obj, do_unlink=True)
    if _old_curve.users == 0:
        bpy.data.curves.remove(_old_curve)

bpy.ops.object.text_add(location=(0, 0, 0))
text_obj = bpy.context.active_object
text_obj.name = "Year_Display"

# Parent to the camera so the text 
text_obj.parent = camera_obj

# Position in camera local space:
text_obj.location = (0.35, 0.3, -2.0)  

# No rotation needed — text parented to camera already faces the lens at (0,0,0).
text_obj.rotation_euler = (0.0, 0.0, 0.0)

# Text objects are 1 BU = 1 km by default 
text_obj.scale = (0.06, 0.06, 0.06)   # 60 m tall letters in world space

text_obj.data.extrude    = 0.06     # letter depth (gives the halo geometry to shade)
text_obj.data.bevel_depth = 0.05   # bevel radius — wider = wider white halo
text_obj.data.space_character = 1.2  # slightly looser kerning for readability

mat_text = bpy.data.materials.new(name="Text_Outline_Mat")
mat_text.use_nodes = True
text_nodes = mat_text.node_tree.nodes
text_links = mat_text.node_tree.links
text_nodes.clear()

node_output_t    = text_nodes.new(type='ShaderNodeOutputMaterial')
node_output_t.location = (400, 0)

# Emission shader — fully unlit, so black stays black regardless of scene lighting.
node_emission_t = text_nodes.new(type='ShaderNodeEmission')
node_emission_t.location = (100, 0)
node_emission_t.inputs['Strength'].default_value = 1.0
text_links.new(node_emission_t.outputs[0], node_output_t.inputs[0])

# LayerWeight Facing: 0 = face on, 1 = edge on. Higher Blend >> wider white halo.
node_weight = text_nodes.new(type='ShaderNodeLayerWeight')
node_weight.location = (-500, 0)
node_weight.inputs['Blend'].default_value = 0.6   # how far the white halo extends from edges

node_ramp_t = text_nodes.new(type='ShaderNodeValToRGB')
node_ramp_t.location = (-200, 0)
node_ramp_t.color_ramp.elements[0].position = 0.2   # facing < 0.2 --> black (front face)
node_ramp_t.color_ramp.elements[0].color    = (0.0, 0.0, 0.0, 1.0)   # front face: pure black
node_ramp_t.color_ramp.elements[1].position = 0.4   # facing > 0.4 --> white (side edges = halo)
node_ramp_t.color_ramp.elements[1].color    = (1.0, 1.0, 1.0, 1.0)   # wide white halo

text_links.new(node_weight.outputs['Facing'], node_ramp_t.inputs[0])
text_links.new(node_ramp_t.outputs[0], node_emission_t.inputs['Color'])

text_obj.data.materials.append(mat_text)

_MONTHS = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']

def _year_label(y):
    month = min(int((y % 1) * 12), 11)
    return f"{_MONTHS[month]} {int(y)}"

# Updates the HUD text every frame — interpolates between YEARS using YEAR_FRAMES
def update_year_text(scene):
    obj = bpy.data.objects.get("Year_Display")
    if obj is None:
        return

    current_frame = scene.frame_current

    if current_frame <= YEAR_FRAMES[0]:
        obj.data.body = _year_label(YEARS[0])
        return
    if current_frame >= YEAR_FRAMES[-1]:
        obj.data.body = _year_label(YEARS[-1])
        return

    for i in range(len(YEAR_FRAMES) - 1):
        f0 = YEAR_FRAMES[i]
        f1 = YEAR_FRAMES[i + 1]
        if f0 <= current_frame <= f1:
            blend = (current_frame - f0) / (f1 - f0)
            current_year = YEARS[i] + blend * (YEARS[i + 1] - YEARS[i])
            obj.data.body = _year_label(current_year)
            return

# Remove only our own handler to avoid breaking other addons 
bpy.app.handlers.frame_change_post[:] = [
    h for h in bpy.app.handlers.frame_change_post
    if getattr(h, '__name__', '') != 'update_year_text'
]
bpy.app.handlers.frame_change_post.append(update_year_text)

# Force an immediate update so the HUD shows the first year straight away
bpy.context.scene.frame_set(1)

print("=" * 60)
print("DONE — Glacier simulation built successfully.")
print(f"  Animation  : frames 1 – {ANIMATION_LENGTH}")
print(f"  Year frames: {dict(zip(YEARS, YEAR_FRAMES))}")
print(f"  FLOW_SPEED : {FLOW_SPEED:.8f} ")
print("=" * 60)
