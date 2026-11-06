"""Полный эксперимент: для каждой модели поднять vLLM, прогнать loop и oneshot по seed'ам.

python -m dfm.run_models --models models.json --seeds 0 1 2 --runs runs
Возобновляемо: готовые детали (summary.json) пропускаются. --dry-run печатает команды.
Модели из models.json: проверьте, что id существуют на HuggingFace (и что нет gated-доступа).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

PORT = 8000


def wait_server(timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            requests.get(f"http://localhost:{PORT}/v1/models", timeout=2)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(5)
    return False


def sh(cmd, env, dry):
    print("$", " ".join(cmd))
    if not dry:
        subprocess.run(cmd, env=env, check=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="models.json")
    ap.add_argument("--parts", default="parts")
    ap.add_argument("--process", default="process.json")
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--max-model-len", type=int, default=8192)
    ap.add_argument("--only", default=None, help="tag одной модели")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    py = sys.executable
    for m in json.loads(Path(a.models).read_text()):
        if a.only and m["tag"] != a.only:
            continue
        env = dict(os.environ, LLM_BASE_URL=f"http://localhost:{PORT}/v1", LLM_MODEL=m["model"])
        srv = None
        if not a.dry_run:
            log = open(f"vllm_{m['tag']}.log", "w")
            srv = subprocess.Popen(["vllm", "serve", m["model"], "--dtype", "half",
                                    "--max-model-len", str(a.max_model_len),
                                    "--gpu-memory-utilization", "0.90", "--port", str(PORT),
                                    *m.get("vllm_args", [])], stdout=log, stderr=subprocess.STDOUT)
            if not wait_server():
                print(f"[error] сервер для {m['tag']} не поднялся, см. vllm_{m['tag']}.log")
                srv.terminate()
                continue
        try:
            for seed in a.seeds:
                base = Path(a.runs) / m["tag"] / f"seed{seed}"
                common = ["--parts", a.parts, "--process", a.process, "--seed", str(seed),
                          "--temperature", str(a.temperature)]
                sh([py, "-m", "dfm.loop", *common, "--out", str(base / "loop")], env, a.dry_run)
                sh([py, "-m", "dfm.oneshot", *common, "--out", str(base / "oneshot")], env, a.dry_run)
        finally:
            if srv:
                srv.terminate()
                srv.wait(timeout=60)
                time.sleep(10)  # дать освободиться памяти GPU


if __name__ == "__main__":
    main()
