"""Prepare stage6 target/reference registry and score marginal inputs only."""
from pathlib import Path
import argparse
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_stage6_prepare import run
from src.data_contract import fingerprint,write_json

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='config/strength_stage6_preparation.json');a=p.parse_args()
    try:run(a.config)
    except Exception as error:
        write_json(ROOT/'outputs/logs/strength_stage6'/('failure-'+fingerprint(repr(error))[:20]+'.json'),dict(error=repr(error),completed=False,config=a.config))
        raise
