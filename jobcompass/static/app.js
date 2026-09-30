'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const escapeHTML = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names = {discover:'岗位发现',resume:'我的简历',sources:'数据工作台',tracker:'投递看板'};
let state = {jobs:[],profile:{},preferences:{},ai:{},logs:[]};
let shown = 15, currentJob = null, toastTimer;
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
function go(page) {
  $$('.page').forEach(x=>x.classList.toggle('active',x.id===page));
  $$('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===page));
  $('#breadcrumb').textContent='工作空间 / '+names[page]; window.scrollTo({top:0,behavior:'smooth'});
}
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
async function refresh(fill=false) {
  state=await api('/api/state');
  if(fill) { $('#resume-text').value=state.resume||''; $('#pref-location').value=state.preferences.location||''; $('#pref-years').value=state.preferences.experience_years??''; }
  $('#char-count').textContent=$('#resume-text').value.length+' 字符';
  const real=state.jobs.filter(j=>!j.is_demo), saved=state.jobs.filter(j=>j.status);
  const best=state.jobs.length?Math.max(...state.jobs.map(j=>j.score||0)):0;
  const numbers=[['岗位总数',state.jobs.length,'包含 '+(state.jobs.length-real.length)+' 条课程示例','▤'],['最高匹配分',state.resume?best:'—','满分 100，仅供排序参考','✧'],['已有技能',(state.profile.skills||[]).length,'从原始简历提取','⌘'],['收藏与投递',saved.length,'记录你的每一步','↗']];
  $('#stats').innerHTML=numbers.map(([title,note,foot,icon])=>`<div class="stat"><div class="stat-top">${title}<span class="stat-icon">${icon}</span></div><div class="stat-number">${note}</div><div class="stat-foot">${foot}</div></div>`).join('');
  $('#welcome').hidden=Boolean(state.resume);
  $('#profile-title').textContent=state.resume?'已识别你的技能画像':'等待认识你';
  $('#profile-subtitle').textContent=state.resume?`${state.profile.education} · ${state.profile.experience_years??'待确认'} 年经验`:'添加简历，提取你已有的技能与经历。';
  $('#profile-skills').innerHTML=tags((state.profile.skills||[]).slice(0,9),(state.profile.skills||[]));
  $('#ai-status').textContent=state.ai.configured?`${state.ai.model} · 已配置`:'未配置 API 密钥';
  $('#ranking-hint').textContent=state.resume?'技能证据 + TF-IDF 文本相关度':'保存简历后可查看匹配度';
  refreshSelect('#source-filter',state.jobs.map(j=>j.source)); refreshSelect('#location-filter',state.jobs.map(j=>j.location));
  $('#resume-analysis').innerHTML=state.resume?`<div class="tags">${tags(state.profile.skills||[],state.profile.skills||[])}</div>`+Object.entries(state.profile.evidence||{}).map(([k,v])=>`<div class="evidence"><b>${escapeHTML(k)}</b><span>${escapeHTML(v)}</span></div>`).join(''):'保存简历后，这里会展示技能证据与改进建议。';
  $('#collection-logs').innerHTML=state.logs.length?state.logs.map(l=>`<div class="log-row"><b>${escapeHTML(l.source)}</b><span>${l.status==='success'?'已完成':l.status==='cached'?'缓存':'失败'}</span><span>${escapeHTML(l.message)}</span><time>${escapeHTML(new Date(l.created_at).toLocaleString('zh-CN'))}</time></div>`).join(''):empty('尚无采集记录','选择公开数据源，或导入自己的岗位文件。');
  renderJobs(); renderBoard();
  if(fill && (state.polished||state.ai_analysis)) renderAI(state.polished||state.ai_analysis,$('#ai-result'));
}
function renderJobs() {
  const query=$('#search').value.trim().toLowerCase(), source=$('#source-filter').value, location=$('#location-filter').value;
  const jobs=state.jobs.filter(j=>(!query||[j.title,j.company,j.description,...j.skills].join(' ').toLowerCase().includes(query))&&(!source||j.source===source)&&(!location||j.location===location)&&(!$('#real-only').checked||!j.is_demo));
  if($('#sort').value==='recent') jobs.sort((a,b)=>b.collected_at.localeCompare(a.collected_at));
  $('#job-count').textContent=jobs.length; $('#load-more').hidden=shown>=jobs.length;
  $('#job-list').innerHTML=jobs.length?jobs.slice(0,shown).map(j=>`<article class="job-card" tabindex="0" role="button" aria-label="查看 ${escapeHTML(j.title)}" data-id="${j.id}"><div class="job-top"><div class="company-icon">${escapeHTML(j.company.slice(0,1))}</div><div class="job-name"><h3>${escapeHTML(j.title)}</h3><div class="job-meta">${escapeHTML(j.company)} · ${escapeHTML(j.location||'地区未注明')}</div></div><div class="score">${j.score===undefined?'—':Math.round(j.score)}${j.score===undefined?'':'<em> /100</em>'}<small>${j.score===undefined?'等待简历':'匹配评分'}</small></div></div><div class="salary">${escapeHTML(j.salary||'薪资未公开')}</div><div class="tags">${tags(j.skills.slice(0,7),j.matched_skills)}</div><div class="job-bottom"><span>${j.is_demo?'<span class="demo-tag">虚构示例</span>':escapeHTML(j.source)} · ${j.is_demo?'课堂演示':dateLabel(j.published_at)}${j.remote?' · 远程':''}</span><span class="job-action">${escapeHTML(j.status||'查看匹配详情')} ↗</span></div></article>`).join(''):empty('没有找到符合条件的岗位','尝试调整筛选条件，或前往数据工作台同步岗位。');
  $$('#job-list .job-card').forEach(el=>{el.addEventListener('click',()=>openJob(el.dataset.id));el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openJob(el.dataset.id);}});});
}
function renderBoard() {
  $('#board').innerHTML=['收藏','已投递','面试中','已录用','已结束'].map(status=>{const jobs=state.jobs.filter(j=>j.status===status);return `<div class="board-column"><h3>${status} <span> ${jobs.length}</span></h3>${jobs.map(j=>`<div class="board-card" tabindex="0" role="button" data-id="${j.id}"><b>${escapeHTML(j.title)}</b><small>${escapeHTML(j.company)}</small><small>${escapeHTML(j.note||'点击添加备注')}</small></div>`).join('')}${jobs.length?'':'<p class="small muted">暂时没有岗位</p>'}</div>`;}).join('');
  $$('.board-card').forEach(el=>{el.addEventListener('click',()=>openJob(el.dataset.id));el.addEventListener('keydown',e=>{if(e.key==='Enter')openJob(el.dataset.id);});});
}
function openJob(id) {
  currentJob=id;const j=state.jobs.find(x=>x.id===id);if(!j)return;
  $('#job-detail').innerHTML=`<div class="detail-heading"><span class="pill">${escapeHTML(j.source)}${j.is_demo?' · 虚构岗位':''}</span><h2>${escapeHTML(j.title)}</h2><p class="muted">${escapeHTML(j.company)} · ${escapeHTML(j.location||'地区未注明')}</p><b>${escapeHTML(j.salary||'薪资未公开')}</b></div>${j.breakdown?`<div class="breakdown">${j.breakdown.map(b=>`<div><span>${b.label}</span><b>${b.value===null?'—':Math.round(b.value)}</b><small>${b.value===null?'条件缺失':`有效权重 ${b.weight}%`}</small></div>`).join('')}</div><p class="small muted">综合匹配分 ${j.score} / 100 · 可用条件覆盖 ${j.coverage}% · 文本相关度不是语义理解，需结合原始描述核实。</p><div class="tags">${tags(j.matched_skills,j.matched_skills)}</div>${j.warnings.map(w=>`<p class="warning">${escapeHTML(w)}</p>`).join('')}`:'<p class="muted">保存简历后查看匹配分解。</p>'}<div class="mini-divider"></div><h3>岗位描述</h3><div class="detail-description">${escapeHTML(j.description)}</div><div class="action-row">${j.url?`<a class="button primary" href="${escapeHTML(j.url)}" target="_blank" rel="noopener noreferrer">前往 ${escapeHTML(j.source)} 原始岗位 ↗</a>`:'<span class="small muted">此示例无真实申请链接</span>'}<button id="explain-job" class="button secondary">✧ AI 深度解读</button></div><p class="small muted">AI 解读沿用「我的简历」中的本次发送授权。</p><div id="job-ai-result" class="ai-result"></div><div class="detail-status"><h3>记录求职进展</h3><label class="field">当前状态<select id="job-status">${['未收藏','收藏','已投递','面试中','已录用','已结束'].map(s=>`<option ${s===(j.status||'未收藏')?'selected':''}>${s}</option>`).join('')}</select></label><label class="field">备注<textarea id="job-note" rows="3" placeholder="记录投递时间、面试安排或准备事项">${escapeHTML(j.note||'')}</textarea></label><button id="save-application" class="button dark">保存记录</button></div>`;
  $('#save-application').addEventListener('click',e=>action(e.currentTarget,async()=>{await api('/api/application',{id,status:$('#job-status').value,note:$('#job-note').value});await refresh();toast('投递记录已保存');}));
  $('#explain-job').addEventListener('click',e=>action(e.currentTarget,()=>startAI('explain',id)));
  if(!$('#job-dialog').open)$('#job-dialog').showModal();
}
$('#close-dialog').addEventListener('click',()=>$('#job-dialog').close());
$('#job-dialog').addEventListener('click',e=>{if(e.target===$('#job-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
['#search','#source-filter','#location-filter','#sort','#real-only'].forEach(s=>$(s).addEventListener(s==='#search'?'input':'change',()=>{shown=15;renderJobs();}));
$('#load-more').addEventListener('click',()=>{shown+=15;renderJobs();});
$('#resume-text').addEventListener('input',()=>$('#char-count').textContent=$('#resume-text').value.length+' 字符');
$('#save-resume').addEventListener('click',e=>action(e.currentTarget,async()=>{await api('/api/resume',{text:$('#resume-text').value});$('#ai-result').textContent='';await refresh();toast('简历已保存，岗位匹配已更新');}));
$('#clear-resume').addEventListener('click',e=>action(e.currentTarget,async()=>{if(!confirm('清除当前简历和 AI 结果？收藏与岗位库会保留。'))return;await api('/api/resume/clear',{});$('#ai-result').textContent='';await refresh(true);toast('简历数据已清除');}));
async function demo(save) {const r=await api('/api/demo-resume');$('#resume-text').value=r.text;$('#char-count').textContent=r.text.length+' 字符';if(save){await api('/api/resume',{text:r.text});await api('/api/preferences',{location:'香港, Hong Kong, 深圳',experience_years:0});await refresh(true);toast('已载入虚构示例简历，可查看每个岗位的匹配依据');}else go('resume');}
$('#demo-start').addEventListener('click',e=>action(e.currentTarget,()=>demo(true)));
$('#demo-resume').addEventListener('click',e=>action(e.currentTarget,()=>demo(false)));
$('#save-prefs').addEventListener('click',e=>action(e.currentTarget,async()=>{await api('/api/preferences',{location:$('#pref-location').value,experience_years:$('#pref-years').value});await refresh();toast('偏好已保存，岗位排序已更新');}));
async function readFile(file, binary=false) {if(!file)throw new Error('请选择文件');if(file.size>5*1024*1024)throw new Error('文件不能超过 5 MB');return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(binary?String(r.result).split(',')[1]:r.result);r.onerror=()=>reject(new Error('读取文件失败'));binary?r.readAsDataURL(file):r.readAsText(file);});}
$('#resume-file').addEventListener('change',e=>action(null,async()=>{const file=e.target.files[0];if(!file)return;const data=await readFile(file,true);const result=await api('/api/resume/file',{filename:file.name,data});$('#resume-text').value=result.text;$('#char-count').textContent=result.text.length+' 字符';toast('文件已解析，请检查后点击「保存并分析」');e.target.value='';}));
async function track(task_id,label,onDone) {
  tasks.add(task_id);const chip=document.createElement('div');chip.className='task-chip';chip.innerHTML=`<span class="spinner"></span>${escapeHTML(label)}`;$('#task-tray').append(chip);
  let failures=0;
  const poll=async()=>{try{const r=await api('/api/tasks/'+task_id);failures=0;if(r.status==='done'){tasks.delete(task_id);chip.remove();await refresh();onDone?.(r.result);toast(label+'已完成');return;}if(r.status==='error'){tasks.delete(task_id);chip.remove();toast(r.error,true);await refresh();return;}}catch(e){failures++;if(failures>=5){tasks.delete(task_id);chip.remove();toast('连接中断，请刷新页面查看已保存结果。',true);return;}}setTimeout(poll,1200);};poll();
}
$$('.collect').forEach(button=>button.addEventListener('click',()=>action(button,async()=>{const r=await api('/api/collect',{source:button.dataset.source});track(r.task_id,button.dataset.source+' 同步',r=>toast(r.message));})));
$('#collect-page').addEventListener('click',e=>action(e.currentTarget,async()=>{const url=$('#page-url').value.trim();if(!url.startsWith('https://'))throw new Error('请输入 HTTPS 岗位页面地址');const r=await api('/api/collect/page',{url});track(r.task_id,'网页采集');}));
$('#jobs-file').addEventListener('change',e=>action(null,async()=>{const file=e.target.files[0];if(!file)return;const content=await readFile(file);const r=await api('/api/import',{filename:file.name,content});await refresh();toast(`成功导入 ${r.count} 条岗位`);e.target.value='';}));
$('#manual-save').addEventListener('click',e=>action(e.currentTarget,async()=>{const body={};['title','company','location','salary','url','description'].forEach(k=>body[k]=$('#manual-'+k).value);await api('/api/job',body);await refresh();toast('岗位已加入并参与匹配');}));
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
action(null,()=>refresh(true));
