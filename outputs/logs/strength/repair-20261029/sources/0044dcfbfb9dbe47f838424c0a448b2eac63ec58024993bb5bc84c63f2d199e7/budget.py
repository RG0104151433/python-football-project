"""Development-only numerical refinement; never choose budget by validation loss."""
from __future__ import annotations

import argparse

from .experiment import params, stream
from .io import ROOT, config, publish, read_rows


def run(cfg, learning):
    labels = set(cfg["pilot"]["teams"])
    games = [dict(match_id=r["match_id"], date=r["date"], home=r["home_entity_id"], away=r["away_entity_id"],
                  venue=0 if r["is_neutral"] == "true" else 1, friendly=r["tournament_group"] == "friendly",
                  outcome=int(r["outcome_index"]))
             for r in read_rows(learning / "learning_matches.csv")
             if r["home_team"] in labels and r["away_team"] in labels and r["date"] <= "1974-12-31"]
    comparisons, forecasts, diagnostics = [], [], []
    previous = None
    for size, cap in [(8, 2), (16, 3), (32, 3), (64, 3), (64, 4)]:
        numerical = {**cfg["numerics"], "max_components": size, "jump_total_cap": cap,
                     "max_children_per_parent": 1024}
        rows, engine = stream(games, cfg, params(cfg, {"id": "both"}), numerical=numerical)
        evaluation = [r for r in rows if "1970" <= r["date"] <= "1974-12-31"]
        current = {r["match_id"]: r for r in evaluation}
        gap = None if previous is None else max(max(abs(r[k] - previous[mid][k]) for k in
                                                    ("p_home", "p_draw", "p_away")) for mid, r in current.items())
        row = dict(components=size, count_cap=cap, development_matches=len(evaluation),
                   previous_max_probability_difference=gap,
                   within_gate=None if gap is None else gap <= cfg["numerics"]["precision_checks"]["probability_error_gate"],
                   max_pruned_mass=max(d["approximate_posterior_pruned_mass"] for d in engine.diagnostics),
                   max_prior_tail=max(d["transition_prior_tail"] for d in engine.diagnostics))
        comparisons.append(row)
        forecasts.extend(dict(components=size, count_cap=cap, **r) for r in rows)
        diagnostics.extend(dict(components=size, count_cap=cap, **r) for r in engine.diagnostics)
        previous = current
        print(f"Budget {size}/{cap}: {gap}", flush=True)
    report = {"purpose": "development-only numerical budget refinement after initial gate failure",
              "initial_pilot": "outputs/logs/strength/pilot-a41a495cc63d6120327a",
              "no_validation_or_post1980_used": True,
              "last_three_increments_within_gate": all(r["within_gate"] for r in comparisons[-3:]),
              "production_ready": False,
              "limit": "adjacent-budget agreement on21 development games is not a rigorous total approximation bound"}
    return publish("budget", {"config": cfg, "learning_path": learning.relative_to(ROOT).as_posix(),
                              "rule": "8/2,16/3,32/3,64/3,64/4; gate remains0.01; no predictive retuning"},
                   csvs={"budget_comparisons.csv": comparisons, "development_predictions.csv": forecasts,
                         "daily_diagnostics.csv": diagnostics}, jsons={"report.json": report})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learning", required=True)
    args = parser.parse_args()
    learning = (ROOT / args.learning).resolve()
    if not learning.is_relative_to(ROOT):
        raise ValueError("Learning path outside workspace")
    folder, _ = run(config(), learning)
    print(folder.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
