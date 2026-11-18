'use strict';
/* OLAP UI: model instructions are validated/executed by the server, never eval'd here. */
(() => {
  if (location.protocol === 'file:') return;
  const $ = selector => document.querySelector(selector);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const palette = ['#6576df','#57a7a0','#b0a1d8','#85a6cf','#d4aa7a','#8babc0','#b78a9c'];
  const dimensionNames = {month:'月份',quarter:'季度',year:'年份',sector:'职业类别',location:'地区'};
  const measureNames = {ads:'岗位广告数',employers:'雇主标签数',mentions:'提及广告数',share_pct:'全文提及率'};
  const conceptNames = {python:'Python',sql:'SQL',generative_ai:'生成式 AI',large_language_models:'大语言模型',agentic_ai:'Agent 相关',machine_learning:'机器学习',communication:'沟通能力',teamwork:'团队合作',cantonese:'粤语',english:'英语',bachelor:'学士',master:'硕士',data_analysis:'数据分析',excel:'Excel',aws:'AWS',java:'Java'};
  const categoryNames = {'Information & Communication Technology':'信息与通信技术','Education & Training':'教育与培训','Engineering':'工程','Unknown':'未标注'};
  const timeDimensions = new Set(['month','quarter','year']);
  const charts = {};
  const pendingCharts = {};
  let catalog = null, last = null, lastContext = null, exactFilters = {}, busy = false, taskId = null, chartType = 'line', revision = 0, initialized = false;
  let metadataRevision = 0;
  let activeReply=null;
  const welcomeHTML=$('#analytics-chat-messages').innerHTML;
  const clone = value => JSON.parse(JSON.stringify(value));
  const number = (value, percent=false) => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('zh-CN',{maximumFractionDigits:percent?2:0}) + (percent?'%':'') : '—';
  const category = value => categoryNames[value] || String(value ?? '未标注');
  const concept = value => conceptNames[value] || catalog?.concepts?.find(item=>item.id===value)?.label || value;
  const prettyDate = value => {if(!value)return '尚无更新时间';const parsed=new Date(value);return Number.isNaN(parsed.getTime())?String(value).slice(0,10):parsed.toLocaleDateString('zh-CN');};


  function setWorkspaceView(view) {
    const chat=view==='chat';document.body.dataset.workspaceView=chat?'chat':'panel';
    $('#workspace-tab-panel').classList.toggle('active',!chat);$('#workspace-tab-panel').setAttribute('aria-pressed',String(!chat));
    $('#workspace-tab-chat').classList.toggle('active',chat);$('#workspace-tab-chat').setAttribute('aria-pressed',String(chat));
    if(chat){$('#chat-unread').hidden=true;scrollChat();}else requestAnimationFrame(()=>{flushCharts();Object.values(charts).forEach(instance=>instance.resize());});
  }
  function scrollChat() {const log=$('#analytics-chat-messages');requestAnimationFrame(()=>{log.scrollTop=log.scrollHeight;});}
  function appendMessage(role,text,pending=false) {
    const message=document.createElement('article');message.className='chat-message '+role+(pending?' pending':'');
    const label=document.createElement('div');label.className='chat-message-label';label.textContent=role==='user'?'你':'研究助手';
    const body=document.createElement('div');body.className='chat-message-body';body.textContent=text;message.append(label,body);$('#analytics-chat-messages').append(message);
    const history=$('#analytics-chat-messages').querySelectorAll('.chat-message:not(.welcome-message)');if(history.length>80)history[0].remove();scrollChat();return message;
  }
  function completeReply(result,error) {
    if(!activeReply)return;activeReply.classList.remove('pending');const body=activeReply.querySelector('.chat-message-body');body.replaceChildren();
    if(error){activeReply.classList.add('chat-error');const message=document.createElement('p');message.textContent=error;body.append(message);const note=document.createElement('small');note.textContent='没有将失败指令显示为新结果，可以调整问题继续提问。';body.append(note);}
    else {
      const title=document.createElement('p');title.className='chat-result-title';title.textContent='分析已完成，左侧面板已更新。';body.append(title);
      const stats=document.createElement('div');stats.className='chat-result-stats';
      for(const [value,label] of [[number(result.totals.ads),'样本广告'],[String(result.rows.length),'结果分组']]){const item=document.createElement('div');const strong=document.createElement('strong');strong.textContent=value;const caption=document.createElement('span');caption.textContent=label;item.append(strong,caption);stats.append(item);}body.append(stats);
      const scope=document.createElement('p');scope.className='chat-result-scope';scope.textContent=chartTitle(result.query);body.append(scope);
      if(result.instruction?.explanation){const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='查看分析口径';const explanation=document.createElement('p');explanation.textContent=result.instruction.explanation;details.append(summary,explanation);body.append(details);}
      const button=document.createElement('button');button.className='chat-open-panel';button.type='button';button.textContent='打开研究面板 →';button.addEventListener('click',()=>{document.dispatchEvent(new CustomEvent('jobcompass:navigate',{detail:{page:'analytics',preserveWorkspaceView:true}}));setWorkspaceView('panel');});body.append(button);
      const note=document.createElement('small');note.textContent='统计来自当前队列；模型口径说明不等于事实验证。';body.append(note);
    }
    if(document.body.dataset.workspaceView!=='chat')$('#chat-unread').hidden=false;activeReply=null;scrollChat();
  }
  function bindPromptExamples() {document.querySelectorAll('[data-analytics-prompt]').forEach(button=>button.addEventListener('click',()=>{$('#analytics-command').value=button.dataset.analyticsPrompt;runCommand();}));}

  async function api(path, body) {
    const response = await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-JobCompass':'1'},body:JSON.stringify(body)});
    let data;try {data=await response.json();}catch(error){throw new Error('服务没有返回可读取的数据，请稍后重试。');}
    if(!response.ok)throw new Error(data.error||'查询失败，请检查筛选条件。');
    return data;
  }
  function alert(message='') {$('#analytics-alert').hidden=!message;$('#analytics-alert').textContent=message;}
  function setBusy(value) {
    busy=value;$('#analytics').setAttribute('aria-busy',String(value));
    document.querySelectorAll('#analytics-filter-form input,#analytics-filter-form select,#analytics-filter-form button,#analytics-command-form button,[data-analytics-prompt],#analytics-chat-clear,.chat-open-panel,#analytics-refresh,#analytics-reset').forEach(el=>el.disabled=value);
    $('#analytics-send').textContent=value?'正在分析…':'开始分析 →';
  }
  function execution(stage,label,showStages=true) {
    $('#analytics-execution').hidden=false;$('#analytics-execution-label').textContent=label;$('#analytics-execution .execution-stages').hidden=!showStages;
    if(activeReply&&stage!=='done'&&stage!=='error'){activeReply.querySelector('.chat-message-body').textContent=label;scrollChat();}
    const names=['understand','query','chart'];const index=names.indexOf(stage);
    document.querySelectorAll('[data-execution-stage]').forEach(el=>{const i=names.indexOf(el.dataset.executionStage);el.classList.toggle('active',i===index);el.classList.toggle('done',stage==='done'||i<index);});
  }
  function showEmpty(id,title,detail) {
    const el=$('#analytics-'+id+'-empty');el.hidden=false;
    el.innerHTML='<span class="chart-empty-icon">◌</span><b>'+escape(title)+'</b><span>'+escape(detail)+'</span>';
    charts[id]?.clear();
    $('#analytics-'+id+'-chart').setAttribute('aria-label',title+'。'+detail);
  }
  function clearResults(reason='查询尚未完成') {
    Object.keys(pendingCharts).forEach(key=>delete pendingCharts[key]);
    last=null;$('#analytics-export').disabled=true;$('#analytics-export-table').disabled=true;$('#analytics-export-json').disabled=true;$('#analytics-export-png').disabled=true;
    $('#analytics-table').innerHTML='<div class="empty"><b>'+escape(reason)+'</b>成功查询后，数据与图表会同步更新。</div>';
    $('#analytics-table-count').textContent='';$('#analytics-chart-subtitle').textContent=reason+'，完成后更新当前样本口径';$('#analytics-table-caption').textContent='查询完成后显示新的统计结果';$('#analytics-query-json').textContent='';$('#analytics-instruction').textContent='';
    $('#analytics-query-time').textContent='';$('#analytics-result-note').textContent='';$('#analytics-scope-summary').textContent='';$('#analytics-coverage-note').hidden=true;$('#analytics-limitations').hidden=true;
    document.querySelectorAll('#analytics-kpis strong').forEach(el=>el.textContent='—');
    for(const id of ['main','sector','heatmap'])showEmpty(id,reason,'不会用演示数值替代查询结果');
  }
  function chart(id) {
    if(!window.echarts)return null;
    if(!charts[id])charts[id]=echarts.init($('#analytics-'+id+'-chart'),null,{renderer:'canvas'});
    return charts[id];
  }
  function chartBase() {
    return {color:palette,backgroundColor:'#fff',animationDuration:420,animation:!matchMedia('(prefers-reduced-motion: reduce)').matches,
      textStyle:{fontFamily:'-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif',fontSize:10,color:'#79869c'},
      aria:{enabled:true},tooltip:{trigger:'axis',renderMode:'richText',confine:true,backgroundColor:'#fff',borderColor:'#e5eaf3',borderWidth:1,padding:12,textStyle:{color:'#536580',fontSize:11}},
      grid:{left:52,right:24,top:40,bottom:62},xAxis:{type:'category',axisLine:{lineStyle:{color:'#e9edf5'}},axisTick:{show:false},axisLabel:{color:'#8794aa',fontSize:9,margin:13}},
      yAxis:{type:'value',splitNumber:4,axisLabel:{color:'#97a3b6',fontSize:9,formatter:value=>Math.abs(value)>=10000?(value/10000).toFixed(value%10000===0?0:1)+'万':number(value)},splitLine:{lineStyle:{color:'#eff2f7',type:'dashed'}},axisLine:{show:false},axisTick:{show:false}},
      legend:{show:false},dataZoom:[]};
  }
  function timeLabels(field, values) {
    const labels=[...new Set(values)].sort();if(!timeDimensions.has(field))return labels;
    const valid=labels.filter(value=>field==='month'?/^\d{4}-\d{2}$/.test(value):field==='quarter'?/^\d{4}-Q[1-4]$/.test(value):/^\d{4}$/.test(value));
    if(!valid.length)return labels;
    const index=value=>field==='month'?Number(value.slice(0,4))*12+Number(value.slice(5))-1:field==='quarter'?Number(value.slice(0,4))*4+Number(value.slice(6))-1:Number(value);
    const start=index(valid[0]),end=index(valid[valid.length-1]);if(end-start>240)return labels;
    const expanded=[];for(let i=start;i<=end;i++)expanded.push(field==='month'?Math.floor(i/12)+'-'+String(i%12+1).padStart(2,'0'):field==='quarter'?Math.floor(i/4)+'-Q'+(i%4+1):String(i));
    return expanded.concat(labels.filter(value=>!valid.includes(value)));
  }
  function flushCharts(){for(const [id,render] of Object.entries(pendingCharts))applyChart(id,render.option,render.onClick);}
  function applyChart(id, option, onClick) {
    if(!$('#analytics').classList.contains('active')||(matchMedia('(max-width:1100px)').matches&&document.body.dataset.workspaceView==='chat')){pendingCharts[id]={option,onClick};return;}
    delete pendingCharts[id];
    const instance=chart(id);if(!instance){showEmpty(id,'图表组件未加载','仍可在下方查看表格并导出结果');return;}
    $('#analytics-'+id+'-empty').hidden=true;instance.setOption(option,true);instance.off('click');if(onClick)instance.on('click',onClick);
    requestAnimationFrame(()=>instance.resize());
  }
  function valueLabel(value,query) {return number(value,query.measure==='share_pct');}
  function chartTitle(query) {return query.dimensions.map(id=>dimensionNames[id]||id).join(' × ')+' · '+(query.measure==='mentions'||query.measure==='share_pct'?concept(query.concept)+' ':'')+measureNames[query.measure];}

  function heatmapOption(result) {
    const {query,pivot}=result;const first=query.dimensions[0],second=query.dimensions[1];
    const horizontal=timeDimensions.has(first)?first:timeDimensions.has(second)?second:first;
    const vertical=horizontal===first?second:first;
    const x=timeLabels(horizontal,result.rows.map(row=>row[horizontal]));
    const y=[...new Set(result.rows.map(row=>row[vertical]))].sort();
    const values=result.rows.filter(row=>typeof row.value==='number'&&Number.isFinite(row.value)).map(row=>({value:[x.indexOf(row[horizontal]),y.indexOf(row[vertical]),row.value],dimensions:{[first]:row[first],[second]:row[second]}}));
    const max=Math.max(1,...values.map(row=>row.value[2]));const option=chartBase();
    option.grid={left:vertical==='sector'?125:100,right:35,top:22,bottom:72};
    option.xAxis={...option.xAxis,data:x,splitArea:{show:true,areaStyle:{color:['#fafbfe','#fafbfe']}},axisLabel:{...option.xAxis.axisLabel,rotate:x.length>16?35:0,formatter:value=>value==='Unknown'?'未标注':value}};
    option.yAxis={type:'category',data:y,axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#71819b',fontSize:9,width:110,overflow:'truncate',formatter:category},splitArea:{show:true,areaStyle:{color:['#fafbfe','#fafbfe']}}};
    option.visualMap={type:'continuous',min:0,max,calculable:false,orient:'horizontal',left:'center',bottom:12,itemWidth:9,itemHeight:130,text:[valueLabel(max,query),'0'],textStyle:{fontSize:8,color:'#97a2b6'},inRange:{color:['#eef1ff','#cbd3fa','#9cabea','#6c7fdf','#455ac8']}};
    option.tooltip={...option.tooltip,trigger:'item',formatter:params=>{const data=params.data;return x[data.value[0]]+' / '+category(y[data.value[1]])+'\n'+measureNames[query.measure]+'  '+valueLabel(data.value[2],query);}};
    option.series=[{name:measureNames[query.measure],type:'heatmap',data:values,label:{show:x.length<=12&&y.length<=8,fontSize:9,color:'#5063ac',formatter:params=>query.measure==='share_pct'?number(params.value[2],true):number(params.value[2])},itemStyle:{borderColor:'#fff',borderWidth:3,borderRadius:3},emphasis:{itemStyle:{borderColor:'#d5dcff',borderWidth:2}}}];
    if(x.length>18)option.dataZoom=[{type:'inside',xAxisIndex:0,filterMode:'none'}];
    return option;
  }
  function renderMain(result, preferred) {
    const query=result.query;let dimensions=[...query.dimensions];
    const selected=preferred==='table'?'bar':preferred;
    chartType=selected||(dimensions.length===2?'heatmap':timeDimensions.has(dimensions[0])?'line':'bar');
    if(chartType==='heatmap'&&dimensions.length!==2)chartType='bar';
    const lineAllowed=dimensions.filter(dimension=>timeDimensions.has(dimension)).length===1;
    if(chartType==='line'&&!lineAllowed)chartType='bar';
    if(chartType==='line'&&!timeDimensions.has(dimensions[0]))dimensions.reverse();
    document.querySelectorAll('[data-chart-type]').forEach(button=>{const type=button.dataset.chartType;button.disabled=(type==='heatmap'&&dimensions.length!==2)||(type==='line'&&!lineAllowed);button.classList.toggle('active',type===chartType);button.setAttribute('aria-pressed',String(type===chartType));});
    $('#analytics-chart-title').textContent=chartTitle(query);
    $('#analytics-chart-subtitle').textContent=(query.dataset==='research'?'纵向研究样本':'当前岗位样本')+' · '+(query.dedup==='family'?'雇主正文族':'唯一广告 ID')+' · '+number(result.totals.ads)+' 条广告';
    $('#analytics-query-time').textContent=typeof result.metadata?.elapsed_seconds==='number'?result.metadata.elapsed_seconds.toFixed(2)+' 秒':'';
    $('#analytics-result-note').textContent=result.metadata?.truncated?'仅展示前 '+result.rows.length+' / '+result.metadata.total_groups+' 个分组；上方指标为完整筛选总量':'悬停查看数值 · 点击数据点下钻 · 缺失值保留为空白';
    if(!result.rows.length){showEmpty('main','当前口径下没有数据','调整日期、行业或其他筛选条件');return;}
    if(chartType==='heatmap'){applyChart('main',heatmapOption(result),params=>params.data?.dimensions&&drill(params.data.dimensions));return;}
    const field=dimensions[0],seriesField=dimensions[1];
    let labels=chartType==='line'?timeLabels(field,result.rows.map(row=>row[field])):[...new Set(result.rows.map(row=>row[field]))];
    const seriesLabels=seriesField?[...new Set(result.rows.map(row=>row[seriesField]))]:[null];
    const option=chartBase();const horizontal=chartType==='bar'&&!timeDimensions.has(field)&&dimensions.length===1;
    const observed=new Map(result.rows.map(row=>[JSON.stringify([row[field],seriesField?row[seriesField]:null]),row]));
    option.xAxis.data=labels;option.xAxis.axisLabel.formatter=value=>category(value);
    option.yAxis.max=query.measure==='share_pct'?100:null;
    if(query.measure==='share_pct')option.yAxis.axisLabel.formatter=value=>value+'%';
    if(horizontal){option.grid={left:132,right:42,top:22,bottom:35};option.yAxis={type:'category',data:labels,inverse:true,axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#7b8aa3',fontSize:10,width:115,overflow:'truncate',formatter:category}};option.xAxis={...chartBase().yAxis,max:query.measure==='share_pct'?100:null};option.tooltip.axisPointer={type:'shadow'};}
    else if(labels.length>12){option.dataZoom=[{type:'inside',xAxisIndex:0,filterMode:'none'},{type:'slider',xAxisIndex:0,height:13,bottom:10,borderColor:'transparent',backgroundColor:'#f5f7fb',fillerColor:'#e5e9fb',handleSize:8,handleStyle:{color:'#b2bde8'},showDetail:false}];}
    if(seriesLabels.length>1){option.legend={show:true,top:8,left:44,right:20,type:'scroll',itemWidth:9,itemHeight:3,textStyle:{fontSize:9,color:'#8e9cb2'},formatter:category};option.grid.top=48;}
    option.series=seriesLabels.map((name,index)=>({name:name===null?measureNames[query.measure]:String(name),type:chartType,connectNulls:false,smooth:false,showSymbol:labels.length<40,symbol:'circle',symbolSize:5,
      data:labels.map(label=>{const row=observed.get(JSON.stringify([label,name]));return {value:row?.value??null,dimensions:row?Object.fromEntries(dimensions.map(dim=>[dim,row[dim]])):null};}),
      barMaxWidth:horizontal?18:28,itemStyle:{color:palette[index%palette.length],borderRadius:chartType==='bar'?(horizontal?[0,3,3,0]:[3,3,0,0]):0},lineStyle:{width:2},
      areaStyle:chartType==='line'&&seriesLabels.length===1?{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'#6576df20'},{offset:1,color:'#6576df01'}]}}:undefined,
      emphasis:{focus:'series'},label:{show:horizontal,position:'right',color:'#8a99b1',fontSize:9,formatter:params=>valueLabel(params.value,query)}}));
    option.tooltip.formatter=params=>{const list=Array.isArray(params)?params:[params];return category(list[0]?.axisValue||list[0]?.name||'')+'\n'+list.filter(row=>row.value!==null&&row.value!==undefined).map(row=>category(row.seriesName)+'  '+valueLabel(row.value,query)).join('\n');};
    applyChart('main',option,params=>params.data?.dimensions&&drill(params.data.dimensions));
  }
  function renderSector(result) {
    if(!result.rows.length){showEmpty('sector','暂无行业数据','当前筛选没有可统计的广告');return;}
    const option=chartBase();option.grid={left:115,right:48,top:25,bottom:30};
    option.xAxis={...option.yAxis,type:'value'};option.yAxis={type:'category',data:result.rows.map(row=>row.sector),inverse:true,axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#7b8aa3',fontSize:9,width:100,overflow:'truncate',formatter:category}};
    option.tooltip={...option.tooltip,trigger:'item',formatter:params=>category(params.name)+'\n广告数  '+number(params.value)};
    option.series=[{type:'bar',barMaxWidth:19,data:result.rows.map((row,index)=>({value:row.ads,name:row.sector,dimensions:{sector:row.sector},itemStyle:{color:index===0?'#7181dd':'#c7cff0'}})),itemStyle:{borderRadius:[0,3,3,0]},label:{show:true,position:'right',color:'#8291ab',fontSize:9,formatter:params=>number(params.value)}}];
    applyChart('sector',option,params=>params.data?.dimensions&&drill(params.data.dimensions));
  }
  function renderHeatmap(result) {
    $('#analytics-heatmap-title').textContent=result.query.dimensions.map(dim=>dimensionNames[dim]).join(' × ');
    $('#analytics-heatmap-subtitle').textContent=measureNames[result.query.measure]+' · 与当前主视图使用相同筛选条件';
    $('#analytics-heatmap-note').textContent=result.metadata?.truncated?'展示 '+result.rows.length+' / '+result.metadata.total_groups+' 个分组':'点击单元格查看对应队列';
    if(!result.rows.length){showEmpty('heatmap','没有可交叉分析的数据','未观察到的组合不会补成零');return;}
    applyChart('heatmap',heatmapOption(result),params=>params.data?.dimensions&&drill(params.data.dimensions));
  }
  function renderKPIs(result) {
    const total=result.totals, label=concept(result.query.concept);
    const cards=[['样本广告',number(total.ads),'筛选后去重的广告记录'],['雇主标签',number(total.employers),'按规范化的雇主显示名称'],[label+' 提及',number(total.mentions),'全文中出现该探针的广告'],['样本提及率',number(total.share_pct,true),'提及广告 / 全部筛选广告']];
    $('#analytics-kpis').innerHTML=cards.map(([title,value,foot])=>'<div class="kpi-card"><span>'+escape(title)+'</span><strong>'+escape(value)+'</strong><small>'+escape(foot)+'</small></div>').join('');
  }
  function renderTable(result) {
    const fields=[...result.query.dimensions,'ads','employers','mentions','share_pct'];
    if(!result.rows.length){$('#analytics-table').innerHTML='<div class="empty"><b>没有符合条件的观测</b>请调整筛选；没有把缺失结果填成零。</div>';}
    else {
      $('#analytics-table').innerHTML='<table><thead><tr>'+fields.map(field=>'<th class="'+(result.query.dimensions.includes(field)?'':'numeric')+'">'+escape(dimensionNames[field]||measureNames[field])+'</th>').join('')+'</tr></thead><tbody>'+result.rows.map((row,index)=>'<tr>'+fields.map((field,i)=>'<td class="'+(result.query.dimensions.includes(field)?'':'numeric')+'">'+(i===0?'<button class="row-drill" data-result-row="'+index+'">'+escape(category(row[field]))+'</button>':escape(result.query.dimensions.includes(field)?category(row[field]):number(row[field],field==='share_pct')))+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
      document.querySelectorAll('[data-result-row]').forEach(button=>button.addEventListener('click',()=>{const row=result.rows[Number(button.dataset.resultRow)];drill(Object.fromEntries(result.query.dimensions.map(dim=>[dim,row[dim]])));}));
    }
    $('#analytics-table-caption').textContent='筛选总量 '+number(result.totals.ads)+' 条广告 · 维度分组按 '+(result.query.sort==='label'?'标签排序':'指标从高到低排序');
    $('#analytics-table-count').textContent=result.rows.length+' 个已显示分组'+(result.metadata?.truncated?' / 共 '+result.metadata.total_groups+' 组':'');
    $('#analytics-query-json').textContent=JSON.stringify({query:result.query,metadata:result.metadata},null,2);
    $('#analytics-instruction').textContent=(result.instruction?.explanation?'DeepSeek 口径说明（模型生成，需核实）：'+result.instruction.explanation:'使用当前手动选择的统计口径。')+(result.chart?.title?'\n模型建议标题（未用作统计标题）：'+result.chart.title:'');
  }
  function fillControls(query) {
    $('#analytics-dataset').value=query.dataset;$('#analytics-dimension').value=query.dimensions[0];$('#analytics-dimension-2').value=query.dimensions[1]||'';
    $('#analytics-measure').value=query.measure;$('#analytics-concept').value=query.concept;$('#analytics-dedup').value=query.dedup;
    for(const [key,id] of Object.entries({title:'title-filter',sector:'sector-filter',location:'location-filter',company:'company-filter',start:'start',end:'end',cutoff:'cutoff'})){
      const element=$('#analytics-'+id);const value=query.filters?.[key]||'';
      if(element.tagName==='SELECT'&&value&&![...element.options].some(option=>option.value===value))element.add(new Option(category(value),value));element.value=value;
    }
    $('#analytics-common').checked=query.filters?.common_only===true;$('#analytics-fresh').checked=query.filters?.fresh_only===true;exactFilters=clone(query.exact_filters||{});
    updateControlState();renderBreadcrumbs(query);
  }
  function updateControlState() {
    const first=$('#analytics-dimension').value;
    for(const option of $('#analytics-dimension-2').options)option.disabled=option.value===first;
    if($('#analytics-dimension-2').value===first)$('#analytics-dimension-2').value='';
    const needed=['mentions','share_pct'].includes($('#analytics-measure').value);const conceptField=$('#analytics-concept-field');conceptField.classList.toggle('optional-concept',!needed);conceptField.firstChild.textContent=needed?'技能 / 词语':'附加词语观察';conceptField.title=needed?'当前统计指标按所选探针计算':'不筛选广告总量，仅用于上方附加提及指标';
  }
  function queryFromControls() {
    const dimensions=[$('#analytics-dimension').value];if($('#analytics-dimension-2').value)dimensions.push($('#analytics-dimension-2').value);
    const filters={common_only:$('#analytics-common').checked,fresh_only:$('#analytics-fresh').checked};
    for(const [key,id] of Object.entries({title:'title-filter',sector:'sector-filter',location:'location-filter',company:'company-filter',start:'start',end:'end',cutoff:'cutoff'})){const value=$('#analytics-'+id).value.trim();if(value)filters[key]=value;}
    if(filters.start&&filters.end&&filters.start>filters.end)throw new Error('起始日期不能晚于截止日期。');
    return {dataset:$('#analytics-dataset').value,dimensions,measure:$('#analytics-measure').value,concept:$('#analytics-concept').value,filters,exact_filters:clone(exactFilters),dedup:$('#analytics-dedup').value,limit:100,sort:timeDimensions.has(dimensions[0])?'label':'value_desc'};
  }
  function renderBreadcrumbs(query) {
    const entries=Object.entries(query.exact_filters||{});$('#analytics-reset').hidden=!entries.length;
    $('#analytics-breadcrumbs').innerHTML=entries.length?entries.map(([key,value])=>'<span class="drilldown-chip">'+escape(dimensionNames[key])+': '+escape(category(value))+'<button type="button" data-remove-drill="'+escape(key)+'" aria-label="移除'+escape(dimensionNames[key])+'下钻">×</button></span>').join(''):'<span class="drilldown-placeholder">点击图表中的数据点，继续下钻分析</span>';
    document.querySelectorAll('[data-remove-drill]').forEach(button=>button.onclick=()=>{if(busy)return;delete exactFilters[button.dataset.removeDrill];runQuery(queryFromControls());});
  }
  async function companions(result, token) {
    const shared=clone(result.query);const sectorQuery={...shared,dimensions:['sector'],measure:'ads',limit:10,sort:'value_desc'};
    const temporal=result.query.dimensions.includes('year')?'year':'quarter';const heatQuery={...shared,dimensions:[temporal,'sector'],limit:100,sort:'label'};
    const results=await Promise.allSettled([api('/api/analytics/query',{query:sectorQuery}),api('/api/analytics/query',{query:heatQuery})]);
    if(token!==revision)return;
    if(results[0].status==='fulfilled')renderSector(results[0].value);else showEmpty('sector','行业分布暂时不可用',results[0].reason.message);
    if(results[1].status==='fulfilled')renderHeatmap(results[1].value);else showEmpty('heatmap','交叉分析暂时不可用',results[1].reason.message);
  }
  async function renderResult(result, preferred, token) {
    if(token!==revision)return;if(!result||!Array.isArray(result.rows)||!result.query||!result.totals)throw new Error('分析结果格式不完整，未显示旧数据。');
    last=result;lastContext={query:clone(result.query),totals:clone(result.totals)};fillControls(result.query);renderKPIs(result);renderMain(result,preferred);renderTable(result);
    $('#analytics-export').disabled=false;$('#analytics-export-table').disabled=false;$('#analytics-export-json').disabled=false;$('#analytics-export-png').disabled=!window.echarts||!result.rows.length;
    const source=catalog?.datasets?.find(dataset=>dataset.id===result.query.dataset);
    $('#analytics-chat-context').textContent=(source?.label||'当前数据集')+' · '+result.query.dimensions.map(dim=>dimensionNames[dim]).join(' × ')+' · '+measureNames[result.query.measure];
    $('#analytics-freshness').textContent=(source?.label||'岗位样本')+' · 更新于 '+prettyDate(result.metadata?.updated_at||source?.updated_at);
    const interpretation=[result.metadata?.date_meaning,result.metadata?.employer_definition,'全文提及不等于真实技能要求；样本不代表整体招聘市场。'];
    if(result.metadata?.truncated)interpretation.push('图表分组经过截断，总量由完整队列独立计算。');
    $('#analytics-methodology-text').textContent=interpretation.filter(Boolean).join(' ');
    const filters=result.query.filters||{};
    const scope=[filters.common_only?'共同三个职业类别':'全部职业类别',filters.fresh_only?'近期所见（−1 至 35 天）':'未限制观察间隔',filters.start||filters.end?('来源日期 '+(filters.start||'不限')+' 至 '+(filters.end||'不限')):'全部来源日期'];
    if(filters.cutoff)scope.push('观察截止 '+filters.cutoff);
    for(const key of ['title','sector','location','company'])if(filters[key])scope.push(({title:'职位',sector:'类别',location:'地区',company:'雇主'})[key]+'：'+filters[key]);
    $('#analytics-scope-summary').innerHTML='<span class="scope-summary-label">当前样本口径</span>'+scope.map(value=>'<span>'+escape(value)+'</span>').join('');
    const warnings=Array.isArray(result.metadata?.warnings)?result.metadata.warnings.filter(item=>typeof item==='string'):[];
    const coverage=warnings.find(item=>result.query.dataset==='research'?/断档|覆盖变化|类别覆盖/.test(item):/当前库/.test(item));
    $('#analytics-coverage-note').hidden=!coverage;$('#analytics-coverage-note').textContent=coverage||'';
    $('#analytics-limitations').hidden=!warnings.length;$('#analytics-limitations-label').textContent='数据覆盖与解释边界 · '+warnings.length+' 项说明';
    $('#analytics-limitations-list').innerHTML=warnings.map(value=>'<li>'+escape(value)+'</li>').join('');
    await companions(result,token);
  }
  async function runQuery(query,preferred) {
    if(busy)return;const token=++revision;setBusy(true);alert();execution('query','正在按面板筛选查询数据，不调用大模型…',false);
    clearResults('正在查询数据');
    try {const result=await api('/api/analytics/query',{query});await renderResult(result,preferred,token);execution('done','面板查询完成 · '+number(result.totals.ads)+' 条广告 · '+result.rows.length+' 个分组',false);}
    catch(error){if(token===revision){clearResults('查询未完成');alert(error.message);execution('error','本次查询未完成，未显示旧结果',false);}}
    finally {if(token===revision)setBusy(false);}
  }
  async function runCommand() {
    if(busy)return;const command=$('#analytics-command').value.trim();if(!command){$('#analytics-command').focus();return;}
    if(command.length>1500){alert('研究问题需为 1–1500 个字符。');return;}
    const dataset=$('#analytics-dataset').value;const context=lastContext?.query.dataset===dataset?clone(lastContext):null;
    const token=++revision;setBusy(true);alert();appendMessage('user',command);activeReply=appendMessage('assistant','正在理解问题，随后自动查询数据…',true);$('#analytics-command').value='';clearResults('正在理解研究问题');execution('understand','DeepSeek 正在理解问题，随后将自动查询数据…');
    try {
      const started=await api('/api/analytics/command',{command,dataset,context});taskId=started.task_id;
      let result=started;
      if(taskId){let failures=0;const began=Date.now();for(;;){
        if(Date.now()-began>10*60*1000)throw new Error('等待结果超时。服务端任务可能仍在运行，请稍后查看。');
        let status;try{status=await api('/api/tasks/'+encodeURIComponent(taskId));failures=0;}catch(error){if(++failures>=4)throw error;await new Promise(resolve=>setTimeout(resolve,1600));continue;}
        if(status.progress?.phase)execution(/查询|计算|执行/.test(status.progress.phase)?'query':'understand',status.progress.phase);
        if(status.status==='error')throw new Error(status.error||'分析未完成。');
        if(status.status==='cancelled')throw new Error('分析已停止，未显示未完成的结果。');
        if(status.status==='done'){result=status.result;break;}await new Promise(resolve=>setTimeout(resolve,1200));
      }}
      execution('chart','查询已执行，正在更新图表…');await renderResult(result,result.chart?.type,token);execution('done','分析完成 · 图表与统计已更新');completeReply(result);
      document.dispatchEvent(new CustomEvent('jobcompass:navigate',{detail:{page:'analytics',preserveWorkspaceView:true}}));
      if(result.chart?.type==='table')$('#analytics-table').scrollIntoView({behavior:'smooth',block:'center'});
    } catch(error){if(token===revision){clearResults('本次分析未完成');alert(error.message);execution('error','指令未成功执行，请调整问题后重试');completeReply(null,error.message);}}
    finally{taskId=null;if(token===revision)setBusy(false);}
  }
  function drill(values) {
    if(busy||!last)return;exactFilters={...exactFilters,...values};const query=queryFromControls();query.exact_filters=clone(exactFilters);
    const next=['month','sector','location','quarter'].find(dimension=>!Object.prototype.hasOwnProperty.call(exactFilters,dimension));
    if(next)query.dimensions=[next];query.sort=timeDimensions.has(query.dimensions[0])?'label':'value_desc';runQuery(query);
  }
  function downloadCSV() {
    if(!last)return;const fields=[...last.query.dimensions,'ads','employers','mentions','share_pct'];
    const cell=value=>{let text=value===null||value===undefined?'':String(value);if(/^[\s]*[=+@-]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';};
    const csv='\ufeff'+[fields,...last.rows.map(row=>fields.map(field=>row[field]))].map(row=>row.map(cell).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='JobCompass-'+last.query.dimensions.join('-')+'-'+last.query.measure+'.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function downloadBlob(filename,content,type) {
    const url=URL.createObjectURL(new Blob([content],{type}));const anchor=document.createElement('a');anchor.href=url;anchor.download=filename;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function downloadJSON() {if(last)downloadBlob('JobCompass-analysis.json',JSON.stringify(last,null,2),'application/json;charset=utf-8');}
  function downloadPNG() {
    if(!last||!charts.main)return;
    const result=last,instance=charts.main,graphic=new Image();
    graphic.onload=()=>{const pad=36,header=106,footer=44,canvas=document.createElement('canvas');canvas.width=graphic.width+pad*2;canvas.height=graphic.height+header+footer;const context=canvas.getContext('2d');context.fillStyle='#ffffff';context.fillRect(0,0,canvas.width,canvas.height);context.fillStyle='#273b5d';context.font='600 25px -apple-system, sans-serif';context.fillText(chartTitle(result.query).slice(0,75),pad,40,canvas.width-pad*2);context.fillStyle='#75849d';context.font='16px -apple-system, sans-serif';context.fillText((result.query.dataset==='research'?'纵向研究样本':'当前岗位样本')+' · '+number(result.totals.ads)+' 条广告 · '+(result.query.dedup==='family'?'雇主正文族':'唯一广告 ID'),pad,75);context.drawImage(graphic,pad,header);context.font='13px -apple-system, sans-serif';context.fillText('JobCompass · 样本广告不等于招聘人数，全文提及不等于技能要求。',pad,canvas.height-16);canvas.toBlob(blob=>{if(!blob)return;downloadBlob('JobCompass-'+result.query.dimensions.join('-')+'-'+result.query.measure+'.png',blob,'image/png');},'image/png');};
    graphic.onerror=()=>alert('图表导出失败，请重试或下载数据表。');graphic.src=instance.getDataURL({type:'png',pixelRatio:2,backgroundColor:'#fff'});
  }
  function optionList(items,format=item=>item.label) {return items.map(item=>'<option value="'+escape(item.id)+'"'+(item.available===false?' disabled':'')+'>'+escape(format(item))+(item.available===false?' · 未就绪':'')+'</option>').join('');}
  async function loadCatalog(dataset, preserve=false) {
    const ticket=++metadataRevision;const data=await api('/api/analytics/catalog'+(dataset?'?dataset='+encodeURIComponent(dataset):''));if(ticket!==metadataRevision)return null;
    catalog=data;const selected=dataset||data.dataset||data.default_dataset;
    if(lastContext&&lastContext.query.dataset!==selected)lastContext=null;
    const previous=preserve?queryFromControls():null;
    $('#analytics-dataset').innerHTML=optionList(data.datasets);$('#analytics-dataset').value=selected;
    $('#analytics-dimension').innerHTML=optionList(data.dimensions);$('#analytics-dimension-2').innerHTML='<option value="">不交叉</option>'+optionList(data.dimensions);
    $('#analytics-measure').innerHTML=optionList(data.measures);$('#analytics-concept').innerHTML=optionList(data.concepts,item=>conceptNames[item.id]||item.label);
    $('#analytics-sector-filter').innerHTML='<option value="">所有类别</option>'+(data.facets?.sector||[]).map(item=>'<option value="'+escape(item.value)+'">'+escape(category(item.value))+'</option>').join('');
    const source=data.datasets.find(item=>item.id===selected);$('#analytics-chat-context').textContent=(source?.label||'当前数据集')+' · 可结合当前筛选继续提问';$('#topbar-dataset').textContent=source?.available?(source.label+' · '+number(source.ads)+' 条广告'):(source?.reason||'尚无可用数据');
    $('#analytics-freshness').textContent=(source?.label||'岗位样本')+' · 更新于 '+prettyDate(source?.updated_at);
    const query=previous||{dataset:selected,dimensions:['month'],measure:'ads',concept:'python',filters:{common_only:selected==='research',fresh_only:false},exact_filters:{},dedup:'id',limit:100,sort:'label'};
    query.dataset=selected;fillControls(query);
    if(data.ai)updateAI(data.ai);return query;
  }
  function updateAI(ai) {const status=$('#analytics-ai-status');status.classList.toggle('available',Boolean(ai?.configured));status.innerHTML='<span></span>'+escape(ai?.configured?'DeepSeek · 已连接':'DeepSeek · 暂未配置');}
  async function initialize() {
    if(initialized)return;initialized=true;
    try {const query=await loadCatalog();if(query)await runQuery(query);}
    catch(error){alert(error.message);clearResults('数据服务暂时不可用');$('#topbar-dataset').textContent='数据连接未完成';}
  }
  $('#analytics-filter-form').addEventListener('submit',event=>{event.preventDefault();try{runQuery(queryFromControls());}catch(error){alert(error.message);}});
  $('#analytics-command-form').addEventListener('submit',event=>{event.preventDefault();runCommand();});
  $('#analytics-command').addEventListener('keydown',event=>{if(event.key==='Enter'&&(event.metaKey||event.ctrlKey)){event.preventDefault();runCommand();}});
  bindPromptExamples();
  $('#analytics-dataset').addEventListener('change',async()=>{if(busy)return;const selected=$('#analytics-dataset').value;setBusy(true);alert();try{const query=await loadCatalog(selected);setBusy(false);if(query)await runQuery(query);}catch(error){alert(error.message);clearResults('数据集加载未完成');setBusy(false);}});
  $('#analytics-dimension').addEventListener('change',updateControlState);$('#analytics-measure').addEventListener('change',updateControlState);
  $('#analytics-refresh').addEventListener('click',async()=>{if(busy)return;setBusy(true);try{const query=await loadCatalog($('#analytics-dataset').value,true);setBusy(false);if(query)await runQuery(query,chartType);}catch(error){alert(error.message);setBusy(false);}});
  $('#analytics-reset').addEventListener('click',()=>{exactFilters={};runQuery(queryFromControls());});
  $('#analytics-clear-filters').addEventListener('click',()=>{const query=queryFromControls();query.filters={common_only:false,fresh_only:false};query.exact_filters={};fillControls(query);runQuery(query);});
  document.querySelectorAll('[data-chart-type]').forEach(button=>button.addEventListener('click',()=>{if(last)renderMain(last,button.dataset.chartType);}));
  $('#analytics-export').addEventListener('click',downloadCSV);$('#analytics-export-table').addEventListener('click',downloadCSV);$('#analytics-export-json').addEventListener('click',downloadJSON);$('#analytics-export-png').addEventListener('click',downloadPNG);
  document.addEventListener('jobcompass:state',event=>updateAI(event.detail.ai));
  document.addEventListener('jobcompass:page',event=>{if(event.detail.page==='analytics'){initialize();requestAnimationFrame(()=>{flushCharts();Object.values(charts).forEach(instance=>instance.resize());});}});
  if(window.ResizeObserver){const observer=new ResizeObserver(()=>Object.values(charts).forEach(instance=>instance.resize()));observer.observe($('#analytics'));}
  else window.addEventListener('resize',()=>Object.values(charts).forEach(instance=>instance.resize()));
  $('#workspace-tab-panel').addEventListener('click',()=>setWorkspaceView('panel'));
  $('#workspace-tab-chat').addEventListener('click',()=>setWorkspaceView('chat'));
  document.addEventListener('jobcompass:workspace',event=>setWorkspaceView(event.detail.view));
  $('#analytics-chat-clear').addEventListener('click',()=>{if(busy)return;$('#analytics-chat-messages').innerHTML=welcomeHTML;lastContext=null;$('#analytics-execution').hidden=true;$('#analytics-command').value='';$('#chat-unread').hidden=true;$('#analytics-chat-context').textContent='新对话 · 使用当前选择的数据集';bindPromptExamples();});
  initialize();
})();
