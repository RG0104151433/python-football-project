"""Read-only SHA protection check for the two earlier research questions."""
import hashlib
import json
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").is_file())
state = json.loads((ROOT / "研究/pipeline_state.json").read_text(encoding="utf-8"))
result = {}
for question in ("question_1", "question_2"):
    relative = state[question]["run_manifest"]
    manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    n = 0
    for section in ("inputs", "outputs", "code_hashes"):
        for path, expected in manifest[section].items():
            actual_path = (ROOT / path.replace("\\", "/")).resolve()
            assert actual_path.is_relative_to(ROOT)
            assert hashlib.sha256(actual_path.read_bytes()).hexdigest() == expected, path
            n += 1
    result[question] = dict(run_manifest=relative, fingerprints=n, outputs=len(manifest["outputs"]))
out = Path(__file__).parent / "previous_questions.json"
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result))
