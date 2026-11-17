# Classroom presentation: adopted V5

[中文](README.md) | **English**


The current deck has 14 screens. The owner confirmed both research-submission channels; As of 17 November 2026, 09:19 Beijing time, 44 results are verified and eight fixtures remain pending. Main binary accuracy is 30/43 (69.8%); auxiliary three-way accuracy is 30/44 (68.2%). A timed rehearsal remains pending.

## Detailed redesign plan — not yet implemented

[Page-by-page plan, Chinese](HTML展示逐页内容规划_20261117.md) arranges 36 main pages and eight Q&A pages around the agreed seven-part explanation standard. It covers objectives, input selection, method choices and optimization, execution, outputs, interpretation and transitions. These are proposed content units, not a page/time cap or completed HTML. Current V5 and its script remain in use; the plan labels evidence to reuse, details to extract, illustrations and unimplemented proposals.

## Use these files

- [index.html](index.html): open offline in Chrome or Edge. Keep [repository_architecture.html](repository_architecture.html) beside it.
- [Speaking script](PRESENTATION_SCRIPT_EN.md): about 557 spoken English words. Read English quotation blocks; Chinese action cues are not spoken. Planned total including actions is 8:25, with 1:35 spare; timing has not been rehearsed.
- [Results checklist](RESULTS_DAY_CHECKLIST.md) and [CSV template](results_template.csv): prepare verified results before presenting, without changing archived probabilities.
- The local classroom copy is in `交付材料/03_课堂展示/`, with the same HTML, structure diagram, template, script and rehearsal instructions.

## Operate and maintain

Use Next/Back or arrow keys between screens and the page's own controls for figures. Speaker notes are visible on the projector, so keep them closed during the talk. The short script uses Europe, Brazil/China and one fixture rather than exploring every item.

From the full repository, `python presentation/build.py` publishes adopted V5. It reads frozen V4 and adds the V5 extension. Editing only the script requires no HTML rebuild. V4 remains frozen in `versions/v4_20261110/`; the adopted copy is in `versions/v5_20261110/`.

Check [current_version.json](current_version.json), [hover verification](v5_verification.json) and [results-interface verification](v5_results_handoff_verification.json) for their recorded scope. They are actual prior checks, not proof of a timed rehearsal.

Sources and rights are in [VISUAL_SOURCES.md](VISUAL_SOURCES.md). The current repository diagram is native SVG; the previous Archify output is historical. The [old ten-page handout](archive/initial_10_screen/handout.pdf) does not represent V5. Old decks, acquisition records and receipts are indexed in the [archive](archive/README.en.md). Build and verification entry points retain their paths.

## Historical notes

[Preserved original-language README, derivations and version history](../文档/04_整理记录/README历史快照_20261112/presentation/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.

## Verified morning results

As of 17 November 2026, 09:19 Beijing time, 44 results are verified and eight fixtures remain pending. Main binary accuracy is 30/43 (69.8%); auxiliary three-way accuracy is 30/44 (68.2%). Open screen 10 directly: verified scores are embedded for offline use. [Filled CSV](results_checked_20261117.csv). Restore morning results resets any local edits. `build_checked_results.py` checks the saved UEFA factual rows and produces the comparison table and payload; `build_v5.py` embeds that payload. The frozen forecasts and V4 remain unchanged.
