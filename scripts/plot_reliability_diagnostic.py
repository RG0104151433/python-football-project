"""Static presentation figure: matched simulation diagnostic, not football data."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
from pathlib import Path
import sys
import csv

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt,font_manager
from src.reliability.design import sha
from src.reliability.experiment import write_json


def main(refresh_layout=False):
    source="outputs/logs/reliability/iteration-20261028/failure_localization_metrics.csv"
    data=list(csv.DictReader((ROOT/source).open(encoding="utf-8-sig",newline="")))
    names=["fitted_margin_fitted_dependence","true_margin_fitted_dependence","fitted_margin_true_dependence","true_margin_true_dependence"]
    labels=["p estimated\ndependence\nestimated","p known\ndependence\nestimated","p estimated\ndependence\nknown","p known\ndependence\nknown"]
    folder=ROOT/"outputs/figures/reliability/method-iterations-20261028"
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/"C09_diagnostic.png").exists():
        if not refresh_layout:raise RuntimeError("Preserve original figure")
        prior=__import__("json").loads((ROOT/"outputs/logs/reliability/implementation-20261028/diagnostic_figure.json").read_text(encoding="utf-8"))
        if prior["source_sha256"]!=sha(ROOT/source):raise RuntimeError("Layout refresh must not replace a changed statistical version")
    fig,axes=plt.subplots(1,2,figsize=(12,6.75),dpi=160)
    colors=["#286A94","#DB8744"]
    for c,color in zip((1,2),colors):
        vals=[next(r for r in data if r["family"]=="CONDITIONAL" and r["variant"]==n and int(r["multiplier"])==c) for n in names]
        x=np.arange(4)+(c-1.5)*.34
        for ax,field in zip(axes,("coverage","mean_span_fraction")):
            y=[float(r[field]) for r in vals]
            ax.bar(x,y,width=.32,color=color,label=f"Critical multiplier {c}")
            if field=="coverage":
                for xi,yi,r in zip(x,y,vals):ax.text(xi,yi+.02,f"{r['covered']}/10",ha="center",fontsize=9)
    axes[0].axhline(.95,color="#555555",ls="--",lw=1,label="Nominal 95%")
    axes[0].set_title("Joint coverage of all 71 conditional rates",fontsize=12)
    axes[1].set_title("Average interval width / logical range",fontsize=12)
    for ax in axes:
        ax.set_xticks(np.arange(4),labels,fontsize=8)
        ax.set_ylim(0,1.13);ax.set_yticks(np.linspace(0,1,6));ax.grid(axis="y",alpha=.18);ax.set_axisbelow(True)
        ax.spines[["top","right"]].set_visible(False)
    axes[0].legend(loc="upper left",fontsize=8,frameon=False)
    fig.suptitle("Why the fitted model failed at full scale: C09 truth-switch diagnostic",fontsize=15,y=.96)
    fig.text(.5,.035,"10 reused simulated outer datasets on the fixed 24,917-fixture design. Known truths are unavailable in real data.\nDiagnostic only: not independent validation, not a confidence claim about actual football.",ha="center",fontsize=10,color="#444444")
    fig.subplots_adjust(left=.06,right=.98,top=.86,bottom=.23,wspace=.17)
    png=folder/"C09_diagnostic.png";svg=folder/"C09_diagnostic.svg"
    fig.savefig(png,metadata={"Software":"python-football-project; source hashes in figure manifest"})
    fig.savefig(svg,metadata={"Date":None});plt.close(fig)
    font=Path(font_manager.findfont("DejaVu Sans"))
    write_json(ROOT/"outputs/logs/reliability/implementation-20261028/diagnostic_figure.json",dict(
        source=source,source_sha256=sha(ROOT/source),script_sha256=sha(Path(__file__)),
        matplotlib=matplotlib.__version__,font_sha256=sha(font),actual_football_results=False,
        outputs={p.relative_to(ROOT).as_posix():sha(p) for p in (png,svg)}))
    print(png.relative_to(ROOT).as_posix())


if __name__=="__main__":
    parser=__import__("argparse").ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-layout",action="store_true")
    main(parser.parse_args().refresh_layout)
