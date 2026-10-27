"""Expanded scope: role-consistent exceptions, directed cells and source history."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_region_protocol import build
from src.regions.describe import build_counts
from src.regions.export import fields_for, registered_path, verify_run
from src.regions.groups import build_groups, matches_group
from src.regions.io import RegionError, apply_study_labels, sha, study_labels
from src.regions.standardize import build_adjustments

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def classification():
    return json.loads((ROOT / "config/regions_study_overrides.json").read_text(encoding="utf-8"))


def fact(home, away, hr, hu, ar, au):
    return dict(match_id="toy", date="1980-01-01", home_team_id=home, away_team_id=away,
                home_region=hr, home_unit=hu, away_region=ar, away_unit=au,
                home_rule_id="H", away_rule_id="A", direction=hr + ">" + ar,
                relation="same_unit" if hr == ar and hu == au else "same_region_diff_unit" if hr == ar else "cross_region",
                A_usable=True, B_usable=True, C_usable=True, A_reason="base", B_reason="base", C_reason="base")


@pytest.mark.parametrize("team,hr,hu,region,unit", [
    ("team:iran", "142", "034", "142", "145"),
    ("team:australia", "009", "053", "142", "035"),
    ("team:turkey", "142", "145", "150", "039"),
])
def test_requested_override_applies_in_both_roles_and_preserves_base(classification, team, hr, hu, region, unit):
    source = fact(team, team, hr, hu, hr, hu)
    original = copy.deepcopy(source)
    result = apply_study_labels(source, classification)
    assert source == original
    for role in ("home", "away"):
        assert (result[role + "_region"], result[role + "_unit"]) == (region, unit)
        assert (result["base_" + role + "_region"], result["base_" + role + "_unit"]) == (hr, hu)
        assert result[role + "_rule_id"] == original[role + "_rule_id"]
        assert result[role + "_study_rule_id"].startswith("STUDY-")


@pytest.mark.parametrize("value", ["1980-01-01", "2024-12-31"])
def test_turkey_fixed_rule_covers_complete_analysis_scope(classification, value):
    assert study_labels("team:turkey", value, "142", "145", "base", classification)[:2] == ("150", "039")


def test_exception_does_not_reassign_all_uefa_members(classification):
    result = apply_study_labels(fact("team:israel", "team:cyprus", "142", "145", "142", "145"), classification)
    assert result["home_region"] == result["away_region"] == "142"
    assert result["home_unit"] == result["away_unit"] == "145"


def test_requested_base_must_match_before_override(classification):
    with pytest.raises(RegionError, match="Unexpected original classification"):
        study_labels("team:iran", "2000-01-01", "142", "145", "wrong", classification)


@pytest.mark.parametrize("source,expected", [
    (fact("team:turkey", "team:iran", "142", "145", "142", "034"), "cross_region"),
    (fact("team:iran", "team:saudi-arabia", "142", "034", "142", "145"), "same_unit"),
    (fact("team:australia", "team:new-zealand", "009", "053", "009", "053"), "cross_region"),
    (fact("team:kenya", "team:south-africa", "002", "014", "002", "018"), "same_unit"),
])
def test_relations_rebuilt_after_reclassification(classification, source, expected):
    result = apply_study_labels(source, classification)
    assert result["relation"] == expected
    assert result["base_relation"] == source["relation"]


def test_unknown_historical_geography_is_not_imputed(classification):
    result = apply_study_labels(fact("team:russia", "team:france", "", "", "150", "155"), classification)
    assert result["home_region"] == result["home_unit"] == ""
    assert not result["A_usable"] and not result["B_usable"] and not result["C_usable"]
    assert result["relation"] == "unknown"


def test_outside_macro_filter_does_not_require_away_partition():
    row = fact("h", "a", "150", "039", "142", "")
    row["C_usable"] = True
    spec = dict(eligibility="C", home_regions=["150"], home_units=["039"], away_regions=["142"], away_units=[], relations=[])
    assert matches_group(row, spec)
    spec["away_units"] = ["145"]
    assert not matches_group(row, spec)


def test_zero_conditional_cell_retained_and_reverse_direction_separate():
    rows = []
    for i in range(3):
        row = fact("n", "s", "150", "154", "150", "039")
        row.update(match_id=str(i), era="e", tournament_group="friendly", home_win=int(i == 0), outcome="home" if i == 0 else "draw")
        rows.append(row)
    group = lambda h, a: dict(label=h+"->"+a, eligibility=None, home_regions=["150"], home_units=[h], away_regions=["150"], away_units=[a], relations=[])
    c = dict(groups=dict(REF=dict(label="all", eligibility=None, home_regions=[], home_units=[], away_regions=[], away_units=[], relations=[]),
                         NS=group("154", "039"), SN=group("039", "154")),
             analysis_targets=dict(M=dict(groups=["NS", "SN"], reference_group="REF", type="matchup_partition")),
             strata=dict(eras=[dict(id="e")], tournament_groups=["friendly"]), comparisons=[])
    membership, groups, refs = build_groups(rows, c)
    tables = dict(analysis_membership=membership, **build_counts(groups, c, {"n":"n", "s":"s"}))
    build_adjustments(tables, groups, refs, c)
    summaries = {r["group_id"]: r for r in tables["group_summary"]}
    assert summaries["NS"]["n_matches"] == 3 and summaries["NS"]["home_win_rate"] == 1/3
    assert summaries["SN"]["n_matches"] == 0 and summaries["SN"]["home_win_rate"] is None
    assert summaries["SN"]["standardized_home_win_rate"] is None


def test_generated_catalogue_has_all_cells_without_automatic_pairwise_explosion():
    c = build(ROOT)
    assert len(c["analysis_targets"]) == 15 and len(c["comparisons"]) == 29
    assert [len(c["analysis_targets"][t]["groups"]) for t in ["C_EUR","C_ASIA","C_AFR","C_AMER"]] == [4,5,3,4]
    assert len(c["analysis_targets"]["M_MACRO"]["groups"]) == 25
    assert sum(len(t["groups"]) for k,t in c["analysis_targets"].items() if k.startswith("M_") and k!='M_MACRO') == 130
    assert not any(k == "M_OCE" or k == "C_OCE" for k in c["analysis_targets"])
    assert sum(x["target_id"].startswith('C_') and x['target_id']!='C_AMER_FOCUS' for x in c['comparisons']) == 25
    assert len({x["id"] for x in c["comparisons"]}) == 29


def test_old_and_new_fact_schemas_are_explicit():
    assert "base_home_region" not in fields_for(dict(protocol_id="regions-study-v3"))["analysis_matches"]
    assert "base_home_region" in fields_for(dict(protocol_id="regions-study-v4"))["analysis_matches"]
    assert "matchup_rates" not in fields_for(dict(protocol_id="regions-study-v3"))
    assert "study_team_registry" in fields_for(dict(protocol_id="regions-study-v4"))


def test_archive_resolution_checks_expected_bytes(tmp_path):
    original = tmp_path/'source.py';original.write_bytes(b'new')
    archive = tmp_path/'archived.py';archive.write_bytes(b'old')
    expected = sha(archive)
    index = tmp_path/'outputs/logs/regions/archive-v3-20261027/index.json';index.parent.mkdir(parents=True)
    index.write_text(json.dumps(dict(bindings={'source.py':{expected:'archived.py'}})),encoding='utf-8')
    assert registered_path(tmp_path,'source.py',expected,True) == archive
    with pytest.raises(RegionError): registered_path(tmp_path,'source.py',expected,False)
    archive.write_bytes(b'changed')
    with pytest.raises(RegionError): registered_path(tmp_path,'source.py',expected,True)


def test_archive_cannot_hide_changed_published_output(tmp_path):
    output=tmp_path/'output.txt';output.write_bytes(b'changed')
    archive=tmp_path/'old.txt';archive.write_bytes(b'original')
    expected=sha(archive)
    index=tmp_path/'outputs/logs/regions/archive-v3-20261027/index.json';index.parent.mkdir(parents=True)
    index.write_text(json.dumps(dict(bindings={'output.txt':{expected:'old.txt'}})),encoding='utf-8')
    manifest=dict(status='success',analysis_id='regions-6f5915b013976712736b',inputs={},code={},run_artifacts={},outputs={'output.txt':expected})
    (tmp_path/'run.json').write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(RegionError):verify_run(tmp_path,'run.json')
