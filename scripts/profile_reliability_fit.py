"""Post-fit stationarity and constrained tau profiles, not confidence sets."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
from pathlib import Path
import sys
import json
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.optimize import minimize
from src.reliability.experiment import actual_design,write_json,write_csv
from src.reliability.models import keyed_rng,truth_margin,fit_margin,pair_metadata,association_objective
from src.reliability.refinements import generate_fast
from src.reliability.design import sha


def project(par):
    w=np.maximum(par[:4],0)
    if w.sum()>.95:
        u=np.sort(w)[::-1];cs=np.cumsum(u)
        rho=np.flatnonzero(u>(cs-.95)/np.arange(1,5))[-1]
        w=np.maximum(w-(cs[rho]-.95)/(rho+1),0)
    return np.r_[w,np.clip(par[4],np.log(7),np.log(3650)),np.clip(par[5],np.log(1),np.log(1460))]


def main():
    source="outputs/logs/reliability/refined-full-pilot-20261028T010917282465Z"
    out=ROOT/"outputs/logs/reliability/iteration-20261028"
    target=out/"fit_profiles.json"
    if target.exists():raise RuntimeError("Preserve existing profile evidence")
    d,_=actual_design(ROOT)
    raw=list(__import__("csv").DictReader((ROOT/"outputs/logs/reliability/methods-full-development-20261028T005622778442Z/association_pair_indices.csv").open(encoding="utf-8-sig")))
    pairs=pair_metadata(d,np.array([int(r["i"]) for r in raw]),np.array([int(r["j"]) for r in raw]))
    scenarios={s["id"]:s for s in json.loads((ROOT/"config/reliability_validation_v1.json").read_text(encoding="utf-8-sig"))["simulations"]["scenarios"]}
    selected=[]
    for line in (ROOT/source/"replications.jsonl").read_text(encoding="utf-8").splitlines():
        r=json.loads(line)
        if r["replication"]==0 and r["scenario"] in ("C00","C05","C09","C10"):selected.append(r)
    if len(selected)!=4:raise RuntimeError("Selected completed fits unavailable")
    bounds=[(0,.95)]*4+[(np.log(7),np.log(3650)),(np.log(1),np.log(1460))]
    rows=[];diagnostics=[];cpu0=time.process_time()
    for r in selected:
        sc=scenarios[r["scenario"]];rng=keyed_rng(0);rng.bit_generator.state=r["outer_state_before"]
        p=truth_margin(d,sc);y=generate_fast(d,p,sc,1,rng)[0]
        if __import__("hashlib").sha256(y.astype("u1").tobytes()).hexdigest()!=r["outcome_sha256"]:raise RuntimeError("Replay Y hash failed")
        margin=fit_margin(d,y,.5)
        if __import__("hashlib").sha256(margin["p"].astype("<f8").tobytes()).hexdigest()!=r["fitted_margin_sha256"]:raise RuntimeError("Margin replay failed")
        fun=association_objective(d,pairs,margin["p"],y);par=np.array(r["parameters"]);f,g=fun(par)
        residual=float(np.max(np.abs(par-project(par-g))))
        diagnostics.append(dict(scenario=sc["id"],projected_gradient_inf=residual,
            satisfies_mean_objective_tolerance_1e_minus6=residual<=1e-6,
            optimizer_success_is_not_identification=True,inactive_team_tau=bool(par[0]+par[1]<1e-7),
            inactive_common_tau=bool(par[3]<1e-7)))
        for coordinate,grid in ((4,[7,30,365,1460,3650]),(5,[1,30,365,1460])):
            active=(par[0]+par[1]>=1e-7) if coordinate==4 else par[3]>=1e-7
            for value in grid:
                if time.process_time()-cpu0>120:raise RuntimeError("Profile budget120 CPU seconds exceeded; preserve incomplete status")
                bb=bounds.copy();bb[coordinate]=(np.log(value),np.log(value));x=par.copy();x[coordinate]=np.log(value)
                opt=minimize(fun,x,jac=True,method="SLSQP",bounds=bb,
                    constraints=[dict(type="ineq",fun=lambda z:.95-z[:4].sum(),jac=lambda z:np.r_[-np.ones(4),0,0])],
                    options=dict(maxiter=300,ftol=1e-10))
                rows.append(dict(scenario=sc["id"],coordinate="team_tau" if coordinate==4 else "common_tau",active=active,
                    tau_days=value,success=bool(opt.success),objective=float(opt.fun),delta_mean_pair_NLL=float(opt.fun-f),
                    profile_role="identification diagnostic only; no chi-square likelihood-ratio CI for composite likelihood"))
    write_csv(out/"fit_profiles.csv",rows)
    write_json(target,dict(source=source,script_sha256=sha(Path(__file__)),diagnostics=diagnostics,
        profile_rows=len(rows),cpu_seconds=time.process_time()-cpu0,
        constraints="Weights simplex and tau bounds retained; inactive tau flatness is not evidence of an unidentified ACTIVE parameter.",
        confidence_set=False,formal_model_approval=False,actual_football_Y_fitted=False))
    print(json.dumps(dict(diagnostics=diagnostics,profile_rows=len(rows),cpu_seconds=time.process_time()-cpu0)))


if __name__=="__main__":main()
