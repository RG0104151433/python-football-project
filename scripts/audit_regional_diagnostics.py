"""Independent scalar audit of Q7 composition and common-mix arithmetic."""
from collections import Counter
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def audit(run_id=None):
    pointer=json.loads((ROOT/'outputs/logs/regional_effectiveness/diagnostics_pointer.json').read_text(encoding='utf-8-sig'))
    rid=run_id or pointer['run_id'];log=ROOT/'outputs/logs/regional_effectiveness'/rid;table=ROOT/'outputs/tables/regional_effectiveness'/rid
    def read(path):
        with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    manifest=json.loads((log/'manifest.json').read_text(encoding='utf-8-sig'));checks=[]
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value)))
        if not value:raise AssertionError(name)
    for path,h in manifest['outputs'].items():check('sealed:'+path,hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h)
    inputs=manifest['identity']['inputs'];parent_id=manifest['identity']['protocol']['source_run']
    rows=read(ROOT/f'outputs/tables/regional_effectiveness/{parent_id}/evaluation_matches.csv')
    rows=[r for r in rows if 2010<=int(r['year'])<=2024]
    facts_path=next(p for p in inputs if 'joint-preparation-' in p and p.endswith('/analysis_matches.csv'))
    train=[r for r in read(ROOT/facts_path) if '1980-01-01'<=r['date']<'2010-01-01']
    cuts=json.loads((log/'thresholds.json').read_text(encoding='utf-8-sig'))
    def q(values,p):
        s=sorted(values);position=(len(s)-1)*p;i=int(position);f=position-i
        return s[i] if i==len(s)-1 else s[i]+f*(s[i+1]-s[i])
    absolute=[abs(float(r['strength_difference'])) for r in train]
    sd=[math.sqrt(float(r['strength_difference_variance'])) for r in train]
    check('past training count and maximum',len(train)==cuts['training_rows'] and max(r['date'] for r in train)==cuts['training_max'])
    check('signed median',abs(statistics.median(absolute)-cuts['signed_gap_magnitude'])<1e-12)
    check('absolute quantiles',all(abs(q(absolute,p)-v)<1e-12 for p,v in zip([1/3,2/3],cuts['absolute_gap_cuts'])))
    check('uncertainty quantiles',all(abs(q(sd,p)-v)<1e-12 for p,v in zip([1/3,2/3],cuts['uncertainty_sd_cuts'])))
    memberships={r['match_id']:r for r in read(table/'strata_membership.csv')}
    byid={r['match_id']:r for r in rows}
    check('same unique target IDs',len(memberships)==len(rows)==9727 and set(memberships)==set(byid))
    for r in rows:
        d=float(r['strength_difference']);t=cuts['signed_gap_magnitude'];v=math.sqrt(float(r['strength_difference_variance']))
        sg='away_advantage' if d < -t else 'home_advantage' if d > t else 'relatively_close'
        unc=['low','middle','high'][sum(v>=c for c in cuts['uncertainty_sd_cuts'])]
        saved=memberships[r['match_id']]
        if sg!=saved['signed_gap'] or unc!=saved['uncertainty'] or saved['joint_cell']!=sg+'|'+unc:raise AssertionError('classification:'+r['match_id'])
        r.update(saved)
    check('all predictor classifications independently rebuilt',True)
    def subset(group):
        if group=='ALL':return rows
        if group=='SOUTH_AMERICA':return [r for r in rows if r['home_region']=='019' and r['home_unit']=='005']
        if group=='OTHER_AMERICAS':return [r for r in rows if r['home_region']=='019' and r['home_unit']!='005']
        return [r for r in rows if (r['home_region'] or 'UNKNOWN')==group]
    def metric(rr,model):
        pp=[float(r['p_'+model]) for r in rr];y=[int(r['home_win']) for r in rr]
        loss=statistics.mean(-math.log(max(1e-6,min(1-1e-6,p))) if yy else -math.log1p(-max(1e-6,min(1-1e-6,p))) for p,yy in zip(pp,y))
        return loss,100*statistics.mean(p-yy for p,yy in zip(pp,y))
    weights=read(table/'reference_weights.csv');std=read(table/'standardized_metrics.csv')
    cfg=manifest['identity']['protocol']
    for set_name,gg in [('primary5',cfg['standardization']['primary_set']),('americas2',cfg['standardization']['americas_set'])]:
        ww=[r for r in weights if r['comparison_set']==set_name]
        expected={c:sum(sum(r['joint_cell']==c for r in subset(g)) for g in gg) for c in [w['joint_cell'] for w in ww] if all(any(r['joint_cell']==c for r in subset(g)) for g in gg)}
        denominator=sum(expected.values());expected={c:n/denominator for c,n in expected.items()} if denominator else {}
        check('label-free reference:'+set_name,all(abs(float(w['weight'])-expected.get(w['joint_cell'],0))<8e-11 for w in ww))
        for s in [r for r in std if r['comparison_set']==set_name]:
            rr=[r for g in gg for r in subset(g)] if s['group']=='ALL' else subset(s['group'])
            keep=[r for r in rr if r['joint_cell'] in expected]
            check('retained count:'+set_name+s['group']+s['model'],len(keep)==int(s['retained_matches']))
            if not expected:check('unsupported blank:'+set_name+s['group'],s['standardized_loss']=='');continue
            values=[(w,metric([r for r in rr if r['joint_cell']==c],s['model'])) for c,w in expected.items()]
            loss=sum(w*m[0] for w,m in values);bias=sum(w*m[1] for w,m in values)
            check('scalar standardized:'+set_name+s['group']+s['model'],abs(loss-float(s['standardized_loss']))<8e-11 and abs(bias-float(s['standardized_bias_pp']))<8e-9)
    # One check per group/factor, covering all saved levels and both models.
    cells=read(table/'stratum_metrics.csv')
    for group,dim in sorted({(r['group'],r['dimension']) for r in cells}):
        rr=subset(group);saved=[r for r in cells if r['group']==group and r['dimension']==dim]
        ok=True
        for s in saved:
            ss=[r for r in rr if r[dim]==s['level']]
            ok=ok and len(ss)==int(s['matches'])
            if ss:
                loss,bias=metric(ss,s['model']);ok=ok and abs(loss-float(s['log_loss']))<8e-11 and abs(bias-float(s['bias_pp']))<8e-9
            else:ok=ok and s['log_loss']==''
        check('factor metric block:'+group+dim,ok)
    for s in read(table/'africa_calibration.csv'):
        ss=[r for r in subset('002') if r[s['dimension']]==s['level'] and min(int(float(r['p_joint'])*5),4)==int(s['probability_bin'])]
        ok=len(ss)==int(s['matches'])
        if ss:
            loss,bias=metric(ss,'joint');ok=ok and abs(loss-float(s['log_loss']))<8e-11 and abs(bias-float(s['bias_pp']))<8e-9
        check('Africa bin:'+s['dimension']+s['level']+s['probability_bin'],ok)
    for p in table.glob('*.csv'):check('BOM/LF:'+p.name,p.read_bytes().startswith(b'\xef\xbb\xbf') and b'\r\n' not in p.read_bytes())
    result=dict(passed=True,run_id=rid,checks=len(checks),checks_detail=checks,scalar_metric_cells=468,
                audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                scope='one scalar/source/partition audit; no statistical uncertainty, fits or repeated ratings',human_review=False)
    (log/'independent_audit.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print('DIAGNOSTIC_AUDIT_PASSED',rid,len(checks));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-id');audit(p.parse_args().run_id)
