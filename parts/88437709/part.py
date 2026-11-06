import cadquery as cq

# Parameters
max_diameter = 80.0
body_diameter = 60.0
body_radius = body_diameter / 2.0
cone_base_diameter = body_diameter
cone_base_radius = cone_base_diameter / 2.0
cone_tip_diameter = 30.0
cone_tip_radius = cone_tip_diameter / 2.0
cone_length = 20.0
body_length = 45.0
flange_diameter = max_diameter
flange_radius = flange_diameter / 2.0
flange_thickness = 5.0
flange_recess_depth = 3.0
flange_recess_radius = flange_radius - 5.0
inner_bore_diameter = 20.0
inner_bore_radius = inner_bore_diameter / 2.0
fillet_radius = 2.0
mounting_hole_dia = 5.0
mounting_hole_count = 3
mounting_hole_offset = flange_radius - 10.0
mounting_hole_angle = 360.0 / mounting_hole_count

# Create outer profile for revolve
profile = (
    cq.Workplane("XY")
    .moveTo(0, 0)
    .lineTo(cone_tip_radius, 0)
    .lineTo(cone_base_radius, cone_length)
    .lineTo(body_radius, cone_length + body_length)
    .lineTo(flange_radius, cone_length + body_length)
    .lineTo(flange_radius, cone_length + body_length + flange_thickness)
    .lineTo(0, cone_length + body_length + flange_thickness)
    .close()
)

# Revolve profile around Y axis
outer_body = profile.revolve()

# Apply fillet to all exterior sharp edges
outer_body = outer_body.edges().fillet(fillet_radius)

# Subtract inner bore through entire length
total_height = cone_length + body_length + flange_thickness
inner_cylinder = (
    cq.Workplane("XY")
    .center(0, 0)
    .circle(inner_bore_radius)
    .extrude(total_height)
)
outer_body = outer_body.cut(inner_cylinder)

# Create recessed flange pocket
recess = (
    cq.Workplane("XY")
    .center(0, cone_length + body_length)
    .circle(flange_recess_radius)
    .extrude(flange_recess_depth)
)
outer_body = outer_body.cut(recess)

# Add mounting holes on top flange in a triangular pattern
outer_body = (
    outer_body
    .faces(">Y")
    .workplane()
    .polarArray(radius=mounting_hole_offset, count=mounting_hole_count, angle=mounting_hole_angle, startAngle=0)
    .hole(mounting_hole_dia)
)

result = outer_body