import cadquery as cq

outer_diameter = 80.0
body_height = 70.0
wall_thickness = 4.0
rib_radius = 2.0
rib_height = 55.0
rib_count = 8
slot_width = 20.0
slot_height = 8.0
slot_depth = wall_thickness
chamfer_size = 1.0

outer_radius = outer_diameter / 2.0
inner_radius = outer_radius - wall_thickness

profile = (
    cq.Workplane("XZ")
    .lineTo(outer_radius, 0)
    .lineTo(outer_radius, body_height)
    .lineTo(0, body_height)
    .close()
)

valve_body = profile.revolve()
valve_body = valve_body.shell(-wall_thickness)

rib_array = (
    cq.Workplane("XY")
    .polarArray(radius=inner_radius - rib_radius, count=rib_count, startAngle=0, angle=360)
    .circle(rib_radius)
    .extrude(rib_height)
)

valve_body = valve_body.union(rib_array)

slot_cut = (
    cq.Workplane("XY")
    .center(outer_radius - wall_thickness/2, 0)
    .rect(slot_width, slot_height)
    .extrude(-slot_depth)
)

valve_body = valve_body.cut(slot_cut)

valve_body = valve_body.faces(">Z").edges().chamfer(chamfer_size)

result = valve_body