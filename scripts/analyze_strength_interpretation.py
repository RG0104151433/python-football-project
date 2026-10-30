"""Q5 stages 4/5 supplementary interpretation; does not run stage6 inference."""
from pathlib import Path
import argparse
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_interpretation import run
from src.data_contract import write_json,fingerprint

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',default='config/strength_interpretation.json')
    args=parser.parse_args()
    try:run(args.config)
    except Exception as error:
        write_json(ROOT/'outputs/logs/strength_interpretation'/('failure-'+fingerprint(repr(error))[:20]+'.json'),
                   dict(error=repr(error),completed=False,config=args.config))
        raise
