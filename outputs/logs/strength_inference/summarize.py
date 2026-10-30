"""Editorial summary of actual saved results; no new fits or coverage claims."""
from pathlib import Path
import json
import csv
import numpy as np
from src.data_contract import file_hash, write_json
from src.strength.io import ROOT

base = ROOT/'outputs/logs/strength_inference'
dp = json.loads((base/'diagnostic_pointer.json').read_text()); folder = ROOT/dp['directory']
rows = list(csv.DictReader((folder/'diagnostic_ranges.csv').open(encoding='utf-8-sig')))
report = json.loads((folder/'report.json').read_text())
bands = []
for b in (1,90,365,1095):
    rr = [r for r in rows if int(r['bandwidth_days']) == b]
    bands.append(dict(bandwidth_days=b, targets=len(rr), median_diagnostic_se_pp=float(np.median([float(r['diagnostic_se_pp']) for r in rr])),
        median_diagnostic_half_width_pp=float(np.median([(float(r['diagnostic_upper_pp'])-float(r['diagnostic_lower_pp']))/2 for r in rr])),
        max_t_critical=float(rr[0]['max_t_critical'])))
summary = dict(diagnostic=dp, B_seconds=report['seconds'], target_reconstruction_max_error_pp=report['registry_reconstruction_error_pp'],
    bandwidths=bands, development_only=True, final_method_selected=False, formal_inference_admitted=False,
    raw_hash=file_hash(ROOT/'data/raw/international_results/results.csv'),
    clean_hash=file_hash(ROOT/'data/processed/prep-3fab808178cf8ad71d88/matches_clean.csv'),
    helper_sha256=file_hash(Path(__file__)))
if (base/'pilot_pointer.json').exists():
    pp = json.loads((base/'pilot_pointer.json').read_text()); pf = ROOT/pp['directory']
    pr = json.loads((pf/'report.json').read_text()); er = list(csv.DictReader((pf/'world_estimates.csv').open(encoding='utf-8-sig')))
    worlds = []
    for world in pr['worlds']:
        rr = [r for r in er if int(r['seed']) == world['seed'] and r['axis']=='level']
        error = np.array([float(r['known_M3_error_pp']) for r in rr])
        worlds.append(dict(seed=world['seed'], learning_matches=world['learning_matches'], study_matches=world['study_matches'],
            seconds=world['total_seconds'], generation_seconds=world['seconds'], target_and_B_seconds=world['targets_and_B_seconds'],
            max_query_error=world['max_query_error'], known_M3_targets=len(rr), known_M3_RMSE_pp=float(np.sqrt(np.mean(error**2))),
            known_M3_mean_error_pp=float(error.mean()),
            diagnostic_known_truth_containment_count=sum(abs(float(r['known_M3_error_pp'])) <= float(r['B365_diagnostic_half_width_pp']) for r in rr),
            interpretation='27 dependent targets in one world, NOT 27 independent coverage repetitions'))
    summary.update(pilot=pp, worlds=worlds, mean_full_world_seconds=float(np.mean([w['seconds'] for w in worlds])),
        M0_truth_status=pr['truth_status'], independent_truth_worlds=pr['independent_truth_worlds'],
        projection_batch_coefficient_max_difference=float(np.max(abs(np.array(pr['M0_single_world_path_projections'][0]['theta'])-pr['M0_single_world_path_projections'][1]['theta']))))
write_json(base/'summary.json', summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
