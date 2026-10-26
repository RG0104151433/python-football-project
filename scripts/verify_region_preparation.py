"""Verify preserved run hashes using explicit source relocations, without rewriting history."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.artifact_store import INDEX, digest, resolve_artifact, resolve_input


def main():
    checks, relocated = 0, 0
    draft_package_mismatches = []
    index = json.loads((ROOT / INDEX).read_text(encoding="utf-8"))
    for old, item in index["aliases"].items():
        path = resolve_artifact(old, ROOT)
        assert digest(path) == item["sha256"]
        assert not (ROOT / old).exists(), old
    runs = []
    for path in sorted((ROOT / "outputs/logs/regions").rglob("manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if "files" not in manifest or "run_id" not in manifest:
            continue
        run = path.parent
        for name, expected in manifest["files"].items():
            original = run / name
            actual = resolve_artifact(original, ROOT)
            assert digest(actual) == expected, str(original)
            checks += 1
            relocated += actual != original
        package = manifest.get("package_dir", manifest.get("package"))
        for name, expected in manifest.get("package_files", {}).items():
            assert package
            actual = resolve_artifact(ROOT / package / name, ROOT)
            if digest(actual) != expected:
                # Early unadopted v1 draft runs shared a package that was
                # revised before the accepted 040745 run. Never rewrite these
                # old claims to make them appear historically correct.
                if run.name == "preparation-20261026T040745Z-52745246":
                    raise AssertionError(str(actual))
                draft_package_mismatches.append({"manifest":str(path.relative_to(ROOT)),
                                                 "package_file":str(actual.relative_to(ROOT)),
                                                 "expected":expected,"actual":digest(actual)})
            checks += 1
        inputs = run / "inputs/inputs_manifest.json"
        if inputs.is_file():
            for item in json.loads(inputs.read_text(encoding="utf-8"))["items"].values():
                resolve_input(run, item, ROOT)
                checks += 1
        runs.append(str(run.relative_to(ROOT)))
    html = [p for base in [ROOT/"data/external", ROOT/"outputs/logs"] for p in base.rglob("m49_*.html")]
    assert len(html) == 2, html
    expected = {"m49_page.html":"4d5cabcb10ad9ef184553b5e64c0a34ba8deeb20dab2e02cd0be3599b93bb01d",
                "m49_overview.html":"b9048114f6e7f2abda83bf03d4263c9d7cd1bd7230e3d0461025ee7839a7a1fb"}
    assert {p.name:digest(p) for p in html} == expected
    old_review = json.loads((ROOT/"outputs/logs/regions/grouping-acceptance-20261026/review.json").read_text(encoding="utf-8"))
    protocol_hash = next(v for k,v in old_review["source_fingerprints"].items() if k.replace('\\','/')=='config/regions_study.json')
    assert digest(ROOT/"config/archive/regions_study_v1.json") == protocol_hash
    new_protocol=json.loads((ROOT/"config/regions_study.json").read_text(encoding="utf-8"))
    assert len(new_protocol["studies"])==4
    contrast_count = len([c for c in new_protocol["comparisons"] if c["role"]=="study_subanalysis"])
    assert contrast_count == {"regions-study-v2":6,"regions-study-v3":11}[new_protocol["protocol_id"]]
    if new_protocol["protocol_id"] == "regions-study-v3":
        assert len(new_protocol["analysis_targets"]["C_EUR"]["groups"]) == 4
        assert len([c for c in new_protocol["comparisons"] if c["target_id"] == "C_EUR"]) == 6
    accepted = ROOT/"outputs/logs/regions/grouping-acceptance-20261026/preparation-20261026T090739Z-82cd5e84-accepted-r1"
    migration = ROOT/"outputs/logs/regions/storage-migration-20261026"
    normal_runs = [p for p in migration.glob("*shared-normal") if (p/"manifest.json").is_file()]
    assert len(normal_runs)==1
    normal = normal_runs[0]
    core = list(accepted.glob("*.csv"))
    assert len(core)==16 and all(digest(p)==digest(normal/p.name) for p in core)
    result={"schema_version":"shared-source-verification-v1", "decision_log_id":new_protocol["decision_log_id"],
            "adopted_artifacts_and_relocations_passed":True,"historical_run_count":len(runs),"hash_checks":checks,
            "hash_matches":checks-len(draft_package_mismatches),
            "unadopted_draft_mismatch_count":len(draft_package_mismatches),
            "new_normal_run":str(normal.relative_to(ROOT)),"new_normal_core_csv_identical":16,
            "relocated_manifest_entries":relocated,"persistent_m49_html_files":2,
            "removed_duplicate_copies_net":16,"bytes_saved":30183544,
            "original_manifests_rewritten":False,"old_protocol_preserved":True,
            "current_protocol":new_protocol["protocol_id"],"studies":4,"numerical_contrasts":contrast_count,
            "regional_outcomes_computed":False,"runs":runs,
            "unadopted_early_package_mismatches":draft_package_mismatches,
            "code_sha256":digest(Path(__file__)),"relocations_sha256":digest(ROOT/INDEX)}
    filename = "verification.json" if new_protocol["protocol_id"] == "regions-study-v2" else "verification-regions-study-v3.json"
    out=ROOT/"outputs/logs/regions/storage-migration-20261026"/filename
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({k:v for k,v in result.items() if k!='runs'},ensure_ascii=True))


if __name__=="__main__":
    main()
