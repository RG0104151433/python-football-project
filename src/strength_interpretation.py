"""Q5 stages 4/5: paired descriptive comparisons, curves and evidence ledger.

No new fitting, independent prediction assessment, standard errors or CI.
"""
from collections import Counter
from pathlib import Path
import io
import json
import math
import zipfile
import numpy as np
from src.data_contract import atomic_bytes, csv_bytes, file_hash, fingerprint, write_json
from src.strength.io import ROOT, read_rows, environment
from src.strength_joint.contract import load as load_joint
from src.strength_joint.design import Design, Support, group_matches
from src.strength_joint.model import Kernel, slopes


def losses(y, p):
    if not np.isfinite(p).all() or np.any((p <= 0) | (p >= 1)):
        raise ValueError("Invalid published probability; do not silently clip")
    return -(y * np.log(p) + (1 - y) * np.log1p(-p))


def paired_metrics(y, pa, pb):
    la, lb = losses(y, pa), losses(y, pb)
    return dict(matches=len(y), before_loss=float(la.mean()), after_loss=float(lb.mean()),
                loss_reduction=float((la - lb).mean()),
                before_brier=float(np.mean((pa-y)**2)), after_brier=float(np.mean((pb-y)**2)),
                accuracy_change_pp=float(100*np.mean(((pb >= .5) == y).astype(float) - ((pa >= .5) == y).astype(float))),
                mean_absolute_probability_change_pp=float(100*np.mean(abs(pa-pb))),
                role="paired_retrospective_description_not_independent_prediction_or_test")


def layers(rows, predictions, pairs):
    if [r["match_id"] for r in rows] != [r["match_id"] for r in predictions]:
        raise ValueError("INPUT_VERSION_MISMATCH: row order")
    y = np.array([int(r["home_win"]) for r in rows])
    probabilities = {m: np.array([float(r[m]) for r in predictions]) for pair in pairs for m in pair[:2]}
    full, grouped = [], []
    for a, b, label in pairs:
        full.append(dict(comparison_id=label, before_model=a, after_model=b, **paired_metrics(y, probabilities[a], probabilities[b])))
        for field in ("year", "era", "tournament_group", "home_region", "away_region"):
            for value in sorted({r[field] for r in rows}):
                mask = np.array([r[field] == value for r in rows])
                grouped.append(dict(comparison_id=label, before_model=a, after_model=b, grouping=field, group=value or "unknown",
                    **paired_metrics(y[mask], probabilities[a][mask], probabilities[b][mask])))
    return full, grouped


def curves(rows, design, models, cfg, joint_cfg):
    output = []; contrasts = []
    grid = np.arange(cfg["curve_mean_min"], cfg["curve_mean_max"] + cfg["curve_mean_step"]/2, cfg["curve_mean_step"])
    support = Support(rows, joint_cfg["support_bins"], joint_cfg["sparse_cell_warning"])
    diagnostic = {}
    for kind in ("friendly", "non_friendly"):
        changed_type = [dict(r, tournament_group=kind) for r in rows]
        observed = [float(r["strength_difference"]) for r in rows if r["tournament_group"] == kind]
        for d in grid:
            scenario = [dict(r, strength_difference=float(d)) for r in changed_type]
            zero, sparse, outside = support.flags(scenario)
            diagnostic[kind, float(d)] = dict(observed_nearby_matches=int(sum(abs(v-d) <= .25 for v in observed)),
                zero_cell_fraction=float(zero.mean()), sparse_cell_fraction=float(sparse.mean()), outside_background_score_range_fraction=float(outside.mean()))
        for model in cfg["curve_models"]:
            result = models[model]; x, names = design.matrix(changed_type, model)
            if names != result["names"]:
                raise ValueError("Design mismatch in curve")
            theta = np.array(result["theta"]); s = slopes(changed_type, model)
            b = np.exp(s @ theta[x.shape[1]:])
            kernel = Kernel(rows, mode=result["mode"])
            eta = x @ theta[:x.shape[1]]
            for d in grid:
                kernel.mu = np.full(len(rows), d)
                p = kernel.evaluate(eta, b)
                output.append(dict(model_id=model, tournament_group=kind, strength_mean=float(d),
                    standardized_home_probability=float(p.mean()), reference_rows=len(rows),
                    reference_id="curve-reference-"+fingerprint(dict(input=cfg["analysis"], rule=cfg["curve_reference"]))[:20],
                    **diagnostic[kind, float(d)], lower=None, upper=None, inference_status="INFERENCE_NOT_ADMITTED",
                    interpretation="model_scenario_fixed_original_variances_and_background; monotonicity_is_imposed_not_discovered"))
    index = {(r["model_id"], r["tournament_group"], r["strength_mean"]): r for r in output}
    for model in cfg["curve_models"]:
        for d in grid:
            a, b = [index[model, t, float(d)] for t in ("friendly", "non_friendly")]
            contrasts.append(dict(model_id=model, strength_mean=float(d), reference_id=a["reference_id"],
                friendly_probability=a["standardized_home_probability"], other_probability=b["standardized_home_probability"],
                friendly_minus_other_pp=100*(a["standardized_home_probability"]-b["standardized_home_probability"]),
                lower_pp=None, upper_pp=None, inference_status="INFERENCE_NOT_ADMITTED"))
    return output, contrasts


def target_ledger(contrasts, sensitivity, cfg):
    output = []
    tids = sorted({r["target_id"] for r in contrasts})
    lookup = {(r["target_id"],r["reference_kind"],r["model_id"]):r for r in contrasts}
    for tid in tids:
        full = lookup[tid,"full","M3_nested"]
        overlap = lookup[tid,"cell_range_overlap","M3_nested"]
        for reference in ("full", "cell_range_overlap"):
            rows = [lookup[tid,reference,m] for m in cfg["target_model_comparison"]]
            values = [float(r["difference_pp"]) for r in rows if r["difference_pp"]]
            signs = sorted({int(np.sign(v)) for v in values})
            output.append(dict(target_id=tid, label=full["label"], reference_kind=reference,
                reference_id=rows[0]["reference_id"], reference_rows=int(rows[0]["reference_rows"]),
                original_target_status=full["old_target_status"],
                retained_reference_fraction=int(overlap["reference_rows"])/int(full["reference_rows"]),
                M3_difference_pp=rows[0]["difference_pp"], M4_difference_pp=rows[1]["difference_pp"], M5_difference_pp=rows[2]["difference_pp"],
                specified_model_min_pp=min(values) if values else None, specified_model_max_pp=max(values) if values else None,
                specified_model_span_pp=max(values)-min(values) if values else None,
                same_direction_in_these_models=len(signs)==1 if values else False,
                initialization_mean_only_max_change_pp=max((abs(float(r["difference_change_pp"])) for r in sensitivity if r["target_id"]==tid and r["variant"].startswith("repaired-initialization") and r["difference_change_pp"]), default=0.),
                weak_jump_change_pp=next((r["difference_change_pp"] for r in sensitivity if r["target_id"]==tid and r["variant"]=="weak_jump_full_distribution"), None),
                sensitivity_reference_scope="sensitivity columns refer to FULL reference only, not overlap result",
                full_reference_extrapolation=True, model_range_is_confidence_interval=False,
                significance="NOT_TESTED", inference_status="INFERENCE_NOT_ADMITTED"))
    return output


def arm_composition(rows, facts, geography):
    output = []
    for comparison in geography["comparisons"]:
        # Existing 29 primary Q3 differences, not 155 independent interaction fits.
        if comparison["id"].startswith("A_"):
            continue
        for arm in ("arm1", "arm2"):
            group_id = comparison[arm]; group = geography["groups"][group_id]
            selected = [r for r in rows if group_matches(r, group) and
                        (not group.get("eligibility") or facts[r["match_id"]][group["eligibility"]+"_usable"]=="true")]
            if not selected:
                continue
            d = np.array([float(r["strength_difference"]) for r in selected])
            output.append(dict(comparison_id=comparison["id"], arm=arm, group_id=group_id, label=group["label"], matches=len(selected),
                home_wins=sum(int(r["home_win"]) for r in selected), observed_home_rate=float(np.mean([int(r["home_win"]) for r in selected])),
                score_gap_mean=float(d.mean()), score_gap_median=float(np.median(d)), score_gap_q10=float(np.quantile(d,.1)), score_gap_q90=float(np.quantile(d,.9)),
                positive_gap_fraction=float(np.mean(d>0)), mean_score_variance=float(np.mean([float(r["strength_difference_variance"]) for r in selected])),
                cold_start_matches=sum(r["cold_start"]=="true" for r in selected),
                meaning="observed_composition_of_rated_relative_strength_not_true_strength_or_causal_mechanism"))
    return output


def bridge(contrasts):
    lookup={(r["target_id"],r["reference_kind"],r["model_id"]):r for r in contrasts}
    return [dict(target_id=tid, original_status=lookup[tid,"full","M3_nested"]["old_target_status"],
        original_estimate_pp=None if not lookup[tid,"full","M3_nested"]["old_estimate_probability"] else 100*float(lookup[tid,"full","M3_nested"]["old_estimate_probability"]),
        new_without_strength_pp=lookup[tid,"full","M0_nested"]["difference_pp"], new_with_strength_pp=lookup[tid,"full","M3_nested"]["difference_pp"],
        new_overlap_with_strength_pp=lookup[tid,"cell_range_overlap","M3_nested"]["difference_pp"],
        difference_from_original=None, same_estimand_as_original=False,
        explanation="original adjusted fewer composition factors; new model/reference differs; never call subtraction percentage causally explained")
        for tid in sorted({r["target_id"] for r in contrasts})]


def source_files():
    files=[ROOT/"src/strength_interpretation.py", ROOT/"src/data_contract.py", ROOT/"src/strength/io.py",
           ROOT/"scripts/analyze_strength_interpretation.py",ROOT/"scripts/audit_strength_interpretation.py",
           ROOT/"tests/test_strength_interpretation.py",ROOT/"config/strength_interpretation.json", *ROOT.glob("src/strength_joint/*.py")]
    return {p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(files)}


def figures(full, curves_data, curve_contrasts, ledger):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    available={f.name for f in font_manager.fontManager.ttflist}
    font=next((f for f in ("Microsoft YaHei","SimHei","Noto Sans CJK SC") if f in available),"DejaVu Sans")
    plt.rcParams.update({"font.family":font,"axes.unicode_minus":False,"svg.hashsalt":"strength-interpretation-v1"})
    out={}
    def save(fig,name):
        for ext in ("png","svg"):
            b=io.BytesIO();fig.savefig(b,format=ext,dpi=160,bbox_inches="tight",metadata={"Date":None} if ext=="svg" else {})
            out[name+"."+ext]=b.getvalue()
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5),layout="constrained")
    chosen=full[:6]
    labels=["同大区背景加入实力","同分区背景加入实力","实力后加入年代/赛事/大区","再加入洲内分区","允许两赛事实力联系不同","再加入有限对手关系"]
    ax.barh(range(6),[r["loss_reduction"] for r in chosen],color="#59788e")
    ax.set(yticks=range(6),yticklabels=labels,xlabel="平均主胜二元对数损失的减少（越大表示样本内拟合改善越多）",title="哪些信息带来的样本内变化较大？")
    ax.invert_yaxis()
    for i,r in enumerate(chosen):ax.text(r["loss_reduction"]+.001,i,f'{r["loss_reduction"]:.5f}',va="center",fontsize=9)
    ax.margins(x=.15);fig.text(.5,-.015,"同24917场。增加顺序影响增量，不是各因素的独立贡献率；不是未来预测成绩。",ha="center",fontsize=9)
    save(fig,"layer_comparison")
    fig,axs=plt.subplots(1,2,figsize=(11,4.5),layout="constrained",sharey=True)
    for ax,model,title in zip(axs,["M3_nested","M4_type_slope"],["主模型：共用实力联系","有限扩展：两赛事联系分别估计"]):
        for kind,label,color in [("non_friendly","其他赛事","#59788e"),("friendly","友谊赛","#b57b40")]:
            rr=[r for r in curves_data if r["model_id"]==model and r["tournament_group"]==kind]
            ax.plot([r["strength_mean"] for r in rr],[100*r["standardized_home_probability"] for r in rr],label=label,color=color)
        ax.set(title=title,xlabel="赛前实力差均值（主队减客队，评分单位）",ylim=(0,100));ax.axvline(0,color=".7",linewidth=.8);ax.legend()
    axs[0].set_ylabel("共同参考的模型主胜概率（%）")
    fig.text(.5,-.02,"保留原方差、跳变及背景的模型情景；单调性为预设，含外推，无置信带；均值差为0不表示无主场作用。",ha="center",fontsize=8.5)
    save(fig,"strength_probability_curves")
    fig,ax=plt.subplots(figsize=(9,4.5),layout="constrained")
    for model,label,color in [("M3_nested","主模型：共用联系","#59788e"),("M4_type_slope","两类赛事分别估计联系","#b57b40")]:
        rr=[r for r in curve_contrasts if r["model_id"]==model]
        ax.plot([r["strength_mean"] for r in rr],[r["friendly_minus_other_pp"] for r in rr],label=label,color=color)
    ax.axhline(0,color=".6",linewidth=.8);ax.axvline(0,color=".8",linewidth=.8)
    ax.set(xlabel="赛前实力差均值（主队减客队）",ylabel="友谊赛减其他赛事的模型概率差（百分点）",title="赛事差是否随双方强弱改变？")
    ax.legend();fig.text(.5,-.02,"同一模型参考情景，非实际分档胜率、非显著性检验；不能把曲线斜率当作友谊赛学习权重。",ha="center",fontsize=8.5)
    save(fig,"tournament_difference_curve")
    return out,font


def run(config_path="config/strength_interpretation.json"):
    cfg=json.loads((ROOT/config_path).read_text(encoding="utf-8"));folder=ROOT/cfg["analysis"]
    if file_hash(folder/"manifest.json")!=cfg["analysis_manifest_sha256"]:raise ValueError("INPUT_VERSION_MISMATCH")
    original=json.loads((folder/"manifest.json").read_text())
    for name,h in original["outputs"].items():
        if file_hash(folder/name)!=h:raise ValueError("INPUT_VERSION_MISMATCH: "+name)
    joint_cfg,rows,targets,geography,inputs=load_joint()
    for path,h in original["identity"]["code"].items():
        if file_hash(ROOT/path)!=h:raise ValueError("Executed joint source changed: "+path)
    predictions=read_rows(folder/"joint_predictions.csv");models=json.loads((folder/"models.json").read_text())
    contrasts=read_rows(folder/"contrasts.csv");sens=read_rows(folder/"sensitivity.csv")
    facts={r["match_id"]:r for r in read_rows(ROOT/joint_cfg["facts"])}
    print("INTERPRET_LAYERS",flush=True)
    full,grouped=layers(rows,predictions,cfg["layer_pairs"])
    print("INTERPRET_CURVES",flush=True)
    curve_data,curve_diff=curves(rows,Design(rows),models,cfg,joint_cfg)
    ledger=target_ledger(contrasts,sens,cfg);arms=arm_composition(rows,facts,geography)
    old_groups=read_rows((ROOT/joint_cfg["facts"]).parent/"group_summary.csv")
    counts={r["group_id"]:int(r["n_matches"]) for r in old_groups}
    for r in arms:
        if r["group_id"] in counts and r["matches"]!=counts[r["group_id"]]:raise ValueError("Original comparison arm population changed: "+r["group_id"])
    sl=[]
    for model in ("M1_strength","M2_common","M3_nested","M4_type_slope","M5_relation"):
        result=models[model]
        for name,value in zip(result["slope_names"],result["theta"][-len(result["slope_names"]):]):
            sl.append(dict(model_id=model,parameter=name,positive_slope=math.exp(value),meaning="latent_scale_not_percentage_or_learning_weight",formal_test="NOT_PERFORMED"))
    csvs={"layer_comparisons.csv":full,"layer_group_diagnostics.csv":grouped,"strength_curves.csv":curve_data,
          "tournament_curve_differences.csv":curve_diff,"target_evidence_ledger.csv":ledger,"observed_score_composition.csv":arms,
          "original_new_estimand_bridge.csv":bridge(contrasts),"strength_slopes.csv":sl}
    images,font=figures(full,curve_data,curve_diff,ledger)
    display=dict(study_rows=len(rows),layer_comparisons=full,strength_slopes=sl,target_evidence=ledger,
                 curves=curve_data,tournament_differences=curve_diff,stage4_computation_complete=True,stage5_descriptive_materials_complete=True,
                 stage6_statistical_acceptance_complete=False,inference_status="INFERENCE_NOT_ADMITTED",actual_human_review=False)
    identity=dict(protocol=cfg,inputs={**inputs,config_path:file_hash(ROOT/config_path),cfg["analysis"]+"/manifest.json":file_hash(folder/"manifest.json")},
                  code=source_files(),environment=environment(),font=font)
    ident="strength-interpretation-"+fingerprint(identity)[:20];dest=ROOT/"outputs/tables/strength_joint"/ident
    content={name:csv_bytes(list(rr[0]),rr) for name,rr in csvs.items()}
    content.update(images)
    texts={"display_data.json":display,"scope.json":dict(stages_completed=[4,5],stage6_complete=False,statistical_inference=False,new_model_fits=False,
        original_study_rows=24917,original_core_targets=32,source_manifest=cfg["analysis_manifest_sha256"],
        note="conditional retrospective interpretation; ranges of models are not CI; prior missing support retained")}
    for name,obj in texts.items():content[name]=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')
    content['data_dictionary.md']=('''# 第五问第四、五环节补充结果\n\n八模型对比使用同24917场、逐场配对的主胜二元损失。按年/年代/赛事/主客大区重建，不把检查数当独立样本数。所有比较是回顾性描述；新增因素的增量受顺序影响，不解释因果贡献。\nstrength_curves按共同原参考、设置实力均值与赛事、保留原方差/Poisson/年代/地理。正斜率单调为模型假设；observed_nearby_matches只是同赛事均值附近.25评分单位场数，不是充分共同支持。支持字段另给零单元/稀疏/范围外比例。\ntarget_evidence_ledger记录32目标×两参考，在M3/M4/M5的最小/最大/跨度，是已列模型的取值范围，不是区间或显著性。初始化均值/弱跳变敏感列仅指原FULL参考，不能冒充辅助参考敏感性。\nobserved_score_composition按原分组和资格追踪真实对比臂；评分均值差不等于真实实力，不能断言哪一方真正变强。original_new_estimand_bridge保留旧缺层/估计与新结果，跨估计对象差值为空。\nCSV为UTF-8 BOM、LF、固定十位小数；未计算区间为空INFERENCE_NOT_ADMITTED。原评分、拟合和结果不覆盖。\n''').encode('utf-8')
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
        for name in sorted(identity['code']):z.writestr(zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)),(ROOT/name).read_bytes())
    content['source_snapshot.zip']=archive.getvalue()
    for name,value in content.items():
        if (dest/name).exists() and (dest/name).read_bytes()!=value:raise ValueError("Immutable output collision: "+name)
    for name,value in content.items():atomic_bytes(dest/name,value)
    write_json(dest/'manifest.json',dict(stage_id=ident,identity=identity,outputs={name:file_hash(dest/name) for name in content}))
    write_json(ROOT/'outputs/logs/strength_interpretation/current.json',dict(directory=dest.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(dest/'manifest.json')))
    print('INTERPRETATION_COMPLETE',dest.relative_to(ROOT).as_posix(),flush=True)
    return dest
