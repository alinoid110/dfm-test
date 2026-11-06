"""Базовый прогон по датасету: стоимость + самопроверка ТЗ для каждой детали.

python -m dfm.evaluate --parts parts --process process.json --out baseline.csv
"""
import argparse
import csv
import json
import time
from pathlib import Path

import cadquery as cq

from .checks import check_spec, load_spec
from .cost import compute_cost, load_process
from .sandbox import run_code


def part_dirs(root):
    return sorted(d for d in Path(root).iterdir() if d.is_dir() and (d / "part.py").exists())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="parts")
    ap.add_argument("--process", default="process.json")
    ap.add_argument("--out", default="baseline.csv")
    args = ap.parse_args()
    proc = load_process(args.process)
    rows = []
    for d in part_dirs(args.parts):
        t0 = time.time()
        code = (d / "part.py").read_text()
        r = run_code(code)
        row = dict(part=d.name, ok=r.ok)
        if not r.ok:
            row["error"] = r.error.strip().splitlines()[-1][:120]
            print(f"[FAIL] {d.name}: {row['error']}")
            rows.append(row)
            continue
        spec = load_spec(d / "spec.json")
        chk = check_spec(r.shape, r.shape, spec)           # деталь против самой себя
        rep = compute_cost(r.shape, proc)
        (d / "cost_report.json").write_text(json.dumps(rep, indent=1, default=str))
        f = rep["features"]
        row.update(cost=rep["total"], setups=f["setups"], faces=f["n_faces"],
                   sharp=f["sharp_internal_corners"], small_r=f["small_internal_radius"],
                   ball=f["ball_nose_faces"], nonstd_holes=f["nonstandard_holes"],
                   thin=f["thin_wall"], inaccessible=f["inaccessible_faces"],
                   spec_self_ok=chk.ok, sec=round(time.time() - t0, 1))
        step = next(d.glob("*.step"), None)               # sanity: part.py == STEP?
        if step:
            try:
                ref = cq.importers.importStep(str(step)).val()
                row["vol_ratio_vs_step"] = round(r.shape.Volume() / ref.Volume(), 4)
            except Exception:  # noqa: BLE001
                row["vol_ratio_vs_step"] = "err"
        print(f"[ok] {d.name}: cost={rep['total']} issues={[(i['id'], i['count']) for i in rep['issues']]}")
        rows.append(row)
    keys = sorted({k for r in rows for k in r}, key=lambda k: ["part", "ok"].index(k) if k in ("part", "ok") else 99)
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print("saved", args.out)


if __name__ == "__main__":
    main()
