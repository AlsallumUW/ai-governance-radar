/* AI Governance Radar · the world maps on the Analysis, Timeline, Global and Search pages (built as SVG by scripts/visuals.py).
   Shared: hover/focus info card, raised outline, keyboard focus (one tab stop; arrow keys move between countries by name),
   tap-to-preview on touch screens. Per page: Analysis lenses (each recolours the map, with its own legend, card text and
   top five) and the scope switch; Timeline year slider and Play; Global organisation explorer (pick an organisation or a
   country); Search shading (search.js calls RadarMap.shade with the counts of every result set and RadarMap.select with the
   countries picked; the map announces "wm:pick" and "wm:unpick"). Every text comes from the page, in its language. */
(function(){'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const RM=matchMedia('(prefers-reduced-motion: reduce)');
const fill=(t,o)=>t.replace(/\{(\w+)\}/g,(m,k)=>o[k]!=null?o[k]:m);
const setBin=(a,b)=>{a.setAttribute('class','m'+b+(a._sel?' sel':''))};
const X='<svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true"><path d="M2.5 2.5l7 7M9.5 2.5l-7 7"/></svg>';
/* URL state: set or remove some keys, keeping every other parameter (the page's own filters) */
function urlSet(o){const q=new URLSearchParams(location.search);Object.keys(o).forEach(k=>{if(o[k])q.set(k,o[k]);else q.delete(k)});
  const s=q.toString();history.replaceState(history.state,'',location.pathname+(s?'?'+s:'')+location.hash)}
const qget=k=>new URLSearchParams(location.search).get(k)||'';
/* flags sit beside this script (assets/flags/), whatever the page's depth (the Arabic pages are one level down) */
const ASSETS=((document.currentScript&&document.currentScript.src)||'../assets/maps.js').replace(/maps\.js[^/]*$/,'');
const flag=iso=>iso?`<img class="rk-flag" src="${ASSETS}flags/${esc(iso)}.svg" alt="" width="24" height="18" loading="lazy">`:'<span class="rk-flag"></span>';

function init(fig){
  const svg=$('svg.wm',fig),stage=$('.wm-stage',fig),card=$('.wm-card',fig),kind=fig.dataset.map;
  const links=$$('a[data-iso3]',svg),hqs=$$('.hq',svg),all=links.concat(hqs);
  /* the native <title> tooltips would double the card: keep their text as the accessible name instead */
  all.forEach(el=>{const t=$('title',el);if(t){el.setAttribute('aria-label',t.textContent);t.remove()}});
  let cur=null,pinned=false,lastPointer='mouse';
  const m={fig,links,hqs,kind,pick:null,escape:null,extra:null};
  /* raise a country above its neighbours (moving a focused element would drop its focus: keyboard moves raise before focusing) */
  const raise=el=>{if(el.tagName.toLowerCase()==='a'&&el!==document.activeElement&&el.parentNode.lastElementChild!==el)el.parentNode.appendChild(el)};
  const show=(el,x,y,html)=>{
    if(cur&&cur!==el)cur.classList.remove('on');cur=el;el.classList.add('on');
    raise(el);
    const d=el.dataset;let h=html||`<b>${esc(d.name)}</b>`+(d.i?`<span>${esc(d.i)}</span>`:'')+(d.l?`<span class="wm-l">${esc(d.l)}</span>`:'')+(m.extra?m.extra(el,pinned):'');
    if(!html&&pinned&&el.tagName.toLowerCase()==='a')h+=kind==='search'?`<span class="wm-l">${esc(fig.dataset.tPick||'')}</span>`:`<a href="${esc(el.getAttribute('href'))}">${esc(fig.dataset.tOpen||'Open the country page')}</a>`;
    card.innerHTML=h;card.hidden=false;card.classList.toggle('pin',pinned);place(x,y)};
  const place=(x,y)=>{const sw=stage.clientWidth,cw=card.offsetWidth,ch=card.offsetHeight;
    let l=x+14,t=y-ch-12;if(l+cw>sw-4)l=x-cw-14;if(l<4)l=Math.max(4,Math.min(sw-cw-4,x-cw/2));if(t<4)t=y+18;
    card.style.left=l+'px';card.style.top=t+'px'};
  const hide=()=>{if(cur)cur.classList.remove('on');cur=null;pinned=false;card.hidden=true};
  const at=ev=>{const r=stage.getBoundingClientRect();return[ev.clientX-r.left,ev.clientY-r.top]};
  const target=ev=>ev.target.closest&&ev.target.closest('a[data-iso3],.hq');
  svg.addEventListener('pointerdown',ev=>{lastPointer=ev.pointerType});
  svg.addEventListener('pointerover',ev=>{if(ev.pointerType==='touch')return;const el=target(ev);if(el&&el!==cur&&!pinned){show(el,...at(ev))}});
  svg.addEventListener('pointermove',ev=>{if(ev.pointerType==='touch'||!cur||pinned)return;place(...at(ev))});
  svg.addEventListener('pointerleave',ev=>{if(ev.pointerType!=='touch'&&!pinned)hide()});
  svg.addEventListener('click',ev=>{const el=target(ev);if(!el){if(pinned)hide();return}
    /* a page that handles the selection itself (Global, Search) */
    if(m.pick){const r=m.pick(el,ev,at(ev));if(r){ev.preventDefault();if(r!=='keep')hide();return}}
    /* touch: the first tap shows the card (with a link), a second tap on the same country follows it */
    if(lastPointer==='touch'&&!(pinned&&cur===el)){ev.preventDefault();pinned=true;show(el,...at(ev));return}});
  card.addEventListener('click',ev=>ev.stopPropagation());
  document.addEventListener('click',ev=>{if(pinned&&!fig.contains(ev.target))hide()});
  /* keyboard: one tab stop; arrows move through the countries in name order; Enter opens (or selects); Escape clears a selection */
  const order=links.slice().sort((a,b)=>a.dataset.name.localeCompare(b.dataset.name,document.documentElement.lang));
  if(order.length)order[0].setAttribute('tabindex','0');
  const centre=el=>{const r=el.getBoundingClientRect(),s=stage.getBoundingClientRect();return[r.left-s.left+r.width/2,r.top-s.top+r.height/2]};
  svg.addEventListener('focusin',ev=>{const el=target(ev);if(el){pinned=false;show(el,...centre(el))}});
  svg.addEventListener('focusout',ev=>{if(!svg.contains(ev.relatedTarget))hide()});
  svg.addEventListener('keydown',ev=>{const el=target(ev);if(!el||!el.dataset.iso3)return;const k=ev.key;
    if(k==='Escape'){hide();if(m.escape)m.escape();return}
    if((k==='Enter'||k===' ')&&m.pick){if(m.pick(el,ev,centre(el))){ev.preventDefault();show(el,...centre(el))}return}
    if(!['ArrowRight','ArrowLeft','ArrowDown','ArrowUp','Home','End'].includes(k))return;
    ev.preventDefault();const n=order.indexOf(el),fw=k==='ArrowRight'||k==='ArrowDown';
    const nx=k==='Home'?order[0]:k==='End'?order[order.length-1]:order[(n+(fw?1:-1)+order.length)%order.length];
    el.setAttribute('tabindex','-1');nx.setAttribute('tabindex','0');raise(nx);nx.focus()});
  /* Escape anywhere on the map card (not only on a focused country) */
  fig.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&!svg.contains(ev.target)&&m.escape&&!ev.target.matches('select')){if(pinned)hide();m.escape()}});
  m.refresh=()=>{if(cur&&!card.hidden&&!pinned)show(cur,parseFloat(card.style.left)||0,(parseFloat(card.style.top)||0)+card.offsetHeight+12)};
  m.pin=(el,x,y,html)=>{pinned=true;show(el,x,y,html)};
  m.hide=hide;
  return m;
}

/* ------------------------------------------------------------ Analysis: lenses */
const AR=document.documentElement.lang==='ar';
function qbins(vals,k=6){const v=vals.filter(x=>x>0).sort((a,b)=>a-b);if(!v.length)return[];
  const u=[...new Set(v)];if(u.length<=k)return u;const out=[];
  for(let i=1;i<=k;i++){const q=v[Math.min(v.length-1,Math.ceil(i*v.length/k)-1)];if(!out.length||q>out[out.length-1])out.push(q)}
  if(out[out.length-1]!==v[v.length-1])out.push(v[v.length-1]);return out}
const spread=(k,m)=>m===1?4:Math.round(1+(k-1)*5/(m-1));
const upBin=(n,ups)=>{if(!n)return 0;for(let k=0;k<ups.length;k++)if(ups[k]==null||n<=ups[k])return k+1;return ups.length};

function analysis(m){const f=m.fig,blob=$('#map-lens');if(!blob)return;
  const D=JSON.parse(blob.textContent),L=D.lens,t=D.t,C=D.c;
  Object.values(C).forEach(r=>{r[6]=r[6]?r[6].split(',').map(Number):[]});
  const h2=$('h2',f),desc=$('.wm-desc',f),note=$('.wm-note',f),topH=$('.wm-top-h',f),topL=$('.wm-top-l',f),ctl=$('.wm-ctl',f);
  const tabs=$$('.wm-lens .seg-b',f),tsel=$('[data-topic]',f),tlab=$('.wm-topic',f),legs=$$('.wm-legend[data-lens]',f);
  const lh=$('.wm-legend[data-lens="docs"] .wm-lh',f),t0=lh&&lh.textContent;
  const cat=k=>(D.cats.find(c=>c[0]===k)||[k,k])[1],ci=k=>D.cats.findIndex(c=>c[0]===k);
  const lenses=tabs.map(b=>b.dataset.lens);
  let lens='docs',all=false,topic=tsel.value;
  m.links.forEach(a=>{a.dataset.i0=a.dataset.i});
  const name=a=>a.dataset.name;
  /* each lens: shade, card text, and a value to rank by (with its label) for the top five */
  function values(){const out=new Map(),tn=cat(topic),ti=ci(topic);let ups=null;
    if(lens==='topic')ups=qbins(m.links.map(a=>(C[a.dataset.iso3]||[])[6]?C[a.dataset.iso3][6][ti]:0));
    m.links.forEach(a=>{const c=a.dataset.iso3,r=C[c];if(!r)return;let v;
      if(lens==='docs'){const n=all?r[2]:r[1];v={b:all?a.dataset.bAll:a.dataset.b,i:all?a.dataset.iAll:a.dataset.i0,k:n,l:String(n)}}
      else if(lens==='strategy'){const s=r[4];v=s?{b:s[3],i:s[1]+D.sep+s[2],k:s[0],l:s[2]}:{b:0,i:t.strat0,k:null}}
      else if(lens==='binding'){const n=r[1],b=r[3];if(n<D.min)v={b:'h',i:fill(t.share0,{n}),k:null};
        else{const p=Math.round(100*b/n);v={b:upBin(Math.max(p,.1),D.sb),i:fill(t.share,{p,b,n}),k:n>=D.topmin?p*1000+n:null,l:fill(t.pct,{p})}}}
      else if(lens==='topic'){const n=r[6][ti]||0;let b=0;if(n){b=6;for(let k=0;k<ups.length;k++)if(n<=ups[k]){b=spread(k+1,ups.length);break}}
        v={b,i:fill(n===1?t.topic1:n?t.topicn:t.topic0,{n,topic:tn}),k:n||null,l:String(n)}}
      else{const n=r[5];v={b:upBin(n,D.rb),i:n===1?t.rec1:n?fill(t.recn,{n}):t.rec0,k:n||null,l:String(n)}}
      out.set(c,v)});
    return{out,ups}}
  function render(){const{out,ups}=values(),tn=cat(topic);
    f.dataset.lens=lens;
    m.links.forEach(a=>{const v=out.get(a.dataset.iso3);if(!v)return;setBin(a,v.b);a.dataset.i=v.i});
    tabs.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.lens===lens)));
    tlab.hidden=lens!=='topic';ctl.hidden=lens!=='docs';
    legs.forEach(l=>l.hidden=l.dataset.lens!==lens);
    if(lh&&lh.dataset.alt)lh.textContent=all?lh.dataset.alt:t0;
    h2.textContent=lens==='topic'?fill(t.topich,{topic:tn}):L[lens].h;desc.textContent=L[lens].d;
    note.textContent=L[lens].note||'';note.hidden=!L[lens].note;
    if(lens==='topic'){const lg=$('.wm-legend[data-lens="topic"]',f);$('.wm-lh',lg).textContent=fill(t.toplh,{topic:tn});
      let h=$('.wm-keys .k0',lg).outerHTML,lo=1;ups.forEach((u,k)=>{h+=`<span><i class="wk m${spread(k+1,ups.length)}"></i><bdi dir="ltr">${lo===u?u:lo+'–'+u}</bdi></span>`;lo=u+1});
      $('.wm-keys',lg).innerHTML=h}
    /* top five: highest value (earliest strategy); equal values in name order */
    const rows=m.links.map(a=>[a,out.get(a.dataset.iso3)]).filter(([,v])=>v&&v.k!=null&&v.k!==0);
    const asc=lens==='strategy';
    rows.sort(([a,x],[b,y])=>(asc?(x.k<y.k?-1:x.k>y.k?1:0):(y.k-x.k))||name(a).localeCompare(name(b),document.documentElement.lang));
    topH.textContent=lens==='topic'?fill(t.toptop,{topic:tn}):L[lens].top;
    topL.innerHTML=rows.slice(0,5).map(([a,v])=>`<li><a href="${esc(a.getAttribute('href'))}">${flag(C[a.dataset.iso3][0])}<span class="wm-top-n">${esc(name(a))}</span><span class="wm-top-v" dir="auto">${esc(v.l)}</span></a></li>`).join('');
    m.refresh()}
  const set=(l,tp)=>{lens=lenses.includes(l)?l:'docs';if(tp&&ci(tp)>=0){topic=tp;tsel.value=tp}render();
    urlSet({lens:lens==='docs'?'':lens,topic:lens==='topic'?topic:''})};
  tabs.forEach(b=>b.addEventListener('click',()=>set(b.dataset.lens)));
  tsel.addEventListener('change',()=>set('topic',tsel.value));
  document.addEventListener('change',ev=>{if(ev.target.matches&&ev.target.matches('[data-scope-toggle]')){all=ev.target.checked;if(lens==='docs')render()}});
  const tg=$('[data-scope-toggle]');all=!!(tg&&tg.checked);
  lens=lenses.includes(qget('lens'))?qget('lens'):'docs';const tp=qget('topic');if(tp&&ci(tp)>=0){topic=tp;tsel.value=tp}
  render()}

/* ------------------------------------------------------------ Timeline: month slider and Play
   The slider moves month by month; the current month and the running count are shown large on the map itself, and the
   countries that publish their first document in that month flash briefly. About 6 months a second when playing. */
function timeline(m){const f=m.fig,range=$('input[type=range]',f),out=$('.wm-count',f),btn=$('.wm-pb',f);if(!range)return;
  const min=+range.min,max=+range.max;let timer=null,prev=null;
  const AR=document.documentElement.lang==='ar';
  const MF=new Intl.DateTimeFormat(AR?'ar-u-ca-gregory-nu-latn':'en-GB',{month:'long',year:'numeric',timeZone:'UTC'});
  const lab=M=>MF.format(new Date(Date.UTC(Math.floor(M/12),M%12,1)));
  const stage=$('.wm-stage',f),ov=document.createElement('div');ov.className='wm-when';ov.setAttribute('aria-hidden','true');
  ov.innerHTML='<span class="wm-when-d"></span><span class="wm-when-n"></span>';stage.appendChild(ov);
  const paint=M=>{let n=0;m.links.forEach(a=>{const mi=+a.dataset.m||0,on=mi&&mi<=M;if(on)n++;setBin(a,on?a.dataset.b:0);
      a.classList.toggle('wm-new',!!(on&&prev!==null&&mi>prev&&M-mi<2))});
    prev=M;const L=lab(M);range.value=M;range.setAttribute('aria-valuetext',L);
    const t=fill(n===1?f.dataset.tOne:f.dataset.tMany,{n,y:L});out.textContent=t;
    $('.wm-when-d',ov).textContent=L;$('.wm-when-n',ov).textContent=fill(n===1?f.dataset.tOneS:f.dataset.tManyS,{n})};
  const stop=()=>{clearInterval(timer);timer=null;btn.setAttribute('aria-pressed','false');$('span',btn).textContent=btn.dataset.play};
  const play=()=>{let M=+range.value>=max?min:+range.value;prev=null;paint(M);btn.setAttribute('aria-pressed','true');$('span',btn).textContent=btn.dataset.pause;
    timer=setInterval(()=>{M++;if(M>max){stop();m.links.forEach(a=>a.classList.remove('wm-new'));return}paint(M)},RM.matches?700:170)};
  btn.addEventListener('click',()=>timer?stop():play());
  range.addEventListener('input',()=>{if(timer)stop();prev=null;paint(+range.value)});
  prev=null;paint(max);
  /* once, when the map first comes into view: play the months through (not with reduced motion) */
  if(!RM.matches&&'IntersectionObserver' in window){const io=new IntersectionObserver(es=>{if(es.some(e=>e.isIntersecting)){io.disconnect();setTimeout(()=>{if(!timer&&+range.value===max)play()},400)}},{threshold:.6});io.observe(stage)}}

/* ------------------------------------------------------------ Global: organisation explorer */
function globalMap(m){const f=m.fig,blob=$('#map-orgs');if(!blob)return;
  const D=JSON.parse(blob.textContent),O=D.o,t=D.t;
  const selO=$('[data-pick="org"]',f),selC=$('[data-pick="country"]',f),clr=$('.wm-clear',f),p0=$('.wm-p0',f),p1=$('.wm-p1',f),panel=$('.wm-panel',f);
  const legs=$$('.wm-legend[data-mode]',f),hqG=$('.wm-hq',f);
  const byIso={};m.links.forEach(a=>{byIso[a.dataset.iso3]=a;a.dataset.i0=a.dataset.i});
  /* member states and signatories come as strings of ISO3 codes ("!" + the countries left out, for the UN system) */
  const ALL=Object.keys(D.f),codes=s=>s.replace(/^!/,'').match(/.{3}/g)||[];
  const dec=s=>{if(s[0]!=='!')return codes(s);const x=new Set(codes(s));return ALL.filter(c=>!x.has(c))};
  Object.values(O).forEach(o=>{if(o[3])o[3]=dec(o[3]);o[5].forEach(d=>{if(typeof d[3]==='string')d[3]=codes(d[3])})});
  const coll=new Intl.Collator(document.documentElement.lang);
  m.links.slice().sort((a,b)=>coll.compare(a.dataset.name,b.dataset.name)).forEach(a=>selC.add(new Option(a.dataset.name,a.dataset.iso3)));
  const ofC={};Object.keys(O).forEach(b=>{if(O[b][3])O[b][3].forEach(c=>(ofC[c]=ofC[c]||[]).push(b))});
  const SUM=Object.keys(O).find(b=>!O[b][3]);
  const gname=g=>(D.g.find(x=>x[0]===g)||[g,''])[1];
  const listList=$('[data-f="org"]');      /* the documents list's organisation filter (global.js) */
  let S={org:'',country:'',doc:''},quiet=false;
  const docLi=(b,d,k)=>`<li><a href="../body/${esc(b)}/#${esc(d[0])}" dir="auto">${esc(d[1])}</a><span class="wm-p-d">${esc(d[2]||t.date)}${k===0?`<span class="wm-p-tag">${esc(t.latest)}</span>`:''}</span></li>`;
  /* country mode: every other country is shaded by the number of recorded organisations it shares with the one picked */
  function shared(c){const n={};(ofC[c]||[]).forEach(b=>O[b][3].forEach(x=>{if(x!==c)n[x]=(n[x]||0)+1}));return n}
  function paintMap(hit,mode){let sh=null,ups=null;
    if(mode==='country'){sh=shared(S.country);ups=qbins(Object.values(sh));
      const lg=$('.wm-legend[data-mode="country"]',f),keys=$('.wm-keys',lg);let h=keys.dataset.k0||(keys.dataset.k0=keys.innerHTML),lo=1;
      ups.forEach((u,k)=>{h+=`<span class="wm-k"><i class="wk m${spread(k+1,ups.length)}"></i><bdi dir="ltr">${lo===u?u:lo+'–'+u}</bdi></span>`;lo=u+1});keys.innerHTML=h}
    const sb=n=>{if(!n)return 0;for(let k=0;k<ups.length;k++)if(n<=ups[k])return spread(k+1,ups.length);return 6};
    m.links.forEach(a=>{const c=a.dataset.iso3;a._sel=mode==='country'&&c===S.country;
      setBin(a,mode===''?a.dataset.b:mode==='org'?(hit.has(c)?4:0):(a._sel?'sel':sb(sh[c]||0)));
      if(mode==='country')a.dataset.i=a._sel?'':fill(sh[c]===1?t.shared1:t.shared,{n:sh[c]||0,c:(byIso[S.country]||{dataset:{}}).dataset.name});else a.dataset.i=a.dataset.i0});
    if(mode==='country'&&byIso[S.country]){const a=byIso[S.country];if(a!==document.activeElement)a.parentNode.appendChild(a)}
    const orgs=mode==='org'?new Set([S.org]):mode==='country'?new Set(ofC[S.country]||[]):null;
    m.hqs.forEach(h=>h.classList.toggle('hl',!!orgs&&h.dataset.orgs.split(' ').some(b=>orgs.has(b))));
    hqG.classList.toggle('dim',!!orgs);
    legs.forEach(l=>l.hidden=l.dataset.mode!==mode)}
  function orgPanel(b){const o=O[b],none=!o[3],n=o[4];let h=`<p class="wm-p-g">${esc(gname(o[2]))}</p><h3 class="wm-p-name"><a href="../body/${esc(b)}/">${esc(o[0])}</a></h3>`;
    if(!none){h+=`<dl class="wm-p-stats"><div><dt>${esc(t.lmem)}</dt><dd>${o[3].length}</dd></div><div><dt>${esc(t.ldocs)}</dt><dd>${n}</dd></div></dl>`;
      if(o[5].length)h+=`<h4 class="wm-p-sub">${esc(t.recent)}</h4><ol class="wm-p-docs">${o[5].map((d,k)=>docLi(b,d,k)).join('')}</ol>`}
    else{const d=o[5].find(x=>x[0]===S.doc)||o[5][0];S.doc=d?d[0]:'';const sig=d?d[3]:[];
      h+=`<dl class="wm-p-stats"><div><dt>${esc(t.ldecl)}</dt><dd>${n}</dd></div><div><dt>${esc(t.signed)}</dt><dd>${sig.length||'–'}</dd></div></dl>`;
      h+=`<label class="wm-p-decl"><span>${esc(t.decl)}</span><select data-doc>${o[5].map(x=>`<option value="${esc(x[0])}"${x[0]===S.doc?' selected':''}>${esc(x[1])} (${esc(x[2])})</option>`).join('')}</select></label>`;
      if(d)h+=`<ol class="wm-p-docs"><li><a href="../body/${esc(b)}/#${esc(d[0])}" dir="auto">${esc(d[1])}</a><span class="wm-p-d">${esc(d[2]||t.date)}</span></li></ol>`
        +(sig.length?'':`<p class="wm-p-note">${esc(t.nosig)}</p>`)}
    h+=`<p class="wm-p-more"><a href="../body/${esc(b)}/">${esc(n>3||none?fill(t.all,{n}):t.orgpage)}</a></p>`;
    return h}
  function countryPanel(c){const a=byIso[c],nm=a?a.dataset.name:c,bs=(ofC[c]||[]).slice().sort((x,y)=>O[y][4]-O[x][4]||coll.compare(O[x][1],O[y][1]));
    const M=bs.reduce((s,b)=>s+O[b][4],0),top=Math.max(1,...bs.map(b=>O[b][4]));
    let h=`<div class="wm-p-ct">${flag(D.f[c])}<h3 class="wm-p-name"><a href="../country/${esc(c)}/">${esc(nm)}</a></h3></div>`;
    h+=`<p class="wm-p-lead">${esc(fill(bs.length===1?t.cline1:bs.length?t.cline:t.cline0,{c:nm,n:bs.length,m:M.toLocaleString('en')}))}</p>`;
    if(bs.length)h+=`<ol class="wm-p-orgs">${bs.map(b=>`<li><a href="../body/${esc(b)}/">${esc(O[b][1])}</a><span class="wm-p-n">${O[b][4]}</span><i style="--w:${(100*O[b][4]/top).toFixed(1)}%"></i></li>`).join('')}</ol>`;
    if(SUM){const ds=O[SUM][5],k=ds.filter(d=>d[3]&&d[3].includes(c)).length;if(k)h+=`<p class="wm-p-note">${esc(fill(t.csum,{c:nm,k,n:ds.length}))}</p>`}
    h+=`<p class="wm-p-more"><a href="../country/${esc(c)}/">${esc(t.cpage)}</a></p>`;
    return h}
  function render(){const mode=S.org?'org':S.country?'country':'';let hit=new Set();
    if(mode==='org'){const o=O[S.org];if(o[3])hit=new Set(o[3]);else{const d=o[5].find(x=>x[0]===S.doc)||o[5][0];hit=new Set(d?d[3]:[])}
      const lg=$('.wm-legend[data-mode="org"]',f);$('[data-org-title]',lg).textContent=o[0];$('[data-org-key]',lg).textContent=o[3]?t.lmem:t.signed}
    if(mode==='country'){const lg=$('.wm-legend[data-mode="country"]',f);$('[data-country-title]',lg).textContent=fill(t.sharedh,{c:(byIso[S.country]||{dataset:{}}).dataset.name||S.country})}
    paintMap(hit,mode);
    p0.hidden=!!mode;p1.hidden=!mode;p1.innerHTML=mode==='org'?orgPanel(S.org):mode==='country'?countryPanel(S.country):'';
    panel.classList.toggle('on',!!mode);
    selO.value=S.org;selC.value=S.country;clr.hidden=!mode;
    const dsel=$('[data-doc]',p1);if(dsel)dsel.addEventListener('change',()=>{S.doc=dsel.value;render()});
    urlSet({org:S.org,country:S.country});
    /* the documents list below follows the organisation picked here */
    if(listList&&!quiet){const v=S.org&&Array.from(listList.options).some(o=>o.value===S.org)?S.org:'';
      if(listList.value!==v){quiet=true;listList.value=v;listList.dispatchEvent(new Event('change'));quiet=false;urlSet({org:S.org,country:S.country})}}
    m.refresh()}
  const pickOrg=b=>{if(!O[b])return;S={org:b,country:'',doc:''};render()};
  const pickCountry=c=>{if(!byIso[c])return;S={org:'',country:c,doc:''};render()};
  const clear=()=>{if(!S.org&&!S.country)return;S={org:'',country:'',doc:''};render()};
  selO.addEventListener('change',()=>selO.value?pickOrg(selO.value):clear());
  selC.addEventListener('change',()=>selC.value?pickCountry(selC.value):clear());
  clr.addEventListener('click',()=>{clear();selO.focus()});
  $$('.wm-ex',f).forEach(b=>b.addEventListener('click',()=>b.dataset.org?pickOrg(b.dataset.org):pickCountry(b.dataset.country)));
  m.escape=clear;
  /* a click on a country selects it (again: clears); on a headquarters marker, picks its organisation (or offers a choice) */
  m.pick=(el,ev,xy)=>{if(el.dataset.iso3){if(S.country===el.dataset.iso3)clear();else pickCountry(el.dataset.iso3);return true}
    const bs=el.dataset.orgs.split(' ').filter(b=>O[b]);if(!bs.length)return false;
    if(bs.length===1){pickOrg(bs[0]);return true}
    m.pin(el,xy[0],xy[1],`<b>${esc(el.dataset.name)}</b><span class="wm-l">${esc(t.choose)}</span><span class="wm-cbtns">${bs.map(b=>`<button type="button" data-org="${esc(b)}">${esc(O[b][1])}</button>`).join('')}</span>`);
    return'keep'};
  $('.wm-card',f).addEventListener('click',ev=>{const b=ev.target.closest('button[data-org]');if(b){m.hide();pickOrg(b.dataset.org)}});
  if(listList)listList.addEventListener('change',()=>{if(quiet)return;const v=listList.value;if(v&&O[v]&&v!==S.org){quiet=true;pickOrg(v);quiet=false}else if(!v&&S.org){quiet=true;clear();quiet=false}});
  const o0=qget('org'),c0=qget('country');if(O[o0])S.org=o0;else if(byIso[c0])S.country=c0;
  if(S.org||S.country){quiet=true;render();quiet=false}}

/* ------------------------------------------------------------ Search: quantile bins of the counts, recomputed for each result set */
function shade(fig,counts){const m=fig&&fig._wm;if(!m)return;
  const ups=qbins(m.links.map(a=>counts[a.dataset.iso3]||0)),d=fig.dataset;
  const bin=n=>{if(!n)return 0;for(let k=0;k<ups.length;k++)if(n<=ups[k])return spread(k+1,ups.length);return 6};
  m.links.forEach(a=>{const n=counts[a.dataset.iso3]||0;setBin(a,bin(n));a.dataset.i=n?fill(n===1?d.tOne:d.tMany,{n:n.toLocaleString('en')}):d.tNone});
  const keys=$('.wm-keys',fig);if(keys){let h=`<span class="k0"><i class="wk m0"></i><bdi>${esc(d.tLnone)}</bdi></span>`;let lo=1;
    ups.forEach((u,k)=>{h+=`<span><i class="wk m${spread(k+1,ups.length)}"></i><bdi dir="ltr">${lo===u?u:lo+'–'+u}</bdi></span>`;lo=u+1});keys.innerHTML=h}
  m.refresh()}
/* the countries the search is limited to: outlined on the map, one removable chip each, and "Show all countries" */
function select(fig,isos){const m=fig&&fig._wm;if(!m)return;const d=fig.dataset,set=new Set(isos||[]),box=$('.wm-sel',fig);
  m.sel=set;m.links.forEach(a=>{const s=set.has(a.dataset.iso3);if(s!==!!a._sel){a._sel=s;a.classList.toggle('sel',s)}if(s&&a!==document.activeElement)a.parentNode.appendChild(a)});
  if(!box)return;const picked=m.links.filter(a=>set.has(a.dataset.iso3));
  box.hidden=!picked.length;
  box.innerHTML=picked.map(a=>`<button type="button" class="wm-chip" data-iso3="${a.dataset.iso3}" aria-label="${esc(fill(d.tRm,{name:a.dataset.name}))}"><span>${esc(fill(d.tChip,{name:a.dataset.name}))}</span>${X}</button>`).join('')
    +(picked.length?`<button type="button" class="linkbtn wm-all">${esc(d.tAll)}</button>`:'')}
function search(m){const f=m.fig,un=detail=>f.dispatchEvent(new CustomEvent('wm:unpick',{detail}));
  m.sel=new Set();
  m.pick=el=>{const c=el.dataset.iso3;if(!c)return false;if(m.sel.has(c))un({iso3:c});else f.dispatchEvent(new CustomEvent('wm:pick',{detail:{iso3:c,name:el.dataset.name}}));return true};
  m.escape=()=>{if(m.sel.size)un({all:true})};
  $('.wm-sel',f).addEventListener('click',ev=>{const b=ev.target.closest('button');if(!b)return;if(b.classList.contains('wm-all'))un({all:true});else un({iso3:b.dataset.iso3})})}

const maps=$$('figure.wmap');
maps.forEach(f=>{const m=init(f);f._wm=m;const k=f.dataset.map;
  if(k==='analysis')analysis(m);if(k==='timeline')timeline(m);if(k==='global')globalMap(m);if(k==='search')search(m)});
window.RadarMap={shade,select};
})();
