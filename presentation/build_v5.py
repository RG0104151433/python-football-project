"""Build the adopted V5 and publish it at the main entry; never rewrite frozen V4."""
from pathlib import Path
import hashlib,json,shutil
H=Path(__file__).resolve().parent
V4=H/'versions/v4_20261110';V5=H/'versions/v5_20261110'
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((V4/'manifest.json').read_text(encoding='utf-8'))
for name,expected in m['files'].items():assert h(V4/name)==expected,name
before=h(H/'index.html');V5.mkdir(exist_ok=True)
base=(V4/'index.html').read_text(encoding='utf-8');extra=(H/'forecast_hover_v5.js').read_text(encoding='utf-8-sig')
html=base.replace('</html>','<script>'+extra+'</script></html>')
snapshot_path=H/'verified_results_payload.json'
snapshot=None
if snapshot_path.exists():
 snapshot=json.loads(snapshot_path.read_text(encoding='utf-8'))
 checked_path=H/'results_checked_20261117.csv'
 assert h(checked_path)==snapshot['csv_sha256'],'Checked results CSV differs from verified payload'
 bootstrap=(H/'verified_results.js').read_text(encoding='utf-8')
 payload=json.dumps(snapshot,ensure_ascii=False).replace('</','<\\/')
 html=html.replace('</html>','<script>window.matchdayResultsSnapshot='+payload+';</script><script>'+bootstrap+'</script></html>')
(V5/'index.html').write_text(html,encoding='utf-8')
for name in ['repository_architecture.html','results_template.csv']:shutil.copyfile(V4/name,V5/name)
if snapshot is not None:shutil.copyfile(H/'results_checked_20261117.csv',V5/'results_checked_20261117.csv')
shutil.copyfile(V5/'index.html',H/'index.html')
shutil.copyfile(V5/'repository_architecture.html',H/'repository_architecture.html')
for name in ['PRESENTATION_SCRIPT_EN.md','RESULTS_DAY_CHECKLIST.md']:
 if (H/name).exists():shutil.copyfile(H/name,V5/name)
out={'version':'V5','decision_log_id':'R20261110-05','base':'presentation/versions/v4_20261110/index.html','base_sha256':h(V4/'index.html'),'extension':'presentation/forecast_hover_v5.js','extension_sha256':h(H/'forecast_hover_v5.js'),'files':{n:h(V5/n) for n in ['index.html','repository_architecture.html','results_template.csv']},'forecast_values_changed':False,'main_entry_replaced':True,'adopted':True,'V4_modified':False}
if snapshot is not None:
 out['decision_log_id']='R20261117-01'
 out['files']['results_checked_20261117.csv']=h(V5/'results_checked_20261117.csv')
 out['results_snapshot']={'checked_at':snapshot['checked_at'],'payload':'presentation/verified_results_payload.json','payload_sha256':h(snapshot_path),'bootstrap_sha256':h(H/'verified_results.js'),'final':snapshot['summary']['final'],'pending':snapshot['summary']['pending'],'forecast_probabilities_changed':False}
(V5/'manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('V5 created from frozen V4. Published at the main entry; frozen V4 unchanged.')
