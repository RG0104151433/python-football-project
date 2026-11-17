"""Join the morning's sourced results to sealed forecasts; never refit them."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "presentation"
SOURCE = ROOT / "data/external/future_predictions/unl-november-2026/results-20261117/uefa_results_source.json"
FORECASTS = ROOT / "outputs/tables/future_predictions/future-unl-61f639846da9193d4cca/forecasts.csv"
OUT = ROOT / "outputs/tables/future_predictions/results-check-20261117-am"
ALIASES = {"Türkiye": "Turkey", "Czechia": "Czech Republic"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row, source=False):
    home = row["home_label" if source else "home_team"]
    away = row["away_label" if source else "away_team"]
    return row["date"], ALIASES.get(home, home), ALIASES.get(away, away)


def write_csv(path, fields, rows):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))


def main():
    source = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    cutoff = datetime.fromisoformat(source["checked_at"])
    with FORECASTS.open(encoding="utf-8-sig", newline="") as handle:
        forecasts = list(csv.DictReader(handle))
    assert len(forecasts) == 52 and len({r["match_id"] for r in forecasts}) == 52
    primary = {key(r, True): r for r in source["primary_records"]}
    assert len(primary) == 52 and set(primary) == {key(f) for f in forecasts}
    secondary = {}
    for r in source["secondary_occurrences"]:
        k = key(r, True)
        value = r["status"], r["home_score"], r["away_score"]
        if k in secondary and secondary[k] != value:
            raise ValueError(f"Conflicting UEFA team-page values: {k}")
        secondary[k] = value
    assert set(primary) == set(secondary)
    for k, r in primary.items():
        assert secondary[k] == (r["status"], r["home_score"], r["away_score"]), k

    checked, table, evaluator = [], [], []
    main_labels, aux_labels = [], []
    main_losses, aux_losses = [], []
    pending, withheld_final = 0, 0
    for f in forecasts:
        r = primary[key(f)]
        assert r["group"] == f["group"]
        kick = datetime.fromisoformat(f["date"] + "T" + f["kickoff_cet"]).replace(
            tzinfo=timezone(timedelta(hours=1)))
        final = r["status"] == "final"
        if final:
            assert kick + timedelta(minutes=90) < cutoff
            assert all(type(r[x]) is int and r[x] >= 0 for x in ["home_score", "away_score"])
        else:
            assert kick > cutoff, "A past fixture needs a verified status, not an assumed pending value"
            pending += 1
        hs, aws = (r["home_score"], r["away_score"]) if final else ("", "")
        native = [float(f[x]) for x in ["native_home_probability", "native_draw_probability", "native_away_probability"]]
        native_pick = max(range(3), key=lambda i: native[i])
        p = float(f["main_home_probability"]) if f["main_home_probability"] else None
        outcome = (0 if hs > aws else 1 if hs == aws else 2) if final else None
        main_check = aux_check = "pending"
        if final:
            aux_correct = native_pick == outcome
            aux_labels.append(aux_correct)
            aux_check = "correct" if aux_correct else "wrong"
            aux_losses.append(-math.log(max(1e-6, native[outcome])))
            if p is None:
                main_check = "withheld"
                withheld_final += 1
            else:
                correct = (p >= .5) == (outcome == 0)
                main_labels.append(correct)
                main_check = "correct" if correct else "wrong"
                main_losses.append(-math.log(max(1e-6, p if outcome == 0 else 1 - p)))
        checked.append(dict(fixture_id=f["match_id"], status=r["status"], home_score=hs,
                            away_score=aws, source_url=source["primary_url"], checked_at=source["checked_at"]))
        table.append(dict(fixture_id=f["match_id"], date_cet=f["date"],
                          kickoff_beijing=kick.astimezone(timezone(timedelta(hours=8))).isoformat(),
                          round=f["round"], group=f["group"], home_team=f["home_team"], away_team=f["away_team"],
                          status=r["status"], actual_score=f"{hs}-{aws}" if final else "", actual_outcome=["home", "draw", "away"][outcome] if final else "",
                          main_home_probability=f["main_home_probability"], main_pick=f["main_pick"], main_check=main_check,
                          latent_probability_p05=f["latent_probability_p05"], latent_probability_p95=f["latent_probability_p95"],
                          auxiliary_home_probability=f["native_home_probability"], auxiliary_draw_probability=f["native_draw_probability"],
                          auxiliary_away_probability=f["native_away_probability"], auxiliary_pick=f["native_pick"], auxiliary_check=aux_check,
                          source_url=source["primary_url"], crosscheck_url=source["secondary_url"], checked_at=source["checked_at"]))
        if final:
            evaluator.append(dict(match_id=f["match_id"], home_score=hs, away_score=aws,
                                  final_confirmed="true", observed_at_utc=cutoff.astimezone(timezone.utc).isoformat(),
                                  source_url=source["primary_url"]))
    assert len(evaluator) == 44 and pending == 8 and withheld_final == 1
    assert len(main_labels) == 43 and len(aux_labels) == 44
    OUT.mkdir(parents=True, exist_ok=True)
    checked_path = SOURCE.parent / "results_checked_20261117.csv"
    write_csv(checked_path, list(checked[0]), checked)
    write_csv(OUT / "results_vs_forecasts_20261117.csv", list(table[0]), table)
    write_csv(OUT / "confirmed_results_for_evaluator.csv", list(evaluator[0]), evaluator)
    (HERE / checked_path.name).write_bytes(checked_path.read_bytes())

    def metrics(labels, losses):
        return dict(evaluated=len(labels), correct=sum(labels), wrong=len(labels)-sum(labels),
                    accuracy=sum(labels)/len(labels), log_loss=sum(losses)/len(losses))

    summary = dict(schema_version=1, decision_log_id="R20261117-01", checked_at=source["checked_at"],
                   forecast_run="future-unl-61f639846da9193d4cca", forecast_sha256=sha(FORECASTS),
                   source=str(SOURCE.relative_to(ROOT)).replace("\\", "/"), source_sha256=sha(SOURCE),
                   checked_csv=str(checked_path.relative_to(ROOT)).replace("\\", "/"), checked_csv_sha256=sha(checked_path),
                   fixtures=52, final=44, pending=8, main_withheld_total=3, main_withheld_completed=1,
                   main=metrics(main_labels, main_losses), auxiliary=metrics(aux_labels, aux_losses),
                   cutoff_policy="Verified as of Beijing morning; Nov 17 CET fixtures remain pending until Nov 18 Beijing time",
                   decision_rules=dict(main="p>=0.5 -> home win; draw/away -> non-home win", auxiliary="argmax home/draw/away; ties in that order", score="90 minutes plus stoppage time"),
                   sources_crosschecked=52, crosscheck_independent_organization=False,
                   human_review=False, models_refitted=False, forecasts_modified=False,
                   all_fixtures_evaluated=False)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    payload = dict(checked_at=source["checked_at"], csv_sha256=sha(checked_path),
                   csv=checked_path.read_text(encoding="utf-8-sig"), summary=summary)
    (HERE / "verified_results_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
