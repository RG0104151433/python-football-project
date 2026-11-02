"""Independent scalar arithmetic audit of Q7 stability; no fitted models imported."""
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def audit(run_id=None):
    def read(path):
        with Path(path).open(encoding='utf-8-sig',newline='') as f:
            return list(csv.DictReader(f))
    def js(path):
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    rid=run_id or js(ROOT/'outputs/logs/regional_effectiveness/stability_pointer.json')['run_id']
    log=ROOT/'outputs/logs/regional_effectiveness'/rid
    tab=ROOT/'outputs/tables/regional_effectiveness'/rid
    manifest=js(log/'manifest.json')
    cfg=manifest['identity']['protocol']
    counters=Counter()
    def check(family,value):
        counters[family]+=1
        if not value:raise AssertionError(family)
    def close(x,y,tol=2e-8):
        if x in (None,'') or y in (None,''):return x in (None,'') and y in (None,'')
        return abs(float(x)-float(y))<tol
    def sign(x):
        return None if x in (None,'') else 1 if float(x)>1e-12 else -1 if float(x)<-1e-12 else 0
    for p,h in manifest['outputs'].items():
        check('sealed_outputs',sha(ROOT/p)==h)
    for p,h in manifest['identity']['inputs'].items():
        check('source_inputs',sha(ROOT/p)==h)
    ev=ROOT/'outputs/tables/regional_effectiveness'/cfg['evaluation_run']
    dg=ROOT/'outputs/tables/regional_effectiveness'/cfg['diagnostics_run']
    rows=[r for r in read(ev/'evaluation_matches.csv') if 2010<=int(r['year'])<=2024]
    mem={r['match_id']:r for r in read(dg/'strata_membership.csv')}
    check('unique_cohort',len(rows)==len({r['match_id'] for r in rows})==9727 and set(mem)=={r['match_id'] for r in rows})
    for r in rows:
        r.update({k:mem[r['match_id']][k] for k in ['joint_cell','uncertainty']})
    def in_group(r,g):
        if g=='SOUTH_AMERICA':return r['home_region']=='019' and r['home_unit']=='005'
        if g=='OTHER_AMERICAS':return r['home_region']=='019' and r['home_unit']!='005'
        return r['home_region']==g
    gs={'primary5':['150','142','002','019','009'],'americas2':['SOUTH_AMERICA','OTHER_AMERICAS']}
    cells=sorted(set(mem[r['match_id']]['joint_cell'] for r in rows))
    counts={s:{g:Counter(r['joint_cell'] for r in rows if in_group(r,g)) for g in groups} for s,groups in gs.items()}
    refs={}
    for s,by in counts.items():
        common=[c for c in cells if all(by[g][c]>0 for g in by)]
        cc={c:sum(by[g][c] for g in by) for c in common}
        refs[s]={c:n/sum(cc.values()) for c,n in cc.items()}
    def loss(p,y):
        p=min(1-cfg['probability_clip'],max(cfg['probability_clip'],float(p)))
        return -math.log(p if int(y) else 1-p)
    for r in rows:
        j,s=float(r['p_joint']),float(r['p_strength']);y=int(r['home_win'])
        r['_joint_loss']=loss(j,y)
        r['_loss_difference']=r['_joint_loss']-loss(s,y)
        r['_joint_bias']=100*(j-y)
        r['_brier_difference']=(j-y)**2-(s-y)**2
    target=read(tab/'targets.csv')
    expected=[('paired',g,'',False) for g in gs['primary5']]+[
        ('between','002','150',False),('between','002','150',True),
        ('calibration','002','',False),('calibration','002','',False),
        ('between','SOUTH_AMERICA','OTHER_AMERICAS',False),('between','SOUTH_AMERICA','OTHER_AMERICAS',True),
        ('paired','009','',True),('bias','009','',True)]
    check('target_registry',len(target)==13)
    for t,expect in zip(target,expected):
        check('target_definition',(t['kind'],t['group_a'],t['group_b'],t['weighted']=='true')==expect)
    def select(source,t,g):
        result=[r for r in source if in_group(r,g)]
        if t['kind']=='calibration':
            b=int(t['probability_bin'])
            result=[r for r in result if r['uncertainty']=='low' and b/5<=float(r['p_joint'])<(b+1)/5]
        return result
    def evaluate(source,t,w=None):
        vals=[];sizes={};bad=False;brier=[]
        for g in [t['group_a']]+([t['group_b']] if t['group_b'] else []):
            rr=select(source,t,g)
            if t['weighted']=='true':
                rr=[r for r in rr if r['joint_cell'] in (w or {})]
                sizes[g]=len(rr)
                if not w:bad=True;continue
                sums=0.;bsums=0.
                for c,wc in w.items():
                    cr=[r for r in rr if r['joint_cell']==c]
                    if not cr:bad=True;continue
                    sums+=wc*math.fsum(r['_'+t['metric']] for r in cr)/len(cr)
                    bsums+=wc*math.fsum(r['_brier_difference'] for r in cr)/len(cr)
                vals.append(sums);brier.append(bsums)
            else:
                sizes[g]=len(rr)
                if not rr:bad=True;continue
                vals.append(math.fsum(r['_'+t['metric']] for r in rr)/len(rr))
                brier.append(math.fsum(r['_brier_difference'] for r in rr)/len(rr))
        return (None if bad else vals[0]-(vals[1] if t['group_b'] else 0),sizes,
                None if bad or t['kind']!='paired' else brier[0])
    bytid={t['target_id']:t for t in target}
    for t in target:
        v,s,b=evaluate(rows,t,refs.get(t['comparison_set']))
        check('baseline_scalars',close(v,t['value']) and close(b,t['brier_difference']) and sum(s.values())==int(t['remaining_matches']))
    scenarios={('year',str(y)) for y in range(2010,2025)}|{('team',g) for g in {r[k] for r in rows for k in ['home_team_id','away_team_id']}}
    deletion=read(tab/'deletion_results.csv')
    keys=[(r['scenario_kind'],r['scenario_key'],r['target_id']) for r in deletion]
    check('scenario_coverage',len(keys)==len(set(keys))==len(scenarios)*13 and set(keys)=={(k,v,t) for k,v in scenarios for t in bytid})
    cache={}
    for kind,key in sorted(scenarios):
        cache[kind,key]=[r for r in rows if (r['year']!=key if kind=='year' else key not in (r['home_team_id'],r['away_team_id']))]
    for r in deletion:
        t=bytid[r['target_id']]
        v,s,b=evaluate(cache[r['scenario_kind'],r['scenario_key']],t,refs.get(t['comparison_set']))
        original=float(t['value'])
        check('deleted_scalars',close(v,r['value']) and close(b,r['brier_difference']))
        check('deleted_support',s==json.loads(r['remaining_by_group']) and (v is None)==(r['status']=='unsupported'))
        check('deleted_counts',sum(s.values())==int(r['remaining_matches']) and int(r['original_matches'])-sum(s.values())==int(r['removed_matches']))
        check('deleted_direction',r['direction_changed']==('' if v is None else str(sign(v)!=sign(original)).lower()) and close(None if v is None else v-original,r['change']))
        check('deleted_affected',(int(r['removed_matches'])>0)==(r['affected']=='true'))
    rw=read(tab/'reference_weights.csv')
    variants={}
    for st,by in counts.items():
        for variant in ['pooled','equal_region','minimum_10','minimum_20']:
            minimum=int(variant.split('_')[1]) if variant.startswith('minimum_') else 1
            cc=[c for c in cells if all(by[g][c]>=minimum for g in by)]
            raw={c:sum(by[g][c]/sum(by[g].values()) for g in by)/len(by) if variant=='equal_region' else refs[st][c] for c in cc}
            total=math.fsum(raw.values());w={c:x/total for c,x in raw.items()} if total else {}
            variants[st,variant]=w
            emitted={r['joint_cell']:float(r['weight']) for r in rw if r['comparison_set']==st and r['variant']==variant}
            check('reference_weights',set(emitted)==set(cells) and all(close(emitted[c],w.get(c,0),1e-9) for c in cells))
    reference=read(tab/'reference_sensitivity.csv')
    for r in reference:
        t=bytid[r['target_id']];v,s,b=evaluate(rows,t,variants[r['comparison_set'],r['variant']])
        check('reference_scalars',close(v,r['value']) and close(b,r['brier_difference']) and sum(s.values())==int(r['remaining_matches']))
    for r in read(tab/'reference_support.csv'):
        w=variants[r['comparison_set'],r['variant']];g=r['group']
        n=sum(1 for x in rows if in_group(x,g) and x['joint_cell'] in w)
        check('reference_retained_scope',n==int(r['retained_matches']) and len(w)==int(r['common_cells']) and close(math.fsum(refs[r['comparison_set']].get(c,0) for c in w),r['original_reference_mass']))
    mw=read(tab/'match_weights.csv');byid={r['match_id']:r for r in rows}
    weight_by=defaultdict(list)
    seen=set()
    for r in mw:
        st,g,mid=r['comparison_set'],r['group'],r['match_id'];x=byid[mid]
        key=(st,g,mid);check('match_weight_identity',key not in seen and in_group(x,g));seen.add(key)
        w=refs[st][x['joint_cell']]/counts[st][g][x['joint_cell']]
        check('individual_weight',close(w,r['match_weight'],1e-10))
        weight_by[st,g].append((x,w))
    for r in read(tab/'weight_concentration.csv'):
        ww=weight_by[r['comparison_set'],r['group']]
        if r['dimension']=='summary':
            a=[w for x,w in ww]
            check('weight_concentration',close(max(a),r['max_match_weight']) and close(1/math.fsum(w*w for w in a),r['weight_concentration_equivalent_matches']) and abs(math.fsum(a)-1)<1e-10)
        else:
            level=r['level'];dim=r['dimension']
            selected=[w for x,w in ww if (x['joint_cell']==level if dim=='cell' else x['year']==level if dim=='year' else level in (x['home_team_id'],x['away_team_id']))]
            check('weight_contribution',len(selected)==int(r['matches']) and close(math.fsum(selected),r['weight']))
    for c in read(tab/'conclusion_review.csv'):
        dr=[r for r in deletion if r['target_id']==c['target_id'] and r['affected']=='true']
        rr=[r for r in reference if r['target_id']==c['target_id'] and r['variant']!='pooled' and not r['alias_of']]
        changes=sum(r['direction_changed']=='true' for r in dr+rr)
        missing=sum(r['status']=='unsupported' for r in dr+rr)
        expected='sensitive' if changes else 'direction_preserved_with_support_gaps' if missing else 'direction_preserved_in_checked_variations'
        check('evidence_labels',c['evidence']==expected and int(c['unsupported_variations'])==missing)
        for k in ['year','team']:
            dd=[r for r in deletion if r['target_id']==c['target_id'] and r['scenario_kind']==k]
            vals=[float(r['value']) for r in dd if r['value']]
            check('influence_summary',int(c[k+'_total'])==len(dd) and int(c[k+'_unsupported'])==sum(r['status']=='unsupported' for r in dd) and int(c[k+'_sign_changes'])==sum(r['direction_changed']=='true' for r in dd) and close(min(vals) if vals else None,c[k+'_min']) and close(max(vals) if vals else None,c[k+'_max']))
    dlookup={(r['scenario_kind'],r['scenario_key'],r['target_id']):r for r in deletion}
    for r in read(tab/'story_results.csv'):
        def get(t):
            return bytid[t] if r['scenario_kind']=='original' else dlookup[r['scenario_kind'],r['scenario_key'],t]
        a,b=get(r['first_target']),get(r['second_target'])
        check('synchronized_story_values',close(a['value'],r['first_value']) and close(b['value'],r['second_value']))
        if a['value']=='' or b['value']=='':
            check('synchronized_story_status',r['status']=='unsupported' and r['story_preserved']=='')
        else:
            x,y=float(a['value']),float(b['value'])
            expected=x>y>0 if r['story']=='africa_positive_gap_shrinks' else x>0 and y<0 if r['story']=='south_america_order_reverses' else x<0 and y>0
            check('synchronized_story_status',r['story_preserved']==str(expected).lower())
    for p in tab.glob('*.csv'):
        raw=p.read_bytes()
        check('csv_format',raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw)
    display=js(tab/'display_data.json')
    check('interpretation_flags',not display['formal_inference'] and not display['refitted'] and not display['human_review'])
    result=dict(run_id=rid,passed=True,checks=sum(counters.values()),check_families=dict(counters),
                formal_inference=False,refitted=False,human_review=False,
                auditor_sha256=sha(Path(__file__)),manifest_sha256=sha(log/'manifest.json'))
    # This supplementary audit is outside the original sealed output manifest.
    with (log/'independent_audit.json').open('w',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(result,ensure_ascii=False))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-id')
    audit(p.parse_args().run_id)
