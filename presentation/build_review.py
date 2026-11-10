from pathlib import Path
import csv,json,math,hashlib,base64,shutil
import build
H=Path(__file__).resolve().parent;R=H.parent
import runpy
runpy.run_path(str(H/'make_repository_visual.py'))
D=build.data();D['yearly']=build.rows('yearly')
path=R/'outputs/tables/tournaments/tournaments-4893e38db46f83f6c219/type_estimates.csv'
D['eraTypes']=[x for x in csv.DictReader(path.open(encoding='utf-8-sig')) if x['scope']=='era' and x['estimand']=='raw']
source=R/'data/processed/strength/strength-delivery-ca43fe498cd43ec8e21f/study_prematch_features.csv';chosen={'China':'team:china','South Africa':'team:south-africa'};pts={n:{} for n in chosen}
for row in csv.DictReader(source.open(encoding='utf-8-sig')):
 for name,prefix in chosen.items():
  for role in ['home','away']:
   if row[role].split('@')[0]==prefix:
    point={'date':row['date'],'mean':float(row[role+'_mean']),'sd':math.sqrt(float(row[role+'_variance'])),'match_id':row['match_id']}
    year=row['date'][:4]
    if year not in pts[name] or (point['date'],point['match_id'])>(pts[name][year]['date'],pts[name][year]['match_id']):pts[name][year]=point
for n,ys in pts.items():
 assert ys,n
 D['states'][n]=[ys[y] for y in sorted(ys)]
world=json.loads((H/'assets/world.geojson').read_text(encoding='utf-8'));D['map']=[]
for f in world['features']:
 prop=f['properties'];g=f['geometry']
 if prop['CONTINENT']=='Antarctica':continue
 D['map'].append({'name':prop['ADMIN'],'continent':prop['CONTINENT'],'geometry':g})
registry=list(csv.DictReader((R/'outputs/tables/regions/regions-0a1c61664a722e6c641f/study_team_registry.csv').open(encoding='utf-8-sig')))
lookup={x['source_team_label']:x for x in registry}
alias={'United States of America':'United States','United Republic of Tanzania':'Tanzania','Republic of Serbia':'Serbia','Democratic Republic of the Congo':'DR Congo','Republic of the Congo':'Congo','Ivory Coast':'Ivory Coast','South Korea':'South Korea','North Korea':'North Korea','The Bahamas':'Bahamas','Czechia':'Czech Republic','United Kingdom':'England','Ireland':'Republic of Ireland','eSwatini':'Eswatini'}
for f in D['map']:
 row=lookup.get(alias.get(f['name'],f['name']))
 f['studyRegion']=row['study_region'] if row else None
 f['unit']=row['study_unit'] if row else None
for f in D['map']:
 if f['name']=='Greenland':f['studyRegion']='019';f['unit']='021';f['map_only']=True
D['geoGroups']=list(csv.DictReader((R/'outputs/tables/regions/regions-0a1c61664a722e6c641f/group_summary.csv').open(encoding='utf-8-sig')))
D['frames3d']=['data:image/png;base64,'+base64.b64encode(x.read_bytes()).decode() for x in sorted((H/'assets/history3d').glob('frame*.png'))]
D['factorPhotos']={x:'data:image/png;base64,'+base64.b64encode((H/f'assets/{x}_source.png').read_bytes()).decode() for x in ['ranking','wembley','leagues','schedule'] if (H/f'assets/{x}_source.png').exists()}
D['factorPhotos']['wembley']='data:image/jpeg;base64,'+base64.b64encode((H/'assets/wembley_user.jpg').read_bytes()).decode()
D['photo']='data:image/jpeg;base64,'+base64.b64encode((H/'assets/brazil_training.jpg').read_bytes()).decode()
D['github']='https://github.com/RG0104151433/python-football-project'
(H/'assets/review_data.json').write_text(json.dumps(D,ensure_ascii=False),encoding='utf-8')
html=(H/'review.template.html').read_text(encoding='utf-8').replace('__DATA__',json.dumps(D,ensure_ascii=False).replace('</','<\\/'))
html=html.replace('</body>', '</body>')
html=html.replace('</html>','<script>'+ (H/'refinement.js').read_text(encoding='utf-8')+'</script><script>'+ (H/'final_polish.js').read_text(encoding='utf-8')+'</script></html>')
(H/'index.html').write_text(html,encoding='utf-8')
version=H/'versions/v3_20261110';version.mkdir(parents=True,exist_ok=True)
(version/'index.html').write_text(html,encoding='utf-8')
shutil.copyfile(H/'repository_architecture.html',version/'repository_architecture.html')
# Empty results are deliberately separate from the sealed forecast ledger.
p=H/'results_template.csv'
if not p.exists():
 with p.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['fixture_id','status','home_score','away_score','source_url','checked_at']);w.writerows([[x['id'],'pending','','','',''] for x in D['forecasts']])
manifest={'decision_log_id':'R20261110-03','source':'presentation/build_review.py','model_refit':False,'forecasts_modified':False,'source_files':{k:v for k,v in D['sourceFiles'].items()},'extra_sources':[str(path.relative_to(R)),str(source.relative_to(R))],'outputs':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in [H/'index.html',H/'assets/review_data.json',p]},'countries':list(D['states']),'results':'No actual scores supplied; all pending by default'}
(H/'review_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Review deck built: six countries, 52 sealed forecasts, separate results import')
