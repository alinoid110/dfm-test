"""Безопасный запуск кода CadQuery: отдельный процесс + таймаут."""
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

WORKER = str(Path(__file__).with_name("worker.py"))


@dataclass
class RunResult:
    ok: bool
    shape: Optional[object] = None  # cq.Shape
    error: str = ""


def run_code(code: str, timeout: int = 90) -> RunResult:
    import cadquery as cq

    with tempfile.TemporaryDirectory() as td:
        code_p, step_p = Path(td) / "code.py", Path(td) / "out.step"
        code_p.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run([sys.executable, WORKER, str(code_p), str(step_p)],
                                  capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return RunResult(False, None, f"Timeout: script ran longer than {timeout}s.")
        lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
        try:
            info = json.loads(lines[-1])
        except Exception:  # noqa: BLE001
            return RunResult(False, None, "Worker crashed:\n" + (proc.stderr or "")[-1500:])
        if not info["ok"]:
            return RunResult(False, None, info["error"])
        try:
            wp = cq.importers.importStep(str(step_p))
            shape = wp.val()
        except Exception as e:  # noqa: BLE001
            return RunResult(False, None, f"STEP re-import failed: {e}")
        return RunResult(True, shape, "")
