"""Select only from independent development checks; final validation still needed."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
from pathlib import Path
import sys
import json
import gzip

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from src.reliability.experiment import actual_design,write_json,write_csv
from src.reliability.models import truth_margin,exact_mc_limits
from src.reliability.joint import finite_calibration_critical
from src.reliability.design import sha


def main(config_path="config/reliability_joint_v8.json"):
    cfg=json.loads((ROOT/config_path).read_text(encoding="utf-8-sig"))
    base=ROOT/cfg.get("experiment_root","outputs/logs/reliability/joint-20261028")
    if (base/"model_selection.json").exists():raise RuntimeError("Preserve selected candidate; use new protocol")
    rule=json.loads((ROOT/"config/reliability_joint_selection_v9.json").read_text(encoding="utf-8-sig"))
    source=json.loads((base/"development_latest.json").read_text(encoding="utf-8"))["directory"]
    path=ROOT/source/"replications.jsonl"
    if path.exists():records=[json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    else:
        with gzip.open(ROOT/source/"replications.jsonl.gz","rt",encoding="utf-8") as stream:records=[json.loads(x) for x in stream]
    d,_=actual_design(ROOT)
    scenarios={s["id"]:s for s in json.loads((ROOT/"config/reliability_validation_v1.json").read_text(encoding="utf-8-sig"))["simulations"]["scenarios"]}
    truth={s:d.apply(truth_margin(d,sc)) for s,sc in scenarios.items()}
    metrics=[];candidates=[];criticals={}
    for name in cfg["models"]:
        critical={}
        for f in d.families:
            byworld=[]
            for s in cfg["required_scenarios"]:
                vals=[r["models"][name]["scores"][f] for r in records if r["scenario"]==s and r["replication"]<50 and r["models"][name]["ok"]]
                if len(vals)!=50:raise RuntimeError("Development fit failure:"+name+":"+s)
                byworld.append(finite_calibration_critical(vals,.025))
            critical[f]=max(byworld)
        criticals[name]=critical;qualifies=True;widths={f:[] for f in d.families}
        for sid in scenarios:
            selected=[r for r in records if r["scenario"]==sid and r["replication"]>=50]
            for f,ids in d.families.items():
                covered=0;ww=[];failures=0
                for r in selected:
                    m=r["models"][name]
                    if not m["ok"]:failures+=1;continue
                    h=critical[f]*np.array(m["scale"])[ids]
                    if m["all_constant"]:h=np.maximum(h,d.span[ids])
                    est=truth[sid][ids]+np.array(r["estimate_error"])[ids]
                    lo=np.maximum(est-h,d.lo[ids]);hi=np.minimum(est+h,d.hi[ids])
                    covered+=bool(np.all((lo<=truth[sid][ids]+1e-12)&(hi>=truth[sid][ids]-1e-12)))
                    ww.append(float(np.mean(hi-lo)))
                if sid in cfg["required_scenarios"]:
                    qualifies &= failures==0 and covered/50>=rule["required_min_development_check_coverage"]
                    widths[f].extend(ww)
                metrics.append(dict(model=name,scenario=sid,family=f,R=50,covered=covered,failures=failures,
                                    **exact_mc_limits(covered,50),mean_width=float(np.mean(ww)) if ww else None))
        candidates.append(dict(model=name,development_qualified=bool(qualifies),
            mean_CORE_width=float(np.mean(widths["CORE"])),mean_ROLLING_width=float(np.mean(widths["ROLLING"])),
            mean_CONDITIONAL_width=float(np.mean(widths["CONDITIONAL"]))))
    qualified=[c for c in candidates if c["development_qualified"]]
    winner=min(qualified,key=lambda r:(r["mean_CORE_width"],r["mean_ROLLING_width"],r["mean_CONDITIONAL_width"])) if qualified else None
    result=dict(source=source,rule_sha256=sha(ROOT/"config/reliability_joint_selection_v9.json"),script_sha256=sha(Path(__file__)),
        candidates=candidates,development_trial_critical=criticals,selected_model=winner["model"] if winner else None,
        selection_scope="minimum development width among tested eligible candidates; not a universal optimality theorem",
        independent_calibration_completed=False,locked_validation_completed=False,production_approved=False)
    write_csv(base/"development_comparison.csv",metrics);write_json(base/"model_selection.json",result)
    print(json.dumps(result))


if __name__=="__main__":
    parser=__import__("argparse").ArgumentParser(description=__doc__)
    parser.add_argument("--config",default="config/reliability_joint_v8.json")
    main(parser.parse_args().config)
