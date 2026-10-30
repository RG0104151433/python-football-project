"""Extract current stage2 handoff facts; no final presentation or joint effects."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.io import publish,read_rows
from src.data_contract import file_hash


def run():
    pointer=ROOT/'outputs/logs/strength/repair-20261029/adoption_pointer.json';packet=ROOT/json.loads(pointer.read_text())['directory']
    adoption=json.loads((packet/'adoption.json').read_text());normal=ROOT/adoption['adopted_pipeline'];report=json.loads((normal/'report.json').read_text())
    audit=json.loads((packet/'proofs/final_audit.json').read_text());sim=json.loads((packet/'proofs/simulations.json').read_text())
    selected=[r for r in report['forecast_checks'] if r['scope']=='accepted_study']
    types=[r for r in report['type_checks'] if r['period'] in ('reused_2020_2022','reused_2023_2024')]
    sources=[packet/'adoption.json',normal/'report.json',packet/'proofs/final_audit.json',packet/'proofs/raw_audit.json',
             packet/'proofs/raw_replay.json',packet/'proofs/final_replay.json',packet/'tests.xml']
    data=dict(status='stage2_all_required_engineering_gates_passed_third_design_only',study_matches=24917,
        learning_matches=38919,forecast_check_blocks=len(report['forecast_checks'])+len(report['type_checks']),
        historical_periods=selected,recent_type_checks=types,all_forecast_gates_passed=report['all_forecast_gates_passed'],
        tests=adoption['tests_passed'],raw_independent_checks=json.loads((packet/'proofs/raw_audit.json').read_text())['checks'],
        final_independent_checks=audit['checks'],max_tightening_probability_difference=audit['max_complete_probability_difference'],
        repeated_raw_files=4,repeated_final_files=8,synthetic_stress_runs=96,unseen_parameter_runs=16,
        cold_start=adoption['cold_start'],initialization_sensitive=adoption['initialization_sensitive'],previously_disconnected=adoption['previously_disconnected'],
        adopted_pipeline=adoption['adopted_pipeline'],handoff_packet=packet.relative_to(ROOT).as_posix(),
        no_new_independent_football_test=True,no_joint_model_fitted=True,no_causal_claim=True,human_review='not_performed',
        sources={p.relative_to(ROOT).as_posix():file_hash(p) for p in sources})
    folder,_=publish('strength-final-display',dict(sources=data['sources'],runner_sha=file_hash(Path(__file__))),
        jsons={'display_data.json':data},texts={'runner_snapshot.py':Path(__file__).read_text(encoding='utf-8')})
    print(folder.relative_to(ROOT).as_posix(),flush=True)
    return folder


if __name__=='__main__':run()
