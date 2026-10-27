"""Resolve shared source bytes while preserving historical manifest hashes."""
import hashlib
import json
from pathlib import Path

INDEX = "data/external/geography_sources/m49-20261026/relocations.json"
CANONICAL = "data/external/geography_sources/m49-20261026"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_artifact(path, root):
    root = Path(root).resolve()
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    if path.is_file():
        return path
    try:
        key = path.resolve().relative_to(root).as_posix()
    except ValueError:
        raise FileNotFoundError(path)
    index = root / INDEX
    aliases = json.loads(index.read_text(encoding="utf-8"))["aliases"] if index.is_file() else {}
    record = aliases.get(key)
    if not record:
        raise FileNotFoundError(path)
    actual = (root / record["canonical_path"]).resolve()
    if not actual.is_relative_to(root) or not actual.is_file() or digest(actual) != record["sha256"]:
        raise ValueError(f"Shared artifact is absent or changed: {key}")
    return actual


def is_shared_source(path):
    return Path(path).name in {"m49_page.html", "m49_overview.html"}


def resolve_input(run, item, root):
    if item.get("storage") == "shared":
        path = resolve_artifact(item["shared_path"], root)
    else:
        path = resolve_artifact(Path(run) / item["snapshot_path"], root)
    if digest(path) != item["sha256"]:
        raise ValueError("Input content hash differs from its recorded value")
    return path
