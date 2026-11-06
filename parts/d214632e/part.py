import cadquery as cq

p_body_length = 80.0
p_large_dia = 60.0
p_small_dia = 40.0
p_transition_len = 20.0
p_fillet_radius = 5.0
p_passage_dia = 20.0
p_counterbore_dia = 15.0
p_counterbore_shaft_dia = 8.0
p_counterbore_depth = 8.0
p_chamfer = 1.0

large_r = p_large_dia / 2.0
small_r = p_small_dia / 2.0
large_section_len = (p_body_length - p_transition_len) / 2.0
p_counterbore_radius = large_r - 5.0

profile = (
    cq.Workplane('XZ')
    .moveTo(0, 0)
    .lineTo(large_r, 0)
    .lineTo(large_r, large_section_len - p_fillet_radius)
    .threePointArc((large_r + p_fillet_radius, large_section_len), (small_r, large_section_len + p_fillet_radius))
    .lineTo(small_r, p_body_length)
    .lineTo(0, p_body_length)
    .close()
)

body = profile.revolve()

body = (
    body
    .faces(">Z")
    .workplane()
    .hole(p_passage_dia)
    .faces(">Z")
    .workplane()
    .polarArray(radius=p_counterbore_radius, count=3, startAngle=0, angle=120)
    .cboreHole(p_counterbore_shaft_dia, p_counterbore_dia, p_counterbore_depth)
    .faces(">Z")
    .edges()
    .chamfer(p_chamfer)
)

result = body