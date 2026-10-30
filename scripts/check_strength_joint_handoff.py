"""Independent overlap membership, subset contrasts and final documentation QA."""
from pathlib import Path
from collections import Counter, defaultdict
import json
import re
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_contract import file_hash, fingerprint, write_json
from src.strength.io import read_rows
from src.strength_joint.design import Design
from src.strength_joint.model import predict


def run():
    log = ROOT / "outputs/logs/strength_joint"
    pointer = json.loads((log / "analysis_pointer.json").read_text())
    folder = ROOT / pointer["directory"]
    manifest = json.loads((folder / "manifest.json").read_text()); cfg = manifest["identity"]["protocol"]
    rows = read_rows(ROOT / cfg["input"] / "analysis_matches.csv")
    models = json.loads((folder / "models.json").read_text()); design = Design(rows)
    geography = json.loads((ROOT / cfg["regions_config"]).read_text(encoding="utf-8-sig"))
    targets = [r for r in read_rows(ROOT / cfg["targets"]) if r["family"] == "CORE"]
    saved = {(r["target_id"], r["reference_kind"], r["model_id"]): r for r in read_rows(folder / "contrasts.csv")}
    parents = {r[side + "_unit"]: r[side + "_region"] for r in rows for side in ("home", "away")}
    counts = Counter(); ranges = defaultdict(list); failed = []; checks = 0
    def check(label, ok):
        nonlocal checks
        checks += 1
        if not ok:
            failed.append(label)
    def key(r):
        return (r["era"], r["tournament_group"], r["home_region"], r["home_unit"], r["away_region"],
                sum(float(r["strength_difference"]) >= b for b in cfg["support_bins"]))
    for r in rows:
        k = key(r); counts[k] += 1; ranges[k[:-1]].append(float(r["strength_difference"]))
    bounds = {k: (min(v), max(v)) for k, v in ranges.items()}
    def matches(r, g):
        fields = (("home_regions", "home_region"), ("home_units", "home_unit"), ("away_regions", "away_region"), ("away_units", "away_unit"))
        if any(g.get(a) and r[b] not in g[a] for a, b in fields):
            return False
        rel = "unknown" if not r["home_region"] or not r["away_region"] else "cross_region" if r["home_region"] != r["away_region"] else "same_unit" if r["home_unit"] == r["away_unit"] else "same_region_other_unit"
        return not g.get("relations") or rel in g["relations"]
    def scenarios(t, base):
        tid = t["target_id"]
        if tid.startswith("Q1:"):
            era = "2010s" if "2010s_minus" in tid else "2020_2024"
            return base, [[(1., [dict(r, era=e) for r in base])] for e in (era, "1980s")], "all24917_equal"
        if tid.startswith("Q2:"):
            return base, [[(1., [dict(r, tournament_group=s) for r in base])] for s in ("friendly", "non_friendly")], "all24917_equal"
        comp = next(c for c in geography["comparisons"] if c["id"] == t["source_row_key"])
        groups = [geography["groups"][comp[k]] for k in ("arm1", "arm2")]
        if comp["id"].startswith("B_"):
            group = geography["groups"][comp["reference_group"]]
            reference = [r for r in base if matches(r, group) and r["home_unit"] and r["away_unit"]]
            arms = []
            for group in groups:
                pieces = []
                for hu, n in sorted(Counter(r["home_unit"] for r in reference).items()):
                    rr = [r for r in reference if r["home_unit"] == hu]
                    cc = Counter(r["away_unit"] for r in rows if r["home_unit"] == hu and matches(r, group) and r["away_unit"])
                    for au, count in sorted(cc.items()):
                        pieces.append((n / len(reference) * count / sum(cc.values()), [dict(r, away_unit=au, away_region=parents[au]) for r in rr]))
                arms.append(pieces)
            return reference, arms, "parent_home_equal:" + comp["id"]
        arms = []
        for group in groups:
            cc = Counter(r["home_unit"] for r in rows if matches(r, group))
            arms.append([(n / sum(cc.values()), [dict(r, home_unit=u, home_region=parents[u]) for r in base]) for u, n in sorted(cc.items())])
        return base, arms, "all24917_equal"
    for target in targets:
        reference, arms, rule = scenarios(target, rows)
        bad = set()
        for arm in arms:
            for _, scenario in arm:
                for r in scenario:
                    k = key(r); lo, hi = bounds.get(k[:-1], (float("inf"), -float("inf")))
                    if not counts[k] or not lo <= float(r["strength_difference"]) <= hi:
                        bad.add(r["match_id"])
        kept = [r for r in reference if r["match_id"] not in bad]
        if kept:
            rr, aa, rule = scenarios(target, kept)
        else:
            rr, aa = [], None
        refid = "reference-" + fingerprint(dict(rule=rule, kind="cell_range_overlap", rows=[
            (r["match_id"], r["strength_difference"], r["strength_difference_base_variance"], r["home_jump_intensity"], r["away_jump_intensity"], r["jump_scale_sd"]) for r in rr]))[:20]
        for model in ("M0_nested", "M3_nested"):
            saved_row = saved[target["target_id"], "cell_range_overlap", model]
            check("overlap_reference:" + target["target_id"] + model, saved_row["reference_id"] == refid and int(saved_row["reference_rows"]) == len(rr))
            if aa is not None:
                probabilities = [sum(w * float(predict(models[model], rs, design).mean()) for w, rs in arm) for arm in aa]
                check("overlap_value:" + target["target_id"] + model, max(abs(probabilities[j] - float(saved_row[f"arm{j+1}_probability"])) for j in range(2)) < 2e-8)
        print("JOINT_OVERLAP_REVIEW", target["target_id"], len(rr), flush=True)
    audit = json.loads((log / (folder.name + "-audit.json")).read_text()); check("independent_audit", audit["passed"])
    repeated = json.loads((log / "reproducibility.json").read_text()); check("core_repeated", repeated["passed"] and repeated["original"] == pointer["directory"])
    global_report = json.loads((log / "global_feedback.json").read_text())
    check("global_feedback", global_report["all_engineering_checks_passed"] and len(global_report["reports"]) == 2 and not global_report["confidence_interval_coverage_admitted"])
    material_pointer = json.loads((log / "materials_pointer.json").read_text()); material = ROOT / material_pointer["directory"]
    material_manifest = json.loads((material / "manifest.json").read_text())
    for name, digest in material_manifest["outputs"].items():
        check("material_hash:" + name, file_hash(material / name) == digest)
    docs = ["README.md", "研究/README.md", "研究/05_赛前实力/README.md", "研究/05_赛前实力/实力评估_逻辑与运行说明.md",
            "研究/05_赛前实力/第三环节_联合分析准备与接口.md", "研究/05_赛前实力/第三环节_运行结果与交接.md", "文档/05_团队协作/论文与汇报支撑材料索引.md"]
    for name in docs:
        p = ROOT / name
        for link in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8-sig")):
            if "://" in link or link.startswith(("#", "mailto:")):
                continue
            target = link.split("#", 1)[0].strip("<>")
            if target:
                check("link:" + name + ":" + target, (p.parent / target).resolve().exists())
    state = json.loads((ROOT / "研究/pipeline_state.json").read_text(encoding="utf-8"))["question_5"]["joint_analysis"]
    check("pipeline_binding", state["directory"] == pointer["directory"] and state["joint_fit_performed"] and not state["inference_admitted"])
    result = dict(passed=not failed, checks=checks, failed=failed, original_input_ids=24917,
        independent_overlap_membership_targets=32, subset_probabilities_checked_with_previously_independently_audited_kernel=True,
        independent_probability_audit_checks=audit["checks"], repeated_files=repeated["identical_core_files"],
        point_analysis_completed=True, statistical_inference_admitted=False, human_review=False)
    write_json(log / "handoff_review.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
