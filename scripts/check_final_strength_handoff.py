"""Final adopted packet, provenance, same-version inputs and documentation QA."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.io import read_rows
from src.data_contract import file_hash,write_json


def run():
    out=ROOT/'outputs/logs/strength/repair-20261029';count=0;failed=[]
    def check(label,yes):
        nonlocal count
        count+=1
        if not yes:failed.append(label)
    pointer=json.loads((out/'adoption_pointer.json').read_text());packet=ROOT/pointer['directory']
    manifest=json.loads((packet/'manifest.json').read_text());adoption=json.loads((packet/'adoption.json').read_text())
    check('adoption_manifest',file_hash(packet/'manifest.json')==pointer['manifest_sha'])
    for name,h in manifest['outputs'].items():check('packet_hash:'+name,file_hash(packet/name)==h)
    for name,e in adoption['evidence'].items():check('embedded_evidence:'+name,file_hash(packet/e['embedded_path'])==e['sha256'])
    suite=ET.parse(packet/'tests.xml').getroot().find('testsuite')
    check('immutable_tests',int(suite.get('tests'))==63 and int(suite.get('failures'))==0 and int(suite.get('errors'))==0)
    source=ROOT/'outputs/tables/regions/regions-0a1c61664a722e6c641f/analysis_matches.csv';facts={r['match_id']:r for r in read_rows(source)}
    rows=read_rows(packet/'analysis_matches.csv');check('same24917',len(rows)==24917 and {r['match_id'] for r in rows}==facts.keys())
    check('no_forecast_or_scores_as_predictors',not any(k in rows[0] for k in ('p_home','p_draw','p_away','home_term','home_score','away_score')))
    for r in rows:
        mid=r['match_id'];f=facts[mid]
        check('original_fact:'+mid,all(r[k]==f[k] for k in ('date','home_win','outcome','home_region','away_region','home_unit','away_unit','era','tournament_group')))
        mu=float(r['strength_difference']);total=float(r['strength_difference_variance']);base=float(r['strength_difference_base_variance'])
        nu=float(r['home_jump_intensity'])+float(r['away_jump_intensity']);sd=float(r['jump_scale_sd'])
        check('distribution:'+mid,base>0 and nu>=0 and sd>=0 and abs(base+nu*sd*sd-total)<1e-8)
        vh,va,c=map(float,(r['home_variance'],r['away_variance'],r['home_away_covariance']))
        check('covariance:'+mid,vh>0 and va>0 and c*c<=vh*va+1e-8 and abs(vh+va-2*c-total)<1e-8)
        check('past_only:'+mid,r['prediction_cutoff']<r['date'])
        check('initialization_flag:'+mid,(r['initialization_sensitive']=='true')==(float(r['initialization_raw_probability_max_change'])>.01))
    cells=read_rows(packet/'support_cells.csv');check('support_cell_sum',sum(int(r['matches']) for r in cells)==24917)
    for name in ('analysis_matches.csv','support.csv','support_cells.csv'):
        data=(packet/name).read_bytes();check('BOM_LF:'+name,data.startswith(b'\xef\xbb\xbf') and b'\r\n' not in data)
    check('no_joint_implementation',not (ROOT/'src/strength_joint').exists() and not (ROOT/'scripts/analyze_strength_joint.py').exists())
    state=json.loads((ROOT/'研究/pipeline_state.json').read_text(encoding='utf-8'))['question_5']
    check('pipeline_adoption',state['acceptance_handoff']['joint_input']==pointer['directory'] and state['acceptance_handoff']['all_required_stage2_checks_passed'])
    check('third_design_only',state['acceptance_handoff']['third_stage_design_complete'] and not state['acceptance_handoff']['joint_fit_performed'])
    docs=['README.md','研究/README.md','研究/05_赛前实力/README.md','研究/05_赛前实力/第二环节_验收与正式交接.md',
        '研究/05_赛前实力/第三环节_联合分析准备与接口.md','文档/05_团队协作/论文与汇报支撑材料索引.md','参考资料/方法文献/README.md']
    for name in docs:
        path=ROOT/name;text=path.read_text(encoding='utf-8-sig')
        for link in re.findall(r'\]\(([^)]+)\)',text):
            if '://' in link or link.startswith(('#','mailto:')):continue
            target=link.split('#',1)[0].strip('<>')
            if target:check('link:'+name+':'+target,(path.parent/target).resolve().exists())
    log=(ROOT/'文档/01_项目方案/研究日志与决策记录.md').read_text(encoding='utf-8-sig')
    ids=re.findall(r'^### (R\d{8}-\d+)\b',log,re.M);check('unique_logs',len(ids)==len(set(ids)))
    catalog=json.loads((ROOT/'参考资料/方法文献/sources.json').read_text(encoding='utf-8-sig'));ids=[r['id'] for r in catalog['records']]
    check('unique_sources',len(ids)==len(set(ids)))
    for r in catalog['records']:
        if r['id'] in ('Q5-P15','Q5-P16'):check('new_paper:'+r['id'],file_hash(ROOT/'参考资料/方法文献'/r['local_path'])==r['sha256'])
    files=set(ROOT.glob('src/strength/*.py'))|set(ROOT.glob('scripts/*strength*.py'))|set(ROOT.glob('tests/test_strength*.py'))|set(ROOT.glob('config/strength*.json'))
    files|={ROOT/'scripts/repair_composed_calibration.py',ROOT/'scripts/diagnose_fast_calibration.py'}
    source_index={}
    for path in sorted(files):
        digest=file_hash(path);destination=out/'sources'/digest/path.name;destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():shutil.copyfile(path,destination)
        check('source_snapshot:'+path.name,file_hash(destination)==digest)
        source_index[path.relative_to(ROOT).as_posix()]=dict(sha256=digest,path=destination.relative_to(ROOT).as_posix())
    write_json(out/'current_sources.json',source_index)
    result=dict(passed=not failed,checks=count,failed=failed,adopted_packet=pointer['directory'],study_rows=len(rows),
        cold_start=sum(r['cold_start']=='true' for r in rows),initialization_sensitive=sum(r['initialization_sensitive']=='true' for r in rows),
        earlier_disconnected=sum(r['previously_disconnected']=='true' for r in rows),
        unknown_home_region=sum(r['home_region']=='' for r in rows),unknown_away_region=sum(r['away_region']=='' for r in rows),
        third_model_code_created=False,third_design_document_exists=True,actual_human_review=False)
    write_json(out/'final_handoff_review.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
    if failed:raise SystemExit(1)


if __name__=='__main__':run()
