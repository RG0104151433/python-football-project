"""Load immutable adopted inputs; formal runs must not use development settings."""
import json
from src.strength.io import ROOT, read_rows
from src.strength.global_run import load as learning_load
from src.strength_joint.contract import load as joint_load
from src.strength_stage6_prepare import verify_manifest
from src.data_contract import file_hash


def load(config_path="config/strength_inference.json"):
    cfg = json.loads((ROOT / config_path).read_text(encoding="utf-8-sig"))
    if cfg["schema_version"] != "strength-inference-development-v1":
        raise ValueError("UNKNOWN_INFERENCE_PROTOCOL")
    if cfg["formal_application_allowed"] or cfg["protocol_frozen"]:
        raise ValueError("DEVELOPMENT_IMPLEMENTATION_CANNOT_ADMIT_FORMAL_INFERENCE")
    inputs = {config_path: file_hash(ROOT / config_path)}
    for key in ("preparation", "analysis", "sensitivity", "paired"):
        folder = ROOT / cfg[key]
        digest = file_hash(folder / "manifest.json")
        if digest != cfg[key + "_manifest_sha256"]:
            raise ValueError("INPUT_VERSION_MISMATCH: " + key)
        verify_manifest(folder)
        inputs[cfg[key] + "/manifest.json"] = digest
    jc, rows, _, _, old_inputs = joint_load()
    _, games, li = learning_load(jc["learning_config"])
    games = sorted((g for g in games if "1950-01-01" <= g["date"] <= "2024-12-31"), key=lambda g: (g["date"], g["match_id"]))
    if len(games) != 38919 or {g["match_id"] for g in games if g["study"]} != {r["match_id"] for r in rows}:
        raise ValueError("LEARNING_STUDY_ID_MISMATCH")
    registry = read_rows(ROOT / cfg["preparation"] / "target_registry.csv")
    primary = [r for r in registry if r["family"] == cfg["family"]]
    if len(registry) != 143 or len(primary) != 54 or len({r["registry_id"] for r in primary}) != 54:
        raise ValueError("PRIMARY_FAMILY_MISMATCH")
    score = verify_manifest(ROOT / cfg["score"])
    inputs.update(old_inputs); inputs.update(li)
    inputs[cfg["score"] + "/manifest.json"] = file_hash(ROOT / cfg["score"] / "manifest.json")
    return dict(cfg=cfg, joint_cfg=jc, rows=rows, games=games, registry=primary, inputs=inputs,
                score_parameters=score["identity"]["parameters"], score_numerics=score["identity"]["numerics"])
