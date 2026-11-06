import cadquery as cq

# Parameters
body_diameter = 60.0
body_radius = body_diameter / 2.0
body_length = 50.0
bulge_factor = 1.2
mid_section_height = body_length / 2.0
dome_height = 25.0
total_height = body_length + dome_height
inlet_diameter = 15.0
outlet_diameter = 12.0
port_center_z = body_length * 0.6
gasket_seat_diameter = 30.0
gasket_seat_depth = 5.0
thread_length = 12.0
thread_diameter = body_diameter + 5.0
mount_hole_diameter = 5.0
mount_hole_spacing = 40.0
chamfer_distance = 2.0

# Lofted valve body with bulged dome
valve_body = (
    cq.Workplane("XY")
    .circle(body_radius)
    .workplane(offset=mid_section_height)
    .circle(body_radius * bulge_factor)
    .workplane(offset=total_height - mid_section_height)
    .circle(body_radius)
    .loft(combine=True)
)

# Recessed gasket seat
gasket_seat = (
    cq.Workplane("XY")
    .center(0, 0)
    .circle(gasket_seat_diameter / 2.0)
    .extrude(-gasket_seat_depth)
)
valve_body = valve_body.cut(gasket_seat.translate((0, 0, total_height - gasket_seat_depth)))

# Inlet port (side hole)
inlet_port = (
    cq.Workplane("YZ")
    .center(0, port_center_z)
    .circle(inlet_diameter / 2.0)
    .extrude(body_radius * 2.0)
)
valve_body = valve_body.cut(inlet_port)

# Outlet port (side hole)
outlet_port = (
    cq.Workplane("YZ")
    .center(0, port_center_z)
    .circle(outlet_diameter / 2.0)
    .extrude(body_radius * 2.0)
)
valve_body = valve_body.cut(outlet_port)

# External thread region (cylindrical boss)
thread_region = (
    cq.Workplane("XY")
    .center(0, 0)
    .circle(thread_diameter / 2.0)
    .extrude(thread_length)
    .translate((0, 0, total_height - thread_length))
)
valve_body = valve_body.union(thread_region)

# Mounting holes through side walls
mount_hole = (
    cq.Workplane("YZ")
    .center(0, total_height / 2.0)
    .circle(mount_hole_diameter / 2.0)
    .extrude(body_radius * 2.0)
)
hole1 = mount_hole.translate((0, 0, -mount_hole_spacing / 2.0))
hole2 = mount_hole.translate((0, 0, mount_hole_spacing / 2.0))
valve_body = valve_body.cut(hole1).cut(hole2)

# Chamfer top edge
valve_body = valve_body.edges(">Z").chamfer(chamfer_distance)

result = valve_body