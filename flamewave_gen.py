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

    COLOR_TEX  = "PLACEHOLDER_Color.jpg"
    ROUGH_TEX  = "PLACEHOLDER_Roughness.jpg"
    NORMAL_TEX = "PLACEHOLDER_NormalGL.jpg"

    # Overall UV scale — higher = texture tiles more densely
    TEX_SCALE       = 8.0
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

    tex_color  = img_node(COLOR_TEX,  "Playa Color",    100,  200)
    tex_rough  = img_node(ROUGH_TEX,  "Playa Roughness", 100,   0, colorspace="Non-Color")
    tex_normal = img_node(NORMAL_TEX, "Playa Normal",    100, -200, colorspace="Non-Color")

    # ── Normal map ──
    normal_map = N("ShaderNodeNormalMap",  350, -150)
    normal_map.inputs["Strength"].default_value = 0.6
    links.new(tex_normal.outputs["Color"], normal_map.inputs["Color"])

    # ── Wire into BSDF ──
    links.new(tex_color.outputs["Color"],  bsdf.inputs["Base Color"])
    links.new(tex_rough.outputs["Color"],  bsdf.inputs["Roughness"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

    # Playa is very non-metallic, slightly subsurface-ish
    bsdf.inputs["Metallic"].default_value  = 0.0
    bsdf.inputs["Roughness"].default_value = 0.9  # fallback if texture missing

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

bpy.ops.mesh.primitive_plane_add(size=25, location=(0, 0, 0))
ground = bpy.context.object
ground.name = "Playa"
assign_mat(ground, MAT_PLAYA)


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
sky_tex.sky_type       = 'NISHITA'
sky_tex.sun_elevation  = math.radians(SUN_ELEVATION_DEG)
sky_tex.sun_rotation   = math.radians(SUN_ROTATION_DEG)
sky_tex.air_density    = AIR_DENSITY
sky_tex.dust_density   = DUST_DENSITY
sky_tex.ozone_density  = OZONE_DENSITY
wlinks.new(sky_tex.outputs["Color"], w_out.inputs["Surface"])

# Sun lamp — matches Nishita sky direction so shadows are consistent.
# Use for EEVEE; Cycles can render directly from the sky texture.
bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
sun_lamp = bpy.context.object
sun_lamp.name = "Sun"
sun_lamp.data.energy = 5.0
sun_lamp.data.color  = (1.0, 0.95, 0.82)   # warm late-afternoon tint
sun_lamp.data.angle  = math.radians(0.53)   # solar disk angular size
sun_lamp.rotation_euler = (
    math.radians(90 - SUN_ELEVATION_DEG),
    0,
    math.radians(SUN_ROTATION_DEG + 90)
)


# ── MOUNTAIN RANGE ────────────────────────────────────────────────────────────
#
# Low ridgeline ring representing the distant mountain ranges visible from
# Black Rock Desert. Placed at MOUNTAIN_RADIUS meters from origin.
# Heights are generated from summed sine waves seeded to give a plausible
# Nevada Basin-and-Range silhouette — gentle, broad ridges, not sharp peaks.

import bmesh, random

MOUNTAIN_RADIUS   = 350    # metres — far enough to sit at horizon
MOUNTAIN_SEGMENTS = 180    # horizontal resolution of the ring
MOUNTAIN_BASE_Z   = -3.0   # below ground so bottom edge never shows

random.seed(7)             # fixed seed for reproducible silhouette

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

verts_bot, verts_top = [], []
for i in range(MOUNTAIN_SEGMENTS):
    a = 2 * math.pi * i / MOUNTAIN_SEGMENTS
    x = MOUNTAIN_RADIUS * math.cos(a)
    y = MOUNTAIN_RADIUS * math.sin(a)
    verts_bot.append(bm.verts.new((x, y, MOUNTAIN_BASE_Z)))
    verts_top.append(bm.verts.new((x, y, mountain_height(a))))

bm.verts.ensure_lookup_table()
for i in range(MOUNTAIN_SEGMENTS):
    j = (i + 1) % MOUNTAIN_SEGMENTS
    bm.faces.new([verts_bot[i], verts_bot[j], verts_top[j], verts_top[i]])

bm.to_mesh(mesh_mtns)
bm.free()

obj_mtns = bpy.data.objects.new("Mountain_Range", mesh_mtns)
bpy.context.collection.objects.link(obj_mtns)

mat_mtns = mat("Mountains", (0.22, 0.20, 0.17), metallic=0.0, roughness=0.92)
assign_mat(obj_mtns, mat_mtns)


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
