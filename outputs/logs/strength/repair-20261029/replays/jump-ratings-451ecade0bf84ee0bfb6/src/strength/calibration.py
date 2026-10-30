"""Past-only regularized multiclass probability correction, not latent rerating.

Restricted log-probability affine calibration. An offset-only or common-slope
map is deliberately smaller than a free Dirichlet calibration matrix. Covariance
is a conditional Laplace approximation; projected two-logit Gaussian integration
does not account for historical model selection or misspecification.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.special import softmax,logsumexp
from datetime import date


def objective(theta,u,y,precision,temperature):
    slope=theta[2] if temperature else 1.
    logits=np.column_stack((u*slope+theta[:2],np.zeros(len(u))))
    probs=softmax(logits,axis=1)
    residual=probs[:,:2]-np.eye(3)[y,:2]
    prior=theta-np.array([0.,0.,1.])[:len(theta)]
    loss=float(np.sum(logsumexp(logits,axis=1)-logits[np.arange(len(y)),y])+.5*precision*(prior@prior))
    gradient=np.r_[residual.sum(axis=0),np.sum(residual*u)] if temperature else residual.sum(axis=0)
    return loss,gradient+precision*prior


def fit(probabilities,targets,method="temperature_offset",precision=8.,bounds=(.25,3.)):
    p=np.asarray(probabilities,dtype=float);y=np.asarray(targets,dtype=int)
    if p.shape!=(len(y),3) or len(y)==0 or not np.isfinite(p).all() or np.min(p)<=0:
        raise ValueError("Invalid calibration training data")
    if np.max(abs(p.sum(axis=1)-1))>1e-8 or np.any((y<0)|(y>2)):
        raise ValueError("Invalid probabilities/targets")
    temp=method=="temperature_offset"
    if method not in {"temperature_offset","offset"}:raise ValueError("Unknown calibration")
    u=np.log(p[:,:2]/p[:,2:]);initial=np.array([0.,0.,1.]) if temp else np.zeros(2)
    result=minimize(objective,initial,args=(u,y,precision,temp),jac=True,method="L-BFGS-B",
        bounds=[(None,None),(None,None)]+([tuple(bounds)] if temp else []),
        options=dict(ftol=1e-13,gtol=1e-8,maxiter=300))
    if not result.success and np.max(abs(result.jac))>1e-5:
        raise RuntimeError("Calibration optimizer failed: "+str(result.message))
    theta=result.x;logits=np.column_stack((u*(theta[2] if temp else 1)+theta[:2],np.zeros(len(u))))
    pp=softmax(logits,axis=1)[:,:2]
    dim=len(theta);design=np.zeros((len(y),2,dim));design[:,0,0]=1;design[:,1,1]=1
    if temp:design[:,:,2]=u
    weights=-pp[:,:,None]*pp[:,None,:]
    weights[:,0,0]+=pp[:,0];weights[:,1,1]+=pp[:,1]
    hessian=np.einsum('nia,nij,njb->ab',design,weights,design)+precision*np.eye(dim)
    cov=np.linalg.inv(hessian)
    if np.linalg.eigvalsh(cov).min()<=0:raise RuntimeError("Nonpositive calibration covariance")
    return dict(theta=theta.tolist(),covariance=cov.tolist(),method=method,count=len(y),
        objective=float(result.fun),gradient_max=float(np.max(abs(result.jac))),
        slope_at_boundary=bool(temp and min(abs(theta[2]-bounds[0]),abs(theta[2]-bounds[1]))<1e-7))


def predict(probabilities,state,order=9,integrate=True):
    p=np.asarray(probabilities,dtype=float)
    u=np.log(p[:,:2]/p[:,2:]);theta=np.array(state["theta"])
    dim=len(theta);temp=dim==3
    mu=u*(theta[2] if temp else 1)+theta[:2]
    if not integrate:return softmax(np.column_stack((mu,np.zeros(len(p)))),axis=1)
    design=np.zeros((len(p),2,dim));design[:,0,0]=1;design[:,1,1]=1
    if temp:design[:,:,2]=u
    cov=np.einsum('nia,ab,njb->nij',design,np.array(state["covariance"]),design)
    roots=np.linalg.cholesky(cov)
    nodes,weights=np.polynomial.hermite.hermgauss(order)
    xy=np.array([(a,b) for a in nodes for b in nodes])*np.sqrt(2)
    ww=np.outer(weights,weights).ravel()/np.pi
    values=mu[:,None,:]+np.einsum('nij,kj->nki',roots,xy)
    logits=np.concatenate((values,np.zeros((*values.shape[:2],1))),axis=2)
    return np.einsum('nkc,k->nc',softmax(logits,axis=2),ww)


def contextual_year(past_p,past_y,past_context,current_p,current_context,method,precision=8.,minimum=100,order=9):
    """Caller supplies past-only arrays; contexts are (friendly,neutral) tuples."""
    output=np.zeros_like(current_p);states=[]
    pc=np.asarray(past_context,dtype=int);cc=np.asarray(current_context,dtype=int)
    for friendly,neutral in sorted(set(map(tuple,cc))):
        mask=(pc[:,0]==friendly)&(pc[:,1]==neutral);scope="exact_context"
        if int(mask.sum())<minimum:mask=pc[:,0]==friendly;scope="friendly_parent"
        if int(mask.sum())<minimum:mask=np.ones(len(pc),dtype=bool);scope="pooled_parent"
        if mask.sum()==0:
            output[(cc[:,0]==friendly)&(cc[:,1]==neutral)]=current_p[(cc[:,0]==friendly)&(cc[:,1]==neutral)]
            continue
        state=fit(past_p[mask],past_y[mask],method,precision)
        selected=(cc[:,0]==friendly)&(cc[:,1]==neutral)
        output[selected]=predict(current_p[selected],state,order)
        states.append(dict(friendly=int(friendly),neutral=int(neutral),scope=scope,**state))
    return output,states


def online_offsets(probabilities,targets,dates,contexts,q=.02,order=9):
    """Zero-drift dynamic offsets: joint-day quadrature update after prediction.

The complete date's targets update a shared cell once, never before its forecasts.
Two-dimensional Gauss-Hermite moments are then Gaussian-projected. No latent
strength rerating is claimed. Calendar gaps change uncertainty, not the center.
"""
    p=np.asarray(probabilities);targets=np.asarray(targets);contexts=np.asarray(contexts)
    nodes,ww=np.polynomial.hermite.hermgauss(order)
    nodes=np.array([(a,b) for a in nodes for b in nodes])*np.sqrt(2)
    logw=np.log(np.outer(ww,ww).ravel()/np.pi)
    output=np.zeros_like(p);states={};diagnostics=[]
    begin=0
    while begin<len(dates):
        end=begin+1
        while end<len(dates) and dates[end]==dates[begin]:end+=1
        day=dates[begin]
        for key in sorted(set(map(tuple,contexts[begin:end]))):
            indices=np.array([i for i in range(begin,end) if tuple(contexts[i])==key])
            m,c,last,count=states.get(key,(np.zeros(2),np.eye(2)/8,None,0))
            if last is not None:c=c+q*((date.fromisoformat(day)-date.fromisoformat(last)).days/365.2425)*np.eye(2)
            points=m+nodes@np.linalg.cholesky(c).T
            logits=np.log(p[indices])[:,None,:]+np.concatenate((points,np.zeros((len(points),1))),axis=1)[None,:,:]
            lp=logits-logsumexp(logits,axis=2,keepdims=True)
            output[indices]=np.einsum('nkc,k->nc',np.exp(lp),np.exp(logw))
            weights=logw+lp[np.arange(len(indices)),:,targets[indices]].sum(axis=0)
            weights=np.exp(weights-logsumexp(weights))
            nm=weights@points;center=points-nm;nc=(center.T*weights)@center
            if np.linalg.eigvalsh(nc).min()<=0:raise RuntimeError('Online calibration covariance not PSD')
            states[key]=(nm,nc,day,count+len(indices))
            diagnostics.append(dict(date=day,friendly=int(key[0]),neutral=int(key[1]),matches=len(indices),
                history=count,prediction_cutoff=last or 'initial_prior',posterior_mean=nm.tolist(),posterior_covariance=nc.tolist()))
        begin=end
    return output,diagnostics
