"""Joint retrospective mean/wave fit; no football confidence intervals yet."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
from pathlib import Path
import sys
import json
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from scripts import develop_reliability_joint as api
from src.reliability.experiment import write_json,write_csv
from src.reliability.guard import protect_scale
from src.reliability.design import sha


def main():
    base=ROOT/"outputs/logs/reliability/joint-final-20261028"
    folder=base/"joint_fit"
    if folder.exists():raise RuntimeError("Preserve original joint fit")
    folder.mkdir(parents=True)
    cfg="config/reliability_joint_v11.json";api.initialize(cfg)
    d=api.WORK["d"];model=api.WORK["model"]
    choice=json.loads((base/"model_selection.json").read_text(encoding="utf-8"))
    name=choice["selected_model"];eta=float(name.split("@")[1]);cpu=time.process_time()
    y=np.array([int(r["home_win"]) for r in d.facts],float)
    fit=model.fit(y,coarse=True);fit=protect_scale(fit,api.WORK["guard"],eta)
    joint=model.joint_gls(y,fit["theta"],rtol=1e-8,maxiter=2000)
    common=sum((v for label,v in joint["components"].items() if label.startswith("time:")),np.zeros(d.n))
    other=sum((v for label,v in joint["components"].items() if not label.startswith("time:")),np.zeros(d.n))
    reconstructed=joint["mean"]+common+other+(fit["theta"][0]+joint["noise_ridge"])*joint["alpha"]
    error=float(np.linalg.norm(y-reconstructed)/max(1,np.linalg.norm(y)))
    orthogonal=float(np.max(np.abs(d.X.T@joint["alpha"])))
    if error>1e-6 or orthogonal>1e-5:raise RuntimeError("Joint equation reconstruction failed")
    write_csv(folder/"variance_components.csv",[dict(kernel=k,working_variance_component=float(v),
        scope="retrospective second-moment nuisance fit; not a proved physical variance") for k,v in zip(model.labels,fit["theta"])])
    write_csv(folder/"mean_and_common_wave.csv",[dict(match_id=r["match_id"],date=r["date"],observed_home_win=int(y[i]),
        joint_mean=float(joint["mean"][i]),common_wave=float(common[i]),other_random_components=float(other[i]),
        working_predictor=float(joint["mean"][i]+common[i]+other[i]),
        is_probability_forecast=False) for i,r in enumerate(d.facts)])
    write_csv(folder/"target_scales.csv",[dict(target_id=tid,original_point_estimate=float(d.apply(y)[j]),
        working_variance=float(model.target_variance[j]@fit["theta"]),protected_scale=float(fit["scale"][j]),
        is_standard_error=False,real_confidence_interval_generated=False) for j,tid in enumerate(d.targets)])
    summary=dict(selected_model=name,n=d.n,supported_targets=len(d.targets),unsupported_targets=len(d.unsupported),
        cpu_seconds=time.process_time()-cpu,GLS_iterations=joint["iterations"],
        relative_projected_equation_error=joint["relative_equation_residual"],
        relative_joint_reconstruction_error=error,mean_score_orthogonality_max=orthogonal,
        mean_outside_unit_interval=int(np.sum((joint["mean"]<0)|(joint["mean"]>1))),
        predictor_is_not_probability=True,noise_ridge=joint["noise_ridge"],
        scope="Joint GLS/BLUP working decomposition; no causal/pre-match/physical-state identification claim; scale guard separate from variance parameter fit",
        real_football_intervals=False,human_review="not_performed",
        source_sha256={p:sha(ROOT/p) for p in (cfg,"src/reliability/joint.py","src/reliability/guard.py","scripts/fit_joint_mean_wave.py")})
    summary["outputs"]={p.relative_to(ROOT).as_posix():sha(p) for p in folder.iterdir() if p.is_file()}
    write_json(folder/"manifest.json",summary)
    print(json.dumps(summary))


if __name__=="__main__":main()
