/* Arabic pages: translate interface text that scripts add after load, with the same dictionary and rules as the build
   (scripts/i18n.py). Data text never matches and is left as published. Wrapped by i18n.runtime_js(), which defines I. */
var S=I.s,LOW={};for(var k in S)if(!Object.prototype.hasOwnProperty.call(LOW,k.toLowerCase()))LOW[k.toLowerCase()]=S[k];var P=I.p.map(function(x){return [new RegExp(x[0]),x[1]]}),M=I.m,EM=I.em;
var DATE=new RegExp('^(?:(\\d{1,2}) )?('+Object.keys(EM).sort(function(a,b){return b.length-a.length}).join('|')+') (\\d{4})$');
function arDate(t){var m=DATE.exec(t.trim());if(!m)return null;return [m[1],M[EM[m[2]]],m[3]].filter(Boolean).join(' ')}
var MISS={};
function render(rep,m){return rep.replace(/\{([td]?)(\d)\}/g,function(_,k,i){var g=m[+i]||'';
  if(k==='t'){var u=tr(g);if(u===g&&/[A-Za-z]{2}/.test(g))throw MISS;return u}
  return k==='d'?(arDate(g)||g):g})}
function tr(text){
  if(!text||!text.trim())return text;
  var lead=text.match(/^\s*/)[0],trail=text.match(/\s*$/)[0],core=text.trim().replace(/\s+/g,' ');
  if(Object.prototype.hasOwnProperty.call(S,core))return lead+S[core]+trail;
  if(core===core.toUpperCase()&&/[A-Z]/.test(core)&&Object.prototype.hasOwnProperty.call(LOW,core.toLowerCase()))return lead+LOW[core.toLowerCase()]+trail;
  for(var i=0;i<P.length;i++){var m=P[i][0].exec(core);if(m){try{return lead+render(P[i][1],m)+trail}catch(e){if(e!==MISS)throw e}}}
  if(core.indexOf(' · ')>=0){var ps=core.split(' · '),q=ps.map(tr);if(q.join('\u0001')!==ps.join('\u0001'))return lead+q.join(' · ')+trail}
  var d=arDate(core);if(d)return lead+d+trail;
  return text}
var ATTRS=['placeholder','aria-label','title','alt'],SKIP={SCRIPT:1,STYLE:1,TEXTAREA:1};
/* data a script marks translate="no" (titles, names, excerpts) is left as published */
function keep(el){return !!(el&&el.closest&&el.closest('[translate="no"]'))}
function textNode(n){if(keep(n.parentNode))return;var v=n.nodeValue,u=tr(v);if(u!==v)n.nodeValue=u}
function attrs(el){if(keep(el))return;for(var i=0;i<ATTRS.length;i++){var v=el.getAttribute&&el.getAttribute(ATTRS[i]);if(v){var u=tr(v);if(u!==v)el.setAttribute(ATTRS[i],u)}}}
function walk(root){
  if(root.nodeType===3){if(!root.parentNode||!SKIP[root.parentNode.nodeName])textNode(root);return}
  if(root.nodeType!==1||SKIP[root.nodeName])return;
  attrs(root);
  if(root.nodeName==='INPUT'&&(root.type==='button'||root.type==='submit')&&root.value){var u=tr(root.value);if(u!==root.value)root.value=u}
  if(keep(root))return;
  var w=document.createTreeWalker(root,NodeFilter.SHOW_ELEMENT|NodeFilter.SHOW_TEXT,{acceptNode:function(x){return x.nodeType===1&&x.getAttribute('translate')==='no'?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT}}),n;
  while((n=w.nextNode())){if(n.nodeType===3){if(!SKIP[n.parentNode.nodeName])textNode(n)}else if(!SKIP[n.nodeName])attrs(n)}}
/* Base direction of data text (titles, summaries, names, details). The browser's dir="auto" and unicode-bidi:plaintext take
   the direction of the first letter, so an Arabic title that starts with a code ("GB/T 47863-2026 — …", "CCN-STIC-2011 …")
   was set left to right. Here the direction follows the script of most of the letters; text with no letters keeps the page's. */
var BIDI='[dir="auto"],[data-bidi],.inst-sum,.inst-status,.prose p,.plain li,.lead-list li,.pp-cap,.pb-cap span,.hero-cap,.tl-card p,.tl-card h4,.pl-title,.credits-table td,.sr-title,.sr-ot,.sr-ex,.c-i .v';
var RTL=/[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]/g,LTR=/[A-Za-z\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF\u3040-\u30FF\u3400-\u9FFF\uAC00-\uD7AF]/g;
function dirOf(s){var r=(s.match(RTL)||[]).length,l=(s.match(LTR)||[]).length;return r||l?(r>=l?'rtl':'ltr'):'rtl'}
function setDir(el){if(el.closest&&el.closest('svg'))return;var d=dirOf(el.textContent||'');el.setAttribute('data-bidi','');if(el.getAttribute('dir')!==d)el.setAttribute('dir',d)}
function bidi(root){if(root.nodeType!==1)return;if(root.matches&&root.matches(BIDI))setDir(root);var l=root.querySelectorAll(BIDI);for(var i=0;i<l.length;i++)setDir(l[i])}
function bidiUp(n){var el=n.nodeType===1?n:n.parentNode,b=el&&el.closest&&el.closest(BIDI);if(b)setDir(b)}
window.I18N={t:tr,date:arDate,lang:'ar',dir:dirOf};
function start(){
  walk(document.body);bidi(document.body);
  new MutationObserver(function(ms){ms.forEach(function(m){
    if(m.type==='characterData'){textNode(m.target);bidiUp(m.target)}
    else if(m.type==='attributes')attrs(m.target);
    else{m.addedNodes.forEach(function(n){walk(n);bidi(n)});if(m.addedNodes.length)bidiUp(m.target)}})}).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:ATTRS});
  document.title=tr(document.title)}
if(document.body)start();else document.addEventListener('DOMContentLoaded',start);
