"""Build Q5 scientific figures, offline HTML and report-ready narrative."""
from pathlib import Path
import csv,html,io,json,re,zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,environment


MAIN_LABELS={
 'Q1:2010s_minus_1980s:adjusted':'2010年代 − 1980年代',
 'Q1:2020_2024_minus_1980s:adjusted':'2020—2024 − 1980年代',
 'Q2:difference:overall:all:era_standardized':'友谊赛 − 其他赛事'}
MODEL_LABELS={'M0_nested':'仅背景','M1_strength':'仅实力','M3_nested':'实力＋背景'}


def read(path):return list(csv.DictReader(Path(path).open(encoding='utf-8-sig')))


def gather(stage='final'):
    base=ROOT/'outputs/logs/strength_inference'
    cp=json.loads((base/'comparison_pointer.json').read_text());comparison=ROOT/cp['directory']
    suffix='_first_stage' if stage=='initial' else ''
    decision=json.loads((comparison/('scope_decision'+suffix+'.json')).read_text())
    prediction=json.loads((base/'prediction_pointer.json').read_text());pd=ROOT/prediction['directory']
    audit=json.loads((base/'prediction_audit.json').read_text())
    if not audit['passed']:raise ValueError('FORECAST_AUDIT_REQUIRED')
    forecast_protocol=json.loads((pd/'protocol.json').read_text())
    if not forecast_protocol.get('geographic_encoding_weights_use_past_only'):raise ValueError('PAST_ONLY_ENCODING_REQUIRED')
    ranges=read(comparison/('scope_reference_ranges'+suffix+'.csv'))
    comparisons=read(comparison/('scope_method_comparison'+suffix+'.csv'))
    groups=read(pd/'group_metrics.csv');years=read(pd/'yearly_metrics.csv')
    all_metrics=[r for r in groups if r['group']=='all']
    geography=json.loads((ROOT/'config/regions_study.json').read_text(encoding='utf-8-sig'))
    registry=read(ROOT/'outputs/tables/strength_joint/stage6-preparation-662dd5a756b8c1bf7688/target_registry.csv')
    byid={r['registry_id']:r for r in ranges};dispositions=[]
    for r in registry:
        primary=byid.get(r['registry_id'])
        if primary:status=primary['status'];reason='30族固定生成机制参照' if status=='MODEL_CONDITIONAL_REFERENCE' else '独立模拟标准精度未达到0.25pp'
        elif r['family']=='F_AUX_REFERENCE':status='AUXILIARY_SENSITIVITY_ONLY';reason='较窄参考改变目标人群；保留描述及敏感性，不套用全参考范围'
        elif r['family']=='F_EXPLORATORY_RELATIONS':status='EXPLORATORY_NOT_CONFIRMATORY';reason='赛事斜率与25点曲线为探索假说；无新增确认性区间'
        elif r['family']=='F_DESCRIPTIVE_FIT':status='TRAINING_FIT_DESCRIPTION_ONLY';reason='样本内拟合比较；不能冒充预测验证'
        elif r['family']=='F_EXTRAPOLATION_ONLY':status='UNSUPPORTED_EXTRAPOLATION_ONLY';reason='原缺层外推；模型有数值不补出实际支持'
        else:raise ValueError('UNREGISTERED_FAMILY: '+r['family'])
        dispositions.append(dict(registry_id=r['registry_id'],family=r['family'],target_id=r['target_id'],axis=r['effect_size_axis'],
            estimate=r['estimate'],unit=r['unit'],status=status,reason=reason,human_review=False))
    if len(dispositions)!=143:raise ValueError('ALL_OBJECT_INVENTORY_CHANGED')
    confirmation=dict(new_worlds=0,current_stop='initial_screen_only_not_final') if stage=='initial' else json.loads((comparison/'confirmation_result.json').read_text())
    return dict(schema_version='q5-closeout-materials-v1',decision_log_id='R20261031-05' if stage=='initial' else 'R20261031-06',layout_preview=stage=='initial',
        sample_matches=24917,learning_matches=38919,prediction_matches=21413,prediction_period='1990—2024',
        fresh_confirmation=confirmation,complete_worlds=264+confirmation['new_worlds'],
        comparison=cp['directory'],prediction=prediction['directory'],decision=decision,
        ranges=ranges,all_object_dispositions=dispositions,method_comparison=comparisons,prediction_metrics=all_metrics,prediction_group_metrics=groups,yearly_metrics=years,
        prediction_audit=audit,baseline_stage6_delivery='outputs/logs/strength_stage6/delivery-618a9dd942fad38863e6',
        region_labels={'Q3:'+r['id']+':adjusted':r['label'] for r in geography['comparisons']},
        nominal_reference_level=.95,unconditional_coverage_certified=False,new_blind_future_test=False,
        full_WDL_prediction=False,teacher_HTML_permission_confirmed=False,actual_human_review=False,actual_browser_validation=False)


def configure_figures():
    for family in ('Microsoft YaHei','Noto Sans CJK SC','SimHei','WenQuanYi Micro Hei'):
        try:font=font_manager.findfont(family,fallback_to_default=False);break
        except ValueError:continue
    else:raise ValueError('缺少可用中文字体；可直接使用已保存的HTML/图，需要重绘时先配置中文字体。')
    plt.rcParams.update({'font.family':family,'axes.unicode_minus':False,'svg.hashsalt':'q5-closeout-v1',
        'font.size':13,'axes.titlesize':20,'axes.labelsize':14,'axes.spines.top':False,'axes.spines.right':False,
        'figure.facecolor':'white','axes.facecolor':'white'})
    return font


def save(fig,folder,name):
    folder.mkdir(parents=True,exist_ok=True)
    fig.savefig(folder/(name+'.png'),dpi=120,bbox_inches='tight')
    fig.savefig(folder/(name+'.svg'),metadata={'Date':None},bbox_inches='tight')
    plt.close(fig)


def figures(data,folder):
    records={r['model_id']:r for r in data['prediction_metrics']};models=['M0_nested','M1_strength','M3_nested']
    fig,axes=plt.subplots(1,2,figsize=(16,7));colors=['#929ba4','#637a8b','#245a78']
    for ax,field,title in [(axes[0],'log_loss','概率预测对数损失（越低越好）'),(axes[1],'binary_accuracy','主胜 / 非主胜准确率')]:
        values=[float(records[m][field])*(100 if field=='binary_accuracy' else 1) for m in models]
        bars=ax.bar([MODEL_LABELS[m] for m in models],values,color=colors,width=.6)
        ax.set_title(title,pad=18);ax.set_ylabel('百分比（%）' if field=='binary_accuracy' else '平均对数损失（nats / 场）')
        ax.set_ylim(0,80 if field=='binary_accuracy' else .78)
        for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value+.015*(80 if field=='binary_accuracy' else .78),f'{value:.2f}%' if field=='binary_accuracy' else f'{value:.4f}',ha='center')
    fig.suptitle('实力是主要预测信息，背景提供较小增量',fontsize=23)
    fig.text(.5,.005,'1990—2024｜21,413场｜按年向前拟合｜研究规则曾复用历史，不是新增盲测',ha='center',fontsize=11)
    fig.tight_layout(rect=[0,.055,1,.95]);save(fig,folder,'prediction_comparison')
    ys={m:{int(r['year']):float(r['log_loss']) for r in data['yearly_metrics'] if r['model_id']==m} for m in models}
    years=list(range(1990,2025));delta=[ys['M3_nested'][y]-ys['M1_strength'][y] for y in years]
    fig,ax=plt.subplots(figsize=(16,7));ax.plot(years,delta,color='#245a78',marker='o',markersize=4)
    ax.axhline(0,color='#333333',linewidth=1);ax.set_xlabel('预测年份');ax.set_ylabel('联合模型 − 仅实力模型：平均对数损失差（nats / 场）')
    ax.set_title('背景信息的增量随年份变化；负值表示联合模型更好',pad=18)
    fig.text(.5,.015,f"35年中{data['prediction_audit']['joint_beats_strength_years']}年改善；点之间是历史年度比较，不是35次独立显著性检验。来源：yearly_metrics.csv",ha='center',fontsize=11)
    fig.tight_layout(rect=[0,.055,1,1]);save(fig,folder,'yearly_increment')
    chosen=[r for axis in ('level','paired_change') for r in data['ranges'] if r['axis']==axis and r['target_id'] in MAIN_LABELS]
    fig,ax=plt.subplots(figsize=(16,8));labels=[]
    for i,r in enumerate(chosen):
        v=float(r['estimate_pp']);labels.append(MAIN_LABELS[r['target_id']]+('｜实力后差异' if r['axis']=='level' else '｜相对背景模型的变化'))
        if r['status']=='MODEL_CONDITIONAL_REFERENCE':
            lo,hi=float(r['lower_pp']),float(r['upper_pp']);ax.plot([lo,hi],[i,i],color='#245a78',linewidth=3)
        ax.scatter([v],[i],color='#245a78' if r['axis']=='level' else '#616b72',s=45,zorder=3)
    ax.axvline(0,color='#333333',linewidth=1);ax.set_yticks(range(len(labels)),labels);ax.invert_yaxis();ax.set_xlabel('差异或差异变化（百分点）')
    ax.set_title('年代与赛事比较：点估计与本轮获准的模型条件参照',pad=18)
    fig.text(.5,.015,'线段为获准时的名义95%模型条件参照；非真实无条件保证、非因果效应，也不是原始主胜率。',ha='center',fontsize=11)
    fig.tight_layout(rect=[0,.055,1,1]);save(fig,folder,'main_reference_ranges')
    levels=[r for r in data['ranges'] if r['axis']=='level']
    fig,ax=plt.subplots(figsize=(16,13));labels=[]
    for i,r in enumerate(levels):
        value=float(r['estimate_pp']);labels.append(MAIN_LABELS.get(r['target_id'],data['region_labels'].get(r['target_id'],r['target_id'])))
        if r['status']=='MODEL_CONDITIONAL_REFERENCE':ax.plot([float(r['lower_pp']),float(r['upper_pp'])],[i,i],color='#245a78',linewidth=2)
        ax.scatter([value],[i],s=25,color='#245a78',zorder=3)
    ax.axvline(0,color='#333333',linewidth=1);ax.set_yticks(range(len(labels)),labels,fontsize=11);ax.invert_yaxis()
    ax.set_xlabel('加入实力后，第一组减第二组的模型主胜概率差（百分点）');ax.set_title('全部27个主要实力后差异：不按结果挑选地区',pad=18)
    fig.text(.5,.01,'固定全参考、两预定机制的名义95%模型条件参照；非真实无条件保证，原缺层对象不升格为已支持。',ha='center',fontsize=11)
    fig.tight_layout(rect=[0,.04,1,1]);save(fig,folder,'all_level_reference_ranges')
    fig,ax=plt.subplots(figsize=(16,7));labels=[]
    for i,r in enumerate(data['method_comparison']):
        fresh=bool(r.get('new_stream_worlds'));n=int(r['new_stream_worlds']) if fresh else int(r['planned'])
        k=int(r['new_stream_contained']) if fresh else int(r['joint_contained'])
        rate=100*k/n;lower=float(r['one_sided_MC_lower'])*100
        ax.plot([lower,rate],[i,i],color='#245a78',linewidth=3);ax.scatter([rate],[i],color='#245a78',s=45)
        labels.append(('独立日期机制' if r['scenario']=='conditional_independent_dates' else '同日共同冲击')+'｜路线'+r['route']+('（新流）' if fresh else ''))
        ax.text(101,i,f" {k}/{n}",va='center',fontsize=12)
    lower_limit=min(float(r['one_sided_MC_lower'])*100 for r in data['method_comparison'])-2
    ax.axvline(93,color='#777777',linestyle='--',label='事前MC下限门槛93%');ax.set_xlim(max(0,lower_limit),104)
    ax.set_yticks(range(len(labels)),labels);ax.invert_yaxis();ax.set_xlabel('30目标共同包含（%）；左端为初轮精确下限 / 补充新流顺序下限')
    ax.set_title('方法可靠性检查：每一整个历史才算一次验证',pad=18);ax.legend(loc='center left')
    fig.text(.5,.015,'同日情景保留初轮63/64失败，后两行采用新流；下限各自预算见方法，不是比赛预测准确率。来源：scope_method_comparison.csv',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.055,1,1]);save(fig,folder,'route_validation')


def svg(folder,name):
    text=(folder/(name+'.svg')).read_text(encoding='utf-8');text=text[text.index('<svg'):]
    # Matplotlib reuses IDs such as figure_1 and glyph names in every SVG.
    # Namespace BOTH definitions and references before combining five SVGs.
    prefix='q5-'+name+'-'
    for ident in re.findall(r'\bid="([^"]+)"',text):
        text=text.replace('id="'+ident+'"','id="'+prefix+ident+'"')
        text=text.replace('href="#'+ident+'"','href="#'+prefix+ident+'"')
        text=text.replace('url(#'+ident+')','url(#'+prefix+ident+')')
    return text


def render_html(data,figure_folder,root_prefix='../../../'):
    audit=data['prediction_audit'];decision=data['decision'];route=decision['selected_route']
    metrics={r['model_id']:r for r in data['prediction_metrics']}
    group={(r['model_id'],r['group']):r for r in data['prediction_group_metrics']}
    payload=json.dumps(data,ensure_ascii=False).replace('</','<\\/')
    selected='路线'+route if route else '未采用正式范围方法'
    choice_note='B全流程仅约9%的节省，未达到事前20%的替代门槛，保留完整非线性A。' if route=='A' else '当前尚未全部准入；B全流程仅约9%的节省，仍保留A为优先工程候选。'
    preview='<p style="margin:0;padding:6px 4vw;background:#fff0cd;font-size:14px">初轮真实数据的布局预览：初轮未整体准入，新流仍在运行；此页不是最终交付。</p>' if data.get('layout_preview') else ''
    body=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>第五问｜实力、预测与可靠性</title><style>
    :root{{--ink:#173447;--muted:#536572;--line:#d8e0e5;--accent:#245a78;--paper:#f6f8f9}}
    *{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:18px/1.55 "Microsoft YaHei",system-ui,sans-serif}}
    header{{display:flex;justify-content:space-between;align-items:center;padding:14px 4vw;border-bottom:1px solid var(--line);background:white}}
    .project{{font-size:15px;color:var(--muted)}}nav{{display:flex;gap:12px;align-items:center}}button{{font:inherit;font-size:15px;background:white;border:1px solid var(--line);border-radius:4px;padding:7px 15px;color:var(--ink);cursor:pointer}}
    button:hover,button:focus-visible{{border-color:var(--accent)}}main{{max-width:1540px;margin:auto}}.slide{{padding:25px 4vw 20px;min-height:calc(100vh - 77px)}}.slide[hidden]{{display:none}}
    .eyebrow{{font-size:14px;color:var(--muted);letter-spacing:1px}}h1{{font-size:clamp(27px,3.2vw,43px);line-height:1.25;margin:10px 0 18px}}h2{{font-size:25px;margin:10px 0}}p{{margin:8px 0 14px}}
    .lead{{font-size:clamp(18px,1.7vw,23px);max-width:1100px}}.numbers{{display:flex;gap:38px;margin:15px 0 12px;flex-wrap:wrap}}.number{{font-size:35px;font-weight:650;line-height:1.1}}.caption{{font-size:14px;color:var(--muted);max-width:1000px}}
    .figure{{background:white;margin:18px 0 8px;padding:8px 15px;max-height:56vh;overflow:hidden}}.figure svg{{display:block;width:100%;height:auto;max-height:54vh}}
    .split{{display:block}}.split .figure{{max-height:40vh}}.split .figure svg{{max-height:38vh}}.explanations{{display:grid;grid-template-columns:repeat(3,1fr);gap:25px}}.open{{padding:10px 0;border-top:1px solid var(--line)}}.small{{font-size:16px}}.note{{border-left:3px solid var(--accent);padding:10px 17px;background:white;margin-top:15px}}
    footer{{color:var(--muted);font-size:13px;padding:10px 4vw}}dialog{{border:1px solid var(--line);max-width:1000px;width:90vw;max-height:85vh;padding:26px;overflow:auto}}dialog::backdrop{{background:#172c3a77}}
    .appendix-figure svg{{width:100%;height:auto}}a{{color:var(--accent)}}@media(max-width:900px){{.explanations{{grid-template-columns:1fr}}.figure,.split .figure{{max-height:none}}.figure svg,.split .figure svg{{max-height:none}}.numbers{{gap:20px}}header{{align-items:flex-start;gap:12px;flex-wrap:wrap}}nav{{gap:6px;flex-wrap:wrap}}}}
    @media print{{header,footer,.controls{{display:none}}.slide,.slide[hidden]{{display:block!important;min-height:0;page-break-after:always;padding:10mm}}.figure,.figure svg,.split .figure,.split .figure svg{{max-height:none}}body{{background:white;font-size:13px}}h1{{font-size:25px}}.number{{font-size:25px}}}}
    </style></head><body>{preview}<header><div><strong>国家队主队表现研究</strong><div class="project">第五问：把实力作为正式因素</div></div><nav aria-label="展示导航"><button id="previous" aria-label="上一页">上一页</button><span id="page" aria-live="polite">1 / 3</span><button id="next" aria-label="下一页">下一页</button><button id="appendixButton">方法与来源</button><button id="full">全屏</button></nav></header><main>
    <section class="slide" data-page="1"><div class="eyebrow">预测增量｜1990—2024，逐年只用过去拟合</div><h1>实力提供主要信息，背景还有多少增量？</h1>
    <p class="lead">在21,413场历史向前预测中，实力＋背景相对仅背景的对数损失下降{100*audit['background_to_joint_relative_loss_reduction']:.1f}%；在仅实力基础上的进一步改善为{100*audit['strength_to_joint_relative_loss_reduction']:.2f}%。</p>
    <div class="numbers"><div><div class="number">{100*float(metrics['M3_nested']['binary_accuracy']):.2f}%</div><div class="caption">主胜 / 非主胜准确率</div></div><div><div class="number">{audit['joint_beats_strength_years']} / 35 年</div><div class="caption">背景在实力之上改善对数损失</div></div><div><div class="number">21,413 场</div><div class="caption">三个方案使用相同预测样本</div></div></div>
    <div class="figure" role="img" aria-label="三种方案的逐年向前预测损失与二元准确率">{svg(figure_folder,'prediction_comparison')}</div>
    <p class="caption">背景还改善了场景偏差：友谊赛平均主胜偏差由{float(group['M1_strength','tournament_group:friendly']['calibration_bias_pp']):+.2f}降至{float(group['M3_nested','tournament_group:friendly']['calibration_bias_pp']):+.2f}个百分点；欧洲由{float(group['M1_strength','home_region:150']['calibration_bias_pp']):+.2f}变为{float(group['M3_nested','home_region:150']['calibration_bias_pp']):+.2f}。这是回顾性滚动验证，不是新增盲测或完整胜平负准确率。</p></section>
    <section class="slide" data-page="2" hidden><div class="eyebrow">研究解释｜同一24,917场、同一比较参考</div><h1>历史上的差异，不能只靠胜率排名解释</h1>
    <p class="lead">年代、赛事与地域的差异需要和双方赛前实力一起看。下方年代与赛事的六项参照均跨零，不能把点估计方向说成稳定规律；前后变化也不是因果贡献比例。</p>
    <div class="figure" role="img" aria-label="年代与赛事的模型点估计和获准模型条件参照">{svg(figure_folder,'main_reference_ranges')}</div>
    <div class="note small">保留原54个主要对象。当前获准名义95%模型条件参照：{decision['admitted_targets']}项；未获准：{decision['withheld_targets']}项。24个地域前后变化的模拟标准精度不足，保留描述，不添加统计星号。</div></section>
    <section class="slide" data-page="3" hidden><div class="eyebrow">可靠性与交接｜最终采用判断</div><h1>{selected}：结论写到证据支持的位置</h1>
    <div class="split"><div><div class="figure" role="img" aria-label="两条路线在完整模拟历史上的锁定检验">{svg(figure_folder,'route_validation')}</div></div><div class="explanations">
    <div class="open"><h2>两条路线检查同一件事</h2><p class="small">A重新生成并学习完整历史、重拟合两模型；B保留整段历史得分作一阶近似。两者共用目标、参考和独立标准答案。{choice_note}</p></div>
    <div class="open"><h2>保留三层判断</h2><p class="small">计算是否正确、模拟条件下的范围是否合格、真实未来是否预测得更好，分别回答。历史滚动表现不能证明未知未来准确率。</p></div>
    <div class="open"><h2>下一问：该参考多久的历史？</h2><p class="small">先区分“评分记忆长度”和“共同模型训练年限”，再用同一向前评价协议比较，避免一次改动多个因素。</p></div></div></div>
    <p class="caption">范围针对两种预定生成机制；不是所有真实足球规律、所有相关强度或历史模型选择后的无条件95%保证。</p></section></main>
    <footer>← → / PageUp PageDown 切页 · F 全屏 · 方法与来源含额外年度图。第五问建议讲述约90秒；整组总时长仍按课程10分钟安排。</footer>
    <dialog id="appendix"><button id="closeAppendix" class="controls">关闭</button><h2>方法、证据与使用范围</h2><p>数据：24,917场非中立国家队比赛（1980—2024）；评分学习从1950开始，共38,919场。主客双方都提供学习信息。</p>
    <p>统一标准：有实力模型参数来自固定生成器；无实力对照是独立完整历史期望损失的投影，不由删去实力系数获得。</p><p>30项报告族的设定由目标类型和独立模拟真值精度决定，在锁定验证历史之前记录；原54族整体不准入。模拟重复的独立单位是完整历史。</p>
    <p>已生成{data['complete_worlds']}个独立完整历史，含80个真值、56个校准、128个首轮验证及{data['fresh_confirmation']['new_worlds']}个新流确认。首轮同日情景63/64未达MC下限门槛，保留失败后按扣除旧检验错误预算的新流顺序检验确认，未改模型或宽度。</p>
    <p>此处的范围是固定插件生成器下的模型条件参照；MC真值余量采用独立世界CLT/t近似。没有证明未知真实分布、历史选型或每个外层重新校准后的无条件覆盖。</p>
    <div class="appendix-figure">{svg(figure_folder,'yearly_increment')}</div>
    <div class="appendix-figure">{svg(figure_folder,'all_level_reference_ranges')}</div>
    <p>完整方法、版本与数值来源：<a href="../../../研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md">方法记录</a>；<a href="../../../{html.escape(data['comparison'])}/scope_reference_ranges.csv">原54项当前范围与状态</a>；<a href="../../../{html.escape(data['prediction'])}/group_metrics.csv">滚动预测分组结果</a>。</p>
    <p>理论资料：Morris等2019（仿真与MC误差）；Gonçalves–White及Shao（依赖与重采样）；Lei等2018（秩校准背景）；Howard等2020v5/2021（顺序检验背景）。完整历史独立性、Bernoulli似然比和剩余预算论证在项目内另行写明。<a href="../../../参考资料/方法文献/sources.json">来源、阅读和下载状态登记</a>区分已保存副本与仅在线可读资料。</p>
    <p class="caption">这是可离线预览、可并入全组汇报的第五问素材；实际浏览器/投影验收、老师载体许可、全组排练和组员真人复核尚待本机完成。</p></dialog>
    <script id="q5-data" type="application/json">{payload}</script><script>
    const pages=[...document.querySelectorAll('.slide')];let current=0;const dialog=document.getElementById('appendix');
    function show(n){{current=Math.max(0,Math.min(pages.length-1,n));pages.forEach((p,i)=>p.hidden=i!==current);document.getElementById('page').textContent=`${{current+1}} / ${{pages.length}}`;document.getElementById('previous').disabled=current===0;document.getElementById('next').disabled=current===pages.length-1;}}
    document.getElementById('previous').onclick=()=>show(current-1);document.getElementById('next').onclick=()=>show(current+1);document.getElementById('appendixButton').onclick=()=>dialog.showModal();document.getElementById('closeAppendix').onclick=()=>dialog.close();
    function full(){{if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen().catch(()=>{{}});}}document.getElementById('full').onclick=full;
    document.addEventListener('keydown',e=>{{if(dialog.open)return;if(['ArrowRight','PageDown',' '].includes(e.key)){{e.preventDefault();show(current+1)}}else if(['ArrowLeft','PageUp'].includes(e.key)){{e.preventDefault();show(current-1)}}else if(e.key.toLowerCase()==='f')full();}});show(Number(new URLSearchParams(location.search).get('page')||1)-1);
    </script></body></html>'''
    return body.replace('href="../../../','href="'+root_prefix)


def narrative(data,figure_dir,material_dir):
    audit=data['prediction_audit'];decision=data['decision'];route=decision['selected_route'] or '无正式采用'
    metrics={r['model_id']:r for r in data['prediction_metrics']}
    group={(r['model_id'],r['group']):r for r in data['prediction_group_metrics']}
    loss_text='、'.join(f"{float(metrics[m]['log_loss']):.6f}" for m in ('M0_nested','M1_strength','M3_nested'))
    accuracy_text='、'.join(f"{100*float(metrics[m]['binary_accuracy']):.2f}%" for m in ('M0_nested','M1_strength','M3_nested'))
    epoch={r['model_id']:float(r['log_loss']) for r in data['prediction_group_metrics'] if r['group']=='era:1990s'}
    epoch_note='1990年代的整体损失略逊仅实力' if epoch['M3_nested']>epoch['M1_strength'] else '1990年代的整体损失也低于仅实力'
    timing=json.loads((ROOT/'outputs/logs/strength_inference/route_timing.json').read_text())
    def method_line(r):
        name='日期条件独立' if r['scenario']=='conditional_independent_dates' else '同日共同冲击'
        if r.get('new_stream_worlds'):
            count=f"初轮{r['first_stage_contained']}/{r['first_stage_planned']}未过；新流{r['new_stream_contained']}/{r['new_stream_worlds']}，新流顺序下限"
        else:count=f"初轮{r['joint_contained']}/{r['planned']}，精确MC下限"
        return f"- {name}，路线{r['route']}：{count}{100*float(r['one_sided_MC_lower']):.3f}%，最终数值失败{r['numerical_failures']}。"
    route_lines='\n'.join(method_line(r) for r in data['method_comparison'])
    directional=[r for r in data['ranges'] if r['status']=='MODEL_CONDITIONAL_REFERENCE' and (float(r['lower_pp'])>0 or float(r['upper_pp'])<0)]
    directional_lines='\n'.join(f"- {MAIN_LABELS.get(r['target_id'],data['region_labels'].get(r['target_id'],r['target_id']))}：{float(r['estimate_pp']):+.3f}个百分点，参照[{float(r['lower_pp']):+.3f}, {float(r['upper_pp']):+.3f}]。" for r in directional)
    effect_lines='\n'.join(f"- {MAIN_LABELS[r['target_id']]}，{'实力后差异' if r['axis']=='level' else '相对无实力背景模型的变化'}：{float(r['estimate_pp']):+.3f}个百分点；"+(f"模型条件参照[{float(r['lower_pp']):+.3f}, {float(r['upper_pp']):+.3f}]。" if r['status']=='MODEL_CONDITIONAL_REFERENCE' else '未准入统计参照。') for r in data['ranges'] if r['target_id'] in MAIN_LABELS)
    return f'''# 第五问收尾：预测增量、统计范围与下一问交接

本文件由实际同版结果生成，供论文写作、组内转述和HTML制作。执行Codex（AI），没有组员本人复核。当前研究结论不等于未知真实足球分布或未来比赛的无条件保证。

## 研究究竟增加了什么价值

前三问描述年代、赛事与地域的主队表现差异；第五问把双方赛前实力作为正式因素，检验这些历史信息对预测有多大帮助。不能把地区排名或某个胜率差本身当作研究机制。

## 可直接用于报告的结果

1990—2024共21,413场，每年只用此前比赛构造编码与拟合，三个方案使用同一预测样本。背景、仅实力、实力加背景的平均对数损失分别为{loss_text}；主胜/非主胜准确率分别{accuracy_text}。联合方案相对背景损失降{100*audit['background_to_joint_relative_loss_reduction']:.2f}%，相对仅实力只再降{100*audit['strength_to_joint_relative_loss_reduction']:.2f}%；35年中{audit['joint_beats_strength_years']}年优于仅实力，{epoch_note}。模型平均校准偏差由仅实力约{float(metrics['M1_strength']['calibration_bias_pp']):+.3f}个百分点变为联合约{float(metrics['M3_nested']['calibration_bias_pp']):+.3f}个百分点。首版沿用全期编码的数字已被修正版替代，首版证据另存，不混用。

主要信息来自实力，背景仍提供较小、随时期变化的增量。上面是回顾性按年向前预测，研究规则已复用历史，不能改写成新增盲测、未来胜平负准确率70%或所有年份都有提升。

本轮检验支持它作为历史比较工具和下一问的预测基线：样本与时间边界、概率公式、指标和分组结果都已核对。但0.42%是这批历史的平均改善，未另对真实预测损失差建立时间相关性区间，不能写成“已统计证明未来一定提升”。30项模型参照检验的是预定效应对象，也不自动替代预测损失比较的检验。未知未来的正式验证仍归后续第八、九问。

背景的价值并不只看多猜对几场：在这批历史向前预测中，友谊赛平均主胜概率偏差由仅实力的{float(group['M1_strength','tournament_group:friendly']['calibration_bias_pp']):+.3f}变为联合的{float(group['M3_nested','tournament_group:friendly']['calibration_bias_pp']):+.3f}个百分点，欧洲由{float(group['M1_strength','home_region:150']['calibration_bias_pp']):+.3f}变为{float(group['M3_nested','home_region:150']['calibration_bias_pp']):+.3f}。这更像是在部分场景减少系统性高估，而不是大幅提高猜中率。两组只是帮助理解的例子，完整分组表全部保留，不当作挑选后的独立确认性证据。

年度共同模型的系数和编码只用往年数据拟合；球队评分仍按比赛日期向前更新，今年较早赛果可以帮助预测今年较晚的比赛，同日赛果不能互相泄漏。这和赛前真实可用信息一致，不是把整年结束后的排名回填到年初。

按洲的平均概率偏差也没有全部消失：联合模型在欧洲约高估1.17个百分点、美洲约低估1.08个百分点；大洋洲仅283场，联合模型损失还略逊仅实力。地域未知的7场单独保留，不拿其偏差概括一个地区。因此这里只支持“总体历史表现有改善”，不支持“每个地区均已可靠”。后续第七问专门评估地区有效性。

年代与赛事的主要比较为：

{effect_lines}

上述六个范围全部跨零，不能确认这几项年代/赛事差异或加入实力后的变化有稳定方向；跨零也不等于证明差异不存在。全部30项参照中，只有{len(directional)}项范围完全在零的一侧：

{directional_lines or '本轮没有。'}

该结果仅按当前全参考与生成机制解释，保留外推和敏感性标记，不把下端略高于零的结果包装成普遍、稳健或因果的地域优势。主要研究价值仍是识别实力的预测信息及背景的场景纠偏价值，不能只挑一个正差来讲故事。

原第一至第三问的构成调整统计量，与第五问M0背景模型并不是同一个估计量。“M3减M0”才是本轮严格配对的模型比较；不能把旧比例与M3之差全部归给实力，也不能解释为实力造成了某个百分比的历史变化。

## 理论与标准答案

共同模型使用Poisson跳变与正态不确定性积分后的probit主胜均值。两模型的差异必须在同一参考上配对计算；无实力模型的真值为跨完整历史的期望损失投影。独立标准流、校准流、锁定验证流分开；每个完整生成历史才是一个独立重复。

核心概率公式为`p_i = Σ_k π_k(ν_i) Φ((η_i + b μ_i) / √(1 + b²(v_i + k τ²)))`。这里μ是主队减客队的赛前实力，v为基础不确定性，ν与τ描述潜在跳变，η包含年代、赛事和双方地域背景；b为正的实力关联系数。公式把评分不确定性积分进概率，不把比分差直接线性当主胜概率。双方比赛信息共同更新评分；同日先全部预测再学习。它描述主胜对非主胜，不能自行拆出平局和客胜概率。

主评价选对数损失而不只看猜对多少场，是因为在真实概率为p时，报q的期望对数损失减去报p的损失，恰为两种Bernoulli分布的KL距离，非负且p=q时为零；Brier期望差则为(q−p)²。两者评价概率本身是否有用。准确率只是0.5阈值的补充指标，主胜均值偏差很小也不证明逐场校准完美。

A完整生成并学习历史后重拟合；B以同一历史完整总得分、Hessian及目标梯度作一阶展开，保留M0的可预测漂移和与赛果创新的协方差，不把按日删漂移当作修正完成。源公式、推导、限制和迭代依据见《第六环节_清单评分敏感性与数学方法》第13、15、19节及后续实际结果。

最终B已不同于R20261030-16原始日期乘子诊断：因为原方法对M0均值漂移和长期反馈的条件没有得到证明，本轮改为统一完整生成历史中的得分线性化。A/B共享生成器和标准答案，接近只说明这两种计算在当前情景中一致，不能当成两份独立的真实世界证据。

## 本轮正式采用范围

本轮采用路线：{route}。原54主要对象仍全部保留，原54族整体不准入。当前获准模型条件参照{decision['admitted_targets']}项，未获准{decision['withheld_targets']}项；30项候选为27个实力后差异、年代两项和赛事一项的前后变化。24个地域前后变化的模拟真值精度不足，仅保留描述，不能据此说地域变化已被证伪，也不能把模拟计算精度不足解释成真实差异不存在。

原143条登记已逐条给出处置：54主要对象按上述30/24处理；64个较窄参考作为敏感性描述，10个原缺层对象仅作外推，7个赛事斜率/曲线对象保持探索，8个样本内拟合比较保持描述。没有把它们遗忘，也没有把全部143条升级成正式检验。对应`object_disposition.csv`与本版展示数据同目录保存。

{route_lines}

第一次128个锁定历史并未整体通过：日期独立各64/64，同日情景各63/64，后者MC下限90.4388%低于93%。原失败结果单独留存。随后冻结模型、目标、尺度和宽度，只为未过情景另起新流；新流实际完成{data['fresh_confirmation']['new_worlds']}个独立历史，旧64次不进入其E值。

重复查看的错误预算也有明确扣除：每门原预算0.0125，首轮误过概率至多0.93^64，剩余0.0028858984给新流。新流使用固定0.99对0.93的Bernoulli似然比非负超鞅，达到剩余预算倒数才通过；最多192次。停止规则允许增加精度，不允许扩大范围或反复无预算试到满意。四门总MC误准入预算仍不超过0.05，推导及Howard原文见数学文档19.7节。

两路线的标准化近似误差约0.023，都很接近；A重新拟合，避免用一阶展开代替完整误差。两代表历史的额外步骤平均耗时A约{timing['A_specific_mean_seconds']:.2f}秒、B约{timing['B_specific_mean_seconds']:.2f}秒，完整历史生成约{timing['generation_mean_seconds']:.2f}秒。B全流程节省的乐观估计约{100*timing['B_whole_run_relative_saving']:.2f}%，未达到事前20%替代线。因此A是当前范围内的合理主方案，不宣称所有可能模型中的全局最优。

校准与验证针对两个预定生成机制：日期条件独立、同日共同冲击0.25。范围使用完整族最大标准化误差并增加MC真值余量。初轮报告固定样本精确MC下限，新流报告允许停止的顺序下限，合并包含率只作描述；不拿停止后的样本数直接套普通固定样本区间。95%名义和93%工程下限分开，数值失败0次也不认证真实失败概率低于1%。不把固定插件模型的新模拟历史包含率当成未知真实分布、模型选择后或连续所有相关强度的覆盖证明。

## 论文必须交代的边界

- 研究对象是这批历史中的模型关联；非中立样本不能单独识别纯粹主场因果效应。
- 全参考存在模型外推，原缺层和窄参考仍按原标记；有数值不等于历史支持已补齐。
- 评分器中的友谊赛参数0.65相对削弱赛果里的实力信号；实际代码通过κ=(1−ε)α把实力概率和均匀赛果背景混合，并非把主胜率、比赛数量或每次评分变化简单乘0.65。M4不同实力斜率是另一项探索，不把两者混成已证机制。
- 原评分器最终预测校正与共同分析用的原始评分边际不同，不能混用其成绩。
- 完整模拟为了继续学习需要同时生成胜平负；非主胜中的平局/客胜拆分沿用固定假设。两个情景没有验证所有拆分规则，也不能把共同二元模型当成已经验收的胜平负预测器。
- 0.25是同日生成器的潜在共同冲击参数，不意味着任意两场比赛的实际结果相关系数都恰为0.25；两点情景也不验证所有相关强度。
- 三起点、梯度与曲率检查确认本次数值局部稳定，不是所有非线性拟合均达全局最优的证明。A校准的是这套已固定算法实际输出的误差，不能因未证明全局最优而偷偷换算法后继续套用原范围。
- 原24个地域前后变化不输出获准统计区间；A/B本人复核、最终课程论文正文、载体许可和全组现场排练不伪写完成。

## HTML和论文支撑文件

- 展示入口：`研究/05_赛前实力/展示/index.html`；三屏约90秒，箭头键切页，附录保留年度增量和来源。
- 本版展示取数与143对象处置：`{material_dir.as_posix()}/presentation_data.json`、`{material_dir.as_posix()}/object_disposition.csv`、`{material_dir.as_posix()}/manifest.json`。
- 稳定HTML入口与本版不可变副本保存同一内容；以后应修改生成程序后重建，不单独编辑页面让数字脱离CSV。图的本机字体文件指纹与Matplotlib版本均记录在材料身份中。
- 比较与范围：`{data['comparison']}/scope_method_comparison.csv`、`scope_reference_ranges.csv`、`scope_decision.json`；原54不准入另见`method_decision.json`。
- 预测：`{data['prediction']}/predictions.csv`、`yearly_metrics.csv`、`group_metrics.csv`、`calibration_bins.csv`、`models.json`。
- 预测独立核验：`outputs/logs/strength_inference/prediction_audit.json`；严格恢复与全历史等价：`full_fast_equivalence.json`及比较包`numerical_extension.json`。
- 图：`{figure_dir.as_posix()}`下五组PNG/SVG，包含全部27个主要实力后差异；数据源和单位均写在图内。
- 论文与汇报统一索引：`文档/05_团队协作/论文与汇报支撑材料索引.md`，只登记路径，不复制原材料。

HTML的静态资源、唯一标识、图形引用和19项控制逻辑已检查；图像另作人工式视觉审读。内置验收浏览器的安全规则拒绝本地file预览，实际浏览器/投影验收未执行，也没有换渠道绕过规则。汇报机器上正常打开后，仍须本人检查切页、附录、全屏、断网与打印；静态检查不能冒充这一步完成。

## 本地复核与重新运行

先按环境说明在仓库根目录选择自己的Python环境。无需为了重看成果重新跑264个历史；打开CSV、HTML和独立核验即可。组员A先运行`python scripts/audit_strength_predictive_validation.py`、`python scripts/audit_strength_q5_final.py --materials`，核对`passed`与本文同版数字。若完整世界缓存尚未下载，第二个命令会明确缺文件，不能把它当成已经复核。

完整重建依次运行：`python scripts/run_strength_inference_final.py --phase truth --workers 16`；`--phase calibration`；`python scripts/report_strength_inference.py --phase calibrate`；`python scripts/run_strength_inference_final.py --phase validation --workers 16`；`python scripts/audit_strength_inference_truth.py`；`python scripts/report_strength_inference.py --phase apply`。这里的16是本机使用的并行数，较小机器可调为2或4；同配置完整世界支持续跑，缓存不等于新增独立重复。不要在已有包上修改协议后仍冒用原版本。

复现首轮失败后的补充确认，再运行`python scripts/confirm_strength_inference.py --workers 16`，然后重新运行`python scripts/report_strength_inference.py --phase apply`。补充脚本支持按已冻结查看点续跑；不可删除其种子或阈值后仍宣称复现当前结果。

另运行`python scripts/analyze_strength_predictive_validation.py`及对应独立核验重建年度预测，随后`python scripts/build_strength_q5_materials.py`更新展示材料。完整重建耗时明显较长；原始数据和首版失败保留，上传/克隆时须检查Git忽略项是否包含本地世界缓存，并按源码和冻结种子重建缺失包。论文取数用已登记CSV与清单，真人审核仍须本人实际提交记录。

## 给组员的90秒转述稿（时长预算，未实测排练）

前面我们看到年代、赛事和地区的主胜率不同，但其中可能混有球队实力和对手选择。这一问把双方赛前实力正式加入模型，并用1990—2024年21,413场比赛逐年向前检查，每次只用过去的比赛和过去的编码权重。

结果显示，实力是主要预测信息：联合方案相对只用背景，对数损失下降约{100*audit['background_to_joint_relative_loss_reduction']:.1f}%，主胜或非主胜准确率约{100*float(metrics['M3_nested']['binary_accuracy']):.1f}%。背景在实力之外的增量只有约{100*audit['strength_to_joint_relative_loss_reduction']:.2f}%，而且不是每年都改善。

我们还用完整模拟历史比较两条可靠性路线。本轮采用{route}，只对证据达到要求的范围作模型条件解释；24个地域前后变化仍保留描述，不写成因果贡献或已显著。历史验证不是未知未来的准确率保证。下一问会进一步研究，参考过去多少年更合适。

## 下一问准备：参考多久的历史

第六问先区分两个对象：球队评分记住多久的比赛，以及共同预测模型用多少年的数据训练。现有评分的扩散/跳变已经带有动态记忆，不能把“1950起学习”直接当作每场历史都同等权重。

建议先讨论固定2、4、8、12、20年与累计历史作为有限候选。一次只改一个层面；每个预测年份只用以前的数据选择周期，再评价下一年。统一比较对数损失、Brier和分组校准，不能在全部测试期上挑出最优周期后把同一期再称独立验收。

可直接复用本轮逐年预测样本、训练边界、评分分布与评价脚本。第六问本轮只准备接口与决策点，没有运行周期比较或宣布最优年限。
'''


def run():
    data=gather();font=configure_figures();source=ROOT/'src/strength_q5_closeout.py'
    identity=dict(data_sha256=fingerprint(data),code_sha256=file_hash(source),font=font,font_sha256=file_hash(Path(font)),
        matplotlib=matplotlib.__version__,environment=environment())
    ident='q5-closeout-'+fingerprint(identity)[:20];folder=ROOT/'outputs/logs/strength_q5_closeout'/ident
    figs=ROOT/'outputs/figures/strength_q5'/ident
    figures(data,figs);write_json(folder/'presentation_data.json',data)
    atomic_bytes(folder/'object_disposition.csv',csv_bytes(list(data['all_object_dispositions'][0]),data['all_object_dispositions']))
    html_path=ROOT/'研究/05_赛前实力/展示/index.html';atomic_bytes(html_path,render_html(data,figs).encode('utf-8'))
    atomic_bytes(folder/'index.html',render_html(data,figs,'../../../../').encode('utf-8'))
    notes=narrative(data,figs.relative_to(ROOT),folder.relative_to(ROOT)).encode('utf-8')
    doc=ROOT/'研究/05_赛前实力/第五问_收尾与下一问交接.md';atomic_bytes(doc,notes)
    atomic_bytes(folder/'paper_notes.md',notes)
    write_json(folder/'identity.json',identity)
    paths=[folder/'presentation_data.json',folder/'object_disposition.csv',folder/'identity.json',folder/'index.html',folder/'paper_notes.md',*sorted(figs.glob('*'))]
    write_json(folder/'manifest.json',dict(schema_version='q5-closeout-materials-v1',identity=identity,
        outputs={p.relative_to(ROOT).as_posix():file_hash(p) for p in paths},human_review=False,final_teacher_acceptance=False))
    write_json(ROOT/'outputs/logs/strength_q5_closeout/current.json',dict(directory=folder.relative_to(ROOT).as_posix(),
        figures=figs.relative_to(ROOT).as_posix(),HTML=html_path.relative_to(ROOT).as_posix(),HTML_sha256=file_hash(html_path),
        document=doc.relative_to(ROOT).as_posix(),document_sha256=file_hash(doc),manifest_sha256=file_hash(folder/'manifest.json')))
    print('Q5_MATERIALS_COMPLETE',folder.relative_to(ROOT).as_posix(),flush=True)
