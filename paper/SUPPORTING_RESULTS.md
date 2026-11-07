# Supporting results and reproduction guide

Current paper coverage review: R20261107-03 (7 November 2026), Codex (AI).
This guide indexes existing adopted results; it does not copy the data, rerun
models, or turn exploratory/historical versions into adopted evidence.
Paths below are relative to the repository root. Model assumptions and the
difference between a reported estimate, a model-conditional range, and a future
outcome remain as stated in the paper.

## How to read the complete study

The paper presents representative evidence for its three research questions.
The original nine study stages are mapped below. Use
`研究/pipeline_state.json` to identify adopted versions, and
`scripts/README.md` for the corresponding configuration, execution and verification
entry points. Research history and rejected iterations are preserved in
`文档/01_项目方案/研究日志与决策记录.md`. Those materials include Chinese working
notes; the manuscript, this guide and the paper figures are in English.

## Data preparation and identity confirmation — Method 2.1

- Registered original files: `data/raw/manifest.json` and `data/raw/international_results/`.
- Base preparation version: `data/processed/prep-3fab808178cf8ad71d88/`.
- Adopted identity/eligibility record: `data/processed/team_identity/identity-reviewed-29d880765c1623764940/identity_manifest.json`.
- Cleaning rules and row dispositions: `src/clean.py`, `src/audit.py`, `src/validate.py` and the base preparation outputs.
- Research narrative: `研究/00_数据再次确认/README.md`.

The 24,917-match study population includes 117 owner-accepted records. It is not a
certification of every record in the global historical archive.

## Stage 1: historical eras — Method 2.2; Results 3.1

Complete adopted tables: `outputs/tables/eras/eras-fifa-dddf11dd6dc0b7531b88/`.

- `era_estimates.csv` and `era_summary.csv`: all five era rates and sample counts.
- `era_contrasts.csv`, `reference_weights.csv`: direct/adjusted contrasts and their references.
- `weight_sensitivity.csv`, `schedule_diagnostics.csv`, `team_schedule.csv`: weight and schedule diagnostics.
- Adopted execution: `outputs/logs/team_identity/confirmed-eras-20261025T013539824757Z-45eb57c2/run_manifest.json`.

The final era contains five years. Historical rate differences are separate from
strength-adjusted comparisons in Stage 5.

## Stage 2: friendlies and other tournaments — Method 2.2; Results 3.1

Complete adopted tables: `outputs/tables/tournaments/tournaments-4893e38db46f83f6c219/`.

- `type_estimates.csv`, `type_differences.csv`: whole-period, era-specific and rolling results.
- `rolling_windows.csv`, `rolling_counts.csv`, `window_membership.csv`: all 36 overlapping ten-year windows and their composition.
- `reference_weights.csv`, `grouped_counts.csv`: adjustment references and raw denominators.
- Adopted execution: `outputs/logs/tournaments/tournaments-20261025T022318417600Z-78d8e623/run_manifest.json`.

The difference table contains both raw and standardized window estimates; 36
windows are not 36 independent repetitions. Descriptive friendly weighting and
the rating model's information weight have different roles.

## Stage 3: geography and directional matchups — Method 2.1–2.2; Results 3.1

Complete adopted tables: `outputs/tables/regions/regions-0a1c61664a722e6c641f/`.

- `contrast_results.csv`: all 29 predefined regional contrasts, including unsupported rows.
- `matchup_rates.csv`: all 155 directional matchups; 153 have matches and 71 support complete adjustment.
- `group_summary.csv`, `stratum_counts.csv`, `reference_weights.csv`: group rates, era/type cells and references.
- `study_team_registry.csv`: explicit team/entity assignments and effective rules.
- `opponent_composition.csv`, `team_contributions.csv`: opponent balance and team contributions.
- Adopted execution: `outputs/logs/regions/closeout-20261027/regions-20261027T084412226301Z-f05899a3/run_manifest.json`.

Europe uses Eastern, Southern, Western and Northern study groups; Africa uses
North, West and remaining sub-Saharan groups. Asia retains its five study
subregions; the Americas include the South American focus. Within-continent
opponents use study subregions, while external opponents are aggregated by macro
region. Turkey, Iran and Australia follow the explicit study overrides described
in Method 2.1. Oceania is not subdivided. These conventions are not universal
geographic or historical confederation definitions.

## Stage 4: shared historical uncertainty and sensitivity — Method 2.2; Results 3.1

Complete adopted tables: `outputs/tables/reliability/applied-ab04b82da3b12ca434239452/`.

- `interval_results.csv`: 292 original targets, 198 model-conditional ranges and 94 unsupported targets.
- `conclusion_review.csv`, `sensitivity_summary.csv`, `sensitivity_results.csv`: interpretations and 26,704 rows from 324 sensitivity scenarios.
- `sensitivity_references.csv`, `sensitivity_membership_changes.csv`: changed references and row-level membership changes.
- Adopted execution and limits: `outputs/logs/reliability/application-20261028/adoption.json`.
- Mathematical construction/iteration records: `研究/04_共同可靠性/第三步_条件论证与候选方法验收方案.md` and `研究/04_共同可靠性/第三步_联合模型选择与第四步交接.md`.
- Application/reproduction: `研究/04_共同可靠性/第四步_运行结果与复现.md`.

The 198 calculable targets belong to four separately calibrated families (27, 64, 36 and 71 quantities), not one globally covered family. The frozen calibration contract is `outputs/logs/reliability/joint-envelope-20261028/fourth_step_contract.json`. The permanent global-shock pressure failure remains a declared boundary. Changed
targets do not automatically receive newly calibrated intervals. Validation
counts are computational checks, not additional independent football histories.

## Stage 5: pre-match strength and joint prediction — Method 2.3–2.5; Results 3.2

- Adopted closeout pointer: `outputs/logs/strength_q5_closeout/current.json`.
- Complete closeout records: `outputs/logs/strength_q5_closeout/q5-closeout-1c4c593487304afa0f6a/`, including `paper_notes.md`, `presentation_data.json` and `object_disposition.csv`.
- Same-match predictions/metrics: `outputs/tables/strength_joint/rolling-prediction-4722c7b1b5f63cef35e3/`, including `group_metrics.csv` and `yearly_metrics.csv`.
- Rating logic and implementation: `研究/05_赛前实力/实力评估_逻辑与运行说明.md`, `src/strength/` and `src/strength_joint/`.
- Adopted handoff: `研究/05_赛前实力/第五问_收尾与下一问交接.md`.

The stage handoff links the rating initialization/selection, joint analysis,
sensitivity and complete-history versus first-order validation records. The 30
admitted quantities and 24 unadmitted regional changes must remain distinct.
The main predictor is binary; the native auxiliary predictor is three-class.

## Stage 6: historical information length — Method 2.5; Results 3.3

- Outcome-history results: `outputs/tables/history_window/outcome-0a52e15e2ae493570acb/`.
- Rating-memory results: `outputs/tables/history_window/rating-memory-1c8aebdf661ccdddff05/`.
- Joint comparison and controlled cost records: `outputs/tables/history_window/joint-review-4888d987645daee73e19/`.
- Reliability checks: `outputs/tables/history_window/reliability-c3586b1614a4ba59c9c5/`.
- Protocol, limitations and handoff: `研究/06_历史参考周期/README.md`.

These contain the tested 2/4/8/12/20-year and cumulative candidates, the selected
joint combinations and past-only window selection. A measured component saving
is not a reduction in total pipeline time. No universal optimal window is claimed.

## Stage 7: regional applicability — Method 2.5; Results 3.4

- Regional prediction metrics: `outputs/tables/regional_effectiveness/regional-evaluation-7ea3e4ab7c7dbb8eeb58/`.
- Composition/calibration diagnostics: `outputs/tables/regional_effectiveness/regional-diagnostics-3e4473ad441fd44fe4df/`.
- Fixed-prediction deletion checks: `outputs/tables/regional_effectiveness/regional-stability-366606ed5bca8e0fe6b8/`.
- Final scope and conclusions: `研究/07_地区有效性/第七问_研究说明与收尾交接.md`.

The files retain sparse or unsupported cells and the South America/Oceania
limitations. Deletion checks omit scored observations without rebuilding the
original learning history.

## Stage 8: sealed prospective application — Results 3.5

- Full 52-fixture forecast ledger and supporting tables: `outputs/tables/future_predictions/future-unl-61f639846da9193d4cca/`, especially `forecasts.csv`.
- Adopted information dates and issue checks: `outputs/logs/future_predictions/future-unl-61f639846da9193d4cca/handoff_adoption.json`.
- Closeout: `outputs/logs/future_predictions/q8-closeout-7bf020e93213562df8de/closeout_adoption.json`.
- Reading guide: `研究/08_未来比赛预测/运行结果与预测清单.md`.

There are 49 joint binary forecasts, three withheld joint estimates, and 52
auxiliary three-class forecasts. Outcomes remain unevaluated in this submission.

## Stage 9: proposed extensions — Discussion 4.3

`研究/09_预测优化展望/README.md` contains the four proposed directions, their
mathematical reasoning and limitations: joint three-class outcomes, calibration,
additional information/mechanisms and club transfer. There are no new optimization
experiments or club-model results to report. Optional Stage 10 club experiments
were not implemented.

## Paper figures and equations

`paper/图表来源说明.md` identifies each adopted graphic. The historical overview
has machine-readable row selections in `paper/historical_overview_manifest.json`.
`paper/results_evidence.json` and `paper/method_evidence.json` preserve the main
numerical/method bindings; `paper/coverage_layout_review.json` records this coverage
check. The eight displayed equations describe standardization, historical
envelopes, strength evolution, outcome likelihood, strength-difference mixtures,
joint probabilities, fixed-reference contrasts and probability scores. Detailed
kernel definitions, filter derivations, simulation iterations and run-specific
settings remain in the linked stage records rather than being reproduced as
additional main-text formulas.


## Review clarifications: configuration, environment and evidence scope

The following resolves the presentation issues identified in
`outputs/review_layer3/最终审查报告.md`; that independent report is preserved unchanged.

- **Adopted rating parameters:** `data/processed/strength/jump-ratings-451ecade0bf84ee0bfb6/report.json`, model `jump_full`: q=.03, jump_rate=.08, jump_sd=1.2, delta=.4, alpha=.65, epsilon=.05 and home_q=.005. This is the `M23_PARAMETERS` source in `paper/method_evidence.json`.
- **Different exercise:** `config/strength_handoff.json` sets jump_rate=0 for the Gaussian special-case handoff/past-only rule evaluation. It does not override the full-jump input adopted in `config/strength_joint.json`.
- **Reproduce Table 3:** from the repository root run `python scripts/analyze_strength_predictive_validation.py`. It loads `config/strength_joint.json` through `src/strength_joint/contract.py`. Use `outputs/tables/strength_joint/rolling-prediction-4722c7b1b5f63cef35e3/protocol.json` and `manifest.json` for the adopted v2 protocol, hashes and environment. Historical `rolling-prediction-41c77e3a1f9eeba865ec` is v1: fixed full-cohort outcome-free geographic coding; v2 constructs geographic coding from each year's past training rows. The paper adopts v2, not the best result selected among interchangeable seeds. Code changes may alter a newly generated content-derived directory ID; compare its protocol and metrics rather than assuming its directory name.
- **Runtime and dependencies:** the adopted v2 manifest records Windows 11, Python 3.14.8, NumPy 2.5.4 and SciPy 1.18.1. `requirements.txt` pins the recorded full package list; `requirements-core.txt` supplies minimum versions and is not an exact lock. No cross-platform lock or fresh-machine model reproduction is claimed. Follow `文档/02_环境配置/克隆仓库后的快速上手.md`; running `check_env.py` writes a local environment report. The review's Python 3.13.14 read-only check is a separate execution record.
- **Priors:** `src/strength/gaussian.py`, `GaussianStrengthFilter.__init__`, defines variances 1 and .25; `config/strength_global_v3.json` records initialization settings. The full-jump filter uses the common Gaussian state machinery.
- **Numerics:** `config/strength_joint.json` / `numerics` records starts .3/1/2 and coefficient/slope bounds; `src/strength_predictive_validation.py` / `fit_past` implements annual optimization and gates.
- **Historical covariance and calibration:** `研究/04_共同可靠性/第三步_联合模型选择与第四步交接.md` defines the six components; `outputs/logs/reliability/joint-envelope-20261028/fourth_step_contract.json` fixes the family calibration. These are distinct from the .25 same-day simulation parameter in `config/strength_inference_validation.json`.
- **153 observed matchups:** count rows with `n_matches>0` in the adopted `matchup_rates.csv`; 155 total rows include two empty groups. The number is derived from row counts, not a separate scalar field.
- **Data dates and cutpoints:** `data/raw/manifest.json` records the results file's `date_end`; `src/regional_diagnostics.py` / `thresholds` records training date bounds and computes the pre-2010 cutpoints. Use the stage protocol and source-linked configuration in its adopted manifest.
- **Randomness:** `config/strength_joint.json` contains exploratory simulation seeds; `config/strength_inference_validation.json` contains named truth/calibration/validation streams. `src/reliability/models.py` / `keyed_rng` derives reproducible seeds from labels. These mechanisms have different roles and are not one global seed.
- **Auxiliary forecasts:** the native three-class probabilities are background outputs, not competitors in Table 3's binary comparison. This response does not establish independently validated prospective three-class performance.
- **Evidence scope:** `paper/results_evidence.json` contains 17 registered sources and 57 selected bindings, including derived summaries. It is a selected Results register, not an assertion that every repository row or inference has been independently recomputed. `paper/method_evidence.json` binds implementation claims. The review's sample audit and the author response's source/row checks remain distinct from model-level replication.
- **Public-data use:** the analysis uses historical match records distributed under CC0. It does not recruit participants or collect new individual-level health data. No ethics approval/exemption, funding or conflict-of-interest declaration is inferred from this dataset licence. Author identities, contributions, funding and conflicts await the project owner's confirmation.


## Expanded model argument and rating evidence (R20261107-09)

The current manuscript has six Method subsections and six Results subsections. Method 2.3 compares transferable ideas from Elo-derived prediction, dynamic paired comparisons, TrueSkill, EP, and goal-count modelling. Sections 2.4--2.5 derive transition moments, the robust likelihood responsibility, opponent covariance, Gaussian tilted-moment identities with their limits, and the integrated probit probability. Section 2.6 distinguishes complete-history uncertainty route A from its first-order alternative B. These are stated mathematical identities and conditional modelling choices, not proofs of universal football validity.

Results 3.2 now presents the strength estimator itself: selected pre-match states, actual numerical and probability-correction failures and repairs, and a separate three-class pipeline evaluation. Figure 3 uses the adopted delivery's study_prematch_features.csv; Table 3 uses the same delivery's report.json. Both are generated by paper/make_strength_evidence.py. Source fingerprints, exact selected states, four disjoint period selectors, and count checks are in paper/strength_evidence_manifest.json. The four periods sum to 24,917; the binary comparison is now Table 4 and still uses 21,413 different evaluation matches.

The eight-candidate composition report is outputs/logs/strength/composed-calibration-8176105d420b3f2400eb/report.json. Its two admitted candidates' losses 0.8909487480 and 0.8912580894 are weighted over the four accepted_study periods (24,917), rather than all_learning. This denominator has been rechecked in the presentation generator; the original scientific report remains unchanged. Numerical-reference, cold-start, initialization, simulation, replay, and test counts are prior recorded checks, not newly rerun experiments. Development and failed versions remain indexed in 研究/05_赛前实力/第二环节_验收与正式交接.md; final contrast-route choices are indexed in 研究/05_赛前实力/第五问_收尾与下一问交接.md.

Current manuscript and PDF fingerprints and the scope of the writing checks are in paper/method_expansion_manifest.json. Earlier dated draft/review manifests retain historical fingerprints and must not be used to authenticate this revision. No external FIFA/Elo evaluation or new prospective accuracy is claimed.


## Separate language revision (R20261107-10)

The preferred reading version is paper/language_revision_20261107/main.tex, compiled to its own build/main.pdf. The previous paper/main.tex, sections, and build/main.pdf remain unchanged for comparison. Figures and generated table rows are shared from paper/figures and retain their recorded hashes. The language_changes.diff and revision_manifest.json in the revision directory record the edits and checks. This revision changes wording and paragraph organization without rerunning the models or changing numerical claims, displayed equations, citation sequences, or study scope. Both PDFs have 22 pages.


## Course requirements and academic-language check (R20261107-11)

The current language version has 23 pages and 18 references. Its requirements_language_review.md/.json records direct comparison with the assignment images, source attribution, implementation-flow and contribution clarifications, and cautious statistical wording. Three references were added: FIFA affiliation records, the UEFA schedule underlying the archived fixture ledger, and Groll et al. (2024) as contemporary methodological context. No ranking data, fixture inputs, predictions, model parameters, or empirical results were updated. The Groll paper was not implemented as a benchmark; metadata, abstract, and the first two PDF pages were inspected.

The original paper sources/PDF remain unchanged. Names, student IDs, and classes remain deferred by the project lead; actual independent reproduction and final submission-package checks are not certified by this editorial review. Cite checking must select the current version: python paper/check_citations.py --paper-dir paper/language_revision_20261107 --strict. Earlier R10/R09 manifests identify historical artifacts.
