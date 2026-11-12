# geo-prep-v3: input binding and handoff revisions

[中文](README.zh-CN.md) | **English**


Historical package created on 26 October 2026 after v2. The classification dictionary, carriers, exceptions and candidate specifications retain their v2 content. The final comparison list is separately fixed in `config/regions_study.json`.

The two M49 HTML files now live in the [shared source directory](../../geography_sources/m49-20261026/README.en.md). Original CSVs, manifests and hashes remain unchanged; `relocations.json` and the artifact resolver locate old paths. A `sources/` path in the original record does not imply a second physical copy.

## P1–P5 changes

1. Snapshot 13 inputs at run start: six package inputs, two M49 pages and match/identity inputs. Calculations read these snapshots.
2. Add team contributions per candidate, arm, period, type, role and team. Zero denominators stay unavailable; contributions reconcile to arm counts.
3. Accept only literal `true`/`false`, without trimming or case conversion; selection and validation share the rule.
4. Replay uses archived code and inputs, writes a new directory and compares core CSVs, rather than using current `scripts/` code.
5. Failures write `failure_report.json` and exit 2, without publishing a successful manifest. Code snapshots remain available.

The v2 script is retained in `code_snapshots/`. Run from the repository root:

```powershell
python scripts/prepare_region_mapping.py prepare --tag r1
python scripts/prepare_region_mapping.py prepare --tag r2
python scripts/prepare_region_mapping.py replay --run outputs/logs/regions/<r1>
python scripts/prepare_region_mapping.py finalize outputs/logs/regions/<run>
```

Use actual run directories. The package is completed preparation evidence, not a requirement to restart geographic classification whenever the study is reproduced.

Original preserved file: [README.md](README.md). This reading edition does not replace its registered evidence.
