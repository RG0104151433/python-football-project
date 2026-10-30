"""Versioned outputs, exact source snapshot and explicit development status."""
import gzip
import io
import json
import zipfile
from datetime import datetime, timezone
from src.data_contract import atomic_bytes, csv_bytes, file_hash, fingerprint, write_json
from src.strength.io import ROOT, environment


def publish(stage, contract, csvs=None, jsons=None):
    paths = [*ROOT.glob("src/strength_inference/*.py"), ROOT/"scripts/analyze_strength_inference.py",
        ROOT/"scripts/audit_strength_inference.py", ROOT/"config/strength_inference.json", ROOT/"tests/test_strength_inference.py",
        *ROOT.glob("src/strength_joint/*.py"), *ROOT.glob("src/strength/*.py"), ROOT/"src/data_contract.py", ROOT/"src/strength_stage6_sensitivity.py"]
    identity = dict(stage=stage, execution_utc=datetime.now(timezone.utc).isoformat(), protocol=contract["cfg"], inputs=contract["inputs"], code={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(paths) if p.exists()},
                    environment=environment())
    ident = "inference-"+stage+"-"+fingerprint(identity)[:20]
    folder = ROOT/"outputs/tables/strength_joint"/ident; content = {}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as z:
        for name in identity["code"]: z.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), (ROOT/name).read_bytes())
    content["source_snapshot.zip"] = archive.getvalue()
    for name, rows in (csvs or {}).items():
        if not rows: raise ValueError("EMPTY_TABLE_WITHOUT_SCHEMA: "+name)
        data = csv_bytes(list(rows[0]), rows); content[name] = gzip.compress(data, mtime=0) if name.endswith(".gz") else data
    for name, obj in (jsons or {}).items(): content[name] = (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n").encode()
    content["protocol.json"] = (json.dumps(contract["cfg"], sort_keys=True, indent=2)+"\n").encode()
    for name, data in content.items():
        if (folder/name).exists() and (folder/name).read_bytes() != data: raise ValueError("IMMUTABLE_COLLISION: "+name)
        atomic_bytes(folder/name, data)
    write_json(folder/"manifest.json", dict(stage_id=ident, identity=identity, outputs={n:file_hash(folder/n) for n in content}))
    write_json(ROOT/"outputs/logs/strength_inference"/(stage+"_pointer.json"), dict(directory=folder.relative_to(ROOT).as_posix(), manifest_sha256=file_hash(folder/"manifest.json")))
    print("INFERENCE_COMPLETE", stage, folder.relative_to(ROOT).as_posix(), flush=True)
    return folder
