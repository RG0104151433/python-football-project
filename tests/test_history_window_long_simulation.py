import pytest
from src.history_window.simulation_long import generate,extend

@pytest.mark.parametrize('path',['constant','drift','jump'])
@pytest.mark.parametrize('link',['probit','logistic'])
def test_long_world_prefix_stable_and_change_inside_evaluation(path,link):
    games,truth=generate(631201,path,link,240)
    extended,tt=extend(631201,path,link,games,truth,360)
    direct,dt=generate(631201,path,link,360)
    assert extended==direct and tt==dt and extended[:480]==games and tt[:240]==truth
    assert len(extended)==720 and len(tt)==360
    assert all(abs(g['true_p_home']+g['true_p_draw']+g['true_p_away']-1)<1e-12 for g in extended)
    if path=='constant':assert tt[0]['true_A']==tt[-1]['true_A']
    if path=='jump':assert tt[287]['true_A']-tt[288]['true_A']==pytest.approx(1.6)
    if path=='drift':assert tt[239]['true_A']==tt[240]['true_A'] and tt[241]['true_A']<tt[240]['true_A']

def test_shared_seed_scenarios_and_generation_order():
    a,ta=generate(631211,'constant','probit',240)
    b,tb=generate(631211,'jump','probit',240)
    assert [(r['home'],r['away'],r['outcome']) for r in a]==[(r['home'],r['away'],r['outcome']) for r in b]
    generate(631212,'drift','logistic',360)
    c,tc=generate(631211,'constant','probit',240)
    assert c==a and tc==ta
