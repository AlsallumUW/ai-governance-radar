(function(){'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
/* back link and methodology links keep the map's filters (query string) */
const q=location.search;if(q){$$('#backToMap,#footMap,[data-keep-query]').forEach(a=>{const u=new URL(a.getAttribute('href'),location.href);new URLSearchParams(q).forEach((v,k)=>{if(!u.searchParams.has(k))u.searchParams.set(k,v)});a.href=u.pathname+u.search+u.hash})}
/* links to other country / body pages carry the same query */
if(q)$$('a[href^="../../country/"],a[href^="../../body/"]').forEach(a=>{if(!a.href.includes('?'))a.href+=q});
/* chart/table toggles */
$$('[data-toggle-table]').forEach(b=>b.addEventListener('click',()=>{const f=document.getElementById(b.dataset.toggleTable),t=$('.fig-table',f),c=$('.fig-chart',f),open=t.hidden;t.hidden=!open;c.hidden=open;b.textContent=open?'Show as chart':'Show as table';b.setAttribute('aria-expanded',String(open))}));
/* tooltip for chart marks and coverage cells */
const tip=document.createElement('div');tip.className='tip';tip.hidden=true;tip.setAttribute('role','status');document.body.appendChild(tip);
document.addEventListener('pointerover',e=>{const m=e.target.closest('[data-tip]');if(!m){tip.hidden=true;return}tip.textContent=m.dataset.tip;tip.hidden=false});
document.addEventListener('pointermove',e=>{if(tip.hidden)return;const w=tip.offsetWidth,h=tip.offsetHeight;tip.style.left=Math.min(innerWidth-w-8,e.clientX+12)+'px';tip.style.top=Math.max(8,e.clientY-h-12)+'px'});
document.addEventListener('pointerout',e=>{if(!e.relatedTarget||!e.relatedTarget.closest||!e.relatedTarget.closest('[data-tip]'))tip.hidden=true});
/* instrument lists: sort + filter */
const CAT={};try{Object.assign(CAT,JSON.parse(document.getElementById('category-names')?.textContent||'{}'))}catch(e){}
$$('.list-block').forEach(sec=>{const list=$('[data-list]',sec),items=$$('.inst',list),st=$('.list-status',sec),sort=$('[data-sort]',sec),ft=$('[data-ftype]',sec),fc=$('[data-fcat]',sec),fq=$('[data-fq]',sec);
  const catName=k=>(fc&&fc.querySelector(`option[value="${k}"]`)?.textContent)||k||'Other';
  function apply(){const mode=sort.value,t=ft.value,c=fc.value,s=(fq.value||'').trim().toLowerCase();let rows=items.filter(i=>(!t||i.dataset.type===t)&&(!c||i.dataset.cats.split(' ').includes(c))&&(!s||i.dataset.text.includes(s)));
    const byDate=(a,b)=>b.dataset.date.localeCompare(a.dataset.date);
    if(mode==='weight')rows.sort((a,b)=>a.dataset.weight-b.dataset.weight||byDate(a,b));else if(mode==='category')rows.sort((a,b)=>catName(a.dataset.cat).localeCompare(catName(b.dataset.cat))||byDate(a,b));else rows.sort(byDate);
    $$('.group-h',list).forEach(h=>h.remove());items.forEach(i=>i.hidden=true);let last=null;
    rows.forEach(i=>{i.hidden=false;if(mode==='category'&&i.dataset.cat!==last){const h=document.createElement('h3');h.className='group-h';h.textContent=catName(i.dataset.cat);list.appendChild(h);last=i.dataset.cat}list.appendChild(i)});
    st.textContent=rows.length===items.length?`${items.length} instruments`:`${rows.length} of ${items.length} instruments shown`}
  [sort,ft,fc].forEach(x=>x.addEventListener('change',apply));fq.addEventListener('input',apply);apply()});
/* print: open collapsed sections and show every instrument */
addEventListener('beforeprint',()=>{$$('details').forEach(d=>{d.dataset.wasOpen=d.open;d.open=true});$$('.inst[hidden]').forEach(i=>{i.dataset.wasHidden='1';i.hidden=false});$$('.fig-table').forEach(t=>t.hidden=true);$$('.fig-chart').forEach(c=>c.hidden=false)});
addEventListener('afterprint',()=>{$$('details').forEach(d=>{d.open=d.dataset.wasOpen==='true'});$$('.inst[data-was-hidden]').forEach(i=>{i.hidden=true;delete i.dataset.wasHidden})});
/* export */
const B=JSON.parse(document.getElementById('profile-data').textContent),jid=B.meta.jurisdiction_id,stamp=B.meta.build_date||'';
const F=['id','jurisdiction_id','layer','government_level','subnational_unit','official_title','english_title','categories','legal_status','lifecycle','issuing_authority','publisher_name','publication_date','effective_date','last_amended_date','current_status','summary','language','source_url','official_pdf_url','verification_level','verification_date','metadata_gaps'];
const cell=v=>'"'+String(Array.isArray(v)?v.join(' | '):v??'').replace(/"/g,'""')+'"';
function dl(text,name,type){const a=document.createElement('a'),u=URL.createObjectURL(new Blob([text],{type}));a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500)}
$$('[data-export]').forEach(b=>b.addEventListener('click',()=>{const base=`AI-Governance-Radar-${jid}-${stamp}`;if(b.dataset.export==='json')dl(JSON.stringify(B,null,2),base+'.json','application/json');else{const rows=[...B.instruments.map(i=>({...i,layer:i.jurisdiction_id===jid?'national':'regional'})),...(B.regional_instruments_applying_here||[]).map(i=>({...i,jurisdiction_id:i.regional_jurisdiction_id,layer:'regional ('+i.regional_jurisdiction_id+')'}))];dl('﻿'+[F.map(cell).join(','),...rows.map(r=>F.map(k=>cell(r[k])).join(','))].join('\r\n'),base+'.csv','text/csv')}}));
})();
