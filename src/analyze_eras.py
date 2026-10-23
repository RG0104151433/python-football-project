"""Run exploratory era analysis as a module; never edits raw or cleaned data."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path

from .data_contract import (PrepError, csv_bytes, digest, file_hash, fingerprint,
                            load_config, make_run_dir, project_path, write_json, atomic_bytes)
from .eras import RULES_VERSION
from .eras.checks import collect_issues, run_sensitivity, validate_tables
from .eras.data import load_analysis_config, load_validated_dataset, select_samples, sample_id, upstream_flow
from .eras.inference import require_off
from .eras.reporting import figure_artifacts, publish_outputs, table_artifacts, verify_run
from .eras.standardize import build_standardization
from .eras.statistics import build_statistics


def environment():
    return {"python": platform.python_version(), **{name: importlib.metadata.version(name) for name in ("numpy", "matplotlib")}}


def code_hashes(root):
    paths = [root / "src" / name for name in ("analyze_eras.py", "data_contract.py", "validate.py", "snapshot.py")]
    paths += sorted((root / "src" / "eras").glob("*.py"))
    return {p.relative_to(root).as_posix(): file_hash(p) for p in paths}


def git_state(root):
    def command(*args):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    try:
        status = command("status", "--porcelain")
        return {"commit": command("rev-parse", "HEAD"), "working_tree_dirty": None if status is None else bool(status)}
    except OSError:
        return {"commit": None, "working_tree_dirty": None}


def sample_flow(samples, membership, root, manifest):
    flow = upstream_flow(root, manifest)
    reasons = Counter(r["primary_exclusion_reason"] for r in membership if not r["in_base_venue"])
    flow.append(dict(flow_id="analysis", stage="base_venue", parent_stage="processed_matches", reason="included",
                     n_records=len(samples["base_venue"]), basis="processed_matches", status="ok"))
    flow.extend(dict(flow_id="analysis", stage="base_excluded", parent_stage="processed_matches", reason=reason,
                     n_records=count, basis="processed_matches", status="ok") for reason, count in sorted(reasons.items()))
    flow.extend([
        dict(flow_id="analysis", stage="classified_venue", parent_stage="base_venue", reason="included", n_records=len(samples["classified_venue"]), basis="processed_matches", status="ok"),
        dict(flow_id="analysis", stage="classification_excluded", parent_stage="base_venue", reason="tournament_ineligible_or_unknown",
             n_records=len(samples["base_venue"]) - len(samples["classified_venue"]), basis="processed_matches", status="ok")])
    if sum(r["n_records"] for r in flow if r["basis"] == "upstream_raw") != manifest["counts"]["input"]:
        raise PrepError("UPSTREAM_COUNT_MISMATCH", "Lineage does not sum to raw input")
    if len(samples["base_venue"]) + sum(reasons.values()) != len(membership):
        raise PrepError("ANALYSIS_COUNT_MISMATCH", "Membership accounting failed")
    return flow


def build_summary(analysis_id, config, counts, references, tables, issues):
    lines = ["# 年代分析运行小结", "", f"analysis_id: {analysis_id}", f"data_version: {config['data_version']}",
             f"协议状态：{config['protocol_status']}；当前为探索性分析，不作确认性检验。",
             f"范围：{config['analysis_start']} 至 {config['analysis_end']}。", "",
             f"基础非中立场样本：{counts['base_venue']}；赛事分类已知：{counts['classified_venue']}。",
             "比分含加时、不含点球；主胜率的分母包含平局。区间与显著性检验未运行。", ""]
    for reference in references:
        lines.append(f"- {reference['scheme']}: 友谊赛参考占比={reference['weight_friendly']}；缺年={reference['missing_years']}。")
    if "era_summary" in tables:
        lines.extend(["", "## 年代主胜率（原始计数）", ""])
        for row in tables["era_summary"]:
            if row["sample_name"] != "base_venue":
                continue
            rate = "不可估计" if row["home_win_rate"] is None else f"{100 * row['home_win_rate']:.4f}%"
            lines.append(f"- {row['period_id']}: n={row['n_matches']}, home_wins={row['n_home_wins']}, rate={rate}。")
    lines.extend(["", "## 限制", "", "参考构成统一不等于控制双方实力或地区；不是主场因果效应。人工核验状态以输入 manifest 为准。",
                  "同队反复参赛、主客角色及共同时间冲击的推断适配尚未验收；不能从图中推断统计显著。", ""])
    for severity, code, message in issues:
        lines.append(f"- [{severity}/{code}] {message}")
    return "\n".join(lines) + "\n"


def run_analysis(prep_config_path="config.json", analysis_config_path="config/eras.json", stage="all"):
    if stage not in {"diagnose", "describe", "all"}:
        raise PrepError("ANALYSIS_STAGE_INVALID", stage)
    root, prep_config = load_config(prep_config_path)
    run_dir = make_run_dir(root / "outputs" / "logs" / "eras", "eras")
    run_id = run_dir.name
    manifest = {"schema_version": "eras-run-v1", "status": "running", "run_id": run_id, "stage_requested": stage}
    try:
        analysis_path = project_path(root, str(analysis_config_path))
        config = load_analysis_config(analysis_path, prep_config["data"]["cutoff_date"])
        require_off(config)
        rows, data_manifest, validation, inputs = load_validated_dataset(root, prep_config, config)
        inputs[analysis_path.relative_to(root).as_posix()] = file_hash(analysis_path)
        prep_path = Path(prep_config_path).resolve()
        inputs[prep_path.relative_to(root).as_posix()] = file_hash(prep_path)
        sources, versions = code_hashes(root), environment()
        identity = {"inputs": inputs, "config": config, "code": sources, "environment": versions,
                    "stage": stage, "rules_version": RULES_VERSION}
        analysis_id = "eras-" + fingerprint(identity)[:20]
        samples, membership = select_samples(rows, config)
        tables = {"analysis_membership": membership, "sample_flow": sample_flow(samples, membership, root, data_manifest)}
        tables.update(build_statistics(samples, config, outcomes=stage != "diagnose"))
        references = []
        if stage != "diagnose":
            standardized, references = build_standardization(samples["classified_venue"], config)
            tables.update(standardized)
        if stage == "all":
            tables["sensitivity_results"] = run_sensitivity(samples["classified_venue"], config, references)
        checks = validate_tables(tables, samples, membership, config)
        issues = collect_issues(data_manifest, config, tables)
        counts = {name: len(selected) for name, selected in samples.items()}
        counts["processed_matches"] = len(rows)
        artifacts = table_artifacts(tables, analysis_id)
        if stage != "diagnose":
            artifacts.update(figure_artifacts(tables, references, config, analysis_id))
        outputs = publish_outputs(root, artifacts)
        write_json(run_dir / "analysis_config.json", config)
        write_json(run_dir / "input_validation.json", validation)
        write_json(run_dir / "checks.json", checks)
        issue_rows = [dict(issue_id=f"{run_id}:{i}", run_id=run_id, stage="analysis", severity=severity, code=code,
                           sample_id="", match_id="", field="", message=message, action="DISCLOSE", status="open")
                      for i, (severity, code, message) in enumerate(issues, 1)]
        atomic_bytes(run_dir / "issues.csv", csv_bytes("issue_id run_id stage severity code sample_id match_id field message action status".split(), issue_rows))
        atomic_bytes(run_dir / "summary.md", build_summary(analysis_id, config, counts, references, tables, issues).encode("utf-8"))
        for name in ("analysis_config.json", "input_validation.json", "checks.json", "issues.csv", "summary.md"):
            path = run_dir / name
            outputs[path.relative_to(root).as_posix()] = file_hash(path)
        manifest.update(status="completed", analysis_id=analysis_id, data_version=config["data_version"],
                        protocol_status=config["protocol_status"], publication_status="preliminary",
                        input_human_review_pending=data_manifest["human_review_pending"], input_frozen=data_manifest["frozen"],
                        config=config, inputs=inputs, outputs=outputs, code_hashes=sources, environment=versions,
                        git=git_state(root), counts=counts, references=references,
                        sample_ids={name: sample_id(selected, config["data_version"]) for name, selected in samples.items()},
                        stages={"diagnostics": "completed", "description": "not_run" if stage == "diagnose" else "completed",
                                "standardization": "not_run" if stage == "diagnose" else "completed",
                                "sensitivity": "completed" if stage == "all" else "not_run", "inference": "not_run"},
                        checks=checks, review_status="pending", tables_schema="eras-tables-v1")
        write_json(run_dir / "run_manifest.json", manifest)
        return manifest, run_dir
    except Exception as exc:
        manifest.update(status="failed", code=getattr(exc, "code", "EXECUTION_FAILED"), message=str(exc))
        write_json(run_dir / "run_manifest.json", manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prep-config", default="config.json")
    parser.add_argument("--analysis-config", default="config/eras.json")
    parser.add_argument("--stage", choices=("diagnose", "describe", "all"), default="all")
    parser.add_argument("--verify-run", help="Project-relative completed run_manifest.json to verify without recomputing")
    args = parser.parse_args()
    try:
        if args.verify_run:
            root, _ = load_config(args.prep_config)
            print(json.dumps(verify_run(root, args.verify_run), ensure_ascii=False))
        else:
            manifest, folder = run_analysis(args.prep_config, args.analysis_config, args.stage)
            print(json.dumps({"status": manifest["status"], "analysis_id": manifest["analysis_id"], "counts": manifest["counts"],
                              "report": str(folder), "inference": "not_run", "protocol_status": manifest["protocol_status"]}, ensure_ascii=False))
        return 0
    except (PrepError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"[FATAL {getattr(exc, 'code', 'EXECUTION_FAILED')}] {exc}", file=sys.stderr)
        return 2 if getattr(exc, "code", "") == "INFERENCE_NOT_IMPLEMENTED" else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(main())
