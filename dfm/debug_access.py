"""Диагностика эвристики доступности: какие грани считаются недоступными и почему.

python -m dfm.debug_access parts/15867d50
"""
import sys
from pathlib import Path

import numpy as np

from . import geom
from .sandbox import run_code


def main():
    pdir = Path(sys.argv[1])
    r = run_code((pdir / "part.py").read_text())
    if not r.ok:
        print(r.error)
        return
    mesh = geom.MeshData(r.shape)
    cover = mesh.setup_cover()
    print("установы:", cover["directions"], "| недоступных граней:", len(cover["uncovered"]),
          "из", len(mesh.faces))
    dirs = cover["all_dirs"]
    for fi in cover["uncovered"]:
        f = mesh.faces[fi]
        c = f.Center()
        _, n = geom.face_mid(f)
        print(f"\nгрань #{fi}: {f.geomType()} area={f.Area():.2f} "
              f"center=({c.x:.1f},{c.y:.1f},{c.z:.1f}) normal≈{np.round(n, 2).tolist()}")
        print("  доля доступных образцов по направлениям:",
              {str(d): round(float(cover['frac'][i][fi]), 2) for i, d in enumerate(dirs)})


if __name__ == "__main__":
    main()
