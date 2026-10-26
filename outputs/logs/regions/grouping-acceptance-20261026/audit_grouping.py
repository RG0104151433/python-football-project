"""Grouping acceptance and count-only study protocol check; no outcome rates."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
RUN = OUT / 'preparation-20261026T090739Z-82cd5e84-accepted-r1'
REPLAY = OUT / 'preparation-20261026T091035Z-82cd5e84-replay-r1'
V2 = ROOT / 'outputs/logs/regions/preparation-20261026T074311Z-af547658-r1'
PROTOCOL = ROOT / 'config/regions_study.json'


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks, fingerprints, hash_checks = [], {}, 0

    def check(name, ok, detail=None):
        checks.append(dict(name=name, passed=bool(ok), detail=detail))

    def bind(path):
        fingerprints[str(path.relative_to(ROOT))] = sha(path)
        return sha(path)

    for run in [RUN, REPLAY]:
        manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
        bind(run / 'manifest.json')
        for name, expected in manifest['files'].items():
            check('hash:'+str(run.name)+':'+name, bind(run/name)==expected)
            hash_checks += 1
        inputs = json.loads((run/'inputs/inputs_manifest.json').read_text(encoding='utf-8'))
        check(run.name+':13_input_snapshots', len(inputs['items'])==13)
        for role, item in inputs['items'].items():
            check(run.name+':source_and_snapshot:'+role,
                  bind(Path(item['source_path']))==item['sha256']==sha(run/item['snapshot_path']))
        report = json.loads((run/'validation_report.json').read_text(encoding='utf-8'))
        check(run.name+':all_runtime_checks', report['status']=='ok' and not report['failures']
              and all(c['passed'] for c in report['checks']))
        check(run.name+':14_internal_selftests', len(report['self_tests'])==14
              and all(c['passed'] for c in report['self_tests']))
    check('16_core_csv_snapshot_replay_identical', len(list(RUN.glob('*.csv')))==16
          and all(sha(p)==sha(REPLAY/p.name) for p in RUN.glob('*.csv')))
    check('current_code_is_accepted_snapshot', bind(ROOT/'scripts/prepare_region_mapping.py')==sha(RUN/'code/prepare_region_mapping.py'))
    prior = json.loads((ROOT/'outputs/logs/regions/review-20261026-geo-prep-v2/review.json').read_text(encoding='utf-8'))
    bind(ROOT/'outputs/logs/regions/review-20261026-geo-prep-v2/review.json')
    immutable = [(p,h) for p,h in prior['source_fingerprints'].items() if p!='scripts\\prepare_region_mapping.py'
                 and p!='scripts/prepare_region_mapping.py']
    check('prior_independent_v2_evidence_sources_unchanged', all(sha(ROOT/p)==h for p,h in immutable))
    rows = read(RUN/'match_region_relations.csv')
    old = {r['match_id']:r for r in read(V2/'match_region_relations.csv')}
    mismatches = []
    for r in rows:
        before = old.get(r['match_id'])
        if before is None:
            mismatches.append(r['match_id']); continue
        for key,value in r.items():
            if key.endswith('_rule_id'):
                continue
            expected = before[key].lower() if key.endswith('_usable') else before[key]
            if value != expected:
                mismatches.append((r['match_id'],key))
    check('24917_classifications_equal_independently_rebuilt_v2', len(rows)==24917
          and len({r['match_id'] for r in rows})==24917 and set(old)=={r['match_id'] for r in rows}
          and not mismatches, mismatches[:5])
    check('canonical_output_flags', all(r[t+'_usable'] in {'true','false'} for r in rows for t in 'ABC'))
    rules = {r['rule_id']:r for r in read(RUN/'team_geography_rules.csv')}
    check('new_rule_ids_match_actual_roles_and_dates', all(
        r[role+'_team_id']==rules[r[role+'_rule_id']]['team_id']
        and rules[r[role+'_rule_id']]['date_start']<=r['date']<=rules[r[role+'_rule_id']]['date_end']
        and r[role+'_region']==rules[r[role+'_rule_id']]['project_region_code']
        and r[role+'_unit']==rules[r[role+'_rule_id']]['project_unit_code']
        for r in rows for role in ['home','away']))
    specs = read(RUN/'inputs/package/candidate_specs.csv')
    expected, denominators = Counter(), Counter()
    for c in specs:
        if c['candidate_class']!='comparison_candidate':
            continue
        for no in [1,2]:
            def belongs(r):
                if c['candidate_type']=='A':
                    return r['home_region']==c[f'arm{no}_definition'].split('=')[1]
                if r['home_region']!=c['background_region']:
                    return False
                return r['relation']==c[f'arm{no}_relation'] if c['candidate_type']=='B' else r['home_unit']==c[f'arm{no}_unit']
            for r in rows:
                if not belongs(r):
                    continue
                cell=(c['candidate_id'],str(no),r['era'],r['tournament_group'])
                denominators[cell]+=1
                for role in ['home','away']:
                    expected[cell+(role,r[role+'_team_id'])]+=1
    contributions=read(RUN/'team_contributions.csv')
    seen={}
    for r in contributions:
        cell=tuple(r[k] for k in ['candidate_id','arm_no','era','tournament_group'])
        key=cell+(r['role'],r['team_id'])
        seen[key]=int(r['matches'])
        if int(r['denominator'])!=denominators[cell] or float(r['share'])!=round(expected[key]/denominators[cell],6):
            raise AssertionError(('Invalid contribution',key))
    check('29290_full_team_contributions_independently_rebuilt', len(contributions)==29290
          and len(seen)==len(contributions) and seen==dict(expected))
    protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    bind(PROTOCOL)
    bind(ROOT/'tests/test_region_preparation_contract.py')
    check('accepted_code_and_inputs_match_locked_protocol',
          protocol['grouping']['script_sha256']==sha(RUN/'code/prepare_region_mapping.py')
          and protocol['grouping']['input_manifest_sha256']==sha(RUN/'inputs/inputs_manifest.json'))
    groups=protocol['groups']
    def matches(g,r):
        if g['eligibility'] and r[g['eligibility']+'_usable']!='true':
            return False
        return all(not allowed or r[field] in allowed for field,allowed in [
            ('home_region',g['home_regions']),('home_unit',g['home_units']),('relation',g['relations'])])
    members={gid:[r for r in rows if matches(g,r)] for gid,g in groups.items()}
    cells={gid:Counter((r['era'],r['tournament_group']) for r in rs) for gid,rs in members.items()}
    layers=[(e['id'],t) for e in protocol['strata']['eras'] for t in protocol['strata']['tournament_groups']]
    check('five_macroregion_profiles_plus_unknown_reconcile', sum(len(members[g]) for g in protocol['profiles']['macroregions']['groups'])
          +sum(r['A_usable']=='false' for r in rows)==24917)
    check('south_america_nested_not_sixth_macroregion', all(r['home_region']=='019' and r['home_unit']=='005' for r in members['SA_FEATURE']))
    support=[]
    profile_support=[]
    for gid in protocol['profiles']['macroregions']['groups']+['SA_FEATURE']:
        for e,t in layers:
            rn,gn=cells['PARENT'][e,t],cells[gid][e,t]
            profile_support.append(dict(group_id=gid,era=e,tournament_group=t,group_matches=gn,reference_matches=rn))
    check('all_six_profiles_have_global_reference_support', all(r['group_matches']>0 for r in profile_support if r['reference_matches']>0))
    for c in protocol['comparisons']:
        g,h,ref=c['arm1'],c['arm2'],c['reference_group']
        check(c['id']+':disjoint_arms', not ({r['match_id'] for r in members[g]} & {r['match_id'] for r in members[h]}))
        missing=[]
        for e,t in layers:
            rn=cells[ref][e,t]
            for no,gid in [(1,g),(2,h)]:
                gn=cells[gid][e,t]
                state='not_required' if rn==0 else 'supported' if gn else 'unsupported_positive_reference_layer'
                if rn and not gn:
                    missing.append(dict(arm=no,era=e,tournament_group=t))
                support.append(dict(target_id=c['id'],role=c['role'],arm=no,group_id=gid,era=e,
                                    tournament_group=t,group_matches=gn,reference_matches=rn,status=state))
        check(c['id']+':planned_use_matches_support',
              not missing if c['role'] in {'primary','auxiliary'} else
              bool(missing) and c.get('standardized_policy')=='unestimable_for_full_period_no_scope_change')
    sa=members['SA_FEATURE']
    sa_teams=sorted({r['home_team_id'] for r in sa} | {r['away_team_id'] for r in rows if r['away_unit']=='005'})
    scope=dict(protocol_id=protocol['protocol_id'],protocol_sha256=sha(PROTOCOL),source_run=str(RUN.relative_to(ROOT)),
               outcome_rates_computed=False,group_counts={gid:len(rs) for gid,rs in members.items()},
               south_america=dict(home_matches=len(sa),team_ids=sa_teams,team_count=len(sa_teams),
                                  home_team_count=len({r['home_team_id'] for r in sa}),
                                  opponent_regions=dict(Counter(r['away_region'] or 'UNKNOWN' for r in sa))),
               reference_counts={gid:len(members[gid]) for gid in {c['reference_group'] for c in protocol['comparisons']}|{'PARENT'}},
               reference_layers={gid:[dict(era=e,tournament_group=t,numerator=cells[gid][e,t],denominator=len(members[gid])) for e,t in layers]
                                 for gid in {c['reference_group'] for c in protocol['comparisons']}|{'PARENT'}},
               profile_support=profile_support,
               target_support=[dict(id=c['id'],role=c['role'],arm1_matches=len(members[c['arm1']]),
                                    arm2_matches=len(members[c['arm2']]),
                                    status='supported' if not any(x['target_id']==c['id'] and x['status']=='unsupported_positive_reference_layer' for x in support) else 'unsupported_positive_reference_layer') for c in protocol['comparisons']],
               support_cells=support)
    (OUT/'scope_counts.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    result=dict(executor='Codex (AI)',created_at_utc=datetime.now(timezone.utc).isoformat(),
                accepted_run=str(RUN.relative_to(ROOT)),replay_run=str(REPLAY.relative_to(ROOT)),
                checks=checks,check_count=len(checks),registered_file_hash_checks=hash_checks,
                all_passed=all(c['passed'] for c in checks),target_counts={t:sum(r[t+'_usable']=='true' for r in rows) for t in 'ABC'},
                source_fingerprints=fingerprints,audit_code_sha256=sha(Path(__file__)),
                regional_outcomes_computed=False,formal_analysis_implemented=False,
                limitations=['Acceptance applies to current study scope, not universal absence of bugs',
                             'Historical geographic carriers and 99 relation-unknown matches remain explicit project policy',
                             'No causal or inferential validation'],human_review='not_performed')
    (OUT/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(checks=result['check_count'],all_passed=result['all_passed'],
                         hashes=hash_checks,south_america=scope['south_america'],
                         target_support=scope['target_support'],references=scope['reference_counts']),ensure_ascii=True))
    if not result['all_passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
