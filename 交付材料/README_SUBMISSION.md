# Course submission: code and reproduction

Project: Home-Win Prediction in International Football: Team Strength, Historical Information, and Regional Variation.

## Combine the archives

Extract Code.zip and Data.zip into the SAME parent directory. Both contain a FootballProject/ directory; merge them. Do not put Data.zip inside src/ or nest one FootballProject directory inside another. Report.zip is a separate report attachment.

The combined root must contain quick_check.py, config.json, src/, scripts/, config/, data/, outputs/, and 研究/.

Code.zip intentionally contains no experimental data/ or outputs/ payloads. Submit only the report and code on python123; send all three separate archives by email as required by the course.

## Quick, read-only check (no dependencies required)

Use Python 3.14 (the recorded environment is 3.14.8, Windows x64). In the merged FootballProject directory:

    python quick_check.py

Expected: seven checks pass. This reads archived assets; it does not rerun model training, establish future accuracy, or replace independent reproduction.

## Environment for calculations

Create a new local environment; do not copy another machine's .venv:

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe -m pip check

The full requirements.txt is the recorded machine freeze. requirements-core.txt is an alternative minimal dependency range, not an identical pinned environment; differences must be recorded and checked. No GPU is required. Installing packages needs network access unless suitable wheels are already cached.

## Reproduce an analysis

Start with scripts/README.md, then the selected stage's reproduction instructions in 研究/. Use 研究/pipeline_state.json for adopted versions. Do not choose a file merely because its name has the largest version number. Some historical scripts start work even if passed --help, so read the script guide first.

For module entry points, use python -m src.clean from the project root rather than running src/clean.py directly. Full chronological ratings and simulation experiments can take substantially longer than the quick check. Run expensive experiments in a copy if you need to preserve issued results unchanged.

paper/SUPPORTING_RESULTS.md identifies reported results, settings, and adopted inputs. Code includes historical/rejected implementations for transparency; their presence does not mean that they generated the current paper. Regenerable per-job/checkpoint caches and unrelated development outputs are excluded from the submission data selection. Archived manifests can mention historical files outside the selected package; these are not silently relabelled as current results.

## Delivery checks

The separate verification record distributed with the archives states exactly which checks were actually run. It is not a certificate of independent group-member review or a fresh installation on another computer. The package contains source code and configuration, not a preinstalled Python environment. Source-data licensing and attribution remain with their corresponding data records; the entire project is not claimed to have a new blanket license.
