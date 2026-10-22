/* Worldwide airport map using the existing SAMA language system and Leaflet. */
(()=>{'use strict';
 const $=id=>document.getElementById(id),core=window.SamaAirports,params=new URLSearchParams(location.search),PAGE=25;
 const state={country:params.get('country')||'',search:params.get('q')||'',type:params.get('type')||'airports',scheduled:params.get('scheduled')==='1',closed:params.get('closed')==='1',continent:'',region:params.get('region')||''};
 const regions={europe:'EU',africa:'AF',asia:'AS','north-america':'NA','south-america':'SA',oceania:'OC',antarctica:'AN'};
 const countryRegions={'middle-east':['AE','BH','EG','IQ','IR','IL','JO','KW','LB','OM','PS','QA','SA','SY','YE'],'central-asia-iran':['KZ','KG','TJ','TM','UZ','IR']};
 function regionScope(){state.continent=regions[state.region]||'';state.countrySet=countryRegions[state.region]?new Set(countryRegions[state.region]):null;}
 regionScope();
 const controls=[...document.querySelectorAll('#airport-filters input,#airport-filters select,#airport-filters button,#airport-fit,#airport-next,#airport-previous')];controls.forEach(el=>el.disabled=true);
 let data,rows=[],filtered=[],page=1,selected=null,map,points,selection,renderer,drawFrame=0,searchTimer=0;
 const lang=()=>window.SamaLanguage?.lang||'en',t=x=>window.SamaLanguage?.t(x)||x;
 const e=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const number=x=>new Intl.NumberFormat(lang(),{maximumFractionDigits:0}).format(x);
 const cname=code=>{try{return new Intl.DisplayNames([lang()],{type:'region'}).of(code)||data.countries[code]?.name||code;}catch(_){return data.countries[code]?.name||code;}};
 const safe=url=>{try{const u=new URL(url);return ['https:','http:'].includes(u.protocol)?u.href:null;}catch(_){return null;}};
 async function loadJson(path){
  if(typeof window.DecompressionStream!=='function'){const response=await fetch(path);if(!response.ok)throw Error('data');return response.json();}
  const response=await fetch(path+'.gz');if(!response.ok)throw Error('data');const bytes=new Uint8Array(await response.arrayBuffer());
  return bytes[0]===31&&bytes[1]===139?new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).json():JSON.parse(new TextDecoder().decode(bytes));
 }
 function url(){const u=new URL(location.href);for(const key of ['country','q','type','scheduled','closed','region'])u.searchParams.delete(key);
  for(const [key,value] of Object.entries({country:state.country,q:state.search,type:state.type==='airports'?'':state.type,scheduled:state.scheduled?'1':'',closed:state.closed?'1':'',region:state.region}))if(value)u.searchParams.set(key,value);
  u.searchParams.set('lang',lang());history.replaceState(null,'',u);
 }
 function translate(){document.querySelectorAll('#airports-app [data-t]').forEach(el=>el.textContent=t(el.dataset.t));$('airport-search').placeholder=t('Name, city, IATA or ICAO');$('airport-search').setAttribute('aria-label',t('Search airports'));$('airport-country').setAttribute('aria-label',t('Country'));$('airport-type').setAttribute('aria-label',t('Airport type'));$('airport-region').setAttribute('aria-label',t('Region'));document.querySelector('.airport-map-panel').setAttribute('aria-label',t('Airport map'));document.querySelector('.airport-results').setAttribute('aria-label',t('Airport results'));document.querySelector('#airports-app .mode-nav').setAttribute('aria-label',t('Choose your map'));document.title=t('World Airports')+' | SAMA Transportations';}
 function countries(){const codes=[...new Set(rows.map(r=>r.country))].sort((a,b)=>cname(a).localeCompare(cname(b),lang()));$('airport-country').innerHTML='<option value="">'+e(t('All countries'))+'</option>'+codes.map(code=>'<option value="'+e(code)+'">'+e(cname(code))+'</option>').join('');$('airport-country').value=state.country;}
 function stats(){const entries=[[filtered.length,'Matching airports'],[new Set(filtered.map(r=>r.country)).size,'Countries & territories'],[filtered.filter(r=>r.scheduled).length,'Scheduled airline service'],[rows.length,'Source records']];$('airport-stats').innerHTML=entries.map(([n,label])=>'<div class="stat-card"><strong>'+number(n)+'</strong><span>'+e(t(label))+'</span></div>').join('');}
 function list(){const pages=Math.max(1,Math.ceil(filtered.length/PAGE));page=Math.max(1,Math.min(page,pages));$('airport-result-count').textContent=number(filtered.length);
  $('airport-list').innerHTML=filtered.slice((page-1)*PAGE,page*PAGE).map(r=>'<button type="button" class="airport-row '+(selected?.ident===r.ident?'selected':'')+'" data-airport="'+e(r.ident)+'"><strong>'+e(r.name)+'</strong><small>'+(r.iata?'<span class="airport-code" dir="ltr">'+e(r.iata)+'</span>':'')+(r.icao?'<span class="airport-code" dir="ltr">'+e(r.icao)+'</span>':'')+e(r.city||'')+(r.city?' · ':'')+e(cname(r.country))+'</small><small>'+e(t(core.TYPES[r.type]||r.type))+(r.scheduled?' · '+e(t('Scheduled airline service')):'')+'</small></button>').join('')||'<p class="airport-empty">'+e(t('No airports match these filters.'))+'</p>';
  $('airport-page').textContent=number(page)+' / '+number(pages);$('airport-previous').disabled=page===1;$('airport-next').disabled=page===pages;
 }
 function details(){if(!selected){$('airport-detail').replaceChildren();return;}
  const r=selected,field=(label,value)=>'<div><dt>'+e(t(label))+'</dt><dd>'+e(value||t('Not specified by source'))+'</dd></div>';
  const runway=r.runway?number(r.runway[0])+' m · '+r.runway[1]:'',elevation=r.elevation_ft?number(Number(r.elevation_ft)*0.3048)+' m':'';
  const website=safe(r.website),wiki=safe(r.wikipedia);
  $('airport-detail').innerHTML='<h3>'+e(r.name)+'</h3><span class="airport-code" dir="ltr">'+e(r.ident)+'</span><dl class="airport-detail-grid">'+field('Country',cname(r.country))+field('City',r.city)+field('IATA code',r.iata)+field('ICAO code',r.icao)+field('Airport type',t(core.TYPES[r.type]||r.type))+field('Scheduled airline service',t(r.scheduled?'Yes':'No'))+field('Longest published runway',runway)+field('Elevation',elevation)+field('Coordinates',r.point?.join(', '))+'</dl><div class="airport-detail-links"><a target="_blank" rel="noopener noreferrer" href="https://ourairports.com/airports/'+encodeURIComponent(r.ident)+'/">OurAirports ↗</a>'+(website?'<a target="_blank" rel="noopener noreferrer" href="'+e(website)+'">'+e(t('Airport website'))+' ↗</a>':'')+(wiki?'<a target="_blank" rel="noopener noreferrer" href="'+e(wiki)+'">Wikipedia ↗</a>':'')+'</div>';
 }
 function choose(r){selected=r;selection.clearLayers();if(r.point){L.circleMarker(r.point,{radius:10,color:'#fff',weight:3,fillColor:'#e49019',fillOpacity:1}).addTo(selection);map.setView(r.point,Math.max(map.getZoom(),9));}details();list();}
 function drawMap(){cancelAnimationFrame(drawFrame);drawFrame=requestAnimationFrame(()=>{
  points.clearLayers();if(!map)return;const zoom=map.getZoom(),bounds=map.getBounds(),bins=new Map(),cell=zoom<5?52:42;
  for(const r of filtered){if(!r.point||(zoom>=4&&!bounds.pad(.2).contains(r.point)))continue;const p=map.project(r.point,zoom),key=Math.floor(p.x/cell)+':'+Math.floor(p.y/cell);let bin=bins.get(key);if(!bin){bin={x:0,y:0,n:0,first:r};bins.set(key,bin);}bin.x+=p.x;bin.y+=p.y;bin.n++;}
  for(const bin of bins.values()){
   const center=map.unproject([bin.x/bin.n,bin.y/bin.n],zoom);
   if(bin.n===1){L.circleMarker(center,{renderer,radius:bin.first.type==='large_airport'?7:5,color:'#fff',weight:1,fillColor:'#087eac',fillOpacity:.9}).bindTooltip(()=>e(bin.first.name)+(bin.first.iata?' · '+e(bin.first.iata):'')).on('click',()=>choose(bin.first)).addTo(points);}
   else {const size=bin.n>999?44:36;L.marker(center,{icon:L.divIcon({className:'airport-map-cluster',html:e(number(bin.n)),iconSize:[size,size],iconAnchor:[size/2,size/2]})}).on('click',()=>map.setView(center,Math.min(18,zoom+2))).addTo(points);}
  }
 });}
 function fit(){const coordinates=filtered.map(r=>r.point).filter(Boolean);if(!coordinates.length)return;if(!state.country&&!state.search){map.setView([22,12],2);return;}map.fitBounds(L.latLngBounds(coordinates),{padding:[28,28],maxZoom:10});}
 function sources(){const date=new Intl.DateTimeFormat(lang(),{dateStyle:'long',timeZone:'UTC'}).format(new Date(data.date+'T00:00:00Z'));
  $('airport-source').innerHTML='OurAirports · '+e(t('Data retrieved'))+': '+e(date)+' · '+e(t('Public domain data'))+' · <a href="data/airports-source.json" target="_blank" rel="noopener">'+e(t('Sources & coverage'))+'</a>';
  $('sources-body').innerHTML='<p>'+e(t('Airport names, locations, codes and service information are provided by OurAirports.'))+'</p><p>'+e(t('Closed records and other facility types can be included using the filters.'))+'</p><p>'+e(t('Data retrieved'))+': '+e(date)+' · '+number(rows.length)+' '+e(t('Source records'))+'</p><p><a href="https://ourairports.com/data/" target="_blank" rel="noopener noreferrer">OurAirports open data ↗</a></p><p><a href="https://ourairports.com/help/data-dictionary.html" target="_blank" rel="noopener noreferrer">'+e(t('Dataset field definitions'))+' ↗</a></p><p>'+e(t('Runway dimensions are published source values, not a confirmation of current operating conditions.'))+'</p><p><a href="data/world-airports.json.gz" download>'+e(t('Download airport data'))+' ↓</a></p>';
 }
 function apply(refit=false){if(!map||!data)return;filtered=core.filter(rows,state);if(selected&&!filtered.some(r=>r.ident===selected.ident)){selected=null;selection.clearLayers();details();}page=1;stats();list();drawMap();if(refit)fit();url();}
 function language(){translate();if(data){countries();stats();list();details();sources();drawMap();url();}}
 $('airport-filters').addEventListener('submit',event=>event.preventDefault());
 $('airport-search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.search=$('airport-search').value;apply(true);},160);});
 for(const [id,key] of [['airport-region','region'],['airport-country','country'],['airport-type','type'],['airport-scheduled','scheduled'],['airport-closed','closed']])$(id).addEventListener('change',()=>{state[key]=$(id).type==='checkbox'?$(id).checked:$(id).value;if(key==='region'){state.country='';$('airport-country').value='';}if(key==='country'){state.region='';$('airport-region').value='';}regionScope();apply(true);});
 $('airport-reset').addEventListener('click',()=>{clearTimeout(searchTimer);selected=null;selection?.clearLayers();details();Object.assign(state,{country:'',search:'',type:'airports',scheduled:false,closed:false,continent:'',region:'',countrySet:null});$('airport-region').value='';$('airport-country').value='';$('airport-search').value='';$('airport-type').value='airports';$('airport-scheduled').checked=false;$('airport-closed').checked=false;apply(true);});
 $('airport-list').addEventListener('click',event=>{const button=event.target.closest('[data-airport]');if(button){const r=filtered.find(r=>r.ident===button.dataset.airport);if(r)choose(r);}});
 $('airport-previous').addEventListener('click',()=>{page--;list();});$('airport-next').addEventListener('click',()=>{page++;list();});$('airport-fit').addEventListener('click',fit);
 $('sources-button').addEventListener('click',()=>$('sources-dialog').showModal());$('close-sources').addEventListener('click',()=>$('sources-dialog').close());
 document.addEventListener('sama:languagechange',language);
 async function start(){try{
  translate();data=await loadJson('data/world-airports.json');rows=core.decode(data);rows.forEach(r=>r.continent=data.countries[r.country]?.continent||'');
  rows.sort((a,b)=>(a.type==='large_airport'?0:a.type==='medium_airport'?1:2)-(b.type==='large_airport'?0:b.type==='medium_airport'?1:2)||a.name.localeCompare(b.name));
  countries();if(state.country&&!rows.some(r=>r.country===state.country)){state.country='';$('airport-country').value='';}
  $('airport-search').value=state.search;if(![...$('airport-region').options].some(o=>o.value===state.region))state.region='';$('airport-region').value=state.region;regionScope();if(![...$('airport-type').options].some(o=>o.value===state.type))state.type='airports';$('airport-type').value=state.type;$('airport-scheduled').checked=state.scheduled;$('airport-closed').checked=state.closed;
  map=L.map('airport-map',{worldCopyJump:true,minZoom:2,maxZoom:18}).setView([22,12],2);renderer=L.canvas({padding:.3});points=L.layerGroup().addTo(map);selection=L.layerGroup().addTo(map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
  map.on('moveend zoomend',drawMap);loadJson('data/world.json').then(world=>L.geoJSON(world,{interactive:false,style:{color:'#7b9db8',weight:.6,fillOpacity:0}}).addTo(map)).catch(()=>{});
  controls.forEach(el=>el.disabled=false);language();apply(true);sources();$('airport-message').textContent='';$('airports-app').setAttribute('aria-busy','false');
 }catch(error){console.error(error);$('airport-message').textContent=t('Airport data could not be loaded. Please reload the page.');$('airports-app').setAttribute('aria-busy','false');}}
 start();
})();
