"""Выполняет скрипт CadQuery в отдельном процессе и сохраняет результат в STEP.

Запуск: python worker.py code.py out.step
Последняя строка stdout — JSON {"ok": bool, "error": str, "var": str}.
"""
import contextlib
import json
import sys
import traceback

CANDIDATE_NAMES = ("result", "part", "shape", "body", "model", "r", "solid", "res", "obj")


def _to_shape(obj, cq):
    """Приводит объект CadQuery к cq.Shape из твёрдых тел (или None)."""
    if isinstance(obj, cq.Assembly):
        obj = obj.toCompound()
    if isinstance(obj, cq.Workplane):
        shapes = [v for v in obj.vals() if isinstance(v, cq.Shape)]
        if not shapes:
            return None
        obj = shapes[0] if len(shapes) == 1 else cq.Compound.makeCompound(shapes)
    if isinstance(obj, cq.Shape):
        solids = obj.Solids()
        if not solids:
            return None
        return solids[0] if len(solids) == 1 else cq.Compound.makeCompound(solids)
    return None


def find_result(ns, cq):
    for name in CANDIDATE_NAMES:
        if name in ns:
            s = _to_shape(ns[name], cq)
            if s is not None:
                return name, s
    for name in ("build", "make", "create"):  # скрипт-функция без аргументов
        if callable(ns.get(name)):
            try:
                s = _to_shape(ns[name](), cq)
                if s is not None:
                    return name + "()", s
            except TypeError:
                pass
    for name in reversed(list(ns.keys())):  # последний подходящий объект
        if name.startswith("__"):
            continue
        s = _to_shape(ns[name], cq)
        if s is not None:
            return name, s
    return None, None


def main():
    code_path, out_path = sys.argv[1], sys.argv[2]
    try:
        import cadquery as cq

        code = open(code_path, encoding="utf-8").read()
        ns = {"__name__": "__main__", "show_object": lambda *a, **k: None,
              "debug": lambda *a, **k: None}
        with contextlib.redirect_stdout(sys.stderr):
            exec(compile(code, "<part>", "exec"), ns)
            var, shape = find_result(ns, cq)
        if shape is None:
            raise RuntimeError(
                "No solid found. Assign the final solid to a variable named `result`.")
        cq.exporters.export(cq.Workplane(obj=shape), out_path)
        print(json.dumps({"ok": True, "error": "", "var": var}))
    except BaseException:  # noqa: BLE001
        tb = traceback.format_exc()
        print(json.dumps({"ok": False, "error": tb[-1500:], "var": ""}))


if __name__ == "__main__":
    main()
