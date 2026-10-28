"""Retrieve public method originals once; record failures without bypassing access."""
from pathlib import Path
from datetime import datetime,timezone
import urllib.request
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
if __name__=="__main__":
    destination=ROOT/"参考资料/方法文献/原文";rows=[]
    for rid,url,name in [
        ("Q4-P11","https://www.sciencedirect.com/science/article/pii/0047259X71900017","Rao_1971_MINQUE.pdf"),
        ("Q4-P12","https://www.stat.cmu.edu/~ryantibs/papers/conformal-jasa.pdf","Lei_etal_2018_conformal_author.pdf")]:
        row=dict(id=rid,url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),local_path=None)
        try:
            request=urllib.request.Request(url,headers={"User-Agent":"Academic research source archival"})
            with urllib.request.urlopen(request,timeout=25) as response:data=response.read()
            if not data.startswith(b"%PDF-"):raise ValueError("Response is not a PDF")
            path=destination/name
            if path.exists() and path.read_bytes()!=data:raise RuntimeError("Preserve prior original")
            path.write_bytes(data);row.update(status="downloaded",local_path=path.relative_to(ROOT).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        except Exception as exc:row.update(status="failed_no_local_original",error=type(exc).__name__+":"+str(exc))
        rows.append(row)
    path=ROOT/"outputs/logs/reliability/joint-20261028/source_retrieval.json"
    if path.exists():raise RuntimeError("Preserve previous retrieval record")
    path.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(rows,ensure_ascii=False))
