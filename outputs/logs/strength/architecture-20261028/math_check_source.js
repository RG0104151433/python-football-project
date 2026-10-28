const result = (function () {
'use strict';
const normalPdf = x => Number.isFinite(x) ? Math.exp(-x*x/2)/Math.sqrt(2*Math.PI) : 0;
const nodes=[], weights=[], order=32;
for(let i=1;i<=order;i++){
 let z=Math.cos(Math.PI*(i-.25)/(order+.5)), derivative=0;
 for(let k=0;k<50;k++){
  let p0=1,p1=z;
  for(let j=2;j<=order;j++){const p=((2*j-1)*z*p1-(j-1)*p0)/j;p0=p1;p1=p;}
  derivative=order*(z*p1-p0)/(z*z-1);
  const next=z-p1/derivative;
  if(Math.abs(next-z)<2e-15){z=next;break;}z=next;
 }
 let p0=1,p1=z;for(let j=2;j<=order;j++){const p=((2*j-1)*z*p1-(j-1)*p0)/j;p0=p1;p1=p;}
 derivative=order*(z*p1-p0)/(z*z-1);
 nodes.push(z);weights.push(2/((1-z*z)*derivative*derivative));
}
function normalCdf(x){
 if(x===Infinity)return 1;if(x===-Infinity)return 0;
 const a=Math.abs(x);if(a>12)return x>0?1:0;
 let integral=0;for(let i=0;i<order;i++)integral+=weights[i]*normalPdf(a*(nodes[i]+1)/2);
 integral*=a/2;return Math.max(0,Math.min(1,.5+(x<0?-integral:integral)));
}
function interval(y,d){return y==='H'?[d,Infinity]:y==='A'?[-Infinity,-d]:[-d,d];}
function theoretical(c){
 const [low,high]=interval(c.y,c.delta),scale=Math.sqrt(c.v+1),a=(low-c.m-c.h)/scale,b=(high-c.m-c.h)/scale;
 const P=normalCdf(b)-normalCdf(a),u=(normalPdf(a)-normalPdf(b))/P;
 const xphi=x=>Number.isFinite(x)?x*normalPdf(x):0;
 const truncVariance=1+(xphi(a)-xphi(b))/P-u*u;
 const informativeMean=c.m+c.v/scale*u;
 const informativeVariance=c.v+c.v*c.v/(scale*scale)*(truncVariance-1);
 const Z=c.kappa*P+(1-c.kappa)/3,r=c.kappa*P/Z;
 const mean=c.m+r*(informativeMean-c.m);
 const variance=(1-r)*c.v+r*informativeVariance+r*(1-r)*(informativeMean-c.m)**2;
 return {P,Z,r,mean,variance,informativeMean,informativeVariance};
}
function numerical(c){
 const [low,high]=interval(c.y,c.delta),sd=Math.sqrt(c.v),n=6000,left=c.m-10*sd,step=20*sd/n,sums=[0,0,0];
 for(let i=0;i<=n;i++){
  const x=left+i*step,likelihood=c.kappa*(normalCdf(high-x-c.h)-normalCdf(low-x-c.h))+(1-c.kappa)/3;
  const density=normalPdf((x-c.m)/sd)/sd*likelihood,w=(i===0||i===n)?1:i%2?4:2;
  sums[0]+=w*density;sums[1]+=w*density*x;sums[2]+=w*density*x*x;
 }
 const Z=sums[0]*step/3,mean=sums[1]/sums[0],variance=sums[2]/sums[0]-mean*mean;
 return {Z,mean,variance};
}
const cases=[
 {m:0,v:.4,h:.2,delta:.3,kappa:1,y:'H'},
 {m:.4,v:.6,h:0,delta:.35,kappa:.8,y:'D'},
 {m:-2,v:.5,h:0,delta:.3,kappa:.8,y:'H'},
 {m:2,v:1,h:.1,delta:.3,kappa:.55,y:'A'},
 {m:.2,v:.3,h:.2,delta:.3,kappa:0,y:'H'},
 {m:-2,v:.5,h:0,delta:.3,kappa:1,y:'H'},
 {m:-2,v:.5,h:0,delta:.3,kappa:.4,y:'H'}
];
const tolerance=2e-7,results=cases.map(c=>{
 const a=theoretical(c),b=numerical(c),errors={Z:Math.abs(a.Z-b.Z),mean:Math.abs(a.mean-b.mean),variance:Math.abs(a.variance-b.variance)};
 if(Object.values(errors).some(e=>e>tolerance))throw Error('Integration check failed '+JSON.stringify({c,errors}));
 return {parameters:c,closed_form:a,numerical_integral:b,absolute_errors:errors};
});
const assertions={
 variance_may_increase:results[2].closed_form.variance>cases[2].v,
 lower_reliability_smaller_same_case_mean_update:Math.abs(results[6].closed_form.mean+2)<Math.abs(results[2].closed_form.mean+2)&&Math.abs(results[2].closed_form.mean+2)<Math.abs(results[5].closed_form.mean+2),
 zero_reliability_preserves_prior:Math.abs(results[4].closed_form.mean-cases[4].m)<1e-12&&Math.abs(results[4].closed_form.variance-cases[4].v)<1e-12,
 neutral_equal_strength_symmetry:Math.abs(theoretical({m:0,v:.5,h:0,delta:.3,kappa:.8,y:'H'}).Z-theoretical({m:0,v:.5,h:0,delta:.3,kappa:.8,y:'A'}).Z)<1e-12,
 probabilities_sum_to_one:Math.abs(['H','D','A'].map(y=>theoretical({m:.4,v:.6,h:.2,delta:.3,kappa:.8,y}).Z).reduce((a,b)=>a+b,0)-1)<1e-12
};
if(Object.values(assertions).some(x=>!x))throw Error('Structural assertion failed');
return {schema_version:1,scope:'Hypothetical scalar Gaussian-prior single-match probability/moment formula checks; no football data or rating experiment',integration:'Independent composite Simpson posterior integration; normal CDF from32-node Gauss-Legendre quadrature',tolerance,results,assertions};
})();
console.log(JSON.stringify(result, null, 2));
