"""Validate adoption, preserve old releases, and export current presentation data.

This only checks the Q2 input interface; it never estimates Q2 results.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.build_team_identity import verify_identity
from src.eras.reporting import verify_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--config', default='config/confirmed_eras_reviewed.json')
    args = parser.parse_args()
    root = ROOT
    def load(p):
        return json.loads((root / p).read_text(encoding='utf-8'))
    def rows(p):
        with (root / p).open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))
    def sha(p):
        return hashlib.sha256((root / p).read_bytes()).hexdigest()
    folder = (root / args.output_dir).resolve()
    if not folder.is_relative_to(root):
        raise ValueError('Output must stay inside repository')
    folder.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        with (folder / name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    checks = []
    def check(name, passed):
        checks.append(dict(name=name, passed=bool(passed)))
        if not passed:
            raise ValueError(name)
    cfg = load(args.config)
    im = load(cfg['identity_manifest'])
    run = load(args.run)
    verification = verify_run(root, args.run)
    identity_check = verify_identity(root, cfg['identity_manifest'])
    check('run_binds_current_config_and_identity', args.config in run['inputs'] and cfg['identity_manifest'] in run['inputs'])
    adoption = load('config/membership_review_adoption.json')
    old_im = load(adoption['base_identity_manifest'])
    old_check = verify_identity(root, adoption['base_identity_manifest'])
    def overlay(manifest):
        return {r['match_id']: r for r in rows(next(p for p in manifest['outputs'] if p.endswith('/match_identity.csv')))}
    old, new = overlay(old_im), overlay(im)
    clean_path = 'data/processed/' + im['data_version'] + '/matches_clean.csv'
    clean = {r['match_id']: r for r in rows(clean_path)}
    check('exact_overlay_and_clean_id_sets', set(old) == set(new) == set(clean))
    fact_fields = 'match_id source_record_id date home_source_team_id away_source_team_id home_source_label away_source_label home_fifa_code away_fifa_code in_previous_study full_history_verified'.split()
    check('source_fields_preserved', all(all(new[mid][k] == old[mid][k] for k in fact_fields) for mid in old))
    check('outside_study_decisions_preserved', all(all(new[mid][k] == old[mid][k] for k in old[mid] if k != 'policy_id') for mid in old if old[mid]['in_previous_study'] == 'false'))
    check('policy_id_consistent', {r['policy_id'] for r in new.values()} == {im['policy_id']})
    approval_path = next(p for p in im['outputs'] if p.endswith('/user_approval.json'))
    approval = load(approval_path)
    approved = set(approval['approved_match_ids'])
    selected = {mid for mid, r in new.items() if r['in_previous_study'] == 'true' and r['eligible_under_provisional_policy'] == 'true'}
    check('all_117_distinct_matches_adopted', len(approved) == 117 and approved <= selected)
    changes = Counter(old[mid]['change_from_previous_study'] + ' -> ' + new[mid]['change_from_previous_study'] for mid in old if old[mid]['in_previous_study'] == 'true')
    check('expected_scope_counts', len(selected) == 24917 and im['counts']['study_disposition'] == {'excluded_by_membership_evidence': 1138, 'retained': 24917})
    td = 'outputs/tables/eras/' + run['analysis_id']
    tables = {p.stem: rows(p.relative_to(root).as_posix()) for p in (root / td).glob('*.csv')}
    check('q1_exact_approved_population', selected == {r['match_id'] for r in tables['analysis_membership'] if r['in_classified_venue'] == 'true'})
    year_cells = Counter((int(clean[mid]['date'][:4]), clean[mid]['tournament_group']) for mid in selected)
    groups = ('friendly', 'non_friendly')
    missing = [(year, group) for year in range(1980, 2025) for group in groups if not year_cells[(year, group)]]
    interface = dict(selected_matches=len(selected), year_type_cells=len(year_cells), missing_year_type_cells=missing,
                     minimum_per_type={g: min(year_cells[(y, g)] for y in range(1980, 2025)) for g in groups},
                     complete_ten_year_windows=sum(all(year_cells[(y, g)] for y in range(start, start + 10) for g in groups) for start in range(1980, 2016)),
                     q2_effects_computed=False, scope='Input availability only; no Q2 effect estimates or inference')
    check('q2_input_has_all_90_cells_and_36_windows', not missing and interface['complete_ten_year_windows'] == 36)
    cell_rates = {(r['analysis_era_id'], r['tournament_group']): int(r['n_home_wins']) / int(r['n_matches']) for r in tables['era_tournament_summary']}
    for row in tables['weight_sensitivity']:
        contrast = next(c for c in load(cfg['analysis_config'])['primary_contrasts'] if c['id'] == row['contrast_id'])
        delta = {g: cell_rates[(contrast['later'], g)] - cell_rates[(contrast['earlier'], g)] for g in groups}
        w = float(row['weight_friendly'])
        expected = 100 * (w * delta['friendly'] + (1 - w) * delta['non_friendly'])
        check('curve:' + row['contrast_id'] + ':' + row['weight_friendly'], abs(float(row['difference_pp']) - expected) < 1e-8)
        flip = -delta['non_friendly'] / (delta['friendly'] - delta['non_friendly'])
        check('flip:' + row['contrast_id'] + ':' + row['weight_friendly'], abs(float(row['flip_weight']) - flip) < 1e-9)
    historical_runs = [
        'outputs/logs/team_identity/confirmed-eras-20261025T002437005064Z-f19d8184/run_manifest.json',
        cfg['previous_run']]
    preservation = {p: verify_run(root, p) for p in historical_runs}
    prior = load(historical_runs[0])
    comparison = dict(previous_run=historical_runs[0], current_run=args.run, previous_matches=prior['summary']['new_matches'],
                      current_matches=len(selected), added_matches=len(selected) - prior['summary']['new_matches'],
                      disposition_transitions=dict(sorted(changes.items())),
                      eras=[dict(era=r['era'], previous_n=prior['summary']['eras'][i]['new_n'], current_n=r['new_n'],
                                 previous_observed_rate=prior['summary']['eras'][i]['new_home_win_rate'], current_observed_rate=r['new_home_win_rate'],
                                 previous_standardized_rate=prior['summary']['eras'][i]['new_standardized_rate'], current_standardized_rate=r['new_standardized_rate']) for i, r in enumerate(run['summary']['eras'])])
    audit_path = (folder / 'independent_audit.json').relative_to(root).as_posix()
    audit = load(audit_path)
    check('independent_audit_is_this_run', audit['passed'] and audit['run_manifest'] == args.run)
    summary = run['summary']
    display = dict(schema_version='q1-current-display-v2', source_run=args.run, analysis_id=run['analysis_id'],
        identity_version=im['identity_version'], data_version=im['data_version'], publication_status='study_population_owner_accepted_description',
        decision_log_id='R20261025-10', sample_size=len(selected), population_flow=dict(summary['exclusions'], quarantined_pending=0),
        weight_friendly=summary['new_weight_friendly'], eras=[],
        primary_contrasts=summary['primary_contrasts'],
        weight_curve_flip_points={r['contrast_id']: r['flip_weight'] for r in tables['weight_sensitivity']},
        audit=dict(report=audit_path, passed_checks=len(audit['checks']), same_version_core_artifacts=audit['core_artifacts_identical']),
        limitations=['Descriptive results; formal inference and team-strength adjustment not run.', 'User-reviewed study population; not a complete historical FIFA register.', 'The last era covers five years.'],
        source_fingerprints={args.run: sha(args.run), cfg['identity_manifest']: sha(cfg['identity_manifest']), **run['outputs']},
        previous_display_data='outputs/logs/team_identity/full-chain-review-20261025/display_data.json',
        preparation_note='Current main presentation dataset; internal adoption details remain in membership records.',
        era_type_cells=[dict(era=r['analysis_era_id'], tournament_group=r['tournament_group'], **{k: int(r[k]) for k in ('n_matches','n_home_wins','n_draws','n_away_wins')}, home_win_rate=float(r['home_win_rate'])) for r in tables['era_tournament_summary']],
        reference_compositions=[dict(reference_id=r['reference_id'], scheme=r['scheme'], tournament_group=r['tournament_group'], weight=float(r['weight'])) for r in tables['reference_weights']],
        weight_curve=[dict(contrast_id=r['contrast_id'], weight_friendly=float(r['weight_friendly']), difference_pp=float(r['difference_pp']), flip_weight=float(r['flip_weight']), status=r['status']) for r in tables['weight_sensitivity']],
        figures=sorted(p for p in run['outputs'] if p.startswith('outputs/figures/')))
    by_era = {r['period_id']: r for r in tables['era_summary'] if r['sample_name'] == 'classified_venue'}
    display['eras'] = [dict(era=r['era'], n=r['new_n'], n_home_wins=int(by_era[r['era']]['n_home_wins']), observed_rate=r['new_home_win_rate'], standardized_rate=r['new_standardized_rate']) for r in summary['eras']]
    save('population_and_curve_checks.json', dict(passed=True, checks=checks, counts=im['counts'], approval=approval_path))
    save('interface_and_scope.json', interface)
    save('compare_previous.json', comparison)
    save('display_data.json', display)
    save('review.json', dict(passed=True, run_manifest=args.run, identity_manifest=cfg['identity_manifest'],
        current_verification=verification, identity_verification=identity_check, previous_identity_preserved=old_check,
        historical_run_verifications=preservation, checks=len(checks), independent_checks=len(audit['checks']),
        code_fingerprint=sha('scripts/closeout_reviewed_eras.py'), inference='not_run', q2='planning_only', human_basis='Project owner user; support not archived'))
    print(json.dumps(dict(passed=True, checks=len(checks), independent_checks=len(audit['checks']), interface=interface), ensure_ascii=True))


if __name__ == '__main__':
    main()
