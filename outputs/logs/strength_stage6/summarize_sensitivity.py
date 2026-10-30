"""Transparent descriptive summaries of all declared step3 runs; no inference."""
from pathlib import Path
import csv,io,json,hashlib
ROOT=Path(__file__).resolve().parents[3]
log=ROOT/'outputs/logs/strength_stage6'
pointer=json.loads((log/'sensitivity_pointer.json').read_text());dest=ROOT/pointer['directory']
manifest=json.loads((dest/'manifest.json').read_text());prep=ROOT/manifest['identity']['protocol']['preparation']
def read(p):return list(csv.DictReader(io.StringIO(p.read_text(encoding='utf-8-sig'))))
rows=read(dest/'contrasts.csv');registry=read(prep/'target_registry.csv')
primary={r['target_id'] for r in registry if r['family']=='F_PRIMARY_CONDITIONAL' and r['effect_size_axis']=='level'}
out=[]
for metric in read(dest/'fit_metrics.csv'):
    rr=[r for r in rows if r['fit_id']==metric['fit_id']]
    old=[r for r in rr if r['original_reference_all_scenarios_estimable']=='true']
    full=[r for r in old if r['reference_kind']=='full'];main=[r for r in full if r['target_id'] in primary]
    def flips(part):return [dict(target_id=r['target_id'],reference_kind=r['reference_kind'],base=float(r['common_reference_baseline_estimate_pp']),new=float(r['common_reference_new_estimate_pp'])) for r in part if float(r['common_reference_baseline_estimate_pp'])*float(r['common_reference_new_estimate_pp'])<0]
    def top(part):return sorted([dict(target_id=r['target_id'],reference_kind=r['reference_kind'],change_pp=float(r['change_at_common_reference_pp']),base_pp=float(r['common_reference_baseline_estimate_pp']),new_pp=float(r['common_reference_new_estimate_pp'])) for r in part],key=lambda r:abs(r['change_pp']),reverse=True)[:5]
    new=[r for r in rr if r['original_reference_all_scenarios_estimable']!='true']
    out.append(dict(**metric,original_estimable=len(old),new_reference_targets=len(new),
        new_reference_ranges=sorted({(int(r['original_reference_rows']),int(r['common_estimable_reference_rows'])) for r in new}),
        primary_original_estimable=len(main),primary_sign_flips=flips(main),all_full_sign_flips=flips(full),all_original_sign_flips=flips(old),
        top_primary_changes=top(main),top_full_changes=top(full),top_comparable_changes=top([r for r in rr if r['change_at_common_reference_pp']]),
        focus=[{k:r[k] for k in ('target_id','reference_kind','original_target_new_estimate_pp','common_reference_new_estimate_pp','common_reference_baseline_estimate_pp','change_at_common_reference_pp','reference_change','original_reference_rows','common_estimable_reference_rows')} for r in rr if r['target_id'].startswith(('Q1:','Q2:','Q3:B_'))]))
mean=read(dest/'mean_only_vs_full.csv');means=[]
for key in sorted({r['fit_id'] for r in mean}):
    subset=[r for r in mean if r['fit_id']==key];worst=max(subset,key=lambda r:abs(float(r['difference_from_mean_only_pp'])))
    means.append(dict(fit_id=key,targets=len(subset),maximum_abs_difference_from_old_mean_only_pp=abs(float(worst['difference_from_mean_only_pp'])),worst_target=worst['target_id']))
raw=ROOT/'data/raw/international_results/results.csv';clean=ROOT/'data/processed/prep-3fab808178cf8ad71d88/matches_clean.csv'
data_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (raw,clean)}
result=dict(directory=pointer['directory'],manifest_sha256=pointer['manifest_sha256'],model_summaries=out,mean_only_comparison=means,
            strength_slopes=read(dest/'strength_slopes.csv'),relation_points=read(dest/'relation_points.csv'),data_hashes=data_hashes,
            no_confidence_intervals=True,sign_agreement_is_not_statistical_significance=True,actual_human_review=False)
(log/'sensitivity_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='model_summaries'},ensure_ascii=False))
for r in out:print(json.dumps({k:v for k,v in r.items() if k not in ('focus','top_comparable_changes','top_full_changes','top_primary_changes')},ensure_ascii=False))
