
const PHASES=["Setup","Portao de viabilidade/coleta","Estruturacao/extrator","Modelo","Produto/dashboard/API/deploy","Seguranca e custo"];
function showError(msg){
  const b=document.getElementById('errorBanner');
  b.style.display='block';
  b.textContent=msg;
}
function mk(tag, cls){const e=document.createElement(tag); if(cls) e.className=cls; return e;}
function txt(parent, value){ parent.textContent = (value===null||value===undefined)?'':String(value); return parent; }
function append(parent, child){ parent.appendChild(child); return parent; }

async function load(){
  let d=null;
  try{
    const r=await fetch('/data.json',{cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    d=await r.json();
  }catch(e){
    showError('data.json invalido ou inacessivel: '+e.message);
    return;
  }
  const banner=document.getElementById('errorBanner');
  banner.style.display='none';
  if(d && (d.error || d.checklist_error)){
    showError('Erro: '+(d.error||d.checklist_error));
  }
  render(d||{});
}
function render(d){
  const op = (typeof d.overall_percent === 'number' && isFinite(d.overall_percent)) ? d.overall_percent : null;
  document.getElementById('overallNum').textContent = (op===null?'--':Math.round(op)+'%');
  document.getElementById('overallBar').style.width = (op===null?0:op)+'%';
  const sc=d.checklist?.progress?.state_counts||d.checklist?.progress?.counts||{};
  document.getElementById('overallCounts').textContent='Feito: '+(sc.Feito||0)+' · Em revisao: '+(sc['Em revisao']||0)+' · Em andamento: '+(sc['Em andamento']||0)+' · Pendente: '+(sc.Pendente||0)+' · Bloqueado: '+(sc.Bloqueado||0);
  document.getElementById('overallMeta').textContent='Itens: '+(d.checklist?.progress?.n_items||0)+' | peso: '+((d.checklist?.progress?.total_weight||0).toFixed?((d.checklist.progress.total_weight||0).toFixed(1)):(d.checklist?.progress?.total_weight||0));
  // tests
  const t=d.tests||{};
  const lastCi=d.tests?.last_ci_main||t.last_ci_main||null;
  const passed=(typeof t.passed==='number')?t.passed:(t.ci?.passed);
  const testsNumEl=document.getElementById('testsNum');
  if(lastCi && lastCi.conclusion && lastCi.conclusion!=='success'){
    testsNumEl.textContent='FAIL';
    testsNumEl.style.color='var(--block)';
  } else {
    testsNumEl.style.color='';
    testsNumEl.textContent=(passed===undefined||passed===null?'--':passed);
  }
  const detail=document.getElementById('testsDetail');
  detail.textContent='';
  const ci=d.tests?.last_ci_main||t.last_ci_main||null;
  if(ci){
    const line=mk('div'); line.textContent='ultimo CI main: '+(ci.conclusion||ci.status||'--')+' · '+(ci.name||'')+' · '+(ci.updatedAt||'');
    detail.appendChild(line);
  }
  if(t.error){ const e=mk('div'); e.textContent=t.error; detail.appendChild(e); }
  // budget
  const b=d.budget||{};
  document.getElementById('budgetNum').textContent='R$ '+((b.spent_brl||0).toFixed? (b.spent_brl||0).toFixed(2): (b.spent_brl||0));
  const bp=(typeof b.percent==='number' && isFinite(b.percent))? b.percent : 0;
  document.getElementById('budgetBar').style.width=Math.min(100,bp)+'%';
  document.getElementById('budgetDetail').textContent='teto R$ '+((b.cap_brl||100).toFixed? (b.cap_brl||100).toFixed(2): (b.cap_brl||100))+' ('+bp.toFixed(1)+'%)';
  // phases
  const ph=d.phases||{};
  const phasesDiv=document.getElementById('phases');
  phasesDiv.textContent='';
  for(const p of PHASES){
    const val=ph[p];
    const num=(typeof val==='number' && isFinite(val))?(val<=1?val*100:val):0;
    const wrap=mk('div','phase');
    const label=mk('div','label');
    const left=mk('span'); left.textContent=p;
    const right=mk('span'); right.textContent=Math.round(num)+'%';
    append(label,left); append(label,right);
    const bar=mk('div','bar'); const fill=mk('div'); fill.style.width=num+'%'; bar.appendChild(fill);
    append(wrap,label); append(wrap,bar);
    phasesDiv.appendChild(wrap);
  }
  // items
  const itemsDiv=document.getElementById('items');
  itemsDiv.textContent='';
  const items = (d.checklist && Array.isArray(d.checklist.items)) ? d.checklist.items : [];
  if(d.checklist_error){
    const e=mk('div'); e.style.color='var(--err)'; e.textContent='Checklist invalido: '+d.checklist_error; itemsDiv.appendChild(e);
  }
  for(const it of items){
    const st=it.estado||'Pendente';
    const row=mk('div','item');
    const c1=mk('div'); c1.style.fontWeight='700'; c1.textContent=it.id||'';
    const c2=mk('div');
    const title=mk('div'); title.textContent=it.title||'';
    const meta=mk('div'); meta.style.fontSize='13px'; meta.style.color='var(--muted)'; meta.textContent=(it.fase||'')+' · peso '+(it.peso??'');
    append(c2,title); append(c2,meta);
    const c3=mk('div'); const badge=mk('span','badge b-'+String(st).replace(/ /g,'-')); badge.textContent=st; c3.appendChild(badge);
    const c4=mk('div'); c4.style.fontSize='14px'; c4.textContent=it.evidencia||'';
    const c5=mk('div'); c5.style.fontSize='14px'; c5.style.color='var(--muted)'; c5.textContent=it.updated_at||'';
    [c1,c2,c3,c4,c5].forEach(c=>row.appendChild(c));
    itemsDiv.appendChild(row);
  }
  if(!items.length && !d.checklist_error){ const e=mk('div'); e.style.color='var(--muted)'; e.textContent='sem itens'; itemsDiv.appendChild(e); }
  // PRs
  function renderPr(container, list){
    container.textContent='';
    const arr=Array.isArray(list)?list:[];
    if(!arr.length){ const e=mk('div'); e.style.color='var(--muted)'; e.textContent='nehum'; container.appendChild(e); return;}
    for(const p of arr){
      const wrap=mk('div','pr');
      const title=mk('div'); title.style.fontWeight='700'; title.textContent='#'+(p.number||'')+' '+(p.title||'');
      const ci=p.ci||'unknown';
      const cross = p.awaits_cross_test ? ' · aguarda teste cruzado' : '';
      const sub=mk('div'); sub.style.fontSize='14px'; sub.style.color='var(--muted)';
      const ciSpan=mk('span','ci '+ci); ciSpan.textContent=ci;
      sub.textContent='CI: '; sub.appendChild(ciSpan); txt(sub, ' '+ (p.state||'') + cross);
      // rebuild properly:
      sub.textContent='';
      const pref=mk('span'); pref.textContent='CI: '; sub.appendChild(pref);
      sub.appendChild(ciSpan);
      const tail=mk('span'); tail.textContent=' · '+(p.state||'')+cross; sub.appendChild(tail);
      append(wrap,title); append(wrap,sub);
      container.appendChild(wrap);
    }
  }
  renderPr(document.getElementById('prsOpen'), d.prs?.open||[]);
  renderPr(document.getElementById('prsMerged'), d.prs?.merged||[]);
  // agents
  const agentsDiv=document.getElementById('agents');
  agentsDiv.textContent='';
  const agents=(d.agents && Array.isArray(d.agents.agents))?d.agents.agents:[];
  if(d.agents && d.agents.available===false){ const e=mk('div'); e.style.color='var(--muted)'; e.textContent=d.agents.error||'maestri indisponivel'; agentsDiv.appendChild(e);}
  const ul=mk('ul');
  for(const a of agents){
    const ct=a.current_task || (Array.isArray(a.tasks)?a.tasks.join(', '):'');
    const li=mk('li');
    const b=mk('b'); b.textContent=a.name||''; li.appendChild(b);
    const role=a.role?' ('+a.role+')':''; const t=ct?' — '+ct:'';
    li.appendChild(document.createTextNode(role+t));
    ul.appendChild(li);
  }
  agentsDiv.appendChild(ul);
  // tasks
  const tasksDiv=document.getElementById('tasks');
  tasksDiv.textContent='';
  const table=mk('table');
  const thead=mk('thead'); const hr=mk('tr');
  ['ID','Tarefa','Responsavel','Status'].forEach(h=>{const th=mk('th'); th.textContent=h; hr.appendChild(th);});
  thead.appendChild(hr); table.appendChild(thead);
  const tbody=mk('tbody');
  const tasks=Array.isArray(d.tasks)?d.tasks:[];
  for(const t of tasks){
    const tr=mk('tr');
    [t.id,t.tarefa,t.responsavel,t.status].forEach(v=>{const td=mk('td'); td.textContent=(v===null||v===undefined)?'':v; tr.appendChild(td);});
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  tasksDiv.appendChild(table);
  // status
  const blocksDiv=document.getElementById('blocks'); blocksDiv.textContent='';
  const blocks=Array.isArray(d.status?.blocks)?d.status.blocks:[];
  if(!blocks.length){ const li=mk('li'); li.style.color='var(--muted)'; li.textContent='n/a'; blocksDiv.appendChild(li);}
  for(const x of blocks){ const li=mk('li'); li.textContent=x; blocksDiv.appendChild(li);}
  const nextsDiv=document.getElementById('nexts'); nextsDiv.textContent='';
  const nexts=Array.isArray(d.status?.next_steps)?d.status.next_steps:[];
  if(!nexts.length){ const li=mk('li'); li.style.color='var(--muted)'; li.textContent='n/a'; nextsDiv.appendChild(li);}
  for(const x of nexts){ const li=mk('li'); li.textContent=x; nextsDiv.appendChild(li);}
  // last ci
  const lastCiDiv=document.getElementById('lastCi'); lastCiDiv.textContent='';
  const lastCi = (d.tests&&d.tests.last_ci_main) ? d.tests.last_ci_main : null;
  if(lastCi){
    const a=mk('div'); a.style.fontWeight='700'; a.textContent=lastCi.conclusion||lastCi.status||'--';
    const b=mk('div'); b.style.color='var(--muted)'; b.style.fontSize='15px'; b.textContent=(lastCi.name||'')+' · '+(lastCi.updatedAt||'');
    lastCiDiv.appendChild(a); lastCiDiv.appendChild(b);
  } else {
    lastCiDiv.textContent='indisponivel';
  }
}
load();
setInterval(load,5000);
