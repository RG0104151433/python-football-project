"""Versioned training/heldout critical inflation; never a formal coverage proof."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from src.reliability.design import sha
from src.reliability.experiment import small_design,write_json,write_csv,collect_metric
from src.reliability.models import exact_mc_limits,truth_margin


def run(stage,source):
    design=small_design()
    protocol=json.loads((ROOT/"config/reliability_validation_v1.json").read_text(encoding="utf-8-sig"))
    cfg=json.loads((ROOT/"config/reliability_iteration_v4.json").read_text(encoding="utf-8-sig"))
    scenarios={s["id"]:s for s in protocol["simulations"]["scenarios"]}
    destination=ROOT/"outputs/logs/reliability/iteration-20261028"
    destination.mkdir(parents=True,exist_ok=True)
    rows=[]
    for line in (ROOT/source/"replications.jsonl").read_text(encoding="utf-8").splitlines():
        row=json.loads(line)
        if (stage=="select" and row["replication"]<50) or (stage=="holdout" and 50<=row["replication"]<100):
            rows.append(row)
    for sid in scenarios:
        if sum(r["scenario"]==sid for r in rows)!=50:raise RuntimeError("Incomplete designated split:"+sid)
    if stage=="select":
        multipliers=cfg["calibration_grid"]
    else:
        training=json.loads((destination/"calibration_training.json").read_text(encoding="utf-8"))
        if training["selected_multiplier"] is None:raise RuntimeError("No calibration candidate passed training screen")
        multipliers=[1,training["selected_multiplier"]]
    metrics=[];qualified=[]
    for c in multipliers:
        minimum=50
        for sid,sc in scenarios.items():
            subset=[r for r in rows if r["scenario"]==sid]
            truth=truth_margin(design,sc)
            T=design.apply(truth)
            family_values={f:[] for f in design.families}
            for row in subset:
                method=row["methods"]["P1-cell-ridge"]
                half=np.zeros(len(design.targets))
                if method["ok"]:
                    for f,ids in design.families.items():half[ids]=c*method["bootstrap"]["critical"][f]*design.scale[ids]
                    values=collect_metric(design,T+np.array(row["bias_vector"]),T,half)
                else:values={f:dict(covered=False) for f in design.families}
                for f,v in values.items():family_values[f].append(v)
            for f,values in family_values.items():
                k=sum(v["covered"] for v in values)
                if sc["MP_domain"]:minimum=min(minimum,k)
                metrics.append(dict(multiplier=c,scenario=sid,MP_domain=sc["MP_domain"],family=f,R=50,covered=k,
                    **exact_mc_limits(k,50),mean_span_fraction=float(np.mean([v["mean_span_fraction"] for v in values if "mean_span_fraction" in v]))))
        if minimum>=49:qualified.append(c)
    write_csv(destination/("calibration_training_metrics.csv" if stage=="select" else "calibration_holdout_metrics.csv"),metrics)
    result=dict(stage=stage,source=source,config_sha256=sha(ROOT/"config/reliability_iteration_v4.json"),
                script_sha256=sha(Path(__file__)),n_outer_rows=len(rows),replications="0..49" if stage=="select" else "50..99",
                source_selected_rows_sha256=__import__("hashlib").sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
                selected_multiplier=min(qualified) if stage=="select" and qualified else training["selected_multiplier"] if stage=="holdout" else None,
                formal_acceptance=False,formal_R5000_not_completed=True,
                note="Training screen49/50 is tuning only. Heldout50 has MC uncertainty and does not establish95% full-design coverage.")
    target=destination/("calibration_training.json" if stage=="select" else "calibration_holdout.json")
    if target.exists():raise RuntimeError("Preserve existing calibration decision; use a new version")
    write_json(target,result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["select","holdout"],required=True)
    parser.add_argument("--source",required=True)
    args=parser.parse_args();run(args.stage,args.source)
