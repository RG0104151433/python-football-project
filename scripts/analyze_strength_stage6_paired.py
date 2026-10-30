"""Complete five subset M0 refits and paired changes, or audit that output."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_stage6_paired import run,audit
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',action='store_true');args=p.parse_args()
    audit() if args.audit else run()
