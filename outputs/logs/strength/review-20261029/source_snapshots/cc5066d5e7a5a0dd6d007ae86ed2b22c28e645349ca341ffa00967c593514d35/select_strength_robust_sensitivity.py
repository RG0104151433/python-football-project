"""Lock an epsilon>0 sensitivity from pre1980 candidates, never by holdout rank."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.global_run import choose
from src.strength.io import read_rows,publish
from src.data_contract import file_hash


def main():
    source=ROOT/"outputs/logs/strength/global-selection-5e8794cea926b9879b78"
    original=json.loads((source/"selection.json").read_text(encoding="utf-8"))
    cfg=original["protocol"]
    metrics=[]
    for r in read_rows(source/"candidate_metrics.csv"):
        if int(r["modules"])==0:continue
        metrics.append(dict(r,modules=int(r["modules"]),candidate_order=int(r["candidate_order"]),
            start=int(r["start"]),count=int(r["count"]),log_loss=float(r["log_loss"]),
            max_absolute_class_bias=float(r["max_absolute_class_bias"])))
    winner,best=choose(metrics,cfg)
    selected=dict(original,winner=winner,minimum_validation_log_loss=best,
        parameters=cfg["candidates"][winner["candidate_order"]]["parameters"],
        selection_role="prespecified_functional_robustness_sensitivity_not_holdout_winner",
        sensitivity_reason="Retain positive transient-background mechanism for upset/uncertainty concerns; select only from pre1980 calibrated candidates; do not choose between references using later test scores.")
    folder,_=publish("robust-sensitivity-selection",{"parent_manifest_sha":file_hash(source/"manifest.json"),
        "runner_sha":file_hash(Path(__file__)),"constraint":"modules>0; same calibration and tie rules"},
        jsons={"selection.json":selected})
    print(folder.relative_to(ROOT).as_posix(),json.dumps(winner),flush=True)


if __name__=="__main__":main()
