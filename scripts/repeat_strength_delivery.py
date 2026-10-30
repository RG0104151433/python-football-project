"""Repeat final calibration/interface run; raw scorer has separate archive proof."""
from pathlib import Path
import json
import os
import subprocess
import sys
import hashlib
ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out=ROOT/'outputs/logs/strength/repair-20261029'
    folder=ROOT/json.loads((out/'delivery_normal.json').read_text())['directory']
    m=json.loads((folder/'manifest.json').read_text());before={name:sha(folder/name) for name in [*m['outputs'],'manifest.json']}
    (out/'delivery_repeat_before.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8')
    with (out/'delivery_repeat_execution.txt').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,'-X','utf8','-m','src.strength.delivery'],cwd=ROOT,
            env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),stdout=log,stderr=subprocess.STDOUT)
    changed=[name for name,h in before.items() if sha(folder/name)!=h]
    after=json.loads((out/'delivery_normal.json').read_text())['directory']
    proof=dict(passed=result.returncode==0 and not changed and after==folder.relative_to(ROOT).as_posix(),
        exit_code=result.returncode,files_checked=len(before),changed=changed,same_version=after==folder.relative_to(ROOT).as_posix(),
        source_directory=folder.relative_to(ROOT).as_posix(),raw_replay='outputs/logs/strength/repair-20261029/replay_jump_full.json')
    (out/'delivery_reproducibility.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8');print(json.dumps(proof),flush=True)
    if not proof['passed']:raise SystemExit(1)


if __name__=='__main__':main()
