"""Run Q6 steps1-3 feasibility, keeping the existing Q5 artifacts unchanged."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.history_window.pilot import execute

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default='config/history_window.json')
    execute(parser.parse_args().config)
