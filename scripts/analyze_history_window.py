"""Q6 annual outcome, rating-memory and prefix-stable latent simulation entry."""
from pathlib import Path
import argparse,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.history_window.outcome import run

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['outcome','rating','latent','all'],default='outcome')
    p.add_argument('--config');p.add_argument('--resume',action='store_true')
    p.add_argument('--mode',choices=['plan','development','full'],default='full')
    p.add_argument('--plan-only',action='store_true');a=p.parse_args()
    if a.stage=='outcome':run(a.config or 'config/history_window_analysis.json',a.resume,a.plan_only)
    else:
        from src.history_window.experiments import run as run_rating
        run_rating(a.stage,'plan' if a.plan_only else a.mode,a.config or 'config/history_window_rating.json')
