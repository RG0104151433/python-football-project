"""Read-only checks: report candidates without repairing or deleting facts."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from .data_contract import (ISSUE_FIELDS, SCHEMAS, atomic_bytes, csv_bytes, file_hash,
                            fingerprint, issue, load_config, make_run_dir, normalize,
                            parse_date, parse_neutral, parse_score, paths, print_summary,
                            read_csv, run_cli, source_record, tournament_group, write_json, print_issue_examples)
from .snapshot import verify_snapshot


def load_inputs(root, config):
    manifest = verify_snapshot(root, config)
    tables = {}
    for entry in manifest["files"]:
        path = root / entry["path"]
        if path.name not in SCHEMAS:
            continue
        fields, rows = read_csv(path, SCHEMAS[path.name])
        # Check again after parsing, so a concurrent edit cannot bypass verify.
        if file_hash(path) != entry["sha256"]:
            from .data_contract import PrepError
            raise PrepError("INPUT_CHANGED_DURING_READ", entry["path"])
        tables[path.name] = [source_record(r, path.name, entry["sha256"], n, entry["path"])
                             for n, r in enumerate(rows, 1)]
    return manifest, tables


def analyze_matches(records):
    issues, groups = [], defaultdict(list)
    for record in records:
        raw = record["raw"]
        values = {k: normalize(raw[k]) for k in SCHEMAS["results.csv"]}
        for name, parser, code in [("date", parse_date, "INVALID_DATE"),
                                   ("home_score", parse_score, "INVALID_SCORE"),
                                   ("away_score", parse_score, "INVALID_SCORE")]:
            try:
                values[name] = parser(raw[name])
            except ValueError:
                values[name] = None
                issues.append(issue(code, "ERROR", record, field=name, value=raw[name],
                                    expected="有效日期或非负整数比分", message="关键值无法解析，不填补猜测值。", action="QUARANTINE"))
        try:
            values["neutral"] = parse_neutral(raw["neutral"])
        except ValueError:
            values["neutral"] = None
            issues.append(issue("VENUE_UNKNOWN", "WARNING", record, field="neutral", value=raw["neutral"],
                                expected="TRUE/FALSE", message="场地未知；保留可靠赛果，排除场地分析。", action="EXCLUDE_VENUE"))
        for field in ("home_team", "away_team"):
            if not values[field] or "\ufffd" in values[field] or any(ord(c) < 32 for c in values[field]):
                issues.append(issue("INVALID_TEAM", "ERROR", record, field=field, value=raw[field], action="QUARANTINE", message="球队名为空或存在异常字符。"))
        if values["home_team"] and values["home_team"] == values["away_team"]:
            issues.append(issue("SELF_MATCH", "ERROR", record, message="双方是同一规范名称。", action="QUARANTINE"))
        if tournament_group(values["tournament"]) == "unknown":
            issues.append(issue("TOURNAMENT_UNKNOWN", "WARNING", record, field="tournament", value=raw["tournament"], message="赛事组未知。", action="EXCLUDE_TOURNAMENT"))
        for field in ("city", "country"):
            if not values[field]:
                issues.append(issue("LOCATION_MISSING", "WARNING", record, field=field, message="举办地字段缺失，不自动删除赛果。", action="KEEP_WITH_WARNING"))
        if isinstance(values["home_score"], int) and isinstance(values["away_score"], int):
            if abs(values["home_score"] - values["away_score"]) >= 5:
                issues.append(issue("LARGE_MARGIN", "WARNING", record, message="净胜球至少 5；只是核验线索，不据此删除。", action="KEEP_WITH_WARNING"))
        record["values"] = values
        if values["date"] and values["home_team"] and values["away_team"]:
            pair = sorted([values["home_team"], values["away_team"]])
            groups[(values["date"], *pair)].append(record)

    candidates = []
    for key, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        case_id = "pair:" + fingerprint(list(key))
        related = sorted(r["source_record_id"] for r in members)
        signatures = set()
        orientations = set()
        for r in members:
            v = r["values"]
            score = (v["home_score"], v["away_score"])
            if v["home_team"] != key[1]:
                score = tuple(reversed(score))
            signatures.add(score)
            orientations.add(v["home_team"])
        if len({r["row_content_sha256"] for r in members}) == 1:
            code = "EXACT_DUPLICATE_CANDIDATE"
        elif len(signatures) > 1:
            code = "SCORE_CONFLICT"
        elif len(orientations) > 1:
            code = "REVERSED_PAIR_CANDIDATE"
        else:
            code = "SAME_PAIR_DATE_CANDIDATE"
        fields_differ = [k for k in SCHEMAS["results.csv"] if len({r["raw"][k] for r in members}) > 1]
        for r in members:
            issues.append(issue(code, "ERROR", r, case_id=case_id, related=related,
                                value={k: r["raw"][k] for k in fields_differ},
                                message="同日同双方仅为候选；可能是多场或日期精度问题，先隔离，不保留第一条。", action="QUARANTINE"))
            candidates.append({"case_id": case_id, "code": code, "source_record_id": r["source_record_id"],
                               "source_record_no": r["source_record_no"], "date": r["raw"]["date"],
                               "home_team": r["raw"]["home_team"], "away_team": r["raw"]["away_team"],
                               "home_score": r["raw"]["home_score"], "away_score": r["raw"]["away_score"], "different_fields": fields_differ})

    # A team playing different opponents on the same date is a warning, not proof of duplication.
    team_days = defaultdict(list)
    for r in records:
        v = r["values"]
        if v["date"]:
            for name in set([v["home_team"], v["away_team"]]) - {""}:
                team_days[(v["date"], name)].append(r)
    for (day, name), members in sorted(team_days.items()):
        if len(members) > 1 and len({tuple(sorted([r["values"]["home_team"], r["values"]["away_team"]])) for r in members}) > 1:
            case = "team-day:" + fingerprint([day, name])
            for r in members:
                issues.append(issue("TEAM_MULTIPLE_SAME_DAY", "WARNING", r, case_id=case,
                                    message=f"{name} 同日出现多场；后续按日批量更新评级。", action="KEEP_WITH_WARNING"))
    return issues, candidates


def analyze_auxiliary(matches, shootouts, former_names):
    issues, unmatched = [], []
    by_pair = defaultdict(list)
    for r in matches:
        v = r["values"]
        if v["date"]:
            by_pair[(v["date"], *sorted([v["home_team"], v["away_team"]]))].append(r)
    pending = defaultdict(list)
    attachments = {}
    for s in shootouts:
        raw = s["raw"]
        try:
            day = parse_date(raw["date"])
        except ValueError:
            day = None
        home, away, winner = [normalize(raw[k]) for k in ("home_team", "away_team", "winner")]
        key = (day, *sorted([home, away]))
        found = by_pair.get(key, []) if day else []
        reason = ""
        if not day:
            reason = "INVALID_AUX_DATE"
        elif not home or not away or winner not in {home, away}:
            reason = "INVALID_SHOOTOUT_WINNER"
        elif normalize(raw["first_shooter"]) not in {"", home, away}:
            reason = "INVALID_FIRST_SHOOTER"
        elif len(found) != 1:
            reason = "AUX_UNMATCHED" if not found else "AUX_AMBIGUOUS"
        if reason:
            issues.append(issue(reason, "WARNING", s, message="点球资料不能唯一可靠关联；不更改主比分。", action="LEAVE_AUX_UNRESOLVED"))
            unmatched.append({"source_record_id": s["source_record_id"], "reason": reason, **raw})
            for m in found:
                attachments[m["source_record_id"]] = ("unresolved", "")
        else:
            pending[found[0]["source_record_id"]].append((s, winner, found[0]))
    for source_id, entries in pending.items():
        s, winner, match = entries[0]
        v = match["values"]
        if len(entries) > 1 or v["home_score"] != v["away_score"] or v["home_score"] is None or source_id in attachments:
            attachments[source_id] = ("unresolved", "")
            for s, _, _ in entries:
                issues.append(issue("SHOOTOUT_CONFLICT", "WARNING", s, message="点球关联重复或与主比分矛盾，需核验。", action="LEAVE_AUX_UNRESOLVED"))
                unmatched.append({"source_record_id": s["source_record_id"], "reason": "SHOOTOUT_CONFLICT", **s["raw"]})
        else:
            attachments[source_id] = ("matched", winner)

    former_groups = defaultdict(list)
    for record in former_names:
        raw = record["raw"]
        try:
            start = parse_date(raw["start_date"]) if raw["start_date"].strip() else "0001-01-01"
            end = parse_date(raw["end_date"]) if raw["end_date"].strip() else "9999-12-31"
            if start > end or not normalize(raw["current"]) or not normalize(raw["former"]):
                raise ValueError("invalid interval or name")
        except ValueError:
            issues.append(issue("FORMER_NAME_INVALID", "WARNING", record, message="历史名称或时间区间无效，不自动应用映射。", action="REVIEW_MAPPING"))
            continue
        former_groups[normalize(raw["former"])].append((start, end, normalize(raw["current"]), record))
    for members in former_groups.values():
        for index, (start, end, current, record) in enumerate(members):
            for a, b, other, prior in members[:index]:
                if current != other and max(start, a) <= min(end, b):
                    issues.append(issue("FORMER_NAME_OVERLAP", "WARNING", record, related=[prior["source_record_id"]], message="同一旧名时间区间对应不同球队，不自动继承。", action="REVIEW_MAPPING"))
    return issues, attachments, unmatched


def audit_data(root, config):
    manifest, tables = load_inputs(root, config)
    matches = tables["results.csv"]
    issues, candidates = analyze_matches(matches)
    aux_issues, attachments, unmatched = analyze_auxiliary(matches, tables["shootouts.csv"], tables["former_names.csv"])
    issues += aux_issues
    for entry in manifest["files"]:
        if entry.get("extra_fields"):
            issues.append(issue("EXTRA_COLUMNS", "WARNING", message=f"{entry['path']} 新列：{entry['extra_fields']}；未用于本轮分析。", action="REGISTER_ONLY"))
    counts = {
        "input_matches": len(matches), "teams": len({r["values"][k] for r in matches for k in ("home_team", "away_team")} - {""}),
        "tournaments": len({r["values"]["tournament"] for r in matches}),
        "duplicate_groups": len({r["case_id"] for r in candidates}),
        "issues_by_code": dict(sorted(Counter(i["code"] for i in issues).items())),
        "issues_by_severity": dict(sorted(Counter(i["severity"] for i in issues).items())),
        "years": dict(sorted(Counter(r["values"]["date"][:4] for r in matches if r["values"]["date"]).items())),
        "tournament_counts": dict(sorted(Counter(r["values"]["tournament"] for r in matches).items())),
        "neutral_counts": dict(Counter(str(r["values"]["neutral"]) for r in matches)),
        "aux_unmatched": len(unmatched),
    }
    return {"matches": matches, "issues": issues, "candidates": candidates,
            "attachments": attachments, "unmatched": unmatched, "counts": counts,
            "snapshot": manifest}


def write_audit(data, run_dir):
    rows = [{**i, "run_id": run_dir.name} for i in data["issues"]]
    atomic_bytes(run_dir / "issues.csv", csv_bytes(ISSUE_FIELDS, rows))
    fields = "case_id code source_record_id source_record_no date home_team away_team home_score away_score different_fields".split()
    atomic_bytes(run_dir / "duplicate_candidates.csv", csv_bytes(fields, data["candidates"]))
    fields = ["source_record_id", "reason", *SCHEMAS["shootouts.csv"]]
    atomic_bytes(run_dir / "unmatched_supplement.csv", csv_bytes(fields, data["unmatched"]))
    review = [i for i in data["issues"] if i["severity"] == "ERROR" or i["case_id"]]
    atomic_bytes(run_dir / "review_cases.csv", csv_bytes(ISSUE_FIELDS, [{**i, "run_id": run_dir.name} for i in review]))
    write_json(run_dir / "input_audit.json", data["counts"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    root, config = load_config(args.config)
    data = audit_data(root, config)
    run_dir = make_run_dir(paths(root, config)["logs"], "audit")
    write_audit(data, run_dir)
    errors = any(i["severity"] == "ERROR" for i in data["issues"])
    report = {"status": "review_needed" if errors else "passed", "counts": data["counts"]}
    write_json(run_dir / "run_manifest.json", report)
    print_issue_examples(data["issues"])
    print_summary(report, run_dir)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
