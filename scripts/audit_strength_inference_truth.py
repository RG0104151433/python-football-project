"""Independent convex Newton reference and block-jackknife MC diagnostics."""
from pathlib import Path
import json,os,sys
import numpy as np
from scipy.optimize import minimize
from scipy.special import log_ndtr
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_inference.comparison import protocol
from src.strength_inference.fast import FrozenTargets
from src.data_contract import write_json,file_hash


def independent_projection(x,p):
    def fun(beta):
        eta=x@beta;lp=log_ndtr(eta);lq=log_ndtr(-eta);density=-eta*eta/2-.5*np.log(2*np.pi)
        plus=np.exp(density-lp);minus=np.exp(density-lq)
        loss=-float(np.mean(p*lp+(1-p)*lq));grad=x.T@((1-p)*minus-p*plus)/len(x)
        weights=p*plus*(eta+plus)+(1-p)*minus*(minus-eta)
        h=(x.T*weights)@x/len(x)
        return loss,grad,h
    result=minimize(lambda b:fun(b)[:2],np.zeros(x.shape[1]),jac=True,hess=lambda b:fun(b)[2],
        method='trust-exact',options=dict(gtol=1e-10,maxiter=500))
    loss,gradient,h=fun(result.x)
    if max(abs(gradient))>1e-7:raise ValueError('INDEPENDENT_NEWTON_FAILED')
    return result.x,float(max(abs(gradient))),float(np.linalg.eigvalsh(h).min())


if __name__=='__main__':
    cfg,c,folder=protocol();operator=FrozenTargets(c);x=operator.x
    m3=json.loads((ROOT/c['cfg']['analysis']/'models.json').read_text())['M3_nested'];details=[]
    for sc in cfg['scenarios']:
        truth=json.loads((folder/sc['id']/'truth.json').read_text());ps=[]
        for seed in range(*sc['truth_seeds']):
            with np.load(folder/'worlds'/sc['id']/'truth'/f'{seed}.npz') as ar:ps.append(ar['true_p'])
        ps=np.array(ps);beta,grad,eig=independent_projection(x,ps.mean(axis=0))
        reference,jac=operator.evaluate(beta,m3['theta'],c['rows'],True)
        original,_=operator.evaluate(truth['theta_M0'],m3['theta'],c['rows'])
        # Directional check covers both models, sparse mixtures and log-slope.
        rng=np.random.default_rng(910001);direction=rng.normal(size=jac.shape[1]);direction/=np.linalg.norm(direction)
        p=len(beta);step=1e-5;tt=np.array(m3['theta'])
        plus,_=operator.evaluate(beta+step*direction[:p],tt+step*direction[p:],c['rows'])
        minus,_=operator.evaluate(beta-step*direction[:p],tt-step*direction[p:],c['rows'])
        directional=float(max(abs((plus-minus)/(2*step)-jac@direction)))
        deletion=[]
        for block in np.array_split(np.arange(len(ps)),8):
            chosen=np.ones(len(ps),bool);chosen[block]=False
            b,_,_=independent_projection(x,ps[chosen].mean(axis=0));value,_=operator.evaluate(b,m3['theta'],c['rows'])
            deletion.append(value)
        deletion=np.array(deletion);jack_se=np.sqrt(7/8*np.sum((deletion-deletion.mean(axis=0))**2,axis=0))
        jack_bias=7*(deletion.mean(axis=0)-reference)
        intended=np.array([r['effect_size_axis']=='paired_change' and r['target_id'].startswith(('Q1:','Q2:')) for r in c['registry']])
        linearse=np.array(truth['target_MC_standard_errors_at_real_reference_pp'])
        covariance=np.array(truth['MC_covariance_M0'])
        details.append(dict(scenario=sc['id'],independent_solver_max_parameter_difference=float(max(abs(beta-truth['theta_M0']))),
            independent_solver_max_target_difference_pp=float(max(abs(reference-original))),newton_gradient=grad,minimum_curvature=eig,
            sparse_directional_gradient_error=directional,MC_covariance_min_eigenvalue=float(np.linalg.eigvalsh(covariance).min()),
            era_type_MC_linear_se_pp=linearse[intended].tolist(),era_type_MC_jackknife_se_pp=jack_se[intended].tolist(),
            era_type_MC_jackknife_bias_pp=jack_bias[intended].tolist(),
            jackknife_to_linear_ratios=(jack_se[intended]/linearse[intended]).tolist(),
            passed=bool(max(abs(reference-original))<2e-5 and directional<2e-6 and eig>0 and np.linalg.eigvalsh(covariance).min()>-1e-8)))
        print('TRUTH_AUDIT_SCENARIO',sc['id'],details[-1],flush=True)
    report=dict(passed=all(d['passed'] for d in details),details=details,independent_solvers=True,
        jackknife_is_empirical_diagnostic_not_finite_sample_certificate=True,source_sha256=file_hash(Path(__file__)))
    write_json(ROOT/'outputs/logs/strength_inference/truth_audit.json',report)
    if not report['passed']:raise SystemExit(1)
