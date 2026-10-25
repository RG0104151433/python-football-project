"""Publish a provisional FIFA-year identity overlay; never alter source matches.

The supported release is explicitly conditional on membership continuity. It is
not a complete historical FIFA register and cannot pass final-release approval.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.audit_team_identity import (code_hashes, digest, file_hash, json_bytes,
    load_inputs, load_json, safe, selected, verify_run)
from scripts.plan_team_identity import ensure
from src.data_contract import csv_bytes, parse_date, read_csv, PrepError

AFF_FIELDS = 'record_no official_name fifa_code affiliation_years pdf_page evidence_id'.split()
CROSS_FIELDS = 'source_team_id source_team_label fifa_code official_name mapping_basis evidence_id checked_by independently_reviewed_by'.split()
MATCH_FIELDS = ('match_id source_record_id date home_source_team_id away_source_team_id '
    'home_source_label away_source_label home_fifa_code away_fifa_code home_status away_status '
    'home_evidence_id away_evidence_id home_reason away_reason membership_status eligible_under_provisional_policy '
    'in_previous_study change_from_previous_study policy_id full_history_verified').split()
SOURCE_FILES = ('fifa_affiliations.csv', 'label_crosswalk.csv', 'historical_exceptions.json',
                'admission_events.json', 'population_policy.json', 'sources.json')


def validate_registry(data, affiliations, crosswalk, exceptions, events, policy):
    ensure(policy.get('schema_version') == 'fifa-population-policy-v1' and policy.get('analysis_scope') == data['scope']
           and policy.get('final_release_allowed') is False and bool(policy.get('continuity_assumption'))
           and policy.get('unknown_action') == 'quarantine_for_this_release_not_delete',
           'FIFA_POLICY_INVALID', 'Only explicitly provisional, bounded publication is supported')
    codes = {}
    for row in affiliations:
        ensure(re.fullmatch(r'[A-Z]{3}', row['fifa_code']) and row['fifa_code'] not in codes
               and re.fullmatch(r'[12][0-9]{3}(?:/[12][0-9]{3})*', row['affiliation_years']),
               'FIFA_AFFILIATION_INVALID', str(row))
        years = [int(y) for y in row['affiliation_years'].split('/')]
        ensure(years == sorted(set(years)) and max(years) <= 2018 and row['evidence_id'] == 'FIFA-FINANCIAL-2018-MEMBERS',
               'FIFA_AFFILIATION_INVALID', row['fifa_code'])
        codes[row['fifa_code']] = dict(row, years=years)
    ensure(len(codes) == 211 and sorted(int(r['record_no']) for r in affiliations) == list(range(1, 212)),
           'FIFA_AFFILIATION_COVERAGE', 'Expected the complete 211-row original table')
    source = {r['team_id']: r['canonical_name'] for r in data['registry']}
    mapping = {}
    for row in crosswalk:
        tid, code = row['source_team_id'], row['fifa_code']
        ensure(tid in source and tid not in mapping and source[tid] == row['source_team_label'] and code in codes
               and row['official_name'] == codes[code]['official_name'] and bool(row['checked_by'])
               and row['evidence_id'] == 'FIFA-FINANCIAL-2018-MEMBERS'
               and row['mapping_basis'] in {'literal', 'explicit_name_correspondence'},
               'FIFA_CROSSWALK_INVALID', tid)
        ensure(row['mapping_basis'] != 'literal' or row['source_team_label'] == row['official_name'],
               'FIFA_CROSSWALK_INVALID', tid)
        mapping[tid] = codes[code]
    ensure(len(mapping) == 211 and len({r['fifa_code'] for r in crosswalk}) == 211,
           'FIFA_CROSSWALK_COVERAGE', 'Each listed association must have exactly one explicit source-label mapping')
    names = set(source.values())
    checked_exceptions = []
    for e in exceptions:
        ensure(set(e) == {'source_team_label', 'start', 'end', 'reason'} and e['source_team_label'] in names
               and parse_date(e['start']) <= parse_date(e['end']) and bool(e['reason']),
               'FIFA_HISTORY_INVALID', str(e))
        for old in checked_exceptions:
            ensure(old['source_team_label'] != e['source_team_label'] or old['end'] < e['start'] or e['end'] < old['start'],
                   'FIFA_HISTORY_CONFLICT', e['source_team_label'])
        checked_exceptions.append(e)
    exact = {}
    by_name = {r['source_team_label']: mapping[r['source_team_id']] for r in crosswalk}
    for e in events:
        ensure(set(e) == {'source_team_label', 'start', 'evidence_id', 'url', 'locator'}
               and e['source_team_label'] in by_name and e['source_team_label'] not in exact
               and e['url'].startswith(('https://inside.fifa.com/', 'https://vod.fifa.com/'))
               and int(parse_date(e['start'])[:4]) == by_name[e['source_team_label']]['years'][-1]
               and bool(e['locator']) and bool(e['evidence_id']), 'FIFA_ADMISSION_INVALID', str(e))
        exact[e['source_team_label']] = e
    return mapping, exact


def classify_side(day, tid, name, mapping, exact, exceptions, scope):
    if not scope['start'] <= day <= scope['end']:
        return '', 'outside_scope', '', 'No approval for pre-1980, post-2024 or Elo warmup'
    for e in exceptions:
        if e['source_team_label'] == name and e['start'] <= day <= e['end']:
            return '', 'pending_historical_episode', '', e['reason']
    if tid not in mapping:
        return '', 'pending_unmapped_label', '', 'Absent from 2018 roster is not proof of no historical FIFA membership'
    record = mapping[tid]
    code, eid, years = record['fifa_code'], record['evidence_id'], record['years']
    year = int(day[:4])
    if name in exact:
        e = exact[name]
        if day < e['start']:
            return code, 'nonmember_before_admission', e['evidence_id'], 'Before official dated admission'
        return code, 'conditional_member', e['evidence_id'], 'Admission day verified; subsequent continuity is provisional'
    if year < years[-1]:
        if len(years) > 1:
            return code, 'pending_historical_episode', eid, 'Multiple affiliations: earlier spell/withdrawal boundaries not verified'
        return code, 'nonmember_before_admission', eid, 'Before listed affiliation year; predecessor history may still require review'
    if year == years[-1]:
        return code, 'pending_admission_year', eid, 'Year known, exact admission day not verified; do not invent 1 January'
    return code, 'conditional_member', eid, 'After listed affiliation year; continuity and inherited-name crosswalk are provisional'


def build_match_overlay(data, mapping, exact, exceptions, policy):
    rows = []
    for r in data['clean']:
        sides = [classify_side(r['date'], r[s+'_team_id'], r[s+'_team'], mapping, exact, exceptions, data['scope']) for s in ('home','away')]
        states = [s[1] for s in sides]
        if 'outside_scope' in states:
            state = 'outside_scope'
        elif 'nonmember_before_admission' in states:
            state = 'nonmember_evidence'
        elif all(s == 'conditional_member' for s in states):
            state = 'conditional_both_members'
        else:
            state = 'pending'
        allowed, prior = state == 'conditional_both_members', selected(r, data['scope'])
        row = dict(match_id=r['match_id'], source_record_id=r['source_record_id'], date=r['date'],
            home_source_team_id=r['home_team_id'], away_source_team_id=r['away_team_id'],
            home_source_label=r['home_team'], away_source_label=r['away_team'],
            membership_status=state, eligible_under_provisional_policy=allowed, in_previous_study=prior,
            change_from_previous_study='retained' if prior and allowed else 'excluded_by_membership_evidence' if prior and state=='nonmember_evidence'
                else 'quarantined_pending' if prior else 'outside_previous_study',
            policy_id=policy['policy_id'], full_history_verified=False)
        for side, (code, status, eid, reason) in zip(('home','away'), sides):
            row.update({side+'_fifa_code': code, side+'_status': status, side+'_evidence_id': eid, side+'_reason': reason})
        rows.append(row)
    ensure(len(rows) == len(data['clean']) and len({r['match_id'] for r in rows}) == len(rows),
           'FIFA_MATCH_COVERAGE', 'Every clean match must have exactly one disposition')
    return sorted(rows, key=lambda r:r['match_id'])


def verify_identity(root, relative):
    m = load_json(safe(root, relative))
    ensure(m.get('schema_version') == 'fifa-identity-release-v1' and m.get('status') == 'published_provisional'
           and m.get('full_history_verified') is False, 'FIFA_RELEASE_INVALID', relative)
    for label in ('inputs','code_hashes','outputs'):
        for p,h in m[label].items():
            ensure(file_hash(safe(root,p)) == h, 'FIFA_RELEASE_HASH_MISMATCH', p)
    return dict(passed=True, identity_version=m['identity_version'], verified_outputs=len(m['outputs']), final_release=False)


def run_build(root, relative='config/team_identity_fifa.json'):
    cfg = load_json(safe(root, relative))
    ensure(set(cfg)=={'schema_version','inventory_config','inventory_run','source_dir'} and cfg['schema_version']=='fifa-identity-build-config-v1',
           'FIFA_CONFIG_INVALID', relative)
    verify_run(root,cfg['inventory_run'])
    data=load_inputs(root,cfg['inventory_config'])
    inv=load_json(safe(root,cfg['inventory_run']))
    ensure(inv['inputs']==data['inputs'], 'FIFA_INVENTORY_MISMATCH','Inventory input changed')
    folder=safe(root,cfg['source_dir'])
    inputs=dict(data['inputs'])
    for p in [safe(root,relative),safe(root,cfg['inventory_run']),*(folder/n for n in SOURCE_FILES)]:
        inputs[p.relative_to(root).as_posix()]=file_hash(p)
    source_register=load_json(folder/'sources.json')
    ensure(source_register.get('schema_version')=='fifa-source-register-v1','FIFA_SOURCE_INVALID','Source register')
    evidence={e['evidence_id'] for e in source_register['sources']}
    for e in source_register['sources']:
        if 'local_path' in e:
            p=safe(root,e['local_path'])
            ensure(file_hash(p)==e['sha256'],'FIFA_SOURCE_HASH_MISMATCH',e['local_path'])
            inputs[e['local_path']]=e['sha256']
    aff_fields,aff=read_csv(folder/'fifa_affiliations.csv',AFF_FIELDS)
    cross_fields,cross=read_csv(folder/'label_crosswalk.csv',CROSS_FIELDS)
    ensure(aff_fields==AFF_FIELDS and cross_fields==CROSS_FIELDS,'FIFA_FIELDS_INVALID','Unexpected CSV columns')
    policy=load_json(folder/'population_policy.json')
    exceptions=load_json(folder/'historical_exceptions.json')['exceptions']
    events=load_json(folder/'admission_events.json')['events']
    ensure(all(r['evidence_id'] in evidence for r in [*aff,*cross,*events]),'FIFA_EVIDENCE_MISSING','Unknown evidence ID')
    mapping,exact=validate_registry(data,aff,cross,exceptions,events,policy)
    rows=build_match_overlay(data,mapping,exact,exceptions,policy)
    sources={**code_hashes(root), **{p:file_hash(root/p) for p in ('scripts/build_team_identity.py','scripts/plan_team_identity.py')}}
    identity='identity-fifa-'+digest(json_bytes(dict(inputs=inputs,code=sources,format='utf8-bom-lf-v1')))[:20]
    out=safe(root,'data/processed/team_identity/'+identity)
    counts=dict(clean_matches=len(rows),previous_study_matches=sum(r['in_previous_study'] for r in rows),
        study_disposition=dict(sorted(Counter(r['change_from_previous_study'] for r in rows if r['in_previous_study']).items())),
        membership_status=dict(sorted(Counter(r['membership_status'] for r in rows).items())))
    artifacts={'match_identity.csv':csv_bytes(MATCH_FIELDS,rows),'association_registry.csv':csv_bytes(AFF_FIELDS,aff),
        'label_crosswalk.csv':csv_bytes(CROSS_FIELDS,cross),'population_policy.json':json_bytes(policy),
        'historical_exceptions.json':json_bytes(dict(exceptions=exceptions)),
        'checks.json':json_bytes(dict(passed=True,unique_matches=True,complete_clean_coverage=True,counts=counts,final_release=False)),
        'data_dictionary.md':('# FIFA会员资格覆盖表（临时发布）\n\n逐场表主键match_id，覆盖全部清洗比赛；双方来源编号和标签保留。'
            'source_team_id不是已审核历史实体ID；fifa_code只对应有据可查的会员，不合并来源球队。\n\n'
            'conditional_both_members仅表示按官方加入年份加明示连续性假设，双方可以暂纳入；不等于逐日资格已核验。'
            'pending待核不等于非会员；nonmember_evidence是至少一方早于已记录加入时间；outside_scope不进入本次1980—2024用途。\n\n'
            'eligible_under_provisional_policy不含原有非中立、赛事等条件，后续必须同时满足。'
            'in_previous_study只用于旧样本对账，不能当最终样本。full_history_verified恒false。\n\n'
            '现有显示名和历史继承尚未全面解决；不用于Elo历史身份或相关性分组验收。'
            'CSV为UTF-8 BOM/LF；布尔true/false；不含比分或场地事实修正。\n').encode('utf-8')}
    def unchanged():
        for p,h in {**inputs,**sources}.items():
            ensure(file_hash(safe(root,p))==h,'FIFA_INPUT_CHANGED',p)
    unchanged()
    if out.exists():
        result=verify_identity(root,(out/'identity_manifest.json').relative_to(root).as_posix())
        return dict(result,counts=counts,manifest=(out/'identity_manifest.json').relative_to(root).as_posix())
    out.mkdir(parents=True,exist_ok=False)
    try:
        outputs={}
        for name,content in artifacts.items():
            p=out/name
            with p.open('xb') as f:f.write(content)
            outputs[p.relative_to(root).as_posix()]=digest(content)
        unchanged()
        manifest=dict(schema_version='fifa-identity-release-v1',status='published_provisional',identity_version=identity,
            created_at_utc=datetime.now(timezone.utc).isoformat(),data_version=data['config']['data_version'],
            scope=data['scope'],policy_id=policy['policy_id'],full_history_verified=False,human_review_pending=True,
            input_frozen=False,final_release=False,inputs=inputs,code_hashes=sources,outputs=outputs,counts=counts,
            limitations=['Year-only admissions have no fabricated day.','Continuity after affiliation is an assumption, not a complete historical register.',
                'Unmapped labels and predecessor episodes are quarantined, not declared nonmembers.','Not approved for final population claims, Elo or inferential entity resolution.'])
        with (out/'identity_manifest.json').open('xb') as f:f.write(json_bytes(manifest))
    except Exception as e:
        with (out/'failure.json').open('xb') as f:f.write(json_bytes(dict(status='failed',error=str(e))))
        raise
    return dict(status='published_provisional',identity_version=identity,manifest=(out/'identity_manifest.json').relative_to(root).as_posix(),counts=counts,final_release=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group()
    g.add_argument('--config');g.add_argument('--verify')
    a=p.parse_args(argv)
    try:
        r=verify_identity(PROJECT,a.verify) if a.verify else run_build(PROJECT,a.config or 'config/team_identity_fifa.json')
        print(json.dumps(r,ensure_ascii=True));return 0
    except (PrepError,OSError,ValueError,KeyError,TypeError) as e:
        print(json.dumps(dict(status='failed',code=getattr(e,'code','FIFA_INPUT_INVALID'),message=str(e)),ensure_ascii=True),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
