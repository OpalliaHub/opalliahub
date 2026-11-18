'use strict';
if (window.location.protocol === 'file:') {
  document.querySelector('#file-launch').hidden = false;
  document.querySelector('.sidebar').inert = true;
  document.querySelector('main').inert = true;
} else {
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const escapeHTML = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names = {analytics:'研究总览',discover:'岗位检索',resume:'简历分析',sources:'数据管理',tracker:'投递管理',research:'深度研究',learning:'技能成长'};
let state = {jobs:[],profile:{},preferences:{},ai:{},logs:[]};
let stateLoaded=false,stateLoading=null;
let shown = 15, currentJob = null, currentJobIsRecommendation=false, toastTimer, jobsdbTask = null;
const tasks = new Set();
function toast(message, error=false) {
  clearTimeout(toastTimer); $('#toast').textContent=message; $('#toast').className=error?'error':'';
  $('#toast').style.display='block'; toastTimer=setTimeout(()=>$('#toast').style.display='none',error?8000:4200);
}
async function api(path, body) {
  const response=await fetch(path, body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-JobCompass':'1'},body:JSON.stringify(body)});
  const data=await response.json(); if(!response.ok) throw new Error(data.error||'请求失败'); return data;
}
async function action(button, fn) {
  if(button) button.disabled=true;
  try { await fn(); } catch(e) { toast(e.message||'处理失败，请重试。',true); }
  finally { if(button) button.disabled=false; }
}
function go(page, preserveWorkspaceView=false) {
  if(!Object.prototype.hasOwnProperty.call(names,page))page='analytics';
  if(!preserveWorkspaceView)document.dispatchEvent(new CustomEvent('jobcompass:workspace',{detail:{view:'panel'}}));
  $$('.page').forEach(x=>x.classList.toggle('active',x.id===page));
  $$('.nav').forEach(x=>{const active=x.dataset.page===page;x.classList.toggle('active',active);if(active)x.setAttribute('aria-current','page');else x.removeAttribute('aria-current');});
  $('#breadcrumb').textContent=names[page];
  $('#app-sidebar').classList.remove('open');$('#mobile-menu').setAttribute('aria-expanded','false');
  if(location.hash!=='#'+page)history.replaceState(null,'','#'+page);
  window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  document.dispatchEvent(new CustomEvent('jobcompass:page',{detail:{page}}));
  if(['discover','resume','sources','tracker'].includes(page))action(null,()=>ensureState());
}
$('#mobile-menu').addEventListener('click',()=>{const open=$('#app-sidebar').classList.toggle('open');$('#mobile-menu').setAttribute('aria-expanded',String(open));});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('#app-sidebar').classList.remove('open');$('#mobile-menu').setAttribute('aria-expanded','false');}});
document.addEventListener('click',e=>{if(!e.target.closest('.sidebar')&&!e.target.closest('#mobile-menu')){$('#app-sidebar').classList.remove('open');$('#mobile-menu').setAttribute('aria-expanded','false');}});
window.addEventListener('hashchange',()=>{const page=location.hash.slice(1);if(Object.prototype.hasOwnProperty.call(names,page))go(page);});
document.addEventListener('jobcompass:navigate',event=>go(event.detail.page,Boolean(event.detail.preserveWorkspaceView)));

$$('.nav').forEach(x=>x.addEventListener('click',()=>go(x.dataset.page)));
$$('[data-go]').forEach(x=>x.addEventListener('click',()=>go(x.dataset.go)));
function tags(skills, hits=[]) { return skills.map(s=>`<span class="tag ${hits.includes(s)?'match':''}">${escapeHTML(s)}</span>`).join(''); }
function empty(title,text) { return `<div class="empty"><b>${escapeHTML(title)}</b>${escapeHTML(text)}</div>`; }
function dateLabel(s) { if(!s) return '日期未提供'; const d=new Date(s); return Number.isNaN(d.getTime())?'日期未提供':d.toLocaleDateString('zh-CN'); }
function refreshSelect(selector, values) {
  const select=$(selector), selected=select.value, first=select.options[0].outerHTML;
  select.innerHTML=first+[...new Set(values.filter(Boolean))].sort().map(x=>`<option value="${escapeHTML(x)}">${escapeHTML(x)}</option>`).join('');
  if([...select.options].some(x=>x.value===selected)) select.value=selected;
}
function applyMeta(info) {
  const deployment=info.deployment||{public_mode:false,label:'本地研究工作台'};
  document.body.dataset.deployment=deployment.public_mode?'public':'local';
  $('#deployment-label').textContent=deployment.label||'研究工作台';
  $('#workspace-name').textContent=deployment.public_mode?'公共研究空间':'研究工作空间';
  $('#deployment-note').textContent=deployment.public_mode?'开放访问 · 个人工具按浏览器访客隔离':'本地数据 · 可追溯的分析口径';
  $('#access-label').textContent=deployment.public_mode?'公开访问 · 无需登录':'本地访问 · 无需登录';
  document.querySelectorAll('[data-local-only]').forEach(el=>el.hidden=Boolean(deployment.public_mode));
  document.dispatchEvent(new CustomEvent('jobcompass:state',{detail:{deployment,ai:info.ai}}));
}
async function ensureState(){if(stateLoaded)return;if(!stateLoading)stateLoading=refresh(true).finally(()=>{stateLoading=null;});return stateLoading;}
async function refresh(fill=false, options={}) {
  const previous=state;
  const fields=['#resume-text','#pref-location','#pref-years'];
  const initialDraft=fill?fields.map(selector=>$(selector).value):null;
  state=await api('/api/state');
  if(!options.preserveRecommendations && !sameRecommendationData(previous,state))invalidateRecommendations('简历、偏好或岗位库已更新，请重新生成推荐。');
  stateLoaded=true;applyMeta(state);
  if(fill) {
    const saved=[state.resume||'',state.preferences.location||'',state.preferences.experience_years??''];
    fields.forEach((selector,index)=>{if($(selector).value===initialDraft[index])$(selector).value=saved[index];});
  }
  $('#char-count').textContent=$('#resume-text').value.length+' 字符';
  const real=state.jobs.filter(j=>!j.is_demo), saved=state.jobs.filter(j=>j.status);
  const primary=state.jobs.filter(j=>j.source_family==='JobsDB'&&j.availability!=='expired');
  const best=primary.length?Math.max(...primary.map(j=>j.score||0)):0;
  const numbers=[['JobsDB 岗位',primary.length,'另有 '+(real.length-primary.length)+' 条其他或过期岗位',''],['最高基础匹配分',state.resume?best:'—','满分 100，仅供排序参考',''],['已识别技能',(state.profile.skills||[]).length,'从原始简历提取',''],['收藏与投递',saved.length,'当前个人工作空间','']];
  $('#stats').innerHTML=numbers.map(([title,note,foot,icon])=>`<div class="stat"><div class="stat-top">${title}<span class="stat-icon">${icon}</span></div><div class="stat-number">${note}</div><div class="stat-foot">${foot}</div></div>`).join('');
  $('#welcome').hidden=Boolean(state.resume);
  $('#profile-title').textContent=state.resume?'已识别你的技能画像':'等待认识你';
  $('#profile-subtitle').textContent=state.resume?`${state.profile.education} · ${state.profile.experience_years??'待确认'} 年经验`:'添加简历，提取你已有的技能与经历。';
  $('#profile-skills').innerHTML=tags((state.profile.skills||[]).slice(0,9),(state.profile.skills||[]));
  $('#ai-status').textContent=state.ai.configured?`${state.ai.model} · 已配置`:'未配置 API 密钥';
  $('#ranking-hint').textContent=state.resume?'技能证据 + TF-IDF 文本相关度':'保存简历后可查看匹配度';
  const sourceSelect=$('#source-filter'), selectedSource=sourceSelect.value;
  sourceSelect.innerHTML='<option value="JobsDB">JobsDB（主要来源）</option><option value="">所有来源</option>'+[...new Set(state.jobs.map(j=>j.source_family).filter(x=>x&&x!=='JobsDB'))].sort().map(x=>`<option value="${escapeHTML(x)}">${escapeHTML(x)}</option>`).join('');
  sourceSelect.value=fill&&state.jobs.length&&state.jobs.every(j=>j.is_demo)?'':selectedSource;
  refreshSelect('#location-filter',state.jobs.map(j=>j.location));
  $('#resume-analysis').innerHTML=state.resume?`<div class="tags">${tags(state.profile.skills||[],state.profile.skills||[])}</div>`+Object.entries(state.profile.evidence||{}).map(([k,v])=>`<div class="evidence"><b>${escapeHTML(k)}</b><span>${escapeHTML(v)}</span></div>`).join(''):'保存简历后，这里会展示技能证据与改进建议。';
  $('#collection-logs').innerHTML=state.logs.length?state.logs.map(l=>`<div class="log-row"><b>${escapeHTML(l.source)}</b><span>${({success:'已完成',cached:'缓存',partial:'部分完成',cancelled:'已停止',error:'失败'})[l.status]||l.status}</span><span>${escapeHTML(l.message)}</span><time>${escapeHTML(new Date(l.created_at).toLocaleString('zh-CN'))}</time></div>`).join(''):empty('尚无采集记录','选择公开数据源，或导入自己的岗位文件。');
  const run=state.jobsdb?.last_run;
  if(run&&!jobsdbTask) $('#jobsdb-run-status').textContent=new Date(run.checked_at).toLocaleString('zh-CN')+' · '+run.message;
  for(const t of state.active_tasks||[]) if(t.label==='更新 JobsDB 岗位'&&!tasks.has(t.id)) track(t.id,t.label);
  renderJobs(); renderBoard();
  if(fill && (state.polished||state.ai_analysis)) renderAI(state.polished||state.ai_analysis,$('#ai-result'));
}
function renderJobs() {
  const query=$('#search').value.trim().toLowerCase(), source=$('#source-filter').value, location=$('#location-filter').value;
  const jobs=state.jobs.filter(j=>(!query||[j.title,j.company,j.description,...j.skills].join(' ').toLowerCase().includes(query))&&(!source||j.source_family===source)&&(!location||j.location===location)&&(!$('#real-only').checked||!j.is_demo)&&(!$('#hide-expired').checked||j.availability!=='expired')&&(!$('#live-only').checked||Boolean(j.last_live_checked)));
  if($('#sort').value==='recent') jobs.sort((a,b)=>b.collected_at.localeCompare(a.collected_at));
  $('#job-count').textContent=jobs.length; $('#load-more').hidden=shown>=jobs.length;
  $('#job-list').innerHTML=jobs.length?jobs.slice(0,shown).map(j=>`<article class="job-card" tabindex="0" role="button" aria-label="查看 ${escapeHTML(j.title)}" data-id="${j.id}"><div class="job-top"><div class="company-icon">${escapeHTML(j.company.slice(0,1))}</div><div class="job-name"><h3>${escapeHTML(j.title)}</h3><div class="job-meta">${escapeHTML(j.company)} · ${escapeHTML(j.location||'地区未注明')}</div></div><div class="score">${j.score===undefined?'—':Math.round(j.score)}${j.score===undefined?'':'<em> /100</em>'}<small>${j.score===undefined?'等待简历':'基础匹配分'}</small></div></div><div class="freshness">${freshness(j)}</div><div class="salary">${escapeHTML(j.salary||'薪资未公开')}</div><div class="tags">${tags(j.skills.slice(0,7),j.matched_skills)}</div><div class="job-bottom"><span>${j.is_demo?'<span class="demo-tag">虚构示例</span>':escapeHTML(j.source)} · ${j.is_demo?'课堂演示':dateLabel(j.published_at)}${j.remote?' · 远程':''}</span><span class="job-action">${escapeHTML(j.status||'查看匹配详情')} ↗</span></div></article>`).join(''):empty('没有找到符合条件的岗位','尝试调整筛选条件，或前往数据工作台同步岗位。');
  $$('#job-list .job-card').forEach(el=>{el.addEventListener('click',()=>openJob(el.dataset.id));el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openJob(el.dataset.id);}});});
}
function renderBoard() {
  const history=state.history||{undo:0,redo:0};
  $('#history-undo').disabled=!history.undo; $('#history-redo').disabled=!history.redo;
  $('#history-count').textContent=`可撤销 ${history.undo} 次 · 可重做 ${history.redo} 次`;
  $('#board').innerHTML=['收藏','已投递','面试中','已录用','已结束'].map(status=>{const jobs=state.jobs.filter(j=>j.status===status);return `<div class="board-column"><h3>${status} <span> ${jobs.length}</span></h3>${jobs.map(j=>`<div class="board-card" tabindex="0" role="button" data-id="${j.id}"><b>${escapeHTML(j.title)}</b><small>${escapeHTML(j.company)}</small><small>${escapeHTML(j.note||'点击添加备注')}</small></div>`).join('')}${jobs.length?'':'<p class="small muted">暂时没有岗位</p>'}</div>`;}).join('');
  $$('.board-card').forEach(el=>{el.addEventListener('click',()=>openJob(el.dataset.id));el.addEventListener('keydown',e=>{if(e.key==='Enter')openJob(el.dataset.id);});});
}
for (const direction of ['undo','redo']) $('#history-'+direction).addEventListener('click', async()=>{
  $('#history-undo').disabled=true; $('#history-redo').disabled=true;
  try { await api('/api/application/history',{action:direction}); await refresh(); toast(direction==='undo'?'已撤销最近一次修改':'已重做修改'); }
  catch(e) { toast(e.message,true); renderBoard(); }
});
function freshness(j) {
  if(j.source_family!=='JobsDB')return '';
  if(j.availability==='expired')return '已过期 · 仅供记录与研究';
  return j.last_live_checked?'在线更新于 '+escapeHTML(new Date(j.last_live_checked).toLocaleString('zh-CN'))+' · 申请前请核实':'历史研究快照 · 尚未在线核实';
}
function openJob(id, recommendation=null) {
  currentJob=id;currentJobIsRecommendation=Boolean(recommendation);const original=state.jobs.find(x=>x.id===id);
  const j=recommendation?{...original,...recommendation,coverage:recommendation.effective_coverage,status:original?.status||recommendation.status,note:original?.note??recommendation.note}:original;if(!j)return;
  $('#job-detail').innerHTML=`<div class="detail-heading"><span class="pill">${escapeHTML(j.source)}${j.is_demo?' · 虚构岗位':''}</span><h2>${escapeHTML(j.title)}</h2><p class="freshness">${freshness(j)}</p><p class="muted">${escapeHTML(j.company)} · ${escapeHTML(j.location||'地区未注明')}</p><b>${escapeHTML(j.salary||'薪资未公开')}</b></div>${j.breakdown?`<div class="breakdown">${j.breakdown.map(b=>`<div><span>${escapeHTML(b.label)}</span><b>${b.value===null?'—':Math.round(b.value)}</b><small>${b.value===null?'条件缺失':`有效权重 ${b.weight}%`}</small></div>`).join('')}</div><p class="small muted">${recommendation?'个性化匹配分':'基础匹配分'} ${j.score} / 100 · 可用条件覆盖 ${j.coverage}% · 文本相关度不是语义理解，需结合原始描述核实。</p><div class="tags">${tags(j.matched_skills,j.matched_skills)}</div>${j.warnings.map(w=>`<p class="warning">${escapeHTML(w)}</p>`).join('')}`:'<p class="muted">保存简历后查看匹配分解。</p>'}<div class="mini-divider"></div><h3>岗位描述</h3><div class="detail-description">${escapeHTML(j.description)}</div><div class="action-row">${j.url?`<a class="button primary" href="${escapeHTML(j.url)}" target="_blank" rel="noopener noreferrer">前往 ${escapeHTML(j.source)} 原始岗位 ↗</a>`:'<span class="small muted">此示例无真实申请链接</span>'}<button id="explain-job" class="button secondary">✧ AI 深度解读</button></div><p class="small muted">AI 解读沿用「我的简历」中的本次发送授权。</p><div id="job-ai-result" class="ai-result"></div><div class="detail-status"><h3>记录求职进展</h3><label class="field">当前状态<select id="job-status">${['未收藏','收藏','已投递','面试中','已录用','已结束'].map(s=>`<option ${s===(j.status||'未收藏')?'selected':''}>${s}</option>`).join('')}</select></label><label class="field">备注<textarea id="job-note" rows="3" placeholder="记录投递时间、面试安排或准备事项">${escapeHTML(j.note||'')}</textarea></label><button id="save-application" class="button dark">保存记录</button></div>`;
  $('#save-application').addEventListener('click',e=>action(e.currentTarget,async()=>{await api('/api/application',{id,status:$('#job-status').value,note:$('#job-note').value});await refresh();toast('投递记录已保存');}));
  $('#explain-job').addEventListener('click',e=>action(e.currentTarget,()=>startAI('explain',id)));
  if(!$('#job-dialog').open)$('#job-dialog').showModal();
}
$('#close-dialog').addEventListener('click',()=>$('#job-dialog').close());
$('#job-dialog').addEventListener('click',e=>{if(e.target===$('#job-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
['#search','#source-filter','#location-filter','#sort','#real-only','#hide-expired','#live-only'].forEach(s=>$(s).addEventListener(s==='#search'?'input':'change',()=>{shown=15;renderJobs();}));
$('#load-more').addEventListener('click',()=>{shown+=15;renderJobs();});
$('#resume-text').addEventListener('input',()=>{$('#char-count').textContent=$('#resume-text').value.length+' 字符';invalidateRecommendations('简历已编辑，请重新生成推荐。');});
$('#save-resume').addEventListener('click',e=>action(e.currentTarget,async()=>{invalidateRecommendations('正在保存简历，请稍后重新生成推荐。');await api('/api/resume',{text:$('#resume-text').value});$('#ai-result').textContent='';await refresh();toast('简历已保存，岗位匹配已更新');}));
$('#clear-resume').addEventListener('click',e=>action(e.currentTarget,async()=>{if(!confirm('清除当前简历和 AI 结果？收藏与岗位库会保留。'))return;invalidateRecommendations('简历已清除，请添加简历后重新生成推荐。');await api('/api/resume/clear',{});$('#ai-result').textContent='';await refresh(true);toast('简历数据已清除');}));
async function demo(save) {invalidateRecommendations('正在载入示例简历，请稍后重新生成推荐。');const r=await api('/api/demo-resume');invalidateRecommendations('已载入虚构示例简历，请重新生成推荐。');$('#resume-text').value=r.text;$('#char-count').textContent=r.text.length+' 字符';if(save){await api('/api/resume',{text:r.text});await api('/api/preferences',{location:'香港, Hong Kong, 深圳',experience_years:0});await refresh(true);toast('已载入虚构示例简历，可查看每个岗位的匹配依据');}else go('resume');}
$('#demo-start').addEventListener('click',e=>action(e.currentTarget,()=>demo(true)));
$('#demo-resume').addEventListener('click',e=>action(e.currentTarget,()=>demo(false)));
$('#save-prefs').addEventListener('click',e=>action(e.currentTarget,async()=>{invalidateRecommendations('求职偏好已保存，请重新生成推荐。');await api('/api/preferences',{location:$('#pref-location').value,experience_years:$('#pref-years').value});await refresh();toast('偏好已保存，岗位排序已更新');}));
async function readFile(file, binary=false) {if(!file)throw new Error('请选择文件');if(file.size>5*1024*1024)throw new Error('文件不能超过 5 MB');return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(binary?String(r.result).split(',')[1]:r.result);r.onerror=()=>reject(new Error('读取文件失败'));binary?r.readAsDataURL(file):r.readAsText(file);});}
$('#resume-file').addEventListener('change',e=>action(null,async()=>{const file=e.target.files[0];if(!file)return;invalidateRecommendations('正在解析新简历，请稍后重新生成推荐。');const data=await readFile(file,true);const result=await api('/api/resume/file',{filename:file.name,data});invalidateRecommendations('已导入新简历，请核实内容后重新生成推荐。');$('#resume-text').value=result.text;$('#char-count').textContent=result.text.length+' 字符';toast('文件已解析，请检查后点击「保存并分析」');e.target.value='';}));
async function track(task_id,label,onDone,options={}) {
  if(tasks.has(task_id))return;
  const isJobsDB=label==='更新 JobsDB 岗位';
  if(isJobsDB){jobsdbTask=task_id;$('#update-jobsdb').disabled=true;$('#cancel-jobsdb').hidden=false;}
  tasks.add(task_id);const chip=document.createElement('div');chip.className='task-chip';chip.innerHTML=`<span class="spinner"></span>${escapeHTML(label)}`;$('#task-tray').append(chip);
  const finish=()=>{tasks.delete(task_id);chip.remove();if(isJobsDB){jobsdbTask=null;$('#update-jobsdb').disabled=false;$('#cancel-jobsdb').hidden=true;}};
  let failures=0;
  const poll=async()=>{try{
    const r=await api('/api/tasks/'+task_id);failures=0;
    if(isJobsDB&&r.progress){const p=r.progress;$('#jobsdb-run-status').textContent=p.phase+'\n进度 '+p.completed+' / '+p.total+' · 有效岗位 '+p.saved;}
    if(options.isCurrent?.()!==false)options.onProgress?.(r);
    if(['done','cancelled','error'].includes(r.status)){
      finish();if(!options.skipRefresh)await refresh();
      if(options.isCurrent?.()===false){options.onStale?.();return;}
      if(r.status==='error'||(r.status==='cancelled'&&options.onError)){const error=new Error(r.error||'任务已停止，请重新生成。');options.onError?.(error);toast(error.message,true);return;}
      if(onDone?.(r.result)!==false)toast(r.result?.message||label+'已完成',r.result?.status==='partial');return;
    }
  }catch(e){failures++;if(failures>=5){finish();const error=new Error('连接中断，请重新生成或刷新页面。');if(options.isCurrent?.()===false){options.onStale?.();return;}options.onError?.(error);toast(error.message,true);return;}}
  setTimeout(poll,1200);};poll();
}
$('#update-jobsdb').addEventListener('click',async e=>{
 const button=e.currentTarget;button.disabled=true;
 try {invalidateRecommendations('正在更新岗位库，完成后请重新生成推荐。');const r=await api('/api/jobsdb/update',{limit:Number($('#jobsdb-limit').value),keyword:$('#jobsdb-keyword').value.trim()});track(r.task_id,'更新 JobsDB 岗位');}
 catch(err){button.disabled=false;toast(err.message,true);}
});
$('#cancel-jobsdb').addEventListener('click',e=>action(e.currentTarget,async()=>{if(jobsdbTask){const r=await api('/api/tasks/cancel',{task_id:jobsdbTask});toast(r.message);}}));
$$('.collect').forEach(button=>button.addEventListener('click',()=>action(button,async()=>{invalidateRecommendations('正在更新岗位库，完成后请重新生成推荐。');const r=await api('/api/collect',{source:button.dataset.source});track(r.task_id,button.dataset.source+' 同步',r=>toast(r.message));})));
$('#import-benchmark').addEventListener('click',e=>action(e.currentTarget,async()=>{invalidateRecommendations('正在导入岗位，完成后请重新生成推荐。');const r=await api('/api/benchmark/import',{});track(r.task_id,'JobsDB 研究快照导入',r=>toast(r.message));}));
$('#collect-page').addEventListener('click',e=>action(e.currentTarget,async()=>{const url=$('#page-url').value.trim();if(!url.startsWith('https://'))throw new Error('请输入 HTTPS 岗位页面地址');invalidateRecommendations('正在采集岗位，完成后请重新生成推荐。');const r=await api('/api/collect/page',{url});track(r.task_id,'网页采集');}));
$('#jobs-file').addEventListener('change',e=>action(null,async()=>{const file=e.target.files[0];if(!file)return;invalidateRecommendations('正在导入岗位，完成后请重新生成推荐。');const content=await readFile(file);const r=await api('/api/import',{filename:file.name,content});await refresh();toast(`成功导入 ${r.count} 条岗位`);e.target.value='';}));
$('#manual-save').addEventListener('click',e=>action(e.currentTarget,async()=>{invalidateRecommendations('正在更新岗位库，完成后请重新生成推荐。');const body={};['title','company','location','salary','url','description'].forEach(k=>body[k]=$('#manual-'+k).value);await api('/api/job',body);await refresh();toast('岗位已加入并参与匹配');}));
// Recommendation results belong to one exact draft and one observed job snapshot.
let recommendationRevision=0, recommendationBusy=false, recommendationResult=null;
const recommendationJobFields=['id','source','source_family','title','company','location','salary','url','description','skills','published_at','collected_at','is_demo','remote','expires_at','availability','last_live_checked','experience_years'];
function sameRecommendationData(before,after){
  if(before.resume!==after.resume||JSON.stringify(before.preferences||{})!==JSON.stringify(after.preferences||{}))return false;
  if((before.jobs||[]).length!==(after.jobs||[]).length)return false;
  const old=new Map((before.jobs||[]).map(job=>[job.id,job]));
  return (after.jobs||[]).every(job=>{const previous=old.get(job.id);return previous&&recommendationJobFields.every(key=>Array.isArray(job[key])||Array.isArray(previous[key])?JSON.stringify(job[key])===JSON.stringify(previous[key]):job[key]===previous[key]);});
}
function recommendationStatus(text,kind='idle'){
  const el=$('#recommendations-status');el.textContent=text;el.dataset.state=kind;
}
function clearRecommendationOutput(){
  recommendationResult=null;$('#recommendations-results').hidden=true;
  ['summary','strengths','strength-note','count','jobs','method'].forEach(id=>$('#recommendations-'+id).replaceChildren());
}
function invalidateRecommendations(message='输入内容已变化，请重新生成推荐。'){
  recommendationRevision++;clearRecommendationOutput();recommendationStatus(message);
  if(currentJobIsRecommendation){if($('#job-dialog').open)$('#job-dialog').close();currentJobIsRecommendation=false;}
}
function recommendationInputs(){
  return {text:$('#resume-text').value,location:$('#pref-location').value,experience_years:$('#pref-years').value,target_role:$('#recommendations-target').value.trim(),limit:12,min_score:Number($('#recommendations-min-score').value),strict_location:$('#recommendations-strict-location').checked,include_demo:$('#recommendations-include-demo').checked};
}
function setRecommendationBusy(busy){
  recommendationBusy=busy;$('#recommendations-run').disabled=busy;
  $('#recommendations-run span').textContent=busy?'正在分析与匹配…':'提炼优势并推荐岗位';
  $('#recommendations-form').setAttribute('aria-busy',String(busy));
}
['#pref-location','#pref-years','#recommendations-target','#recommendations-min-score','#recommendations-strict-location','#recommendations-include-demo'].forEach(selector=>$(selector).addEventListener('input',()=>invalidateRecommendations('求职条件已变化，请重新生成推荐。')));
$('#recommendations-form').addEventListener('submit',async event=>{
  event.preventDefault();if(recommendationBusy)return;
  if(!event.currentTarget.reportValidity())return;
  invalidateRecommendations('正在保存简历与求职偏好…');setRecommendationBusy(true);
  let revision=recommendationRevision;
  try{
    await ensureState();revision=recommendationRevision;
    const input=recommendationInputs(),draft=JSON.stringify(input);
    if(input.text.trim().length<30)throw new Error('请先添加至少 30 个字符的简历内容，或填入示例简历。');
    if(input.strict_location&&!input.location.trim())throw new Error('请先填写希望工作的地区，或关闭严格地区筛选。');
    const isCurrent=()=>revision===recommendationRevision&&draft===JSON.stringify(recommendationInputs());
    await api('/api/resume',{text:input.text});
    if(!isCurrent()){setRecommendationBusy(false);return;}
    $('#ai-result').replaceChildren();
    await api('/api/preferences',{location:input.location,experience_years:input.experience_years});
    if(!isCurrent()){setRecommendationBusy(false);return;}
    await refresh(false,{preserveRecommendations:true});
    if(!isCurrent()){setRecommendationBusy(false);return;}
    recommendationStatus('已保存简历与偏好，正在提炼原文证据并计算岗位匹配…','loading');
    const response=await api('/api/recommendations',{target_role:input.target_role,limit:input.limit,min_score:input.min_score,strict_location:input.strict_location,include_demo:input.include_demo});
    if(!response.task_id)throw new Error('未收到推荐任务编号，请重试。');
    track(response.task_id,'优势与岗位推荐',result=>{
      setRecommendationBusy(false);if(!isCurrent())return;
      try{renderRecommendations(result);}catch(error){clearRecommendationOutput();recommendationStatus(error.message||'推荐结果无法显示，请重试。','error');return false;}
    },{skipRefresh:true,isCurrent,onStale:()=>setRecommendationBusy(false),onError:error=>{setRecommendationBusy(false);clearRecommendationOutput();recommendationStatus(error.message,'error');},onProgress:task=>{if(task.status==='queued')recommendationStatus('任务已排队，等待本地匹配计算…','loading');else if(task.status==='running')recommendationStatus('正在核对优势证据、筛选岗位并计算个性化匹配分…','loading');}});
  }catch(error){
    setRecommendationBusy(false);
    if(revision===recommendationRevision){clearRecommendationOutput();recommendationStatus(error.message||'生成失败，请重试。','error');toast(error.message,true);}
  }
});
function recommendationNumber(value){return value!==null&&value!==undefined&&Number.isFinite(Number(value))?Number(value).toLocaleString('zh-CN'):'—';}
function recommendationSource(job){
  const parts=[`<span>${escapeHTML(job.source||'来源未注明')}</span>`,`<span>发布 ${escapeHTML(dateLabel(job.published_at))}</span>`,`<span>收录 ${escapeHTML(dateLabel(job.collected_at))}</span>`];
  if(job.is_demo)parts.push('<span class="demo-tag">虚构演示岗位</span>');
  else if(!job.last_live_checked)parts.push('<span class="historical">历史 / 未在线核实</span>');
  else{parts.push(`<span>最近核实 ${escapeHTML(dateLabel(job.last_live_checked))}</span>`);const elapsed=Date.now()-new Date(job.last_live_checked).getTime();if(Number.isFinite(elapsed)&&elapsed>30*86400000)parts.push('<span class="historical">核实记录超过 30 天</span>');}
  return parts.join('');
}
function recommendationBreakdown(job){
  return `<div class="recommendation-breakdown">${(job.breakdown||[]).map(part=>{const available=part.value!==null&&part.value!==undefined;const value=available?Number(part.value):0;return `<div class="recommendation-component"><span>${escapeHTML(part.label||part.key)}</span><meter min="0" max="100" value="${Number.isFinite(value)?Math.max(0,Math.min(100,value)):0}" aria-label="${escapeHTML(part.label||part.key)} ${available?recommendationNumber(value):'条件未知'}"></meter><b>${available?recommendationNumber(value):'—'}</b><small>${available?'有效权重 '+recommendationNumber(part.weight)+'%':'条件未知'}</small></div>`;}).join('')}</div>`;
}
function renderRecommendations(result){
  if(!result||!result.profile||!result.summary||!Array.isArray(result.jobs))throw new Error('推荐结果结构不完整，请重新生成。');
  recommendationResult=result;
  const profile=result.profile,summary=result.summary;
  $('#recommendations-summary').innerHTML=[[summary.total,'当前岗位库'],[summary.eligible,'通过初步筛选'],[summary.returned,'本次展示推荐']].map(([number,label])=>`<div><strong>${recommendationNumber(number)}</strong><span>${label}</span></div>`).join('');
  const strengths=profile.strengths||[];
  $('#recommendations-strengths').innerHTML=strengths.length?strengths.map((strength,index)=>`<article class="strength-card"><div class="strength-card-head"><span class="strength-card-number">${String(index+1).padStart(2,'0')}</span><div><h4>${escapeHTML(strength.title)}</h4><div class="tags">${tags(strength.skills||[],strength.skills||[])}</div></div></div>${(strength.evidence||[]).slice(0,3).map(evidence=>`<blockquote><span>简历原文证据</span>${escapeHTML(evidence)}</blockquote>`).join('')}</article>`).join(''):empty('尚未提取到明确的优势证据','补充具体项目、负责事项、使用的技能与成果后，再次分析。');
  const questions=profile.questions||[],excluded=profile.excluded_skills||[];
  $('#recommendations-strength-note').innerHTML=(questions.length?`<p>${questions.map(escapeHTML).join('<br>')}</p>`:'')+(excluded.length?`<p>未作为已有优势计入：${excluded.map(item=>escapeHTML(item.skill)+'（'+escapeHTML(({denied:'否定表述',conflicting:'表述冲突',negated:'否定表述',aspirational:'计划学习',planned:'计划学习',uncertain:'待核实表述'})[item.status]||'待核实表述')+'）').join('、')}。规划或否定表述不等于已具备的能力。</p>`:'');
  $('#recommendations-count').textContent=`达到分数条件 ${recommendationNumber(summary.available_after_score_filter)} 个 · 展示 ${recommendationNumber(summary.returned)} 个`;
  $('#recommendations-jobs').innerHTML=result.jobs.length?result.jobs.map((job,index)=>{
    const own=state.jobs.find(item=>item.id===job.id),saved=own?.status||job.status;
    return `<article class="recommendation-card"><div class="job-top"><div class="company-icon">${escapeHTML((job.company||'?').slice(0,1))}</div><div class="job-name"><h4>${escapeHTML(job.title)}</h4><div class="job-meta">${escapeHTML(job.company)} · ${escapeHTML(job.location||'地区未注明')}</div></div><div class="recommendation-score">${recommendationNumber(job.score)}<em> /100</em><small>个性化匹配分</small></div></div><div class="recommendation-freshness">${recommendationSource(job)}${job.weak_signal?'<span class="historical">证据较弱 · 请人工核实</span>':''}</div><ul class="recommendation-reasons">${(job.reasons||[]).map(reason=>`<li>${escapeHTML(reason)}</li>`).join('')}</ul><div class="recommendation-skills"><span>已有技能匹配</span>${(job.matched_skills||[]).length?tags(job.matched_skills,job.matched_skills):'<span class="small muted">暂无明确的技能交集</span>'}</div>${(job.missing_skills||[]).length?`<div class="recommendation-skills missing"><span>尚缺简历证据</span>${tags(job.missing_skills.slice(0,8))}</div>`:''}<details class="recommendation-explanation"><summary>查看分数分解与匹配证据</summary>${recommendationBreakdown(job)}<p>可用条件覆盖 ${recommendationNumber(job.effective_coverage)}%。缺失条件不按零分惩罚；分项采用本次有效权重。</p>${(job.evidence_matches||[]).slice(0,4).map(match=>`<div class="evidence"><b>${escapeHTML(match.skill)}</b><span>${(match.evidence||[]).map(escapeHTML).join('；')}</span></div>`).join('')}${(job.warnings||[]).map(warning=>`<p class="warning">${escapeHTML(warning)}</p>`).join('')}</details><div class="action-row recommendation-actions"><span class="salary">${escapeHTML(job.salary||'薪资未公开')}</span><div><button type="button" class="button secondary" data-recommendation-open="${index}">岗位详情与原始链接 ↗</button><button type="button" class="button subtle" data-recommendation-save="${index}" ${saved?'disabled':''}>${saved?'已记录 · '+escapeHTML(saved):'收藏岗位'}</button></div></div></article>`;
  }).join(''):empty('当前条件下没有可推荐的岗位',summary.empty_reason||'尝试调整目标职位、地区或最低匹配分；也可先更新真实岗位库。');
  const method=result.method||{},labelMap={baseline:'岗位基础匹配',project_evidence:'行动与项目证据',target_role:'目标职位名称',skills:'技能匹配',text:'文本相关',experience:'经验',location:'地区',education:'学历',strengths:'优势证据',evidence:'优势证据',target:'目标职位',title:'职位相关',bm25:'词项相关'};
  const weights=Object.entries(method.weights||{}).map(([key,value])=>{const number=Number(value);return `<span>${escapeHTML(labelMap[key]||key)} ${Number.isFinite(number)?recommendationNumber(number<=1?number*100:number):'—'}%</span>`;}).join('');
  const exclusions=[['过期/不可用',summary.excluded_expired],['演示岗位',summary.excluded_demo],['重复岗位',summary.excluded_duplicates],['地区不符',summary.excluded_location],['低于最低分',summary.excluded_min_score]].filter(([,number])=>Number(number)>0).map(([label,number])=>`${label} ${recommendationNumber(number)} 条`);
  $('#recommendations-method').innerHTML=`<p>本地可解释匹配 · 方法版本 ${escapeHTML(method.version||'未提供')}。当前库 ${recommendationNumber(summary.total)} 条，初步筛选 ${recommendationNumber(summary.eligible)} 条；超过展示上限的候选未在此全部列出。</p><div class="method-weights">${weights}</div><p>筛选排除：${exclusions.length?exclusions.join('；'):'本次没有此类排除记录'}。</p>${summary.data_mode==='demo'||summary.demo_fallback?'<p class="warning">本次包含演示数据，虚构岗位仅供功能演示。</p>':''}<ul>${(method.limitations||[]).map(note=>`<li>${escapeHTML(note)}</li>`).join('')}</ul><p>这是针对当前简历与岗位库的个性化匹配分；「岗位检索」保留基础匹配分，两者使用不同的排序依据。所有优势仍需你核实，分数不代表录用概率。</p>`;
  $('#recommendations-results').hidden=false;
  if($('#resume').classList.contains('active'))$('#recommendations-results').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
  recommendationStatus(result.jobs.length?`已完成本地证据分析，展示 ${summary.returned} 个岗位推荐。修改简历或筛选后需重新生成。`:'优势分析已完成，当前条件下没有岗位达到筛选要求。','done');
  $$('[data-recommendation-open]').forEach(button=>button.addEventListener('click',()=>{const job=recommendationResult?.jobs[Number(button.dataset.recommendationOpen)];if(job)openJob(job.id,job);}));
  $$('[data-recommendation-save]').forEach(button=>button.addEventListener('click',()=>action(button,async()=>{
    const job=recommendationResult?.jobs[Number(button.dataset.recommendationSave)];if(!job)return;
    const current=state.jobs.find(item=>item.id===job.id);
    if(current?.status){toast('该岗位已有求职记录，可在详情中管理。');return;}
    await api('/api/application',{id:job.id,status:'收藏',note:current?.note||''});await refresh();
    button.textContent='已记录 · 收藏';toast('岗位已收藏，可在投递管理中继续跟进。');
  })));
}

function renderAI(result, target) {
  if(!target)return;
  const labels={summary:'分析概述',strengths:'已有优势',suggestions:'改善建议',questions:'待核实信息',changes:'修改说明',gaps:'岗位差距',actions:'准备建议'};
  target.innerHTML=Object.entries(labels).filter(([k])=>result[k]).map(([k,label])=>`<h3>${label}</h3><div>${escapeHTML(Array.isArray(result[k])?result[k].map(x=>'· '+x).join('\n'):result[k])}</div>`).join('');
  if(result.polished_resume){const h=document.createElement('h3');h.textContent='润色草稿（请核实后使用）';const p=document.createElement('div');p.textContent=result.polished_resume;target.prepend(p);target.prepend(h);const btn=document.createElement('button');btn.className='button secondary';btn.textContent='下载润色简历 TXT';btn.addEventListener('click',()=>download('JobCompass润色简历.txt',result.polished_resume));target.append(btn);}
  const note=document.createElement('p');note.className='small muted';note.textContent=`由 ${result.model} 生成。请核实内容真实性与岗位条件。`;target.append(note);
}
function download(name,text) {const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function startAI(task,job_id) {
  if(!$('#ai-consent').checked)throw new Error('请先到「我的简历」勾选本次发送至 DeepSeek 的授权。');
  const r=await api('/api/ai',{task,job_id,consent:true});
  track(r.task_id,{analyze:'AI 优势分析',polish:'AI 简历润色',explain:'AI 岗位解读'}[task],result=>{if(task==='explain'){if(currentJob===job_id)renderAI(result,$('#job-ai-result'));}else renderAI(result,$('#ai-result'));});
}
$('#ai-analyze').addEventListener('click',e=>action(e.currentTarget,()=>startAI('analyze')));
$('#ai-polish').addEventListener('click',e=>action(e.currentTarget,()=>startAI('polish')));
go(location.hash.slice(1)||'analytics');
action(null,async()=>applyMeta(await api('/api/status')));
}
