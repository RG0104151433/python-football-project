"""Extract presentation facts with source bindings; no final HTML or paper."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.io import publish,read_rows
from src.data_contract import file_hash


def run():
    sources={"current":"outputs/logs/strength/rolling-handoff-1a1f052c0b16becafcad/report.json",
        "legacy_checks":"data/processed/strength/joint-input-0812683da0560b0b687b/legacy_period_checks.json",
        "old_failed_reference":"data/processed/strength/ratings-27b4f4352e5aec283bde/rating_report.json",
        "release":"data/processed/strength/joint-input-0812683da0560b0b687b/release.json",
        "repeat":"outputs/logs/strength/review-20261029/reproducibility.json",
        "numeric":"data/processed/strength/joint-input-0812683da0560b0b687b/full_scale_numeric_comparison.csv",
        "jump":"outputs/logs/strength/streaming-followup-ca0db86dd4df83030df4/comparisons.csv"}
    data={k:json.loads((ROOT/v).read_text(encoding="utf-8")) for k,v in sources.items() if v.endswith(".json")}
    old=next(r for r in data["old_failed_reference"]["external_checks"] if r["period"]=="last_time_holdout_2023_2024" and r["scope"]=="accepted_study")
    current=next(r for r in data["legacy_checks"] if r["period"]=="legacy_reused_2023_2024" and r["scope"]=="accepted_study")
    failed=next(r for r in data["legacy_checks"] if r["period"]=="legacy_reused_2020_2022" and r["scope"]=="accepted_study")
    display=dict(status="stage2_exploratory_handoff_not_full_forecast_pass",study_matches=24917,
        rows_per_full_candidate=38919,post1980_rolling_rows=data["current"]["rows"],
        latest_2023_2024=dict(count=current["count"],old_mean_home_bias_pp=100*old["home_probability_bias"],
            current_mean_home_bias_pp=100*current["home_probability_bias"],current_accuracy=current["accuracy"],
            current_log_loss=current["log_loss"]),
        remaining_failure_2020_2022=dict(count=failed["count"],mean_home_bias_pp=100*failed["home_probability_bias"],
            threshold_pp=3,passed=failed["passed"]),
        max_type_bias_pp=100*data["release"]["max_era_type_home_bias"],
        repeat_files=data["repeat"]["files_checked"],repeat_passed=data["repeat"]["passed"],
        max_strict_probability_difference=max(float(r["max_probability_difference"]) for r in read_rows(ROOT/sources["numeric"])),
        jump_comparisons=read_rows(ROOT/sources["jump"]),
        experimental_joint_input_admitted=data["release"]["experimental_joint_input_admitted"],
        unrestricted_forecast_admitted=False,joint_model_fitted=False,historical_tests_reused=True,
        sources={k:dict(path=v,sha256=file_hash(ROOT/v)) for k,v in sources.items()},
        mandatory_footnotes=["Historical rolling checks are reused, not independent blind tests",
            "Recent pooled improvement does not erase2020-2022 or tournament-specific calibration failure",
            "Jump route rejected for numerical approximation sensitivity, not proven inferior prediction",
            "Conditional covariance and alternative-score ranges are not real-world unconditional confidence guarantees"])
    folder,_=publish("handoff-display",{"sources":display["sources"],"runner_sha":file_hash(Path(__file__))},jsons={"display_data.json":display})
    print(folder.relative_to(ROOT).as_posix(),flush=True)


if __name__=="__main__":run()
