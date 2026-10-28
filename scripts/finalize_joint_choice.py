"""Versioned parsimony decision after development, before calibration/testing."""
from pathlib import Path
import sys
import json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.reliability.experiment import write_json
from src.reliability.design import sha

if __name__=="__main__":
    source="outputs/logs/reliability/joint-v10-20261028/model_selection.json"
    old=json.loads((ROOT/source).read_text(encoding="utf-8"))
    cfg=json.loads((ROOT/"config/reliability_joint_v10.json").read_text(encoding="utf-8-sig"))
    eligible=[r for r in old["candidates"] if r["development_qualified"]]
    best=min(r["mean_CORE_width"] for r in eligible)
    near=[r for r in eligible if r["mean_CORE_width"]<=best*1.01]
    chosen=min(near,key=lambda r:(6 if r["model"].startswith("J1") else 17,r["mean_CORE_width"],r["mean_ROLLING_width"]))
    cfg.update(schema_version="joint-final-candidate-v11-before-independent-calibration",
        experiment_root="outputs/logs/reliability/joint-final-20261028",random_stream_version="joint-final-v11",
        models=[chosen["model"]],development_source=source,
        selection="After observing development only,1%relative CORE-width tolerance introduced to avoid claiming a meaningful gain from0.2pp width. Choose6kernels over17 within tolerance; prior exact-minimum decision preserved. No calibration/locked-test outcomes used.",
        selector_code_sha256=sha(Path(__file__)))
    target=ROOT/"config/reliability_joint_v11.json"
    if target.exists():raise RuntimeError("Preserve final choice version")
    write_json(target,cfg)
    out=ROOT/cfg["experiment_root"];out.mkdir(parents=True,exist_ok=True)
    result=dict(selected_model=chosen["model"],source=source,source_sha256=sha(ROOT/source),
        candidates=old["candidates"],near_best_candidates=near,width_tolerance_relative=.01,
        reason="Numerical development minimum is not statistically established superiority. Simpler joint-corrected6-kernel model within1% width is the project choice.",
        development_seen=True,calibration_seen=False,locked_validation_seen=False,production_approved=False,
        status="frozen_candidate_before_independent_calibration",config_sha256=sha(target))
    write_json(out/"model_selection.json",result)
    print(json.dumps(result))
