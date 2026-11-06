"""Агентный цикл: Reviewer -> Modifier <-> Verifier, по одной проверенной правке за раз.

python -m dfm.loop --parts parts --process process.json --out runs/qwen7b
"""
import argparse
import json
import time
import traceback
from pathlib import Path

from . import llm
from .agents import Modifier, Reviewer, Verifier
from .checks import load_spec
from .cost import compute_cost, load_process
from .evaluate import part_dirs
from .sandbox import run_code


def log(fh, **kw):
    fh.write(json.dumps(kw, ensure_ascii=False, default=str) + "\n")
    fh.flush()


def run_part(pdir: Path, out: Path, process, max_steps=5, max_retries=4):
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
    report = compute_cost(ref.shape, process)
    cost0 = report["total"]
    verifier, reviewer = Verifier(ref.shape, spec, process), Reviewer()
    banned = set()
    with open(out / "trajectory.jsonl", "a") as fh:
        for step in range(max_steps):
            rec = reviewer.propose(code, spec, process, report, banned)
            if rec is None:
                log(fh, step=step, event="stop", reason="no actionable issues left")
                break
            log(fh, step=step, event="recommendation", **rec, cost=report["total"])
            mod, accepted = Modifier(code, rec["transition"]), False
            for attempt in range(max_retries):
                new_code = mod.generate()
                v = verifier.verify(new_code, report["total"])
                log(fh, step=step, attempt=attempt, event="attempt", accepted=v.accepted,
                    feedback=v.feedback[:800], cost_after=(v.report or {}).get("total"),
                    code=new_code, code_before=code)
                if v.accepted:
                    code, report, accepted = new_code, v.report, True
                    break
                mod.feedback(v.feedback)
            if not accepted:
                banned.add(rec["issue_id"])   # не повторять эту проблему
    (out / "final.py").write_text(code)
    summary = dict(part=pdir.name, method="loop", valid=True, cost_before=cost0, cost_after=report["total"],
                   saving_pct=round(100 * (1 - report["total"] / cost0), 2),
                   remaining=[(i["id"], i["count"]) for i in report["issues"]],
                   sec=round(time.time() - t0, 1))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(summary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="parts")
    ap.add_argument("--process", default="process.json")
    ap.add_argument("--out", default="runs/run1")
    ap.add_argument("--only", default=None, help="id детали (имя папки)")
    ap.add_argument("--max-steps", type=int, default=5)
    ap.add_argument("--retries", type=int, default=4)
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
        method="loop", model=llm.MODEL, **llm.SETTINGS, max_steps=a.max_steps,
        retries=a.retries, process=proc), indent=1, default=str))
    for d in part_dirs(a.parts):
        if a.only and d.name != a.only:
            continue
        try:
            run_part(d, Path(a.out) / d.name, proc, a.max_steps, a.retries)
        except Exception:  # noqa: BLE001  один сбой не должен убивать весь прогон
            print(f"[error] {d.name}\n{traceback.format_exc()[-800:]}")


if __name__ == "__main__":
    main()
