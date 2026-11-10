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
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "交付材料"
META = OUT / "04_清单与验收"
MAIL = OUT / "01_邮件附件"
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
    target = MAIL / f"{kind}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
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
    return {"archive": target.relative_to(OUT).as_posix(), "bytes": target.stat().st_size,
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
    entries["FootballProject/README_SUBMISSION.md"] = META / "README_SUBMISSION.md"
    # Templates and selection inventory let recipients inspect packaging decisions.
    for name in ["README_SUBMISSION.md", "REPORT_README.md", "DATA_PACKAGE_README.md", "data_selection_plan.json", "DELIVERY_CHECKS.md"]:
        entries["FootballProject/交付材料/04_清单与验收/" + name] = META / name
    if any(name.startswith(("FootballProject/data/", "FootballProject/outputs/"))
           or name.lower().endswith((".csv", ".parquet", ".npz", ".npy")) for name in entries):
        raise ValueError("Experimental data must not be in the platform code archive")
    return entries


def report_entries() -> dict[str, Path]:
    paper = ROOT / "paper/language_revision_20261107"
    entries = {"FootballProject/paper/final_paper.pdf": ROOT / "paper/final_paper.pdf",
               "FootballProject/REPORT_README.md": META / "REPORT_README.md"}
    sources = [paper / "main.tex", paper / "references.bib", *sorted((paper / "sections").glob("*.tex"))]
    if (paper / "cover.tex").exists():
        sources.append(paper / "cover.tex")
    for source in sources:
        entries["FootballProject/paper/language_revision_20261107/" + source.relative_to(paper).as_posix()] = source
    # Preserve ../figures paths used by the canonical manuscript.
    for source in sorted((ROOT / "paper/figures").glob("*")):
        if source.suffix.lower() in {".pdf", ".tex"} or source.name == "bit_school_header.jpeg":
            entries["FootballProject/paper/figures/" + source.name] = source
    return entries


def data_entries() -> dict[str, Path]:
    plan = json.loads((META / "data_selection_plan.json").read_text(encoding="utf-8"))
    entries = {}
    for name in plan["files"]:
        if not name.startswith(("data/", "outputs/")):
            raise ValueError(f"Unexpected data path: {name}")
        entries["FootballProject/" + name] = ROOT / name
    entries["FootballProject/DATA_PACKAGE_README.md"] = META / "DATA_PACKAGE_README.md"
    return entries


def refresh_data_plan() -> None:
    """Select real inputs, final summaries and bound evidence, not simulation worlds.

    Deliberately do not recursively follow every path in archived manifests: that
    pulled hundreds of MB of simulation histories into the former mail package.
    Full evidence stays in the repository; omitted attachment members are listed.
    """
    historical = OUT / "90_历史记录/data_selection_plan_完整旧版.json"
    current = META / "data_selection_plan.json"
    old = json.loads((historical if historical.exists() else current).read_text(encoding="utf-8"))["files"]
    selected: dict[str, list[str]] = {}

    def add(name: str, why: str) -> None:
        path = (ROOT / name).resolve()
        if path.is_relative_to(ROOT) and path.is_file():
            selected.setdefault(name, []).append(why)

    inputs = ("data/raw/", "data/external/", "data/processed/prep-3fab808178cf8ad71d88/",
              "data/processed/team_identity/identity-reviewed-29d880765c1623764940/",
              "data/processed/strength/joint-preparation-6fa9d025ba40d11cd2f8/")
    for name in old:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(name)
        if name.startswith(inputs):
            add(name, "original_or_adopted_input")
        elif (name.startswith("outputs/tables/") and len(Path(name).parts) == 5
              and path.suffix in {".csv", ".json", ".md", ".txt"}
              and path.stat().st_size < 512 * 1024):
            add(name, "reported_summary_or_comparison")
        elif (name.startswith("outputs/logs/") and len(Path(name).parts) <= 6
              and path.suffix == ".json" and path.stat().st_size < 256 * 1024
              and any(tag in path.name for tag in ["report", "manifest", "adoption", "review", "selection", "validation"])):
            add(name, "audit_summary")
    for name in ["paper/results_evidence.json", "paper/strength_evidence_manifest.json"]:
        for source in re.findall(r'"((?:data|outputs)/[^"\n]+)"', (ROOT / name).read_text(encoding="utf-8")):
            add(source, "paper_bound_evidence")
    for name in [
        "outputs/tables/strength_joint/rolling-prediction-4722c7b1b5f63cef35e3/predictions.csv",
        "outputs/tables/regional_effectiveness/regional-evaluation-7ea3e4ab7c7dbb8eeb58/evaluation_matches.csv",
        "outputs/tables/regions/regions-0a1c61664a722e6c641f/analysis_matches.csv",
    ]:
        add(name, "real_match_level_evaluation")
    omitted = sorted(set(old) - set(selected))
    plan = {"schema_version": "email-data-selection-v2", "decision_log_id": "R20261110-07",
            "method": "explicit inputs + paper-bound evidence + final summaries; no recursive manifest closure",
            "files": sorted(selected), "reasons": selected,
            "uncompressed_bytes": sum((ROOT / n).stat().st_size for n in selected),
            "omitted_from_attachment_not_deleted_from_repository": omitted,
            "omission_reason": "simulation histories, per-world fits, recomputable intermediate copies or bulky row-level diagnostics; retained in the full repository",
            "scope": "inspect reported results and run documented core examples; not every historical experiment can resume without regeneration"}
    current.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", choices=["Report", "Code", "Data"],
                        default=["Report", "Code", "Data"])
    parser.add_argument("--refresh-data-plan", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    META.mkdir(exist_ok=True)
    if args.refresh_data_plan:
        refresh_data_plan()
    manifest_path = META / "PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
        "schema_version": "course-submission-archives-v2", "external_submission_performed": False,
        "data_selection": "04_清单与验收/data_selection_plan.json", "packages": {}}
    manifest["schema_version"] = "course-submission-archives-v2"
    manifest["decision_log_id"] = "R20261110-07"
    manifest["data_selection"] = "04_清单与验收/data_selection_plan.json"
    builders = {"Report": report_entries, "Code": code_entries, "Data": data_entries}
    for kind in args.only:
        result = write_archive(kind, builders[kind]())
        manifest["packages"][kind] = result
        print(f"{kind}: {result['file_count']} files, {result['bytes'] / 1024**2:.2f} MiB", flush=True)
    if "Report" in args.only:
        standalone = OUT / "02_平台上传/Report.pdf"
        standalone.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / "paper/final_paper.pdf", standalone)
        manifest["standalone_report"] = {"file": standalone.relative_to(OUT).as_posix(),
                                          "bytes": standalone.stat().st_size,
                                          "sha256": sha(standalone)}
    total = sum(item["bytes"] for item in manifest["packages"].values())
    if total > 40 * 1024**2:
        raise ValueError("Three mail archives exceed the project 40 MiB budget; review the selection. This is not a verified mailbox limit.")
    manifest["email_attachment_bytes"] = total
    manifest["mailbox_upload_tested"] = False
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums = "".join(f"{v['sha256']}  {v['archive']}\n"
                   for _, v in sorted(manifest["packages"].items()))
    if "standalone_report" in manifest:
        sums += f"{manifest['standalone_report']['sha256']}  {manifest['standalone_report']['file']}\n"
    (META / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")


if __name__ == "__main__":
    main()
