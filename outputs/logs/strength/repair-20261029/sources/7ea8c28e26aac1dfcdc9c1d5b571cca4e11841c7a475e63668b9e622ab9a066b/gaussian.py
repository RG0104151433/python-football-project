"""Efficient joint Gaussian special case of the same rating model (lambda=0).

No diagonal-independence shortcut. Full covariance is retained. Single-game
updates are exact tilted moments followed by Gaussian projection; multi-game
dates use the same parallel EP as the original pilot. PSD is checked periodically
and at checkpoints rather than doing an O(n^3) eigenproblem for every child.
"""
from __future__ import annotations

from datetime import date
import math
import copy
import numpy as np

from .filter import batch_update, outcome_moments, probabilities, NumericalFailure


class GaussianStrengthFilter:
    def __init__(self, teams, params, numerics, team_variance=1.0, home_variance=.25):
        if params["jump_rate"] != 0:
            raise ValueError("Gaussian special case requires jump_rate=0")
        self.teams = sorted(set(teams))
        if not self.teams or min(team_variance,home_variance)<=0 or params["q"]<0 or params["delta"]<=0:
            raise ValueError("Invalid roster, prior or diffusion")
        if not 0<params["alpha"]<1 or not 0<=params["epsilon"]<1:
            raise ValueError("Invalid outcome mixture")
        self.index = {t: i for i, t in enumerate(self.teams)}
        self.params, self.numerics = dict(params), dict(numerics)
        self.home_dimensions = 2 if params.get("home_by_type",False) else 1
        if params.get("home_q",0)<0:
            raise ValueError("Negative home diffusion")
        self.mean = np.zeros(len(self.teams)+self.home_dimensions)
        self.cov = np.diag([team_variance]*len(self.teams)+[home_variance]*self.home_dimensions)
        self.last, self.counts = {}, {t: 0 for t in self.teams}
        self.last_day, self.days = None, 0
        self.parent = {t: t for t in self.teams}
        self.diagnostics = []

    def find(self, t):
        while self.parent[t] != t:
            self.parent[t] = self.parent[self.parent[t]]
            t = self.parent[t]
        return t

    def day(self, day, games):
        if not games or self.last_day is not None and day <= self.last_day:
            raise ValueError("Complete batches must strictly advance date")
        games = sorted(games, key=lambda g: g["match_id"])
        if len({g["match_id"] for g in games}) != len(games):
            raise ValueError("Duplicate match ID")
        active = {g[k] for g in games for k in ("home","away")}
        if not active.issubset(self.index):
            raise ValueError("Unknown team")
        for t in sorted(active):
            elapsed = (date.fromisoformat(day)-date.fromisoformat(self.last.get(t,day))).days/365.2425
            self.cov[self.index[t],self.index[t]] += self.params["q"]*elapsed
        if self.last_day is not None:
            dt=(date.fromisoformat(day)-date.fromisoformat(self.last_day)).days/365.2425
            for j in range(len(self.teams),len(self.mean)):
                self.cov[j,j] += self.params.get("home_q",0)*dt
        design = np.zeros((len(games),len(self.mean)))
        kappas = []
        for k,g in enumerate(games):
            if g["home"] == g["away"] or g["venue"] not in {-1,0,1} or g["outcome"] not in {0,1,2}:
                raise ValueError("Invalid game")
            h=len(self.teams)+(int(g["friendly"]) if self.home_dimensions==2 else 0)
            design[k,self.index[g["home"]]],design[k,self.index[g["away"]]],design[k,h] = 1,-1,g["venue"]
            kappas.append((1-self.params["epsilon"])*(self.params["alpha"] if g["friendly"] else 1))
        cross = self.cov@design.T
        projected_mean = design@self.mean
        projected_variance = np.sum(design*cross.T,axis=1)
        rows = []
        for k,g in enumerate(games):
            i,j = self.index[g["home"]],self.index[g["away"]]
            h=len(self.teams)+(int(g["friendly"]) if self.home_dimensions==2 else 0)
            p = probabilities(projected_mean[k],projected_variance[k],self.params["delta"],kappas[k])
            gapv = self.cov[i,i]+self.cov[j,j]-2*self.cov[i,j]
            rows.append(dict(match_id=g["match_id"],date=day,home=g["home"],away=g["away"],
                home_mean=float(self.mean[i]),away_mean=float(self.mean[j]),
                home_variance=float(self.cov[i,i]),away_variance=float(self.cov[j,j]),
                home_away_covariance=float(self.cov[i,j]),difference=float(self.mean[i]-self.mean[j]),
                difference_variance=float(gapv),home_term=float(self.mean[h]),
                home_term_variance=float(self.cov[h,h]),venue=g["venue"],friendly=g["friendly"],
                p_home=float(p[0]),p_draw=float(p[1]),p_away=float(p[2]),
                home_history=self.counts[g["home"]],away_history=self.counts[g["away"]],
                home_days_since_last=(date.fromisoformat(day)-date.fromisoformat(self.last[g["home"]])).days if g["home"] in self.last else None,
                away_days_since_last=(date.fromisoformat(day)-date.fromisoformat(self.last[g["away"]])).days if g["away"] in self.last else None,
                cold_start=self.counts[g["home"]]<5 or self.counts[g["away"]]<5,
                previously_disconnected=self.find(g["home"])!=self.find(g["away"]),
                outcome_index=g["outcome"],prediction_cutoff=self.last_day or "initial_prior",
                prediction_basis="fixed_rule_pre_day_full_joint_covariance"))
        if len(games)==1:
            _,_,_,gradient,curvature = outcome_moments(projected_mean[0],projected_variance[0],
                games[0]["outcome"],self.params["delta"],kappas[0])
            self.mean += cross[:,0]*gradient
            self.cov += np.outer(cross[:,0],cross[:,0])*curvature
            iterations=0
        else:
            self.mean,self.cov,_,diag = batch_update(self.mean,self.cov,design,
                [g["outcome"] for g in games],kappas,self.params["delta"],self.numerics)
            iterations=diag["iterations"]
        self.cov=(self.cov+self.cov.T)/2
        if not np.isfinite(self.mean).all() or not np.isfinite(self.cov).all() or np.diag(self.cov).min()<=0:
            raise NumericalFailure("Invalid Gaussian state")
        self.days += 1
        checked = self.days%self.numerics.get("psd_check_every",50)==0
        mineig = float(np.linalg.eigvalsh(self.cov).min()) if checked else None
        if checked and mineig < -self.numerics["psd_tolerance"]:
            raise NumericalFailure("Gaussian state not PSD")
        for g in games:
            self.counts[g["home"]]+=1
            self.counts[g["away"]]+=1
            a,b=self.find(g["home"]),self.find(g["away"])
            self.parent[a]=b
        for t in active:
            self.last[t]=day
        self.last_day=day
        self.diagnostics.append(dict(date=day,matches=len(games),ep_iterations=iterations,
            minimum_eigenvalue=mineig,psd_checked=checked))
        return rows

    def state(self):
        eig = float(np.linalg.eigvalsh(self.cov).min())
        if eig < -self.numerics["psd_tolerance"]:
            raise NumericalFailure("Checkpoint covariance not PSD")
        return dict(schema_version="strength-gaussian-v1",teams=list(self.teams),
            params=copy.deepcopy(self.params),numerics=copy.deepcopy(self.numerics),
            mean=self.mean.tolist(),cov=self.cov.tolist(),last=self.last.copy(),counts=self.counts.copy(),
            parent=self.parent.copy(),last_day=self.last_day,days=self.days,minimum_eigenvalue=eig,
            unobserved_teams="prior placeholders only; never present as historical rankings")

    @classmethod
    def restore(cls,s):
        if s["schema_version"]!="strength-gaussian-v1":
            raise ValueError("Unknown state")
        result=cls(s["teams"],s["params"],s["numerics"])
        result.mean,result.cov=np.array(s["mean"]),np.array(s["cov"])
        result.last,result.counts,result.parent=s["last"].copy(),s["counts"].copy(),s["parent"].copy()
        result.last_day,result.days=s["last_day"],s["days"]
        n=len(result.teams)+result.home_dimensions
        if result.mean.shape!=(n,) or result.cov.shape!=(n,n):
            raise ValueError("Bad state shape")
        if not np.isfinite(result.mean).all() or not np.isfinite(result.cov).all():
            raise ValueError("Nonfinite state")
        if np.max(abs(result.cov-result.cov.T))>1e-9:
            raise ValueError("Asymmetric state covariance")
        if set(result.counts)!=set(result.teams) or set(result.parent)!=set(result.teams):
            raise ValueError("State roster mismatch")
        if any(t not in result.index or day>result.last_day for t,day in result.last.items()):
            raise ValueError("Checkpoint contains future last-observation date")
        if any(not isinstance(v,int) or v<0 for v in result.counts.values()):
            raise ValueError("Invalid checkpoint history counts")
        if any(p not in result.parent for p in result.parent.values()):
            raise ValueError("Invalid checkpoint connection graph")
        for t in result.teams:
            seen=set();node=t
            while result.parent[node]!=node:
                if node in seen:raise ValueError("Checkpoint graph cycle")
                seen.add(node);node=result.parent[node]
        result.state()
        return result
