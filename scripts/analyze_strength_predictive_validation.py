"""Actual annual past-only comparison of background, strength and joint models."""
from pathlib import Path
import os,sys
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_predictive_validation import run
if __name__=='__main__':run()
