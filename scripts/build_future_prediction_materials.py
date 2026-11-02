"""Build Q8 submission materials from sealed forecasts; never train or predict."""
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
DOC = "研究/08_未来比赛预测/第八问_研究说明与收尾交接.md"
LIST = "研究/08_未来比赛预测/运行结果与预测清单.md"
SELF = "scripts/build_future_prediction_materials.py"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n", encoding="utf-8", newline="\n")


def run():
    pointer = read_json(ROOT / "outputs/logs/future_predictions/current.json")
    log = ROOT / pointer["log_directory"]
    table = ROOT / pointer["table_directory"]
    manifest = read_json(log / "manifest.json")
    checks = []

    def check(label, condition):
        if not condition:
            raise ValueError(label)
        checks.append(label)

    check("original_manifest_matches_pointer",
          digest(log / "manifest.json") == pointer["manifest_sha256"])
    for section in (manifest["identity"]["inputs"], manifest["identity"]["code"],
                    manifest["outputs"]):
        for path, expected in section.items():
            check("sealed_sha:" + path, digest(ROOT / path) == expected)
    old_adoption = read_json(log / "handoff_adoption.json")
    check("original_audit_preserved", digest(log / "independent_audit.json")
          == old_adoption["independent_audit_sha256"])
    with (table / "forecasts.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    check("52_unique", len(rows) == len({r["match_id"] for r in rows}) == 52)
    check("26_each_round", Counter(r["round"] for r in rows) == {"5": 26, "6": 26})
    check("only_unobserved_forecasts", all(r["future_result_received"] == "false" for r in rows))

    # Match the existing Chinese list in date/order and verify its rounded main probability.
    translated = []
    day = None
    for line in (ROOT / LIST).read_text(encoding="utf-8-sig").splitlines():
        if re.fullmatch(r"### \d{4}-\d{2}-\d{2}", line):
            day = line[4:]
        match = re.match(r"- \*\*(.+?)—(.+?)\*\*：", line)
        if match:
            translated.append((day, *match.groups(), line))
    check("52_chinese_entries", len(translated) == len(rows))
    for row, (day, home, away, line) in zip(rows, translated):
        check("list_date:" + row["match_id"], row["date"] == day)
        if row["main_home_probability"]:
            check("list_probability:" + row["match_id"],
                  f"主胜{100 * float(row['main_home_probability']):.1f}%" in line)
        row["label_zh"] = home + "—" + away

    main = [r for r in rows if r["main_status"] == "issued_binary"]
    withheld = [r for r in rows if r["main_status"] != "issued_binary"]
    summary = dict(total=len(rows), main=len(main), withheld=len(withheld),
        main_home_pick=sum(float(r["main_home_probability"]) >= .5 for r in main),
        main_nonhome_pick=sum(float(r["main_home_probability"]) < .5 for r in main),
        conditional_range_crosses_half=sum(float(r["latent_probability_p05"]) <= .5
            <= float(r["latent_probability_p95"]) for r in main),
        actual_results_received=0, actual_accuracy=None,
        forecast_run_id=pointer["run_id"], issued_at_utc=pointer["issued_at_utc"],
        latest_learning_date="2026-10-06", coefficients_last_date="2025-12-29",
        round6_scope="Nov2 early forecast; no round5 results", human_review=False,
        scope="pre-match application; no empirical future accuracy yet",
        uncertainty="fixed-coefficient latent strength central90 probability range; not real coverage")
    check("adopted_summary", [summary[k] for k in
        ("total", "main", "withheld", "main_home_pick", "main_nonhome_pick",
         "conditional_range_crosses_half")] == [52, 49, 3, 21, 28, 32])
    check("third_country_main_blank", len(withheld) == 3 and all(
        not r["main_home_probability"] and not r["latent_probability_p05"]
        and not r["latent_probability_p95"] for r in withheld))
    choices = [("Czech Republic", "Spain", "主胜倾向低"),
               ("Netherlands", "Greece", "接近五五开"),
               ("England", "Croatia", "有倾向仍需谨慎"),
               ("Ukraine", "Georgia", "第三国场地不外推")]
    cases = []
    for home, away, role in choices:
        found = [r for r in rows if r["home_team"] == home and r["away_team"] == away]
        check("unique_case:" + home, len(found) == 1)
        r = found[0]
        cases.append({k: r[k] for k in ("match_id", "date", "label_zh",
            "main_home_probability", "latent_probability_p05", "latent_probability_p95",
            "native_home_probability", "native_draw_probability", "native_away_probability",
            "main_status", "round6_preliminary", "venue_basis")} | {"role": role})

    inputs = {p: digest(ROOT / p) for p in [
        pointer["log_directory"] + "/manifest.json",
        pointer["log_directory"] + "/independent_audit.json",
        pointer["log_directory"] + "/handoff_adoption.json",
        pointer["table_directory"] + "/forecasts.csv", DOC, LIST]}
    font = font_manager.FontProperties(family="Microsoft YaHei")
    font_path = Path(font_manager.findfont(font, fallback_to_default=False))
    environment = {"python": sys.version.split()[0], "matplotlib": matplotlib.__version__,
                   "font": "Microsoft YaHei", "font_sha256": digest(font_path)}
    identity = dict(forecast_run_id=pointer["run_id"], inputs=inputs,
                    code={SELF: digest(ROOT / SELF)}, environment=environment,
                    decision="R20261102-13", scope=summary["scope"])
    rid = "q8-closeout-" + hashlib.sha256(canonical(identity)).hexdigest()[:20]
    folder = ROOT / "outputs/logs/future_predictions" / rid
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "manifest.json").exists():
        for path, expected in read_json(folder / "manifest.json")["outputs"].items():
            if digest(ROOT / path) != expected:
                raise ValueError("MATERIAL_CHANGED:" + path)
    else:
        plt.rcParams.update({"font.family": "Microsoft YaHei", "axes.unicode_minus": False,
                             "svg.fonttype": "none", "font.size": 10})

        def plot(items, filename, title):
            fig, ax = plt.subplots(figsize=(11.5, max(3.5, len(items) * .30 + 2.4)))
            for i, r in enumerate(items):
                p, lo, hi = (100 * float(r[k]) for k in
                    ("main_home_probability", "latent_probability_p05", "latent_probability_p95"))
                ax.hlines(i, lo, hi, color="#275c83", linewidth=1.5)
                ax.scatter([p], [i], color="#275c83", s=21, zorder=3)
            ax.axvline(50, color="0.55", linestyle="--", linewidth=.8)
            ax.set_yticks(range(len(items)),
                          [r["date"][5:] + "  " + r["label_zh"] for r in items])
            ax.invert_yaxis()
            ax.set_xlim(0, 100)
            ax.set_xlabel("共同模型主胜概率（%）；圆点为预测，横线为实力条件中央90%范围")
            ax.set_ylabel("比赛日期与主队—客队（赛事当地日期）")
            ax.set_title(title, loc="left", pad=18)
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="x", alpha=.15)
            fig.text(.02, .02,
                "来源：" + pointer["run_id"] + " / forecasts.csv\n"
                "11月2日封存；第6轮为提前版。范围固定模型系数，不是现实置信保证；赛果尚未发生。"
                + ("\n另3场第三国场地未套用主模型；完整52场见原清单。" if len(items) == 49 else ""),
                fontsize=8, va="bottom")
            fig.tight_layout(rect=(0, .13 if len(items) < 10 else .065, 1, 1))
            for extension in ("png", "svg"):
                fig.savefig(folder / (filename + "." + extension), dpi=160,
                            metadata={"Creator": "Q8 sealed forecast materials"})
            plt.close(fig)

        plot(main, "forecast_overview", "11月欧国联：49场赛前主胜概率与实力条件范围")
        plot([r for r in cases if r["main_home_probability"]], "forecast_examples",
             "三个例子：主胜倾向低、接近五五开、有倾向仍需谨慎")
        write_json(folder / "summary.json", summary)
        fields = list(cases[0])
        with (folder / "selected_cases.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(cases)
        story = {"source_run": pointer["run_id"], "summary": summary, "cases": cases,
            "full_list": LIST, "full_forecasts": pointer["table_directory"] + "/forecasts.csv",
            "selection_basis": "explanatory roles chosen before outcomes, not performance selection",
            "screens": [
                {"title": "从历史走到未来", "text": "更新真实赛果 → 更新球队判断 → 输入未来赛程 → 封存概率与范围"},
                {"title": "模型有倾向，也有犹豫", "figure": "forecast_examples.png", "case_ids": [r["match_id"] for r in cases]},
                {"title": "交付一份可追溯的赛前预测", "text": "52场完整保留；49场主预测、3场不外推；实际表现尚未知"}],
            "not_claimed": ["future accuracy", "causal home effect", "real90 coverage", "lineups included"],
            "html_created": False, "browser_or_projector_verified": False}
        write_json(folder / "presentation_story.json", story)
        support = {"source_run": pointer["run_id"], "narrative": DOC,
            "methods": ["src/future_predictions.py", "config/future_predictions.json",
                        pointer["log_directory"] + "/models.json"],
            "results": [pointer["table_directory"] + "/forecasts.csv", "summary.json",
                        "selected_cases.csv", "forecast_overview.svg", "forecast_examples.svg"],
            "historical_validation_is_separate": "研究/05_赛前实力/第五问_收尾与下一问交接.md",
            "limitations": summary["uncertainty"], "actual_results": None,
            "path_base": "generated filenames relative to this material folder; repository paths otherwise"}
        write_json(folder / "paper_support.json", support)
        check("all_figures_written", all((folder / (stem + ext)).stat().st_size > 1000
              for stem in ("forecast_overview", "forecast_examples") for ext in (".png", ".svg")))
        with zipfile.ZipFile(folder / "source_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for path in [SELF, DOC, LIST]:
                archive.write(ROOT / path, path)
        write_json(folder / "review.json", {"passed": True, "checks": len(checks),
            "check_names": checks, "model_rerun": False, "human_review": False,
            "actual_results_evaluated": False, "visual_review": "pending separate image inspection",
            "previous_model_tests": 6, "previous_independent_model_checks": 2275,
            "previous_checks_reexecuted": False})
        outputs = {p.relative_to(ROOT).as_posix(): digest(p)
                   for p in sorted(folder.iterdir()) if p.is_file()}
        write_json(folder / "manifest.json", {"identity": identity, "outputs": outputs})
    result = {"material_run_id": rid, "forecast_run_id": pointer["run_id"],
              "directory": folder.relative_to(ROOT).as_posix(),
              "manifest_sha256": digest(folder / "manifest.json"),
              "submission_scope": summary["scope"], "actual_postmatch_complete": False}
    write_json(ROOT / "outputs/logs/future_predictions/closeout_pointer.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    run()
