"""Build separate course report/code/data archives without moving research files.

Run from the repository root. The data selection plan is reviewed independently;
this utility packages that explicit inventory, not every historical experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "交付材料"
SKIP = {"__pycache__", ".pytest_cache", ".venv", ".git", "build", "checkpoints", "jobs", "probe_jobs", "test_tmp"}


def files_under(relative: str):
    for parent, dirs, files in os.walk(ROOT / relative):
        dirs[:] = [d for d in dirs if d not in SKIP and d != "论文写作技能"]
        for name in sorted(files):
            yield Path(parent) / name


def sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_archive(kind: str, entries: dict[str, Path]) -> dict:
    target = OUT / f"{kind}.zip"
    inventory = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as archive:
        for destination, source in sorted(entries.items()):
            source = source.resolve()
            if not source.is_relative_to(ROOT) or not source.is_file():
                raise ValueError(f"Invalid source: {source}")
            if Path(destination).is_absolute() or ".." in Path(destination).parts:
                raise ValueError(f"Invalid member: {destination}")
            archive.write(source, destination)
            inventory.append({"member": destination, "source": source.relative_to(ROOT).as_posix(),
                              "bytes": source.stat().st_size, "sha256": sha(source)})
    return {"archive": target.name, "bytes": target.stat().st_size,
            "sha256": sha(target), "file_count": len(inventory), "members": inventory}


def code_entries() -> dict[str, Path]:
    selected = []
    for folder in ["src", "scripts", "config", "tests", "研究", "文档"]:
        selected.extend(p for p in files_under(folder)
                        if p.suffix.lower() in {".py", ".json", ".md", ".toml", ".ini", ".txt", ".html", ".css", ".js"})
    for name in ["README.md", "AGENTS.md", "config.json", "pytest.ini", "quick_check.py", "check_env.py",
                 "requirements.txt", "requirements.in", "requirements-core.txt"]:
        selected.append(ROOT / name)
    selected.extend(p for p in (ROOT / "paper").glob("*")
                    if p.is_file() and p.suffix in {".py", ".json", ".md"})
    entries = {"FootballProject/" + p.relative_to(ROOT).as_posix(): p for p in selected}
    entries["FootballProject/README_SUBMISSION.md"] = OUT / "README_SUBMISSION.md"
    if any(name.startswith(("FootballProject/data/", "FootballProject/outputs/"))
           or name.lower().endswith((".csv", ".parquet", ".npz", ".npy")) for name in entries):
        raise ValueError("Experimental data must not be in the platform code archive")
    return entries


def report_entries() -> dict[str, Path]:
    paper = ROOT / "paper/language_revision_20261107"
    entries = {"FootballProject/paper/final_paper.pdf": ROOT / "paper/final_paper.pdf",
               "FootballProject/REPORT_README.md": OUT / "REPORT_README.md"}
    for source in [paper / "main.tex", paper / "references.bib", *sorted((paper / "sections").glob("*.tex"))]:
        entries["FootballProject/paper/language_revision_20261107/" + source.relative_to(paper).as_posix()] = source
    # Preserve ../figures paths used by the canonical manuscript.
    for source in sorted((ROOT / "paper/figures").glob("*")):
        if source.suffix.lower() in {".pdf", ".tex"}:
            entries["FootballProject/paper/figures/" + source.name] = source
    return entries


def data_entries() -> dict[str, Path]:
    plan = json.loads((OUT / "data_selection_plan.json").read_text(encoding="utf-8"))
    entries = {}
    for name in plan["files"]:
        if not name.startswith(("data/", "outputs/")):
            raise ValueError(f"Unexpected data path: {name}")
        entries["FootballProject/" + name] = ROOT / name
    entries["FootballProject/DATA_PACKAGE_README.md"] = OUT / "DATA_PACKAGE_README.md"
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", choices=["Report", "Code", "Data"],
                        default=["Report", "Code", "Data"])
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    manifest_path = OUT / "PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
        "schema_version": "course-submission-archives-v1", "external_submission_performed": False,
        "data_selection": "data_selection_plan.json", "packages": {}}
    builders = {"Report": report_entries, "Code": code_entries, "Data": data_entries}
    for kind in args.only:
        result = write_archive(kind, builders[kind]())
        manifest["packages"][kind] = result
        print(f"{kind}: {result['file_count']} files, {result['bytes'] / 1024**2:.2f} MiB", flush=True)
    if "Report" in args.only:
        standalone = OUT / "Report.pdf"
        shutil.copyfile(ROOT / "paper/final_paper.pdf", standalone)
        manifest["standalone_report"] = {"file": standalone.name,
                                          "bytes": standalone.stat().st_size,
                                          "sha256": sha(standalone)}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums = "".join(f"{v['sha256']}  {v['archive']}\n"
                   for _, v in sorted(manifest["packages"].items()))
    if "standalone_report" in manifest:
        sums += f"{manifest['standalone_report']['sha256']}  Report.pdf\n"
    (OUT / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")


if __name__ == "__main__":
    main()
