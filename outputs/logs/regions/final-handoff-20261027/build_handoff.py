"""Build final Q3 conclusion cards and readable presentation figures from pinned results."""
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from src.regions.export import verify_run
from src.regions.io import json_bytes, project_path, read_json, read_rows, require, sha
from src.regions.rendering import pin_figure_font, rendering_environment


def main():
    out = Path(__file__).resolve().parent
    require(not (out / "review.json").exists(), "REG_OUTPUT_COLLISION", "Final handoff already exists; do not overwrite")
    state = read_json(ROOT / "研究/pipeline_state.json")
    q3 = state["question_3"]
    manifest = read_json(ROOT / q3["run_manifest"])
    integrity = verify_run(ROOT, q3["run_manifest"])
    aid = manifest["analysis_id"]
    folder = ROOT / "outputs/tables/regions" / aid
    names = ("group_summary", "stratum_counts", "reference_weights", "contrast_results", "matchup_rates", "analysis_matches")
    tables = {name: read_rows(folder / (name + ".csv")) for name in names}
    groups = {(r["target_id"], r["group_id"]): r for r in tables["group_summary"]}
    contrasts = {r["contrast_id"]: r for r in tables["contrast_results"]}
    strata = {(r["target_id"], r["group_id"], r["era"], r["tournament_group"]): r for r in tables["stratum_counts"]}
    references = {}
    for row in tables["reference_weights"]:
        references.setdefault(row["target_id"], []).append(row)
    checks = 0

    def check(ok, message):
        nonlocal checks
        require(ok, "REG_FINAL_HANDOFF", message)
        checks += 1

    def equal(value, stored, message):
        check(stored == "" if value is None else stored != "" and abs(float(value) - float(stored)) < 1e-12, message)

    exact = {}
    for (tid, gid), row in groups.items():
        selected = [r for (t, g, e, k), r in strata.items() if (t, g) == (tid, gid)]
        for column in ("n_matches", "n_home_wins", "n_draws", "n_away_wins"):
            check(sum(int(r[column]) for r in selected) == int(row[column]), "Layer total:" + tid + gid + column)
        n, wins = int(row["n_matches"]), int(row["n_home_wins"])
        direct = Fraction(wins, n) if n else None
        value = Fraction(0)
        supported = True
        check(len(selected) == 10, "Complete ten-layer grid")
        for ref in references[tid]:
            q = Fraction(int(ref["n_reference_matches"]), int(ref["n_reference_total"]))
            r = strata[tid, gid, ref["era"], ref["tournament_group"]]
            nn = int(r["n_matches"])
            check(nn == int(r["n_home_wins"]) + int(r["n_draws"]) + int(r["n_away_wins"]), "Layer WDL")
            if q and not nn:
                supported = False
            elif q:
                value += q * Fraction(int(r["n_home_wins"]), nn)
        adjusted = value if supported else None
        equal(direct, row["home_win_rate"], "Raw rate")
        equal(adjusted, row["standardized_home_win_rate"], "Adjusted rate")
        exact[tid, gid] = direct, adjusted
    for c in contrasts.values():
        left, right = exact[c["target_id"], c["arm1"]], exact[c["target_id"], c["arm2"]]
        direct = left[0] - right[0] if left[0] is not None and right[0] is not None else None
        adjusted = left[1] - right[1] if left[1] is not None and right[1] is not None and c["contrast_id"] != "B_SA" else None
        equal(direct, c["direct_difference"], "Direct contrast")
        equal(adjusted, c["adjusted_difference"], "Adjusted contrast")
        equal(None if adjusted is None else adjusted * 100, c["adjusted_difference_pp"], "Percentage points")
    expected = set()
    regions = ["002", "019", "142", "150", "009"]
    partitions = {"150": ["151", "039", "155", "154"], "142": ["030", "035", "034", "143", "145"],
                  "002": ["015", "011", "SSA_OTHER"], "019": ["005", "013", "021", "029"]}
    for h in regions:
        for a in regions:
            expected.add((h, "", a, ""))
    for region, units in partitions.items():
        for h in units:
            expected.update((region, h, region, a) for a in units)
            expected.update((region, h, a, "") for a in regions if a != region)
    actual = [(r["home_region"], r["home_unit"], r["away_region"], r["away_unit"]) for r in tables["matchup_rates"]]
    check(set(actual) == expected and len(actual) == len(expected) == 155, "Every planned directed cell exactly once")
    check(len(contrasts) == 29 and sum(c["adjusted_status"] == "ok" for c in contrasts.values()) == 24, "All 29 contrasts, 24 estimable")
    parent = {r["match_id"] for r in tables["analysis_matches"]}
    check(len(parent) == len(tables["analysis_matches"]) == 24917, "Unique parent matches")
    protected = {}
    sources = {q3["run_manifest"]: sha(ROOT / q3["run_manifest"])}
    for question, flag in (("question_1", "in_classified_venue"), ("question_2", "included")):
        old_path = state[question]["run_manifest"]
        old = read_json(ROOT / old_path)
        for p, expected_hash in old["outputs"].items():
            check(sha(project_path(ROOT, p)) == expected_hash, "Preserved preceding result:" + p)
        membership_path = next(p for p in old["outputs"] if p.endswith("/analysis_membership.csv"))
        members = {r["match_id"] for r in read_rows(ROOT / membership_path) if r[flag] == "true"}
        check(members == parent, "Same 24917 IDs:" + question)
        protected[question] = dict(analysis_id=old["analysis_id"], outputs_verified=len(old["outputs"]), same_match_ids=24917)
        sources[old_path], sources[membership_path] = sha(ROOT / old_path), sha(ROOT / membership_path)
    support_path = q3["support_audit"]["report"]
    support = read_json(ROOT / support_path)
    check(support["analysis_id"] == aid, "Support audit same version")
    source_files = [folder / (n + ".csv") for n in names] + [ROOT / support_path, ROOT / q3["support_audit"]["inventory"],
                    ROOT / q3["display_data"], folder / "analysis_metadata.json", folder / "data_dictionary.md",
                    ROOT / "outputs/logs/regions/closeout-20261027/tests.xml",
                    ROOT / "outputs/logs/regions/closeout-20261027/independent_audit_repeat.json"]
    sources.update({p.relative_to(ROOT).as_posix(): sha(p) for p in source_files})

    def atom(tid, gid, metric="standardized_home_win_rate"):
        row = groups[tid, gid]
        return dict(table="group_summary.csv", target_id=tid, group_id=gid, field=metric,
                    value=float(row[metric]) if row[metric] else None, unit="probability",
                    n_matches=int(row["n_matches"]), reference_group=row["reference_group"])

    def difference(cid):
        row = contrasts[cid]
        return dict(table="contrast_results.csv", contrast_id=cid, field="adjusted_difference_pp",
                    value=float(row["adjusted_difference_pp"]) if row["adjusted_difference_pp"] else None,
                    unit="percentage_points", arm1=row["arm1"], arm2=row["arm2"],
                    n_arm1=int(row["n_arm1"]), n_arm2=int(row["n_arm2"]), reference_group=row["reference_group"])

    cards = [
        dict(id="Q3-F01", title="同一大洲内部不能只看一个平均数", status="supported_description",
             statement="统一年代和赛事构成后，北非、西非、其余撒哈拉以南非洲的主胜率仍不同；洲内分区值得保留。",
             evidence=[atom("C_AFR", g) for g in ("C_AFR_015", "C_AFR_011", "C_AFR_SSA_OTHER")] + [difference("C_AFR_015_VS_OTHER")],
             allowed="本样本调整率约65.73%、55.97%、46.42%；北非减其余为19.31个百分点。",
             forbidden="北非拥有最强的纯主场优势；地域造成了19.31个百分点。", figure="finding_01_africa"),
        dict(id="Q3-F02", title="南美更高，要先说明在和谁比较", status="supported_description",
             statement="南美相对其他美洲合并组的差，不能代表它相对每个分区都高出相同幅度。",
             evidence=[atom("C_AMER", g) for g in ("C_AMER_005", "C_AMER_013", "C_AMER_021", "C_AMER_029")] +
                      [difference("C_AMER_FOCUS"), difference("C_AMER_005_VS_013")],
             allowed="南美减其他合并组约7.08个百分点，南美减中美洲约0.56；两种比较对象不同。",
             forbidden="南美比美洲其他每个分区都高7.08个百分点；合并比较已经揭示原因。", figure="finding_02_americas"),
        dict(id="Q3-F03", title="面对洲外对手，欧亚主队呈现相反方向", status="supported_description",
             statement="在各自主队背景内，洲外减同分区的调整主胜率差，欧洲为正、亚洲为负。",
             evidence=[difference("B_EUR"), difference("B_ASIA")],
             allowed="欧洲约+17.50、亚洲约−14.61个百分点；地域关系与观察到的胜率相关，双方实力尚未控制。",
             forbidden="跨洲旅行使欧洲增加17.50个百分点，或导致亚洲下降14.61个百分点。", figure="finding_03_relations"),
    ]
    card_payload = dict(schema_version="q3-final-conclusion-cards-v1", analysis_id=aid, source_run=q3["run_manifest"],
                        selection_status="Post-result presentation focus, not a preregistered inferential primary family; all comparisons retained",
                        cards=cards, supplementary=[dict(id="Q3-A01", evidence=[difference("C_EUR_151_VS_155"), difference("C_EUR_151_VS_154")],
                                                               allowed="东欧与西欧点估计接近，不等于证明无差异。"),
                                                    dict(id="Q3-A02", evidence=[difference("C_ASIA_030_VS_034")],
                                                         allowed="东亚减南亚约15.72个百分点；中亚全期调整率不可估，不加入完整调整排名。")],
                        boundary=dict(conditional_cells=155, observed=153, adjustable=71, zero_cells=2,
                                      observed_but_missing_positive_layers=82, contrasts=29, adjusted_contrasts=24,
                                      inference="not_run", strength_adjustment="not_run"), source_sha256=sources)
    (out / "conclusion_cards.json").write_bytes(json_bytes(card_payload))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    import numpy as np
    env, font = rendering_environment(manifest["rendering_runtime"]["font_file"])
    check(env == manifest["environment"]["rendering"], "Derived figures use the bound rendering environment")
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({"font.family": env["font_family"], "font.size": 14, "axes.unicode_minus": False, "svg.hashsalt": "q3-final-handoff-v1"})
    figures = ROOT / "outputs/figures/regions/presentation" / aid
    figures.mkdir(parents=True, exist_ok=True)
    generated = {}
    for card in cards:
        fig, ax = plt.subplots(figsize=(12.8, 7.2))
        if card["id"] != "Q3-F03":
            tid = "C_AFR" if card["id"] == "Q3-F01" else "C_AMER"
            gids = [x["group_id"] for x in card["evidence"] if x["table"] == "group_summary.csv"]
            rs = [groups[tid, gid] for gid in gids]
            ys = np.arange(len(rs))
            ax.barh(ys - .18, [100 * float(r["home_win_rate"]) for r in rs], height=.32, color="#e7a052", label="直接主胜率")
            ax.barh(ys + .18, [100 * float(r["standardized_home_win_rate"]) for r in rs], height=.32, color="#357ba2", label="共同构成调整率")
            for y, r in zip(ys, rs):
                ax.text(100 * float(r["standardized_home_win_rate"]) + 1, y + .18,
                        f"{100 * float(r['standardized_home_win_rate']):.2f}%", va="center", fontsize=14)
            ax.set_yticks(ys, [r["group_label"] + f"（n={int(r['n_matches']):,}）" for r in rs])
            ax.set_xlim(0, 100)
            ax.set_xlabel("主胜率（%）；平局保留在分母")
            reference = sum(int(r["n_reference_matches"]) for r in references[tid])
            subtitle = f"同一大洲参考、十个年代×赛事层；参考n={reference:,}"
        else:
            rs = [contrasts[x] for x in ("B_EUR", "B_ASIA")]
            ys = np.arange(2)
            ax.barh(ys - .18, [float(r["direct_difference_pp"]) for r in rs], height=.32, color="#e7a052", label="直接差")
            ax.barh(ys + .18, [float(r["adjusted_difference_pp"]) for r in rs], height=.32, color="#357ba2", label="共同构成调整差")
            for y, r in zip(ys, rs):
                value = float(r["adjusted_difference_pp"])
                ax.text(value + (0.6 if value > 0 else -0.6), y + .18, f"{value:+.2f}",
                        va="center", ha="left" if value > 0 else "right", fontsize=15)
            ax.set_yticks(ys, ["欧洲主队", "亚洲主队"])
            ax.set_xlim(-25, 25)
            ax.axvline(0, color="#555555", linewidth=1)
            ax.set_xlabel("洲外对手减同一研究分区对手（百分点）")
            subtitle = "各自主队背景与共同参考；不同目标不拼成地区排名"
        ax.invert_yaxis()
        ax.set_title(subtitle, fontsize=14, pad=20)
        ax.grid(axis="x", alpha=.2)
        ax.legend(loc="lower right", fontsize=12)
        fig.suptitle(card["title"], fontsize=22, y=.97)
        fig.text(.02, .07, "1980—2024男子国家队非中立比赛；加时后、不含点球；无区间、未控制实力，仅描述。", fontsize=11)
        fig.text(.02, .025, "项目例外：土耳其归欧洲/南欧，伊朗归西亚，澳大利亚归亚洲/东南亚。", fontsize=11)
        pin_figure_font(fig, font)
        fig.tight_layout(rect=(.02, .12, .98, .91))
        pin_figure_font(fig, font)
        for extension in ("png", "svg"):
            target = figures / (card["figure"] + "." + extension)
            require(not target.exists(), "REG_OUTPUT_COLLISION", "Do not overwrite presentation figure")
            metadata = {"Software": "q3-final-handoff-v1"} if extension == "png" else {"Date": None, "Creator": "q3-final-handoff-v1"}
            fig.savefig(target, dpi=150, metadata=metadata)
            generated[target.relative_to(ROOT).as_posix()] = sha(target)
        plt.close(fig)
    assets = dict(schema_version="q3-presentation-assets-v1", analysis_id=aid, source_run=q3["run_manifest"],
                  conclusion_cards=(out / "conclusion_cards.json").relative_to(ROOT).as_posix(),
                  primary_figure_pairs=generated, appendix_figures=read_json(ROOT / q3["display_data"])["figures"],
                  presentation_scope="90-second suggested segment within whole-group 10-minute presentation; not a finished HTML page",
                  full_comparisons=29, directed_cells=155, source_sha256=sources)
    (out / "presentation_assets.json").write_bytes(json_bytes(assets))
    generated.update({(out / name).relative_to(ROOT).as_posix(): sha(out / name)
                      for name in ("conclusion_cards.json", "presentation_assets.json")})
    result = dict(schema_version="q3-final-handoff-review-v1", decision_log_id="R20261027-05", status="passed",
                  analysis_id=aid, source_run=q3["run_manifest"], arithmetic_checks=checks, run_integrity=integrity,
                  preceding_questions=protected, groups=len(groups), contrasts=len(contrasts), conditional_cells=155,
                  source_sha256=sources, output_sha256=generated, builder_sha256=sha(Path(__file__)),
                  core_run_unchanged=True, pytest="Existing 160-test record verified as source; not rerun for material-only changes",
                  closure="Description and agreed material preparation closed; inference/final delivery/human review explicitly deferred",
                  inference="not_run", sensitivity="not_run", human_review="not_performed")
    (out / "review.json").write_bytes(json_bytes(result))
    print(json.dumps({k: v for k, v in result.items() if k not in ("source_sha256", "output_sha256")}, ensure_ascii=True))


if __name__ == "__main__":
    main()
