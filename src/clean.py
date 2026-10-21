"""Prepare a versioned dataset offline; uncertain key records are isolated.

This first version supports deterministic format cleanup and conservative
isolation. Nonempty fact amendments/aliases/additional matches fail explicitly
until their reviewed processing is implemented, rather than being ignored.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from .audit import audit_data, write_audit
from .data_contract import (CLEAN_FIELDS, GROUP_FIELDS, LINEAGE_FIELDS, RULES_VERSION,
                            SCHEMAS, TEAM_FIELDS, PrepError, atomic_bytes, csv_bytes,
                            digest, file_hash, fingerprint, load_config, make_run_dir,
                            normalize, paths, print_summary, read_csv, run_cli,
                            team_slug, tournament_group, write_json)
from .snapshot import verify_snapshot
from .validate import validate_dataset, validate_rows


def check_pending_external(external):
    amendment = external / "amendments.jsonl"
    if amendment.exists() and amendment.read_text(encoding="utf-8-sig").strip():
        raise PrepError("AMENDMENTS_NOT_IMPLEMENTED", "存在非空事实修改，第一版不会跳过或擅自应用；请先实现并审核修正重放。")
    for name in ("team_aliases.csv", "extra_matches.csv", "review_decisions.csv"):
        path = external / name
        if path.exists() and path.read_text(encoding="utf-8-sig").strip():
            _, rows = read_csv(path)
            if rows:
                raise PrepError("EXTERNAL_INPUT_NOT_IMPLEMENTED", f"{name} 已有记录，当前版本不支持应用，停止以避免静默忽略。")


def check_old_value(actual, expected):
    """Guard for the future amendment handler; never mutate an input here."""
    if actual != expected:
        raise PrepError("PATCH_OLD_VALUE_MISMATCH", "修改前的值与预期不符，停止。")


def build_team_registry(matches, external):
    existing = external / "team_registry.csv"
    rows = read_csv(existing, TEAM_FIELDS)[1] if existing.exists() else []
    names, ids = {}, {}
    for row in rows:
        name, team_id = row["canonical_name"], row["team_id"]
        if name in names or team_id in ids or not name or not team_id or not row["registry_version"] or normalize(name) != name:
            raise PrepError("TEAM_REGISTRY_INVALID", f"球队表重复或字段无效：{name}")
        names[name], ids[team_id] = row, name
    input_names = sorted({r["values"][k] for r in matches for k in ("home_team", "away_team")} - {""})
    for name in input_names:
        if name in names:
            continue
        slug = team_slug(name)
        team_id = "team:" + slug
        if not slug or team_id in ids:
            raise PrepError("TEAM_ID_COLLISION", f"名称 {name!r} 无法取得唯一 slug，请审核并先登记稳定 ID。")
        row = dict(zip(TEAM_FIELDS, [team_id, name, "team-registry-v1", name]))
        names[name], ids[team_id] = row, name
    return sorted(names.values(), key=lambda r: r["team_id"]), {name: row["team_id"] for name, row in names.items()}


def build_tournament_groups(matches, external):
    path = external / "tournament_groups.csv"
    existing = read_csv(path, GROUP_FIELDS)[1] if path.exists() else []
    evidence_path = external / "evidence.csv"
    evidence = {}
    if evidence_path.exists():
        for entry in read_csv(evidence_path, ["evidence_id", "url"])[1]:
            if not entry["evidence_id"] or entry["evidence_id"] in evidence:
                raise PrepError("EVIDENCE_INVALID", "证据 ID 为空或重复。")
            evidence[entry["evidence_id"]] = entry
    overrides = {}
    for row in existing:
        name = row["tournament_name"]
        if name in overrides or normalize(name) != name:
            raise PrepError("TOURNAMENT_MAPPING_INVALID", "赛事表名称重复或未规范化。")
        if row["group"] not in {"friendly", "non_friendly", "unknown"}:
            raise PrepError("TOURNAMENT_MAPPING_INVALID", name)
        default = tournament_group(name)
        if row["group"] != default:
            if row["review_status"] != "approved" or not row["rationale"] or not row["evidence_id"]:
                raise PrepError("TOURNAMENT_OVERRIDE_UNAPPROVED", f"{name} 的例外需批准状态、理由和证据 ID。")
            cited = evidence.get(row["evidence_id"], {})
            if not cited.get("url", "").startswith(("https://", "http://")):
                raise PrepError("EVIDENCE_MISSING", f"{name} 引用的证据不在 evidence.csv 或没有具体 URL。")
        overrides[name] = row
    counts = Counter(r["values"]["tournament"] for r in matches)
    rows = []
    for name, count in sorted(counts.items()):
        default = tournament_group(name)
        prior = overrides.get(name, {})
        rows.append({"tournament_name": name, "match_count": count, "default_group": default,
                     "group": prior.get("group", default), "mapping_version": "tournament-groups-v1",
                     "rationale": prior.get("rationale", "数据集标记规则，不表示官方赛事资格"),
                     "review_status": prior.get("review_status", "generated_unreviewed"), "evidence_id": prior.get("evidence_id", "")})
    return rows, {r["tournament_name"]: r["group"] for r in rows}


def time_split(day, config):
    for name, boundary in [("warmup", "warmup_end"), ("train", "train_end"), ("valid", "valid_end"), ("test", "test_end")]:
        if day <= config["time_split"][boundary]:
            return name
    raise PrepError("DATE_OUTSIDE_SPLITS", day)


def build_clean_rows(data, config, team_ids, groups):
    issue_index = defaultdict(list)
    for item in data["issues"]:
        issue_index[item["source_record_id"]].append(item)
    clean, lineage, quarantine = [], [], []
    for record in data["matches"]:
        v, raw = record["values"], record["raw"]
        found = issue_index[record["source_record_id"]]
        errors = [i for i in found if i["severity"] == "ERROR"]
        if v["date"] and v["date"] > config["data"]["cutoff_date"]:
            state, reason = "outside_window", "超过预先固定的分析截止日，原始文件仍保留。"
        elif errors:
            state, reason = "quarantined", "按 isolate-v1 政策隔离未决关键记录；不代表事实已裁定。"
        else:
            state, reason = "included", "关键字段有效；可选信息按资格字段限制用途。"
        tracking = {k: record[k] for k in ("source_record_id", "source_file", "source_sha256", "source_record_no", "match_id")}
        tracking.update(final_status=state, case_ids=sorted({i["case_id"] for i in found if i["case_id"]}),
                        issue_codes=sorted({i["code"] for i in found}), reason=reason)
        lineage.append(tracking)
        if state == "quarantined":
            quarantine.append({**tracking, **raw})
        if state != "included":
            continue
        venue_ok = v["neutral"] is not None
        group = groups[v["tournament"]]
        status, winner = data["attachments"].get(record["source_record_id"], ("no_record", ""))
        row = {k: record[k] for k in ("match_id", "source_record_id", "row_content_sha256", "source_file", "source_sha256", "source_record_no")}
        home, away = v["home_score"], v["away_score"]
        row.update(date=v["date"], date_precision="day", home_team_raw=raw["home_team"], away_team_raw=raw["away_team"],
                   home_team_id=team_ids[v["home_team"]], away_team_id=team_ids[v["away_team"]],
                   home_team=v["home_team"], away_team=v["away_team"], home_score=home, away_score=away,
                   outcome="home" if home > away else "away" if home < away else "draw", goal_difference=home-away,
                   result_basis="after_extra_time_excluding_shootout", shootout_status=status,
                   shootout_winner_id=team_ids[winner] if winner else "", tournament_raw=raw["tournament"],
                   tournament=v["tournament"], tournament_group=group, city=v["city"], country=v["country"],
                   neutral_raw=raw["neutral"], is_neutral=v["neutral"], venue_basis="dataset" if venue_ok else "unresolved",
                   year=int(v["date"][:4]), decade_start=int(v["date"][:4])//10*10,
                   time_split=time_split(v["date"], config), eligible_elo=True, eligible_venue_analysis=venue_ok,
                   eligible_tournament_analysis=venue_ok and group != "unknown",
                   review_status="clear" if venue_ok and group != "unknown" and status != "unresolved" else "limited_use")
        clean.append(row)
    clean.sort(key=lambda r: (r["date"], r["match_id"]))
    return clean, lineage, quarantine


def code_identity():
    folder = Path(__file__).parent
    return {p.name: digest(p.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8"))
            for p in sorted(folder.glob("*.py"))}


def git_identity(root):
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout)
        return {"commit": head, "working_tree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "working_tree_dirty": None}


def data_dictionary():
    descriptions = {
        "match_id": "比赛内容版本 ID，未改原始记录跨快照不变；不是现实比赛永久身份。",
        "source_record_id": "文件指纹与数据记录序号，定位该快照内一条输入。",
        "source_record_no": "整数，数据记录序号从 1 起，不含表头。",
        "is_neutral": "可空布尔，true/false/空；空值不得参加场地分析。",
        "tournament_group": "friendly / non_friendly / unknown；不代表官方比赛资格。",
        "shootout_status": "matched / no_record / unresolved；no_record 不证明从未有点球。",
        "review_status": "clear 表示通过自动规则，不表示逐场人工核验；limited_use 表示用途受限。",
        "time_split": "warmup / train / valid / test，来自配置时间边界。",
        "outcome": "home / draw / away，含加时不含点球。",
        "goal_difference": "整数，第一方比分减第二方比分，不可用于本场赛前预测。",
        "result_basis": "固定 after_extra_time_excluding_shootout，不能称为 90 分钟赛果。",
    }
    integer = {"source_record_no", "home_score", "away_score", "goal_difference", "year", "decade_start"}
    booleans = {"is_neutral", "eligible_elo", "eligible_venue_analysis", "eligible_tournament_analysis"}
    optional = {"city", "country", "tournament_raw", "tournament", "neutral_raw", "is_neutral", "shootout_winner_id"}
    lines = ["# 清洗数据字典", "", "UTF-8 BOM、LF 行尾；每行一场比赛；空字符串表示缺失。原始文件不覆盖。", "",
             "场地与赛事类别仍需团队核验；自动检查通过不等于全部历史事实正确。", ""]
    for field in CLEAN_FIELDS:
        kind = "整数" if field in integer else "布尔" if field in booleans else "文本"
        required = "允许空值" if field in optional else "不允许空值"
        detail = descriptions.get(field, "")
        if field.endswith("_raw"):
            detail = "原始文本值，未按规范名覆盖；可通过来源记录复查。"
        elif field.startswith("eligible_"):
            detail = "true/false；只有 true 才能进入相应用途，场地分析另筛选非中立场。"
        lines.append(f"- `{field}`：{kind}；{required}。{detail}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def export_review_pack(run_dir, data, groups):
    """Prefilled local values, never fabricated external verification results."""
    folder = run_dir / "team_handoff"
    fields = "tournament_name match_count default_group proposed_group reason source_url review_status".split()
    rows = [{"tournament_name": r["tournament_name"], "match_count": r["match_count"],
             "default_group": r["default_group"], "proposed_group": r["group"],
             "reason": "", "source_url": "", "review_status": "not_reviewed"} for r in groups]
    atomic_bytes(folder / "A" / "tournament_review.csv", csv_bytes(fields, rows))
    fields = "case_id code source_record_id source_record_no date home_team away_team home_score away_score different_fields".split()
    atomic_bytes(folder / "A" / "historical_candidates.csv", csv_bytes(fields, data["candidates"]))
    wanted = {("2014-07-08", "Brazil", "Germany"), ("2022-12-18", "Argentina", "France"),
              ("2018-07-07", "Russia", "Croatia"), ("2010-07-11", "Netherlands", "Spain"),
              ("2014-07-13", "Germany", "Argentina"), ("2018-07-15", "France", "Croatia"),
              ("2024-03-23", "England", "Brazil"), ("2024-06-03", "Germany", "Ukraine")}
    fields = """source_record_id source_record_no date home_team away_team home_score away_score
country neutral tournament source_url source_title accessed_on source_score_90 source_score_aet
source_shootout source_venue agreement uncertainty explanation executor review_status""".split()
    rows = []
    for record in data["matches"]:
        raw = record["raw"]
        if (raw["date"], raw["home_team"], raw["away_team"]) not in wanted:
            continue
        row = {k: raw[k] for k in SCHEMAS["results.csv"] if k in fields}
        row.update(source_record_id=record["source_record_id"], source_record_no=record["source_record_no"], review_status="not_reviewed")
        rows.append(row)
    atomic_bytes(folder / "B" / "match_checks.csv", csv_bytes(fields, rows))


def run_cleaning(root, config):
    location = paths(root, config)
    check_pending_external(location["external"])
    data = audit_data(root, config)
    run_dir = make_run_dir(location["logs"], "clean")
    write_audit(data, run_dir)
    registry, team_ids = build_team_registry(data["matches"], location["external"])
    groups, group_map = build_tournament_groups(data["matches"], location["external"])
    rows, lineage, quarantine = build_clean_rows(data, config, team_ids, group_map)
    sources = {r["source_record_id"] for r in data["matches"]}
    validation = validate_rows(rows, lineage, sources, config["data"]["cutoff_date"])
    atomic_bytes(run_dir / "row_lineage.csv", csv_bytes(LINEAGE_FIELDS, lineage))
    atomic_bytes(run_dir / "quarantine.csv", csv_bytes([*LINEAGE_FIELDS, *SCHEMAS["results.csv"]], quarantine))
    write_json(run_dir / "validation_report.json", validation)
    if not validation["passed"]:
        raise PrepError("VALIDATION_FAILED", f"生成结果未通过检查，旧版不覆盖：{run_dir}")
    registry_bytes = csv_bytes(TEAM_FIELDS, registry)
    group_bytes = csv_bytes(GROUP_FIELDS, groups)
    identity = {"input_files": data["snapshot"]["files"], "config": config, "code": code_identity(),
                "rules_version": RULES_VERSION, "registry_hash": digest(registry_bytes), "groups_hash": digest(group_bytes),
                "isolation_policy": "isolate-v1", "amendments_applied": 0}
    evidence_path = location["external"] / "evidence.csv"
    identity["evidence_hash"] = file_hash(evidence_path) if evidence_path.exists() else None
    version = "prep-" + fingerprint(identity)[:20]
    content = {"matches_clean.csv": csv_bytes(CLEAN_FIELDS, rows), "data_dictionary.md": data_dictionary()}
    hashes = {name: digest(value) for name, value in content.items()}
    summary = {"input": len(data["matches"]), "included": len(rows), "states": validation["states"],
               "time_splits": dict(sorted(Counter(r["time_split"] for r in rows).items())),
               "eligible_venue_analysis": sum(r["eligible_venue_analysis"] for r in rows),
               "eligible_tournament_analysis": sum(r["eligible_tournament_analysis"] for r in rows),
               "shootout_status": dict(Counter(r["shootout_status"] for r in rows)),
               "issues_by_code": data["counts"]["issues_by_code"], "amendments_applied": 0}
    report = {"status": "validated_with_exclusions" if quarantine else "validated", "data_version": version,
              "human_review_pending": True, "counts": summary, "git": git_identity(root)}
    write_json(run_dir / "clean_log.json", report)
    text = ["# 数据清洗运行记录", "", f"数据版本：{version}", "", f"输入 {len(data['matches'])}，纳入 {len(rows)}。", "",
            f"互斥去向：{json.dumps(validation['states'], ensure_ascii=False)}", "",
            "政策：关键字段错误及同日同双方候选全部隔离，不自动删重、不修改比分。场地/赛事未知以资格字段限制用途。", "",
            "本次应用 0 条事实修正；球队表和赛事表由规则生成，尚待团队核验。点球无记录不等于确认没有点球。", "",
            "隔离改变了可用历史，后续 Elo 必须基于本版本从头计算；报告需要说明此限制。", ""]
    atomic_bytes(run_dir / "clean_log.md", "\n".join(text).encode("utf-8"))
    verify_snapshot(root, config)
    target = location["processed"] / version
    manifest = {**report, "identity": identity, "input_files": data["snapshot"]["files"], "config": config,
                "output_hashes": hashes, "lineage_path": (run_dir / "row_lineage.csv").relative_to(root).as_posix(),
                "lineage_sha256": file_hash(run_dir / "row_lineage.csv"), "frozen": False}
    if target.exists():
        prior = json.loads((target / "dataset_manifest.json").read_text(encoding="utf-8"))
        if prior["identity"] != identity or prior["output_hashes"] != hashes:
            raise PrepError("DATA_VERSION_COLLISION", "同一版本 ID 对应不同产物，停止而不覆盖。")
        validate_dataset(root, config, version)
        report["reused_identical_dataset"] = True
    else:
        location["processed"].mkdir(parents=True, exist_ok=True)
        # Stage beside the final directory; a failed generation cannot replace a prior dataset.
        with tempfile.TemporaryDirectory(dir=location["processed"], prefix=".prep-") as temporary:
            staging = Path(temporary)
            if staging.parent.resolve() != location["processed"].resolve():
                raise PrepError("STAGING_PATH_INVALID", str(staging))
            for name, value in content.items():
                atomic_bytes(staging / name, value)
            write_json(staging / "dataset_manifest.json", manifest)
            staging.rename(target)
    # These are generated proposals; existing approved classifications/IDs were read above.
    atomic_bytes(location["external"] / "team_registry.csv", registry_bytes)
    atomic_bytes(location["external"] / "tournament_groups.csv", group_bytes)
    export_review_pack(run_dir, data, groups)
    write_json(run_dir / "run_manifest.json", {**report, "dataset_path": target.relative_to(root).as_posix(),
                                             "output_hashes": hashes, "identity": identity})
    print_summary(report, run_dir)
    return target, run_dir, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    root, config = load_config(args.config)
    run_cleaning(root, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
