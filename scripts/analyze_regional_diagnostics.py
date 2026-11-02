"""Q7 step4 descriptive composition diagnostics; no refitting."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.regional_diagnostics import run

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='config/regional_effectiveness_diagnostics.json')
    run(p.parse_args().config)
