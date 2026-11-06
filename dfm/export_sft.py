"""Собирает обучающие данные из траекторий цикла.

python -m dfm.export_sft --runs runs --out data
Создаёт:
  data/trajectories.jsonl  — по записи на принятую правку: контекст -> принятый код + метаданные
  data/sft.jsonl           — формат chat messages (system/user/assistant), для TRL SFTTrainer
  data/dpo.jsonl           — prompt / chosen / rejected (отклонённая попытка того же шага)
Берутся только шаги, где правка принята Verifier'ом (ТЗ выполнено, стоимость снизилась).
"""
import argparse
import json
from pathlib import Path

from .agents import MODIFIER_SYS, modifier_prompt


def fence(code: str) -> str:
    return "```python\n" + code.strip() + "\n```"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--out", default="data")
    ap.add_argument("--only-model", default=None, help="tag модели (напр. только лучшей)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    n_traj = n_dpo = 0
    with open(out / "trajectories.jsonl", "w") as ft, open(out / "sft.jsonl", "w") as fs, \
            open(out / "dpo.jsonl", "w") as fd:
        for tp in sorted(Path(a.runs).glob("*/seed*/loop/*/trajectory.jsonl")):
            model, seed, part = tp.parts[-5], tp.parts[-4], tp.parts[-2]
            if a.only_model and model != a.only_model:
                continue
            events = [json.loads(l) for l in open(tp)]
            rec_by_step, rejected = {}, {}
            for e in events:
                if e["event"] == "recommendation":
                    rec_by_step[e["step"]] = e
                    rejected[e["step"]] = []
                elif e["event"] == "attempt":
                    rec = rec_by_step.get(e["step"])
                    if rec is None:
                        continue
                    if not e["accepted"]:
                        rejected[e["step"]].append(e["code"])
                        continue
                    prompt = modifier_prompt(e["code_before"], rec["transition"])
                    meta = dict(model=model, seed=seed, part=part, step=e["step"],
                                attempt=e["attempt"], issue_id=rec["issue_id"],
                                cost_before=rec["cost"], cost_after=e["cost_after"])
                    ft.write(json.dumps(dict(system=MODIFIER_SYS, prompt=prompt,
                                             completion=e["code"], **meta),
                                        ensure_ascii=False) + "\n")
                    fs.write(json.dumps({"messages": [
                        {"role": "system", "content": MODIFIER_SYS},
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": fence(e["code"])}]},
                        ensure_ascii=False) + "\n")
                    n_traj += 1
                    for bad in rejected[e["step"]]:
                        fd.write(json.dumps(dict(system=MODIFIER_SYS, prompt=prompt,
                                                 chosen=fence(e["code"]), rejected=fence(bad),
                                                 **meta), ensure_ascii=False) + "\n")
                        n_dpo += 1
    print(f"принятых правок (SFT): {n_traj}, пар для DPO: {n_dpo} -> {out}/")


if __name__ == "__main__":
    main()
