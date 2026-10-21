(async function(){'use strict';
const Q0=location.search; // query at load: the map's first render rewrites the URL before the restore code below reads it
const PRE=document.documentElement.lang==='ar'?'../':'',AS=window.RADAR_ASSETS||{};   // Arabic page sits one folder down
const getJSON=u=>fetch(PRE+u).then(r=>{if(!r.ok)throw new Error(u+' '+r.status);return r.json()});
let D,T,TL,F,AX;try{[D,T,TL,F,AX]=await Promise.all([getJSON(AS.data),getJSON(AS.geo),getJSON(AS.geoLo),getJSON(AS.flags),AS.ar?getJSON(AS.ar):null])}
catch(e){const l=document.getElementById('mapLoading');if(l)l.textContent='The data could not be loaded. Please reload the page.';throw e}
if(AX){window.AR_CT=AX.CT;window.AR_CD=AX.CD;window.AR_MAP=AX.MAP}   // Arabic page: tables from assets/home-ar.json
document.getElementById('mapLoading')?.remove();document.body.classList.remove('is-loading');
const $=s=>document.querySelector(s),$$=s=>Array.from(document.querySelectorAll(s)),esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])),norm=s=>String(s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
// Arabic pages: country names are matched and sorted in Arabic (i18n-ar.js defines I18N before this script runs)
const AR=document.documentElement.lang==='ar'&&window.I18N,arName=j=>AR?I18N.t(j.name):'',byName=AR?(a,b)=>arCol.compare(arName(a),arName(b)):(a,b)=>a.name.localeCompare(b.name),arCol=new Intl.Collator('ar');
const jurisdictionByID=new Map(D.jurisdictions.map(j=>[j.id,j])),instrumentByID=new Map(D.instruments.map(i=>[i.id,i])),orgByID=new Map(D.organizations.map(o=>[o.id,o]));
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
let selected=null,status='all',docType='',orgType='',body=null;
const filters=new Set();

/* ---------- classification helpers ---------- */
const TYPES=[['law','Law (binding)'],['regulation','Regulation (binding)'],['treaty','International treaty'],['mandatory','Mandatory policy (in scope)'],['guidance','Guidance & opinions'],['strategy','National strategy'],['draft','Draft / consultation']];
const TYPE_OF={binding_law:'law',binding_regulation:'regulation',international_treaty:'treaty',administrative_policy_mandatory_in_scope:'mandatory',administrative_guideline:'guidance',nonbinding_guidance:'guidance',regulatory_opinion:'guidance',voluntary_code:'guidance',national_strategy:'strategy',consultation_draft:'draft'};
const ORGS=[['legislature','Parliament / legislature'],['government','Government, cabinet & ministries'],['agency','Government agencies'],['regulator','Sector regulators'],['dpa','Data protection authorities'],['centralbank','Central banks'],['standards','Standards bodies'],['courts','Courts & justice'],['local','State & local government'],['other','Advisory, audit & other bodies']];
const ORG_OF={legislature:'legislature',parliament:'legislature',government:'government',executive:'government',ministry:'government',head_of_state:'government',government_department:'government',government_council:'government',national:'government',executive_agency:'agency',agency:'agency',government_agency:'agency',military_agency:'agency',regulator:'regulator',sector_body:'regulator',oversight_body:'regulator',cybersecurity_agency:'regulator',data_protection_authority:'dpa',central_bank:'centralbank',standards_body:'standards',judiciary:'courts',court:'courts',judicial_body:'courts',prosecution_service:'courts',attorney_general:'courts',local_government:'local',subnational_government:'local',municipal:'local'};
const typeOf=i=>TYPE_OF[i.legal_status]||'guidance';
const orgOf=i=>ORG_OF[i.authority_type||orgByID.get(i.organization_id)?.authority_type]||'other';

function flag(j){const code=(j.iso2||j.id==='EU'&&'EU'||'').toLowerCase(),src=F[code];return src?`<img class="country-flag" src="${src}" width="24" height="18" alt="${esc(j.name)} flag">`:'<span class="regional-symbol" aria-hidden="true">◈</span>'}
const nationalCache=new Map(),inheritedCache=new Map();
function national(j){if(!nationalCache.has(j.id))nationalCache.set(j.id,D.instruments.filter(i=>i.jurisdiction_id===j.id));return nationalCache.get(j.id)}
function inherited(j){if(!inheritedCache.has(j.id))inheritedCache.set(j.id,D.regional_applicability.filter(a=>a.jurisdiction_id===j.id).map(a=>instrumentByID.get(a.instrument_id)).filter(Boolean));return inheritedCache.get(j.id)}
function all(j){return [...national(j),...inherited(j)]}
function matches(i){return (!filters.size||i.categories.some(c=>filters.has(c)))&&(!docType||typeOf(i)===docType)&&(!orgType||orgOf(i)===orgType)&&(status==='all'||status==='binding'&&['binding_law','binding_regulation'].includes(i.legal_status)||status==='draft'&&i.categories.includes('drafts')||status==='reviewed'&&i.verification_level==='reviewed_primary_metadata'||status==='pending'&&i.verification_level!=='reviewed_primary_metadata')}
const filtering=()=>filters.size||docType||orgType||status!=='all';
function mapMatchCount(j){return national(j).filter(matches).length}

/* ---------- international bodies ---------- */
const BODY_MEMBERS=new Map(Object.entries(D.regional_members||{}).map(([k,v])=>[k,new Set(v)]));
D.regional_applicability.forEach(a=>{if(a.regional_jurisdiction_id==='COE')return;if(!BODY_MEMBERS.has(a.regional_jurisdiction_id))BODY_MEMBERS.set(a.regional_jurisdiction_id,new Set());BODY_MEMBERS.get(a.regional_jurisdiction_id).add(a.jurisdiction_id)});
const CETS225=D.instruments.find(i=>i.jurisdiction_id==='COE'&&i.party_status);
const C108=D.instruments.find(i=>i.jurisdiction_id==='COE'&&/Convention for the Protection of Individuals/.test(i.english_title||''));
const OECD_ADH=(D.instruments.find(i=>i.jurisdiction_id==='OECD'&&i.adherents)||{}).adherents||{};
function bodyClass(id){if(!body)return '';if(body==='OECD'){const a=OECD_ADH[id];return a?(a.member?'b-member':'b-adh'):''}if(body==='COE'){const ps=CETS225?.party_status?.[id];if(ps)return ps.status==='ratified'?'b-ratified':'b-signed';if((C108?.regional_applicability||[]).includes(id))return 'b-c108';return BODY_MEMBERS.get('COE')?.has(id)?'b-coe':''}return BODY_MEMBERS.get(body)?.has(id)?'b-member':''}

/* ---------- living map (UX phase 5): flat Equal Earth map or orthographic globe ---------- */
const svg=d3.select('#mapSvg'),zoomLayer=svg.select('#zoomLayer'),shell=$('#mapShell'),tip=$('#mapTip');
const countriesFC=topojson.feature(T.countries,T.countries.objects.countries),landFC=topojson.feature(T.land,T.land.objects.land),borders=topojson.mesh(T.countries,T.countries.objects.countries,(a,b)=>a!==b);
// low-detail copy (scripts/make_topo_lo.py): drawn while the globe moves; land always uses it on the globe
/* motion geometry also leaves out islands under ~500 km2 (invisible at globe scale); each country keeps its largest part */
/* simplification can flip a small ring's winding, which d3 reads as "everything except this ring": any polygon larger
   than a hemisphere is turned back the right way (no country or land mass is that large) */
const orient=c=>d3.geoArea({type:'Polygon',coordinates:c})>2*Math.PI?c.map(r=>r.slice().reverse()):c;
const dropIslets=f=>{const g=f.geometry;if(!g)return f;if(g.type==='Polygon')return {...f,geometry:{type:'Polygon',coordinates:orient(g.coordinates)}};if(g.type!=='MultiPolygon')return f;const P=g.coordinates.map(orient),A=P.map(c=>d3.geoArea({type:'Polygon',coordinates:c})),m=Math.max(...A);return {...f,geometry:{type:'MultiPolygon',coordinates:P.filter((c,k)=>A[k]>=1.2e-5||A[k]===m)}}};
const countriesLo=new Map(topojson.feature(TL.countries,TL.countries.objects.countries).features.map(f=>[f.id,dropIslets(f)])),landLo=dropIslets(topojson.feature(TL.land,TL.land.objects.land).features?{type:'Feature',geometry:{type:'MultiPolygon',coordinates:topojson.feature(TL.land,TL.land.objects.land).features.flatMap(f=>f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[f.geometry.coordinates])}}:topojson.feature(TL.land,TL.land.objects.land)),bordersLo=topojson.mesh(TL.countries,TL.countries.objects.countries,(a,b)=>a!==b);
await new Promise(r=>setTimeout(r));   // yield: keep start-up in short tasks (no multi-second freeze on phones)
const flat=d3.geoEqualEarth(),globe=d3.geoOrthographic().clipAngle(90).precision(.5),graticule=d3.geoGraticule10();
let mode='map',projection=flat;const path=d3.geoPath(flat);
const countryPaths=new Map(),centers=new Map(),geoCenters=new Map(),featureByID=new Map(countriesFC.features.map(f=>[f.id,f]));
let width=0,height=0,transform=d3.zoomIdentity,globeK=1,rot=[-30,-18],spinTimer=null,userMoved=false,pinned=null,lastPointer='mouse';
const ROOT=document.documentElement.lang==='ar'?'../':'';                 // Arabic page sits one folder down
const PH=JSON.parse(document.getElementById('photos')?.textContent||'{}'),ARM=window.AR_MAP||{};
const BINDING=new Set(['binding_law','binding_regulation','international_treaty','administrative_policy_mandatory_in_scope']);
const kindOf=i=>i.legal_status==='consultation_draft'?'draft':BINDING.has(i.legal_status)?'binding':'soft';
/* documents recorded: single-hue ramp, breaks 1/3/6/11/21/51/101+ (it counts documents; it does not rate governance) */
const BREAKS=[1,3,6,11,21,51,101],RAMP=d3.quantize(d3.interpolateLab('#3a4a8f','#8bbcc4'),7),ZERO='#2a3363';
const shade=n=>{if(!n)return ZERO;let k=0;while(k<6&&n>=BREAKS[k+1])k++;return RAMP[k]};
const docCount=j=>national(j).length;
/* government actions (kind "world") in the last 30 days */
/* days since a date, counted from local midnight today in the reader's browser (not the build date); inLast(d,30) = today and the 29 days before */
const DAY=864e5,TODAY=(()=>{const t=new Date();t.setHours(0,0,0,0);return t.getTime()})(),fullDate=d=>d.length===4?d+'-12-31':d.length===7?d+'-28':d,ageOf=d=>d?Math.round((TODAY-new Date(fullDate(d)+'T00:00:00').getTime())/DAY):1e9,inLast=(d,n)=>{const a=ageOf(d);return a>=0&&a<n};
/* pulses follow the Updates window (30/60/90 days, default 30); state/provincial actions sit in their country's changes */
let winDays=(()=>{const d=new URLSearchParams(Q0).get('days');return ['30','60','90'].includes(d)?+d:30})();
const recent=new Map(),recentItems=new Map();
function countRecent(){recent.clear();recentItems.clear();D.changes.forEach(c=>{const id=c.jurisdiction_id;if(c.kind!=='world'||jurisdictionByID.get(id)?.type!=='country'||!inLast(c.date,winDays))return;if(!recentItems.has(id))recentItems.set(id,[]);recentItems.get(id).push(c)});recentItems.forEach((ev,id)=>recent.set(id,groupDocs(ev).length))}
/* one entry per document: a document's milestones (adopted, published, in force...) are grouped by instrument_id; events without one stay single; newest first */
function groupDocs(events){const m=new Map();events.forEach(c=>{const k=c.instrument_id?c.jurisdiction_id+'|'+c.instrument_id:'c|'+c.id;if(!m.has(k))m.set(k,{key:k,jid:c.jurisdiction_id,inst:instrumentByID.get(c.instrument_id)||null,events:[]});m.get(k).events.push(c)});
  const out=[...m.values()];out.forEach(g=>{g.events.sort((a,b)=>(a.date||'').localeCompare(b.date||''));g.latest=g.events[g.events.length-1];g.date=g.latest.date;g.review=g.events.some(c=>c.needs_review)});return out.sort((a,b)=>(b.date||'').localeCompare(a.date||''))}
countRecent();
/* "What's new" panel and pulse legend labels: English here, translated on Arabic pages by site/i18n/ar.json (checked by check_ar_charts.py) */
const WN_L=/*WN_L*/{"legend":"Updates in the last {d} days","n1":"1 document with updates in the last {d} days","n":"{n} documents with updates in the last {d} days","sub":"{s} of {n} are state/provincial-level","more":"+ {m} more on the country profile","open":"Open country profile →","src":"Official source ↗","close":"Close","aria":"{c}: updates in the last {d} days","pulse1":"{c}: 1 document with updates in the last {d} days","pulse":"{c}: {n} documents with updates in the last {d} days","card1":"1 document with updates in the last {d} days","card":"{n} documents with updates in the last {d} days","published":"Published","adopted":"Adopted","applied":"In force","consultation":"Consultation opened","revised":"Amended","superseded":"Superseded","repealed":"Repealed","event":"Event","binding":"Binding or mandatory","soft":"Non-binding","draft":"Draft"}/*/WN_L*/;
const L=(k,o={})=>WN_L[k].replace(/\{(\w)\}/g,(_,x)=>o[x]??'');
const pulseR=n=>Math.sqrt(Math.min(Math.max(n,1),10));
const hasPulse=id=>recent.has(id)&&countryPaths.has(id)&&!countryPaths.get(id).classList.contains('is-dim');
const zoom=d3.zoom().scaleExtent([1,48]).filter(e=>mode==='map'&&(!e.ctrlKey||e.type==='wheel')&&!e.button).on('zoom',e=>{transform=e.transform;zoomLayer.attr('transform',transform);shell.style.setProperty('--k',transform.k);placeRadar();placeRings();if(pinned)placeCard(pinned)});
const LP=new Map();function largestPart(f){if(!LP.has(f))LP.set(f,largestPart0(f));return LP.get(f)}
function largestPart0(f){if(f.geometry.type!=='MultiPolygon')return f;let best=null,max=-1;for(const c of f.geometry.coordinates){const g={type:'Feature',geometry:{type:'Polygon',coordinates:c}},a=d3.geoArea(g);if(a>max){max=a;best=g}}return best}
const narrow=matchMedia('(max-width:760px)');
function layout(){const r=shell.getBoundingClientRect();width=Math.max(280,r.width);const S={type:'Sphere'};path.projection(flat);
  if(narrow.matches){flat.fitWidth(width-12,S);const lg=$('#mapLegend'),[[,y0],[,y1]]=path.bounds(S),top=48,bottom=46+(lg&&!lg.hidden?lg.offsetHeight+6:0)+(typeof pulseLegend!=='undefined'&&pulseLegend.offsetHeight?pulseLegend.offsetHeight+6:0);height=Math.ceil(y1-y0)+top+bottom;flat.fitExtent([[6,top],[width-6,height-bottom]],S);shell.style.height=height+'px';shell.style.minHeight='0'}
  else{shell.style.height='';shell.style.minHeight='';height=Math.max(260,r.height);flat.fitExtent([[10,10],[width-10,height-10]],S)}
  countriesFC.features.forEach(f=>centers.set(f.id,path.centroid(largestPart(f))));
  globe.translate([width/2,height/2]).scale(baseR()*globeK).rotate(rot);
  path.projection(projection);svg.attr('viewBox',`0 0 ${width} ${height}`);zoom.extent([[0,0],[width,height]]).translateExtent([[-width*.1,-height*.1],[width*1.1,height*1.1]]);render();placeRadar();placePulseLegend()}
const baseR=()=>Math.max(80,Math.min(width,height)/2-22);
let moving=false,idleT=0,rafPending=false;
function motion(){moving=true;clearTimeout(idleT);idleT=setTimeout(()=>{moving=false;if(mode==='globe')render()},150)}
function frame(){motion();if(rafPending)return;rafPending=true;requestAnimationFrame(()=>{rafPending=false;render()})}
/* globe: a country whose whole outline lies on the far side is skipped without projecting it (centre + angular radius,
   computed once); while moving the outline is resampled more coarsely (precision 2 px instead of 0.5 px) */
const CULL=new Map();function cullOf(f){if(!CULL.has(f.id)){const c=d3.geoCentroid(f);let r=0;const walk=a=>{if(typeof a[0]==='number'){const d=d3.geoDistance(c,a);if(d>r)r=d}else a.forEach(walk)};walk(f.geometry.coordinates);CULL.set(f.id,{c,r})}return CULL.get(f.id)}
function render(){const g=mode==='globe',lo=g&&moving;globe.precision(lo?2:.5);svg.select('#sphere').attr('d',path({type:'Sphere'}));svg.select('#graticule').attr('d',g?path(graticule):null);svg.select('#land').attr('d',path(g?landLo:landFC));
  const vc=[-rot[0],-rot[1]];
  countriesFC.features.forEach(f=>{const el=countryPaths.get(f.id);if(!el)return;if(g){const q=cullOf(f);if(d3.geoDistance(q.c,vc)>Math.PI/2+q.r+.02){if(el.getAttribute('d'))el.setAttribute('d','');return}}el.setAttribute('d',path(lo?countriesLo.get(f.id)||f:f)||'')});
  svg.select('#borders').attr('d',path(lo?bordersLo:borders));
  const [cx,cy]=globe.translate(),R=globe.scale();svg.select('#globeGlow').attr('cx',cx).attr('cy',cy).attr('r',g?R*1.16:0);placeRings();if(pinned)placeCard(pinned)}
function initMap(){const g=zoomLayer.select('#countries').node();countriesFC.features.forEach(f=>{const j=jurisdictionByID.get(f.id);if(!j)return;geoCenters.set(f.id,d3.geoCentroid(largestPart(f)));const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('class','country');p.dataset.iso=f.id;p.setAttribute('tabindex','0');p.setAttribute('role','button');p.setAttribute('aria-label',j.name);
    p.addEventListener('pointerdown',e=>{lastPointer=e.pointerType});p.addEventListener('pointerenter',e=>{if(panel.hidden)showTip(j,e)});p.addEventListener('pointermove',e=>moveTip(e));p.addEventListener('pointerleave',hideTip);
    p.addEventListener('click',e=>{if(hasPulse(f.id)){openUpdates(f.id,e);return}if(lastPointer==='touch'&&pinned!==f.id){pin(f.id);return}select(f.id)});p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();if(hasPulse(f.id))openUpdates(f.id,null);else select(f.id)}});g.appendChild(p);countryPaths.set(f.id,p)});
  layout();svg.call(zoom).on('dblclick.zoom',null);
  svg.call(d3.drag().filter(e=>mode==='globe'&&!e.button).on('start',()=>{stopSpin();svg.classed('is-dragging',true)}).on('drag',e=>{const k=.28/globeK;rot=[rot[0]+e.dx*k,Math.max(-80,Math.min(80,rot[1]-e.dy*k))];globe.rotate(rot);frame()}).on('end',()=>svg.classed('is-dragging',false)));
  svg.on('wheel.globe',e=>{if(mode!=='globe')return;e.preventDefault();stopSpin();setGlobeK(globeK*Math.exp(-e.deltaY*.0015),0)},{passive:false});
  svg.on('pointerdown.spin',()=>{if(mode==='globe')stopSpin()});
  new ResizeObserver(()=>{layout();placePanel()}).observe(shell);
  $('#zoomIn').onclick=()=>mode==='globe'?setGlobeK(globeK*1.6):svg.transition().duration(reduced.matches?0:250).call(zoom.scaleBy,1.8);
  $('#zoomOut').onclick=()=>mode==='globe'?setGlobeK(globeK/1.6):svg.transition().duration(reduced.matches?0:250).call(zoom.scaleBy,1/1.8);
  $('#zoomReset').onclick=()=>resetMap();
  $$('[data-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.mode));
  shell.addEventListener('click',e=>{if(pinned&&!e.target.closest('.country,.map-tip,.latest-strip'))unpin()});
  buildLatest();applyHighlight()}
function setGlobeK(k,ms=250){stopSpin();const k0=globeK,k1=Math.max(.8,Math.min(9,k));if(reduced.matches){globeK=k1;globe.scale(baseR()*globeK);render();return}if(!ms){globeK=k1;globe.scale(baseR()*globeK);frame();return}d3.transition().duration(ms).tween('gk',()=>{const i=d3.interpolate(k0,k1);return t=>{globeK=i(t);globe.scale(baseR()*globeK);motion();render()}})}
function setMode(m){if(m===mode)return;mode=m;unpin();hideTip();closeUpdates();$$('[data-mode]').forEach(b=>{const on=b.dataset.mode===m;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on))});shell.classList.toggle('is-globe',m==='globe');
  if(m==='globe'){transform=d3.zoomIdentity;zoomLayer.attr('transform',null);projection=globe}else{projection=flat;zoomLayer.attr('transform',transform)}
  path.projection(projection);render();placeRadar();applyHighlight();if(m==='globe')startSpin();else stopSpin()}
let mapVisible=true;
const spinOK=()=>mode==='globe'&&!shell.hidden&&mapVisible&&!document.hidden;
function startSpin(){if(reduced.matches||userMoved||spinTimer||!spinOK())return;let last=null;spinTimer=d3.timer(t=>{if(!spinOK()){pauseSpin();return}const dt=last===null?0:t-last;last=t;rot=[rot[0]+dt*.006,rot[1]];globe.rotate(rot);motion();render()})}
function pauseSpin(){if(spinTimer){spinTimer.stop();spinTimer=null}}
new IntersectionObserver(es=>{mapVisible=es[es.length-1].isIntersecting;if(mapVisible)startSpin();else pauseSpin()}).observe(shell);
document.addEventListener('visibilitychange',()=>{if(document.hidden)pauseSpin();else startSpin()});
function stopSpin(){userMoved=true;if(spinTimer){spinTimer.stop();spinTimer=null}}
function resetMap(){unpin();if(mode==='globe'){rot=[-30,-18];globe.rotate(rot);setGlobeK(1,reduced.matches?0:300)}else svg.transition().duration(reduced.matches?0:300).call(zoom.transform,d3.zoomIdentity)}
/* smooth zoom (map) or rotation (globe) to a country, about 650 ms */
function focusCountry(id,done){const f=featureByID.get(id),end=()=>{if(done)done()};if(!f||shell.hidden){end();return}
  if(mode==='globe'){stopSpin();const [lon,lat]=geoCenters.get(id)||d3.geoCentroid(f),r0=rot.slice(),r1=[-lon,Math.max(-80,Math.min(80,-lat))],k0=globeK,k1=Math.max(globeK,1.6);
    if(reduced.matches){rot=r1;globeK=k1;globe.rotate(rot).scale(baseR()*globeK);render();end();return}
    d3.transition().duration(650).ease(d3.easeCubicInOut).tween('rot',()=>{const i=d3.interpolate(r0,r1),z=d3.interpolate(k0,k1);return t=>{rot=i(t);globeK=z(t);globe.rotate(rot).scale(baseR()*globeK);motion();render()}}).on('end',end).on('interrupt',end);return}
  const [[x0,y0],[x1,y1]]=d3.geoPath(flat).bounds(largestPart(f)),k=Math.max(1,Math.min(12,.55/Math.max((x1-x0)/width,(y1-y0)/height))),t=d3.zoomIdentity.translate(width/2,height/2).scale(k).translate(-(x0+x1)/2,-(y0+y1)/2);
  if(reduced.matches){svg.call(zoom.transform,t);end();return}svg.transition().duration(650).ease(d3.easeCubicInOut).call(zoom.transform,t).on('end',end).on('interrupt',end)}
const zoomTo=id=>focusCountry(id);
/* screen position of a country's centre; null when it is on the far side of the globe */
function screenPos(id){if(mode==='globe'){const c=geoCenters.get(id);if(!c||d3.geoDistance(c,[-rot[0],-rot[1]])>Math.PI/2-.05)return null;return globe(c)}const c=centers.get(id);return c&&!isNaN(c[0])?transform.apply(c):null}
/* orange pulses: government actions in the Updates window, area ∝ count (capped at 10); larger ones drawn first so small ones stay clickable */
function placeRings(){const g=svg.select('#rings');let hits=svg.select('#ringHits');if(hits.empty())hits=svg.insert('g','#rings').attr('id','ringHits');
  const data=[...recent.keys()].filter(hasPulse).map(id=>({id,n:recent.get(id),p:screenPos(id)})).filter(d=>d.p);
  const open=(ev,d)=>{ev.stopPropagation();openUpdates(d.id,ev)},enter=(ev,d)=>{const j=jurisdictionByID.get(d.id);if(j&&panel.hidden)showTip(j,ev)};
  /* invisible hit circles sit in a layer beneath every core, so a core always takes the click and the hit areas only fill the gaps */
  const hs=hits.selectAll('circle.ring-hit').data(data,d=>d.id);hs.exit().remove();
  hs.enter().append('circle').attr('class','ring-hit').attr('aria-hidden','true').on('click',open).on('pointerenter',enter).on('pointermove',ev=>moveTip(ev)).on('pointerleave',()=>hideTip())
   .merge(hs).attr('r',d=>Math.max(11,8*pulseR(d.n)).toFixed(1)).attr('cx',d=>d.p[0].toFixed(1)).attr('cy',d=>d.p[1].toFixed(1));
  hits.selectAll('circle.ring-hit').sort((a,b)=>b.n-a.n);
  const s=g.selectAll('g.ring').data(data,d=>d.id);s.exit().remove();
  const e=s.enter().append('g').attr('class','ring').attr('role','button').attr('tabindex','0');
  e.append('circle').attr('class','ring-pulse');e.append('circle').attr('class','ring-core');e.append('text').attr('class','ring-n').attr('dy','0.35em');
  e.on('click',open).on('keydown',(ev,d)=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();openUpdates(d.id,ev)}})
   .on('pointerenter',enter).on('pointermove',ev=>moveTip(ev)).on('pointerleave',()=>hideTip());
  const m=e.merge(s);
  m.attr('aria-label',d=>L(d.n===1?'pulse1':'pulse',{c:jurisdictionByID.get(d.id)?.name,n:d.n,d:winDays}));
  m.select('.ring-pulse').attr('r',d=>(8*pulseR(d.n)).toFixed(1));
  m.select('.ring-core').attr('r',d=>(4.2*pulseR(d.n)).toFixed(1));
  m.select('.ring-n').text(d=>d.n>=3?(d.n>99?'99+':d.n):'');
  m.attr('transform',d=>`translate(${d.p[0].toFixed(1)},${d.p[1].toFixed(1)})`);
  g.selectAll('g.ring').sort((a,b)=>b.n-a.n)}
/* legend for pulse sizes (bottom end corner of the map, phones too) */
const pulseLegend=document.createElement('div');pulseLegend.className='pulse-legend';pulseLegend.setAttribute('aria-hidden','true');shell.appendChild(pulseLegend);
function renderPulseLegend(){pulseLegend.innerHTML=`<b>${esc(L('legend',{d:winDays}))}</b><div class="sz">`+[1,5,10].map(n=>{const r=4.2*pulseR(n);return `<span><i style="width:${(r*2).toFixed(0)}px;height:${(r*2).toFixed(0)}px"></i>${n===10?'10+':n}</span>`}).join('')+'</div>'}
/* phones: the documents legend spans the bottom, so the size legend sits just above it (bottom end corner) */
function placePulseLegend(){const lg=$('#mapLegend');pulseLegend.style.bottom=narrow.matches&&lg&&!lg.hidden?(lg.offsetTop>0?shell.clientHeight-lg.offsetTop+6:46)+'px':''}
renderPulseLegend();
/* "What's new" panel: a country's government actions in the Updates window (beside the click; bottom sheet on phones) */
const panel=document.createElement('div');panel.className='wn-panel';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','false');panel.tabIndex=-1;shell.appendChild(panel);
const ACT={published:'published',adopted:'adopted',applied:'applied',consultation:'consultation',revised:'revised',superseded:'superseded',repealed:'repealed',event:'event'};
const SUBN=new Set(['subnational','local']);
const fmtShort=d=>{if(!d)return '';if(d.length<10)return fmtDate(d);return new Date(d+'T00:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})};
let wnFor=null,wnReturn=null,wnAt=null;
const THIS_YEAR=String(new Date(TODAY).getFullYear());
/* short milestone date: day and month (year only when it is not this year); Arabic month names on Arabic pages */
const dayMonth=d=>{if(!d||d.length<10)return fmtDate(d);let t=fmtShort(d);if(AR&&I18N.date&&I18N.date(t))t=I18N.date(t);return d.slice(0,4)===THIS_YEAR?t.replace(/ \d{4}$/,''):t};
/* Arabic pages: an issuing body's Arabic name where the site has one (build.py AR_MAP.issuers), else the name as published */
const issuerName=(s,j)=>{const k=String(s||'').trim(),m=ROOT&&ARM.issuers;return (m&&(m[j+'|'+k]||m[k]||m[k.replace(/\s*\([^()]*\)\s*$/,'')]))||s};
function groupTitle(g){if(g.inst)return docTitle(g.inst);const CT=window.AR_CT||{};return CT[g.latest.id]||g.latest.title||''}
function msHTML(g){return g.events.map(c=>`<span class="ms"><b>${esc(L(ACT[c.type]||'event'))}</b> <span class="ms-d">${esc(dayMonth(c.date))}</span></span>`).join('<span class="ms-sep" aria-hidden="true"> · </span>')}
function profileURL(id){const p=new URLSearchParams(location.search);p.delete('view');if(winDays!==30)p.set('days',winDays);else p.delete('days');const s=p.toString();return (jurisdictionByID.get(id)?.type!=='country'?'body/':'country/')+id+'/'+(s?'?'+s:'')}
function openUpdates(id,ev){const j=jurisdictionByID.get(id),docs=groupDocs(recentItems.get(id)||[]);if(!j||!docs.length){select(id);return}
  const same=!panel.hidden&&wnFor===id;if(!same)wnReturn=document.activeElement;unpin();hideTip();
  const n=docs.length,sub=docs.filter(g=>SUBN.has(g.inst?.government_level)).length,shown=docs.slice(0,8);
  panel.innerHTML=`<div class="wn-h"><div><h3>${flag(j)}<span>${esc(j.name)}</span></h3><p class="wn-n">${esc(L(n===1?'n1':'n',{n,d:winDays}))}</p>${sub?`<p class="wn-sub">${esc(L('sub',{s:sub,n}))}</p>`:''}</div><button class="wn-x" type="button" aria-label="${esc(L('close'))}">×</button></div>`
   +`<ul class="wn-list">${shown.map(g=>{const i=g.inst,iss=i&&(i.issuing_authority||i.publisher_name),src=g.latest.source_url||i?.source_url,k=i&&kindOf(i);
      return `<li><div class="wn-meta"><span>${esc(fmtShort(g.date))}</span>${k?`<span class="wn-chip ${k==='binding'?'b':k==='draft'?'d':'n'}">${esc(L(k))}</span>`:''}</div>`
       +`<div class="wn-ms">${msHTML(g)}</div><div class="wn-t" dir="auto">${esc(groupTitle(g))}</div>`+(iss?`<div class="wn-iss" dir="auto">${esc(issuerName(iss,i.jurisdiction_id))}</div>`:'')
       +(src?`<a class="wn-src" href="${esc(src)}" target="_blank" rel="noopener noreferrer">${esc(L('src'))}</a>`:'')+'</li>'}).join('')}`
   +(n>shown.length?`<li class="wn-more">${esc(L('more',{m:n-shown.length}))}</li>`:'')+'</ul>'
   +`<div class="wn-f"><a href="${esc(profileURL(id))}">${esc(L('open'))}</a></div>`;
  panel.setAttribute('aria-label',L('aria',{c:j.name,d:winDays}));panel.hidden=false;wnFor=id;
  if(ev&&ev.clientX>0)wnAt=[ev.clientX-shell.getBoundingClientRect().left,ev.clientY-shell.getBoundingClientRect().top];else if(!same||!wnAt){const p=screenPos(id);wnAt=p||[width/2,height/2]}
  placePanel();panel.querySelector('.wn-x').onclick=closeUpdates;panel.querySelector('.wn-x').focus()}
function placePanel(){if(panel.hidden)return;if(narrow.matches){panel.style.left=panel.style.top='';return}const r=shell.getBoundingClientRect(),w=panel.offsetWidth,h=panel.offsetHeight,rtl=document.documentElement.dir==='rtl',[x,y]=wnAt;
  let Lx=rtl?x-w-18:x+18;if(Lx+w>r.width-12||Lx<12)Lx=rtl?x+18:x-w-18;Lx=Math.max(12,Math.min(r.width-w-12,Lx));let Ty=Math.max(12,Math.min(r.height-h-12,y-40));panel.style.left=Lx+'px';panel.style.top=Ty+'px'}
function closeUpdates(){if(panel.hidden)return;panel.hidden=true;wnFor=null;const r=wnReturn;wnReturn=null;if(r&&document.contains(r)&&r.focus)try{r.focus()}catch(e){}}
addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)closeUpdates()});
document.addEventListener('pointerdown',e=>{if(!panel.hidden&&!panel.contains(e.target)&&!e.target.closest('#rings g.ring,#ringHits,.country'))closeUpdates()});
/* the Updates window selector (changelog.js) resizes pulses, the legend and an open panel */
addEventListener('radar:days',e=>{const d=+e.detail;if(![30,60,90].includes(d)||d===winDays)return;winDays=d;countRecent();renderPulseLegend();placeRings();if(wnFor){const id=wnFor;if(recent.has(id))openUpdates(id,null);else closeUpdates()}})
/* hover / tap card */
const fmtDate=d=>{if(!d)return '';if(d.length===4)return d;const x=new Date((d.length===7?d+'-01':d)+'T00:00:00');return x.toLocaleDateString('en-GB',d.length===7?{month:'long',year:'numeric'}:{day:'numeric',month:'long',year:'numeric'})};
const isAr=s=>/[؀-ۿ]/.test(s||'');
function latestDoc(j){let best=null;for(const i of national(j)){if(i.publication_date&&(!best||i.publication_date>best.publication_date))best=i}return best}
function docTitle(i){if(ROOT&&isAr(i.official_title))return i.official_title;return (ROOT&&ARM.titles&&ARM.titles[i.id])||i.english_title||i.official_title||''}
function cardHTML(j,pinnedCard){const ph=PH[j.id],n=national(j),k={binding:0,soft:0,draft:0};n.forEach(i=>k[kindOf(i)]++);const r=recent.get(j.id)||0,last=latestDoc(j),extra=[];
  if(body){const c=bodyClass(j.id);extra.push(`<div class="tip-match">${{'b-member':'Member of '+esc(jurisdictionByID.get(body)?.short_name||body)+(body==='OECD'?' · adheres to the AI Recommendation':''),'b-adh':'Non-member adherent to the OECD AI Recommendation','b-ratified':'CETS 225: ratified','b-signed':'CETS 225: signed','b-c108':'Convention 108 party'+(BODY_MEMBERS.get('COE')?.has(j.id)?' · CoE member':' · not a CoE member'),'b-coe':'Council of Europe member (no CETS 225 or Convention 108 status recorded)'}[c]||'Not shown as a member'}</div>`)}
  else if(filtering()){const m=mapMatchCount(j);extra.push(`<div class="tip-match">${m} matching document${m===1?'':'s'}</div>`)}
  return (ph?`<figure class="card-photo"><img src="${ROOT}${esc(ph.file)}" width="640" height="360" alt="" loading="lazy" decoding="async"><figcaption>${esc((ROOT&&ARM.captions&&ARM.captions[j.id])||ph.caption||'')}</figcaption></figure>`:'')
   +`<div class="card-body"><strong>${flag(j)}<span>${esc(j.name)}</span></strong>${extra.join('')}`
   +`<div class="card-counts"><span class="cc cc-b"><b>${k.binding}</b><span>Binding or mandatory</span></span><span class="cc cc-n"><b>${k.soft}</b><span>Non-binding</span></span><span class="cc cc-d"><b>${k.draft}</b><span>Drafts</span></span></div>`
   +(r?`<div class="card-actions"><i class="ring-sw"></i><span>${esc(L(r===1?'card1':'card',{n:r,d:winDays}))}</span></div>`:'')
   +(last?`<div class="card-latest"><span class="card-k">Latest document</span><span class="card-t" dir="auto">${esc(docTitle(last))}</span><span class="card-d">${esc(fmtDate(last.publication_date))}</span></div>`:'')
   +(pinnedCard?`<a class="card-open" href="${pageURL(j.id)}">Open country page →</a>`:'')+'</div>'}
function showTip(j,e){if(e.pointerType==='touch'||pinned)return;tip.innerHTML=cardHTML(j,false);tip.hidden=false;tip.classList.remove('is-pinned');moveTip(e);countryPaths.get(j.id)?.classList.add('is-hover')}
function moveTip(e){if(tip.hidden||pinned)return;const r=shell.getBoundingClientRect();placeAt(e.clientX-r.left,e.clientY-r.top)}
function placeAt(x,y){const r=shell.getBoundingClientRect(),w=tip.offsetWidth,h=tip.offsetHeight;let L=x+16;if(L+w>r.width-8)L=x-w-16;tip.style.left=Math.max(8,L)+'px';tip.style.top=Math.max(8,Math.min(r.height-h-8,y-h/2))+'px'}
function hideTip(){if(pinned)return;tip.hidden=true;$$('.country.is-hover').forEach(p=>p.classList.remove('is-hover'))}
function pin(id){const j=jurisdictionByID.get(id);if(!j)return;pinned=id;tip.innerHTML=cardHTML(j,true);tip.hidden=false;tip.classList.add('is-pinned');$$('.country.is-hover').forEach(p=>p.classList.remove('is-hover'));countryPaths.get(id)?.classList.add('is-hover');placeCard(id)}
function placeCard(id){const p=screenPos(id);if(!p){placeAt(width/2,height/2);return}placeAt(p[0],p[1])}
function unpin(){if(!pinned)return;countryPaths.get(pinned)?.classList.remove('is-hover');pinned=null;tip.hidden=true;tip.classList.remove('is-pinned')}
function syncURL(){const p=new URLSearchParams();if(filters.size)p.set('cat',[...filters].join(','));if(docType)p.set('type',docType);if(orgType)p.set('org',orgType);if(status!=='all')p.set('status',status);if(body)p.set('body',body);if(!$('#updatesView').hidden){p.set('view','updates');const d=window.RADAR_TEST?.updDays?.()??new URLSearchParams(Q0).get('days');if(d&&d!=='30')p.set('days',d)}const s=p.toString();history.replaceState(null,'',location.pathname+(s?'?'+s:'')+location.hash)}
function applyHighlight(){const fil=filtering();let n=0;countryPaths.forEach((p,id)=>{const j=jurisdictionByID.get(id);p.style.setProperty('--fill',shade(docCount(j)));p.classList.remove('is-match','is-dim','b-member','b-signed','b-ratified','b-c108','b-coe','b-adh');p.classList.toggle('is-selected',id===selected);p.setAttribute('aria-pressed',String(id===selected));if(body){const c=bodyClass(id);if(c){p.classList.add(c);n++}else p.classList.add('is-dim')}else if(fil){if(mapMatchCount(j)){p.classList.add('is-match');n++}else p.classList.add('is-dim')}});
  const cap=$('#scanStatus');if(body){const j=jurisdictionByID.get(body),mm=BODY_MEMBERS.get(body);cap.textContent=`${(j?.name||body).toUpperCase()} · ${mm?mm.size+' MEMBER STATES · ':''}${n} COUNTR${n===1?'Y':'IES'} HIGHLIGHTED`}else if(fil){const parts=[...[...filters].map(k=>D.categories[k]),docType&&TYPES.find(t=>t[0]===docType)[1],orgType&&ORGS.find(o=>o[0]===orgType)[1],status!=='all'&&$('#statusFilter').selectedOptions[0].text].filter(Boolean);cap.textContent=`${n} countr${n===1?'y':'ies'} match · ${parts.join(' · ')}`}else cap.textContent=mode==='globe'?'GLOBE · GOVERNMENT AI GOVERNANCE':'EQUAL EARTH · GOVERNMENT AI GOVERNANCE';
  renderLegend(fil);if(narrow.matches&&!shell.hidden&&width)layout();placeRings();if(pinned)pin(pinned);syncURL()}
function renderLegend(fil){const box=$('#mapLegend');box.classList.toggle('legend-shade',!fil&&!body);if(body==='OECD'){box.innerHTML='<span><i class="sw b-member"></i>OECD members (all adhere to the AI Recommendation)</span><span><i class="sw b-adh"></i>Non-member adherents</span>';box.hidden=false}else if(body==='COE'){box.innerHTML='<span><i class="sw b-ratified"></i>CETS 225 ratified</span><span><i class="sw b-signed"></i>CETS 225 signed</span><span><i class="sw b-c108"></i>Convention 108 party only</span><span><i class="sw b-coe"></i>CoE member, neither</span>';box.hidden=false}else if(body){box.innerHTML=`<span><i class="sw b-member"></i>${esc(jurisdictionByID.get(body)?.short_name||body)} members</span>`;box.hidden=false}
  if(body){box.insertAdjacentHTML('beforeend',`<a class="legend-link" href="${pageURL(body)}">Open ${esc(jurisdictionByID.get(body)?.short_name||body)} page →</a>`)}
  else if(fil){box.innerHTML=`<span><i class="sw is-match"></i>Matching documents</span><span><i class="sw is-dim"></i>No match</span>`;box.hidden=false}
  else{const lab=['0','1–2','3–5','6–10','11–20','21–50','51–100','101+'],col=[ZERO,...RAMP];box.innerHTML=`<div class="lg-head">Documents recorded</div><div class="ramp">${col.map((c,k)=>`<span class="rk"><i style="background:${c}"></i><small>${lab[k]}</small></span>`).join('')}</div><div class="lg-note">Counts documents recorded; it does not rate the quality of governance.</div>`;box.hidden=false}}
/* radar sweep: flat map only, about 7 s per turn (CSS animation) */
function origin(){const p=flat([0,0])||[width/2,height/2];return transform.apply(p)}
function placeRadar(){const o=origin(),sw=$('#sweep');const r=Math.hypot(width,height);sw.style.width=sw.style.height=(r*2)+'px';sw.style.left=o[0]+'px';sw.style.top=o[1]+'px'}
function startAnimation(){if(mode==='globe')startSpin()}
reduced.addEventListener('change',()=>{if(reduced.matches)stopSpin()});
/* "Latest" strip: the 12 most recent government actions */
function buildLatest(){const box=$('#latestTrack');if(!box)return;const items=groupDocs(D.changes.filter(c=>c.kind==='world'&&jurisdictionByID.get(c.jurisdiction_id)?.type==='country'&&ageOf(c.date)>=0)).slice(0,12);
  const one=g=>{const j=jurisdictionByID.get(g.jid);return `<button type="button" class="ls-item" data-latest="${j.id}">${flag(j)}<span class="ls-name">${esc(j.name)}</span><span class="ls-title" dir="auto">${esc(groupTitle(g))}</span><span class="ls-date">${esc(fmtDate(g.date))}</span></button>`};
  const html=items.map(one).join('');box.innerHTML=`<div class="ls-set">${html}</div><div class="ls-set ls-dup" aria-hidden="true">${html}</div>`;
  box.querySelectorAll('.ls-dup button').forEach(b=>b.tabIndex=-1);
  box.querySelectorAll('[data-latest]').forEach(b=>b.onclick=e=>{e.stopPropagation();const id=b.dataset.latest;showView('map');focusCountry(id,()=>pin(id))})}
function pageURL(id){const j=jurisdictionByID.get(id);return (j&&j.type!=='country'?'body/':'country/')+id+'/'+location.search}
/* click a country, a search result or an update: zoom (map) or rotate (globe), then open its page */
function select(id){let gone=false;const go=()=>{if(gone)return;gone=true;location.href=pageURL(id)};if(jurisdictionByID.get(id)?.type!=='country'||reduced.matches){go();return}
  if($('#mapShell').hidden){showView('map');requestAnimationFrame(()=>{layout();focusCountry(id,go)})}else focusCountry(id,go);setTimeout(go,1400)}

/* ---------- views (Map / Updates) ---------- */
function showView(v){$$('[data-view]').forEach(b=>{const on=b.dataset.view===v;b.classList.toggle('active',on);b.setAttribute('aria-selected',String(on))});$('#mapShell').hidden=v!=='map';if($('#latestStrip'))$('#latestStrip').hidden=v!=='map';$('#updatesView').hidden=v!=='updates';if(v==='updates')window.dispatchEvent(new CustomEvent('radar:updates'));syncURL()}
$$('[data-view]').forEach(b=>b.onclick=()=>showView(b.dataset.view));

/* ---------- sidebar filters ---------- */
function refreshFilters(){applyHighlight()}
Object.entries(D.categories).filter(([c])=>c!=='historical'&&c!=='international').forEach(([c,label])=>{const b=document.createElement('button');b.className='chip';b.dataset.cat=c;b.textContent=label;b.setAttribute('aria-pressed','false');b.onclick=()=>{filters.has(c)?filters.delete(c):filters.add(c);b.classList.toggle('active',filters.has(c));b.setAttribute('aria-pressed',String(filters.has(c)));setBody(null);refreshFilters()};$('#filters').appendChild(b)});
$('#typeFilter').innerHTML='<option value="">All document types</option>'+TYPES.map(([k,v])=>`<option value="${k}">${v} (${D.instruments.filter(i=>i.jurisdiction_id.length===3&&jurisdictionByID.get(i.jurisdiction_id)?.type==='country'&&typeOf(i)===k).length})</option>`).join('');
$('#orgFilter').innerHTML='<option value="">All issuing organisations</option>'+ORGS.map(([k,v])=>`<option value="${k}">${v} (${D.instruments.filter(i=>jurisdictionByID.get(i.jurisdiction_id)?.type==='country'&&orgOf(i)===k).length})</option>`).join('');
$('#typeFilter').onchange=e=>{docType=e.target.value;setBody(null);refreshFilters()};$('#orgFilter').onchange=e=>{orgType=e.target.value;setBody(null);refreshFilters()};$('#statusFilter').onchange=e=>{status=e.target.value;setBody(null);refreshFilters()};
$('#clearFilters').onclick=()=>{filters.clear();status='all';docType='';orgType='';$('#statusFilter').value='all';$('#typeFilter').value='';$('#orgFilter').value='';$$('.chip[data-cat]').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-pressed','false')});setBody(null);refreshFilters()};
function setBody(id){body=id;$$('[data-body]').forEach(b=>{b.classList.toggle('active',b.dataset.body===id);b.setAttribute('aria-pressed',String(b.dataset.body===id))});applyHighlight()}
D.jurisdictions.filter(j=>j.type!=='country').forEach(j=>{const b=document.createElement('button');b.className='button body-btn';b.dataset.body=j.id;b.setAttribute('aria-pressed','false');b.textContent=j.short_name||j.id;b.title=`Highlight ${j.name} members on the map`;b.onclick=()=>{if(body===j.id){setBody(null);return}showView('map');setBody(j.id)};$('#regionalLinks').appendChild(b)});

/* ---------- directory & search ---------- */
function directory(){const q=norm($('#directorySearch').value);$('#directory').innerHTML=D.jurisdictions.filter(j=>j.type==='country'&&norm(j.name+' '+arName(j)+' '+j.id+' '+(j.aliases||[]).join(' ')).includes(q)).sort(AR?byName:()=>0).map(j=>`<button data-country="${j.id}">${flag(j)} ${esc(j.name)}<small>${national(j).length} documents</small></button>`).join('');$$('[data-country]').forEach(b=>b.onclick=()=>select(b.dataset.country))}$('#directoryBtn').onclick=()=>{directory();$('#directoryDialog').showModal();$('#directorySearch').focus()};$('#directorySearch').oninput=directory;
$('#searchInput').oninput=e=>{const q=norm(e.target.value.trim()),out=$('#searchResults');if(!q){out.hidden=true;return}const hits=D.jurisdictions.map(j=>{const name=norm(j.name+' '+arName(j)+' '+(j.aliases||[]).join(' ')+' '+j.id),bodyText=norm(national(j).map(i=>[i.english_title,i.official_title,i.publisher_name,i.categories.map(c=>D.categories[c])].join(' ')).join(' '));const exact=[j.name,arName(j),j.short_name,j.id,...(j.aliases||[])].some(x=>x&&norm(x)===q);   // an exact name match ranks first
return {j,rank:exact?-1:name.startsWith(q)||norm(arName(j)).startsWith(q)?0:name.includes(q)?1:bodyText.includes(q)?2:9}}).filter(x=>x.rank<9).sort((a,b)=>a.rank-b.rank||byName(a.j,b.j)).slice(0,15);out.innerHTML=hits.map(({j})=>`<button class="search-result" data-search-id="${j.id}">${flag(j)} ${esc(j.name)}<small>${national(j).length} documents</small></button>`).join('')||'<div class="small" style="padding:10px">No matching countries.</div>';out.hidden=false;$$('[data-search-id]').forEach(b=>b.onclick=()=>select(b.dataset.searchId))};$('#searchInput').onkeydown=e=>{if(e.key==='Enter'){$('#searchResults button')?.click();e.preventDefault()}if(e.key==='Escape')$('#searchResults').hidden=true};document.addEventListener('click',e=>{if(!e.target.closest('.search-wrap'))$('#searchResults').hidden=true});
$('#methodBtn').onclick=()=>$('#methodDialog').showModal();$('#exportBtn').onclick=()=>{fillExportCountries();$('#exportDialog').showModal()};$$('[data-close]').forEach(b=>b.onclick=()=>document.getElementById(b.dataset.close).close());$('#resetBtn').onclick=()=>{resetMap();$('#clearFilters').click()};

/* ---------- export ---------- */
const INST_FIELDS=['id','jurisdiction_id','layer','government_level','subnational_unit','official_title','english_title','categories','legal_status','lifecycle','issuing_authority','publisher_name','authority_type','publication_date','effective_date','last_amended_date','current_status','summary','language','source_url','official_pdf_url','official_webpage_url','verification_level','verification_date','first_recorded'];
function csv(rows,fields){const cell=v=>'"'+String(Array.isArray(v)?v.join(' | '):v??'').replace(/"/g,'""')+'"';return '﻿'+[fields.map(cell).join(','),...rows.map(r=>fields.map(k=>cell(r[k])).join(','))].join('\r\n')}
function download(content,name,type){const a=document.createElement('a'),u=URL.createObjectURL(new Blob([content],{type}));a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500);toast(`Downloaded ${name}`)}
function instRow(i,layer){return {...i,layer,authority_type:i.authority_type||orgByID.get(i.organization_id)?.authority_type||''}}
const stamp=()=>D.meta.build_date||D.meta.research_date||'';
async function countryBundle(j){const X=await full(),I=new Map(X.instruments.map(i=>[i.id,i])),n=X.instruments.filter(i=>i.jurisdiction_id===j.id);return {n,bundle:{meta:{...X.meta,export:'single jurisdiction',jurisdiction_id:j.id,exported_from:'AI Governance Radar'},jurisdiction:X.jurisdictions.find(x=>x.id===j.id)||j,narrative:X.narratives[j.id]||null,instruments:n,organizations:X.organizations.filter(o=>o.jurisdiction_id===j.id),sources:X.sources.filter(s=>n.some(i=>i.source_id===s.id)),coverage_audit:X.coverage_audit.find(a=>a.jurisdiction_id===j.id)||null,changes:X.changes.filter(c=>c.jurisdiction_id===j.id)}}}
async function exportCountry(j,kind){const base=`AI-Governance-Radar-${j.id}-${stamp()}`,{n,bundle}=await countryBundle(j);if(kind==='json')download(JSON.stringify(bundle,null,2),base+'.json','application/json');else download(csv(n.map(i=>instRow(i,'national')),INST_FIELDS),base+'.csv','text/csv')}
/* downloads use the full public data (data.json), fetched only when someone downloads; the page itself loads assets/data.min.json */
let FULLP=null;const full=()=>FULLP||(FULLP=getJSON(AS.full));
async function exportAll(kind){const X=await full(),base=`AI-Governance-Radar-all-${stamp()}`,J=new Map(X.jurisdictions.map(j=>[j.id,j]));if(kind==='json')download(JSON.stringify(X,null,2),base+'.json','application/json');else if(kind==='csv')download(csv(X.instruments.map(i=>instRow(i,J.get(i.jurisdiction_id)?.type==='country'?'national':'regional')),INST_FIELDS),base+'.csv','text/csv');else download(csv(X.coverage_audit,['jurisdiction_id','country','review_status','categories_with_findings','categories_where_no_material_was_found','review_date','last_sweep']),'AI-governance-coverage-audit.csv','text/csv')}
$$('[data-export]').forEach(b=>b.onclick=()=>exportAll(b.dataset.export));
function fillExportCountries(){const s=$('#exportCountry');if(!s.options.length)s.innerHTML=D.jurisdictions.slice().sort((a,b)=>(a.type!=='country')-(b.type!=='country')||byName(a,b)).map(j=>`<option value="${j.id}">${esc(j.name)}</option>`).join('');if(selected)s.value=selected}
$$('[data-export-country]').forEach(b=>b.onclick=()=>{const j=jurisdictionByID.get($('#exportCountry').value);if(j)exportCountry(j,b.dataset.exportCountry)});
function toast(m){const t=$('#toast');t.textContent=m;t.hidden=false;clearTimeout(toast.t);toast.t=setTimeout(()=>t.hidden=true,2600)}

$('#statRecords').textContent=(D.instruments.filter(i=>jurisdictionByID.get(i.jurisdiction_id)?.type==='country').length).toLocaleString('en-US');$('#statNational').textContent=(D.jurisdictions.filter(j=>j.type==='country'&&national(j).length).length).toLocaleString('en-US');$('#statReviewed').textContent=(D.instruments.filter(i=>i.verification_level==='reviewed_primary_metadata').length).toLocaleString('en-US');
(function restore(){const p=new URLSearchParams(Q0);(p.get('cat')||'').split(',').filter(c=>D.categories[c]).forEach(c=>{filters.add(c);const b=$(`.chip[data-cat="${c}"]`);if(b){b.classList.add('active');b.setAttribute('aria-pressed','true')}});if(TYPES.some(x=>x[0]===p.get('type'))){docType=p.get('type');$('#typeFilter').value=docType}if(ORGS.some(x=>x[0]===p.get('org'))){orgType=p.get('org');$('#orgFilter').value=orgType}if(p.get('status')&&$(`#statusFilter option[value="${p.get('status')}"]`)){status=p.get('status');$('#statusFilter').value=status}const BODY_ALIAS={ISESCO:'ICESCO'};if(BODY_ALIAS[p.get('body')])p.set('body',BODY_ALIAS[p.get('body')]);if(p.get('body')&&jurisdictionByID.get(p.get('body'))?.type!=='country'){body=p.get('body');$$('[data-body]').forEach(b=>{b.classList.toggle('active',b.dataset.body===body);b.setAttribute('aria-pressed',String(b.dataset.body===body))})}})();
await new Promise(r=>setTimeout(r));   // yield: keep start-up in short tasks (no multi-second freeze on phones)
try{initMap()}catch(e){console.error(e);$('#mapError').hidden=false}
await new Promise(r=>setTimeout(r));   // yield: keep start-up in short tasks (no multi-second freeze on phones)
(function(){const p=new URLSearchParams(Q0);if(p.get('view')==='updates')showView('updates');if(p.get('about')==='method'){p.delete('about');history.replaceState(null,'',location.pathname+(p.toString()?'?'+p:''));$('#methodDialog').showModal()}})();
window.RADAR_TEST={data:D,flags:F,groupDocs,issuerName,msHTML,groupTitle,kindOf,dayMonth,initialQuery:Q0,ageOf,inLast,syncURL,select,focusCountry,setMode,pin,get mode(){return mode},get rot(){return rot},recent,inherited,national,filters,reduced,countryPaths,centers,geometryCount:countriesFC.features.length,resetMap,zoomTo,applyHighlight,setBody,showView,get transform(){return transform},projection,exportCountry,exportAll};
setTimeout(()=>document.dispatchEvent(new Event('radar:ready')));   // the Updates tab builds in its own task
})();
