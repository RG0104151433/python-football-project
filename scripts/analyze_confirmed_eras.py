"""Step six: apply the provisional FIFA overlay and rerun Q1 descriptions.

Reuse the existing statistical implementation without changing its registered
source, preserving verification of pre-overlay runs. No Q2 or inference here.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0,str(PROJECT))

from scripts.audit_team_identity import json_bytes, load_json, safe, digest, file_hash
from scripts.build_team_identity import MATCH_FIELDS, verify_identity
from scripts.plan_team_identity import ensure
from src.analyze_eras import code_hashes, environment, sample_flow
from src.data_contract import csv_bytes, load_config, read_csv, PrepError
from src.eras.data import load_analysis_config, load_validated_dataset, select_samples
from src.eras.statistics import build_statistics
from src.eras.standardize import build_standardization
from src.eras.checks import validate_tables
from src.eras.reporting import table_artifacts, figure_artifacts, publish_outputs, verify_run


def apply_overlay(rows, config, overlay):
    by_id={r['match_id']:r for r in overlay}
    ensure(len(by_id)==len(overlay) and set(by_id)=={r['match_id'] for r in rows},
           'CONFIRMED_COVERAGE_INVALID','Overlay must exactly cover clean matches')
    baseline,membership=select_samples(rows,config)
    allowed=set()
    for row in rows:
        o=by_id[row['match_id']]
        ensure(o['date']==row['date'] and o['source_record_id']==row['source_record_id']
               and all(o[s+'_source_team_id']==row[s+'_team_id'] and o[s+'_source_label']==row[s+'_team'] for s in ('home','away')),
               'CONFIRMED_IDENTITY_MISMATCH',row['match_id'])
        ensure(o['eligible_under_provisional_policy'] in ('true','false') and o['full_history_verified']=='false',
               'CONFIRMED_BOOLEAN_INVALID',row['match_id'])
        eligible=o['eligible_under_provisional_policy']=='true'
        ensure(eligible==(o['membership_status']=='conditional_both_members'),
               'CONFIRMED_STATUS_INVALID',row['match_id'])
        if eligible:allowed.add(row['match_id'])
    samples={name:[r for r in selected if r['match_id'] in allowed] for name,selected in baseline.items()}
    for m in membership:
        o=by_id[m['match_id']]
        if m['match_id'] not in allowed:
            reason='fifa_nonmember_evidence' if o['membership_status']=='nonmember_evidence' else 'fifa_membership_pending'
            if config['analysis_start']<=m['date']<=config['analysis_end']:
                m['exclusion_reasons'].append(reason)
                if not m['primary_exclusion_reason']:m['primary_exclusion_reason']=reason
            m['in_base_venue']=False;m['in_classified_venue']=False
    return baseline,samples,membership


def run_confirmed(root, relative='config/confirmed_eras.json'):
    cfg=load_json(safe(root,relative))
    ensure(set(cfg)=={'schema_version','identity_manifest','analysis_config','prep_config','previous_run'}
           and cfg['schema_version']=='confirmed-eras-config-v1','CONFIRMED_CONFIG_INVALID',relative)
    verify_identity(root,cfg['identity_manifest'])
    verify_run(root,cfg['previous_run'])
    im=load_json(safe(root,cfg['identity_manifest']))
    _,prep=load_config(safe(root,cfg['prep_config']))
    config=load_analysis_config(safe(root,cfg['analysis_config']),prep['data']['cutoff_date'])
    ensure(im['scope']=={'start':config['analysis_start'],'end':config['analysis_end']} and im['data_version']==config['data_version'],
           'CONFIRMED_SCOPE_INVALID','Overlay/config must use the same data/window')
    rows,dm,validation,inputs=load_validated_dataset(root,prep,config)
    op=next(p for p in im['outputs'] if p.endswith('/match_identity.csv'))
    _,overlay=read_csv(safe(root,op),MATCH_FIELDS)
    inputs.update(im['inputs'])
    for p in [relative,cfg['identity_manifest'],cfg['analysis_config'],cfg['prep_config'],cfg['previous_run'],*im['outputs']]:
        inputs[p]=file_hash(safe(root,p))
    sources={**code_hashes(root),**im['code_hashes'], 'scripts/analyze_confirmed_eras.py':file_hash(root/'scripts/analyze_confirmed_eras.py')}
    versions=environment()
    analysis_id='eras-fifa-'+digest(json_bytes(dict(inputs=inputs,code=sources,config=config,environment=versions)))[:20]
    baseline,samples,membership=apply_overlay(rows,config,overlay)
    tables={'analysis_membership':membership,'sample_flow':sample_flow(samples,membership,root,dm)}
    tables.update(build_statistics(samples,config))
    standardized,references=build_standardization(samples['classified_venue'],config)
    tables.update(standardized)
    checks=validate_tables(tables,samples,membership,config)
    old_tables=build_statistics(baseline,config)
    old_standardized,old_references=build_standardization(baseline['classified_venue'],config)
    old_eras={r['period_id']:r for r in old_tables['era_summary'] if r['sample_name']=='classified_venue'}
    old_est={(r['analysis_era_id'],r['estimand']):r['estimate'] for r in old_standardized['era_estimates'] if r['reference_id']==old_references[0]['reference_id']}
    new_est={(r['analysis_era_id'],r['estimand']):r['estimate'] for r in tables['era_estimates'] if r['reference_id']==references[0]['reference_id']}
    comparison=[]
    for r in tables['era_summary']:
        if r['sample_name']!='classified_venue':continue
        era=r['period_id'];old=old_eras[era]
        comparison.append(dict(era=era,old_n=old['n_matches'],new_n=r['n_matches'],removed_n=old['n_matches']-r['n_matches'],
            old_home_win_rate=old['home_win_rate'],new_home_win_rate=r['home_win_rate'],
            raw_change_pp=100*(r['home_win_rate']-old['home_win_rate']) if r['home_win_rate'] is not None and old['home_win_rate'] is not None else None,
            old_standardized_rate=old_est[(era,'standardized_rate')],new_standardized_rate=new_est[(era,'standardized_rate')]))
    # Independent direct enumeration checks both sample sizes and all five rates.
    for r in comparison:
        selected=[x for x in samples['classified_venue'] if next(e['id'] for e in config['eras'] if e['start']<=x['date']<=e['end'])==r['era']]
        ensure(len(selected)==r['new_n'] and (not selected or abs(sum(x['outcome']=='home' for x in selected)/len(selected)-r['new_home_win_rate'])<1e-12),
               'CONFIRMED_DIRECT_RECOUNT_FAILED',r['era'])
    artifacts=table_artifacts(tables,analysis_id)
    artifacts.update(figure_artifacts(tables,references,config,analysis_id))
    artifacts[f'outputs/tables/eras/{analysis_id}/before_after.csv']=csv_bytes(list(comparison[0]),comparison)
    def unchanged():
        for p,h in {**inputs,**sources}.items():
            ensure(file_hash(safe(root,p))==h,'CONFIRMED_INPUT_CHANGED',p)
    unchanged()
    outputs=publish_outputs(root,artifacts)
    run_id='confirmed-eras-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8]
    folder=safe(root,'outputs/logs/team_identity/'+run_id);folder.mkdir(parents=True,exist_ok=False)
    summary=dict(analysis_id=analysis_id,identity_version=im['identity_version'],publication_status='provisional_conditional',
        baseline_matches=len(baseline['classified_venue']),new_matches=len(samples['classified_venue']),
        exclusions=dict(sorted(Counter(r['change_from_previous_study'] for r in overlay if r['in_previous_study']=='true').items())),
        old_weight_friendly=old_references[0]['weight_friendly'],new_weight_friendly=references[0]['weight_friendly'],
        eras=comparison,primary_contrasts=[r for r in tables['era_contrasts'] if r['reference_id']==references[0]['reference_id']],
        full_history_verified=False,inference='not_run',shared_reliability='not_run',q2='not_implemented',
        warning='Membership continuity and label correspondence are provisional; no claim of complete historical FIFA population.')
    for name,content in {'summary.json':json_bytes(summary),'checks.json':json_bytes(checks),
        'summary.md':('# FIFA口径接入第一题（有条件探索）\n\n'+f'分析编号：{analysis_id}。\n\n'
            +f"旧研究{summary['baseline_matches']}场；本次暂纳入{summary['new_matches']}场。\n\n"
            +'本次采用官方加入年份与明示连续性假设，未决记录另存。不是全历史资格已核验的新最终结论。'
            '原26,055场版保留作基线；两个版本不可混用数字和图。第二题只登记接口，未计算；可靠性仍后置。\n').encode('utf-8')}.items():
        p=folder/name
        with p.open('xb') as f:f.write(content)
        outputs[p.relative_to(root).as_posix()]=digest(content)
    unchanged()
    manifest=dict(schema_version='confirmed-eras-run-v1',status='completed',analysis_id=analysis_id,
        identity_version=im['identity_version'],created_at_utc=datetime.now(timezone.utc).isoformat(),
        inputs=inputs,outputs=outputs,code_hashes=sources,environment=versions,summary=summary,
        stages={'description':'completed','inference':'not_run','shared_reliability':'not_run','q2':'not_implemented'},
        publication_status='provisional_conditional',full_history_verified=False)
    with (folder/'run_manifest.json').open('xb') as f:f.write(json_bytes(manifest))
    return dict(analysis_id=analysis_id,run_manifest=(folder/'run_manifest.json').relative_to(root).as_posix(),summary=summary)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='config/confirmed_eras.json');p.add_argument('--verify-run')
    a=p.parse_args(argv)
    try:
        result=verify_run(PROJECT,a.verify_run) if a.verify_run else run_confirmed(PROJECT,a.config)
        print(json.dumps(result,ensure_ascii=True));return 0
    except (PrepError,OSError,ValueError,KeyError,TypeError) as e:
        print(json.dumps(dict(status='failed',code=getattr(e,'code','CONFIRMED_FAILED'),message=str(e)),ensure_ascii=True),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
