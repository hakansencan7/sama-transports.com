from fastapi import HTTPException, Request
from pydantic import BaseModel

class MaintenanceStartIn(BaseModel):
    plate: str
    reason: str = ""

class MaintenanceFinishIn(BaseModel):
    work_done: str


def register_maintenance_ops(app, db, audit):
    def ensure_schema(c):
        c.executescript("""
        CREATE TABLE IF NOT EXISTS maintenance_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          plate TEXT NOT NULL,
          previous_state TEXT DEFAULT 'BOSTA',
          reason TEXT DEFAULT '',
          work_done TEXT DEFAULT '',
          started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          finished_at DATETIME,
          started_by TEXT DEFAULT '',
          finished_by TEXT DEFAULT '',
          is_active INTEGER DEFAULT 1
        );
        """)

    @app.get('/api/maintenance-operations')
    def maintenance_operations(active_only: int = 0):
        c=db(); ensure_schema(c)
        sql="SELECT * FROM maintenance_events"
        if active_only: sql+=" WHERE is_active=1"
        sql+=" ORDER BY id DESC"
        rows=[dict(r) for r in c.execute(sql).fetchall()]
        c.commit();c.close();return rows

    @app.post('/api/maintenance-operations/start')
    def maintenance_start(x: MaintenanceStartIn, request: Request):
        plate=x.plate.strip().upper()
        if not plate: raise HTTPException(400,'Plaka gerekli.')
        c=db(); ensure_schema(c)
        if c.execute("SELECT 1 FROM maintenance_events WHERE UPPER(plate)=UPPER(?) AND is_active=1",(plate,)).fetchone():
            c.close();raise HTTPException(409,'Araç zaten bakımda.')
        fv=c.execute("SELECT garage_state FROM fleet_vehicles WHERE UPPER(plate)=UPPER(?) AND is_active=1",(plate,)).fetchone()
        if not fv: c.close();raise HTTPException(404,'Aktif filo aracında plaka bulunamadı.')
        vo=c.execute("SELECT gps_state,vessel_state FROM vehicle_operations WHERE UPPER(plate)=UPPER(?)",(plate,)).fetchone()
        trip=c.execute("SELECT status,exit_done,entry_done FROM trips WHERE UPPER(plate)=UPPER(?) AND COALESCE(is_deleted,0)=0 ORDER BY CASE WHEN status='Yolda' AND entry_done=0 THEN 0 ELSE 1 END,id DESC LIMIT 1",(plate,)).fetchone()
        previous='BOSTA'
        if vo and (vo['vessel_state'] or '')=='CALISIYOR': previous='GEMIDE'
        elif vo and (vo['gps_state'] or '')=='DONUYOR': previous='DONUYOR'
        elif trip and int(trip['exit_done'] or 0)==1 and int(trip['entry_done'] or 0)==0: previous='YOLDA'
        elif trip and (trip['status'] or '')=='Bekliyor': previous='BEKLEMEDE'
        user=getattr(request.state,'auth_user',{}) or {}
        c.execute("INSERT INTO maintenance_events(plate,previous_state,reason,started_at,started_by,is_active) VALUES(?,?,?,DATETIME('now','localtime'),?,1)",(plate,previous,(x.reason or '').strip(),user.get('username','')))
        c.execute("UPDATE fleet_vehicles SET garage_state='BAKIM',updated_at=CURRENT_TIMESTAMP WHERE UPPER(plate)=UPPER(?)",(plate,))
        c.commit();c.close();audit('MAINTENANCE_START',plate,f'Bakıma alındı | Önceki durum: {previous} | Neden: {x.reason}','FILO',previous,'BAKIM')
        return {'ok':True,'plate':plate,'previous_state':previous}

    @app.post('/api/maintenance-operations/{event_id}/finish')
    def maintenance_finish(event_id:int,x:MaintenanceFinishIn,request:Request):
        if not (x.work_done or '').strip(): raise HTTPException(400,'Yapılan işlemler zorunlu.')
        c=db();ensure_schema(c)
        row=c.execute("SELECT * FROM maintenance_events WHERE id=? AND is_active=1",(event_id,)).fetchone()
        if not row: c.close();raise HTTPException(404,'Aktif bakım kaydı bulunamadı.')
        user=getattr(request.state,'auth_user',{}) or {}
        c.execute("UPDATE maintenance_events SET work_done=?,finished_at=DATETIME('now','localtime'),finished_by=?,is_active=0 WHERE id=?",((x.work_done or '').strip(),user.get('username',''),event_id))
        c.execute("UPDATE fleet_vehicles SET garage_state=CASE WHEN ?='BOSTA' THEN 'GARAGE' ELSE 'DISARIDA' END,updated_at=CURRENT_TIMESTAMP WHERE UPPER(plate)=UPPER(?)",(row['previous_state'],row['plate']))
        c.commit();c.close();audit('MAINTENANCE_FINISH',row['plate'],f"Bakım bitti | Yapılan işlemler: {x.work_done} | Geri dönüş: {row['previous_state']}",'FILO','BAKIM',row['previous_state'])
        return {'ok':True,'plate':row['plate'],'return_state':row['previous_state']}
