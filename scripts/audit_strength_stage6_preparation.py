"""Independent registry/reference checks and bisection-based score reconstruction."""
from pathlib import Path
from collections import Counter,defaultdict
from bisect import bisect_left
from datetime import date
from fractions import Fraction
import argparse,csv,gzip,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import file_hash,fingerprint,write_json
from src.strength.io import read_rows


def read(path):
    p=Path(path)
    if p.suffix=='.gz':return list(csv.DictReader(io.StringIO(gzip.decompress(p.read_bytes()).decode('utf-8-sig'))))
    return read_rows(p)


def run(directory=None):
    log=ROOT/'outputs/logs/strength_stage6'
    if directory is None:directory=json.loads((log/'current.json').read_text())['directory']
    folder=ROOT/directory;manifest=json.loads((folder/'manifest.json').read_text());cfg=manifest['identity']['protocol']
    checks=0;failed=[]
    def check(label,yes):
        nonlocal checks
        checks+=1
        if not yes:failed.append(label)
    for name,h in manifest['outputs'].items():check('artifact:'+name,file_hash(folder/name)==h)
    for name,h in manifest['identity']['inputs'].items():check('input:'+name,file_hash(ROOT/name)==h)
    for name,h in manifest['identity']['code'].items():check('code:'+name,file_hash(ROOT/name)==h)
    mainfolder=ROOT/cfg['analysis'];m=json.loads((mainfolder/'manifest.json').read_text());jc=m['identity']['protocol']
    base=read(ROOT/jc['input']/'analysis_matches.csv');baseidx={r['match_id']:r for r in base};check('baseline24917',len(base)==24917)
    original=[r for r in read(mainfolder/'contrasts.csv') if r['model_id']=='M3_nested'];old={(r['target_id'],r['reference_kind']):r for r in original}
    registry=read(folder/'target_registry.csv');check('registry143',len(registry)==len({r['registry_id'] for r in registry})==143)
    check('familycounts',Counter(r['family'] for r in registry)==dict(F_PRIMARY_CONDITIONAL=54,F_AUX_REFERENCE=64,F_EXTRAPOLATION_ONLY=10,F_EXPLORATORY_RELATIONS=7,F_DESCRIPTIVE_FIT=8))
    both={(r['target_id'],r['reference_kind'],r['model_id']):r for r in read(mainfolder/'contrasts.csv')}
    for r in registry:
        check('not_admitted',r['inference_status']=='NOT_ADMITTED' and r['independent_confirmation']=='false')
        if r['target_id']:
            o=old[r['target_id'],r['reference_kind']]
            family='F_AUX_REFERENCE' if r['reference_kind']!='full' else 'F_PRIMARY_CONDITIONAL' if o['old_target_status']=='supported_point_target' else 'F_EXTRAPOLATION_ONLY'
            value=float(o['difference_pp'])
            if r['effect_size_axis']=='paired_change':value-=float(both[r['target_id'],r['reference_kind'],'M0_nested']['difference_pp'])
            check('target_mapping:'+r['registry_id'],r['family']==family and r['reference_id']==o['reference_id'] and abs(float(r['estimate'])-value)<2e-8)
    scopes=read(folder/'reference_scope.csv');check('scope64',len(scopes)==64)
    members=defaultdict(list)
    for r in read(folder/'reference_membership.csv.gz'):
        check('member_known',r['match_id'] in baseidx and int(r['weight_numerator'])==1)
        members[r['reference_id']].append(r)
    for r in scopes:
        rr=members[r['reference_id']];ids=[x['match_id'] for x in rr];original_row=old[r['target_id'],r['reference_kind']]
        check('membership_count',len(ids)==len(set(ids))==int(r['reference_rows'])==int(original_row['reference_rows']))
        check('weights_exact',all(int(x['weight_denominator'])==len(ids) for x in rr))
        expected='reference-'+fingerprint(dict(rule=original_row['reference_rule'],kind=r['reference_kind'],rows=[
            (mid,baseidx[mid]['strength_difference'],baseidx[mid]['strength_difference_base_variance'],baseidx[mid]['home_jump_intensity'],baseidx[mid]['away_jump_intensity'],baseidx[mid]['jump_scale_sd']) for mid in ids]))[:20]
        check('adopted_reference_hash',r['reference_id']==expected==original_row['reference_id'])
        check('not_training_sample',int(r['fitted_matches'])==24917 and r['original_missing_support_restored']=='false')
        yy=Counter(baseidx[mid]['year'] for mid in ids)
        check('year_concentration',len(yy)==int(r['year_categories']) and abs(max(yy.values())/len(ids)-float(r['year_largest_share']))<1e-9)
        for arm in (1,2):
            for name in ('zero_cell_fraction','sparse_cell_fraction','outside_score_range_fraction'):
                check('support_preserved',abs(float(r[f'arm{arm}_{name}'])-float(original_row[f'arm{arm}_{name}']))<2e-8)
            z=float(r[f'arm{arm}_zero_cell_fraction']);o=float(r[f'arm{arm}_outside_score_range_fraction']);u=float(r[f'arm{arm}_unsupported_union_fraction'])
            check('union_bounds',max(z,o)-1e-9<=u<=min(1,z+o)+1e-9)
    mixes=defaultdict(list)
    for r in read(folder/'scenario_mixtures.csv'):mixes[r['target_id'],r['reference_kind'],r['arm']].append(r)
    for key,ss in mixes.items():check('exact_scenario_mass',sum((Fraction(int(x['weight_numerator']),int(x['weight_denominator'])) for x in ss),Fraction())==1)
    # Independent history algorithm: per-team sorted appearances and bisect_left;
    # excludes all appearances on the current date including duplicates.
    learning_cfg=json.loads((ROOT/jc['learning_config']).read_text());games=read(ROOT/learning_cfg['learning']/'learning_matches.csv')
    readiness=json.loads((folder/'readiness.json').read_text());history_checks=0;max_error=0.
    for variant in readiness['score_variants']:
        selected=[g for g in games if int(g['date'][:4])>=variant['start']];dates=sorted({g['date'] for g in selected});appearance=defaultdict(list)
        for g in selected:
            for side in ('home','away'):appearance[g[side+'_entity_id']].append(g['date'])
        for team in appearance:appearance[team].sort()
        sourcefolder=ROOT/variant['source']
        initial=sourcefolder.name.startswith('repaired-initialization')
        source={r['match_id']:r for r in read(sourcefolder/('study_differences.csv' if initial else 'study_prematch_features.csv'))}
        parameters=json.loads((ROOT/jc['raw_score']/'report.json').read_text())['parameters'] if initial else json.loads((sourcefolder/'report.json').read_text())['parameters']
        prepared=read(folder/variant['prepared_file']);check('variant24917',len(prepared)==24917 and {r['match_id'] for r in prepared}==baseidx.keys())
        for r in prepared:
            day=r['date'];nh=[];valid=True
            for side in ('home','away'):
                dd=appearance[r[side+'_entity']];i=bisect_left(dd,day);previous=dd[i-1] if i else ''
                elapsed=(date.fromisoformat(day)-date.fromisoformat(previous)).days/365.2425 if previous else 0.
                intensity=parameters['jump_rate']*elapsed;nh.append(intensity)
                valid &= int(r[side+'_history'])==i and r[side+'_previous_date']==previous and abs(float(r[side+'_jump_intensity'])-intensity)<2e-8
            j=bisect_left(dates,day);cutoff=dates[j-1] if j else 'initial_prior'
            row=source[r['match_id']];total=float(row['difference_variance']);basev=total-sum(nh)*parameters['jump_sd']**2
            error=max(abs(basev-float(r['strength_difference_base_variance'])),abs(total-float(r['strength_difference_variance'])),abs(float(row['difference'])-float(r['strength_difference'])))
            max_error=max(max_error,error)
            valid &= error<2e-8 and cutoff==r['prediction_cutoff'] and cutoff<day and basev>0
            check('reconstruction:'+variant['variant_id']+':'+r['match_id'],bool(valid));history_checks+=1
    check('five_variants',len(readiness['score_variants'])==5 and history_checks==124585)
    flags=read(folder/'baseline_flags.csv.gz');check('flags_all_ids',len(flags)==24917 and {r['match_id'] for r in flags}==baseidx.keys())
    for r in flags:
        b=baseidx[r['match_id']]
        check('flags_match',r['cold_start']==b['cold_start'] and r['weak_connection']==b['previously_disconnected'] and (r['unknown_home']=='true')==(not b['home_region']) and (r['unknown_away']=='true')==(not b['away_region']))
    check('unresolved_inference',cfg['error_control_method'] is None and cfg['confidence_level'] is None and not readiness['intervals_computed'] and not readiness['stage6_complete'])
    for name in manifest['outputs']:
        if '.csv' in name:
            data=(folder/name).read_bytes();data=gzip.decompress(data) if name.endswith('.gz') else data
            check('BOM_LF:'+name,data.startswith(b'\xef\xbb\xbf') and b'\r\n' not in data)
    result=dict(passed=not failed,checks=checks,failed=failed,directory=directory,independent_history_checks=history_checks,
        max_reconstruction_rounding_error=max_error,reference_membership_verified_against_adopted_hashes=True,
        no_new_score_replay=True,no_joint_refits=True,statistical_inference_admitted=False,human_review=False)
    write_json(log/(folder.name+'-audit.json'),result);print(json.dumps(result,ensure_ascii=False),flush=True)
    if failed:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',nargs='?');run(p.parse_args().directory)
