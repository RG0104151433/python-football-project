"""Frozen independent standard and full-history two-route comparison."""
from pathlib import Path
import argparse,os,sys
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_inference.comparison import run
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=['truth','calibration','validation','summarize','all'],required=True)
    p.add_argument('--workers',type=int);p.add_argument('--scenario')
    args=p.parse_args();run(args.phase,args.workers,args.scenario)
