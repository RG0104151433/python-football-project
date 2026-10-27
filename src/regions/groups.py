"""Target/group membership independent of match outcomes."""
from .io import require


def matches_group(row, spec):
    return ((not spec["eligibility"] or row[spec["eligibility"] + "_usable"])
            and (not spec["home_regions"] or row["home_region"] in spec["home_regions"])
            and (not spec["home_units"] or row["home_unit"] in spec["home_units"])
            and (not spec["relations"] or row["relation"] in spec["relations"]))


def build_groups(facts, config):
    masks = {gid: {r["match_id"] for r in facts if matches_group(r, spec)}
             for gid, spec in config["groups"].items()}
    membership, grouped, references = [], {}, {}
    for tid, target in config["analysis_targets"].items():
        ref = masks[target["reference_group"]]
        require(ref, "REG_EMPTY_REFERENCE", tid)
        references[tid] = [r for r in facts if r["match_id"] in ref]
        for gid in target["groups"]:
            require(masks[gid] <= ref, "REG_REFERENCE", f"Group outside reference: {tid}/{gid}")
            grouped[tid, gid] = [r for r in facts if r["match_id"] in masks[gid]]
        for row in facts:
            mid = row["match_id"]
            found = [gid for gid in target["groups"] if mid in masks[gid]]
            require(len(found) <= 1, "REG_OVERLAP", f"Overlapping groups: {tid}/{mid}")
            gid = found[0] if found else ""
            if gid:
                reason = "included"
            elif not row["home_region"]:
                reason = "geography_unknown"
            elif (config["groups"][target["reference_group"]]["home_regions"]
                  and row["home_region"] not in config["groups"][target["reference_group"]]["home_regions"]):
                reason = "outside_background"
            elif mid in ref:
                reason = "reference_only"
            else:
                reason = "geography_unknown"
            membership.append(dict(target_id=tid, match_id=mid, group_id=gid,
                                   included=bool(gid), in_reference=mid in ref, reason=reason))
    for contrast in config["comparisons"]:
        t = config["analysis_targets"][contrast["target_id"]]
        require(contrast["arm1"] in t["groups"] and contrast["arm2"] in t["groups"]
                and contrast["reference_group"] == t["reference_group"], "REG_CONTRAST", contrast["id"])
    return membership, grouped, references
