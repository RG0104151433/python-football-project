"""Read-only paired evidence, bounded conditional references and small prior probes.

Historical reuse prevents a real-world nominal coverage claim. Subset diagnostics
evaluate already-issued forecasts; they never refit a model on a reduced sample.
"""
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import io
import math
import time
import zipfile

import numpy as np
from threadpoolctl import threadpool_limits

from src.data_contract import atomic_bytes, csv_bytes, file_hash, fingerprint, write_json
from src.strength.io import ROOT, environment, read_rows
from .contracts import read_json
from .protocol import log_losses, paired_radius


def normalize(rows):
    result = []
    for r in rows:
        if str(r['home_win']) not in ('0', '1'):
            raise ValueError('INVALID_BINARY_LABEL')
        day = date.fromisoformat(r['date']).isoformat()
        if day != r['date'] or ('year' in r and int(r['year']) != int(day[:4])):
            raise ValueError('DATE_YEAR_MISMATCH')
        p = float(r['probability'])
        if not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('INVALID_PROBABILITY')
        result.append(dict(match_id=r['match_id'], date=day,
                           home_win=int(r['home_win']), probability=p))
    result.sort(key=lambda r: (r['date'], r['match_id']))
    if not result or len({r['match_id'] for r in result}) != len(result):
        raise ValueError('EMPTY_OR_DUPLICATE_MATCH')
    return result


def pair(a, b, epsilon):
    a, b = normalize(a), normalize(b)
    if [(r['match_id'], r['date'], r['home_win']) for r in a] != [
            (r['match_id'], r['date'], r['home_win']) for r in b]:
        raise ValueError('PAIRED_FACTS_DIFFER')
    y = [r['home_win'] for r in a]
    la = log_losses([r['probability'] for r in a], y, epsilon)
    lb = log_losses([r['probability'] for r in b], y, epsilon)
    return a, la, lb, la - lb


def assert_alias(a, b):
    if normalize(a) != normalize(b):
        raise ValueError('REGISTERED_ALIAS_DIFFER')


def daily(rows, differences):
    if len(rows) != len(differences):
        raise ValueError('DAILY_LENGTH_MISMATCH')
    grouped = defaultdict(list)
    for r, d in zip(rows, differences):
        grouped[r['date']].append(float(d))
    return [dict(date=day, matches=len(values), loss_difference_sum=math.fsum(values))
            for day, values in sorted(grouped.items())]


def subset_metric(rows, la, lb, mask, name):
    mask = np.asarray(mask, bool)
    if mask.shape != la.shape or la.shape != lb.shape or len(rows) != len(mask):
        raise ValueError('SUBSET_MASK_MISMATCH')
    n = int(mask.sum())
    delta = float(np.mean((la-lb)[mask])) if n else None
    return dict(diagnostic=name, matches=n, candidate_loss=float(la[mask].mean()) if n else None,
                baseline_loss=float(lb[mask].mean()) if n else None, mean_loss_minus_baseline=delta,
                descriptive_direction='candidate_lower' if delta is not None and delta < 0 else
                'baseline_lower' if delta is not None and delta > 0 else 'tie' if n else 'empty',
                refitted=False, formal_inference=False)


def seed_comparisons(rows, cfg):
    seeds = set(cfg['simulation_seeds'])
    paths, links = cfg['simulation_paths'], cfg['simulation_links']
    baseline = cfg['simulation_baseline']
    policies = [baseline] + [f'annual_reset_{w}y' for w in cfg['windows']]
    cells = {}
    for r in rows:
        key = (int(r['seed']), r['path'], r['link'], r['policy_name'])
        if key in cells or int(r['months']) != 120:
            raise ValueError('SIMULATION_DUPLICATE_OR_SCOPE')
        for field in ('gap_mse', 'native_probability_mse'):
            if not math.isfinite(float(r[field])) or float(r[field]) < 0:
                raise ValueError('INVALID_SIMULATION_ERROR')
        cells[key] = r
    expected = {(s, p, l, w) for s in seeds for p in paths for l in links for w in policies}
    if set(cells) != expected:
        raise ValueError('MISSING_OR_EXTRA_SIMULATION_SEED_CELL')
    result = []
    for path in paths:
        for link in links:
            for policy in policies[1:]:
                out = dict(path=path, link=link, policy_name=policy, baseline=baseline,
                           independent_seed_groups=len(seeds), real_world_coverage=False)
                for field in ('gap_mse', 'native_probability_mse'):
                    diffs = np.array([float(cells[s, path, link, policy][field])-
                                      float(cells[s, path, link, baseline][field])
                                      for s in sorted(seeds)])
                    out[field+'_difference'] = float(diffs.mean())
                    out[field+'_paired_mcse'] = float(diffs.std(ddof=1)/math.sqrt(len(seeds)))
                    out[field+'_candidate_lower_seed_groups'] = int(np.sum(diffs < 0))
                result.append(out)
    return result


def prior_engine(roster, parameters, numerics, scale, team_variance, home_variance):
    from src.strength.collapsed_jump import CollapsedJumpFilter
    return CollapsedJumpFilter(roster, parameters, numerics,
                               team_variance*scale, home_variance*scale)


def native_prior_probes(cfg, target_ids, target_day, log):
    """Six pre-fixed endpoint probes. No fitting of downstream outcome models."""
    from .ratings import load_inputs, numerical_cache
    from .replay import forecast
    _, games, _, _, params, num, inputs = load_inputs()
    probe = cfg['native_prior_probe']
    targets = [g for g in games if g['match_id'] in target_ids]
    if {g['match_id'] for g in targets} != set(target_ids) or any(g['date'] != target_day for g in targets):
        raise ValueError('PROBE_TARGET_MEMBERSHIP_CHANGED')
    result, ledger = [], []
    for years in probe['annual_window_years']:
        left = f'{int(target_day[:4])-years}-01-01'
        past = [g for g in games if left <= g['date'] < target_day]
        roster = {g[k] for g in past+targets for k in ('home', 'away')}
        grouped = defaultdict(list)
        for g in past:
            grouped[g['date']].append(g)
        for scale in probe['joint_prior_variance_scales']:
            job = log/'probe_jobs'/f'years{years}-scale{scale}.json'
            identity = dict(years=years, scale=scale, target_day=target_day, left=left,
                            history_sha=fingerprint(past), targets_sha=fingerprint(sorted(target_ids)),
                            parameters=params, numerics=num,
                            team_prior=probe['base_team_variance']*scale,
                            home_prior=probe['base_home_variance']*scale)
            if job.exists():
                old = read_json(job)
                if old['identity'] != identity:
                    raise ValueError('PRIOR_PROBE_CACHE_CHANGED')
                result.extend(old['rows']); ledger.append(old['ledger']); continue
            started = time.perf_counter()
            engine = prior_engine(roster, params, num, scale, probe['base_team_variance'],
                                  probe['base_home_variance'])
            with numerical_cache():
                for day, batch in sorted(grouped.items()):
                    if time.perf_counter()-started > probe['max_job_seconds']:
                        raise TimeoutError('PRIOR_PROBE_BUDGET')
                    engine.day(day, batch)
                preds = forecast(engine, target_day, targets)
            rr = [dict(years=years, prior_variance_scale=scale,
                       **{k:r[k] for k in ('match_id', 'date', 'difference', 'difference_variance',
                                         'p_home', 'p_draw', 'p_away', 'home_history', 'away_history')})
                  for r in preds]
            item = dict(**identity, history_rows=len(past), history_dates=len(grouped),
                        seconds=time.perf_counter()-started, prediction_cutoff=engine.last_day,
                        scope='native endpoint probe; no downstream refit; not cumulative sensitivity')
            if not all(abs(r['p_home']+r['p_draw']+r['p_away']-1) < 1e-8 for r in rr):
                raise ValueError('PROBE_PROBABILITIES_INVALID')
            write_json(job, dict(identity=identity, rows=rr, ledger=item))
            result.extend(rr); ledger.append(item)
            print('PRIOR_PROBE_COMPLETE', years, scale, round(item['seconds'], 2), flush=True)
    for r in result:
        base = next(b for b in result if b['years'] == r['years'] and
                    b['match_id'] == r['match_id'] and b['prior_variance_scale'] == 1)
        r['native_home_probability_difference'] = r['p_home']-base['p_home']
        r['native_strength_difference_change'] = r['difference']-base['difference']
    return result, ledger, inputs


def run(config_path='config/history_window_reliability.json'):
    cfg = read_json(ROOT/config_path)
    original = read_json(ROOT/'config/history_window.json')
    if (cfg['schema_version'] != 'history-window-reliability-v1' or cfg['main_years'] != [2010, 2024]
            or cfg['windows'] != [2, 4, 8, 12, 20] or cfg['expected_matches'] != 9727
            or cfg['real_historical_nominal_coverage'] is not False
            or cfg['production_admissible_loss_tolerance'] is not None
            or cfg['production_cost_budget'] is not None):
        raise ValueError('RELIABILITY_PROTOCOL_CHANGED')
    old = original['pairwise_inference']
    if (cfg['alpha'] != old['alpha'] or cfg['maximum_registered_pairs'] != old['maximum_registered_pairs']
            or cfg['lambda_powers'] != old['lambda_powers']
            or cfg['probability_clip'] != original['probability_clip']):
        raise ValueError('ORIGINAL_ERROR_BUDGET_CHANGED')
    inputs = {config_path:file_hash(ROOT/config_path),
              'config/history_window.json':file_hash(ROOT/'config/history_window.json')}
    parents = {}
    for key in ('outcome_run', 'rating_run', 'joint_run', 'joint_review_run'):
        path = f'outputs/logs/history_window/{cfg[key]}/manifest.json'
        parents[key] = read_json(ROOT/path)
        inputs[path] = file_hash(ROOT/path)
    # Existing dependency graph binds old source manifests to the adopted joint.
    for child, parent in [('joint_run', 'outcome_run'), ('joint_run', 'rating_run'),
                          ('joint_review_run', 'joint_run')]:
        p = f'outputs/logs/history_window/{cfg[parent]}/manifest.json'
        if parents[child]['identity']['inputs'][p] != inputs[p]:
            raise ValueError('PARENT_MANIFEST_CHANGED:'+p)

    def take(parent, path, frozen_key=None):
        expected = parents[parent]['outputs'][path]
        actual = file_hash(ROOT/path)
        if actual != expected or (frozen_key and actual != cfg['frozen_prediction_sha256'][frozen_key]):
            raise ValueError('INPUT_CHANGED:'+path)
        inputs[path] = actual
        return path

    tables = {k:f'outputs/tables/history_window/{cfg[k]}' for k in parents}
    sources = dict(
        outcome=take('outcome_run', tables['outcome_run']+'/predictions.csv', 'outcome'),
        adaptive=take('outcome_run', tables['outcome_run']+'/adaptive_predictions.csv', 'adaptive'),
        rating=take('rating_run', tables['rating_run']+'/rating_predictions.csv', 'rating'),
        joint=take('joint_run', tables['joint_run']+'/predictions.csv', 'joint'),
        simulation=take('rating_run', tables['rating_run']+'/latent_seed_metrics.csv', 'simulation'))
    cost_path = take('joint_review_run', tables['joint_review_run']+'/cost_components.csv')
    for name in ('strict_probes.csv', 'annual_reset_diagnostics.csv'):
        take('rating_run', tables['rating_run']+'/'+name)
    features = {}
    for policy in ['cumulative_1950']+[f'annual_reset_{w}y' for w in cfg['windows']]:
        path = f'data/processed/history_window/{policy}-1c8aebdf661c/prematch_features.csv'
        features[policy] = take('rating_run', path)
    # Snapshot every dependency used by the six small native probes too.
    from .ratings import load_inputs
    _, _, _, _, _, _, probe_inputs = load_inputs()
    inputs.update(probe_inputs)
    for p, h in parents['rating_run']['identity']['code'].items():
        if p.startswith('src/strength/') or p in ('src/history_window/ratings.py', 'src/history_window/replay.py'):
            if file_hash(ROOT/p) != h:
                raise ValueError('NATIVE_ENGINE_CHANGED:'+p)
    files = [*sorted((ROOT/'src/history_window').glob('*.py')),
             *sorted((ROOT/'src/strength').glob('*.py')), ROOT/'src/data_contract.py',
             ROOT/'scripts/analyze_history_window.py', ROOT/'tests/test_history_window_reliability.py']
    identity = dict(protocol=cfg, inputs=inputs,
                    code={p.relative_to(ROOT).as_posix():file_hash(p) for p in files}, environment=environment())
    rid = 'reliability-'+fingerprint(identity)[:20]
    log = ROOT/'outputs/logs/history_window'/rid
    table = ROOT/'outputs/tables/history_window'/rid
    if (log/'manifest.json').exists():
        for p, h in read_json(log/'manifest.json')['outputs'].items():
            if file_hash(ROOT/p) != h:
                raise ValueError('RELIABILITY_OUTPUT_CHANGED:'+p)
        print('RELIABILITY_VERIFIED_COMPLETE', rid, flush=True)
        return log, table
    log.mkdir(parents=True, exist_ok=True); table.mkdir(parents=True, exist_ok=True)
    write_json(log/'protocol.json', cfg)
    write_json(log/'started.json', dict(identity=identity, scientific_choices_fixed_before_new_results=True))
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as z:
        for p in files+[ROOT/config_path]:
            z.writestr(zipfile.ZipInfo(p.relative_to(ROOT).as_posix(), (1980,1,1,0,0,0)), p.read_bytes())
    atomic_bytes(log/'source_snapshot.zip', archive.getvalue())
    try:
        with threadpool_limits(limits=cfg['threads']):
            return _execute(cfg, sources, features, cost_path, identity, rid, log, table)
    except Exception as exc:
        write_json(log/'failure.json', dict(type=type(exc).__name__, message=str(exc)))
        raise


def _execute(cfg, sources, features, cost_path, identity, rid, log, table):
    lo, hi = cfg['main_years']
    def main(rows):
        return [r for r in rows if lo <= int(r['date'][:4]) <= hi]
    data = {k:main(read_rows(ROOT/p)) for k,p in sources.items() if k != 'simulation'}
    def choose(source, field, value):
        return [r for r in data[source] if r[field] == value]
    baseline = choose('outcome', 'window', 'cumulative')
    registry, vectors, policies = [], {'BASE':baseline}, {'BASE':'cumulative_1950'}
    def add(name, source, field, value, policy, alias_of=''):
        rr = choose(source, field, value)
        rows, _, _, _ = pair(rr, baseline, cfg['probability_clip'])
        if len(rows) != cfg['expected_matches']:
            raise ValueError('COMMON_SAMPLE_COUNT_CHANGED:'+name)
        if alias_of:
            assert_alias(rr, vectors[alias_of])
        else:
            vectors[name] = rr; policies[name] = policy
        registry.append(dict(comparison_id=name, alias_of=alias_of, source_file=sources[source],
                             selector=field+'='+value, rating_policy=policy, matches=len(rows),
                             prediction_vector_sha256=fingerprint(rows)))
    add('BASE', 'outcome', 'window', 'cumulative', 'cumulative_1950', 'BASE')
    for w in cfg['windows']:
        add(f'T{w:02}', 'outcome', 'window', f'{w}y', 'cumulative_1950')
        add(f'R{w:02}', 'rating', 'policy_name', f'annual_reset_{w}y', f'annual_reset_{w}y')
    for w in (20, 12):
        add(f'J{w}T12', 'joint', 'combination_id', f'annual_reset_{w}y__outcome_12y', f'annual_reset_{w}y')
    add('A', 'adaptive', 'policy_id', 'adaptive-prior-years', 'cumulative_1950')
    add('alias_R_cumulative', 'rating', 'policy_name', 'cumulative_1950', 'cumulative_1950', 'BASE')
    for value, canonical, policy in [
            ('cumulative_1950__outcome_cumulative', 'BASE', 'cumulative_1950'),
            ('cumulative_1950__outcome_12y', 'T12', 'cumulative_1950'),
            ('annual_reset_12y__outcome_cumulative', 'R12', 'annual_reset_12y'),
            ('annual_reset_20y__outcome_cumulative', 'R20', 'annual_reset_20y')]:
        add('alias_J_'+canonical, 'joint', 'combination_id', value, policy, canonical)
    if len(registry) != 19 or len(vectors) != 14 or len({fingerprint(normalize(v)) for v in vectors.values()}) != 14:
        raise ValueError('FROZEN_POLICY_REGISTRY_CHANGED')
    feature_rows = {p:{r['match_id']:r for r in main(read_rows(ROOT/path))} for p,path in features.items()}
    canonical = normalize(baseline)
    dates = Counter(r['date'] for r in canonical)
    radius = paired_radius(list(dates.values()), cfg['probability_clip'], cfg['alpha'],
                           cfg['maximum_registered_pairs'], cfg['lambda_powers'])
    daily_rows, refs, sens, yearly = [], [], [], []
    for name, rr in vectors.items():
        if name == 'BASE':
            continue
        a, la, lb, delta = pair(rr, baseline, cfg['probability_clip'])
        daily_rows.extend(dict(comparison_id=name, **d) for d in daily(a, delta))
        leave = []
        for year in range(lo, hi+1):
            item = subset_metric(a, la, lb, [int(r['date'][:4]) != year for r in a], f'exclude_evaluation_year_{year}')
            sens.append(dict(comparison_id=name, **item)); leave.append(item['mean_loss_minus_baseline'])
            yearly.append(dict(comparison_id=name, year=year, **subset_metric(
                a, la, lb, [int(r['date'][:4]) == year for r in a], 'single_evaluation_year')))
        original_by_id = {r['match_id']:r for r in rr}
        for kind in cfg['sensitivity']['tournament_groups']:
            mask = [original_by_id[r['match_id']]['tournament_group'] == kind for r in a]
            sens.append(dict(comparison_id=name, **subset_metric(a, la, lb, mask, 'tournament_'+kind)))
        for start, end in cfg['sensitivity']['periods']:
            sens.append(dict(comparison_id=name, **subset_metric(a, la, lb,
                [start <= int(r['date'][:4]) <= end for r in a], f'period_{start}_{end}')))
        for months in cfg['sensitivity']['calendar_month_groups']:
            sens.append(dict(comparison_id=name, **subset_metric(a, la, lb,
                [int(r['date'][5:7]) in months for r in a], 'months_'+'_'.join(map(str, months)))))
        mask = []
        threshold = cfg['sensitivity']['common_non_cold_start_minimum_both_team_history']
        for r in a:
            aa = feature_rows[policies[name]][r['match_id']]
            bb = feature_rows['cumulative_1950'][r['match_id']]
            if aa['date'] != r['date'] or bb['date'] != r['date']:
                raise ValueError('COLD_START_FEATURE_DATE_DIFFER')
            mask.append(min(int(x[k]) for x in (aa, bb) for k in ('home_history','away_history')) >= threshold)
        cold = subset_metric(a, la, lb, mask, 'common_both_policies_non_cold_start')
        sens.append(dict(comparison_id=name, **cold))
        point = float(delta.mean())
        refs.append(dict(comparison_id=name, matches=len(a), dates=len(dates),
            candidate_loss=float(la.mean()), baseline_loss=float(lb.mean()),
            mean_loss_minus_baseline=point, conditional_reference_radius=radius,
            reference_lower=point-radius, reference_upper=point+radius,
            real_historical_nominal_coverage=False,
            inference_grade='applicability_not_admitted_and_bound_cannot_resolve',
            descriptive_leave_one_year_min=min(leave), descriptive_leave_one_year_max=max(leave),
            leave_one_year_sign_stable=all(x*point > 0 for x in leave),
            common_non_cold_start_matches=cold['matches'],
            common_non_cold_start_difference=cold['mean_loss_minus_baseline'],
            equivalence_admitted=False, full_pipeline_initialization_sensitivity=False))
    simulations = seed_comparisons(read_rows(ROOT/sources['simulation']), cfg)
    first_day = min(dates)
    ids = {r['match_id'] for r in canonical if r['date'] == first_day}
    probe_rows, probe_ledger, _ = native_prior_probes(cfg, ids, first_day, log)
    # Default probes must reproduce the stored annual-policy native predictions.
    max_base_error = 0.
    for r in probe_rows:
        stored = feature_rows[f"annual_reset_{r['years']}y"][r['match_id']]
        if r['prior_variance_scale'] == 1:
            max_base_error = max(max_base_error, *(abs(r[k]-float(stored[k])) for k in ('p_home','p_draw','p_away')))
    if max_base_error > 1e-8:
        raise ValueError('PRIOR_PROBE_DEFAULT_NOT_REPRODUCED')
    costs = read_rows(ROOT/cost_path)
    bounds_sum_squares = sum(n*n for n in dates.values())
    lower_bound = math.log((1-cfg['probability_clip'])/cfg['probability_clip'])*math.sqrt(
        2*math.log(2*cfg['maximum_registered_pairs']*len(cfg['lambda_powers'])/cfg['alpha'])/len(canonical))
    if radius < lower_bound or any(not (r['reference_lower'] < 0 < r['reference_upper']) for r in refs):
        raise ValueError('BOUND_ARITHMETIC_INCONSISTENT')
    applicability = dict(
        real_historical_nominal_coverage=False, history_reused=True,
        reference_target='average conditional expected paired clipped log loss along the fixed observed schedule',
        reason='researcher selection and retrospective cohort predictability not established; conditional formula only',
        independent_matches_assumed=False, maximum_registered_pairs=cfg['maximum_registered_pairs'],
        alpha=cfg['alpha'], day_counts_sum=len(canonical), sum_squared_day_counts=bounds_sum_squares,
        conditional_reference_radius=radius, analytical_radius_lower_bound=lower_bound,
        formal_inference_admitted=False, simulation_unit='10 independent seed groups; MCSE only',
        subset_diagnostics='fixed issued predictions; no retraining; changed evaluation populations',
        prior_probe='two annual endpoints, one prespecified day, joint variance scaling; native only',
        prior_probe_target_date=first_day,
        unverified=['full-period downstream initialization sensitivity', 'cumulative-rating initialization sensitivity',
                    'strict-W full-period calibrated predictions', 'new blind future test',
                    'scientific noninferiority margin and end-to-end standardized cost frontier'])
    grade = []
    for r in refs:
        grade.append(dict(comparison_id=r['comparison_id'],
            mean_loss_minus_baseline=r['mean_loss_minus_baseline'],
            historical_point_direction='baseline_lower' if r['mean_loss_minus_baseline'] > 0 else 'candidate_lower',
            statistical_direction_support='not_admitted', equivalence='not_established',
            leave_one_year_sign_stable=r['leave_one_year_sign_stable'],
            initialization_validation='native_endpoint_probe_only; no full downstream claim',
            allowed_claim='historical paired loss and descriptive sensitivity only',
            recommendation='retain original cumulative default; no statistically guaranteed unique optimum'))
    for name, rows in [('comparison_registry.csv',registry), ('daily_paired_losses.csv',daily_rows),
                       ('conditional_reference.csv',refs), ('simulation_paired_summary.csv',simulations),
                       ('sensitivity.csv',sens), ('yearly_paired.csv',yearly),
                       ('native_prior_probes.csv',probe_rows), ('evidence_grades.csv',grade)]:
        atomic_bytes(table/name, csv_bytes(list(rows[0]), rows))
    write_json(log/'native_prior_ledger.json', probe_ledger)
    write_json(log/'applicability.json', applicability)
    conclusion = dict(default_retained='cumulative_1950__outcome_cumulative',
        baseline_lowest_historical_point=all(r['mean_loss_minus_baseline'] > 0 for r in refs),
        formal_statistical_winner_established=False, equivalence_established=False,
        real_historical_nominal_coverage=False, no_unique_optimal_cycle=True,
        new_outcome_fits=0, new_large_simulations=0, native_endpoint_replay_jobs=len(probe_ledger),
        prior_probe_max_abs_native_home_probability_change=max(abs(r['native_home_probability_difference']) for r in probe_rows),
        initialization_scope='local native endpoint diagnostic; cannot validate full outcome-prediction pipeline',
        controlled_cost_scope='same R10 outcome design/fit/predict only; 66.31percent saving is not end-to-end',
        step7_closed_scope='conditional-reference failure documented; descriptive sensitivity and local prior probes complete',
        next_step='internal step8 interpretation, paper/showcase archive, same-version sources and final handoff',
        human_review=False)
    write_json(log/'conclusions.json', conclusion)
    write_json(table/'display_data.json', dict(run_id=rid, comparison_metrics=refs, evidence_grades=grade,
               simulation=simulations, cost_source=cost_path, cost_rows=len(costs), conclusions=conclusion,
               applicability=applicability, no_real_world_confidence_guarantee=True))
    review = dict(passed=True, registry_rows=len(registry), distinct_series=len(vectors),
                  baseline_comparisons=len(refs), common_matches=len(canonical), dates=len(dates),
                  daily_rows=len(daily_rows), sensitivity_rows=len(sens), yearly_rows=len(yearly),
                  simulation_comparisons=len(simulations), independent_simulation_seed_groups=10,
                  native_probe_jobs=len(probe_ledger), native_probe_rows=len(probe_rows),
                  default_native_probe_max_probability_error=max_base_error,
                  checks='source hashes and manifests, exact facts and aliases, finite forecasts, common subsets, complete seeds, analytical radius lower bound, stored native default reproduction',
                  new_outcome_fits=0, new_large_simulation_histories=0, human_review=False,
                  formal_real_world_inference=False)
    write_json(log/'review.json', review)
    outputs = {p.relative_to(ROOT).as_posix():file_hash(p) for folder in (log, table)
               for p in folder.iterdir() if p.is_file() and p.name not in ('manifest.json','failure.json')}
    write_json(log/'manifest.json', dict(identity=identity, outputs=outputs))
    write_json(log/'adoption.json', dict(run_id=rid, manifest_sha256=file_hash(log/'manifest.json'),
               scope='Q6 step7 limited-scope reliability and sensitivity; no formal real-world inference',
               internal_step8_ready=True, question6_fully_closed=False, human_review=False))
    write_json(ROOT/'outputs/logs/history_window/reliability_pointer.json',dict(run_id=rid,
               log_directory=log.relative_to(ROOT).as_posix(), table_directory=table.relative_to(ROOT).as_posix(),
               step7_complete_in_declared_scope=True, internal_step8_ready=True, formal_real_world_inference=False))
    print('RELIABILITY_COMPLETE',rid,review,flush=True)
    return log, table
