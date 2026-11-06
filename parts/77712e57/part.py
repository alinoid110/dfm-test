import cadquery as cq

# Parameters
body_diameter = 80.0
body_length = 100.0
wall_thickness = 5.0
port_width = 20.0
port_height = 15.0
port_center_offset = 30.0
blind_hole_diameter = 5.0
blind_hole_spacing = 20.0
blind_hole_depth = 12.0
chamfer_size = 2.0

# Base solid: outer cylinder
result = (
    cq.Workplane("XY")
    .circle(body_diameter / 2)
    .extrude(body_length)
)

# Shell to create wall thickness (hollow interior)
result = result.shell(-wall_thickness)

# Side port block for cutting
side_port = (
    cq.Workplane("XZ")
    .rect(port_width, port_height)
    .extrude(body_diameter)  # extrude enough to cut through
    .translate((0, 0, port_center_offset - body_length / 2))
)
result = result.cut(side_port)

# Blind holes array for weight relief
# Create a grid of points inside the front half of the body
num_x = int(body_length / blind_hole_spacing)
num_y = int(body_diameter / blind_hole_spacing)
result = (
    result.faces(">Z")
    .workplane()
    .rarray(blind_hole_spacing, blind_hole_spacing, num_x, num_y)
    .hole(blind_hole_diameter, depth=blind_hole_depth)
)

# Chamfer outer cylindrical edge
result = result.edges("|Z").chamfer(chamfer_size)
