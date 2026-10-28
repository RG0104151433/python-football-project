"""Small counterexamples for changed references and geographic rule composition."""
import numpy as np
from src.reliability.sensitivity import Engine,Selectors,relabel


def tiny():
    facts=[];eras=["1980s","1990s","2000s","2010s","2020s"]
    for j,e in enumerate(eras):
        for k in range(3):
            facts.append(dict(match_id=f"m{j}-{k}",year=str(1980+10*j),date=f"{1980+10*j}-01-01",era=e,
                tournament_group="friendly" if k==0 else "non_friendly",home_win=str(int((j==4 and k==0) or (j==0 and k>0))),
                home_region="002",away_region="002",home_unit="015",away_unit="011",relation="same_region_diff_unit",
                A_usable="true",B_usable="true",C_usable="true"))
    a=[]
    for e,sign in (("2020s",1),("1980s",-1)):
        for g,n in (("friendly",1),("non_friendly",2)):
            a.append(dict(target_id="Q1:test:adjusted",era=e,tournament_group=g,q_numerator=n,q_denominator=3,multiplier=sign))
    for e in eras:
        for g,n in (("friendly",1),("non_friendly",2)):
            a.append(dict(target_id="Q3:dummy",region_group="REF",region_target="C_AFR",era=e,tournament_group=g,
                q_numerator=n,q_denominator=15,multiplier=1))
    cat=[dict(target_id="Q1:test:adjusted",question="Q1",family="CORE",kind="difference",label="test",estimate_probability=-1/3),
         dict(target_id="Q3:dummy",question="Q3",family="CONDITIONAL",kind="rate",label="dummy",estimate_probability=.2)]
    cfg=dict(groups={"REF":dict(eligibility="C",home_regions=["002"])},analysis_targets={"C_AFR":dict(reference_group="REF")})
    return Engine(dict(facts=facts,components=a,catalogue=cat),cfg)


def scenario(policy):
    return dict(scenario_id="test",selection_id="test",reference_policy=policy,check_type="test",subsample_id="test",classification_id="test")


def test_positive_missing_layer_and_zero_weight_layer_differ():
    e=tiny();keep=np.asarray([r["tournament_group"]=="friendly" for r in e.facts])
    e.start(scenario("fixed"),keep);a=e.evaluate("Q1:test:adjusted")
    assert a["status"]=="unsupported" and a["estimate_probability"] is None
    e.start(scenario("recomputed"),keep);b=e.evaluate("Q1:test:adjusted")
    assert b["status"]=="ok" and b["estimate_probability"]==1
    assert b["lower_probability_scale"] is None and b["uncertainty_status"]=="not_calibrated_for_variant"


def test_baseline_fraction_direction_and_percentage_point_conversion():
    e=tiny();e.start(scenario("fixed"),np.ones(len(e.facts),bool));r=e.evaluate("Q1:test:adjusted")
    assert abs(r["estimate_probability"]+1/3)<1e-14
    assert abs(r["estimate_pp"]+100/3)<1e-12
    assert abs(r["change_from_baseline_pp"])<1e-12


def test_unrelated_year_with_fixed_reference_is_not_extra_stability_evidence():
    e=tiny();keep=np.asarray([r["year"]!="1990" for r in e.facts])
    e.start(scenario("fixed"),keep);r=e.evaluate("Q1:test:adjusted")
    assert not r["affects_target"] and not r["affects_reference"] and not r["applicable"]
    assert abs(r["estimate_probability"]+1/3)<1e-14
    e.start(scenario("recomputed"),keep);s=e.evaluate("Q1:test:adjusted")
    assert s["affects_reference"] and s["applicable"]


def test_relabel_removes_one_override_but_keeps_merges_in_both_roles():
    r=dict(match_id="x",date="2001-01-01",home_team_id="team:turkey",away_team_id="team:australia",
        base_home_region="142",base_home_unit="145",base_away_region="009",base_away_unit="053",
        home_region="150",home_unit="039",away_region="142",away_unit="035",
        home_rule_id="a",away_rule_id="b",base_direction="142>009",base_relation="cross_region",direction="150>142",relation="cross_region")
    cfg=dict(scope=dict(start="1980-01-01",end="2024-12-31"),overrides=[
        dict(team_id="team:turkey",base_region="142",base_unit="145",region="150",unit="039",rule_id="T"),
        dict(team_id="team:australia",base_region="009",base_unit="053",region="142",unit="035",rule_id="A")],
        merges=[dict(region="009",base_units=["053"],unit="OCEANIA_ALL",rule_id="O")])
    a=relabel([r],cfg,["team:australia"])[0]
    assert (a["home_region"],a["home_unit"])==("150","039")
    assert (a["away_region"],a["away_unit"])==("009","OCEANIA_ALL")
    assert a["B_usable"]=="true" and a["relation"]=="cross_region"
    b=relabel([r],cfg,["team:turkey"])[0]
    assert (b["home_region"],b["home_unit"])==("142","145")
    assert (r["home_region"],r["away_region"])==("150","142")


def test_explicit_string_false_is_not_truthy_eligibility():
    e=tiny();facts=[dict(e.facts[0],C_usable="false")]
    s=Selectors(facts,{"g":dict(eligibility="C",home_regions=["002"])})
    assert len(s.indices(dict(group="g"))[1])==0
