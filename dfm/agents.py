"""Три агента: Reviewer (что менять), Modifier (как менять код), Verifier (принять ли)."""
from __future__ import annotations

import json
from dataclasses import dataclass

from . import llm
from .checks import check_spec
from .cost import compute_cost
from .sandbox import run_code

REVIEWER_SYS = """You are a Design-for-Manufacturing (DFM) reviewer for CNC milling.
You receive a CadQuery part, a machining process description, a fixed specification (the
part must keep meeting it) and a list of detected manufacturability issues with estimated
savings. Pick exactly ONE issue and propose ONE concrete, intent-preserving geometric change
that fixes it WITHOUT violating the specification (bounding box, required holes, protected
zones must not change). Be specific: which features, which numeric values (radius, chamfer size).
Reply ONLY with JSON: {"issue_id": str, "title": str, "transition": str, "rationale": str}."""

MODIFIER_SYS = """You edit CadQuery 2.x Python scripts. You get the current script and a
description of ONE change to apply. Return the COMPLETE updated script in a single ```python
block, nothing else. Rules: change as little as possible; keep all other dimensions and
features identical; keep the name of the final variable that holds the part (usually `result`);
do not call show_object or export; use only cadquery and the standard library."""


def modifier_prompt(code: str, transition: str) -> str:
    """Первый пользовательский промпт Modifier (используется и в экспорте для SFT)."""
    return (f"CURRENT SCRIPT:\n```python\n{code}\n```\n\n"
            f"CHANGE TO APPLY:\n{transition}")


def _spec_view(spec: dict) -> str:
    return json.dumps(spec, ensure_ascii=False, indent=1)[:3000]


class Reviewer:
    def propose(self, code, spec, process, report, banned_issues=()):
        issues = [i for i in report["issues"] if i["id"] not in banned_issues]
        if not issues:
            return None  # нечего улучшать -> STOP без вызова LLM
        user = (f"PROCESS:\n{json.dumps(process)}\n\nSPEC (must stay satisfied):\n{_spec_view(spec)}\n\n"
                f"CURRENT COST: {report['total']}\nISSUES:\n{json.dumps(issues, indent=1)}\n\n"
                f"CADQUERY CODE:\n```python\n{code}\n```")
        try:
            out = llm.chat([{"role": "system", "content": REVIEWER_SYS},
                            {"role": "user", "content": user}], json_mode=True, max_tokens=700)
            rec = llm.extract_json(out)
            if not isinstance(rec, dict) or not rec.get("transition"):
                raise ValueError("bad reviewer JSON")
        except Exception:  # noqa: BLE001  слабые модели иногда ломают JSON
            rec = {"title": issues[0]["id"], "transition": issues[0]["text"],
                   "rationale": "fallback: reviewer output unusable", "fallback": True}
        valid = {i["id"] for i in issues}
        if rec.get("issue_id") not in valid:
            rec["issue_id"] = issues[0]["id"]   # неверный id -> берём самую выгодную
        return rec


class Modifier:
    def __init__(self, code, transition):
        self.messages = [
            {"role": "system", "content": MODIFIER_SYS},
            {"role": "user", "content": modifier_prompt(code, transition)}]

    def generate(self) -> str:
        out = llm.chat(self.messages, max_tokens=3500)
        self.messages.append({"role": "assistant", "content": out})
        return llm.extract_code(out)

    def feedback(self, text: str):
        self.messages.append({"role": "user", "content":
            f"The script was rejected:\n{text}\nFix it and return the complete script again."})


@dataclass
class Verdict:
    accepted: bool
    feedback: str
    report: dict | None = None
    shape: object | None = None


class Verifier:
    """Программный верификатор: компиляция -> ТЗ -> стоимость должна снизиться."""

    def __init__(self, ref_shape, spec, process, min_gain=0.002):
        self.ref, self.spec, self.process, self.min_gain = ref_shape, spec, process, min_gain

    def verify(self, code, cost_before) -> Verdict:
        r = run_code(code)
        if not r.ok:
            return Verdict(False, "Script failed to run:\n" + r.error)
        chk = check_spec(r.shape, self.ref, self.spec)
        if not chk.ok:
            return Verdict(False, chk.text())
        rep = compute_cost(r.shape, self.process)
        if rep["total"] > cost_before * (1 - self.min_gain):
            return Verdict(False, f"Spec is OK, but manufacturing cost did not decrease "
                                  f"(before {cost_before}, after {rep['total']}). "
                                  f"Remaining issues: {[(i['id'], i['count']) for i in rep['issues']]}. "
                                  "The change must actually remove the issue.", rep, r.shape)
        return Verdict(True, "accepted", rep, r.shape)
