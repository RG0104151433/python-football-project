"""Independent read-only review; writes only this directory's review.json."""
import csv
import hashlib
import html
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
PKG = ROOT / 'data/external/geography_preparation/geo-prep-v2'
RUN = ROOT / 'outputs/logs/regions/preparation-20261026T074311Z-af547658-r1'
REPEAT = ROOT / 'outputs/logs/regions/preparation-20261026T074344Z-af547658-r2'
LAYERS = [(e, t) for e in ['1980s', '1990s', '2000s', '2010s', '2020_2024']
          for t in ['friendly', 'non_friendly']]


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flag(value):
    if value.strip().lower() not in {'true', 'false'}:
        raise ValueError(value)
    return value.strip().lower() == 'true'


def main():
    checks, findings, hashes, fingerprints = [], [], [], {}

    def check(name, passed, detail=None):
        checks.append(dict(name=name, passed=bool(passed), detail=detail))

    def fingerprint(path):
        fingerprints[str(path.relative_to(ROOT))] = digest(path)
        return fingerprints[str(path.relative_to(ROOT))]

    input_sets = []
    for run in [RUN, REPEAT]:
        manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
        fingerprint(run / 'manifest.json')
        for name, expected in manifest['files'].items():
            hashes.append(fingerprint(run / name) == expected)
        inputs = json.loads((run / 'inputs_used.json').read_text(encoding='utf-8'))
        input_sets.append(inputs)
        for v in inputs.values():
            if 'sha256' in v:
                hashes.append(fingerprint(ROOT / v['path']) == v['sha256'])
        hashes.append(digest(run / inputs['script']['snapshot']) == inputs['script']['snapshot_sha256'])
    check('registered_run_and_input_hashes', all(hashes), len(hashes))
    inputs = input_sets[0]
    package_paths = list(PKG.rglob('*'))
    for p in package_paths:
        if p.is_file():
            fingerprint(p)
    check('two_runs_15_core_csv_identical', len(list(RUN.glob('*.csv'))) == 15 and all(
        digest(p) == digest(REPEAT / p.name) for p in RUN.glob('*.csv')))
    critical = ['team_geography_seed.csv', 'carrier_model.csv', 'region_dictionary.csv',
                'candidate_specs.csv', 'exceptions.csv', 'sources.csv']
    missing_bound = [p for p in critical if not any(
        str(v.get('path', '')).replace('\\', '/').endswith('/' + p) and 'sha256' in v
        for v in inputs.values())]
    if missing_bound:
        findings.append(dict(id='P1', issue='Critical package inputs not fingerprinted or snapshotted in the submitted run',
                             files=missing_bound, affects='Historical reproducibility; current outputs still independently checkable'))

    q2 = read(ROOT / inputs['q2_membership']['path'])
    clean = read(ROOT / inputs['matches_clean']['path'])
    selected = [r for r in q2 if r['included'] == 'true']
    source = {r['match_id']: r for r in clean}
    rel = read(RUN / 'match_region_relations.csv')
    check('original_clean_unique', len(source) == len(clean))
    check('same_24917_unique_ids', len(selected) == len(rel) == 24917 and
          len({r['match_id'] for r in rel}) == len(rel) and
          {r['match_id'] for r in selected} == {r['match_id'] for r in rel})
    check('q2_bool_and_version', {r['included'] for r in q2} == {'true', 'false'} and
          len({(r['data_version'], r['identity_version'], r['sample_id']) for r in q2}) == 1)
    members = {r['match_id']: r for r in selected}
    rules = read(RUN / 'team_geography_rules.csv')
    by_team = defaultdict(list)
    for r in rules:
        by_team[r['team_id']].append(r)
    continuity = []
    for tid, rs in by_team.items():
        ordered = sorted(rs, key=lambda x: x['date_start'])
        if ordered[0]['date_start'] != '1980-01-01' or ordered[-1]['date_end'] != '2024-12-31':
            continuity.append(tid)
        for a, b in zip(ordered, ordered[1:]):
            if date.fromisoformat(a['date_end']) + timedelta(days=1) != date.fromisoformat(b['date_start']):
                continuity.append(tid)
    check('all_rule_intervals_contiguous_unique', not continuity, continuity)
    dictionary = read(PKG / 'region_dictionary.csv')
    units = {r['area_code']: r for r in dictionary if r['is_project_unit'] == 'true'}
    check('22_mutually_identified_units', len(units) == 22)
    check('rules_fine_parent', all(not r['project_unit_code'] or
          units[r['project_unit_code']]['project_parent_code'] == r['project_region_code'] for r in rules))
    tree = {}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', (PKG / 'sources/m49_overview.html').read_text(encoding='utf-8'), re.S):
        cells = [re.sub(r'\s+', ' ', re.sub('<[^>]+>', '', html.unescape(s))).strip()
                 for s in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)]
        indexes = [i for i, c in enumerate(cells) if re.fullmatch('[A-Z]{2}', c)]
        if not indexes or indexes[0] < 6 or 'World' not in cells[:indexes[0]]:
            continue
        prefix = cells[:indexes[0]-2]
        codes = prefix[::2]
        for parent, child in zip(codes, codes[1:]):
            tree[child] = parent
    check('raw_dictionary_parents_match_saved_standard', all(
        r['raw_parent_code'] == tree.get(r['area_code'])
        for r in dictionary if r['original_level'] in {'subregion', 'intermediate'}))
    errors = []
    for r in rel:
        c, m = source[r['match_id']], members[r['match_id']]
        expected = {k: m[k] for k in ['data_version', 'identity_version', 'sample_id']}
        expected.update(date=c['date'], era=m['analysis_era_id'], tournament_group=m['tournament_group'])
        for role in ['home', 'away']:
            tid = c[role+'_team_id']
            hits = [x for x in by_team[tid] if x['date_start'] <= c['date'] <= x['date_end']]
            if len(hits) != 1:
                errors.append(r['match_id']); continue
            x = hits[0]
            expected.update({role+'_team_id':tid, role+'_region':x['project_region_code'],
                             role+'_unit':x['project_unit_code'], role+'_rule_id':x['rule_id']})
        hr, ar, hu, au = [expected.get(k, '') for k in ['home_region','away_region','home_unit','away_unit']]
        relation = ('unknown_region' if not hr or not ar else 'cross_region' if hr != ar else
                    'unknown_same_region' if not hu or not au else 'same_unit' if hu == au else 'same_region_diff_unit')
        expected.update(direction=f'{hr}>{ar}' if hr and ar else '', relation=relation)
        ok = all(r[k] == v for k, v in expected.items())
        ok &= flag(r['A_usable']) == bool(hr) and flag(r['C_usable']) == bool(hu)
        ok &= flag(r['B_usable']) == (relation in {'same_unit','same_region_diff_unit','cross_region'})
        ok &= c['date'] == m['date'] and c['tournament_group'] == m['tournament_group']
        ok &= c['source_record_id'] == m['source_record_id'] and c['is_neutral'] == 'false'
        ok &= '1980-01-01' <= c['date'] <= '2024-12-31'
        if not ok:
            errors.append(r['match_id'])
    check('all_match_assignments_reconstructed_from_original_inputs', not errors, errors[:5])
    inventory = read(RUN / 'team_inventory.csv')
    hc, ac = Counter(r['home_team_id'] for r in rel), Counter(r['away_team_id'] for r in rel)
    check('215_team_inventory_counts', len(inventory) == 215 and all(
        int(r['home_matches']) == hc[r['team_id']] and int(r['away_matches']) == ac[r['team_id']]
        and int(r['total_matches']) == hc[r['team_id']]+ac[r['team_id']] for r in inventory))
    definitions = [('counts_home_region_era_tournament.csv',['home_region','era','tournament_group']),
                   ('counts_home_unit_era_tournament.csv',['home_unit','era','tournament_group']),
                   ('counts_relation_era_tournament.csv',['home_region','relation','era','tournament_group']),
                   ('counts_direction_matrix.csv',['home_region','away_region'])]
    for file, keys in definitions:
        actual = Counter(tuple(r[k] or 'UNKNOWN' for k in keys) for r in rel)
        table = read(RUN / file)
        seen = {tuple(r[k] for k in keys):int(r['matches']) for r in table}
        check(file+':counts', len(seen) == len(table) and all(seen.get(k) == v for k,v in actual.items())
              and all(actual[k] == v for k,v in seen.items()))
    specs = read(PKG / 'candidate_specs.csv')
    support = read(RUN / 'candidate_reference_support.csv')
    index = {r['candidate_id']:r for r in specs}
    def arm(c, no, r):
        if c['candidate_type'] == 'A':
            return r['home_region'] == c[f'arm{no}_definition'].split('=')[1]
        if r['home_region'] != c['background_region']:
            return False
        return r['relation'] == c[f'arm{no}_relation'] if c['candidate_type'] == 'B' else r['home_unit'] == c[f'arm{no}_unit']
    support_errors = []
    for r in support:
        c = index[r['candidate_id']]
        layer = [x for x in rel if (x['era'],x['tournament_group']) == (r['era'],r['tournament_group'])]
        gn = sum(arm(c,int(r['arm_no']),x) for x in layer)
        rn = sum(not c['background_region'] or x['home_region'] == c['background_region'] for x in layer)
        status = 'reference_layer_absent' if not rn else 'group_missing_layer' if not gn else 'supported'
        if (gn,rn,status, rn>0) != (int(r['group_matches']),int(r['reference_matches']),r['support_status'],flag(r['reference_requires_layer'])):
            support_errors.append(r)
    check('340_arm_reference_support_cells_rebuilt', len(support)==340 and not support_errors, len(support_errors))
    check('17_disjoint_two_arm_candidates', sum(c['candidate_class']=='comparison_candidate' for c in specs)==17 and
          all(not any(arm(c,1,r) and arm(c,2,r) for r in rel) for c in specs if c['candidate_class']=='comparison_candidate'))
    comp_errors = []
    composition = read(RUN / 'composition_home_away.csv')
    for r in composition:
        layer = [x for x in rel if (x['era'],x['tournament_group']) == (r['era'],r['tournament_group'])]
        for role in ['home','away']:
            group = [x for x in layer if (x[role+'_'+r['level']] or 'UNKNOWN')==r['category']]
            teams = Counter(x[role+'_team_id'] for x in group)
            share = round(len(group)/len(layer),4) if layer else None
            top_share = round(max(teams.values())/len(group),4) if group else None
            valid = int(r[role+'_matches'])==len(group) and int(r['distinct_'+role+'_teams'])==len(teams)
            valid &= float(r[role+'_share_of_layer'])==share
            valid &= (r['top1_'+role+'_share']=='无法计算' if top_share is None else float(r['top1_'+role+'_share'])==top_share)
            if not valid:
                comp_errors.append((r['level'],r['category'],role))
    check('290_both_role_coverage_rows_rebuilt', len(composition)==290 and not comp_errors, comp_errors[:5])
    for r in read(RUN / 'candidate_arm_composition.csv'):
        c = index[r['candidate_id']]
        group = [x for x in rel if arm(c,int(r['arm_no']),x)]
        check(r['candidate_id']+':arm'+r['arm_no']+':composition', int(r['matches'])==len(group)
              and int(r['distinct_home_teams'])==len({x['home_team_id'] for x in group})
              and int(r['distinct_away_teams'])==len({x['away_team_id'] for x in group}))
    findings.append(dict(id='P2',issue='Per-team contributions not supplied for each comparison arm/layer: only role totals/top1 and away-region top3',
                         affects='Requested composition audit incomplete; recoverable from existing per-match table, no external collection required'))
    # Import pinned code for non-writing unit probes only, never run prepare/finalize.
    spec = importlib.util.spec_from_file_location('submitted_geo_v2', RUN/'code/prepare_region_mapping.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    m49 = mod.parse_m49(str(PKG/'sources/m49_overview.html'))
    self_tests = mod.run_self_tests(m49)
    check('11_real_function_self_tests_rerun', len(self_tests)==11 and all(x['passed'] for x in self_tests))
    mixed = [{'match_id':'demo','included':'True','data_version':'d','identity_version':'i','sample_id':'s'}]
    got = mod.load_q2_rows(mixed)
    mixed_lost = not [r for r in got if r['included']=='true']
    if mixed_lost:
        findings.append(dict(id='P3',issue='Boolean validator accepts True/whitespace variants but selection only accepts literal true',
                             evidence='One True row accepted by load_q2_rows then omitted by production selection',affects='Not current lowercase Q2 input; harden accepted input contract before reuse'))
    snapshot_root = Path(mod.ROOT)
    if snapshot_root != ROOT:
        findings.append(dict(id='P4',issue='Executing pinned script from code snapshot derives project ROOT from run directory',
                             evidence=str(snapshot_root.relative_to(ROOT)), affects='Snapshot alone not directly replayable with recorded commands; document restore layout or explicit project-root option'))
    findings.append(dict(id='P5',issue='InputError is printed to stdout without the promised structured failed-run report; missing joins can trigger later KeyError',
                         affects='Failure-report contract/reuse, not current successful arithmetic'))
    prior = json.loads((ROOT/'outputs/logs/regions/review-20261026-geo-prep-v1/review.json').read_text(encoding='utf-8'))
    old = [(p,h) for p,h in prior['source_fingerprints'].items() if '/geo-prep-v1/' in p.replace('\\','/') or '/preparation-20261026T040745Z-52745246/' in p.replace('\\','/')]
    check('old_v1_package_and_run_unchanged', all(digest(ROOT/p)==h for p,h in old),len(old))
    result = dict(schema_version='q3-preparation-v2-independent-review', executor='Codex (AI)',
                  created_at_utc=datetime.now(timezone.utc).isoformat(), source_run=str(RUN.relative_to(ROOT)),
                  checks=checks,check_count=len(checks),registered_fingerprint_checks=len(hashes),
                  all_performed_checks_passed=all(c['passed'] for c in checks), findings=findings,
                  target_counts={t:sum(flag(r[t+'_usable']) for r in rel) for t in 'ABC'},
                  adoption_status='arithmetic_reusable_targeted_handoff_and_input_hardening_required',
                  critical_package_inputs_not_bound=missing_bound, source_fingerprints=fingerprints,
                  audit_script_sha256=digest(Path(__file__)), production_outputs_modified=False,
                  regional_outcomes_computed=False,human_review='not_performed')
    (OUT/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ['check_count','registered_fingerprint_checks','all_performed_checks_passed',
                     'target_counts','adoption_status','critical_package_inputs_not_bound']},ensure_ascii=True))
    if not result['all_performed_checks_passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
