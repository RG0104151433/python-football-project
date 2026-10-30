"""Build a separate rating eligibility ledger, preserving the accepted study."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from ..data_contract import file_hash, fingerprint
from .io import ROOT, config, publish, read_rows


def membership(day, label, code, registry, events):
    if not code or code not in registry:
        return False, "unmapped_or_historical_association"
    event = events.get(label)
    if event:
        return (True, "conditional_after_exact_admission") if day >= event else (False, "before_exact_admission")
    years = [int(y) for y in re.findall(r"\d{4}", registry[code]["affiliation_years"])]
    if not years:
        return False, "missing_affiliation_year"
    last = max(years)
    if int(day[:4]) == last:
        return False, "admission_year_day_unknown"
    if int(day[:4]) < last:
        return False, "before_latest_affiliation_or_unresolved_earlier_episode"
    return True, "conditional_after_latest_affiliation"


def make_windows(cfg, former):
    windows = defaultdict(list)
    for row in former:
        windows[row["current"]].append((row["start_date"], row["end_date"], "dataset_former_name_interval:" + row["former"]))
    for row in cfg["identity_policy"]["additional_review_windows"]:
        windows[row["label"]].append((row["start"], row["end"], row["basis"]))
    return windows


def episode(label, team_id, day, windows):
    """Conservative operational episodes, not asserted official succession dates."""
    bounds = set()
    for start, end, _ in windows.get(label, []):
        bounds.add(start)
        bounds.add((date.fromisoformat(end) + timedelta(days=1)).isoformat())
    prior = [b for b in bounds if b <= day]
    return team_id + "@" + (max(prior) if prior else "base")


def graph_summary(rows, end):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    count = 0
    for row in rows:
        if row["date"] > end or not row["included"]:
            continue
        a, b = find(row["home_entity_id"]), find(row["away_entity_id"])
        parent[a] = b
        count += 1
    groups = Counter(find(x) for x in list(parent))
    return {"cutoff": end, "matches": count, "entities": len(parent),
            "component_sizes": sorted(groups.values(), reverse=True),
            "limit": "cumulative connectivity only; not evidence of strong/recent cross-region bridges"}


def build_ledger(cfg):
    clean_path = ROOT / cfg["clean_path"]
    if file_hash(clean_path) != cfg["clean_sha256"]:
        raise ValueError("Clean input hash mismatch; no fallback to raw CSV")
    base = ROOT / cfg["identity_dir"]
    sources = [clean_path, ROOT / cfg["former_names_path"], ROOT / cfg["admission_events_path"],
               *[base / n for n in ("match_identity.csv", "association_registry.csv", "label_crosswalk.csv",
                                    "population_policy.json", "identity_manifest.json")]]
    inputs = {p.relative_to(ROOT).as_posix(): file_hash(p) for p in sources}
    clean = read_rows(clean_path)
    mappings = read_rows(base / "match_identity.csv")
    if len({r["match_id"] for r in mappings}) != len(mappings):
        raise ValueError("Duplicate match identity ID")
    identity = {r["match_id"]: r for r in mappings}
    registry = {r["fifa_code"]: r for r in read_rows(base / "association_registry.csv")}
    crosswalk = {r["source_team_id"]: r for r in read_rows(base / "label_crosswalk.csv")}
    events = {r["source_team_label"]: r["start"] for r in
              json.loads((ROOT / cfg["admission_events_path"]).read_text(encoding="utf-8-sig"))["events"]}
    windows = make_windows(cfg, read_rows(ROOT / cfg["former_names_path"]))
    results, selected, counts = [], [], Counter()
    ids = set()
    for r in clean:
        mid, day = r["match_id"], r["date"]
        if mid in ids:
            raise ValueError("Duplicate clean ID")
        ids.add(mid)
        prior = identity.get(mid)
        if prior is None or prior["date"] != day:
            raise ValueError("Missing or mismatched historical mapping: " + mid)
        accepted = prior["in_previous_study"] == "true" and prior["eligible_under_provisional_policy"] == "true"
        reasons = []
        qualifies = True
        for role in ("home", "away"):
            label = r[role + "_team"]
            if prior[role + "_source_team_id"] != r[role + "_team_id"]:
                raise ValueError("Identity join mismatch")
            code = crosswalk.get(r[role + "_team_id"], {}).get("fifa_code", "")
            ok, why = membership(day, label, code, registry, events)
            unresolved = [basis for start, end, basis in windows.get(label, []) if start <= day <= end]
            qualifies &= ok and not unresolved
            reasons.append(role + ":" + why + (";" + "|".join(unresolved) if unresolved else ""))
        if not cfg["learning_start"] <= day <= cfg["learning_end"]:
            status, included = "outside_learning_range", False
        elif accepted:
            status, included = "included_current_study", True
        elif prior["in_previous_study"] == "true":
            # An existing explicit exclusion is not a new unresolved extension.
            status, included = "excluded_current_study", False
        elif qualifies and r["is_neutral"] in {"true", "false"} and r["tournament_group"] != "unknown":
            status, included = "included_conditional_extension", True
        else:
            status, included = "pending_extension", False
        if r["is_neutral"] not in {"true", "false"} or r["tournament_group"] == "unknown":
            if accepted:
                raise ValueError("Accepted study row has unknown rating inputs")
            included = False
        entry = {
            "match_id": mid, "source_record_id": r["source_record_id"], "date": day,
            "home_team": r["home_team"], "away_team": r["away_team"],
            "home_entity_id": episode(r["home_team"], r["home_team_id"], day, windows),
            "away_entity_id": episode(r["away_team"], r["away_team_id"], day, windows),
            "home_score": int(r["home_score"]), "away_score": int(r["away_score"]),
            "outcome_index": {"home": 0, "draw": 1, "away": 2}[r["outcome"]],
            "is_neutral": r["is_neutral"] == "true", "tournament_group": r["tournament_group"],
            "included": included, "status": status, "accepted_current_study": accepted,
            "reason": " / ".join(reasons),
            "identity_basis": "operational_boundaries_from_naming_archive; no automatic inheritance across boundary",
        }
        results.append(entry)
        counts[status] += 1
        if included:
            selected.append(entry)
    results.sort(key=lambda r: (r["date"], r["match_id"]))
    selected.sort(key=lambda r: (r["date"], r["match_id"]))
    accepted_count = sum(r["accepted_current_study"] for r in results)
    if accepted_count != 24917 or any(not r["included"] for r in results if r["accepted_current_study"]):
        raise ValueError("Existing study population was changed")
    aggregates = Counter((r["date"][:4], r["status"], str(r["is_neutral"]), r["tournament_group"]) for r in results)
    summary = {
        "total_clean_rows": len(results), "status_counts": dict(sorted(counts.items())),
        "included": len(selected), "accepted_study_rows_preserved": accepted_count,
        "pre1980_included": sum(r["date"] < "1980" for r in selected),
        "neutral_included": sum(r["is_neutral"] for r in selected),
        "scope_qualification": "conditional extension with explicit quarantine; not full independent membership/identity verification",
        "graphs": [graph_summary(results, y + "-12-31") for y in ("1969", "1974", "1979")],
        "no_ratings_generated": True,
    }
    identity_info = {"config": cfg, "inputs": inputs, "learning_rows": fingerprint(selected)}
    return results, selected, summary, aggregates, identity_info


def run(cfg):
    ledger, selected, summary, aggregate, identity = build_ledger(cfg)
    rows = [dict(year=y, status=s, is_neutral=n, tournament_group=t, count=c)
            for (y, s, n, t), c in sorted(aggregate.items())]
    folder, manifest = publish("learning", identity, csvs={
        "learning_ledger.csv": ledger, "learning_matches.csv": selected, "coverage.csv": rows},
        jsons={"summary.json": summary},
        texts={"data_dictionary.md": "# 评分学习清单\n\nUTF-8 BOM、LF；每行一场。included决定是否学习；status/reason保留去向。"
               "outcome_index为第一方胜0/平1/第二方胜2，含加时不含点球。is_neutral=true时第一方不代表实际主场。"
               "entity_id的@边界只用于防止无依据继承，不是已考证的官方实体成立日。"
               "保留当前24917场采纳，新增范围仅为条件性资格。无比分修改。\n"})
    return folder, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/strength_pilot.json")
    args = parser.parse_args()
    folder, _ = run(config(args.config))
    print(folder.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
