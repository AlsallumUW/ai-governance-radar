(function(){'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
/* chart/table toggles */
$$('[data-toggle-table]').forEach(b=>b.addEventListener('click',()=>{const f=document.getElementById(b.dataset.toggleTable),t=$('.fig-table',f),c=$('.fig-chart',f),open=t.hidden;t.hidden=!open;c.hidden=open;b.textContent=open?'Show as chart':'Show as table';b.setAttribute('aria-expanded',String(open))}));
/* tooltip for chart marks */
const tip=document.createElement('div');tip.className='tip';tip.hidden=true;tip.setAttribute('role','status');document.body.appendChild(tip);
document.addEventListener('pointerover',e=>{const m=e.target.closest&&e.target.closest('[data-tip]');if(!m){tip.hidden=true;return}tip.textContent=m.dataset.tip;tip.hidden=false});
document.addEventListener('pointermove',e=>{if(tip.hidden)return;const w=tip.offsetWidth,h=tip.offsetHeight;tip.style.left=Math.max(8,Math.min(innerWidth-w-8,e.clientX+12))+'px';tip.style.top=Math.max(8,e.clientY-h-12)+'px'});
document.addEventListener('pointerout',e=>{if(!e.relatedTarget||!e.relatedTarget.closest||!e.relatedTarget.closest('[data-tip]'))tip.hidden=true});
/* per-chart CSV: exactly the rows of that chart's table */
const cell=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
$$('[data-csv]').forEach(b=>b.addEventListener('click',()=>{const f=document.getElementById(b.dataset.csv),d=JSON.parse($('.csv-data',f).textContent);
  const text='﻿'+[d.head.map(cell).join(','),...d.rows.map(r=>r.map(cell).join(','))].join('\r\n');
  const a=document.createElement('a'),u=URL.createObjectURL(new Blob([text],{type:'text/csv'}));a.href=u;a.download=d.file;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500)}));
addEventListener('beforeprint',()=>{$$('.fig-table').forEach(t=>t.hidden=true);$$('.fig-chart').forEach(c=>c.hidden=false)});
})();
