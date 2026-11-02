"""Run Q7 finite-history stability checks; no refitting or formal intervals."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.regional_stability import run

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='config/regional_effectiveness_stability.json')
    run(parser.parse_args().config)
