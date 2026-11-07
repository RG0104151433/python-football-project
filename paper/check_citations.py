"""Check paper citation keys against the BibTeX database.

Usage (from the repository root):
    python paper/check_citations.py
    python paper/check_citations.py --strict
    python paper/check_citations.py --paper-dir paper/language_revision_20261107 --strict

It prints:
- cited keys missing from the selected version's references.bib (error)
- duplicate BibTeX keys (error)
- BibTeX keys never cited in that version's manuscript sources (warning)
- summary counts

Exit code 1 on missing/duplicate keys, or on uncited keys when --strict is used.
This is a writing-time check, not a substitute for reading the sources.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BIB_KEY = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
CITE = re.compile(r"\\cite[a-zA-Z]*\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]+)\}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail on uncited BibTeX keys")
    parser.add_argument("--paper-dir", default="paper", help="manuscript directory, relative to the repository root or absolute")
    args = parser.parse_args()
    paper = Path(args.paper_dir)
    if not paper.is_absolute():
        paper = ROOT / paper
    bib = paper / "references.bib"

    if not bib.exists():
        print(f"ERROR: missing {bib}")
        return 1

    bib_text = bib.read_text(encoding="utf-8")
    keys = BIB_KEY.findall(bib_text)
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)

    cited: set[str] = set()
    # Exclude other saved manuscript versions and their build caches.
    tex_files = [paper / "main.tex"] if (paper / "main.tex").exists() else []
    for directory in ("sections", "figures"):
        tex_files.extend(sorted((paper / directory).rglob("*.tex")))
    for path in tex_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for group in CITE.findall(text):
            for key in group.split(","):
                key = key.strip()
                if key:
                    cited.add(key)

    key_set = set(keys)
    missing = sorted(cited - key_set)
    uncited = sorted(key_set - cited)

    print(f"BibTeX entries: {len(keys)}")
    print(f"TeX files scanned: {len(tex_files)}")
    print(f"Distinct cited keys: {len(cited)}")
    if duplicates:
        print("ERROR duplicate keys: " + ", ".join(duplicates))
    if missing:
        print("ERROR cited but missing from BibTeX: " + ", ".join(missing))
    if uncited:
        print("WARNING BibTeX entries never cited: " + ", ".join(uncited))
    if not (duplicates or missing or (args.strict and uncited)):
        print("OK: citation keys are consistent.")

    return 1 if duplicates or missing or (args.strict and uncited) else 0


if __name__ == "__main__":
    raise SystemExit(main())
