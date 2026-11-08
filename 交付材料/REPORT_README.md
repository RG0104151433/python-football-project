# Final course report

Open FootballProject/paper/final_paper.pdf to read the final 25-page paper. Author class is preserved in Chinese as 睿信2526班.

All three archives share the FootballProject/ root and may be extracted into the same parent directory. Report.zip is also independently usable for reading or compiling the paper.

paper/language_revision_20261107/ contains main.tex, six section files, and references.bib. paper/figures/ contains shared PDF figures and TeX figure/table inputs. Their relative layout preserves the manuscript's ../figures references.

To rebuild, use TeX Live with XeLaTeX, latexmk and BibTeX. FandolSong-Regular.otf for the Chinese class line is distributed with TeX Live. Do not compile sections individually.

From FootballProject/paper/language_revision_20261107/ in PowerShell:

    $reportSource = (Get-Location).Path
    $env:BIBINPUTS = "$reportSource;$reportSource/build;"
    latexmk -xelatex -interaction=nonstopmode -outdir=build main.tex

The regenerated PDF is build/main.pdf. The supplied export remains ../final_paper.pdf. Including the LaTeX sources is our reproducibility choice, not an additional source-delivery requirement explicitly stated by the course.


Cover update R20261108-08: the separate unnumbered cover retains only the provided school mark, paper title, class, names and IDs. cover.tex and ../figures/bit_school_header.jpeg are required and included. The JPEG is extracted unchanged from the owner-provided Word reference. Abstract and contents use i/ii; body pages remain 1–22. Earlier report PDF/source are retained in the main repository's paper/archive/pre_cover_20261108/; that historical copy is not the current submission.
