"""Independently reconstruct Q3 from pinned scores using exact integer fractions."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import math
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from src.regions.io import json_bytes, project_path, read_json, read_rows, require, sha
from src.regions.export import FIELDS, KEYS, verify_run


def audit(root, run_path, compare=None):
    root = Path(root).resolve()
    integrity = verify_run(root, run_path)
    manifest = read_json(project_path(root, run_path))
    aid = manifest["analysis_id"]
    folder = root / "outputs/tables/regions" / aid
    metadata = read_json(folder / "analysis_metadata.json")
    c = metadata["config"]
    upstream = project_path(root, metadata["grouping_run"])
    im = read_json(upstream / "inputs/inputs_manifest.json")["items"]
    source_path = lambda key: project_path(root, (upstream / im[key]["snapshot_path"].replace("\\", "/")).relative_to(root))
    clean = {r["match_id"]: r for r in read_rows(source_path("matches_clean"), "match_id")}
    membership = read_rows(source_path("q2_membership"), "match_id")
    geo = {r["match_id"]: r for r in read_rows(upstream / "match_region_relations.csv", "match_id")}
    checks = 0

    def check(value, label):
        nonlocal checks
        require(value, "REG_INDEPENDENT_AUDIT", label)
        checks += 1

    def near(text, exact, label):
        check(text == "" if exact is None else text != "" and abs(Fraction(text) - exact) <= Fraction(1, 10**12), label)

    check(set(geo) == {r["match_id"] for r in membership if r["included"] == "true"}, "Raw sample agrees with Q2")
    tables = {}
    for name in FIELDS:
        path = folder / (name + ".csv")
        data = path.read_bytes()
        check(data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data, "BOM/LF:" + name)
        rows = read_rows(path)
        check(all(set(r) == {"analysis_id", *FIELDS[name].split()} and r["analysis_id"] == aid for r in rows), "Fields/version:" + name)
        keys = [tuple(r[k] for k in KEYS[name].split()) for r in rows]
        check(len(set(keys)) == len(rows) and keys == sorted(keys), "Unique sorted keys:" + name)
        tables[name] = rows
    fact = {r["match_id"]: r for r in tables["analysis_matches"]}
    check(set(fact) == set(geo), "Fact table IDs")
    for mid, g in geo.items():
        raw, out = clean[mid], fact[mid]
        fields = [k for k in g if k in FIELDS["analysis_matches"].split()]
        check(all(out[k] == g[k] for k in fields), "Fact geography:" + mid)
        for k in ("source_record_id", "date", "home_team_id", "away_team_id", "home_team", "away_team",
                  "home_score", "away_score", "result_basis", "city", "country", "is_neutral", "outcome"):
            check(out[k] == raw[k], "Fact raw:" + mid + k)
        check(out["home_win"] == str(int(int(raw["home_score"]) > int(raw["away_score"]))), "Score outcome:" + mid)
        check(out["year"] == raw["date"][:4], "Fact year:" + mid)
    wins = {mid: int(int(clean[mid]["home_score"]) > int(clean[mid]["away_score"])) for mid in geo}
    draws = {mid: int(clean[mid]["home_score"] == clean[mid]["away_score"]) for mid in geo}
    # No production group, count, reference or standardization function is called.
    groups = {}
    for gid, spec in c["groups"].items():
        selected = set()
        for mid, row in geo.items():
            if spec["eligibility"] and row[spec["eligibility"] + "_usable"] != "true":
                continue
            if any(spec[key] and row[column] not in spec[key] for key, column in
                   [("home_regions", "home_region"), ("home_units", "home_unit"), ("relations", "relation")]):
                continue
            selected.add(mid)
        groups[gid] = selected
    cells = [(e["id"], t) for e in c["strata"]["eras"] for t in c["strata"]["tournament_groups"]]
    cell_of = {mid: (g["era"], g["tournament_group"]) for mid, g in geo.items()}
    member_rows = {(r["target_id"], r["match_id"]): r for r in tables["analysis_membership"]}
    counts, summaries, reference, exact_rates = {}, {}, {}, {}
    team_counts, opponent_counts = Counter(), Counter()
    for tid, target in c["analysis_targets"].items():
        ref_ids = groups[target["reference_group"]]
        ref_counts = Counter(cell_of[mid] for mid in ref_ids)
        reference[tid] = {cell: Fraction(ref_counts[cell], len(ref_ids)) for cell in cells}
        for mid in geo:
            row = member_rows[tid, mid]
            found = [gid for gid in target["groups"] if mid in groups[gid]]
            check(len(found) <= 1 and row["group_id"] == (found[0] if found else "") and row["included"] == str(bool(found)).lower()
                  and row["in_reference"] == str(mid in ref_ids).lower(), "Target flow:" + tid + mid)
        for gid in target["groups"]:
            ids = groups[gid]
            n, w, d = len(ids), sum(wins[mid] for mid in ids), sum(draws[mid] for mid in ids)
            summaries[tid, gid] = (n, w, d, n - w - d)
            good = True
            estimate = Fraction(0)
            for cell in cells:
                subset = {mid for mid in ids if cell_of[mid] == cell}
                ncell, wcell, dcell = len(subset), sum(wins[mid] for mid in subset), sum(draws[mid] for mid in subset)
                counts[tid, gid, *cell] = (ncell, wcell, dcell, ncell - wcell - dcell)
                q = reference[tid][cell]
                if q and not ncell:
                    good = False
                elif q:
                    estimate += q * Fraction(wcell, ncell)
                for mid in subset:
                    for role in ("home", "away"):
                        team_counts[tid, gid, *cell, role, geo[mid][role + "_team_id"]] += 1
                    opponent_counts[tid, gid, *cell, geo[mid]["away_region"], geo[mid]["away_unit"]] += 1
            exact_rates[tid, gid] = estimate if good else None
    check(len(member_rows) == len(geo) * len(c["analysis_targets"]), "Complete membership cardinality")
    check(len(tables["group_summary"]) == len(summaries), "Complete summary cardinality")
    check(len(tables["stratum_counts"]) == len(counts), "Complete layer cardinality")
    check(len(tables["reference_weights"]) == len(c["analysis_targets"]) * len(cells), "Complete reference cardinality")
    for r in tables["group_summary"]:
        key = r["target_id"], r["group_id"]
        n, w, d, loss = summaries[key]
        check(tuple(int(r[k]) for k in ("n_matches", "n_home_wins", "n_draws", "n_away_wins")) == (n, w, d, loss), "Group integers:" + str(key))
        for name, numerator in (("home_win_rate", w), ("draw_rate", d), ("away_win_rate", loss)):
            near(r[name], Fraction(numerator, n) if n else None, "Group rate:" + str(key) + name)
        near(r["standardized_home_win_rate"], exact_rates[key], "Group standardization:" + str(key))
        check((r["standardization_status"] == "ok") == (exact_rates[key] is not None), "Group support status:" + str(key))
        ids = groups[key[1]]
        check(int(r["n_home_teams"]) == len({geo[mid]["home_team_id"] for mid in ids})
              and int(r["n_away_teams"]) == len({geo[mid]["away_team_id"] for mid in ids}), "Distinct teams:" + str(key))
    for r in tables["stratum_counts"]:
        key = tuple(r[k] for k in ("target_id", "group_id", "era", "tournament_group"))
        n, w, d, loss = counts[key]
        check(tuple(int(r[k]) for k in ("n_matches", "n_home_wins", "n_draws", "n_away_wins")) == (n, w, d, loss), "Cell integers:" + str(key))
        for name, numerator in (("home_win_rate", w), ("draw_rate", d), ("away_win_rate", loss)):
            near(r[name], Fraction(numerator, n) if n else None, "Cell rate:" + str(key) + name)
        total = summaries[key[:2]][0]
        near(r["group_share"], Fraction(n, total) if total else None, "Cell share:" + str(key))
    for r in tables["reference_weights"]:
        tid, cell = r["target_id"], (r["era"], r["tournament_group"])
        ids = groups[c["analysis_targets"][tid]["reference_group"]]
        check(int(r["n_reference_total"]) == len(ids) and int(r["n_reference_matches"]) == sum(cell_of[mid] == cell for mid in ids), "Reference integers:" + tid + str(cell))
        near(r["weight"], reference[tid][cell], "Reference exact weight:" + tid + str(cell))
    for name, expected, keys in (("team_contributions", team_counts, "target_id group_id era tournament_group role team_id"),
                                 ("opponent_composition", opponent_counts, "target_id group_id era tournament_group away_region away_unit")):
        actual = {tuple(r[k] for k in keys.split()): r for r in tables[name]}
        check(set(actual) == set(expected), "Composition keys:" + name)
        for key, n in expected.items():
            row = actual[key]
            denominator = counts[key[:4]][0]
            check(int(row["n_matches"]) == n and int(row["denominator"]) == denominator, "Composition integers:" + str(key))
            near(row["share"], Fraction(n, denominator), "Composition share:" + str(key))
    coef_rows = {(r["contrast_id"], r["method"], r["match_id"]): r for r in tables["match_coefficients"]}
    expected_coefs = set()
    contrast_rows = {r["contrast_id"]: r for r in tables["contrast_results"]}
    layer_rows = {(r["contrast_id"], r["era"], r["tournament_group"]): r for r in tables["layer_contributions"]}
    check(set(contrast_rows) == {s["id"] for s in c["comparisons"]}, "Complete contrast cardinality")
    check(set(layer_rows) == {(s["id"], *cell) for s in c["comparisons"] for cell in cells}, "Complete contrast layers")
    for spec in c["comparisons"]:
        cid, tid, a, b = (spec[k] for k in ("id", "target_id", "arm1", "arm2"))
        ra, rb = summaries[tid, a], summaries[tid, b]
        direct = Fraction(ra[1], ra[0]) - Fraction(rb[1], rb[0]) if ra[0] and rb[0] else None
        pa, pb = exact_rates[tid, a], exact_rates[tid, b]
        adjusted = pa - pb if pa is not None and pb is not None else None
        if spec.get("standardized_policy"):
            adjusted = None
        out = contrast_rows[cid]
        check(out["target_id"] == tid and out["arm1"] == a and out["arm2"] == b
              and out["reference_group"] == spec["reference_group"] and int(out["n_arm1"]) == ra[0]
              and int(out["n_arm2"]) == rb[0], "Contrast definition:" + cid)
        near(out["direct_arm1_rate"], Fraction(ra[1], ra[0]) if ra[0] else None, "Contrast raw arm1:" + cid)
        near(out["direct_arm2_rate"], Fraction(rb[1], rb[0]) if rb[0] else None, "Contrast raw arm2:" + cid)
        near(out["adjusted_arm1_rate"], pa, "Contrast adjusted arm1:" + cid)
        near(out["adjusted_arm2_rate"], pb, "Contrast adjusted arm2:" + cid)
        near(out["direct_difference"], direct, "Raw exact contrast:" + cid)
        near(out["direct_difference_pp"], direct * 100 if direct is not None else None, "Raw pp:" + cid)
        near(out["adjusted_difference"], adjusted, "Adjusted exact contrast:" + cid)
        near(out["adjusted_difference_pp"], adjusted * 100 if adjusted is not None else None, "Adjusted pp:" + cid)
        near(out["direct_minus_adjusted_pp"], (direct - adjusted) * 100 if direct is not None and adjusted is not None else None,
             "Composition adjustment:" + cid)
        check((out["adjusted_status"] == "ok") == (adjusted is not None), "Adjusted status:" + cid)
        for cell in cells:
            na, wa = counts[tid, a, *cell][:2]
            nb, wb = counts[tid, b, *cell][:2]
            delta = Fraction(wa, na) - Fraction(wb, nb) if na and nb else None
            q = reference[tid][cell]
            contribution = q * delta if q and delta is not None else Fraction(0) if not q else None
            row = layer_rows[cid, *cell]
            check((int(row["n_arm1"]), int(row["wins_arm1"]), int(row["n_arm2"]), int(row["wins_arm2"])) == (na, wa, nb, wb), "Layer inputs:" + cid + str(cell))
            near(row["layer_difference"], delta, "Layer delta:" + cid + str(cell))
            near(row["arm1_rate"], Fraction(wa, na) if na else None, "Layer arm1:" + cid + str(cell))
            near(row["arm2_rate"], Fraction(wb, nb) if nb else None, "Layer arm2:" + cid + str(cell))
            near(row["weight"], q, "Layer weight:" + cid + str(cell))
            near(row["contribution"], contribution, "Layer contribution:" + cid + str(cell))
        for method, value in (("direct", direct), ("standardized", adjusted)):
            if value is None:
                continue
            reconstructed = Fraction(0)
            for gid, sign in ((a, 1), (b, -1)):
                for mid in groups[gid]:
                    cell = cell_of[mid]
                    q = Fraction(1) if method == "direct" else reference[tid][cell]
                    denominator = summaries[tid, gid][0] if method == "direct" else counts[tid, gid, *cell][0]
                    if not q:
                        continue
                    key = cid, method, mid
                    expected_coefs.add(key)
                    row = coef_rows[key]
                    coefficient = sign * q / denominator
                    near(row["coefficient"], coefficient, "Exact coefficient:" + str(key))
                    check(row["target_id"] == tid and row["group_id"] == gid and int(row["denominator"]) == denominator, "Coefficient definition:" + str(key))
                    near(row["weight"], q, "Coefficient reference:" + str(key))
                    reconstructed += coefficient * wins[mid]
            check(reconstructed == value, "Exact score reconstruction:" + cid + method)
    check(set(coef_rows) == expected_coefs, "Complete coefficient keys")
    identical = None
    if compare:
        previous = read_json(project_path(root, compare))
        check(previous["analysis_id"] == aid, "Repeated analysis identity")
        check(previous["outputs"] == manifest["outputs"], "Repeated core output hashes")
        identical = len(manifest["outputs"])
    return dict(status="passed", analysis_id=aid, source_run=run_path, parent_matches=len(geo),
                independent_checks=checks, fingerprint_checks=integrity["fingerprint_checks"],
                repeated_core_artifacts_identical=identical, tables={k: len(v) for k, v in tables.items()},
                calculation="Exact rational reconstruction from pinned original scores; no production statistical functions",
                verifier_sha256=sha(Path(__file__)), inference="not_run", sensitivity="not_run", human_review="not_performed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(PROJECT))
    parser.add_argument("--run", required=True)
    parser.add_argument("--compare")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = project_path(root, args.output)
    require(not output.exists(), "REG_OUTPUT_COLLISION", "Choose a new audit output path")
    try:
        result = audit(root, args.run, args.compare)
        code = 0
    except Exception as exc:
        result = dict(status="failed", code=getattr(exc, "code", type(exc).__name__), message=str(exc))
        code = 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(json_bytes(result))
    print(json_bytes(result).decode("utf-8"))
    return code


if __name__ == "__main__":
    sys.exit(main())
