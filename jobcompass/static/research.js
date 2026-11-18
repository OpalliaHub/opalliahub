'use strict';
if(location.protocol!=='file:') (()=>{
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let info=null,last=null,busy=false,activeResearchTask=null;
const labels={dataset:'筛选与导出广告行',overview:'职业分布与数据质量',skills:'能力全文提及分布',trend:'月度全文提及趋势',compare:'两期提及率比较',sample:'可追溯原文证据',pairs:'同广告词语新增与删除',forecast:'成熟窗口历史预测诊断'};
const concepts={generative_ai:'生成式 AI',large_language_models:'大语言模型',python:'Python',agentic_ai:'Agent 相关',cantonese:'粤语',bachelor:'学士',master:'硕士',communication:'沟通能力',teamwork:'团队合作',machine_learning:'机器学习'};
const msg=(text,error=false)=>{const el=$('#research-progress');el.textContent=text;el.classList.toggle('research-error',error);};
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-JobCompass':'1'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'请求失败');return d;}
async function task(path,body,done) {
  if(busy){msg('研究任务正在运行，请稍候。');return;}
  busy=true;document.querySelectorAll('#research .button').forEach(b=>b.disabled=true);msg('正在处理…');
  try {
    const t=await api(path,body);
    if(!t.task_id){await done?.(t);return;}
    activeResearchTask=t.task_id;
    $('#research-agent-stop').disabled=path!=='/api/research/agent';
    for(;;){
      const r=await api('/api/tasks/'+t.task_id);
      if(r.progress){msg(`${r.progress.phase} · ${r.progress.completed} / ${r.progress.total}`);$('#research-build-state').textContent=$('#research-progress').textContent;}
      if(r.status==='error')throw Error(r.error);
      if(['done','cancelled'].includes(r.status)){
        await done?.(r.result);msg(r.result.message||'分析完成，已保存可复现记录。');break;
      }
      await new Promise(ok=>setTimeout(ok,1400));
    }
  } catch(e){msg(e.message,true);}
  finally{busy=false;activeResearchTask=null;document.querySelectorAll('#research .button').forEach(b=>b.disabled=false);$('#research-agent-stop').disabled=true;}
}
async function load(){try{info=await api('/api/research/status');$('#research-path').value=info.path||'';$('#research-ai-status').textContent=info.ai_configured?'DeepSeek · 已配置':'DeepSeek · 未配置';const selected=$('#research-concept').value||'python';$('#research-concept').innerHTML=info.concepts.map(c=>`<option value="${esc(c)}">${esc(concepts[c]||c)}</option>`).join('');$('#research-concept').value=selected;const m=info.index||{};$('#research-metrics').innerHTML=[['首版分析广告',m.rows?.toLocaleString()||'—','正文 ≥100 字元'],['有效快照观测',m.observations?.toLocaleString()||'—','观测行与独立广告分开'],['日期快照',m.snapshots?.length||'—','时间缺口保留为空缺'],['词语探针',info.concepts.length,'规则标签 · 非人工金标准']].map(([a,b,c])=>`<div class="stat"><div class="stat-top">${a}</div><div class="stat-number">${b}</div><div class="stat-foot">${c}</div></div>`).join('');$('#research-build-state').textContent=info.ready?'分析索引就绪 · '+new Date(m.built_at).toLocaleString():info.connected?'研究库已找到，请构建分析索引。':'未连接纵向数据；可先分析当前平台岗位。';$('#research-history').innerHTML=info.runs.map(r=>`<button class="research-history-item" data-run="${r.id}">${esc(labels[r.plan.action])} · ${r.population_n.toLocaleString()} 个广告 <small>${esc(new Date(r.created_at).toLocaleString())}</small></button>`).join('')||'<p class="muted small">暂无记录</p>';$('#research-cohorts').innerHTML=info.cohorts.map((r,i)=>`<button class="research-history-item" data-cohort="${i}">队列 · ${esc(r.name)}</button>`).join('');document.querySelectorAll('[data-run]').forEach(b=>b.onclick=async()=>{try{render(await api('/api/research/result/'+b.dataset.run));}catch(e){msg(e.message,true);}});document.querySelectorAll('[data-cohort]').forEach(b=>b.onclick=()=>showPlan(info.cohorts[Number(b.dataset.cohort)].plan,'已加载保存队列；可编辑后运行。'));}catch(e){msg(e.message,true);}}
function plan(){const p={dataset:$('#research-dataset').value,action:$('#research-action').value,concept:$('#research-concept').value,dedup:$('#research-dedup').value,limit:30,filters:{}};for(const k of ['title','sector','start','end','cutoff'])if($('#research-'+k).value)p.filters[k]=$('#research-'+k).value;p.filters.common_only=$('#research-common').checked;p.filters.fresh_only=$('#research-fresh').checked;if(p.action==='compare'){p.period_a=[$('#research-a-start').value,$('#research-a-end').value];p.period_b=[$('#research-b-start').value,$('#research-b-end').value];}return p;}
function showPlan(p,why=''){ $('#research-plan-json').value=JSON.stringify(p,null,2);$('#research-plan-explanation').textContent=why;$('#research-plan-box').open=true; }
function barChart(rows,key,label,suffix=''){const data=rows.filter(r=>Number.isFinite(r[key])).slice(0,36),max=Math.max(1,...data.map(r=>r[key]));return '<div class="research-bars">'+data.map(r=>`<div class="research-bar-row"><span>${esc(concepts[r[label]]||r[label])}</span><meter min="0" max="${max}" value="${Math.max(0,r[key])}" aria-label="${esc(r[label])}"></meter><b>${esc(r[key])}${suffix}</b></div>`).join('')+'</div>';}
function render(r){last=r;$('#research-interpretation').textContent='';$('#research-chart').innerHTML='';$('#research-table').innerHTML='';$('#research-result').innerHTML=`<h3>${esc(labels[r.plan.action])}</h3><p class="muted">筛选后 ${r.population_n.toLocaleString()} 个广告 · ${esc(concepts[r.plan.concept]||r.plan.concept)} · ${r.elapsed_seconds} 秒 · ${r.plan.dedup==='id'?'唯一 ID':'首次雇主正文族'}</p>${r.details.difference_pp!==undefined?`<div class="research-delta">${r.details.difference_pp===null?'样本不足':(r.details.difference_pp>0?'+':'')+r.details.difference_pp+' pp'}<small>B 减 A 的百分点差</small></div>`:''}`;if(r.plan.action==='overview')$('#research-chart').innerHTML=barChart(r.rows,'n','label');if(r.plan.action==='skills')$('#research-chart').innerHTML=barChart(r.rows.slice(0,15),'share_pct','concept','%');if(['trend','compare'].includes(r.plan.action))$('#research-chart').innerHTML=barChart(r.rows,'share_pct',r.plan.action==='trend'?'month':'period','%');if(r.rows.length){const cols=Object.keys(r.rows[0]);$('#research-table').innerHTML='<table><thead><tr>'+cols.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr></thead><tbody>'+r.rows.map(row=>'<tr>'+cols.map(c=>`<td>${esc(row[c]===null?'未标注 / 不可估计':row[c])}</td>`).join('')+'</tr>').join('')+'</tbody></table>';}else $('#research-table').textContent='此口径下没有足够数据；没有将缺失值填成零。';const q=r.details.quality;$('#research-notes').innerHTML=(q?`<p class="small muted">雇主正文族 ${q.families.toLocaleString()} · 薪资缺失 ${q.missing_salary||0} · 来源标示日期 ${esc(q.first_date)} 至 ${esc(q.last_date)}。薪资未跨币种或周期强行合并。</p>`:'')+(r.details.method?`<p>${esc(r.details.method)}</p>`:'')+'<details><summary>研究边界与复现信息</summary><ul>'+r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')+`</ul><p class="small muted research-hash">数据指纹 ${esc(r.dataset_fingerprint)}<br>规则推导 · ${esc(r.created_at)}</p><pre>${esc(JSON.stringify(r.plan,null,2))}</pre></details>`;for(const ext of ['csv','json']){const link=$('#research-'+ext);link.hidden=false;link.href='/api/research/result/'+r.id+'.'+ext;link.download='research-'+r.id+'.'+ext;}$('#research-explain').hidden=['sample','pairs','dataset'].includes(r.plan.action);$('#research-save').hidden=false;}
$('#research-action').onchange=()=>$('#research-periods').hidden=$('#research-action').value!=='compare';$('#research-dataset').onchange=()=>{const current=$('#research-dataset').value==='current';$('#research-common').checked=!current;$('#research-fresh').checked=!current;};
$('#research-run').onclick=()=>{const p=plan();showPlan(p,'使用你选定的筛选口径。');task('/api/research/run',{plan:p},async r=>{render(r);await load();});};
$('#research-execute-plan').onclick=()=>{try{const p=JSON.parse($('#research-plan-json').value);task('/api/research/run',{plan:p},async r=>{render(r);await load();});}catch(e){msg('JSON 计划格式不正确。',true);}};
$('#research-plan').onclick=()=>task('/api/research/plan',{command:$('#research-command').value,dataset:$('#research-dataset').value},r=>showPlan(r.plan,r.explanation));
$('#research-agent').onclick=()=>{
  if(!$('#research-agent-consent').checked){msg('请先勾选本次研究助手的发送授权。',true);return;}
  $('#research-agent-trace').textContent='正在启动分步分析…';
  task('/api/research/agent',{command:$('#research-command').value,dataset:$('#research-dataset').value,max_steps:3,consent:true},async r=>{
    $('#research-agent-trace').innerHTML=`<h3>执行轨迹 · ${esc(r.status)}</h3><p>${esc(r.summary)}</p><p class="small muted">模型调用 ${r.model_calls} / ${r.max_steps} · 平台分析 ${r.executed_steps} 次 · 结论属于模型推断</p>`+r.steps.map(step=>`<details><summary>第 ${step.step} 轮 · ${esc(step.plan?.action||step.action||'停止')} · ${esc(step.status)}</summary><pre>${esc(JSON.stringify({plan:step.plan,observation:step.observation},null,2))}</pre>${step.result_id?`<button class="button secondary" data-agent-result="${esc(step.result_id)}">查看统计结果</button>`:''}</details>`).join('');
    document.querySelectorAll('[data-agent-result]').forEach(button=>button.onclick=async()=>{try{render(await api('/api/research/result/'+button.dataset.agentResult));}catch(error){msg(error.message,true);}});
    await load();
  });
};
$('#research-agent-stop').onclick=async()=>{if(activeResearchTask){try{const r=await api('/api/tasks/cancel',{task_id:activeResearchTask});msg(r.message);}catch(error){msg(error.message,true);}}};
$('#research-connect').onclick=()=>task('/api/research/connect',{path:$('#research-path').value},async r=>{msg(r.message);await load();});$('#research-build').onclick=()=>task('/api/research/build',{},load);
$('#research-explain').onclick=()=>last&&task('/api/research/explain',{id:last.id},r=>{$('#research-interpretation').innerHTML=`<h3>DeepSeek 解读 · 模型推断</h3><p>${esc(r.summary)}</p><ul>${r.limitations.concat(r.next_steps).map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`;});
$('#research-save').onclick=()=>{const name=prompt('给这个筛选队列命名');if(name&&last)task('/api/research/cohort',{name,plan:last.plan},load);};
const examples={compare:'比较 2025 年 3–4 月与 2026 年 3–4 月，共同三类近期所见广告中 Python 的全文提及率，按唯一广告 ID 去重。',pairs:'在共同三类中查看生成式 AI 词语在同一广告首末观察版本中的新增与删除，给出 20 个原文样例。',skills:'分析 Education & Training 类别的近期所见广告，列出 36 类能力的全文提及率。'};document.querySelectorAll('[data-example]').forEach(b=>b.onclick=()=>$('#research-command').value=examples[b.dataset.example]);
let loaded=false;function activate(){if(!loaded){loaded=true;load();}}document.querySelector('[data-page="research"]').addEventListener('click',activate);document.addEventListener('jobcompass:page',e=>{if(e.detail.page==='research')activate();});if(document.querySelector('#research').classList.contains('active'))activate();
})();
