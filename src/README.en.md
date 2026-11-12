# Code map: where are the methods implemented?

[中文](README.md) | **English**


Start with the [script guide](../scripts/README.en.md) to run a question. Most files here are imported by entry points and should not be executed individually. Use `python -m src.…` where a module entry is explicitly provided, preserving package-relative imports.

## From data to results

- Preparation: [snapshot.py](snapshot.py) registers/verifies source snapshots; [audit.py](audit.py) reports anomalies; [clean.py](clean.py) creates a traceable version; [validate.py](validate.py) verifies it. [data_contract.py](data_contract.py) defines shared fields, versions and serialization.
- Q1: [eras/](eras/) handles selection, integer counts, standardization and export. [analyze_eras.py](analyze_eras.py) retains the earlier baseline; adopted identity-confirmed analysis uses [analyze_confirmed_eras.py](../scripts/analyze_confirmed_eras.py) with the explicit adopted configuration.
- Q2: [tournaments/](tournaments/) handles match-type grouping, period composition, rolling windows and output.
- Q3: [regions/](regions/) handles inputs, groups, overall/directed combinations, common references and plots.
- Q4: [reliability/](reliability/) contains development and application. `application.py`, `sensitivity.py`, `interpretation.py` and `reporting.py` implement adopted calculations, variants, interpretation and reporting. Earlier `models.py` routes do not automatically represent the final method.
- Q5 ratings: [strength/](strength/) handles outcomes, bilateral updating, jumps, uncertainty, calibration and handoff. Read `collapsed_jump.py`, `filter.py`, `calibration.py` and `delivery.py` alongside the mathematical stage notes.
- Q5 joint analysis: [strength_joint/](strength_joint/) implements match interfaces, design variables, probability integration, fitting, contrasts and verification. [strength_interpretation.py](strength_interpretation.py) and [strength_predictive_validation.py](strength_predictive_validation.py) handle interpretation and chronological prediction.
- Q5 inference: [strength_inference/](strength_inference/) retains both routes, simulated worlds, targets and comparisons. `strength_stage6_*.py` handles registration/sensitivity; `strength_inference_numerics.py` and `strength_inference_report.py` provide final numerical retries and bounded conclusions. [strength_q5_closeout.py](strength_q5_closeout.py) packages existing results into plots, HTML and paper support.
- Q6: [history_window/](history_window/) separates outcome-model memory, rating memory, combinations, limited checks and cost. Entry points are in `scripts/`.
- Q7: [regional_effectiveness.py](regional_effectiveness.py), [regional_diagnostics.py](regional_diagnostics.py) and [regional_stability.py](regional_stability.py) read existing predictions to summarize performance, composition and deletion stability.
- Q8: [future_predictions.py](future_predictions.py) ingests recent actual matches, extends ratings and publishes forecasts. Its entry point is `scripts/predict_future_matches.py`.
- Shared provenance: [artifact_store.py](artifact_store.py) resolves registered relocations without erasing original fingerprints.

## Relating code to evidence

Identify the question and adopted scope in the [research overview](../研究/README.en.md), find its entry/configuration in [scripts](../scripts/README.en.md), then follow imports. Use the [material index, Chinese](../文档/05_团队协作/论文与汇报支撑材料索引.md) for reported numbers; examples and early defaults are not adopted results.

Current source may postdate an archived execution. Exact historical replay uses the run's bound source snapshot and protocol. [AGENTS.md](../AGENTS.md) requires recording substantive edits, failures and adoption decisions.
