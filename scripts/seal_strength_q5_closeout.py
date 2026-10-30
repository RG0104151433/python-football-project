"""Seal the final current documents, source extension, evidence and materials."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,io,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import atomic_bytes,file_hash,fingerprint,write_json
from src.strength.io import environment


def run():
    log=ROOT/'outputs/logs/strength_inference';audit=json.loads((log/'q5_final_audit.json').read_text())
    if not audit['passed']:raise ValueError('FINAL_AUDIT_REQUIRED')
    cp=json.loads((log/'comparison_pointer.json').read_text());prediction=json.loads((log/'prediction_pointer.json').read_text())
    material=json.loads((ROOT/'outputs/logs/strength_q5_closeout/current.json').read_text())
    sources=sorted(set([*ROOT.glob('src/strength/*.py'),*ROOT.glob('src/strength_joint/*.py'),*ROOT.glob('src/strength_inference/*.py'),
        *ROOT.glob('src/strength_inference_*.py'),ROOT/'src/strength_predictive_validation.py',ROOT/'src/strength_q5_closeout.py',
        *ROOT.glob('scripts/*strength*inference*.py'),ROOT/'scripts/analyze_strength_predictive_validation.py',ROOT/'scripts/audit_strength_predictive_validation.py',
        ROOT/'scripts/build_strength_q5_materials.py',ROOT/'scripts/sync_strength_q5_closeout.py',ROOT/'scripts/register_strength_confirmation_source.py',
        ROOT/'scripts/seal_strength_q5_closeout.py',ROOT/'scripts/audit_strength_confirmation_protocol.py',
        ROOT/'scripts/audit_strength_q5_html.py',ROOT/'scripts/audit_strength_q5_html.cjs',
        *ROOT.glob('tests/test_strength*.py'),*ROOT.glob('config/strength*.json'),ROOT/'src/data_contract.py',ROOT/'requirements.txt',ROOT/'requirements.in']))
    code={p.relative_to(ROOT).as_posix():file_hash(p) for p in sources}
    names=['README.md','研究/README.md','研究/pipeline_state.json','研究/05_赛前实力/README.md',
        '研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md','研究/06_历史参考周期/README.md',
        '文档/01_项目方案/研究日志与决策记录.md','文档/05_团队协作/论文与汇报支撑材料索引.md',
        '文档/05_团队协作/汇报要求与HTML方案.md','文档/05_团队协作/分工与交付/03_后续分析与展示.md',
        '参考资料/方法文献/README.md','参考资料/方法文献/sources.json',
        material['HTML'],material['document'],material['directory']+'/manifest.json',
        cp['directory']+'/manifest.json',cp['directory']+'/scope_decision.json',cp['directory']+'/scope_method_comparison.csv',cp['directory']+'/scope_reference_ranges.csv',
        cp['directory']+'/confirmation_result.json',prediction['directory']+'/manifest.json',
        'outputs/logs/strength_inference/q5_final_audit.json','outputs/logs/strength_inference/q5_all_tests.xml',
        'outputs/logs/strength_inference/prediction_audit.json','outputs/logs/strength_inference/confirmation_protocol_audit.json',
        'outputs/logs/strength_q5_closeout/browser_review.json','outputs/logs/strength_q5_closeout/visual_review.json',
        'outputs/logs/strength_q5_closeout/document_review.json',
        '文档/02_环境配置/克隆仓库后的快速上手.md']
    artifacts={name:file_hash(ROOT/name) for name in names}
    identity=dict(schema_version='q5-final-release-v1',decision_log_id='R20261031-06',code=code,artifacts=artifacts,environment=environment())
    ident='release-'+fingerprint(identity)[:20];folder=ROOT/'outputs/logs/strength_q5_closeout'/ident
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in code:z.writestr(zipfile.ZipInfo(name,(1980,1,1,0,0,0)),(ROOT/name).read_bytes())
    atomic_bytes(folder/'source_snapshot.zip',archive.getvalue())
    with zipfile.ZipFile(folder/'source_snapshot.zip') as archived:
        archive_verified=all(hashlib.sha256(archived.read(name)).hexdigest()==h for name,h in code.items())
    if not archive_verified:raise ValueError('SOURCE_ARCHIVE_MISMATCH')
    result=dict(identity=identity,source_snapshot_sha256=file_hash(folder/'source_snapshot.zip'),
        actual_human_review=False,committed_or_pushed=False,teacher_HTML_permission_confirmed=False,actual_browser_validation=False,
        original54_joint_admitted=False,unconditional_football_coverage_certified=False,
        executed_utc=datetime.now(timezone.utc).isoformat())
    write_json(folder/'release.json',result)
    write_json(ROOT/'outputs/logs/strength_q5_closeout/release_pointer.json',dict(directory=folder.relative_to(ROOT).as_posix(),
        release_sha256=file_hash(folder/'release.json'),source_snapshot_sha256=result['source_snapshot_sha256']))
    checks=all(file_hash(ROOT/name)==h for name,h in {**code,**artifacts}.items())
    write_json(ROOT/'outputs/logs/strength_q5_closeout/release_review.json',dict(passed=checks,code_files=len(code),artifact_files=len(artifacts),
        source_archive_verified=archive_verified,decision_log_id='R20261031-06',human_review=False))
    if not checks:raise SystemExit('FINAL_SEAL_HASH_MISMATCH')
    print('Q5_FINAL_SEALED',ident,len(code),len(artifacts),flush=True)


if __name__=='__main__':run()
