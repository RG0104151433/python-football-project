const result = (function frameworkMathU(){
'use strict';
const phi=x=>Number.isFinite(x)?Math.exp(-x*x/2)/Math.sqrt(2*Math.PI):0;
const nodes=[],weights=[],order=32;
for(let i=1;i<=order;i++){let z=Math.cos(Math.PI*(i-.25)/(order+.5)),dp=0;for(let k=0;k<50;k++){let p0=1,p1=z;for(let j=2;j<=order;j++){const p=((2*j-1)*z*p1-(j-1)*p0)/j;p0=p1;p1=p;}dp=order*(z*p1-p0)/(z*z-1);const next=z-p1/dp;if(Math.abs(next-z)<2e-15){z=next;break;}z=next;}let p0=1,p1=z;for(let j=2;j<=order;j++){const p=((2*j-1)*z*p1-(j-1)*p0)/j;p0=p1;p1=p;}dp=order*(z*p1-p0)/(z*z-1);nodes.push(z);weights.push(2/((1-z*z)*dp*dp));}
function Phi(x){if(x===Infinity)return 1;if(x===-Infinity)return 0;const a=Math.abs(x);if(a>12)return x>0?1:0;let s=0;for(let k=0;k<order;k++)s+=weights[k]*phi(a*(nodes[k]+1)/2);return Math.max(0,Math.min(1,.5+(x<0?-1:1)*a*s/2));}
function probs(M,c,delta,kappa=.9){const A=Phi((-delta-M)/c),H=1-Phi((delta-M)/c),D=1-H-A;return [H,D,A].map(p=>kappa*p+(1-kappa)/3);}
const delta=.3,kappa=.95,muI=1,muJ=.2,varI=.4,varJ=.6,h=.25;
const M=muI-muJ+h,c=Math.sqrt(1+varI+varJ);
const pA=Phi((-delta-M)/c),gA=-phi((-delta-M)/c)/pA,rA=kappa*pA/(kappa*pA+(1-kappa)/3);
const increments={home:rA*varI/c*gA,away:-rA*varJ/c*gA};
const forward=probs(M,c,delta),reverse=probs(-M,c,delta);
function poisson(n,m){let p=Math.exp(-m);for(let j=1;j<=n;j++)p*=m/j;return p;}
let convolutionError=0;const m1=.14,m2=.27;for(let n=0;n<=14;n++){let s=0;for(let j=0;j<=n;j++)s+=poisson(j,m1)*poisson(n-j,m2);convolutionError=Math.max(convolutionError,Math.abs(s-poisson(n,m1+m2)));}
let mixtureVariance=0,mass=0;const q=.04,lambda=.2,J2=2.5,dt=.7;for(let n=0;n<=30;n++){const p=poisson(n,lambda*dt);mass+=p;mixtureVariance+=p*(q*dt+n*J2);}const varianceFormula=(q+lambda*J2)*dt;
const gridN=12000,left=-15,step=30/gridN,grid=Array.from({length:gridN+1},(_,i)=>left+i*step);
function prior(m,v){const d=grid.map(x=>phi((x-m)/Math.sqrt(v))/Math.sqrt(v));const z=d.reduce((a,b)=>a+b,0);return d.map(p=>p/z);}
const coreProb=grid.map(x=>probs(x,1,delta,kappa));
function moments(d){let m=0;for(let i=0;i<d.length;i++)m+=grid[i]*d[i];let v=0;for(let i=0;i<d.length;i++)v+=(grid[i]-m)**2*d[i];return {mean:m,variance:v};}
function sequence(outcomes){let ds=[prior(1.5,.12),prior(1.5,2.62)],w=[.95,.05];const trace=[];for(const y of outcomes){const j={H:0,D:1,A:2}[y],Z=ds.map(d=>d.reduce((s,p,i)=>s+p*coreProb[i][j],0));const norm=w[0]*Z[0]+w[1]*Z[1],oldOdds=w[1]/w[0],newOdds=oldOdds*Z[1]/Z[0];w=w.map((p,i)=>p*Z[i]/norm);ds=ds.map((d,b)=>d.map((p,i)=>p*coreProb[i][j]/Z[b]));const b=ds.map(moments),mean=w[0]*b[0].mean+w[1]*b[1].mean,variance=w.reduce((s,p,i)=>s+p*(b[i].variance+(b[i].mean-mean)**2),0);if(Math.abs(w[1]/w[0]-newOdds)>1e-9)throw Error('Odds recursion mismatch');trace.push({outcome:y,stable_predictive:Z[0],changed_predictive:Z[1],changed_weight:w[1],stable_mean:b[0].mean,changed_mean:b[1].mean,mixture_mean:mean,mixture_variance:variance});}return trace;}
const sustained=sequence(['A','A','A','A','A']),isolated=sequence(['A','H','H','H','H']);
const illustrativeOdds=[];let odds=.05/.95;for(let k=1;k<=4;k++){odds*=.6/.1;illustrativeOdds.push({k,changed_weight:odds/(1+odds)});}
const I=.5,smallV=.12,largeV=2.62,oldWeightSmall=1/(1+smallV*I),oldWeightLarge=1/(1+largeV*I);
const checks={away_win_updates_both_sides:increments.home<0&&increments.away>0,label_swap_symmetry:Math.abs(forward[0]-reverse[2])<1e-12&&Math.abs(forward[1]-reverse[1])<1e-12,poisson_time_partition_consistency:convolutionError<1e-12,jump_variance_identity:Math.abs(mixtureVariance-varianceFormula)<1e-12&&Math.abs(mass-1)<1e-12,sustained_support_exceeds_isolated:sustained.at(-1).changed_weight>isolated.at(-1).changed_weight,sustained_changed_branch_adapts_faster_than_stable:sustained.at(-1).changed_mean<sustained.at(-1).stable_mean,larger_prior_uncertainty_reduces_old_weight:oldWeightLarge<oldWeightSmall};if(Object.values(checks).some(v=>!v))throw Error('Structural check failed');
return {schema_version:1,scope:'Mathematical identities and hypothetical persistent-branch Gaussian-grid illustration; no football data, no production rating solver, no detection-rate estimate',cdf:'32-node Gauss-Legendre normal CDF',grid:{left,right:15,intervals:gridN,initial_mean:1.5,stable_variance:.12,shift_branch_variance:2.62,shift_prior_weight:.05,delta,kappa,extra_shifts_during_sequence:false},away_increments:increments,poisson_convolution_max_error:convolutionError,variance_check:{numerical:mixtureVariance,formula:varianceFormula},sustained,isolated,illustrative_constant_predictive_odds:illustrativeOdds,local_gaussian_memory_example:{information:I,small_prior_variance:smallV,large_prior_variance:largeV,old_weight_small:oldWeightSmall,old_weight_large:oldWeightLarge},checks};
})();
console.log(JSON.stringify(result, null, 2));
