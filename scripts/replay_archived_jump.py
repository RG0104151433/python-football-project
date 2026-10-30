"""Repeat the exact archived scorer, checking all numeric core outputs bytewise.

Only an isolated archived import tree is created; original source/data untouched.
Auxiliary calibration modules changed later are not substituted into old runs.
"""
from pathlib import Path
from collections import defaultdict
import argparse
import csv
import hashlib
import json
import sys
import zipfile
import time


def sha(data):return hashlib.sha256(data).hexdigest()


def main(value):
    root=Path(__file__).resolve().parents[1];folder=root/value
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    archived=root/'outputs/logs/strength/repair-20261029/replays'/folder.name
    archived.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(folder/'source_snapshot.zip') as z:
        for name,digest in manifest['identity']['code'].items():
            text=z.read(name).decode('utf-8');actual=sha(json.dumps(text,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
            if actual!=digest:raise ValueError('Archive changed')
            path=(archived/name).resolve()
            if not path.is_relative_to(archived.resolve()):raise ValueError('Unsafe archive path')
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists() and path.read_bytes()!=text.encode():raise ValueError('Conflicting archived import')
            path.write_text(text,encoding='utf-8',newline='\n')
    (archived/'src/__init__.py').write_text('',encoding='utf-8')
    sys.path.insert(0,str(archived))
    from src.strength.collapsed_jump import CollapsedJumpFilter
    from src.data_contract import csv_bytes
    source=root/'outputs/logs/strength/learning-b2889411cc93b44f88b6/learning_matches.csv'
    for name,digest in manifest['identity']['inputs'].items():
        if sha((root/name).read_bytes())!=digest:raise ValueError('Input changed')
    with source.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
    games=[dict(match_id=r['match_id'],date=r['date'],home=r['home_entity_id'],away=r['away_entity_id'],
        venue=0 if r['is_neutral']=='true' else 1,friendly=r['tournament_group']=='friendly',outcome=int(r['outcome_index']),
        study=r['accepted_current_study']=='true') for r in raw]
    identity=manifest['identity'];p=identity['parameters'];num=identity['numerics'];model=identity['model']
    e=CollapsedJumpFilter({g[k] for g in games for k in ('home','away')},p,num)
    groups=defaultdict(list)
    for g in games:groups[g['date']].append(g)
    remaining=sorted(json.loads((folder/'checkpoints.json').read_text(encoding='utf-8')))
    rows=[];states={};start=time.perf_counter()
    for i,(day,gs) in enumerate(sorted(groups.items())):
        while remaining and remaining[0]<day:
            boundary=remaining.pop(0);states[boundary]=dict(asof=boundary,state=e.state())
        rows.extend(e.day(day,gs))
        if i%1000==0:print('ARCHIVED_REPLAY',i,day,flush=True)
    while remaining:
        boundary=remaining.pop(0);states[boundary]=dict(asof=boundary,state=e.state())
    study={g['match_id'] for g in games if g['study']}
    features=[dict(**{k:v for k,v in r.items() if k!='outcome_index'},rating_run_id=folder.name,
        rating_rules_version='collapsed-jump-v1-'+model,accepted_study=r['match_id'] in study,
        input_learning_version='learning-b2889411cc93b44f88b6') for r in rows]
    output={'prematch_features.csv':csv_bytes(list(features[0]),features),
        'study_prematch_features.csv':csv_bytes(list(features[0]),[r for r in features if r['accepted_study']]),
        'diagnostics.csv':csv_bytes(list(e.diagnostics[0]),e.diagnostics),
        'checkpoints.json':(json.dumps(states,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()}
    results={name:sha(value)==manifest['outputs'][name] for name,value in output.items()}
    # Complete final state supplements older run's last dated checkpoint, never overwrites it.
    final=dict(asof='2024-12-31',last_observed_date=e.last_day,state=e.state(),
        source_manifest_sha=sha((folder/'manifest.json').read_bytes()),representation='lazy_calendar; next day propagation from last observations')
    (archived/'recovered_final_state.json').write_text(json.dumps(final,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    result=dict(passed=all(results.values()),files=results,rows=len(features),study_rows=len(study),
        directory=folder.relative_to(root).as_posix(),archived_source_replayed=True,seconds=time.perf_counter()-start,
        final_checkpoint=(archived/'recovered_final_state.json').relative_to(root).as_posix(),
        final_checkpoint_sha=sha((archived/'recovered_final_state.json').read_bytes()),human_review='not_performed')
    (root/'outputs/logs/strength/repair-20261029'/('replay_'+model+'.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('ARCHIVED_PROOF',json.dumps(result),flush=True)
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');main(p.parse_args().folder)
