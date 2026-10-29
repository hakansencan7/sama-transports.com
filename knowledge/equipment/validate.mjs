import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=new URL('./',import.meta.url),data=JSON.parse(fs.readFileSync(new URL('catalog.json',base),'utf8'));
const dict=JSON.parse(fs.readFileSync(new URL('equipment-i18n.js',base),'utf8').match(/register\((.*)\);/s)[1]);
for(const collection of [data.categories,data.types,data.records])assert.equal(new Set(collection.map(x=>x.id)).size,collection.length,'Duplicate ID');
for(const item of [...data.categories,...data.types,...(data.seaGroups||[]),...(data.containerGroups||[]),...(data.roadGroups||[]),...(data.railGroups||[]),...(data.craneGroups||[]),...(data.unloadingGroups||[]),...(data.machineryGroups||[]),...(data.carGroups||[])])for(const lang of ['en','tr','ar'])assert.ok(dict[item.name]?.[lang],`Missing ${lang}: ${item.name}`);
for(const row of data.records){
 const type=data.types.find(x=>x.id===row.type);assert.equal(type?.category,row.category);
 if(row.category==='rail')assert.ok(row.country,'Rail record must identify country');
 if(row.verified){assert.match(row.source,/^https:\/\//);assert.ok(row.checked);assert.ok(row.variant);assert.ok(Object.keys(row.specs).length);}
 else assert.equal(Object.keys(row.specs).length,0,'Unverified reference may not invent specifications');
 for(const key of Object.keys(row.specs))for(const lang of ['en','tr','ar'])assert.ok(dict[key]?.[lang],`Missing ${lang}: ${key}`);
 if(row.photo){
  if(row.photo.startsWith('/assets/knowledge/')){
   assert.match(row.photo,/^\/assets\/knowledge\/(vessels|containers|road|rail|cranes|machinery|cars)\/[a-z0-9-]+\.webp$/);
   const image=new URL('../..'+row.photo,base);assert.ok(fs.existsSync(image),`Missing photo: ${row.photo}`);
   assert.ok(fs.statSync(image).size>1000,'Empty photograph');
   for(const key of ['title','author','license','license_url','source','changes'])assert.ok(row.photo_credit?.[key],`Missing photo ${key}: ${row.id}`);
   assert.match(row.photo_credit.source,/^https:\/\/commons\.wikimedia\.org\/wiki\/File:/);
   assert.match(row.photo_credit.license,/^(CC BY|CC0|Public domain)/);
  }else assert.match(row.photo,/^https:\/\//);
 }
 if(row.category==='cars'){
  assert.equal(row.verified,true);
  assert.ok(data.carGroups.some(g=>g.id===type.group),'Missing car family');
  assert.ok(row.country&&row.photo&&row.variant&&row.data_note&&row.photo_note,'Car scope and photograph required');
  assert.equal(row.photo_type_example,true,'Identify model photographs separately from the reference configuration');
  assert.ok(row.specs['Overall length']&&row.specs['Overall height']);
  assert.ok(Object.keys(row.specs).some(k=>/width/i.test(k)),'Published width required');
  assert.ok(Object.keys(row.specs).some(k=>/weight|mass/i.test(k)&&!/gross/i.test(k)),'Published unladen or running-order mass required');
  for(const key of [row.name,row.variant,row.data_note,row.photo_note,...Object.entries(row.guide).flat()])for(const lang of ['en','tr','ar'])assert.ok(dict[key]?.[lang],`Missing ${lang}: ${key}`);
  for(const value of Object.values(row.specs))assert.match(value,/^\d+(?:\.\d+)?(?:–\d+(?:\.\d+)?)? (?:mm|kg)$/,'Car dimensions and weights must retain explicit units');
 }
 if(row.category==='machinery'){
  assert.ok(data.machineryGroups.some(g=>g.id===type.group),'Missing machinery family');
  assert.equal(row.verified,true);
  assert.ok(row.photo,'Every machinery card needs a real photograph');
  assert.equal(row.photo_type_example,true,'Identify machinery reference photographs');
  assert.ok(row.guide?.['Typical use']);assert.ok(row.guide?.['Reference configuration']);
  for(const key of [row.name,row.variant,row.data_note,row.photo_note,...Object.entries(row.guide).flat()])for(const lang of ['en','tr','ar'])assert.ok(dict[key]?.[lang],`Missing ${lang}: ${key}`);
  for(const [key,value] of Object.entries(row.specs)){assert.ok(/\d/.test(value),`Machinery figure has no number: ${row.id} ${key}`);assert.ok(!/[\uFFFD]/.test(key+value),'Corrupt machinery text');}
 }
 if(row.category==='unloading'){
  assert.ok(data.unloadingGroups.some(g=>g.id===type.group),'Missing unloading technology group');
  assert.ok(row.photo,'Every unloading record needs a real photograph');
  assert.equal(row.verified,true);
  assert.ok(row.photo_exact || row.photo_type_example,'Identify photo scope');
  assert.ok(Object.keys(row.specs).some(k=>/capacity|throughput/i.test(k)),'Missing published capacity');
  for(const key of [row.name,row.variant,row.data_note,row.photo_note,...Object.entries(row.guide||{}).flat()].filter(Boolean))for(const lang of ['en','tr','ar'])assert.ok(dict[key]?.[lang],`Missing ${lang}: ${key}`);
  assert.ok(row.guide?.['Capacity basis'],'Missing capacity conditions');
 }
 if(row.category==='cranes'){
  assert.ok(data.craneGroups.some(g=>g.id===type.group),'Missing crane family');
  assert.ok(row.photo,'Every crane needs a real photograph');
  assert.equal(row.photo_type_example,true,'Identify representative crane photographs');
  assert.equal(row.verified,true);assert.ok(Object.keys(row.guide||{}).length>=2);
  if(row.photo_credit?.external){assert.ok(row.photo_credit.author);assert.match(row.photo_credit.source,/^https:\/\//);}
  for(const key of [row.name,row.variant,row.data_note,row.photo_note,...Object.entries(row.guide).flat()].filter(Boolean))for(const lang of ['en','tr','ar'])assert.ok(dict[key]?.[lang],`Missing ${lang}: ${key}`);
 }
 if(row.category==='rail'){
  assert.ok(data.railGroups.some(g=>g.id===type.group),'Missing rail family');
  assert.ok(row.photo?.startsWith('/assets/knowledge/rail/'),'Rail photograph must be local and credited');
  assert.equal(row.photo_type_example,true,'Representative wagon photos must be identified');
  assert.match(row.source,/^https:\/\//);assert.ok(row.checked);
  assert.ok(Object.keys(row.guide||{}).length>=2);
  for(const key of [row.name,row.variant,row.data_note,row.photo_note,...Object.entries(row.guide).flat()].filter(Boolean))for(const lang of ['en','tr','ar'])assert.ok(dict[key]?.[lang],`Missing ${lang}: ${key}`);
  if(row.specs['Axle count'])assert.equal(Number(row.specs['Wheel count (derived)']),2*Number(row.specs['Axle count']),'Rail wheel count is derived from axles');
  if(row.country==='IQ'){assert.equal(row.verified,false);assert.equal(Object.keys(row.specs).length,0,'Historical Iraqi requirements are not model specifications');}
 }
 if(row.category==='sea'){
  assert.ok(data.seaGroups.some(g=>g.id===type.group),'Missing vessel family');
  assert.ok(row.photo,'Every vessel record needs a real photograph');
  if(!row.verified){
   assert.ok(row.guide&&Object.keys(row.guide).length>=2,'Missing vessel characteristics');
   assert.match(row.source,/^https:\/\//);assert.ok(row.checked);
   for(const [key,value] of Object.entries(row.guide))for(const lang of ['en','tr','ar']){
    assert.ok(dict[key]?.[lang],`Missing guide label ${lang}: ${key}`);
    assert.ok(dict[value]?.[lang],`Missing guide prose ${lang}: ${row.id}`);
   }
  }else assert.equal(row.photo_type_example,true,'Model must identify its representative type photograph');
 }
 if(['containers','road'].includes(row.category)){
  assert.ok((row.category==='road'?data.roadGroups:data.containerGroups).some(g=>g.id===type.group),'Missing equipment family');
  assert.ok(row.photo,'Every equipment record needs a photograph');
  assert.equal(row.photo_type_example,true,'Identify representative equipment photographs');
  assert.match(row.source,/^https:\/\//);assert.ok(row.checked);
  if(row.photo_credit?.external){assert.ok(row.photo_credit.author);assert.match(row.photo_credit.source,/^https:\/\//);}
  assert.ok(Object.keys(row.guide||{}).length>=2,'Missing container characteristics');
  const text=[row.name,row.variant,row.data_note,row.photo_note,...(row.missing||[]),...Object.entries(row.guide).flat()].filter(Boolean);
  for(const key of text)for(const lang of ['en','tr','ar'])assert.ok(dict[key]?.[lang],`Missing ${lang}: ${key}`);
  const number=key=>row.specs[key]===undefined?null:parseFloat(row.specs[key].replaceAll(',',''));
  const gross=number('Maximum gross weight')??number('Gross weight (tare + payload)')??number('Technical gross weight'),tare=number('Tare weight'),payload=number('Payload')??number('Payload (gross minus tare)')??number('Technical payload');
  if([gross,tare,payload].every(v=>v!==null))assert.ok(Math.abs(gross-tare-payload)<.1,`Inconsistent weight totals: ${row.id}`);
  const dimensions=key=>row.specs[key]?.replaceAll(',','').match(/\d+(?:\.\d+)?/g)?.map(Number);
  const outside=dimensions('External dimensions (L × W × H)'),inside=dimensions('Internal dimensions (L × W × H)');
  if(outside&&inside)assert.ok(inside.every((v,i)=>v<=outside[i]),`Internal dimension exceeds exterior: ${row.id}`);
 }
}
assert.equal(data.records.filter(r=>r.category==='sea'&&r.guide).length,50);
assert.equal(data.seaGroups.length,9);
assert.equal(data.containerGroups.length,8);
assert.equal(data.types.filter(r=>r.category==='containers').length,33);
assert.equal(data.records.filter(r=>r.category==='containers').length,51);
assert.equal(data.roadGroups.length,8);
assert.equal(data.types.filter(r=>r.category==='road').length,44);
assert.equal(data.records.filter(r=>r.category==='road').length,54);
assert.equal(data.railGroups.length,6);
assert.equal(data.types.filter(r=>r.category==='rail').length,24);
assert.equal(data.records.filter(r=>r.category==='rail').length,74);
for(const country of ['TR','IR','RU','EU'])assert.ok(data.records.some(x=>x.category==='rail'&&x.country===country&&x.verified),'Missing sourced rail country: '+country);
assert.equal(data.records.filter(x=>x.category==='rail'&&x.country==='IQ').length,5);
assert.equal(data.records.filter(x=>x.brand==='TCDD Taşımacılık').length,7);
assert.equal(data.craneGroups.length,8);
assert.equal(data.types.filter(x=>x.category==='cranes').length,37);
assert.equal(data.records.filter(x=>x.category==='cranes').length,47);
const crane=id=>data.records.find(r=>r.id===id);
assert.equal(crane('crane-shuttlelift').specs['Maximum lifting capacity'],'18.1437 t (20 US t)','Short tons must not be presented as metric tonnes');
assert.equal(crane('crane-rambiz').specs['Maximum tandem lifting capacity'],'3300 t','Combined crane rating must be identified');
assert.equal(crane('crane-grt8100').specs['Maximum tip height'],'73 m','Tip height is not hook height');
assert.equal(crane('crane-rikon-rmg').specs['Rail span'],'25 m','Do not mix base RMG configuration with optional spans');
assert.equal(crane('crane-zlk').specs['Boom / jib length'],'Not applicable — bridge / gantry structure');
const cars=data.records.filter(r=>r.category==='cars');
assert.equal(cars.length,76);assert.equal(data.brands.cars.length,25);assert.equal(data.carGroups.length,3);
assert.deepEqual([...new Set(cars.map(r=>r.brand))].sort(),data.brands.cars);
const car=id=>cars.find(r=>r.id===id);
assert.equal(car('toyota-corolla').specs['Kerb weight'],'1345 kg');
assert.equal(car('bmw-1-series').specs['EC unladen weight including driver'],'1500 kg');
assert.equal(car('audi-a3').specs['Mass excluding driver'],'1315 kg');
assert.equal(car('audi-a3').specs['Mass including driver'],'1390 kg');
assert.equal(car('renault-clio').specs['Body width (mirrors excluded)'],undefined);
assert.equal(car('chery-tiggo7').specs['Tare mass'],'1489 kg');
assert.notEqual(car('toyota-corolla-touring').photo,car('toyota-hatch').photo,'Estate and hatchback photographs must differ');
console.log(`PASS: ${data.categories.length} categories, ${data.types.length} types, ${data.records.length} records, ${data.records.filter(x=>x.verified).length} source-backed records; translated labels and country separation validated.`);
