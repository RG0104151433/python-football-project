"""Two-route development/scale checks; does not publish football intervals."""
import argparse
import os
from pathlib import Path
import sys

# Keep nested numerical libraries from silently oversubscribing this machine.
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.reliability.experiment import graph_experiment,simulation


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["small-graph","full-graph","small-baseline","small-development","full-development"],required=True)
    parser.add_argument("--config",default="config/reliability_development_v2.json")
    args=parser.parse_args()
    if args.stage.endswith("graph"):
        graph_experiment(ROOT,args.config,actual=args.stage.startswith("full"))
    else:
        simulation(ROOT,args.config,actual=args.stage.startswith("full"),baseline=args.stage.endswith("baseline"))
