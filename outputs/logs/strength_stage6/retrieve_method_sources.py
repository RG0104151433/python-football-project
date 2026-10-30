"""Retain primary manuscripts; record actual download outcomes, never replace originals."""
from pathlib import Path
import datetime, hashlib, json, urllib.request

ROOT = Path(__file__).resolve().parents[3]
catalog = ROOT / '参考资料/方法文献/sources.json'
specs = [
    ('Q5-P17', 'The Dependent Wild Bootstrap', 'Xiaofeng Shao', '2010 JASA 105(489),218–235; DOI10.1198/jasa.2009.tm08744',
     'https://publish.illinois.edu/xshao/files/2012/11/JASA-DWB.pdf', 'Shao_2010_Dependent_Wild_Bootstrap.pdf',
     'Read introduction, dependent multipliers, regular/irregular time conditions and smooth-function scope; not a proof for our adaptive nonstationary rating process.'),
    ('Q5-P18', 'Maximum Likelihood and the Bootstrap for Nonlinear Dynamic Models', 'Silvia Goncalves; Halbert White',
     'CIRANO working paper 2002s-41, April2002; retained working version, not publisher typeset 2004 article',
     'https://depot.erudit.org/dspace/bitstream/000170dd/1/2002s-41.pdf', 'Goncalves_White_2002_CIRANO_dynamic_bootstrap.pdf',
     'Read introduction, QMLE/score representation, assumptions2.1–2.2 and theorem2.2, hypothesis-testing cautions. NED, mixing and heterogeneity restrictions not established for football.'),
    ('Q5-P19', 'Universal Inference', 'Larry Wasserman; Aaditya Ramdas; Sivaraman Balakrishnan',
     'arXiv1912.11436v3 June2020 author manuscript; publication DOI10.1073/pnas.1922664117',
     'https://arxiv.org/pdf/1912.11436v3', 'Wasserman_Ramdas_Balakrishnan_2020_Universal_Inference_v3.pdf',
     'Read sections2,6 conditional likelihood and null-likelihood upper bound,7 misspecification,8 sequential construction. Not adopted; requires correct conditional law/predictability and certified null optimization, not merely a composite likelihood.')
]
obj = json.loads(catalog.read_text(encoding='utf-8-sig'))
events = []
for ident,title,authors,version,url,name,scope in specs:
    path = ROOT / '参考资料/方法文献/原文' / name
    record = dict(id=ident,title=title,authors=authors,version=version,requested_url=url,
                  retrieved_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  local_path='原文/'+name,reading_scope=scope,decision_log_id='R20261030-12',
                  redistribution_status='not_evaluated',git_policy='local_retained; existing_ignore_policy; not_committed_or_pushed')
    try:
        if path.exists():
            data=path.read_bytes()
        else:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=45) as response:data=response.read()
            if not data.startswith(b'%PDF'):raise ValueError('Response is not a PDF')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        record.update(status='downloaded',bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),error=None)
    except Exception as exc:
        record.update(status='download_failed',bytes=None,sha256=None,error=str(exc))
    old=next((r for r in obj['records'] if r['id']==ident),None)
    if old is None:obj['records'].append(record)
    else:
        if old.get('sha256') and old['sha256']!=record.get('sha256'):raise ValueError('Existing source identity changed')
        old.update(record)
    events.append(record)
catalog.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'outputs/logs/strength_stage6/source_retrieval.json').write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps([dict(id=r['id'],status=r['status'],bytes=r['bytes']) for r in events]))
