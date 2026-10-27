"""Run the approved Q3 descriptive analysis; no inference or source mutation."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
from pathlib import Path
import platform
import subprocess
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from src.regions.io import json_bytes, load_inputs, project_path, require, sha
from src.regions.groups import build_groups
from src.regions.describe import build_counts
from src.regions.standardize import build_adjustments, validate_tables
from src.regions.export import LIMITATIONS, figure_artifacts, publish, table_artifacts, verify_run


def run_analysis(root=PROJECT, config="config/regions_study.json", run_root="outputs/logs/regions"):
    root = Path(root).resolve()
    run_id = "regions-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    log_dir = project_path(root, run_root) / run_id
    log_dir.mkdir(parents=True, exist_ok=False)
    stage = "inputs"
    try:
        context = load_inputs(root, config)
        c, facts = context["config"], context["facts"]
        sources = sorted((root / "src/regions").glob("*.py")) + [root / "scripts/analyze_regions.py", root / "src/artifact_store.py"]
        code = {p.relative_to(root).as_posix(): sha(p) for p in sources}
        environment = dict(python=platform.python_version(), **{p: importlib.metadata.version(p) for p in ("numpy", "matplotlib")})
        aid = "regions-" + hashlib.sha256(json_bytes(dict(config=c, inputs=context["inputs"], code=code, environment=environment))).hexdigest()[:20]
        stage = "membership"
        membership, grouped, references = build_groups(facts, c)
        stage = "statistics"
        tables = dict(analysis_matches=facts, analysis_membership=membership,
                      **build_counts(grouped, c, context["team_labels"]))
        build_adjustments(tables, grouped, references, c)
        checks = validate_tables(facts, tables, c)
        rules_key = next(p for p in context["inputs"] if p.endswith("/team_geography_rules.csv"))
        metadata = dict(schema_version="regions-metadata-v1", analysis_id=aid, protocol_id=c["protocol_id"],
                        data_version=c["scope"]["data_version"], identity_version=c["scope"]["identity_version"],
                        sample_id=c["scope"]["sample_id"], geography_version="geo-prep-v3:" + context["inputs"][rules_key][:12],
                        grouping_run=context["grouping_run"], parent_matches=len(facts), config=c,
                        inputs=context["inputs"], code=code, environment=environment,
                        uncertainty="not_run", sensitivity="not_run", strength_adjustment="not_run", limitations=LIMITATIONS)
        stage = "export"
        artifacts = table_artifacts(tables, metadata, aid)
        artifacts.update(figure_artifacts(tables, c, aid))
        for path, expected in {**context["inputs"], **code}.items():
            require(sha(project_path(root, path)) == expected, "REG_INPUT_CHANGED", path)
        output_hashes = publish(root, log_dir, artifacts)
        run_path = (log_dir / "run_manifest.json").relative_to(root).as_posix()
        display = dict(schema_version="regions-display-v1", source_run=run_path, analysis_id=aid,
                       sample_id=c["scope"]["sample_id"], parent_matches=len(facts), studies=c["studies"],
                       groups=tables["group_summary"], contrasts=tables["contrast_results"],
                       strata=tables["stratum_counts"], references=tables["reference_weights"],
                       figures=[p for p in output_hashes if p.startswith("outputs/figures/")],
                       source_fingerprints={**context["inputs"], **output_hashes}, limitations=LIMITATIONS,
                       inference="not_run", sensitivity="not_run", strength="not_run")
        summary = dict(analysis_id=aid, parent_matches=len(facts), studies=4, member_targets=len(c["analysis_targets"]),
                       table_rows={k: len(v) for k, v in tables.items()},
                       adjusted_contrasts_available=sum(r["adjusted_status"] == "ok" for r in tables["contrast_results"]),
                       checks_passed=checks["n_checks"], inference="not_run", sensitivity="not_run",
                       european_groups=[r for r in tables["group_summary"] if r["target_id"] == "C_EUR"],
                       contrasts=tables["contrast_results"], limitations=LIMITATIONS)
        for name, value in (("config.json", c), ("checks.json", checks), ("summary.json", summary), ("display_data.json", display)):
            (log_dir / name).write_bytes(json_bytes(value))
        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip() or None
            dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True).stdout.strip())
        except OSError:
            commit, dirty = None, None
        manifest = dict(schema_version="regions-run-v1", status="success", run_id=run_id, analysis_id=aid,
                        generated_at_utc=datetime.now(timezone.utc).isoformat(), config_path=context["config_path"].relative_to(root).as_posix(),
                        inputs=context["inputs"], code=code, environment=environment, outputs=output_hashes,
                        run_artifacts={(log_dir / name).relative_to(root).as_posix(): sha(log_dir / name)
                                       for name in ("config.json", "checks.json", "summary.json", "display_data.json")},
                        git=dict(commit=commit, working_tree_dirty=dirty, code_identity="Actual file SHA256, not commit alone"))
        (log_dir / "run_manifest.json").write_bytes(json_bytes(manifest))
        return dict(status="success", analysis_id=aid, run_manifest=run_path, **{k: v for k, v in summary.items()
                    if k in ("parent_matches", "table_rows", "checks_passed", "adjusted_contrasts_available")})
    except Exception as exc:
        (log_dir / "failure_report.json").write_bytes(json_bytes(dict(status="failed", stage=stage,
            code=getattr(exc, "code", type(exc).__name__), message=str(exc), run_id=run_id)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(PROJECT))
    parser.add_argument("--config", default="config/regions_study.json")
    parser.add_argument("--run-root", default="outputs/logs/regions")
    parser.add_argument("--verify-run")
    parser.add_argument("--inference", choices=["off"], default="off")
    args = parser.parse_args()
    try:
        result = verify_run(Path(args.root), args.verify_run) if args.verify_run else run_analysis(args.root, args.config, args.run_root)
        print(json_bytes(result).decode("utf-8"))
        return 0
    except Exception as exc:
        print(json_bytes(dict(status="failed", code=getattr(exc, "code", type(exc).__name__), message=str(exc))).decode("utf-8"))
        return 2


if __name__ == "__main__":
    sys.exit(main())
