/* AI Governance Radar · update requests: builds a prefilled GitHub issue (template update-request.yml) and opens it. */
(function(){'use strict';
const f=document.getElementById('sgForm');if(!f)return;
const sel=document.getElementById('sgCountry'),url=document.getElementById('sgUrl'),err=document.getElementById('sgError');
const q=new URLSearchParams(location.search),pre=(q.get('country')||'').toUpperCase();
if(pre&&sel.querySelector(`option[value="${pre}"]`))sel.value=pre;
const t=q.get('type');if(t){const r=f.querySelector(`input[name=change_type][value="${t}"]`);if(r)r.checked=true}
function valid(u){try{const x=new URL(u);return x.protocol==='https:'||x.protocol==='http:'}catch(e){return false}}
f.addEventListener('submit',ev=>{ev.preventDefault();const country=sel.value,src=url.value.trim(),type=(f.querySelector('input[name=change_type]:checked')||{}).value||'',notes=f.elements.notes.value.trim();
  const problems=[];if(!country)problems.push('choose a country or body');if(!valid(src))problems.push('give the official source as a full web address (https://…)');
  if(problems.length){err.textContent='Please '+problems.join(' and ')+'.';err.hidden=false;(country?url:sel).focus();return}
  err.hidden=true;const name=sel.options[sel.selectedIndex].text;
  const p=new URLSearchParams({template:'update-request.yml',labels:'update-request',title:`[Update] ${name}: ${type}`,country:`${name} (${country})`,change_type:type,source_url:src,notes});
  window.open(`${f.dataset.repo}/issues/new?${p.toString()}`,'_blank','noopener')});
})();
