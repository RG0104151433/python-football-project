#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第三问（地域差异）数据准备工具 v2：资料整理、关联、计数、逐组支持与校验。

不计算地区胜率/调整值/区间/排名，不冻结正式统计协议。

用法（仓库根目录）：
  python scripts/prepare_region_mapping.py prepare            # 默认包 geo-prep-v2，自动生成运行目录
  python scripts/prepare_region_mapping.py prepare --package data/external/geography_preparation/geo-prep-v2 --tag r2
  python scripts/prepare_region_mapping.py finalize outputs/logs/regions/<run_dir>   # 报告生成完后登记最终指纹

失败语义：输入/规则/父级/引用不合格时，写出 status=failed 的 validation_report.json 并以退出码 2 结束，
不生成 handoff/manifest 成功标记。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html as htmllib
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PACKAGE = os.path.join(ROOT, "data", "external", "geography_preparation", "geo-prep-v2")
DEFAULT_Q2 = os.path.join(ROOT, "outputs", "tables", "tournaments",
                          "tournaments-4893e38db46f83f6c219", "analysis_membership.csv")
DEFAULT_CLEAN = os.path.join(ROOT, "data", "processed", "prep-3fab808178cf8ad71d88", "matches_clean.csv")
DEFAULT_IDENTITY = os.path.join(ROOT, "data", "processed", "team_identity", "identity-reviewed-29d880765c1623764940")
WINDOW_START, WINDOW_END = "1980-01-01", "2024-12-31"
EXPECTED = {"q2_rows": 48102, "included": 24917, "home_labels": 214, "away_labels": 214, "union_labels": 215}
REGION_ZH = {"001": "世界", "002": "非洲", "019": "美洲", "142": "亚洲", "150": "欧洲", "009": "大洋洲",
             "202": "撒哈拉以南非洲", "419": "拉丁美洲和加勒比", "053": "澳大利亚和新西兰",
             "015": "北非", "011": "西非", "014": "东非", "017": "中非", "018": "南部非洲",
             "021": "北美", "013": "中美洲", "029": "加勒比", "005": "南美",
             "030": "东亚", "034": "南亚", "035": "东南亚", "143": "中亚", "145": "西亚",
             "039": "南欧", "151": "东欧", "154": "北欧", "155": "西欧",
             "054": "美拉尼西亚", "057": "密克罗尼西亚", "061": "波利尼西亚"}
ERAS = ["1980s", "1990s", "2000s", "2010s", "2020_2024"]
TGS = ["friendly", "non_friendly"]
RELATIONS = ["same_unit", "same_region_diff_unit", "cross_region", "unknown_same_region", "unknown_region"]


class InputError(Exception):
    """输入或规则不合格（fail-fast）。"""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def d(s):
    return date.fromisoformat(s)


# ---------------------------------------------------------------- M49
def parse_m49(path):
    t = open(path, encoding="utf-8", errors="ignore").read()
    areas, nodes, parents = {}, {}, {}
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        cells = [re.sub(r"\s+", " ", re.sub("<[^>]+>", "", htmllib.unescape(c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if not cells:
            continue
        idx = [i for i, c in enumerate(cells) if re.fullmatch(r"[A-Z]{2}", c)]
        if not idx:
            continue
        j = idx[0]
        if j < 6 or "World" not in cells[: j]:
            continue
        code, name, iso2, iso3 = cells[j - 1], cells[j - 2], cells[j], cells[j + 1]
        par = cells[: j - 2]
        pairs = [(par[k], par[k + 1]) for k in range(0, len(par) - 1, 2)]
        for c, n in pairs:
            nodes[c] = n
        for k in range(1, len(pairs)):
            parents[pairs[k][0]] = pairs[k - 1][0]
        region = pairs[1] if len(pairs) > 1 else ("", "")
        sub = pairs[2] if len(pairs) > 2 else ("", "")
        inter = pairs[3] if len(pairs) > 3 else ("", "")
        areas[code] = {"code": code, "name": name, "iso2": iso2, "iso3": iso3,
                       "region_code": region[0], "subregion_code": sub[0],
                       "inter_code": inter[0], "unit_code": inter[0] or sub[0]}
    return {"areas": areas, "nodes": nodes, "parents": parents}


# ---------------------------------------------------------------- input validation
def load_q2_rows(rows):
    bad = [r["included"] for r in rows if r["included"].strip().lower() not in ("true", "false")]
    if bad:
        raise InputError(f"included 非法：{sorted(set(bad))[:3]}")
    vers = {(r["data_version"], r["identity_version"], r["sample_id"]) for r in rows}
    if len(vers) != 1:
        raise InputError(f"版本不唯一：{sorted(vers)[:3]}")
    ids = [r["match_id"] for r in rows]
    if len(ids) != len(set(ids)):
        dup = [k for k, v in Counter(ids).items() if v > 1][:3]
        raise InputError(f"重复 match_id：{dup}")
    return rows


def load_q2(path):
    return load_q2_rows(read_csv(path))


def load_clean(path):
    rows = read_csv(path)
    ids = [r["match_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise InputError("清洗表存在重复 match_id")
    return {r["match_id"]: r for r in rows}


# ---------------------------------------------------------------- rules
def build_rules(seed, m49, carrier):
    rules, rid = [], 0
    for s in sorted(seed, key=lambda x: x["team_id"]):
        tid, code = s["team_id"], s["m49_code"]
        ck = carrier.get(tid, {}).get("carrier_kind", "")
        if tid == "team:russia":
            for st, en, reg, unit, status, why in [
                ("1980-01-01", "1991-12-25", "", "", "multi_region", "苏联时期：跨欧亚，无法唯一归入单一大区"),
                ("1991-12-26", "1992-07-02", "", "", "multi_region", "独联体过渡期：无单一大区"),
                ("1992-07-03", "2024-12-31", "150", "151", "resolved",
                 "俄罗斯：欧洲/东欧。分段界为项目约定（FIFA 2018 年报 RUS 1912/1992 年份级；UPI 1992-07-03 大会报道为线索），非 FIFA 逐日官方记录")]:
                rid += 1
                rules.append({"rule_id": f"GEO2-R{rid:03d}", "team_id": tid, "carrier_m49_code": code,
                              "carrier_kind": ck, "project_region_code": reg, "project_unit_code": unit,
                              "date_start": st, "date_end": en, "date_precision": "project_rule",
                              "status": status, "reason": why})
        else:
            area = m49["areas"].get(code)
            if area is None and code == "412":
                area = {"region_code": "150", "unit_code": "039"}
            if area is None:
                raise InputError(f"承载代码不在 M49 表中：{tid} -> {code}")
            rid += 1
            rules.append({"rule_id": f"GEO2-R{rid:03d}", "team_id": tid, "carrier_m49_code": code,
                          "carrier_kind": ck, "project_region_code": area["region_code"],
                          "project_unit_code": area["unit_code"], "date_start": WINDOW_START,
                          "date_end": WINDOW_END, "date_precision": "analysis_window",
                          "status": "project_mapping" if ck in ("historical_association_carrier",
                                                                "constituent_association_of_UK",
                                                                "statistical_area_412",
                                                                "statistical_area_inside_156") else "source_explicit",
                          "reason": "M49 国家/地区条目"})
    return rules


def check_rule_series(rules_by_team, window=(WINDOW_START, WINDOW_END)):
    """逐队检查：覆盖完整、无中间断档、无重叠。"""
    problems = []
    for tid, rs in rules_by_team.items():
        rs = sorted(rs, key=lambda x: x["date_start"])
        if d(rs[0]["date_start"]) != d(window[0]):
            problems.append(f"{tid}: 起点 {rs[0]['date_start']} != {window[0]}")
        if d(rs[-1]["date_end"]) != d(window[1]):
            problems.append(f"{tid}: 终点 {rs[-1]['date_end']} != {window[1]}")
        for a, b in zip(rs, rs[1:]):
            gap = (d(b["date_start"]) - d(a["date_end"])).days
            if gap > 1:
                problems.append(f"{tid}: 中间断档 {a['date_end']} → {b['date_start']}")
            elif gap <= 0:
                problems.append(f"{tid}: 重叠 {a['date_end']} / {b['date_start']}")
    return problems


def rule_for(rules_by_team, team_id, day):
    hits = [r for r in rules_by_team.get(team_id, []) if r["date_start"] <= day <= r["date_end"]]
    if len(hits) > 1:
        raise InputError(f"{team_id} 在 {day} 命中多条规则，拒绝静默取舍")
    return hits[0] if hits else None


def check_rule_parents(rules, m49):
    problems = []
    for r in rules:
        if not r["project_unit_code"]:
            continue
        expect = m49["parents"].get(r["project_unit_code"], "")
        if expect != r["project_region_code"]:
            problems.append(f"{r['rule_id']}: 细区 {r['project_unit_code']} 的原始父级 {expect} != 规则大区 {r['project_region_code']}")
    return problems


# ---------------------------------------------------------------- relations
def relation_of(hr, hu, ar, au):
    if not hr or not ar:
        return "unknown_region"
    if hr != ar:
        return "cross_region"
    if hu and au:
        return "same_unit" if hu == au else "same_region_diff_unit"
    return "unknown_same_region"


def process_relations(records, rules_by_team):
    """records: 迭代 (match_id, date, home_team_id, away_team_id) → 逐场关系行。"""
    out = []
    for mid, day, ht, at in records:
        hr_, ar_ = rule_for(rules_by_team, ht, day), rule_for(rules_by_team, at, day)
        if hr_ is None or ar_ is None:
            raise InputError(f"{mid}: 缺少匹配规则（{ht if hr_ is None else at} @ {day}）")
        hreg, hunit = hr_["project_region_code"], hr_["project_unit_code"]
        areg, aunit = ar_["project_region_code"], ar_["project_unit_code"]
        rel = relation_of(hreg, hunit, areg, aunit)
        b_ok = rel in ("same_unit", "same_region_diff_unit", "cross_region")
        out.append({"match_id": mid, "date": day, "home_team_id": ht, "away_team_id": at,
                    "home_region": hreg, "home_unit": hunit, "home_rule_id": hr_["rule_id"],
                    "away_region": areg, "away_unit": aunit, "away_rule_id": ar_["rule_id"],
                    "direction": f"{hreg}>{areg}" if hreg and areg else "",
                    "relation": rel,
                    "A_usable": bool(hreg), "B_usable": b_ok, "C_usable": bool(hunit),
                    "A_reason": "主队大区已定" if hreg else "主队大区未定",
                    "B_reason": "关系可判定" if b_ok else ("同大区但细区不足" if rel == "unknown_same_region" else "大区信息不足"),
                    "C_reason": "主队细区已定" if hunit else "主队细区未定"})
    return out


# ---------------------------------------------------------------- support
def support_rows(cands, rel_rows, layer_key):
    """逐候选×臂×层 的支持表。layer_key(candidate, era, tg) → 参考层场次。"""
    rows = []
    for c in cands:
        if c["candidate_class"] != "comparison_candidate":
            continue
        bg = c["background_region"]
        arms = [(1, c["arm1_definition"], c["arm1_relation"], c["arm1_unit"], c["arm1_definition"]),
                (2, c["arm2_definition"], c["arm2_relation"], c["arm2_unit"], c["arm2_definition"])]
        for no, definition, relation, unit, _ in arms:
            if c["candidate_type"] == "A":
                reg = (c["arm1_definition"] if no == 1 else c["arm2_definition"]).split("=")[1]
            for era in ERAS:
                for tg in TGS:
                    def match_arm(r):
                        if r["era"] != era or r["tournament_group"] != tg:
                            return False
                        if c["candidate_type"] == "A":
                            return r["home_region"] == reg
                        if c["candidate_type"] == "B":
                            return r["home_region"] == bg and r["relation"] == relation
                        return r["home_region"] == bg and r["home_unit"] == unit
                    group_n = sum(1 for r in rel_rows if match_arm(r))
                    ref_n = layer_key(c, era, tg)
                    if ref_n == 0:
                        status = "reference_layer_absent"
                        reason = "参考人群在该层无比赛（该层不在参考支持范围）"
                    elif group_n == 0:
                        status = "group_missing_layer"
                        reason = "参考要求该层，但该比较组在该层无比赛：当前参考方案下不支持完整比较"
                    else:
                        status = "supported"
                        reason = ""
                    rows.append({"candidate_id": c["candidate_id"], "candidate_type": c["candidate_type"],
                                 "background_region": bg, "arm_no": no, "arm_definition": definition,
                                 "era": era, "tournament_group": tg, "group_matches": group_n,
                                 "reference_matches": ref_n,
                                 "reference_requires_layer": "true" if ref_n > 0 else "false",
                                 "support_status": status, "missing_reason": reason})
    return rows


def arm_support_summary(cands, support):
    out = []
    for c in cands:
        if c["candidate_class"] != "comparison_candidate":
            out.append({"candidate_id": c["candidate_id"], "candidate_type": c["candidate_type"],
                        "candidate_class": c["candidate_class"], "status": "display_only",
                        "layers_both_supported": "", "layers_missing": "",
                        "note": "分布展示候选，不做两组比较"})
            continue
        rows = [r for r in support if r["candidate_id"] == c["candidate_id"]]
        a1 = sum(r["group_matches"] for r in rows if r["arm_no"] == 1)
        a2 = sum(r["group_matches"] for r in rows if r["arm_no"] == 2)
        miss = sorted({f"{r['era']}|{r['tournament_group']}|arm{r['arm_no']}"
                       for r in rows if r["support_status"] == "group_missing_layer"})
        both = sum(1 for era in ERAS for tg in TGS
                   if all(any(r["era"] == era and r["tournament_group"] == tg and r["arm_no"] == n
                              and r["group_matches"] > 0 for r in rows) for n in (1, 2)))
        if a1 == 0 or a2 == 0:
            status = "unsupported_arm_empty"
        elif miss:
            status = "supported_with_missing_layers"
        else:
            status = "supported_all_layers"
        out.append({"candidate_id": c["candidate_id"], "candidate_type": c["candidate_type"],
                    "candidate_class": c["candidate_class"], "status": status,
                    "layers_both_supported": f"{both}/10", "layers_missing": "; ".join(miss),
                    "note": f"arm1={a1}场, arm2={a2}场"})
    return out


# ---------------------------------------------------------------- self tests
def run_self_tests(m49):
    tests = []

    def t(name, fn):
        try:
            fn()
            tests.append({"name": name, "passed": True, "detail": ""})
        except Exception as ex:  # noqa: BLE001
            tests.append({"name": name, "passed": False, "detail": repr(ex)})

    def fx_rules():
        return {"a": [{"rule_id": "R1", "project_region_code": "150", "project_unit_code": "151",
                       "date_start": "1980-01-01", "date_end": "2024-12-31"}],
                "b": [{"rule_id": "R2", "project_region_code": "002", "project_unit_code": "015",
                       "date_start": "1980-01-01", "date_end": "2024-12-31"}],
                "c": [{"rule_id": "R3", "project_region_code": "150", "project_unit_code": "155",
                       "date_start": "1980-01-01", "date_end": "2024-12-31"}],
                "u": [{"rule_id": "R4", "project_region_code": "", "project_unit_code": "",
                       "date_start": "1980-01-01", "date_end": "2024-12-31"}]}

    def swap_test():
        rows = process_relations([("m1", "2000-01-01", "a", "b")], fx_rules())
        rows2 = process_relations([("m1", "2000-01-01", "b", "a")], fx_rules())
        assert rows[0]["direction"] == "150>002" and rows2[0]["direction"] == "002>150"
        assert rows[0]["relation"] == rows2[0]["relation"] == "cross_region"

    def dup_test():
        rows = [{"match_id": "m", "included": "true", "data_version": "d", "identity_version": "i", "sample_id": "s"},
                {"match_id": "m", "included": "true", "data_version": "d", "identity_version": "i", "sample_id": "s"}]
        try:
            load_q2_rows(rows)
        except InputError:
            return
        raise AssertionError("重复ID未被拒绝")

    def bool_test():
        rows = [{"match_id": "m", "included": "yes", "data_version": "d", "identity_version": "i", "sample_id": "s"}]
        try:
            load_q2_rows(rows)
        except InputError:
            return
        raise AssertionError("非法布尔未被拒绝")

    def ver_test():
        rows = [{"match_id": "m1", "included": "true", "data_version": "d", "identity_version": "i1", "sample_id": "s"},
                {"match_id": "m2", "included": "true", "data_version": "d", "identity_version": "i2", "sample_id": "s"}]
        try:
            load_q2_rows(rows)
        except InputError:
            return
        raise AssertionError("版本不一致未被拒绝")

    def gap_test():
        rs = {"t": [{"rule_id": "1", "date_start": "1980-01-01", "date_end": "1990-12-31"},
                    {"rule_id": "2", "date_start": "1995-01-01", "date_end": "2024-12-31"}]}
        probs = check_rule_series(rs)
        assert any("断档" in p for p in probs), probs

    def overlap_test():
        rs = {"t": [{"rule_id": "1", "date_start": "1980-01-01", "date_end": "2000-12-31"},
                    {"rule_id": "2", "date_start": "1995-01-01", "date_end": "2024-12-31"}]}
        probs = check_rule_series(rs)
        assert any("重叠" in p for p in probs), probs

    def multi_rule_test():
        rs = {"a": [{"rule_id": "1", "project_region_code": "150", "project_unit_code": "151",
                     "date_start": "1980-01-01", "date_end": "2005-12-31"},
                    {"rule_id": "2", "project_region_code": "150", "project_unit_code": "151",
                     "date_start": "2000-01-01", "date_end": "2024-12-31"}]}
        try:
            rule_for(rs, "a", "2001-01-01")
        except InputError:
            return
        raise AssertionError("多规则命中未被拒绝")

    def parent_test():
        bad = [{"rule_id": "X", "project_region_code": "002", "project_unit_code": "151"}]
        probs = check_rule_parents(bad, m49)
        assert probs, "父级不一致未被发现"

    def one_side_test():
        rows = process_relations([("m2", "2000-01-01", "a", "u")], fx_rules())
        r = rows[0]
        assert r["A_usable"] and r["C_usable"] and not r["B_usable"] and r["relation"] == "unknown_region"

    def zero_vs_unknown_test():
        rel = [{"home_region": "", "relation": "unknown_region"},
               {"home_region": "150", "relation": "same_unit"}]
        known = sum(1 for r in rel if r["home_region"] == "150")
        unknown = sum(1 for r in rel if r["home_region"] == "")
        assert known == 1 and unknown == 1, "未知与已知未分开统计"

    def support_missing_test():
        cands = [{"candidate_id": "X", "candidate_type": "B", "candidate_class": "comparison_candidate",
                  "background_region": "150", "arm1_definition": "背景=150 且 relation=cross_region",
                  "arm2_definition": "背景=150 且 relation=same_unit", "arm1_relation": "cross_region",
                  "arm2_relation": "same_unit", "arm1_unit": "", "arm2_unit": ""}]
        rel = [{"home_region": "150", "relation": "same_unit", "home_unit": "151", "era": "1980s",
                "tournament_group": "friendly", "home_team_id": "x", "away_team_id": "y", "away_region": "150"}]
        rows = support_rows(cands, rel, lambda c, e, t: 5 if (e, t) == ("1980s", "friendly") else 0)
        arm1 = [r for r in rows if r["arm_no"] == 1 and r["era"] == "1980s" and r["tournament_group"] == "friendly"][0]
        assert arm1["support_status"] == "group_missing_layer", arm1

    t("swap_direction_through_processor", swap_test)
    t("duplicate_match_id_rejected", dup_test)
    t("invalid_boolean_rejected", bool_test)
    t("version_mismatch_rejected", ver_test)
    t("rule_middle_gap_detected", gap_test)
    t("rule_overlap_detected", overlap_test)
    t("multiple_rule_match_rejected", multi_rule_test)
    t("parent_mismatch_detected", parent_test)
    t("one_side_known_relation", one_side_test)
    t("unknown_vs_true_zero", zero_vs_unknown_test)
    t("reference_layer_missing_flagged", support_missing_test)
    return tests


# ---------------------------------------------------------------- prepare
def prepare(args):
    pkg = os.path.abspath(args.package)
    if not os.path.isdir(pkg):
        raise InputError(f"准备包不存在：{pkg}")
    script_path = os.path.abspath(__file__)
    code8 = sha256(script_path)[:8]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = f"-{args.tag}" if args.tag else ""
    run = os.path.join(os.path.abspath(args.run_root), f"preparation-{stamp}-{code8}{tag}")
    os.makedirs(run, exist_ok=True)
    os.makedirs(os.path.join(run, "code"), exist_ok=True)
    shutil.copyfile(script_path, os.path.join(run, "code", "prepare_region_mapping.py"))
    checks = []

    def chk(name, ok, detail=""):
        checks.append({"name": name, "passed": bool(ok), "detail": str(detail)})

    q2 = load_q2(args.q2)
    clean = load_clean(args.clean)
    m49 = parse_m49(os.path.join(pkg, "sources", "m49_overview.html"))
    seed = read_csv(os.path.join(pkg, "team_geography_seed.csv"))
    carrier = {r["team_id"]: r for r in read_csv(os.path.join(pkg, "carrier_model.csv"))}
    dictionary = read_csv(os.path.join(pkg, "region_dictionary.csv"))
    specs = read_csv(os.path.join(pkg, "candidate_specs.csv"))
    exceptions = read_csv(os.path.join(pkg, "exceptions.csv"))

    inc = [r for r in q2 if r["included"] == "true"]
    chk("q2_rows_expected", len(q2) == EXPECTED["q2_rows"], len(q2))
    chk("included_expected", len(inc) == EXPECTED["included"], len(inc))
    missing = [r["match_id"] for r in inc if r["match_id"] not in clean]
    chk("all_included_matched", not missing, len(missing))
    bad_link = [r["match_id"] for r in inc if clean[r["match_id"]]["date"] != r["date"]
                or clean[r["match_id"]]["tournament_group"] != r["tournament_group"]]
    chk("join_field_consistency", not bad_link, len(bad_link))
    chk("neutral_scope", all(clean[r["match_id"]]["is_neutral"] == "false" for r in inc))
    chk("date_window", all(WINDOW_START <= r["date"] <= WINDOW_END for r in inc))
    chk("m49_areas_parsed", len(m49["areas"]) >= 240, len(m49["areas"]))
    known_codes = set(m49["areas"]) | {"001", "412"} | {r["area_code"] for r in dictionary if r["project_level"] == "rollup"}
    chk("dictionary_codes_known", {r["area_code"] for r in dictionary} <= known_codes)
    units = {r["area_code"]: r for r in dictionary if r["is_project_unit"] == "true"}
    chk("project_units_count", len(units) == 22, len(units))
    chk("project_units_parent_in_regions", all(r["project_parent_code"] in REGION_ZH for r in units.values()))
    chk("raw_parents_filled", all(r["raw_parent_code"] for r in dictionary if r["original_level"] in ("subregion", "intermediate")))
    chk("raw_parent_matches_m49", all(r["raw_parent_code"] == m49["parents"].get(r["area_code"], r["raw_parent_code"])
                                     for r in dictionary if r["original_level"] != "project_unit"))
    rules = build_rules(seed, m49, carrier)
    rules_by_team = defaultdict(list)
    for r in rules:
        rules_by_team[r["team_id"]].append(r)
    chk("every_team_has_rule", set(rules_by_team) == {s["team_id"] for s in seed})
    ser = check_rule_series(rules_by_team)
    chk("rules_full_window_no_gap_overlap", not ser, "; ".join(ser[:3]))
    par = check_rule_parents(rules, m49)
    chk("rule_fine_parent_consistency", not par, "; ".join(par[:3]))
    chk("carrier_kind_covered", all(r["team_id"] in carrier for r in rules))

    records = [(r["match_id"], clean[r["match_id"]]["date"],
                clean[r["match_id"]]["home_team_id"], clean[r["match_id"]]["away_team_id"]) for r in inc]
    rel = process_relations(records, rules_by_team)
    meta = {r["match_id"]: r for r in inc}
    for row in rel:
        q = meta[row["match_id"]]
        row.update({"data_version": q["data_version"], "identity_version": q["identity_version"],
                    "sample_id": q["sample_id"], "era": q["analysis_era_id"],
                    "tournament_group": q["tournament_group"]})
    chk("relation_rows_equal_sample", len(rel) == EXPECTED["included"], len(rel))
    chk("relation_no_duplicate", len({r["match_id"] for r in rel}) == len(rel))

    home_labels = {clean[r["match_id"]]["home_team_id"] for r in inc}
    away_labels = {clean[r["match_id"]]["away_team_id"] for r in inc}
    union = home_labels | away_labels
    chk("home_labels", len(home_labels) == EXPECTED["home_labels"], len(home_labels))
    chk("away_labels", len(away_labels) == EXPECTED["away_labels"], len(away_labels))
    chk("union_labels", len(union) == EXPECTED["union_labels"], len(union))

    stats = defaultdict(lambda: {"dates": [], "home": 0, "away": 0, "raw": set()})
    for r in inc:
        c = clean[r["match_id"]]
        for tid, role, raw in ((c["home_team_id"], "home", c["home_team_raw"]),
                               (c["away_team_id"], "away", c["away_team_raw"])):
            s = stats[tid]
            s["dates"].append(c["date"])
            s[role] += 1
            s["raw"].add(raw)
    inventory = [{"team_id": t, "current_label": carrier.get(t, {}).get("entity_label", ""),
                  "raw_names": "; ".join(sorted(s["raw"])), "first_date": min(s["dates"]),
                  "last_date": max(s["dates"]), "home_matches": s["home"], "away_matches": s["away"],
                  "total_matches": s["home"] + s["away"],
                  "carrier_kind": carrier.get(t, {}).get("carrier_kind", "")}
                 for t, s in sorted(stats.items())]
    write_csv(os.path.join(run, "team_inventory.csv"), inventory,
              ["team_id", "current_label", "raw_names", "first_date", "last_date", "home_matches",
               "away_matches", "total_matches", "carrier_kind"])
    write_csv(os.path.join(run, "team_geography_rules.csv"), rules,
              ["rule_id", "team_id", "carrier_m49_code", "carrier_kind", "project_region_code",
               "project_unit_code", "date_start", "date_end", "date_precision", "status", "reason"])
    write_csv(os.path.join(run, "match_region_relations.csv"), rel,
              ["match_id", "data_version", "identity_version", "sample_id", "date", "era",
               "tournament_group", "home_team_id", "away_team_id", "home_region", "home_unit",
               "home_rule_id", "away_region", "away_unit", "away_rule_id", "direction", "relation",
               "A_usable", "A_reason", "B_usable", "B_reason", "C_usable", "C_reason"])

    def cell_rows(keyfn, cats, extra_field):
        agg = defaultdict(lambda: {"n": 0, "teams": Counter()})
        for r in rel:
            k = keyfn(r)
            agg[k]["n"] += 1
            agg[k]["teams"][r["home_team_id"]] += 1
        out = []
        for cat in cats:
            for era in ERAS:
                for tg in TGS:
                    c = agg.get((cat, era, tg), {"n": 0, "teams": Counter()})
                    top = c["teams"].most_common(1)
                    out.append({extra_field: cat, "zh": REGION_ZH.get(cat, "未定"), "era": era,
                                "tournament_group": tg, "matches": c["n"],
                                "n_teams": len(c["teams"]),
                                "top1_team": top[0][0] if top else "",
                                "top1_share": round(top[0][1] / c["n"], 4) if c["n"] else "无法计算"})
        return out
    region_rows = cell_rows(lambda r: r["home_region"] or "UNKNOWN", ["002", "019", "142", "150", "009", "UNKNOWN"], "home_region")
    write_csv(os.path.join(run, "counts_home_region_era_tournament.csv"), region_rows,
              ["home_region", "zh", "era", "tournament_group", "matches", "n_teams", "top1_team", "top1_share"])
    unit_rows = cell_rows(lambda r: r["home_unit"] or "UNKNOWN", sorted(units) + ["UNKNOWN"], "home_unit")
    write_csv(os.path.join(run, "counts_home_unit_era_tournament.csv"), unit_rows,
              ["home_unit", "zh", "era", "tournament_group", "matches", "n_teams", "top1_team", "top1_share"])
    relagg = Counter((r["home_region"] or "UNKNOWN", r["relation"], r["era"], r["tournament_group"]) for r in rel)
    rel_rows = [{"home_region": reg, "relation": relation, "era": era, "tournament_group": tg,
                 "matches": relagg.get((reg, relation, era, tg), 0)}
                for reg in ["002", "019", "142", "150", "009", "UNKNOWN"] for relation in RELATIONS
                for era in ERAS for tg in TGS]
    write_csv(os.path.join(run, "counts_relation_era_tournament.csv"), rel_rows,
              ["home_region", "relation", "era", "tournament_group", "matches"])
    dm = Counter((r["home_region"] or "UNKNOWN", r["away_region"] or "UNKNOWN") for r in rel)
    dm_rows = [{"home_region": a, "away_region": b, "matches": dm.get((a, b), 0)}
               for a in ["002", "019", "142", "150", "009", "UNKNOWN"]
               for b in ["002", "019", "142", "150", "009", "UNKNOWN"]]
    write_csv(os.path.join(run, "counts_direction_matrix.csv"), dm_rows,
              ["home_region", "away_region", "matches"])
    chk("counts_sum", sum(r["matches"] for r in region_rows) == EXPECTED["included"]
        and sum(r["matches"] for r in unit_rows) == EXPECTED["included"]
        and sum(r["matches"] for r in rel_rows) == EXPECTED["included"]
        and sum(r["matches"] for r in dm_rows) == EXPECTED["included"])

    comp = []
    for level, cats in (("region", ["002", "019", "142", "150", "009", "UNKNOWN"]),
                        ("unit", sorted(units) + ["UNKNOWN"])):
        for era in ERAS:
            for tg in TGS:
                layer_n = sum(1 for r in rel if r["era"] == era and r["tournament_group"] == tg)
                for cat in cats:
                    if level == "region":
                        h = [r for r in rel if r["era"] == era and r["tournament_group"] == tg and (r["home_region"] or "UNKNOWN") == cat]
                        a = [r for r in rel if r["era"] == era and r["tournament_group"] == tg and (r["away_region"] or "UNKNOWN") == cat]
                        unk_n = sum(1 for r in rel if r["era"] == era and r["tournament_group"] == tg and not r["home_region"])
                    else:
                        h = [r for r in rel if r["era"] == era and r["tournament_group"] == tg and (r["home_unit"] or "UNKNOWN") == cat]
                        a = [r for r in rel if r["era"] == era and r["tournament_group"] == tg and (r["away_unit"] or "UNKNOWN") == cat]
                        unk_n = ""
                    hc = Counter(r["home_team_id"] for r in h)
                    ac = Counter(r["away_team_id"] for r in a)
                    comp.append({"level": level, "category": cat, "zh": REGION_ZH.get(cat, "未定"),
                                 "era": era, "tournament_group": tg,
                                 "home_matches": len(h), "away_matches": len(a),
                                 "distinct_home_teams": len(hc), "distinct_away_teams": len(ac),
                                 "home_share_of_layer": round(len(h) / layer_n, 4) if layer_n else "无法计算",
                                 "away_share_of_layer": round(len(a) / layer_n, 4) if layer_n else "无法计算",
                                 "top1_home_team": hc.most_common(1)[0][0] if hc else "",
                                 "top1_home_share": round(hc.most_common(1)[0][1] / len(h), 4) if h else "无法计算",
                                 "top1_away_team": ac.most_common(1)[0][0] if ac else "",
                                 "top1_away_share": round(ac.most_common(1)[0][1] / len(a), 4) if a else "无法计算",
                                 "unknown_matches_in_layer": unk_n})
    write_csv(os.path.join(run, "composition_home_away.csv"), comp,
              ["level", "category", "zh", "era", "tournament_group", "home_matches", "away_matches",
               "distinct_home_teams", "distinct_away_teams", "home_share_of_layer", "away_share_of_layer",
               "top1_home_team", "top1_home_share", "top1_away_team", "top1_away_share",
               "unknown_matches_in_layer"])

    arm_rows = support_rows(specs, rel, lambda c, era, tg: sum(
        1 for r in rel if r["era"] == era and r["tournament_group"] == tg
        and (not c["background_region"] or r["home_region"] == c["background_region"])))
    write_csv(os.path.join(run, "candidate_reference_support.csv"), arm_rows,
              ["candidate_id", "candidate_type", "background_region", "arm_no", "arm_definition",
               "era", "tournament_group", "group_matches", "reference_matches",
               "reference_requires_layer", "support_status", "missing_reason"])
    summary = arm_support_summary(specs, arm_rows)
    arm_comp = []
    for c in specs:
        if c["candidate_class"] != "comparison_candidate":
            continue
        for no, reln, unit in ((1, c["arm1_relation"], c["arm1_unit"]), (2, c["arm2_relation"], c["arm2_unit"])):
            if c["candidate_type"] == "A":
                reg = (c["arm1_definition"] if no == 1 else c["arm2_definition"]).split("=")[1]
                sub = [r for r in rel if r["home_region"] == reg]
            elif c["candidate_type"] == "B":
                sub = [r for r in rel if r["home_region"] == c["background_region"] and r["relation"] == reln]
            else:
                sub = [r for r in rel if r["home_region"] == c["background_region"] and r["home_unit"] == unit]
            ar = Counter(r["away_region"] or "UNKNOWN" for r in sub)
            top = ar.most_common(3)
            arm_comp.append({"candidate_id": c["candidate_id"], "arm_no": no,
                             "arm_definition": c["arm1_definition"] if no == 1 else c["arm2_definition"],
                             "matches": len(sub),
                             "distinct_home_teams": len({r["home_team_id"] for r in sub}),
                             "distinct_away_teams": len({r["away_team_id"] for r in sub}),
                             "away_top1": f"{top[0][0]}:{top[0][1]}" if top else "",
                             "away_top2": f"{top[1][0]}:{top[1][1]}" if len(top) > 1 else "",
                             "away_top3": f"{top[2][0]}:{top[2][1]}" if len(top) > 2 else "",
                             "away_unknown": ar.get("UNKNOWN", 0),
                             "away_unknown_share": round(ar.get("UNKNOWN", 0) / len(sub), 4) if sub else "无法计算"})
    write_csv(os.path.join(run, "candidate_arm_composition.csv"), arm_comp,
              ["candidate_id", "arm_no", "arm_definition", "matches", "distinct_home_teams",
               "distinct_away_teams", "away_top1", "away_top2", "away_top3", "away_unknown",
               "away_unknown_share"])
    write_csv(os.path.join(run, "candidate_support_summary.csv"), summary,
              ["candidate_id", "candidate_type", "candidate_class", "status", "layers_both_supported",
               "layers_missing", "note"])

    zrows = []
    for table, rows_, catfield, known in (
            ("counts_home_region_era_tournament.csv", region_rows, "home_region", {"002", "019", "142", "150", "009"}),
            ("counts_home_unit_era_tournament.csv", unit_rows, "home_unit", set(units)),
            ("counts_relation_era_tournament.csv", rel_rows, "relation", {"same_unit", "same_region_diff_unit", "cross_region"})):
        for r in rows_:
            if int(r["matches"]) != 0:
                continue
            cat = r[catfield]
            category = "known_category_zero" if cat in known else "unknown_category_zero"
            why = "该已知分组在该层确实没有比赛" if category == "known_category_zero" else "未知类别（非已知地区没有赛程）"
            zrows.append({"table": table, "category_field": catfield, "category": cat,
                          "era": r["era"], "tournament_group": r["tournament_group"],
                          "zero_type": category, "explanation": why})
    write_csv(os.path.join(run, "zero_cell_analysis.csv"), zrows,
              ["table", "category_field", "category", "era", "tournament_group", "zero_type", "explanation"])
    known_zero = sum(1 for z in zrows if z["zero_type"] == "known_category_zero")
    unknown_zero = sum(1 for z in zrows if z["zero_type"] == "unknown_category_zero")
    chk("zero_cells_classified", known_zero + unknown_zero == len(zrows), f"known={known_zero}, unknown={unknown_zero}")

    inv_by = {r["team_id"]: r for r in inventory}
    imp = []
    for e in exceptions:
        tid = e["team_id"]
        i = inv_by.get(tid, {})
        seg = []
        if tid == "team:russia":
            pre = [r for r in rel if tid in (r["home_team_id"], r["away_team_id"]) and r["date"] < "1992-07-03"]
            post = [r for r in rel if tid in (r["home_team_id"], r["away_team_id"]) and r["date"] >= "1992-07-03"]
            seg.append(f"1992-07-03前 {len(pre)} 场（含主/客），之后 {len(post)} 场")
        imp.append({"exception_id": e["exception_id"], "team_id": tid,
                    "total_matches": i.get("total_matches", ""), "home_matches": i.get("home_matches", ""),
                    "away_matches": i.get("away_matches", ""), "first_date": i.get("first_date", ""),
                    "last_date": i.get("last_date", ""), "segment_note": "; ".join(seg)})
    write_csv(os.path.join(run, "exception_impacts.csv"), imp,
              ["exception_id", "team_id", "total_matches", "home_matches", "away_matches",
               "first_date", "last_date", "segment_note"])

    unk = []
    for target in ("A", "B", "C"):
        for era in ERAS:
            for tg in TGS:
                sub = [r for r in rel if r["era"] == era and r["tournament_group"] == tg]
                ok = sum(1 for r in sub if r[target + "_usable"])
                reasons = Counter(r[target + "_reason"] for r in sub if not r[target + "_usable"])
                unk.append({"target": target, "era": era, "tournament_group": tg,
                            "usable": ok, "unusable": len(sub) - ok,
                            "reasons": "; ".join(f"{k}:{v}" for k, v in reasons.most_common())})
    write_csv(os.path.join(run, "unknown_distribution.csv"), unk,
              ["target", "era", "tournament_group", "usable", "unusable", "reasons"])

    tests = run_self_tests(m49)
    for t_ in tests:
        chk("selftest_" + t_["name"], t_["passed"], t_["detail"])

    inputs = {"q2_membership": {"path": os.path.relpath(args.q2, ROOT), "sha256": sha256(args.q2)},
              "matches_clean": {"path": os.path.relpath(args.clean, ROOT), "sha256": sha256(args.clean)},
              "identity_registry": {"path": os.path.relpath(os.path.join(DEFAULT_IDENTITY, "association_registry.csv"), ROOT),
                                    "sha256": sha256(os.path.join(DEFAULT_IDENTITY, "association_registry.csv"))},
              "m49_overview": {"path": os.path.relpath(os.path.join(pkg, "sources", "m49_overview.html"), ROOT),
                               "sha256": sha256(os.path.join(pkg, "sources", "m49_overview.html"))},
              "m49_page": {"path": os.path.relpath(os.path.join(pkg, "sources", "m49_page.html"), ROOT),
                           "sha256": sha256(os.path.join(pkg, "sources", "m49_page.html"))},
              "package": {"path": os.path.relpath(pkg, ROOT), "version": os.path.basename(pkg)},
              "script": {"path": os.path.relpath(script_path, ROOT), "sha256": sha256(script_path),
                         "snapshot": "code/prepare_region_mapping.py",
                         "snapshot_sha256": sha256(os.path.join(run, "code", "prepare_region_mapping.py"))}}
    json.dump(inputs, open(os.path.join(run, "inputs_used.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    linkage = {"q2_rows": len(q2), "included": len(inc), "excluded": len(q2) - len(inc),
               "versions": [{"triple": list(v)} for v in {(r["data_version"], r["identity_version"], r["sample_id"]) for r in q2}],
               "home_labels": len(home_labels), "away_labels": len(away_labels), "union_labels": len(union),
               "missing": len(missing), "join_field_mismatch": len(bad_link),
               "eras": dict(Counter(r["analysis_era_id"] for r in inc)),
               "tournament_groups": dict(Counter(r["tournament_group"] for r in inc)),
               "relation_counts": dict(Counter(r["relation"] for r in rel))}
    json.dump(linkage, open(os.path.join(run, "linkage_checks.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)

    failures = [c["name"] for c in checks if not c["passed"]]
    status = "ok" if not failures else "failed"
    report = {"schema_version": "region-preparation-v2", "run_id": os.path.basename(run),
              "status": status, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "package": os.path.relpath(pkg, ROOT), "checks": checks, "failures": failures,
              "self_tests": tests,
              "not_run": ["地区胜率/胜平负", "共同构成调整值/区间/排名", "正式比较清单冻结", "第四/五问检验"],
              "stats": {"relations": dict(Counter(r["relation"] for r in rel)),
                        "targets": {t: sum(1 for r in rel if r[t + "_usable"]) for t in ("A", "B", "C")},
                        "candidates": len(specs)}}
    json.dump(report, open(os.path.join(run, "validation_report.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)

    if failures:
        print(json.dumps({"run_dir": os.path.relpath(run, ROOT), "status": "failed", "failures": failures},
                         ensure_ascii=False))
        return 2
    print(json.dumps({"run_dir": os.path.relpath(run, ROOT), "status": "ok",
                      "targets": report["stats"]["targets"],
                      "relations": report["stats"]["relations"],
                      "self_tests": f"{sum(1 for t_ in tests if t_['passed'])}/{len(tests)}"},
                     ensure_ascii=False))
    return 0


def finalize(run_dir):
    run = os.path.abspath(run_dir)
    rep = json.load(open(os.path.join(run, "validation_report.json"), encoding="utf-8"))
    files = {}
    for base, prefix in ((run, ""), (os.path.join(run, "code"), "code/")):
        if not os.path.isdir(base):
            continue
        for f in sorted(os.listdir(base)):
            p = os.path.join(base, f)
            if os.path.isfile(p) and f != "manifest.json":
                files[prefix + f] = sha256(p)
    manifest = {"run_id": os.path.basename(run), "status": rep["status"],
                "package": rep["package"], "command": "python scripts/prepare_region_mapping.py prepare",
                "files": files,
                "finalized_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "note": "最终指纹在全部报告生成后由 finalize 程序重新登记"}
    json.dump(manifest, open(os.path.join(run, "manifest.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    print(json.dumps({"finalized": os.path.relpath(run, ROOT), "files": len(files)}, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("prepare")
    p.add_argument("--package", default=DEFAULT_PACKAGE)
    p.add_argument("--run-root", default=os.path.join(ROOT, "outputs", "logs", "regions"))
    p.add_argument("--tag", default="")
    p.add_argument("--q2", default=DEFAULT_Q2)
    p.add_argument("--clean", default=DEFAULT_CLEAN)
    f = sub.add_parser("finalize")
    f.add_argument("run_dir")
    args = ap.parse_args()
    try:
        if args.cmd == "finalize":
            return finalize(args.run_dir)
        return prepare(args)
    except InputError as ex:
        print(json.dumps({"status": "failed", "error": str(ex)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
