"""Validated fixed-Q5 input for stage4; new rating policies need own adapters."""
import json
from src.data_contract import file_hash, fingerprint
from src.strength.io import ROOT
from src.strength_joint.contract import load


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def load_outcome(config_path='config/history_window_analysis.json'):
    cfg=read_json(ROOT/config_path)
    if cfg['schema_version']!='history-window-outcome-v1' or cfg['stage']!='outcome':
        raise ValueError('UNKNOWN_OUTCOME_PROTOCOL')
    base=read_json(ROOT/cfg['base_protocol'])
    if cfg['windows']!=base['candidate_years'] or [cfg['first_year'],cfg['last_year']]!=base['fixed_comparison_years']:
        raise ValueError('WINDOW_PROTOCOL_MISMATCH')
    if cfg['model']!=base['model'] or cfg['ridge_precision']!=base['ridge_precision'] or cfg['probability_clip']!=base['probability_clip']:
        raise ValueError('FROZEN_RULE_MISMATCH')
    joint,rows,_,_,inputs=load(cfg['study_config'])
    rows=sorted(rows,key=lambda r:(r['date'],r['match_id']))
    if len([r for r in rows if cfg['first_year']<=int(r['year'])<=cfg['last_year']])!=16599:
        raise ValueError('COMMON_PREDICTION_SAMPLE_CHANGED')
    if any(r['home_win'] not in ('0','1') or int(r['year'])!=int(r['date'][:4]) for r in rows):
        raise ValueError('INVALID_LABEL_OR_YEAR')
    inputs.update({config_path:file_hash(ROOT/config_path),cfg['base_protocol']:file_hash(ROOT/cfg['base_protocol']),
                   joint['input']+'/analysis_matches.csv':file_hash(ROOT/joint['input']/'analysis_matches.csv')})
    return cfg,joint,rows,inputs


def id_digest(rows):
    return fingerprint(sorted(r['match_id'] for r in rows))
