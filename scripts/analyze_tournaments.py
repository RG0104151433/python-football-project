"""Run Q2's approved descriptive analysis, or verify an existing Q2 run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from src.analyze_eras import environment, git_state
from src.data_contract import PrepError, digest, file_hash, json_bytes, project_path
from src.tournaments.checks import validate_tables
from src.tournaments.data import load_inputs, require
from src.tournaments.reporting import LIMITATIONS, figure_artifacts, publish, table_artifacts, verify_run
from src.tournaments.rolling import build_rolling
from src.tournaments.standardize import build_main
from src.tournaments.statistics import build_counts, build_flow


def run_analysis(root=PROJECT, relative="config/tournaments.json"):
    root = Path(root).resolve()
    run_id = "tournaments-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    log_dir = root / "outputs/logs/tournaments" / run_id
    log_dir.mkdir(parents=True, exist_ok=False)
    run_path = (log_dir / "run_manifest.json").relative_to(root).as_posix()
    try:
        context = load_inputs(root, relative)
        context["root"] = root
        sources = dict(context["inherited_code"])
        sources.update({p.relative_to(root).as_posix(): file_hash(p) for p in sorted((root/"src/tournaments").glob("*.py"))})
        sources["scripts/analyze_tournaments.py"] = file_hash(root/"scripts/analyze_tournaments.py")
        versions = environment()
        aid = "tournaments-" + digest(json_bytes(dict(config=context["config"], inputs=context["inputs"], code=sources, environment=versions)))[:20]
        selected, analysis, sid = context["selected"], context["analysis"], context["sample_id"]
        tables = dict(analysis_membership=context["membership"], sample_flow=build_flow(context), grouped_counts=build_counts(selected, analysis))
        main, definitions = build_main(tables["grouped_counts"], analysis, sid)
        tables.update(main)
        rolling, more_definitions = build_rolling(selected, tables["grouped_counts"], analysis, sid)
        for name, rows in rolling.items():
            tables.setdefault(name, []).extend(rows)
        definitions.extend(more_definitions)
        checks = validate_tables(selected, analysis, tables, definitions, sid)
        # The same underlying ten cells must reproduce the already verified Q1 counts.
        qpath = next(p for p in context["q1_run"]["outputs"] if p.endswith("/era_tournament_summary.csv"))
        from src.data_contract import read_csv
        _, qcells = read_csv(project_path(root,qpath))
        cells = {(r["period_id"],r["tournament_group"]):r for r in tables["grouped_counts"] if r["scope"] == "era"}
        require(len(cells) == len(qcells) and all(all(cells[(r["analysis_era_id"],r["tournament_group"])][k] == int(r[k])
                for k in ("n_matches","n_home_wins","n_draws","n_away_wins")) for r in qcells),
                "TQ_RECONCILIATION_FAILED", "Q1/Q2 era/type counts differ")
        checks["q1_cells_identical"] = True
        processed_flow = [r for r in tables["sample_flow"] if r["basis"] == "processed_matches"]
        require(sum(r["n_records"] for r in processed_flow) == len(context["all_rows"]), "TQ_RECONCILIATION_FAILED", "Sample flow does not sum to clean population")
        issues = [dict(code=r["status"], table=name, key=r.get("estimate_id",r.get("contrast_id",r.get("reference_id",""))))
                  for name in ("reference_weights","type_estimates","type_differences") for r in tables[name] if r["status"] != "ok"]
        artifacts = table_artifacts(tables, definitions, aid)
        artifacts.update(figure_artifacts(tables, analysis, aid))
        def unchanged():
            for p,h in {**context["inputs"], **sources}.items():
                require(file_hash(project_path(root,p)) == h, "TQ_INPUT_HASH_MISMATCH", "Changed during run: "+p)
        unchanged()
        core_outputs = publish(root, artifacts)
        summary = dict(analysis_id=aid, data_version=analysis["data_version"], identity_version=context["identity"]["identity_version"],
            sample_id=sid, n_matches=len(selected), direction="friendly_minus_non_friendly", protocol_status="exploratory",
            overall_rates=[r for r in tables["type_estimates"] if r["scope"] == "overall"],
            overall_differences=[r for r in tables["type_differences"] if r["scope"] == "overall"],
            era_differences=[r for r in tables["type_differences"] if r["scope"] == "era"],
            n_windows=len(tables["rolling_windows"]), n_window_memberships=len(tables["window_membership"]),
            table_rows={k:len(v) for k,v in tables.items()}, checks_passed=checks["n_checks"], issues=len(issues),
            inference="not_run", sensitivity="not_run", shared_reliability="not_run", limitations=LIMITATIONS)
        display = dict(schema_version="tournaments-display-v1", source_run=run_path, analysis_id=aid, sample_id=sid,
            data_version=analysis["data_version"], identity_version=context["identity"]["identity_version"], n_matches=len(selected),
            direction="friendly_minus_non_friendly", rates=tables["type_estimates"], differences=tables["type_differences"],
            grouped_counts=tables["grouped_counts"], references=tables["reference_weights"], windows=tables["rolling_windows"],
            figures=sorted(p for p in core_outputs if p.startswith("outputs/figures/")), source_fingerprints={**context["inputs"], **core_outputs},
            limitations=LIMITATIONS, inference="not_run", zero_is_not_missing=True)
        lines = ["# 第二问探索性描述结果", "", f"分析：{aid}；成员：{summary['identity_version']}；样本{len(selected):,}场。",
                 "方向：友谊赛减其他非友谊赛事，差值单位为百分点；比例分母含平局，比分含加时不含点球。", ""]
        for row in summary["overall_differences"]:
            value = "不可算" if row["estimate"] is None else f"{row['estimate']:+.6f}个百分点"
            lines.append(f"- {row['estimand']}: {value}；{row['status']}。")
        lines += ["", "## 解释边界", ""] + ["- "+x["text"] for x in LIMITATIONS] + ["", "AI运行与自检不等于A已独立复现；无正式区间/显著性/因果结论。", ""]
        outputs = dict(core_outputs)
        for name, content in {"config_snapshot.json": json_bytes(dict(config=context["config"], inherited_analysis=analysis)),
                              "checks.json": json_bytes(checks), "issues.json": json_bytes(issues), "summary.json":json_bytes(summary),
                              "summary.md":"\n".join(lines).encode("utf-8"), "display_data.json":json_bytes(display)}.items():
            path=log_dir/name
            with path.open("xb") as stream: stream.write(content)
            outputs[path.relative_to(root).as_posix()]=digest(content)
        unchanged()
        manifest = dict(schema_version="tournaments-run-v1", status="completed", run_id=run_id, analysis_id=aid,
                        created_at_utc=datetime.now(timezone.utc).isoformat(), config_path=relative, inputs=context["inputs"],
                        outputs=outputs, core_outputs=core_outputs, code_hashes=sources, environment=versions, git=git_state(root),
                        identity_version=summary["identity_version"], data_version=analysis["data_version"], sample_id=sid,
                        q1_run_manifest=context["config"]["q1_run_manifest"], summary=summary,
                        stages=dict(description="completed", inference="not_run", sensitivity="not_run", shared_reliability="not_run"))
        with (log_dir/"run_manifest.json").open("xb") as stream: stream.write(json_bytes(manifest))
        return dict(status="completed", analysis_id=aid, run_manifest=run_path, summary=summary)
    except (PrepError, OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        failure = dict(schema_version="tournaments-run-v1", status="failed", run_id=run_id,
                       code=getattr(exc,"code","TQ_RUN_FAILED"), message=str(exc), config_path=relative)
        with (log_dir/"run_manifest.json").open("xb") as stream: stream.write(json_bytes(failure))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",default="config/tournaments.json")
    parser.add_argument("--verify-run")
    args=parser.parse_args()
    try:
        result=verify_run(PROJECT,args.verify_run) if args.verify_run else run_analysis(PROJECT,args.config)
        print(json.dumps(result,ensure_ascii=True));return 0
    except (PrepError,OSError,ValueError,KeyError,TypeError,StopIteration) as exc:
        print(json.dumps(dict(status="failed",code=getattr(exc,"code","TQ_RUN_FAILED"),message=str(exc)),ensure_ascii=True),file=sys.stderr);return 2


if __name__ == "__main__":
    raise SystemExit(main())
