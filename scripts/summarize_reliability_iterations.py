"""Adjudicate completed evidence, never upgrade a failed route automatically."""
import csv
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.reliability.experiment import write_json,write_csv
from src.reliability.design import sha


def load(p):return json.loads((ROOT/p).read_text(encoding="utf-8-sig"))
def rows(p):return list(csv.DictReader((ROOT/p).open(encoding="utf-8-sig",newline="")))


def main():
    base="outputs/logs/reliability/implementation-20261028"
    reg=load(base+"/current_runs.json");runs={}
    for path in reg["runs"]:
        m=load(path)
        if m["status"]=="running":raise RuntimeError("Await completion:"+path)
        runs[m["stage"]]=dict(path=path,manifest=m)
    protocol=load("config/reliability_validation_v1.json")
    scenarios={s["id"]:s for s in protocol["simulations"]["scenarios"]}
    full=runs["full-pilot"]["path"].rsplit("/",1)[0]
    records=[json.loads(x) for x in (ROOT/full/"replications.jsonl").read_text(encoding="utf-8").splitlines()]
    costs=[]
    for r in records:
        if r["replication"]==0:
            count=5000 if scenarios[r["scenario"]]["MP_domain"] else 1000
            c=r["fit_cpu"]+r["inner_B999_cpu"]
            costs.append(dict(scenario=r["scenario"],MP_domain=scenarios[r["scenario"]]["MP_domain"],
                formal_R=count,measured_fit_plus_B999_CPU_seconds=c,projected_CPU_hours=c*count/3600))
    weighted_hours=sum(r["projected_CPU_hours"] for r in costs)
    write_csv(ROOT/base/"cost_projection_audit.csv",costs)
    formal=runs["full-graph-oracle"]["path"].rsplit("/",1)[0]
    stats=rows(formal+"/metrics.csv")
    G=load("outputs/logs/reliability/refined-graph-20261028T010916841071Z/graph_constants.json")
    cat=rows("outputs/tables/reliability/design-e1ebd48827f8a5ff4be8/target_catalogue.csv")
    supported=[r for r in cat if r["status"]=="supported_point_target"]
    ids={f:[j for j,r in enumerate(supported) if r["family"]==f] for f in protocol["scope"]["families"]}
    graph=[]
    for method in ("G2-weighted","G3-Markov-choice"):
        for L in ("90","365","730","1460","all_dependent"):
            for family in ids:
                selected=[r for r in stats if r["method"]==method+":L="+L and r["family"]==family]
                all_markov=method.startswith("G3") and all(G[L]["markov_choice"][j] for j in ids[family])
                in_scope=[r for r in selected if all_markov or scenarios[r["scenario"]]["domain_MG_L_days"][L]]
                stress=[r for r in selected if r not in in_scope]
                graph.append(dict(method=method,L_days=L,family=family,all_targets_use_boundedness_only=all_markov,
                    original_graph_domain_counts=sum(s["domain_MG_L_days"][L] for s in scenarios.values()),
                    effective_in_domain_scenarios=len(in_scope),in_domain_numeric_gate_passes=sum(r["coverage_numeric_gate"]=="True" for r in in_scope),
                    in_domain_min_coverage=min(float(r["coverage_estimate"]) for r in in_scope),
                    in_domain_min_lower99=min(float(r["coverage_lower99"]) for r in in_scope),
                    mean_span_fraction=sum(float(r["mean_span_fraction"]) for r in in_scope)/len(in_scope),
                    near_full_fraction=sum(float(r["near_full_fraction"]) for r in in_scope)/len(in_scope),
                    stress_numeric_failures=sum(r["coverage_numeric_gate"]!="True" for r in stress),
                    graph_independence_factually_established=False))
    write_csv(ROOT/base/"graph_adjudication.csv",graph)
    oracle=[r for r in stats if r["method"]=="generator-oracle-not-fitted-MP"]
    pstats=rows(full+"/metrics.csv")
    failed=next(r for r in pstats if r["scenario"]=="C09" and r["method"]=="P3-trained-inflation" and r["family"]=="CONDITIONAL")
    result=dict(schema_version="method-adjudication-20261028-v1",decision_log_id="R20261028-02",
        status="no_informative_production_method_admitted_no_single_route_selected",retained_routes=["M-G","M-P"],
        production_estimator=None,actual_football_intervals_published=False,football_significance_claims=False,
        step_3_5="implemented_and_hand_checked_60_tests_passed",
        step_3_6=dict(M_G="18scenarios_times5000_full_design_completed",generator_oracle="18independent9999_reference_pools_and5000validation_each_not_fitted_MP",
            M_P="80fixture_development_and_full24917fixture_pilot_completed; fitted formal58000rounds_not_admitted_or_run"),
        step_3_7="conditional_math_and_scope_adjudicated; both uncertainty_information_and_cost_constraints_remain",
        step_3_8="iteration_path_and_failures_documented; no positive gate to major_step4",
        M_G=dict(mathematical_status="conditional_graph_guarantee_or_unconditional_boundedness_Markov_for_selected_targets",
            informative_status="mostly_wide_or_nearly_full_logical_ranges",no_data_proof_of_finite_dependence=True,
            no_uniform_winner_G3_over_G2=True,adjudication_csv=base+"/graph_adjudication.csv"),
        M_P=dict(small_split_multiplier=2,full_pilot_each_scenario_R=10,fitted_formal_validation_completed=False,
            in_domain_counterexample_C09_CONDITIONAL=failed,
            cost_projection_weighted_CPU_hours=weighted_hours,
            earlier_unweighted_projection_CPU_hours=runs["full-pilot"]["manifest"]["summary"]["projected_formal_58000_CPU_hours"],
            cost_projection_note="Audit weights each scenario by its protocol5000/1000 count; original manifest's equal-scenario estimate retained, not overwritten. One timing per scenario is a projection, not measured full-run cost or a cost confidence bound.",
            computational_admission=weighted_hours<=24,statistical_admission=False,
            failure_localization="outputs/logs/reliability/iteration-20261028/failure_localization.json"),
        known_generator_oracle=dict(rows=len(oracle),minimum_coverage=min(float(r["coverage_estimate"]) for r in oracle),
            maximum_coverage=max(float(r["coverage_estimate"]) for r in oracle),
            numeric_gate_failures=sum(r["coverage_numeric_gate"]!="True" for r in oracle),
            note="Finite-MC non-certification can coexist with known-parameter exchangeability guarantee. Never substitute for fitted model validation or change thresholds after observing results."),
        next_work=dict(approved_real_inference=False,required="Improve and identify dependence estimation jointly with mean or develop defensible nuisance uncertainty set; lock a feasible fresh protocol before further statistical acceptance.",
            graph="Defend independence/decay assumptions or accept broad ranges; no outcome-guided L selection."),
        manifests=[r["path"] for r in runs.values()],script_sha256=sha(Path(__file__)),human_review="not_performed")
    path=ROOT/base/"method_adjudication.json"
    if path.exists():raise RuntimeError("Preserve original adjudication; version any change")
    write_json(path,result)
    print(json.dumps(dict(status=result["status"],weighted_cost_CPU_hours=weighted_hours,oracle=result["known_generator_oracle"])))


if __name__=="__main__":main()
