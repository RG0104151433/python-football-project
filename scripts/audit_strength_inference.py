"""Independent output/hash, algebra and simulation record audit; not coverage."""
from pathlib import Path
import argparse
import csv
import gzip
import io
import json
import sys
import numpy as np
from scipy.special import ndtr
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from src.data_contract import file_hash, write_json


def records(path):
    data = path.read_bytes()
    if path.suffix == ".gz": data = gzip.decompress(data)
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def audit(stage):
    pointer = json.loads((ROOT/"outputs/logs/strength_inference"/(stage+"_pointer.json")).read_text())
    folder = ROOT/pointer["directory"]; manifest = json.loads((folder/"manifest.json").read_text()); checks = []
    def check(name, ok): checks.append(dict(name=name, passed=bool(ok)))
    check("manifest_hash", file_hash(folder/"manifest.json") == pointer["manifest_sha256"])
    for name, digest in manifest["outputs"].items(): check("output:"+name, file_hash(folder/name) == digest)
    for group in ("inputs", "code"):
        for name, digest in manifest["identity"][group].items(): check(group+":"+name, file_hash(ROOT/name) == digest)
    protocol = json.loads((folder/"protocol.json").read_text())
    check("formal_application_blocked", not protocol["formal_application_allowed"] and not protocol["protocol_frozen"])
    if stage == "interface":
        r = json.loads((folder/"review.json").read_text()); check("interface_passed", r["passed"])
        for row in r["detail"]: check("independent_gate:"+row["name"], row["error"] <= row["limit"])
    else:
        r = json.loads((folder/"report.json").read_text()); check("not_admitted", not r["formal_inference_admitted"])
    if stage == "diagnostic":
        rr = records(folder/"diagnostic_ranges.csv"); check("216_diagnostics", len(rr) == 216)
        for row in rr:
            estimate, se, critical, lo, hi = [float(row[k]) for k in ("estimate_pp", "diagnostic_se_pp", "max_t_critical", "diagnostic_lower_pp", "diagnostic_upper_pp")]
            check("symmetric_range", abs((hi+lo)/2-estimate) < 3e-9 and abs((hi-lo)/2-critical*se) < 3e-8)
            check("not_confidence_interval", row["coverage_admitted"] == "false" and "NOT_CONFIDENCE_INTERVAL" in row["status"])
        draws = records(folder/"multiplier_draws.csv.gz"); check("3996_draws", len(draws) == 4*999)
        by_band = {}
        for row in draws: by_band.setdefault(int(row["bandwidth_days"]), []).append(row)
        ids = [name for name in draws[0] if name.startswith("S6:")]
        check("54_paired_target_columns", len(ids) == 54)
        for bandwidth, group in by_band.items():
            matrix = np.array([[float(row[k]) for k in ids] for row in group]); se = np.sqrt(np.sum((matrix-matrix.mean(axis=0))**2, axis=0)/(len(matrix)-1))
            ordered = sorted(np.max(abs(matrix/se), axis=1)); position = .95*(len(matrix)-1)
            left = int(position); critical = ordered[left]+(position-left)*(ordered[left+1]-ordered[left])
            for row in (record for record in rr if int(record["bandwidth_days"]) == bandwidth):
                j = ids.index(row["registry_id"]); check("independent_draw_sd", abs(se[j]-float(row["diagnostic_se_pp"])) < 2e-8)
            check("max_t_quantile", abs(critical-float(next(row["max_t_critical"] for row in rr if int(row["bandwidth_days"]) == bandwidth))) < 2e-8)
    if stage == "pilot":
        pp = records(folder/"world_probabilities.csv.gz"); scores = records(folder/"world_score_marginals.csv.gz"); estimates = records(folder/"world_estimates.csv")
        check("two_worlds", r["world_count"] == 2); check("full_learning_probability_rows", len(pp) == 77838 and len(scores) == 49834)
        check("auxiliary_probability_rows", sum(row["auxiliary_learning"] == "true" for row in pp) == 28004)
        check("108_target_rows", len(estimates) == 108)
        for row in pp:
            p = [float(row[k]) for k in ("true_home_probability", "true_draw_probability", "true_away_probability")]
            check("WDL", min(p) > 0 and abs(sum(p)-1) < 3e-10)
        for row in scores:
            v, base, nh, na, sd = [float(row[k]) for k in ("strength_difference_variance", "strength_difference_base_variance", "home_jump_intensity", "away_jump_intensity", "jump_scale_sd")]
            check("variance_decomposition", base > 0 and abs(v-base-(nh+na)*sd**2) < 4e-9)
            check("past_only", row["prediction_cutoff"] < row["date"])
        for row in estimates:
            level = row["axis"] == "level"
            check("no_fake_paired_truth", bool(row["known_M3_truth_pp"]) == level and row["coverage_admitted"] == "false")
            if level: check("M3_error_arithmetic", abs(float(row["estimate_pp"])-float(row["known_M3_truth_pp"])-float(row["known_M3_error_pp"])) < 3e-9)
        for w in r["worlds"]:
            check("full_learning", w["learning_matches"] == 38919 and w["study_matches"] == 24917)
            check("same_day_query", w["max_query_error"] < 2e-8 and w["all_same_day_generated_before_update"])
    result = dict(passed=all(c["passed"] for c in checks), checks=len(checks), failed=[c["name"] for c in checks if not c["passed"]],
        stage=stage, directory=pointer["directory"], formal_inference_admitted=False, human_review=False)
    write_json(ROOT/"outputs/logs/strength_inference"/(stage+"_audit.json"), result)
    print(json.dumps(result), flush=True)
    if not result["passed"]: raise SystemExit(1)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--stage", choices=["interface", "diagnostic", "pilot"], required=True)
    audit(p.parse_args().stage)
