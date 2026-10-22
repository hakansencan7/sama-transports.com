import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=new URL('./',import.meta.url),data=JSON.parse(fs.readFileSync(new URL('catalog.json',base),'utf8'));
const dict=JSON.parse(fs.readFileSync(new URL('equipment-i18n.js',base),'utf8').match(/register\((.*)\);/s)[1]);
for(const collection of [data.categories,data.types,data.records])assert.equal(new Set(collection.map(x=>x.id)).size,collection.length,'Duplicate ID');
for(const item of [...data.categories,...data.types,...(data.seaGroups||[])])for(const lang of ['en','tr','ar'])assert.ok(dict[item.name]?.[lang],`Missing ${lang}: ${item.name}`);
for(const row of data.records){
 const type=data.types.find(x=>x.id===row.type);assert.equal(type?.category,row.category);
 if(row.category==='rail')assert.ok(row.country,'Rail record must identify country');
 if(row.verified){assert.match(row.source,/^https:\/\//);assert.ok(row.checked);assert.ok(row.variant);assert.ok(Object.keys(row.specs).length);}
 else assert.equal(Object.keys(row.specs).length,0,'Unverified reference may not invent specifications');
 for(const key of Object.keys(row.specs))for(const lang of ['en','tr','ar'])assert.ok(dict[key]?.[lang],`Missing ${lang}: ${key}`);
 if(row.photo){
  if(row.photo.startsWith('/assets/knowledge/vessels/')){
   assert.match(row.photo,/^\/assets\/knowledge\/vessels\/[a-z-]+\.webp$/);
   const image=new URL('../..'+row.photo,base);assert.ok(fs.existsSync(image),`Missing photo: ${row.photo}`);
   assert.ok(fs.statSync(image).size>1000,'Empty photograph');
   for(const key of ['title','author','license','license_url','source','changes'])assert.ok(row.photo_credit?.[key],`Missing photo ${key}: ${row.id}`);
   assert.match(row.photo_credit.source,/^https:\/\/commons\.wikimedia\.org\/wiki\/File:/);
   assert.match(row.photo_credit.license,/^(CC BY|CC0|Public domain)/);
  }else assert.match(row.photo,/^https:\/\//);
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
}
assert.equal(data.records.filter(r=>r.category==='sea'&&r.guide).length,50);
assert.equal(data.seaGroups.length,9);
for(const country of ['TR','IR','RU'])assert.ok(data.records.some(x=>x.category==='rail'&&x.country===country&&x.verified),'Missing sourced rail country: '+country);
console.log(`PASS: ${data.categories.length} categories, ${data.types.length} types, ${data.records.length} records, ${data.records.filter(x=>x.verified).length} source-backed records; translated labels and country separation validated.`);
