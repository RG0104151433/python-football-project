# Q1 same-version handoff — 25 October 2026, historical

[中文](README.zh-CN.md) | **English**


The owner deferred further country-specific evidence collection and authorized a rerun under the existing scope, recorded before execution as R20261025-04. Selection, statistical code, configuration, membership rules and unresolved dispositions were unchanged.

The [run manifest](../confirmed-eras-20261025T002437005064Z-f19d8184/run_manifest.json) records the historical 24,279-match provisional analysis. A new run ID did not create a new analysis identity. Twenty-two registered products were verified, and 19 core CSV/dictionary/figure artifacts were byte-identical to the previous same-version run.

[independent_audit.json](independent_audit.json) contains 630 independent recalculation checks without calling the production counting/standardization functions. It checked periods, years, types, references, rates, differences, fields, keys and serialization. This validates implementation under the stated scope, not the underlying historical facts or inference theory.

[display_data.json](display_data.json) binds the historical presentation data; [supplemental_checks.json](supplemental_checks.json) adds 208 weight-curve rows and crossover checks. Those checks are separate from the 630-count audit.

The old main reference was 38.2223% friendlies; standardized later-period differences were +0.3083 and +1.6026 percentage points. These are historical numbers, superseded by the later adopted sample. Read the [current Q1 guide](../../../../研究/01_年代变化/README.en.md) and [reproduction instructions, Chinese](../../../../研究/01_年代变化/本地运行与复现.md) before reuse.

No new full pytest, Q2 analysis, Elo calculation or formal uncertainty inference was run in this handoff. Changes observed in batch04 evidence were recorded, not authored or fully accepted by this rerun.

Original preserved file: [README.md](README.md). This reading edition does not replace its registered evidence.
