"""Move identical M49 pages to one shared location; preserve old hash records."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data/external/geography_sources/m49-20261026"
EXPECTED = {
    "m49_page.html": "4d5cabcb10ad9ef184553b5e64c0a34ba8deeb20dab2e02cd0be3599b93bb01d",
    "m49_overview.html": "b9048114f6e7f2abda83bf03d4263c9d7cd1bd7230e3d0461025ee7839a7a1fb",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    files = []
    for base in [ROOT / "data/external", ROOT / "outputs/logs"]:
        for name, expected in EXPECTED.items():
            for path in base.rglob(name):
                if path.is_symlink():
                    raise ValueError(f"Symbolic link is not a deletion candidate: {path}")
                path = path.resolve()
                if path.parent == DEST.resolve():
                    continue
                if not path.is_relative_to(ROOT) or path.is_symlink() or sha(path) != expected:
                    raise ValueError(f"Unexpected path/content, refusing deletion: {path}")
                files.append(path)
    index_path = DEST / "relocations.json"
    data = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {
        "schema_version": "shared-m49-v1", "decision_log_id": "R20261026-16", "aliases": {},
        "note": "Old manifests retain original bytes and hashes; current resolver follows these exact path relocations."
    }
    for path in files:
        data["aliases"][path.relative_to(ROOT).as_posix()] = {
            "canonical_path": (DEST / path.name).relative_to(ROOT).as_posix(),
            "sha256": EXPECTED[path.name], "bytes": path.stat().st_size,
        }
    total = sum(p.stat().st_size for p in files)
    if args.apply:
        DEST.mkdir(parents=True, exist_ok=True)
        for name, expected in EXPECTED.items():
            target = DEST / name
            if not target.exists():
                source = next(p for p in files if p.name == name)
                shutil.copyfile(source, target)
            if sha(target) != expected:
                raise ValueError(f"Canonical source changed: {target}")
        # Persist all redirects before removing any byte-identical old path.
        index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8", newline="\n")
        for path in files:
            if not path.is_relative_to(ROOT) or path == DEST / path.name or sha(path) != EXPECTED[path.name]:
                raise ValueError(f"Pre-delete verification failed: {path}")
            path.unlink()  # Exact regular files only; no recursive deletion.
    print(json.dumps({"applied":args.apply, "old_paths":len(files), "old_bytes":total,
                      "canonical_files":2, "canonical_directory":DEST.relative_to(ROOT).as_posix(),
                      "aliases_total":len(data["aliases"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
