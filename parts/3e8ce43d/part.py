import cadquery as cq

# Parameters
body_outer_radius = 30.0
body_length = 80.0
outlet_radius = 12.0
outlet_length = 20.0
wall_thickness = 4.0
pocket_width = 15.0
pocket_depth = 8.0
pocket_height = 30.0
rib_height = 6.0
rib_thickness = 4.0
rib_position = 0.5  # fraction of length from bottom

# Outer profile sketch (XY plane) for revolve
profile = (
    cq.Workplane("XY")
    .moveTo(0, 0)
    .lineTo(body_outer_radius, 0)
    .lineTo(body_outer_radius, body_length - outlet_length)
    .lineTo(outlet_radius, body_length - outlet_length)
    .lineTo(outlet_radius, body_length)
    .lineTo(0, body_length)
    .close()
)

# Revolve to create solid body (full 360° around Z)
outer_body = profile.revolve(360)

# Shell to create hollow interior
hollow_body = outer_body.shell(-wall_thickness)

# Internal pocket cut (rectangular pocket on side)
# Position pocket at mid‑length, centered on the side wall
pocket = (
    cq.Workplane("YZ")
    .center(body_outer_radius - wall_thickness - pocket_depth / 2, body_length * 0.5)
    .rect(pocket_depth, pocket_height)
    .extrude(pocket_width)
)

hollow_body = hollow_body.cut(pocket)

# Reinforcement rib (external thin cylindrical band)
rib_center_z = body_length * rib_position
rib = (
    cq.Workplane("XY")
    .center(0, rib_center_z)
    .circle(body_outer_radius + rib_height)
    .extrude(rib_thickness)
    .translate((0, 0, -rib_thickness / 2))
)

result = hollow_body.union(rib)
