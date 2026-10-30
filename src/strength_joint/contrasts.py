"""Same-reference g-computation, explicit interventions and extrapolation flags."""
from collections import Counter
import numpy as np
from src.data_contract import fingerprint
from .design import group_matches, Support
from .model import predict


def recipes(target, rows, geography, design, reference_override=None):
    """Return two stochastic interventions; weights fixed from observed labels only."""
    tid = target["target_id"]
    base = rows if reference_override is None else reference_override
    if tid.startswith("Q1:"):
        era = "2010s" if "2010s_minus" in tid else "2020_2024"
        return base, [[(1., [dict(r, era=e) for r in base])] for e in (era, "1980s")], "all24917_equal", tid
    if tid.startswith("Q2:"):
        return base, [[(1., [dict(r, tournament_group=t) for r in base])] for t in ("friendly", "non_friendly")], "all24917_equal", "friendly_minus_nonfriendly"
    cid = target["source_row_key"]
    comparison = next(c for c in geography["comparisons"] if c["id"] == cid)
    groups = [geography["groups"][comparison[k]] for k in ("arm1", "arm2")]
    if cid.startswith("B_"):
        parent = geography["groups"][comparison["reference_group"]]
        reference = [r for r in base if group_matches(r, parent) and r["home_unit"] and r["away_unit"]]
        arms = []
        # Preserve each reference home-unit share in BOTH arms. Only replace opponent units.
        for group in groups:
            pieces = []
            for homeunit, n in sorted(Counter(r["home_unit"] for r in reference).items()):
                subset = [r for r in reference if r["home_unit"] == homeunit]
                observed = [r for r in rows if r["home_unit"] == homeunit and group_matches(r, group)]
                counts = Counter(r["away_unit"] for r in observed if r["away_unit"])
                if not counts:
                    return reference, None, "parent_home_equal:" + cid, "NO_COMMON_SUPPORT: opponent mixture for " + homeunit
                for awayunit, count in sorted(counts.items()):
                    # piece lengths differ: weight is total mass, predict() uses piece mean.
                    weight = n / len(reference) * count / sum(counts.values())
                    pieces.append((weight, [design.set_away_unit(r, awayunit) for r in subset]))
            arms.append(pieces)
        return reference, arms, "parent_home_equal:" + cid, comparison["label"]
    arms = []
    for group in groups:
        units = group["home_units"]
        counts = Counter(r["home_unit"] for r in rows if r["home_unit"] in units and group_matches(r, group))
        if not counts:
            return base, None, "all24917_equal", "NO_COMMON_SUPPORT: home-unit mixture"
        arms.append([(count / sum(counts.values()), [design.set_home_unit(r, unit) for r in base])
                     for unit, count in sorted(counts.items())])
    return base, arms, "all24917_equal", comparison["label"]


def calculate(results, rows, targets, geography, design, cfg, supported_reference=False):
    support = Support(rows, cfg["support_bins"], cfg["sparse_cell_warning"])
    output = []
    for target in targets:
        reference, arms, refname, label = recipes(target, rows, geography, design)
        reference_kind = "full" if not supported_reference else "cell_range_overlap"
        if supported_reference and arms is not None:
            bad = set()
            for arm in arms:
                for _, scenario in arm:
                    zero, _, outside = support.flags(scenario)
                    bad.update(r["match_id"] for r, z, o in zip(scenario, zero, outside) if z or o)
            retained = [r for r in reference if r["match_id"] not in bad]
            if retained:
                reference, arms, refname, label = recipes(target, rows, geography, design, retained)
            else:
                reference, arms = [], None
        refid = "reference-" + fingerprint(dict(rule=refname, kind=reference_kind,
            rows=[(r["match_id"], r["strength_difference"], r["strength_difference_base_variance"],
                   r["home_jump_intensity"], r["away_jump_intensity"], r["jump_scale_sd"]) for r in reference]))[:20]
        diagnostics = []
        if arms is not None:
            for arm in arms:
                values = np.zeros(3)
                for weight, scenario in arm:
                    flags = support.flags(scenario)
                    values += weight * np.array([f.mean() for f in flags])
                diagnostics.append(values)
        for model_id, result in results.items():
            if model_id in ("M1_strength", "M3_plugin", "M3_total_normal") or target["question"] == "Q3" and model_id in ("M0_regions", "M2_common"):
                continue
            row = dict(target_id=target["target_id"], question=target["question"], model_id=model_id,
                       label=label, reference_id=refid, reference_rule=refname, reference_kind=reference_kind, reference_rows=len(reference),
                       old_target_status=target["status"], old_estimate_probability=target["estimate_probability"],
                       old_reference_id=target["reference_id"], same_estimand_as_old=False,
                       arm1_probability=None, arm2_probability=None, difference_pp=None,
                       arm1_zero_cell_fraction=None, arm2_zero_cell_fraction=None,
                       arm1_sparse_cell_fraction=None, arm2_sparse_cell_fraction=None,
                       arm1_outside_score_range_fraction=None, arm2_outside_score_range_fraction=None,
                       point_status="NO_COMMON_SUPPORT", interpretation="", lower_pp=None, upper_pp=None,
                       inference_status="INFERENCE_NOT_ADMITTED", main_evidence_eligible=False)
            if arms is not None:
                values = [sum(w * float(predict(result, scenario, design).mean()) for w, scenario in arm) for arm in arms]
                row.update(arm1_probability=values[0], arm2_probability=values[1], difference_pp=100 * (values[0] - values[1]))
                for j in range(2):
                    for k, field in enumerate(("zero_cell", "sparse_cell", "outside_score_range")):
                        row[f"arm{j + 1}_{field}_fraction"] = float(diagnostics[j][k])
                extrap = any(d[0] > 0 or d[2] > 0 for d in diagnostics)
                row["point_status"] = "MODEL_DEPENDENT_EXTRAPOLATION" if extrap else "OBSERVED_CELL_RANGE_SUPPORTED"
                row["interpretation"] = "working-model standardized association; cell/range overlap is necessary diagnostic, not identification proof"
                row["main_evidence_eligible"] = target["status"] == "supported_point_target" and not extrap
            output.append(row)
        print("JOINT_CONTRAST", target["target_id"], flush=True)
    return output


def changes(contrasts):
    index = {(r["target_id"], r["reference_kind"], r["model_id"]): r for r in contrasts}
    output = []
    for (tid, reference_kind, model), main in index.items():
        if model != "M3_nested":
            continue
        old = index[tid, reference_kind, "M0_nested"]
        if main["reference_id"] != old["reference_id"]:
            raise ValueError("INPUT_VERSION_MISMATCH: comparison references")
        output.append(dict(target_id=tid, reference_kind=reference_kind, reference_id=main["reference_id"], reference_rows=main["reference_rows"], without_strength_pp=old["difference_pp"],
                           with_strength_pp=main["difference_pp"],
                           change_pp=None if main["difference_pp"] is None else main["difference_pp"] - old["difference_pp"],
                           interpretation="same new reference; not percentage causally explained, not subtraction from old Q4 target"))
    return output
