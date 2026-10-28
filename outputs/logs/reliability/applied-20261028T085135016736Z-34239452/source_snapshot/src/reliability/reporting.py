"""Deterministic study artifacts with separately timestamped execution evidence."""
from pathlib import Path
import csv
import gzip
import json
import platform
import shutil
import numpy as np
import scipy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from .design import sha, require
from .experiment import json_text, write_json, write_csv


def environment():
    font=None
    for p in (Path("C:/Windows/Fonts/msyh.ttc"),Path("C:/Windows/Fonts/simhei.ttf")):
        if p.exists():font=p;break
    if font is None:
        for f in font_manager.fontManager.ttflist:
            if "Noto Sans CJK" in f.name:font=Path(f.fname);break
    require(font is not None,"No verified Chinese plotting font")
    return dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
        matplotlib=matplotlib.__version__,platform=platform.system(),font_path=font.as_posix(),font_sha256=sha(font))


def compressed_cells(path, records):
    # mtime=0 avoids timestamp-only differences between two runs.
    with Path(path).open("wb") as raw:
        with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as zipped:
            import io
            with io.TextIOWrapper(zipped,encoding="utf-8-sig",newline="") as stream:
                cols=["scenario_id","selector_id","n","wins"]
                w=csv.DictWriter(stream,cols,lineterminator="\n");w.writeheader();w.writerows(records)


def save_sensitivity(folder, data):
    for name,key,sort in (("sensitivity_results","results",lambda r:(r["scenario_id"],r["target_id"])),
        ("sensitivity_references","references",lambda r:(r["scenario_id"],r["reference_key"],r["stratum"])),
        ("sensitivity_membership_changes","membership",lambda r:(r["selection_id"],r["match_id"])),
        ("common_teams","common_teams",lambda r:r["team_id"])):
        write_csv(folder/(name+".csv"),sorted(data[key],key=sort))
    compressed_cells(folder/"sensitivity_cells.csv.gz",sorted(data["cells"],key=lambda r:(r["scenario_id"],r["selector_id"])))
    for name,key in (("sensitivity_scenarios","scenarios"),("selector_definitions","selectors"),
        ("target_templates","templates"),("sensitivity_groups","groups"),("selection_definitions","selection_definitions")):
        write_json(folder/(name+".json"),data[key])


def plot_results(folder, tables, aid, env):
    folder.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({"font.family":font_manager.FontProperties(fname=env["font_path"]).get_name(),
        "axes.unicode_minus":False,"svg.hashsalt":aid,"font.size":11})
    intervals=tables["interval_results"];all_data={r["target_id"]:r for r in intervals}
    assets=[]
    def save(fig,name,source_ids):
        fig.text(.02,.01,"固定赛程与参考的工作模型条件范围；四家族分别解释。非因果、非未来预测。",fontsize=9)
        fig.tight_layout(rect=(0,.04,1,1))
        for ext in ("png","svg"):
            path=folder/(name+"."+ext)
            fig.savefig(path,dpi=160,metadata={"Date":None} if ext=="svg" else {"Software":"football-reliability"})
        plt.close(fig);assets.append(dict(name=name,target_ids=source_ids,source="interval_results.csv"))
    def forest(rows,name,title):
        fig,ax=plt.subplots(figsize=(12,max(4,.27*len(rows)+1.4)))
        for j,r in enumerate(rows):
            if r["point_display"] is None:continue
            ax.plot([r["lower_display"],r["upper_display"]],[j,j],color="#247a87",lw=2)
            ax.plot(r["point_display"],j,"o",color="#163b50")
        friendly_labels={"Q1:2010s_minus_1980s:adjusted":"2010—2019减1980—1989（共同赛事构成）",
            "Q1:2020_2024_minus_1980s:adjusted":"2020—2024减1980—1989（共同赛事构成）",
            "Q2:difference:overall:all:era_standardized":"全期友谊赛减其他赛事（共同年代构成）",
            "Q2:difference:era:2020_2024:raw":"2020—2024友谊赛减其他赛事（直接差）"}
        labels=[friendly_labels.get(r["target_id"],r["label"].replace(" adjusted","（调整后）"))+
            ("【原目标缺层，不可估】" if r["point_display"] is None else "") for r in rows]
        ax.set_yticks(range(len(rows)),labels);ax.invert_yaxis()
        ax.axvline(0,color="gray",lw=.8);ax.set_xlabel("前组减后组（百分点）");ax.set_title(title)
        save(fig,name,[r["target_id"] for r in rows])
    forest([r for r in intervals if r["question"]=="Q1" and r["family"]=="CORE"],"q1_intervals","第一问：预定年代差及模型条件范围（CORE家族）")
    forest([all_data[k] for k in ("Q2:difference:overall:all:era_standardized","Q2:difference:era:2020_2024:raw")],
        "q2_overall_recent","第二问：全期调整差与末五年直接差（分别属CORE/AUX）")
    roll=[r for r in intervals if r["family"]=="ROLLING"]
    roll.sort(key=lambda r:r["target_id"])
    fig,ax=plt.subplots(figsize=(12,5));x=np.arange(len(roll))
    ax.fill_between(x,[r["lower_display"] for r in roll],[r["upper_display"] for r in roll],alpha=.22,color="#247a87",label="36窗共同范围")
    ax.plot(x,[r["point_display"] for r in roll],color="#163b50",label="共同年份参考后的差值")
    labels=[r["target_id"].split(":")[-2].replace("_","—") for r in roll]
    ax.set_xticks(x[::5],[labels[i] for i in x[::5]],rotation=25);ax.axhline(0,color="gray",lw=.8)
    ax.set_ylabel("友谊赛减其他赛事（百分点）");ax.set_title("第二问：36个重叠十年窗口；窗口不是独立样本");ax.legend()
    save(fig,"q2_rolling_joint",[r["target_id"] for r in roll])
    forest([r for r in intervals if r["question"]=="Q3" and r["family"]=="CORE"],"q3_predefined_contrasts","第三问：29项预定地域差值，24项可算（CORE目录）")
    rate=[r for r in intervals if r["family"]=="CONDITIONAL" and r["point_display"] is not None]
    fig,ax=plt.subplots(figsize=(12,6));ax.scatter([r["point_display"] for r in rate],
        [r["upper_display"]-r["lower_display"] for r in rate],color="#247a87",alpha=.7)
    ax.set_xlabel("调整后条件主胜率（%）");ax.set_ylabel("模型条件范围宽度（百分点）")
    ax.set_title("第三问：71个条件率的精度；点的位置不能当作实力排名")
    save(fig,"q3_conditional_precision",[r["target_id"] for r in rate])
    rev=[r for r in tables["conclusion_review"] if r["family"]=="CORE"]
    fig,ax=plt.subplots(figsize=(12,8));yy=np.arange(len(rev))
    for j,r in enumerate(rev):
        if r["min_change_pp"] is not None:ax.plot([r["min_change_pp"],r["max_change_pp"]],[j,j],lw=2,color="#a66b3c")
    ax.set_yticks(yy,[r["label"].replace(" adjusted","（调整后）")+("【原目标缺层】" if r["point_display"] is None else "") for r in rev]);ax.invert_yaxis();ax.axvline(0,color="gray",lw=.8)
    ax.set_xlabel("相对原值的位移（百分点）；是描述变体范围，不是置信区间")
    ax.set_title("CORE目标在已列可算对照中的变化范围")
    save(fig,"core_sensitivity_shifts",[r["target_id"] for r in rev])
    assets[-1]["source"]="conclusion_review.csv"
    write_json(folder/"figure_sources.json",dict(analysis_id=aid,environment=env,figures=assets))


def publish(root, work, destination):
    destination=Path(destination)
    require(destination.resolve().is_relative_to(Path(root).resolve()/"outputs"),"Publication outside outputs")
    if destination.exists():
        actual={p.relative_to(work).as_posix():sha(p) for p in work.rglob("*") if p.is_file()}
        existing={p.relative_to(destination).as_posix():sha(p) for p in destination.rglob("*") if p.is_file()}
        require(actual==existing,"Existing analysis identity has different bytes:"+str(destination))
        return "verified_identical_existing_artifacts"
    shutil.copytree(work,destination)
    return "new_content_identity_published"


def data_dictionary(folder):
    definitions={
        "point_probability_scale":"Original weighted win rate or signed difference, probability scale; draws remain in denominator",
        "lower_probability_scale":"Model-conditional calibrated lower endpoint; blank for unsupported or uncalibrated variants",
        "upper_probability_scale":"Model-conditional calibrated upper endpoint; not a universal real-world guarantee",
        "point_display":"100 times probability scale; percent for rates, percentage points for differences",
        "applicable":"Metadata change affects target/reference or explicitly alternative definition; not extra independent evidence",
        "change_from_baseline_pp":"100*(variant point-original point); blank for a new or originally unavailable target",
        "n_target_union":"Union of observed contributing positive-reference cells; not effective independent sample size",
        "weight_numerator":"Exact reference fraction numerator, stored as integer text",
        "weight_denominator":"Exact positive reference fraction denominator",
        "calibrated_score_scale":"Calibration score normalization, not a standard error",
        "uncertainty_status":"Changed targets remain not_calibrated_for_variant; descriptive spread is not a confidence interval"}
    fields={}
    for path in sorted(folder.glob("*.csv")):
        with path.open(encoding="utf-8-sig",newline="") as stream:fields[path.name]=next(csv.reader(stream))
    write_json(folder/"data_dictionary.json",dict(schema="reliability-applied-v1",fields=fields,
        definitions=definitions,all_other_fields="Identifiers/status/provenance or integer counts as named; definitions and scope in method_scope.json",
        units="Internal probabilities; all *_pp/display differences in percentage points. Four families separately, not global198."))
