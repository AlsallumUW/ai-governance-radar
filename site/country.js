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
/* pipeline: move actions whose date has passed out of "upcoming" (the page itself is static, built on data-asof) */
(function(){const f=document.getElementById('fig-pipeline');if(!f)return;const up=f.querySelector('[data-upcoming]');if(!up)return;const now=new Date(),today=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;const passed=f.querySelector('.pl-passed'),pl=passed.querySelector('ol');let moved=0;Array.from(up.children).forEach(li=>{if((li.dataset.date||'')<today){pl.appendChild(li);moved++}});if(moved){passed.hidden=false;const a=f.querySelector('.asof');if(a)a.textContent=a.textContent+' · checked '+today}if(!up.children.length){const n=f.querySelector('.pl-none');if(n)n.hidden=false}})();
/* export: the profile bundle sits next to the page (profile.json) and is fetched only when asked for */
const jid=document.body.dataset.jid,stamp=document.body.dataset.build||'';
const F=['id','jurisdiction_id','layer','government_level','subnational_unit','official_title','english_title','categories','legal_status','lifecycle','issuing_authority','publisher_name','publication_date','effective_date','last_amended_date','current_status','summary','language','source_url','official_pdf_url','verification_level','verification_date','metadata_gaps'];
const cell=v=>'"'+String(Array.isArray(v)?v.join(' | '):v??'').replace(/"/g,'""')+'"';
function dl(text,name,type){const a=document.createElement('a'),u=URL.createObjectURL(new Blob([text],{type}));a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500)}
let bundle=null;const getBundle=()=>bundle?Promise.resolve(bundle):fetch('profile.json').then(r=>{if(!r.ok)throw new Error(r.status);return r.json()}).then(b=>bundle=b);
$$('[data-export]').forEach(b=>b.addEventListener('click',()=>{b.disabled=true;getBundle().then(B=>{const base=`AI-Governance-Radar-${jid}-${stamp}`;if(b.dataset.export==='json')dl(JSON.stringify(B,null,2),base+'.json','application/json');else{const rows=[...B.instruments.map(i=>({...i,layer:i.jurisdiction_id===jid?'national':'regional'})),...(B.regional_instruments_applying_here||[]).map(i=>({...i,jurisdiction_id:i.regional_jurisdiction_id,layer:'regional ('+i.regional_jurisdiction_id+')'}))];dl('﻿'+[F.map(cell).join(','),...rows.map(r=>F.map(k=>cell(r[k])).join(','))].join('\r\n'),base+'.csv','text/csv')}}).catch(()=>alert('The download could not be prepared. Please try again.')).finally(()=>{b.disabled=false})}));

/* ---------------------------------------------------------------- scroll design (UX phase 2b) */
const bands=$$('.pb-media').filter(m=>m.firstElementChild&&m.firstElementChild.tagName==='IMG');
const root=document.documentElement,bar=$('.topnav'),hero=$('#top'),media=$('.hero-media'),railEl=$('.rail'),railIn=$('.rail-in');
const reduce=matchMedia('(prefers-reduced-motion: reduce)');
const setSbw=()=>root.style.setProperty('--sbw',(innerWidth-root.clientWidth)+'px');setSbw();addEventListener('resize',setSbw);
/* sections the rail, top bar and menu link to */
const links=$$('.rail-nav a,.topnav .toc a,.secmenu nav a');
const secs=[...new Set(links.map(a=>a.getAttribute('href').slice(1)))].map(id=>document.getElementById(id)).filter(Boolean);
const menu=$('.secmenu');if(menu)$$('a',menu).forEach(a=>a.addEventListener('click',()=>{menu.open=false}));
/* the hero becomes the slim sticky bar once it has scrolled away */
if(hero&&bar&&'IntersectionObserver' in window){new IntersectionObserver(([en])=>{bar.classList.toggle('stuck',!en.isIntersecting)},{rootMargin:`-${bar.offsetHeight}px 0px 0px 0px`}).observe(hero)}
/* charts backdrop reveal (wide screens): --rv goes 0 to 1 as the charts heading rises from near the bottom of the screen to ~35% from the top */
const rvSec=$('.charts-sec.has-bg'),rvH=rvSec&&$('.charts-h',rvSec);
if(rvH){const hint=document.createElement('div');hint.className='rv-hint';hint.setAttribute('aria-hidden','true');hint.textContent=rvH.textContent;rvSec.appendChild(hint)}
let ticking=false,current=null;
function frame(){ticking=false;const y=scrollY,vh=innerHeight,max=Math.max(1,root.scrollHeight-vh),p=Math.min(1,Math.max(0,y/max));
  root.style.setProperty('--p',p.toFixed(4));
  if(rvH){if(innerWidth<760)rvSec.style.removeProperty('--rv');else rvSec.style.setProperty('--rv',Math.min(1,Math.max(0,(vh*.95-rvH.getBoundingClientRect().top)/(vh*.6))).toFixed(3))}
  if(media&&!reduce.matches){const h=hero.offsetHeight;if(y<h)media.style.transform=`translate3d(0,${(y*.3).toFixed(1)}px,0)`}
  const line=(bar?bar.offsetHeight:0)+vh*.25;let cur=secs[0]||null;for(const s of secs){if(s.getBoundingClientRect().top<=line)cur=s}
  if(y+vh>=root.scrollHeight-4&&secs.length)cur=secs[secs.length-1];
  if(cur!==current){current=cur;links.forEach(a=>{const on=cur&&a.getAttribute('href')==='#'+cur.id;if(on)a.setAttribute('aria-current','true');else a.removeAttribute('aria-current')})}
  if(railIn&&railEl.offsetParent){const r=railIn.getBoundingClientRect(),over=el=>{const q=el.getBoundingClientRect();return q.top<r.bottom&&q.bottom>r.top};
    railEl.classList.toggle('dim',$$('.photo-break,.closing').some(over));railEl.classList.toggle('ondark',$$('.charts-sec.has-bg .cs-bg').some(b=>b.offsetWidth>innerWidth*.6&&over(b)))}
  /* band photo: gentle parallax while it crosses the viewport */
  if(!reduce.matches)bands.forEach(b=>{const q=b.getBoundingClientRect();if(q.bottom<0||q.top>vh)return;const t=(q.top+q.height/2-vh/2)/(vh/2+q.height/2);b.firstElementChild.style.transform=`translate3d(0,${(t*q.height*.06).toFixed(1)}px,0)`})}
addEventListener('scroll',()=>{if(!ticking){ticking=true;requestAnimationFrame(frame)}},{passive:true});addEventListener('resize',frame);frame();
/* sections fade in once as they enter; charts grow from zero; header counts count up */
function motion(){if(reduce.matches||!('IntersectionObserver' in window))return;
  const els=$$('.intro,.content>section.block,.lede-grid>.block,.ov-grid>.block,.ov-photo,.charts-h,.fig,.photo-break,.closing-in').filter(el=>!(el===rvH&&innerWidth>=760));
  root.classList.add('js-motion');els.forEach(el=>el.classList.add('rv'));
  const io=new IntersectionObserver(es=>es.forEach(en=>{if(en.isIntersecting){en.target.classList.add('in');io.unobserve(en.target)}}),{rootMargin:'0px 0px -6% 0px',threshold:0});
  els.forEach(el=>io.observe(el));
  $$('.hero dd[data-count]').forEach(dd=>{const v=+dd.dataset.count;if(!(v>1))return;const t0=performance.now(),dur=Math.min(900,400+v*4);dd.textContent='0';
    const step=t=>{const k=Math.min(1,(t-t0)/dur),e=1-Math.pow(1-k,3);dd.textContent=String(Math.round(v*e));if(k<1)requestAnimationFrame(step)};requestAnimationFrame(step)})}
motion();
reduce.addEventListener&&reduce.addEventListener('change',()=>{if(reduce.matches){root.classList.remove('js-motion');if(media)media.style.transform='';bands.forEach(b=>b.firstElementChild.style.transform='');$$('.hero dd[data-count]').forEach(dd=>dd.textContent=dd.dataset.count)}});
addEventListener('beforeprint',()=>{$$('.rv').forEach(el=>el.classList.add('in'));$$('.hero dd[data-count]').forEach(dd=>dd.textContent=dd.dataset.count);if(media)media.style.transform=''});
})();
/* header counts: (i) button opens the definitions; Escape or a click elsewhere closes them */
(function(){const b=document.querySelector('.info-btn'),p=b&&document.getElementById(b.getAttribute('aria-controls'));if(!p)return;
const set=o=>{p.hidden=!o;b.setAttribute('aria-expanded',String(o))};
b.addEventListener('click',e=>{e.stopPropagation();set(p.hidden)});
document.addEventListener('click',e=>{if(!p.hidden&&!p.contains(e.target))set(false)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!p.hidden){set(false);b.focus()}})})();
