/* AI Governance Radar · the world maps on the Analysis, Timeline, Global and Search pages (built as SVG by scripts/visuals.py).
   Shared: hover/focus info card, raised outline, keyboard focus (one tab stop; arrow keys move between countries by name),
   tap-to-preview on touch screens. Per page: Analysis scope switch, Timeline year slider and Play, Search shading (search.js
   calls RadarMap.shade with the counts of every result set; a selected country is announced with a "wm:pick" event). */
(function(){'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const RM=matchMedia('(prefers-reduced-motion: reduce)');
const fill=(t,o)=>t.replace(/\{(\w+)\}/g,(m,k)=>o[k]!=null?o[k]:m);
const setBin=(a,b)=>{a.setAttribute('class','m'+b)};

function init(fig){
  const svg=$('svg.wm',fig),stage=$('.wm-stage',fig),card=$('.wm-card',fig),kind=fig.dataset.map;
  const links=$$('a[data-iso3]',svg),hqs=$$('.hq',svg),all=links.concat(hqs);
  /* the native <title> tooltips would double the card: keep their text as the accessible name instead */
  all.forEach(el=>{const t=$('title',el);if(t){el.setAttribute('aria-label',t.textContent);t.remove()}});
  let cur=null,pinned=false,lastPointer='mouse';
  /* raise a country above its neighbours (moving a focused element would drop its focus: keyboard moves raise before focusing) */
  const raise=el=>{if(el.tagName.toLowerCase()==='a'&&el!==document.activeElement&&el.parentNode.lastElementChild!==el)el.parentNode.appendChild(el)};
  const show=(el,x,y)=>{
    if(cur&&cur!==el)cur.classList.remove('on');cur=el;el.classList.add('on');
    raise(el);
    const d=el.dataset;let h=`<b>${esc(d.name)}</b>`+(d.i?`<span>${esc(d.i)}</span>`:'')+(d.l?`<span class="wm-l">${esc(d.l)}</span>`:'');
    if(pinned&&el.tagName.toLowerCase()==='a')h+=kind==='search'?`<span class="wm-l">${esc(fig.dataset.tPick||'')}</span>`:`<a href="${esc(el.getAttribute('href'))}">${esc(fig.dataset.tOpen||'Open the country page')}</a>`;
    card.innerHTML=h;card.hidden=false;card.classList.toggle('pin',pinned);place(x,y)};
  const place=(x,y)=>{const sw=stage.clientWidth,cw=card.offsetWidth,ch=card.offsetHeight;
    let l=x+14,t=y-ch-12;if(l+cw>sw-4)l=x-cw-14;if(l<4)l=Math.max(4,Math.min(sw-cw-4,x-cw/2));if(t<4)t=y+18;
    card.style.left=l+'px';card.style.top=t+'px'};
  const hide=()=>{if(cur)cur.classList.remove('on');cur=null;pinned=false;card.hidden=true};
  const at=ev=>{const r=stage.getBoundingClientRect();return[ev.clientX-r.left,ev.clientY-r.top]};
  const target=ev=>ev.target.closest&&ev.target.closest('a[data-iso3],.hq');
  svg.addEventListener('pointerdown',ev=>{lastPointer=ev.pointerType});
  svg.addEventListener('pointerover',ev=>{if(ev.pointerType==='touch')return;const el=target(ev);if(el&&el!==cur){pinned=false;show(el,...at(ev))}});
  svg.addEventListener('pointermove',ev=>{if(ev.pointerType==='touch'||!cur||pinned)return;place(...at(ev))});
  svg.addEventListener('pointerleave',ev=>{if(ev.pointerType!=='touch'&&!pinned)hide()});
  svg.addEventListener('click',ev=>{const el=target(ev);if(!el){if(pinned)hide();return}
    /* touch: the first tap shows the card (with a link), a second tap on the same country follows it */
    if(lastPointer==='touch'&&!(pinned&&cur===el)){ev.preventDefault();pinned=true;show(el,...at(ev));return}
    if(kind==='search'&&el.dataset.iso3){ev.preventDefault();hide();fig.dispatchEvent(new CustomEvent('wm:pick',{detail:{iso3:el.dataset.iso3,name:el.dataset.name}}))}});
  document.addEventListener('click',ev=>{if(pinned&&!fig.contains(ev.target))hide()});
  /* keyboard: one tab stop; arrows move through the countries in name order; Enter opens (or, on Search, selects) */
  const order=links.slice().sort((a,b)=>a.dataset.name.localeCompare(b.dataset.name,document.documentElement.lang));
  if(order.length)order[0].setAttribute('tabindex','0');
  const centre=el=>{const r=el.getBoundingClientRect(),s=stage.getBoundingClientRect();return[r.left-s.left+r.width/2,r.top-s.top+r.height/2]};
  svg.addEventListener('focusin',ev=>{const el=target(ev);if(el){pinned=false;show(el,...centre(el))}});
  svg.addEventListener('focusout',ev=>{if(!svg.contains(ev.relatedTarget))hide()});
  svg.addEventListener('keydown',ev=>{const el=target(ev);if(!el||!el.dataset.iso3)return;const k=ev.key;
    if(k==='Escape'){hide();return}
    if(!['ArrowRight','ArrowLeft','ArrowDown','ArrowUp','Home','End'].includes(k))return;
    ev.preventDefault();const n=order.indexOf(el),fw=k==='ArrowRight'||k==='ArrowDown';
    const nx=k==='Home'?order[0]:k==='End'?order[order.length-1]:order[(n+(fw?1:-1)+order.length)%order.length];
    el.setAttribute('tabindex','-1');nx.setAttribute('tabindex','0');raise(nx);nx.focus()});
  if(kind==='search')svg.addEventListener('keydown',ev=>{const el=target(ev);if(el&&el.dataset.iso3&&(ev.key==='Enter'||ev.key===' ')){ev.preventDefault();
    fig.dispatchEvent(new CustomEvent('wm:pick',{detail:{iso3:el.dataset.iso3,name:el.dataset.name}}))}});
  const refresh=()=>{if(cur&&!card.hidden)show(cur,parseFloat(card.style.left)||0,(parseFloat(card.style.top)||0)+card.offsetHeight+12)};
  return{fig,links,refresh};
}

/* ------------------------------------------------------------ Analysis: the scope switch re-shades the map */
function analysis(m){const lh=$('.wm-lh',m.fig),t0=lh&&lh.textContent;
  const use=all=>{m.links.forEach(a=>{const d=a.dataset;setBin(a,all?d.bAll:d.b);a.dataset.i=all?d.iAll:(d.i0??d.i)});
    if(lh&&lh.dataset.alt)lh.textContent=all?lh.dataset.alt:t0;m.refresh()};
  m.links.forEach(a=>{a.dataset.i0=a.dataset.i});
  document.addEventListener('change',ev=>{if(ev.target.matches&&ev.target.matches('[data-scope-toggle]'))use(ev.target.checked)});
  const t=$('[data-scope-toggle]');if(t&&t.checked)use(true)}

/* ------------------------------------------------------------ Timeline: year slider and Play */
function timeline(m){const f=m.fig,range=$('input[type=range]',f),out=$('.wm-count',f),btn=$('.wm-pb',f);if(!range)return;
  const min=+range.min,max=+range.max;let timer=null;
  const paint=Y=>{let n=0;m.links.forEach(a=>{const y=+a.dataset.y||0,on=y&&y<=Y;if(on)n++;setBin(a,on?a.dataset.b:0)});
    range.value=Y;range.setAttribute('aria-valuetext',String(Y));out.textContent=fill(n===1?f.dataset.tOne:f.dataset.tMany,{n,y:Y})};
  const stop=()=>{clearInterval(timer);timer=null;btn.setAttribute('aria-pressed','false');$('span',btn).textContent=btn.dataset.play};
  const play=()=>{let Y=+range.value>=max?min:+range.value;paint(Y);btn.setAttribute('aria-pressed','true');$('span',btn).textContent=btn.dataset.pause;
    timer=setInterval(()=>{Y++;if(Y>max){stop();return}paint(Y)},RM.matches?1100:650)};
  btn.addEventListener('click',()=>timer?stop():play());
  range.addEventListener('input',()=>{if(timer)stop();paint(+range.value)});
  /* once, when the map first comes into view: play the years through (not with reduced motion) */
  if(!RM.matches&&'IntersectionObserver' in window){const io=new IntersectionObserver(es=>{if(es.some(e=>e.isIntersecting)){io.disconnect();setTimeout(()=>{if(!timer&&+range.value===max)play()},400)}},{threshold:.6});io.observe($('.wm-stage',f))}}

/* ------------------------------------------------------------ Search: quantile bins of the counts, recomputed for each result set */
function qbins(vals,k=6){const v=vals.filter(x=>x>0).sort((a,b)=>a-b);if(!v.length)return[];
  const u=[...new Set(v)];if(u.length<=k)return u;const out=[];
  for(let i=1;i<=k;i++){const q=v[Math.min(v.length-1,Math.ceil(i*v.length/k)-1)];if(!out.length||q>out[out.length-1])out.push(q)}
  if(out[out.length-1]!==v[v.length-1])out.push(v[v.length-1]);return out}
const spread=(k,m)=>m===1?4:Math.round(1+(k-1)*5/(m-1));
function shade(fig,counts){const m=fig&&fig._wm;if(!m)return;
  const ups=qbins(m.links.map(a=>counts[a.dataset.iso3]||0)),d=fig.dataset;
  const bin=n=>{if(!n)return 0;for(let k=0;k<ups.length;k++)if(n<=ups[k])return spread(k+1,ups.length);return 6};
  m.links.forEach(a=>{const n=counts[a.dataset.iso3]||0;setBin(a,bin(n));a.dataset.i=n?fill(n===1?d.tOne:d.tMany,{n:n.toLocaleString('en')}):d.tNone});
  const keys=$('.wm-keys',fig);if(keys){let h=`<span class="k0"><i class="wk m0"></i><bdi>${esc(d.tLnone)}</bdi></span>`;let lo=1;
    ups.forEach((u,k)=>{h+=`<span><i class="wk m${spread(k+1,ups.length)}"></i><bdi dir="ltr">${lo===u?u:lo+'–'+u}</bdi></span>`;lo=u+1});keys.innerHTML=h}
  m.refresh()}

const maps=$$('figure.wmap');
maps.forEach(f=>{const m=init(f);f._wm=m;if(f.dataset.map==='analysis')analysis(m);if(f.dataset.map==='timeline')timeline(m)});
window.RadarMap={shade};
})();
