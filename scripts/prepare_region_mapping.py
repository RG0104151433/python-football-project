#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第三问（地域差异）数据准备工具 v3。

只做资料整理、关联、计数、逐组支持与校验；不计算地区胜率/调整值/区间/排名。

用法（任意目录均可，路径全部显式）：
  python scripts/prepare_region_mapping.py prepare --root <repo> [--package ...] [--tag r1]
  python scripts/prepare_region_mapping.py replay --run outputs/logs/regions/<run> --tag replay
  python scripts/prepare_region_mapping.py finalize outputs/logs/regions/<run>
  python scripts/prepare_region_mapping.py selftest --root <repo> [--package ...]

v3 变更（对应审查 P1–P5）：
- P1: 六份关键包输入 + M49 快照 + 比赛/身份输入全部复制到 run/inputs/ 并登记 SHA，计算只读快照。
- P2: 新增 team_contributions.csv（候选×臂×年代×赛事×角色×球队，含分母与占比）。
- P3: 布尔严格规范化：只接受字面 true/false，其余立即失败；筛选与校验使用同一规则。
- P4: replay 子命令用原运行的代码快照与输入快照重放，写入新目录并比对核心 CSV。
- P5: 任何不合格输入/缺失关联/规则冲突 → 写 failure_report.json（结构化原因）并退出码 2，不生成成功 manifest。
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
import subprocess
import sys
import tempfile
import traceback
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

ROOT_DEFAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_REL = os.path.join("data", "external", "geography_preparation", "geo-prep-v3")
Q2_REL = os.path.join("outputs", "tables", "tournaments", "tournaments-4893e38db46f83f6c219",
                      "analysis_membership.csv")
CLEAN_REL = os.path.join("data", "processed", "prep-3fab808178cf8ad71d88", "matches_clean.csv")
IDENTITY_REL = os.path.join("data", "processed", "team_identity", "identity-reviewed-29d880765c1623764940")
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
IDENTITY_FILES = ["association_registry.csv", "historical_exceptions.json", "adopted_decisions.csv"]


class InputError(Exception):
    """输入/规则不合格；由上层写成结构化失败报告。"""

    def __init__(self, message, stage="", detail=None):
        super().__init__(message)
        self.stage = stage
        self.detail = detail or {}


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
            values = {k: r.get(k, "") for k in fields}
            w.writerow({k: str(v).lower() if isinstance(v, bool) else v
                        for k, v in values.items()})


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


# ---------------------------------------------------------------- boolean contract
def load_q2_rows(rows):
    """严格布尔：只接受字面 'true'/'false'（区分大小写、无空白）。"""
    bad = [r["included"] for r in rows if r["included"] not in ("true", "false")]
    if bad:
        raise InputError("included 含非规范布尔值（只允许字面 true/false）",
                         stage="load_q2", detail={"examples": sorted(set(bad))[:5], "count": len(bad)})
    vers = {(r["data_version"], r["identity_version"], r["sample_id"]) for r in rows}
    if len(vers) != 1:
        raise InputError("版本三元组不唯一", stage="load_q2", detail={"triples": [list(v) for v in sorted(vers)]})
    ids = [r["match_id"] for r in rows]
    if len(ids) != len(set(ids)):
        dup = [k for k, v in Counter(ids).items() if v > 1][:3]
        raise InputError("重复 match_id", stage="load_q2", detail={"duplicates": dup})
    return rows


def load_q2(path):
    return load_q2_rows(read_csv(path))


def select_included(rows):
    """筛选与校验使用同一严格规则，并核对无静默丢失。"""
    inc = [r for r in rows if r["included"] == "true"]
    exc = [r for r in rows if r["included"] == "false"]
    if len(inc) + len(exc) != len(rows):
        raise InputError("筛选后记录数不等于输入总数（存在静默丢失）", stage="select_included",
                         detail={"total": len(rows), "included": len(inc), "excluded": len(exc)})
    return inc, exc


def load_clean(path):
    rows = read_csv(path)
    ids = [r["match_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise InputError("清洗表存在重复 match_id", stage="load_clean")
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
                rules.append({"rule_id": f"GEO3-R{rid:03d}", "team_id": tid, "carrier_m49_code": code,
                              "carrier_kind": ck, "project_region_code": reg, "project_unit_code": unit,
                              "date_start": st, "date_end": en, "date_precision": "project_rule",
                              "status": status, "reason": why})
        else:
            area = m49["areas"].get(code)
            if area is None and code == "412":
                area = {"region_code": "150", "unit_code": "039"}
            if area is None:
                raise InputError("承载代码不在 M49 表中", stage="build_rules",
                                 detail={"team_id": tid, "code": code})
            rid += 1
            rules.append({"rule_id": f"GEO3-R{rid:03d}", "team_id": tid, "carrier_m49_code": code,
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
        raise InputError("同一球队同一日期命中多条规则（拒绝静默取舍）", stage="rule_for",
                         detail={"team_id": team_id, "date": day, "rules": [h["rule_id"] for h in hits]})
    if not hits:
        raise InputError("同一球队同一日期没有匹配规则", stage="rule_for",
                         detail={"team_id": team_id, "date": day})
    return hits[0]


def check_rule_parents(rules, m49):
    unit_region = {}
    for a in m49["areas"].values():
        if a["unit_code"]:
            unit_region[a["unit_code"]] = a["region_code"]
    unit_region["412"] = "150"
    problems = []
    for r in rules:
        if not r["project_unit_code"]:
            continue
        expect = unit_region.get(r["project_unit_code"], "")
        if expect != r["project_region_code"]:
            problems.append(f"{r['rule_id']}: 细区 {r['project_unit_code']} 所属大区 {expect} != 规则大区 {r['project_region_code']}")
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
    out = []
    for mid, day, ht, at in records:
        hr_, ar_ = rule_for(rules_by_team, ht, day), rule_for(rules_by_team, at, day)
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


# ---------------------------------------------------------------- support & contributions
def arm_filter(cand, arm_no, row):
    if cand["candidate_type"] == "A":
        reg = (cand["arm1_definition"] if arm_no == 1 else cand["arm2_definition"]).split("=")[1]
        return row["home_region"] == reg
    if cand["candidate_type"] == "B":
        relation = cand["arm1_relation"] if arm_no == 1 else cand["arm2_relation"]
        return row["home_region"] == cand["background_region"] and row["relation"] == relation
    unit = cand["arm1_unit"] if arm_no == 1 else cand["arm2_unit"]
    return row["home_region"] == cand["background_region"] and row["home_unit"] == unit


def support_rows(cands, rel_rows, layer_key):
    rows = []
    for c in cands:
        if c["candidate_class"] != "comparison_candidate":
            continue
        for no in (1, 2):
            for era in ERAS:
                for tg in TGS:
                    group_n = sum(1 for r in rel_rows if r["era"] == era and r["tournament_group"] == tg
                                  and arm_filter(c, no, r))
                    ref_n = layer_key(c, era, tg)
                    if ref_n == 0:
                        status, reason = "reference_layer_absent", "参考人群在该层无比赛（该层不在参考支持范围）"
                    elif group_n == 0:
                        status, reason = "group_missing_layer", "参考要求该层，但该比较组在该层无比赛：当前参考方案下不支持完整比较"
                    else:
                        status, reason = "supported", ""
                    rows.append({"candidate_id": c["candidate_id"], "candidate_type": c["candidate_type"],
                                 "background_region": c["background_region"], "arm_no": no,
                                 "arm_definition": c["arm1_definition"] if no == 1 else c["arm2_definition"],
                                 "era": era, "tournament_group": tg, "group_matches": group_n,
                                 "reference_matches": ref_n,
                                 "reference_requires_layer": "true" if ref_n > 0 else "false",
                                 "support_status": status, "missing_reason": reason})
    return rows


def contributions_rows(cands, rel_rows, labels):
    rows = []
    for c in cands:
        if c["candidate_class"] != "comparison_candidate":
            continue
        for no in (1, 2):
            arm_def = c["arm1_definition"] if no == 1 else c["arm2_definition"]
            for era in ERAS:
                for tg in TGS:
                    cell = [r for r in rel_rows if r["era"] == era and r["tournament_group"] == tg
                            and arm_filter(c, no, r)]
                    for role, key in (("home", "home_team_id"), ("away", "away_team_id")):
                        cnt = Counter(r[key] for r in cell)
                        denom = sum(cnt.values())
                        if denom == 0:
                            rows.append({"candidate_id": c["candidate_id"], "arm_no": no,
                                         "arm_definition": arm_def, "era": era, "tournament_group": tg,
                                         "role": role, "team_id": "__NONE__", "team_label": "",
                                         "matches": 0, "denominator": 0, "share": "无法计算"})
                            continue
                        for tid, n in sorted(cnt.items(), key=lambda x: (-x[1], x[0])):
                            rows.append({"candidate_id": c["candidate_id"], "arm_no": no,
                                         "arm_definition": arm_def, "era": era, "tournament_group": tg,
                                         "role": role, "team_id": tid, "team_label": labels.get(tid, ""),
                                         "matches": n, "denominator": denom, "share": round(n / denom, 6)})
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


# ---------------------------------------------------------------- snapshotting
def snapshot_inputs(run, sources):
    """复制全部输入到 run/inputs/，登记并复核 SHA；计算只读快照。"""
    manifest = {"schema_version": "region-inputs-v3", "items": {}}
    for role, src in sorted(sources.items()):
        if not os.path.exists(src):
            raise InputError("输入文件不存在", stage="snapshot_inputs", detail={"role": role, "path": src})
        if role.startswith("package_sources_"):
            folder = os.path.join(run, "inputs", "package", "sources")
        elif role.startswith("package_"):
            folder = os.path.join(run, "inputs", "package")
        else:
            folder = os.path.join(run, "inputs", "external")
        os.makedirs(folder, exist_ok=True)
        snap = os.path.join(folder, os.path.basename(src))
        shutil.copyfile(src, snap)
        h_src, h_snap = sha256(src), sha256(snap)
        if h_src != h_snap:
            raise InputError("快照复制后哈希不一致", stage="snapshot_inputs",
                             detail={"role": role, "source": h_src, "snapshot": h_snap})
        manifest["items"][role] = {"source_path": src, "snapshot_path": os.path.relpath(snap, run),
                                   "sha256": h_snap, "bytes": os.path.getsize(snap)}
    with open(os.path.join(run, "inputs", "inputs_manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return manifest


def snapshot_paths(run, manifest):
    return {role: os.path.join(run, item["snapshot_path"]) for role, item in manifest["items"].items()}


# ---------------------------------------------------------------- self tests
def run_self_tests(pkg, root):
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
                "u": [{"rule_id": "R4", "project_region_code": "", "project_unit_code": "",
                       "date_start": "1980-01-01", "date_end": "2024-12-31"}]}

    def row(mid, inc):
        return {"match_id": mid, "included": inc, "data_version": "d", "identity_version": "i", "sample_id": "s"}

    def strict_true_variants():
        for bad in ("True", " true", "true ", "TRUE"):
            try:
                load_q2_rows([row("m", bad)])
            except InputError:
                continue
            raise AssertionError(f"未拒绝变体 {bad!r}")

    def canonical_pass_and_no_drop():
        rows = [row("m1", "true"), row("m2", "false"), row("m3", "true")]
        load_q2_rows(rows)
        inc, exc = select_included(rows)
        assert len(inc) == 2 and len(exc) == 1 and len(inc) + len(exc) == 3

    def dup_test():
        try:
            load_q2_rows([row("m", "true"), row("m", "true")])
        except InputError:
            return
        raise AssertionError("重复ID未被拒绝")

    def ver_test():
        try:
            load_q2_rows([row("m1", "true"), {**row("m2", "true"), "identity_version": "i2"}])
        except InputError:
            return
        raise AssertionError("版本不一致未被拒绝")

    def swap_test():
        rows = process_relations([("m1", "2000-01-01", "a", "b")], fx_rules())
        rows2 = process_relations([("m1", "2000-01-01", "b", "a")], fx_rules())
        assert rows[0]["direction"] == "150>002" and rows2[0]["direction"] == "002>150"
        assert rows[0]["relation"] == rows2[0]["relation"] == "cross_region"

    def gap_test():
        rs = {"t": [{"rule_id": "1", "date_start": "1980-01-01", "date_end": "1990-12-31"},
                    {"rule_id": "2", "date_start": "1995-01-01", "date_end": "2024-12-31"}]}
        assert any("断档" in p for p in check_rule_series(rs))

    def overlap_test():
        rs = {"t": [{"rule_id": "1", "date_start": "1980-01-01", "date_end": "2000-12-31"},
                    {"rule_id": "2", "date_start": "1995-01-01", "date_end": "2024-12-31"}]}
        assert any("重叠" in p for p in check_rule_series(rs))

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

    def missing_rule_test():
        try:
            rule_for(fx_rules(), "a", "1979-01-01")
        except InputError:
            return
        raise AssertionError("缺少规则未被拒绝")

    def parent_test():
        m49 = parse_m49(os.path.join(pkg, "sources", "m49_overview.html"))
        bad = [{"rule_id": "X", "project_region_code": "002", "project_unit_code": "151"}]
        assert check_rule_parents(bad, m49), "父级不一致未被发现"

    def one_side_test():
        r = process_relations([("m2", "2000-01-01", "a", "u")], fx_rules())[0]
        assert r["A_usable"] and r["C_usable"] and not r["B_usable"] and r["relation"] == "unknown_region"

    def contributions_test():
        cands = [{"candidate_id": "X", "candidate_type": "A", "candidate_class": "comparison_candidate",
                  "background_region": "", "arm1_definition": "主队大区=150",
                  "arm2_definition": "主队大区=002", "arm1_relation": "", "arm2_relation": "",
                  "arm1_unit": "", "arm2_unit": ""}]
        rel = [{"home_region": "150", "home_unit": "151", "away_region": "002", "away_unit": "015",
                "relation": "cross_region", "era": "1980s", "tournament_group": "friendly",
                "home_team_id": "a", "away_team_id": "b"},
               {"home_region": "150", "home_unit": "151", "away_region": "150", "away_unit": "155",
                "relation": "same_region_diff_unit", "era": "1980s", "tournament_group": "friendly",
                "home_team_id": "a", "away_team_id": "c"}]
        rows = contributions_rows(cands, rel, {"a": "A", "b": "B", "c": "C"})
        arm1 = [r for r in rows if r["arm_no"] == 1 and r["role"] == "home"
                and r["era"] == "1980s" and r["tournament_group"] == "friendly"]
        assert sum(r["matches"] for r in arm1) == 2 and all(r["denominator"] == 2 for r in arm1)
        arm2 = [r for r in rows if r["arm_no"] == 2 and r["era"] == "1980s"
                and r["tournament_group"] == "friendly"]
        assert all(r["share"] == "无法计算" and r["denominator"] == 0 for r in arm2), arm2

    def support_missing_test():
        cands = [{"candidate_id": "X", "candidate_type": "B", "candidate_class": "comparison_candidate",
                  "background_region": "150", "arm1_definition": "主队大区=150 且 relation=cross_region",
                  "arm2_definition": "主队大区=150 且 relation=same_unit", "arm1_relation": "cross_region",
                  "arm2_relation": "same_unit", "arm1_unit": "", "arm2_unit": ""}]
        rel = [{"home_region": "150", "relation": "same_unit", "home_unit": "151", "era": "1980s",
                "tournament_group": "friendly", "home_team_id": "x", "away_team_id": "y", "away_region": "150"}]
        rows = support_rows(cands, rel, lambda c, e, t: 5 if (e, t) == ("1980s", "friendly") else 0)
        arm1 = [r for r in rows if r["arm_no"] == 1 and r["era"] == "1980s" and r["tournament_group"] == "friendly"][0]
        assert arm1["support_status"] == "group_missing_layer", arm1

    def failure_report_test():
        tmp = tempfile.mkdtemp(prefix="geo-failtest-")
        try:
            bad = os.path.join(tmp, "bad_q2.csv")
            with open(bad, "w", encoding="utf-8", newline="\n") as f:
                f.write("data_version,identity_version,sample_id,match_id,included\n")
                f.write("d,i,s,m1,True\n")
            out_root = os.path.join(tmp, "runs")
            cmd = [sys.executable, os.path.abspath(__file__), "prepare", "--root", root,
                   "--package", pkg, "--q2", bad,
                   "--clean", os.path.join(root, CLEAN_REL),
                   "--run-root", out_root, "--tag", "failtest"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            assert proc.returncode == 2, (proc.returncode, proc.stdout[-400:], proc.stderr[-400:])
            runs = [os.path.join(out_root, x) for x in os.listdir(out_root)] if os.path.isdir(out_root) else []
            assert runs, "未创建失败运行目录"
            fr = os.path.join(runs[0], "failure_report.json")
            assert os.path.exists(fr), "未写 failure_report.json"
            rep = json.load(open(fr, encoding="utf-8"))
            assert rep["status"] == "failed" and rep["error_type"], rep
            assert not os.path.exists(os.path.join(runs[0], "manifest.json")), "失败运行不应有 manifest"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    t("strict_boolean_rejects_variants", strict_true_variants)
    t("canonical_boolean_no_silent_drop", canonical_pass_and_no_drop)
    t("duplicate_match_id_rejected", dup_test)
    t("version_mismatch_rejected", ver_test)
    t("swap_direction_through_processor", swap_test)
    t("rule_middle_gap_detected", gap_test)
    t("rule_overlap_detected", overlap_test)
    t("multiple_rule_match_rejected", multi_rule_test)
    t("missing_rule_rejected", missing_rule_test)
    t("parent_mismatch_detected", parent_test)
    t("one_side_known_relation", one_side_test)
    t("contributions_reconcile_and_zero_denominator", contributions_test)
    t("reference_layer_missing_flagged", support_missing_test)
    t("failure_report_end_to_end", failure_report_test)
    return tests


# ---------------------------------------------------------------- core run
def run_core(run, snap, pkg_label, root, checks, stage_holder):
    def chk(name, ok, detail=""):
        checks.append({"name": name, "passed": bool(ok), "detail": str(detail)})

    stage_holder["stage"] = "load_inputs"
    q2 = load_q2(snap["q2_membership"])
    clean = load_clean(snap["matches_clean"])
    inc, exc = select_included(q2)
    chk("q2_rows_expected", len(q2) == EXPECTED["q2_rows"], len(q2))
    chk("included_expected", len(inc) == EXPECTED["included"], len(inc))
    chk("excluded_expected", len(exc) == EXPECTED["q2_rows"] - EXPECTED["included"], len(exc))
    missing = [r["match_id"] for r in inc if r["match_id"] not in clean]
    if missing:
        raise InputError("第二问纳入记录在清洗表中缺失（拒绝继续）", stage="join",
                         detail={"missing": len(missing), "examples": missing[:5]})
    bad_link = [r["match_id"] for r in inc if any(
        clean[r["match_id"]].get(field) != r.get(field)
        for field in ("date", "tournament_group", "source_record_id"))
        or ("data_version" in clean[r["match_id"]]
            and clean[r["match_id"]]["data_version"] != r.get("data_version"))]
    if bad_link:
        raise InputError("关联后字段不一致", stage="join", detail={"count": len(bad_link), "examples": bad_link[:5]})
    if not all(clean[r["match_id"]]["is_neutral"] == "false" for r in inc):
        raise InputError("样本含中立场比赛", stage="join")
    if not all(WINDOW_START <= r["date"] <= WINDOW_END for r in inc):
        raise InputError("样本日期越界", stage="join")

    stage_holder["stage"] = "load_package"
    m49 = parse_m49(snap["package_sources_m49_overview"])
    seed = read_csv(snap["package_seed"])
    carrier = {r["team_id"]: r for r in read_csv(snap["package_carrier"])}
    dictionary = read_csv(snap["package_dictionary"])
    specs = read_csv(snap["package_specs"])
    exceptions = read_csv(snap["package_exceptions"])
    chk("m49_areas_parsed", len(m49["areas"]) >= 240, len(m49["areas"]))
    known_codes = (set(m49["areas"]) | set(m49["nodes"]) | {"001", "412"}
                   | {r["area_code"] for r in dictionary if r["project_level"] == "rollup"})
    chk("dictionary_codes_known", {r["area_code"] for r in dictionary} <= known_codes)
    units = {r["area_code"]: r for r in dictionary if r["is_project_unit"] == "true"}
    chk("project_units_count", len(units) == 22, len(units))
    chk("project_units_parent_in_regions", all(r["project_parent_code"] in REGION_ZH for r in units.values()))
    chk("raw_parents_filled", all(r["raw_parent_code"] for r in dictionary
                                  if r["original_level"] in ("subregion", "intermediate")))
    chk("raw_parent_matches_m49", all(r["raw_parent_code"] == m49["parents"].get(r["area_code"], r["raw_parent_code"])
                                      for r in dictionary if r["original_level"] != "project_unit"))

    stage_holder["stage"] = "build_rules"
    rules = build_rules(seed, m49, carrier)
    rules_by_team = defaultdict(list)
    for r in rules:
        rules_by_team[r["team_id"]].append(r)
    chk("every_team_has_rule", set(rules_by_team) == {s["team_id"] for s in seed})
    ser = check_rule_series(rules_by_team)
    if ser:
        raise InputError("规则时间序列存在断档/重叠/覆盖缺口", stage="build_rules", detail={"problems": ser[:10]})
    par = check_rule_parents(rules, m49)
    if par:
        raise InputError("规则细区与所属大区不一致", stage="build_rules", detail={"problems": par[:10]})
    chk("carrier_kind_covered", all(r["team_id"] in carrier for r in rules))

    stage_holder["stage"] = "process_relations"
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

    stage_holder["stage"] = "inventory"
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
    labels = {r["team_id"]: r["current_label"] for r in inventory}
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

    stage_holder["stage"] = "counts"
    def cell_rows(keyfn, cats, extra):
        agg = defaultdict(lambda: {"n": 0, "teams": Counter()})
        for r in rel:
            k = (keyfn(r), r["era"], r["tournament_group"])
            agg[k]["n"] += 1
            agg[k]["teams"][r["home_team_id"]] += 1
        out = []
        for cat in cats:
            for era in ERAS:
                for tg in TGS:
                    c = agg.get((cat, era, tg), {"n": 0, "teams": Counter()})
                    top = c["teams"].most_common(1)
                    out.append({extra: cat, "zh": REGION_ZH.get(cat, "未定"), "era": era,
                                "tournament_group": tg, "matches": c["n"], "n_teams": len(c["teams"]),
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
    dm_rows = [{"home_region": a_, "away_region": b_, "matches": dm.get((a_, b_), 0)}
               for a_ in ["002", "019", "142", "150", "009", "UNKNOWN"]
               for b_ in ["002", "019", "142", "150", "009", "UNKNOWN"]]
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
                        a_ = [r for r in rel if r["era"] == era and r["tournament_group"] == tg and (r["away_region"] or "UNKNOWN") == cat]
                        unk_n = sum(1 for r in rel if r["era"] == era and r["tournament_group"] == tg and not r["home_region"])
                    else:
                        h = [r for r in rel if r["era"] == era and r["tournament_group"] == tg and (r["home_unit"] or "UNKNOWN") == cat]
                        a_ = [r for r in rel if r["era"] == era and r["tournament_group"] == tg and (r["away_unit"] or "UNKNOWN") == cat]
                        unk_n = ""
                    hc = Counter(r["home_team_id"] for r in h)
                    ac = Counter(r["away_team_id"] for r in a_)
                    comp.append({"level": level, "category": cat, "zh": REGION_ZH.get(cat, "未定"),
                                 "era": era, "tournament_group": tg,
                                 "home_matches": len(h), "away_matches": len(a_),
                                 "distinct_home_teams": len(hc), "distinct_away_teams": len(ac),
                                 "home_share_of_layer": round(len(h) / layer_n, 4) if layer_n else "无法计算",
                                 "away_share_of_layer": round(len(a_) / layer_n, 4) if layer_n else "无法计算",
                                 "top1_home_team": hc.most_common(1)[0][0] if hc else "",
                                 "top1_home_share": round(hc.most_common(1)[0][1] / len(h), 4) if h else "无法计算",
                                 "top1_away_team": ac.most_common(1)[0][0] if ac else "",
                                 "top1_away_share": round(ac.most_common(1)[0][1] / len(a_), 4) if a_ else "无法计算",
                                 "unknown_matches_in_layer": unk_n})
    write_csv(os.path.join(run, "composition_home_away.csv"), comp,
              ["level", "category", "zh", "era", "tournament_group", "home_matches", "away_matches",
               "distinct_home_teams", "distinct_away_teams", "home_share_of_layer", "away_share_of_layer",
               "top1_home_team", "top1_home_share", "top1_away_team", "top1_away_share",
               "unknown_matches_in_layer"])

    stage_holder["stage"] = "support"
    arm_rows = support_rows(specs, rel, lambda c, era, tg: sum(
        1 for r in rel if r["era"] == era and r["tournament_group"] == tg
        and (not c["background_region"] or r["home_region"] == c["background_region"])))
    write_csv(os.path.join(run, "candidate_reference_support.csv"), arm_rows,
              ["candidate_id", "candidate_type", "background_region", "arm_no", "arm_definition",
               "era", "tournament_group", "group_matches", "reference_matches",
               "reference_requires_layer", "support_status", "missing_reason"])
    summary = arm_support_summary(specs, arm_rows)
    write_csv(os.path.join(run, "candidate_support_summary.csv"), summary,
              ["candidate_id", "candidate_type", "candidate_class", "status", "layers_both_supported",
               "layers_missing", "note"])

    contrib = contributions_rows(specs, rel, labels)
    write_csv(os.path.join(run, "team_contributions.csv"), contrib,
              ["candidate_id", "arm_no", "arm_definition", "era", "tournament_group", "role",
               "team_id", "team_label", "matches", "denominator", "share"])
    bad = []
    keys = {(r["candidate_id"], r["arm_no"], r["era"], r["tournament_group"]) for r in contrib}
    for cid, no, era, tg in keys:
        for role in ("home", "away"):
            rows_ = [r for r in contrib if (r["candidate_id"], r["arm_no"], r["era"],
                                            r["tournament_group"], r["role"]) == (cid, no, era, tg, role)]
            total = sum(int(r["matches"]) for r in rows_)
            support_cell = [r for r in arm_rows if (r["candidate_id"], r["arm_no"],
                                                    r["era"], r["tournament_group"]) == (cid, no, era, tg)][0]
            if total != int(support_cell["group_matches"]):
                bad.append((cid, no, era, tg, role, total, support_cell["group_matches"]))
    chk("contributions_reconcile_to_arm_cells", not bad, str(bad[:5]))

    arm_comp = []
    for c in specs:
        if c["candidate_class"] != "comparison_candidate":
            continue
        for no in (1, 2):
            sub = [r for r in rel if arm_filter(c, no, r)]
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

    probes = [("PROBE-AF-CROSS-1980S-NF", "002", "cross_region", "1980s", "non_friendly"),
              ("PROBE-OC-SAMEUNIT-1980S-F", "009", "same_unit", "1980s", "friendly"),
              ("PROBE-OC-DIFFUNIT-2000S-F", "009", "same_region_diff_unit", "2000s", "friendly")]
    probe_rows = []
    for pid, reg, reln, era, tg in probes:
        g = sum(1 for r in rel if r["home_region"] == reg and r["relation"] == reln
                and r["era"] == era and r["tournament_group"] == tg)
        ref = sum(1 for r in rel if r["home_region"] == reg and r["era"] == era and r["tournament_group"] == tg)
        status = ("reference_layer_absent" if ref == 0 else
                  "group_missing_layer" if g == 0 else "supported")
        probe_rows.append({"probe_id": pid, "background_region": reg, "relation": reln, "era": era,
                           "tournament_group": tg, "group_matches": g, "reference_matches": ref,
                           "support_status": status, "expectation": "group_missing_layer"})
        chk("probe_" + pid.lower(), status == "group_missing_layer", f"group={g}, ref={ref}")
    write_csv(os.path.join(run, "coverage_probe_cases.csv"), probe_rows,
              ["probe_id", "background_region", "relation", "era", "tournament_group",
               "group_matches", "reference_matches", "support_status", "expectation"])

    stage_holder["stage"] = "aux"
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
            zrows.append({"table": table, "category_field": catfield, "category": cat, "era": r["era"],
                          "tournament_group": r["tournament_group"], "zero_type": category, "explanation": why})
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
        seg = ""
        if tid == "team:russia":
            pre = [r for r in rel if tid in (r["home_team_id"], r["away_team_id"]) and r["date"] < "1992-07-03"]
            post = [r for r in rel if tid in (r["home_team_id"], r["away_team_id"]) and r["date"] >= "1992-07-03"]
            seg = f"1992-07-03前 {len(pre)} 场（含主/客），之后 {len(post)} 场"
        imp.append({"exception_id": e["exception_id"], "team_id": tid,
                    "total_matches": i.get("total_matches", ""), "home_matches": i.get("home_matches", ""),
                    "away_matches": i.get("away_matches", ""), "first_date": i.get("first_date", ""),
                    "last_date": i.get("last_date", ""), "segment_note": seg})
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
                unk.append({"target": target, "era": era, "tournament_group": tg, "usable": ok,
                            "unusable": len(sub) - ok,
                            "reasons": "; ".join(f"{k}:{v}" for k, v in reasons.most_common())})
    write_csv(os.path.join(run, "unknown_distribution.csv"), unk,
              ["target", "era", "tournament_group", "usable", "unusable", "reasons"])

    stage_holder["stage"] = "selftest"
    tests = run_self_tests(snap["package_root"], root)
    for t_ in tests:
        chk("selftest_" + t_["name"], t_["passed"], t_["detail"])

    stage_holder["stage"] = "reports"
    linkage = {"q2_rows": len(q2), "included": len(inc), "excluded": len(exc),
               "versions": [{"triple": list(v)} for v in {(r["data_version"], r["identity_version"], r["sample_id"]) for r in q2}],
               "home_labels": len(home_labels), "away_labels": len(away_labels), "union_labels": len(union),
               "missing": 0, "join_field_mismatch": 0,
               "eras": dict(Counter(r["analysis_era_id"] for r in inc)),
               "tournament_groups": dict(Counter(r["tournament_group"] for r in inc)),
               "relation_counts": dict(Counter(r["relation"] for r in rel))}
    json.dump(linkage, open(os.path.join(run, "linkage_checks.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)

    failures = [c["name"] for c in checks if not c["passed"]]
    report = {"schema_version": "region-preparation-v3", "run_id": os.path.basename(run),
              "status": "ok" if not failures else "failed",
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "package": pkg_label, "checks": checks, "failures": failures, "self_tests": tests,
              "not_run": ["地区胜率/胜平负", "共同构成调整值/区间/排名", "正式比较清单冻结", "第四/五问检验"],
              "stats": {"relations": dict(Counter(r["relation"] for r in rel)),
                        "targets": {t: sum(1 for r in rel if r[t + "_usable"]) for t in ("A", "B", "C")},
                        "candidates": len(specs), "contribution_rows": len(contrib)}}
    json.dump(report, open(os.path.join(run, "validation_report.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    if failures:
        raise InputError("运行内检查失败", stage="checks", detail={"failures": failures})
    write_manifest(run, report)
    return report


def write_manifest(run, report):
    files = {}
    for base, prefix in ((run, ""), (os.path.join(run, "code"), "code/"),
                         (os.path.join(run, "inputs"), "inputs/")):
        if not os.path.isdir(base):
            continue
        for root_, _, fs in os.walk(base):
            for f in sorted(fs):
                p = os.path.join(root_, f)
                rel = os.path.relpath(p, base).replace(os.sep, "/")
                if prefix + rel == "manifest.json":
                    continue
                files[prefix + rel] = sha256(p)
    manifest = {"run_id": os.path.basename(run), "status": report["status"],
                "package": report["package"], "files": files,
                "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "note": "输入快照与代码快照均在本运行目录内；finalize 在补充 handoff/replay 后重算"}
    json.dump(manifest, open(os.path.join(run, "manifest.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)


def failure_report(run, stage, ex, checks):
    os.makedirs(run, exist_ok=True)
    payload = {"schema_version": "region-preparation-v3-failure", "status": "failed",
               "run_id": os.path.basename(run), "stage": stage,
               "error_type": type(ex).__name__, "message": str(ex),
               "detail": getattr(ex, "detail", {}) if isinstance(ex, InputError) else {},
               "checks_so_far": checks,
               "traceback_tail": traceback.format_exc().splitlines()[-8:],
               "failed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "note": "失败运行不生成 manifest/handoff，不得作为成功交接使用"}
    json.dump(payload, open(os.path.join(run, "failure_report.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- commands
def build_sources(pkg, q2, clean, identity):
    s = {"q2_membership": q2, "matches_clean": clean}
    for f in IDENTITY_FILES:
        s["identity_" + f.split(".")[0]] = os.path.join(identity, f)
    s["package_seed"] = os.path.join(pkg, "team_geography_seed.csv")
    s["package_carrier"] = os.path.join(pkg, "carrier_model.csv")
    s["package_dictionary"] = os.path.join(pkg, "region_dictionary.csv")
    s["package_specs"] = os.path.join(pkg, "candidate_specs.csv")
    s["package_exceptions"] = os.path.join(pkg, "exceptions.csv")
    s["package_sources"] = os.path.join(pkg, "sources.csv")
    s["package_sources_m49_page"] = os.path.join(pkg, "sources", "m49_page.html")
    s["package_sources_m49_overview"] = os.path.join(pkg, "sources", "m49_overview.html")
    return s


def prepare(args):
    root = os.path.abspath(args.root)
    pkg = os.path.abspath(args.package)
    script_path = os.path.abspath(__file__)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = f"-{args.tag}" if args.tag else ""
    run = os.path.join(os.path.abspath(args.run_root), f"preparation-{stamp}-{sha256(script_path)[:8]}{tag}")
    checks, stage = [], {"stage": "init"}
    try:
        os.makedirs(run, exist_ok=True)
        stage["stage"] = "code_snapshot"
        os.makedirs(os.path.join(run, "code"), exist_ok=True)
        shutil.copyfile(script_path, os.path.join(run, "code", "prepare_region_mapping.py"))
        stage["stage"] = "snapshot_inputs"
        sources = build_sources(pkg, args.q2, args.clean, args.identity)
        snapshot = snapshot_inputs(run, sources)
        snap = snapshot_paths(run, snapshot)
        snap["package_root"] = pkg
        stage["stage"] = "run_core"
        report = run_core(run, snap, os.path.relpath(pkg, root), root, checks, stage)
        print(json.dumps({"run_dir": os.path.relpath(run, root), "status": "ok",
                          "targets": report["stats"]["targets"],
                          "relations": report["stats"]["relations"],
                          "self_tests": f"{sum(1 for t_ in report['self_tests'] if t_['passed'])}/{len(report['self_tests'])}",
                          "contributions": report["stats"]["contribution_rows"]}, ensure_ascii=False))
        return 0
    except Exception as ex:  # noqa: BLE001
        failure_report(run, stage["stage"], ex, checks)
        print(json.dumps({"run_dir": os.path.relpath(run, root), "status": "failed",
                          "stage": stage["stage"], "error_type": type(ex).__name__,
                          "message": str(ex)}, ensure_ascii=False))
        return 2


def replay(args):
    root = os.path.abspath(args.root)
    orig = os.path.abspath(args.run)
    man_path = os.path.join(orig, "inputs", "inputs_manifest.json")
    if not os.path.exists(man_path):
        raise InputError("原运行缺少 inputs_manifest.json", stage="replay", detail={"run": orig})
    man = json.load(open(man_path, encoding="utf-8"))
    # A replay must use recorded bytes, including provenance-only inputs.
    for role, item in man["items"].items():
        snapshot = os.path.join(orig, item["snapshot_path"])
        if not os.path.isfile(snapshot) or sha256(snapshot) != item["sha256"]:
            raise InputError("输入快照与登记指纹不一致，拒绝重放", stage="replay",
                             detail={"role": role, "snapshot_path": item["snapshot_path"]})
    code_snapshot = os.path.join(orig, "code", "prepare_region_mapping.py")
    if not os.path.exists(code_snapshot):
        raise InputError("原运行缺少代码快照", stage="replay", detail={"run": orig})
    old_manifest_path = os.path.join(orig, "manifest.json")
    if os.path.exists(old_manifest_path):
        original_files = json.load(open(old_manifest_path, encoding="utf-8"))["files"]
        expected_inputs = original_files.get("inputs/inputs_manifest.json")
        if expected_inputs and sha256(man_path) != expected_inputs:
            raise InputError("输入清单与旧 manifest 不一致，拒绝重放", stage="replay")
        expected_code = original_files.get("code/prepare_region_mapping.py")
        if expected_code and sha256(code_snapshot) != expected_code:
            raise InputError("代码快照与旧 manifest 不一致", stage="replay", detail={"run": orig})
    snap = {role: os.path.join(orig, item["snapshot_path"]) for role, item in man["items"].items()}
    pkg_snap = os.path.join(orig, "inputs", "package")
    cmd = [sys.executable, code_snapshot, "prepare", "--root", root, "--package", pkg_snap,
           "--q2", snap["q2_membership"], "--clean", snap["matches_clean"],
           "--identity", os.path.join(orig, "inputs", "external"),
           "--run-root", os.path.abspath(args.run_root),
           "--tag", f"replay-{os.path.basename(orig).split('-')[-1]}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=1800)
    if proc.returncode != 0:
        raise InputError("重放运行失败", stage="replay",
                         detail={"returncode": proc.returncode, "stdout": proc.stdout[-800:]})
    line = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")][-1]
    new_run = os.path.join(root, json.loads(line)["run_dir"])
    same, diff = [], []
    for f in sorted(os.listdir(orig)):
        if not f.endswith(".csv"):
            continue
        a, b = os.path.join(orig, f), os.path.join(new_run, f)
        if os.path.exists(b) and sha256(a) == sha256(b):
            same.append(f)
        else:
            diff.append(f)
    res = {"schema_version": "region-replay-v3", "original_run": os.path.relpath(orig, root),
           "replay_run": os.path.relpath(new_run, root), "code_snapshot": "code/prepare_region_mapping.py",
           "code_snapshot_sha256": sha256(code_snapshot),
           "csv_checked": len(same) + len(diff), "csv_identical": len(same), "csv_diff": diff,
           "note": "重放使用原运行的代码快照与输入快照；新目录不覆盖原运行"}
    json.dump(res, open(os.path.join(new_run, "replay_check.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    rep = json.load(open(os.path.join(new_run, "validation_report.json"), encoding="utf-8"))
    write_manifest(new_run, rep)
    print(json.dumps({"original": os.path.relpath(orig, root), "replay": os.path.relpath(new_run, root),
                      "csv_identical": len(same), "csv_diff": diff}, ensure_ascii=False))
    return 0 if not diff else 3


def finalize(run_dir):
    run = os.path.abspath(run_dir)
    rep = json.load(open(os.path.join(run, "validation_report.json"), encoding="utf-8"))
    if rep.get("status") != "ok" or os.path.exists(os.path.join(run, "failure_report.json")):
        raise InputError("失败运行不能登记为成功交接", stage="finalize")
    write_manifest(run, rep)
    n = len(json.load(open(os.path.join(run, "manifest.json"), encoding="utf-8"))["files"])
    print(json.dumps({"finalized": run, "files": n}, ensure_ascii=False))
    return 0


def selftest(args):
    tests = run_self_tests(os.path.abspath(args.package), os.path.abspath(args.root))
    print(json.dumps({"tests": tests, "passed": sum(1 for t in tests if t["passed"]),
                      "total": len(tests)}, ensure_ascii=False, indent=1))
    return 0 if all(t["passed"] for t in tests) else 2


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("prepare")
    p.add_argument("--root", default=ROOT_DEFAULT)
    p.add_argument("--package", default=None)
    p.add_argument("--q2", default=None)
    p.add_argument("--clean", default=None)
    p.add_argument("--identity", default=None)
    p.add_argument("--run-root", default=None)
    p.add_argument("--tag", default="")
    r = sub.add_parser("replay")
    r.add_argument("--root", default=ROOT_DEFAULT)
    r.add_argument("--run", required=True)
    r.add_argument("--run-root", default=None)
    f = sub.add_parser("finalize")
    f.add_argument("run_dir")
    s = sub.add_parser("selftest")
    s.add_argument("--root", default=ROOT_DEFAULT)
    s.add_argument("--package", default=None)
    args = ap.parse_args()
    args.root = os.path.abspath(getattr(args, "root", ROOT_DEFAULT))
    if hasattr(args, "package"):
        args.package = os.path.abspath(args.package or os.path.join(args.root, PKG_REL))
        args.q2 = os.path.abspath(getattr(args, "q2", None) or os.path.join(args.root, Q2_REL))
        args.clean = os.path.abspath(getattr(args, "clean", None) or os.path.join(args.root, CLEAN_REL))
        args.identity = os.path.abspath(getattr(args, "identity", None) or os.path.join(args.root, IDENTITY_REL))
    args.run_root = os.path.abspath(getattr(args, "run_root", None) or os.path.join(args.root, "outputs", "logs", "regions"))
    try:
        if args.cmd == "finalize":
            return finalize(args.run_dir)
        if args.cmd == "replay":
            return replay(args)
        if args.cmd == "selftest":
            return selftest(args)
        return prepare(args)
    except InputError as ex:
        print(json.dumps({"status": "failed", "stage": ex.stage, "error_type": type(ex).__name__,
                          "message": str(ex), "detail": ex.detail}, ensure_ascii=False))
        return 2
    except Exception as ex:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error_type": type(ex).__name__,
                          "message": str(ex)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
