"""Finite-history influence diagnostics for Q7; no refitting or confidence intervals."""
from collections import Counter
from itertools import product
import io
import json
import math
import zipfile

import numpy as np

from src.data_contract import atomic_bytes, csv_bytes, file_hash, fingerprint, write_json
from src.strength.io import ROOT, environment, read_rows
from src.regional_effectiveness import groups, unique
from src.regional_diagnostics import classify, LEVELS

SETS = {'primary5': ['150', '142', '002', '019', '009'],
        'americas2': ['SOUTH_AMERICA', 'OTHER_AMERICAS']}
CELLS = ['|'.join(p) for p in product(LEVELS['signed_gap'], LEVELS['uncertainty'])]


def targets():
    out = [dict(target_id=f'T{i:02d}', kind='paired', group_a=g, group_b='',
                comparison_set='', weighted=False, metric='loss_difference',
                label=label+'：联合减仅实力', unit='log_loss')
           for i, (g, label) in enumerate(zip(SETS['primary5'], ['欧洲', '亚洲', '非洲', '美洲', '大洋洲']), 1)]
    for tid, a, b, weighted, st, label in [
        ('T06', '002', '150', False, '', '非洲减欧洲：原始损失差'),
        ('T07', '002', '150', True, 'primary5', '非洲减欧洲：共同构成损失差'),
        ('T10', 'SOUTH_AMERICA', 'OTHER_AMERICAS', False, '', '南美减其余美洲：原始损失差'),
        ('T11', 'SOUTH_AMERICA', 'OTHER_AMERICAS', True, 'americas2', '南美减其余美洲：共同构成损失差')]:
        out.append(dict(target_id=tid, kind='between', group_a=a, group_b=b,
                        comparison_set=st, weighted=weighted, metric='joint_loss', label=label, unit='log_loss'))
    for tid, bin_no in [('T08', 1), ('T09', 3)]:
        out.append(dict(target_id=tid, kind='calibration', group_a='002', group_b='',
                        comparison_set='', weighted=False, metric='joint_bias', probability_bin=bin_no,
                        label=f'非洲低评分不确定性：概率档{bin_no}偏差', unit='percentage_points'))
    out += [dict(target_id='T12', kind='paired', group_a='009', group_b='', comparison_set='primary5',
                 weighted=True, metric='loss_difference', label='大洋洲：共同构成联合减仅实力', unit='log_loss'),
            dict(target_id='T13', kind='bias', group_a='009', group_b='', comparison_set='primary5',
                 weighted=True, metric='joint_bias', label='大洋洲：共同构成平均偏差', unit='percentage_points')]
    for t in out:
        t.setdefault('probability_bin',None)
    return sorted(out, key=lambda t: t['target_id'])


def sign(x, tol=1e-12):
    return None if x is None else 1 if x > tol else -1 if x < -tol else 0


class Cohort:
    def __init__(self, rows, eps):
        self.rows = rows
        self.size = len(rows)
        self.years = np.array([int(r['year']) for r in rows])
        self.home = np.array([r['home_team_id'] for r in rows])
        self.away = np.array([r['away_team_id'] for r in rows])
        if any(not r['home_team_id'] or not r['away_team_id'] for r in rows):
            raise ValueError('MISSING_TEAM_ID')
        self.cells = np.array([r['joint_cell'] for r in rows])
        self.masks = {g: np.array([g in groups(r) for r in rows]) for gs in SETS.values() for g in gs}
        y = np.array([int(r['home_win']) for r in rows])
        if not np.isin(y, [0, 1]).all():
            raise ValueError('INVALID_BINARY_LABEL')
        p = {m: np.array([float(r['p_'+m]) for r in rows]) for m in ['joint', 'strength']}
        if any(not np.isfinite(v).all() or np.any((v < 0) | (v > 1)) for v in p.values()):
            raise ValueError('INVALID_PROBABILITY')
        loss = {}
        for m, v in p.items():
            clipped = np.clip(v, eps, 1-eps)
            loss[m] = -(y*np.log(clipped)+(1-y)*np.log1p(-clipped))
        self.values = dict(joint_loss=loss['joint'], loss_difference=loss['joint']-loss['strength'],
                           joint_bias=100*(p['joint']-y),
                           brier_difference=(p['joint']-y)**2-(p['strength']-y)**2)
        self.probability = p['joint']
        self.low_uncertainty = np.array([r['uncertainty']=='low' for r in rows])

    def keep(self, kind, key):
        if kind == 'year':
            return self.years != int(key)
        if kind == 'team':
            return (self.home != key) & (self.away != key)
        raise ValueError('UNKNOWN_DELETE_KIND')

    def target_mask(self, t, group):
        mask = self.masks[group].copy()
        if t['kind'] == 'calibration':
            left = t['probability_bin']/5
            mask &= self.low_uncertainty & (self.probability >= left) & (self.probability < left+.2)
        return mask

    def reference(self, set_name, mode='pooled', minimum=1):
        counts = {g: {c: int(np.sum(self.masks[g] & (self.cells==c))) for c in CELLS} for g in SETS[set_name]}
        common = [c for c in CELLS if all(counts[g][c] >= minimum for g in counts)]
        if not common:
            return {}, counts
        if mode == 'equal_region':
            # Full sample shares, conditioned on original common support if any is missing.
            raw = {c: sum(counts[g][c]/sum(counts[g].values()) for g in counts)/len(counts) for c in common}
        elif mode == 'pooled':
            raw = {c: sum(counts[g][c] for g in counts) for c in common}
        else:
            raise ValueError('UNKNOWN_REFERENCE_MODE')
        total = math.fsum(raw.values())
        return {c: v/total for c, v in raw.items()}, counts

    def evaluate(self, t, keep=None, weights=None):
        keep = np.ones(self.size, dtype=bool) if keep is None else np.asarray(keep, dtype=bool)
        if keep.shape != (self.size,):
            raise ValueError('INVALID_KEEP_MASK')
        original = 0
        remaining = 0
        sizes = {}
        missing = []
        values = []
        brier = []
        for g in [t['group_a']]+([t['group_b']] if t['group_b'] else []):
            base = self.target_mask(t, g)
            selected = base & keep
            if t['weighted']:
                selected &= np.isin(self.cells,list(weights or {}))
            original += int(base.sum())
            remaining += int(selected.sum())
            sizes[g] = int(selected.sum())
            if t['weighted']:
                if not weights:
                    missing.append(g+':no_common_support')
                    continue
                parts = []
                bparts = []
                for c, w in weights.items():
                    if w <= 0:
                        continue
                    ss = selected & (self.cells==c)
                    if not ss.any():
                        missing.append(g+':'+c)
                        continue
                    parts.append(w*float(self.values[t['metric']][ss].mean()))
                    if t['kind']=='paired':
                        bparts.append(w*float(self.values['brier_difference'][ss].mean()))
                values.append(math.fsum(parts))
                if t['kind']=='paired':
                    brier.append(math.fsum(bparts))
            elif selected.any():
                values.append(float(self.values[t['metric']][selected].mean()))
                if t['kind']=='paired':
                    brier.append(float(self.values['brier_difference'][selected].mean()))
            else:
                missing.append(g+':empty_target')
        value = None if missing else values[0]-(values[1] if t['group_b'] else 0)
        return dict(value=value, brier_difference=brier[0] if brier and not missing else None,
                    original_matches=original, remaining_matches=remaining, removed_matches=original-remaining,
                    removed_share=(original-remaining)/original if original else None,
                    remaining_by_group=sizes, status='unsupported' if missing else 'calculated',
                    reason=';'.join(missing), affected=remaining!=original)


def concentration(a):
    a = np.asarray(a, dtype=float)
    if not len(a) or np.any(a < 0) or not np.isclose(a.sum(), 1, atol=1e-10, rtol=0):
        raise ValueError('INVALID_NORMALIZED_MATCH_WEIGHTS')
    return dict(max_match_weight=float(a.max()), weight_concentration_equivalent_matches=1/float(a@a))


def stories(results, scenario_kind, scenario_key):
    by = {r['target_id']: r for r in results}
    out = []
    for name, a, b, rule in [
        ('africa_positive_gap_shrinks', 'T06', 'T07', lambda x,y: x>y>0),
        ('south_america_order_reverses', 'T10', 'T11', lambda x,y: x>0 and y<0),
        ('oceania_gain_changes_direction', 'T05', 'T12', lambda x,y: x<0 and y>0),
        ('africa_opposite_bin_biases', 'T08', 'T09', lambda x,y: x<0 and y>0)]:
        x,y = by[a]['value'], by[b]['value']
        out.append(dict(story=name, scenario_kind=scenario_kind, scenario_key=scenario_key,
                        first_target=a, second_target=b, first_value=x, second_value=y,
                        status='unsupported' if x is None or y is None else 'calculated',
                        story_preserved=None if x is None or y is None else rule(x,y),
                        affected=by[a]['affected'] or by[b]['affected']))
    return out


def compute(data, cfg):
    tt = targets()
    refs = {s: data.reference(s)[0] for s in SETS}
    base = {t['target_id']: data.evaluate(t, weights=refs.get(t['comparison_set'])) for t in tt}
    target_rows = [dict(**t, **base[t['target_id']], original_sign=sign(base[t['target_id']]['value'])) for t in tt]
    deletions = []
    story_rows = stories(target_rows, 'original', '')
    scenarios = [('year', str(y)) for y in range(cfg['main_years'][0],cfg['main_years'][1]+1)]
    scenarios += [('team', g) for g in sorted(set(data.home)|set(data.away))]
    for kind, key in scenarios:
        keep = data.keep(kind,key)
        local = []
        for t in tt:
            r = data.evaluate(t,keep,refs.get(t['comparison_set']))
            original = base[t['target_id']]['value']
            r = dict(target_id=t['target_id'], scenario_kind=kind, scenario_key=key, **r,
                     original_value=original, change=None if r['value'] is None or original is None else r['value']-original,
                     direction_changed=None if r['value'] is None else sign(r['value']) != sign(original))
            local.append(r)
        deletions += local
        story_rows += stories(local,kind,key)
    reference_rows = []
    reference_weights = []
    support = []
    for st in SETS:
        variants = [('pooled',refs[st], '')]
        variants.append(('equal_region',data.reference(st,'equal_region')[0],''))
        for minimum in cfg['sparse_minimums']:
            w, _ = data.reference(st,minimum=minimum)
            variants.append((f'minimum_{minimum}',w,'pooled' if w==refs[st] else ''))
        seen_weights = {}
        reference_cache = {}
        for variant, w, alias in variants:
            weight_key = tuple(sorted(w.items()))
            alias = seen_weights.get(weight_key,'')
            if not alias:
                seen_weights[weight_key] = variant
            mass = math.fsum(refs[st].get(c,0) for c in w)
            for c in CELLS:
                reference_weights.append(dict(comparison_set=st,variant=variant,joint_cell=c,
                                              weight=w.get(c,0.),in_support=c in w,alias_of=alias))
            for g in SETS[st]:
                full = int(data.masks[g].sum())
                retained = int(np.sum(data.masks[g] & np.isin(data.cells,list(w))))
                support.append(dict(comparison_set=st,variant=variant,group=g,full_matches=full,
                                    retained_matches=retained,retained_share=retained/full if full else None,
                                    common_cells=len(w),original_reference_mass=mass,alias_of=alias))
            for t in tt:
                if not t['weighted'] or t['comparison_set'] != st:
                    continue
                # Identical weights have identical metrics; reuse rather than count as new evidence.
                if alias:
                    r = dict(reference_cache[t['target_id'],alias])
                else:
                    r = dict(base[t['target_id']]) if variant=='pooled' else data.evaluate(t,weights=w)
                reference_cache[t['target_id'],variant] = r
                reference_rows.append(dict(target_id=t['target_id'],comparison_set=st,variant=variant,alias_of=alias,
                    **r,original_reference_mass=mass,common_cells=len(w),
                    original_value=base[t['target_id']]['value'],
                    direction_changed=None if r['value'] is None else sign(r['value'])!=sign(base[t['target_id']]['value'])))
    weights_rows = []
    concentration_rows = []
    for st, ww in refs.items():
        for g in SETS[st]:
            idx = np.flatnonzero(data.masks[g] & np.isin(data.cells,list(ww)))
            counts = Counter(data.cells[idx])
            a = np.array([ww[data.cells[i]]/counts[data.cells[i]] for i in idx])
            stats = concentration(a)
            for i,v in zip(idx,a):
                weights_rows.append(dict(comparison_set=st,group=g,match_id=data.rows[i]['match_id'],
                                         joint_cell=data.cells[i],match_weight=float(v)))
            concentration_rows.append(dict(comparison_set=st,group=g,dimension='summary',level='ALL',
                matches=len(idx),weight=1.,**stats))
            for dim, keys in [('cell',data.cells[idx]),('year',data.years[idx])]:
                for k in sorted(set(keys)):
                    mm = keys==k
                    concentration_rows.append(dict(comparison_set=st,group=g,dimension=dim,level=str(k),
                        matches=int(mm.sum()),weight=float(a[mm].sum()),max_match_weight=None,
                        weight_concentration_equivalent_matches=None))
            for team in sorted(set(data.home[idx])|set(data.away[idx])):
                mm = (data.home[idx]==team)|(data.away[idx]==team)
                concentration_rows.append(dict(comparison_set=st,group=g,dimension='team_either_role',level=team,
                    matches=int(mm.sum()),weight=float(a[mm].sum()),max_match_weight=None,
                    weight_concentration_equivalent_matches=None))
    conclusions = []
    for t in tt:
        tid = t['target_id']
        dr = [r for r in deletions if r['target_id']==tid and r['affected']]
        rr = [r for r in reference_rows if r['target_id']==tid and r['variant']!='pooled' and not r['alias_of']]
        changes = [r for r in dr+rr if r['direction_changed']]
        missing = [r for r in dr+rr if r['status']=='unsupported']
        vals = [r['value'] for r in dr if r['value'] is not None]
        extreme = max([r for r in dr if r['change'] is not None],key=lambda r: abs(r['change']),default=None)
        row = dict(target_id=tid,label=t['label'],original_value=base[tid]['value'],
            evidence='sensitive' if changes else 'direction_preserved_with_support_gaps' if missing else 'direction_preserved_in_checked_variations',
            affected_deletions=len(dr),calculated_affected_deletions=sum(r['status']=='calculated' for r in dr),
            deletion_sign_changes=sum(bool(r['direction_changed']) for r in dr),
            reference_sign_changes=sum(bool(r['direction_changed']) for r in rr),
            unsupported_variations=len(missing),deletion_min=min(vals) if vals else None,deletion_max=max(vals) if vals else None,
            largest_change_kind=extreme['scenario_kind'] if extreme else '',largest_change_key=extreme['scenario_key'] if extreme else '',
            largest_change=extreme['change'] if extreme else None,
            largest_change_removed_share=extreme['removed_share'] if extreme else None,
            formal_inference=False,refitted=False,human_review=False)
        for kind in ['year','team']:
            sub = [r for r in deletions if r['target_id']==tid and r['scenario_kind']==kind]
            vv = [r['value'] for r in sub if r['value'] is not None]
            row.update({kind+'_total':len(sub),kind+'_affected':sum(r['affected'] for r in sub),
                        kind+'_unsupported':sum(r['status']=='unsupported' for r in sub),
                        kind+'_sign_changes':sum(bool(r['direction_changed']) for r in sub),
                        kind+'_min':min(vv) if vv else None,kind+'_max':max(vv) if vv else None})
        conclusions.append(row)
    return dict(targets=target_rows,deletion_results=deletions,reference_sensitivity=reference_rows,
                reference_weights=reference_weights,reference_support=support,match_weights=weights_rows,
                weight_concentration=concentration_rows,conclusion_review=conclusions,story_results=story_rows)


def load_sources(cfg,config_path):
    inputs = {config_path:file_hash(ROOT/config_path)}
    parents = {}
    for key in ['evaluation','diagnostics']:
        folder = ROOT/'outputs/logs/regional_effectiveness'/cfg[key+'_run']
        manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8-sig'))
        hand = json.loads((folder/'handoff_adoption.json').read_text(encoding='utf-8-sig'))
        if file_hash(folder/'manifest.json') != hand['manifest_sha256'] or not hand['passed']:
            raise ValueError('INVALID_PARENT_ADOPTION:'+key)
        for name, binding in [('independent_audit.json','independent_audit_sha256'),('adoption.json','original_adoption_sha256')]:
            if file_hash(folder/name) != hand[binding]:
                raise ValueError('PARENT_HANDOFF_CHANGED:'+name)
        for path,h in manifest['outputs'].items():
            if file_hash(ROOT/path)!=h:
                raise ValueError('PARENT_OUTPUT_CHANGED:'+path)
            inputs[path]=h
        for name in ['manifest.json','handoff_adoption.json','independent_audit.json','adoption.json']:
            p = folder/name
            inputs[p.relative_to(ROOT).as_posix()] = file_hash(p)
        parents[key] = manifest
    if parents['diagnostics']['identity']['protocol']['source_run'] != cfg['evaluation_run']:
        raise ValueError('PARENT_RUNS_NOT_ALIGNED')
    tab = ROOT/'outputs/tables/regional_effectiveness'
    allrows = read_rows(tab/cfg['evaluation_run']/'evaluation_matches.csv')
    unique(allrows,'parent')
    rows = [r for r in allrows if cfg['main_years'][0]<=int(r['year'])<=cfg['main_years'][1]]
    mem = unique(read_rows(tab/cfg['diagnostics_run']/'strata_membership.csv'),'membership')
    if len(rows)!=cfg['expected_matches'] or {r['match_id'] for r in rows}!=set(mem):
        raise ValueError('COHORT_OR_MEMBERSHIP_CHANGED')
    cuts = json.loads((ROOT/f"outputs/logs/regional_effectiveness/{cfg['diagnostics_run']}/thresholds.json").read_text(encoding='utf-8-sig'))
    classified = []
    for r in rows:
        c = classify(r,cuts,5)
        m = mem[r['match_id']]
        if any(c[k]!=m[k] for k in ['date','home_region','home_unit','signed_gap','absolute_gap','uncertainty','history','joint_cell']):
            raise ValueError('MEMBERSHIP_DISAGREES:'+r['match_id'])
        if r['date'][:4]!=r['year'] or r['training_max']>=r['date'] or r['prediction_cutoff']>=r['date']:
            raise ValueError('INVALID_PREMATCH_CUTOFF')
        classified.append(c)
    return sorted(classified,key=lambda r:(r['date'],r['match_id'])),inputs


def run(config_path='config/regional_effectiveness_stability.json'):
    cfg = json.loads((ROOT/config_path).read_text(encoding='utf-8-sig'))
    if cfg['schema_version']!='regional-stability-v1' or cfg['target_ids']!=[t['target_id'] for t in targets()]:
        raise ValueError('PROTOCOL_TARGETS_CHANGED')
    rows, inputs = load_sources(cfg,config_path)
    code_names = ['src/regional_stability.py','scripts/analyze_regional_stability.py','scripts/audit_regional_stability.py',
                  'tests/test_regional_stability.py','src/regional_diagnostics.py','src/regional_effectiveness.py',
                  'src/data_contract.py','src/strength/io.py']
    identity = dict(protocol=cfg,inputs=inputs,code={p:file_hash(ROOT/p) for p in code_names},environment=environment())
    rid = 'regional-stability-'+fingerprint(identity)[:20]
    log = ROOT/'outputs/logs/regional_effectiveness'/rid
    table = ROOT/'outputs/tables/regional_effectiveness'/rid
    pointer = ROOT/'outputs/logs/regional_effectiveness/stability_pointer.json'
    if (log/'manifest.json').exists():
        for p,h in json.loads((log/'manifest.json').read_text(encoding='utf-8-sig'))['outputs'].items():
            if file_hash(ROOT/p)!=h:
                raise ValueError('SEALED_OUTPUT_CHANGED:'+p)
        write_json(pointer,dict(run_id=rid,log_directory=log.relative_to(ROOT).as_posix(),table_directory=table.relative_to(ROOT).as_posix(),steps_completed=[1,2,3,4,5],formal_inference=False))
        print('STABILITY_VERIFIED',rid,flush=True)
        return log,table
    log.mkdir(parents=True,exist_ok=True)
    table.mkdir(parents=True,exist_ok=True)
    write_json(log/'started.json',dict(identity=identity))
    write_json(log/'protocol.json',cfg)
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
        for p in code_names+[config_path]:
            z.writestr(zipfile.ZipInfo(p,(1980,1,1,0,0,0)),(ROOT/p).read_bytes())
    atomic_bytes(log/'source_snapshot.zip',archive.getvalue())
    try:
        data = Cohort(rows,cfg['probability_clip'])
        tables = compute(data,cfg)
        # Reconcile the exact original contrasts against adopted published parents.
        oldtab = ROOT/'outputs/tables/regional_effectiveness'/cfg['diagnostics_run']
        std = {(r['comparison_set'],r['group'],r['model']):r for r in read_rows(oldtab/'standardized_metrics.csv')}
        base = {r['target_id']:r for r in tables['targets']}
        checks = []
        def check(name,got,want):
            error=abs(got-want)
            checks.append(dict(name=name,error=error,passed=error<2e-8))
            if error>=2e-8:raise ValueError('BASELINE_MISMATCH:'+name)
        evtab = ROOT/'outputs/tables/regional_effectiveness'/cfg['evaluation_run']
        metrics = {(r['group'],r['model']):r for r in read_rows(evtab/'regional_metrics.csv') if r['scope']=='main'}
        # Scope labels are checked explicitly rather than silently falling back.
        if not metrics:raise ValueError('UNRECOGNIZED_PARENT_METRIC_SCOPE')
        for i,g in enumerate(SETS['primary5'],1):
            check(f'T{i:02d}',base[f'T{i:02d}']['value'],float(metrics[g,'joint']['log_loss'])-float(metrics[g,'strength']['log_loss']))
        for tid,a,b,st in [('T06','002','150',''),('T07','002','150','primary5'),
                            ('T10','SOUTH_AMERICA','OTHER_AMERICAS',''),('T11','SOUTH_AMERICA','OTHER_AMERICAS','americas2')]:
            expected = (float(std[st,a,'joint']['standardized_loss'])-float(std[st,b,'joint']['standardized_loss'])) if st else (float(metrics[a,'joint']['log_loss'])-float(metrics[b,'joint']['log_loss']))
            check(tid,base[tid]['value'],expected)
        africa = read_rows(oldtab/'africa_calibration.csv')
        for tid,bin_no in [('T08',1),('T09',3)]:
            old = next(r for r in africa if r['dimension']=='uncertainty' and r['level']=='low' and int(r['probability_bin'])==bin_no)
            check(tid,base[tid]['value'],float(old['bias_pp']))
        check('T12',base['T12']['value'],float(std['primary5','009','joint']['standardized_loss'])-float(std['primary5','009','strength']['standardized_loss']))
        check('T13',base['T13']['value'],float(std['primary5','009','joint']['standardized_bias_pp']))
        for name,rr in tables.items():
            fields=list(dict.fromkeys(k for row in rr for k in row))
            atomic_bytes(table/(name+'.csv'),csv_bytes(fields,rr))
        write_json(table/'data_dictionary.json',dict(
            shared='status=unsupported => value blank; no imputation. refitted/formal_inference/human_review false.',
            targets='Definitions plus baseline; negative paired loss difference favors joint model; bias is percentage points.',
            deletion_results='All years/union of team IDs; both roles removed once; affected=false identifies no-op. Fixed original weights.',
            reference_sensitivity='Changes target population. original_matches is the full arm; remaining_matches retains only weighted supported cells; reference_support gives each arm separately.',
            reference_support='Retained actual counts and original reference mass; minimum 10/20 are sensitivity settings, not evidence admission.',
            match_weights='Weight w_cell / observed group-cell count, normalized separately in each set/group.',
            weight_concentration='Equivalent count measures weighting only; not an independent sample size. Team weights overlap.',
            conclusion_review='Direction stability on observed finite history only, not p-values, confidence intervals or future guarantee.',
            story_results='Paired narrative checked within the same deletion; unsupported when either contrast cannot be calculated.'))
        write_json(table/'display_data.json',dict(run_id=rid,source_runs=[cfg['evaluation_run'],cfg['diagnostics_run']],
            conclusions=tables['conclusion_review'],reference_sensitivity=tables['reference_sensitivity'],
            stories_original=[r for r in tables['story_results'] if r['scenario_kind']=='original'],
            formal_inference=False,refitted=False,human_review=False,
            interpretation='finite-history stability only; deletion ranges are not confidence intervals; changed references change target population'))
        review = dict(passed=True,step5_complete=True,main_matches=len(rows),
                      unique_teams=len(set(data.home)|set(data.away)),years=15,
                      baseline_checks=checks,table_rows={k:len(v) for k,v in tables.items()},
                      new_fits=0,new_ratings=0,new_simulations=0,formal_inference=False,human_review=False,
                      question_closed=False)
        write_json(log/'review.json',review)
        outputs={p.relative_to(ROOT).as_posix():file_hash(p) for d in [log,table] for p in d.iterdir() if p.is_file() and p.name not in ['manifest.json','adoption.json','failure.json']}
        write_json(log/'manifest.json',dict(identity=identity,outputs=outputs))
        write_json(log/'adoption.json',dict(run_id=rid,manifest_sha256=file_hash(log/'manifest.json'),step5_complete=True,
                                         formal_inference=False,human_review=False,independent_audit_pending=True))
        write_json(pointer,dict(run_id=rid,log_directory=log.relative_to(ROOT).as_posix(),table_directory=table.relative_to(ROOT).as_posix(),steps_completed=[1,2,3,4,5],formal_inference=False))
        print('STABILITY_COMPLETE',rid,json.dumps(review,ensure_ascii=False),flush=True)
        return log,table
    except Exception as exc:
        write_json(log/'failure.json',dict(type=type(exc).__name__,message=str(exc)))
        raise
