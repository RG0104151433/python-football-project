"""Build outcome-free grouping protection; preserve its data and source hashes."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from src.reliability.experiment import actual_design,write_json
from src.reliability.guard import grouped_time_guard
from src.reliability.design import sha

if __name__=="__main__":
    out=ROOT/"outputs/logs/reliability/joint-20261028"
    if (out/"guard.npz").exists():raise RuntimeError("Preserve prior guard version")
    d,binding=actual_design(ROOT);guard,meta=grouped_time_guard(d)
    np.savez_compressed(out/"guard.npz",guard=guard)
    write_json(out/"guard_manifest.json",dict(metadata=meta,design_binding=binding,
        guard_sha256=sha(out/"guard.npz"),source_sha256=sha(ROOT/"src/reliability/guard.py"),
        script_sha256=sha(Path(__file__)),scope="score protection, not a proved upper bound on actual covariance"))
    print(dict(targets=len(guard),**meta))
