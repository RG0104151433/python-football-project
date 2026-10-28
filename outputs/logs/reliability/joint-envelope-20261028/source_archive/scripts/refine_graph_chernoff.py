"""Graph route G4: preserve distribution-free conditional theory."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
from pathlib import Path
import sys
import json
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.reliability.experiment import actual_design,write_json,write_csv
from src.reliability.graph_exact import refine_all
from src.reliability.design import sha

if __name__=="__main__":
    out=ROOT/"outputs/logs/reliability/joint-20261028"
    if (out/"graph_chernoff.json").exists():raise RuntimeError("Preserve original G4 result")
    d,_=actual_design(ROOT)
    path="outputs/logs/reliability/refined-graph-20261028T010916841071Z/graph_constants.json"
    base=json.loads((ROOT/path).read_text(encoding="utf-8-sig"));started=time.process_time()
    rows=refine_all(d,base);write_csv(out/"graph_chernoff.csv",rows)
    write_json(out/"graph_chernoff.json",dict(n=d.n,targets=len(d.targets),ranges=5,rows=len(rows),
        source=path,source_sha256=sha(ROOT/path),code_sha256=sha(ROOT/"src/reliability/graph_exact.py"),
        script_sha256=sha(Path(__file__)),CPU_seconds=time.process_time()-started,
        graph_independence_assumption_not_certified=True,mathematical_guarantee="same graph assumption; Bernoulli supremumMGF andHolder; no outcome-based choice"))
    print(dict(rows=len(rows),CPU_seconds=time.process_time()-started))
