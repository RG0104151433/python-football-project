"""Check paper citation keys against the BibTeX database.

Usage (from the repository root):
    python paper/check_citations.py
    python paper/check_citations.py --strict

It prints:
- cited keys missing from paper/references.bib (error)
- duplicate BibTeX keys (error)
- BibTeX keys never cited in paper/**/*.tex (warning)
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
BIB = ROOT / "paper/references.bib"
PAPER = ROOT / "paper"

BIB_KEY = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
CITE = re.compile(r"\\cite[a-zA-Z]*\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]+)\}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail on uncited BibTeX keys")
    args = parser.parse_args()

    if not BIB.exists():
        print(f"ERROR: missing {BIB}")
        return 1

    bib_text = BIB.read_text(encoding="utf-8")
    keys = BIB_KEY.findall(bib_text)
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)

    cited: set[str] = set()
    tex_files = sorted(PAPER.rglob("*.tex"))
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
