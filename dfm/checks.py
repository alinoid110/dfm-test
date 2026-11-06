"""Проверка ТЗ (spec): жёсткие программные ограничения на геометрию."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cadquery as cq
import numpy as np

from . import geom

DEFAULT_SPEC = {
    "bbox_tol": 0.01,            # допуск на габариты, доля от размера (по осям)
    "volume_ratio": [0.5, 1.1],  # объём результата / объём исходной детали
    "keep_holes": True,          # все исходные отверстия должны сохраниться
    "hole_d_tol": 0.01,          # допуск на диаметр, доля
    "hole_pos_tol_frac": 0.005,  # допуск на положение оси, доля диагонали
    "keep_boxes": [],            # [[x0,y0,z0,x1,y1,z1], ...] зоны, которые нельзя менять
    "keep_box_tol": 0.01,        # допуск на объём в зоне, доля
    "min_wall_mm": None,         # опционально: мин. толщина стенки
}


def load_spec(path) -> dict:
    spec = dict(DEFAULT_SPEC)
    p = Path(path)
    if p.exists():
        spec.update(json.loads(p.read_text()))
    return spec


@dataclass
class CheckResult:
    ok: bool
    reasons: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def text(self) -> str:
        return "OK" if self.ok else "SPEC VIOLATIONS:\n- " + "\n- ".join(self.reasons)


def _hole_matches(h, cands, diag, spec):
    for c in cands:
        if abs(c["d"] - h["d"]) > spec["hole_d_tol"] * h["d"]:
            continue
        if abs(abs(np.dot(c["dir"], h["dir"])) - 1) > 1e-3:
            continue
        if np.linalg.norm(c["a0"] - h["a0"]) > spec["hole_pos_tol_frac"] * diag:
            continue
        return True
    return False


def check_spec(shape, ref, spec) -> CheckResult:
    """shape — кандидат, ref — исходная деталь (опорная геометрия)."""
    reasons, met = [], {}
    if shape is None:
        return CheckResult(False, ["no shape"])
    if not shape.isValid():
        reasons.append("Resulting solid is not valid (self-intersections / bad topology).")
    ns = len(shape.Solids())
    met["n_solids"] = ns
    if ns != 1:
        reasons.append(f"Result must be exactly one solid, got {ns}.")

    lo, hi = geom.bbox_min_max(shape)
    rlo, rhi = geom.bbox_min_max(ref)
    dims, rdims = hi - lo, rhi - rlo
    if "bbox_size" in spec:
        rdims = np.array(spec["bbox_size"], float)
    tol = spec["bbox_tol"]
    for ax, d, r in zip("XYZ", dims, rdims):
        if abs(d - r) > tol * max(r, 1e-9):
            reasons.append(f"Bounding-box size along {ax} is {d:.3f}, required {r:.3f} "
                           f"(tolerance {tol*100:.1f}%).")
    if np.linalg.norm((lo + hi) / 2 - (rlo + rhi) / 2) > 0.01 * np.linalg.norm(rdims):
        reasons.append("Part was shifted/moved: bounding-box center changed.")

    v, rv = shape.Volume(), ref.Volume()
    met["volume_ratio"] = round(v / rv, 4)
    lo_r, hi_r = spec["volume_ratio"]
    if not (lo_r <= v / rv <= hi_r):
        reasons.append(f"Volume ratio {v/rv:.3f} outside allowed [{lo_r}, {hi_r}].")

    diag = float(np.linalg.norm(rdims))
    if spec["keep_holes"]:
        ref_holes, new_holes = geom.find_holes(ref), geom.find_holes(shape)
        for h in ref_holes:
            if not _hole_matches(h, new_holes, diag, spec):
                reasons.append(f"Required hole d={h['d']:.3f} (axis {np.round(h['dir'],2).tolist()}, "
                               f"through point {np.round(h['a0'],2).tolist()}) is missing or changed.")
        met["n_holes"] = (len(ref_holes), len(new_holes))

    for box in spec["keep_boxes"]:
        b = cq.Solid.makeBox(box[3] - box[0], box[4] - box[1], box[5] - box[2],
                             cq.Vector(box[0], box[1], box[2]))
        try:
            v_ref = ref.intersect(b).Volume()
            v_new = shape.intersect(b).Volume()
        except Exception:  # noqa: BLE001
            reasons.append(f"Boolean failed in keep-zone {box}.")
            continue
        if abs(v_new - v_ref) > spec["keep_box_tol"] * max(v_ref, 1e-9):
            reasons.append(f"Protected zone {box} was modified (volume {v_new:.2f} vs {v_ref:.2f}).")

    if spec.get("min_wall_mm"):
        mw = geom.MeshData(shape).min_wall()
        met["min_wall"] = round(mw, 3)
        if mw < spec["min_wall_mm"]:
            reasons.append(f"Minimum wall thickness ~{mw:.2f} < required {spec['min_wall_mm']}.")

    return CheckResult(not reasons, reasons, met)
