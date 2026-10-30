"""Frozen past-only calibration and rolling selection; reused-history tests."""
from pathlib import Path
import argparse
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.calibration import contextual_year
from src.strength.global_run import load,gate
from src.strength.baseline import frequency,fixed_step
from src.strength.handoff import choose_past
from src.strength.experiment import score,calibration
from src.strength.io import read_rows,publish
from src.data_contract import file_hash,write_json


def run(strict=False,extra=None,config_path='config/strength_repair_v5.json'):
    protocol=json.loads((ROOT/config_path).read_text(encoding="utf-8"))
    cfg,games,inputs=load(protocol["base_protocol"]);lookup={g["match_id"]:g for g in games}
    prior=json.loads((ROOT/protocol["previous_handoff"]/"report.json").read_text(encoding="utf-8"))
    names=["smooth_static","robust_static","robust_dynamic_shared","robust_type_dynamic"]
    sources={k:prior["candidate_directories"][k] for k in names}
    if extra:sources.update(extra)
    cache={};specs=[];states=[];metrics=[];raw_indexes={};bindings={}
    cp=protocol["calibration"];order=cp["strict_gh_order"] if strict else cp["gh_order"]
    for raw_name,source in sources.items():
        folder=ROOT/source;manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
        path=folder/"prematch_features.csv"
        if file_hash(path)!=manifest["outputs"]["prematch_features.csv"]:raise ValueError("Raw source changed")
        bindings[source]=file_hash(folder/"manifest.json")
        raw=read_rows(path);raw_indexes[raw_name]={r["match_id"]:r for r in raw}
        dates=np.array([int(r["date"][:4]) for r in raw]);ys=np.array([lookup[r["match_id"]]["outcome"] for r in raw])
        pp=np.array([[float(r[k]) for k in ("p_home","p_draw","p_away")] for r in raw])
        clipped=np.maximum(pp,1e-12);clipped/=clipped.sum(axis=1,keepdims=True)
        contexts=np.array([[int(lookup[r["match_id"]]["friendly"]),int(lookup[r["match_id"]]["venue"]==0)] for r in raw])
        for window in cp["window_years"]:
            for method in cp["methods"]:
                name=f"{raw_name}__{method}__{window}y";rows=[]
                for year in range(1960,2025):
                    past=(dates>=year-window)&(dates<year);now=dates==year
                    if not now.any():continue
                    if not past.any():raise ValueError("Missing earlier calibration history")
                    predicted,st=contextual_year(clipped[past],ys[past],contexts[past],clipped[now],contexts[now],method,
                        cp["ridge_precision"],cp["minimum_cell_matches"],order)
                    states.extend(dict(model=name,year=year,training_start=year-window,training_end=year-1,
                        **s) for s in st)
                    for k,(index,p) in enumerate(zip(np.flatnonzero(now),predicted)):
                        r=raw[index]
                        rows.append(dict(match_id=r["match_id"],date=r["date"],p_home=float(p[0]),p_draw=float(p[1]),p_away=float(p[2]),
                            outcome_index=int(ys[index]),calibration_cutoff=f"{year-1}-12-31"))
                cache[name]=rows
                base_modules=next((c["modules"] for c in json.loads((ROOT/"config/strength_handoff.json").read_text(encoding="utf-8"))["candidates"] if c["id"]==raw_name),4)
                specs.append(dict(id=name,raw=raw_name,modules=base_modules+2+int(method!="offset")))
                selected=[r for r in rows if r["date"]>="1980-01-01" and lookup[r["match_id"]]["study"]]
                metrics.append(dict(model=name,**score(selected)))
                print("CALIBRATION",name,metrics[-1],flush=True)
    choices=[];rolling=[]
    for year in range(1980,2025):
        losses={name:score([r for r in rows if year-10<=int(r["date"][:4])<year])["log_loss"] for name,rows in cache.items()}
        chosen=choose_past(specs,losses,protocol["rolling_selection"]["tie_margin"])
        raw_chosen=next(s['raw'] for s in specs if s['id']==chosen)
        if not protocol['rolling_selection'].get('contextual_calibration',False):
            for name,loss in losses.items():choices.append(dict(year=year,context='all',model=name,raw_model=raw_chosen,
                log_loss=loss,chosen=name==chosen,selection_scope='all'))
            rolling.extend(dict(r,selected_model=chosen,raw_model=raw_chosen,selector_cutoff=f"{year-1}-12-31")
                for r in cache[chosen] if r["date"].startswith(str(year)))
        else:
            for friendly in (False,True):
                for neutral in (False,True):
                    eligible=[r['match_id'] for r in cache[chosen] if year-10<=int(r['date'][:4])<year]
                    subset={mid for mid in eligible if lookup[mid]['friendly']==friendly and (lookup[mid]['venue']==0)==neutral}
                    scope='exact_context'
                    if len(subset)<200:subset={mid for mid in eligible if lookup[mid]['friendly']==friendly};scope='friendly_parent'
                    if len(subset)<200:subset=set(eligible);scope='pooled_parent'
                    limited=[s for s in specs if s['raw']==raw_chosen]
                    local_losses={s['id']:score([r for r in cache[s['id']] if r['match_id'] in subset])['log_loss'] for s in limited}
                    selected=choose_past(limited,local_losses,protocol['rolling_selection']['tie_margin'])
                    for name,loss in local_losses.items():choices.append(dict(year=year,context=f'{int(friendly)}:{int(neutral)}',
                        model=name,raw_model=raw_chosen,log_loss=loss,chosen=name==selected,selection_scope=scope))
                    rolling.extend(dict(r,selected_model=selected,raw_model=raw_chosen,selector_cutoff=f'{year-1}-12-31')
                        for r in cache[selected] if r['date'].startswith(str(year)) and lookup[r['match_id']]['friendly']==friendly and (lookup[r['match_id']]['venue']==0)==neutral)
    rolling.sort(key=lambda r:(r["date"],r["match_id"]))
    study_ids={g["match_id"] for g in games if g["study"]};base=frequency(games,1950);elo=fixed_step(games,40,100,.75,1950)
    checks=[];type_checks=[]
    for a,b in protocol["periods"]:
        period=dict(id=f"reused_{a}_{b}",start=f"{a}-01-01",end=f"{b}-12-31")
        checks.extend(gate(rolling,base,elo,period,study_ids,cfg))
        for friendly in (False,True):
            subset=[r for r in rolling if a<=int(r["date"][:4])<=b and r["match_id"] in study_ids and lookup[r["match_id"]]["friendly"]==friendly]
            n=len(subset);bias=float(np.mean([r["p_home"]-int(r["outcome_index"]==0) for r in subset]))
            bins=calibration(subset,"chosen");eligible=[r for r in bins if r["count"]>=200]
            error=max((abs(r["mean_probability"]-r["observed_frequency"]) for r in eligible),default=0)
            type_checks.append(dict(period=period["id"],friendly=friendly,**score(subset),home_bias=bias,
                max_bin_error=error,required=n>=200,passed=n<200 or abs(bias)<=.03 and error<=.1))
    features=[]
    for row in rolling:
        raw=raw_indexes[row["raw_model"]][row["match_id"]]
        features.append(dict(raw,raw_p_home=raw["p_home"],raw_p_draw=raw["p_draw"],raw_p_away=raw["p_away"],
            **{k:row[k] for k in ("p_home","p_draw","p_away","selected_model","raw_model","calibration_cutoff","selector_cutoff")}))
    sf=[r for r in features if r["match_id"] in study_ids]
    if len(sf)!=24917:raise ValueError("Lost study population")
    report=dict(protocol=protocol,source_directories=sources,strict=strict,forecast_checks=checks,type_checks=type_checks,
        all_forecast_gates_passed=all(r["passed"] for r in checks+type_checks),
        calibration_parameter_uncertainty="conditional Laplace Gaussian logit covariance integrated; no selection/misspecification guarantee",
        strength_posterior_changed_by_calibration=False,unopened_historical_test_remains=False,prospective_test_run=False,
        rows=len(features),study_rows=len(sf))
    folder,_=publish("repaired-calibration",{"protocol_sha":file_hash(ROOT/config_path),"inputs":inputs,
        "sources":bindings,"strict":strict,"runner_sha":file_hash(Path(__file__))},
        csvs={"prematch_features.csv":features,"study_prematch_features.csv":sf,"annual_choices.csv":choices,
            "candidate_metrics.csv":metrics},jsons={"report.json":report,"calibration_states.json":states},
        texts={"runner_snapshot.py":Path(__file__).read_text(encoding="utf-8")})
    print("REPAIRED",folder.relative_to(ROOT).as_posix(),json.dumps({k:v for k,v in report.items() if k not in {"protocol","forecast_checks","type_checks","source_directories"}}),flush=True)
    write_json(ROOT/"outputs/logs/strength/repair-20261029"/("strict_pointer.json" if strict else "normal_pointer.json"),
        dict(directory=folder.relative_to(ROOT).as_posix(),manifest_sha=file_hash(folder/"manifest.json")))
    return folder


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--strict",action="store_true");p.add_argument("--extra",help="JSON model-to-directory mapping")
    p.add_argument('--config',default='config/strength_repair_v5.json')
    args=p.parse_args();run(args.strict,json.loads(Path(args.extra).read_text(encoding="utf-8")) if args.extra else None,args.config)
