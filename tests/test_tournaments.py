"""Worked examples for Q2; real repository inputs are never mutated."""
import copy
import json
from pathlib import Path

import pytest

from src.data_contract import PrepError
from src.tournaments.checks import validate_tables
from src.tournaments.data import assert_same_sample, load_settings, validate_results
from src.tournaments.reporting import publish, sorted_rows, table_artifacts
from src.tournaments.rolling import build_rolling, enumerate_membership, make_windows
from src.tournaments.standardize import build_main
from src.tournaments.statistics import build_counts

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def analysis():
    return dict(data_version="toy", analysis_start="1980-01-01", analysis_end="1999-12-31",
                eras=[dict(id="early", start="1980-01-01", end="1989-12-31", label="early"),
                      dict(id="late", start="1990-01-01", end="1999-12-31", label="late")])


def record(year, number, group="friendly", outcome="home", day=None):
    return dict(match_id=str(number), date=day or f"{year}-01-01", year=year, tournament_group=group,
                outcome=outcome, home_win=int(outcome=="home"), home_score=int(outcome=="home"),
                away_score=int(outcome=="away"), result_basis="after_extra_time_excluding_shootout")


def toy_rows():
    # Both types have 40% in the early era and 60% later. Different era mixes
    # give 44% versus 56% observed rates; a common mix gives 50% for each.
    rows=[]
    for year,group,n,wins in [(1980,"friendly",80,32),(1980,"non_friendly",20,8),
                              (1990,"friendly",20,12),(1990,"non_friendly",80,48)]:
        rows += [record(year,len(rows)+i,group,"home" if i<wins else "draw") for i in range(n)]
    return rows


def build(rows,analysis):
    tables=dict(analysis_membership=[dict(match_id=r["match_id"],included=True,sample_id="toy") for r in rows],grouped_counts=build_counts(rows,analysis))
    main,defs=build_main(tables["grouped_counts"],analysis,"toy");tables.update(main)
    rolling,more=build_rolling(rows,tables["grouped_counts"],analysis,"toy")
    for k,v in rolling.items():tables.setdefault(k,[]).extend(v)
    return tables,defs+more


def test_composition_alone_can_change_overall_gap(analysis):
    rows=toy_rows();tables,defs=build(rows,analysis)
    rates={(r["estimand"],r["tournament_group"]):r["estimate"] for r in tables["type_estimates"] if r["scope"]=="overall"}
    assert rates[("raw","friendly")]==pytest.approx(.44)
    assert rates[("raw","non_friendly")]==pytest.approx(.56)
    assert rates[("era_standardized","friendly")]==pytest.approx(.5)
    assert rates[("era_standardized","non_friendly")]==pytest.approx(.5)
    diffs={r["estimand"]:r for r in tables["type_differences"] if r["scope"]=="overall"}
    assert diffs["raw"]["estimate"]==pytest.approx(-12)
    assert diffs["era_standardized"]["estimate"]==pytest.approx(0)
    assert validate_tables(rows,analysis,tables,defs,"toy")["passed"]


def test_positive_weight_missing_type_is_not_zero(analysis):
    rows=[record(1980,1),record(1990,2),record(1990,3,"non_friendly")]
    tables,defs=build(rows,analysis)
    target=next(r for r in tables["type_estimates"] if r["scope"]=="overall" and r["estimand"]=="era_standardized" and r["tournament_group"]=="non_friendly")
    assert target["estimate"] is None and target["status"]=="missing_stratum"
    d=next(d for d in defs if d["target_id"]==target["estimate_id"])
    assert d["missing_strata"]["non_friendly"]==["early"]
    raw=next(r for r in tables["type_differences"] if r["scope"]=="overall" and r["estimand"]=="raw")
    assert raw["estimate"] is not None
    assert validate_tables(rows,analysis,tables,defs,"toy")["passed"]


def test_empty_year_weight_zero_and_empty_reference(analysis):
    tables,defs=build(toy_rows(),analysis)
    weights=[w for w in tables["reference_weights"] if w["period_id"]=="1980_1989"]
    assert next(w for w in weights if w["stratum_id"]=="1981")["weight"]==0
    assert next(r for r in tables["rolling_windows"] if r["window_id"]=="1980_1989")["n_observed_years"]==1
    empty,defs=build([],analysis)
    assert all(r["estimate"] is None for r in empty["type_estimates"])
    assert all(r["status"]=="empty_reference" for r in empty["type_estimates"] if r["estimand"]!="raw")
    assert validate_tables([],analysis,empty,defs,"toy")["passed"]


def test_window_endpoints_overlap_and_duplicate_rejection(analysis):
    windows=make_windows(analysis)
    assert windows[0]["start_date"]=="1980-01-01" and windows[-1]["end_date"]=="1999-12-31"
    rows=[record(1980,1),record(1989,2,day="1989-12-31"),record(1990,3),record(1999,4,day="1999-12-31")]
    members=enumerate_membership(rows,windows)
    first={r["match_id"] for r in members if r["window_id"]=="1980_1989"}
    assert first=={"1","2"}
    assert sum(r["match_id"]=="2" for r in members)==10
    with pytest.raises(PrepError,match="Repeated"):
        enumerate_membership(rows+rows[:1],windows)


def test_draw_and_shootout_do_not_change_main_result():
    row=record(1980,1,outcome="draw");row.update(shootout_winner_id="home")
    validate_results([row]);assert row["home_win"]==0
    row["outcome"]="home"
    with pytest.raises(PrepError):validate_results([row])


def test_same_number_different_ids_fails():
    with pytest.raises(PrepError) as exc:
        assert_same_sample([dict(match_id="A")],["B"])
    assert exc.value.code=="TQ_Q1_SAMPLE_MISMATCH"


@pytest.mark.parametrize("change",[{"inference_mode":"bootstrap"},{"sensitivity":True},{"difference_direction":"non_friendly_minus_friendly"},
                                  {"rolling":dict(window_years=5,step_years=1,alignment="trailing_calendar_years",reference_scheme="pooled_year_counts")}])
def test_unapproved_analysis_switches_rejected(tmp_path,change):
    cfg=json.loads((PROJECT/"config/tournaments.json").read_text(encoding="utf-8"));cfg.update(change)
    (tmp_path/"cfg.json").write_text(json.dumps(cfg),encoding="utf-8")
    with pytest.raises(PrepError):load_settings(tmp_path,"cfg.json")


def test_failed_publication_does_not_write_new_or_change_existing_files(tmp_path):
    publish(tmp_path,{"old.csv":b"old"})
    with pytest.raises(PrepError) as exc:publish(tmp_path,{"new.csv":b"new","old.csv":b"different"})
    assert exc.value.code=="TQ_REPRODUCIBILITY_MISMATCH"
    assert (tmp_path/"old.csv").read_bytes()==b"old" and not (tmp_path/"new.csv").exists()


def test_auto_check_detects_corrupted_rate(analysis):
    rows=toy_rows();tables,defs=build(rows,analysis)
    tables["type_estimates"][0]["estimate"]+=.01
    with pytest.raises(PrepError):validate_tables(rows,analysis,tables,defs,"toy")


def test_serialization_contract_and_unimplemented_intervals(analysis):
    tables,_=build(toy_rows(),analysis)
    from src.data_contract import csv_bytes
    from src.tournaments.reporting import FIELDS
    for name in ("type_estimates","type_differences","reference_weights","window_membership"):
        data=csv_bytes(FIELDS[name].split(),sorted_rows(name,tables[name]))
        assert data.startswith(b"\xef\xbb\xbf") and b"\r" not in data
    assert all(r["uncertainty_status"]=="not_run" and r["ci_lower"] is None for r in tables["type_estimates"])


def test_failed_main_run_is_recorded_and_does_not_publish(tmp_path):
    from scripts.analyze_tournaments import run_analysis
    (tmp_path/"bad.json").write_text("{}",encoding="utf-8")
    with pytest.raises(PrepError):run_analysis(tmp_path,"bad.json")
    manifests=list((tmp_path/"outputs/logs/tournaments").glob("*/run_manifest.json"))
    assert len(manifests)==1
    assert json.loads(manifests[0].read_text(encoding="utf-8"))["status"]=="failed"
    assert not (tmp_path/"outputs/tables").exists()
