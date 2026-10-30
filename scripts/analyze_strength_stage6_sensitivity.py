"""Run declared stage6 step3 sensitivity fits, not formal inference."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_stage6_sensitivity import run
from src.data_contract import write_json,fingerprint
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='config/strength_stage6_sensitivity.json');a=p.parse_args()
    try:run(a.config)
    except Exception as error:
        write_json(ROOT/'outputs/logs/strength_stage6'/('sensitivity-failure-'+fingerprint(repr(error))[:20]+'.json'),dict(error=repr(error),completed=False))
        raise
