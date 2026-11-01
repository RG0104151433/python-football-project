"""Build Q6 explanation materials from adopted results; never run research jobs."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
import argparse
import io
import json
import math
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_contract import atomic_bytes, file_hash, fingerprint, write_json
from src.strength.io import ROOT, environment, read_rows

RUNS = dict(outcome='outcome-0a52e15e2ae493570acb',
            rating='rating-memory-1c8aebdf661ccdddff05',
            joint='joint-review-4888d987645daee73e19',
            reliability='reliability-c3586b1614a4ba59c9c5')
EXPLANATION = '研究/06_历史参考周期/第六问_研究说明与收尾交接.md'
HTML_ENTRY = '研究/06_历史参考周期/展示/index.html'


def load_materials():
    inputs, manifests = {}, {}
    for key, rid in RUNS.items():
        path = f'outputs/logs/history_window/{rid}/manifest.json'
        inputs[path] = file_hash(ROOT/path)
        manifests[key] = json.loads((ROOT/path).read_text(encoding='utf-8-sig'))

    def take(key, filename, table=True, as_csv=True):
        path = f"outputs/{'tables' if table else 'logs'}/history_window/{RUNS[key]}/{filename}"
        actual = file_hash(ROOT/path)
        if manifests[key]['outputs'][path] != actual:
            raise ValueError('MATERIAL_SOURCE_CHANGED:'+path)
        inputs[path] = actual
        return read_rows(ROOT/path) if as_csv else json.loads((ROOT/path).read_text(encoding='utf-8-sig'))

    o = take('outcome', 'group_metrics.csv')
    r = take('rating', 'rating_metrics.csv')
    a = take('outcome', 'adaptive_metrics.csv')
    combos = take('joint', 'combination_metrics.csv')
    costs = take('joint', 'cost_components.csv')
    joint = take('joint', 'conclusions.json', False, False)
    refs = take('reliability', 'conditional_reference.csv')
    sens = take('reliability', 'sensitivity.csv')
    take('reliability', 'simulation_paired_summary.csv')
    take('reliability', 'native_prior_probes.csv')
    conclusion = take('reliability', 'conclusions.json', False, False)
    applicability = take('reliability', 'applicability.json', False, False)
    log = ROOT/'outputs/logs/history_window'/RUNS['reliability']
    handoff = json.loads((log/'handoff_adoption.json').read_text(encoding='utf-8-sig'))
    for name, field in [('manifest.json','manifest_sha256'),
                        ('adoption.json','original_adoption_sha256'),
                        ('handoff_review.json','independent_handoff_review_sha256')]:
        if file_hash(log/name) != handoff[field]:
            raise ValueError('RELIABILITY_HANDOFF_CHANGED:'+name)
        inputs[(log/name).relative_to(ROOT).as_posix()] = file_hash(log/name)
    inputs[(log/'handoff_adoption.json').relative_to(ROOT).as_posix()] = file_hash(log/'handoff_adoption.json')
    for key in ('outcome', 'rating'):
        parent = f'outputs/logs/history_window/{RUNS[key]}/manifest.json'
        if manifests['reliability']['identity']['inputs'][parent] != inputs[parent]:
            raise ValueError('MIXED_SOURCE_GENERATIONS:'+key)
    parent = f"outputs/logs/history_window/{RUNS['joint']}/manifest.json"
    if manifests['reliability']['identity']['inputs'][parent] != inputs[parent]:
        raise ValueError('MIXED_JOINT_GENERATION')

    def one(rows, **where):
        selected = [x for x in rows if all(x[k] == v for k,v in where.items())]
        if len(selected) != 1:
            raise ValueError('EXPECTED_ONE_METRIC:'+str(where))
        if int(selected[0]['matches']) != 9727:
            raise ValueError('MAIN_COHORT_CHANGED')
        return selected[0]

    history = []
    for years in (2, 4, 8, 12, 20, None):
        name = 'cumulative' if years is None else f'{years}y'
        rule = one(o, group='adaptive_evaluation', window=name)
        rating = one(r, group='evaluation', policy_name='cumulative_1950' if years is None else f'annual_reset_{years}y')
        history.append(dict(years=years, label='累计' if years is None else f'{years}年',
                            outcome_history_loss=float(rule['primary_log_loss']),
                            rating_history_loss=float(rating['primary_log_loss'])))
    baseline = history[-1]['outcome_history_loss']
    adaptive = one(a, group='adaptive_evaluation', window='adaptive-prior-years')
    candidates = [x for x in combos if x['scope'] == 'evaluation']
    if len(candidates) != 6 or len(refs) != 13 or not conclusion['baseline_lowest_historical_point']:
        raise ValueError('PUBLISHED_RESULT_SHAPE_CHANGED')
    if not all(x['leave_one_year_sign_stable'] == 'true' for x in refs):
        raise ValueError('LEAVE_YEAR_CLAIM_UNSUPPORTED')
    if not all(float(x['common_non_cold_start_difference']) > 0 for x in refs):
        raise ValueError('COMMON_COLD_START_CLAIM_UNSUPPORTED')
    controlled = {x['outcome_window']:x for x in costs if x['rating_policy'] == 'cumulative_1950'}
    before = float(controlled['cumulative']['outcome_job_seconds'])
    after = float(controlled['12y']['outcome_job_seconds'])
    if abs((1-after/before)-joint['controlled_outcome_compute_saving_fraction']) > 1e-10:
        raise ValueError('COST_CLAIM_UNSUPPORTED')
    special = next(x for x in sens if x['comparison_id']=='R20' and x['diagnostic']=='months_1_2_3')
    if float(special['mean_loss_minus_baseline']) >= 0:
        raise ValueError('QUARTER_EXCEPTION_CHANGED')
    inputs[EXPLANATION] = file_hash(ROOT/EXPLANATION)
    packet = dict(title='预测下一场比赛，过去的比赛应该记住多久？',
                  decision_log_id='R20261101-10', source_runs=RUNS,
                  full_period='2000—2024', full_matches=16599,
                  main_period='2010—2024', main_matches=9727,
                  task='主胜与非主胜的概率判断', history=history,
                  baseline_loss=baseline, adaptive_loss=float(adaptive['primary_log_loss']),
                  joint_evaluation=candidates, outcome_compute_before_seconds=before,
                  outcome_compute_after_seconds=after,
                  compute_saving_fraction=1-after/before,
                  relative_loss_increase=joint['controlled_short_outcome_evaluation_relative_loss_increase'],
                  all13_leave_year_direction_stable=True, all13_common_non_cold_start_direction_stable=True,
                  first_quarter_20year_difference=float(special['mean_loss_minus_baseline']),
                  reliability_conclusion=conclusion, applicability=applicability,
                  explanation=EXPLANATION, human_review=False, teacher_html_permission_confirmed=False,
                  source_paths=list(inputs), published_figures='existing stages retain their own immutable figures')
    return packet, inputs


def history_svg(data):
    """A teaching line chart of published metrics, not a new fitted analysis."""
    low = .55
    high = math.ceil(max(max(x['outcome_history_loss'],x['rating_history_loss']) for x in data)*100)/100
    width, height = 800, 335
    x = lambda i: 102+i*127
    y = lambda value: 263-(value-low)/(high-low)*212
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-labelledby="plotTitle plotDesc">',
             '<title id="plotTitle">不同历史长度的平均概率扣分</title>',
             '<desc id="plotDesc">同一9727场比赛；两条线分别只改变球队评分历史、只改变预测经验历史；越低越好。这是已核验历史结果，不是胜率或未来保证。</desc>']
    for i in range(5):
        tick = low+(high-low)*i/4
        parts.append(f'<line x1="90" x2="755" y1="{y(tick):.2f}" y2="{y(tick):.2f}" stroke="#d7dedc"/><text x="78" y="{y(tick)+5:.2f}" text-anchor="end" class="axis">{tick:.3f}</text>')
    for field, color, label, legend_x in [('outcome_history_loss','#087e8b','改变预测经验历史',108),
                                          ('rating_history_loss','#b4602b','改变球队评分历史',435)]:
        points = ' '.join(f'{x(i)},{y(r[field]):.2f}' for i,r in enumerate(data))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
        for i,r in enumerate(data):
            parts.append(f'<circle cx="{x(i)}" cy="{y(r[field]):.2f}" r="5" fill="{color}"><title>{r["label"]}：{r[field]:.6f}</title></circle>')
        parts.append(f'<line x1="{legend_x}" x2="{legend_x+25}" y1="23" y2="23" stroke="{color}" stroke-width="3"/><text x="{legend_x+33}" y="28" class="axis">{label}</text>')
    for i,r in enumerate(data):
        parts.append(f'<text x="{x(i)}" y="290" text-anchor="middle" class="axis">{r["label"]}</text>')
    parts.append('<text x="420" y="324" text-anchor="middle" class="axis">参考的历史长度</text></svg>')
    return ''.join(parts)


def html_page(p, material_id):
    plot = history_svg(p['history'])
    sources = ''.join(f'<li><code>{escape(path)}</code></li>' for path in p['source_paths'])
    payload = json.dumps(p, ensure_ascii=False, allow_nan=False).replace('<', '\u003c')
    return '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>第六问｜过去的比赛应该记住多久</title><style>
:root{color-scheme:light;--ink:#153b3a;--muted:#526766;--accent:#087e8b;--paper:#f5f7f3}*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei","PingFang SC",sans-serif;line-height:1.65}
header,main,footer{max-width:1180px;margin:auto;padding:18px 34px}header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ccd5d0}
button{font:inherit;color:var(--ink);background:white;border:1px solid #90aaa6;border-radius:5px;padding:6px 14px;cursor:pointer}button:focus-visible,a:focus-visible{outline:3px solid var(--accent);outline-offset:3px}button:disabled{opacity:.4;cursor:default}
.page{min-height:570px;padding:18px 0 8px;border-bottom:1px solid #ccd5d0}.js .page[hidden]{display:none}h1{font-size:clamp(29px,3.7vw,45px);line-height:1.3;margin:10px 0 20px;max-width:1000px}h2{font-size:28px;margin:12px 0}p,li{font-size:21px}p{max-width:1000px}.eyebrow,.caption{font-size:15px;color:var(--muted)}.lede{font-size:25px;max-width:920px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:36px}.rule{padding:16px 0;border-top:2px solid #9abbb7}.number{font-size:46px;font-weight:700;letter-spacing:-1px}.accent{color:var(--accent)}.flow{display:flex;gap:16px;align-items:center;flex-wrap:wrap;font-size:20px;margin:24px 0}.flow span{border-bottom:2px solid var(--accent);padding:5px 0}.note{font-size:17px;border-left:4px solid #b4602b;padding:6px 18px}.axis{font-size:17px;fill:#284b49}svg{width:100%;max-height:355px}figure{margin:8px 0 0}figcaption{font-size:15px;color:var(--muted)}.facts{display:flex;gap:38px;flex-wrap:wrap}.facts p{font-size:17px}.facts strong{display:block;font-size:30px}details{margin:20px 0;font-size:17px}details li{font-size:15px;overflow-wrap:anywhere}code{font-size:13px;overflow-wrap:anywhere}a{color:var(--accent)}footer{font-size:13px;color:var(--muted);overflow-wrap:anywhere}.controls{display:flex;gap:8px;align-items:center}.page ol{padding-left:28px}.page li{margin:10px 0}
@media(max-width:740px){header,main,footer{padding:14px 20px}.columns{grid-template-columns:1fr;gap:10px}.page{min-height:auto}p,li{font-size:18px}.lede{font-size:21px}header{flex-wrap:wrap;gap:10px}.number{font-size:36px}}
@media print{header .controls{display:none}.page,.js .page[hidden]{display:block!important;min-height:0;break-after:page;border:0}body{background:white}details{display:block}footer{font-size:10px}.page:last-child{break-after:auto}}
</style></head><body><header><span>国际足球研究 · 第六问</span><nav class="controls" aria-label="页面控制"><button id="prev" type="button">上一屏</button><span id="counter" aria-live="polite">1 / 4</span><button id="next" type="button">下一屏</button><button id="fullscreen" type="button">全屏</button></nav></header><main>
<section class="page" id="page1" aria-labelledby="title1"><p class="eyebrow">01 / 从前面的发现，继续追问</p><h1 id="title1">判断实力很重要。<br>但过去的比赛，应该记住多久？</h1><p class="lede">球队会换球员、换教练，旧成绩可能过时；只看最近，比赛又太少，几次意外就可能带偏判断。</p><div class="columns"><div class="rule"><h2>判断球队现在多强</h2><p>既要跟上变化，也要避免输一场就把实力看得太低。</p></div><div class="rule"><h2>积累怎样预测的经验</h2><p>从过去很多比赛，学习怎样结合双方强弱、主场和赛事情况。</p></div></div><p class="note">两种历史用途，未必应该保留同样长。原来的实力判断本来就会随新赛果变化，累计不等于旧比赛永远同权。</p></section>
<section class="page" id="page2" aria-labelledby="title2"><p class="eyebrow">02 / 公平地比，而不只凭直觉</p><h1 id="title2">参考2年到20年，还是继续积累？</h1><div class="flow"><span>只看此前的比赛</span><b>→</b><span>给下一场判断</span><b>→</b><span>真实结果出现</span><b>→</b><span>再影响后面的判断</span></div><p>先分别改变两种历史，再比较少量组合。所有办法面对同样的比赛；“过度自信地判断错”会扣更多分，分数越低越好。</p><div class="facts"><p><strong>16,599 场</strong>2000—2024完整比较</p><p><strong>9,727 场</strong>2010—2024主要后段比较</p><p><strong>另做模拟</strong>设定球队实力不变、渐变或突然下滑</p></div><p class="note">这些都是已研究过的历史。保持时间顺序，不等于新的未来盲测。有限评分在年初重建、年内更新，不是每场严格只留整整W年。</p></section>
<section class="page" id="page3" aria-labelledby="title3"><p class="eyebrow">03 / 主要发现</p><h1 id="title3">主动忘掉旧资料，这次没有改善总体预测</h1><div class="columns"><figure>''' + plot + '''<figcaption>平均概率扣分（对数损失），越低越好；同一9,727场。点线图纵轴从0.55起，比较的是损失，不是胜率。来源：训练/评分历史比较已封存表。</figcaption></figure><div><p>两年、四年的历史总体较差；长一些的办法较接近，累计办法整体最好。每年追随过去表现较好的年限，也没有超过它。</p><div class="rule"><div class="number accent">''' + f"{p['compute_saving_fraction']*100:.0f}%" + '''</div><p>只把积累预测经验的资料缩到12年，可省这一部分约三分之二计算；但平均概率损失相对增加约''' + f"{p['relative_loss_increase']*100:.2f}%" + '''。</p></div></div></div><p class="note">省时只指同一批次中总结预测规律的计算，不是全系统；损失增加不是准确率下降，也没有因此宣布12年方案完全等效。</p></section>
<section class="page" id="page4" aria-labelledby="title4"><p class="eyebrow">04 / 结论能说到哪里</p><h1 id="title4">保留原办法，但不宣布一个普适的最佳年数</h1><ol><li>去掉任一年的评价成绩，或排除双方历史记录不足的比赛，整体方向仍保持；个别年份、第一季度仍有其他办法较好。</li><li>现有不确定性方法给出的范围太宽，无法认证这些小差距；局部初始设定也有影响，不能保证未来显著最好。</li><li>模拟中的较短历史有时更会追踪变化，但设定有限，不能直接推广为真实球队统一的换代周期。</li></ol><p class="lede accent">接下来：这个总体表现较好的办法，在不同地区是否同样好用？</p><p class="caption">第七问将比较各地区的预测表现与高估、低估，区别于第三问“哪里主队胜率高”。</p><details><summary>方法和出处（答辩时展开）</summary><p class="caption">对象为主胜与非主胜；球队评分按日先预测后更新，总结规律按年只看过去。2000—2009为开发历史，后段主比较仍被研究复用。概率裁剪10⁻⁶；13项同基准比较，原60槽位条件界未获得现实覆盖准入。独立模拟重复单位为10个种子组，非60个独立世界。全期下游初始化、真正未来盲测、损失容忍预算和全流程计时均未全面验证。</p><ul>''' + sources + '''</ul></details></section>
</main><footer>材料身份：''' + material_id + ''' · 固定结果展示；无在线数据请求 · 最终载体许可与投影排练须另行确认。</footer><script id="material-data" type="application/json">''' + payload + '''</script><script>
(()=>{'use strict';const pages=Array.from(document.querySelectorAll('.page'));let index=0;document.documentElement.classList.add('js');const prev=document.getElementById('prev'),next=document.getElementById('next');function show(i){index=Math.max(0,Math.min(pages.length-1,i));pages.forEach((p,n)=>p.hidden=n!==index);prev.disabled=index===0;next.disabled=index===pages.length-1;document.getElementById('counter').textContent=(index+1)+' / '+pages.length;}prev.addEventListener('click',()=>show(index-1));next.addEventListener('click',()=>show(index+1));document.addEventListener('keydown',event=>{if(event.altKey||event.ctrlKey||event.metaKey||['INPUT','TEXTAREA','SELECT','BUTTON','SUMMARY'].includes(event.target.tagName)||event.target.isContentEditable)return;if(['ArrowRight','PageDown','ArrowLeft','PageUp','Home','End'].includes(event.key)){event.preventDefault();if(['ArrowRight','PageDown'].includes(event.key))show(index+1);else if(['ArrowLeft','PageUp'].includes(event.key))show(index-1);else show(event.key==='Home'?0:pages.length-1);}});document.getElementById('fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else if(document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();}catch(error){document.getElementById('counter').textContent='请使用浏览器全屏键；当前 '+(index+1)+' / '+pages.length;}});show(0);})();
</script></body></html>'''


class Inspect(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.remote=[]; self.controls=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='button':self.controls.append(attrs.get('id'))
        for key in ('src','href'):
            if attrs.get(key,'').startswith(('http:', 'https:', '//')):self.remote.append(attrs[key])


def build():
    p, inputs = load_materials()
    this_path=Path(__file__).resolve()
    code_paths=[this_path,ROOT/'src/data_contract.py',ROOT/'src/strength/io.py']
    identity=dict(inputs=inputs, code={x.relative_to(ROOT).as_posix():file_hash(x) for x in code_paths},
                  environment=environment(), purpose='Q6 step8 explanation and material archive; no refitting')
    material_id='q6-closeout-'+fingerprint(identity)[:20]
    folder=ROOT/'outputs/logs/history_window_closeout'/material_id
    if (folder/'manifest.json').exists():
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8-sig'))
        for path,h in manifest['outputs'].items():
            if file_hash(ROOT/path)!=h:raise ValueError('CLOSEOUT_ARTIFACT_CHANGED:'+path)
        atomic_bytes(ROOT/HTML_ENTRY,(folder/'index.html').read_bytes())
        write_json(ROOT/'outputs/logs/history_window_closeout/current.json',dict(material_id=material_id,
            directory=folder.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(folder/'manifest.json'),
            html_entry=HTML_ENTRY,html_sha256=file_hash(ROOT/HTML_ENTRY),source_runs=RUNS,
            research_closed_in_declared_scope=True,final_group_delivery_complete=False,human_review=False))
        print('Q6_MATERIALS_VERIFIED',material_id,flush=True)
        return folder
    folder.mkdir(parents=True,exist_ok=True)
    page=html_page(p,material_id)
    inspection=Inspect();inspection.feed(page)
    if (len(inspection.ids)!=len(set(inspection.ids)) or inspection.remote or
            not all(x in inspection.ids for x in ['page1','page2','page3','page4','material-data'])
            or set(inspection.controls)!={'prev','next','fullscreen'} or len(page.encode('utf-8'))>65000):
        raise ValueError('HTML_STATIC_CHECK_FAILED')
    atomic_bytes(folder/'index.html',page.encode('utf-8'))
    write_json(folder/'presentation_data.json',p)
    write_json(folder/'paper_support.json',dict(explanation=EXPLANATION,
        sections=['前文联系与两个历史用途','向前比较的边界与概率评价','两层历史、选窗与六组合结果',
                  '计算取舍','敏感性、理论分辨力和未准入范围','保留默认与地区有效性交接'],
        source_runs=RUNS,existing_files=list(inputs),
        prohibited_claims=['现实唯一最佳年限','未来95%准确或覆盖保证','未显著所以等效',
                           '全系统省时66%','准确率下降0.36个百分点','单日初值检查认证完整流程'],
        course_report_submitted=False,human_review=False))
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
        for source in code_paths+[ROOT/EXPLANATION]:
            z.writestr(zipfile.ZipInfo(source.relative_to(ROOT).as_posix(),(1980,1,1,0,0,0)),source.read_bytes())
    atomic_bytes(folder/'source_snapshot.zip',archive.getvalue())
    write_json(folder/'review.json',dict(passed=True,scope='sealed sources, exact source cohorts, published claims and basic offline HTML structure',
        source_runs=RUNS,main_matches=9727,source_files=len(inputs),html_pages=4,html_bytes=len(page.encode('utf-8')),
        unique_ids=True,no_remote_assets=True,controls_present=True,model_fits=0,scoring_replays=0,simulations=0,
        browser_runtime_checked=False,projector_checked=False,human_review=False))
    outputs={f.relative_to(ROOT).as_posix():file_hash(f) for f in folder.iterdir() if f.is_file()}
    write_json(folder/'manifest.json',dict(identity=identity,outputs=outputs))
    atomic_bytes(ROOT/HTML_ENTRY,(folder/'index.html').read_bytes())
    write_json(ROOT/'outputs/logs/history_window_closeout/current.json',dict(material_id=material_id,
        directory=folder.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(folder/'manifest.json'),
        html_entry=HTML_ENTRY,html_sha256=file_hash(ROOT/HTML_ENTRY),source_runs=RUNS,
        research_closed_in_declared_scope=True,final_group_delivery_complete=False,human_review=False))
    print('Q6_MATERIALS_COMPLETE',material_id,'html_bytes',len(page.encode('utf-8')),flush=True)
    return folder


if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()
