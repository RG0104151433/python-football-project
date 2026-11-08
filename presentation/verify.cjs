// Local browser QA for the presentation, not a new scientific experiment.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const {createRequire} = require('node:module');
const runtime = process.env.PRESENTATION_NODE_MODULES;
const load = runtime ? createRequire(path.join(runtime, 'package.json')) : require;
const {chromium} = load('playwright');
let activeBrowser;

(async()=>{
 const here=__dirname, out=path.join(here,'_build');fs.mkdirSync(path.join(out,'screens'),{recursive:true});
 const browser=activeBrowser=await chromium.launch({executablePath:process.env.PRESENTATION_BROWSER || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const context=await browser.newContext({viewport:{width:1600,height:900},deviceScaleFactor:1});
 await context.setOffline(true);
 const page=await context.newPage(), errors=[], requests=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
 await page.goto(pathToFileURL(path.join(here,'index.html')).href);await page.waitForFunction(()=>window.presentationAPI);
 assert.equal(await page.locator('.slide').count(),10);
 await page.locator('[data-pick="Home win"]').click();assert.match(await page.locator('#poll-output').textContent(),/Home win/);
 await page.evaluate(()=>presentationAPI.goTo(2));await page.locator('[data-pattern="types"]').click();await page.locator('#adjust-toggle').click();
 assert.match(await page.locator('#patterns-chart').textContent(),/-2\.8831/);
 await page.locator('[data-pattern="eras"]').click();await page.locator('#scale-toggle').click();assert.match(await page.locator('#patterns-chart').textContent(),/Zoomed/);
 await page.evaluate(()=>presentationAPI.goTo(3));await page.locator('[data-phase="4"]').click();assert.match(await page.locator('#mechanism-insight').textContent(),/Never use/);
 assert.equal(await page.locator('#mechanism').evaluate(e=>getComputedStyle(e).position),'relative');
 await page.evaluate(()=>presentationAPI.goTo(4));await page.selectOption('#team-select','Japan');
 await page.locator('#year-range').evaluate(e=>{e.value='1990';e.dispatchEvent(new Event('input',{bubbles:true}));});
 await page.locator('#year-play').click();await page.waitForTimeout(450);await page.locator('#year-play').click();assert.ok((await page.evaluate(()=>presentationAPI.getState().year))>1990);
 await page.locator('#year-range').evaluate(e=>{e.value='2024';e.dispatchEvent(new Event('input',{bubbles:true}));});
 await page.evaluate(()=>presentationAPI.goTo(5));await page.locator('#model-reset').click();await page.locator('#model-reveal').click();await page.locator('#model-reveal').click();await page.locator('#metric-accuracy').click();assert.match(await page.locator('#models-chart').textContent(),/70\.01/);await page.locator('#metric-loss').click();
 assert.equal(await page.locator('#models-chart .growbar').first().evaluate(e=>getComputedStyle(e).animationName),'growbar');
 assert.ok(await page.evaluate(()=>[...document.styleSheets[0].cssRules].some(r=>r.type===7&&r.name==='growbar')));
 await page.evaluate(()=>presentationAPI.goTo(6));await page.locator('[data-combo="cumulative_1950__outcome_12y"]').click();assert.equal(await page.locator('#window-choices .active').count(),1);
 await page.evaluate(()=>presentationAPI.goTo(7));await page.locator('[data-region="Africa"]').click();assert.match(await page.locator('#region-insight').textContent(),/Egypt/);await page.locator('[data-region="Oceania"]').click();assert.match(await page.locator('#region-count').textContent(),/148/);await page.locator('[data-region="Africa"]').click();
 await page.evaluate(()=>presentationAPI.goTo(8));await page.locator('#forecast-uncertainty').click();assert.match(await page.locator('#forecast-chart').textContent(),/43\.54/);
 const opts=await page.locator('#fixture-select option').evaluateAll(xs=>xs.map(x=>({value:x.value,label:x.textContent})));
 const ukraine=opts.find(x=>x.label.includes('Ukraine')&&x.label.includes('Georgia'));assert.ok(ukraine);await page.selectOption('#fixture-select',ukraine.value);assert.match(await page.locator('#forecast-description').textContent(),/No joint estimate/);await page.locator('#native-toggle').click();assert.match(await page.locator('#forecast-kind').textContent(),/SEPARATE AUXILIARY/);await page.locator('#native-toggle').click();
 await page.selectOption('#fixture-select',opts.find(x=>x.label.includes('England')&&x.label.includes('Croatia')).value);
 for(const option of opts){await page.selectOption('#fixture-select',option.value);assert.ok((await page.locator('#forecast-description').textContent()).length>0);}
 await page.selectOption('#fixture-select',opts.find(x=>x.label.includes('England')&&x.label.includes('Croatia')).value);
 await page.locator('#notes-toggle').click();assert.equal(await page.locator('#notes').isVisible(),true);await page.keyboard.press('Escape');assert.equal(await page.locator('#notes').isVisible(),false);
 await page.locator('#sources-open').click();assert.equal(await page.locator('#sources').isVisible(),true);await page.locator('#sources-close').click();
 const overflow=[];
 for(let i=0;i<10;i++){
  await page.evaluate(i=>{presentationAPI.goTo(i);const s=document.querySelector('.slide.active');const max=+s.dataset.steps;while(presentationAPI.getState().steps[i]<max)presentationAPI.advance();},i);
  const box=await page.locator('.slide.active').evaluate(e=>({scroll:e.scrollHeight,height:e.clientHeight,width:e.scrollWidth,clientWidth:e.clientWidth}));
  if(box.scroll>box.height+2||box.width>box.clientWidth+2)overflow.push({slide:i+1,...box});
  await page.screenshot({path:path.join(out,'screens',`${String(i+1).padStart(2,'0')}.png`),animations:'disabled'});
 }
 await page.setViewportSize({width:1366,height:768});const compactOverflow=[];
 for(let i=0;i<10;i++){await page.evaluate(i=>presentationAPI.goTo(i),i);const box=await page.locator('.slide.active').evaluate(e=>({scroll:e.scrollHeight,height:e.clientHeight}));if(box.scroll>box.height+2)compactOverflow.push({slide:i+1,...box});}
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>presentationAPI.goTo(0));assert.equal(await page.locator('#next').isVisible(),true);
 await page.setViewportSize({width:1600,height:900});await page.evaluate(()=>presentationAPI.goTo(0));
 await page.pdf({path:path.join(here,'handout.pdf'),preferCSSPageSize:true,printBackground:true});
 await page.goto(pathToFileURL(path.join(here,'figure_comparison.html')).href);assert.equal(await page.locator('img').count(),4);assert.ok(await page.locator('img').evaluateAll(xs=>xs.every(x=>x.complete&&x.naturalWidth>0)));
 const result={date:'2026-11-08',browser:'Chromium / local Chrome executable',slides:10,browser_network_offline:true,fixture_selections_rendered:opts.length,interaction_checks:'poll, composition/scale, workflow, year playback, model/metric, history choice, regions, all fixture types, uncertainty, separate auxiliary model, notes, sources, live animation CSS',page_errors:errors,external_page_requests:requests,desktop_overflow:overflow,compact_projector_overflow:compactOverflow,mobile_navigation:true,comparison_images_loaded:4,print_export:'presentation/handout.pdf',scientific_model_refit:false};
 fs.writeFileSync(path.join(out,'browser_check.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 await browser.close();assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);assert.deepEqual(overflow,[]);assert.deepEqual(compactOverflow,[]);
})().catch(async e=>{console.error(e);if(activeBrowser)await activeBrowser.close();process.exitCode=1;});
