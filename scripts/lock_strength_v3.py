"""Reuse pre1980 candidate scores; lock both final references without reading new test."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.io import read_rows,publish
from src.strength.global_run import choose
from src.data_contract import file_hash


def main():
    cfg=json.loads((ROOT/"config/strength_global_v3.json").read_text(encoding="utf-8"))
    source=ROOT/"outputs/logs/strength/global-selection-5e8794cea926b9879b78"
    original=json.loads((source/"selection.json").read_text(encoding="utf-8"))
    metrics=[]
    for r in read_rows(source/"candidate_metrics.csv"):
        metrics.append(dict(r,modules=int(r["modules"]),candidate_order=int(r["candidate_order"]),
            start=int(r["start"]),count=int(r["count"]),log_loss=float(r["log_loss"]),
            max_absolute_class_bias=float(r["max_absolute_class_bias"])))
    for role,pool in [("selected_reference",metrics),("robust_functional_sensitivity",[r for r in metrics if r["modules"]>0])]:
        winner,best=choose(pool,cfg)
        result=dict(original,winner=winner,minimum_validation_log_loss=best,protocol=cfg,
            parameters=cfg["candidates"][winner["candidate_order"]]["parameters"],selection_role=role,
            caveat="Numerically admitted candidate pool only; same-complexity parameter order corrected; no claim globally optimal")
        folder,_=publish("final-reference-selection",{"protocol":cfg,"source_manifest_sha":file_hash(source/"manifest.json"),
            "source_metrics_sha":file_hash(source/"candidate_metrics.csv"),"runner_sha":file_hash(Path(__file__)),"role":role},
            jsons={"selection.json":result})
        print(role,folder.relative_to(ROOT).as_posix(),json.dumps(winner),flush=True)


if __name__=="__main__":main()
