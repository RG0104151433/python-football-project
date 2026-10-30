"""Independent projected Gauss-Hermite/count reference, including next-outcome probability."""
from pathlib import Path
import itertools
import json
import math
import sys
import numpy as np
from scipy.special import ndtr
from scipy.stats import poisson
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.collapsed_jump import jump_update,count_weights
from src.strength.io import config,publish
from src.strength.filter import probabilities
from src.data_contract import file_hash,write_json


def reference(mean,cov,A,outcomes,kappas,mus,jv,delta,next_a,order):
    joint=np.vstack([A,next_a]);meanp=joint@mean
    total=sum(mus);cap=len(count_weights(total,1e-11))-1
    zsum=0.;prediction=np.zeros(3)
    nodes,weights=np.polynomial.hermite.hermgauss(order)
    for n in range(cap+1):
        for choices in itertools.combinations_with_replacement(range(len(mus)),n):
            count=np.bincount(choices,minlength=len(mus))
            logp=-total+sum(int(k)*math.log(mu)-math.lgamma(int(k)+1) for k,mu in zip(count,mus) if mu>0)
            cc=cov.copy()
            for i,k in enumerate(count):cc[i,i]+=k*jv
            pc=joint@cc@joint.T;ev,U=np.linalg.eigh(pc);keep=ev>1e-12
            grid=np.array(list(itertools.product(range(order),repeat=int(keep.sum()))))
            points=np.sqrt(2)*nodes[grid]@(U[:,keep]*np.sqrt(ev[keep])).T+meanp
            ww=np.prod(weights[grid]/np.sqrt(np.pi),axis=1)*math.exp(logp)
            for i,y in enumerate(outcomes):
                u=points[:,i]
                pp=[ndtr(u-delta),ndtr(delta-u)-ndtr(-delta-u),ndtr(-delta-u)][y]
                ww*=kappas[i]*pp+(1-kappas[i])/3
            zsum+=ww.sum();u=points[:,-1]
            pn=np.array([ndtr(u-delta),ndtr(delta-u)-ndtr(-delta-u),ndtr(-delta-u)]).T
            prediction+=ww@pn
    return prediction/zsum


def main():
    protocol=dict(case_means=[0.,.7,1.8],outcomes=[[0,1],[2,0]],shared_and_disjoint=True,
        orders=[21,31],probability_gate=.01,reference_count_tail=1e-11,
        scope='finite predeclared local fixtures; no exact full-history posterior claim')
    write_json(ROOT/'config/strength_jump_reference.json',protocol)
    cfg=config();records=[]
    for shared in (False,True):
        teams=['A','B','C'] if shared else ['A','B','C','D'];index={t:i for i,t in enumerate(teams)}
        games=[dict(home='A',away='B',friendly=False),dict(home='B' if shared else 'C',away='C' if shared else 'D',friendly=True)]
        n=len(teams)+1;A=np.zeros((2,n))
        for k,g in enumerate(games):A[k,index[g['home']]]=1;A[k,index[g['away']]]=-1;A[k,-1]=1
        mus={t:.01+.003*i for i,t in enumerate(teams)};C=np.eye(n)*.4;C[-1,-1]=.1
        for meanvalue in protocol['case_means']:
            mean=np.zeros(n);mean[0]=meanvalue;mean[-1]=.4
            for outcomes in protocol['outcomes']:
                gs=[dict(g,outcome=y,match_id=str(i)) for i,(g,y) in enumerate(zip(games,outcomes))]
                p=dict(q=.03,jump_rate=.08,jump_sd=1.2,delta=.4,alpha=.65,epsilon=.05)
                mm,cc,_,_=jump_update(mean,C,A,gs,index,mus,p,dict(cfg['numerics'],poisson_tail_tolerance=1e-13,ep_tolerance=1e-8,ep_max_iter=300))
                next_a=np.zeros(n);next_a[index['A']]=1;next_a[index['C']]=-1;next_a[-1]=1
                raw=probabilities(float(next_a@mm),float(next_a@cc@next_a),.4,1.)
                rr=[reference(mean,C,A,outcomes,[.95,.95*.65],list(mus.values()),1.44,.4,next_a,k) for k in protocol['orders']]
                error=float(np.max(abs(raw-rr[-1])));refgap=float(np.max(abs(rr[0]-rr[1])))
                records.append(dict(shared=shared,mean=meanvalue,outcomes=str(outcomes),
                    max_probability_error=error,reference_order_gap=refgap,passed=error<=.01 and refgap<=.001))
                print(records[-1],flush=True)
    folder,_=publish('collapsed-jump-reference',dict(protocol=protocol,runner_sha=file_hash(Path(__file__))),
        csvs={'cases.csv':records},jsons={'report.json':dict(passed=all(r['passed'] for r in records),protocol=protocol)},
        texts={'runner_snapshot.py':Path(__file__).read_text(encoding='utf-8')})
    print('REFERENCE',folder.relative_to(ROOT).as_posix(),flush=True)


if __name__=='__main__':main()
