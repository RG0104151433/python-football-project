# -*- coding: utf-8 -*-
"""Mechanical delivery checks for batch 20261024-batch03.
Re-runnable by the mainline. Writes validation_report.json next to itself.
Content/fact checks (historical semantics) are NOT covered here; see README."""
import csv, json, hashlib, os, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
B = HERE
B1 = os.path.join(ROOT, "data/external/team_identity/submissions/20261024-batch01")
B2 = os.path.join(ROOT, "data/external/team_identity/submissions/20261024-batch02")
TASKS = os.path.join(ROOT, "outputs/logs/team_identity/evidence-and-reference-audit-20261024/evidence_tasks.csv")
IDENT = os.path.join(ROOT, "data/processed/team_identity/identity-fifa-f4b591a95719b634d9de/match_identity.csv")
FIFA_PDF = os.path.join(ROOT, "参考资料/数据来源/FIFA/FIFA_Financial_Report_2018.pdf")

report = {"schema_version": "membership-batch-validation-v1",
          "batch": "20261024-batch03", "run_at": None, "timezone": "UTC+08:00 (Asia/Shanghai, local machine)",
          "inputs": {}, "checks": [], "failures": [], "not_run": []}

def check(name, ok, detail=""):
    report["checks"].append({"name": name, "passed": bool(ok), "detail": detail})
    if not ok:
        report["failures"].append({"name": name, "detail": detail})
    return ok

def jload(p):
    raw = open(p, "rb").read()
    assert b"\r" not in raw, "CR found in " + p
    return [json.loads(l) for l in raw.decode("utf-8").rstrip("\n").split("\n")], raw

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

report["run_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

try:
    tasks = list(csv.DictReader(open(TASKS, encoding="utf-8-sig")))
    ident = list(csv.DictReader(open(IDENT, encoding="utf-8-sig")))
    report["inputs"] = {"evidence_tasks_rows": len(tasks), "match_identity_rows": len(ident),
                        "evidence_tasks_sha256": sha(TASKS), "match_identity_sha256": sha(IDENT)}
    dates = {r["match_id"]: r["date"] for r in ident}
    tm = {(t["source_team_id"], t["pending_status"]): json.loads(t["match_ids"]) for t in tasks}
    tlabel = {t["source_team_id"]: t["source_team_label"] for t in tasks}

    ev, _ = jload(os.path.join(B, "evidence.jsonl"))
    cl, _ = jload(os.path.join(B, "claims.jsonl"))
    ca, _ = jload(os.path.join(B, "case_assessments.jsonl"))
    sl, _ = jload(os.path.join(B, "search_log.jsonl"))
    co, _ = jload(os.path.join(B, "corrections.jsonl"))
    cov = list(csv.DictReader(open(os.path.join(B, "task_coverage.csv"), encoding="utf-8")))
    cl1, _ = jload(os.path.join(B1, "claims.jsonl")); ca1, _ = jload(os.path.join(B1, "case_assessments.jsonl"))
    cl2, _ = jload(os.path.join(B2, "claims.jsonl")); ca2, _ = jload(os.path.join(B2, "case_assessments.jsonl"))

    report["row_counts"] = {"evidence": len(ev), "claims": len(cl), "case_assessments": len(ca),
                            "search_log": len(sl), "corrections": len(co), "task_coverage": len(cov)}

    eids = [e["evidence_id"] for e in ev]; cids = [c["claim_id"] for c in cl]
    aids = [a["assessment_id"] for a in ca]; sids = [s["search_id"] for s in sl]; xids = [x["correction_id"] for x in co]
    check("id_unique_evidence", len(eids) == len(set(eids)))
    check("id_unique_claims", len(cids) == len(set(cids)))
    check("id_unique_assessments", len(aids) == len(set(aids)))
    check("id_unique_search", len(sids) == len(set(sids)))
    check("id_unique_corrections", len(xids) == len(set(xids)))
    check("batch_prefix_consistent", all(i.startswith("AGB3-") for i in eids + cids + aids + sids + xids))

    eset, cset = set(eids), set(cids)
    check("claims_ref_evidence", all(set(c["evidence_ids"]) <= eset for c in cl),
          str([c["claim_id"] for c in cl if not set(c["evidence_ids"]) <= eset]))
    check("claims_locators_keys_match", all(set(c["evidence_ids"]) == set(c["evidence_locators"].keys()) for c in cl))
    check("assess_ref_claims_evidence", all(set(a["claim_ids"]) <= cset and set(a["evidence_ids"]) <= eset for a in ca))
    withdrawn = {"AGB3-C006", "AGB3-C014", "AGB2-C006", "AGB2-C014"}
    check("withdrawn_claims_absent", not (withdrawn & cset))
    check("assess_do_not_cite_withdrawn", all(not (withdrawn & set(a["claim_ids"])) for a in ca))

    # match membership / labels / non-empty
    bad = []
    for a in ca:
        key = (a["source_team_id"], a["original_pending_status"])
        if key not in tm: bad.append((a["assessment_id"], "key"))
        elif not a["match_ids"]: bad.append((a["assessment_id"], "empty"))
        elif any(m not in tm[key] for m in a["match_ids"]): bad.append((a["assessment_id"], "foreign_match"))
        elif a["source_team_label"] != tlabel[a["source_team_id"]]: bad.append((a["assessment_id"], "label"))
    check("assess_match_membership_nonempty_labels", not bad, str(bad))
    check("no_german_dr_label_regression", all(a["source_team_label"] != "German-dr" for a in ca))
    gdr = [c for c in cl if c["claim_id"] == "AGB3-C008"]
    check("gdr_exit_no_fake_precision", bool(gdr) and gdr[0]["event_date"] is None and gdr[0]["date_bounds"]["earliest"] is None and gdr[0]["date_bounds"]["latest"] is None)
    mkd = [c for c in cl if c["claim_id"] == "AGB3-C019"]
    check("mkd_year_only", bool(mkd) and mkd[0]["event_date"] is None and mkd[0]["date_precision"] == "year")
    eps = [a for a in ca if a["assessment_id"] in ("AGB3-A008", "AGB3-A009", "AGB3-A012")]
    check("baltic_1991_not_nonmember", all(a["proposed_membership"] == "unresolved" for a in eps))
    c15 = [c for c in cl if c["claim_id"] == "AGB3-C015"]
    check("c015_no_asserted_date", bool(c15) and c15[0]["event_date"] is None and c15[0]["date_precision"] == "unknown")
    pre = [a for a in ca if a["assessment_id"] in ("AGB3-A002","AGB3-A010","AGB3-A013","AGB3-A016","AGB3-A035","AGB3-A040")]
    check("pre_admission_rows_unresolved", all(a["proposed_membership"] == "unresolved" for a in pre))
    check("corrections_single_old_id", all("," not in x["previous_id"] and "all rows" not in x["previous_id"] for x in co))

    # corrections traceability
    cl2ids = {c["claim_id"] for c in cl2}; ca2ids = {a["assessment_id"] for a in ca2}
    bad = []
    for x in co:
        pid = x["previous_id"]
        if pid not in cl2ids and pid not in ca2ids: bad.append((x["correction_id"], pid))
        for rid in x["replacement_ids"]:
            if rid not in cset and rid not in set(aids): bad.append((x["correction_id"], rid))
    check("corrections_previous_and_replacement_ids_exist", not bad, str(bad))
    expected_revised = {x["previous_id"] for x in co if x["action"] in ("replace", "withdraw")}
    check("corrections_count_23", len(co) == 23, f"got {len(co)}")

    # coverage table
    check("coverage_148_rows", len(cov) == 148)
    ckeys = [(r["source_team_id"], r["pending_status"]) for r in cov]
    check("coverage_keys_match_input", set(ckeys) == set(tm) and len(ckeys) == 148)
    bad = []
    for r in cov:
        k = (r["source_team_id"], r["pending_status"])
        cur = json.loads(r["current_assessment_ids"]); prev = json.loads(r["previous_assessment_ids"])
        if any(x not in set(aids) for x in cur): bad.append((k, "cur"))
        if any(x not in ca2ids for x in prev): bad.append((k, "prev"))
        if cur:
            got = set()
            for a in ca:
                if (a["source_team_id"], a["original_pending_status"]) == k: got |= set(a["match_ids"])
            if int(r["covered_match_count"]) != len(got) or int(r["remaining_match_count"]) != len(set(tm[k]) - got):
                bad.append((k, "counts"))
        else:
            if r["work_status"] != "not_reviewed" or r["resolution_status"] != "not_reviewed": bad.append((k, "status"))
    check("coverage_ids_and_counts_consistent", not bad, str(bad[:6]))

    # distinct match suggestion stats
    mm = {}
    for a in ca:
        for m in a["match_ids"]: mm.setdefault(m, set()).add(a["proposed_membership"])
    stats = {"distinct_matches_with_suggestions": len(mm),
             "member_only": sum(1 for v in mm.values() if v == {"member"}),
             "non_member_only": sum(1 for v in mm.values() if v == {"non_member"}),
             "differing_proposals": sum(1 for v in mm.values() if len(v) > 1),
             "proposals": {p: sum(1 for a in ca if a["proposed_membership"] == p) for p in ("member","non_member","unresolved","conflict")},
             "task_status_rows": {p: sum(1 for a in ca if a["task_status"] == p) for p in ("resolved","partial","not_found","conflict","not_reviewed")},
             "resolution_rollup": {r: sum(1 for x in cov if x["resolution_status"] == r) for r in ("resolved","partial","conflict","not_found","not_reviewed")},
             "work_rollup": {r: sum(1 for x in cov if x["work_status"] == r) for r in ("not_reviewed","reviewed_no_new_evidence","revised","new_evidence")}}
    report["stats"] = stats
    check("no_row_claiming_resolved", stats["task_status_rows"]["resolved"] == 0 and stats["resolution_rollup"]["resolved"] == 0)

    # local evidence hashes
    bad = []
    for e in ev:
        if e["local_path"]:
            p = os.path.join(ROOT, e["local_path"])
            if not os.path.exists(p): bad.append((e["evidence_id"], "missing"))
            elif sha(p) != e["sha256"]: bad.append((e["evidence_id"], "hash_mismatch"))
        else:
            if e["sha256"]: bad.append((e["evidence_id"], "hash_without_file"))
    check("local_evidence_hashes", not bad, str(bad))
    report["local_evidence"] = [{"evidence_id": e["evidence_id"], "reused": bool(e["reused_from_batch"]),
                                 "authority": e["authority"], "access_status": e["access_status"],
                                 "local_path": e["local_path"], "sha256_ok": (sha(os.path.join(ROOT, e["local_path"])) == e["sha256"]) if e["local_path"] else None} for e in ev]

    # production protection
    prot = {"match_identity.csv": sha(IDENT),
            "FIFA_Financial_Report_2018.pdf": sha(FIFA_PDF),
            "evidence_tasks.csv": sha(TASKS)}
    rev2 = json.load(open(os.path.join(ROOT, "outputs/logs/team_identity/batch-review-20261024-batch02/review.json"), encoding="utf-8"))
    b2hashes = rev2.get("submission_hashes", {})
    mism = []
    for rel, h in b2hashes.items():
        p = os.path.join(ROOT, rel)
        if os.path.exists(p) and sha(p) != h: mism.append(rel)
    check("batch02_files_unchanged_vs_review", not mism, str(mism))
    rev1 = json.load(open(os.path.join(ROOT, "outputs/logs/team_identity/batch-review-20261024-batch01/review.json"), encoding="utf-8"))
    b1hashes = rev1.get("submission_hashes", {})
    mism = []
    for rel, h in b1hashes.items():
        p = os.path.join(ROOT, rel)
        if os.path.exists(p) and sha(p) != h: mism.append(rel)
    check("batch01_files_unchanged_vs_review", not mism, str(mism))
    report["production_fingerprints"] = prot
    report["previous_batch_protection"] = {"batch01_files_checked": len(b1hashes), "batch02_files_checked": len(b2hashes)}
except Exception as ex:
    report["failures"].append({"name": "unexpected_exception", "detail": repr(ex)})

report["not_run"] = [
 "内容/史实复查（日期语义、临时会员与批准关系、来源权威性判断）属人工或内容审查，不在本程序范围；见README内容审查节",
 "未运行生产构建、会员发布、第一问重算或pytest",
 "未独立复得UPI在线全文、wayback存档或FIFA大会原件（网络受限，见search_log）",
]
with open(os.path.join(B, "validation_report.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print("checks:", len(report["checks"]), "failures:", len(report["failures"]))
for f_ in report["failures"]: print("FAIL:", f_)
