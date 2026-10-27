"""Generate the explicit v4 comparison catalogue from the preserved v3 protocol."""
import argparse
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(root=ROOT):
    root = Path(root)
    c = json.loads((root / "config/archive/regions_study_v3.json").read_text(encoding="utf-8"))
    classification = json.loads((root / "config/regions_study_overrides.json").read_text(encoding="utf-8"))
    c.update(schema_version="regions-study-protocol-v4", protocol_id="regions-study-v4", decision_log_id="R20261027-01",
             previous_protocol="config/archive/regions_study_v3.json", status="approved_expanded_descriptive_scope",
             study_classification=classification, study_classification_path="config/regions_study_overrides.json")
    groups, targets, contrasts = {}, {}, []
    region_ids = ["002", "019", "142", "150", "009"]
    short = {"002": "AFR", "019": "AMER", "142": "ASIA", "150": "EUR", "009": "OCE"}
    studies = {"002": "AFRICA", "019": "AMERICAS", "142": "ASIA", "150": "EUROPE"}

    def group(gid, label, eligibility=None, hr=(), hu=(), ar=(), au=(), relations=()):
        groups[gid] = dict(label=label, eligibility=eligibility, home_regions=list(hr), home_units=list(hu),
                           away_regions=list(ar), away_units=list(au), relations=list(relations))
        return gid

    def target(tid, gids, reference, kind, **kwargs):
        targets[tid] = dict(groups=gids, reference_group=reference, type=kind, **kwargs)

    def contrast(cid, tid, a, b, label, study, **kwargs):
        record = dict(id=cid, target_id=tid, label=label, role="study_subanalysis", family=tid[0],
                      arm1=a, arm2=b, reference_group=targets[tid]["reference_group"], parent_study=study)
        record.update(kwargs)
        contrasts.append(record)

    group("PARENT", "母样本")
    for reg in region_ids:
        group("A_" + short[reg], classification["regions"][reg], "A", hr=[reg])
    target("PROFILE_MACRO", ["A_" + short[r] for r in region_ids], "PARENT", "profile")
    group("SA_FEATURE", "南美洲", "C", hr=["019"], hu=["005"])
    target("PROFILE_SA", ["SA_FEATURE"], "PARENT", "profile")
    for reg in ["150", "142", "002", "019"]:
        tag = short[reg]
        ref = group("C_" + tag + "_REF", classification["regions"][reg] + "主队研究分区明确", "C", hr=[reg])
        gids = []
        for part in classification["partitions"][reg]:
            gid = group("C_" + tag + "_" + part["id"], part["label"], "C", hr=[reg], hu=[part["id"]])
            gids.append(gid)
        tid = "C_" + tag
        target(tid, gids, ref, "multigroup", display_order=gids)
        for a, b in itertools.combinations(gids, 2):
            contrast(tid + "_" + a.rsplit("_", 1)[-1] + "_VS_" + b.rsplit("_", 1)[-1], tid, a, b,
                     groups[a]["label"] + "减" + groups[b]["label"], studies[reg])
    # Retain the original north-minus-south direction for the European pair.
    for spec in contrasts:
        if spec["target_id"] == "C_EUR" and {spec["arm1"], spec["arm2"]} == {"C_EUR_039", "C_EUR_154"}:
            spec.update(id="C_EUR_NORTH_SOUTH", arm1="C_EUR_154", arm2="C_EUR_039", label="北欧减南欧")
    for reg in ["150", "142", "019"]:
        tid = "B_SA" if reg == "019" else "B_" + short[reg]
        unit = ["005"] if reg == "019" else []
        prefix = "南美主队" if reg == "019" else classification["regions"][reg] + "主队"
        ref = group(tid + "_REF", prefix + "关系明确", "B", hr=[reg], hu=unit)
        gids = []
        for relation, suffix, name in [("same_unit", "SAME", "同一研究分区"),
                                        ("same_region_diff_unit", "OTHER", "同洲其他研究分区"),
                                        ("cross_region", "CROSS", "洲外")]:
            gids.append(group(tid + "_" + suffix, prefix + "：" + name, "B", hr=[reg], hu=unit, relations=[relation]))
        target(tid, gids, ref, "relationship")
        extra = dict(role="descriptive_only", standardized_policy="unestimable_for_full_period_no_scope_change") if reg == "019" else {}
        contrast(tid, tid, gids[2], gids[0], prefix + "：洲外减同分区", studies[reg], **extra)
    other = group("C_OTHER_AMER", "美洲其他分区合并", "C", hr=["019"], hu=["013", "021", "029"])
    target("C_AMER_FOCUS", ["SA_FEATURE", other], "C_AMER_REF", "comparison")
    contrast("C_AMER_FOCUS", "C_AMER_FOCUS", "SA_FEATURE", other, "南美减美洲其他分区合并", "AMERICAS")
    # Every directed macro cell is explicit, including structural/observed zero cells.
    matrix = []
    for hr in region_ids:
        for ar in region_ids:
            gid = group(f"MACRO_{hr}_{ar}", classification["regions"][hr] + "主队对" + classification["regions"][ar],
                        "A", hr=[hr], ar=[ar])
            matrix.append(gid)
    target("M_MACRO", matrix, "PARENT", "matchup_macro")
    for reg, parts in classification["partitions"].items():
        gids = []
        for home in parts:
            for away in parts:
                gid = group(f"PAIR_{reg}_{home['id']}_{away['id']}", home["label"] + "主队对" + away["label"],
                            "C", hr=[reg], hu=[home["id"]], ar=[reg], au=[away["id"]])
                gids.append(gid)
            for ar in region_ids:
                if ar != reg:
                    gid = group(f"OUT_{reg}_{home['id']}_{ar}", home["label"] + "主队对" + classification["regions"][ar],
                                "C", hr=[reg], hu=[home["id"]], ar=[ar])
                    gids.append(gid)
        target("M_" + short[reg], gids, "C_" + short[reg] + "_REF", "matchup_partition")
    c.update(groups=groups, analysis_targets=targets, comparisons=contrasts)
    for study in c["studies"]:
        study["subanalyses"] = [tid for tid in targets if tid.endswith({"EUROPE":"EUR", "ASIA":"ASIA", "AFRICA":"AFR", "AMERICAS":"AMER"}[study["id"]])]
        study["contrast_ids"] = [x["id"] for x in contrasts if x["parent_study"] == study["id"]]
        if study["id"] == "AMERICAS":
            study["subanalyses"].extend(["C_AMER_FOCUS", "B_SA"])
    c["profiles"] = dict(macroregions=dict(groups=targets["PROFILE_MACRO"]["groups"], reference_group="PARENT"),
                         south_america_feature=dict(groups=["SA_FEATURE"], reference_group="PARENT"))
    c["inference"]["multiple_comparison_scope"] = "25个分区总体率差+2欧亚关系差+1南美汇总差；南美关系另只描述。155条件率格不是155独立检验。第四问另定联合检验。"
    c["output_contract"]["implementation_design_log_id"] = "R20261027-01"
    c["catalogue_counts"] = dict(studies=4, targets=15, partition_groups=16, partition_rate_contrasts=25,
                                 other_adjusted_contrasts=3, descriptive_contrasts=1, macro_matchup_cells=25,
                                 within_partition_cells=66, outside_macro_cells=64)
    assert len(targets) == 15 and len(contrasts) == 29
    return c


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="config/regions_study.json")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("Output outside repository")
    content = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output.exists() and output.read_bytes() != content:
        current = json.loads(output.read_text(encoding="utf-8"))
        if current.get("protocol_id") != "regions-study-v3":
            raise ValueError("Refusing to overwrite a different existing protocol")
    output.write_bytes(content)
    print(json.dumps(dict(protocol="regions-study-v4", output=str(output.relative_to(ROOT))), ensure_ascii=True))


if __name__ == "__main__":
    main()
