"""Package adopted Q7 evidence and plain-language handoff; no research calculations."""
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,read_rows

RUNS={'evaluation':'regional-evaluation-7ea3e4ab7c7dbb8eeb58',
      'diagnostics':'regional-diagnostics-3e4473ad441fd44fe4df',
      'stability':'regional-stability-366606ed5bca8e0fe6b8'}
DOC='研究/07_地区有效性/第七问_研究说明与收尾交接.md'


def build():
    inputs={}
    parents={}
    def record(p):
        inputs[p]=file_hash(ROOT/p)
    for key,rid in RUNS.items():
        folder=f'outputs/logs/regional_effectiveness/{rid}'
        manifest=json.loads((ROOT/folder/'manifest.json').read_text(encoding='utf-8-sig'))
        hand=json.loads((ROOT/folder/'handoff_adoption.json').read_text(encoding='utf-8-sig'))
        if not hand['passed'] or file_hash(ROOT/folder/'manifest.json')!=hand['manifest_sha256']:
            raise ValueError('PARENT_ADOPTION_MISMATCH:'+key)
        if file_hash(ROOT/folder/'independent_audit.json')!=hand['independent_audit_sha256']:
            raise ValueError('PARENT_AUDIT_MISMATCH:'+key)
        for name in ['manifest.json','handoff_adoption.json','independent_audit.json']:
            record(folder+'/'+name)
        parents[key]=manifest
    def take(key,name):
        p=f'outputs/tables/regional_effectiveness/{RUNS[key]}/{name}'
        if file_hash(ROOT/p)!=parents[key]['outputs'][p]:raise ValueError('ADOPTED_TABLE_CHANGED:'+p)
        record(p)
        return read_rows(ROOT/p)
    metrics=take('evaluation','regional_metrics.csv')
    paired=take('evaluation','paired_differences.csv')
    conclusions=take('stability','conclusion_review.csv')
    references=take('stability','reference_sensitivity.csv')
    standard=take('diagnostics','standardized_metrics.csv')
    africa=take('diagnostics','africa_calibration.csv')
    bytarget={r['target_id']:r for r in conclusions}
    if len(bytarget)!=13 or sum(r['evidence']=='sensitive' for r in conclusions)!=4:
        raise ValueError('CONCLUSION_REGISTER_CHANGED')
    if sum(int(r['matches']) for r in metrics if r['scope']=='main' and r['model']=='joint' and r['group'] in ['150','142','002','019','009'])!=9727:
        raise ValueError('MAIN_SAMPLE_CHANGED')
    narrative={
      '150':('T01','历史小幅增量在所查删年删队中保留','不能推及欧洲每个子区域或保证未来'),
      '142':('T02','历史小幅增量在所查删年删队中保留','不能推及亚洲每个子区域或保证未来'),
      '002':('T03;T06;T07;T08;T09','背景增量敏感；残余误差差和两档偏差保留方向','不能宣称整套方法无用、地区因果或已找到偏差原因'),
      '019':('T04','大区历史小幅增量保留；内部排名另行限制','大区结论不认证南美内部比较或每个小区'),
      '009':('T05;T12;T13','原始增量保留；共同构成比较敏感且有支持缺口','148场、小格放大；暂不判整个地区可靠或失效'),
      'SOUTH_AMERICA':('T10;T11','与其余美洲的先后顺序敏感，不作可靠排名','属于美洲补充；地理005不等同CONMEBOL十会员'),
      'OTHER_AMERICAS':('T10;T11','与南美的先后顺序敏感，不作可靠排名','与美洲大区结果重叠，不是独立地区试验'),
      'UNKNOWN':('','本期无比赛，不能评价','保留空项，不替无资料地区作结论')}
    app=[]
    for g,(target_ids,allowed,limits) in narrative.items():
        m=next(r for r in metrics if r['scope']=='main' and r['model']=='joint' and r['group']==g)
        p=next(r for r in paired if r['scope']=='main' and r['reference']=='strength' and r['group']==g)
        app.append(dict(group=g,label=m['label'],matches=int(m['matches']),
            joint_log_loss=float(m['log_loss']) if m['log_loss'] else None,
            joint_minus_strength_loss=float(p['joint_minus_reference_loss']) if p['joint_minus_reference_loss'] else None,
            mean_bias_pp=float(m['bias_pp']) if m['bias_pp'] else None,
            target_ids=target_ids,allowed_statement=allowed,limits=limits,
            future_probability_adjustment='none_adopted',formal_inference=False,human_review=False))
    figures=[]
    for key in ['evaluation','diagnostics']:
        for p,h in parents[key]['outputs'].items():
            if p.endswith('.png'):
                if file_hash(ROOT/p)!=h:raise ValueError('FIGURE_CHANGED:'+p)
                record(p);figures.append(p)
    for p in [DOC,'研究/06_历史参考周期/第六问_研究说明与收尾交接.md',
              '研究/07_地区有效性/第五步_可靠性检查与脚本规划.md']:
        record(p)
    source='scripts/build_regional_effectiveness_materials.py'
    code={p:file_hash(ROOT/p) for p in [source,'src/data_contract.py','src/strength/io.py']}
    identity=dict(inputs=inputs,code=code,source_runs=RUNS,scope='adopted historical diagnosis; not formal future guarantee')
    rid='q7-closeout-'+fingerprint(identity)[:20]
    folder=ROOT/'outputs/logs/regional_effectiveness'/rid
    pointer=ROOT/'outputs/logs/regional_effectiveness/closeout_pointer.json'
    if not (folder/'manifest.json').exists():
        folder.mkdir(parents=True,exist_ok=True)
        atomic_bytes(folder/'applicability.csv',csv_bytes(list(app[0]),app))
        slides=[dict(title='为什么还要问地区？',text='总体有用，未必各地同样好用。承接第六问保留累计默认。'),
                dict(title='怎样比较才公平？',text='同场比较；先看概率判断，再统一两项比赛构成，最后查年份、球队和小格影响。'),
                dict(title='哪些话可以保留？',text='欧亚美洲原增量较稳；非洲偏差值得追查；南美不排可靠名次；大洋洲证据有限。'),
                dict(title='怎样走向未来？',text='先锁定未来预测再看赛果；本问诊断不直接改概率，第九问再单独验证改进。')]
        write_json(folder/'presentation_data.json',dict(material_id=rid,source_runs=RUNS,main_matches=9727,
            applicability=app,slides=slides,figures=figures,stability=conclusions,
            source_standardized=standard,source_africa_bins=africa,reference_sensitivity=references,
            formal_inference=False,new_predictions=False,html_created=False,human_review=False))
        write_json(folder/'paper_support.json',dict(
            method_and_plain_explanation=DOC,source_runs=RUNS,
            source_file_paths=sorted(inputs),
            sections=['前文衔接与问题','同场概率评价','构成及不确定性诊断','关键对象稳健性','适用说明与限制','第八九问交接'],
            mathematical_support=['研究/07_地区有效性/第四步_差异解释与第五步交接.md#3-数学与分组规则',
                                  '研究/07_地区有效性/第五步_可靠性检查与脚本规划.md#5-数学上为什么这样查以及它不能证明什么'],
            not_claimed=['新盲测','完整胜平负','现实95%保证','地区因果识别','正式报告已提交','真人已复核']))
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_STORED) as z:
            for p in [source,DOC]:z.writestr(zipfile.ZipInfo(p,(1980,1,1,0,0,0)),(ROOT/p).read_bytes())
        atomic_bytes(folder/'source_snapshot.zip',b.getvalue())
        write_json(folder/'review.json',dict(passed=True,main_matches=9727,applicability_rows=8,
            source_files_checked=len(inputs),parent_runs_checked=3,prior_independent_audits_verified=True,
            existing_figures_hash_verified=len(figures),new_model_fits=0,new_ratings=0,new_simulations=0,
            no_new_unit_tests_needed=True,html_created=False,human_review=False,
            formal_inference=False,research_closed_in_declared_scope=True,final_group_delivery_complete=False))
        outputs={p.relative_to(ROOT).as_posix():file_hash(p) for p in folder.iterdir() if p.is_file() and p.name!='manifest.json'}
        write_json(folder/'manifest.json',dict(identity=identity,outputs=outputs))
    else:
        for p,h in json.loads((folder/'manifest.json').read_text(encoding='utf-8-sig'))['outputs'].items():
            if file_hash(ROOT/p)!=h:raise ValueError('SEALED_MATERIAL_CHANGED:'+p)
    write_json(pointer,dict(material_id=rid,directory=folder.relative_to(ROOT).as_posix(),
        manifest_sha256=file_hash(folder/'manifest.json'),source_runs=RUNS,steps_completed=[1,2,3,4,5,6],
        research_closed_in_declared_scope=True,final_group_delivery_complete=False,human_review=False,formal_inference=False))
    print('Q7_MATERIALS_COMPLETE',rid,'sources',len(inputs),'applicability',len(app),flush=True)
    return folder


if __name__=='__main__':build()
