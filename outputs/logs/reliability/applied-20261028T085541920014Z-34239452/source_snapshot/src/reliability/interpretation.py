"""Separate descriptive direction, scoped interval support and perturbations."""
from collections import defaultdict


def sign(value, tol=1e-12):
    return 0 if abs(value)<=tol else 1 if value>0 else -1


def review_conclusions(intervals, sensitivity):
    grouped=defaultdict(list)
    for r in sensitivity:
        if r["applicable"]:grouped[r["target_id"]].append(r)
    result=[]
    for r in intervals:
        tid=r["target_id"];cases=grouped[tid]
        usable=[v for v in cases if v["estimate_probability"] is not None]
        changes=[v["change_from_baseline_pp"] for v in usable if v["change_from_baseline_pp"] is not None]
        point=r["point_probability_scale"]
        if point is None:
            direction="unavailable";support="unsupported"
            wording="原参考正权重层缺失，主结果不可估；不以变体结果填补。"
        elif r["kind"]=="rate":
            direction="rate_not_a_predefined_contrast";support="conditional_rate_envelope_only"
            wording="条件率与范围按当前参考解释；不自动对0.5检验主场优势或据此排名。"
        else:
            direction={-1:"negative",0:"zero",1:"positive"}[sign(point)]
            lo,hi=r["lower_probability_scale"],r["upper_probability_scale"]
            support="positive" if lo>0 else "negative" if hi<0 else "includes_zero"
            wording="在所列工作模型条件下，预定差值方向得到支持。" if support!="includes_zero" else "描述差异仍在，但当前工作模型范围跨零，尚不能确认方向；不表示没有差异。"
        flips=sum(sign(v["estimate_probability"])!=sign(point) for v in usable) if point is not None and r["kind"]=="difference" else None
        result.append(dict(target_id=tid,question=r["question"],family=r["family"],kind=r["kind"],label=r["label"],
            point_display=r["point_display"],lower_display=r["lower_display"],upper_display=r["upper_display"],
            display_unit=r["display_unit"],descriptive_direction=direction,model_conditional_support=support,
            applicable_variants=len(cases),computable_variants=len(usable),unsupported_variants=len(cases)-len(usable),
            min_change_pp=min(changes) if changes else None,max_change_pp=max(changes) if changes else None,
            max_absolute_change_pp=max(map(abs,changes)) if changes else None,descriptive_direction_changes=flips,
            suggested_wording=wording,causal_or_predictive_claim=False,scope=r["scope"]))
    return result


def sensitivity_summary(sensitivity, intervals):
    meta={r["target_id"]:r for r in intervals};groups=defaultdict(list)
    for r in sensitivity:
        groups[(r["check_type"],r["reference_policy"],r["target_id"])].append(r)
    out=[]
    for (kind,policy,tid),rows in sorted(groups.items()):
        applicable=[r for r in rows if r["applicable"]]
        good=[r for r in applicable if r["estimate_probability"] is not None]
        changes=[r["change_from_baseline_pp"] for r in good if r["change_from_baseline_pp"] is not None]
        baseline=rows[0]["baseline_probability"]
        isdiff=meta.get(tid,{}).get("kind")=="difference"
        out.append(dict(check_type=kind,reference_policy=policy,target_id=tid,
            total_scenarios=len(rows),applicable_scenarios=len(applicable),computable_scenarios=len(good),
            unsupported_scenarios=len(applicable)-len(good),
            min_estimate_pp=min(r["estimate_pp"] for r in good) if good else None,
            max_estimate_pp=max(r["estimate_pp"] for r in good) if good else None,
            max_absolute_change_pp=max(map(abs,changes)) if changes else None,
            direction_changes=sum(sign(r["estimate_probability"])!=sign(baseline) for r in good) if baseline is not None and isdiff else None,
            uncertainty_status="descriptive_range_not_confidence_interval"))
    return out
