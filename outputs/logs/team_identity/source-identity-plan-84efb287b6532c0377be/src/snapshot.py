"""Register existing local files, or verify their immutable byte fingerprints."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .data_contract import (SCHEMAS, PrepError, file_hash, load_config, parse_date,
                            paths, read_csv, run_cli, write_json)


def inspect_inputs(root, config):
    location = paths(root, config)
    entries = []
    for name in [*SCHEMAS, "README.md", "LICENSE"]:
        path = location["input"] / name
        if not path.is_file():
            raise PrepError("INPUT_MISSING", str(path))
        before = file_hash(path)
        entry = {"path": path.relative_to(root).as_posix(), "sha256": before, "bytes": path.stat().st_size}
        if name in SCHEMAS:
            fields, rows = read_csv(path, SCHEMAS[name])
            dates, invalid = [], 0
            for row in rows:
                if "date" in row:
                    try:
                        dates.append(parse_date(row["date"]))
                    except ValueError:
                        invalid += 1
            entry.update(fields=fields, rows=len(rows), extra_fields=sorted(set(fields) - set(SCHEMAS[name])))
            if "date" in fields:
                entry.update(date_start=min(dates, default=None), date_end=max(dates, default=None), invalid_dates=invalid)
        if file_hash(path) != before:
            raise PrepError("INPUT_CHANGED_DURING_READ", str(path))
        entries.append(entry)
    return entries


def verify_snapshot(root, config):
    manifest_path = paths(root, config)["snapshot"]
    if not manifest_path.exists():
        raise PrepError("SNAPSHOT_NOT_REGISTERED", "请先运行 src.snapshot --register，现有原始文件不会自动登记。")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list):
        raise PrepError("SNAPSHOT_INVALID", "登记清单格式不正确")
    actual = inspect_inputs(root, config)
    if manifest["files"] != actual:
        raise PrepError("SNAPSHOT_MISMATCH", "原始文件、字段或统计与登记清单不同；停止，不能自动刷新旧清单。")
    return manifest


def register_snapshot(root, config):
    path = paths(root, config)["snapshot"]
    if path.exists():
        return verify_snapshot(root, config)
    manifest = {
        "schema_version": 1,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "acquired_at": None, "upstream_commit": None,
        "declared_source": "https://github.com/martj42/international_results",
        "acquisition_method": "existing local copy; original acquisition time unknown",
        "license": "CC0-1.0, see registered LICENSE",
        "files": inspect_inputs(root, config),
    }
    write_json(path, manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--register", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    root, config = load_config(args.config)
    manifest = register_snapshot(root, config) if args.register else verify_snapshot(root, config)
    print(f"快照{'登记/验证' if args.register else '验证'}通过：{len(manifest['files'])} 个文件；未修改原始文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
