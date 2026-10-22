const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),zlib=require('node:zlib');
const {JSDOM}=require('jsdom');const core=require('../knowledge/atlas/airports-core.js');
const root='knowledge/atlas/',data=JSON.parse(zlib.gunzipSync(fs.readFileSync(root+'data/world-airports.json.gz'))),rows=core.decode(data);
rows.forEach(r=>r.continent=data.countries[r.country]?.continent||'');
test('world snapshot is complete, unique, located and reproducible',()=>{
 const manifest=JSON.parse(fs.readFileSync(root+'data/airports-source.json'));
 assert.equal(rows.length,manifest.records);assert.ok(rows.length>80000);assert.equal(new Set(rows.map(r=>r.ident)).size,rows.length);
 assert.equal(new Set(rows.map(r=>r.country)).size,manifest.countries);
 assert.ok(rows.every(r=>r.point&&Math.abs(r.point[0])<=90&&Math.abs(r.point[1])<=180));
 assert.equal(core.filter(rows,{type:'all',closed:true}).length,rows.length);
 assert.ok(core.filter(rows,{type:'airports'}).every(r=>['large_airport','medium_airport','small_airport'].includes(r.type)));
});
test('IATA and ICAO exact search, Turkish city search and combined filters work worldwide',()=>{
 assert.equal(core.filter(rows,{search:'ist',type:'airports'})[0].ident,'LTFM');
 assert.equal(core.filter(rows,{search:'LTFM',type:'airports'}).length,1);
 assert.ok(core.filter(rows,{search:'İstanbul',country:'TR',type:'airports'}).some(r=>r.ident==='LTFM'));
 assert.ok(core.filter(rows,{search:'JFK',type:'airports'}).some(r=>r.country==='US'));
 assert.ok(core.filter(rows,{search:'SYD',type:'airports'}).some(r=>r.country==='AU'));
 assert.ok(core.filter(rows,{country:'IQ',scheduled:true,type:'airports'}).some(r=>r.iata==='BGW'));
 assert.ok(core.filter(rows,{continent:'EU',type:'all'}).every(r=>r.continent==='EU'));
 assert.ok(core.filter(rows,{countrySet:new Set(['IQ','IR']),type:'all'}).every(r=>['IQ','IR'].includes(r.country)));
 assert.equal(core.filter(rows,{country:'IQ',search:'LTFM',type:'airports'}).length,0);
 assert.ok(core.filter(rows,{type:'all',closed:true}).some(r=>r.type==='closed'));
 assert.ok(core.filter(rows,{type:'all'}).every(r=>r.type!=='closed'));
});
const tick=()=>new Promise(r=>setTimeout(r,220));
async function setup(t){
 const dom=new JSDOM(fs.readFileSync(root+'airports.html','utf8'),{url:'https://sama.test/knowledge/atlas/airports.html?lang=tr',runScripts:'outside-only',pretendToBeVisual:true});t.after(()=>dom.window.close());const w=dom.window,d=w.document;
 const dictionaries={};w.SamaLanguage={lang:'tr',register:x=>Object.assign(dictionaries,x),t:x=>dictionaries[x]?.[w.SamaLanguage.lang]||x};w.eval(fs.readFileSync(root+'airports-i18n.js','utf8'));
 w.fetch=async url=>({ok:true,json:async()=>url.includes('world-airports')?data:{type:'FeatureCollection',features:[]}});w.DecompressionStream=undefined;
 const layer=()=>({clearLayers(){},addTo(){return this},bindTooltip(){return this},on(){return this}}),m={setView(){return this},getZoom:()=>2,getBounds:()=>({pad(){return this},contains:()=>true}),project:()=>({x:1,y:1}),unproject:()=>[0,0],fitBounds(){},on(){}};
 w.L={map:()=>m,canvas:()=>({}),layerGroup:layer,tileLayer:layer,geoJSON:layer,circleMarker:layer,marker:layer,divIcon:x=>x,latLngBounds:x=>x};
 w.eval(fs.readFileSync(root+'airports-core.js','utf8'));w.eval(fs.readFileSync(root+'airports.js','utf8'));await tick();return {w,d};
}
test('real page searches, opens source-linked details, changes language and resets without losing records',async t=>{
 const {w,d}=await setup(t);
 d.getElementById('airport-search').value='IST';d.getElementById('airport-search').dispatchEvent(new w.Event('input'));await tick();
 assert.equal(d.querySelectorAll('[data-airport]').length,1);assert.equal(d.querySelector('[data-airport]').dataset.airport,'LTFM');
 d.querySelector('[data-airport]').click();assert.match(d.getElementById('airport-detail').textContent,/LTFM/);assert.match(d.getElementById('airport-detail').textContent,/IATA/);
 assert.ok(d.querySelector('#airport-detail a[href="https://ourairports.com/airports/LTFM/"]'));
 assert.equal(new URL(w.location.href).searchParams.get('q'),'IST');
 w.SamaLanguage.lang='ar';d.dispatchEvent(new w.Event('sama:languagechange'));assert.equal(d.querySelector('h1').textContent,'مطارات العالم');assert.match(d.getElementById('airport-detail').textContent,/LTFM/);
 d.getElementById('airport-reset').click();assert.equal(d.querySelectorAll('[data-airport]').length,25);assert.equal(d.getElementById('airport-search').value,'');
 assert.equal(d.getElementById('airport-detail').textContent,'');assert.equal(new URL(w.location.href).searchParams.has('q'),false);
 d.getElementById('airport-next').click();assert.ok(d.getElementById('airport-page').textContent.startsWith(new Intl.NumberFormat('ar').format(2)));
});
test('new menu is connected from the knowledge page and existing atlas navigation',()=>{
 const html=fs.readFileSync('knowledge-base.html','utf8');assert.match(html,/href="#airports"/);assert.match(html,/id="airports"/);assert.match(html,/\/knowledge\/atlas\/airports.html/);
 assert.match(fs.readFileSync(root+'atlas.js','utf8'),/airports:'World Airports'/);
 for(const file of ['index.html','country.html','ports.html','railways.html','roads.html','borders.html'])assert.match(fs.readFileSync(root+file,'utf8'),/airports-i18n.js/);
});
