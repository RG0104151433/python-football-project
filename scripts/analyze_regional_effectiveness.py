"""Q7 first three steps: descriptive evaluation, no rating/model retraining."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.regional_effectiveness import run

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='config/regional_effectiveness.json')
    run(p.parse_args().config)
