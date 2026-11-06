import cadquery as cq
import math

# Parameters
body_outer_radius = 30.0
body_length = 50.0
wall_thickness = 5.0
through_hole_diameter = 15.0
fastener_hole_diameter = 6.0
counterbore_diameter = 10.0
counterbore_depth = 10.0
fastener_hole_radial_distance = body_outer_radius - wall_thickness/2.0
chamfer_distance = 1.0
inlet_radius = 12.0
inlet_length = 15.0
inlet_offset = 5.0

# Base body extrusion with top face tag
result = (
    cq.Workplane('XY')
    .circle(body_outer_radius)
    .extrude(body_length)
    .faces('>Z')
    .tag('top')
)

# Create inner bore for valve passage using top workplane
result = result.workplaneFromTagged('top').hole(through_hole_diameter)

# Add side inlet port using a cylindrical cutter
inlet_cutter = (
    cq.Workplane('YZ')
    .circle(inlet_radius)
    .extrude(inlet_length)
    .translate((0, body_outer_radius - inlet_offset, 0))
)
result = result.cut(inlet_cutter)

# Add four peripheral counterbore slots for fasteners using top workplane
fastener_angles = [45, 135, 225, 315]
fastener_points = [
    (
        fastener_hole_radial_distance * math.cos(math.radians(a)),
        fastener_hole_radial_distance * math.sin(math.radians(a))
    )
    for a in fastener_angles
]
result = (
    result.workplaneFromTagged('top')
    .pushPoints(fastener_points)
    .cboreHole(fastener_hole_diameter, counterbore_diameter, counterbore_depth)
)

# Apply chamfer to top edge for safety
result = result.edges('>Z').chamfer(chamfer_distance)
