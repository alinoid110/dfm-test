"""Сводная таблица: модель × метод (loop / oneshot) по всем seed.

python -m dfm.compare --runs runs --out results.csv
Ожидаемая структура: runs/<model_tag>/seed<k>/<loop|oneshot>/<part>/summary.json
"""
import argparse
import json
from pathlib import Path

import pandas as pd


def collect(root: Path) -> pd.DataFrame:
    rows = []
    for sp in root.glob("*/seed*/*/*/summary.json"):
        tag, seed, method, part = sp.parts[-5], sp.parts[-4], sp.parts[-3], sp.parts[-2]
        s = json.loads(sp.read_text())
        if "error" in s:
            continue
        rows.append(dict(model=tag, seed=seed, method=method, part=part,
                         cost_before=s["cost_before"], cost_after=s["cost_after"],
                         saving_pct=s["saving_pct"], valid=s.get("valid", True),
                         sec=s.get("sec")))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--out", default="results.csv")
    a = ap.parse_args()
    df = collect(Path(a.runs))
    if df.empty:
        print("нет summary.json в", a.runs)
        return
    df["improved"] = df["saving_pct"] > 0
    g = df.groupby(["model", "method"])
    t = g.agg(n=("part", "count"),
              valid_pct=("valid", lambda x: round(100 * x.mean(), 1)),
              improved_pct=("improved", lambda x: round(100 * x.mean(), 1)),
              mean_saving_pct=("saving_pct", "mean"),
              median_saving_pct=("saving_pct", "median"),
              mean_sec=("sec", "mean")).round(2)
    print(t.to_string())
    # прямое сравнение loop vs oneshot по одинаковым (model, seed, part)
    piv = df.pivot_table(index=["model", "seed", "part"], columns="method",
                         values="saving_pct")
    if {"loop", "oneshot"} <= set(piv.columns):
        piv = piv.dropna()
        w = piv.assign(loop_wins=piv["loop"] > piv["oneshot"],
                       tie=piv["loop"] == piv["oneshot"]).groupby("model")[["loop_wins", "tie"]].sum()
        w["total"] = piv.groupby("model").size()
        print("\nloop лучше oneshot (число деталей):")
        print(w.to_string())
    df.to_csv(a.out, index=False)
    t.to_csv(Path(a.out).with_suffix(".summary.csv"))
    print("saved", a.out)


if __name__ == "__main__":
    main()
