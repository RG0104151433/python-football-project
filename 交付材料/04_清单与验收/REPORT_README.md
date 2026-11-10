# Report and LaTeX source

Open FootballProject/paper/final_paper.pdf. The current paper has 25 pages, including the cover, abstract, contents, main text and final declarations. Class remains 睿信2526班 as requested by the project owner.

References is numbered Section 5, followed by unnumbered Declarations. Scientific text, formulas, empirical results and cover content were not changed for this delivery revision.

The source entry is paper/language_revision_20261107/main.tex. Its sections/ folder includes the separate declarations.tex. Preserve the adjacent paper/figures/ directory because the source uses ../figures paths.

With TeX Live, XeLaTeX, latexmk and BibTeX installed, run from paper/language_revision_20261107/:

    latexmk -xelatex -interaction=nonstopmode -outdir=build main.tex

FandolSong-Regular.otf is supplied by TeX Live. Compile main.tex, not the individual section files. Report.zip can be used independently or merged with the code and data archives under FootballProject/.
