import cadquery as cq

body_length = 80
outer_diameter = 80
outer_radius = outer_diameter / 2
shoulder_diameter = 60
shoulder_radius = shoulder_diameter / 2
shoulder_length = 20
central_bore_diameter = 20
chamfer_dist = 2
keyway_width = 12
keyway_depth = 6
keyway_length = 40
keyway_center_z = body_length / 2
port_diameter = 15
port_offset_z = shoulder_length / 2
relief_depth = 5
rib_thickness = 3
rib_offset = 5

profile = (
    cq.Workplane("XZ")
    .lineTo(outer_radius, 0)
    .lineTo(outer_radius, body_length - shoulder_length)
    .lineTo(shoulder_radius, body_length - shoulder_length)
    .lineTo(shoulder_radius, body_length)
    .lineTo(0, body_length)
    .close()
)

body = profile.revolve()

body = body.faces(">Z").workplane().hole(central_bore_diameter)

keyway_block = (
    cq.Workplane("YZ")
    .rect(keyway_width, keyway_length)
    .extrude(keyway_depth)
    .translate((outer_radius - keyway_depth / 2, 0, keyway_center_z))
)

body = body.cut(keyway_block)

# Relief pocket on top of shoulder
body = (
    body.faces(">Z")
    .workplane()
    .center(0, 0)
    .rect(shoulder_diameter * 0.6, shoulder_length * 0.5)
    .cutBlind(-relief_depth)
)

# External reinforcing rib near outer surface
rib_profile = (
    cq.Workplane("XZ")
    .lineTo(outer_radius - rib_offset - rib_thickness, 0)
    .lineTo(outer_radius - rib_offset - rib_thickness, body_length)
    .lineTo(outer_radius - rib_offset, body_length)
    .lineTo(outer_radius - rib_offset, 0)
    .close()
)
rib = rib_profile.revolve()
body = body.union(rib)

port_x_offset = -outer_radius + chamfer_dist + port_diameter / 2
port_z_positions = [port_offset_z, -port_offset_z]
for z in port_z_positions:
    port_cut = (
        cq.Workplane("YZ")
        .circle(port_diameter / 2)
        .extrude(outer_diameter + 20)
        .translate((port_x_offset, 0, z))
    )
    body = body.cut(port_cut)

result = body