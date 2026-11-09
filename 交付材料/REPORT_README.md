# Final course report

**审稿排版优化（R20261109-02）：** 封面保留；已统一关键词、三级目录、公式引用/正负号、图表、声明结构、文献链接断行与美式正文拼写。当前仍25页，研究数值不变；详见 `paper/editorial_review_20261109.md`。正式源/PDF与提交包已同步，旧记录保留历史。


**手动修订同步（R20261109-01）：** 已保留用户对当前main.tex摘要的三处英文修改，重新编译25页论文并同步正式PDF、现有main.pdf副本及提交报告源/PDF。旧版存档不覆盖；研究结果未变。


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
