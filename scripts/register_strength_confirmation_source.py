"""Preserve the primary sequential-inference source and honest retrieval status."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import write_json,atomic_bytes


def run():
    base=ROOT/'参考资料/方法文献';registry=json.loads((base/'sources.json').read_text(encoding='utf-8-sig'))
    url='https://arxiv.org/pdf/1810.08240v5';path=base/'原文/Howard_etal_2020v5_confidence_sequences.pdf'
    result=dict(id='Q5-P20',title='Time-uniform, nonparametric, nonasymptotic confidence sequences',
        authors='Steven R. Howard; Aaditya Ramdas; Jon McAuliffe; Jasjeet Sekhon',
        version='arXiv:1810.08240v5, 2020-05-30; published Annals of Statistics49(2),2021,1055–1080',
        requested_url=url,doi='https://doi.org/10.1214/20-AOS1991',retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
        decision_log_id='R20261031-05',web_read_url='https://arxiv.org/html/1810.08240v5',
        reading_scope='Read introduction, time-uniform coverage, stopping validity, nonnegative-supermartingale framework and sequential testing discussion; own Bernoulli LR and first-screen budget proof written in project, not a claim to have rechecked every paper theorem',
        adaptation='independent units are complete generated histories; conditional on frozen generator/truth/calibration. Not a confidence sequence for dependent football matches or real plug-in coverage.')
    try:
        if not path.exists():
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as response:data=response.read()
            if not data.startswith(b'%PDF-'):raise ValueError('not a PDF response')
            atomic_bytes(path,data)
        data=path.read_bytes();result.update(status='downloaded',local_path=path.relative_to(base).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:result.update(status='web_read_only_local_download_failed',local_path=None,download_error=str(exc))
    if any(r['id']=='Q5-P20' for r in registry['records']):raise ValueError('ALREADY_REGISTERED')
    registry['records'].append(result);write_json(base/'sources.json',registry)
    write_json(ROOT/'outputs/logs/strength_inference/confirmation_source.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':run()
