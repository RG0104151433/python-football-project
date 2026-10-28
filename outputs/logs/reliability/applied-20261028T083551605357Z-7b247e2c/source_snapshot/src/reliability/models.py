"""Development implementations, not approved football inference.

The original A*Y statistic is never replaced by a fitted prediction. All random
streams are supplied by callers. No dense match-by-match covariance is built.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import hashlib
import heapq
import math
import time

import numpy as np
from scipy import sparse
from scipy.integrate import quad
from scipy.optimize import minimize
from scipy.special import expit, ndtr, ndtri, owens_t
from scipy.stats import beta, t as student_t


class ModelFailure(RuntimeError):
    pass


def keyed_rng(*labels):
    seed = int.from_bytes(hashlib.sha256("|".join(map(str, labels)).encode()).digest()[:16], "big")
    return np.random.default_rng(seed)


@dataclass
class FixedDesign:
    facts: list
    A: object
    targets: list
    families: dict
    unsupported: list

    def __post_init__(self):
        self.A = sparse.csr_matrix(self.A, dtype=float)
        self.n = len(self.facts)
        self.days = np.array([date.fromisoformat(r["date"]).toordinal() for r in self.facts])
        self.years = np.array([int(r["year"]) for r in self.facts])
        self.teams = sorted({r[k] for r in self.facts for k in ("home_team_id", "away_team_id")})
        idx = {x: i for i, x in enumerate(self.teams)}
        self.home = np.array([idx[r["home_team_id"]] for r in self.facts])
        self.away = np.array([idx[r["away_team_id"]] for r in self.facts])
        if np.any(self.home == self.away):
            raise ValueError("Self fixture")
        pairs = [tuple(sorted((h, a))) for h, a in zip(self.home, self.away)]
        pidx = {p: i for i, p in enumerate(sorted(set(pairs)))}
        self.pair = np.array([pidx[p] for p in pairs])
        self.npairs = len(pidx)
        self.eras = sorted({r["era"] for r in self.facts})
        cells = sorted({(r["era"], r["tournament_group"]) for r in self.facts})
        self.cells = cells
        self.cell = np.array([cells.index((r["era"], r["tournament_group"])) for r in self.facts])
        self.era = np.array([self.eras.index(r["era"]) for r in self.facts])
        self.slope = np.zeros((self.n, len(self.eras)))
        for e, era in enumerate(self.eras):
            # Calendar definition, never the observed subset's min/max year.
            start = int(era[:4]); end = min(start + 9, 2024)
            mask = self.era == e
            self.slope[mask, e] = (self.years[mask] - (start + end) / 2) / max(1, end - start)
        ci = sparse.csr_matrix((np.ones(self.n), (np.arange(self.n), self.cell)), shape=(self.n, len(cells)))
        team = sparse.csr_matrix((np.r_[np.ones(self.n), -np.ones(self.n)],
                                 (np.tile(np.arange(self.n), 2), np.r_[self.home, self.away])),
                                shape=(self.n, len(self.teams)))
        self.X = sparse.hstack((ci, team, sparse.csr_matrix(self.slope)), format="csr")
        self.scale = np.sqrt(np.asarray(self.A.multiply(self.A).sum(axis=1)).ravel())
        self.lo = np.asarray(self.A.minimum(0).sum(axis=1)).ravel()
        self.hi = np.asarray(self.A.maximum(0).sum(axis=1)).ravel()
        self.span = self.hi - self.lo
        self.order = np.lexsort((np.arange(self.n), self.days))
        self.team_events = self._team_events()
        self.unique_days, self.date_index = np.unique(self.days, return_inverse=True)

    def _team_events(self):
        nodes = sorted({(int(t), int(day)) for t, day in zip(np.r_[self.home, self.away], np.tile(self.days, 2))})
        index = {v: i for i, v in enumerate(nodes)}
        prev = np.full(len(nodes), -1, dtype=int)
        gaps = np.zeros(len(nodes)); levels = defaultdict(list); last = {}; depths = {}
        for j, (team, day) in enumerate(nodes):
            if team in last:
                prev[j] = last[team]; gaps[j] = day - nodes[prev[j]][1]
            depth = depths.get(team, -1) + 1
            levels[depth].append(j); depths[team] = depth; last[team] = j
        return dict(n=len(nodes), prev=prev, gaps=gaps, levels=[np.array(v) for v in levels.values()],
                    home=np.array([index[(int(h), int(d))] for h, d in zip(self.home, self.days)]),
                    away=np.array([index[(int(a), int(d))] for a, d in zip(self.away, self.days)]))

    def apply(self, ys):
        ys = np.asarray(ys)
        return (self.A @ ys.T).T if ys.ndim == 2 else self.A @ ys


def greedy_colors(design, L, indices=None, reverse=False):
    """Every color is a team-disjoint set with all date gaps strictly > L."""
    order = design.order if indices is None else np.array(sorted(indices, key=lambda i: (design.days[i], i)))
    if reverse:
        order = order[::-1]
    color = np.full(design.n, -1, dtype=int)
    if L == "all_dependent":
        color[order] = np.arange(len(order))
        return color
    # Time-blocked colors stay in a heap. This is exactly chronological
    # first-fit, without rescanning thousands of colors that cannot yet recur.
    teams = []; waiting=[]; available=[]
    for i in order:
        h, a, day = int(design.home[i]), int(design.away[i]), int(design.days[i])
        now=-day if reverse else day
        while waiting and waiting[0][0]<now:
            _,ready=heapq.heappop(waiting);heapq.heappush(available,ready)
        blocked=[];c=None
        while available:
            candidate=heapq.heappop(available)
            if h not in teams[candidate] and a not in teams[candidate]:
                c=candidate;break
            blocked.append(candidate)
        for candidate in blocked:heapq.heappush(available,candidate)
        if c is None:
            c=len(teams);teams.append(set())
        color[i]=c;teams[c].update((h,a));heapq.heappush(waiting,(now+L,c))
    return color


def coloring_valid(design, color, L):
    for c in np.unique(color[color >= 0]):
        ids = np.flatnonzero(color == c)
        if len(set(np.r_[design.home[ids], design.away[ids]])) != 2 * len(ids):
            return False
        if len(ids) > 1 and (L == "all_dependent" or np.min(np.diff(np.sort(design.days[ids]))) <= L):
            return False
    return True


def color_constant(a, color):
    ids = np.flatnonzero(a)
    if not len(ids):
        return 0.0
    if np.any(color[ids] < 0):
        raise ValueError("Uncolored nonzero coefficient")
    v = np.bincount(color[ids], weights=a[ids] ** 2)
    return float(np.sum(np.sqrt(v)) ** 2)


def graph_bounds(design, L, optimized=False):
    """Optimization is design-only: best valid coloring for each target.

    Selecting the minimum bound constant using no Y preserves its proof. This
    does not assert that the underlying independence graph is factually true.
    """
    started = time.process_time()
    global_colors = greedy_colors(design, L)
    if not coloring_valid(design, global_colors, L):
        raise ModelFailure("Invalid global coloring")
    constants = []; baseline = []; schemes = []
    for j in range(design.A.shape[0]):
        a = design.A.getrow(j).toarray().ravel()
        c0 = color_constant(a, global_colors)
        candidates = [(c0, "global_chronological")]
        if optimized and L != "all_dependent":
            ids = np.flatnonzero(a)
            for reverse in (False, True):
                colors = greedy_colors(design, L, ids, reverse)
                if not coloring_valid(design, colors, L):
                    raise ModelFailure("Invalid target-specific coloring")
                candidates.append((color_constant(a, colors), "target_reverse" if reverse else "target_chronological"))
        c, scheme = min(candidates)
        constants.append(c); baseline.append(c0); schemes.append(scheme)
    constants = np.array(constants)
    half = np.zeros(len(constants))
    for family, js in design.families.items():
        half[js] = np.sqrt(constants[js] / 2 * np.log(2 * len(js) / .05))
    return dict(C=constants, C_baseline=np.array(baseline), half=half, schemes=schemes,
                colors=int(global_colors.max() + 1), cpu_seconds=time.process_time() - started)


def clipped_intervals(design, estimates, half):
    return np.maximum(estimates - half, design.lo), np.minimum(estimates + half, design.hi)


def bvn_cdf(h, k, r):
    """Deterministic Owen-T identity, with adaptive tail quadrature fallback.

    No randomized multivariate-normal CDF occurs inside the objective.
    """
    h, k, r = np.broadcast_arrays(np.asarray(h, float), np.asarray(k, float), np.asarray(r, float))
    if np.any(np.abs(r) >= 1):
        raise ValueError("Nonsingular correlations required")
    den = np.sqrt(1 - r*r)
    hh = np.where(h == 0, 1, h); kk = np.where(k == 0, 1, k)
    result = .5*(ndtr(h)+ndtr(k)) - owens_t(h, (k/hh-r)/den) - owens_t(k, (h/kk-r)/den)
    result -= (1 - np.sign(h)*np.sign(k)) / 4
    result = np.where(h == 0, .5*ndtr(k) + owens_t(k, r/den), result)
    result = np.where(k == 0, .5*ndtr(h) + owens_t(h, r/den), result)
    # Cancellation can dominate rare quadrants. Evaluate their positive integral.
    bad = (result < 1e-12) | (result > np.minimum(ndtr(h), ndtr(k)) + 1e-12)
    if np.any(bad):
        result = result.copy()
        for ix in zip(*np.where(np.atleast_1d(bad))):
            flat = np.ravel_multi_index(ix, np.atleast_1d(bad).shape)
            a, b, rho = h.flat[flat], k.flat[flat], r.flat[flat]
            val, err = quad(lambda x: math.exp(-x*x/2) / math.sqrt(2*math.pi) * ndtr((b-rho*x)/math.sqrt(1-rho*rho)),
                            -np.inf, a, epsabs=1e-12, epsrel=1e-10, limit=100)
            if err > 1e-10 or val < 0:
                raise ModelFailure("Bivariate probability quadrature failure")
            result.flat[flat] = val
    return result


def bvn_density(h, k, r):
    return np.exp(-(h*h - 2*r*h*k + k*k)/(2*(1-r*r))) / (2*np.pi*np.sqrt(1-r*r))


def fit_margin(design, y, cell_ridge=0.0):
    nc = len(design.cells)
    penalty = np.r_[np.full(nc, cell_ridge), np.ones(design.X.shape[1]-nc)]
    def fun(b):
        eta = design.X @ b
        val = np.sum(np.logaddexp(0, eta)-y*eta) + .5*np.dot(penalty*b, b)
        grad = np.asarray(design.X.T @ (expit(eta)-y)) + penalty*b
        return float(val), grad
    result = minimize(fun, np.zeros(design.X.shape[1]), method="L-BFGS-B", jac=True,
                      options=dict(maxiter=300, gtol=1e-6, ftol=1e-14, maxls=40))
    counts = np.bincount(design.cell, minlength=nc)
    wins = np.bincount(design.cell, weights=y, minlength=nc)
    separated = np.flatnonzero((wins == 0) | (wins == counts)).tolist()
    raw = expit(design.X @ result.x)
    team_b = result.x[nc:nc+len(design.teams)]
    # Team contrasts are shift invariant; ridge gives the sum-zero minimizer.
    ok = bool(result.success and (cell_ridge > 0 or not separated))
    return dict(ok=ok, p=np.clip(raw, 1e-8, 1-1e-8), beta=result.x,
                status="ok" if ok else "separated_unpenalized_cell" if separated and cell_ridge == 0 else "optimizer_failure",
                diagnostic=dict(success=bool(result.success), message=str(result.message), iterations=int(result.nit),
                                gradient_max=float(np.max(np.abs(result.jac))), separated_cells=separated,
                                team_coefficient_sum=float(team_b.sum()), probability_clip_count=int(np.sum((raw<1e-8)|(raw>1-1e-8))),
                                cell_ridge=cell_ridge))


def pair_metadata(design, i, j):
    h, a, hh, aa = design.home[i], design.away[i], design.home[j], design.away[j]
    same = (h == hh).astype(float) + (a == aa)
    cross = (h == aa).astype(float) + (a == hh)
    gap = np.abs(design.days[i] - design.days[j]).astype(float)
    relation = np.where((h == hh)&(a == aa), 0,
                np.where((h == aa)&(a == hh), 1, np.where(same > 0, 2, np.where(cross > 0, 3, 4))))
    lag = np.select([gap == 0, gap <= 30, gap <= 365, gap <= 1460], [0, 1, 2, 3], default=4)
    return dict(i=np.asarray(i), j=np.asarray(j), gap=gap, minus=(same-cross)/2, plus=(same+cross)/2,
                pair=(design.pair[i] == design.pair[j]).astype(float), relation=relation, lag=lag)


def select_pairs(design, seed=20261028, proposals=1_000_000, cap=1000):
    rng = keyed_rng(seed, "metadata_pair_selection", design.n)
    if design.n * (design.n - 1) // 2 <= proposals:
        i, j = np.triu_indices(design.n, 1)
    else:
        draw = rng.integers(0, design.n, size=(proposals, 2))
        draw.sort(axis=1); draw = draw[draw[:, 0] != draw[:, 1]]
        keys = np.unique(draw[:, 0]*design.n + draw[:, 1]); i, j = keys//design.n, keys%design.n
    meta = pair_metadata(design, i, j)
    strata = meta["relation"]*5 + meta["lag"]
    keep = []; counts = {}
    for s in range(25):
        ids = np.flatnonzero(strata == s)
        hashes = [hashlib.sha256(f"{seed}|{design.facts[int(i[k])]['match_id']}|{design.facts[int(j[k])]['match_id']}".encode()).digest() for k in ids]
        chosen = sorted(range(len(ids)), key=lambda k: hashes[k])[:cap]
        keep.extend(ids[chosen].tolist()); counts[str(s)] = dict(proposed=len(ids), retained=len(chosen))
    keep = np.array(sorted(keep), dtype=int)
    result = pair_metadata(design, i[keep], j[keep]); result["counts"] = counts
    result["sha256"] = hashlib.sha256(np.column_stack((result["i"], result["j"])).astype("<i8").tobytes()).hexdigest()
    return result


def correlation_and_gradient(par, pairs):
    w = par[:4]; tau, tt = np.exp(par[4:])
    kt = np.exp(-pairs["gap"]/tau); ku = np.exp(-pairs["gap"]/tt)
    bases = np.column_stack((pairs["minus"]*kt, pairs["plus"]*kt, pairs["pair"], ku))
    rho = bases @ w
    dt = (w[0]*bases[:, 0]+w[1]*bases[:, 1])*pairs["gap"]/tau
    du = w[3]*ku*pairs["gap"]/tt
    return rho, np.column_stack((bases, dt, du))


def association_objective(design, pairs, p, y):
    sign = 2*np.asarray(y, float)-1
    si, sj = sign[pairs["i"]], sign[pairs["j"]]
    z = ndtri(p); h, k = si*z[pairs["i"]], sj*z[pairs["j"]]
    def fun(par):
        rho, grad = correlation_and_gradient(par, pairs)
        r = rho*si*sj
        prob = bvn_cdf(h, k, r)
        if np.any(prob <= 0) or np.any(~np.isfinite(prob)):
            raise ModelFailure("Nonpositive pair likelihood, no silent floor")
        score = bvn_density(h, k, r)*si*sj/prob
        # Mean objective has same optimizer; gradient tolerance is documented.
        return float(-np.mean(np.log(prob))), -(grad.T @ score)/len(prob)
    return fun


def fit_association(design, pairs, p, y, starts=9):
    fun = association_objective(design, pairs, p, y)
    vectors = [[.05,.05,.05,.05], [.2,.1,.1,.1], [.1,.1,.05,.25]]
    initial = [np.r_[v, np.log(tau), np.log(tau)] for v in vectors for tau in (30,365,1460)]
    if starts == 1:
        initial = [initial[4]]
    fits = []
    bounds = [(0,.95)]*4 + [(math.log(7),math.log(3650)), (math.log(1),math.log(1460))]
    for x in initial:
        try:
            opt = minimize(fun, x, jac=True, method="SLSQP", bounds=bounds,
                           constraints=[dict(type="ineq", fun=lambda v:.95-v[:4].sum(), jac=lambda v:np.r_[-np.ones(4),0,0])],
                           options=dict(maxiter=300, ftol=1e-10))
            par = opt.x.copy()
            if par[0]+par[1] < 1e-7: par[4] = math.log(365)
            if par[3] < 1e-7: par[5] = math.log(365)
            valid = bool(opt.success and np.isfinite(opt.fun) and np.all(par[:4]>=-1e-9) and par[:4].sum()<=.950000001)
            fits.append(dict(ok=valid, par=par, objective=float(opt.fun), iterations=int(opt.nit), message=str(opt.message)))
        except (ModelFailure, FloatingPointError, ValueError) as exc:
            fits.append(dict(ok=False, message=str(exc)))
    valid = [r for r in fits if r["ok"]]
    if not valid:
        return dict(ok=False, status="all_association_starts_failed", fits=fits)
    best = min(valid, key=lambda r:r["objective"])
    par = best["par"]
    h = 1e-4
    hess = np.column_stack([(fun(par+np.eye(6)[j]*h)[1]-fun(par-np.eye(6)[j]*h)[1])/(2*h) for j in range(6)])
    eig = np.linalg.eigvalsh((hess+hess.T)/2)
    # Identification is a warning, never silently converted into a proved CI.
    return dict(ok=True, status="development_fit_not_inference_approval", par=par, fits=fits,
                diagnostic=dict(best_objective=best["objective"], successful_starts=len(valid), attempted_starts=len(fits),
                                weight_boundary=[j for j in range(4) if par[j]<1e-6],
                                tau_team_days=float(np.exp(par[4])), tau_time_days=float(np.exp(par[5])),
                                curvature_eigenvalues=eig.tolist(), weak_curvature=bool(eig.min()<1e-6),
                                near_optimal_parameter_spread=(np.ptp(np.stack([v["par"] for v in valid if v["objective"]<=best["objective"]+1e-5]),axis=0)).tolist()))


def draw_team_process(design, B, tau, rng):
    ev = design.team_events
    values = rng.normal(size=(B, ev["n"]))
    rho = np.exp(-ev["gaps"]/tau)
    for ids in ev["levels"][1:]:
        values[:, ids] = values[:, ev["prev"][ids]]*rho[ids] + values[:, ids]*np.sqrt(-np.expm1(-2*ev["gaps"][ids]/tau))
    return values[:, ev["home"]], values[:, ev["away"]]


def draw_time_process(design, B, tau, rng):
    values = rng.normal(size=(B,len(design.unique_days)))
    for k in range(1,len(design.unique_days)):
        gap = design.unique_days[k]-design.unique_days[k-1]
        rho = np.exp(-gap/tau)
        values[:,k] = rho*values[:,k-1] + np.sqrt(-np.expm1(-2*gap/tau))*values[:,k]
    return values[:,design.date_index]


def generate(design, p, scenario, B, rng):
    w = scenario["latent"]
    innovation = np.full(design.n, w["e"])
    if scenario.get("time_loading"):
        loading = np.where(design.years<2000,.5,1.)
        innovation = 1-w["minus"]-w["time"]*loading**2
    else:
        loading = np.ones(design.n)
    latent = rng.normal(size=(B,design.n))*np.sqrt(innovation)
    for name in ("minus","plus"):
        if w[name]:
            h,a = draw_team_process(design,B,scenario.get("team_tau_days",365),rng)
            latent += np.sqrt(w[name]/2)*(h-a if name=="minus" else h+a)
    if w["pair"]:
        latent += np.sqrt(w["pair"])*rng.normal(size=(B,design.npairs))[:,design.pair]
    if w["time"]:
        kernel = scenario.get("time_kernel","none")
        if kernel=="OU":
            common = draw_time_process(design,B,scenario["time_tau_days"],rng)
        elif kernel=="one_global_normal":
            common = rng.normal(size=(B,1))
        elif kernel=="finite_gaussian_MA":
            L = scenario["time_range_days"]; base = int(design.days.min())-L
            eps = rng.normal(size=(B,int(design.days.max())-base+1))
            cumulative = np.column_stack((np.zeros(B),np.cumsum(eps,axis=1)))
            end = design.days-base+1; begin=end-L-1
            common = (cumulative[:,end]-cumulative[:,begin])/np.sqrt(L+1)
        else:
            raise ValueError("Unsupported nonzero time kernel:"+kernel)
        latent += np.sqrt(w["time"])*loading*common
    if w.get("synthetic_competition",0):
        groups = defaultdict(list)
        for i,r in enumerate(design.facts): groups[(r.get("tournament_name",r["tournament_group"]),r["year"])].append(i)
        ids = np.zeros(design.n,dtype=int); label=0
        for members in groups.values():
            members.sort(key=lambda i:(design.days[i],design.facts[i]["match_id"]))
            for start in range(0,len(members),20):
                ids[members[start:start+20]]=label; label+=1
        latent += np.sqrt(w["synthetic_competition"])*rng.normal(size=(B,label))[:,ids]
    if scenario.get("copula"):
        latent /= np.sqrt(rng.chisquare(5,size=(B,1))/5)
        z=student_t.ppf(p,5)
    else:
        z=ndtri(p)
    return (latent+z>0).astype(np.float64)


def scenario_from_fit(par):
    w=par[:4]
    return dict(latent=dict(zip(("minus","plus","pair","time","e"),[*w,max(.05,1-w.sum())])),
                team_tau_days=float(np.exp(par[4])),time_tau_days=float(np.exp(par[5])),time_kernel="OU")


def bootstrap_halfwidth(design, p, par, B, rng, batch=128):
    truth = design.apply(p); d=design.scale
    pivots={f:[] for f in design.families}
    scenario=scenario_from_fit(par)
    for offset in range(0,B,batch):
        values=design.apply(generate(design,p,scenario,min(batch,B-offset),rng))
        for f,js in design.families.items():
            active=np.array(js)[d[js]>0]
            pivots[f].extend(np.max(np.abs(values[:,active]-truth[active])/d[active],axis=1).tolist() if len(active) else [0]*len(values))
    half=np.zeros(len(d)); crit={}; rank=math.ceil((B+1)*.95)
    for f,js in design.families.items():
        c=float(np.sort(pivots[f])[rank-1]) if rank<=B else float("inf")
        crit[f]=c; half[js]=np.where(d[js]>0,c*d[js],0)
    return half,dict(B=B,rank=rank,critical=crit,design_scale_not_SE=True)


def exact_mc_limits(k,R):
    return dict(estimate=k/R,lower99=float(beta.ppf(.01,k,R-k+1)) if k else 0.,
                upper99=float(beta.ppf(.99,k+1,R-k)) if k<R else 1.)


def truth_margin(design, scenario, seed=20261028):
    label=scenario["margin"]
    if label.startswith("constant_"):
        return np.full(design.n,float(label.removeprefix("constant_")))
    def u(name):
        return (int(hashlib.sha256(f"{seed}|{scenario['id']}|{name}".encode()).hexdigest()[:16],16)+.5)/2**64
    nc=len(design.cells)
    cells=np.array([.8*(u("cell:"+"/".join(c))-.5) for c in design.cells])
    teams=np.array([1.5*(u("team:"+x)-.5) for x in design.teams]);teams-=teams.mean()
    slopes=np.array([.4*(u("slope:"+x)-.5) for x in design.eras])
    eta=design.X@np.r_[cells,teams,slopes]
    if "omitted" in label:
        interaction=np.array([[u("interaction:"+e+":"+t)-.5 for t in design.teams] for e in design.eras])
        interaction-=interaction.mean(axis=1,keepdims=True)
        eta+=interaction[design.era,design.home]-interaction[design.era,design.away]
    return expit(eta)
