"""Prespecified development-only reducer comparison; no winner by validation."""
from __future__ import annotations
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.strength.io import read_rows, config, publish
from src.strength.experiment import params, score
from src.strength.reduction import ReducedStrengthFilter


def run():
    begin = time.perf_counter()
    protocol = json.loads((ROOT/"config/strength_refinement.json").read_text(encoding="utf-8"))
    cfg = config(protocol["base_protocol"])
    labels = set(cfg["pilot"]["teams"])
    data = [dict(match_id=r["match_id"], date=r["date"], home=r["home_entity_id"], away=r["away_entity_id"],
                 venue=0 if r["is_neutral"]=="true" else 1, friendly=r["tournament_group"]=="friendly",
                 outcome=int(r["outcome_index"])) for r in read_rows(ROOT/protocol["learning"]/"learning_matches.csv")
            if r["home_team"] in labels and r["away_team"] in labels and r["date"] <= protocol["analysis_end"]]
    grouped = defaultdict(list)
    for g in data:
        grouped[g["date"]].append(g)
    predictions, summary, diagnostics = [], [], []
    cache = {}
    for method in protocol["reducers"]:
        previous = None
        for size in protocol["components"]:
            numerical = {**cfg["numerics"], "reducer": method, "max_components": size,
                         "jump_total_cap": protocol["jump_total_cap"], "max_children_per_parent": protocol["maximum_children"]}
            engine = ReducedStrengthFilter({g[k] for g in data for k in ("home", "away")},
                                            params(cfg, {"id": "both"}), numerical)
            rows = []
            for day, batch in sorted(grouped.items()):
                rows.extend(engine.day(day, batch))
            evaluated = [r for r in rows if r["date"] >= protocol["comparison_start"]]
            current = {r["match_id"]: r for r in evaluated}
            gap = None if previous is None else max(max(abs(r[k]-previous[mid][k]) for k in
                                  ("p_home", "p_draw", "p_away")) for mid,r in current.items())
            summary.append(dict(method=method, components=size, **score(evaluated),
                                previous_max_probability_difference=gap,
                                moment_error=max(d["moment_error"] for d in engine.diagnostics),
                                probability_gate_pass=None if gap is None else gap<=protocol["probability_gate"]))
            predictions.extend(dict(method=method, components=size, **r) for r in rows)
            diagnostics.extend(dict(method=method, components=size, **d) for d in engine.diagnostics)
            cache[(method,size)] = current
            previous = current
            print(method, size, "gap", gap, flush=True)
    highest = protocol["components"][-1]
    cross = max(max(abs(r[k]-cache[("runnalls",highest)][mid][k]) for k in ("p_home","p_draw","p_away"))
                for mid,r in cache[("cluster",highest)].items())
    report = {"protocol": protocol, "comparison_scope": "six-team development<=1974 only",
              "cross_method_highest_budget_difference": cross,
              "last_two_budget_increments_pass": {m: all(r["probability_gate_pass"] for r in summary
                                                if r["method"]==m and r["components"] in protocol["components"][-2:]) for m in protocol["reducers"]},
              "cross_method_within_gate": cross<=protocol["probability_gate"],
              "production_ready": False, "no_validation_or_post1980_used": True}
    folder,_ = publish("reduction", {"protocol": protocol, "base": cfg}, csvs={
        "comparisons.csv": summary, "development_predictions.csv": predictions,
        "daily_diagnostics.csv": diagnostics}, jsons={"report.json": report})
    print(folder.relative_to(ROOT).as_posix(), "seconds", time.perf_counter()-begin, flush=True)


if __name__ == "__main__":
    run()
