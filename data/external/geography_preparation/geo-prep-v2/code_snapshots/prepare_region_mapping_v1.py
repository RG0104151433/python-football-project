#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第三问（地域差异）数据准备工具：只做资料整理、关联、计数与校验。

不计算地区胜率/调整值/区间/排名，不冻结正式统计协议。
用法（仓库根目录）：
    python scripts/prepare_region_mapping.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html as htmllib
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "data", "external", "geography_preparation", "geo-prep-v1")
DEFAULT_Q2 = os.path.join(ROOT, "outputs", "tables", "tournaments",
                          "tournaments-4893e38db46f83f6c219", "analysis_membership.csv")
DEFAULT_CLEAN = os.path.join(ROOT, "data", "processed", "prep-3fab808178cf8ad71d88", "matches_clean.csv")
DEFAULT_REGISTRY = os.path.join(ROOT, "data", "processed", "team_identity",
                                "identity-reviewed-29d880765c1623764940", "association_registry.csv")
M49_OVERVIEW = os.path.join(PKG, "sources", "m49_overview.html")
M49_PAGE = os.path.join(PKG, "sources", "m49_page.html")
SEED = os.path.join(PKG, "team_geography_seed.csv")

WINDOW_START, WINDOW_END = "1980-01-01", "2024-12-31"
EXPECTED = {"q2_rows": 48102, "included": 24917, "home_labels": 214, "away_labels": 214, "union_labels": 215}

REGION_ZH = {"001": "世界", "002": "非洲", "019": "美洲", "142": "亚洲", "150": "欧洲", "009": "大洋洲",
             "202": "撒哈拉以南非洲", "419": "拉丁美洲和加勒比", "053": "澳大利亚和新西兰",
             "015": "北非", "011": "西非", "014": "东非", "017": "中非", "018": "南部非洲",
             "021": "北美", "013": "中美洲", "029": "加勒比", "005": "南美",
             "030": "东亚", "034": "南亚", "035": "东南亚", "143": "中亚", "145": "西亚",
             "039": "南欧", "151": "东欧", "154": "北欧", "155": "西欧",
             "054": "美拉尼西亚", "057": "密克罗尼西亚", "061": "波利尼西亚"}

ROLLUPS = {
    "sub_saharan_africa": {"name_zh": "撒哈拉以南非洲", "region": "002", "members": ["011", "014", "017", "018"],
                           "rule": "M49 202(SSA) 之下的四个细区合并；不含 015 北非"},
    "north_africa": {"name_zh": "北非", "region": "002", "members": ["015"], "rule": "M49 细区 015 单独成组"},
    "latin_america": {"name_zh": "拉丁美洲", "region": "019", "members": ["005", "013", "029"],
                      "rule": "M49 419(LAC) 去掉 021 北美后的三细区合并（仅供候选对照）"},
}


# ---------------------------------------------------------------- helpers
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, rows: list[dict], fields: list[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).strip()


# ---------------------------------------------------------------- M49 parse
def parse_m49(path: str) -> dict:
    """解析官方 M49 overview 页面英文表格：返回 code -> area dict。"""
    t = open(path, encoding="utf-8", errors="ignore").read()
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S)
    areas = {}
    nodes = {}
    for r in rows:
        cells = [re.sub(r"\s+", " ", re.sub("<[^>]+>", "", htmllib.unescape(c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if not cells:
            continue
        idx = [i for i, c in enumerate(cells) if re.fullmatch(r"[A-Z]{2}", c)]
        if not idx:
            continue
        j = idx[0]
        if j < 6 or "World" not in cells[:j]:
            continue
        code, name, iso2, iso3 = cells[j - 1], cells[j - 2], cells[j], cells[j + 1]
        parents = cells[: j - 2]
        pairs = [(parents[k], parents[k + 1]) for k in range(0, len(parents) - 1, 2)]
        for c, n in pairs:
            nodes[c] = n
        region = pairs[1] if len(pairs) > 1 else ("", "")
        sub = pairs[2] if len(pairs) > 2 else ("", "")
        inter = pairs[3] if len(pairs) > 3 else ("", "")
        areas[code] = {"code": code, "name": name, "iso2": iso2, "iso3": iso3,
                       "region_code": region[0], "region_name": region[1],
                       "subregion_code": sub[0], "subregion_name": sub[1],
                       "inter_code": inter[0], "inter_name": inter[1],
                       "unit_code": inter[0] or sub[0], "unit_name": inter[1] or sub[1]}
    return {"areas": areas, "nodes": nodes}


def build_dictionary(m49: dict) -> list[dict]:
    """原始层级与项目候选层级分开保存；项目细区=最深的非空 M49 层。"""
    rows = []
    base = {"standard_version": "M49 accessed 2026-10-26 (UNSD)", "source_id": "SRC-M49-UNSD-2026"}
    for code, name in m49["nodes"].items():
        if not code:
            continue
        if code == "001":
            level, parent = "world", ""
            p_region = p_unit = ""
        elif code in ("002", "019", "142", "150", "009"):
            level, parent = "region", "001"
            p_region = code
            p_unit = ""
        elif code in ("202", "419", "053", "015", "021") or code in ("030", "034", "035", "143", "145",
                                                                   "039", "151", "154", "155", "054", "057", "061"):
            level, parent = "subregion", ""
            p_region = ""
            p_unit = ""
        else:
            level, parent = "intermediate", ""
            p_region = p_unit = ""
        rows.append({**base, "area_code": code, "original_name": name,
                     "zh_name": REGION_ZH.get(code, ""), "parent_code": parent,
                     "original_level": level, "project_region_code": p_region,
                     "project_unit_code": p_unit, "is_project_unit": "",
                     "merge_rule": "", "note": "节点行；项目细区见球队规则"})
    # project units = 22 exclusive units, with parent region resolved from areas
    unit_parent = {}
    for a in m49["areas"].values():
        unit_parent[a["unit_code"]] = a["region_code"]
    for ucode, region in sorted(unit_parent.items()):
        if not ucode:
            continue
        rows.append({**base, "area_code": ucode, "original_name": m49["nodes"].get(ucode, ""),
                     "zh_name": REGION_ZH.get(ucode, ""), "parent_code": region,
                     "original_level": "project_unit", "project_region_code": region,
                     "project_unit_code": ucode, "is_project_unit": "true", "merge_rule": "",
                     "note": "项目候选细区（互斥；由最深非空 M49 层确定）"})
    for rid, spec in ROLLUPS.items():
        rows.append({**base, "area_code": rid, "original_name": rid, "zh_name": spec["name_zh"],
                     "parent_code": spec["region"], "original_level": "project_rollup",
                     "project_region_code": spec["region"], "project_unit_code": "", "is_project_unit": "false",
                     "merge_rule": spec["rule"], "note": "仅供候选粗分组展示，不参与细区互斥计数"})
    return rows


# ---------------------------------------------------------------- rules
def build_rules(seed_rows: list[dict], m49: dict) -> list[dict]:
    rules = []
    rid = 0
    for s in sorted(seed_rows, key=lambda x: x["team_id"]):
        tid, code = s["team_id"], s["m49_code"]
        note = s.get("note", "")
        if tid == "team:russia":
            segments = [
                ("1980-01-01", "1991-12-25", None, None, "multi_region", "project_rule",
                 "苏联时期：跨欧亚，无法唯一归入单一大区（不按首都或继承国猜）"),
                ("1991-12-26", "1992-07-02", None, None, "multi_region", "project_rule",
                 "独联体过渡期：无单一大区"),
                ("1992-07-03", "2024-12-31", "150", "151", "resolved", "project_rule",
                 "俄罗斯：欧洲/东欧；1992-07-03 为俄足协FIFA接纳日（项目规则，见身份阶段记录）"),
            ]
            for st, en, reg, unit, status, dtype, why in segments:
                rid += 1
                rules.append({"rule_id": f"GEO-R{rid:03d}", "team_id": tid, "entity": "Russia / USSR / CIS",
                              "m49_code": code if reg else "", "project_region_code": reg or "",
                              "project_unit_code": unit or "", "date_start": st, "date_end": en,
                              "date_precision": "project_rule", "status": status, "source_id": "SRC-M49-UNSD-2026",
                              "reason": why})
        else:
            rid += 1
            if code in m49["areas"]:
                area = m49["areas"][code]
            elif code == "412":  # Kosovo 统计用码（M49 FAQ），地理层级同塞尔维亚
                area = {"region_code": "150", "unit_code": "039"}
            else:
                raise KeyError(code)
            status = "project_mapping" if note else "source_explicit"
            rules.append({"rule_id": f"GEO-R{rid:03d}", "team_id": tid,
                          "entity": s["dataset_label"] + ("；" + note if note else ""),
                          "m49_code": code, "project_region_code": area["region_code"],
                          "project_unit_code": area["unit_code"], "date_start": WINDOW_START,
                          "date_end": WINDOW_END, "date_precision": "analysis_window", "status": status,
                          "source_id": "SRC-M49-UNSD-2026",
                          "reason": "M49 国家/地区条目" + ("；例外说明：" + note if note else "")})
    return rules


def rule_for(rules_by_team: dict, team_id: str, date: str) -> dict | None:
    for r in rules_by_team.get(team_id, []):
        if r["date_start"] <= date <= r["date_end"]:
            return r
    return None


def relation_of(home_region, home_unit, away_region, away_unit):
    if not home_region or not away_region:
        return "unknown_region"
    if home_region != away_region:
        return "cross_region"
    if home_unit and away_unit:
        return "same_unit" if home_unit == away_unit else "same_region_diff_unit"
    return "unknown_same_region"


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q2", default=DEFAULT_Q2)
    ap.add_argument("--clean", default=DEFAULT_CLEAN)
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_hash = sha256(os.path.abspath(__file__))[:8]
    run_id = f"preparation-{stamp}-{run_hash}"
    run = os.path.join(ROOT, "outputs", "logs", "regions", run_id)
    os.makedirs(run, exist_ok=True)
    checks = []

    def chk(name, ok, detail=""):
        checks.append({"name": name, "passed": bool(ok), "detail": detail})

    # ---------- inputs
    q2 = read_csv(args.q2)
    clean = read_csv(args.clean)
    registry = read_csv(args.registry)
    inputs = {k: {"path": os.path.relpath(v, ROOT), "sha256": sha256(v),
                  "bytes": os.path.getsize(v)}
              for k, v in {"q2_membership": args.q2, "matches_clean": args.clean,
                           "association_registry": args.registry, "m49_overview_html": M49_OVERVIEW,
                           "m49_page_html": M49_PAGE, "team_seed": SEED,
                           "script": os.path.abspath(__file__)}.items()}
    q2_versions = Counter((r["data_version"], r["identity_version"], r["sample_id"]) for r in q2)
    inc = [r for r in q2 if r["included"].strip().lower() == "true"]
    inc_ids = [r["match_id"] for r in inc]
    clean_by_id = {r["match_id"]: r for r in clean}

    chk("q2_rows_expected", len(q2) == EXPECTED["q2_rows"], f"got {len(q2)}")
    chk("included_expected", len(inc) == EXPECTED["included"], f"got {len(inc)}")
    chk("included_values_binary", set(r["included"].strip().lower() for r in q2) <= {"true", "false"})
    chk("single_version_triple", len(q2_versions) == 1, str(list(q2_versions)))

    # linkage
    dup_q2 = len(inc_ids) - len(set(inc_ids))
    dup_clean = len(clean) - len(clean_by_id)
    missing = [m for m in inc_ids if m not in clean_by_id]
    chk("duplicate_match_ids", dup_q2 == 0 and dup_clean == 0, f"q2={dup_q2},clean={dup_clean}")
    chk("all_included_matched", not missing, f"{len(missing)} missing")
    # 1:1 join, verify identity of date/tournament/source
    bad_link = []
    for r in inc:
        m = clean_by_id[r["match_id"]]
        if (m["date"] != r["date"] or m["tournament_group"] != r["tournament_group"]
                or m["source_record_id"] != r["source_record_id"] or m["year"] < "1980"):
            bad_link.append(r["match_id"])
    chk("join_field_consistency", not bad_link, f"{len(bad_link)} mismatched")
    chk("no_row_inflation", len(inc) == EXPECTED["included"] and len(set(inc_ids)) == EXPECTED["included"])
    chk("neutral_scope", all(clean_by_id[r["match_id"]]["is_neutral"] == "false" for r in inc))
    chk("date_window", all(WINDOW_START <= clean_by_id[r["match_id"]]["date"] <= WINDOW_END for r in inc))

    # team inventory
    stats = {}
    for r in inc:
        m = clean_by_id[r["match_id"]]
        for tid, role, raw in ((m["home_team_id"], "home", m["home_team_raw"]),
                               (m["away_team_id"], "away", m["away_team_raw"])):
            s = stats.setdefault(tid, {"labels": Counter(), "raw": set(), "dates": [],
                                       "home": 0, "away": 0})
            s["labels"][m["home_team"] if role == "home" else m["away_team"]] += 1
            s["raw"].add(raw)
            s["dates"].append(m["date"])
            s["home" if role == "home" else "away"] += 1
    chk("home_labels_expected", len({clean_by_id[r["match_id"]]["home_team_id"] for r in inc}) == EXPECTED["home_labels"])
    chk("away_labels_expected", len({clean_by_id[r["match_id"]]["away_team_id"] for r in inc}) == EXPECTED["away_labels"])
    chk("union_labels_expected", len(stats) == EXPECTED["union_labels"], f"got {len(stats)}")

    inventory = []
    for tid, s in sorted(stats.items()):
        inventory.append({"team_id": tid, "current_label": s["labels"].most_common(1)[0][0],
                          "raw_names": "; ".join(sorted(s["raw"])), "first_date": min(s["dates"]),
                          "last_date": max(s["dates"]), "home_matches": s["home"],
                          "away_matches": s["away"], "total_matches": s["home"] + s["away"]})
    write_csv(os.path.join(run, "team_inventory.csv"), inventory,
              ["team_id", "current_label", "raw_names", "first_date", "last_date",
               "home_matches", "away_matches", "total_matches"])

    # ---------- M49 + dictionary + rules
    m49 = parse_m49(M49_OVERVIEW)
    chk("m49_areas_parsed", len(m49["areas"]) >= 240, f"got {len(m49['areas'])}")
    dict_rows = build_dictionary(m49)
    write_csv(os.path.join(PKG, "region_dictionary.csv"), dict_rows,
              ["standard_version", "area_code", "original_name", "zh_name", "parent_code",
               "original_level", "project_region_code", "project_unit_code", "is_project_unit",
               "merge_rule", "note", "source_id"])
    areas_rows = [{"standard_version": "M49 accessed 2026-10-26 (UNSD)", "m49_code": a["code"],
                   "original_name": a["name"], "iso2": a["iso2"], "iso3": a["iso3"],
                   "region_code": a["region_code"], "region_name": a["region_name"],
                   "subregion_code": a["subregion_code"], "subregion_name": a["subregion_name"],
                   "intermediate_code": a["inter_code"], "intermediate_name": a["inter_name"],
                   "project_region_code": a["region_code"], "project_unit_code": a["unit_code"],
                   "zh_name": "", "source_id": "SRC-M49-OVERVIEW-2026"}
                  for a in sorted(m49["areas"].values(), key=lambda x: x["code"])]
    write_csv(os.path.join(run, "m49_areas.csv"), areas_rows,
              ["standard_version", "m49_code", "original_name", "iso2", "iso3", "region_code",
               "region_name", "subregion_code", "subregion_name", "intermediate_code",
               "intermediate_name", "project_region_code", "project_unit_code", "zh_name", "source_id"])
    # no parent-child double counting among project units
    unit_codes = {r["area_code"] for r in dict_rows if r["is_project_unit"] == "true"}
    parents_of_units = {r["parent_code"] for r in dict_rows if r["is_project_unit"] == "true"}
    chk("project_units_exclusive", not (unit_codes & parents_of_units), str(unit_codes & parents_of_units))
    chk("project_units_count", len(unit_codes) == 22, f"got {len(unit_codes)}")

    seed_rows = read_csv(SEED)
    rules = build_rules(seed_rows, m49)
    rules_by_team = defaultdict(list)
    for r in rules:
        rules_by_team[r["team_id"]].append(r)
    chk("every_team_has_rule", set(rules_by_team) == set(stats), f"missing {set(stats) - set(rules_by_team)}")
    # coverage + overlap
    overlap, uncovered = [], []
    for tid, rs in rules_by_team.items():
        rs = sorted(rs, key=lambda x: x["date_start"])
        if rs[0]["date_start"] > WINDOW_START or rs[-1]["date_end"] < WINDOW_END:
            uncovered.append(tid)
        for a, b in zip(rs, rs[1:]):
            if a["date_end"] >= b["date_start"]:
                overlap.append((tid, a["date_end"], b["date_start"]))
    chk("rules_cover_window", not uncovered, str(uncovered))
    chk("rules_no_overlap", not overlap, str(overlap))
    write_csv(os.path.join(run, "team_geography_rules.csv"), rules,
              ["rule_id", "team_id", "entity", "m49_code", "project_region_code", "project_unit_code",
               "date_start", "date_end", "date_precision", "status", "source_id", "reason"])

    # ---------- per-match relations
    rel_rows = []
    rel_counter = Counter()
    for r in inc:
        m = clean_by_id[r["match_id"]]
        hr = rule_for(rules_by_team, m["home_team_id"], m["date"])
        ar = rule_for(rules_by_team, m["away_team_id"], m["date"])
        hreg, hunit = hr["project_region_code"], hr["project_unit_code"]
        areg, aunit = ar["project_region_code"], ar["project_unit_code"]
        relation = relation_of(hreg, hunit, areg, aunit)
        a_ok = bool(hreg)
        if not hreg:
            a_reason = "主队大区未定（多区/未知历史实体）"
        else:
            a_reason = "主队大区已定"
        if relation == "cross_region":
            b_ok, b_reason = True, "双方大区不同，跨大区可判定（细区缺失不影响）"
        elif relation in ("same_unit", "same_region_diff_unit"):
            b_ok, b_reason = True, "同大区且双方细区明确"
        elif relation == "unknown_same_region":
            b_ok, b_reason = False, "同大区但细区不足，关系未知"
        else:
            b_ok, b_reason = False, "大区信息不足"
        c_ok = bool(hunit)
        c_reason = "主队细区已定" if c_ok else "主队细区未定"
        rel_rows.append({
            "match_id": r["match_id"], "data_version": r["data_version"],
            "identity_version": r["identity_version"], "sample_id": r["sample_id"],
            "date": m["date"], "era": r["analysis_era_id"], "tournament_group": r["tournament_group"],
            "home_team_id": m["home_team_id"], "away_team_id": m["away_team_id"],
            "home_region": hreg, "home_unit": hunit, "home_rule_id": hr["rule_id"], "home_status": hr["status"],
            "away_region": areg, "away_unit": aunit, "away_rule_id": ar["rule_id"], "away_status": ar["status"],
            "direction": f"{hreg}>{areg}" if hreg and areg else "",
            "relation": relation,
            "A_usable": str(a_ok).lower(), "A_reason": a_reason,
            "B_usable": str(b_ok).lower(), "B_reason": b_reason,
            "C_usable": str(c_ok).lower(), "C_reason": c_reason})
        rel_counter["A" if a_ok else "A_no"] += 1
        rel_counter["B" if b_ok else "B_no"] += 1
        rel_counter["C" if c_ok else "C_no"] += 1
        rel_counter["rel_" + relation] += 1
    write_csv(os.path.join(run, "match_region_relations.csv"), rel_rows,
              ["match_id", "data_version", "identity_version", "sample_id", "date", "era",
               "tournament_group", "home_team_id", "away_team_id", "home_region", "home_unit",
               "home_rule_id", "home_status", "away_region", "away_unit", "away_rule_id", "away_status",
               "direction", "relation", "A_usable", "A_reason", "B_usable", "B_reason", "C_usable", "C_reason"])
    chk("relation_rows_equal_sample", len(rel_rows) == EXPECTED["included"])
    chk("relation_no_duplicate_match", len({r["match_id"] for r in rel_rows}) == len(rel_rows))

    # ---------- counts
    eras = ["1980s", "1990s", "2000s", "2010s", "2020_2024"]
    tgroups = ["friendly", "non_friendly"]
    regions = ["002", "019", "142", "150", "009"]
    units = sorted(unit_codes)

    def agg(keyfn):
        d = defaultdict(lambda: {"n": 0, "teams": Counter()})
        for row in rel_rows:
            k = keyfn(row)
            d[k]["n"] += 1
            d[k]["teams"][row["home_team_id"]] += 1
        return d

    def contribution(teams: Counter, n: int):
        top = teams.most_common(3)
        return {"n_teams": len(teams),
                "top1_share": round(top[0][1] / n, 4) if n else 0.0,
                "top3_share": round(sum(v for _, v in top) / n, 4) if n else 0.0,
                "top1_team": top[0][0] if top else ""}

    rows = []
    a = agg(lambda r: (r["home_region"] or "UNKNOWN", r["era"], r["tournament_group"]))
    for reg in regions + ["UNKNOWN"]:
        for era in eras:
            for tg in tgroups:
                cell = a.get((reg, era, tg))
                n = cell["n"] if cell else 0
                c = contribution(cell["teams"], n) if cell else {"n_teams": 0, "top1_share": 0, "top3_share": 0, "top1_team": ""}
                rows.append({"home_region": reg, "region_zh": REGION_ZH.get(reg, "未定"),
                             "era": era, "tournament_group": tg, "matches": n,
                             "n_teams": c["n_teams"], "top1_team": c["top1_team"],
                             "top1_share": c["top1_share"], "top3_share": c["top3_share"]})
    write_csv(os.path.join(run, "counts_home_region_era_tournament.csv"), rows,
              ["home_region", "region_zh", "era", "tournament_group", "matches", "n_teams",
               "top1_team", "top1_share", "top3_share"])
    sum_region = sum(r["matches"] for r in rows)
    chk("region_counts_sum_to_sample", sum_region == EXPECTED["included"], f"{sum_region}")

    rows = []
    u = agg(lambda r: (r["home_unit"] or "UNKNOWN", r["era"], r["tournament_group"]))
    for unit in units + ["UNKNOWN"]:
        for era in eras:
            for tg in tgroups:
                cell = u.get((unit, era, tg))
                n = cell["n"] if cell else 0
                c = contribution(cell["teams"], n) if cell else {"n_teams": 0, "top1_share": 0, "top3_share": 0, "top1_team": ""}
                rows.append({"home_unit": unit, "unit_zh": REGION_ZH.get(unit, "未定"),
                             "era": era, "tournament_group": tg, "matches": n,
                             "n_teams": c["n_teams"], "top1_team": c["top1_team"],
                             "top1_share": c["top1_share"], "top3_share": c["top3_share"]})
    write_csv(os.path.join(run, "counts_home_unit_era_tournament.csv"), rows,
              ["home_unit", "unit_zh", "era", "tournament_group", "matches", "n_teams",
               "top1_team", "top1_share", "top3_share"])
    chk("unit_counts_sum_to_sample", sum(r["matches"] for r in rows) == EXPECTED["included"])

    rows = []
    b = agg(lambda r: (r["home_region"] or "UNKNOWN", r["relation"], r["era"], r["tournament_group"]))
    for reg in regions + ["UNKNOWN"]:
        for relation in ["same_unit", "same_region_diff_unit", "cross_region", "unknown_same_region", "unknown_region"]:
            for era in eras:
                for tg in tgroups:
                    cell = b.get((reg, relation, era, tg))
                    rows.append({"home_region": reg, "relation": relation, "era": era,
                                 "tournament_group": tg, "matches": cell["n"] if cell else 0,
                                 "n_teams": len(cell["teams"]) if cell else 0})
    write_csv(os.path.join(run, "counts_relation_era_tournament.csv"), rows,
              ["home_region", "relation", "era", "tournament_group", "matches", "n_teams"])
    chk("relation_counts_sum_to_sample", sum(r["matches"] for r in rows) == EXPECTED["included"])

    rows = []
    dm = Counter((r["home_region"] or "UNKNOWN", r["away_region"] or "UNKNOWN") for r in rel_rows)
    for hr in regions + ["UNKNOWN"]:
        for ar in regions + ["UNKNOWN"]:
            rows.append({"home_region": hr, "away_region": ar, "matches": dm.get((hr, ar), 0)})
    write_csv(os.path.join(run, "counts_direction_matrix.csv"), rows,
              ["home_region", "away_region", "matches"])
    chk("direction_matrix_sum", sum(r["matches"] for r in rows) == EXPECTED["included"])

    rows = []
    for target in ("A", "B", "C"):
        for era in eras:
            for tg in tgroups:
                sub = [r for r in rel_rows if r["era"] == era and r["tournament_group"] == tg]
                ok = [r for r in sub if r[f"{target}_usable"] == "true"]
                reasons = Counter(r[f"{target}_reason"] for r in sub if r[f"{target}_usable"] != "true")
                rows.append({"target": target, "era": era, "tournament_group": tg,
                             "usable": len(ok), "unusable": len(sub) - len(ok),
                             "unusable_reasons": "; ".join(f"{k}:{v}" for k, v in reasons.most_common())})
    write_csv(os.path.join(run, "unknown_distribution.csv"), rows,
              ["target", "era", "tournament_group", "usable", "unusable", "unusable_reasons"])

    # ---------- candidates
    reg_tot = Counter(r["home_region"] for r in rel_rows if r["home_region"])
    unit_tot = Counter(r["home_unit"] for r in rel_rows if r["home_unit"])
    rel_by_reg = Counter((r["home_region"], r["relation"]) for r in rel_rows if r["home_region"])
    cands = []
    top_regions = [k for k, _ in reg_tot.most_common(4)]
    pair_i = 0
    for i in range(len(top_regions)):
        for j in range(i + 1, len(top_regions)):
            x, y = top_regions[i], top_regions[j]
            if min(reg_tot[x], reg_tot[y]) < 500:
                continue
            pair_i += 1
            cands.append({"target_id": f"CAND-A{pair_i}", "target_type": "A",
                          "home_background": f"{REGION_ZH[x]} vs {REGION_ZH[y]}",
                          "comparison_groups": f"主队大区 {x} 与 {y}",
                          "difference_direction": f"{REGION_ZH[x]}主胜率 − {REGION_ZH[y]}主胜率（方向待定，未计算）",
                          "purpose": "主队大区背景比较",
                          "coverage_issue": f"场数 {reg_tot[x]} vs {reg_tot[y]}；见 counts 文件",
                          "status": "candidate_pending_mainline"})
    for reg in top_regions[:2]:
        for relation in ("cross_region", "same_unit"):
            n = rel_by_reg.get((reg, relation), 0)
            if n >= 150:
                cands.append({"target_id": f"CAND-B{len([c for c in cands if c['target_type']=='B'])+1}",
                              "target_type": "B",
                              "home_background": f"{REGION_ZH[reg]}内",
                              "comparison_groups": f"{relation} vs 其余关系（固定主队大区）",
                              "difference_direction": f"固定{REGION_ZH[reg]}后 cross/same 关系主胜率差（未计算）",
                              "purpose": "同一主队大区内的对手关系比较",
                              "coverage_issue": f"{relation} 场数 {n}",
                              "status": "candidate_pending_mainline"})
    unit_top = [k for k, _ in unit_tot.most_common(8)]
    for reg in top_regions[:2]:
        ins = [uu for uu in unit_top if uu in unit_tot and
               [d for d in dict_rows if d["is_project_unit"] == "true" and d["area_code"] == uu and d["parent_code"] == reg]]
        if len(ins) >= 2:
            cands.append({"target_id": f"CAND-C{len([c for c in cands if c['target_type']=='C'])+1}",
                          "target_type": "C",
                          "home_background": REGION_ZH[reg],
                          "comparison_groups": " 与 ".join(REGION_ZH.get(x, x) for x in ins[:3]),
                          "difference_direction": "洲内细区之间主胜率差（未计算）",
                          "purpose": "大区平均是否遮盖洲内差异",
                          "coverage_issue": "；".join(f"{REGION_ZH.get(x,x)} {unit_tot[x]}" for x in ins[:3]),
                          "status": "candidate_pending_mainline"})
    write_csv(os.path.join(run, "candidate_comparisons.csv"), cands,
              ["target_id", "target_type", "home_background", "comparison_groups",
               "difference_direction", "purpose", "coverage_issue", "status"])

    # ---------- reference support
    ref_rows = []
    for c in cands:
        t = c["target_type"]
        if t == "A":
            ref = "母样本（1980—2024，非中立，合格会员）"
            sub = rel_rows
        elif t == "B":
            ref = "该主队大区内合并赛程"
            reg = c["home_background"].split("内")[0]
            reg_code = next((k for k, v in REGION_ZH.items() if v == reg), "")
            sub = [r for r in rel_rows if r["home_region"] == reg_code]
        else:
            ref = "该大区内合并赛程"
            reg_code = next(k for k, v in REGION_ZH.items() if v == c["home_background"])
            sub = [r for r in rel_rows if r["home_region"] == reg_code]
        layers = Counter((r["era"], r["tournament_group"]) for r in sub)
        missing = [f"{e}|{g}" for e in eras for g in tgroups if layers.get((e, g), 0) == 0]
        ref_rows.append({"target_id": c["target_id"], "reference_population": ref,
                         "reference_matches": len(sub),
                         "layers_present": len(layers), "layers_missing": "; ".join(missing),
                         "layer_counts": "; ".join(f"{e}|{g}:{layers.get((e,g),0)}" for e in eras for g in tgroups),
                         "note": "正权重层缺组则该目标不可估；不补零、不静默删层"})
    write_csv(os.path.join(run, "reference_support.csv"), ref_rows,
              ["target_id", "reference_population", "reference_matches", "layers_present",
               "layers_missing", "layer_counts", "note"])

    # ---------- micro checks (fixtures)
    fx_rules = {"team:x": [{"rule_id": "R1", "date_start": "1980-01-01", "date_end": "1999-12-31",
                            "project_region_code": "150", "project_unit_code": "151"},
                           {"rule_id": "R2", "date_start": "2000-01-01", "date_end": "2024-12-31",
                            "project_region_code": "142", "project_unit_code": "030"}]}
    chk("micro_boundary_switch", rule_for(fx_rules, "team:x", "1999-12-31")["rule_id"] == "R1"
        and rule_for(fx_rules, "team:x", "2000-01-01")["rule_id"] == "R2")
    chk("micro_swap_direction", relation_of("150", "151", "002", "015") == "cross_region"
        and f"002>150" != f"150>002")
    chk("micro_region_known_unit_unknown", relation_of("150", "", "150", "151") == "unknown_same_region")
    chk("micro_cross_region_without_units", relation_of("150", "", "002", "") == "cross_region")
    chk("micro_same_unit", relation_of("150", "151", "150", "151") == "same_unit"
        and relation_of("150", "151", "150", "155") == "same_region_diff_unit")
    chk("micro_unknown_region", relation_of("", "", "150", "151") == "unknown_region")
    unit_rows = read_csv(os.path.join(run, "counts_home_unit_era_tournament.csv"))
    zero_cells = sum(1 for r in unit_rows if int(r["matches"]) == 0)
    chk("micro_zero_rows_present", zero_cells > 0, f"{zero_cells} zero cells in unit counts")
    chk("micro_unknown_distinct_from_zero",
        any(r["home_unit"] == "UNKNOWN" and int(r["matches"]) > 0 for r in unit_rows),
        "unknown category kept separate from zero-filled combos")

    # ---------- write reports
    linkage = {"q2_rows": len(q2), "included": len(inc), "excluded": len(q2) - len(inc),
               "versions": [{"data_version": k[0], "identity_version": k[1], "sample_id": k[2],
                             "rows": v} for k, v in q2_versions.items()],
               "eras": dict(Counter(r["analysis_era_id"] for r in inc)),
               "tournament_groups": dict(Counter(r["tournament_group"] for r in inc)),
               "home_labels": len({clean_by_id[r["match_id"]]["home_team_id"] for r in inc}),
               "away_labels": len({clean_by_id[r["match_id"]]["away_team_id"] for r in inc}),
               "union_labels": len(stats),
               "duplicate_match_ids": dup_q2 + dup_clean, "unmatched": len(missing),
               "join_consistency_failures": len(bad_link), "row_inflation": 0,
               "relation_rows": len(rel_rows)}
    json.dump(linkage, open(os.path.join(run, "linkage_checks.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    json.dump(inputs, open(os.path.join(run, "inputs_used.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)

    # sources
    write_csv(os.path.join(PKG, "sources.csv"), [
        {"source_id": "SRC-M49-UNSD-2026", "title": "Standard country or area codes for statistical use (M49)",
         "institution": "United Nations Statistics Division (UNSD)",
         "url": "https://unstats.un.org/unsd/methodology/m49/", "accessed_at": "2026-10-26",
         "supports": "官方地区代码与层级（Region/Sub-region/Intermediate Region）；FAQ 对台湾/科索沃的 M49 处理",
         "local_path": "data/external/geography_preparation/geo-prep-v1/sources/m49_page.html",
         "sha256": inputs["m49_page_html"]["sha256"], "status": "full_text_saved"},
        {"source_id": "SRC-M49-OVERVIEW-2026", "title": "M49 overview table (countries or areas)",
         "institution": "UNSD", "url": "https://unstats.un.org/unsd/methodology/m49/overview/",
         "accessed_at": "2026-10-26", "supports": "国家/地区代码、ISO 码与三级父级链（本包解析对象）",
         "local_path": "data/external/geography_preparation/geo-prep-v1/sources/m49_overview.html",
         "sha256": inputs["m49_overview_html"]["sha256"], "status": "full_text_saved"},
        {"source_id": "SRC-REGISTRY", "title": "association_registry.csv（身份阶段官方名册提取）",
         "institution": "项目内部（FIFA Financial Report 2018 提取）",
         "url": "data/processed/team_identity/identity-reviewed-29d880765c1623764940/association_registry.csv",
         "accessed_at": "2026-10-26", "supports": "仅用于实体名称交叉核对，不作地理代码来源",
         "local_path": "data/processed/team_identity/identity-reviewed-29d880765c1623764940/association_registry.csv",
         "sha256": inputs["association_registry"]["sha256"], "status": "reused"},
    ], ["source_id", "title", "institution", "url", "accessed_at", "supports", "local_path", "sha256", "status"])

    # exceptions
    ex = []
    for tid in ("team:england", "team:scotland", "team:wales", "team:northern-ireland"):
        ex.append({"exception_id": f"EXC-{tid.split(':')[1]}", "team_id": tid,
                   "issue": "英国四个独立足协球队，M49 无对应条目", "evidence": "M49 只有 United Kingdom (826)",
                   "current_level": "大区=欧洲；细区=北欧", "treatment": "映射到 826 并保留独立球队ID",
                   "affected_targets": "A/B/C 均可用", "status": "resolved_project_mapping"})
    ex.append({"exception_id": "EXC-kosovo", "team_id": "team:kosovo",
               "issue": "M49 不单列科索沃", "evidence": "官方 FAQ：M49 中视为塞尔维亚(688)一部分；统计可用 412",
               "current_level": "大区=欧洲；细区=南欧", "treatment": "采用 412（统计用码），地理层级同塞尔维亚",
               "affected_targets": "A/B/C 均可用", "status": "resolved_source_faq"})
    ex.append({"exception_id": "EXC-taiwan", "team_id": "team:taiwan",
               "issue": "M49 不单列台湾", "evidence": "官方 FAQ：M49 中视为中国(156)一部分",
               "current_level": "大区=亚洲；细区=东亚", "treatment": "采用 156，保留独立球队ID",
               "affected_targets": "A/B/C 均可用", "status": "resolved_source_faq"})
    ex.append({"exception_id": "EXC-german-dr", "team_id": "team:german-dr",
               "issue": "已消失足协（东德）", "evidence": "M49 只有德国(276)",
               "current_level": "大区=欧洲；细区=西欧", "treatment": "按领土对应德国 276；不改球队ID",
               "affected_targets": "A/B/C 均可用", "status": "resolved_project_mapping"})
    ex.append({"exception_id": "EXC-czechoslovakia", "team_id": "team:czechoslovakia",
               "issue": "已消失足协", "evidence": "M49 只有捷克(203)/斯洛伐克(703)，两国同属东欧",
               "current_level": "大区=欧洲；细区=东欧", "treatment": "以 203 为载体，细区不受继承国选择影响",
               "affected_targets": "A/B/C 均可用", "status": "resolved_project_mapping"})
    ex.append({"exception_id": "EXC-yugoslavia", "team_id": "team:yugoslavia",
               "issue": "已消失足协", "evidence": "M49 只有塞尔维亚(688)，前南各国均属南欧",
               "current_level": "大区=欧洲；细区=南欧", "treatment": "以 688 为载体，细区不受继承国选择影响",
               "affected_targets": "A/B/C 均可用", "status": "resolved_project_mapping"})
    ex.append({"exception_id": "EXC-russia-ussr", "team_id": "team:russia",
               "issue": "Russia 标签在早期比赛代表苏联/独联体，属跨欧亚实体",
               "evidence": "M49 只有俄罗斯(643，欧洲/东欧)；苏联与独联体跨欧亚",
               "current_level": "1992-07-03 后：欧洲/东欧；此前：多区未知",
               "treatment": "三段日期规则；早期比赛主队大区未知，影响 A/C 可用性",
               "affected_targets": "A/C（苏联段主队）；B（任一方为苏联段）",
               "status": "partial_unknown_by_design"})
    write_csv(os.path.join(PKG, "exceptions.csv"), ex,
              ["exception_id", "team_id", "issue", "evidence", "current_level", "treatment",
               "affected_targets", "status"])

    # validation + manifest
    report = {"schema_version": "region-preparation-v1", "run_id": run_id,
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "inputs": inputs,
              "expected_vs_actual": {k: {"expected": v, "actual": {"q2_rows": len(q2), "included": len(inc),
                                                                  "home_labels": len({clean_by_id[r["match_id"]]["home_team_id"] for r in inc}),
                                                                  "away_labels": len({clean_by_id[r["match_id"]]["away_team_id"] for r in inc}),
                                                                  "union_labels": len(stats)}[k]} for k, v in EXPECTED.items()},
              "checks": checks, "failures": [c["name"] for c in checks if not c["passed"]],
              "stats": {"relation_counts": dict(rel_counter),
                        "regions": {REGION_ZH[k]: v for k, v in reg_tot.items()},
                        "units_top": {REGION_ZH.get(k, k): v for k, v in unit_tot.most_common(10)},
                        "candidates": len(cands)},
              "not_run": ["地区胜率/胜平负统计", "共同构成调整值/区间/排名",
                          "正式脚本与输出契约冻结", "第四/第五问检验"]}
    json.dump(report, open(os.path.join(run, "validation_report.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)

    files = sorted(os.listdir(run))
    manifest = {"run_id": run_id, "command": "python scripts/prepare_region_mapping.py",
                "package_dir": "data/external/geography_preparation/geo-prep-v1",
                "run_dir": os.path.relpath(run, ROOT),
                "files": {f: sha256(os.path.join(run, f)) for f in files if f != "manifest.json"},
                "package_files": {f: sha256(os.path.join(PKG, f)) for f in sorted(os.listdir(PKG))
                                  if os.path.isfile(os.path.join(PKG, f))},
                "cannot_redo": [], "versions": {"data_version": "prep-3fab808178cf8ad71d88",
                                                "identity_version": "identity-reviewed-29d880765c1623764940",
                                                "sample_id": "sample-3bc69e2cc4f843242018",
                                                "q2_version": "tournaments-4893e38db46f83f6c219",
                                                "m49": "accessed 2026-10-26"}}
    json.dump(manifest, open(os.path.join(run, "manifest.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)

    print(json.dumps({"run_dir": os.path.relpath(run, ROOT), "failures": report["failures"],
                      "relation_counts": dict(rel_counter), "candidates": len(cands)}, ensure_ascii=False))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
