"""Generate the real-result Q5 HTML, scientific figures and paper handoff."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_q5_closeout import run
if __name__=='__main__':run()
