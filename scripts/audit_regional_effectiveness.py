"""Independent scalar audit of saved Q7 tables; no fitting or plotting."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def audit(run_id=None):
    ptr=json.loads((ROOT/'outputs/logs/regional_effectiveness/current.json').read_text(encoding='utf-8-sig'))
    rid=run_id or ptr['run_id'];table=ROOT/'outputs/tables/regional_effectiveness'/rid
    log=ROOT/'outputs/logs/regional_effectiveness'/rid
    def read(name):
        with (table/name).open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
    rows=read('evaluation_matches.csv');checks=[]
    def check(name,passed):
        checks.append(dict(name=name,passed=bool(passed)))
        if not passed:raise AssertionError(name)
    def select(scope,group):
        rr=[r for r in rows if scope=='background' or 2010<=int(r['year'])<=2024]
        if group=='ALL':return rr
        if group=='SOUTH_AMERICA':return [r for r in rr if r['home_region']=='019' and r['home_unit']=='005']
        if group=='OTHER_AMERICAS':return [r for r in rr if r['home_region']=='019' and r['home_unit']!='005']
        return [r for r in rr if (r['home_region'] or 'UNKNOWN')==group]
    metrics=read('regional_metrics.csv')
    for m in metrics:
        ss=select(m['scope'],m['group']);label=m['scope']+':'+m['group']+':'+m['model']
        check('count:'+label,len(ss)==int(m['matches']))
        if not ss:
            check('empty blank:'+label,m['log_loss']=='' and m['bias_pp']=='');continue
        pp=[float(r['p_'+m['model']]) for r in ss];yy=[int(r['home_win']) for r in ss]
        cl=[max(1e-6,min(1-1e-6,p)) for p in pp]
        loss=statistics.mean(-math.log(p) if y else -math.log1p(-p) for p,y in zip(cl,yy))
        check('scalar metrics:'+label,abs(loss-float(m['log_loss']))<8e-11 and
            abs(statistics.mean((p-y)**2 for p,y in zip(pp,yy))-float(m['brier']))<8e-11 and
            abs(100*statistics.mean(p-y for p,y in zip(pp,yy))-float(m['bias_pp']))<8e-11 and
            abs(statistics.mean((p>=.5)==y for p,y in zip(pp,yy))-float(m['accuracy']))<8e-11)
    bins=read('calibration.csv')
    for m in metrics:
        bb=[r for r in bins if all(r[k]==m[k] for k in ['scope','group','model'])]
        label=m['scope']+':'+m['group']+':'+m['model']
        check('bin partition:'+label,len(bb)==5 and sum(int(r['matches']) for r in bb)==int(m['matches']))
        if int(m['matches']):
            mean=sum(int(r['matches'])*float(r['mean_probability']) for r in bb if int(r['matches']))/int(m['matches'])
            check('bin weighted mean:'+label,abs(mean-float(m['mean_probability']))<1.2e-10)
    for r in read('paired_differences.csv'):
        a=next(m for m in metrics if m['scope']==r['scope'] and m['group']==r['group'] and m['model']=='joint')
        b=next(m for m in metrics if m['scope']==r['scope'] and m['group']==r['group'] and m['model']==r['reference'])
        check('paired mean:'+r['scope']+r['group']+r['reference'],
            abs(float(a['log_loss'])-float(b['log_loss'])-float(r['joint_minus_reference_loss']))<1.6e-10
            if int(r['matches']) else r['joint_minus_reference_loss']=='')
    for scope in ['main','background']:
        check('Americas partition:'+scope,len(select(scope,'019'))==len(select(scope,'SOUTH_AMERICA'))+len(select(scope,'OTHER_AMERICAS')))
        check('primary partition:'+scope,len(select(scope,'ALL'))==sum(len(select(scope,g)) for g in ['150','142','002','019','009','UNKNOWN']))
    for path in table.glob('*.csv'):
        raw=path.read_bytes();check('BOM LF:'+path.name,raw.startswith(b'\xef\xbb\xbf') and b'\r\n' not in raw)
    manifest=json.loads((log/'manifest.json').read_text(encoding='utf-8-sig'))
    for path,h in manifest['outputs'].items():check('sealed:'+path,hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h)
    result=dict(passed=True,run_id=rid,checks=len(checks),checks_detail=checks,
                scope='independent scalar arithmetic and saved-source/format check; no model fitting or rating replay',
                auditor_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),human_review=False)
    (log/'independent_audit.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print('REGIONAL_AUDIT_PASSED',rid,len(checks));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id')
    audit(parser.parse_args().run_id)
