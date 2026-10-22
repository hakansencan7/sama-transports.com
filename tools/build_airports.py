"""Build the public worldwide airport atlas from OurAirports CSV snapshots."""
import csv, gzip, hashlib, io, json, math
from pathlib import Path
import argparse, urllib.request

ROOT=Path(__file__).resolve().parents[1]
BASE='https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/'

def build(cache, output, date):
    cache.mkdir(parents=True,exist_ok=True);output.mkdir(parents=True,exist_ok=True)
    raw={}
    for name in ('airports','countries','runways'):
        path=cache/(name+'.csv')
        if not path.exists():path.write_bytes(urllib.request.urlopen(BASE+name+'.csv',timeout=90).read())
        raw[name]=path.read_bytes()
    def rows(name):return csv.DictReader(io.StringIO(raw[name].decode('utf-8-sig')))
    countries={r['code']:{'name':r['name'],'continent':r['continent']} for r in rows('countries')}
    runways={}
    for r in rows('runways'):
        if r['closed']=='1':continue
        try:length=round(float(r['length_ft'])*0.3048)
        except (ValueError,TypeError):continue
        old=runways.get(r['airport_ident'])
        if not old or length>old[0]:runways[r['airport_ident']]=[length,r['surface'],r['lighted']=='1']
    records=[];seen=set();unlocated=0
    for r in rows('airports'):
        ident=r['ident']
        if ident in seen:raise ValueError('Duplicate airport identifier: '+ident)
        seen.add(ident)
        try:
            lat,lon=float(r['latitude_deg']),float(r['longitude_deg'])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):raise ValueError()
            point=[round(lat,6),round(lon,6)]
        except (ValueError,TypeError):point=None;unlocated+=1
        records.append([ident,r['name'],r['type'],r['iso_country'],r['municipality'],r['iata_code'],r.get('icao_code') or '',point,
            r['scheduled_service']=='yes',r['elevation_ft'],r['home_link'],r['wikipedia_link'],runways.get(ident)])
    data={'date':date,'columns':['ident','name','type','country','city','iata','icao','point','scheduled','elevation_ft','website','wikipedia','runway'],
          'countries':countries,'airports':records}
    content=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
    (output/'world-airports.json.gz').write_bytes(gzip.compress(content,compresslevel=9,mtime=0))
    (output/'world-airports.json').write_bytes(content)
    manifest={'source':'OurAirports','url':'https://ourairports.com/data/','license':'Public Domain',
        'retrieved':date,'records':len(records),'countries':len({r[3] for r in records}), 'unlocated':unlocated,
        'source_files':{n:{'url':BASE+n+'.csv','sha256':hashlib.sha256(b).hexdigest()} for n,b in raw.items()}}
    (output/'airports-source.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**{k:manifest[k] for k in ('records','countries','unlocated')},'gzip_bytes':(output/'world-airports.json.gz').stat().st_size}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--date',required=True)
    args=p.parse_args();build(args.cache,ROOT/'knowledge/atlas/data',args.date)
