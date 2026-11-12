# Script guide: choose the correct entry point

[中文](README.md) | **English**


Use the stage guide before running code. The [complete script catalog, Chinese](脚本用途目录.md) describes individual files; the [source map](../src/README.en.md) locates internal algorithms. Reading conclusions does not require recomputation.

Run commands from the repository root with your own environment. In PyCharm, choose a module for `src.*` and a script path for `scripts/*.py`; set the working directory to the repository root. See the [setup guide, Chinese](../文档/02_环境配置/克隆仓库后的快速上手.md).

Use adopted versions from [pipeline_state.json](../研究/pipeline_state.json). Larger filenames or default configurations are not necessarily current. Some audit/build tools write reports or publish state. Do not use `--help` unless the program parses it: `predict_future_matches.py`, for example, directly starts its computation.

<a id="data"></a>
## Preparation

Verify snapshot, audit, clean, then validate the emitted version:

```powershell
python -m src.snapshot --verify --config config.json
python -m src.audit --config config.json
python -m src.clean --config config.json
```

`src.validate` requires the actual `--data-version`. Registration changes snapshot metadata; routine checks use `--verify`. The unchanged raw archive contains known issues, so audit's documented `review_needed`/exit 1 is not an environment failure. Outputs are versioned under `data/processed/` and `outputs/logs/data_prep/`. Read the [data contract/design, Chinese](../文档/01_项目方案/前三项研究的数据标准与清洗脚本设计.md).

<a id="identity"></a>
## Identity and scope confirmation

```powershell
python scripts/adopt_membership_reviews.py --config config/membership_review_adoption.json
```

This adopts already reviewed match-level decisions; it does not repeat historical research. It produces `data/processed/team_identity/identity-reviewed-*/`. Verify the actual identity manifest with `build_team_identity.py --verify`. `audit_team_identity.py` inventories names and `plan_team_identity.py` previews rules. Read [sample confirmation](../研究/00_数据再次确认/README.en.md).

<a id="q1"></a>
## Q1: periods

```powershell
python scripts/analyze_confirmed_eras.py --config config/confirmed_eras_reviewed.json
```

Specify the reviewed configuration: the default `confirmed_eras.json` is older. Inputs bind cleaning, identity adoption and period rules. Tables/figures go to `outputs/tables/eras/` and `outputs/figures/eras/`; logs are under `outputs/logs/team_identity/`.

`audit_confirmed_eras.py` needs explicit configuration, actual/compare directories and a new report path. `closeout_reviewed_eras.py` packages adopted scope and display data. Earlier `src.analyze_eras`, `audit_eras_outputs.py` and `prepare_era_display_data.py` retain baseline purposes. See [local instructions, Chinese](../研究/01_年代变化/本地运行与复现.md).

<a id="q2"></a>
## Q2: match types

```powershell
python scripts/analyze_tournaments.py --config config/tournaments.json
```

Reads the existing clean table, membership scope and registered Q1 reference. Tables/figures/logs use the corresponding `tournaments/` directories. `audit_tournaments.py` requires `--run` and a new `--output`; `--compare` compares reruns. `--verify-run` checks an existing run, rather than re-estimating it. See [local instructions, Chinese](../研究/02_赛事类型差异/本地运行与复现.md).

<a id="q3"></a>
## Q3: geography

```powershell
python scripts/analyze_regions.py --config config/regions_study.json
```

Reads the same 24,917 matches, adopted groups, comparison list and exceptions. Output families are `regions/`. `verify_region_analysis.py` independently recalculates; `audit_region_support.py` examines missing/sparse cells. Both need actual run/report paths. See [local instructions, Chinese](../研究/03_地域差异/本地运行与复现.md).

`prepare_region_mapping.py`, `build_region_roster.py` and `build_region_protocol.py` are already-completed preparation/publication steps. The protocol builder can target the formal configuration. Do not rerun them routinely. `deduplicate_m49_sources.py` is an archival utility.

<a id="q4"></a>
## Q4: shared reliability

```powershell
python -m scripts.analyze_reliability --config config/reliability_analysis.json --stage all
```

The configuration binds adopted models, targets and scales. It does not redevelop the method. `--stage check` validates inputs and writes a log, not final ranges; use `--run` to continue a staged run. Output tables use `outputs/tables/reliability/applied-*/`.

`audit_reliability_analysis.py` independently checks the application and refuses to overwrite an existing independent report. Development tools such as `validate_reliability.py`, `refine_reliability.py` and `develop_reliability_joint.py` preserve simulations and failures, not a routine checklist. Read [application instructions, Chinese](../研究/04_共同可靠性/第四步_运行结果与复现.md).

<a id="q5"></a>
## Q5: strength, joint analysis and inference

These are separate stages, not one interchangeable “Q5 program.”

```powershell
python -m src.strength.delivery
python scripts/analyze_strength_joint.py --config config/strength_joint.json --stage analysis
```

The delivery module reads archived base ratings using `config/strength_final_delivery.json` and `config/strength_global_v3.json`; it does not relearn all ratings from 1950. It exports `data/processed/strength/strength-delivery-*/`. Check/repeat with `audit_final_strength_delivery.py` and `repeat_strength_delivery.py`. Actual base-rating replay uses `replay_archived_jump.py` with the adopted directory and can be expensive.

Joint analysis reads registered match-level preparation, writes `outputs/tables/strength_joint/joint-analysis-*/`, and registers `outputs/logs/strength_joint/analysis_pointer.json`. `audit_strength_joint.py` independently verifies a specified directory; `reproduce_strength_joint.py` compares a dedicated repeat.

`analyze_strength_interpretation.py` explains comparisons. `analyze_strength_predictive_validation.py` performs past-only yearly prediction, writes `rolling-prediction-*/` and registers `outputs/logs/strength_inference/prediction_pointer.json`; it has no independent help parser.

Sensitivity entry points are `prepare_strength_stage6.py` for target registration, `analyze_strength_stage6_sensitivity.py` for rating/sample variants and `analyze_strength_stage6_paired.py` for paired changes. `run_strength_inference_final.py`, `confirm_strength_inference.py` and `report_strength_inference.py` implement the dedicated two-route calculation, sequential confirmation and bounded application. They can be long-running; follow the [mathematical/iteration record, Chinese](../研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md).

`build_strength_q5_materials.py` packages adopted plots, pages and paper support. `audit_strength_q5_final.py` checks the final delivery; `audit_strength_q5_html.py` checks page resources/controls. Packaging is not refitting, and static checks do not certify classroom projection. Follow the [Q5 closeout, Chinese](../研究/05_赛前实力/第五问_收尾与下一问交接.md) and [rating handoff, Chinese](../研究/05_赛前实力/第二环节_验收与正式交接.md).

<a id="q6"></a>
## Q6: history length

Use `analyze_history_window.py` in its documented stages for outcome memory, rating memory and combinations, with the corresponding history-window configurations. `audit_history_window.py --stage outcome/rating` checks the selected stage; its default `pilot` is only the early feasibility study. `--refit-examples` actually recalculates examples. `check_history_window.py` also concerns feasibility. `build_history_window_materials.py` packages existing results.

- `outcome` uses [history_window_analysis.json](../config/history_window_analysis.json) for outcome-history length, yearly predictions and cost.
- `rating` uses [history_window_rating.json](../config/history_window_rating.json) to rebuild rating-memory policies and simulations; this is a longer computation.
- `joint` uses [history_window_joint.json](../config/history_window_joint.json) to combine preceding results.
- `joint-review` uses [history_window_joint_review.json](../config/history_window_joint_review.json) for scores and component costs.
- `reliability` uses [history_window_reliability.json](../config/history_window_reliability.json) for prescribed checks, including a few rating probes; it is not entirely read-only.

```powershell
python scripts/analyze_history_window.py --stage outcome --config config/history_window_analysis.json --resume
```

Use plan mode only where supported: `joint-review` and `reliability` do not support `--plan-only`. A plan is not a computed result.

Tables and figures use `outputs/tables/history_window/` and `outputs/figures/history_window/`; logs and stage pointers are in `outputs/logs/history_window/`. Final features, states and failure evidence remain; redundant completed-task checkpoints can be regenerated. Follow [Q6 operation and closeout, Chinese](../研究/06_历史参考周期/第六问_研究说明与收尾交接.md).

<a id="q7"></a>
## Q7: regional applicability

```powershell
python scripts/analyze_regional_effectiveness.py --config config/regional_effectiveness.json
python scripts/analyze_regional_diagnostics.py --config config/regional_effectiveness_diagnostics.json
python scripts/analyze_regional_stability.py --config config/regional_effectiveness_stability.json
```

These respectively describe prediction quality, explain strength/information composition and examine deletion stability. They read existing predictions, without retraining the rating/joint models. Matching audit scripts accept `--run-id`; record and specify the adopted ID. Tables/logs are under `regional_effectiveness/`, with the adopted materials at [closeout_pointer.json](../outputs/logs/regional_effectiveness/closeout_pointer.json).

<a id="q8"></a>
## Q8: prospective forecasts

```powershell
python scripts/predict_future_matches.py
```

The script internally reads `config/future_predictions.json`; it has no `--config` or separate `--help`. Sources bind recent matches, fixtures, archived strength and historical joint-model records. Results are in `outputs/tables/future_predictions/<run_id>/`, with logs and [current.json](../outputs/logs/future_predictions/current.json).

`audit_future_predictions.py --run-id …` recalculates checks and writes a report; `build_future_prediction_materials.py` packages sealed results. `evaluate_future_matches.py` is a later extension requiring verified actual results via `--results`. No actual future-fixture accuracy is currently recorded. See [forecast instructions, Chinese](../研究/08_未来比赛预测/运行结果与预测清单.md).

<a id="q9"></a>
## Q9 and optional Q10

[Q9](../研究/09_预测优化展望/README.en.md) is a documented outlook, with no new experimental script or result. The actual club experiment remains optional and unimplemented.

## Maintenance and historical tools

The [complete catalog](脚本用途目录.md) separates preparation, analysis, verification, reproduction, materials, development, historical handoff and later evaluation. Real failures remain evidence. `seal_*`, `sync_*` and `finalize_*` can publish or seal decisions; they are not generic harmless checks.

Documentation checks use `python scripts/audit_documentation.py`; this reads text, checks local links and README language pairs, and writes an audit report. It does not verify every external webpage or rerun models.
