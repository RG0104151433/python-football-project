"""Explain the retained first-screen failure without modifying its gates."""
from pathlib import Path
import csv,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import write_json


def run():
    log=ROOT/'outputs/logs/strength_inference';folder=ROOT/json.loads((log/'comparison_pointer.json').read_text())['directory']
    config=json.loads((ROOT/'config/strength_inference_validation.json').read_text());cal=json.loads((folder/'scope_calibration.json').read_text())
    scale=np.array(cal['fixed_original_scales_pp']);registry=list(csv.DictReader((ROOT/'outputs/tables/strength_joint/stage6-preparation-662dd5a756b8c1bf7688/target_registry.csv').open(encoding='utf-8-sig')))
    registry=[r for r in registry if r['family']=='F_PRIMARY_CONDITIONAL'];out=[]
    for sc in config['scenarios']:
        selected={r for r in cal['scenarios'][sc['id']]['registry_ids']};indices=[j for j,r in enumerate(registry) if r['registry_id'] in selected]
        for route in ('A','B'):
            critical=cal['scenarios'][sc['id']]['methods'][route]['critical'];bad=[];ratios=[]
            for seed in range(*sc['validation_seeds']):
                fit=json.loads((folder/'fits'/sc['id']/'validation'/f'{seed}.json').read_text())
                standardized=abs(np.array(fit['A_error_pp']))/scale;ratio=max(standardized[indices])/critical;ratios.append(ratio)
                if ratio>1:
                    j=max(indices,key=lambda j:standardized[j]);bad.append(dict(seed=seed,registry_id=registry[j]['registry_id'],
                        error_pp=fit['A_error_pp'][j],half_width_pp=critical*scale[j],ratio=float(ratio),
                        multistart_loss_spreads={m:max(t['loss'] for t in r['trials'])-min(t['loss'] for t in r['trials']) for m,r in fit['models'].items()},
                        gradients={m:r['gradient'] for m,r in fit['models'].items()}))
            out.append(dict(scenario=sc['id'],route=route,outside_worlds=bad,maximum_width_ratio=max(ratios),
                interpretation='finite64 screen uncertainty; retain failure and check new independent histories, do not tune width'))
    report=dict(details=out,models_widths_and_gates_unchanged=True)
    write_json(log/'initial_screen_diagnostic.json',report);print(json.dumps(report))


if __name__=='__main__':run()
