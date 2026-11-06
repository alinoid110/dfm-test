import cadquery as cq

length = 80
width = 60
height = 30
wall_thickness = 4
inlet_radius = 10
vent_hole_width = 5
vent_hole_height = 12
vent_spacing = 20
vent_angle = 45
mount_hole_dia = 6
mount_offset = 15
chamfer_dist = 2
rib_height = 5
rib_width = width / 4
rib_length = length / 2

base_sketch = cq.Sketch().rect(length, width)
result = (
    cq.Workplane("XY")
    .placeSketch(base_sketch)
    .extrude(height)
    .shell(-wall_thickness)
)

result = (
    result.faces("<X")
    .workplane()
    .hole(inlet_radius * 2)
)

num_rows = int((length - 2 * mount_offset) / vent_spacing) + 1
for i in range(num_rows):
    x_pos = -length/2 + mount_offset + i * vent_spacing
    result = (
        result.faces(">Z")
        .workplane()
        .center(x_pos, 0)
        .rotate((0, 0, 0), (0, 0, 1), vent_angle)
        .rect(vent_hole_width, vent_hole_height)
        .cutBlind(-wall_thickness)
    )

result = (
    result.faces("<X")
    .workplane()
    .rarray(mount_hole_dia * 2, mount_hole_dia * 2, 2, 2)
    .hole(mount_hole_dia)
)

result = (
    result.faces(">Z")
    .workplane()
    .center(0, 0)
    .rect(rib_length, rib_width)
    .extrude(rib_height)
)

result = result.edges("|Z").chamfer(chamfer_dist)
