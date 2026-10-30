"""Precision-supported scope, kept distinct from original54 nonadmission."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_inference_report import run
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['calibrate','apply'],required=True)
    run(p.parse_args().phase)
