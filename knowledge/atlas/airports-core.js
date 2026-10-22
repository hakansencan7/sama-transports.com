/* Shared pure airport filtering, testable without the map or browser. */
(function(root){
 'use strict';
 const TYPES={large_airport:'Large airport',medium_airport:'Medium airport',small_airport:'Small airport / airfield',heliport:'Heliport',seaplane_base:'Seaplane base',balloonport:'Balloonport',closed:'Closed airport'};
 const normal=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/ı/g,'i').toLowerCase();
 function decode(data){return data.airports.map(values=>{const row=Object.fromEntries(data.columns.map((key,index)=>[key,values[index]]));row.search=normal([row.ident,row.name,row.city,row.iata,row.icao,row.country,data.countries[row.country]?.name].join(' '));return row;});}
 function filter(rows,state){const tokens=normal(state.search).trim().split(/\s+/).filter(Boolean);const found=rows.filter(r=>{
  if(state.country&&r.country!==state.country)return false;
  if(state.continent&&state.continent!==r.continent)return false;
  if(state.countrySet&&!state.countrySet.has(r.country))return false;
  if(r.type==='closed'&&!state.closed)return false;
  if(state.type&&state.type!=='all'&&r.type!=='closed'){
   if(state.type==='airports'){if(!['large_airport','medium_airport','small_airport'].includes(r.type))return false;}
   else if(r.type!==state.type)return false;
  }
  if(state.scheduled&&!r.scheduled)return false;
  return tokens.every(token=>r.search.includes(token));
 });const code=normal(state.search).trim();const exact=tokens.length===1?found.filter(r=>[r.iata,r.icao,r.ident].some(value=>value&&normal(value)===code)):[];return exact.length?exact:found;}
 const api={TYPES,normal,decode,filter};root.SamaAirports=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof window==='object'?window:globalThis);
