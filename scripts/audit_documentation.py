"""Check documentation inventory, local links and README language pairs.

Standard-library only; this does not refit models or certify external sources.
Historical records and immutable source documents are reported separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", ".idea", ".mimosa", ".workbuddy", "__pycache__",
        ".pytest_cache", "build", "_build", "test_tmp"}
EXTENSIONS = {".md", ".rst", ".txt", ".tex", ".bib"}
LANGUAGE_VARIANT = re.compile(r"\.(en|zh-CN)\.(md|rst|txt)$", re.I)
LINK = re.compile(r"!?\[[^\]\n]*\]\(([^\n)]+)\)")


def scope(name: str) -> str:
    if LANGUAGE_VARIANT.search(name):
        return "language_reading_edition"
    if (name.startswith(("data/", "outputs/"))
            or (name.startswith("presentation/vendor/") and name != "presentation/vendor/README.md")
            or "/CCFA-Skills/91ca9e280169/" in name):
        return "immutable_source_or_run_record"
    if ("/archive/" in name or "/versions/v3_" in name or "/versions/v4_" in name
            or "整理前" in name or "研究日志与决策记录" in name or "README历史快照_" in name
            or "外部核查原文" in name or "独立复核报告_" in name
            or "review_layer" in name or "_review_2026" in name):
        return "historical_or_append_only"
    return "project_documentation"


def load_mapping() -> dict[str, str]:
    result: dict[str, str] = {}
    f = ROOT / "文档/04_整理记录/仓库优化执行记录_20261111.json"
    if f.exists():
        result.update(json.loads(f.read_text(encoding="utf-8-sig"))["path_mapping"])
    f = ROOT / "文档/04_整理记录/README双语目录_20261112.json"
    if f.exists():
        result.update(json.loads(f.read_text(encoding="utf-8-sig")).get("history_mapping", {}))
    return result


def inventory() -> tuple[list[Path], list[dict]]:
    files: list[Path] = []
    errors: list[dict] = []

    def onerror(error: OSError) -> None:
        errors.append({"path": str(error.filename), "error": str(error)})

    for parent, dirs, names in os.walk(ROOT, onerror=onerror):
        dirs[:] = [d for d in dirs if d not in SKIP and not (Path(parent) / d).is_symlink()]
        for name in names:
            p = Path(parent) / name
            if p.suffix.lower() in EXTENSIONS and not name.startswith("requirements"):
                files.append(p)
    return sorted(files), errors


def audit() -> dict:
    mapping = load_mapping()
    files, errors = inventory()
    records = []
    for p in files:
        name = p.relative_to(ROOT).as_posix()
        raw = p.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
            encoding = "utf-8"
        except UnicodeDecodeError:
            records.append({"path": name, "status": "non_utf8_source",
                            "bytes": len(raw), "scope": scope(name)})
            continue
        links = []
        # Fenced examples are instructions, not active Markdown links.
        prose = re.sub(r"(?ms)^```[^\n]*\n.*?^```[^\n]*", "", text)
        for match in LINK.finditer(prose):
            target = match.group(1).strip()
            target = re.split(r'\s+["\']', target, maxsplit=1)[0].strip("<>")
            if target.startswith("#") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            local = unquote(target.split("#", 1)[0])
            if not local or "${" in local or "\\(" in local:
                continue
            resolved = (p.parent / local).resolve()
            if not resolved.is_relative_to(ROOT):
                links.append({"target": target, "status": "outside_repository"})
                continue
            rel = resolved.relative_to(ROOT).as_posix()
            if resolved.exists():
                status = "exists"
            elif rel in mapping and (ROOT / mapping[rel]).exists():
                status = "relocated_historical_reference"
            else:
                status = "missing_or_planned"
            in_history = "<details>" in prose[:match.start()]
            links.append({"target": target, "resolved": rel, "status": status,
                          "section": "historical_appendix" if in_history else "main"})
        current = text.split("<details>", 1)[0]
        signals = sorted(set(re.findall(
            r"尚未提交|尚未生成PDF|没有生成PDF|待提供姓名|10屏|12屏|V5尚未采用|213个赛事", current)))
        records.append({"path": name, "scope": scope(name), "status": "text_scanned",
                        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                        "current_state_signals_for_review": signals,
                        "local_link_count": len(links),
                        "valid_local_link_count": sum(x["status"] == "exists" for x in links),
                        "local_links": [x for x in links if x["status"] != "exists"]})
    pairs_path = ROOT / "文档/04_整理记录/README双语目录_20261112.json"
    pairs = []
    if pairs_path.exists():
        registry = json.loads(pairs_path.read_text(encoding="utf-8-sig"))
        for item in registry["readmes"]:
            chinese, english = ROOT / item["chinese"], ROOT / item["english"]
            en_link = os.path.relpath(english, chinese.parent).replace("\\", "/")
            zh_link = os.path.relpath(chinese, english.parent).replace("\\", "/")
            ok = (chinese.exists() and english.exists()
                  and f"]({en_link})" in chinese.read_text(encoding="utf-8-sig")
                  and f"]({zh_link})" in english.read_text(encoding="utf-8-sig"))
            original_ok = True
            if item.get("original_preserved"):
                original_ok = hashlib.sha256((ROOT / item["original"]).read_bytes()).hexdigest() == item["original_sha256"]
            pairs.append({"original": item["original"], "chinese": item["chinese"],
                          "english": item["english"], "reciprocal_links": ok,
                          "preserved_original_hash": original_ok})
    originals = {p.relative_to(ROOT).as_posix() for p in files
                 if p.name.lower().startswith("readme")
                 and not LANGUAGE_VARIANT.search(p.name)}
    registered = {x["original"] for x in pairs}
    active_issues = [{"document": d["path"], **link}
                     for d in records if d["scope"] in {"project_documentation", "language_reading_edition"}
                     for link in d.get("local_links", [])
                     if link["status"] in {"missing_or_planned", "outside_repository"}
                     and link.get("section", "main") != "historical_appendix"]
    return {"schema_version": 1, "date": "2026-11-12", "executor": "Codex (AI)",
            "method": "full-text inventory and static local-link checks; manual findings recorded in companion report",
            "external_sites_rechecked": False, "access_errors": errors,
            "documents": records, "readme_pairs": pairs,
            "unpaired_original_readmes": sorted(originals - registered),
            "current_link_issues": active_issues,
            "summary": {"documents": len(records), "readme_pairs": len(pairs),
                        "local_links_checked": sum(x.get("local_link_count", 0) for x in records),
                        "current_link_issues": len(active_issues),
                        "pairs_passed": sum(x["reciprocal_links"] and x["preserved_original_hash"] for x in pairs)}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "文档/04_整理记录/文档核对明细_20261112.json")
    args = parser.parse_args()
    report = audit()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report["summary"], "access_errors": len(report["access_errors"])}, ensure_ascii=False))
    if report["access_errors"] or report["current_link_issues"] or report["unpaired_original_readmes"] or any(not (x["reciprocal_links"] and x["preserved_original_hash"])
                                      for x in report["readme_pairs"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
