"""
FLAMEWAVE — Blender geometry generator
Run in Blender's Scripting panel (Text > Run Script)

Two 3/4" EMT conduit arms extend outward and downward from a center post.
Propane leaks through threaded couplings creating a flaming rope effect.
Participants pull chains at the outer spring-mounted ends to excite waves.
Floating inner ends near center trigger a poofer when they sync.
"""

import bpy
import math
from mathutils import Vector, Quaternion

# ── PARAMETERS (edit these freely) ────────────────────────────────────────────

ARM_LENGTH_FT       = 10.0   # length of each conduit arm
ARM_ANGLE_DEG       = 17.5   # drop angle from horizontal (try 15–20)
CENTER_ATTACH_FT    = 9.0    # height where conduit meets center post
POOFER_HEIGHT_FT    = 10.0   # poofer head height (10' rule)

SEGMENTS_PER_ARM    = 4      # EMT sticks per arm; more = more couplings = more flame pts
EMT_OD_IN           = 0.922  # 3/4" EMT outer diameter
EMT_ID_IN           = 0.824  # 3/4" EMT inner diameter
COUPLING_OD_IN      = 1.10   # threaded coupling OD (approx)
COUPLING_LEN_IN     = 1.75   # threaded coupling length

CENTER_POST_OD_IN   = 2.375  # center post (2" pipe OD)
OUTER_POST_OD_IN    = 1.900  # outer post (1.5" pipe OD)
SPRING_COILS        = 10
SPRING_RADIUS_IN    = 0.75
SPRING_LENGTH_FT    = 1.0    # spring free length
CHAIN_LENGTH_FT     = 4.5    # chain hanging from outer end junction

MOUNTAIN_RADIUS     = 350    # metres — sets both ground plane and mountain ring size
PLAYA_TILE_SIZE_M   = 2.5    # metres per texture tile — controls crack density

# ── CONSTANTS ─────────────────────────────────────────────────────────────────

FOOT = 0.3048
INCH = 0.0254


# ── SCENE SETUP ───────────────────────────────────────────────────────────────

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)

bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.length_unit = 'METERS'

# Cycles + GPU — adaptive subdivision on the ground plane.
bpy.context.scene.render.engine = 'CYCLES'
for _attr, _val in [
    ('device',                  'GPU'),
    ('feature_set',             'EXPERIMENTAL'),
    ('dicing_rate',             2.0),
    ('offscreen_dicing_scale',  4.0),
]:
    try:
        setattr(bpy.context.scene.cycles, _attr, _val)
    except (AttributeError, TypeError):
        pass


# ── MATERIALS ─────────────────────────────────────────────────────────────────

def mat(name, color, metallic=0.0, roughness=0.5):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    return m

MAT_EMT      = mat("EMT",      (0.62, 0.62, 0.68), metallic=0.9,  roughness=0.3)
MAT_COUPLING = mat("Coupling", (0.50, 0.50, 0.56), metallic=0.9,  roughness=0.45)
MAT_POST     = mat("Post",     (0.35, 0.35, 0.40), metallic=0.85, roughness=0.5)
MAT_SPRING   = mat("Spring",   (0.72, 0.65, 0.48), metallic=0.95, roughness=0.25)
MAT_CHAIN    = mat("Chain",    (0.28, 0.28, 0.32), metallic=0.95, roughness=0.2)
MAT_POOFER   = mat("Poofer",   (0.80, 0.60, 0.18), metallic=1.0,  roughness=0.15)
MAT_GROUND_PLATE = mat("GroundPlate", (0.4, 0.4, 0.45), metallic=0.8, roughness=0.6)


def make_playa_material():
    """
    Stochastic texture bombing for the playa ground plane.

    A Voronoi texture divides the surface into cells; each cell receives a
    random UV offset before sampling the ground texture maps. This breaks up
    tiling repetition across the large ground plane without requiring a huge
    texture resolution.

    Node graph:
        TexCoord → Mapping (overall scale) ──────────────────────────────────┐
                                           → Voronoi (cell random color)     │
                                             → add offset to scaled UV       │
                                             → Image Texture (Color)  → BSDF │
                                             → Image Texture (Rough)  → BSDF │
                                             → Image Texture (Normal) → Normal Map → BSDF

    TEXTURE PATHS — replace the three PLACEHOLDER strings below with your
    actual file paths, e.g.:
        COLOR_TEX  = "/home/dan/textures/Ground013_4K_Color.jpg"
        ROUGH_TEX  = "/home/dan/textures/Ground013_4K_Roughness.jpg"
        NORMAL_TEX = "/home/dan/textures/Ground013_4K_NormalGL.jpg"
    """

    import os
    # Use the saved .blend file's directory if available, else the repo path
    _blend_dir = os.path.dirname(bpy.data.filepath)
    _repo      = _blend_dir or "/home/dan/sandbox/dnewcome/flamewave"
    _tex_dir   = os.path.join(_repo, "playa-texture")
    COLOR_TEX  = os.path.join(_tex_dir, "Ground031_1K-JPG_Color.jpg")
    ROUGH_TEX  = os.path.join(_tex_dir, "Ground031_1K-JPG_Roughness.jpg")
    NORMAL_TEX = os.path.join(_tex_dir, "Ground031_1K-JPG_NormalGL.jpg")
    DISP_TEX   = os.path.join(_tex_dir, "Ground031_1K-JPG_Displacement.jpg")

    # Displacement scale in metres — playa cracks are shallow, 1–2cm deep
    DISP_SCALE  = 0.015
    DISP_MIDLEVEL = 0.5   # grey = no displacement

    # Tile scale derived from ground size and desired crack density
    TEX_SCALE       = (MOUNTAIN_RADIUS * 2) / PLAYA_TILE_SIZE_M
    # Voronoi cell size relative to scaled UV (controls how large each
    # randomly-offset patch is; 1.0 = one patch per texture tile)
    VORONOI_SCALE   = 1.0
    # How much the random offset can shift UVs (0–1 range; 1.0 = full tile)
    OFFSET_STRENGTH = 1.0

    m = bpy.data.materials.new(name="Playa")
    m.use_nodes = True
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    nodes.clear()

    def N(node_type, x, y):
        n = nodes.new(node_type)
        n.location = (x, y)
        return n

    # ── Outputs ──
    out      = N("ShaderNodeOutputMaterial",  800,  0)
    bsdf     = N("ShaderNodeBsdfPrincipled",  400,  0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # ── Coordinates & overall scale ──
    coord    = N("ShaderNodeTexCoord",       -900,  100)
    mapping  = N("ShaderNodeMapping",        -700,  100)
    mapping.inputs["Scale"].default_value    = (TEX_SCALE, TEX_SCALE, TEX_SCALE)
    links.new(coord.outputs["UV"], mapping.inputs["Vector"])

    # ── Voronoi — provides per-cell random color used as UV offset ──
    voronoi  = N("ShaderNodeTexVoronoi",     -500,  300)
    voronoi.voronoi_dimensions = "2D"
    voronoi.feature             = "F1"
    voronoi.inputs["Scale"].default_value      = VORONOI_SCALE
    voronoi.inputs["Randomness"].default_value = 1.0
    links.new(mapping.outputs["Vector"], voronoi.inputs["Vector"])

    # ── Scale the random color down to use as a subtle offset ──
    offset_scale = N("ShaderNodeVectorMath",  -300,  300)
    offset_scale.operation = "SCALE"
    offset_scale.inputs["Scale"].default_value = OFFSET_STRENGTH
    links.new(voronoi.outputs["Color"], offset_scale.inputs["Vector"])

    # ── Add offset to the scaled UV ──
    add_offset = N("ShaderNodeVectorMath",   -100,  200)
    add_offset.operation = "ADD"
    links.new(mapping.outputs["Vector"],       add_offset.inputs[0])
    links.new(offset_scale.outputs["Vector"],  add_offset.inputs[1])

    # ── Image textures (placeholders) ──
    def img_node(path, label, x, y, colorspace="sRGB"):
        n = N("ShaderNodeTexImage", x, y)
        n.label = label
        try:
            img = bpy.data.images.load(path, check_existing=True)
            img.colorspace_settings.name = colorspace
            n.image = img
        except Exception:
            # Path not found — node stays empty, renders magenta as reminder
            pass
        links.new(add_offset.outputs["Vector"], n.inputs["Vector"])
        return n

    tex_color  = img_node(COLOR_TEX,  "Playa Color",       100,  200)
    tex_rough  = img_node(ROUGH_TEX,  "Playa Roughness",   100,    0, colorspace="Non-Color")
    tex_normal = img_node(NORMAL_TEX, "Playa Normal",      100, -200, colorspace="Non-Color")
    tex_disp   = img_node(DISP_TEX,   "Playa Displacement", 100, -400, colorspace="Non-Color")

    # ── Normal map ──
    normal_map = N("ShaderNodeNormalMap", 350, -150)
    normal_map.inputs["Strength"].default_value = 0.6
    links.new(tex_normal.outputs["Color"], normal_map.inputs["Color"])

    # ── Displacement (Cycles only — ignored by EEVEE) ──
    disp_node = N("ShaderNodeDisplacement", 350, -350)
    disp_node.inputs["Scale"].default_value    = DISP_SCALE
    disp_node.inputs["Midlevel"].default_value = DISP_MIDLEVEL
    links.new(tex_disp.outputs["Color"], disp_node.inputs["Height"])

    # ── Wire into BSDF and Output ──
    links.new(tex_color.outputs["Color"],   bsdf.inputs["Base Color"])
    links.new(tex_rough.outputs["Color"],   bsdf.inputs["Roughness"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(disp_node.outputs["Displacement"], out.inputs["Displacement"])

    try:
        m.cycles.displacement_method = 'DISPLACEMENT'
    except AttributeError:
        pass

    bsdf.inputs["Metallic"].default_value  = 0.0
    bsdf.inputs["Roughness"].default_value = 0.9

    return m

MAT_PLAYA = make_playa_material()


# ── HELPERS ───────────────────────────────────────────────────────────────────

def assign_mat(obj, material):
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)


def cylinder_between(p1, p2, radius, name, material=None, verts=16):
    """Place a cylinder aligned between two points."""
    direction = p2 - p1
    length = direction.length
    if length < 1e-6:
        return None
    mid = (p1 + p2) / 2

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=verts, radius=radius, depth=length, location=mid
    )
    obj = bpy.context.object
    obj.name = name

    z = Vector((0, 0, 1))
    d = direction.normalized()
    dot = max(-1.0, min(1.0, z.dot(d)))
    if abs(dot) < 0.9999:
        axis = z.cross(d).normalized()
        angle = math.acos(dot)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = Quaternion(axis, angle)
    elif dot < 0:
        obj.rotation_mode = 'EULER'
        obj.rotation_euler = (math.pi, 0, 0)

    if material:
        assign_mat(obj, material)
    return obj


# ── COMPUTED GEOMETRY ─────────────────────────────────────────────────────────

angle       = math.radians(ARM_ANGLE_DEG)
arm_len     = ARM_LENGTH_FT  * FOOT
attach_h    = CENTER_ATTACH_FT * FOOT
poofer_h    = POOFER_HEIGHT_FT * FOOT
spring_len  = SPRING_LENGTH_FT * FOOT
coup_l      = COUPLING_LEN_IN * INCH
coup_r      = (COUPLING_OD_IN / 2) * INCH
emt_r       = (EMT_OD_IN / 2) * INCH

# Center: floating ends of each conduit arm meet here
center_attach = Vector((0, 0, attach_h))

# Outer ends: spring + chain attachment (lower than center)
outer_L = Vector((-arm_len * math.cos(angle), 0, attach_h - arm_len * math.sin(angle)))
outer_R = Vector(( arm_len * math.cos(angle), 0, attach_h - arm_len * math.sin(angle)))


# ── GROUND ────────────────────────────────────────────────────────────────────

bpy.ops.mesh.primitive_plane_add(size=MOUNTAIN_RADIUS * 2, location=(0, 0, 0))
ground = bpy.context.object
ground.name = "Playa"
assign_mat(ground, MAT_PLAYA)

# Adaptive subdivision — Cycles tessellates only what the camera sees.
# Requires Cycles + Experimental feature set (set below).
# DICING_RATE: higher = fewer polygons = faster but coarser cracks.
# 2.0 is a good balance on a 4070; drop to 1.0 for final renders.
sub = ground.modifiers.new("Adaptive_Subdiv", 'SUBSURF')
sub.subdivision_type = 'SIMPLE'
sub.levels = 0
sub.render_levels = 6
try:
    sub.use_adaptive_subdivision = True
except AttributeError:
    pass


# ── CENTER POST ───────────────────────────────────────────────────────────────

post_r = (CENTER_POST_OD_IN / 2) * INCH
cylinder_between(
    Vector((0, 0, -0.6)),
    Vector((0, 0, poofer_h + 0.35)),
    post_r, "Center_Post", MAT_POST, verts=12
)

# Ground plate
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.02))
gp = bpy.context.object
gp.name = "Ground_Plate"
gp.scale = (0.4, 0.4, 0.02)
bpy.ops.object.transform_apply(scale=True)
assign_mat(gp, MAT_GROUND_PLATE)


# ── POOFER ASSEMBLY ───────────────────────────────────────────────────────────

# Body
bpy.ops.mesh.primitive_cylinder_add(
    vertices=12, radius=0.065, depth=0.18,
    location=(0, 0, poofer_h + 0.09)
)
pb = bpy.context.object
pb.name = "Poofer_Body"
assign_mat(pb, MAT_POOFER)

# Nozzle
bpy.ops.mesh.primitive_cone_add(
    vertices=12, radius1=0.065, radius2=0.025, depth=0.12,
    location=(0, 0, poofer_h + 0.24)
)
pn = bpy.context.object
pn.name = "Poofer_Nozzle"
assign_mat(pn, MAT_POOFER)

# Solenoid valve block (side-mounted)
bpy.ops.mesh.primitive_cube_add(size=1, location=(post_r + 0.06, 0, poofer_h - 0.15))
sv = bpy.context.object
sv.name = "Solenoid_Valve"
sv.scale = (0.06, 0.04, 0.08)
bpy.ops.object.transform_apply(scale=True)
assign_mat(sv, MAT_POOFER)


# ── CONDUIT ARMS ─────────────────────────────────────────────────────────────

def build_arm(start, end, label, n_seg):
    """
    Build conduit arm: alternating EMT sections and threaded couplings.
    start = floating end (near center post)
    end   = spring/chain end (outer post)
    """
    direction = (end - start).normalized()
    total_len = (end - start).length
    seg_len = total_len / n_seg

    for i in range(n_seg):
        p_seg_start = start + direction * (seg_len * i)
        p_seg_end   = start + direction * (seg_len * (i + 1))

        # Coupling gap at start of each segment (except first)
        emt_start = p_seg_start + direction * (coup_l / 2 if i > 0 else 0)
        # Coupling gap at end of each segment (except last)
        emt_end   = p_seg_end   - direction * (coup_l / 2 if i < n_seg - 1 else 0)

        cylinder_between(emt_start, emt_end, emt_r, f"EMT_{label}_{i}", MAT_EMT, verts=12)

        # Coupling at joint between segments
        if i < n_seg - 1:
            joint = p_seg_end
            cylinder_between(
                joint - direction * coup_l / 2,
                joint + direction * coup_l / 2,
                coup_r, f"Coupling_{label}_{i}", MAT_COUPLING, verts=12
            )

build_arm(center_attach, outer_L, "L", SEGMENTS_PER_ARM)
build_arm(center_attach, outer_R, "R", SEGMENTS_PER_ARM)


# ── OUTER POSTS ───────────────────────────────────────────────────────────────

outer_post_r = (OUTER_POST_OD_IN / 2) * INCH

for label, outer_end in [("L", outer_L), ("R", outer_R)]:
    spring_anchor = Vector((outer_end.x, outer_end.y, outer_end.z + spring_len))
    post_top      = spring_anchor + Vector((0, 0, 0.25))
    post_bot      = Vector((outer_end.x, outer_end.y, -0.4))

    cylinder_between(post_bot, post_top, outer_post_r, f"Outer_Post_{label}", MAT_POST, verts=12)

    # Cap plate at post top
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=outer_post_r * 2.5, depth=0.015,
        location=(outer_end.x, outer_end.y, spring_anchor.z + 0.015)
    )
    cap = bpy.context.object
    cap.name = f"Post_Cap_{label}"
    assign_mat(cap, MAT_POST)

    # Ground plate for outer post
    bpy.ops.mesh.primitive_cube_add(size=1, location=(outer_end.x, outer_end.y, 0.02))
    ogp = bpy.context.object
    ogp.name = f"Outer_Ground_Plate_{label}"
    ogp.scale = (0.25, 0.25, 0.02)
    bpy.ops.object.transform_apply(scale=True)
    assign_mat(ogp, MAT_GROUND_PLATE)


# ── SPRINGS ───────────────────────────────────────────────────────────────────

def create_spring(bottom, top, n_coils, coil_r, name, material=None):
    """Helical spring as a NURBS curve with bevel."""
    cdata = bpy.data.curves.new(name=name, type='CURVE')
    cdata.dimensions = '3D'
    cdata.bevel_depth = 0.004
    cdata.bevel_resolution = 3
    cdata.use_fill_caps = True

    pts_per_coil = 16
    total_pts = n_coils * pts_per_coil + 1
    spline = cdata.splines.new('NURBS')
    spline.points.add(total_pts - 1)

    for i in range(total_pts):
        t = i / (total_pts - 1)
        a = t * n_coils * 2 * math.pi
        x = bottom.x + coil_r * math.cos(a)
        y = bottom.y + coil_r * math.sin(a)
        z = bottom.z + t * (top.z - bottom.z)
        spline.points[i].co = (x, y, z, 1.0)

    spline.use_endpoint_u = True
    obj = bpy.data.objects.new(name, cdata)
    bpy.context.collection.objects.link(obj)
    if material:
        obj.data.materials.append(material)
    return obj

coil_r = SPRING_RADIUS_IN * INCH

for label, outer_end in [("L", outer_L), ("R", outer_R)]:
    spring_bottom = outer_end
    spring_top    = Vector((outer_end.x, outer_end.y, outer_end.z + spring_len))
    create_spring(spring_bottom, spring_top, SPRING_COILS, coil_r, f"Spring_{label}", MAT_SPRING)


# ── CHAINS ────────────────────────────────────────────────────────────────────

def create_chain(anchor, length, name, material=None):
    """Chain as alternating torus links hanging from anchor."""
    link_major = 0.022
    link_minor = 0.005
    spacing = link_major * 1.8
    n_links = int(length / spacing)
    n_links = min(n_links, 40)  # cap for viewport performance

    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)

    for i in range(n_links):
        z = anchor.z - i * spacing
        rot = (math.pi / 2, 0, math.pi / 2 if i % 2 == 0 else 0)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=link_major,
            minor_radius=link_minor,
            major_segments=16,
            minor_segments=6,
            location=(anchor.x, anchor.y, z),
            rotation=rot
        )
        link = bpy.context.object
        link.name = f"{name}_{i:03d}"
        bpy.context.scene.collection.objects.unlink(link)
        col.objects.link(link)
        if material:
            link.data.materials.append(material)

chain_len = CHAIN_LENGTH_FT * FOOT
for label, outer_end in [("L", outer_L), ("R", outer_R)]:
    create_chain(outer_end, chain_len, f"Chain_{label}", MAT_CHAIN)


# ── TRIGGER INDICATOR (floating end proximity zone) ───────────────────────────
# Visual placeholder showing the trigger zone near center post
# Replace with actual sensor geometry when design is finalized

# ── MECHANICAL LIMIT SWITCHES ────────────────────────────────────────────────
#
# One roller-lever limit switch per arm, mounted on a bracket off the center
# post. The floating conduit tip carries a striker plate; when the tip rises
# (or falls) to the trigger height it contacts the roller and closes the switch.
# Both switches wired in series → solenoid only fires when both close together.
#
# SWITCH_OFFSET_Y: how far from post center the switch body sits (Y axis here
#   is perpendicular to the arm run, so each switch is offset to its own side)
# TRIGGER_HEIGHT:  Z at which the conduit tip trips the switch. Adjust to tune
#   sync difficulty — higher = tip must travel further = harder to sync.

SWITCH_OFFSET_X  = post_r + 0.045   # switch body clears the post
TRIGGER_HEIGHT   = attach_h - 0.05  # slightly below attach_h; tune on site

MAT_SWITCH       = mat("Switch_Body",   (0.15, 0.15, 0.18), metallic=0.5, roughness=0.6)
MAT_SWITCH_LEVER = mat("Switch_Lever",  (0.55, 0.55, 0.60), metallic=0.9, roughness=0.3)
MAT_STRIKER      = mat("Striker_Plate", (0.70, 0.65, 0.45), metallic=1.0, roughness=0.2)

for label, sign in [("L", -1), ("R", 1)]:
    sx = sign * SWITCH_OFFSET_X

    # ── Mounting bracket: vertical flat bar off post ──
    bracket_top = Vector((sx, 0, TRIGGER_HEIGHT + 0.06))
    bracket_bot = Vector((sx, 0, TRIGGER_HEIGHT - 0.10))
    cylinder_between(bracket_bot, bracket_top, 0.006, f"Switch_Bracket_{label}", MAT_POST, verts=6)

    # ── Switch body (Honeywell micro-switch footprint ~31×16×14 mm) ──
    bpy.ops.mesh.primitive_cube_add(size=1, location=(sx, 0, TRIGGER_HEIGHT))
    sw_body = bpy.context.object
    sw_body.name = f"Switch_Body_{label}"
    sw_body.scale = (0.016, 0.031, 0.014)
    bpy.ops.object.transform_apply(scale=True)
    assign_mat(sw_body, MAT_SWITCH)

    # ── Roller lever arm (extends inward toward conduit tip) ──
    lever_root = Vector((sx, 0, TRIGGER_HEIGHT + 0.007))
    lever_tip  = Vector((sx * 0.3, 0, TRIGGER_HEIGHT + 0.035))
    cylinder_between(lever_root, lever_tip, 0.003, f"Switch_Lever_{label}", MAT_SWITCH_LEVER, verts=6)

    # Roller ball at lever tip
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.006, segments=8, ring_count=6,
        location=lever_tip
    )
    roller = bpy.context.object
    roller.name = f"Switch_Roller_{label}"
    assign_mat(roller, MAT_SWITCH_LEVER)

    # ── Striker plate on floating conduit tip ──
    # Small angle-iron tab welded/clamped to the conduit end near center_attach.
    # Positioned to contact the roller when the tip reaches TRIGGER_HEIGHT.
    striker_pos = Vector((sign * (post_r + 0.03), 0, TRIGGER_HEIGHT))
    bpy.ops.mesh.primitive_cube_add(size=1, location=striker_pos)
    striker = bpy.context.object
    striker.name = f"Striker_{label}"
    striker.scale = (0.008, 0.025, 0.025)
    bpy.ops.object.transform_apply(scale=True)
    assign_mat(striker, MAT_STRIKER)


# ── SKY & WORLD ───────────────────────────────────────────────────────────────
#
# Nishita sky model — physically-based sun/atmosphere. Adjust SUN_ELEVATION
# and SUN_ROTATION to change time of day and direction.
#
# Black Rock Desert sits at ~3900 ft elevation in a high-desert basin.
# The surrounding ranges (Calico Hills NE, Jackson Mtns N, Kamma Mtns S)
# are 10–20 miles out and rise maybe 2000 ft above the playa floor, so they
# sit low on the horizon — modelled as a gentle ridgeline ring below.
#
# These parameters match late afternoon (golden hour) facing roughly SW,
# which gives the dramatic side-lighting typical of BRC event photography.

SUN_ELEVATION_DEG = 22.0   # degrees above horizon (22 = ~2hrs before sunset)
SUN_ROTATION_DEG  = 230.0  # compass bearing of sun (230 = SW)
AIR_DENSITY       = 1.0
DUST_DENSITY      = 0.8    # playa dust haze
OZONE_DENSITY     = 1.0

world = bpy.context.scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
wnodes = world.node_tree.nodes
wlinks = world.node_tree.links
wnodes.clear()

w_out = wnodes.new("ShaderNodeOutputWorld")
w_out.location = (300, 0)
sky_tex = wnodes.new("ShaderNodeTexSky")
sky_tex.location = (0, 0)
# Nishita (2.90+) gives the most accurate desert sky; fall back to
# Hosek-Wilkie which is physically-based and available in all versions.
sky_types = sky_tex.bl_rna.properties['sky_type'].enum_items.keys()
if 'NISHITA' in sky_types:
    sky_tex.sky_type      = 'NISHITA'
    sky_tex.sun_elevation = math.radians(SUN_ELEVATION_DEG)
    sky_tex.sun_rotation  = math.radians(SUN_ROTATION_DEG)
    sky_tex.air_density   = AIR_DENSITY
    sky_tex.dust_density  = DUST_DENSITY
    sky_tex.ozone_density = OZONE_DENSITY
    # Built-in sun disk with atmospheric scattering — no emissive sphere needed
    try:
        sky_tex.sun_disc      = True
        sky_tex.sun_size      = math.radians(0.545)   # real solar angular diameter
        sky_tex.sun_intensity = 1.0
    except AttributeError:
        pass
else:
    # Hosek-Wilkie fallback (pre-2.90)
    sky_tex.sky_type      = 'HOSEK_WILKIE'
    sky_tex.sun_elevation = math.radians(SUN_ELEVATION_DEG)
    sky_tex.sun_rotation  = math.radians(SUN_ROTATION_DEG)
    sky_tex.turbidity     = 4.0
    sky_tex.ground_albedo = 0.35
wlinks.new(sky_tex.outputs["Color"], w_out.inputs["Surface"])

# Sun lamp — directional light matching sky sun direction.
bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
sun_lamp = bpy.context.object
sun_lamp.name = "Sun"
sun_lamp.data.energy = 5.0
sun_lamp.data.color  = (1.0, 0.95, 0.82)
sun_lamp.data.angle  = math.radians(0.53)
sun_lamp.rotation_euler = (
    math.radians(90 - SUN_ELEVATION_DEG),
    0,
    math.radians(SUN_ROTATION_DEG + 90)
)

# Sun disk is rendered by Nishita sky texture (sun_disc=True above).
# Emissive sphere fallback only needed if Nishita is unavailable.
if 'NISHITA' not in sky_tex.bl_rna.properties['sky_type'].enum_items.keys():
    _sun_dist = MOUNTAIN_RADIUS * 0.92
    _sun_az   = math.radians(SUN_ROTATION_DEG + 180)
    _sun_el   = math.radians(SUN_ELEVATION_DEG)
    _sun_pos  = (
        _sun_dist * math.cos(_sun_el) * math.sin(_sun_az),
        _sun_dist * math.cos(_sun_el) * math.cos(_sun_az),
        _sun_dist * math.sin(_sun_el),
    )
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=18, segments=64, ring_count=32, location=_sun_pos
    )
    sun_disk = bpy.context.object
    sun_disk.name = "Sun_Disk"
    try:
        sun_disk.visible_shadow = False
    except AttributeError:
        pass
    mat_sun = bpy.data.materials.new("Sun_Emission")
    mat_sun.use_nodes = True
    mat_sun.node_tree.nodes.clear()
    _sout = mat_sun.node_tree.nodes.new("ShaderNodeOutputMaterial")
    _semi = mat_sun.node_tree.nodes.new("ShaderNodeEmission")
    _semi.inputs["Color"].default_value    = (1.0, 0.97, 0.85, 1.0)
    _semi.inputs["Strength"].default_value = 600.0
    mat_sun.node_tree.links.new(_semi.outputs["Emission"], _sout.inputs["Surface"])
    sun_disk.data.materials.append(mat_sun)

# Nishita handles atmospheric scattering natively — no world volume needed.

# ── COMPOSITOR — glare/bloom on the sun ───────────────────────────────────────
bpy.context.scene.use_nodes = True
ctree = getattr(bpy.context.scene, 'node_tree', None)
if ctree is not None:
    cnodes = ctree.nodes
    clinks = ctree.links
    cnodes.clear()

    rl    = cnodes.new("CompositorNodeRLayers");   rl.location   = (-300, 0)
    glare = cnodes.new("CompositorNodeGlare");     glare.location = (0, 0)
    comp  = cnodes.new("CompositorNodeComposite"); comp.location  = (300, 0)

    glare.glare_type = 'FOG_GLOW'
    glare.threshold  = 0.6
    glare.size       = 8
    for _attr, _val in [('quality', 'HIGH'), ('use_extended_limits', False)]:
        try:
            setattr(glare, _attr, _val)
        except (AttributeError, TypeError):
            pass

    clinks.new(rl.outputs["Image"],    glare.inputs["Image"])
    clinks.new(glare.outputs["Image"], comp.inputs["Image"])
else:
    print("Compositor: scene.node_tree unavailable — skipping glare setup")


# ── MOUNTAIN RANGE ────────────────────────────────────────────────────────────
#
# Low ridgeline ring representing the distant mountain ranges visible from
# Black Rock Desert. Placed at MOUNTAIN_RADIUS meters from origin.
# Heights are generated from summed sine waves seeded to give a plausible
# Nevada Basin-and-Range silhouette — gentle, broad ridges, not sharp peaks.

import bmesh, random

MOUNTAIN_SEGMENTS = 180    # horizontal resolution of the ring
MOUNTAIN_BASE_Z   = -3.0   # below ground so bottom edge never shows

random.seed(7)             # fixed seed for reproducible silhouette


def make_mountain_material():
    """
    Nevada Basin-and-Range rock material.

    Uses image textures when available (drop Rock/Cliff packs from ambientCG
    into a 'mountain-texture/' folder beside the .blend file). Falls back to
    procedural noise when textures are missing — nodes are wired either way.

    Recommended ambientCG pack: Rock022 or Cliff001 (4K JPG)
    Expected files:
        mountain-texture/Rock_Color.jpg
        mountain-texture/Rock_Roughness.jpg
        mountain-texture/Rock_NormalGL.jpg

    The procedural noise layers stay active and are multiplied with the
    image texture when present, adding large-scale variation so the texture
    doesn't tile obviously across 700m of mountain ring.
    """
    m = bpy.data.materials.new("Mountains")
    m.use_nodes = True
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    nodes.clear()

    def N(t, x, y):
        n = nodes.new(t)
        n.location = (x, y)
        return n

    out  = N("ShaderNodeOutputMaterial", 900, 0)
    bsdf = N("ShaderNodeBsdfPrincipled", 550, 0)
    bsdf.inputs["Metallic"].default_value  = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # UV coordinates — cylindrical UVs baked into the mesh at generation time
    coord   = N("ShaderNodeTexCoord", -800, 100)
    mapping = N("ShaderNodeMapping",  -600, 100)
    mapping.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    links.new(coord.outputs["UV"], mapping.inputs["Vector"])

    # ── Large-scale zone noise — broad light/shadow banding on the range ──
    noise_lg = N("ShaderNodeTexNoise", -350, 300)
    noise_lg.inputs["Scale"].default_value      = 0.8
    noise_lg.inputs["Detail"].default_value     = 4.0
    noise_lg.inputs["Roughness"].default_value  = 0.6
    noise_lg.inputs["Distortion"].default_value = 0.2
    links.new(mapping.outputs["Vector"], noise_lg.inputs["Vector"])

    # ── Medium rock texture noise — primary color variation ──
    noise_md = N("ShaderNodeTexNoise", -350, 100)
    noise_md.inputs["Scale"].default_value      = 4.0
    noise_md.inputs["Detail"].default_value     = 8.0
    noise_md.inputs["Roughness"].default_value  = 0.7
    noise_md.inputs["Distortion"].default_value = 0.4
    links.new(mapping.outputs["Vector"], noise_md.inputs["Vector"])

    # ── Fine surface noise — roughness variation and bump ──
    noise_sm = N("ShaderNodeTexNoise", -350, -100)
    noise_sm.inputs["Scale"].default_value      = 18.0
    noise_sm.inputs["Detail"].default_value     = 12.0
    noise_sm.inputs["Roughness"].default_value  = 0.75
    noise_sm.inputs["Distortion"].default_value = 0.1
    links.new(mapping.outputs["Vector"], noise_sm.inputs["Vector"])

    # Mix large + medium noise to get overall color driver
    mix_noise = N("ShaderNodeMixRGB", -100, 200)
    mix_noise.blend_type = 'MULTIPLY'
    mix_noise.inputs["Fac"].default_value = 0.6
    links.new(noise_lg.outputs["Fac"], mix_noise.inputs["Color1"])
    links.new(noise_md.outputs["Fac"], mix_noise.inputs["Color2"])

    # ── Procedural color ramp — dark basalt → mid brown → light alkali dust ──
    ramp = N("ShaderNodeValToRGB", 120, 300)
    ramp.color_ramp.interpolation = 'EASE'
    els = ramp.color_ramp.elements
    els[0].position = 0.0;  els[0].color = (0.05, 0.04, 0.03, 1.0)
    els.new(0.35);           els[1].color = (0.10, 0.08, 0.06, 1.0)
    els.new(0.62);           els[2].color = (0.16, 0.12, 0.09, 1.0)
    els.new(0.82);           els[3].color = (0.24, 0.19, 0.13, 1.0)
    els[4].position = 1.0;  els[4].color = (0.32, 0.27, 0.20, 1.0)
    links.new(mix_noise.outputs["Color"], ramp.inputs["Fac"])

    # ── Image texture (optional) — drop Rock/Cliff pack into mountain-texture/ ──
    import os
    _blend_dir = os.path.dirname(bpy.data.filepath)
    _repo      = _blend_dir or "/home/dan/sandbox/dnewcome/flamewave"
    _mtn_dir   = os.path.join(_repo, "mountain-texture")

    def mtn_img(fname, label, x, y, colorspace="sRGB"):
        n = N("ShaderNodeTexImage", x, y)
        n.label = label
        n.projection = 'FLAT'   # cylindrical UVs handle wrapping correctly
        try:
            img = bpy.data.images.load(os.path.join(_mtn_dir, fname), check_existing=True)
            img.colorspace_settings.name = colorspace
            n.image = img
        except Exception:
            pass
        links.new(mapping.outputs["Vector"], n.inputs["Vector"])
        return n

    tex_col  = mtn_img("Rock050_2K-JPG_Color.jpg",     "Rock Color",     350,  300)
    tex_rgh  = mtn_img("Rock050_2K-JPG_Roughness.jpg", "Rock Roughness", 350,  100, "Non-Color")
    tex_nrm  = mtn_img("Rock050_2K-JPG_NormalGL.jpg",  "Rock Normal",    350, -100, "Non-Color")

    # Mix image color with procedural ramp (multiply keeps large-scale variation)
    mix_col = N("ShaderNodeMixRGB", 560, 300)
    mix_col.blend_type = 'MULTIPLY'
    mix_col.inputs["Fac"].default_value = 1.0   # set to 0 to use procedural only
    links.new(ramp.outputs["Color"],       mix_col.inputs["Color1"])
    links.new(tex_col.outputs["Color"],    mix_col.inputs["Color2"])
    links.new(mix_col.outputs["Color"],    bsdf.inputs["Base Color"])

    # Roughness — image if loaded, else noise
    rough_ramp = N("ShaderNodeValToRGB", 120, 100)
    rough_ramp.color_ramp.elements[0].color = (0.72, 0.72, 0.72, 1.0)
    rough_ramp.color_ramp.elements[1].color = (0.95, 0.95, 0.95, 1.0)
    links.new(noise_sm.outputs["Fac"], rough_ramp.inputs["Fac"])
    mix_rgh = N("ShaderNodeMixRGB", 560, 100)
    mix_rgh.blend_type = 'MIX'
    mix_rgh.inputs["Fac"].default_value = 1.0
    links.new(rough_ramp.outputs["Color"], mix_rgh.inputs["Color1"])
    links.new(tex_rgh.outputs["Color"],    mix_rgh.inputs["Color2"])
    links.new(mix_rgh.outputs["Color"],    bsdf.inputs["Roughness"])

    # Normal — image normal map + procedural bump combined
    normal_map = N("ShaderNodeNormalMap", 560, -100)
    normal_map.inputs["Strength"].default_value = 1.2
    links.new(tex_nrm.outputs["Color"], normal_map.inputs["Color"])

    bump = N("ShaderNodeBump", 560, -280)
    bump.inputs["Strength"].default_value  = 0.4
    bump.inputs["Distance"].default_value  = 0.5
    links.new(noise_sm.outputs["Fac"],      bump.inputs["Height"])
    links.new(normal_map.outputs["Normal"], bump.inputs["Normal"])
    links.new(bump.outputs["Normal"],       bsdf.inputs["Normal"])

    return m


def mountain_height(angle):
    """Sum of sine waves giving a low, lumpy Nevada ridgeline profile."""
    h = (
        18 * math.sin(1.1 * angle + 0.40) +
        22 * math.sin(1.7 * angle + 1.80) +
        12 * math.sin(2.9 * angle + 0.95) +
        8  * math.sin(4.3 * angle + 2.30) +
        5  * math.sin(6.1 * angle + 1.10) +
        3  * math.sin(9.0 * angle + 0.60) +
        random.uniform(-2, 2)
    )
    return max(h + 28, 4)   # clamp so ridgeline always clears horizon

mesh_mtns = bpy.data.meshes.new("Mountain_Range")
bm = bmesh.new()
uv_layer = bm.loops.layers.uv.new("UVMap")

# Tile the texture every MTN_TEX_TILE_M metres along the ring circumference
MTN_TEX_TILE_M = 40.0
circumference  = 2 * math.pi * MOUNTAIN_RADIUS
max_h          = 60.0   # approximate max mountain height for V normalisation

verts_bot, verts_top = [], []
heights = []
for i in range(MOUNTAIN_SEGMENTS):
    a = 2 * math.pi * i / MOUNTAIN_SEGMENTS
    x = MOUNTAIN_RADIUS * math.cos(a)
    y = MOUNTAIN_RADIUS * math.sin(a)
    h = mountain_height(a)
    heights.append(h)
    verts_bot.append(bm.verts.new((x, y, MOUNTAIN_BASE_Z)))
    verts_top.append(bm.verts.new((x, y, h)))

bm.verts.ensure_lookup_table()

for i in range(MOUNTAIN_SEGMENTS):
    j = (i + 1) % MOUNTAIN_SEGMENTS

    # U: arc distance along ring, tiled every MTN_TEX_TILE_M metres
    u0 = (i / MOUNTAIN_SEGMENTS * circumference) / MTN_TEX_TILE_M
    u1 = (j / MOUNTAIN_SEGMENTS * circumference) / MTN_TEX_TILE_M

    # V: 0 at bottom, 1 at approximate max height
    v_bot0 = 0.0
    v_top0 = heights[i]  / max_h
    v_bot1 = 0.0
    v_top1 = heights[j]  / max_h

    face = bm.faces.new([verts_bot[i], verts_bot[j], verts_top[j], verts_top[i]])
    face.loops[0][uv_layer].uv = (u0, v_bot0)
    face.loops[1][uv_layer].uv = (u1, v_bot1)
    face.loops[2][uv_layer].uv = (u1, v_top1)
    face.loops[3][uv_layer].uv = (u0, v_top0)

bm.to_mesh(mesh_mtns)
bm.free()

obj_mtns = bpy.data.objects.new("Mountain_Range", mesh_mtns)
bpy.context.collection.objects.link(obj_mtns)
assign_mat(obj_mtns, make_mountain_material())

# Mountains are background scenery — disable shadow participation so the
# closed ring doesn't self-shadow and doesn't cast on the scene.
try:
    obj_mtns.visible_shadow = False          # Blender 3.0+
except AttributeError:
    try:
        obj_mtns.cycles_visibility.shadow = False   # Blender 2.8x
    except AttributeError:
        pass


# ── CLOUDS ────────────────────────────────────────────────────────────────────
#
# Volumetric clouds using sampled noise — two stacked Noise Texture nodes
# (coarse shape + fine turbulent detail) multiplied together and fed through
# a ColorRamp into a Principled Volume shader.
#
# Each cloud is a flat box domain at cloud height. Several are scattered
# across the sky at different positions, sizes, and slight height offsets
# for a natural cumulus scatter appropriate to a hot desert afternoon.
#
# NOTE: volumetric rendering adds render time. If previewing in solid/LookDev
# mode the volumes show as plain boxes — switch to Rendered view to see them.
# Lower CLOUD_STEP_SIZE for sharper detail (slower) or raise it for faster
# previews (puffier/softer edges).
#
# Tuning:
#   CLOUD_HEIGHT       — base altitude of cloud layer
#   CLOUD_DENSITY      — overall opacity (0.02–0.08 for scattered desert cumulus)
#   RAMP_POS           — ColorRamp black point; push right to thin clouds out,
#                        left to make them denser/more solid
#   NOISE_SCALE_COARSE — large cloud shape frequency
#   NOISE_SCALE_DETAIL — turbulent wisps on the edges

CLOUD_HEIGHT        = 120.0   # metres above ground
CLOUD_STEP_SIZE     = 0.8     # volume step size (lower = more detail, slower)
CLOUD_DENSITY       = 0.04    # scatter density
NOISE_SCALE_COARSE  = 0.6
NOISE_SCALE_DETAIL  = 2.8
RAMP_POS            = 0.45    # density threshold — raise to thin clouds out


def make_cloud_material():
    m = bpy.data.materials.new("Cloud")
    m.use_nodes = True
    m.blend_method = 'HASHED'
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    nodes.clear()

    def N(t, x, y):
        n = nodes.new(t)
        n.location = (x, y)
        return n

    out   = N("ShaderNodeOutputMaterial", 900, 0)
    vol   = N("ShaderNodeVolumePrincipled", 600, 0)
    vol.inputs["Density"].default_value         = 0.0   # driven by noise
    vol.inputs["Anisotropy"].default_value       = 0.3   # forward scattering
    vol.inputs["Absorption Color"].default_value = (0.95, 0.95, 1.0, 1.0)
    # "Scatter Color" in 3.x+, plain "Color" in 2.x
    scatter_key = "Scatter Color" if "Scatter Color" in vol.inputs else "Color"
    vol.inputs[scatter_key].default_value        = (1.0, 1.0, 1.0, 1.0)
    links.new(vol.outputs["Volume"], out.inputs["Volume"])

    coord   = N("ShaderNodeTexCoord",   -700, 100)
    mapping = N("ShaderNodeMapping",    -500, 100)

    # Coarse noise — overall cloud shape
    noise_c = N("ShaderNodeTexNoise", -250, 200)
    noise_c.inputs["Scale"].default_value      = NOISE_SCALE_COARSE
    noise_c.inputs["Detail"].default_value     = 6.0
    noise_c.inputs["Roughness"].default_value  = 0.65
    noise_c.inputs["Distortion"].default_value = 0.3
    links.new(mapping.outputs["Vector"], noise_c.inputs["Vector"])

    # Fine noise — wispy turbulent detail
    noise_f = N("ShaderNodeTexNoise", -250, 0)
    noise_f.inputs["Scale"].default_value      = NOISE_SCALE_DETAIL
    noise_f.inputs["Detail"].default_value     = 8.0
    noise_f.inputs["Roughness"].default_value  = 0.75
    noise_f.inputs["Distortion"].default_value = 0.5
    links.new(mapping.outputs["Vector"], noise_f.inputs["Vector"])

    # Multiply coarse × detail to get cloud density field
    multiply = N("ShaderNodeMath", 50, 100)
    multiply.operation = "MULTIPLY"
    links.new(noise_c.outputs["Fac"], multiply.inputs[0])
    links.new(noise_f.outputs["Fac"], multiply.inputs[1])

    # ColorRamp — controls density threshold and falloff
    ramp = N("ShaderNodeValToRGB", 250, 100)
    ramp.color_ramp.interpolation = 'EASE'
    ramp.color_ramp.elements[0].position = RAMP_POS
    ramp.color_ramp.elements[0].color    = (0.0, 0.0, 0.0, 1.0)
    ramp.color_ramp.elements[1].position = min(RAMP_POS + 0.35, 1.0)
    ramp.color_ramp.elements[1].color    = (1.0, 1.0, 1.0, 1.0)
    links.new(multiply.outputs["Value"], ramp.inputs["Fac"])

    # Scale ramp output to density
    density_scale = N("ShaderNodeMath", 480, 100)
    density_scale.operation = "MULTIPLY"
    density_scale.inputs[1].default_value = CLOUD_DENSITY
    links.new(ramp.outputs["Color"], density_scale.inputs[0])
    links.new(density_scale.outputs["Value"], vol.inputs["Density"])

    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    return m


def add_cloud(cx, cy, width, depth, thickness, height_offset=0.0, seed_offset=0):
    """Place a single cloud volume box in the sky."""
    z = CLOUD_HEIGHT + height_offset
    bpy.ops.mesh.primitive_cube_add(location=(cx, cy, z))
    obj = bpy.context.object
    obj.name = f"Cloud_{seed_offset:02d}"
    obj.scale = (width / 2, depth / 2, thickness / 2)
    bpy.ops.object.transform_apply(scale=True)

    cloud_mat = make_cloud_material()
    assign_mat(obj, cloud_mat)

    # Per-cloud noise offset so they don't all look identical
    for node in obj.material_slots[0].material.node_tree.nodes:
        if node.type == 'MAPPING':
            node.inputs["Location"].default_value = (
                seed_offset * 3.7,
                seed_offset * 1.3,
                0.0
            )
    return obj


# Scattered cumulus — positions chosen to frame the sculpture from camera
# without blocking the sky directly overhead
add_cloud( 60,  120, 80, 40, 18,  0.0, seed_offset=0)
add_cloud(-90,   80, 60, 30, 14,  8.0, seed_offset=1)
add_cloud( 30, -140, 70, 35, 20, -5.0, seed_offset=2)
add_cloud(140,   30, 55, 28, 16,  3.0, seed_offset=3)
add_cloud(-50,  160, 90, 45, 22,  6.0, seed_offset=4)


# ── CAMERA ────────────────────────────────────────────────────────────────────

# Three-quarter view camera
bpy.ops.object.camera_add(
    location=(9, -13, 4.5),
    rotation=(math.radians(72), 0, math.radians(34))
)
cam = bpy.context.object
cam.name = "Camera_Main"
cam.data.lens = 35
bpy.context.scene.camera = cam


# ── SUMMARY ───────────────────────────────────────────────────────────────────

outer_h_ft = outer_L.z / FOOT
total_span_ft = (outer_R.x - outer_L.x) / FOOT

print("=" * 50)
print("FLAMEWAVE — geometry generated")
print(f"  Arm angle:          {ARM_ANGLE_DEG}°")
print(f"  Center attach:      {CENTER_ATTACH_FT:.1f} ft")
print(f"  Outer end height:   {outer_h_ft:.2f} ft")
print(f"  Total span:         {total_span_ft:.2f} ft")
print(f"  Segments per arm:   {SEGMENTS_PER_ARM} ({SEGMENTS_PER_ARM - 1} couplings)")
print(f"  Chain bottom:       {(outer_L.z - CHAIN_LENGTH_FT * FOOT) / FOOT:.2f} ft off ground")
print("=" * 50)
