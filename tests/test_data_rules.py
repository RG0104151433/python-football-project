"""Small counterexamples for rules that could silently change research data."""
import csv
import io

import pytest

from src.audit import analyze_auxiliary, analyze_matches
from src.clean import build_team_registry, check_old_value
from src.data_contract import (SCHEMAS, PrepError, csv_bytes, fingerprint, parse_date,
                               parse_neutral, parse_score, source_record, tournament_group)


def match(**changes):
    row = dict(zip(SCHEMAS["results.csv"], ["2018-01-01", "Alpha", "Beta", "1", "0", "Friendly", "City", "Alpha", "FALSE"]))
    row.update(changes)
    return row


def record(row, number=1, sha="snapshot-a", name="results.csv"):
    return source_record(row, name, sha, number, "data/raw/international_results/" + name)


@pytest.mark.parametrize("value,expected", [("FALSE", False), (" false ", False), ("TRUE", True)])
def test_neutral_is_not_python_truthiness(value, expected):
    assert parse_neutral(value) is expected


@pytest.mark.parametrize("value", ["", "unknown", "0", "yes"])
def test_unknown_venue_is_not_assumed_home(value):
    with pytest.raises(ValueError):
        parse_neutral(value)


@pytest.mark.parametrize("value", ["", "-1", "1.5", "nan", "1e2"])
def test_invalid_scores_are_not_filled_with_zero(value):
    with pytest.raises(ValueError):
        parse_score(value)


def test_date_requires_a_known_day():
    for value in ["1974-02", "1974-02-30", "1974-2-01"]:
        with pytest.raises(ValueError):
            parse_date(value)


def test_content_id_survives_append_and_reorder_but_source_location_changes():
    first = record(match(), 1, "file-before")
    second = record(match(), 99, "file-after")
    assert first["match_id"] == second["match_id"]
    assert first["source_record_id"] != second["source_record_id"]
    assert record(match(home_score="2"))["match_id"] != first["match_id"]


def test_identical_rows_still_have_two_input_identities():
    rows = [record(match(), 1), record(match(), 2)]
    issues, candidates = analyze_matches(rows)
    assert len(candidates) == 2
    assert len({r["source_record_id"] for r in candidates}) == 2
    assert {i["code"] for i in issues} == {"EXACT_DUPLICATE_CANDIDATE"}


def test_same_day_opposite_scores_are_not_silently_deduplicated():
    rows = [record(match(), 1), record(match(home_score="0", away_score="1"), 2)]
    issues, candidates = analyze_matches(rows)
    assert len(candidates) == 2
    assert all(i["action"] == "QUARANTINE" for i in issues)
    assert {i["code"] for i in issues} == {"SCORE_CONFLICT"}


def test_same_day_different_opponents_is_only_a_warning():
    rows = [record(match(), 1), record(match(away_team="Gamma"), 2)]
    issues, candidates = analyze_matches(rows)
    assert not candidates
    assert all(i["severity"] == "WARNING" for i in issues)


def test_reverse_shootout_join_and_missing_first_shooter():
    matches = [record(match(home_score="2", away_score="2"))]
    analyze_matches(matches)
    raw = dict(zip(SCHEMAS["shootouts.csv"], ["2018-01-01", "Beta", "Alpha", "Beta", ""]))
    shootouts = [record(raw, name="shootouts.csv")]
    issues, attachments, unmatched = analyze_auxiliary(matches, shootouts, [])
    assert not issues and not unmatched
    assert attachments[matches[0]["source_record_id"]] == ("matched", "Beta")
    assert matches[0]["values"]["home_score"] == matches[0]["values"]["away_score"] == 2


def test_ambiguous_auxiliary_join_does_not_expand_matches():
    matches = [record(match(home_score="1", away_score="1"), 1), record(match(home_score="2", away_score="2"), 2)]
    analyze_matches(matches)
    raw = dict(zip(SCHEMAS["shootouts.csv"], ["2018-01-01", "Alpha", "Beta", "Alpha", ""]))
    issues, attachments, unmatched = analyze_auxiliary(matches, [record(raw, name="shootouts.csv")], [])
    assert len(matches) == 2 and len(unmatched) == 1
    assert all(value == ("unresolved", "") for value in attachments.values())
    assert issues[0]["code"] == "AUX_AMBIGUOUS"


def test_team_slug_collision_requires_a_decision(tmp_path):
    rows = [record(match(home_team="A.B", away_team="A B"))]
    analyze_matches(rows)
    with pytest.raises(PrepError, match="唯一 slug"):
        build_team_registry(rows, tmp_path)


def test_csv_format_has_bom_lf_and_roundtrips_commas():
    data = csv_bytes(["name", "score", "neutral", "rating"], [{"name": 'A,"B"', "score": 1, "neutral": False, "rating": 1500.125}])
    assert data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data
    row = next(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    assert row == {"name": 'A,"B"', "score": "1", "neutral": "false", "rating": "1500.1250000000"}


def test_tournament_names_do_not_claim_official_status():
    assert tournament_group("Friendly") == "friendly"
    assert tournament_group("Regional Invitational") == "non_friendly"
    assert tournament_group("") == "unknown"


def test_old_value_must_match_before_any_future_patch():
    check_old_value("1", "1")
    with pytest.raises(PrepError) as exc:
        check_old_value("1", "2")
    assert exc.value.code == "PATCH_OLD_VALUE_MISMATCH"
