/* AI Governance Radar · Global and regional documents: filter, sort and CSV of the documents list; filters live in the URL. */
(function(){'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const list=$('#gdList');if(!list)return;
const AR=document.documentElement.lang==='ar',tr=s=>(window.I18N&&window.I18N.t)?window.I18N.t(s):s;
const rows=$$('.gd-row',list),ctl={};$$('[data-f]').forEach(el=>ctl[el.dataset.f]=el);
const KEYS=['org','type','cat','from','to','q','sort'],status=$('#gdStatus'),none=$('#gdNone'),csvB=$('#gdCsv');
const CSV=JSON.parse($('#gd-csv').textContent);
let shown=rows.slice();
const valid=(k,v)=>k==='q'?v:(ctl[k]&&Array.from(ctl[k].options).some(o=>o.value===v)?v:'');
function readURL(){const q=new URLSearchParams(location.search);KEYS.forEach(k=>{ctl[k].value=valid(k,q.get(k)||'')});if(!ctl.sort.value)ctl.sort.value='newest'}
function writeURL(){const q=new URLSearchParams();KEYS.forEach(k=>{const v=ctl[k].value.trim();if(v&&!(k==='sort'&&v==='newest'))q.set(k,v)});
  const s=q.toString();history.replaceState(null,'',location.pathname+(s?'?'+s:'')+location.hash)}
const coll=new Intl.Collator(AR?'ar':'en');
function apply(){
  const org=ctl.org.value,type=ctl.type.value,cat=ctl.cat.value,q=ctl.q.value.trim().toLowerCase(),mode=ctl.sort.value;
  let from=+ctl.from.value||0,to=+ctl.to.value||0;if(from&&to&&to<from)[from,to]=[to,from];
  shown=rows.filter(r=>{const d=r.dataset,y=+d.year||0;
    if(org&&d.org!==org)return false;if(type&&d.status!==type)return false;if(cat&&!d.cats.split(' ').includes(cat))return false;
    if((from||to)&&(!y||(from&&y<from)||(to&&y>to)))return false;
    if(q&&!q.split(/\s+/).every(w=>d.text.includes(w)))return false;return true});
  /* undated documents sort last; ties keep the build order (newest first) */
  const newest=(a,b)=>(!a.dataset.date)-(!b.dataset.date)||b.dataset.date.localeCompare(a.dataset.date)||a.dataset.n-b.dataset.n;
  const cmp={newest,oldest:(a,b)=>(!a.dataset.date)-(!b.dataset.date)||a.dataset.date.localeCompare(b.dataset.date)||b.dataset.n-a.dataset.n,
    org:(a,b)=>coll.compare(a.dataset.oname,b.dataset.oname)||newest(a,b),weight:(a,b)=>a.dataset.weight-b.dataset.weight||newest(a,b)}[mode]||newest;
  shown.sort(cmp);rows.forEach(r=>r.hidden=true);shown.forEach(r=>{r.hidden=false;list.appendChild(r)});
  status.textContent=shown.length===rows.length?tr(`${rows.length} documents`):tr(`${shown.length} of ${rows.length} documents shown`);
  none.hidden=shown.length>0;csvB.textContent=tr(`Download CSV (${shown.length})`);csvB.disabled=!shown.length;writeURL()}
KEYS.forEach(k=>ctl[k].addEventListener(k==='q'?'input':'change',apply));
$('#gdClear').addEventListener('click',()=>{KEYS.forEach(k=>ctl[k].value='');ctl.sort.value='newest';apply()});
/* CSV: exactly the rows shown, in their order (UTF-8 with BOM) */
const cell=v=>{v=v==null?'':String(v);return/[",\r\n]/.test(v)||/^\s|\s$/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
csvB.addEventListener('click',()=>{const text='﻿'+[CSV.head,...shown.map(r=>CSV.rows[r.id])].map(r=>r.map(cell).join(',')).join('\r\n')+'\r\n';
  const a=document.createElement('a'),u=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));a.href=u;a.download=CSV.file;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500)});
readURL();apply();
window.RADAR_GLOBAL={count:()=>shown.length,ids:()=>shown.map(r=>r.id),csv:()=>'﻿'+[CSV.head,...shown.map(r=>CSV.rows[r.id])].map(r=>r.map(cell).join(',')).join('\r\n')+'\r\n'};
})();
