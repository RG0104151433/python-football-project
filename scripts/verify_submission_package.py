"""Verify hashes and safely extract the three locally prepared course archives.

This checks delivery integrity, not scientific validity. It never uploads files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "交付材料"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", choices=["Report", "Code", "Data"],
                        default=["Report", "Code", "Data"])
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((OUT / "04_清单与验收/PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    destination = (OUT / "_验收解压").resolve()
    for kind in args.only:
        spec = manifest["packages"][kind]
        path = OUT / spec["archive"]
        with path.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != spec["sha256"]:
                raise ValueError(f"Archive hash mismatch: {kind}")
        expected = {entry["member"]: entry for entry in spec["members"]}
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != set(expected):
                raise ValueError(f"Unexpected or duplicate archive members: {kind}")
            for name in names:
                target = (destination / name).resolve()
                if not target.is_relative_to(destination):
                    raise ValueError(f"Unsafe member: {name}")
                digest = hashlib.sha256()
                if args.extract:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(name) as source, target.open("wb") as output:
                        while block := source.read(1024 * 1024):
                            digest.update(block)
                            output.write(block)
                else:
                    with archive.open(name) as source:
                        while block := source.read(1024 * 1024):
                            digest.update(block)
                if digest.hexdigest() != expected[name]["sha256"]:
                    raise ValueError(f"Member hash mismatch: {name}")
        print(f"{kind}: {len(names)} members verified" + (" and extracted" if args.extract else ""), flush=True)


if __name__ == "__main__":
    main()
