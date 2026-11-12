# Final English manuscript source

[中文](README.md) | **English**


This is the current editable manuscript, not an unfinished language draft. The final report has 25 pages, seven figures, five tables, 12 displayed equations and 18 references. References form Section 5; Declarations follow separately. The owner has confirmed both submission channels.

## Files and compilation

- [main.tex](main.tex) loads `sections/`, [cover.tex](cover.tex) and [references.bib](references.bib).
- Shared figures, the study-design diagram and generated table fragments remain in `../figures/`.
- Read the delivered [final PDF](../final_paper.pdf) and [current manifest](../final_paper_manifest.json).
- The cover keeps 睿信2526班 in Chinese as requested. It has no page number; the abstract and contents use i–ii, followed by 22 body pages.

Set this directory's `main.tex` as the root document, use XeLaTeX with BibTeX, and write compilation products to `build/`. Do not compile `../main.tex` as the current manuscript. Keep this directory with its parent so shared figure paths resolve. Generated PDFs and logs do not certify independent member review.

From the repository root, check the selected manuscript's citations with:

```powershell
python paper/check_citations.py --paper-dir paper/language_revision_20261107 --strict
```

Without `--paper-dir`, the checker targets the older parent version.

## Language and evidence rules

Use formal academic English with consistent American spelling, clear operations and justified claims. Preserve mathematical assumptions, denominators, all 12 equations, citations, real failures and limitations. Do not turn a limited check into universal correctness or a proposed improvement into a measured gain. Editing language does not retrain the model.

Earlier language diffs, CCFA-based revision reports and course-requirement checks remain historical records. Their page counts and manifests apply to their own dates, not the current PDF. CCFA-Skills informed editing; it does not certify CCF-A publication quality.

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/paper/language_revision_20261107/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
