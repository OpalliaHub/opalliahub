'use strict';
(() => {
  if (location.protocol === 'file:') return;
  const $ = selector => document.querySelector(selector);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  $('#learning-build').addEventListener('click', async () => {
    const button = $('#learning-build');
    button.disabled = true;
    $('#learning-summary').textContent = '正在统计岗位技能与学习顺序…';
    // Clear old results before each request so a failed filter cannot look successful.
    $('#learning-metrics').innerHTML = ''; $('#learning-skills').innerHTML = '';
    $('#learning-order').hidden = true; $('#learning-notes').textContent = '';
    try {
      const response = await fetch('/api/learning', {method:'POST', headers:{'Content-Type':'application/json','X-JobCompass':'1'}, body:JSON.stringify({target:$('#learning-target').value.trim(),limit:Number($('#learning-limit').value)})});
      const plan = await response.json();
      if (!response.ok) throw new Error(plan.error || '无法生成学习计划');
      const m = plan.metrics;
      $('#learning-summary').textContent = plan.summary;
      const stats = [['分析岗位',m.analyzed_jobs,m.demo_fallback?'全部为虚构演示数据':'当前库中的历史或在线岗位'],['识别技能',m.distinct_skills,'来自有限的关键词词典'],['待补充技能',m.missing_skills,'简历未体现，不等于不会'],['学习步骤',m.learning_steps,'含项目预设的先修建议']];
      $('#learning-metrics').innerHTML = stats.map(([label,value,detail])=>`<div class="stat"><div class="stat-top">${label}</div><div class="stat-number">${value}</div><div class="stat-foot">${detail}</div></div>`).join('');
      $('#learning-order').hidden = !plan.learning_order.length;
      $('#learning-order').innerHTML = `<div class="section-title"><h2>建议学习顺序</h2><span class="pill">基础优先</span></div><ol class="learning-route">${plan.learning_order.map(skill=>`<li>${escape(skill)}</li>`).join('')}</ol><p class="small muted">优先展示高频技能；路线补入必要的基础技能，属于学习建议，不是招聘方的硬性要求。</p>`;
      $('#learning-skills').innerHTML = plan.skills.map(row=>`<article class="panel skill-card"><div class="section-title"><h2>${escape(row.skill)}</h2><span class="pill ${row.already_known?'skill-known':''}">${row.already_known?'简历已体现':'可以补充'}</span></div><p><b>${row.count}</b> 个岗位提及 · 占分析岗位 ${row.share_pct}%</p><div class="skill-meter" role="meter" aria-label="${escape(row.skill)} 岗位提及率" aria-valuenow="${row.share_pct}" aria-valuemin="0" aria-valuemax="100"><progress max="100" value="${row.share_pct}"></progress></div><p class="small muted">先修建议：${row.prerequisites.length?row.prerequisites.map(escape).join(' → '):'没有预设先修要求'}</p><h3>岗位证据</h3><ul class="skill-evidence">${row.example_jobs.map(job=>`<li><b>${escape(job.title)}</b><span>${escape(job.company)}</span></li>`).join('')}</ul></article>`).join('');
      $('#learning-notes').textContent = `排除 ${m.excluded_expired_jobs||0} 条过期岗位、${m.excluded_demo_jobs} 条演示岗位；合并 ${m.duplicate_jobs} 条重复标识。${m.limitations}`;
    } catch (error) {
      $('#learning-summary').textContent = error.message || '处理失败，请稍后再试。';
    } finally { button.disabled = false; }
  });
})();
