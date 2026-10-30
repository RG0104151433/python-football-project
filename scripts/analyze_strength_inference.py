"""Two-route development: interfaces, 54-target diagnostic or full-history pilot."""
from pathlib import Path
import argparse
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from src.strength_inference.contract import load
from src.strength_inference.experiment import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/strength_inference.json")
    parser.add_argument("--stage", choices=["interface", "diagnostic", "pilot", "truth", "validate", "apply"], required=True)
    args = parser.parse_args(); run(load(args.config), args.stage)
