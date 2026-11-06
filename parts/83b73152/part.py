import cadquery as cq

body_length = 70
body_outer_diameter = 40
body_outer_radius = body_outer_diameter / 2
wall_thickness = 4
inlet_diameter = 20
outlet_diameter = 20
flange_thickness = 6
flange_outer_diameter = 80
flange_outer_radius = flange_outer_diameter / 2
rib_height = 2
rib_width = 15
rib_position = body_length / 3
rib_start = flange_thickness + rib_position - rib_width / 2
rib_end = rib_start + rib_width
inner_radius = body_outer_radius - wall_thickness
o_ring_groove_depth = 1
o_ring_groove_width = 8
o_ring_position = 2 * body_length / 3
o_ring_start = flange_thickness + o_ring_position - o_ring_groove_width / 2
o_ring_end = o_ring_start + o_ring_groove_width
chamfer_size = 1
mount_hole_diameter = 6
mount_hole_spacing = 30
mount_hole_offset = 10

# Outer profile
outer = (
    cq.Workplane("XZ")
    .moveTo(0, 0)
    .lineTo(flange_outer_radius, 0)
    .lineTo(flange_outer_radius, flange_thickness)
    .lineTo(body_outer_radius, flange_thickness)
    .lineTo(body_outer_radius, flange_thickness + body_length)
    .lineTo(flange_outer_radius, flange_thickness + body_length)
    .lineTo(flange_outer_radius, flange_thickness * 2 + body_length)
    .lineTo(0, flange_thickness * 2 + body_length)
    .close()
    .revolve()
)

# Inner cavity profile with rib and O‑ring groove
inner = (
    cq.Workplane("XZ")
    .moveTo(0, 0)
    .lineTo(inner_radius, 0)
    .lineTo(inner_radius, flange_thickness)
    .lineTo(inner_radius, rib_start)
    .lineTo(inner_radius - rib_height, rib_start)
    .lineTo(inner_radius - rib_height, rib_end)
    .lineTo(inner_radius, rib_end)
    .lineTo(inner_radius, o_ring_start)
    .lineTo(inner_radius + o_ring_groove_depth, o_ring_start)
    .lineTo(inner_radius + o_ring_groove_depth, o_ring_end)
    .lineTo(inner_radius, o_ring_end)
    .lineTo(inner_radius, flange_thickness + body_length)
    .lineTo(inner_radius, flange_thickness * 2 + body_length)
    .lineTo(0, flange_thickness * 2 + body_length)
    .close()
    .revolve()
)

# Subtract inner cavity
result = outer.cut(inner)

# Chamfer exit edge on outward flange
result = result.faces(">Z").edges().chamfer(chamfer_size)

# Inlet hole through inlet flange
result = result.faces("<Z").workplane().hole(inlet_diameter)

# Mounting holes on each flange (two opposite)
for offset in (mount_hole_offset, -mount_hole_offset):
    pts = [(mount_hole_spacing / 2, offset), (-mount_hole_spacing / 2, offset)]
    result = result.faces("<Z").workplane()
    result = result.pushPoints(pts).hole(mount_hole_diameter)
    result = result.faces(">Z").workplane()
    result = result.pushPoints(pts).hole(mount_hole_diameter)

