"""Repeat core analysis, compare bytes, restore adopted full-sensitivity pointer."""
from pathlib import Path
import json
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from src.data_contract import file_hash, write_json
from src.strength_joint.contract import load
from analyze_strength_joint import analyze


def run():
    log = ROOT / "outputs/logs/strength_joint"
    original = json.loads((log / "analysis_pointer.json").read_text())
    source = ROOT / original["directory"]
    cfg, rows, targets, geography, inputs = load()
    begin = time.perf_counter()
    replay = analyze(cfg, rows, targets, geography, inputs, run_sensitivity=False)
    names = ["model_metrics.csv", "coefficients.csv", "joint_predictions.csv", "contrasts.csv", "strength_changes.csv", "support.csv", "calibration.csv",
             "models.json", "validation.json", "display_data.json", "data_dictionary.md", "source_snapshot.zip"]
    records = {name: dict(original_sha256=file_hash(source / name), replay_sha256=file_hash(replay / name),
                         identical=(source / name).read_bytes() == (replay / name).read_bytes()) for name in names}
    result = dict(passed=all(r["identical"] for r in records.values()), original=original["directory"], replay=replay.relative_to(ROOT).as_posix(),
        compared_files=records, identical_core_files=sum(r["identical"] for r in records.values()),
        sensitivity_refits_repeated=False, scope="nine models/all32 full and overlap contrasts/small feedback; original four sensitivity variants audited separately, not rerun",
        runner_sha256=file_hash(Path(__file__)), seconds=time.perf_counter() - begin)
    write_json(log / "reproducibility.json", result)
    write_json(log / "analysis_pointer.json", original)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
