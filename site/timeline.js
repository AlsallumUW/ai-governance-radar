/* AI Governance Radar · publication timeline. Reads the inline JSON once; filters live in the URL. */
(function(){'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const T=JSON.parse(document.getElementById('tl-data').textContent);
const NS='http://www.w3.org/2000/svg',GC=['b','n','d'],GROUP=['binding','soft','draft'];
const J=T.jurisdictions,ST=T.statuses,CAT=T.categories,LV=T.levels;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
/* items: dates of year-only or month-only precision sit mid-year / mid-month */
const items=T.items.map(r=>{const [id,j,d,g,t,iss,s,c,l,u,app]=r;let x=null,prec=null;
  if(/^\d{4}-\d{2}-\d{2}$/.test(d)){x=Date.UTC(+d.slice(0,4),+d.slice(5,7)-1,+d.slice(8,10));prec='day'}
  else if(/^\d{4}-\d{2}$/.test(d)){x=Date.UTC(+d.slice(0,4),+d.slice(5,7)-1,15);prec='month'}
  else if(/^\d{4}$/.test(d)){x=Date.UTC(+d,6,1);prec='year'}
  return{id,j,d,g,t,iss,s,c,l,u,app,x,prec,y:x==null?null:new Date(x).getUTCFullYear()}});
const fmt=it=>{if(!it.d)return'Undated';if(it.prec==='year')return it.d+' (year only)';const m=MON[+it.d.slice(5,7)-1];return it.prec==='month'?`${m} ${it.d.slice(0,4)}`:`${+it.d.slice(8,10)} ${m} ${it.d.slice(0,4)}`};
const years=items.filter(i=>i.y!=null).map(i=>i.y),Y0=Math.min(...years),Y1=Math.max(...years,+T.asof.slice(0,4));
const DEF_FROM=Math.max(Y0,2016);
/* filters <-> URL */
const form=$('#tlFilters'),KEYS=['country','region','body','cat','status','level','from','to'];
const fromSel=form.elements.from,toSel=form.elements.to;
for(let y=Y0;y<=Y1;y++){fromSel.add(new Option(y,y));toSel.add(new Option(y,y))}
fromSel.remove(0);toSel.remove(0);
function readURL(){const q=new URLSearchParams(location.search),f={};KEYS.forEach(k=>f[k]=q.get(k)||'');
  if(f.country&&!J[f.country])f.country='';if(f.body&&!T.bodies[f.body])f.body='';
  f.from=+f.from||DEF_FROM;f.to=+f.to||Y1;f.from=Math.min(Math.max(f.from,Y0),Y1);f.to=Math.min(Math.max(f.to,f.from),Y1);return f}
function writeURL(f){const q=new URLSearchParams();KEYS.forEach(k=>{const v=f[k];if(k==='from'&&+v===DEF_FROM)return;if(k==='to'&&+v===Y1)return;if(v)q.set(k,v)});
  const s=q.toString();history.replaceState(null,'',location.pathname+(s?'?'+s:'')+location.hash)}
let F=readURL();
function toForm(){KEYS.forEach(k=>{const el=form.elements[k];if(el)el.value=String(F[k]??'')})}
function fromForm(){const f={};KEYS.forEach(k=>f[k]=form.elements[k].value);f.from=+f.from;f.to=+f.to;if(f.to<f.from)[f.from,f.to]=[f.to,f.from];return f}
form.addEventListener('change',()=>{F=fromForm();writeURL(F);render()});
$('#tlReset').addEventListener('click',()=>{F={country:'',region:'',body:'',cat:'',status:'',level:'',from:DEF_FROM,to:Y1};toForm();writeURL(F);render()});
/* filtering */
const catIdx=k=>CAT.findIndex(c=>c[0]===k),stIdx=k=>ST.findIndex(s=>s[0]===k),lvIdx=k=>LV.findIndex(l=>l[0]===k);
function match(it,f){
  const jj=J[it.j]||['','',0];
  if(f.country){if(!(it.j===f.country||(!jj[2]&&it.app.includes(f.country))))return false}
  if(f.region){if(!jj[2]||jj[1]!==f.region)return false}
  if(f.body){const m=T.bodies[f.body][1];if(!(it.j===f.body||(jj[2]&&m.includes(it.j))))return false}
  if(f.cat&&!it.c.includes(catIdx(f.cat)))return false;
  if(f.status){const gi=GROUP.indexOf(f.status);if(gi>=0?it.g!==gi:it.s!==stIdx(f.status))return false}
  if(f.level&&it.l!==lvIdx(f.level))return false;
  return true}
/* drawing */
const svg=$('#tlSvg'),brush=$('#tlBrush'),card=$('#tlCard'),list=$('#tlList'),status=$('#tlStatus'),chartBox=$('#tlChart');
const el=(n,a,p)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e};
let dots=[],pinned=null;
const pageURL=it=>(J[it.j]&&J[it.j][2]?'../country/':'../body/')+it.j+'/';
function cardHTML(it){const jj=J[it.j]||[it.j];const via=!J[it.j][2]&&F.country&&it.j!==F.country?` · applies to ${esc(J[F.country][0])} through membership`:'';
  return `<button type="button" class="linkbtn x" aria-label="Close">Close</button><h4>${esc(it.t)}</h4>`
  +`<p><span class="k">${J[it.j][2]?'Country':'Body'}:</span> ${esc(jj[0])}${via}</p><p><span class="k">Issuer:</span> ${esc(it.iss||'Not recorded')}</p>`
  +`<p><span class="k">Date:</span> ${esc(fmt(it))}</p><p><span class="k">Status:</span> ${esc(ST[it.s][1])} · ${esc(T.groups[it.g])}</p>`
  +`<p class="links"><a href="${pageURL(it)}">${J[it.j][2]?'Country':'Body'} page →</a>${it.u?`<a href="${esc(it.u)}" target="_blank" rel="noopener">Official source ↗</a>`:''}</p>`}
function showCard(it,px,py,pin){card.innerHTML=cardHTML(it);card.hidden=false;pinned=pin?it:null;
  const bw=chartBox.clientWidth,cw=card.offsetWidth,ch=card.offsetHeight;let x=px+14,y=py-ch-10;if(x+cw>bw)x=Math.max(0,px-cw-14);if(y<0)y=py+14;card.style.left=x+'px';card.style.top=y+'px';
  $('.x',card).onclick=()=>hideCard(true);dots.forEach(d=>d.node.classList.toggle('hl',d.it===it))}
function hideCard(force){if(pinned&&!force)return;card.hidden=true;pinned=null;dots.forEach(d=>d.node.classList.remove('hl'))}
function drawMain(rows){
  svg.textContent='';dots=[];
  const W=Math.max(320,chartBox.clientWidth||900),r=4,dia=2*r+1,L=8,R=8,top=10,axisH=26;
  const x0=Date.UTC(F.from,0,1),x1=Date.UTC(F.to+1,0,1),pw=W-L-R,X=t=>L+pw*(t-x0)/(x1-x0);
  const ncol=Math.floor(pw/dia),col=new Map();
  const sorted=rows.slice().sort((a,b)=>[1,0,2][a.g]-[1,0,2][b.g]||a.x-b.x);
  sorted.forEach(it=>{const c=Math.min(ncol-1,Math.max(0,Math.floor((X(it.x)-L)/dia)));if(!col.has(c))col.set(c,[]);col.get(c).push(it)});
  const maxN=Math.max(1,...Array.from(col.values(),v=>v.length));
  const plotH=Math.min(380,Math.max(120,maxN*dia)),step=Math.min(dia,(plotH-r)/Math.max(1,maxN-1||1));
  const H=top+plotH+axisH;svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('height',H);
  const base=top+plotH-r;
  /* year grid */
  const span=F.to-F.from+1,every=span>24?5:span>12?2:1;
  for(let y=F.from;y<=F.to+1;y++){const gx=X(Date.UTC(y,0,1));el('line',{class:'grid',x1:gx,x2:gx,y1:top,y2:top+plotH},svg);
    if(y<=F.to&&(y-F.from)%every===0){const t=el('text',{class:'tick',x:gx+(span===1?4:X(Date.UTC(y+1,0,1))-gx>30?(X(Date.UTC(y+1,0,1))-gx)/2:0),y:top+plotH+18,'text-anchor':span===1?'start':'middle'},svg);t.textContent=y}}
  if(span===1)for(let m=1;m<12;m++){const gx=X(Date.UTC(F.from,m,1));el('line',{class:'grid',x1:gx,x2:gx,y1:top+plotH-6,y2:top+plotH},svg);const t=el('text',{class:'tick',x:gx+2,y:top+plotH+18},svg);t.textContent=MON[m]}
  el('line',{class:'axis',x1:L,x2:W-R,y1:top+plotH,y2:top+plotH},svg);
  const g=el('g',{},svg);
  col.forEach((v,c)=>v.forEach((it,k)=>{const cx=L+c*dia+r+.5,cy=base-k*step;const n=el('circle',{class:'dot s-'+GC[it.g],cx,cy,r},g);dots.push({it,node:n,cx,cy})}));
  svg.setAttribute('aria-label',`${rows.length} instruments by publication date, ${F.from} to ${F.to}`)}
function nearest(ev){const b=svg.getBoundingClientRect(),vb=svg.viewBox.baseVal,sx=vb.width/b.width,px=(ev.clientX-b.left)*sx,py=(ev.clientY-b.top)*sx;let best=null,bd=144;
  for(const d of dots){const dx=d.cx-px,dy=d.cy-py,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;best=d}}return best&&{d:best,x:best.cx/sx,y:best.cy/sx}}
svg.addEventListener('pointermove',ev=>{if(pinned||ev.pointerType==='touch')return;const n=nearest(ev);if(n)showCard(n.d.it,n.x,n.y,false);else hideCard()});
svg.addEventListener('pointerleave',()=>{if(!pinned)hideCard()});
svg.addEventListener('click',ev=>{const n=nearest(ev);if(n)showCard(n.d.it,n.x,n.y,true);else hideCard(true)});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape')hideCard(true)});
/* year brush: histogram of every year for the current filters (ignoring the year range) */
let drag=null;
function drawBrush(all){brush.textContent='';const W=Math.max(320,chartBox.clientWidth||900),H=54,L=8,R=8,n=Y1-Y0+1,bw=(W-L-R)/n;
  brush.setAttribute('viewBox',`0 0 ${W} ${H}`);brush.setAttribute('height',H);
  brush.setAttribute('aria-valuetext',`${F.from} to ${F.to}`);brush.setAttribute('aria-valuemin',Y0);brush.setAttribute('aria-valuemax',Y1);brush.setAttribute('tabindex','0');
  const cnt=new Array(n).fill(0);all.forEach(it=>{if(it.y!=null)cnt[it.y-Y0]++});const mx=Math.max(1,...cnt),sc=v=>v?Math.max(2,Math.sqrt(v/mx)*(H-20)):0;
  cnt.forEach((v,k)=>{const h=sc(v),y=Y0+k;const b=el('rect',{class:'hb'+(y>=F.from&&y<=F.to?' in':''),x:L+k*bw+1,y:H-16-h,width:Math.max(1,bw-2),height:h},brush);const t=el('title',{},b);t.textContent=`${y}: ${v}`});
  el('rect',{class:'sel',x:L+(F.from-Y0)*bw,y:0,width:(F.to-F.from+1)*bw,height:H-16,rx:3},brush);
  for(let y=Y0;y<=Y1;y++)if(y%10===0||y===Y1){const t=el('text',{class:'tick',x:L+(y-Y0+.5)*bw,y:H-3,'text-anchor':'middle'},brush);t.textContent=y}
  brush._geo={L,bw}}
const yearAt=ev=>{const b=brush.getBoundingClientRect(),vb=brush.viewBox.baseVal,px=(ev.clientX-b.left)*vb.width/b.width,{L,bw}=brush._geo;return Math.min(Y1,Math.max(Y0,Y0+Math.floor((px-L)/bw)))};
brush.addEventListener('pointerdown',ev=>{drag={a:yearAt(ev)};brush.setPointerCapture(ev.pointerId)});
brush.addEventListener('pointermove',ev=>{if(!drag)return;const b=yearAt(ev);F.from=Math.min(drag.a,b);F.to=Math.max(drag.a,b);toForm();render(true)});
brush.addEventListener('pointerup',ev=>{if(!drag)return;const b=yearAt(ev);F.from=Math.min(drag.a,b);F.to=Math.max(drag.a,b);drag=null;toForm();writeURL(F);render()});
brush.addEventListener('keydown',ev=>{const k=ev.key;if(!['ArrowLeft','ArrowRight'].includes(k))return;ev.preventDefault();const d=k==='ArrowLeft'?-1:1;
  if(ev.shiftKey)F.to=Math.min(Y1,Math.max(F.from,F.to+d));else if(F.from+d>=Y0&&F.to+d<=Y1){F.from+=d;F.to+=d}toForm();writeURL(F);render()});
/* phone: vertical list grouped by year, newest first */
function drawList(rows){const by=new Map();rows.slice().sort((a,b)=>b.x-a.x).forEach(it=>{if(!by.has(it.y))by.set(it.y,[]);by.get(it.y).push(it)});
  let h='';by.forEach((v,y)=>{h+=`<section class="tl-year"><h3>${y}<span class="count">${v.length}</span></h3><ol>`+v.map(it=>`<li><i class="sw s-${GC[it.g]}" title="${esc(T.groups[it.g])}"></i><span class="t">${it.u?`<a href="${esc(it.u)}" target="_blank" rel="noopener">${esc(it.t)}</a>`:esc(it.t)}</span>`
    +`<span class="m">${esc(fmt(it))} · <a href="${pageURL(it)}">${esc((J[it.j]||[it.j])[0])}</a> · ${esc(it.iss||'Issuer not recorded')}</span><span class="m">${esc(ST[it.s][1])}</span></li>`).join('')+'</ol></section>'});
  list.innerHTML=h||'<p class="muted">No dated instruments match these filters.</p>'}
const phone=()=>matchMedia('(max-width:700px)').matches;
function render(light){hideCard(true);
  const all=items.filter(it=>match(it,F)),undated=all.filter(it=>it.x==null).length,dated=all.filter(it=>it.x!=null);
  const inR=dated.filter(it=>it.y>=F.from&&it.y<=F.to),out=dated.length-inR.length;
  const ctx=[F.country&&J[F.country][0],F.region,F.body&&T.bodies[F.body][0]+' members',F.cat&&CAT[catIdx(F.cat)][1],F.status&&(GROUP.includes(F.status)?T.groups[GROUP.indexOf(F.status)]:ST[stIdx(F.status)]?.[1]),F.level&&LV[lvIdx(F.level)][1]].filter(Boolean);
  status.textContent=`${inR.length.toLocaleString('en')} instrument${inR.length===1?'':'s'} published ${F.from===F.to?'in '+F.from:F.from+'–'+F.to}${ctx.length?' · '+ctx.join(' · '):''}`
    +(out?` · ${out} outside these years`:'')+` · ${undated} undated instrument${undated===1?'':'s'} excluded`+(F.country?'. Includes regional instruments that apply to this country.':'');
  drawBrush(dated);if(phone()){if(!light)drawList(inR)}else drawMain(inR)}
toForm();render();
let lastPhone=phone(),rt;addEventListener('resize',()=>{clearTimeout(rt);rt=setTimeout(()=>{const p=phone();if(p!==lastPhone){lastPhone=p}render()},120)});
window.RADAR_TIMELINE={state:()=>({...F}),count:()=>items.filter(it=>match(it,F)&&it.x!=null&&it.y>=F.from&&it.y<=F.to).length};
})();
