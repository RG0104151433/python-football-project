"""Independent boundary and interface cases for the provisional FIFA overlay."""
import copy
import json
from pathlib import Path

import pytest

from scripts.audit_team_identity import json_bytes, digest
from scripts.build_team_identity import classify_side, build_match_overlay, verify_identity, validate_registry
from scripts.analyze_confirmed_eras import apply_overlay
from src.data_contract import PrepError
from test_eras import record

SCOPE={'start':'1980-01-01','end':'2024-12-31'}


def mapping(years=(1994,)):
    return {'A':{'fifa_code':'AAA','evidence_id':'source','years':list(years)}}


@pytest.mark.parametrize('day,state', [
    ('1993-12-31','nonmember_before_admission'),
    ('1994-01-01','pending_admission_year'),
    ('1994-12-31','pending_admission_year'),
    ('1995-01-01','conditional_member'),
    ('1979-12-31','outside_scope'),
    ('2025-01-01','outside_scope'),
])
def test_year_precision_never_invents_an_admission_day(day,state):
    assert classify_side(day,'A','Alpha',mapping(),{},[],SCOPE)[1]==state


def test_exact_day_is_inclusive_and_re_affiliation_gaps_remain_unknown():
    exact={'Alpha':{'start':'1994-05-13','evidence_id':'event'}}
    assert classify_side('1994-05-12','A','Alpha',mapping(),exact,[],SCOPE)[1]=='nonmember_before_admission'
    assert classify_side('1994-05-13','A','Alpha',mapping(),exact,[],SCOPE)[1]=='conditional_member'
    assert classify_side('1980-01-01','A','Alpha',mapping((1923,1992)),{},[],SCOPE)[1]=='pending_historical_episode'
    assert classify_side('1992-12-31','A','Alpha',mapping((1923,1992)),{},[],SCOPE)[1]=='pending_admission_year'


def test_absence_is_not_historical_nonmembership_and_exceptions_override_year_inference():
    assert classify_side('2000-01-01','missing','Retired',{}, {},[],SCOPE)[1]=='pending_unmapped_label'
    exc=[dict(source_team_label='Alpha',start='1980-01-01',end='2000-12-31',reason='Unknown predecessor')]
    assert classify_side('2000-12-31','A','Alpha',mapping((1900,)),{},exc,SCOPE)[1]=='pending_historical_episode'
    assert classify_side('2001-01-01','A','Alpha',mapping((1900,)),{},exc,SCOPE)[1]=='conditional_member'


def raw_row(day, mid, home='A',away='B'):
    return dict(match_id=mid,source_record_id='source:'+mid,date=day,home_team_id=home,away_team_id=away,
        home_team='Alpha' if home=='A' else 'Beta',away_team='Beta' if away=='B' else 'Alpha',
        eligible_venue_analysis='true',is_neutral='false',eligible_tournament_analysis='true',tournament_group='friendly')


def test_every_clean_match_has_a_disposition_and_either_ineligible_side_blocks_the_match():
    raw=[raw_row('2000-01-01','1'),raw_row('1994-12-31','2'),raw_row('1985-01-01','3'),raw_row('1970-01-01','4')]
    before=copy.deepcopy(raw)
    maps={**mapping(), 'B':{'fifa_code':'BBB','evidence_id':'source','years':[1900]}}
    rows=build_match_overlay(dict(clean=raw,scope=SCOPE),maps,{},[],{'policy_id':'test'})
    assert len(rows)==4 and raw==before
    assert [r['membership_status'] for r in rows]==['conditional_both_members','pending','nonmember_evidence','outside_scope']
    assert sum(r['eligible_under_provisional_policy'] for r in rows)==1
    assert sum(r['in_previous_study'] for r in rows)==3
    assert all(r['full_history_verified'] is False for r in rows)


def test_q1_overlay_retains_neutral_and_date_rules_and_does_not_modify_input():
    cfg=json.loads((Path(__file__).resolve().parents[1]/'config/eras.json').read_text(encoding='utf-8'))
    raw=[record('1980-01-01',1),record('1981-01-01',2,neutral=True),record('1979-01-01',3),record('1982-01-01',4)]
    for r in raw:r.update(home_team='Alpha',away_team='Beta')
    before=copy.deepcopy(raw)
    overlay=[]
    for i,r in enumerate(raw):
        overlay.append(dict(match_id=r['match_id'],source_record_id=r['source_record_id'],date=r['date'],
            home_source_team_id='A',away_source_team_id='B',home_source_label='Alpha',away_source_label='Beta',
            eligible_under_provisional_policy='true' if i!=3 else 'false',full_history_verified='false',
            membership_status='conditional_both_members' if i!=3 else 'pending'))
    baseline,samples,members=apply_overlay(raw,cfg,overlay)
    assert raw==before
    assert len(baseline['classified_venue'])==2 and len(samples['classified_venue'])==1
    assert members[1]['primary_exclusion_reason']=='neutral'
    assert members[2]['primary_exclusion_reason']=='outside_analysis_window'
    assert members[3]['primary_exclusion_reason']=='fifa_membership_pending'
    overlay[0]['date']='1980-01-02'
    with pytest.raises(PrepError) as exc:apply_overlay(raw,cfg,overlay)
    assert exc.value.code=='CONFIRMED_IDENTITY_MISMATCH'


def test_release_cannot_claim_full_history_and_tampering_is_detected(tmp_path):
    (tmp_path/'overlay.csv').write_bytes(b'original')
    manifest=dict(schema_version='fifa-identity-release-v1',status='published_provisional',full_history_verified=False,
        identity_version='toy',inputs={},code_hashes={},outputs={'overlay.csv':digest(b'original')})
    (tmp_path/'manifest.json').write_bytes(json_bytes(manifest))
    assert verify_identity(tmp_path,'manifest.json')['final_release'] is False
    (tmp_path/'overlay.csv').write_bytes(b'changed')
    with pytest.raises(PrepError) as exc:verify_identity(tmp_path,'manifest.json')
    assert exc.value.code=='FIFA_RELEASE_HASH_MISMATCH'
    manifest['full_history_verified']=True
    (tmp_path/'manifest.json').write_bytes(json_bytes(manifest))
    with pytest.raises(PrepError) as exc:verify_identity(tmp_path,'manifest.json')
    assert exc.value.code=='FIFA_RELEASE_INVALID'


def test_policy_cannot_be_silently_promoted_to_final():
    with pytest.raises(PrepError) as exc:
        validate_registry({'scope':SCOPE},[],[],[],[],dict(schema_version='fifa-population-policy-v1',analysis_scope=SCOPE,
            final_release_allowed=True,continuity_assumption='assumed',unknown_action='quarantine_for_this_release_not_delete'))
    assert exc.value.code=='FIFA_POLICY_INVALID'
