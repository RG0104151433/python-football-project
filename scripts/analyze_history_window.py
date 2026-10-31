"""Q6 stage4 entry; rating/latent stages remain in the reviewed design."""
from pathlib import Path
import argparse,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.history_window.outcome import run

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['outcome'],default='outcome')
    p.add_argument('--config',default='config/history_window_analysis.json');p.add_argument('--resume',action='store_true')
    p.add_argument('--plan-only',action='store_true');a=p.parse_args();run(a.config,a.resume,a.plan_only)
