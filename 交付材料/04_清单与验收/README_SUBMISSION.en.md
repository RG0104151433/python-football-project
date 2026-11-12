# English reading edition

[中文](README_SUBMISSION.zh-CN.md) | **English**


The original document is preserved unchanged. This reading copy retains its original scope; see the source manifest or delivery record for the actual files included.

# Course submission: start here

Project: Home-Win Prediction in International Football: Team Strength, Historical Information, and Regional Variation.

## Open the files

Extract Code.zip and Data.zip into the same parent folder and merge FootballProject/. Extract Report.zip there too if you want the manuscript source. Read paper/final_paper.pdf for the report. Code.zip contains no raw or derived experimental datasets; python123 receives only report and code, while the email uses the three separate archives.

## Quick check

From FootballProject/ run:

    python quick_check.py

This uses only the standard library. Expected: 7/7. It reads adopted records and summaries without rerunning models or checking real future outcomes.

## Python environment

The recorded environment is CPython 3.14.8 on Windows x64. Create your own environment:

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements-core.txt
    .venv\Scripts\python.exe -m pip check

The minimal runtime includes NumPy, SciPy, Matplotlib, psutil, threadpoolctl and pytest. requirements.txt is the original full machine freeze; its optional notebook and plotting packages are not required for this quick check. The minimal ranges are not an identical pinned reproduction environment. No GPU is required.

## What can be checked from these attachments

    python -m src.snapshot --verify --config config.json
    python -m src.audit --config config.json
    python -m pytest -q tests/test_data_rules.py tests/test_strength_baseline.py tests/test_strength_joint.py --basetemp .submission_test_tmp

The first two commands inspect the included raw snapshot; audit writes a new diagnostic run. The unchanged raw archive contains known conflicts, so audit intentionally returns exit code 1 with review_needed and 40 ERROR records. These were handled by the recorded preparation rules; this is not an installation failure or a claim that the cleaned study contains those conflicts. The selected tests exercise core data rules and model calculations. Stage entry points and adopted configurations are indexed by scripts/README.md and 研究/pipeline_state.json.

## Compact-data limits

The data attachment keeps original inputs, paper-bound evidence and final summaries, but omits most simulated worlds, historical checkpoints and bulky diagnostics. Strict identity/archive replay and some long-running historical commands require additional files from the full repository or regeneration. A reference in an archived manifest is not a promise that every historical dependency is bundled. See DATA_PACKAGE_README.md and the explicit selection inventory. Do not edit hash checks to hide missing inputs.

The complete scientific code and configurations remain included. Read the stage guide before running historical scripts: not every entry safely treats --help as a read-only operation. Use python -m src.clean rather than directly executing src/clean.py.

## Evidence and boundaries

paper/SUPPORTING_RESULTS.md maps the reported results to evidence. The 70.01% headline is historical binary home-win/non-home-win accuracy, not three-way or future-fixture accuracy. The current forecasts have no verified actual results in the submission. The separate delivery verification records exactly what was run; it is not a fresh-machine or independent member review certificate.

Original preserved file: [README_SUBMISSION.md](README_SUBMISSION.md). This reading edition does not replace its registered evidence.
