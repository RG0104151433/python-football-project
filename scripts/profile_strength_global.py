"""Pre-1975 global scaling check; no validation/test or parameter selection."""
from pathlib import Path
from collections import defaultdict
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.gaussian import GaussianStrengthFilter
from src.strength.io import config,read_rows,publish
from src.strength.experiment import params,score
from src.data_contract import file_hash,write_json


def main():
    cfg=config()
    source=ROOT/"outputs/logs/strength/learning-b2889411cc93b44f88b6/learning_matches.csv"
    games=[dict(match_id=r["match_id"],date=r["date"],home=r["home_entity_id"],away=r["away_entity_id"],
                venue=0 if r["is_neutral"]=="true" else 1,friendly=r["tournament_group"]=="friendly",
                outcome=int(r["outcome_index"])) for r in read_rows(source) if r["date"]<="1974-12-31"]
    grouped=defaultdict(list)
    for g in games: grouped[g["date"]].append(g)
    predictions,diags,reports,failures=[],[],[],[]
    begin=time.perf_counter()
    for name in ("smooth","robust"):
        p=params(cfg,next(c for c in cfg["pilot"]["candidates"] if c["id"]==name))
        engine=GaussianStrengthFilter({g[k] for g in games for k in ("home","away")},p,cfg["numerics"])
        rows=[]
        try:
            for day,batch in sorted(grouped.items()):
                rows.extend(engine.day(day,batch))
            state=engine.state()
            reports.append(dict(model=name,**score([r for r in rows if r["date"]>="1970"]),
                                all_matches=len(rows),entities=len(engine.teams),
                                minimum_checkpoint_eigenvalue=state["minimum_eigenvalue"],
                                max_ep_iterations=max(d["ep_iterations"] for d in engine.diagnostics)))
            predictions.extend(dict(model=name,**r) for r in rows)
            diags.extend(dict(model=name,**d) for d in engine.diagnostics)
            print(name,reports[-1],flush=True)
        except Exception as e:
            failures.append(dict(model=name,date=day,error=type(e).__name__+": "+str(e)))
            print(failures[-1],flush=True)
    folder,manifest=publish("global-profile",{"base":cfg,"input_sha":file_hash(source),
                "runner_sha":file_hash(Path(__file__)),"end":"1974-12-31","selection":False},
                csvs={**({"metrics.csv":reports,"predictions.csv":predictions,"diagnostics.csv":diags} if reports else {})},
                jsons={"failures.json":failures,"report.json":{"no_validation_or_post1980_used":True,"production_ready":False}})
    write_json(folder/"execution_timing.json",{"seconds":time.perf_counter()-begin,"nondeterministic":True})
    print(folder.relative_to(ROOT).as_posix(),flush=True)


if __name__=="__main__": main()
