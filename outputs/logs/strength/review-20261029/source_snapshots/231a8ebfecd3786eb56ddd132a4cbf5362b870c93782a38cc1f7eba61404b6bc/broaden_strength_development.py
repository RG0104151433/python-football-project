"""Twenty-team budget check and bounded global scalability probe, <=1974."""
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
    cfg=config()
    protocol=json.loads((ROOT/"config/strength_broad_development.json").read_text(encoding="utf-8"))
    source=ROOT/protocol["learning"]
    raw=read_rows(source)
    all_games=[dict(match_id=r["match_id"],date=r["date"],home=r["home_entity_id"],away=r["away_entity_id"],
                   home_label=r["home_team"],away_label=r["away_team"],
                   venue=0 if r["is_neutral"]=="true" else 1,friendly=r["tournament_group"]=="friendly",
                   outcome=int(r["outcome_index"])) for r in raw if r["date"]<=protocol["end"]]
    scope20=set(protocol["teams20"])
    games20=[g for g in all_games if g["home_label"] in scope20 and g["away_label"] in scope20]
    metrics,predictions,diagnostics,failures,timing=[],[],[],[],[]
    previous=None
    begin=time.perf_counter()
    for scope,size in [("twenty",b) for b in protocol["components20"]]+[("global_profile",protocol["global_profile_components"])]:
        games=games20 if scope=="twenty" else all_games
        groups=defaultdict(list)
        for g in games: groups[g["date"]].append(g)
        groups=sorted(groups.items())
        if scope=="global_profile": groups=groups[:protocol["global_profile_days"]]
        numerical={**cfg["numerics"],"reducer":"cluster","max_components":size,"jump_total_cap":3,
                   "max_children_per_parent":2048,"max_child_bytes":protocol["max_child_bytes"],
                   "full_child_psd_check":False,"retained_psd_check_every":25}
        e=ReducedStrengthFilter({g[k] for g in games for k in ("home","away")},params(cfg,{"id":"both"}),numerical)
        forecasts=[]
        start=time.perf_counter()
        try:
            for day,batch in groups:
                forecasts.extend(e.day(day,batch))
                if time.perf_counter()-start>protocol["timing_budget_seconds_per_profile"]:
                    raise RuntimeError("Predeclared feasibility time budget exceeded")
            evaluation=[r for r in forecasts if r["date"]>=protocol["score_start"]]
            current={r["match_id"]:r for r in evaluation}
            gap=None if scope!="twenty" or previous is None else max(max(abs(r[k]-previous[mid][k]) for k in ("p_home","p_draw","p_away")) for mid,r in current.items())
            metrics.append(dict(scope=scope,components=size,**score(evaluation),completed_matches=len(forecasts),
                 previous_probability_difference=gap,within_gate=None if gap is None else gap<=protocol["probability_gate"]))
            if scope=="twenty": previous=current
            predictions.extend(dict(scope=scope,components=size,**r) for r in forecasts)
            diagnostics.extend(dict(scope=scope,components=size,**r) for r in e.diagnostics)
            print(metrics[-1],flush=True)
        except Exception as err:
            failures.append(dict(scope=scope,components=size,date=day,completed_matches=len(forecasts),error=type(err).__name__+": "+str(err)))
            print(failures[-1],flush=True)
        timing.append(dict(scope=scope,components=size,seconds=time.perf_counter()-start))
    folder,_=publish("broad-development",{"protocol":protocol,"base":cfg,"input_sha":file_hash(source),
                         "runner_sha":file_hash(Path(__file__))},
            csvs={**({"metrics.csv":metrics} if metrics else {}),**({"predictions.csv":predictions,"diagnostics.csv":diagnostics} if predictions else {})},
            jsons={"failures.json":failures,"report.json":{"production_ready":False,"development_only":True}})
    write_json(folder/"execution_timing.json",{"runs":timing,"total_seconds":time.perf_counter()-begin})
    print(folder.relative_to(ROOT).as_posix(),flush=True)


if __name__=="__main__": main()
