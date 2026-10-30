"""Independent coefficient/probability and contrast reconstruction (not model.py)."""
from pathlib import Path
from collections import Counter
import argparse
import json
import math
import sys
import numpy as np
from scipy.special import ndtr
from scipy.stats import poisson

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_contract import file_hash, write_json
from src.strength.io import read_rows


def run(directory):
    folder = ROOT / directory
    manifest = json.loads((folder / "manifest.json").read_text())
    cfg = manifest["identity"]["protocol"]
    failures = []; checks = 0
    def check(label, yes):
        nonlocal checks
        checks += 1
        if not yes:
            failures.append(label)
    for name, digest in manifest["outputs"].items():
        check("hash:" + name, file_hash(folder / name) == digest)
    for name, digest in manifest["identity"]["inputs"].items():
        check("input_hash:" + name, file_hash(ROOT / name) == digest)
    rows = read_rows(ROOT / cfg["input"] / "analysis_matches.csv")
    predictions = read_rows(folder / "joint_predictions.csv")
    models = json.loads((folder / "models.json").read_text())
    check("24917IDs", len(predictions) == 24917 and [r["match_id"] for r in predictions] == [r["match_id"] for r in rows])
    counts = {side: Counter((r[side + "_region"], r[side + "_unit"]) for r in rows) for side in ("home", "away")}
    parents = {r[s + "_unit"]: r[s + "_region"] for r in rows for s in ("home", "away")}
    def probability(rs, model):
        result = models[model]; coefficients = dict(zip(result["names"] + result["slope_names"], result["theta"]))
        eta = np.zeros(len(rs))
        for name in result["names"]:
            if name == "intercept":
                value = np.ones(len(rs))
            elif name.startswith("era:"):
                value = np.array([r["era"] == name.split(":")[1] for r in rs])
            elif name == "friendly":
                value = np.array([r["tournament_group"] == "friendly" for r in rs])
            elif ":region:" in name:
                side, _, region = name.split(":"); region = "" if region == "unknown" else region
                value = np.array([r[side + "_region"] == region for r in rs])
            elif ":within:" in name:
                side, _, unit = name.split(":"); region = parents[unit]
                cc = counts[side]; units = [u for (g, u) in cc if g == region]
                anchor = max(units, key=lambda u: (cc[region, u], u))
                value = np.array([float(r[side + "_unit"] == unit) - cc[region, unit] / cc[region, anchor] * (r[side + "_unit"] == anchor)
                                  if r[side + "_region"] == region else 0. for r in rs])
            elif name == "same_region":
                value = np.array([bool(r["home_region"]) and r["home_region"] == r["away_region"] for r in rs])
            elif name == "same_unit":
                value = np.array([bool(r["home_region"]) and r["home_region"] == r["away_region"] and r["home_unit"] == r["away_unit"] for r in rs])
            else:
                raise ValueError("Unknown coefficient " + name)
            eta += coefficients[name] * value
        if not result["slope_names"]:
            return ndtr(eta)
        b = np.array([math.exp(coefficients["log_b_friendly"] if r["tournament_group"] == "friendly" else coefficients["log_b_nonfriendly"])
                      for r in rs]) if len(result["slope_names"]) == 2 else math.exp(coefficients["log_b"])
        mu = np.array([float(r["strength_difference"]) for r in rs])
        v = np.array([float(r["strength_difference_base_variance"]) for r in rs])
        nu = np.array([float(r["home_jump_intensity"]) + float(r["away_jump_intensity"]) for r in rs])
        sd = np.array([float(r["jump_scale_sd"]) for r in rs])
        if result["mode"] == "plugin":
            return ndtr(eta + b * mu)
        if result["mode"] == "total_normal":
            return ndtr((eta + b * mu) / np.sqrt(1 + b * b * (v + nu * sd * sd)))
        cap = int(poisson.isf(1e-14, float(nu.max()))) if nu.max() else 0
        answer = np.zeros(len(rs))
        for n in range(cap + 1):
            answer += poisson.pmf(n, nu) * ndtr((eta + b * mu) / np.sqrt(1 + b * b * (v + n * sd * sd)))
        return answer
    for model, result in models.items():
        p = probability(rows, model)
        saved = np.array([float(r[model]) for r in predictions]); y = np.array([int(r["home_win"]) for r in rows])
        for r, actual, written in zip(rows, p, saved):
            check("p:" + model + ":" + r["match_id"], abs(actual - written) < 2e-8 and 0 < written < 1)
        loss = -float(np.mean(np.where(y, np.log(p), np.log1p(-p))))
        check("loss:" + model, abs(loss - result["loss"]) < 2e-8)
        check("optimization:" + model, result["numerical_fit_passed"] and result["gradient"] < cfg["numerics"]["gradient_gate"] and not result["boundary_parameters"])
    geography = json.loads((ROOT / cfg["regions_config"]).read_text(encoding="utf-8-sig"))
    targets = {r["target_id"]: r for r in read_rows(ROOT / cfg["targets"]) if r["family"] == "CORE"}
    contrasts = read_rows(folder / "contrasts.csv")
    check("32main_full", sum(r["model_id"] == "M3_nested" and r["reference_kind"] == "full" for r in contrasts) == 32)
    check("32main_overlap", sum(r["model_id"] == "M3_nested" and r["reference_kind"] == "cell_range_overlap" for r in contrasts) == 32)
    def matches(r, group):
        if any(group.get(k) and r[field] not in group[k] for k, field in (
            ("home_regions", "home_region"), ("home_units", "home_unit"), ("away_regions", "away_region"), ("away_units", "away_unit"))):
            return False
        rel = "unknown" if not r["home_region"] or not r["away_region"] else "cross_region" if r["home_region"] != r["away_region"] else "same_unit" if r["home_unit"] == r["away_unit"] else "same_region_other_unit"
        return not group.get("relations") or rel in group["relations"]
    for r in contrasts:
        check("empty_unadmitted_intervals", not r["lower_pp"] and not r["upper_pp"] and r["inference_status"] == "INFERENCE_NOT_ADMITTED")
        check("original_target_preserved", r["old_target_status"] == targets[r["target_id"]]["status"])
        if r["model_id"] not in ("M0_nested", "M3_nested") or not r["difference_pp"] or r["reference_kind"] != "full":
            continue
        tid = r["target_id"]; model = r["model_id"]
        if tid.startswith("Q1:"):
            e = "2010s" if "2010s_minus" in tid else "2020_2024"
            values = [float(probability([dict(x, era=era) for x in rows], model).mean()) for era in (e, "1980s")]
        elif tid.startswith("Q2:"):
            values = [float(probability([dict(x, tournament_group=t) for x in rows], model).mean()) for t in ("friendly", "non_friendly")]
        else:
            comp = next(x for x in geography["comparisons"] if x["id"] == targets[tid]["source_row_key"])
            values = []
            for arm in ("arm1", "arm2"):
                group = geography["groups"][comp[arm]]
                if comp["id"].startswith("B_"):
                    parent = geography["groups"][comp["reference_group"]]
                    reference = [x for x in rows if matches(x, parent) and x["home_unit"] and x["away_unit"]]
                    estimate = 0.
                    for hu, count in Counter(x["home_unit"] for x in reference).items():
                        subset = [x for x in reference if x["home_unit"] == hu]
                        cc = Counter(x["away_unit"] for x in rows if x["home_unit"] == hu and matches(x, group) and x["away_unit"])
                        for au, n in cc.items():
                            scenario = [dict(x, away_unit=au, away_region=parents[au]) for x in subset]
                            estimate += count / len(reference) * n / sum(cc.values()) * float(probability(scenario, model).mean())
                else:
                    cc = Counter(x["home_unit"] for x in rows if matches(x, group))
                    estimate = sum(n / sum(cc.values()) * float(probability([dict(x, home_unit=hu, home_region=parents[hu]) for x in rows], model).mean()) for hu, n in cc.items())
                values.append(estimate)
        check("contrast:" + tid + ":" + model, max(abs(values[j] - float(r[f"arm{j + 1}_probability"])) for j in range(2)) < 2e-8 and abs(100 * (values[0] - values[1]) - float(r["difference_pp"])) < 2e-7)
    for name in ("joint_predictions.csv", "contrasts.csv", "model_metrics.csv", "support.csv"):
        data = (folder / name).read_bytes()
        check("BOM_LF:" + name, data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data)
    result = dict(passed=not failures, checks=checks, failed=failures, directory=directory,
                  independent_probability_and_main_contrast_reconstruction=True, statistical_coverage_validated=False, human_review=False)
    write_json(ROOT / "outputs/logs/strength_joint" / (folder.name + "-audit.json"), result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("directory", nargs="?")
    args = parser.parse_args()
    directory = args.directory or json.loads((ROOT / "outputs/logs/strength_joint/analysis_pointer.json").read_text())["directory"]
    run(directory)
