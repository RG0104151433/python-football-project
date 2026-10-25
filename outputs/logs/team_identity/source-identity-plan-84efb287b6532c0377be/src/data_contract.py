"""Shared input contracts, identifiers and deterministic file formats.

Only the standard library is needed for data preparation. Raw files are never
written by this package. CSV values stay strings until explicitly validated.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

RULES_VERSION = "data-prep-v1"
SCHEMAS = {
    "results.csv": "date home_team away_team home_score away_score tournament city country neutral".split(),
    "shootouts.csv": "date home_team away_team winner first_shooter".split(),
    "former_names.csv": "current former start_date end_date".split(),
    "goalscorers.csv": "date home_team away_team team scorer minute own_goal penalty assist".split(),
}
CLEAN_FIELDS = """match_id source_record_id row_content_sha256 source_file source_sha256
source_record_no date date_precision home_team_raw away_team_raw home_team_id away_team_id
home_team away_team home_score away_score outcome goal_difference result_basis
shootout_status shootout_winner_id tournament_raw tournament tournament_group city country
neutral_raw is_neutral venue_basis year decade_start time_split eligible_elo
eligible_venue_analysis eligible_tournament_analysis review_status""".split()
ISSUE_FIELDS = """issue_id run_id rule_version severity code stage case_id source_file
source_sha256 source_record_no source_record_id match_id related_record_ids field raw_value
expected message action status evidence_ids""".split()
LINEAGE_FIELDS = "source_record_id source_file source_sha256 source_record_no match_id final_status case_ids issue_codes reason".split()
TEAM_FIELDS = "team_id canonical_name registry_version source_name".split()
GROUP_FIELDS = "tournament_name match_count default_group group mapping_version rationale review_status evidence_id".split()


class PrepError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value) -> str:
    return digest(json_bytes(value))


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def parse_date(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("expected YYYY-MM-DD")
    return date.fromisoformat(value).isoformat()


def parse_score(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value.strip()):
        raise ValueError("expected a non-negative integer")
    return int(value)


def parse_neutral(value: str) -> bool:
    values = {"true": True, "false": False}
    key = value.strip().casefold()
    if key not in values:
        raise ValueError("expected TRUE or FALSE")
    return values[key]


def tournament_group(name: str) -> str:
    if not name or "\ufffd" in name or any(unicodedata.category(c) == "Cc" for c in name):
        return "unknown"
    return "friendly" if name.casefold() == "friendly" else "non_friendly"


def team_slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def project_path(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise PrepError("PATH_OUTSIDE_PROJECT", f"路径超出项目目录：{value}")
    return path


def load_config(config_path: str | Path):
    path = Path(config_path).resolve()
    root = path.parent
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(config, dict) or not isinstance(config.get("data_prep", {}), dict):
            raise ValueError("配置必须是 JSON 对象，data_prep 必须是对象")
        cutoff = parse_date(config["data"]["cutoff_date"])
        boundaries = [parse_date(config["time_split"][k]) for k in ("warmup_end", "train_end", "valid_end", "test_end")]
        if boundaries != sorted(set(boundaries)) or cutoff > boundaries[-1]:
            raise ValueError("时间边界必须递增且覆盖截止日")
        raw = project_path(root, config["data"]["raw_dir"])
        processed = project_path(root, config["data"]["processed_dir"])
        if raw == root or processed == root or processed.is_relative_to(raw) or raw.is_relative_to(processed):
            raise ValueError("原始目录和产物目录必须分开，不能使用项目根目录")
        policy = config.get("data_prep", {}).get("unresolved_key_policy", "isolate")
        if policy != "isolate":
            raise ValueError("第一版仅支持 isolate 政策")
        if config.get("data_prep", {}).get("isolation_policy_version", "isolate-v1") != "isolate-v1":
            raise ValueError("未知的隔离政策版本")
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise PrepError("CONFIG_INVALID", str(exc)) from exc
    return root, config


def paths(root: Path, config: dict):
    raw = project_path(root, config["data"]["raw_dir"])
    return {
        "raw": raw,
        "input": raw / "international_results",
        "snapshot": raw / "manifest.json",
        "processed": project_path(root, config["data"]["processed_dir"]),
        "external": root / "data" / "external",
        "logs": root / "outputs" / "logs" / "data_prep",
    }


def read_csv(path: Path, required=None):
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            fields = reader.fieldnames
            if not fields or len(fields) != len(set(fields)):
                raise PrepError("SCHEMA_INVALID", f"表头为空或重复：{path}")
            if required and not set(required).issubset(fields):
                raise PrepError("SCHEMA_MISSING", f"{path.name} 缺少列：{sorted(set(required) - set(fields))}")
            rows = list(reader)
            if any(None in r or any(v is None for v in r.values()) for r in rows):
                raise PrepError("CSV_STRUCTURE_INVALID", f"字段数量不匹配：{path}")
    except (OSError, UnicodeError, csv.Error) as exc:
        raise PrepError("INPUT_UNREADABLE", f"{path}: {exc}") from exc
    return fields, rows


def csv_bytes(fields, rows) -> bytes:
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        values = {}
        for field in fields:
            value = row.get(field, "")
            if value is None:
                value = ""
            elif isinstance(value, bool):
                value = "true" if value else "false"
            elif isinstance(value, float):
                import math
                if not math.isfinite(value):
                    raise PrepError("NON_FINITE_OUTPUT", field)
                value = f"{value:.10f}"
            elif isinstance(value, (list, dict)):
                value = json_bytes(value).decode("utf-8")
            values[field] = value
        writer.writerow(values)
    return stream.getvalue().encode("utf-8-sig")


def atomic_bytes(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Temporary sibling + atomic replace prevents partially written files.
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".prep-", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(content)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def write_json(path: Path, value):
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n")


def make_run_dir(base: Path, stage: str) -> Path:
    import uuid
    label = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = base / f"{stage}-{label}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def source_record(raw: dict, file_name: str, sha: str, number: int, relative_path: str):
    prefix = Path(file_name).stem
    content_sha = fingerprint([raw[k] for k in SCHEMAS[file_name]])
    return {
        "raw": raw, "source_record_id": f"{prefix}:{sha}:{number}",
        "match_id": f"{prefix}:{content_sha}", "row_content_sha256": content_sha,
        "source_file": relative_path, "source_sha256": sha, "source_record_no": number,
    }


def issue(code, severity, record=None, *, field="", value="", expected="", message="", action="REVIEW", case_id="", related=None, stage="audit"):
    record = record or {}
    result = {k: record.get(k, "") for k in ("source_file", "source_sha256", "source_record_no", "source_record_id", "match_id")}
    result.update(rule_version=RULES_VERSION, severity=severity, code=code, stage=stage,
                  case_id=case_id, related_record_ids=related or [], field=field,
                  raw_value=value, expected=expected, message=message, action=action,
                  status="open", evidence_ids=[], run_id="")
    result["issue_id"] = "issue:" + fingerprint(result)
    return result


def print_summary(report: dict, run_dir: Path):
    counts = report.get("counts", {})
    brief = {k: v for k, v in counts.items() if k not in {"years", "tournament_counts", "neutral_counts"}}
    print(json.dumps({"status": report.get("status"), "data_version": report.get("data_version"),
                      "counts": brief, "report": str(run_dir)}, ensure_ascii=False))


def print_issue_examples(issues, limit=5):
    examples = sorted(issues, key=lambda i: (i["severity"] != "ERROR", i["issue_id"]))[:limit]
    for item in examples:
        print(f"[{item['severity']} {item['code']}] record={item['source_record_id']} "
              f"case={item['case_id']} field={item['field']} action={item['action']} {item['message']}")
    if len(issues) > limit:
        print(f"以上只展示 {limit} 条；完整 {len(issues)} 条见 issues.csv。问题条数不等于比赛数。")


def run_cli(function):
    # Windows terminals may default to GBK, which cannot display every team name.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        return function()
    except (PrepError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "EXECUTION_FAILED")
        print(f"[FATAL {code}] {exc}", file=sys.stderr)
        # Persist failures when a valid project config was provided.
        try:
            index = sys.argv.index("--config")
            root, config = load_config(sys.argv[index + 1])
            folder = make_run_dir(paths(root, config)["logs"], "failed")
            write_json(folder / "failure.json", {"status": "failed", "code": code, "message": str(exc)})
            print(f"诊断文件：{folder}", file=sys.stderr)
        except (ValueError, IndexError, PrepError, OSError):
            pass
        return 2
