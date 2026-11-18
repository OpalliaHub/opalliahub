/* Regression checks for the resume recommendation interface.
 * Run: node scripts/check_recommendation_ui.js [path/to/app.js]
 * Uses a small simulated DOM and deferred requests to check state transitions,
 * escaping and races. It does not replace real-browser layout/accessibility QA.
 * All resumes and jobs below are fictional fixtures. No browser/API/AI is called.
 */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nodes=new Map();
function node(key='node'){if(nodes.has(key))return nodes.get(key);const n={value:'',textContent:'',innerHTML:'',hidden:false,disabled:false,checked:false,dataset:{},style:{},options:[{outerHTML:'<option></option>',value:''}],children:[],listeners:{},scrollIntoView(){},classList:{contains(){return false;},toggle(){return false;},add(){},remove(){}},setAttribute(){},removeAttribute(){},addEventListener(type,fn){this.listeners[type]=fn;},append(n){this.children.push(n);},replaceChildren(){this.children=[];this.innerHTML='';this.textContent='';},remove(){},showModal(){this.open=true;},close(){this.open=false;},getAttribute(){return null;},reportValidity(){return true;}};nodes.set(key,n);return n;}
const scheduled=[];
const sandbox={console,Map,Set,Date,JSON,Number,String,Boolean,Array,Object,Error,Promise,URL,Blob,Intl,setTimeout:fn=>{scheduled.push(fn);return 1;},clearTimeout(){},document:{body:{dataset:{}},querySelector:node,querySelectorAll(){return [];},addEventListener(){},dispatchEvent(){},createElement(){return node('element'+nodes.size);}},window:{location:{protocol:'http:'},addEventListener(){},scrollTo(){}},location:{hash:''},history:{replaceState(){}},matchMedia(){return {matches:false};},CustomEvent:function(){},confirm(){return true;}};
vm.createContext(sandbox);
let source=fs.readFileSync(process.argv[2]||require('path').resolve(__dirname,'../jobcompass/static/app.js'),'utf8');
source=source.replace("go(location.hash.slice(1)||'analytics');\naction(null,async()=>applyMeta(await api('/api/status')));",'');
const tail=source.lastIndexOf('\n}');
source=source.slice(0,tail)+`\nglobalThis.ui={refresh,sameRecommendationData,invalidateRecommendations,renderRecommendations,clearRecommendationOutput,track,openJob,setState:value=>{state=value;stateLoaded=true;},setAPI:fn=>api=fn,revision:()=>recommendationRevision,result:()=>recommendationResult,busy:()=>recommendationBusy,form:$('#recommendations-form')};`+source.slice(tail);
vm.runInContext(source,sandbox);
const ui=sandbox.ui;
const job={id:'one',title:'Analyst',company:'Example',skills:['Python'],description:'Python reports',source:'JobsDB',source_family:'JobsDB',location:'HK',status:'',note:''};
const state={resume:'A fictional CV with Python analysis project experience.',preferences:{location:'HK'},jobs:[job]};
assert(ui.sameRecommendationData(state,{...state,jobs:[{...job,status:'收藏',note:'new note',score:99}]}));
assert(!ui.sameRecommendationData(state,{...state,jobs:[{...job,description:'Changed requirements'}]}));
assert(!ui.sameRecommendationData(state,{...state,resume:'Edited CV'}));
assert(!ui.sameRecommendationData(state,{...state,preferences:{location:'London'}}));
ui.setState(state);
const output={profile:{strengths:[{title:'<img src=x>',skills:['Python'],evidence:['<script>alert(1)</script>']}],questions:[],excluded_skills:[]},summary:{total:1,eligible:1,returned:1,available_after_score_filter:1},jobs:[{...job,score:81.2,effective_coverage:85,matched_skills:['Python'],missing_skills:[],reasons:['<script>bad</script>'],breakdown:[{key:'skills',label:'<b>Unsafe label</b>',value:90,weight:40}],warnings:[]}],method:{version:'1',weights:{skills:.4},limitations:['Ranking only']}};
ui.renderRecommendations(output);
assert(nodes.get('#recommendations-strengths').innerHTML.includes('&lt;script&gt;'));
assert(!nodes.get('#recommendations-jobs').innerHTML.includes('<script>'));
assert(nodes.get('#recommendations-jobs').innerHTML.includes('个性化匹配分'));
assert(!nodes.get('#recommendations-results').hidden);
const revision=ui.revision();ui.invalidateRecommendations('Edited');
assert.equal(ui.revision(),revision+1);assert.equal(ui.result(),null);assert(nodes.get('#recommendations-results').hidden);assert.equal(nodes.get('#recommendations-jobs').innerHTML,'');
let rendered=0,stale=0,failed=0,requests=[];
ui.setAPI(async path=>{requests.push(path);return {status:'done',result:output};});
(async()=>{
 await ui.track('stale-task','优势与岗位推荐',()=>rendered++,{skipRefresh:true,isCurrent:()=>false,onStale:()=>stale++});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(rendered,0);assert.equal(stale,1);assert(!requests.includes('/api/state'));
 ui.setAPI(async()=>({status:'error',error:'Inputs changed'}));
 await ui.track('error-task','优势与岗位推荐',()=>rendered++,{skipRefresh:true,isCurrent:()=>true,onError:()=>failed++});
 await new Promise(resolve=>setImmediate(resolve));assert.equal(failed,1);assert.equal(rendered,0);
 nodes.get('#resume-text').value=state.resume;nodes.get('#pref-location').value='HK';nodes.get('#recommendations-min-score').value='0';
 let saveResolve;requests=[];
 ui.setAPI(path=>{requests.push(path);if(path==='/api/resume')return new Promise(resolve=>saveResolve=resolve);throw new Error('Unexpected '+path);});
 const submit=ui.form.listeners.submit({preventDefault(){},currentTarget:ui.form});
 await new Promise(resolve=>setImmediate(resolve));
 nodes.get('#resume-text').value='A new draft with different skills';nodes.get('#resume-text').listeners.input();
 saveResolve({});await submit;
 assert.equal(requests.length,1);assert(!requests.includes('/api/recommendations'));assert.equal(ui.busy(),false);
 ui.openJob('one',{...output.jobs[0],score:81.2});
 assert(nodes.get('#job-detail').innerHTML.includes('个性化匹配分 81.2 / 100'));
 assert.equal(state.jobs[0].score,undefined);
 ui.invalidateRecommendations('Edited while detail open');assert.equal(nodes.get('#job-dialog').open,false);
 let stateResolve;
 nodes.get('#resume-text').value='starting draft';nodes.get('#pref-location').value='';nodes.get('#pref-years').value='';
 ui.setAPI(()=>new Promise(resolve=>stateResolve=resolve));
 const loading=ui.refresh(true);
 nodes.get('#resume-text').value='typed while initial loading';nodes.get('#pref-location').value='Singapore';
 stateResolve({...state,jobs:[],resume:'stored old resume',preferences:{location:'HK',experience_years:3},profile:{},ai:{},logs:[],active_tasks:[]});
 await loading;
 assert.equal(nodes.get('#resume-text').value,'typed while initial loading');assert.equal(nodes.get('#pref-location').value,'Singapore');assert.equal(nodes.get('#pref-years').value,3);
 console.log('PASS: initial state preserves independently edited draft fields; snapshot changes; bookmark/notes stability; escaped output; invalidation clears; stale task suppressed; task failure callback; skip full-state refresh; edited draft during save aborts; recommendation detail score preserved without modifying baseline.');
})().catch(error=>{console.error(error);process.exitCode=1;});
