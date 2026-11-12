# geo-prep-v2: revised geographic preparation package

[中文](README.zh-CN.md) | **English**


Historical package created on 26 October 2026 after the v1 review required targeted revision. It is not the final study specification; use `config/regions_study.json` from the repository root for adopted analysis.

## Contents and revisions

- M49 page/overview snapshots retain the original source hashes. Shared-source relocation may apply; use the registered resolver.
- `team_geography_seed.csv` maps 215 teams to M49 carriers.
- `region_dictionary.csv` separates original and project hierarchies, fills 24 raw parent codes and adds project level/parent fields.
- `carrier_model.csv` distinguishes modern states, territories, UK constituent associations, historical carriers, special statistical areas and unions. It separates entity facts, project conventions and assumptions.
- `sources.csv` registers six sources with supported claims and local hashes.
- `exceptions.csv` has ten cases, not the seven previously stated in one log entry.
- `candidate_specs.csv` contains 19 candidates: A×6, B×4, C×7 and D×2. The D candidates describe distributions, not contrasts.
- The original v1 script is retained in `code_snapshots/`.

Zero-cell analysis distinguishes known categories from UNKNOWN: the earlier six empty large-region cells were all UNKNOWN; this package records 44 known and 118 unknown zeros across its fuller analysis. Candidate reference support is evaluated per arm/stratum. Modern M49 labels are carriers, not official day-by-day historical membership evidence.

## Historical reproduction

```powershell
python scripts/prepare_region_mapping.py prepare --package data/external/geography_preparation/geo-prep-v2 --tag r1
python scripts/prepare_region_mapping.py prepare --package data/external/geography_preparation/geo-prep-v2 --tag r2
python scripts/prepare_region_mapping.py finalize outputs/logs/regions/<run_dir>
```

Replace the placeholder with the actual run directory. Preparation snapshots its script; finalize updates the completed manifest. The original pending classifications and candidate choices describe v2's handoff, not unresolved decisions in the completed study. Consult the [current Q3 guide](../../../../研究/03_地域差异/README.en.md).

Original preserved file: [README.md](README.md). This reading edition does not replace its registered evidence.
