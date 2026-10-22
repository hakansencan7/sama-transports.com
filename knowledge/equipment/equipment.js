/* Shared equipment renderer: all translation uses SamaLanguage. */
(()=>{'use strict';
const root=document.getElementById('equipment-app');if(!root)return;
const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const t=s=>window.SamaLanguage?.t(s)||s,raw=s=>'<span translate="no">'+esc(s)+'</span>';
let catalog,state={category:'containers',type:'',brand:'',country:'',q:'',item:''};
const countries={TR:'Türkiye',IR:'Iran',RU:'Russia',US:'United States'};
const clean=v=>String(v||'').normalize('NFD').replace(/\p{Diacritic}/gu,'').replace(/ı/g,'i').toLocaleLowerCase();
const opt=(v,s)=>'<option value="'+esc(v)+'">'+esc(t(s))+'</option>';
const badge=s=>'<span class="eq-badge">'+esc(t(s))+'</span>';
function options(){
 $('eq-type').innerHTML=opt('','All types')+catalog.types.filter(r=>r.category===state.category).map(r=>opt(r.id,r.name)).join('');$('eq-type').value=state.type;
 const rows=catalog.records.filter(r=>r.category===state.category),brands=[...new Set([...(catalog.brands[state.category]||[]),...rows.map(r=>r.brand).filter(Boolean)])].sort();
 $('eq-brand').innerHTML=opt('','All brands')+brands.map(b=>opt(b,b)).join('');$('eq-brand').value=state.brand;
 const codes=[...new Set(rows.map(r=>r.country).filter(Boolean))];$('eq-country').innerHTML=opt('','All countries')+codes.map(c=>opt(c,countries[c]||c)).join('');$('eq-country').value=state.country;$('eq-country-label').hidden=!codes.length;
 $('eq-search').value=state.q;
}
function illustration(row){
 let body='';const wheel=x=>`<circle cx="${x}" cy="206" r="17"/><circle cx="${x}" cy="206" r="6" fill="#071e2b"/>`;
 switch(row.category){
 case 'containers':body='<path d="M90 94h330v100H90z"/><path d="M90 94l45-29h330v101l-45 28M420 94l45-29" fill="none"/>'+Array.from({length:15},(_,i)=>`<path d="M${105+i*21} 104v80"/>`).join('');break;
 case 'rail':body='<path d="M62 125h434v60H62z"/><path d="M45 224h470M45 236h470M90 125V92h375v33" fill="none"/>'+[100,140,425,465].map(wheel).join('');break;
 case 'sea':body='<path d="M55 157h460l-58 62H105z"/><path d="M363 157V84h70v73M385 84V60h18v24M86 132h255v25"/>'+Array.from({length:6},(_,i)=>`<path d="M${100+i*40} 137v20"/>`).join('')+'<path d="M40 241q25-15 50 0t50 0t50 0t50 0t50 0t50 0t50 0t50 0t50 0t50 0" fill="none"/>';break;
 case 'cranes':body='<path d="M145 218V69h35v149M162 69l255 21-255 30M180 78l45 31 38-26 42 20 39-16 38 12M397 89v68l-9 10q5 15 15 0" fill="none" stroke-width="8"/><path d="M97 218h270v16H97zM130 202h73v16h-73z"/>';break;
 case 'unloading':body='<path d="M220 219V113h35v106M237 113l104-43 120 54v47M433 171h55l-28 32zM60 179h130l-22 42H83z" fill="none" stroke-width="9"/><path d="M40 245h470M195 220h95v15h-95z"/>';break;
 case 'machinery':if(row.type==='loader'){body='<path d="M140 160h150v38H140zM195 160V98h68l28 62M290 160l83 20 35-40 40 24-27 35h-58"/>'+[175,286].map(wheel).join('');}else{body='<rect x="115" y="189" width="205" height="39" rx="19"/><path d="M145 188v-50h90V91h61v97M235 139l83-69 99 59-40 52 37 18 18-31-8-42-104-73-119 76"/>';}break;
 case 'cars':body='<path d="M80 181l22-33 70-16 57-45h113l70 52 64 17 13 41H80z"/><path d="M189 131l43-34h49v34h-92M294 98h43l44 33h-87z" fill="#071e2b"/>'+[157,407].map(wheel).join('');break;
 default:body='<path d="M55 166v-45h81l36 45v34H55zM175 108h315v78H175z"/><path d="M76 132h49l24 30H76z" fill="#071e2b"/>'+[98,219,404,447].map(wheel).join('');
 }
 return '<svg class="eq-drawing" viewBox="0 0 560 280" role="img" aria-label="'+esc(t('Schematic illustration — not to scale'))+'"><defs><pattern id="eqgrid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0v28" fill="none" stroke="#36c9ef" stroke-opacity=".09"/></pattern></defs><rect width="560" height="280" fill="#071e2b"/><rect width="560" height="280" fill="url(#eqgrid)"/><g stroke="#65d9ef" fill="#13435a" stroke-width="2.5" stroke-linejoin="round">'+body+'</g></svg>';
}
function detail(row){
 if(!row){$('eq-detail').innerHTML='<div class="eq-empty"><h3>'+esc(t('No matching model'))+'</h3><p>'+esc(t('Choose another brand or clear the filters.'))+'</p></div>';return;}
 const type=catalog.types.find(r=>r.id===row.type);
 const specs=Object.entries(row.specs);
 $('eq-detail').innerHTML='<article class="eq-detail-card"><div class="eq-detail-title"><div class="eq-breadcrumb">'+esc(t(type.name))+'</div><div class="eq-title-row"><h3>'+raw(row.name===type.name?t(row.name):row.name)+'</h3>'+badge(row.verified?'Verified model sheet':'Type reference')+'</div><p>'+raw([row.brand,row.country?t(countries[row.country]||row.country):t('Global / model-specific')].filter(Boolean).join(' · '))+'</p></div><div class="eq-detail-grid"><figure class="eq-figure">'+(row.photo?'<img class="eq-photo" src="'+esc(row.photo)+'" alt="'+esc(row.name)+'" loading="lazy" referrerpolicy="no-referrer">':'')+illustration(row)+'<figcaption>'+esc(t(row.photo?'Manufacturer image (illustrative)':'Schematic illustration — not to scale'))+'</figcaption></figure><div class="eq-spec-side"><h4>'+esc(t('Technical specifications'))+'</h4>'+(specs.length?'<dl class="eq-specs">'+specs.map(([k,v])=>'<div><dt>'+esc(t(k))+'</dt><dd>'+raw(v)+'</dd></div>').join(''):'<div class="eq-pending"><strong>'+esc(t('Verified model sheet pending'))+'</strong><p>'+esc(t('This type has no verified technical model yet. Dimensions and capacities are not estimated.'))+'</p></div>')+'</div></div>'+((row.missing||[]).length?'<p class="eq-missing">'+esc(t('Further dimensions'))+': '+row.missing.map(k=>esc(t(k))).join(' · ')+' — '+esc(t('Not published in this record'))+'</p>':'')+(row.variant?'<div class="eq-config"><b>'+esc(t('Model / configuration'))+'</b><p>'+raw(t(row.variant))+'</p></div>':'')+'<div class="eq-detail-footer"><p>'+esc(t('Dimensions depend on model and configuration. Use the linked manufacturer sheet.'))+'</p>'+(row.source?'<a href="'+esc(row.source)+'" target="_blank" rel="noopener noreferrer">'+esc(t('Source document'))+' ↗</a>'+(row.additional_source?'<a href="'+esc(row.additional_source)+'" target="_blank" rel="noopener noreferrer">'+esc(t('Dimension drawing'))+' ↗</a>':'')+'<small>'+esc(t('Reference checked'))+': '+raw(row.checked)+'</small>':'')+'<div class="eq-detail-actions"><button type="button" data-eq-action="copy">'+esc(t('Copy equipment link'))+'</button><button type="button" data-eq-action="print">'+esc(t('Print selected equipment'))+'</button></div></div></article>';
 const photo=$('eq-detail').querySelector('.eq-photo');if(photo){const figure=photo.closest('figure');figure.classList.add('has-photo');photo.onerror=()=>{photo.remove();figure.classList.remove('has-photo');figure.querySelector('figcaption').textContent=t('Schematic illustration — not to scale');};photo.onclick=()=>{$('eq-image-large').src=row.photo;$('eq-image-large').alt=row.name;$('eq-image-dialog').showModal();};}
}
function syncURL(push=false){
 const url=new URL(location.href);for(const k of ['category','type','brand','country','q','item']){if(state[k])url.searchParams.set('eq_'+k,state[k]);else url.searchParams.delete('eq_'+k);}
 try{history[push?'pushState':'replaceState']({},'',url);}catch(_){}
 const full=root.querySelector('.eq-full');if(full){const u=new URL('/knowledge/equipment/index.html',location.origin);for(const [k,v] of url.searchParams)u.searchParams.set(k,v);full.href=u.href;}
}
function render(push=false){
 $('eq-categories').innerHTML=catalog.categories.map(c=>'<button type="button" data-category="'+c.id+'" aria-pressed="'+(state.category===c.id)+'"><span class="eq-cat-number">'+c.icon+'</span><span>'+esc(t(c.name))+'</span><span class="eq-cat-count" translate="no">'+catalog.records.filter(r=>r.category===c.id).length+'</span></button>').join('');
 const list=catalog.records.filter(r=>r.category===state.category&&(!state.type||r.type===state.type)&&(!state.brand||r.brand===state.brand)&&(!state.country||r.country===state.country)&&(!state.q||clean([r.name,r.brand,countries[r.country],t(r.name),t(catalog.types.find(x=>x.id===r.type)?.name||'')].join(' ')).includes(clean(state.q))));
 const active=list.find(r=>r.id===state.item)||list[0];state.item=active?.id||'';
 const label=catalog.categories.find(r=>r.id===state.category)?.name||'';
 $('eq-count').innerHTML='<span>'+esc(t(label))+'</span><span translate="no">'+list.length+' / '+catalog.records.filter(r=>r.category===state.category).length+'</span>';
 $('eq-overview').innerHTML='<strong>'+catalog.categories.length+'</strong><span>'+esc(t('Equipment categories'))+'</span><strong>'+catalog.records.filter(r=>r.verified).length+'</strong><span>'+esc(t('Verified model sheet'))+'</span>';
 $('eq-list').innerHTML=list.map(r=>'<button type="button" class="eq-model '+(r.id===state.item?'is-selected':'')+'" data-item="'+esc(r.id)+'" aria-pressed="'+(r.id===state.item)+'"><span class="eq-model-icon" aria-hidden="true">'+esc(catalog.categories.find(c=>c.id===r.category).icon)+'</span><span><small>'+raw(r.brand||t(catalog.types.find(x=>x.id===r.type).name))+'</small><b>'+raw(t(r.name))+'</b><small>'+esc(t(r.verified?'Verified model sheet':'Type reference'))+(r.country?' · '+esc(t(countries[r.country]||r.country)):'')+'</small></span><span aria-hidden="true">↗</span></button>').join('');
 detail(active);syncURL(push);window.SamaLanguage?.refresh();
}
function fromURL(){const u=new URL(location.href);for(const k of Object.keys(state))state[k]=u.searchParams.get('eq_'+k)||'';if(!catalog.categories.some(c=>c.id===state.category))state.category='containers';if(state.type&&!catalog.types.some(t=>t.category===state.category&&t.id===state.type))state.type='';}
async function init(){try{
 const response=await fetch('/knowledge/equipment/catalog.json?v=20261022-1');if(!response.ok)throw Error('catalog');catalog=await response.json();fromURL();options();render();
 $('eq-categories').onclick=e=>{const b=e.target.closest('[data-category]');if(!b)return;state={category:b.dataset.category,type:'',brand:'',country:'',q:'',item:''};options();render(true);};
 for(const [id,key]of [['eq-type','type'],['eq-brand','brand'],['eq-country','country']])$(id).onchange=()=>{state[key]=$(id).value;state.item='';render(true);};
 $('eq-search').oninput=()=>{state.q=$('eq-search').value;state.item='';render();};
 $('eq-reset').onclick=()=>{state={category:state.category,type:'',brand:'',country:'',q:'',item:''};options();render(true);};
 $('eq-list').onclick=e=>{const b=e.target.closest('[data-item]');if(!b)return;state.item=b.dataset.item;render(true);};
 $('eq-detail').onclick=async e=>{const b=e.target.closest('[data-eq-action]');if(!b)return;if(b.dataset.eqAction==='print'){root.dataset.printing='true';window.print();delete root.dataset.printing;}if(b.dataset.eqAction==='copy'){try{const url=new URL(root.querySelector('.eq-full').href);await navigator.clipboard.writeText(url.href);b.textContent=t('Link copied');}catch(_){prompt(t('Copy equipment link'),root.querySelector('.eq-full').href);}}};
 $('eq-image-close').onclick=()=>$('eq-image-dialog').close();$('eq-image-dialog').onclick=e=>{if(e.target===$('eq-image-dialog'))$('eq-image-dialog').close();};
 window.addEventListener('popstate',()=>{fromURL();options();render();});
 document.addEventListener('sama:languagechange',()=>{options();render();});
}catch(error){$('eq-detail').innerHTML='<p role="alert">'+esc(t('Equipment could not be loaded. Please reload.'))+'</p>';console.error(error);}}
init();
})();
