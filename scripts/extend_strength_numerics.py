"""Next prespecified development-only merge and cost checks."""
from pathlib import Path
from collections import defaultdict
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.reduction import ReducedStrengthFilter
from src.strength.io import config,read_rows,publish
from src.strength.experiment import params,score
from src.data_contract import file_hash,write_json


def main():
    protocol=json.loads((ROOT/"config/strength_extended_numerics.json").read_text(encoding="utf-8"))
    broad=json.loads((ROOT/protocol["source_protocol"]).read_text(encoding="utf-8"))
    cfg=config()
    source=ROOT/broad["learning"]
    all_games=[dict(match_id=r["match_id"],date=r["date"],home=r["home_entity_id"],away=r["away_entity_id"],
        home_label=r["home_team"],away_label=r["away_team"],venue=0 if r["is_neutral"]=="true" else 1,
        friendly=r["tournament_group"]=="friendly",outcome=int(r["outcome_index"])) for r in read_rows(source)
        if r["date"]<=protocol["end"]]
    labels=set(broad["teams20"])
    games20=[g for g in all_games if g["home_label"] in labels and g["away_label"] in labels]
    predictions,metrics,failures,diagnostics,times=[],[],[],[],[]
    cache={}
    for run in protocol["runs"]:
        scope,method,size=run["scope"],run["method"],run["components"]
        games=games20 if scope=="twenty" else all_games
        groups=defaultdict(list)
        for g in games:groups[g["date"]].append(g)
        groups=sorted(groups.items())
        if scope=="global_profile":groups=groups[:protocol["global_profile_days"]]
        num={**cfg["numerics"],"reducer":method,"max_components":size,"jump_total_cap":3,
             "max_children_per_parent":2048,"max_child_bytes":protocol["max_child_bytes"],
             "full_child_psd_check":False,"retained_psd_check_every":25}
        e=ReducedStrengthFilter({g[k] for g in games for k in ("home","away")},params(cfg,{"id":"both"}),num)
        rows=[]
        begin=time.perf_counter()
        try:
            for day,batch in groups:
                rows.extend(e.day(day,batch))
                if time.perf_counter()-begin>protocol["per_run_seconds"]:raise RuntimeError("Feasibility time budget exceeded")
            chosen=[r for r in rows if r["date"]>=protocol["comparison_start"]]
            current={r["match_id"]:r for r in chosen}
            gap=None
            if scope=="twenty" and (method,size//2) in cache:
                previous=cache[(method,size//2)]
                gap=max(max(abs(r[k]-previous[mid][k]) for k in ("p_home","p_draw","p_away")) for mid,r in current.items())
            cache[(method,size)]=current
            metrics.append(dict(scope=scope,method=method,components=size,**score(chosen),completed_matches=len(rows),
                previous_probability_difference=gap,within_gate=None if gap is None else gap<=protocol["probability_gate"]))
            predictions.extend(dict(scope=scope,method=method,components=size,**r) for r in rows)
            diagnostics.extend(dict(scope=scope,method=method,components=size,**r) for r in e.diagnostics)
            print(metrics[-1],flush=True)
        except Exception as err:
            failures.append(dict(scope=scope,method=method,components=size,date=day,completed_matches=len(rows),
                error=type(err).__name__+": "+str(err)))
            print(failures[-1],flush=True)
        times.append(dict(scope=scope,method=method,components=size,seconds=time.perf_counter()-begin))
    folder,_=publish("extended-numerics",{"protocol":protocol,"broad":broad,"base":cfg,
        "input_sha":file_hash(source),"runner_sha":file_hash(Path(__file__))},
        csvs={**({"metrics.csv":metrics,"predictions.csv":predictions,"diagnostics.csv":diagnostics} if metrics else {})},
        jsons={"failures.json":failures,"report.json":{"production_ready":False,"no_validation_or_post1980":True}})
    write_json(folder/"execution_timing.json",{"runs":times})
    print(folder.relative_to(ROOT).as_posix(),flush=True)


if __name__=="__main__":main()
