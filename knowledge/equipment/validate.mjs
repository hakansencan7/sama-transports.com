import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=new URL('./',import.meta.url),data=JSON.parse(fs.readFileSync(new URL('catalog.json',base),'utf8'));
const dict=JSON.parse(fs.readFileSync(new URL('equipment-i18n.js',base),'utf8').match(/register\((.*)\);/s)[1]);
for(const collection of [data.categories,data.types,data.records])assert.equal(new Set(collection.map(x=>x.id)).size,collection.length,'Duplicate ID');
for(const item of [...data.categories,...data.types])for(const lang of ['en','tr','ar'])assert.ok(dict[item.name]?.[lang],`Missing ${lang}: ${item.name}`);
for(const row of data.records){
 const type=data.types.find(x=>x.id===row.type);assert.equal(type?.category,row.category);
 if(row.category==='rail')assert.ok(row.country,'Rail record must identify country');
 if(row.verified){assert.match(row.source,/^https:\/\//);assert.ok(row.checked);assert.ok(row.variant);assert.ok(Object.keys(row.specs).length);}
 else assert.equal(Object.keys(row.specs).length,0,'Unverified reference may not invent specifications');
 for(const key of Object.keys(row.specs))for(const lang of ['en','tr','ar'])assert.ok(dict[key]?.[lang],`Missing ${lang}: ${key}`);
 if(row.photo)assert.match(row.photo,/^https:\/\//);
}
for(const country of ['TR','IR','RU'])assert.ok(data.records.some(x=>x.category==='rail'&&x.country===country&&x.verified),'Missing sourced rail country: '+country);
console.log(`PASS: ${data.categories.length} categories, ${data.types.length} types, ${data.records.length} records, ${data.records.filter(x=>x.verified).length} source-backed records; translated labels and country separation validated.`);
