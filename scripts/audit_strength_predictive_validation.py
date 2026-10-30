"""Independent past-only audit and scalar Poisson/probit prediction checks."""
from pathlib import Path
import csv,json,math,sys
import numpy as np
from scipy.special import ndtr
from scipy.stats import poisson
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import file_hash,write_json
from src.strength_joint.contract import load
from src.strength_joint.design import Design


def run():
    base=ROOT/'outputs/logs/strength_inference';pointer=json.loads((base/'prediction_pointer.json').read_text());folder=ROOT/pointer['directory']
    manifest=json.loads((folder/'manifest.json').read_text());checks=[]
    def check(name,ok):checks.append(dict(name=name,passed=bool(ok)))
    check('manifest',file_hash(folder/'manifest.json')==pointer['manifest_sha256'])
    for n,h in manifest['outputs'].items():check('output:'+n,file_hash(folder/n)==h)
    for kind in ('inputs','code'):
        for n,h in manifest['identity'][kind].items():check(kind+':'+n,file_hash(ROOT/n)==h)
    def read(name):return list(csv.DictReader((folder/name).open(encoding='utf-8-sig')))
    predictions=read('predictions.csv');metrics=read('group_metrics.csv');yearly=read('yearly_metrics.csv')
    _,facts,_,_,_=load();byid={r['match_id']:r for r in facts};expected={r['match_id'] for r in facts if int(r['year'])>=1990}
    check('21413_ids',len(expected)==21413);check('64239_forecasts',len(predictions)==64239)
    models=json.loads((folder/'models.json').read_text());check('105_past_fits',len(models)==105)
    designs={year:Design([r for r in facts if int(r['year'])<year]) for year in range(1990,2025)}
    for key,model in models.items():
        year=int(key.split(':')[0]);past=[r for r in facts if int(r['year'])<year]
        expected_weights={side+':'+region+':'+unit:value for (side,region,unit),value in designs[year].weights.items()}
        check('past_only_encoding:'+key,model['encoding']['weights']==expected_weights and not model['encoding']['uses_test_rows'])
        check('past_encoding_size:'+key,model['encoding']['training_rows']==len(past) and model['encoding']['date_max']<str(year)+'-01-01')
    for r in predictions:
        actual=byid[r['match_id']];p=float(r['probability'])
        check('past_only',r['training_date_max']<r['year']+'-01-01' and r['strength_prediction_cutoff']<r['date'])
        check('fact_identity',r['date']==actual['date'] and r['home_win']==actual['home_win'])
        check('finite_probability',0<p<1)
    totals={}
    for model in ('M0_nested','M1_strength','M3_nested'):
        rr=[r for r in predictions if r['model_id']==model]
        check('same_ids:'+model,{r['match_id'] for r in rr}==expected and len(rr)==len(expected))
        loss=-math.fsum(math.log(float(r['probability'])) if r['home_win']=='1' else math.log1p(-float(r['probability'])) for r in rr)/len(rr)
        brier=math.fsum((float(r['probability'])-int(r['home_win']))**2 for r in rr)/len(rr)
        accuracy=sum((float(r['probability'])>=.5)==(r['home_win']=='1') for r in rr)/len(rr)
        saved=next(r for r in metrics if r['group']=='all' and r['model_id']==model)
        check('independent_loss:'+model,abs(loss-float(saved['log_loss']))<2e-10)
        check('independent_Brier:'+model,abs(brier-float(saved['brier']))<2e-10)
        check('independent_accuracy:'+model,abs(accuracy-float(saved['binary_accuracy']))<2e-10)
        year_index={r['year']:r for r in yearly if r['model_id']==model}
        check('35_years:'+model,set(year_index)=={str(i) for i in range(1990,2025)})
        totals[model]=dict(log_loss=loss,brier=brier,binary_accuracy=accuracy)
        for r in rr[::max(1,len(rr)//30)]:
            fact=byid[r['match_id']];result=models[r['year']+':'+model];x,names=designs[int(r['year'])].matrix([fact],model)
            theta=np.array(result['theta']);eta=float((x@theta[:len(names)]).item())
            if model=='M0_nested':p=float(ndtr(eta))
            else:
                b=math.exp(theta[-1]);nu=float(fact['home_jump_intensity'])+float(fact['away_jump_intensity'])
                v=float(fact['strength_difference_base_variance']);mu=float(fact['strength_difference']);sd=float(fact['jump_scale_sd'])
                cap=int(poisson.isf(1e-14,nu)) if nu else 0
                p=math.fsum(poisson.pmf(k,nu)*ndtr((eta+b*mu)/math.sqrt(1+b*b*(v+k*sd*sd))) for k in range(cap+1))
            check('independent_scalar_forecast',abs(p-float(r['probability']))<2e-8)
    annual={m:{r['year']:float(r['log_loss']) for r in yearly if r['model_id']==m} for m in totals}
    summary=dict(passed=all(c['passed'] for c in checks),checks=len(checks),failed=[c['name'] for c in checks if not c['passed']],
        predictions_per_model=21413,training_fits=105,metrics=totals,
        joint_beats_background_years=sum(annual['M3_nested'][str(y)]<annual['M0_nested'][str(y)] for y in range(1990,2025)),
        joint_beats_strength_years=sum(annual['M3_nested'][str(y)]<annual['M1_strength'][str(y)] for y in range(1990,2025)),
        background_to_joint_relative_loss_reduction=(totals['M0_nested']['log_loss']-totals['M3_nested']['log_loss'])/totals['M0_nested']['log_loss'],
        strength_to_joint_relative_loss_reduction=(totals['M1_strength']['log_loss']-totals['M3_nested']['log_loss'])/totals['M1_strength']['log_loss'],
        new_blind_future_test=False,full_WDL_accuracy=False,human_review=False)
    write_json(base/'prediction_audit.json',summary);print(json.dumps(summary,ensure_ascii=False))
    if not summary['passed']:raise SystemExit(1)
if __name__=='__main__':run()
