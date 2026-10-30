"""Versioned outputs and normalized source identity for the strength pilot."""
from __future__ import annotations

import csv
import io
import json
import platform
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import scipy

from ..data_contract import atomic_bytes, csv_bytes, file_hash, fingerprint, write_json

ROOT = Path(__file__).resolve().parents[2]


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, strict=True))


def config(path="config/strength_pilot.json"):
    p = ROOT / path
    cfg = json.loads(p.read_text(encoding="utf-8-sig"))
    if cfg["schema_version"] != "strength-pilot-v1":
        raise ValueError("Unknown strength protocol")
    return cfg


def code_hashes():
    files = [*Path(__file__).parent.glob("*.py"), ROOT / "src/data_contract.py"]
    return {p.relative_to(ROOT).as_posix(): fingerprint(p.read_text(encoding="utf-8").replace("\r\n", "\n"))
            for p in sorted(files)}


def environment():
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {"python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "platform": platform.platform(),
            "commit": commit, "execution_code": "working tree; exact source hashes recorded, no commit made"}


def identify(kind, identity, base_dir="outputs/logs/strength"):
    identity = {**identity, "code": code_hashes(), "environment": environment()}
    if base_dir != "outputs/logs/strength":
        identity["artifact_base"] = base_dir
    return kind + "-" + fingerprint(identity)[:20], identity


def publish(kind, identity, csvs=None, jsons=None, texts=None, base_dir="outputs/logs/strength", prepared=None):
    """Immutable content-addressed stage; never overwrite a different artifact."""
    stage_id, identity = prepared or identify(kind, identity, base_dir)
    folder = ROOT / base_dir / stage_id
    if not folder.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Artifact outside workspace")
    content = {}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as z:
        for name in sorted(identity["code"]):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            z.writestr(entry, (ROOT / name).read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8"))
    content["source_snapshot.zip"] = archive.getvalue()
    for name, rows in (csvs or {}).items():
        if not rows:
            raise ValueError("Empty table must have an explicit schema: " + name)
        content[name] = csv_bytes(list(rows[0]), rows)
    for name, value in (jsons or {}).items():
        content[name] = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                                   allow_nan=False) + "\n").encode("utf-8")
    for name, value in (texts or {}).items():
        content[name] = value.encode("utf-8")
    for name, value in content.items():
        target = folder / name
        if target.exists() and target.read_bytes() != value:
            raise ValueError("Artifact collision: " + str(target))
    for name, value in content.items():
        atomic_bytes(folder / name, value)
    manifest = {"stage_id": stage_id, "identity": identity,
                "outputs": {name: file_hash(folder / name) for name in content}}
    write_json(folder / "manifest.json", manifest)
    return folder, manifest


def rounded(value):
    """Stable table serialization; JSON diagnostics retain full precision."""
    return float(f"{float(value):.10f}")
