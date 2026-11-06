"""Baseline: ОДИН вызов модели «оптимизируй деталь под производство» — без цикла,
без обратной связи, без повторов. Результат проверяется той же check_spec и тем же cost.

python -m dfm.oneshot --parts parts --out runs/qwen7b/seed0/oneshot [--blind]
  --blind : модель не получает список проблем из cost-модели (только код, процесс и ТЗ)
"""
import argparse
import json
import time
import traceback
from pathlib import Path

from . import llm
from .agents import _spec_view
from .checks import check_spec, load_spec
from .cost import compute_cost, load_process
from .evaluate import part_dirs
from .sandbox import run_code

SYS = """You are an expert in Design for Manufacturing for CNC milling (3-axis).
Modify the given CadQuery 2.x script so the part is cheaper and easier to machine under the
given process, while STRICTLY satisfying the specification (bounding box, required holes and
protected zones must not change). Return the COMPLETE updated script in a single ```python
block, nothing else. Keep the name of the final variable that holds the part. Do not call
show_object or export."""


def run_part(pdir: Path, out: Path, process, hints=True):
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        print(f"[skip] {pdir.name}")
        return
    t0 = time.time()
    code = (pdir / "part.py").read_text()
    spec = load_spec(pdir / "spec.json")
    ref = run_code(code)
    if not ref.ok:
        (out / "summary.json").write_text(json.dumps(dict(part=pdir.name, error=ref.error)))
        return
    base = compute_cost(ref.shape, process)
    user = f"PROCESS:\n{json.dumps(process)}\n\nSPEC (must stay satisfied):\n{_spec_view(spec)}\n\n"
    if hints:
        user += f"DETECTED ISSUES:\n{json.dumps(base['issues'], indent=1)}\n\n"
    user += f"CADQUERY CODE:\n```python\n{code}\n```"
    raw = llm.chat([{"role": "system", "content": SYS}, {"role": "user", "content": user}],
                   max_tokens=3500)
    new_code = llm.extract_code(raw)
    res = run_code(new_code)
    s = dict(part=pdir.name, method="oneshot", cost_before=base["total"], valid=False,
             cost_after_raw=None, reason="")
    if not res.ok:
        s["reason"] = "run_error: " + res.error.strip().splitlines()[-1][:200]
    else:
        chk = check_spec(res.shape, ref.shape, spec)
        rep = compute_cost(res.shape, process)
        s["cost_after_raw"] = rep["total"]
        s["valid"] = chk.ok
        s["reason"] = "" if chk.ok else "; ".join(chk.reasons)[:300]
    improved = s["valid"] and s["cost_after_raw"] < base["total"]
    # итог как у пользователя, который принимает результат только если ТЗ выполнено и стало дешевле
    s["cost_after"] = s["cost_after_raw"] if improved else base["total"]
    s["saving_pct"] = round(100 * (1 - s["cost_after"] / base["total"]), 2)
    s["raw_saving_pct"] = (round(100 * (1 - s["cost_after_raw"] / base["total"]), 2)
                           if s["cost_after_raw"] is not None else None)
    s["sec"] = round(time.time() - t0, 1)
    (out / "final.py").write_text(new_code)
    (out / "summary.json").write_text(json.dumps(s, indent=1))
    print(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="parts")
    ap.add_argument("--process", default="process.json")
    ap.add_argument("--out", default="runs/oneshot")
    ap.add_argument("--only", default=None)
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--temperature", type=float, default=None)
    a = ap.parse_args()
    if a.seed is not None:
        llm.SETTINGS["seed"] = a.seed
    if a.temperature is not None:
        llm.SETTINGS["temperature"] = a.temperature
    proc = load_process(a.process)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "config.json").write_text(json.dumps(dict(
        method="oneshot", model=llm.MODEL, **llm.SETTINGS, blind=a.blind, process=proc),
        indent=1, default=str))
    for d in part_dirs(a.parts):
        if a.only and d.name != a.only:
            continue
        try:
            run_part(d, Path(a.out) / d.name, proc, hints=not a.blind)
        except Exception:  # noqa: BLE001
            print(f"[error] {d.name}\n{traceback.format_exc()[-800:]}")


if __name__ == "__main__":
    main()
