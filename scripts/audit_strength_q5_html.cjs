// Verify control logic in an isolated stub. This is NOT a rendered browser test.
const fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(process.argv[2],'utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
if(scripts.length!==1)throw new Error('EXPECTED_ONE_CONTROL_SCRIPT');
const code=new vm.Script(scripts[0][1]);let checks=0;
function assert(ok,label){checks++;if(!ok)throw new Error(label);}
function create(search=''){
  const ids=Object.fromEntries(['previous','next','page','appendix','appendixButton','closeAppendix','full'].map(x=>[x,{}]));
  ids.appendix.open=false;ids.appendix.showModal=()=>ids.appendix.open=true;ids.appendix.close=()=>ids.appendix.open=false;
  const pages=[{},{},{}],listeners={};
  const doc={querySelectorAll:()=>pages,getElementById:id=>ids[id],addEventListener:(name,f)=>listeners[name]=f,
    fullscreenElement:null,documentElement:{},exitFullscreen:()=>doc.fullscreenElement=null};
  doc.documentElement.requestFullscreen=()=>{doc.fullscreenElement={};return Promise.resolve();};
  code.runInNewContext({document:doc,location:{search},URLSearchParams});
  return {ids,pages,doc,key:key=>listeners.keydown({key,preventDefault(){}})};
}
const x=create();assert(x.ids.page.textContent==='1 / 3','initial_page');assert(x.ids.previous.disabled,'initial_previous_disabled');
assert(x.pages.filter(p=>!p.hidden).length===1,'one_visible_slide');
x.ids.next.onclick();assert(x.ids.page.textContent==='2 / 3','next_button');
x.key('ArrowRight');assert(x.ids.page.textContent==='3 / 3','right_arrow');assert(x.ids.next.disabled,'last_next_disabled');
x.key('PageDown');assert(x.ids.page.textContent==='3 / 3','upper_boundary');
x.key('ArrowLeft');assert(x.ids.page.textContent==='2 / 3','left_arrow');
x.key('PageUp');assert(x.ids.page.textContent==='1 / 3','page_up');
x.key('PageUp');assert(x.ids.page.textContent==='1 / 3','lower_boundary');
x.ids.appendixButton.onclick();assert(x.ids.appendix.open,'appendix_open');x.key('ArrowRight');assert(x.ids.page.textContent==='1 / 3','modal_stops_slide_keys');
x.ids.closeAppendix.onclick();assert(!x.ids.appendix.open,'appendix_close');
x.key(' ');assert(x.ids.page.textContent==='2 / 3','space_navigation');
x.ids.previous.onclick();assert(x.ids.page.textContent==='1 / 3','previous_button');
x.ids.full.onclick();assert(x.doc.fullscreenElement!==null,'fullscreen_request_logic');x.key('f');assert(x.doc.fullscreenElement===null,'fullscreen_exit_logic');
const y=create('?page=3');assert(y.ids.page.textContent==='3 / 3','direct_page_parameter');
assert(y.pages.filter(p=>!p.hidden).length===1,'one_visible_slide_after_parameter');
console.log(JSON.stringify({passed:true,logical_checks:checks,actual_browser:false,DOM_layout_engine:false,method:'isolated Node vm and DOM stubs; no local HTML browser navigation'}));
