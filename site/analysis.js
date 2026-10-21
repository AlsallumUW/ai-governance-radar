(function(){'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
/* chart/table toggles (a figure with scope variants switches every variant, so the choice survives the scope toggle) */
$$('[data-toggle-table]').forEach(b=>b.addEventListener('click',()=>{const f=document.getElementById(b.dataset.toggleTable),open=b.getAttribute('aria-expanded')!=='true';$$('.fig-table',f).forEach(t=>t.hidden=!open);$$('.fig-chart',f).forEach(c=>c.hidden=open);b.textContent=open?'Show as chart':'Show as table';b.setAttribute('aria-expanded',String(open))}));
/* scope toggle: national-level only (default) or including state/provincial and local; every toggle on the page moves together */
const scopes=$$('[data-scope-toggle]');scopes.forEach(x=>x.addEventListener('change',()=>{const all=x.checked;scopes.forEach(y=>y.checked=all);$$('.variant').forEach(v=>v.hidden=(v.dataset.scope==='all')!==all)}));
/* tooltip for chart marks */
const tip=document.createElement('div');tip.className='tip';tip.hidden=true;tip.setAttribute('role','status');document.body.appendChild(tip);
document.addEventListener('pointerover',e=>{const m=e.target.closest&&e.target.closest('[data-tip]');if(!m){tip.hidden=true;return}tip.textContent=m.dataset.tip;tip.hidden=false});
document.addEventListener('pointermove',e=>{if(tip.hidden)return;const w=tip.offsetWidth,h=tip.offsetHeight;tip.style.left=Math.max(8,Math.min(innerWidth-w-8,e.clientX+12))+'px';tip.style.top=Math.max(8,e.clientY-h-12)+'px'});
document.addEventListener('pointerout',e=>{if(!e.relatedTarget||!e.relatedTarget.closest||!e.relatedTarget.closest('[data-tip]'))tip.hidden=true});
/* per-chart CSV: exactly the rows of that chart's table */
const cell=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
$$('[data-csv]').forEach(b=>b.addEventListener('click',()=>{const f=document.getElementById(b.dataset.csv),v=$('.variant:not([hidden])',f)||f,d=JSON.parse($('.csv-data',v).textContent);
  const text='﻿'+[d.head.map(cell).join(','),...d.rows.map(r=>r.map(cell).join(','))].join('\r\n');
  const a=document.createElement('a'),u=URL.createObjectURL(new Blob([text],{type:'text/csv'}));a.href=u;a.download=d.file;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500)}));
addEventListener('beforeprint',()=>{$$('.fig-table').forEach(t=>t.hidden=true);$$('.fig-chart').forEach(c=>c.hidden=false)});
})();
/* header counts: (i) button opens the definitions; Escape or a click elsewhere closes them (as on country pages) */
(function(){const b=document.querySelector('.info-btn'),p=b&&document.getElementById(b.getAttribute('aria-controls'));if(!p)return;
const set=o=>{p.hidden=!o;b.setAttribute('aria-expanded',String(o))};
b.addEventListener('click',e=>{e.stopPropagation();set(p.hidden)});
document.addEventListener('click',e=>{if(!p.hidden&&!p.contains(e.target))set(false)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!p.hidden){set(false);b.focus()}})})();
/* country ranking: show the top countries or all of them (every scope variant moves together) */
document.querySelectorAll('[data-rank-more]').forEach(b=>b.addEventListener('click',()=>{const open=b.getAttribute('aria-expanded')!=='true';
  document.querySelectorAll('[data-rank-more]').forEach(x=>{x.setAttribute('aria-expanded',String(open));x.textContent=open?x.dataset.less:x.dataset.more});
  document.querySelectorAll('#fig-rank .rk-more').forEach(li=>li.hidden=!open)}));
