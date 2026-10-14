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
function textNode(n){var v=n.nodeValue,u=tr(v);if(u!==v)n.nodeValue=u}
function attrs(el){for(var i=0;i<ATTRS.length;i++){var v=el.getAttribute&&el.getAttribute(ATTRS[i]);if(v){var u=tr(v);if(u!==v)el.setAttribute(ATTRS[i],u)}}}
function walk(root){
  if(root.nodeType===3){if(!root.parentNode||!SKIP[root.parentNode.nodeName])textNode(root);return}
  if(root.nodeType!==1||SKIP[root.nodeName])return;
  attrs(root);
  if(root.nodeName==='INPUT'&&(root.type==='button'||root.type==='submit')&&root.value){var u=tr(root.value);if(u!==root.value)root.value=u}
  var w=document.createTreeWalker(root,NodeFilter.SHOW_ELEMENT|NodeFilter.SHOW_TEXT,null),n;
  while((n=w.nextNode())){if(n.nodeType===3){if(!SKIP[n.parentNode.nodeName])textNode(n)}else if(!SKIP[n.nodeName])attrs(n)}}
window.I18N={t:tr,date:arDate,lang:'ar'};
function start(){
  walk(document.body);
  new MutationObserver(function(ms){ms.forEach(function(m){
    if(m.type==='characterData')textNode(m.target);
    else if(m.type==='attributes')attrs(m.target);
    else m.addedNodes.forEach(walk)})}).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:ATTRS});
  document.title=tr(document.title)}
if(document.body)start();else document.addEventListener('DOMContentLoaded',start);
