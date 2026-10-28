"""Matched truth-switch diagnostic; known nuisance values are not deployable."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
from pathlib import Path
import sys
import json
import math
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from src.reliability.design import sha
from src.reliability.experiment import actual_design,write_json,write_csv
from src.reliability.models import keyed_rng,truth_margin,fit_margin,scenario_from_fit
from src.reliability.refinements import generate_fast,bootstrap_fast


def main():
    cfg=json.loads((ROOT/"config/reliability_ablation_v7.json").read_text(encoding="utf-8-sig"))
    out=ROOT/"outputs/logs/reliability/iteration-20261028"
    if (out/"failure_localization.json").exists():raise RuntimeError("Preserve original localization record")
    source=ROOT/cfg["source"]
    records=[json.loads(s) for s in (source/"replications.jsonl").read_text(encoding="utf-8").splitlines()]
    records=[r for r in records if r["scenario"]==cfg["scenario"]]
    if len(records)!=10:raise RuntimeError("Need all10 matched outer datasets")
    sc=next(s for s in json.loads((ROOT/"config/reliability_validation_v1.json").read_text(encoding="utf-8-sig"))["simulations"]["scenarios"] if s["id"]==cfg["scenario"])
    d,_=actual_design(ROOT);p=truth_margin(d,sc);truth=d.apply(p)
    rows=[];details=[];cpu0=time.process_time()
    for r in records:
        rng=keyed_rng(0);rng.bit_generator.state=r["outer_state_before"]
        y=generate_fast(d,p,sc,1,rng)[0]
        if __import__("hashlib").sha256(y.astype("u1").tobytes()).hexdigest()!=r["outcome_sha256"]:raise RuntimeError("Replay mismatch")
        fitted=fit_margin(d,y,.5)["p"];est=d.apply(y);assoc=scenario_from_fit(np.array(r["parameters"]))
        for name,margin,kernel in (("fitted_margin_fitted_dependence",fitted,assoc),("true_margin_fitted_dependence",p,assoc),
                                   ("fitted_margin_true_dependence",fitted,sc),("true_margin_true_dependence",p,sc)):
            if time.process_time()-cpu0>cfg["CPU_seconds_cap"]:raise RuntimeError("Diagnostic budget exhausted, no completed result")
            inner=keyed_rng(20261028,"ablation-v7",r["replication"],name)
            before=inner.bit_generator.state
            half,cal=bootstrap_fast(d,margin,kernel,199,inner)
            details.append(dict(replication=r["replication"],variant=name,before=before,after=inner.bit_generator.state,calibration=cal))
            for c in (1,2):
                lo=np.maximum(est-c*half,d.lo);hi=np.minimum(est+c*half,d.hi)
                for f,js in d.families.items():
                    rows.append(dict(replication=r["replication"],variant=name,multiplier=c,family=f,
                        covered=bool(np.all((lo[js]<=truth[js]+1e-12)&(hi[js]>=truth[js]-1e-12))),
                        mean_span_fraction=float(np.mean((hi[js]-lo[js])/d.span[js]))))
        print("localized C09 replicate",r["replication"],"CPU",time.process_time()-cpu0,flush=True)
    write_csv(out/"failure_localization_replicates.csv",rows)
    groups={}
    for r in rows:
        key=(r["variant"],r["multiplier"],r["family"]);groups.setdefault(key,[]).append(r)
    aggregate=[dict(variant=k[0],multiplier=k[1],family=k[2],R=len(v),covered=sum(r["covered"] for r in v),
        coverage=sum(r["covered"] for r in v)/len(v),mean_span_fraction=sum(r["mean_span_fraction"] for r in v)/len(v)) for k,v in groups.items()]
    write_csv(out/"failure_localization_metrics.csv",aggregate)
    pvalue=sum(math.comb(10,k)*.94**k*.06**(10-k) for k in range(6))
    result=dict(config_sha256=sha(ROOT/"config/reliability_ablation_v7.json"),script_sha256=sha(Path(__file__)),
        reused_outer_datasets=10,inner_B=199,cpu_seconds=time.process_time()-cpu0,random_states=details,
        diagnostic_not_deployable_model=True,not_independent_validation=True,
        supplemental_negative_result=dict(null="coverage>=.94",observed="5/10",one_sided_exact_binomial_tail=pvalue,
            looked_at_cells=144,Bonferroni144=min(1,144*pvalue),family_alpha=.05),
        actual_football_conclusion=False)
    write_json(out/"failure_localization.json",result)
    print(json.dumps(dict(cpu_seconds=result["cpu_seconds"],negative_check=result["supplemental_negative_result"])))


if __name__=="__main__":main()
