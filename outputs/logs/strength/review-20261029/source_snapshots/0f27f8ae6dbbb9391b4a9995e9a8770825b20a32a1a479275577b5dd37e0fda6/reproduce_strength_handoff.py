"""Repeat the complete normal run, preserving previous core-file hash evidence."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.data_contract import file_hash,write_json


def main(folder):
    report=json.loads((folder/"report.json").read_text(encoding="utf-8"))
    directories=[folder,*[ROOT/p for p in report["candidate_directories"].values()]]
    before={}
    for directory in directories:
        m=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
        for name,digest in m["outputs"].items():
            path=directory/name
            if file_hash(path)!=digest:raise ValueError("Pre-repeat core mismatch")
            before[path.relative_to(ROOT).as_posix()]=digest
        before[(directory/"manifest.json").relative_to(ROOT).as_posix()]=file_hash(directory/"manifest.json")
    out=ROOT/"outputs/logs/strength/review-20261029"
    write_json(out/"repeat_before.json",before)
    env=dict(os.environ,OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1")
    with (out/"repeat_execution.txt").open("w",encoding="utf-8") as stream:
        result=subprocess.run([sys.executable,"-X","utf8","-m","src.strength.handoff"],cwd=ROOT,env=env,
            stdout=stream,stderr=subprocess.STDOUT)
    changed=[name for name,digest in before.items() if file_hash(ROOT/name)!=digest]
    text=(out/"repeat_execution.txt").read_text(encoding="utf-8")
    same_id=("HANDOFF "+folder.relative_to(ROOT).as_posix()) in text
    proof=dict(passed=result.returncode==0 and not changed and same_id,exit_code=result.returncode,
        files_checked=len(before),changed=changed,same_content_addressed_handoff=same_id,
        directory=folder.relative_to(ROOT).as_posix(),runner_sha=file_hash(Path(__file__)),
        excludes="execution_timing.json is nondeterministic and excluded by design",human_review="not_performed")
    write_json(out/"reproducibility.json",proof);print(json.dumps(proof),flush=True)
    if not proof["passed"]:raise SystemExit(1)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("directory");main(ROOT/p.parse_args().directory)
