"""Independent checks on generated matches, lineage and saved file hashes."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter

from .data_contract import (CLEAN_FIELDS, LINEAGE_FIELDS, PrepError, file_hash,
                            load_config, parse_date, paths, project_path, read_csv, run_cli)
from .snapshot import verify_snapshot


def validate_rows(rows, lineage, expected_source_ids, cutoff):
    checks = {}
    ids = [r["match_id"] for r in rows]
    checks["unique_match_ids"] = len(ids) == len(set(ids))
    source_ids = [r["source_record_id"] for r in lineage]
    checks["complete_unique_lineage"] = len(source_ids) == len(set(source_ids)) and set(source_ids) == set(expected_source_ids)
    states = Counter(r["final_status"] for r in lineage)
    allowed_states = {"included", "outside_window", "quarantined", "confirmed_duplicate", "excluded_by_policy"}
    checks["lineage_states"] = set(states).issubset(allowed_states)
    checks["lineage_counts"] = sum(states.values()) == len(expected_source_ids) and states["included"] == len(rows)
    included = {r["source_record_id"]: r["match_id"] for r in lineage if r["final_status"] == "included"}
    checks["included_matches_traceable"] = included == {r["source_record_id"]: r["match_id"] for r in rows}
    checks["nonempty_dataset"] = bool(rows)
    valid_values = True
    for r in rows:
        try:
            for field in CLEAN_FIELDS:
                if field not in r:
                    raise ValueError("missing column")
            if r["source_record_id"] != f"results:{r['source_sha256']}:{int(r['source_record_no'])}":
                raise ValueError("invalid source identity")
            if not re.fullmatch(r"[0-9a-f]{64}", r["row_content_sha256"]):
                raise ValueError("invalid content fingerprint")
            if r["match_id"] != "results:" + r["row_content_sha256"]:
                raise ValueError("content ID mismatch")
            day = parse_date(r["date"])
            home, away = int(r["home_score"]), int(r["away_score"])
            if str(home) != str(r["home_score"]) or str(away) != str(r["away_score"]):
                raise ValueError("non-integer serialization")
            if min(home, away) < 0 or day > cutoff or not r["home_team_id"] or r["home_team_id"] == r["away_team_id"]:
                raise ValueError("invalid core values")
            outcome = "home" if home > away else "away" if home < away else "draw"
            if r["outcome"] != outcome or int(r["goal_difference"]) != home - away:
                raise ValueError("outcome mismatch")
            neutral = r["is_neutral"]
            if neutral not in (True, False, "true", "false", "", None):
                raise ValueError("invalid venue boolean")
            def boolean(value):
                if value is True or value == "true":
                    return True
                if value is False or value == "false":
                    return False
                raise ValueError("invalid eligibility")
            venue_ok = boolean(r["eligible_venue_analysis"])
            tournament_ok = boolean(r["eligible_tournament_analysis"])
            if venue_ok != (neutral is not None and neutral != ""):
                raise ValueError("venue eligibility mismatch")
            group = r["tournament_group"]
            if group not in {"friendly", "non_friendly", "unknown"} or tournament_ok != (venue_ok and group != "unknown"):
                raise ValueError("tournament eligibility mismatch")
            if not boolean(r["eligible_elo"]) or r["time_split"] not in {"warmup", "train", "valid", "test"}:
                raise ValueError("invalid eligibility/split")
            if int(r["year"]) != int(day[:4]) or int(r["decade_start"]) != int(day[:4]) // 10 * 10:
                raise ValueError("date features mismatch")
            if r["result_basis"] != "after_extra_time_excluding_shootout":
                raise ValueError("result basis mismatch")
            if r["shootout_status"] == "matched":
                if home != away or r["shootout_winner_id"] not in {r["home_team_id"], r["away_team_id"]}:
                    raise ValueError("invalid attached shootout")
            elif r["shootout_status"] not in {"no_record", "unresolved"} or r["shootout_winner_id"]:
                raise ValueError("invalid shootout status")
        except (ValueError, KeyError, TypeError):
            valid_values = False
            break
    checks["valid_values_and_eligibility"] = valid_values
    checks["stable_sort"] = [(r["date"], r["match_id"]) for r in rows] == sorted((r["date"], r["match_id"]) for r in rows)
    return {"passed": all(checks.values()), "checks": checks, "states": dict(sorted(states.items()))}


def validate_dataset(root, config, data_version):
    # A data version is a directory name, never a path supplied by a caller.
    if not data_version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in data_version):
        raise PrepError("INVALID_DATA_VERSION", data_version)
    folder = paths(root, config)["processed"] / data_version
    manifest = json.loads((folder / "dataset_manifest.json").read_text(encoding="utf-8"))
    snapshot = verify_snapshot(root, config)
    if manifest["input_files"] != snapshot["files"]:
        raise PrepError("DATASET_INPUT_MISMATCH", "数据版本不属于当前已登记快照。")
    if manifest["config"] != config:
        raise PrepError("DATASET_CONFIG_MISMATCH", "当前配置与该数据版本不同；请显式使用对应配置。")
    for name, expected in manifest["output_hashes"].items():
        path = project_path(root, (folder / name).relative_to(root).as_posix())
        if path.parent != folder or file_hash(path) != expected:
            raise PrepError("OUTPUT_HASH_MISMATCH", name)
    _, rows = read_csv(folder / "matches_clean.csv", CLEAN_FIELDS)
    lineage_path = project_path(root, manifest["lineage_path"])
    if file_hash(lineage_path) != manifest["lineage_sha256"]:
        raise PrepError("LINEAGE_HASH_MISMATCH", str(lineage_path))
    _, lineage = read_csv(lineage_path, LINEAGE_FIELDS)
    results = next(f for f in snapshot["files"] if f["path"].endswith("/results.csv"))
    source_ids = {f"results:{results['sha256']}:{n}" for n in range(1, results["rows"] + 1)}
    report = validate_rows(rows, lineage, source_ids, config["data"]["cutoff_date"])
    if not report["passed"]:
        raise PrepError("VALIDATION_FAILED", json.dumps(report, ensure_ascii=False))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--data-version", required=True)
    args = parser.parse_args()
    root, config = load_config(args.config)
    report = validate_dataset(root, config, args.data_version)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
