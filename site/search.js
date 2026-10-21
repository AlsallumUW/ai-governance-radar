/* AI Governance Radar · document search. Loads assets/search.json and assets/search_terms.json once; every setting lives in the URL. */
(function(){'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const AR=document.documentElement.lang==='ar';
const tr=s=>(window.I18N&&window.I18N.t)?window.I18N.t(s):s;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const fmtD=d=>{if(!d)return'Undated';if(d.length===4)return d;const m=MON[+d.slice(5,7)-1];return d.length===7?`${m} ${d.slice(0,4)}`:`${+d.slice(8,10)} ${m} ${d.slice(0,4)}`};
const PER=50;

/* ------------------------------------------------------------ normalisation (text and query alike) */
const DIAC=/[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭـ]/g;
const SEPC='[\\s\\-_/\\u2010-\\u2015\\u00AD]',SEP=new RegExp(SEPC+'+','g'),SEP1=new RegExp('^'+SEPC+'$');
const fold=s=>s.replace(DIAC,'').replace(/[أإآٱ]/g,'ا').replace(/ة/g,'ه').replace(/ى/g,'ي');
const norm=s=>fold(String(s||'').toLowerCase()).replace(SEP,' ');
/* the same, with a map from each normalised character back to the original text (for excerpts and highlights) */
function normMap(s){let out='',map=[],sp=false;
  for(let i=0;i<s.length;){const cp=s.codePointAt(i),ch=String.fromCodePoint(cp);
    if(SEP1.test(ch)){if(!sp){out+=' ';map.push(i);sp=true}}
    else{const r=fold(ch.toLowerCase());for(const c of r){out+=c;map.push(i)}if(r)sp=false}
    i+=ch.length}
  return[out,map]}
const reEsc=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const LATIN=/^[a-z0-9 ]+$/;
function altSrc(a){let s=a.trim().split(' ').filter(Boolean).map(reEsc).join(' ?');   // a space may match no separator: "deep fake" finds "deepfake"
  if(LATIN.test(a)&&a.replace(/ /g,'').length<=3)s='(?<![\\p{L}\\p{N}])'+s+'(?![\\p{L}\\p{N}])';   // "ai", "llm": whole words only
  return s}
/* containment needs a few letters: "ai" or "gpu" expand only on an exact match */
const canContain=ns=>ns.length>=4||(ns.length>=3&&!LATIN.test(ns));

/* ------------------------------------------------------------ query */
function parseQ(q){q=String(q||'').replace(/[“”„«»]/g,'"').replace(/،/g,',');
  if(!/[",]/.test(q)){const t=q.trim();return t?[t]:[]}
  const out=[],re=/"([^"]*)"|([^",]+)/g;let m;
  while((m=re.exec(q))){const t=(m[1]!=null?m[1]:m[2]).trim();if(t&&!out.some(x=>norm(x)===norm(t)))out.push(t)}
  return out}
let GROUPS=[];
function expand(term,rel){const n=norm(term).trim(),ns=n.replace(/ /g,''),alts=new Map([[n,term]]),groups=[];
  if(rel&&ns)GROUPS.forEach(g=>{if(g.m.some(x=>x.ns===ns||(canContain(ns)&&x.ns.includes(ns)))){groups.push(g);g.m.forEach(x=>{if(!alts.has(x.n))alts.set(x.n,x.raw)})}});
  const list=[...alts].sort((a,b)=>b[0].length-a[0].length);
  const src=list.map(a=>altSrc(a[0])).join('|');
  return{term,n,alts:list,groups,re:new RegExp(src,'u'),reG:new RegExp(src,'gu')}}

/* ------------------------------------------------------------ data */
let T,J,ITEMS=[],ST={},LC={},CATS=[],TYPES=[],EV={},YEARS=[],ASOF='';
/* searched fields: titles (rank 3), summaries (rank 2), issuer and status notes (rank 1) */
const FT=['t','ot','at','iss','issa','sum','st','sa','sta'],RANK={t:3,ot:3,at:3,sum:2,sa:2,iss:1,issa:1,st:1,sta:1};
function load(){
  const get=id=>fetch($('#'+id).href).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()});
  return Promise.all([get('srData'),get('srTerms')]).then(([d,g])=>{
    T=d;J=d.jurisdictions;ASOF=d.as_of;
    d.statuses.forEach(s=>ST[s[0]]=s);d.lifecycles.forEach(s=>LC[s[0]]=s);CATS=d.categories;TYPES=d.types;EV=d.events;
    const f=d.fields;ITEMS=d.items.map(r=>{const o={};f.forEach((k,n)=>o[k]=r[n]);
      const it={id:o.id,j:o.jurisdiction,t:o.title,ot:o.official_title,at:o.arabic_title,iss:o.issuer,issa:o.issuer_ar,d:o.date,ls:o.legal_status,lc:o.lifecycle,
        cat:o.categories,sum:o.summary,st:o.status,sa:o.summary_ar,sta:o.status_ar,u:o.source,act:o.actions};
      it.N={};FT.forEach(k=>{if(it[k])it.N[k]=norm(it[k])});
      it.dk=!it.d?'':it.d.length===4?it.d+'-00-00':it.d.length===7?it.d+'-00':it.d;
      it.ty=d.type_of[it.ls]||'guidance';
      return it});
    const ys=new Set();ITEMS.forEach(it=>{if(it.d)ys.add(+it.d.slice(0,4))});YEARS=[...ys].sort((a,b)=>b-a);
    GROUPS=g.groups.map(x=>({key:x.key,label:AR?x.label_ar:x.label_en,q:AR?x.ar[0]:x.en[0],
      m:[...x.en,...x.ar].map(raw=>{const n=norm(raw).trim();return{raw,n,ns:n.replace(/ /g,'')}})}))})}

/* ------------------------------------------------------------ state <-> URL */
const DEF={q:'',all:false,rel:true,range:'',from:'',to:'',j:[],region:[],body:[],type:'',cat:'',sort:'',actions:false};
const ALIAS={ISESCO:'ICESCO'};
let F={...DEF};
function readURL(){const p=new URLSearchParams(location.search),list=k=>(p.get(k)||'').split(',').map(s=>s.trim()).filter(Boolean);
  const f={...DEF,q:p.get('q')||'',all:p.get('match')==='all',rel:p.get('rel')!=='0',actions:p.get('actions')==='1',
    range:p.get('range')||'',from:p.get('from')||'',to:p.get('to')||'',type:p.get('type')||'',cat:p.get('cat')||'',sort:p.get('sort')||''};
  f.j=list('j').map(x=>ALIAS[x]||x).filter(x=>J[x]);
  const regs=new Set();T.regions.forEach(r=>{regs.add(r[0]);r[2].forEach(s=>regs.add(s[0]))});f.region=list('region').filter(x=>regs.has(x));
  f.body=list('body').map(x=>ALIAS[x]||x).filter(x=>T.bodies[x]);
  if(!['','30','60','90','12m','custom'].includes(f.range)&&!/^\d{4}$/.test(f.range))f.range='';
  const iso=/^\d{4}-\d{2}-\d{2}$/;if(!iso.test(f.from))f.from='';if(!iso.test(f.to))f.to='';
  if(!TYPES.some(t=>t[0]===f.type))f.type='';if(!CATS.some(c=>c[0]===f.cat))f.cat='';if(!['','newest','oldest','country'].includes(f.sort))f.sort='';
  return f}
function writeURL(){const p=new URLSearchParams();
  if(F.q)p.set('q',F.q);if(F.all)p.set('match','all');if(!F.rel)p.set('rel','0');if(F.range)p.set('range',F.range);
  if(F.range==='custom'){if(F.from)p.set('from',F.from);if(F.to)p.set('to',F.to)}
  if(F.j.length)p.set('j',F.j.join(','));if(F.region.length)p.set('region',F.region.join(','));if(F.body.length)p.set('body',F.body.join(','));
  if(F.type)p.set('type',F.type);if(F.cat)p.set('cat',F.cat);if(F.sort)p.set('sort',F.sort);if(F.actions)p.set('actions','1');
  const s=p.toString().replace(/%2C/g,',');history.replaceState(null,'',location.pathname+(s?'?'+s:'')+location.hash)}

/* ------------------------------------------------------------ dates */
const iso=t=>new Date(t).toISOString().slice(0,10);
const addDays=(d,n)=>iso(Date.parse(d+'T00:00:00Z')+n*864e5);
function rangeOf(f){const r=f.range;
  if(!r)return{all:true};
  if(['30','60','90'].includes(r))return{a:addDays(ASOF,-(+r)),b:ASOF,rolling:true};
  if(r==='12m'){const y=+ASOF.slice(0,4)-1;return{a:addDays(`${y}${ASOF.slice(4)}`,0),b:ASOF,rolling:true}}
  if(/^\d{4}$/.test(r))return{a:r+'-01-01',b:r+'-12-31'};
  let a=f.from||'0000-01-01',b=f.to||'9999-12-31';if(a>b)[a,b]=[b,a];return{a,b,custom:true}}
/* a partial date is placed where its month (or, for Year and Custom ranges, its year) overlaps the range */
function inR(d,R){if(R.all)return true;if(!d)return false;
  if(d.length>=10)return d>=R.a&&d<=R.b;
  if(d.length===7)return d+'-01'<=R.b&&d+'-31'>=R.a;
  if(R.rolling)return false;return d+'-01-01'<=R.b&&d+'-12-31'>=R.a}
const yearOverlaps=(d,R)=>d.length===4&&d+'-01-01'<=R.b&&d+'-12-31'>=R.a;
const AMEND=['revised','adopted','applied'];
function actIn(it,R){if(R.all)return null;for(let k=it.act.length-1;k>=0;k--){const[d,t]=it.act[k];if(AMEND.includes(t)&&inR(d,R))return it.act[k]}return null}

/* ------------------------------------------------------------ matching */
let Q=[],R={all:true},RES=[],SHOWN=PER,LEFT=0;
function jFilter(){const js=new Set(F.j),rs=new Set(F.region),ms=new Set();F.body.forEach(b=>(T.bodies[b]||[]).forEach(c=>ms.add(c)));
  const none=!js.size&&!rs.size&&!ms.size;
  return it=>{const jj=J[it.j];if(!jj)return false;if(none)return jj[2]==='c';if(js.has(it.j))return true;
    return jj[2]==='c'&&(rs.has(jj[3])||rs.has(jj[4])||ms.has(it.j))}}
function score(it){if(!Q.length)return 0;let s=0,hit=0;
  for(const q of Q){let best=0;for(const k of FT){const v=it.N[k];if(v&&RANK[k]>best&&q.re.test(v))best=RANK[k]}
    if(best){hit++;s+=best}else if(F.all)return-1}
  return hit?s:-1}
function run(){
  Q=parseQ(F.q).map(t=>expand(t,F.rel));R=rangeOf(F);
  const jok=jFilter(),ci=F.cat?CATS.findIndex(c=>c[0]===F.cat):-1;
  const out=[];LEFT=0;
  for(const it of ITEMS){
    if(!jok(it))continue;if(F.type&&it.ty!==F.type)continue;if(ci>=0&&!it.cat.includes(ci))continue;
    const s=score(it);if(s<0)continue;
    it.score=s;it.via=null;
    if(inR(it.d,R)){out.push(it);continue}
    if(F.actions){const a=actIn(it,R);if(a){it.via=a;out.push(it);continue}}
    if(!it.d||(R.rolling&&yearOverlaps(it.d,R)))LEFT++}
  const byNew=(a,b)=>a.dk<b.dk?1:a.dk>b.dk?-1:0,undatedLast=(a,b)=>(!a.dk)-(!b.dk);
  const nm=it=>AR?J[it.j][1]:J[it.j][0];
  if(F.sort==='newest')out.sort((a,b)=>undatedLast(a,b)||byNew(a,b));
  else if(F.sort==='oldest')out.sort((a,b)=>undatedLast(a,b)||-byNew(a,b));
  else if(F.sort==='country')out.sort((a,b)=>nm(a).localeCompare(nm(b),AR?'ar':'en')||undatedLast(a,b)||byNew(a,b));
  else out.sort((a,b)=>b.score-a.score||undatedLast(a,b)||byNew(a,b));
  RES=out}

/* ------------------------------------------------------------ highlight and excerpt */
function ranges(text){if(!Q.length)return[];const[n,map]=normMap(text),rs=[];
  for(const q of Q){q.reG.lastIndex=0;let m;while((m=q.reG.exec(n))){if(!m[0].length){q.reG.lastIndex++;continue}
    const a=map[m.index],z=map[m.index+m[0].length-1];rs.push([a,z+String.fromCodePoint(text.codePointAt(z)).length])}}
  rs.sort((x,y)=>x[0]-y[0]);const mg=[];rs.forEach(r=>{const l=mg[mg.length-1];if(l&&r[0]<=l[1])l[1]=Math.max(l[1],r[1]);else mg.push(r.slice())});return mg}
function marked(text,rs,from=0,to=text.length){let h='',p=from;
  rs.forEach(([a,z])=>{if(z<=from||a>=to)return;a=Math.max(a,from);z=Math.min(z,to);h+=esc(text.slice(p,a))+'<mark>'+esc(text.slice(a,z))+'</mark>';p=z});
  return h+esc(text.slice(p,to))}
function cut(text,a,len){let s=Math.max(0,a-70),e=Math.min(text.length,s+len);if(e===text.length)s=Math.max(0,e-len);
  if(s>0){const sp=text.indexOf(' ',s);if(sp>=0&&sp<a)s=sp+1}if(e<text.length){const sp=text.lastIndexOf(' ',e);if(sp>a)e=sp}return[s,e]}
function excerpt(it){
  const order=AR?['sa','sta','sum','st']:['sum','st','sa','sta'];
  for(const k of order){const txt=it[k];if(!txt||!Q.length)continue;const rs=ranges(txt);if(!rs.length)continue;
    const[s,e]=cut(txt,rs[0][0],200);return{k,html:(s>0?'… ':'')+marked(txt,rs,s,e)+(e<txt.length?' …':'')}}
  const k=AR&&it.sa?'sa':'sum',txt=it[k]||'';if(!txt)return null;const[s,e]=cut(txt,0,200);return{k,html:esc(txt.slice(s,e))+(e<txt.length?' …':'')}}

/* ------------------------------------------------------------ rendering */
const form=$('#srForm'),qIn=$('#srQ'),sum=$('#srSummary'),box=$('#srResults'),note=$('#srNote'),more=$('#srMore'),csvB=$('#srCsv');
const isAr=s=>/[؀-ۿ]/.test(s||'');
const jName=id=>J[id]?(AR?J[id][1]:J[id][0]):id;
const pageURL=it=>`../${J[it.j]&&J[it.j][2]==='c'?'country':'body'}/${it.j}/#${it.id}`;
function titles(it){const ar=it.at||(isAr(it.ot)?it.ot:'');
  const main=AR&&ar?ar:it.t,second=AR&&ar?(it.t!==ar?it.t:''):it.ot;return[main,second]}
function row(it){
  const[main,second]=titles(it),ex=excerpt(it),body=J[it.j][2]!=='c',st=ST[it.ls]||['', 'Not recorded','غير مسجل'];
  const issuer=AR&&it.issa?it.issa:it.iss;
  const tl=marked(main,ranges(main));
  const date=`<time datetime="${esc(it.d)}">${esc(fmtD(it.d))}</time>`+(it.via?`<span class="sr-via"><span>${esc(EV[it.via[1]]?EV[it.via[1]][0]:it.via[1])}</span> <span>${esc(fmtD(it.via[0]))}</span></span>`:'');
  return`<tr><td class="c-j"><span class="lbl">${body?'Body':'Country'}</span><span class="v"><span translate="no">${esc(jName(it.j))}</span><a class="sr-cp" href="${pageURL(it)}">${body?'Body page':'Country page'}</a></span></td>`
    +`<td class="c-t"><span class="sr-title" translate="no" dir="auto">${it.u?`<a href="${esc(it.u)}" target="_blank" rel="noopener noreferrer">${tl}</a>`:tl}</span>`
    +(second?`<span class="sr-ot" translate="no" dir="auto">${marked(second,ranges(second))}</span>`:'')
    +(ex?`<span class="sr-ex" translate="no" dir="auto"${isAr(it[ex.k])?' lang="ar"':' lang="en"'}>${ex.html}</span>`:'')+'</td>'
    +`<td class="c-i"><span class="lbl">Issuer</span><span class="v" translate="no" dir="auto">${esc(issuer||'')}</span></td>`
    +`<td class="c-d"><span class="lbl">Date</span><span class="v">${date}</span></td>`
    +`<td class="c-s"><span class="lbl">Status</span><span class="v">${esc(AR?st[2]:st[1])}</span></td></tr>`}
const HEAD='<table class="sr-table"><thead><tr><th scope="col">Country</th><th scope="col">Title</th><th scope="col">Issuer</th><th scope="col">Date</th><th scope="col">Status</th></tr></thead><tbody>';
function rangeLabel(){const r=F.range;
  if(!r)return'All time';if(r==='12m')return'Last 12 months';if(/^\d+$/.test(r)&&r.length<4)return`Last ${r} days`;if(/^\d{4}$/.test(r))return`Year ${r}`;
  const a=F.from&&F.to&&F.from>F.to?F.to:F.from,b=F.from&&F.to&&F.from>F.to?F.from:F.to;
  if(a&&b)return`${fmtD(a)} to ${fmtD(b)}`;if(a)return`From ${fmtD(a)}`;if(b)return`Until ${fmtD(b)}`;return'All time'}
function render(keepShown){
  run();if(!keepShown)SHOWN=PER;
  const n=RES.length,cs=new Set(),bs=new Set();RES.forEach(it=>(J[it.j][2]==='c'?cs:bs).add(it.j));
  const cnt=`${n.toLocaleString('en')} document${n===1?'':'s'} in ${cs.size.toLocaleString('en')} countr${cs.size===1?'y':'ies'}`+(bs.size?` and ${bs.size} bod${bs.size===1?'y':'ies'}`:'');
  sum.innerHTML=`<span>${esc(cnt)}</span><span class="dot"> · </span><span>${esc(rangeLabel())}</span>`
    +(F.actions&&F.range?`<span class="dot"> · </span><span>with amendments and entry into force</span>`:'')
    +(Q.length?`<span class="dot"> · </span><span translate="no" dir="auto">${esc(Q.map(q=>'"'+q.term+'"').join(', '))}</span>`+(Q.length>1?` <span>(${F.all?'all terms':'any term'})</span>`:''):'');
  box.innerHTML=n?HEAD+RES.slice(0,SHOWN).map(row).join('')+'</tbody></table>':'<p class="sr-empty">No documents match. Try related terms or a wider date range.</p>';
  note.hidden=!LEFT||F.range==='';
  note.textContent=LEFT===1?'1 matching document has only a year, or no date, and is not placed in this range.':`${LEFT.toLocaleString('en')} matching documents have only a year, or no date, and are not placed in this range.`;
  more.hidden=n<=SHOWN;$('#srShown').textContent=n>SHOWN?`Showing ${SHOWN.toLocaleString('en')} of ${n.toLocaleString('en')}`:'';
  csvB.disabled=!n;csvB.textContent=`Download CSV (${n.toLocaleString('en')})`;
  /* related terms */
  const also=[];Q.forEach(q=>q.alts.forEach(([nn,raw])=>{if(nn!==q.n&&!Q.some(x=>x.n===nn)&&!also.includes(raw))also.push(raw)}));
  $('#srAlso').hidden=!also.length;$('#srAlsoList').textContent=also.join(', ');
  $$('#srTopics button').forEach(b=>b.setAttribute('aria-pressed',String(Q.some(q=>q.groups.some(g=>g.key===b.dataset.key)))))}

/* ------------------------------------------------------------ controls */
function toForm(){qIn.value=F.q;form.elements.mode.value=F.all?'all':'any';$('#srRel').checked=F.rel;$('#srActions').checked=F.actions;
  $('#srType').value=F.type;$('#srCat').value=F.cat;$('#srSort').value=F.sort;if(F.type||F.cat)$('#srMoreF').open=true;
  const yr=/^\d{4}$/.test(F.range);
  $$('.seg-b').forEach(b=>{const k=b.dataset.range,on=k==='year'?yr:k===F.range;b.setAttribute('aria-pressed',String(on))});
  $('#srYearL').hidden=!yr;if(yr){if(!YEARS.includes(+F.range))$('#srYear').add(new Option(F.range,F.range));$('#srYear').value=F.range}
  $('#srCustom').hidden=F.range!=='custom';$('#srFrom').value=F.from;$('#srTo').value=F.to;
  chips()}
function update(keep){writeURL();render(keep)}
let deb;qIn.addEventListener('input',()=>{clearTimeout(deb);deb=setTimeout(()=>{F.q=qIn.value;update()},250)});
qIn.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();clearTimeout(deb);F.q=qIn.value;update()}});
qIn.addEventListener('search',()=>{clearTimeout(deb);F.q=qIn.value;update()});
$$('input[name=mode]').forEach(r=>r.addEventListener('change',()=>{F.all=form.elements.mode.value==='all';update()}));
$('#srRel').addEventListener('change',ev=>{F.rel=ev.target.checked;update()});
$('#srActions').addEventListener('change',ev=>{F.actions=ev.target.checked;update()});
$('#srType').addEventListener('change',ev=>{F.type=ev.target.value;update()});
$('#srCat').addEventListener('change',ev=>{F.cat=ev.target.value;update()});
$('#srSort').addEventListener('change',ev=>{F.sort=ev.target.value;update()});
$$('.seg-b').forEach(b=>b.addEventListener('click',()=>{const k=b.dataset.range;
  F.range=k==='year'?String($('#srYear').value||YEARS[0]):k;
  if(k==='custom'&&!F.from&&!F.to){F.from=addDays(ASOF,-365);F.to=ASOF}
  toForm();update();if(k==='year')$('#srYear').focus();if(k==='custom')$('#srFrom').focus()}));
$('#srYear').addEventListener('change',ev=>{F.range=ev.target.value;update()});
['srFrom','srTo'].forEach(id=>$('#'+id).addEventListener('change',()=>{F.from=$('#srFrom').value;F.to=$('#srTo').value;update()}));
more.addEventListener('click',()=>{const first=SHOWN;SHOWN+=PER;render(true);const r=$$('.sr-table tbody tr')[first];if(r){const a=$('a',r);if(a)a.focus({preventScroll:false})}});
$('#srClear').addEventListener('click',()=>{F={...DEF,j:[],region:[],body:[]};toForm();update();qIn.focus()});

/* jurisdictions: one combobox for countries, regions, "members of" a body and the bodies themselves; picks are combined */
const jIn=$('#srJ'),jList=$('#srJList');let OPTS=[],active=-1,shownOpts=[];
function buildOpts(){OPTS=[];const key=(...s)=>norm(s.join(' '));
  T.regions.forEach(r=>{OPTS.push({g:'Regions',k:'region',v:r[0],label:AR?r[1]:r[0],key:key(r[0],r[1])});
    r[2].forEach(s=>OPTS.push({g:'Regions',k:'region',v:s[0],label:AR?s[1]:s[0],key:key(s[0],s[1],r[0],r[1]),sub:1}))});
  Object.keys(T.bodies).forEach(b=>OPTS.push({g:'Members of',k:'body',v:b,label:`${J[b][0]} members`,key:key(b,J[b][0],J[b][1],'members','أعضاء')}));
  Object.keys(J).filter(id=>J[id][2]==='b').forEach(b=>OPTS.push({g:'Regional and international bodies',k:'j',v:b,label:jName(b),key:key(b,J[b][0],J[b][1])}));
  Object.keys(J).filter(id=>J[id][2]==='c').sort((a,b)=>jName(a).localeCompare(jName(b),AR?'ar':'en'))
    .forEach(c=>OPTS.push({g:'Countries',k:'j',v:c,label:jName(c),key:key(c,J[c][0],J[c][1])}));
  OPTS.forEach((o,n)=>o.id='srO'+n)}
const picked=o=>F[o.k].includes(o.v);
function openList(){const q=norm(jIn.value).trim();shownOpts=OPTS.filter(o=>!q||o.key.includes(q));let h='',g='';
  shownOpts.forEach(o=>{if(o.g!==g){g=o.g;h+=`<li class="grp" role="presentation">${esc(g)}</li>`}
    h+=`<li role="option" id="${o.id}" class="opt${o.sub?' sub':''}" aria-selected="${picked(o)}" data-n="${OPTS.indexOf(o)}"${o.k==='body'?'':' translate="no"'}>${esc(o.label)}</li>`});
  jList.innerHTML=h||'<li class="grp" role="presentation">No match</li>';jList.hidden=false;jIn.setAttribute('aria-expanded','true');active=-1;jIn.removeAttribute('aria-activedescendant')}
function closeList(){jList.hidden=true;jIn.setAttribute('aria-expanded','false');active=-1;jIn.removeAttribute('aria-activedescendant')}
function setActive(n){const els=$$('.opt',jList);if(!els.length)return;active=(n+els.length)%els.length;els.forEach((e,k)=>e.classList.toggle('act',k===active));
  jIn.setAttribute('aria-activedescendant',els[active].id);els[active].scrollIntoView({block:'nearest'})}
function toggle(o){const a=F[o.k];const i=a.indexOf(o.v);if(i>=0)a.splice(i,1);else a.push(o.v);jIn.value='';chips();update();openList()}
function chips(){const all=[...F.region.map(v=>OPTS.find(o=>o.k==='region'&&o.v===v)),...F.body.map(v=>OPTS.find(o=>o.k==='body'&&o.v===v)),...F.j.map(v=>OPTS.find(o=>o.k==='j'&&o.v===v))].filter(Boolean);
  $('#srPicked').innerHTML=all.length?all.map(o=>`<button type="button" class="sr-pick" data-n="${OPTS.indexOf(o)}" aria-label="Remove ${esc(o.label)}"><span${o.k==='body'?'':' translate="no"'}>${esc(o.label)}</span><span aria-hidden="true"> ×</span></button>`).join(''):'<span class="sr-all">All countries</span>'}
$('#srPicked').addEventListener('click',ev=>{const b=ev.target.closest('.sr-pick');if(!b)return;const o=OPTS[+b.dataset.n];const a=F[o.k];a.splice(a.indexOf(o.v),1);chips();update();jIn.focus()});
jIn.addEventListener('focus',openList);jIn.addEventListener('input',openList);
jIn.addEventListener('keydown',ev=>{const k=ev.key;
  if(k==='ArrowDown'){ev.preventDefault();if(jList.hidden)openList();setActive(active+1)}
  else if(k==='ArrowUp'){ev.preventDefault();if(jList.hidden)openList();setActive(active-1)}
  else if(k==='Enter'){ev.preventDefault();const els=$$('.opt',jList);const el=els[active>=0?active:(els.length===1?0:-1)];if(el)toggle(OPTS[+el.dataset.n])}
  else if(k==='Escape'){if(!jList.hidden){ev.preventDefault();closeList()}}
  else if(k==='Backspace'&&!jIn.value){const last=F.j.length?'j':F.body.length?'body':F.region.length?'region':'';if(last){F[last].pop();chips();update();openList()}}
  else if(k==='Tab')closeList()});
jList.addEventListener('mousedown',ev=>ev.preventDefault());
jList.addEventListener('click',ev=>{const el=ev.target.closest('.opt');if(el)toggle(OPTS[+el.dataset.n])});
document.addEventListener('click',ev=>{if(!ev.target.closest('.sr-combo'))closeList()});

/* ------------------------------------------------------------ CSV export (exactly the current results) */
function cell(v){v=v==null?'':String(v);return/[",\r\n]/.test(v)||/^\s|\s$/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}
function matchedTerms(it){const out=[];
  Q.forEach(q=>q.alts.forEach(([n,raw])=>{const re=new RegExp(altSrc(n),'u');if(FT.some(k=>it.N[k]&&re.test(it.N[k]))&&!out.includes(raw))out.push(raw)}));return out.join('; ')}
function csv(){
  const lab=(x,k)=>x?(AR?x[2]:x[1]):(k||'');
  const site=T.site+(AR?'ar/':'');
  const cols=[['Country',it=>J[it.j][0]],...(AR?[['Arabic country name',it=>J[it.j][1]]]:[]),['ISO code',it=>it.j],
    ['Title',it=>it.t],...(AR?[['Arabic title',it=>it.at||(isAr(it.ot)?it.ot:'')]]:[]),['Official title',it=>it.ot||it.t],
    ['Issuer',it=>it.iss],['Publication date',it=>it.d],['Legal status',it=>lab(ST[it.ls],it.ls)],['Lifecycle',it=>lab(LC[it.lc],it.lc)],
    ['Categories',it=>it.cat.map(c=>lab(CATS[c])).join('; ')],['Matched terms',matchedTerms],['Summary',it=>it.sum],...(AR?[['Arabic summary',it=>it.sa]]:[]),
    ['Official source',it=>it.u],['Radar page',it=>`${site}${J[it.j][2]==='c'?'country':'body'}/${it.j}/#${it.id}`]];
  const head=cols.map(c=>cell(AR?tr(c[0]):c[0])).join(',');
  return'﻿'+[head,...RES.map(it=>cols.map(c=>cell(c[1](it))).join(','))].join('\r\n')+'\r\n'}
function dl(text,name,type){const a=document.createElement('a'),u=URL.createObjectURL(new Blob([text],{type}));a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500)}
csvB.addEventListener('click',()=>dl(csv(),`AI-Governance-Radar-search-${ASOF}.csv`,'text/csv;charset=utf-8'));

/* ------------------------------------------------------------ start */
load().then(()=>{
  const ys=$('#srYear');YEARS.forEach(y=>ys.add(new Option(y,y)));
  $('#srTopics').innerHTML=GROUPS.map(g=>`<button type="button" class="sr-topic" data-key="${esc(g.key)}" aria-pressed="false" translate="no">${esc(g.label)}</button>`).join('');
  $('#srTopics').addEventListener('click',ev=>{const b=ev.target.closest('.sr-topic');if(!b)return;const g=GROUPS.find(x=>x.key===b.dataset.key);F.q=g.q;F.rel=true;toForm();update()});
  buildOpts();F=readURL();toForm();render();
  window.RADAR_SEARCH={count:()=>RES.length,state:()=>JSON.parse(JSON.stringify(F)),asOf:()=>ASOF,
    rows:()=>RES.map(it=>({id:it.id,j:it.j,d:it.d,via:it.via,type:J[it.j][2]})),terms:()=>Q.map(q=>q.alts.map(a=>a[1]))};
}).catch(err=>{sum.textContent='The search data could not be loaded. Please reload the page.';if(window.console)console.error(err)});
})();
