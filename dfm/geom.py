"""Геометрические примитивы: грани, отверстия, вогнутые рёбра, сетка, лучи."""
from __future__ import annotations

import math

import cadquery as cq
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp_Face
from OCP.gp import gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_IndexedMapOfShape

TWO_PI = 2 * math.pi


def solids_of(shape):
    return shape.Solids()


def bbox_min_max(shape):
    bb = shape.BoundingBox()
    return np.array([bb.xmin, bb.ymin, bb.zmin]), np.array([bb.xmax, bb.ymax, bb.zmax])


def diag_of(shape) -> float:
    lo, hi = bbox_min_max(shape)
    return float(np.linalg.norm(hi - lo))


def point_normal(face, u, v):
    """Точка и ВНЕШНЯЯ нормаль грани в параметрах (u, v)."""
    bgf = BRepGProp_Face(face.wrapped)
    p, n = gp_Pnt(), gp_Vec()
    bgf.Normal(u, v, p, n)
    nv = np.array([n.X(), n.Y(), n.Z()])
    return np.array([p.X(), p.Y(), p.Z()]), nv / (np.linalg.norm(nv) + 1e-15)


def face_mid(face):
    u0, u1, v0, v1 = face._uvBounds()
    return point_normal(face, (u0 + u1) / 2, (v0 + v1) / 2)


def _canon(d):
    d = np.array(d, dtype=float)
    for c in d:
        if abs(c) > 1e-9:
            return d if c > 0 else -d
    return d


def cylinders(shape):
    """Все цилиндрические грани: радиус, ось, угол, длина, выпуклость."""
    out = []
    for fi, f in enumerate(shape.Faces()):
        if f.geomType() != "CYLINDER":
            continue
        cyl = BRepAdaptor_Surface(f.wrapped).Cylinder()
        ax = cyl.Axis()
        a = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()])
        d = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
        u0, u1, v0, v1 = f._uvBounds()
        p, n = point_normal(f, (u0 + u1) / 2, (v0 + v1) / 2)
        rad = (p - a) - np.dot(p - a, d) * d
        d = _canon(d)
        out.append(dict(face=fi, r=float(cyl.Radius()), dir=d, a0=a - np.dot(a, d) * d,
                        span=float(u1 - u0), length=float(v1 - v0),
                        convex=bool(np.dot(n, rad) > 0)))
    return out


def find_holes(shape):
    """Отверстия = вогнутые цилиндры, в сумме покрывающие ~360° вокруг одной оси."""
    groups: dict = {}
    for c in cylinders(shape):
        if c["convex"]:
            continue
        key = (round(c["r"], 3), tuple(np.round(c["dir"], 3)), tuple(np.round(c["a0"], 2)))
        g = groups.setdefault(key, dict(r=c["r"], dir=c["dir"], a0=c["a0"], span=0.0, length=0.0))
        g["span"] += c["span"]
        g["length"] = max(g["length"], c["length"])
    holes = []
    for g in groups.values():
        if g["span"] >= 0.95 * TWO_PI:
            holes.append(dict(d=2 * g["r"], dir=g["dir"], a0=g["a0"], depth=g["length"]))
    return holes


def _ancestors(shape, kind_from, kind_to):
    m = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape.wrapped, kind_from, kind_to, m)
    return m


def sharp_internal_corners(shape, cover):
    """Вогнутые прямые рёбра ~90° между двумя плоскими гранями, направленные вдоль оси,
    по которой инструмент заходит (она есть среди выбранных установов), и обе грани
    доступны с этого направления. Такое ребро — «вертикальный» внутренний угол кармана,
    который круглая фреза не сделает острым. Рёбра дна кармана не считаются.
    cover — результат MeshData.setup_cover()."""
    solids = shape.Solids()
    eps = 1e-3 * diag_of(shape)
    em = _ancestors(shape, TopAbs_EDGE, TopAbs_FACE)
    fmap = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape.wrapped, TopAbs_FACE, fmap)
    dirs = [np.array(d, float) for d in cover["all_dirs"]]
    picked = {tuple(d) for d in cover["directions"]}
    found = []
    for i in range(1, em.Extent() + 1):
        edge = cq.Edge(TopoDS.Edge_s(em.FindKey(i)))
        if edge.geomType() != "LINE":
            continue
        fl = list(em.FindFromIndex(i))
        if len(fl) != 2:
            continue
        faces = [cq.Face(TopoDS.Face_s(f)) for f in fl]
        if any(f.geomType() != "PLANE" for f in faces):
            continue
        n1, n2 = face_mid(faces[0])[1], face_mid(faces[1])[1]
        if abs(np.dot(n1, n2)) > 0.5:
            continue
        t = edge.tangentAt(0.5)
        t = np.array([t.x, t.y, t.z])
        m = edge.positionAt(0.5)
        m = np.array([m.x, m.y, m.z])
        probe = m + eps * (n1 - n2) / (np.linalg.norm(n1 - n2) + 1e-15)
        if not any(s.isInside(cq.Vector(*probe), 1e-9) for s in solids):
            continue  # выпуклое ребро
        idx = [fmap.FindIndex(f.wrapped) - 1 for f in faces]
        for di, a in enumerate(dirs):
            if abs(abs(np.dot(a, t)) - 1) < 1e-3 and tuple(int(x) for x in a) in picked:
                if cover["acc"][di][idx[0]] and cover["acc"][di][idx[1]]:
                    found.append((m, float(edge.Length())))
                    break
    return found


class MeshData:
    """Треугольная сетка + лучи (чистый numpy, без trimesh/rtree)."""

    def __init__(self, shape, tol_frac: float = 1e-3):
        self.diag = diag_of(shape)
        self.tol = tol_frac * self.diag
        self.faces = shape.Faces()
        verts, tris, tri_face = [], [], []
        for fi, f in enumerate(self.faces):
            try:
                vs, ts = f.tessellate(self.tol, 0.3)
            except Exception:  # noqa: BLE001
                continue
            off = len(verts)
            verts.extend((v.x, v.y, v.z) for v in vs)
            tris.extend((a + off, b + off, c + off) for a, b, c in ts)
            tri_face.extend([fi] * len(ts))
        V = np.array(verts, dtype=float)
        T = np.array(tris, dtype=int)
        self.v0 = V[T[:, 0]]
        self.e1 = V[T[:, 1]] - self.v0
        self.e2 = V[T[:, 2]] - self.v0
        cr = np.cross(self.e1, self.e2)
        ln = np.linalg.norm(cr, axis=1) + 1e-18
        self.normals = cr / ln[:, None]
        self.centroids = self.v0 + (self.e1 + self.e2) / 3.0
        self.tri_face = np.array(tri_face, dtype=int)
        self.face_area = np.array([f.Area() for f in self.faces])

    def first_hit(self, o, d, tmin=None):
        tmin = 1e-6 * self.diag if tmin is None else tmin
        h = np.cross(d, self.e2)
        a = np.einsum("ij,ij->i", self.e1, h)
        ok = np.abs(a) > 1e-12
        inv = np.zeros_like(a)
        inv[ok] = 1.0 / a[ok]
        s = o - self.v0
        u = inv * np.einsum("ij,ij->i", s, h)
        q = np.cross(s, self.e1)
        v = inv * (q @ d)
        t = inv * np.einsum("ij,ij->i", self.e2, q)
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > tmin)
        return float(t[hit].min()) if hit.any() else math.inf

    def samples(self, per_face: int = 3):
        """Точки-образцы на гранях: (face_id, точка, нормаль)."""
        out = []
        for fi in range(len(self.faces)):
            idx = np.where(self.tri_face == fi)[0]
            if len(idx) == 0:
                continue
            pick = idx[np.unique(np.linspace(0, len(idx) - 1, per_face).astype(int))]
            for k in pick:
                out.append((fi, self.centroids[k], self.normals[k]))
        return out

    def min_wall(self, per_face: int = 2):
        """Оценка минимальной толщины стенки: лучи внутрь по нормали."""
        ts = []
        for fi, p, n in self.samples(per_face):
            t = self.first_hit(p, -n)
            if math.isfinite(t):
                ts.append(t)
        return float(np.percentile(ts, 2)) if ts else math.inf

    def setup_cover(self, per_face: int = 3):
        """Жадное покрытие граней направлениями доступа ±X,±Y,±Z.
        Грань доступна из направления a, если n·a >= 0 (торцевая или боковая обработка)
        и луч вдоль a из точки чуть над гранью не упирается в деталь."""
        dirs = [np.array(v, float) for v in
                [(0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)]]
        smp = self.samples(per_face)
        nfaces = len(self.faces)
        eps = 2.5 * self.tol
        acc = np.zeros((len(dirs), nfaces))
        cnt = np.zeros(nfaces)
        for fi, p, n in smp:
            cnt[fi] += 1
            for di, a in enumerate(dirs):
                if np.dot(n, a) < -0.05:
                    continue
                if not math.isfinite(self.first_hit(p + n * eps, a)):
                    acc[di, fi] += 1
        cnt[cnt == 0] = 1
        frac = acc / cnt
        acc = frac >= 0.5
        area = self.face_area
        uncovered = np.ones(nfaces, bool)
        picked = []
        while uncovered.any():
            gain = [(acc[di] & uncovered) @ area for di in range(len(dirs))]
            best = int(np.argmax(gain))
            if gain[best] <= 0:
                break
            picked.append(tuple(int(x) for x in dirs[best]))
            uncovered &= ~acc[best]
        return dict(directions=picked, n_setups=len(picked), n_inaccessible=int(uncovered.sum()),
                    acc=acc, frac=frac, uncovered=[int(i) for i in np.where(uncovered)[0]],
                    all_dirs=[tuple(int(x) for x in d) for d in dirs])
