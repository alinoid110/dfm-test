"""Детерминированная эвристическая модель стоимости 3-осевого фрезерования.

Все коэффициенты — допущения. Их можно/нужно менять в process.json
(и честно описать в тексте ВКР как допущения модели).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import geom

MATERIALS = {  # плотность г/см3, цена $/кг, относительная скорость съёма
    "aluminum_6061": dict(density=2.70, price_kg=6.0, speed=1.0),
    "steel_1018": dict(density=7.87, price_kg=2.0, speed=0.35),
    "stainless_304": dict(density=8.00, price_kg=6.0, speed=0.25),
    "brass": dict(density=8.50, price_kg=9.0, speed=0.8),
}

DEFAULT_PROCESS = {
    "machine": "3-axis mill",
    "material": "aluminum_6061",
    "unit_to_mm": 1.0,               # если модель в других единицах
    "stock_margin_mm": 2.0,          # припуск заготовки с каждой стороны
    "tool_min_radius_mm": 1.5,       # мин. радиус фрезы => мин. внутренний радиус
    "min_wall_mm": 1.0,
    "primary_axis": "Z",
    "machine_rate_per_hour": 60.0,
    "setup_time_min": 20.0,
    "mrr_cm3_per_min": 8.0,          # черновой съём для Al
    "finish_rate_cm2_per_min": 25.0,
    "drill_feed_mm_per_min": 100.0,
    "drill_sizes_mm": [1, 1.5, 2, 2.5, 3, 3.3, 3.5, 4, 4.2, 4.5, 5, 5.5, 6, 6.5, 6.8, 7, 8,
                       8.5, 9, 10, 10.2, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24],
    "deep_hole_ratio": 5.0,
    "angled_face_area_frac": 0.05,
    "penalties_min": {               # штрафное время, мин
        "sharp_internal_corner": 1.5,
        "small_internal_radius": 0.8,
        "ball_nose_face": 3.0,
        "nonstandard_hole": 0.5,
        "deep_hole": 1.0,
        "thin_wall": 5.0,
        "inaccessible_face": 0.0,      # выкл. по умолчанию: эвристика требует проверки (dfm.debug_access)
        "chamfer_face": 0.3,
        "hole_base": 0.2,
    },
}


def load_process(path=None) -> dict:
    proc = json.loads(json.dumps(DEFAULT_PROCESS))
    if path and Path(path).exists():
        user = json.loads(Path(path).read_text())
        pen = user.pop("penalties_min", {})
        proc.update(user)
        proc["penalties_min"].update(pen)
    return proc


def _scale_shape(shape, k):
    if abs(k - 1.0) < 1e-12:
        return shape
    return shape.scale(k)


def compute_features(shape, proc) -> dict:
    pen = proc["penalties_min"]
    tool_r = proc["tool_min_radius_mm"]
    prim = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[proc["primary_axis"].upper()]
    prim = np.array(prim, float)
    faces = shape.Faces()
    cyls = geom.cylinders(shape)
    holes = geom.find_holes(shape)

    small_r, ball = 0, 0
    for c in cyls:
        parallel = abs(abs(np.dot(c["dir"], prim)) - 1) < 1e-3
        if not c["convex"]:
            is_hole_part = any(abs(c["r"] - h["d"] / 2) < 1e-3 and
                               abs(abs(np.dot(c["dir"], h["dir"])) - 1) < 1e-3 for h in holes)
            if not is_hole_part and parallel and c["r"] < tool_r - 1e-6:
                small_r += 1
        elif not parallel and c["span"] < geom.TWO_PI * 0.95:
            ball += 1  # выпуклое «горизонтальное» скругление -> шаровая фреза
    free = sum(1 for f in faces if f.geomType() in ("SPHERE", "TORUS", "BSPLINE", "BEZIER",
                                                     "REVOLUTION", "EXTRUSION", "OTHER"))
    ball += free


    total_area = sum(f.Area() for f in faces)
    angled = 0
    for f in faces:
        if f.geomType() == "PLANE":
            n = geom.face_mid(f)[1]
            if np.max(np.abs(n)) < 0.999:  # не по осям координат => фаска/наклон
                if f.Area() / total_area < proc["angled_face_area_frac"]:
                    angled += 1

    drills = proc["drill_sizes_mm"]
    k = proc["unit_to_mm"]
    nonstd, deep = 0, 0
    hole_list = []
    for h in holes:
        d_mm, depth_mm = h["d"] * k, h["depth"] * k
        std = any(abs(d_mm - s) < 0.05 for s in drills) or d_mm > max(drills)
        isdeep = depth_mm / max(d_mm, 1e-9) > proc["deep_hole_ratio"]
        nonstd += 0 if std else 1
        deep += 1 if isdeep else 0
        hole_list.append(dict(d_mm=round(d_mm, 3), depth_mm=round(depth_mm, 2),
                              standard=bool(std), deep=bool(isdeep)))

    mesh = geom.MeshData(shape)
    min_wall = mesh.min_wall() * k
    cover = mesh.setup_cover()
    sharp = geom.sharp_internal_corners(shape, cover)

    return dict(n_faces=len(faces), holes=hole_list, nonstandard_holes=nonstd, deep_holes=deep,
                sharp_internal_corners=len(sharp), small_internal_radius=small_r,
                ball_nose_faces=ball, chamfer_faces=angled,
                min_wall_mm=round(min_wall, 3) if math.isfinite(min_wall) else None,
                thin_wall=int(math.isfinite(min_wall) and min_wall < proc["min_wall_mm"]),
                setups=cover["n_setups"], setup_dirs=cover["directions"],
                inaccessible_faces=cover["n_inaccessible"])


def compute_cost(shape, process=None) -> dict:
    """Возвращает отчёт: total, разбивку и список проблем для DFM Reviewer."""
    proc = process if process is not None else load_process()
    k = proc["unit_to_mm"]
    shape = _scale_shape(shape, k)           # дальше всё в мм
    proc = {**proc, "unit_to_mm": 1.0}
    mat = MATERIALS[proc["material"]]
    pen = proc["penalties_min"]

    lo, hi = geom.bbox_min_max(shape)
    dims = hi - lo
    m = proc["stock_margin_mm"]
    stock_cm3 = float(np.prod(dims + 2 * m)) / 1000.0
    vol_cm3 = shape.Volume() / 1000.0
    area_cm2 = sum(f.Area() for f in shape.Faces()) / 100.0

    ft = compute_features(shape, proc)

    t_rough = max(stock_cm3 - vol_cm3, 0) / (proc["mrr_cm3_per_min"] * mat["speed"])
    t_finish = area_cm2 / (proc["finish_rate_cm2_per_min"] * mat["speed"])
    t_holes = sum(pen["hole_base"] + h["depth_mm"] / proc["drill_feed_mm_per_min"]
                  for h in ft["holes"])
    pen_items = {
        "sharp_internal_corner": ft["sharp_internal_corners"],
        "small_internal_radius": ft["small_internal_radius"],
        "ball_nose_face": ft["ball_nose_faces"],
        "nonstandard_hole": ft["nonstandard_holes"],
        "deep_hole": ft["deep_holes"],
        "thin_wall": ft["thin_wall"],
        "inaccessible_face": ft["inaccessible_faces"],
        "chamfer_face": ft["chamfer_faces"],
    }
    t_pen = sum(pen[k_] * n for k_, n in pen_items.items())
    t_setup = ft["setups"] * proc["setup_time_min"]
    rate = proc["machine_rate_per_hour"] / 60.0
    machining_time = t_rough + t_finish + t_holes + t_pen
    material_cost = stock_cm3 * mat["density"] * mat["price_kg"] / 1000.0
    machine_cost = rate * (machining_time + t_setup)
    total = material_cost + machine_cost

    texts = {
        "sharp_internal_corner": "Sharp internal vertical corners (no corner radius): a round end mill "
            f"cannot cut them. Add fillets of radius >= {proc['tool_min_radius_mm']} mm.",
        "small_internal_radius": "Internal vertical fillets smaller than the minimum tool radius "
            f"({proc['tool_min_radius_mm']} mm). Increase their radius.",
        "ball_nose_face": "Convex 'horizontal' rounded/freeform faces need a ball-nose tool and 3D "
            "toolpaths. Replace horizontal convex fillets with 45-degree chamfers.",
        "nonstandard_hole": "Holes with non-standard diameters need extra tooling. Use the nearest "
            "standard drill size (only if the spec allows changing the hole).",
        "deep_hole": f"Deep holes (depth/diameter > {proc['deep_hole_ratio']}). Reduce depth if allowed.",
        "thin_wall": f"Walls thinner than {proc['min_wall_mm']} mm (vibration, scrap). Thicken them.",
        "inaccessible_face": "Faces not reachable by a tool from any of 6 axis directions "
            "(would need EDM/5-axis). Open up access.",
    }
    issues = []
    for key, text in texts.items():
        n = pen_items[key]
        if n and pen[key] > 0:
            issues.append(dict(id=key, count=int(n), est_saving_min=round(pen[key] * n, 2),
                               text=text))
    issues.sort(key=lambda i: -i["est_saving_min"])

    return dict(
        total=round(total, 3), material_cost=round(material_cost, 3),
        machine_cost=round(machine_cost, 3),
        time_min=dict(rough=round(t_rough, 2), finish=round(t_finish, 2), holes=round(t_holes, 2),
                      penalties=round(t_pen, 2), setups=round(t_setup, 2)),
        stock_cm3=round(stock_cm3, 2), volume_cm3=round(vol_cm3, 2),
        bbox_mm=[round(x, 3) for x in dims], features=ft, issues=issues)
