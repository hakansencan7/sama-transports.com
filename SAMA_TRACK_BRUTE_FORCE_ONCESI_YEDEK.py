
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import sqlite3
import uvicorn
from io import BytesIO
from datetime import datetime, date
import requests
import re
import html as html_lib
import base64
import hashlib
import secrets
import hmac
import time
from fastapi.responses import Response

BASE = Path(__file__).resolve().parent
DB = BASE / "sevkiyat.db"

app = FastAPI(title="SAMA TRACK V63")

AUTH_FILE = Path.home() / "sama_auth.conf"

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Login ve logout sayfaları kimlik doğrulaması olmadan erişilebilir.
    if path in ("/login", "/logout"):
        return await call_next(request)

    session = request.cookies.get("sama_session", "")

    if not session:
        if path.startswith("/api/"):
            return Response(
                content="Authentication required",
                status_code=401,
            )
        return Response(
            content="Redirecting to login...",
            status_code=302,
            headers={"Location": "/login"},
        )

    try:
        padding = "=" * (-len(session) % 4)
        decoded = base64.urlsafe_b64decode(session + padding)
        parts = decoded.decode("utf-8").split("|", 2)

        if len(parts) != 3:
            raise ValueError("invalid session")

        username, expires_text, signature = parts
        expires = int(expires_text)

        config = {}
        for line in AUTH_FILE.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

        expected_user = config.get("KULLANICI", "")
        session_secret = config.get("SESSION_SECRET", "")

        payload = f"{username}|{expires}".encode("utf-8")
        expected_signature = hmac.new(
            session_secret.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()

        if expires < int(time.time()):
            raise ValueError("session expired")

        if not secrets.compare_digest(username, expected_user):
            raise ValueError("invalid user")

        if not secrets.compare_digest(signature, expected_signature):
            raise ValueError("invalid signature")

    except Exception:
        if path.startswith("/api/"):
            return Response(
                content="Authentication required",
                status_code=401,
            )
        return Response(
            content="Redirecting to login...",
            status_code=302,
            headers={"Location": "/login"},
        )

    return await call_next(request)


@app.get("/logout", response_class=HTMLResponse)
async def logout_page():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Logged Out - SAMA TRACK</title>
<style>
*{box-sizing:border-box}
body{
  margin:0;
  font-family:Segoe UI,Arial,sans-serif;
  background:#f4f7fb;
  color:#1f2937;
}
.logout-header{
  background:#173b5c;
  color:white;
  padding:18px 28px;
  display:flex;
  justify-content:space-between;
  align-items:center;
}
.logo{
  font-size:24px;
  font-weight:800;
  letter-spacing:.3px;
}
.logo span{color:#38bdf8}
.header-text{font-size:14px;opacity:.9}
.logout-wrap{
  min-height:calc(100vh - 70px);
  display:flex;
  align-items:center;
  justify-content:center;
  padding:30px 16px;
}
.logout-card{
  width:min(620px,94vw);
  background:white;
  border-radius:16px;
  padding:42px 32px;
  text-align:center;
  box-shadow:0 8px 30px #00000012;
}
.check{
  width:68px;
  height:68px;
  margin:0 auto 22px;
  border-radius:50%;
  background:#dcfce7;
  color:#16a34a;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:38px;
  font-weight:800;
}
h1{
  margin:0 0 12px;
  color:#173b5c;
  font-size:32px;
}
p{
  margin:8px 0;
  color:#64748b;
  font-size:16px;
}
.login-btn{
  display:inline-block;
  margin-top:24px;
  padding:12px 25px;
  border-radius:9px;
  background:#2563eb;
  color:white;
  text-decoration:none;
  font-weight:700;
}
.login-btn:hover{background:#1d4ed8}
.line{
  height:1px;
  background:#e5e7eb;
  margin:30px 0 18px;
}
.footer{
  color:#64748b;
  font-size:14px;
}
</style>
</head>
<body>
<header class="logout-header">
  <div class="logo">SAMA <span>TRACK</span></div>
  <div class="header-text">Transport Management System</div>
</header>

<main class="logout-wrap">
  <section class="logout-card">
    <div class="check">✓</div>
    <h1>You Have Been Logged Out</h1>
    <p>Your session has been securely terminated.</p>
    <p>You have been signed out of SAMA TRACK.</p>

    <a class="login-btn" href="/">↪ Login Again</a>

    <div class="line"></div>
    <div class="footer">
      We wish you a safe journey.<br>
      <em>SAMA TRACK Team</em>
    </div>
  </section>
</main>
</body>
</html>
""", headers={"Cache-Control": "no-store", "Set-Cookie": "sama_session=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Strict"})

@app.post("/login")
async def login_submit(request: Request):
    try:
        data = await request.json()
        username = str(data.get("username", ""))
        password = str(data.get("password", ""))

        config = {}
        for line in AUTH_FILE.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

        expected_user = config.get("KULLANICI", "")
        expected_hash = config.get("HASH", "")

        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        if (
            not secrets.compare_digest(username, expected_user)
            or not secrets.compare_digest(password_hash, expected_hash)
        ):
            return Response(content="Invalid username or password", status_code=401)

        session_secret = config.get("SESSION_SECRET", "")
        expires = int(time.time()) + 28800
        payload = f"{username}|{expires}".encode("utf-8")
        signature = hmac.new(
            session_secret.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()

        token = base64.urlsafe_b64encode(
            payload + b"|" + signature.encode("ascii")
        ).decode("ascii").rstrip("=")

        return Response(
            content="Login successful",
            status_code=200,
            headers={
                "Set-Cookie": (
                    f"sama_session={token}; "
                    "Max-Age=28800; Path=/; "
                    "HttpOnly; Secure; SameSite=Strict"
                )
            }
        )

    except Exception:
        return Response(content="Invalid login request", status_code=400)


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login - SAMA TRACK</title>
<style>
*{box-sizing:border-box}
body{
  margin:0;
  font-family:Segoe UI,Arial,sans-serif;
  background:#f4f7fb;
  color:#1f2937;
}
.login-header{
  background:#173b5c;
  color:white;
  padding:18px 28px;
  display:flex;
  justify-content:space-between;
  align-items:center;
}
.logo{
  font-size:24px;
  font-weight:800;
  letter-spacing:.3px;
}
.logo span{color:#38bdf8}
.header-text{font-size:14px;opacity:.9}
.login-wrap{
  min-height:calc(100vh - 70px);
  display:flex;
  align-items:center;
  justify-content:center;
  padding:30px 16px;
}
.login-card{
  width:min(440px,94vw);
  background:white;
  border-radius:16px;
  padding:38px 32px;
  box-shadow:0 8px 30px #00000012;
}
.check{
  width:58px;
  height:58px;
  margin:0 auto 18px;
  border-radius:50%;
  background:#e0f2fe;
  color:#2563eb;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:28px;
}
h1{
  margin:0 0 8px;
  text-align:center;
  color:#173b5c;
  font-size:28px;
}
.subtitle{
  text-align:center;
  color:#64748b;
  margin-bottom:26px;
}
label{
  display:block;
  margin:14px 0 6px;
  font-size:13px;
  font-weight:700;
  color:#475569;
}
input{
  width:100%;
  padding:12px 13px;
  border:1px solid #d1d5db;
  border-radius:9px;
  font-size:15px;
}
input:focus{
  outline:none;
  border-color:#2563eb;
  box-shadow:0 0 0 3px #2563eb18;
}
.login-btn{
  width:100%;
  margin-top:22px;
  padding:12px;
  border:0;
  border-radius:9px;
  background:#2563eb;
  color:white;
  font-weight:700;
  font-size:15px;
  cursor:pointer;
}
.login-btn:hover{background:#1d4ed8}
.error{
  display:none;
  margin-top:14px;
  padding:10px;
  border-radius:8px;
  background:#fee2e2;
  color:#991b1b;
  text-align:center;
  font-size:13px;
}
.line{
  height:1px;
  background:#e5e7eb;
  margin:28px 0 18px;
}
.footer{
  text-align:center;
  color:#64748b;
  font-size:13px;
}
</style>
</head>
<body>
<header class="login-header">
  <div class="logo">SAMA <span>TRACK</span></div>
  <div class="header-text">Transport Management System</div>
</header>

<main class="login-wrap">
  <section class="login-card">
    <div class="check">↪</div>
    <h1>Login to Your Account</h1>
    <div class="subtitle">Sign in to access SAMA TRACK</div>

    <form onsubmit="return doLogin(event)">
      <label for="username">Username</label>
      <input id="username" name="username" autocomplete="username" required>

      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required>

      <button class="login-btn" type="submit">Login</button>
      <div id="error" class="error">Invalid username or password.</div>
    </form>

    <div class="line"></div>
    <div class="footer">
      Reliable Logistics, Stronger Tomorrow.<br>
      <em>SAMA TRACK Team</em>
    </div>
  </section>
</main>

<script>
async function doLogin(event){
  event.preventDefault();

  const username=document.getElementById('username').value;
  const password=document.getElementById('password').value;

  const r=await fetch('/login',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username,password})
  });

  if(r.ok){
    window.location.href='/';
  }else{
    document.getElementById('error').style.display='block';
  }

  return false;
}
</script>
</body>
</html>
""", headers={"Cache-Control": "no-store"})

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def addcol(c, table, col, definition):
    cols = [r["name"] for r in c.execute(f"PRAGMA table_info({table})")]
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS drivers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      phone TEXT DEFAULT '',
      d_no TEXT DEFAULT '',
      active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS vehicles(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      plate TEXT NOT NULL UNIQUE,
      driver_id INTEGER,
      active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS areas(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      km_go REAL DEFAULT 0,
      km_back REAL DEFAULT 0,
      active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS cargo_categories(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS customers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS trips(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      scna TEXT NOT NULL UNIQUE,
      plate TEXT NOT NULL,
      driver_id INTEGER,
      area_id INTEGER,
      trip_date TEXT,

      net_kg REAL DEFAULT 0,
      freight_rate REAL DEFAULT 0,
      freight_basis TEXT DEFAULT 'TON',
      cargo_category_id INTEGER,
      cargo_type TEXT DEFAULT 'BULK',
      customer_id INTEGER,

      exit_km REAL DEFAULT 0,
      exit_cash REAL DEFAULT 0,

      tank_start_liters REAL DEFAULT 0,
      dock_fee REAL DEFAULT 0,
      port_fee REAL DEFAULT 0,
      sonar REAL DEFAULT 0,

      exit_official_fuel_liters REAL DEFAULT 0,
      exit_official_fuel_total REAL DEFAULT 0,

      exit_commercial_fuel_liters REAL DEFAULT 0,
      exit_commercial_fuel_total REAL DEFAULT 0,

      exit_baghdad_fuel_liters REAL DEFAULT 0,
      exit_baghdad_fuel_total REAL DEFAULT 0,

      exit_allowance REAL DEFAULT 0,
      exit_premium REAL DEFAULT 0,
      exit_other REAL DEFAULT 0,
      exit_note TEXT DEFAULT '',
      exit_done INTEGER DEFAULT 0,
      exit_at DATETIME,

      entry_km REAL DEFAULT 0,
      tank_end_liters REAL DEFAULT 0,

      entry_extra_expense_1 REAL DEFAULT 0,
      entry_extra_expense_2 REAL DEFAULT 0,
      entry_extra_expense_3 REAL DEFAULT 0,

      entry_collection REAL DEFAULT 0,
      entry_cash_handed REAL DEFAULT 0,
      excel_price_k REAL,
      excel_freight_au REAL,
      excel_amount REAL,
      excel_remain REAL,
      delivery_time TEXT DEFAULT '',
      entry_note TEXT DEFAULT '',
      entry_done INTEGER DEFAULT 0,
      entry_at DATETIME,

      status TEXT DEFAULT 'Bekliyor',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS fuel_purchases(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      scna TEXT NOT NULL,
      liters REAL DEFAULT 0,
      total REAL DEFAULT 0,
      note TEXT DEFAULT '',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      action TEXT,
      scna TEXT,
      detail TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS route_standards(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      area_id INTEGER UNIQUE,
      expected_hours REAL DEFAULT 48,
      expected_km REAL DEFAULT 0,
      expected_l100 REAL DEFAULT 40,
      tolerance_percent REAL DEFAULT 10,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS fleet_vehicles(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      plate TEXT NOT NULL UNIQUE,
      brand TEXT DEFAULT '',
      model TEXT DEFAULT '',
      vehicle_type TEXT DEFAULT 'DAMPER',
      is_active INTEGER DEFAULT 1,
      garage_state TEXT DEFAULT 'GARAGE',
      note TEXT DEFAULT '',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS fleet_drivers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      phone TEXT DEFAULT '',
      d_no TEXT DEFAULT '',
      is_active INTEGER DEFAULT 1,
      note TEXT DEFAULT '',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS vehicle_operations(
      plate TEXT PRIMARY KEY,
      load_state TEXT DEFAULT 'BOS',
      queue_no INTEGER DEFAULT 0,
      vessel TEXT DEFAULT '',
      operation_note TEXT DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS maintenance(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      plate TEXT NOT NULL,
      last_service_km REAL DEFAULT 0,
      next_service_km REAL DEFAULT 0,
      oil_change_km REAL DEFAULT 0,
      tire_note TEXT DEFAULT '',
      brake_note TEXT DEFAULT '',
      engine_note TEXT DEFAULT '',
      note TEXT DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Migrations from older versions
    addcol(c, "trips", "net_kg", "REAL DEFAULT 0")
    addcol(c, "trips", "freight_rate", "REAL DEFAULT 0")
    addcol(c, "trips", "freight_basis", "TEXT DEFAULT 'TON'")
    addcol(c, "trips", "entry_collection", "REAL DEFAULT 0")
    addcol(c, "trips", "entry_cash_handed", "REAL DEFAULT 0")
    addcol(c, "trips", "excel_price_k", "REAL")
    addcol(c, "trips", "excel_freight_au", "REAL")
    addcol(c, "trips", "excel_amount", "REAL")
    addcol(c, "trips", "excel_remain", "REAL")
    addcol(c, "trips", "entry_extra_expense_1", "REAL DEFAULT 0")
    addcol(c, "trips", "entry_extra_expense_2", "REAL DEFAULT 0")
    addcol(c, "trips", "entry_extra_expense_3", "REAL DEFAULT 0")

    addcol(c, "trips", "tank_start_liters", "REAL DEFAULT 0")
    addcol(c, "trips", "tank_end_liters", "REAL DEFAULT 0")

    addcol(c, "trips", "exit_official_fuel_liters", "REAL DEFAULT 0")
    addcol(c, "trips", "exit_official_fuel_total", "REAL DEFAULT 0")
    addcol(c, "trips", "exit_commercial_fuel_liters", "REAL DEFAULT 0")
    addcol(c, "trips", "exit_commercial_fuel_total", "REAL DEFAULT 0")
    addcol(c, "trips", "exit_baghdad_fuel_liters", "REAL DEFAULT 0")
    addcol(c, "trips", "exit_baghdad_fuel_total", "REAL DEFAULT 0")
    addcol(c, "trips", "cargo_category_id", "INTEGER")
    addcol(c, "trips", "cargo_type", "TEXT DEFAULT 'BULK'")
    addcol(c, "trips", "customer_id", "INTEGER")
    addcol(c, "trips", "dock_fee", "REAL DEFAULT 0")
    addcol(c, "trips", "port_fee", "REAL DEFAULT 0")
    addcol(c, "trips", "sonar", "REAL DEFAULT 0")
    addcol(c, "trips", "delivery_time", "TEXT DEFAULT ''")
    addcol(c, "trips", "manual_lock", "INTEGER DEFAULT 0")
    addcol(c, "trips", "manual_lock_at", "TEXT DEFAULT ''")
    addcol(c, "trips", "manual_lock_reason", "TEXT DEFAULT ''")

    if c.execute("SELECT COUNT(*) c FROM drivers").fetchone()["c"] == 0:
        c.executemany(
            "INSERT INTO drivers(name,phone,d_no) VALUES(?,?,?)",
            [
                ("Ali Hassan", "+964700000001", "D001"),
                ("Ahmed Kareem", "+964700000002", "D002"),
                ("Hassan Ali", "+964700000003", "D003"),
                ("Omar Saad", "+964700000004", "D004"),
            ]
        )

    if c.execute("SELECT COUNT(*) c FROM vehicles").fetchone()["c"] == 0:
        ids = {r["name"]: r["id"] for r in c.execute("SELECT id,name FROM drivers")}
        c.executemany(
            "INSERT INTO vehicles(plate,driver_id) VALUES(?,?)",
            [
                ("21L15441", ids["Ali Hassan"]),
                ("22L28424", ids["Ahmed Kareem"]),
                ("22K29376", ids["Hassan Ali"]),
                ("22B34933", ids["Omar Saad"]),
            ]
        )

    if c.execute("SELECT COUNT(*) c FROM areas").fetchone()["c"] == 0:
        c.executemany(
            "INSERT INTO areas(name,km_go,km_back) VALUES(?,?,?)",
            [
                ("Basra", 70, 70),
                ("Baghdad", 600, 600),
                ("Najaf", 520, 520),
                ("Erbil", 950, 950),
                ("Karbala", 570, 570),
                ("Nasiriya", 250, 250),
            ]
        )

    if c.execute("SELECT COUNT(*) c FROM cargo_categories").fetchone()["c"] == 0:
        c.executemany(
            "INSERT INTO cargo_categories(name) VALUES(?)",
            [
                ("Mısır",),
                ("Buğday",),
                ("Arpa",),
                ("Pirinç",),
                ("Un",),
                ("Gübre",),
                ("Diğer",),
            ]
        )

    if c.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"] == 0:
        c.executemany(
            "INSERT INTO customers(name) VALUES(?)",
            [
                ("SAMA ALMANAR",),
                ("FREIGHT",),
                ("DİĞER",),
            ]
        )

    for a in c.execute("SELECT id,name,km_go,km_back FROM areas").fetchall():
        if not c.execute("SELECT 1 FROM route_standards WHERE area_id=?",(a["id"],)).fetchone():
            total_km=float(a["km_go"] or 0)+float(a["km_back"] or 0)
            name=str(a["name"] or "").upper()
            expected_hours=48
            if "BASRA" in name: expected_hours=12
            elif "NASIRI" in name: expected_hours=24
            elif "BAGHDAD" in name or "BAGDAT" in name: expected_hours=36
            elif "NAJAF" in name or "KARBALA" in name: expected_hours=48
            elif "ERBIL" in name: expected_hours=72
            c.execute(
                "INSERT INTO route_standards(area_id,expected_hours,expected_km,expected_l100,tolerance_percent) VALUES(?,?,?,?,?)",
                (a["id"],expected_hours,total_km,40,10)
            )

    c.execute("""
      INSERT OR IGNORE INTO fleet_vehicles(plate)
      SELECT DISTINCT UPPER(TRIM(plate))
      FROM trips
      WHERE TRIM(COALESCE(plate,''))<>''
    """)

    c.execute("""
      INSERT INTO fleet_drivers(name,phone,d_no)
      SELECT d.name,COALESCE(d.phone,''),COALESCE(d.d_no,'')
      FROM drivers d
      WHERE TRIM(COALESCE(d.name,''))<>''
        AND NOT EXISTS(
          SELECT 1 FROM fleet_drivers fd
          WHERE UPPER(TRIM(fd.name))=UPPER(TRIM(d.name))
        )
    """)

    c.commit()
    c.close()

@app.on_event("startup")
def startup():
    init_db()

class TripCreate(BaseModel):
    scna: str
    plate: str
    driver_id: Optional[int] = None
    area_id: Optional[int] = None
    cargo_category_id: Optional[int] = None
    cargo_type: str = "BULK"
    customer_id: Optional[int] = None
    trip_date: str = ""
    net_kg: float = 0
    freight_rate: float = 0
    freight_basis: str = "TON"
    exit_km: float = 0
    tank_start_liters: float = 0
    exit_premium: float = 0
    dock_fee: float = 0
    port_fee: float = 0
    sonar: float = 0

class ExitIn(BaseModel):
    exit_km: float = 0
    exit_cash: float = 0

    tank_start_liters: float = 0

    exit_official_fuel_liters: float = 0
    exit_official_fuel_total: float = 0

    exit_commercial_fuel_liters: float = 0
    exit_commercial_fuel_total: float = 0

    exit_baghdad_fuel_liters: float = 0
    exit_baghdad_fuel_total: float = 0

    exit_allowance: float = 0
    exit_other: float = 0
    exit_note: str = ""

class EntryIn(BaseModel):
    entry_km: float = 0
    tank_end_liters: float = 0

    entry_extra_expense_1: float = 0
    entry_extra_expense_2: float = 0
    entry_extra_expense_3: float = 0

    entry_collection: float = 0
    entry_cash_handed: float = 0
    entry_note: str = ""

class FuelIn(BaseModel):
    liters: float
    total: float
    note: str = ""

class StatusIn(BaseModel):
    status: str

class RouteStandardIn(BaseModel):
    area_id: int
    expected_hours: float = 48
    expected_km: float = 0
    expected_l100: float = 40
    tolerance_percent: float = 10

class MaintenanceIn(BaseModel):
    plate: str
    last_service_km: float = 0
    next_service_km: float = 0
    oil_change_km: float = 0
    tire_note: str = ""
    brake_note: str = ""
    engine_note: str = ""
    note: str = ""

class FleetVehicleIn(BaseModel):
    plate: str
    brand: str = ""
    model: str = ""
    vehicle_type: str = "DAMPER"
    is_active: int = 1
    garage_state: str = "GARAGE"
    note: str = ""

class FleetDriverIn(BaseModel):
    name: str
    phone: str = ""
    d_no: str = ""
    is_active: int = 1
    note: str = ""

class VehicleOperationIn(BaseModel):
    plate: str
    load_state: str = "BOS"
    queue_no: int = 0
    vessel: str = ""
    operation_note: str = ""

class BulkFixIn(BaseModel):
    scnas: list[str] = []
    field: str
    value: str = ""

class TripEditIn(BaseModel):
    plate: str = ""
    driver_id: Optional[int] = None
    area_id: Optional[int] = None
    cargo_category_id: Optional[int] = None
    cargo_type: str = "BULK"
    customer_id: Optional[int] = None
    trip_date: str = ""
    net_kg: float = 0
    freight_rate: float = 0
    freight_basis: str = "KG"
    exit_km: float = 0
    tank_start_liters: float = 0
    exit_premium: float = 0
    dock_fee: float = 0
    port_fee: float = 0
    sonar: float = 0
    exit_allowance: float = 0
    exit_other: float = 0
    entry_km: float = 0
    tank_end_liters: float = 0
    entry_extra_expense_1: float = 0
    entry_extra_expense_2: float = 0
    entry_extra_expense_3: float = 0
    entry_collection: float = 0
    entry_cash_handed: float = 0
    status: str = "Bekliyor"
    note: str = ""

def audit(action, scna, detail=""):
    c = db()
    c.execute(
        "INSERT INTO audit_log(action,scna,detail) VALUES(?,?,?)",
        (action, scna, detail)
    )
    c.commit()
    c.close()

def tq():
    return """
    SELECT
      t.*,
      d.name driver_name,
      d.phone,
      d.d_no,
      a.name area_name,
      a.km_go planned_km_go,
      a.km_back planned_km_back,
      cc.name cargo_name,
      cu.name customer_name,
      t.cargo_type cargo_type_name,

      COALESCE((SELECT vo.vessel FROM vehicle_operations vo
                WHERE UPPER(TRIM(vo.plate))=UPPER(TRIM(t.plate)) LIMIT 1),'') vessel_name,
      COALESCE((SELECT vo.load_state FROM vehicle_operations vo
                WHERE UPPER(TRIM(vo.plate))=UPPER(TRIM(t.plate)) LIMIT 1),'') vessel_operation_state,

      COALESCE(NULLIF(t.entry_at,''), NULLIF(t.delivery_time,'')) entry_display_at,
      CASE
        WHEN COALESCE(NULLIF(t.entry_at,''), NULLIF(t.delivery_time,'')) IS NOT NULL THEN 'Tamamlandı'
        ELSE t.status
      END status_display,

      COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0) road_fuel_total,
      COALESCE((SELECT SUM(f.liters) FROM fuel_purchases f WHERE f.scna=t.scna),0) road_fuel_liters,

      CASE
        WHEN COALESCE((SELECT SUM(f.liters) FROM fuel_purchases f WHERE f.scna=t.scna),0) > 0
        THEN COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0) /
             COALESCE((SELECT SUM(f.liters) FROM fuel_purchases f WHERE f.scna=t.scna),0)
        ELSE 0
      END road_fuel_avg_price,

      CASE
        WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
        ELSE (t.net_kg/1000.0)*t.freight_rate
      END freight_total,

      CASE
        WHEN t.entry_done=1 AND t.exit_km>0 AND t.entry_km>=t.exit_km THEN t.entry_km-t.exit_km
        ELSE 0
      END actual_km,

      CASE
        WHEN t.entry_done=1 AND t.delivery_time<>'' AND t.trip_date<>'' THEN
          ROUND((JULIANDAY(t.delivery_time)-JULIANDAY(t.trip_date))*24,1)
        ELSE 0
      END trip_duration_hours,

      (
        t.tank_start_liters +
        t.exit_official_fuel_liters +
        t.exit_commercial_fuel_liters +
        t.exit_baghdad_fuel_liters +
        COALESCE((SELECT SUM(f.liters) FROM fuel_purchases f WHERE f.scna=t.scna),0)
      ) total_fuel_available,

      CASE
        WHEN t.entry_done=1 AND t.exit_km>0 AND t.entry_km>=t.exit_km THEN
          MAX(
            (
              t.tank_start_liters +
              t.exit_official_fuel_liters +
              t.exit_commercial_fuel_liters +
              t.exit_baghdad_fuel_liters +
              COALESCE((SELECT SUM(f.liters) FROM fuel_purchases f WHERE f.scna=t.scna),0)
            ) - t.tank_end_liters,
            0
          )
        ELSE 0
      END fuel_consumed_liters,

      CASE
        WHEN t.entry_done=1 AND (t.entry_km-t.exit_km)>0 THEN
          (
            MAX(
              (
                t.tank_start_liters +
                t.exit_official_fuel_liters +
                t.exit_commercial_fuel_liters +
                t.exit_baghdad_fuel_liters +
                COALESCE((SELECT SUM(f.liters) FROM fuel_purchases f WHERE f.scna=t.scna),0)
              ) - t.tank_end_liters,
              0
            ) / (t.entry_km-t.exit_km)
          ) * 100
        ELSE 0
      END liters_per_100km,

      CASE
        WHEN t.entry_done=1 AND t.exit_km>0 AND t.entry_km>t.exit_km AND
             MAX(
               (
                 t.tank_start_liters +
                 t.exit_official_fuel_liters +
                 t.exit_commercial_fuel_liters +
                 t.exit_baghdad_fuel_liters +
                 COALESCE((SELECT SUM(f.liters) FROM fuel_purchases f WHERE f.scna=t.scna),0)
               ) - t.tank_end_liters,
               0
             ) > 0
        THEN
          (t.entry_km-t.exit_km) /
          MAX(
            (
              t.tank_start_liters +
              t.exit_official_fuel_liters +
              t.exit_commercial_fuel_liters +
              t.exit_baghdad_fuel_liters +
              COALESCE((SELECT SUM(f.liters) FROM fuel_purchases f WHERE f.scna=t.scna),0)
            ) - t.tank_end_liters,
            0
          )
        ELSE 0
      END km_per_liter,

      (
        t.exit_official_fuel_total +
        t.exit_commercial_fuel_total +
        t.exit_baghdad_fuel_total +
        COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0)
      ) fuel_expense_total,

      (
        t.exit_official_fuel_total +
        t.exit_commercial_fuel_total +
        t.exit_baghdad_fuel_total +
        COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0) +
        t.exit_allowance +
        t.exit_premium +
        t.dock_fee +
        t.port_fee +
        t.sonar +
        t.exit_other +
        t.entry_extra_expense_1 +
        t.entry_extra_expense_2 +
        t.entry_extra_expense_3
      ) total_expense,

      (
        CASE
          WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
          ELSE (t.net_kg/1000.0)*t.freight_rate
        END
      ) -
      (
        t.exit_official_fuel_total +
        t.exit_commercial_fuel_total +
        t.exit_baghdad_fuel_total +
        COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0) +
        t.exit_allowance +
        t.exit_premium +
        t.dock_fee +
        t.port_fee +
        t.sonar +
        t.exit_other +
        t.entry_extra_expense_1 +
        t.entry_extra_expense_2 +
        t.entry_extra_expense_3
      ) trip_profit,

      (
        CASE
          WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
          ELSE (t.net_kg/1000.0)*t.freight_rate
        END
      ) - t.entry_collection amount_due,

      (
        t.exit_official_fuel_total +
        t.exit_commercial_fuel_total +
        t.exit_baghdad_fuel_total +
        COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0)
      ) fuel_to_deduct_from_collection,

      t.entry_collection -
      (
        COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0) +
        t.entry_extra_expense_1 +
        t.entry_extra_expense_2 +
        t.entry_extra_expense_3
      ) expected_cash_handover,

      CASE
        WHEN t.excel_remain IS NOT NULL THEN
          CASE
            WHEN COALESCE(t.entry_collection,0)>0
            THEN t.entry_collection - (
              CASE
                WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate
              END
            )
            ELSE 0
          END
        WHEN COALESCE(t.entry_cash_handed,0)=0
         AND COALESCE(t.entry_collection,0)>0
         AND t.entry_done=1
        THEN t.entry_collection - (
              CASE
                WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate
              END
            )
        ELSE
          t.entry_cash_handed -
          (
            t.entry_collection -
            (
              COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0) +
              t.entry_extra_expense_1 +
              t.entry_extra_expense_2 +
              t.entry_extra_expense_3
            )
          )
      END driver_cash_diff,

      CASE
        WHEN t.entry_done=0 THEN 'AÇIK'
        WHEN ABS(CASE
            WHEN t.excel_remain IS NOT NULL THEN
              CASE
                WHEN COALESCE(t.entry_collection,0)>0
                THEN t.entry_collection - (
              CASE
                WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate
              END
            )
                ELSE 0
              END
            WHEN COALESCE(t.entry_cash_handed,0)=0
             AND COALESCE(t.entry_collection,0)>0
             AND t.entry_done=1
            THEN t.entry_collection - (
              CASE
                WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate
              END
            )
            ELSE
              t.entry_cash_handed -
              (
                t.entry_collection -
                (
                  COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0) +
                  t.entry_extra_expense_1 +
                  t.entry_extra_expense_2 +
                  t.entry_extra_expense_3
                )
              )
          END) < 0.01 THEN 'HESAP TAMAM'
        WHEN (CASE
            WHEN t.excel_remain IS NOT NULL THEN
              CASE
                WHEN COALESCE(t.entry_collection,0)>0
                THEN t.entry_collection - (
              CASE
                WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate
              END
            )
                ELSE 0
              END
            WHEN COALESCE(t.entry_cash_handed,0)=0
             AND COALESCE(t.entry_collection,0)>0
             AND t.entry_done=1
            THEN t.entry_collection - (
              CASE
                WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate
              END
            )
            ELSE
              t.entry_cash_handed -
              (
                t.entry_collection -
                (
                  COALESCE((SELECT SUM(f.total) FROM fuel_purchases f WHERE f.scna=t.scna),0) +
                  t.entry_extra_expense_1 +
                  t.entry_extra_expense_2 +
                  t.entry_extra_expense_3
                )
              )
          END) < 0 THEN 'EKSİK PARA'
        ELSE 'FAZLA PARA'
      END driver_cash_status

    FROM trips t
    LEFT JOIN drivers d ON d.id=t.driver_id
    LEFT JOIN areas a ON a.id=t.area_id
    LEFT JOIN cargo_categories cc ON cc.id=t.cargo_category_id
    LEFT JOIN customers cu ON cu.id=t.customer_id
    """


def _norm_header(v):
    if v is None:
        return ""
    s = str(v).strip().upper()
    repl = {
        "İ":"I","Ş":"S","Ğ":"G","Ü":"U","Ö":"O","Ç":"C",
        "ı":"I","ş":"S","ğ":"G","ü":"U","ö":"O","ç":"C"
    }
    for a,b in repl.items():
        s=s.replace(a,b)
    for ch in [" ", "_", "-", ".", "/", "\\", "(", ")", "[", "]", ":"]:
        s=s.replace(ch,"")
    return s

def _excel_num(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int,float)):
        return float(v)
    s=str(v).strip().replace(" ","")
    if not s:
        return 0.0
    # 1.500.000 / 469.770 gibi IQD formatları
    if "." in s and "," not in s:
        parts=s.split(".")
        if len(parts)>1 and all(len(p)==3 for p in parts[1:]):
            s="".join(parts)
    elif "," in s and "." not in s:
        parts=s.split(",")
        if len(parts)>1 and all(len(p)==3 for p in parts[1:]):
            s="".join(parts)
        else:
            s=s.replace(",",".")
    elif "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s=s.replace(".","").replace(",",".")
        else:
            s=s.replace(",","")
    try:
        return float(s)
    except:
        return 0.0


def _excel_optional_num(v):
    if v is None:
        return None
    s=str(v).strip()
    if s in ("", "-", "—", ".", "#VALUE!", "#DEĞER!", "#N/A", "#SAYI/0!"):
        return None
    return _excel_num(v)

def _excel_date(v):
    if v is None or v == "":
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    # Excel serial date: örn. 45999
    if isinstance(v, (int,float)) and 20000 < float(v) < 80000:
        try:
            from openpyxl.utils.datetime import from_excel
            return from_excel(v).strftime("%Y-%m-%d")
        except:
            pass
    s=str(v).strip()
    for fmt in ("%d.%m.%Y","%d/%m/%Y","%Y-%m-%d","%d-%m-%Y"):
        try:
            return datetime.strptime(s,fmt).strftime("%Y-%m-%d")
        except:
            pass
    return s[:10]

def _excel_datetime(v):
    if v is None or v == "":
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return datetime(v.year,v.month,v.day).strftime("%Y-%m-%d 00:00:00")
    if isinstance(v, (int,float)) and 20000 < float(v) < 80000:
        try:
            from openpyxl.utils.datetime import from_excel
            return from_excel(v).strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass

    s=str(v).strip()
    if s in ("", ".", "-", "—", "#VALUE!", "#DEĞER!", "#N/A", "#SAYI/0!"):
        return ""

    for fmt in (
        "%d.%m.%Y","%d/%m/%Y","%Y-%m-%d",
        "%d-%m-%Y","%d.%m.%Y %H:%M","%Y-%m-%d %H:%M:%S"
    ):
        try:
            return datetime.strptime(s,fmt).strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
    return s

def _first(row, headers, aliases, default=None):
    for alias in aliases:
        k=_norm_header(alias)
        if k in headers:
            val=row[headers[k]]
            if val is not None and str(val).strip()!="":
                return val
    return default

@app.post("/api/import-excel")
async def import_excel(request: Request, filename: str = "", update_existing: int = 0, preview_only: int = 0, skip_warnings: int = 0):
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise HTTPException(
            500,
            "Excel aktarımı için openpyxl gerekli. Komut: pip install openpyxl"
        )

    raw = await request.body()
    if not raw:
        raise HTTPException(400, "Excel dosyası boş")

    try:
        wb = load_workbook(BytesIO(raw), data_only=True, read_only=True)
    except Exception as e:
        raise HTTPException(400, f"Excel dosyası açılamadı: {e}")

    # Öncelik gerçek operasyon sayfasında.
    ws = None
    for name in wb.sheetnames:
        if _norm_header(name) in ("YUKLEMELISTESI","YUKLEMELIST","LOADINGLIST"):
            ws = wb[name]
            break
    if ws is None:
        ws = wb[wb.sheetnames[0]]

    # read_only + iter_rows ile hızlı oku. Bu dosyada 8.797 x 62 hücre var;
    # ws.cell() ile tek tek okumak aşırı yavaştı.
    row_iter = ws.iter_rows(values_only=True)

    header_row = None
    header_map = {}
    buffered_rows = []

    for rno, vals in enumerate(row_iter, start=1):
        vals = tuple(vals)
        hm={_norm_header(v): i for i,v in enumerate(vals) if v is not None}
        score=0
        for candidate in ("SCNA","SERINO","SERIALNO","PLATE","PLAKA","DRIVER","DRIVERNAME","WEIGHT","FRIGHT"):
            if _norm_header(candidate) in hm:
                score += 1
        if score >= 2 or "SCNA" in hm:
            header_row=rno
            header_map=hm
            break
        if rno >= 30:
            break

    if not header_row:
        raise HTTPException(400, "Başlık satırı bulunamadı. SCNA/Plate gibi başlıklar gerekli.")

    # REMAIN kolonunu başlıktan bul. Sabit AX varsayımına güvenmiyoruz.
    remain_col = None
    for candidate in ("REMAIN","KALAN","BALANCE","REMAINING","REMAINDER"):
        key=_norm_header(candidate)
        if key in header_map:
            remain_col=header_map[key]
            break

    c=db()
    added=0
    updated=0
    skipped=0
    warning_skipped=0
    manual_protected_skipped=0
    remain_updated=0
    remain_missing=0
    delivery_date_source_count=0
    delivery_date_written_count=0
    invalid_scna_skipped=0
    excel_duplicate_count=0
    excel_duplicate_records=[]
    seen_excel_scna=set()
    errors=[]
    failed_records=[]
    preview_records=[]
    problem_records=[]
    preview_counts={"clean":0,"warning":0,"error":0,"duplicate":0,"update":0}
    created={"drivers":0,"vehicles":0,"customers":0,"areas":0,"cargo":0}

    def get_or_create_driver(name, phone="", dno=""):
        if not name:
            return None
        row=c.execute("SELECT id FROM drivers WHERE UPPER(name)=UPPER(?)",(name,)).fetchone()
        if row:
            return row["id"]
        cur=c.execute("INSERT INTO drivers(name,phone,d_no) VALUES(?,?,?)",(name,phone or "",dno or ""))
        created["drivers"]+=1
        return cur.lastrowid

    def get_or_create_vehicle(plate, driver_id=None):
        # Şoför araç sabiti değildir; her seferde trips.driver_id ile tutulur.
        if not plate:
            return None
        row=c.execute("SELECT id FROM vehicles WHERE UPPER(plate)=UPPER(?)",(plate,)).fetchone()
        if row:
            return row["id"]
        cur=c.execute("INSERT INTO vehicles(plate,driver_id) VALUES(?,NULL)",(plate.upper(),))
        created["vehicles"]+=1
        return cur.lastrowid

    def get_or_create_named(table, name, key):
        if not name:
            return None
        row=c.execute(f"SELECT id FROM {table} WHERE UPPER(name)=UPPER(?)",(name,)).fetchone()
        if row:
            return row["id"]
        cur=c.execute(f"INSERT INTO {table}(name) VALUES(?)",(name,))
        created[key]+=1
        return cur.lastrowid

    def get_or_create_area(name, km_go=0, km_back=0):
        if not name:
            return None
        row=c.execute("SELECT id,km_go,km_back FROM areas WHERE UPPER(name)=UPPER(?)",(name,)).fetchone()
        if row:
            if (not row["km_go"] and km_go) or (not row["km_back"] and km_back):
                c.execute("UPDATE areas SET km_go=CASE WHEN COALESCE(km_go,0)=0 THEN ? ELSE km_go END, km_back=CASE WHEN COALESCE(km_back,0)=0 THEN ? ELSE km_back END WHERE id=?",(km_go,km_back,row["id"]))
            return row["id"]
        cur=c.execute("INSERT INTO areas(name,km_go,km_back) VALUES(?,?,?)",(name,km_go or 0,km_back or 0))
        created["areas"]+=1
        return cur.lastrowid

    try:
        empty_streak = 0
        processed = 0

        # Header bulunduğunda row_iter zaten bir sonraki satırdan devam ediyor.
        for rno, row in enumerate(row_iter, start=header_row+1):
            row = tuple(row)
            processed += 1

            # Uzun boş kuyruk varsa Excel'in stil uygulanmış ama veri olmayan satırlarını bırak.
            if not any(v is not None and str(v).strip() != "" for v in row):
                empty_streak += 1
                if empty_streak >= 100:
                    break
                continue
            empty_streak = 0

            scna=_first(row,header_map,["SCNA","Serial No","Seri No","SNCA"])
            plate=_first(row,header_map,["Plate","Plaka","Plate - الرقم"])
            if not scna and not plate:
                continue

            scna=str(scna or "").strip().upper()
            invalid_scna_values={"",".","-","—","NONE","NAN","#VALUE!","#N/A"}
            if scna in invalid_scna_values:
                invalid_scna_skipped+=1
                # Kullanıcıyı 5.000 adet nokta satırıyla boğma; ilk örnekleri raporla.
                if plate and len(failed_records)<50:
                    failed_records.append({"row":rno,"scna":scna,"reason":"Geçersiz/boş SCNA; satır aktarılmadı"})
                continue

            if scna in seen_excel_scna:
                excel_duplicate_count+=1
                rec={"row":rno,"scna":scna,"reason":"Aynı SCNA Excel içinde birden fazla kez geçiyor; ikinci kayıt aktarılmadı"}
                excel_duplicate_records.append(rec)
                errors.append(f"Satır {rno} / SCNA {scna}: Excel içinde mükerrer")
                continue
            seen_excel_scna.add(scna)

            existing = c.execute(
                "SELECT id,COALESCE(manual_lock,0) manual_lock FROM trips WHERE UPPER(scna)=UPPER(?)",
                (scna,)
            ).fetchone()
            if existing and int(existing["manual_lock"] or 0)==1:
                protected_delivery=_excel_datetime(row[2] if len(row)>2 else "")
                protected_entry_km=_excel_num(row[29] if len(row)>29 else 0)

                protected_row=c.execute(
                    "SELECT entry_at,delivery_time,entry_km FROM trips WHERE id=?",
                    (existing["id"],)
                ).fetchone()

                if protected_delivery and protected_row and not (
                    (protected_row["entry_at"] or "").strip() or
                    (protected_row["delivery_time"] or "").strip()
                ):
                    c.execute("""
                      UPDATE trips SET
                        delivery_time=?,
                        entry_at=?,
                        entry_km=CASE
                          WHEN COALESCE(entry_km,0)<=0 AND ?>0 THEN ?
                          ELSE entry_km
                        END,
                        entry_done=1,
                        exit_done=1,
                        status='Tamamlandı',
                        updated_at=CURRENT_TIMESTAMP
                      WHERE id=?
                    """,(
                      protected_delivery,protected_delivery,
                      protected_entry_km,protected_entry_km,
                      existing["id"]
                    ))

                manual_protected_skipped += 1
                rec={
                    "row":rno,"scna":scna,"plate":str(plate or "").strip().upper(),
                    "driver":"","customer":"","area":"","cargo":"",
                    "kg":0,"price":0,"freight_rate":0,"amount":0,"collection":0,"excel_remain":None,
                    "delivery_time":"","exit_km":0,"entry_km":0,
                    "status":"MANUEL KORUMALI",
                    "messages":["Program içinde elle değiştirilmiş kayıt. Excel bu SCNA'nın üzerine yazmadı."]
                }
                if len(preview_records)<100: preview_records.append(rec)
                if len(problem_records)<1000: problem_records.append(rec)
                continue

            # Tek senkronizasyon mantığı:
            # - Yeni SCNA: ekle
            # - Mevcut SCNA: güncelle
            # - Manuel korumalı SCNA: dokunma
            # "Mükerrer diye atla" mantığı kaldırıldı; bu mantık giriş tarihlerini kaçırıyordu.

            try:
                c.execute("SAVEPOINT excel_row")
                # Excel'de G=Driver Name, X=Driver (PARA). X sütununu isim sanma.
                driver_name=str(_first(row,header_map,["Driver Name","DRIVERNAME","Şoför","Sofor"],"") or "").strip()
                if not driver_name and len(row) > 6:
                    driver_name=str(row[6] or "").strip()
                phone = str(row[7] or "").strip() if len(row) > 7 else str(_first(row,header_map,["Phone","Telefon"],"") or "").strip()
                dno = str(row[5] or "").strip() if len(row) > 5 else str(_first(row,header_map,["D.No","DNo","Driver No"],"") or "").strip()
                driver_id=get_or_create_driver(driver_name,phone,dno)

                # I = Plate
                if len(row) > 8 and row[8] not in (None,""):
                    plate=str(row[8]).strip()
                plate=str(plate or "").strip().upper()
                if not plate:
                    msg=f"Satır {rno}: Plaka boş"
                    errors.append(msg)
                    failed_records.append({"row":rno,"scna":scna,"reason":"Plaka boş"})
                    continue
                get_or_create_vehicle(plate,driver_id)

                # YUKLEME LISTESI gerçek kolon düzeni:
                # F=D.No, G=Driver Name, H=Phone, I=Plate, J=FRIGHT(Net KG),
                # K=PRICE(KG başı), L=Customer, M=CARGO, N=Cargo Type, O=Delivery Area.
                dno = str(row[5] or "").strip() if len(row) > 5 else str(_first(row,header_map,["D.No","DNo"],"") or "").strip()
                phone = str(row[7] or "").strip() if len(row) > 7 else str(_first(row,header_map,["Phone","Telefon"],"") or "").strip()

                customer = str(row[11] or "").strip() if len(row) > 11 else str(_first(row,header_map,["Customer","Müşteri","Musteri"],"") or "").strip()
                customer_id=get_or_create_named("customers",customer,"customers")

                area = str(row[14] or "").strip() if len(row) > 14 else str(_first(row,header_map,["Delivery Area","DeliveryArea","Teslimat Bölgesi","Teslim Yeri"],"") or "").strip()
                route_km_go=_excel_num(row[15] if len(row)>15 else 0)
                route_km_back=_excel_num(row[16] if len(row)>16 else 0)
                area_id=get_or_create_area(area,route_km_go,route_km_back)

                cargo = str(row[12] or "").strip() if len(row) > 12 else str(_first(row,header_map,["Cargo","Mal Cinsi","Mal","Product","Ürün"],"") or "").strip()
                cargo_id=get_or_create_named("cargo_categories",cargo,"cargo")

                cargo_type = str(row[13] or "").strip().upper() if len(row) > 13 else str(_first(row,header_map,["Cargo Type","CargoType","Yük Tipi","Yuk Tipi"],"") or "").strip().upper()
                # Excel'deki gerçek operasyon tiplerini koru. Sadece bariz yazım hatalarını düzelt.
                cargo_type_alias={"BLUK":"BULK","BULG":"BULK"}
                cargo_type=cargo_type_alias.get(cargo_type,cargo_type or "BULK")

                trip_date = _excel_date(row[1] if len(row) > 1 else _first(row,header_map,["Loading Date","LoadingDate","Date","Tarih"],""))
                delivery_time = _excel_datetime(
                    row[2] if len(row) > 2 else
                    _first(row,header_map,["Delivery Time","DeliveryTime","Teslim Tarihi","Teslim Zamanı"],"")
                )
                if delivery_time:
                    delivery_date_source_count += 1

                excel_exit_at=_excel_datetime(_first(row,header_map,["Exit Date","Exit Time","Çıkış Tarihi","Cikis Tarihi","Çıkış Saati"],""))
                excel_entry_at=_excel_datetime(_first(row,header_map,["Entry Date","Entry Time","Giriş Tarihi","Giris Tarihi","Giriş Saati"],""))

                net_kg = _excel_num(row[9] if len(row) > 9 else 0)       # J = FRIGHT = Net KG
                price_k = _excel_num(row[10] if len(row) > 10 else 0)      # K = PRICE
                freight_rate_au = _excel_num(row[46] if len(row) > 46 else 0) # AU = FREIGHT (final)
                freight_basis = "KG"

                # AV = AMOUNT = gerçek navlun toplamı; AW = COLLECTION = fiilen alınan para.
                freight_total = _excel_num(row[47] if len(row) > 47 else 0)

                # Finansal doğrulukta AV=AMOUNT ana kaynaktır. AU veya K bazı satırlarda
                # AMOUNT ile uyuşmuyor. Bu yüzden efektif navlun oranı mümkünse AMOUNT/KG.
                if freight_total and net_kg:
                    freight_rate = freight_total / net_kg
                else:
                    freight_rate = freight_rate_au or price_k

                exit_km=_excel_num(_first(row,header_map,["GIDIS KM","Exit KM","Çıkış KM","Cikis KM"],0))
                entry_km=_excel_num(_first(row,header_map,["GELIS KM","Entry KM","Giriş KM","Giris KM"],0))
                tank_start=_excel_num(_first(row,header_map,["DEPOSUNDAKI LITRE","Tank Start","Depodaki Mazot","Depo Mazot","Başlangıç Depo"],0))
                tank_end=_excel_num(_first(row,header_map,["DEPODA KALAN","Tank End","Depoda Kalan","Kalan Mazot"],0))
                if len(row) >= 45:
                    if not exit_km: exit_km=_excel_num(row[28])
                    if not entry_km: entry_km=_excel_num(row[29])
                    if not tank_start: tank_start=_excel_num(row[31])
                    if not tank_end: tank_end=_excel_num(row[44])

                # T=Premium, U=Harcırah, V=Port Fee, W=Dock Fee, Y=OTHER, Z=SONAR
                premium=_excel_num(row[19] if len(row)>19 else 0)
                allowance=_excel_num(row[20] if len(row)>20 else 0)
                port_fee=_excel_num(row[21] if len(row)>21 else 0)
                dock_fee=_excel_num(row[22] if len(row)>22 else 0)
                other=_excel_num(row[24] if len(row)>24 else 0)
                sonar=_excel_num(row[25] if len(row)>25 else 0)

                # Çıkış yakıtları: LT ve toplam tutar için farklı olası başlıklar.
                # Başlıklar tekrar ettiği için tam otomatik eşleme bazı eski Excel'lerde belirsiz olabilir.
                # Bilinen alternatif adları yine destekliyoruz.
                off_lt=_excel_num(_first(row,header_map,["RESMI LT","Official Fuel LT","Resmi Mazot LT"],0))
                off_total=_excel_num(_first(row,header_map,["RESMI TOPLAM","Official Fuel Total","Resmi Mazot Toplam"],0))
                com_lt=_excel_num(_first(row,header_map,["TICARI LT","Commercial Fuel LT","Ticari Mazot LT"],0))
                com_total=_excel_num(_first(row,header_map,["TICARI TOPLAM","Commercial Fuel Total","Ticari Mazot Toplam"],0))
                bag_lt=_excel_num(_first(row,header_map,["BAGDAT LT","Baghdad Fuel LT","Bağdat Mazot LT"],0))
                bag_total=_excel_num(_first(row,header_map,["BAGDAT TOPLAM","Baghdad Fuel Total","Bağdat Mazot Toplam"],0))

                # Kullanıcının mevcut YUKLEME LISTESI sabit kolonları:
                # AG=33 LITRE, AH=34 RESMI, AI=35 QID
                # AJ=36 LITRE, AK=37 TICARI, AL=38 IQD
                # AM=39 BAGDAT LITRE, AN=40 RESMI, AO=41 IQD
                # Python 0-index: 32..40
                if len(row) >= 41:
                    if not off_lt: off_lt=_excel_num(row[32])
                    if not off_total: off_total=_excel_num(row[34])
                    if not com_lt: com_lt=_excel_num(row[35])
                    if not com_total: com_total=_excel_num(row[37])
                    if not bag_lt: bag_lt=_excel_num(row[38])
                    if not bag_total: bag_total=_excel_num(row[40])

                # AW = COLLECTION = müşteriden fiilen alınan para.
                collection=_excel_num(row[48] if len(row)>48 else _first(row,header_map,["COLLECTION","Tahsilat","Müşteriden Alınan Para"],0))

                # REMAIN başlıktan okunur. Başlık bulunamazsa eski dosyalar için
                # yalnızca fallback olarak index 49 denenir.
                remain_raw=None
                if remain_col is not None and remain_col < len(row):
                    remain_raw=row[remain_col]
                elif len(row)>49:
                    remain_raw=row[49]

                excel_remain=_excel_optional_num(remain_raw)
                if excel_remain is None:
                    remain_missing+=1
                else:
                    remain_updated+=1

                # ---- EXCEL KONTROL MERKEZİ DOĞRULAMALARI ----
                row_errors=[]
                row_warnings=[]

                expected_amount=net_kg*freight_rate if net_kg and freight_rate else 0

                if price_k and freight_rate_au and abs(price_k-freight_rate_au)>0.0001:
                    row_warnings.append(
                        f"PRICE K ({price_k:,.6f}) ile FREIGHT AU ({freight_rate_au:,.6f}) farklı. "
                        "Finansal hesapta AMOUNT/KG kullanılacak."
                    )
                if excel_remain is not None and freight_total and collection:
                    calc_remain=collection-freight_total
                    if abs(excel_remain-calc_remain)>1:
                        row_warnings.append(
                            f"Excel REMAIN hatalı görünüyor: hücre {excel_remain:,.2f}, doğru COLLECTION-AMOUNT {calc_remain:,.2f}. "
                            "Program hesaplanan farkı kullanacak."
                        )

                if not driver_name:
                    row_warnings.append("Şoför adı boş.")
                if not customer:
                    row_warnings.append("Müşteri boş.")
                if not area:
                    row_warnings.append("Bölge boş.")
                if not cargo:
                    row_warnings.append("Mal cinsi boş.")

                if net_kg < 0:
                    row_errors.append("Net KG negatif.")
                elif net_kg > 80000:
                    row_warnings.append(f"Net KG olağandışı yüksek: {net_kg:,.0f}")

                if freight_rate < 0:
                    row_errors.append("PRICE negatif.")
                elif freight_rate > 100000:
                    row_warnings.append(f"PRICE olağandışı yüksek: {freight_rate:,.2f}")

                if freight_total and expected_amount and abs(freight_total-expected_amount) > 1:
                    row_warnings.append(
                        f"AMOUNT uyuşmuyor: Excel {freight_total:,.2f}, KG×PRICE {expected_amount:,.2f}"
                    )

                if delivery_time and entry_km <= 0:
                    row_warnings.append(
                        f"Giriş tarihi var ({delivery_time[:10]}) fakat GELİŞ KM boş. "
                        "Kayıt Tamamlandı olarak alınacak; KM bilgisi eksik kalacak."
                    )

                if entry_km > 0 and exit_km > 0 and entry_km < exit_km:
                    row_warnings.append(
                        f"Giriş KM ({entry_km:,.0f}) çıkış KM'den ({exit_km:,.0f}) küçük. "
                        "Kayıt aktarılacak fakat KM/anormallik hesabına alınmayacak."
                    )
                if entry_km > 0 and exit_km > 0 and (entry_km-exit_km) > 5000:
                    row_warnings.append(f"Sefer KM farkı çok yüksek: {entry_km-exit_km:,.0f} KM")

                fuel_liters=off_lt+com_lt+bag_lt
                if fuel_liters > 5000:
                    row_errors.append(f"Yakıt miktarı gerçekçi değil: {fuel_liters:,.0f} LT")
                elif fuel_liters > 1500:
                    row_warnings.append(f"Yakıt miktarı yüksek görünüyor: {fuel_liters:,.0f} LT")

                if tank_start > 2000 or tank_end > 2000:
                    row_warnings.append("Depo litre değeri 2.000 LT üzerinde.")

                if collection < 0:
                    row_errors.append("COLLECTION negatif.")
                if collection and expected_amount and collection > expected_amount*1.10:
                    row_warnings.append(
                        f"COLLECTION navlunun %10'dan fazla üzerinde: {collection:,.2f} > {expected_amount:,.2f}"
                    )

                preview_status="HATALI" if row_errors else (
                    "UYARI" if row_warnings else ("GÜNCELLENECEK" if existing else "TEMİZ")
                )
                messages=row_errors+row_warnings
                preview_rec={
                    "row":rno,"scna":scna,"plate":plate,"driver":driver_name,
                    "customer":customer,"area":area,"cargo":cargo,
                    "kg":net_kg,"price":price_k,"freight_rate":freight_rate,
                    "amount":freight_total or expected_amount,
                    "collection":collection,
                    "excel_remain":excel_remain,
                    "delivery_time":delivery_time,
                    "exit_km":exit_km,
                    "entry_km":entry_km,
                    "status":preview_status,"messages":messages
                }

                if row_errors:
                    preview_counts["error"]+=1
                    failed_records.append({
                        "row":rno,"scna":scna,"reason":" | ".join(row_errors)
                    })
                    errors.append(f"Satır {rno} / SCNA {scna}: {' | '.join(row_errors)}")
                    if len(preview_records)<100: preview_records.append(preview_rec)
                    if len(problem_records)<1000: problem_records.append(preview_rec)
                    c.execute("ROLLBACK TO excel_row")
                    c.execute("RELEASE excel_row")
                    continue

                if row_warnings:
                    preview_counts["warning"]+=1
                    if len(problem_records)<1000:
                        problem_records.append(preview_rec)
                    # UYARI sadece bilgi amaçlıdır. Satırın tamamını atlama.
                    # Özellikle "giriş tarihi var / giriş KM boş" gibi durumlarda
                    # dönüş tarihinin kaybolmasına izin verme.
                elif existing:
                    preview_counts["update"]+=1
                else:
                    preview_counts["clean"]+=1

                if len(preview_records)<100:
                    preview_records.append(preview_rec)

                # Durum Excel'deki gerçek hareket bilgisine göre belirlenir.
                # Delivery Time gerçek giriş tarihidir. GELİŞ KM boş olsa bile giriş tarihi varsa
                # kayıt tamamlanmış kabul edilir; KM eksikliği önizlemede ayrıca uyarılır.
                has_delivery_time = bool(delivery_time)
                has_entry_km = entry_km > 0 and (exit_km <= 0 or entry_km >= exit_km)

                entry_done = 1 if (has_delivery_time or has_entry_km) else 0
                exit_done = 1 if (
                    entry_done or exit_km > 0 or off_lt > 0 or com_lt > 0 or
                    bag_lt > 0 or allowance > 0 or other > 0
                ) else 0

                status="Tamamlandı" if entry_done else ("Yolda" if exit_done else "Bekliyor")

                if existing:
                    c.execute("""
                      UPDATE trips SET
                        plate=?,
                        driver_id=?,
                        area_id=?,
                        cargo_category_id=?,
                        cargo_type=?,
                        customer_id=?,
                        trip_date=?,
                        net_kg=?,
                        freight_rate=?,
                        freight_basis=?,
                        exit_km=?,
                        tank_start_liters=?,
                        exit_official_fuel_liters=?,
                        exit_official_fuel_total=?,
                        exit_commercial_fuel_liters=?,
                        exit_commercial_fuel_total=?,
                        exit_baghdad_fuel_liters=?,
                        exit_baghdad_fuel_total=?,
                        exit_allowance=?,
                        exit_premium=?,
                        exit_other=?,
                        dock_fee=?,
                        port_fee=?,
                        sonar=?,
                        entry_km=?,
                        tank_end_liters=?,
                        entry_collection=?,
                        excel_price_k=?,
                        excel_freight_au=?,
                        excel_amount=?,
                        excel_remain=?,
                        delivery_time=?,
                        exit_done=?,
                        entry_done=?,
                        status=?,
                        exit_at=?,
                        entry_at=?,
                        updated_at=CURRENT_TIMESTAMP
                      WHERE id=?
                    """,(
                        plate,driver_id,area_id,cargo_id,cargo_type,customer_id,trip_date,
                        net_kg,freight_rate,freight_basis,
                        exit_km,tank_start,off_lt,off_total,
                        com_lt,com_total,bag_lt,bag_total,
                        allowance,premium,other,dock_fee,port_fee,sonar,
                        entry_km,tank_end,collection,price_k,freight_rate_au,freight_total,excel_remain,delivery_time,
                        exit_done,entry_done,status,
                        excel_exit_at or (trip_date+" 00:00:00" if exit_done and trip_date else None),
                        delivery_time or excel_entry_at or None,
                        existing["id"]
                    ))
                    updated+=1
                else:
                    c.execute("""
                    INSERT INTO trips(
                      scna,plate,driver_id,area_id,cargo_category_id,cargo_type,customer_id,trip_date,
                      net_kg,freight_rate,freight_basis,
                      exit_km,tank_start_liters,exit_official_fuel_liters,exit_official_fuel_total,
                      exit_commercial_fuel_liters,exit_commercial_fuel_total,
                      exit_baghdad_fuel_liters,exit_baghdad_fuel_total,
                      exit_allowance,exit_premium,exit_other,dock_fee,port_fee,sonar,
                      entry_km,tank_end_liters,entry_collection,excel_price_k,excel_freight_au,excel_amount,excel_remain,delivery_time,
                      exit_done,entry_done,status,exit_at,entry_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,(
                    scna,plate,driver_id,area_id,cargo_id,cargo_type,customer_id,trip_date,
                    net_kg,freight_rate,freight_basis,
                    exit_km,tank_start,off_lt,off_total,
                    com_lt,com_total,bag_lt,bag_total,
                    allowance,premium,other,dock_fee,port_fee,sonar,
                    entry_km,tank_end,collection,price_k,freight_rate_au,freight_total,excel_remain,delivery_time,
                    exit_done,entry_done,status,
                    excel_exit_at or (trip_date+" 00:00:00" if exit_done and trip_date else None),
                    delivery_time or excel_entry_at or None
                ))
                    added+=1

                c.execute("RELEASE excel_row")
                if delivery_time:
                    delivery_date_written_count += 1

            except Exception as e:
                try:
                    c.execute("ROLLBACK TO excel_row")
                    c.execute("RELEASE excel_row")
                except Exception:
                    pass
                reason=str(e)
                errors.append(f"Satır {rno} / SCNA {scna}: {reason}")
                failed_records.append({
                    "row":rno,
                    "scna":scna,
                    "reason":reason
                })

        if preview_only:
            c.rollback()
        else:
            c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

    if not preview_only:
        audit(
            "EXCEL_IMPORT",
            filename or "EXCEL",
            f"{added} eklendi, {updated} güncellendi, {skipped} mükerrer atlandı, "
            f"{warning_skipped} uyarılı atlandı, {remain_updated} REMAIN okundu, "
            f"{remain_missing} REMAIN boş, {len(errors)} hata"
        )

    return {
        "ok": True,
        "sheet": ws.title,
        "header_row": header_row,
        "processed": processed,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "warning_skipped": warning_skipped,
        "manual_protected_skipped": manual_protected_skipped,
        "remain_header_found": remain_col is not None,
        "remain_column_index": (remain_col+1) if remain_col is not None else None,
        "remain_updated": remain_updated,
        "remain_missing": remain_missing,
        "delivery_date_source_count": delivery_date_source_count,
        "delivery_date_written_count": delivery_date_written_count,
        "delivery_date_not_written_count": max(delivery_date_source_count-delivery_date_written_count,0),
        "invalid_scna_skipped": invalid_scna_skipped,
        "excel_duplicate_count": excel_duplicate_count,
        "excel_duplicate_records": excel_duplicate_records[:100],
        "error_count": len(errors),
        "errors": errors[:100],
        "failed_records": failed_records[:500],
        "failed_scna": [x["scna"] for x in failed_records if x.get("scna")][:500],
        "preview_only": bool(preview_only),
        "preview_counts": preview_counts,
        "preview_records": preview_records,
        "problem_records": problem_records,
        "created": created
    }


def _safe_float(v):
    try:
        return float(v or 0)
    except:
        return 0.0

def _export_rows(q="", status=""):
    c=db()
    sql=tq()+" WHERE 1=1 "
    p=[]
    if q:
        like=f"%{q}%"
        sql += " AND (t.scna LIKE ? OR t.plate LIKE ? OR d.name LIKE ? OR a.name LIKE ? OR cu.name LIKE ? OR cc.name LIKE ?)"
        p += [like,like,like,like,like,like]
    if status and status != "Tümü":
        sql += " AND t.status=?"
        p.append(status)
    sql += " ORDER BY t.id ASC"
    rows=[dict(r) for r in c.execute(sql,p)]
    c.close()
    return rows

def _excel_headers():
    # Kullanıcının YUKLEME LISTESI düzeni, A:BG.
    # BC ve BD orijinal dosyada başlıksız olduğu için boş bırakılır.
    return [
        "SCNA","Loading\nDate","Delivery Time","AY","SEFER SURESI","D.No",
        "Driver Name","Phone","Plate","FRIGHT","PRICE","Customer","CARGO",
        "Cargo \nType","Delivery Area","KM-GO","KM-BACK","Total","0.35",
        "Premium","Harcırah","Port Fee","Dock Fee","Driver","OTHER","SONAR",
        "G.Total","DRIVER ADVANTAGE","GIDIS KM ","GELIS KM","FARK",
        "DEPOSUNDAKI \nLITRE","LITRE","RESMI","QID","LITRE","TICARI","IQD",
        "BAGDAT\nLITRE","RESMI","IQD","Genel\nToplam","TOPLAM\nLITRE",
        "KALMASI BEKLENEN","DEPODA \nKALAN","% TUKETIM ORANI","FREIGHT",
        "AMOUNT","COLLECTION ","REMAIN","GELİŞ","Maintanence \nCost IQD / Km",
        "Maintanence \nCost ","Gelir","","","GPS CONSUMPTION\nLITRE",
        "TOTAL KM \nGPS","GPS CONSUMPTION %"
    ]

def _build_export_workbook(rows):
    try:
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise HTTPException(
            500,
            "Excel dışa aktarma için openpyxl gerekli. Komut: pip install openpyxl"
        )

    # İstenirse APP.py yanına EXPORT_TEMPLATE.xlsx konabilir.
    # Bu durumda kullanıcının kendi Excel görünümü/stili korunur.
    template = BASE / "EXPORT_TEMPLATE.xlsx"
    if template.exists():
        wb = load_workbook(template)
        if "YUKLEME LISTESI" in wb.sheetnames:
            ws=wb["YUKLEME LISTESI"]
        else:
            ws=wb.create_sheet("YUKLEME LISTESI")

        # Mevcut veri satırlarını temizle; başlık/stil kalsın.
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row-1)
    else:
        wb=Workbook()
        ws=wb.active
        ws.title="YUKLEME LISTESI"

        # Gönderilen çalışma kitabındaki diğer ana sekmeleri de oluştur.
        for name in ["ANA FORM","MAZOT TAKIP","URUNLER","CARILER"]:
            if name not in wb.sheetnames:
                wb.create_sheet(name)

        headers=_excel_headers()
        for idx,h in enumerate(headers,1):
            ws.cell(1,idx,h)

        # Basit ama okunaklı varsayılan stil.
        fill=PatternFill("solid",fgColor="1F4E78")
        font=Font(color="FFFFFF",bold=True)
        thin=Side(style="thin",color="D9E2F3")
        for cell in ws[1]:
            cell.fill=fill
            cell.font=font
            cell.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
            cell.border=Border(bottom=thin)
        ws.row_dimensions[1].height=38
        ws.freeze_panes="A2"
        ws.auto_filter.ref=f"A1:BG1"

        widths={
            "A":14,"B":13,"C":18,"F":10,"G":26,"H":18,"I":14,"J":12,"K":10,
            "L":24,"M":18,"N":12,"O":24,"P":10,"Q":10,"T":12,"U":12,"V":12,
            "W":12,"X":12,"Y":12,"Z":12,"AC":12,"AD":12,"AF":14,"AG":10,
            "AH":10,"AI":12,"AJ":10,"AK":10,"AL":12,"AM":12,"AN":10,"AO":12,
            "AP":14,"AQ":12,"AS":12,"AT":14,"AU":10,"AV":14,"AW":14,"AX":14,
            "AZ":18,"BA":16,"BB":14,"BE":16,"BF":14,"BG":16
        }
        for col,w in widths.items():
            ws.column_dimensions[col].width=w

    # Eğer template başlıkları boşsa/eksikse başlıkları yine yaz.
    headers=_excel_headers()
    for idx,h in enumerate(headers,1):
        if ws.cell(1,idx).value in (None,""):
            ws.cell(1,idx,h)

    # CARILER / URUNLER sekmelerini veritabanından doldur.
    c=db()
    customers=[r["name"] for r in c.execute("SELECT name FROM customers ORDER BY name")]
    cargos=[r["name"] for r in c.execute("SELECT name FROM cargo_categories ORDER BY name")]
    c.close()

    if "CARILER" in wb.sheetnames:
        sh=wb["CARILER"]
        if sh.max_row>1: sh.delete_rows(2,sh.max_row-1)
        if sh["A1"].value in (None,""): sh["A1"]="CARILER"
        for i,v in enumerate(customers,2): sh.cell(i,1,v)

    if "URUNLER" in wb.sheetnames:
        sh=wb["URUNLER"]
        if sh.max_row>1: sh.delete_rows(2,sh.max_row-1)
        if sh["A1"].value in (None,""): sh["A1"]="URUNLER"
        for i,v in enumerate(cargos,2): sh.cell(i,1,v)

    # YUKLEME LISTESI veri satırları.
    for excel_row, x in enumerate(rows, start=2):
        kg=_safe_float(x.get("net_kg"))
        rate=_safe_float(x.get("freight_rate"))
        freight=_safe_float(x.get("freight_total"))
        collection=_safe_float(x.get("entry_collection"))

        km_go=_safe_float(x.get("planned_km_go"))
        km_back=_safe_float(x.get("planned_km_back"))
        planned_total=km_go+km_back

        exit_km=_safe_float(x.get("exit_km"))
        entry_km=_safe_float(x.get("entry_km"))
        actual_km=max(entry_km-exit_km,0) if entry_km and exit_km else 0

        off_lt=_safe_float(x.get("exit_official_fuel_liters"))
        off_total=_safe_float(x.get("exit_official_fuel_total"))
        off_price=off_total/off_lt if off_lt else 0

        com_lt=_safe_float(x.get("exit_commercial_fuel_liters"))
        com_total=_safe_float(x.get("exit_commercial_fuel_total"))
        com_price=com_total/com_lt if com_lt else 0

        bag_lt=_safe_float(x.get("exit_baghdad_fuel_liters"))
        bag_total=_safe_float(x.get("exit_baghdad_fuel_total"))
        bag_price=bag_total/bag_lt if bag_lt else 0

        road_lt=_safe_float(x.get("road_fuel_liters"))
        road_total=_safe_float(x.get("road_fuel_total"))

        tank_start=_safe_float(x.get("tank_start_liters"))
        tank_end=_safe_float(x.get("tank_end_liters"))
        total_liters=tank_start+off_lt+com_lt+bag_lt+road_lt
        consumed=_safe_float(x.get("fuel_consumed_liters"))
        consumption=_safe_float(x.get("liters_per_100km"))

        premium=_safe_float(x.get("exit_premium"))
        allowance=_safe_float(x.get("exit_allowance"))
        port_fee=_safe_float(x.get("port_fee"))
        dock_fee=_safe_float(x.get("dock_fee"))
        other=_safe_float(x.get("exit_other"))
        sonar=_safe_float(x.get("sonar"))
        fuel_total=off_total+com_total+bag_total+road_total
        gtotal=premium+allowance+port_fee+dock_fee+other+sonar+fuel_total

        loading=x.get("trip_date") or ""
        delivery=x.get("delivery_time") or x.get("entry_at") or ""

        # A:BG positional mapping.
        vals = [None]*59
        vals[0]=x.get("scna")
        vals[1]=loading
        vals[2]=delivery

        # AY / sefer süresi
        try:
            if loading:
                vals[3]=int(str(loading)[5:7])
        except:
            vals[3]=""
        vals[4]=_safe_float(x.get("trip_duration_hours"))/24 if x.get("trip_duration_hours") else ""

        vals[5]=x.get("d_no") or ""
        vals[6]=x.get("driver_name") or ""
        vals[7]=x.get("phone") or ""
        vals[8]=x.get("plate") or ""
        vals[9]=kg
        vals[10]=rate
        vals[11]=x.get("customer_name") or ""
        vals[12]=x.get("cargo_name") or ""
        vals[13]=x.get("cargo_type_name") or ""
        vals[14]=x.get("area_name") or ""
        vals[15]=km_go
        vals[16]=km_back
        vals[17]=planned_total
        vals[18]=planned_total*0.35 if planned_total else 0
        vals[19]=premium
        vals[20]=allowance
        vals[21]=port_fee
        vals[22]=dock_fee

        # X Driver: eski Excel'deki sürücü masraf alanı.
        # Programda ayrı alan olmadığı için 0 bırakılır.
        vals[23]=0
        vals[24]=other
        vals[25]=sonar
        vals[26]=gtotal
        vals[27]=""

        vals[28]=exit_km
        vals[29]=entry_km
        vals[30]=actual_km
        vals[31]=tank_start

        vals[32]=off_lt
        vals[33]=off_price
        vals[34]=off_total
        vals[35]=com_lt
        vals[36]=com_price
        vals[37]=com_total
        vals[38]=bag_lt
        vals[39]=bag_price
        vals[40]=bag_total

        vals[41]=fuel_total
        vals[42]=total_liters
        vals[43]=total_liters-consumed if total_liters else ""
        vals[44]=tank_end
        vals[45]=consumption

        vals[46]=rate
        vals[47]=freight
        vals[48]=collection
        vals[49]=collection-freight
        vals[50]=x.get("entry_at") or ""

        # AZ/BA bakım maliyeti DB'de yok, boş bırak.
        vals[51]=""
        vals[52]=""

        vals[53]=_safe_float(x.get("trip_profit"))
        vals[54]=""
        vals[55]=""
        vals[56]=""
        vals[57]=""
        vals[58]=""

        for col,val in enumerate(vals,1):
            ws.cell(excel_row,col,val)

    # Görsel/format ayarları.
    ws.freeze_panes="A2"
    ws.auto_filter.ref=f"A1:BG{max(ws.max_row,1)}"

    # Tarihler metin olarak gelir; para/sayı kolonlarını düzgün formatla.
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for idx,cell in enumerate(row,1):
            if idx in (10,11,16,17,18,19,20,21,22,23,24,25,26,27,29,30,31,32,
                       33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,
                       52,53,54):
                cell.number_format='#,##0.00'

    return wb

@app.get("/api/export-excel")
def export_excel(mode: str="all", q: str="", status: str=""):
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(
            500,
            "Excel dışa aktarma için openpyxl gerekli. Komut: pip install openpyxl"
        )

    if mode == "all":
        rows=_export_rows("","")
        suffix="TUM_KAYITLAR"
    else:
        rows=_export_rows(q,status)
        suffix="FILTRELI"

    wb=_build_export_workbook(rows)
    bio=BytesIO()
    wb.save(bio)
    bio.seek(0)

    stamp=datetime.now().strftime("%Y%m%d_%H%M")
    filename=f"SAMA_YUKLEME_LISTESI_{suffix}_{stamp}.xlsx"

    headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )


@app.get("/api/scna-detail/{scna}")
def scna_detail(scna: str):
    c=db()
    trip=c.execute(tq()+" WHERE t.scna=?",(scna,)).fetchone()
    if not trip:
        c.close()
        raise HTTPException(404,"SCNA bulunamadı")

    fuels=[dict(r) for r in c.execute(
        "SELECT * FROM fuel_purchases WHERE scna=? ORDER BY id",
        (scna,)
    )]

    logs=[dict(r) for r in c.execute(
        "SELECT * FROM audit_log WHERE scna=? ORDER BY id DESC LIMIT 100",
        (scna,)
    )]

    c.close()
    return {
        "trip": dict(trip),
        "fuels": fuels,
        "logs": logs
    }

@app.get("/api/performance/vehicles")
def vehicle_performance():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT
        t.plate,
        COUNT(*) trip_count,
        SUM(CASE WHEN t.entry_done=1 THEN 1 ELSE 0 END) completed_count,
        ROUND(SUM(t.net_kg)/1000.0,2) total_ton,
        ROUND(SUM(CASE WHEN t.freight_basis='KG'
                       THEN t.net_kg*t.freight_rate
                       ELSE (t.net_kg/1000.0)*t.freight_rate END),2) total_freight,
        ROUND(SUM(
          CASE WHEN t.entry_done=1 THEN MAX(t.entry_km-t.exit_km,0) ELSE 0 END
        ),2) total_km,
        ROUND(AVG(
          CASE
            WHEN t.entry_done=1
             AND (t.entry_km-t.exit_km)>0
             AND (
               t.tank_start_liters+
               t.exit_official_fuel_liters+
               t.exit_commercial_fuel_liters+
               t.exit_baghdad_fuel_liters+
               COALESCE(f.road_liters,0)-
               t.tank_end_liters
             )>0
            THEN (
              (
                t.tank_start_liters+
                t.exit_official_fuel_liters+
                t.exit_commercial_fuel_liters+
                t.exit_baghdad_fuel_liters+
                COALESCE(f.road_liters,0)-
                t.tank_end_liters
              )/(t.entry_km-t.exit_km)
            )*100
          END
        ),2) avg_l100,
        ROUND(SUM(
          (CASE WHEN t.freight_basis='KG'
             THEN t.net_kg*t.freight_rate
             ELSE (t.net_kg/1000.0)*t.freight_rate END)
          -
          (
            t.exit_official_fuel_total+
            t.exit_commercial_fuel_total+
            t.exit_baghdad_fuel_total+
            COALESCE(f.road_total,0)+
            t.exit_allowance+
            t.exit_premium+
            t.dock_fee+
            t.port_fee+
            t.sonar+
            t.exit_other+
            t.entry_extra_expense_1+
            t.entry_extra_expense_2+
            t.entry_extra_expense_3
          )
        ),2) total_profit
      FROM trips t
      LEFT JOIN (
        SELECT scna,SUM(liters) road_liters,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      GROUP BY t.plate
      ORDER BY total_profit DESC
    """)]
    c.close()
    return rows

@app.get("/api/performance/drivers")
def driver_performance():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT
        COALESCE(d.name,'') driver_name,
        COUNT(*) trip_count,
        SUM(CASE WHEN t.entry_done=1 THEN 1 ELSE 0 END) completed_count,
        ROUND(SUM(t.net_kg)/1000.0,2) total_ton,
        ROUND(SUM(CASE WHEN t.freight_basis='KG'
                       THEN t.net_kg*t.freight_rate
                       ELSE (t.net_kg/1000.0)*t.freight_rate END),2) total_freight,
        ROUND(SUM(
          CASE WHEN t.entry_done=1 THEN MAX(t.entry_km-t.exit_km,0) ELSE 0 END
        ),2) total_km,
        ROUND(AVG(
          CASE
            WHEN t.entry_done=1
             AND (t.entry_km-t.exit_km)>0
             AND (
               t.tank_start_liters+
               t.exit_official_fuel_liters+
               t.exit_commercial_fuel_liters+
               t.exit_baghdad_fuel_liters+
               COALESCE(f.road_liters,0)-
               t.tank_end_liters
             )>0
            THEN (
              (
                t.tank_start_liters+
                t.exit_official_fuel_liters+
                t.exit_commercial_fuel_liters+
                t.exit_baghdad_fuel_liters+
                COALESCE(f.road_liters,0)-
                t.tank_end_liters
              )/(t.entry_km-t.exit_km)
            )*100
          END
        ),2) avg_l100,
        ROUND(SUM(
          CASE WHEN t.entry_done=1 THEN
            COALESCE(
              t.excel_remain,
              CASE
                WHEN COALESCE(t.entry_cash_handed,0)=0
                 AND COALESCE(t.entry_collection,0)>0
                 AND t.entry_done=1
                THEN t.entry_collection -
                  (CASE WHEN t.freight_basis='KG'
                        THEN t.net_kg*t.freight_rate
                        ELSE (t.net_kg/1000.0)*t.freight_rate END)
                ELSE
                  t.entry_cash_handed -
                  (
                    t.entry_collection -
                    (
                      COALESCE(f.road_total,0)+
                      t.entry_extra_expense_1+
                      t.entry_extra_expense_2+
                      t.entry_extra_expense_3
                    )
                  )
              END
            )
          ELSE 0 END
        ),2) cash_diff
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN (
        SELECT scna,SUM(liters) road_liters,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      GROUP BY d.id,d.name
      ORDER BY completed_count DESC, trip_count DESC
    """)]
    c.close()
    return rows

@app.get("/api/alerts")
def alerts():
    c=db()

    delayed=[dict(r) for r in c.execute("""
      SELECT
        t.scna,t.plate,d.name driver_name,a.name area_name,t.exit_at,
        ROUND((JULIANDAY('now','localtime')-JULIANDAY(t.exit_at))*24,1) hours_on_road
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN areas a ON a.id=t.area_id
      WHERE t.status='Yolda'
        AND t.exit_at IS NOT NULL
        AND (JULIANDAY('now','localtime')-JULIANDAY(t.exit_at))*24 > 48
      ORDER BY hours_on_road DESC
    """)]

    # Completed-trip per vehicle historical average.
    fuel_alerts=[dict(r) for r in c.execute("""
      WITH trip_cons AS (
        SELECT
          t.id,t.scna,t.plate,d.name driver_name,
          CASE
            WHEN t.entry_done=1
             AND (t.entry_km-t.exit_km)>0
             AND (
               t.tank_start_liters+
               t.exit_official_fuel_liters+
               t.exit_commercial_fuel_liters+
               t.exit_baghdad_fuel_liters+
               COALESCE(f.road_liters,0)-
               t.tank_end_liters
             )>0
            THEN (
              (
                t.tank_start_liters+
                t.exit_official_fuel_liters+
                t.exit_commercial_fuel_liters+
                t.exit_baghdad_fuel_liters+
                COALESCE(f.road_liters,0)-
                t.tank_end_liters
              )/(t.entry_km-t.exit_km)
            )*100
          END l100
        FROM trips t
        LEFT JOIN drivers d ON d.id=t.driver_id
        LEFT JOIN (
          SELECT scna,SUM(liters) road_liters
          FROM fuel_purchases GROUP BY scna
        ) f ON f.scna=t.scna
        WHERE t.entry_done=1
      ),
      vehicle_avg AS (
        SELECT plate,AVG(l100) avg_l100,COUNT(l100) n
        FROM trip_cons
        WHERE l100 IS NOT NULL AND l100>0
        GROUP BY plate
      )
      SELECT
        tc.scna,tc.plate,tc.driver_name,
        ROUND(tc.l100,2) trip_l100,
        ROUND(va.avg_l100,2) avg_l100,
        ROUND(((tc.l100/va.avg_l100)-1)*100,1) percent_over
      FROM trip_cons tc
      JOIN vehicle_avg va ON va.plate=tc.plate
      WHERE va.n>=3
        AND tc.l100 > va.avg_l100*1.20
      ORDER BY percent_over DESC
      LIMIT 100
    """)]

    c.close()
    return {
        "delay_threshold_hours":48,
        "fuel_threshold_percent":20,
        "delayed": delayed,
        "fuel_alerts": fuel_alerts
    }


@app.get("/api/live-operations")
def live_operations():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT t.scna,t.plate,t.status,t.exit_at,t.entry_at,
             d.name driver_name,a.name area_name,
             rs.expected_hours,rs.expected_km,rs.expected_l100,rs.tolerance_percent,
             CASE WHEN t.status='Yolda' AND t.exit_at IS NOT NULL
                  THEN ROUND((JULIANDAY('now','localtime')-JULIANDAY(t.exit_at))*24,1)
                  ELSE 0 END hours_on_road,
             CASE WHEN t.status='Yolda' AND t.exit_at IS NOT NULL
                       AND rs.expected_hours IS NOT NULL
                       AND (JULIANDAY('now','localtime')-JULIANDAY(t.exit_at))*24 > rs.expected_hours
                  THEN 1 ELSE 0 END delayed
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN areas a ON a.id=t.area_id
      LEFT JOIN route_standards rs ON rs.area_id=t.area_id
      WHERE t.status IN ('Bekliyor','Yolda')
      ORDER BY delayed DESC,t.exit_at ASC,t.id DESC
      LIMIT 500
    """)]
    s=dict(c.execute("""
      SELECT COUNT(*) total,
             SUM(CASE WHEN status='Yolda' THEN 1 ELSE 0 END) onroad,
             SUM(CASE WHEN status='Bekliyor' THEN 1 ELSE 0 END) waiting,
             SUM(CASE WHEN status='Tamamlandı' THEN 1 ELSE 0 END) completed
      FROM trips
    """).fetchone())
    s["delayed"]=sum(1 for r in rows if r["delayed"])
    s["maintenance_due"]=c.execute("""
      SELECT COUNT(*) c FROM maintenance m
      LEFT JOIN (
        SELECT plate,MAX(CASE WHEN entry_km>exit_km THEN entry_km ELSE exit_km END) current_km
        FROM trips GROUP BY plate
      ) k ON k.plate=m.plate
      WHERE m.next_service_km>0 AND COALESCE(k.current_km,0)>=m.next_service_km-2000
    """).fetchone()["c"]
    c.close()
    return {"summary":s,"rows":rows}

@app.get("/api/route-standards")
def route_standards():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT rs.*,a.name area_name,a.km_go,a.km_back
      FROM route_standards rs
      LEFT JOIN areas a ON a.id=rs.area_id
      ORDER BY a.name
    """)]
    c.close()
    return rows

@app.post("/api/route-standards")
def save_route_standard(x: RouteStandardIn):
    c=db()
    c.execute("""
      INSERT INTO route_standards(area_id,expected_hours,expected_km,expected_l100,tolerance_percent,updated_at)
      VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
      ON CONFLICT(area_id) DO UPDATE SET
        expected_hours=excluded.expected_hours,
        expected_km=excluded.expected_km,
        expected_l100=excluded.expected_l100,
        tolerance_percent=excluded.tolerance_percent,
        updated_at=CURRENT_TIMESTAMP
    """,(x.area_id,x.expected_hours,x.expected_km,x.expected_l100,x.tolerance_percent))
    c.commit(); c.close()
    return {"ok":True}

@app.get("/api/maintenance")
def maintenance_list():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT m.*,
             COALESCE(k.current_km,0) current_km,
             CASE WHEN m.next_service_km<=0 THEN 999999999
                  ELSE m.next_service_km-COALESCE(k.current_km,0) END km_left
      FROM maintenance m
      LEFT JOIN (
        SELECT plate,MAX(CASE WHEN entry_km>exit_km THEN entry_km ELSE exit_km END) current_km
        FROM trips GROUP BY plate
      ) k ON k.plate=m.plate
      ORDER BY km_left ASC,m.plate
    """)]
    c.close()
    return rows

@app.post("/api/maintenance")
def maintenance_save(x: MaintenanceIn):
    c=db()
    plate=x.plate.strip().upper()
    old=c.execute("SELECT id FROM maintenance WHERE plate=? ORDER BY id DESC LIMIT 1",(plate,)).fetchone()
    if old:
        c.execute("""
          UPDATE maintenance SET
            last_service_km=?,next_service_km=?,oil_change_km=?,
            tire_note=?,brake_note=?,engine_note=?,note=?,updated_at=CURRENT_TIMESTAMP
          WHERE id=?
        """,(x.last_service_km,x.next_service_km,x.oil_change_km,
             x.tire_note,x.brake_note,x.engine_note,x.note,old["id"]))
    else:
        c.execute("""
          INSERT INTO maintenance(
            plate,last_service_km,next_service_km,oil_change_km,
            tire_note,brake_note,engine_note,note
          ) VALUES(?,?,?,?,?,?,?,?)
        """,(plate,x.last_service_km,x.next_service_km,x.oil_change_km,
             x.tire_note,x.brake_note,x.engine_note,x.note))
    c.commit(); c.close()
    return {"ok":True}

@app.get("/api/route-fuel-alerts")
def route_fuel_alerts():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT t.scna,t.plate,d.name driver_name,a.name area_name,
             rs.expected_l100,rs.tolerance_percent,
             ROUND(
               ((t.tank_start_liters+t.exit_official_fuel_liters+t.exit_commercial_fuel_liters+
                 t.exit_baghdad_fuel_liters+COALESCE(f.road_liters,0)-t.tank_end_liters)
                /(t.entry_km-t.exit_km))*100,2
             ) actual_l100
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN areas a ON a.id=t.area_id
      LEFT JOIN route_standards rs ON rs.area_id=t.area_id
      LEFT JOIN (
        SELECT scna,SUM(liters) road_liters FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      WHERE t.entry_done=1
        AND rs.expected_l100>0
        AND (t.entry_km-t.exit_km)>0
        AND (((t.tank_start_liters+t.exit_official_fuel_liters+t.exit_commercial_fuel_liters+
               t.exit_baghdad_fuel_liters+COALESCE(f.road_liters,0)-t.tank_end_liters)
              /(t.entry_km-t.exit_km))*100)
            > rs.expected_l100*(1+rs.tolerance_percent/100.0)
      ORDER BY actual_l100 DESC
      LIMIT 200
    """)]
    c.close()
    return rows


def _date_filter_sql(date_from="", date_to=""):
    where = ""
    params = []
    if date_from:
        where += " AND DATE(COALESCE(NULLIF(t.trip_date,''),t.created_at)) >= DATE(?)"
        params.append(date_from)
    if date_to:
        where += " AND DATE(COALESCE(NULLIF(t.trip_date,''),t.created_at)) <= DATE(?)"
        params.append(date_to)
    return where, params

@app.get("/api/finance-summary")
def finance_summary(date_from: str="", date_to: str=""):
    c=db()
    date_sql, params = _date_filter_sql(date_from,date_to)

    row=c.execute(f"""
      SELECT
        COUNT(*) trip_count,
        COALESCE(SUM(t.net_kg),0) total_kg,

        COALESCE(SUM(
          CASE WHEN t.freight_basis='KG'
               THEN t.net_kg*t.freight_rate
               ELSE (t.net_kg/1000.0)*t.freight_rate END
        ),0) total_freight,

        COALESCE(SUM(
          t.exit_official_fuel_total +
          t.exit_commercial_fuel_total +
          t.exit_baghdad_fuel_total +
          COALESCE(f.road_total,0)
        ),0) fuel_cost,

        COALESCE(SUM(
          t.exit_allowance +
          t.exit_premium +
          t.dock_fee +
          t.port_fee +
          t.sonar +
          t.exit_other +
          t.entry_extra_expense_1 +
          t.entry_extra_expense_2 +
          t.entry_extra_expense_3
        ),0) other_cost,

        COALESCE(SUM(
          CASE WHEN t.entry_done=1 THEN MAX(t.entry_km-t.exit_km,0) ELSE 0 END
        ),0) total_km,

        COALESCE(SUM(t.entry_collection),0) collected,

        COALESCE(SUM(
          CASE WHEN t.entry_done=1 THEN
            MAX(
              (CASE WHEN t.freight_basis='KG'
                    THEN t.net_kg*t.freight_rate
                    ELSE (t.net_kg/1000.0)*t.freight_rate END)
              - t.entry_collection,
              0
            )
          ELSE 0 END
        ),0) receivable

      FROM trips t
      LEFT JOIN (
        SELECT scna,SUM(total) road_total
        FROM fuel_purchases
        GROUP BY scna
      ) f ON f.scna=t.scna
      WHERE 1=1 {date_sql}
    """,params).fetchone()

    r=dict(row)

    total_cost=float(r["fuel_cost"] or 0)+float(r["other_cost"] or 0)
    total_profit=float(r["total_freight"] or 0)-total_cost
    total_ton=float(r["total_kg"] or 0)/1000.0
    total_km=float(r["total_km"] or 0)

    r["total_cost"]=total_cost
    r["total_profit"]=total_profit
    r["profit_per_km"]=total_profit/total_km if total_km>0 else 0
    r["profit_per_ton"]=total_profit/total_ton if total_ton>0 else 0
    r["margin_percent"]=(total_profit/float(r["total_freight"]))*100 if float(r["total_freight"] or 0)>0 else 0
    r["total_ton"]=total_ton

    c.close()
    return r

@app.get("/api/finance-by-customer")
def finance_by_customer(date_from: str="", date_to: str=""):
    c=db()
    date_sql, params = _date_filter_sql(date_from,date_to)
    rows=[dict(r) for r in c.execute(f"""
      SELECT
        COALESCE(cu.name,'Tanımsız') name,
        COUNT(*) trip_count,
        ROUND(SUM(t.net_kg)/1000.0,2) total_ton,

        ROUND(SUM(
          CASE WHEN t.freight_basis='KG'
               THEN t.net_kg*t.freight_rate
               ELSE (t.net_kg/1000.0)*t.freight_rate END
        ),2) freight,

        ROUND(SUM(
          t.exit_official_fuel_total +
          t.exit_commercial_fuel_total +
          t.exit_baghdad_fuel_total +
          COALESCE(f.road_total,0) +
          t.exit_allowance +
          t.exit_premium +
          t.dock_fee +
          t.port_fee +
          t.sonar +
          t.exit_other +
          t.entry_extra_expense_1 +
          t.entry_extra_expense_2 +
          t.entry_extra_expense_3
        ),2) cost,

        ROUND(SUM(
          (CASE WHEN t.freight_basis='KG'
                THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate END)
          -
          (
            t.exit_official_fuel_total +
            t.exit_commercial_fuel_total +
            t.exit_baghdad_fuel_total +
            COALESCE(f.road_total,0) +
            t.exit_allowance +
            t.exit_premium +
            t.dock_fee +
            t.port_fee +
            t.sonar +
            t.exit_other +
            t.entry_extra_expense_1 +
            t.entry_extra_expense_2 +
            t.entry_extra_expense_3
          )
        ),2) profit

      FROM trips t
      LEFT JOIN customers cu ON cu.id=t.customer_id
      LEFT JOIN (
        SELECT scna,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      WHERE 1=1 {date_sql}
      GROUP BY cu.id,cu.name
      ORDER BY profit DESC
    """,params)]
    c.close()
    return rows

@app.get("/api/finance-by-area")
def finance_by_area(date_from: str="", date_to: str=""):
    c=db()
    date_sql, params = _date_filter_sql(date_from,date_to)
    rows=[dict(r) for r in c.execute(f"""
      SELECT
        COALESCE(a.name,'Tanımsız') name,
        COUNT(*) trip_count,
        ROUND(SUM(t.net_kg)/1000.0,2) total_ton,

        ROUND(SUM(
          CASE WHEN t.freight_basis='KG'
               THEN t.net_kg*t.freight_rate
               ELSE (t.net_kg/1000.0)*t.freight_rate END
        ),2) freight,

        ROUND(SUM(
          CASE WHEN t.entry_done=1 THEN MAX(t.entry_km-t.exit_km,0) ELSE 0 END
        ),2) total_km,

        ROUND(SUM(
          t.exit_official_fuel_total +
          t.exit_commercial_fuel_total +
          t.exit_baghdad_fuel_total +
          COALESCE(f.road_total,0) +
          t.exit_allowance +
          t.exit_premium +
          t.dock_fee +
          t.port_fee +
          t.sonar +
          t.exit_other +
          t.entry_extra_expense_1 +
          t.entry_extra_expense_2 +
          t.entry_extra_expense_3
        ),2) cost,

        ROUND(SUM(
          (CASE WHEN t.freight_basis='KG'
                THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate END)
          -
          (
            t.exit_official_fuel_total +
            t.exit_commercial_fuel_total +
            t.exit_baghdad_fuel_total +
            COALESCE(f.road_total,0) +
            t.exit_allowance +
            t.exit_premium +
            t.dock_fee +
            t.port_fee +
            t.sonar +
            t.exit_other +
            t.entry_extra_expense_1 +
            t.entry_extra_expense_2 +
            t.entry_extra_expense_3
          )
        ),2) profit

      FROM trips t
      LEFT JOIN areas a ON a.id=t.area_id
      LEFT JOIN (
        SELECT scna,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      WHERE 1=1 {date_sql}
      GROUP BY a.id,a.name
      ORDER BY profit DESC
    """,params)]
    c.close()
    return rows

@app.get("/api/finance-by-cargo")
def finance_by_cargo(date_from: str="", date_to: str=""):
    c=db()
    date_sql, params = _date_filter_sql(date_from,date_to)
    rows=[dict(r) for r in c.execute(f"""
      SELECT
        COALESCE(cc.name,'Tanımsız') name,
        COUNT(*) trip_count,
        ROUND(SUM(t.net_kg)/1000.0,2) total_ton,

        ROUND(SUM(
          CASE WHEN t.freight_basis='KG'
               THEN t.net_kg*t.freight_rate
               ELSE (t.net_kg/1000.0)*t.freight_rate END
        ),2) freight,

        ROUND(SUM(
          t.exit_official_fuel_total +
          t.exit_commercial_fuel_total +
          t.exit_baghdad_fuel_total +
          COALESCE(f.road_total,0) +
          t.exit_allowance +
          t.exit_premium +
          t.dock_fee +
          t.port_fee +
          t.sonar +
          t.exit_other +
          t.entry_extra_expense_1 +
          t.entry_extra_expense_2 +
          t.entry_extra_expense_3
        ),2) cost,

        ROUND(SUM(
          (CASE WHEN t.freight_basis='KG'
                THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate END)
          -
          (
            t.exit_official_fuel_total +
            t.exit_commercial_fuel_total +
            t.exit_baghdad_fuel_total +
            COALESCE(f.road_total,0) +
            t.exit_allowance +
            t.exit_premium +
            t.dock_fee +
            t.port_fee +
            t.sonar +
            t.exit_other +
            t.entry_extra_expense_1 +
            t.entry_extra_expense_2 +
            t.entry_extra_expense_3
          )
        ),2) profit

      FROM trips t
      LEFT JOIN cargo_categories cc ON cc.id=t.cargo_category_id
      LEFT JOIN (
        SELECT scna,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      WHERE 1=1 {date_sql}
      GROUP BY cc.id,cc.name
      ORDER BY profit DESC
    """,params)]
    c.close()
    return rows

@app.get("/api/finance-monthly")
def finance_monthly():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT
        SUBSTR(COALESCE(NULLIF(t.trip_date,''),t.created_at),1,7) month,
        COUNT(*) trip_count,
        ROUND(SUM(t.net_kg)/1000.0,2) total_ton,
        ROUND(SUM(
          CASE WHEN t.freight_basis='KG'
               THEN t.net_kg*t.freight_rate
               ELSE (t.net_kg/1000.0)*t.freight_rate END
        ),2) freight,
        ROUND(SUM(
          t.exit_official_fuel_total+t.exit_commercial_fuel_total+
          t.exit_baghdad_fuel_total+COALESCE(f.road_total,0)+
          t.exit_allowance+t.exit_premium+t.dock_fee+t.port_fee+t.sonar+
          t.exit_other+t.entry_extra_expense_1+t.entry_extra_expense_2+t.entry_extra_expense_3
        ),2) cost
      FROM trips t
      LEFT JOIN (
        SELECT scna,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      GROUP BY month
      HAVING month IS NOT NULL AND month<>''
      ORDER BY month DESC
      LIMIT 24
    """)]
    for r in rows:
        r["profit"]=float(r["freight"] or 0)-float(r["cost"] or 0)
    c.close()
    return rows


@app.get("/api/vehicle-card/{plate}")
def vehicle_card(plate: str):
    c=db()

    vehicle=c.execute("""
      SELECT
        v.plate,
        d.name driver_name,
        d.phone,
        d.d_no
      FROM vehicles v
      LEFT JOIN trips lt ON lt.id=(
        SELECT t2.id
        FROM trips t2
        WHERE UPPER(t2.plate)=UPPER(v.plate)
        ORDER BY
          CASE WHEN t2.status='Yolda' THEN 0 ELSE 1 END,
          t2.id DESC
        LIMIT 1
      )
      LEFT JOIN drivers d ON d.id=lt.driver_id
      WHERE UPPER(v.plate)=UPPER(?)
      LIMIT 1
    """,(plate,)).fetchone()

    if not vehicle:
        c.close()
        raise HTTPException(404,"Araç bulunamadı")

    summary=c.execute("""
      SELECT
        COUNT(*) trip_count,
        SUM(CASE WHEN t.entry_done=1 THEN 1 ELSE 0 END) completed_count,
        ROUND(SUM(t.net_kg)/1000.0,2) total_ton,
        ROUND(SUM(CASE WHEN t.entry_done=1 THEN MAX(t.entry_km-t.exit_km,0) ELSE 0 END),2) total_km,
        ROUND(SUM(
          CASE WHEN t.freight_basis='KG'
               THEN t.net_kg*t.freight_rate
               ELSE (t.net_kg/1000.0)*t.freight_rate END
        ),2) total_freight,
        ROUND(AVG(
          CASE
            WHEN t.entry_done=1
             AND (t.entry_km-t.exit_km)>0
             AND (
               t.tank_start_liters+t.exit_official_fuel_liters+t.exit_commercial_fuel_liters+
               t.exit_baghdad_fuel_liters+COALESCE(f.road_liters,0)-t.tank_end_liters
             )>0
            THEN (
              (
                t.tank_start_liters+t.exit_official_fuel_liters+t.exit_commercial_fuel_liters+
                t.exit_baghdad_fuel_liters+COALESCE(f.road_liters,0)-t.tank_end_liters
              )/(t.entry_km-t.exit_km)
            )*100
          END
        ),2) avg_l100,
        ROUND(SUM(
          (CASE WHEN t.freight_basis='KG'
                THEN t.net_kg*t.freight_rate
                ELSE (t.net_kg/1000.0)*t.freight_rate END)
          -
          (
            t.exit_official_fuel_total+t.exit_commercial_fuel_total+t.exit_baghdad_fuel_total+
            COALESCE(f.road_total,0)+t.exit_allowance+t.exit_premium+t.dock_fee+t.port_fee+
            t.sonar+t.exit_other+t.entry_extra_expense_1+t.entry_extra_expense_2+t.entry_extra_expense_3
          )
        ),2) total_profit
      FROM trips t
      LEFT JOIN (
        SELECT scna,SUM(liters) road_liters,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      WHERE UPPER(t.plate)=UPPER(?)
    """,(plate,)).fetchone()

    trips=[dict(r) for r in c.execute(tq()+"""
      WHERE UPPER(t.plate)=UPPER(?)
      ORDER BY t.id DESC
      LIMIT 20
    """,(plate,))]

    maint=c.execute("""
      SELECT * FROM maintenance
      WHERE UPPER(plate)=UPPER(?)
      ORDER BY id DESC LIMIT 1
    """,(plate,)).fetchone()

    c.close()

    return {
      "vehicle":dict(vehicle),
      "summary":dict(summary),
      "maintenance":dict(maint) if maint else None,
      "trips":trips
    }

@app.get("/api/driver-card/{driver_name}")
def driver_card(driver_name: str):
    c=db()

    driver=c.execute("""
      SELECT id,name,phone,d_no
      FROM drivers
      WHERE UPPER(name)=UPPER(?)
      LIMIT 1
    """,(driver_name,)).fetchone()

    if not driver:
        c.close()
        raise HTTPException(404,"Şoför bulunamadı")

    summary=c.execute("""
      SELECT
        COUNT(*) trip_count,
        SUM(CASE WHEN t.entry_done=1 THEN 1 ELSE 0 END) completed_count,
        ROUND(SUM(t.net_kg)/1000.0,2) total_ton,
        ROUND(SUM(CASE WHEN t.entry_done=1 THEN MAX(t.entry_km-t.exit_km,0) ELSE 0 END),2) total_km,
        ROUND(AVG(
          CASE
            WHEN t.entry_done=1
             AND (t.entry_km-t.exit_km)>0
             AND (
               t.tank_start_liters+t.exit_official_fuel_liters+t.exit_commercial_fuel_liters+
               t.exit_baghdad_fuel_liters+COALESCE(f.road_liters,0)-t.tank_end_liters
             )>0
            THEN (
              (
                t.tank_start_liters+t.exit_official_fuel_liters+t.exit_commercial_fuel_liters+
                t.exit_baghdad_fuel_liters+COALESCE(f.road_liters,0)-t.tank_end_liters
              )/(t.entry_km-t.exit_km)
            )*100
          END
        ),2) avg_l100,
        ROUND(SUM(
          CASE WHEN t.entry_done=1 THEN
            COALESCE(
              t.excel_remain,
              CASE
                WHEN COALESCE(t.entry_cash_handed,0)=0
                 AND COALESCE(t.entry_collection,0)>0
                 AND t.entry_done=1
                THEN t.entry_collection -
                  (CASE WHEN t.freight_basis='KG'
                        THEN t.net_kg*t.freight_rate
                        ELSE (t.net_kg/1000.0)*t.freight_rate END)
                ELSE
                  t.entry_cash_handed -
                  (
                    t.entry_collection -
                    (
                      COALESCE(f.road_total,0)+
                      t.entry_extra_expense_1+t.entry_extra_expense_2+t.entry_extra_expense_3
                    )
                  )
              END
            )
          ELSE 0 END
        ),2) cash_diff,
        SUM(CASE WHEN t.status='Yolda' THEN 1 ELSE 0 END) active_trips
      FROM trips t
      LEFT JOIN (
        SELECT scna,SUM(liters) road_liters,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      WHERE t.driver_id=?
    """,(driver["id"],)).fetchone()

    trips=[dict(r) for r in c.execute(tq()+"""
      WHERE t.driver_id=?
      ORDER BY t.id DESC
      LIMIT 20
    """,(driver["id"],))]

    plates=[r["plate"] for r in c.execute("""
      SELECT DISTINCT plate
      FROM trips
      WHERE driver_id=?
      ORDER BY plate
    """,(driver["id"],))]

    c.close()

    return {
      "driver":dict(driver),
      "summary":dict(summary),
      "plates":plates,
      "trips":trips
    }

@app.get("/api/anomalies")
def anomalies():
    c=db()

    # 1) Yakıt anomalisi: aracın kendi geçmiş ortalamasından %20 fazla
    fuel=[dict(r) for r in c.execute("""
      WITH trip_cons AS (
        SELECT
          t.id,t.scna,t.plate,d.name driver_name,a.name area_name,
          CASE
            WHEN t.entry_done=1
             AND (t.entry_km-t.exit_km)>0
             AND (
               t.tank_start_liters+t.exit_official_fuel_liters+t.exit_commercial_fuel_liters+
               t.exit_baghdad_fuel_liters+COALESCE(f.road_liters,0)-t.tank_end_liters
             )>0
            THEN (
              (
                t.tank_start_liters+t.exit_official_fuel_liters+t.exit_commercial_fuel_liters+
                t.exit_baghdad_fuel_liters+COALESCE(f.road_liters,0)-t.tank_end_liters
              )/(t.entry_km-t.exit_km)
            )*100
          END l100
        FROM trips t
        LEFT JOIN drivers d ON d.id=t.driver_id
        LEFT JOIN areas a ON a.id=t.area_id
        LEFT JOIN (
          SELECT scna,SUM(liters) road_liters
          FROM fuel_purchases GROUP BY scna
        ) f ON f.scna=t.scna
        WHERE t.entry_done=1
      ),
      avg_cons AS (
        SELECT plate,AVG(l100) avg_l100,COUNT(l100) n
        FROM trip_cons
        WHERE l100 IS NOT NULL AND l100>0
        GROUP BY plate
      )
      SELECT
        tc.scna,tc.plate,tc.driver_name,tc.area_name,
        ROUND(tc.l100,2) value,
        ROUND(ac.avg_l100,2) baseline,
        ROUND(((tc.l100/ac.avg_l100)-1)*100,1) deviation
      FROM trip_cons tc
      JOIN avg_cons ac ON ac.plate=tc.plate
      WHERE ac.n>=3 AND tc.l100>ac.avg_l100*1.20
      ORDER BY deviation DESC
      LIMIT 100
    """)]

    # 2) KM anomalisi
    km=[dict(r) for r in c.execute("""
      SELECT
        t.scna,t.plate,d.name driver_name,a.name area_name,
        ROUND(MAX(t.entry_km-t.exit_km,0),2) value,
        ROUND(rs.expected_km,2) baseline,
        ROUND(((MAX(t.entry_km-t.exit_km,0)/rs.expected_km)-1)*100,1) deviation
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN areas a ON a.id=t.area_id
      LEFT JOIN route_standards rs ON rs.area_id=t.area_id
      WHERE t.entry_done=1
        AND rs.expected_km>0
        AND MAX(t.entry_km-t.exit_km,0) > rs.expected_km*(1+rs.tolerance_percent/100.0)
      ORDER BY deviation DESC
      LIMIT 100
    """)]

    # Ortak şoför para farkı mantığı:
    # Excel kökenli kayıtta REMAIN hücresine güvenmiyoruz.
    # COLLECTION varsa fark = COLLECTION - AMOUNT.
    # Yeni program girişinde gerçek teslim edilen para hesabı kullanılır.
    cash=[dict(r) for r in c.execute("""
      WITH cash_calc AS (
        SELECT
          t.scna,t.plate,d.name driver_name,a.name area_name,
          CASE
            WHEN t.excel_remain IS NOT NULL THEN
              CASE
                WHEN COALESCE(t.entry_collection,0)>0 THEN
                  t.entry_collection -
                  (
                    CASE
                      WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                      ELSE (t.net_kg/1000.0)*t.freight_rate
                    END
                  )
                ELSE 0
              END

            WHEN COALESCE(t.entry_cash_handed,0)=0
             AND COALESCE(t.entry_collection,0)>0
             AND t.entry_done=1 THEN
              t.entry_collection -
              (
                CASE
                  WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                  ELSE (t.net_kg/1000.0)*t.freight_rate
                END
              )

            ELSE
              t.entry_cash_handed -
              (
                t.entry_collection -
                (
                  COALESCE(f.road_total,0)+
                  t.entry_extra_expense_1+
                  t.entry_extra_expense_2+
                  t.entry_extra_expense_3
                )
              )
          END cash_diff,

          CASE
            WHEN t.excel_remain IS NOT NULL THEN 'EXCEL COLLECTION-AMOUNT'
            WHEN COALESCE(t.entry_cash_handed,0)=0
             AND COALESCE(t.entry_collection,0)>0
             AND t.entry_done=1 THEN 'ESKİ EXCEL HESABI'
            ELSE 'PROGRAM HESABI'
          END source

        FROM trips t
        LEFT JOIN drivers d ON d.id=t.driver_id
        LEFT JOIN areas a ON a.id=t.area_id
        LEFT JOIN (
          SELECT scna,SUM(total) road_total
          FROM fuel_purchases
          GROUP BY scna
        ) f ON f.scna=t.scna
        WHERE t.entry_done=1
      )
      SELECT
        scna,plate,driver_name,area_name,
        ROUND(cash_diff,2) value,
        0 baseline,
        0 deviation,
        source
      FROM cash_calc
      WHERE cash_diff < -0.01
      ORDER BY cash_diff ASC
      LIMIT 500
    """)]

    # 4) Son 5 tamamlanmış seferin 3+ tanesinde eksik para
    repeated=[dict(r) for r in c.execute("""
      WITH trip_cash AS (
        SELECT
          t.id,t.driver_id,d.name driver_name,t.scna,
          CASE
            WHEN t.excel_remain IS NOT NULL THEN
              CASE
                WHEN COALESCE(t.entry_collection,0)>0 THEN
                  t.entry_collection -
                  (
                    CASE
                      WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                      ELSE (t.net_kg/1000.0)*t.freight_rate
                    END
                  )
                ELSE 0
              END

            WHEN COALESCE(t.entry_cash_handed,0)=0
             AND COALESCE(t.entry_collection,0)>0
             AND t.entry_done=1 THEN
              t.entry_collection -
              (
                CASE
                  WHEN t.freight_basis='KG' THEN t.net_kg*t.freight_rate
                  ELSE (t.net_kg/1000.0)*t.freight_rate
                END
              )

            ELSE
              t.entry_cash_handed -
              (
                t.entry_collection -
                (
                  COALESCE(f.road_total,0)+
                  t.entry_extra_expense_1+
                  t.entry_extra_expense_2+
                  t.entry_extra_expense_3
                )
              )
          END cash_diff

        FROM trips t
        LEFT JOIN drivers d ON d.id=t.driver_id
        LEFT JOIN (
          SELECT scna,SUM(total) road_total
          FROM fuel_purchases
          GROUP BY scna
        ) f ON f.scna=t.scna
        WHERE t.entry_done=1
          AND t.driver_id IS NOT NULL
      ),
      ranked AS (
        SELECT *,
          ROW_NUMBER() OVER(PARTITION BY driver_id ORDER BY id DESC) rn
        FROM trip_cash
      )
      SELECT
        driver_name,
        SUM(CASE WHEN cash_diff < -0.01 THEN 1 ELSE 0 END) short_count,
        COUNT(*) checked_count
      FROM ranked
      WHERE rn<=5
      GROUP BY driver_id,driver_name
      HAVING COUNT(*)>=3
         AND SUM(CASE WHEN cash_diff < -0.01 THEN 1 ELSE 0 END)>=3
      ORDER BY short_count DESC,driver_name
    """)]

    # Sayaçlar: limitten bağımsız gerçek toplamı göster.
    cash_count=c.execute("""
      WITH cash_calc AS (
        SELECT
          CASE
            WHEN t.excel_remain IS NOT NULL THEN
              CASE
                WHEN COALESCE(t.entry_collection,0)>0 THEN
                  t.entry_collection -
                  (CASE WHEN t.freight_basis='KG'
                        THEN t.net_kg*t.freight_rate
                        ELSE (t.net_kg/1000.0)*t.freight_rate END)
                ELSE 0
              END
            WHEN COALESCE(t.entry_cash_handed,0)=0
             AND COALESCE(t.entry_collection,0)>0
             AND t.entry_done=1 THEN
              t.entry_collection -
              (CASE WHEN t.freight_basis='KG'
                    THEN t.net_kg*t.freight_rate
                    ELSE (t.net_kg/1000.0)*t.freight_rate END)
            ELSE
              t.entry_cash_handed -
              (
                t.entry_collection -
                (
                  COALESCE(f.road_total,0)+
                  t.entry_extra_expense_1+
                  t.entry_extra_expense_2+
                  t.entry_extra_expense_3
                )
              )
          END cash_diff
        FROM trips t
        LEFT JOIN (
          SELECT scna,SUM(total) road_total
          FROM fuel_purchases GROUP BY scna
        ) f ON f.scna=t.scna
        WHERE t.entry_done=1
      )
      SELECT COUNT(*) c
      FROM cash_calc
      WHERE cash_diff < -0.01
    """).fetchone()["c"]

    c.close()
    return {
      "fuel":fuel,
      "km":km,
      "cash":cash,
      "cash_total_count":cash_count,
      "repeated_driver_cash":repeated
    }


@app.get("/api/daily-manager-summary")
def daily_manager_summary(day: str=""):
    if not day:
        day=datetime.now().strftime("%Y-%m-%d")
    c=db()

    exited=c.execute("""
      SELECT COUNT(*) c FROM trips
      WHERE DATE(exit_at)=DATE(?)
    """,(day,)).fetchone()["c"]

    entered=c.execute("""
      SELECT COUNT(*) c FROM trips
      WHERE DATE(entry_at)=DATE(?)
    """,(day,)).fetchone()["c"]

    onroad=c.execute("SELECT COUNT(*) c FROM trips WHERE status='Yolda'").fetchone()["c"]

    delayed=c.execute("""
      SELECT COUNT(*) c
      FROM trips t
      LEFT JOIN route_standards rs ON rs.area_id=t.area_id
      WHERE t.status='Yolda'
        AND t.exit_at IS NOT NULL
        AND rs.expected_hours>0
        AND (JULIANDAY('now','localtime')-JULIANDAY(t.exit_at))*24 > rs.expected_hours
    """).fetchone()["c"]

    r=c.execute("""
      SELECT
        COALESCE(SUM(t.net_kg),0) kg,
        COALESCE(SUM(
          CASE WHEN t.freight_basis='KG'
               THEN t.net_kg*t.freight_rate
               ELSE (t.net_kg/1000.0)*t.freight_rate END
        ),0) freight,
        COALESCE(SUM(t.entry_collection),0) collected,
        COALESCE(SUM(
          t.exit_official_fuel_total+t.exit_commercial_fuel_total+t.exit_baghdad_fuel_total+
          COALESCE(f.road_total,0)+t.exit_allowance+t.exit_premium+t.dock_fee+t.port_fee+
          t.sonar+t.exit_other+t.entry_extra_expense_1+t.entry_extra_expense_2+t.entry_extra_expense_3
        ),0) cost,
        COALESCE(SUM(
          CASE WHEN t.entry_done=1 THEN
            COALESCE(
              t.excel_remain,
              CASE
                WHEN COALESCE(t.entry_cash_handed,0)=0
                 AND COALESCE(t.entry_collection,0)>0
                 AND t.entry_done=1
                THEN t.entry_collection -
                  (CASE WHEN t.freight_basis='KG'
                        THEN t.net_kg*t.freight_rate
                        ELSE (t.net_kg/1000.0)*t.freight_rate END)
                ELSE
                  t.entry_cash_handed -
                  (
                    t.entry_collection -
                    (
                      COALESCE(f.road_total,0)+
                      t.entry_extra_expense_1+t.entry_extra_expense_2+t.entry_extra_expense_3
                    )
                  )
              END
            )
          ELSE 0 END
        ),0) driver_diff
      FROM trips t
      LEFT JOIN (
        SELECT scna,SUM(total) road_total FROM fuel_purchases GROUP BY scna
      ) f ON f.scna=t.scna
      WHERE DATE(COALESCE(NULLIF(t.trip_date,''),t.created_at))=DATE(?)
    """,(day,)).fetchone()

    x=dict(r)
    x["ton"]=float(x["kg"] or 0)/1000.0
    x["profit"]=float(x["freight"] or 0)-float(x["cost"] or 0)

    rows=[dict(z) for z in c.execute("""
      SELECT t.scna,t.plate,d.name driver_name,a.name area_name,t.status,t.exit_at,t.entry_at,
             t.net_kg,
             CASE WHEN t.freight_basis='KG'
                  THEN t.net_kg*t.freight_rate
                  ELSE (t.net_kg/1000.0)*t.freight_rate END freight_total
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN areas a ON a.id=t.area_id
      WHERE DATE(t.exit_at)=DATE(?) OR DATE(t.entry_at)=DATE(?)
      ORDER BY COALESCE(t.entry_at,t.exit_at) DESC
    """,(day,day))]

    c.close()
    return {
      "day":day,"exited":exited,"entered":entered,"onroad":onroad,"delayed":delayed,
      **x,"rows":rows
    }


def _validate_trip_values(data):
    errors=[]
    warnings=[]

    kg=float(data.get("net_kg") or 0)
    rate=float(data.get("freight_rate") or 0)
    exit_km=float(data.get("exit_km") or 0)
    entry_km=float(data.get("entry_km") or 0)
    tank_start=float(data.get("tank_start_liters") or 0)
    tank_end=float(data.get("tank_end_liters") or 0)
    collection=float(data.get("entry_collection") or 0)

    if kg < 0:
        errors.append("Net KG negatif olamaz.")
    if kg > 80000:
        warnings.append(f"Net KG çok yüksek görünüyor: {kg:,.0f}")

    if rate < 0:
        errors.append("Navlun birim fiyatı negatif olamaz.")
    if rate > 1000000:
        warnings.append(f"Navlun birim fiyatı çok yüksek görünüyor: {rate:,.0f}")

    if exit_km < 0 or entry_km < 0:
        errors.append("KM değerleri negatif olamaz.")
    if entry_km > 0 and exit_km > 0 and entry_km < exit_km:
        errors.append("Giriş KM, çıkış KM'den küçük olamaz.")
    if entry_km > 0 and exit_km > 0 and (entry_km-exit_km) > 5000:
        warnings.append(f"Sefer KM farkı çok yüksek: {entry_km-exit_km:,.0f} KM")

    for label,val in [
        ("Çıkış depo mazotu",tank_start),
        ("Dönüş depo mazotu",tank_end),
    ]:
        if val < 0:
            errors.append(f"{label} negatif olamaz.")
        if val > 2000:
            warnings.append(f"{label} çok yüksek görünüyor: {val:,.0f} LT")

    if collection < 0:
        errors.append("Müşteriden alınan para negatif olamaz.")

    return errors,warnings

@app.get("/api/trips/{scna}/edit-data")
def trip_edit_data(scna: str):
    c=db()
    row=c.execute("""
      SELECT *
      FROM trips
      WHERE scna=?
    """,(scna,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404,"SCNA bulunamadı")
    c.close()
    return dict(row)

@app.post("/api/trips/{scna}/validate")
def validate_trip(scna: str, x: TripEditIn):
    data=x.model_dump()
    errors,warnings=_validate_trip_values(data)
    return {"ok":len(errors)==0,"errors":errors,"warnings":warnings}

@app.put("/api/trips/{scna}")
def update_trip(scna: str, x: TripEditIn):
    data=x.model_dump()
    errors,warnings=_validate_trip_values(data)
    if errors:
        raise HTTPException(400,{"errors":errors,"warnings":warnings})

    c=db()
    old=c.execute("SELECT * FROM trips WHERE scna=?",(scna,)).fetchone()
    if not old:
        c.close()
        raise HTTPException(404,"SCNA bulunamadı")

    status=x.status if x.status in ("Bekliyor","Yolda","Tamamlandı") else "Bekliyor"
    exit_done=1 if status in ("Yolda","Tamamlandı") else 0
    entry_done=1 if status=="Tamamlandı" else 0

    c.execute("""
      UPDATE trips SET
        plate=?,
        driver_id=?,
        area_id=?,
        cargo_category_id=?,
        cargo_type=?,
        customer_id=?,
        trip_date=?,
        net_kg=?,
        freight_rate=?,
        freight_basis=?,
        exit_km=?,
        tank_start_liters=?,
        exit_premium=?,
        dock_fee=?,
        port_fee=?,
        sonar=?,
        exit_allowance=?,
        exit_other=?,
        entry_km=?,
        tank_end_liters=?,
        entry_extra_expense_1=?,
        entry_extra_expense_2=?,
        entry_extra_expense_3=?,
        entry_collection=?,
        entry_cash_handed=?,
        excel_remain=NULL,
        entry_note=?,
        manual_lock=1,
        manual_lock_at=DATETIME('now','localtime'),
        manual_lock_reason='SCNA Düzenleme Merkezi',
        status=?,
        exit_done=?,
        entry_done=?,
        exit_at=CASE
          WHEN ?=1 THEN COALESCE(exit_at,DATETIME('now','localtime'))
          ELSE NULL
        END,
        entry_at=CASE
          WHEN ?=1 THEN COALESCE(entry_at,DATETIME('now','localtime'))
          ELSE NULL
        END,
        updated_at=CURRENT_TIMESTAMP
      WHERE scna=?
    """,(
      x.plate.strip().upper(),x.driver_id,x.area_id,x.cargo_category_id,
      x.cargo_type.upper(),x.customer_id,x.trip_date,
      x.net_kg,x.freight_rate,x.freight_basis.upper(),
      x.exit_km,x.tank_start_liters,x.exit_premium,x.dock_fee,x.port_fee,x.sonar,
      x.exit_allowance,x.exit_other,x.entry_km,x.tank_end_liters,
      x.entry_extra_expense_1,x.entry_extra_expense_2,x.entry_extra_expense_3,
      x.entry_collection,x.entry_cash_handed,x.note,status,exit_done,entry_done,
      exit_done,entry_done,scna
    ))
    c.commit()
    c.close()

    audit("EDIT",scna,f"SCNA düzenlendi. Uyarı: {' | '.join(warnings) if warnings else 'Yok'}")
    return {"ok":True,"warnings":warnings}


@app.post("/api/trips/{scna}/manual-lock")
def set_manual_lock(scna: str):
    c=db()
    row=c.execute("SELECT id FROM trips WHERE UPPER(scna)=UPPER(?)",(scna,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404,"SCNA bulunamadı")
    c.execute("""
      UPDATE trips SET manual_lock=1,
        manual_lock_at=DATETIME('now','localtime'),
        manual_lock_reason='Kullanıcı koruması',
        updated_at=CURRENT_TIMESTAMP
      WHERE UPPER(scna)=UPPER(?)
    """,(scna,))
    c.commit(); c.close()
    audit("MANUAL_LOCK",scna,"Excel güncelleme koruması açıldı")
    return {"ok":True,"manual_lock":1}

@app.post("/api/trips/{scna}/manual-unlock")
def clear_manual_lock(scna: str):
    c=db()
    row=c.execute("SELECT id FROM trips WHERE UPPER(scna)=UPPER(?)",(scna,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404,"SCNA bulunamadı")
    c.execute("""
      UPDATE trips SET manual_lock=0,
        manual_lock_at='',
        manual_lock_reason='',
        updated_at=CURRENT_TIMESTAMP
      WHERE UPPER(scna)=UPPER(?)
    """,(scna,))
    c.commit(); c.close()
    audit("MANUAL_UNLOCK",scna,"Excel güncelleme koruması kaldırıldı")
    return {"ok":True,"manual_lock":0}

@app.post("/api/trips/{scna}/undo-entry")
def undo_entry(scna: str):
    c=db()
    row=c.execute("SELECT * FROM trips WHERE scna=?",(scna,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404,"SCNA bulunamadı")

    c.execute("""
      UPDATE trips SET
        entry_km=0,
        tank_end_liters=0,
        entry_extra_expense_1=0,
        entry_extra_expense_2=0,
        entry_extra_expense_3=0,
        entry_collection=0,
        entry_cash_handed=0,
        excel_remain=NULL,
        entry_note='',
        entry_done=0,
        entry_at=NULL,
        delivery_time='',
        status=CASE WHEN exit_done=1 THEN 'Yolda' ELSE 'Bekliyor' END,
        updated_at=CURRENT_TIMESTAMP
      WHERE scna=?
    """,(scna,))
    c.commit(); c.close()
    audit("UNDO_ENTRY",scna,"Giriş işlemi geri alındı")
    return {"ok":True}

@app.post("/api/trips/{scna}/undo-exit")
def undo_exit(scna: str):
    c=db()
    row=c.execute("SELECT * FROM trips WHERE scna=?",(scna,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404,"SCNA bulunamadı")

    c.execute("DELETE FROM fuel_purchases WHERE scna=?",(scna,))
    c.execute("""
      UPDATE trips SET
        exit_km=0,
        exit_cash=0,
        tank_start_liters=0,
        exit_official_fuel_liters=0,
        exit_official_fuel_total=0,
        exit_commercial_fuel_liters=0,
        exit_commercial_fuel_total=0,
        exit_baghdad_fuel_liters=0,
        exit_baghdad_fuel_total=0,
        exit_allowance=0,
        exit_other=0,
        exit_done=0,
        exit_at=NULL,

        entry_km=0,
        tank_end_liters=0,
        entry_extra_expense_1=0,
        entry_extra_expense_2=0,
        entry_extra_expense_3=0,
        entry_collection=0,
        entry_cash_handed=0,
        excel_remain=NULL,
        entry_note='',
        entry_done=0,
        entry_at=NULL,
        delivery_time='',

        status='Bekliyor',
        updated_at=CURRENT_TIMESTAMP
      WHERE scna=?
    """,(scna,))
    c.commit(); c.close()
    audit("UNDO_EXIT",scna,"Çıkış ve buna bağlı giriş/yol mazotu işlemleri geri alındı")
    return {"ok":True}


@app.post("/api/export-import-errors")
async def export_import_errors(request: Request):
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(500,"openpyxl gerekli")

    payload=await request.json()
    rows=payload.get("failed_records",[]) if isinstance(payload,dict) else []

    wb=Workbook()
    ws=wb.active
    ws.title="HATALI KAYITLAR"
    ws.append(["SATIR","SCNA","HATA NEDENİ"])

    for x in rows:
        ws.append([
            x.get("row",""),
            x.get("scna",""),
            x.get("reason","")
        ])

    ws.column_dimensions["A"].width=12
    ws.column_dimensions["B"].width=18
    ws.column_dimensions["C"].width=80

    bio=BytesIO()
    wb.save(bio)
    bio.seek(0)

    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":f'attachment; filename="EXCEL_AKTARIM_HATALARI_{stamp}.xlsx"'}
    )


@app.get("/api/data-quality")
def data_quality():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT
        t.scna,t.plate,d.name driver_name,cu.name customer_name,a.name area_name,
        cc.name cargo_name,t.status,t.trip_date,t.exit_at,t.entry_at,
        t.exit_km,t.entry_km,t.net_kg,t.freight_rate,t.entry_collection,
        CASE WHEN (t.entry_at IS NOT NULL AND t.entry_at<>'' AND t.entry_km<=0) THEN 1 ELSE 0 END entry_date_no_km,
        CASE WHEN (t.exit_km>0 AND (t.exit_at IS NULL OR t.exit_at='')) THEN 1 ELSE 0 END exit_km_no_date,
        CASE WHEN ((t.entry_at IS NOT NULL AND t.entry_at<>'') AND t.entry_done=0) THEN 1 ELSE 0 END entry_date_status_mismatch,
        CASE WHEN (t.freight_rate>0 AND t.net_kg>0 AND COALESCE(t.entry_collection,0)=0) THEN 1 ELSE 0 END collection_missing,
        CASE WHEN t.driver_id IS NULL THEN 1 ELSE 0 END driver_missing,
        CASE WHEN t.customer_id IS NULL THEN 1 ELSE 0 END customer_missing,
        CASE WHEN t.area_id IS NULL THEN 1 ELSE 0 END area_missing,
        CASE WHEN t.cargo_category_id IS NULL THEN 1 ELSE 0 END cargo_missing
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN customers cu ON cu.id=t.customer_id
      LEFT JOIN areas a ON a.id=t.area_id
      LEFT JOIN cargo_categories cc ON cc.id=t.cargo_category_id
      ORDER BY t.id DESC
    """)]
    problems=[]
    counts={k:0 for k in [
      "entry_date_no_km","exit_km_no_date","entry_date_status_mismatch",
      "collection_missing","driver_missing","customer_missing","area_missing","cargo_missing"
    ]}
    for x in rows:
        msgs=[]
        mapping=[
          ("entry_date_no_km","Giriş tarihi var, giriş KM yok"),
          ("exit_km_no_date","Çıkış KM var, çıkış tarihi yok"),
          ("entry_date_status_mismatch","Giriş tarihi var ama kayıt tamamlanmış değil"),
          ("collection_missing","Navlun var, COLLECTION boş/0"),
          ("driver_missing","Şoför boş"),
          ("customer_missing","Müşteri boş"),
          ("area_missing","Bölge boş"),
          ("cargo_missing","Mal cinsi boş"),
        ]
        for key,msg in mapping:
            if x[key]:
                counts[key]+=1
                msgs.append(msg)
        if msgs:
            x["problems"]=msgs
            problems.append(x)
    c.close()
    return {"counts":counts,"total":len(problems),"rows":problems[:2000]}

@app.post("/api/bulk-fix")
def bulk_fix(x: BulkFixIn):
    allowed={"status","customer_id","area_id","cargo_category_id","driver_id","cargo_type","trip_date"}
    if x.field not in allowed:
        raise HTTPException(400,"Bu alan toplu düzeltmeye açık değil.")
    if not x.scnas:
        raise HTTPException(400,"SCNA seçilmedi.")
    c=db()
    done=0
    failed=[]
    for scna in x.scnas:
        try:
            val=x.value
            if x.field in ("customer_id","area_id","cargo_category_id","driver_id"):
                val=int(val) if str(val).strip() else None
            if x.field=="status":
                status=val if val in ("Bekliyor","Yolda","Tamamlandı") else "Bekliyor"
                exit_done=1 if status in ("Yolda","Tamamlandı") else 0
                entry_done=1 if status=="Tamamlandı" else 0
                c.execute("""
                  UPDATE trips SET status=?,exit_done=?,entry_done=?,
                    manual_lock=1,manual_lock_at=DATETIME('now','localtime'),manual_lock_reason='Toplu durum düzeltme',
                    exit_at=CASE WHEN ?=1 THEN COALESCE(exit_at,DATETIME('now','localtime')) ELSE NULL END,
                    entry_at=CASE WHEN ?=1 THEN COALESCE(entry_at,DATETIME('now','localtime')) ELSE NULL END,
                    updated_at=CURRENT_TIMESTAMP
                  WHERE scna=?
                """,(status,exit_done,entry_done,exit_done,entry_done,scna))
            else:
                c.execute(
                    f"UPDATE trips SET {x.field}=?,manual_lock=1,manual_lock_at=DATETIME('now','localtime'),manual_lock_reason='Toplu düzeltme',updated_at=CURRENT_TIMESTAMP WHERE scna=?",
                    (val,scna)
                )
            done+=1
        except Exception as e:
            failed.append({"scna":scna,"reason":str(e)})
    c.commit(); c.close()
    audit("BULK_FIX","TOPLU",f"{x.field} alanı {done} kayıtta güncellendi")
    return {"ok":True,"updated":done,"failed":failed}

@app.post("/api/compare-excel-db")
async def compare_excel_db(request: Request):
    raw=await request.body()
    if not raw:
        raise HTTPException(400,"Excel verisi boş.")
    from openpyxl import load_workbook
    wb=load_workbook(BytesIO(raw),data_only=False,read_only=True)
    sheet=None
    for cand in ("YUKLEME LISTESI","YÜKLEME LİSTESİ","YUKLEME LİSTESİ"):
        if cand in wb.sheetnames:
            sheet=wb[cand]; break
    if sheet is None:
        sheet=wb[wb.sheetnames[0]]

    c=db()
    db_rows={str(r["scna"]).strip().upper():dict(r) for r in c.execute(tq())}
    c.close()

    excel_rows={}
    compare_rows=[]
    def sval(v): return str(v or "").strip()

    for rno,row in enumerate(sheet.iter_rows(min_row=2,values_only=True),start=2):
        if not row: continue
        scna=sval(row[0]).upper() if len(row)>0 else ""
        if not scna or scna=="SCNA": continue
        e={
          "row":rno,"scna":scna,
          "delivery_time":_excel_datetime(row[2] if len(row)>2 else ""),
          "driver":sval(row[6] if len(row)>6 else ""),
          "plate":sval(row[8] if len(row)>8 else "").upper(),
          "kg":_excel_num(row[9] if len(row)>9 else 0),
          "price_k":_excel_num(row[10] if len(row)>10 else 0),
          "freight_rate":_excel_num(row[46] if len(row)>46 else 0),
          "amount":_excel_num(row[47] if len(row)>47 else 0),
          "customer":sval(row[11] if len(row)>11 else ""),
          "cargo":sval(row[12] if len(row)>12 else ""),
          "cargo_type":sval(row[13] if len(row)>13 else "").upper(),
          "area":sval(row[14] if len(row)>14 else ""),
          "exit_km":_excel_num(row[28] if len(row)>28 else 0),
          "entry_km":_excel_num(row[29] if len(row)>29 else 0),
          "collection":_excel_num(row[48] if len(row)>48 else 0),
        }
        excel_rows[scna]=e
        d=db_rows.get(scna)
        if not d:
            compare_rows.append({"scna":scna,"row":rno,"result":"EXCEL_VAR_DB_YOK","differences":["Excel'de var, veritabanında yok"]})
            continue
        diffs=[]
        for label,a,b in [
          ("Plaka",e["plate"],sval(d.get("plate")).upper()),
          ("Şoför",e["driver"],sval(d.get("driver_name"))),
          ("Müşteri",e["customer"],sval(d.get("customer_name"))),
          ("Bölge",e["area"],sval(d.get("area_name"))),
          ("Mal",e["cargo"],sval(d.get("cargo_name"))),
          ("Yük Tipi",e["cargo_type"],sval(d.get("cargo_type_name")).upper())
        ]:
            if a.strip().upper()!=b.strip().upper():
                diffs.append(f"{label}: Excel='{a}' / DB='{b}'")
        for label,a,b in [
          ("KG",e["kg"],float(d.get("net_kg") or 0)),
          ("FREIGHT AU",e["freight_rate"] or (e["amount"]/e["kg"] if e["kg"] else 0),float(d.get("freight_rate") or 0)),
          ("Çıkış KM",e["exit_km"],float(d.get("exit_km") or 0)),
          ("Giriş KM",e["entry_km"],float(d.get("entry_km") or 0)),
          ("COLLECTION",e["collection"],float(d.get("entry_collection") or 0))
        ]:
            if abs(float(a or 0)-float(b or 0))>0.01:
                diffs.append(f"{label}: Excel={a} / DB={b}")
        if bool(e["delivery_time"])!=bool(sval(d.get("entry_at"))):
            diffs.append(f"Giriş tarihi: Excel='{e['delivery_time']}' / DB='{sval(d.get('entry_at'))}'")
        if diffs:
            compare_rows.append({"scna":scna,"row":rno,"result":"FARKLI","differences":diffs})

    for scna in db_rows:
        if scna not in excel_rows:
            compare_rows.append({"scna":scna,"row":"","result":"DB_VAR_EXCEL_YOK","differences":["Veritabanında var, Excel'de yok"]})

    counts={
      "excel_only":sum(x["result"]=="EXCEL_VAR_DB_YOK" for x in compare_rows),
      "db_only":sum(x["result"]=="DB_VAR_EXCEL_YOK" for x in compare_rows),
      "different":sum(x["result"]=="FARKLI" for x in compare_rows)
    }
    return {"sheet":sheet.title,"counts":counts,"total":len(compare_rows),"rows":compare_rows[:3000]}


@app.get("/api/operation-center")
def operation_center():
    c=db()

    # Aktif operasyonlar: rota standardı ve geçmiş gerçek rota ortalamaları birlikte
    rows=[dict(r) for r in c.execute("""
      WITH road AS (
        SELECT scna,SUM(liters) road_liters
        FROM fuel_purchases GROUP BY scna
      ),
      route_hist AS (
        SELECT
          t.area_id,
          COUNT(*) completed_trips,
          AVG(CASE WHEN t.entry_done=1 AND t.entry_km>t.exit_km
                   THEN t.entry_km-t.exit_km END) avg_km,
          AVG(CASE WHEN t.entry_done=1 AND t.exit_at IS NOT NULL AND t.entry_at IS NOT NULL
                   THEN (JULIANDAY(t.entry_at)-JULIANDAY(t.exit_at))*24 END) avg_hours,
          AVG(CASE WHEN t.entry_done=1 AND t.entry_km>t.exit_km AND
                        (t.tank_start_liters+t.exit_official_fuel_liters+
                         t.exit_commercial_fuel_liters+t.exit_baghdad_fuel_liters+
                         COALESCE(r.road_liters,0)-t.tank_end_liters)>0
                   THEN (
                     (t.tank_start_liters+t.exit_official_fuel_liters+
                      t.exit_commercial_fuel_liters+t.exit_baghdad_fuel_liters+
                      COALESCE(r.road_liters,0)-t.tank_end_liters)
                     /(t.entry_km-t.exit_km)
                   )*100 END) avg_l100
        FROM trips t
        LEFT JOIN road r ON r.scna=t.scna
        WHERE t.entry_done=1
        GROUP BY t.area_id
      )
      SELECT
        t.scna,t.plate,t.status,t.exit_at,t.trip_date,t.net_kg,
        d.name driver_name,a.name area_name,
        rs.expected_hours,rs.expected_km,rs.expected_l100,rs.tolerance_percent,
        rh.completed_trips,
        ROUND(rh.avg_km,1) route_avg_km,
        ROUND(rh.avg_hours,1) route_avg_hours,
        ROUND(rh.avg_l100,2) route_avg_l100,
        CASE WHEN t.status='Yolda' AND t.exit_at IS NOT NULL
             THEN ROUND((JULIANDAY('now','localtime')-JULIANDAY(t.exit_at))*24,1)
             ELSE 0 END hours_on_road,
        CASE WHEN t.status='Yolda' AND t.exit_at IS NOT NULL AND
                  COALESCE(NULLIF(rh.avg_hours,0),rs.expected_hours,48)>0 AND
                  (JULIANDAY('now','localtime')-JULIANDAY(t.exit_at))*24 >
                  COALESCE(NULLIF(rh.avg_hours,0),rs.expected_hours,48)
             THEN 1 ELSE 0 END delayed
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN areas a ON a.id=t.area_id
      LEFT JOIN route_standards rs ON rs.area_id=t.area_id
      LEFT JOIN route_hist rh ON rh.area_id=t.area_id
      WHERE t.status IN ('Bekliyor','Yolda')
      ORDER BY delayed DESC,t.exit_at ASC,t.id DESC
      LIMIT 500
    """)]

    summary=dict(c.execute("""
      SELECT
        COUNT(*) total,
        SUM(CASE WHEN status='Yolda' THEN 1 ELSE 0 END) onroad,
        SUM(CASE WHEN status='Bekliyor' THEN 1 ELSE 0 END) waiting,
        SUM(CASE WHEN DATE(exit_at)=DATE('now','localtime') THEN 1 ELSE 0 END) today_exit,
        SUM(CASE WHEN DATE(entry_at)=DATE('now','localtime') THEN 1 ELSE 0 END) today_entry
      FROM trips
    """).fetchone())
    summary["delayed"]=sum(1 for x in rows if x["delayed"])

    c.close()
    return {"summary":summary,"rows":rows}

@app.get("/api/route-learning")
def route_learning():
    c=db()
    rows=[dict(r) for r in c.execute("""
      WITH road AS (
        SELECT scna,SUM(liters) road_liters,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      )
      SELECT
        COALESCE(a.name,'Tanımsız') area_name,
        COUNT(*) trip_count,
        ROUND(AVG(CASE WHEN t.entry_done=1 AND t.entry_km>t.exit_km
                       THEN t.entry_km-t.exit_km END),1) avg_km,
        ROUND(AVG(CASE WHEN t.entry_done=1 AND t.exit_at IS NOT NULL AND t.entry_at IS NOT NULL
                       THEN (JULIANDAY(t.entry_at)-JULIANDAY(t.exit_at))*24 END),1) avg_hours,
        ROUND(AVG(CASE WHEN t.entry_done=1 AND t.entry_km>t.exit_km AND
                            (t.tank_start_liters+t.exit_official_fuel_liters+
                             t.exit_commercial_fuel_liters+t.exit_baghdad_fuel_liters+
                             COALESCE(r.road_liters,0)-t.tank_end_liters)>0
                       THEN (
                         (t.tank_start_liters+t.exit_official_fuel_liters+
                          t.exit_commercial_fuel_liters+t.exit_baghdad_fuel_liters+
                          COALESCE(r.road_liters,0)-t.tank_end_liters)
                         /(t.entry_km-t.exit_km)
                       )*100 END),2) avg_l100,
        ROUND(AVG(
          t.exit_official_fuel_total+t.exit_commercial_fuel_total+t.exit_baghdad_fuel_total+
          COALESCE(r.road_total,0)+t.exit_allowance+t.exit_premium+t.dock_fee+t.port_fee+
          t.sonar+t.exit_other+t.entry_extra_expense_1+t.entry_extra_expense_2+t.entry_extra_expense_3
        ),2) avg_cost
      FROM trips t
      LEFT JOIN areas a ON a.id=t.area_id
      LEFT JOIN road r ON r.scna=t.scna
      WHERE t.entry_done=1
      GROUP BY t.area_id,a.name
      HAVING COUNT(*)>=1
      ORDER BY trip_count DESC,a.name
    """)]
    c.close()
    return rows

@app.get("/api/operation-performance")
def operation_performance():
    c=db()

    vehicles=[dict(r) for r in c.execute("""
      WITH road AS (
        SELECT scna,SUM(liters) road_liters,SUM(total) road_total
        FROM fuel_purchases GROUP BY scna
      )
      SELECT
        t.plate name,
        COUNT(*) trip_count,
        ROUND(SUM(CASE WHEN t.entry_done=1 THEN MAX(t.entry_km-t.exit_km,0) ELSE 0 END),1) total_km,
        ROUND(AVG(CASE WHEN t.entry_done=1 AND t.entry_km>t.exit_km AND
                            (t.tank_start_liters+t.exit_official_fuel_liters+
                             t.exit_commercial_fuel_liters+t.exit_baghdad_fuel_liters+
                             COALESCE(r.road_liters,0)-t.tank_end_liters)>0
                       THEN ((t.tank_start_liters+t.exit_official_fuel_liters+
                              t.exit_commercial_fuel_liters+t.exit_baghdad_fuel_liters+
                              COALESCE(r.road_liters,0)-t.tank_end_liters)
                             /(t.entry_km-t.exit_km))*100 END),2) avg_l100,
        ROUND(AVG(CASE WHEN t.entry_done=1 AND t.exit_at IS NOT NULL AND t.entry_at IS NOT NULL
                       THEN (JULIANDAY(t.entry_at)-JULIANDAY(t.exit_at))*24 END),1) avg_hours
      FROM trips t
      LEFT JOIN road r ON r.scna=t.scna
      GROUP BY t.plate
      ORDER BY trip_count DESC
      LIMIT 30
    """)]

    drivers=[dict(r) for r in c.execute("""
      WITH road AS (
        SELECT scna,SUM(liters) road_liters
        FROM fuel_purchases GROUP BY scna
      )
      SELECT
        COALESCE(d.name,'Tanımsız') name,
        COUNT(*) trip_count,
        ROUND(SUM(CASE WHEN t.entry_done=1 THEN MAX(t.entry_km-t.exit_km,0) ELSE 0 END),1) total_km,
        ROUND(AVG(CASE WHEN t.entry_done=1 AND t.entry_km>t.exit_km AND
                            (t.tank_start_liters+t.exit_official_fuel_liters+
                             t.exit_commercial_fuel_liters+t.exit_baghdad_fuel_liters+
                             COALESCE(r.road_liters,0)-t.tank_end_liters)>0
                       THEN ((t.tank_start_liters+t.exit_official_fuel_liters+
                              t.exit_commercial_fuel_liters+t.exit_baghdad_fuel_liters+
                              COALESCE(r.road_liters,0)-t.tank_end_liters)
                             /(t.entry_km-t.exit_km))*100 END),2) avg_l100,
        ROUND(AVG(CASE WHEN t.entry_done=1 AND t.exit_at IS NOT NULL AND t.entry_at IS NOT NULL
                       THEN (JULIANDAY(t.entry_at)-JULIANDAY(t.exit_at))*24 END),1) avg_hours
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN road r ON r.scna=t.scna
      GROUP BY t.driver_id,d.name
      ORDER BY trip_count DESC
      LIMIT 30
    """)]

    c.close()
    return {"vehicles":vehicles,"drivers":drivers}


@app.post("/api/repair-remain-from-excel")
async def repair_remain_from_excel(request: Request):
    raw=await request.body()
    if not raw:
        raise HTTPException(400,"Excel verisi boş.")

    try:
        from openpyxl import load_workbook
    except ImportError:
        raise HTTPException(500,"openpyxl gerekli")

    wb=load_workbook(BytesIO(raw),data_only=True,read_only=True)

    ws=None
    for name in wb.sheetnames:
        if _norm_header(name) in ("YUKLEMELISTESI","YUKLEMELIST","LOADINGLIST"):
            ws=wb[name]
            break
    if ws is None:
        ws=wb[wb.sheetnames[0]]

    row_iter=ws.iter_rows(values_only=True)
    header_row=None
    header_map={}

    for rno,vals in enumerate(row_iter,start=1):
        vals=tuple(vals)
        hm={_norm_header(v):i for i,v in enumerate(vals) if v is not None}
        if "SCNA" in hm or ("PLATE" in hm and ("DRIVER" in hm or "DRIVERNAME" in hm)):
            header_row=rno
            header_map=hm
            break
        if rno>=30:
            break

    if not header_row:
        raise HTTPException(400,"Başlık satırı bulunamadı.")

    scna_col=header_map.get("SCNA")
    if scna_col is None:
        scna_col=header_map.get("SNCA",0)

    remain_col=None
    for candidate in ("REMAIN","KALAN","BALANCE","REMAINING","REMAINDER"):
        key=_norm_header(candidate)
        if key in header_map:
            remain_col=header_map[key]
            break

    # Başlık gerçekten bulunmadıysa eski format fallback.
    if remain_col is None:
        remain_col=49

    c=db()
    updated=0
    blank=0
    db_not_found=0
    parsed=0
    samples=[]

    for rno,row in enumerate(row_iter,start=header_row+1):
        row=tuple(row)
        if scna_col>=len(row):
            continue

        scna=str(row[scna_col] or "").strip().upper()
        if not scna:
            continue

        raw_remain=row[remain_col] if remain_col<len(row) else None
        remain=_excel_optional_num(raw_remain)

        if remain is None:
            blank+=1
            continue

        parsed+=1
        cur=c.execute(
            "UPDATE trips SET excel_remain=?,updated_at=CURRENT_TIMESTAMP WHERE UPPER(scna)=UPPER(?)",
            (remain,scna)
        )
        if cur.rowcount:
            updated+=1
            if len(samples)<25:
                samples.append({"scna":scna,"remain":remain,"row":rno})
        else:
            db_not_found+=1

    c.commit()
    c.close()

    audit("REMAIN_REPAIR","EXCEL",f"{updated} kayıt REMAIN ile güncellendi")

    return {
        "ok":True,
        "sheet":ws.title,
        "header_row":header_row,
        "remain_header_found": any(_norm_header(x) in header_map for x in ("REMAIN","KALAN","BALANCE","REMAINING","REMAINDER")),
        "remain_column_index":remain_col+1,
        "parsed":parsed,
        "updated":updated,
        "blank":blank,
        "db_not_found":db_not_found,
        "samples":samples
    }


@app.get("/api/cash-diagnostic/{scna}")
def cash_diagnostic(scna: str):
    c=db()
    row=c.execute("""
      SELECT
        t.scna,t.plate,t.entry_done,t.freight_basis,t.net_kg,t.freight_rate,
        t.entry_collection,t.entry_cash_handed,t.excel_price_k,t.excel_freight_au,t.excel_amount,t.excel_remain raw_excel_remain,
        CASE WHEN t.freight_basis='KG'
             THEN t.net_kg*t.freight_rate
             ELSE (t.net_kg/1000.0)*t.freight_rate END freight_total,
        CASE
          WHEN t.excel_remain IS NOT NULL THEN
            CASE WHEN COALESCE(t.entry_collection,0)>0
                 THEN t.entry_collection -
                   (CASE WHEN t.freight_basis='KG'
                         THEN t.net_kg*t.freight_rate
                         ELSE (t.net_kg/1000.0)*t.freight_rate END)
                 ELSE 0 END
          WHEN COALESCE(t.entry_cash_handed,0)=0 AND COALESCE(t.entry_collection,0)>0 AND t.entry_done=1
          THEN t.entry_collection -
            (CASE WHEN t.freight_basis='KG'
                  THEN t.net_kg*t.freight_rate
                  ELSE (t.net_kg/1000.0)*t.freight_rate END)
          ELSE t.entry_cash_handed -
            (t.entry_collection -
              (COALESCE((SELECT SUM(total) FROM fuel_purchases f WHERE f.scna=t.scna),0)+
               t.entry_extra_expense_1+t.entry_extra_expense_2+t.entry_extra_expense_3))
        END final_driver_cash_diff,
        CASE
          WHEN t.excel_remain IS NOT NULL THEN 'EXCEL COLLECTION-AMOUNT'
          WHEN COALESCE(t.entry_cash_handed,0)=0 AND COALESCE(t.entry_collection,0)>0 AND t.entry_done=1
          THEN 'ESKİ EXCEL HESABI'
          ELSE 'PROGRAM HESABI'
        END calculation_source
      FROM trips t
      WHERE UPPER(t.scna)=UPPER(?)
      LIMIT 1
    """,(scna,)).fetchone()
    c.close()
    if not row:
        raise HTTPException(404,"SCNA bulunamadı")
    return dict(row)


@app.post("/api/repair-freight-from-excel")
async def repair_freight_from_excel(request: Request):
    raw=await request.body()
    if not raw:
        raise HTTPException(400,"Excel verisi boş.")

    from openpyxl import load_workbook
    wb=load_workbook(BytesIO(raw),data_only=True,read_only=True)

    ws=None
    for name in wb.sheetnames:
        if _norm_header(name) in ("YUKLEMELISTESI","YUKLEMELIST","LOADINGLIST"):
            ws=wb[name]
            break
    if ws is None:
        ws=wb[wb.sheetnames[0]]

    it=ws.iter_rows(values_only=True)
    header_row=0
    scna_col=0

    for rno,row in enumerate(it,start=1):
        hm={_norm_header(v):i for i,v in enumerate(row) if v is not None}
        if "SCNA" in hm:
            header_row=rno
            scna_col=hm["SCNA"]
            break
        if rno>=30:
            break

    if not header_row:
        raise HTTPException(400,"SCNA başlığı bulunamadı.")

    c=db()
    updated=0
    unchanged=0
    missing=0
    db_not_found=0
    samples=[]

    for rno,row in enumerate(it,start=header_row+1):
        row=tuple(row)
        if scna_col>=len(row):
            continue
        scna=str(row[scna_col] or "").strip().upper()
        if not scna:
            continue

        kg=_excel_num(row[9] if len(row)>9 else 0)
        freight_au=_excel_num(row[46] if len(row)>46 else 0)
        amount=_excel_num(row[47] if len(row)>47 else 0)

        rate=freight_au or (amount/kg if amount and kg else 0)
        if not rate:
            missing+=1
            continue

        oldrow=c.execute("SELECT freight_rate FROM trips WHERE UPPER(scna)=UPPER(?)",(scna,)).fetchone()
        if not oldrow:
            db_not_found+=1
            continue

        old_rate=float(oldrow["freight_rate"] or 0)
        if abs(old_rate-rate)<=0.000001:
            unchanged+=1
            continue

        c.execute(
            "UPDATE trips SET freight_rate=?,freight_basis='KG',updated_at=CURRENT_TIMESTAMP WHERE UPPER(scna)=UPPER(?)",
            (rate,scna)
        )
        updated+=1

        if len(samples)<25:
            samples.append({
                "scna":scna,
                "old_rate":old_rate,
                "new_rate":rate,
                "amount":amount
            })

    c.commit(); c.close()
    audit("FREIGHT_REPAIR","EXCEL",f"{updated} kayıt AU/FREIGHT ile güncellendi")

    return {
        "ok":True,"sheet":ws.title,"updated":updated,"unchanged":unchanged,
        "missing":missing,"db_not_found":db_not_found,"samples":samples
    }


@app.post("/api/check-entry-dates-from-excel")
async def check_entry_dates_from_excel(request: Request):
    raw=await request.body()
    if not raw:
        raise HTTPException(400,"Excel verisi boş.")

    from openpyxl import load_workbook
    wb=load_workbook(BytesIO(raw),data_only=True,read_only=True)

    ws=None
    for name in wb.sheetnames:
        if _norm_header(name) in ("YUKLEMELISTESI","YUKLEMELIST","LOADINGLIST"):
            ws=wb[name]
            break
    if ws is None:
        ws=wb[wb.sheetnames[0]]

    it=ws.iter_rows(values_only=True)
    header_row=0
    scna_col=0
    for rno,row in enumerate(it,start=1):
        hm={_norm_header(v):i for i,v in enumerate(row) if v is not None}
        if "SCNA" in hm:
            header_row=rno
            scna_col=hm["SCNA"]
            break
        if rno>=30:
            break
    if not header_row:
        raise HTTPException(400,"SCNA başlığı bulunamadı.")

    c=db()
    excel_with_date=0
    matched=0
    missing_in_db=[]
    date_mismatch=[]

    for rno,row in enumerate(it,start=header_row+1):
        row=tuple(row)
        if scna_col>=len(row):
            continue
        raw_scna=row[scna_col]
        if raw_scna is None:
            continue
        scna=str(raw_scna).strip().upper()
        if scna in ("", ".", "-", "—", "NAN", "NONE", "NULL"):
            continue
        if scna.endswith(".0"):
            try:
                scna=str(int(float(scna)))
            except:
                pass
        excel_date=_excel_datetime(row[2] if len(row)>2 else "")
        if not excel_date:
            continue

        excel_with_date+=1
        dbrow=c.execute(
            "SELECT entry_at,delivery_time,status,manual_lock FROM trips WHERE UPPER(scna)=UPPER(?)",
            (scna,)
        ).fetchone()

        if not dbrow:
            if len(missing_in_db)<200:
                missing_in_db.append({"row":rno,"scna":scna,"excel_date":excel_date})
            continue

        dbdate=dbrow["entry_at"] or dbrow["delivery_time"] or ""
        if not dbdate:
            if len(date_mismatch)<500:
                date_mismatch.append({
                    "row":rno,"scna":scna,"excel_date":excel_date,
                    "db_date":"","status":dbrow["status"],
                    "manual_lock":int(dbrow["manual_lock"] or 0)
                })
        else:
            matched+=1

    c.close()
    return {
        "ok":True,
        "excel_with_entry_date":excel_with_date,
        "db_with_entry_date":matched,
        "missing_date_count":len(date_mismatch),
        "missing_db_count":len(missing_in_db),
        "missing_dates":date_mismatch[:200],
        "missing_db":missing_in_db[:100]
    }


@app.post("/api/repair-entry-dates-from-excel")
async def repair_entry_dates_from_excel(request: Request):
    raw=await request.body()
    if not raw:
        raise HTTPException(400,"Excel verisi boş.")

    from openpyxl import load_workbook
    wb=load_workbook(BytesIO(raw),data_only=True,read_only=True)

    ws=None
    for name in wb.sheetnames:
        if _norm_header(name) in ("YUKLEMELISTESI","YUKLEMELIST","LOADINGLIST"):
            ws=wb[name]
            break
    if ws is None:
        ws=wb[wb.sheetnames[0]]

    it=ws.iter_rows(values_only=True)
    header_row=0
    scna_col=0

    for rno,row in enumerate(it,start=1):
        hm={_norm_header(v):i for i,v in enumerate(row) if v is not None}
        if "SCNA" in hm:
            header_row=rno
            scna_col=hm["SCNA"]
            break
        if rno>=30:
            break

    if not header_row:
        raise HTTPException(400,"SCNA başlığı bulunamadı.")

    c=db()
    excel_dates=0
    already_ok=0
    repaired=0
    db_missing=0
    no_date=0
    repaired_rows=[]

    for rno,row in enumerate(it,start=header_row+1):
        row=tuple(row)
        if scna_col>=len(row):
            continue

        raw_scna=row[scna_col]
        if raw_scna is None:
            continue
        scna=str(raw_scna).strip().upper()
        if scna in ("", ".", "-", "—", "NAN", "NONE", "NULL"):
            continue
        if scna.endswith(".0"):
            try:
                scna=str(int(float(scna)))
            except:
                pass

        delivery=_excel_datetime(row[2] if len(row)>2 else "")
        if not delivery:
            no_date+=1
            continue

        excel_dates+=1
        entry_km=_excel_num(row[29] if len(row)>29 else 0)

        dbrow=c.execute("""
          SELECT id,entry_at,delivery_time,entry_km,status,manual_lock
          FROM trips
          WHERE UPPER(scna)=UPPER(?)
          LIMIT 1
        """,(scna,)).fetchone()

        if not dbrow:
            db_missing+=1
            continue

        current_date=(dbrow["entry_at"] or dbrow["delivery_time"] or "").strip()

        if current_date:
            already_ok+=1
            continue

        # Sadece eksik giriş bilgilerini doldur.
        # Plaka, şoför, müşteri, para, navlun, mazot vb. hiçbir alana dokunmaz.
        c.execute("""
          UPDATE trips SET
            delivery_time=?,
            entry_at=?,
            entry_km=CASE
              WHEN COALESCE(entry_km,0)<=0 AND ?>0 THEN ?
              ELSE entry_km
            END,
            entry_done=1,
            exit_done=1,
            status='Tamamlandı',
            updated_at=CURRENT_TIMESTAMP
          WHERE id=?
        """,(delivery,delivery,entry_km,entry_km,dbrow["id"]))

        repaired+=1
        if len(repaired_rows)<300:
            repaired_rows.append({
                "row":rno,
                "scna":scna,
                "entry_date":delivery,
                "entry_km":entry_km,
                "was_manual_lock":int(dbrow["manual_lock"] or 0)
            })

    c.commit()

    # Repair sonrası ikinci doğrulama.
    verify_missing=[]
    verify_it=ws.iter_rows(values_only=True)
    for _ in range(header_row):
        try:
            next(verify_it)
        except StopIteration:
            break

    for rno,row in enumerate(verify_it,start=header_row+1):
        row=tuple(row)
        if scna_col>=len(row):
            continue
        raw_scna=row[scna_col]
        if raw_scna is None:
            continue
        scna=str(raw_scna).strip().upper()
        if scna in ("", ".", "-", "—", "NAN", "NONE", "NULL"):
            continue
        if scna.endswith(".0"):
            try:
                scna=str(int(float(scna)))
            except:
                pass
        if not scna:
            continue
        delivery=_excel_datetime(row[2] if len(row)>2 else "")
        if not delivery:
            continue

        chk=c.execute("""
          SELECT entry_at,delivery_time
          FROM trips
          WHERE UPPER(scna)=UPPER(?)
          LIMIT 1
        """,(scna,)).fetchone()

        if chk and not (chk["entry_at"] or chk["delivery_time"]):
            if len(verify_missing)<300:
                verify_missing.append({
                    "row":rno,
                    "scna":scna,
                    "excel_date":delivery
                })

    c.close()
    audit("ENTRY_DATE_REPAIR","EXCEL",f"{repaired} eksik giriş tarihi onarıldı")

    return {
        "ok":True,
        "sheet":ws.title,
        "excel_dates":excel_dates,
        "already_ok":already_ok,
        "repaired":repaired,
        "db_missing":db_missing,
        "no_date":no_date,
        "verify_missing_count":len(verify_missing),
        "verify_missing":verify_missing,
        "repaired_rows":repaired_rows
    }


def _looks_like_excel_bytes(content: bytes, content_type: str=""):
    if not content:
        return False
    # xlsx/xlsm are ZIP containers and normally begin PK.
    if content[:2] == b"PK":
        return True
    ct=(content_type or "").lower()
    return (
        "spreadsheetml" in ct or
        "application/vnd.ms-excel" in ct or
        "application/octet-stream" in ct
    ) and not content.lstrip().lower().startswith(b"<!doctype html")

def _extract_onedrive_download_candidates(text: str):
    if not text:
        return []
    decoded=html_lib.unescape(text)

    # JSON escaped URLs
    decoded=decoded.replace("\\u0026","&").replace("\\/","/")

    patterns=[
        r'https://[^"\']+(?:download|Download)[^"\']*',
        r'https://[^"\']+/_layouts/15/download\.aspx[^"\']*',
        r'https://[^"\']+\.files\.1drv\.com/[^"\']+',
        r'https://[^"\']+\.sharepoint\.com/[^"\']+(?:download|Download)[^"\']*',
    ]

    out=[]
    seen=set()
    for p in patterns:
        for m in re.findall(p,decoded,re.I):
            u=m.rstrip("\\")
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out[:20]

def _public_onedrive_download(share_url: str):
    share_url=(share_url or "").strip()
    if not share_url.startswith(("https://1drv.ms/","https://onedrive.live.com/")):
        raise HTTPException(400,"Geçerli bir OneDrive paylaşım linki gir.")

    session=requests.Session()
    session.headers.update({
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36",
        "Accept":"*/*"
    })

    attempts=[]

    # Microsoft sometimes honors download=1 directly on sharing links.
    variants=[]
    sep="&" if "?" in share_url else "?"
    variants.append(share_url + sep + "download=1")
    variants.append(share_url)

    for url in variants:
        try:
            r=session.get(url,allow_redirects=True,timeout=45)
            attempts.append({
                "url":url,
                "status":r.status_code,
                "final_url":r.url,
                "content_type":r.headers.get("content-type",""),
                "size":len(r.content)
            })

            if r.ok and _looks_like_excel_bytes(r.content,r.headers.get("content-type","")):
                return r.content,{
                    "method":"DIRECT_SHARE_LINK",
                    "final_url":r.url,
                    "attempts":attempts
                }

            # If Microsoft returns a viewer HTML page, inspect it for actual download URLs.
            ct=(r.headers.get("content-type") or "").lower()
            if r.ok and ("text/html" in ct or r.content.lstrip().lower().startswith(b"<!doctype html")):
                text=r.text
                candidates=_extract_onedrive_download_candidates(text)

                # Also look through redirection history URLs.
                for h in list(r.history)+[r]:
                    if h.url and ("download" in h.url.lower() or "files.1drv.com" in h.url.lower()):
                        candidates.insert(0,h.url)

                seen=set()
                for candidate in candidates:
                    if candidate in seen:
                        continue
                    seen.add(candidate)
                    try:
                        dr=session.get(candidate,allow_redirects=True,timeout=60)
                        attempts.append({
                            "url":"HTML_CANDIDATE",
                            "status":dr.status_code,
                            "final_url":dr.url,
                            "content_type":dr.headers.get("content-type",""),
                            "size":len(dr.content)
                        })
                        if dr.ok and _looks_like_excel_bytes(dr.content,dr.headers.get("content-type","")):
                            return dr.content,{
                                "method":"HTML_DOWNLOAD_URL",
                                "final_url":dr.url,
                                "attempts":attempts
                            }
                    except Exception as e:
                        attempts.append({"url":"HTML_CANDIDATE","error":str(e)[:200]})

        except Exception as e:
            attempts.append({"url":url,"error":str(e)[:300]})

    raise HTTPException(
        400,
        {
            "message":"OneDrive paylaşım linkinden Excel dosyası doğrudan indirilemedi.",
            "hint":"Dosyanın paylaşım ayarında 'Bağlantıya sahip herkes görüntüleyebilir' açık olmalı. Microsoft bazı kişisel OneDrive bağlantılarında anonim doğrudan indirmeyi engelleyebilir.",
            "attempts":attempts[-10:]
        }
    )

@app.post("/api/public-onedrive/preview")
def public_onedrive_preview(payload: dict):
    share_url=str(payload.get("share_url") or "").strip()
    content,info=_public_onedrive_download(share_url)

    # Excel'i gerçekten açarak doğrula.
    try:
        from openpyxl import load_workbook
        wb=load_workbook(BytesIO(content),data_only=True,read_only=True)
        sheets=wb.sheetnames
        sheet=None
        for name in sheets:
            if _norm_header(name) in ("YUKLEMELISTESI","YUKLEMELIST","LOADINGLIST"):
                sheet=name
                break
        if sheet is None:
            sheet=sheets[0] if sheets else ""
    except Exception as e:
        raise HTTPException(400,f"Bağlantıdan veri geldi ama geçerli Excel olarak açılamadı: {e}")

    return {
        "ok":True,
        "size":len(content),
        "sheet":sheet,
        "sheets":sheets,
        "method":info.get("method"),
        "final_url":info.get("final_url"),
        "attempts":info.get("attempts",[])
    }

@app.post("/api/public-onedrive/file")
def public_onedrive_file(payload: dict):
    share_url=str(payload.get("share_url") or "").strip()
    content,info=_public_onedrive_download(share_url)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition":'attachment; filename="WEB_EXCEL.xlsx"',
            "X-OneDrive-Method":str(info.get("method") or "")
        }
    )



@app.get("/api/fleet/vehicles")
def fleet_vehicles():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT fv.*,
        (
          SELECT d.name FROM trips t
          LEFT JOIN drivers d ON d.id=t.driver_id
          WHERE UPPER(TRIM(t.plate))=UPPER(TRIM(fv.plate))
          ORDER BY t.id DESC LIMIT 1
        ) current_driver
      FROM fleet_vehicles fv
      ORDER BY fv.is_active DESC,fv.plate
    """)]
    c.close()
    return {
      "total":len(rows),
      "active":sum(1 for x in rows if x["is_active"]),
      "passive":sum(1 for x in rows if not x["is_active"]),
      "rows":rows
    }

@app.post("/api/fleet/vehicles")
def save_fleet_vehicle(x: FleetVehicleIn):
    plate=x.plate.strip().upper()
    if not plate: raise HTTPException(400,"Plaka gerekli.")
    c=db()
    c.execute("""
      INSERT INTO fleet_vehicles(plate,brand,model,vehicle_type,is_active,garage_state,note,updated_at)
      VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
      ON CONFLICT(plate) DO UPDATE SET
        brand=excluded.brand,model=excluded.model,vehicle_type=excluded.vehicle_type,
        is_active=excluded.is_active,garage_state=excluded.garage_state,note=excluded.note,
        updated_at=CURRENT_TIMESTAMP
    """,(plate,x.brand.strip(),x.model.strip(),x.vehicle_type.strip().upper(),
         1 if x.is_active else 0,x.garage_state.strip().upper(),x.note.strip()))
    c.commit();c.close()
    audit("FLEET_VEHICLE",plate,"Araç kaydı güncellendi")
    return {"ok":True}

@app.patch("/api/fleet/vehicles/{plate}/active")
def set_fleet_vehicle_active(plate: str, x: dict):
    active=1 if x.get("is_active") else 0
    c=db()
    c.execute("UPDATE fleet_vehicles SET is_active=?,updated_at=CURRENT_TIMESTAMP WHERE UPPER(plate)=UPPER(?)",(active,plate))
    c.commit();c.close()
    audit("FLEET_VEHICLE_ACTIVE",plate,f"Aktif={active}")
    return {"ok":True}

@app.get("/api/fleet/drivers")
def fleet_drivers():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT fd.*,
        (
          SELECT t.plate FROM trips t
          LEFT JOIN drivers d ON d.id=t.driver_id
          WHERE UPPER(TRIM(d.name))=UPPER(TRIM(fd.name))
          ORDER BY t.id DESC LIMIT 1
        ) last_plate
      FROM fleet_drivers fd
      ORDER BY fd.is_active DESC,fd.name
    """)]
    c.close()
    return {
      "total":len(rows),
      "active":sum(1 for x in rows if x["is_active"]),
      "passive":sum(1 for x in rows if not x["is_active"]),
      "rows":rows
    }

@app.post("/api/fleet/drivers")
def save_fleet_driver(x: FleetDriverIn):
    name=x.name.strip()
    if not name: raise HTTPException(400,"Şoför adı gerekli.")
    c=db()
    row=c.execute("SELECT id FROM fleet_drivers WHERE UPPER(TRIM(name))=UPPER(TRIM(?))",(name,)).fetchone()
    if row:
        c.execute("""UPDATE fleet_drivers SET phone=?,d_no=?,is_active=?,note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (x.phone.strip(),x.d_no.strip(),1 if x.is_active else 0,x.note.strip(),row["id"]))
    else:
        c.execute("""INSERT INTO fleet_drivers(name,phone,d_no,is_active,note) VALUES(?,?,?,?,?)""",
                  (name,x.phone.strip(),x.d_no.strip(),1 if x.is_active else 0,x.note.strip()))
    c.commit();c.close()
    audit("FLEET_DRIVER",name,"Şoför kaydı güncellendi")
    return {"ok":True}

@app.patch("/api/fleet/drivers/{driver_id}/active")
def set_fleet_driver_active(driver_id: int, x: dict):
    active=1 if x.get("is_active") else 0
    c=db();c.execute("UPDATE fleet_drivers SET is_active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(active,driver_id))
    c.commit();c.close()
    return {"ok":True}

@app.get("/api/fleet-operations")
def fleet_operations():
    c=db()
    rows=[dict(r) for r in c.execute("""
      WITH plates AS (
        SELECT UPPER(TRIM(plate)) plate FROM fleet_vehicles WHERE is_active=1
      ),
      last_trip AS (
        SELECT t.* FROM trips t JOIN (
          SELECT UPPER(TRIM(plate)) plate,MAX(id) max_id FROM trips
          WHERE TRIM(COALESCE(plate,''))<>'' GROUP BY UPPER(TRIM(plate))
        ) z ON z.max_id=t.id
      )
      SELECT p.plate,
        COALESCE(v.load_state,CASE WHEN COALESCE(NULLIF(lt.entry_at,''),NULLIF(lt.delivery_time,'')) IS NULL AND lt.exit_done=1 THEN 'DOLU' ELSE 'BOS' END) load_state,
        COALESCE(v.queue_no,0) queue_no,COALESCE(v.vessel,'') vessel,COALESCE(v.operation_note,'') operation_note,
        lt.scna,COALESCE(d.name,'') driver,COALESCE(a.name,'') area,lt.exit_at,
        COALESCE(NULLIF(lt.entry_at,''),NULLIF(lt.delivery_time,'')) entry_at
      FROM plates p
      LEFT JOIN last_trip lt ON UPPER(TRIM(lt.plate))=p.plate
      LEFT JOIN drivers d ON d.id=lt.driver_id LEFT JOIN areas a ON a.id=lt.area_id
      LEFT JOIN vehicle_operations v ON UPPER(TRIM(v.plate))=p.plate
      ORDER BY CASE COALESCE(v.load_state,'') WHEN 'SIRA' THEN 1 WHEN 'YUKLEMEDE' THEN 2 WHEN 'DOLU' THEN 3 WHEN 'BOS' THEN 4 ELSE 5 END,
        CASE WHEN COALESCE(v.queue_no,0)>0 THEN v.queue_no ELSE 999999 END,p.plate
    """)]
    c.close()
    counts={"TOPLAM":len(rows),"BOS":0,"DOLU":0,"SIRA":0,"YUKLEMEDE":0}
    for x in rows:
        s=x.get("load_state") or "BOS";counts[s]=counts.get(s,0)+1
    return {"counts":counts,"rows":rows}

@app.post("/api/fleet-operations")
def save_fleet_operation(x: VehicleOperationIn):
    plate=x.plate.strip().upper();state=x.load_state.strip().upper()
    if not plate: raise HTTPException(400,"Plaka gerekli.")
    if state not in ("BOS","DOLU","SIRA","YUKLEMEDE","CALISIYOR","CIKTI"): raise HTTPException(400,"Geçersiz durum.")
    q=max(int(x.queue_no or 0),0)
    if state!="SIRA":q=0
    c=db();c.execute("""INSERT INTO vehicle_operations(plate,load_state,queue_no,vessel,operation_note,updated_at)
      VALUES(?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(plate) DO UPDATE SET
      load_state=excluded.load_state,queue_no=excluded.queue_no,vessel=excluded.vessel,
      operation_note=excluded.operation_note,updated_at=CURRENT_TIMESTAMP""",
      (plate,state,q,x.vessel.strip(),x.operation_note.strip()))
    c.commit();c.close();audit("FLEET_OPERATION",plate,f"{state} / sıra {q} / gemi {x.vessel.strip()}")
    return {"ok":True}

@app.post("/api/fleet-operations/resequence")
def resequence_fleet_operations():
    c=db();rows=c.execute("""SELECT plate FROM vehicle_operations WHERE load_state='SIRA'
      ORDER BY CASE WHEN queue_no>0 THEN queue_no ELSE 999999 END,updated_at,plate""").fetchall()
    for i,r in enumerate(rows,1):c.execute("UPDATE vehicle_operations SET queue_no=? WHERE plate=?",(i,r["plate"]))
    c.commit();c.close();return {"ok":True,"count":len(rows)}


@app.get("/api/health")
def health():
    return {"ok": True, "service": "SAMA TRACK"}


@app.get("/api/integrated-fleet-status")
def integrated_fleet_status():
    c=db()
    rows=[dict(r) for r in c.execute("""
      WITH active_fleet AS (
        SELECT UPPER(TRIM(plate)) plate,brand,model,vehicle_type,garage_state,note
        FROM fleet_vehicles
        WHERE is_active=1
      ),
      latest_trip AS (
        SELECT t.*
        FROM trips t
        JOIN (
          SELECT UPPER(TRIM(plate)) plate,MAX(id) max_id
          FROM trips
          WHERE TRIM(COALESCE(plate,''))<>''
          GROUP BY UPPER(TRIM(plate))
        ) z ON z.max_id=t.id
      )
      SELECT
        f.plate,f.brand,f.model,f.vehicle_type,f.garage_state,f.note fleet_note,
        lt.scna,
        COALESCE(d.name,'') driver,
        COALESCE(a.name,'') area,
        lt.status trip_status,
        lt.exit_done,lt.entry_done,lt.exit_at,
        COALESCE(NULLIF(lt.entry_at,''),NULLIF(lt.delivery_time,'')) entry_at,
        COALESCE(vo.vessel,'') vessel,
        COALESCE(vo.load_state,'') vessel_state,
        COALESCE(vo.operation_note,'') operation_note,
        CASE
          WHEN UPPER(COALESCE(f.garage_state,''))='BAKIM' THEN 'BAKIM'
          WHEN COALESCE(vo.load_state,'')='CALISIYOR' AND TRIM(COALESCE(vo.vessel,''))<>'' THEN 'GEMIDE'
          WHEN lt.exit_done=1 AND COALESCE(NULLIF(lt.entry_at,''),NULLIF(lt.delivery_time,'')) IS NULL THEN 'YOLDA'
          WHEN COALESCE(lt.status,'')='Bekliyor' THEN 'BEKLEMEDE'
          ELSE 'BOSTA'
        END operation_state
      FROM active_fleet f
      LEFT JOIN latest_trip lt ON UPPER(TRIM(lt.plate))=f.plate
      LEFT JOIN drivers d ON d.id=lt.driver_id
      LEFT JOIN areas a ON a.id=lt.area_id
      LEFT JOIN vehicle_operations vo ON UPPER(TRIM(vo.plate))=f.plate
      ORDER BY f.plate
    """)]
    c.close()
    counts={"TOPLAM":len(rows),"GEMIDE":0,"BAKIM":0,"YOLDA":0,"BEKLEMEDE":0,"BOSTA":0}
    for x in rows:
        s=x.get("operation_state") or "BOSTA"
        counts[s]=counts.get(s,0)+1
    return {"counts":counts,"rows":rows}

@app.get("/api/lookups")
def lookups():
    c = db()
    vehicles = [dict(r) for r in c.execute("""
      SELECT
        v.*,
        lt.driver_id current_driver_id,
        d.name driver_name,
        d.phone,
        d.d_no
      FROM vehicles v
      LEFT JOIN trips lt ON lt.id=(
        SELECT t2.id
        FROM trips t2
        WHERE UPPER(t2.plate)=UPPER(v.plate)
        ORDER BY
          CASE WHEN t2.status='Yolda' THEN 0 ELSE 1 END,
          t2.id DESC
        LIMIT 1
      )
      LEFT JOIN drivers d ON d.id=lt.driver_id
      WHERE v.active=1
      ORDER BY v.plate
    """)]
    areas = [dict(r) for r in c.execute(
        "SELECT * FROM areas WHERE active=1 ORDER BY name"
    )]
    cargo_categories = [dict(r) for r in c.execute(
        "SELECT * FROM cargo_categories WHERE active=1 ORDER BY name"
    )]
    customers = [dict(r) for r in c.execute(
        "SELECT * FROM customers WHERE active=1 ORDER BY name"
    )]
    c.close()
    return {
        "vehicles": vehicles,
        "areas": areas,
        "cargo_categories": cargo_categories,
        "customers": customers
    }

@app.get("/api/trips")
def trips(q: str = "", status: str = "", customer: str = "", area: str = "", cargo: str = "", limit: int = 50, offset: int = 0):
    # Binlerce kaydı tarayıcıya tek seferde göndermiyoruz.
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    c = db()
    sql = tq() + " WHERE 1=1 "
    p = []
    if q:
        like = f"%{q}%"
        sql += " AND (t.scna LIKE ? OR t.plate LIKE ? OR d.name LIKE ? OR a.name LIKE ? OR cu.name LIKE ? OR cc.name LIKE ?)"
        p += [like, like, like, like, like, like]
    if status and status != "Tümü":
        sql += " AND t.status=?"
        p.append(status)
    if customer:
        sql += " AND cu.name=?"
        p.append(customer)
    if area:
        sql += " AND a.name=?"
        p.append(area)
    if cargo:
        sql += " AND cc.name=?"
        p.append(cargo)
    sql += " ORDER BY t.id DESC LIMIT ? OFFSET ?"
    p += [limit, offset]
    rows = [dict(r) for r in c.execute(sql, p)]
    c.close()
    return rows

@app.get("/api/trips-count")
def trips_count(q: str = "", status: str = "", customer: str = "", area: str = "", cargo: str = ""):
    c = db()
    sql = """SELECT COUNT(*) c FROM trips t
             LEFT JOIN drivers d ON d.id=t.driver_id
             LEFT JOIN areas a ON a.id=t.area_id
             LEFT JOIN cargo_categories cc ON cc.id=t.cargo_category_id
             LEFT JOIN customers cu ON cu.id=t.customer_id
             WHERE 1=1"""
    p=[]
    if q:
        like=f"%{q}%"
        sql += " AND (t.scna LIKE ? OR t.plate LIKE ? OR d.name LIKE ? OR a.name LIKE ? OR cu.name LIKE ? OR cc.name LIKE ?)"
        p += [like,like,like,like,like,like]
    if status and status != "Tümü":
        sql += " AND t.status=?"
        p.append(status)
    if customer:
        sql += " AND cu.name=?"
        p.append(customer)
    if area:
        sql += " AND a.name=?"
        p.append(area)
    if cargo:
        sql += " AND cc.name=?"
        p.append(cargo)
    n=c.execute(sql,p).fetchone()["c"]
    c.close()
    return {"count":n}

@app.get("/api/stats")
def stats():
    c=db()
    sql="""SELECT
      COUNT(*) total,
      SUM(CASE WHEN status='Bekliyor' THEN 1 ELSE 0 END) waiting,
      SUM(CASE WHEN status='Yolda' THEN 1 ELSE 0 END) onroad,
      SUM(CASE WHEN status='Tamamlandı' THEN 1 ELSE 0 END) completed,
      COALESCE(SUM(freight_total),0) freight_total,
      COALESCE(SUM(CASE WHEN entry_done=1 THEN fuel_consumed_liters ELSE 0 END),0) fuel_consumed,
      COALESCE(SUM(CASE WHEN entry_done=1 THEN MAX(amount_due,0) ELSE 0 END),0) due_total,
      COALESCE(SUM(CASE WHEN entry_done=1 THEN driver_cash_diff ELSE 0 END),0) driver_diff
      FROM ("""+tq()+""") x"""
    r=c.execute(sql).fetchone()
    c.close()
    return dict(r)

@app.get("/api/trips/{scna}")
def trip(scna: str):
    c = db()
    r = c.execute(tq() + " WHERE t.scna=?", (scna,)).fetchone()
    c.close()
    if not r:
        raise HTTPException(404, "Kayıt bulunamadı")
    return dict(r)

@app.patch("/api/trips/{scna}/status")
def set_trip_status(scna: str, x: StatusIn):
    status=x.status.strip()
    if status not in ("Bekliyor","Yolda","Tamamlandı"):
        raise HTTPException(400,"Geçersiz durum")
    c=db()
    row=c.execute("SELECT id FROM trips WHERE scna=?",(scna,)).fetchone()
    if not row:
        c.close(); raise HTTPException(404,"Kayıt bulunamadı")
    if status=="Bekliyor":
        c.execute("""
          UPDATE trips SET
            status=?,exit_done=0,entry_done=0,
            exit_at=NULL,entry_at=NULL,
            updated_at=CURRENT_TIMESTAMP
          WHERE scna=?
        """,(status,scna))
    elif status=="Yolda":
        c.execute("""
          UPDATE trips SET
            status=?,exit_done=1,entry_done=0,
            exit_at=COALESCE(exit_at,DATETIME('now','localtime')),
            entry_at=NULL,
            updated_at=CURRENT_TIMESTAMP
          WHERE scna=?
        """,(status,scna))
    else:
        c.execute("""
          UPDATE trips SET
            status=?,exit_done=1,entry_done=1,
            exit_at=COALESCE(exit_at,DATETIME('now','localtime')),
            entry_at=COALESCE(entry_at,DATETIME('now','localtime')),
            updated_at=CURRENT_TIMESTAMP
          WHERE scna=?
        """,(status,scna))
    c.commit(); c.close()
    audit("STATUS",scna,f"Durum: {status}")
    return {"ok":True,"status":status}

@app.post("/api/trips")
def create_trip(x: TripCreate):
    basis = x.freight_basis.upper()
    if basis not in ("KG", "TON"):
        raise HTTPException(400, "Navlun birimi KG veya TON olmalı")

    c = db()
    try:
        c.execute("""
          INSERT INTO trips(
            scna,plate,driver_id,area_id,cargo_category_id,cargo_type,customer_id,trip_date,
            net_kg,freight_rate,freight_basis,exit_km,tank_start_liters,
            exit_premium,dock_fee,port_fee,sonar,status
          )
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'Bekliyor')
        """, (
            x.scna.strip().upper(),
            x.plate.strip().upper(),
            x.driver_id,
            x.area_id,
            x.cargo_category_id,
            x.cargo_type.upper(),
            x.customer_id,
            x.trip_date,
            x.net_kg,
            x.freight_rate,
            basis,
            x.exit_km,
            x.tank_start_liters,
            x.exit_premium,
            x.dock_fee,
            x.port_fee,
            x.sonar
        ))
        c.commit()
    except sqlite3.IntegrityError:
        c.close()
        raise HTTPException(409, "Bu SCNA zaten mevcut")

    c.close()
    audit("CREATE", x.scna.upper(), "Sevkiyat oluşturuldu")
    return {"ok": True}

@app.patch("/api/trips/{scna}/exit")
def exit_trip(scna: str, x: ExitIn):
    c = db()
    if not c.execute("SELECT 1 FROM trips WHERE scna=?", (scna,)).fetchone():
        c.close()
        raise HTTPException(404, "Kayıt bulunamadı")

    c.execute("""
      UPDATE trips SET
        exit_cash=?,

        exit_official_fuel_liters=?,
        exit_official_fuel_total=?,

        exit_commercial_fuel_liters=?,
        exit_commercial_fuel_total=?,

        exit_baghdad_fuel_liters=?,
        exit_baghdad_fuel_total=?,

        exit_allowance=?,
        exit_other=?,
        exit_note=?,

        exit_done=1,
        exit_at=DATETIME('now','localtime'),
        status='Yolda',
        updated_at=CURRENT_TIMESTAMP
      WHERE scna=?
    """, (
        x.exit_cash,

        x.exit_official_fuel_liters,
        x.exit_official_fuel_total,

        x.exit_commercial_fuel_liters,
        x.exit_commercial_fuel_total,

        x.exit_baghdad_fuel_liters,
        x.exit_baghdad_fuel_total,

        x.exit_allowance,
        x.exit_other,
        x.exit_note,

        scna
    ))

    c.commit()
    c.close()

    audit("EXIT", scna, "Çıkış, depo ve mazot litre/tutar bilgileri kaydedildi")
    return {"ok": True}

@app.patch("/api/trips/{scna}/entry")
def entry_trip(scna: str, x: EntryIn):
    c = db()
    row = c.execute("SELECT * FROM trips WHERE scna=?", (scna,)).fetchone()

    if not row:
        c.close()
        raise HTTPException(404, "Kayıt bulunamadı")

    if not row["exit_done"]:
        c.close()
        raise HTTPException(409, "Önce çıkış işlemi yapılmalı")

    if x.entry_km < row["exit_km"]:
        c.close()
        raise HTTPException(409, "Giriş KM, çıkış KM'den küçük olamaz")

    c.execute("""
      UPDATE trips SET
        entry_km=?,
        tank_end_liters=?,

        entry_extra_expense_1=?,
        entry_extra_expense_2=?,
        entry_extra_expense_3=?,

        entry_collection=?,
        entry_cash_handed=?,
        excel_remain=NULL,
        delivery_time=DATETIME('now','localtime'),
        entry_note=?,

        entry_done=1,
        entry_at=DATETIME('now','localtime'),
        status='Tamamlandı',
        updated_at=CURRENT_TIMESTAMP
      WHERE scna=?
    """, (
        x.entry_km,
        x.tank_end_liters,

        x.entry_extra_expense_1,
        x.entry_extra_expense_2,
        x.entry_extra_expense_3,

        x.entry_collection,
        x.entry_cash_handed,
        x.entry_note,

        scna
    ))

    c.commit()
    c.close()

    audit("ENTRY", scna, "Giriş, kalan depo, ek gider ve para hesabı kaydedildi")
    return {"ok": True}

@app.get("/api/trips/{scna}/fuel")
def fuel_list(scna: str):
    c = db()
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM fuel_purchases WHERE scna=? ORDER BY id",
        (scna,)
    )]
    c.close()
    return rows

@app.post("/api/trips/{scna}/fuel")
def fuel_add(scna: str, x: FuelIn):
    if x.liters <= 0:
        raise HTTPException(400, "Litre 0'dan büyük olmalı")

    unit_price = x.total / x.liters if x.liters else 0

    c = db()
    if not c.execute("SELECT 1 FROM trips WHERE scna=?", (scna,)).fetchone():
        c.close()
        raise HTTPException(404, "Sevkiyat bulunamadı")

    c.execute("""
      INSERT INTO fuel_purchases(scna,liters,total,note)
      VALUES(?,?,?,?)
    """, (scna, x.liters, x.total, x.note))

    c.commit()
    c.close()

    audit("FUEL", scna, f"{x.liters} LT / {x.total} toplam / {unit_price:.2f} birim fiyat")
    return {"ok": True, "unit_price": unit_price}

@app.delete("/api/fuel/{id}")
def fuel_delete(id: int):
    c = db()
    row = c.execute(
        "SELECT scna FROM fuel_purchases WHERE id=?",
        (id,)
    ).fetchone()

    if not row:
        c.close()
        raise HTTPException(404, "Mazot kaydı bulunamadı")

    scna = row["scna"]
    c.execute("DELETE FROM fuel_purchases WHERE id=?", (id,))
    c.commit()
    c.close()

    audit("FUEL_DELETE", scna, "Mazot kaydı silindi")
    return {"ok": True}

@app.get("/api/audit")
def logs():
    c = db()
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT 200"
    )]
    c.close()
    return rows

HTML = r"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAMA TRACK V63</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:Segoe UI,Arial;background:#f4f7fb;color:#1f2937}
.side{position:fixed;inset:0 auto 0 0;width:245px;background:#111827;color:#fff;padding:22px 16px}
.brand{font-size:22px;font-weight:800;margin-bottom:25px}.brand span{color:#38bdf8}
.nav button{width:100%;text-align:left;border:0;background:transparent;color:#cbd5e1;padding:12px;border-radius:9px;font-weight:700;margin:4px 0;cursor:pointer}
.nav button.active,.nav button:hover{background:#1f2937;color:#fff}
.main{margin-left:245px}
.top{background:#fff;padding:18px 26px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between}
.content{padding:24px}
.panel{display:none}.panel.active{display:block}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:16px}
.card{background:white;padding:18px;border-radius:14px;box-shadow:0 4px 15px #0000000d}
.card b{display:block;font-size:24px;margin-top:6px}
.toolbar{display:flex;gap:10px;background:white;padding:14px;border-radius:14px;margin-bottom:14px;box-shadow:0 4px 15px #0000000d}
.toolbar input{flex:1}
input,select,textarea{border:1px solid #d1d5db;border-radius:9px;padding:9px 11px;font-size:14px}
.btn{border:0;border-radius:9px;padding:9px 13px;font-weight:700;cursor:pointer}
.primary{background:#2563eb;color:#fff}
.green{background:#059669;color:#fff}
.orange{background:#d97706;color:#fff}
.secondary{background:#e5e7eb}
.danger{background:#fee2e2;color:#991b1b}
.table{background:white;border-radius:14px;overflow:auto;box-shadow:0 4px 15px #0000000d}
table{width:100%;border-collapse:collapse;min-width:1150px}
th,td{padding:12px;border-bottom:1px solid #eef2f7;text-align:left;font-size:13px;white-space:nowrap}
th{background:#f8fafc;color:#64748b;font-size:11px}
.modal{display:none;position:fixed;inset:0;background:#0f172a8c;align-items:center;justify-content:center;z-index:20}
.box{background:white;width:min(1120px,96vw);max-height:93vh;overflow:auto;border-radius:16px;padding:20px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.field{display:flex;flex-direction:column;gap:5px}
.field label{font-size:12px;font-weight:800;color:#64748b}
.wide{grid-column:1/-1}
.actions{display:flex;justify-content:flex-end;gap:8px;margin-top:18px}
.calc{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:14px;margin-top:14px}
.settle{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}
.settle div{background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;padding:12px}
.settle strong{display:block;font-size:18px;margin-top:4px}
.badge{padding:5px 9px;border-radius:99px;font-weight:800;font-size:11px}
.ok{background:#dcfce7;color:#166534}
.warn{background:#fef3c7;color:#92400e}
.over{background:#e0e7ff;color:#3730a3}
.short{background:#fee2e2;color:#991b1b}
.small{font-size:12px;color:#6b7280}
.mini{min-width:0!important}
.pager{display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:12px 4px;color:#64748b;font-size:13px}
.status-select{min-width:120px;padding:6px 8px;font-weight:700}
.column-picker{position:relative}
.column-panel{
  display:none;position:absolute;right:0;top:42px;z-index:30;
  width:280px;max-height:420px;overflow:auto;background:#fff;
  border:1px solid #e5e7eb;border-radius:12px;padding:12px;
  box-shadow:0 12px 30px rgba(0,0,0,.15)
}
.column-panel.open{display:block}
.column-panel label{display:flex;gap:8px;align-items:center;padding:6px 2px;font-size:13px}
.column-panel input{width:auto}

.diff-box{
  border-radius:14px;
  padding:16px;
  font-size:14px;
  font-weight:800;
  margin-top:14px;
}
.diff-box strong{display:block;font-size:24px;margin-top:6px}
.diff-red{background:#fee2e2;border:1px solid #fecaca;color:#991b1b}
.diff-green{background:#dcfce7;border:1px solid #bbf7d0;color:#166534}
.diff-neutral{background:#f3f4f6;border:1px solid #e5e7eb;color:#374151}
.detail-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}
.detail-box{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px}
.detail-box span{display:block;color:#64748b;font-size:11px;font-weight:700}
.detail-box strong{display:block;margin-top:5px;font-size:15px}
.alert-red{background:#fee2e2;color:#991b1b;font-weight:800}
.alert-orange{background:#ffedd5;color:#9a3412;font-weight:800}
.filterbar{
  display:flex;gap:8px;align-items:center;flex-wrap:wrap;
  background:#fff;padding:10px 12px;border-radius:12px;margin-bottom:12px;
  box-shadow:0 4px 15px #0000000d
}
.filterbar input,.filterbar select{min-width:140px}
.filterbar .grow{flex:1;min-width:220px}
.section-note{font-size:12px;color:#64748b;margin-left:auto}
.compact-actions{display:flex;gap:6px;flex-wrap:wrap}
.empty-state{padding:26px;text-align:center;color:#64748b}
.quick-btn{padding:7px 10px;border-radius:8px;border:1px solid #d1d5db;background:#fff;cursor:pointer;font-weight:700}
.quick-btn:hover{background:#f8fafc}

.clickhead{cursor:pointer;user-select:none;white-space:nowrap}
.clickhead:hover{background:#e8eef7!important}
.clickhead span{font-size:11px;opacity:.65;margin-left:4px}
.head-filter-menu{position:fixed;z-index:99999;background:#fff;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 12px 35px rgba(15,23,42,.18);padding:10px;width:270px}
.head-filter-menu input{width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:7px;padding:8px;margin-bottom:7px}
.head-menu-btn{display:block;width:100%;text-align:left;border:0;background:transparent;padding:8px;border-radius:6px;cursor:pointer;font-weight:600}
.head-menu-btn:hover{background:#f1f5f9}

/* V54 - tüm tablolar için başlıktan sıralama / filtre */
table thead th.v54-head{cursor:pointer;user-select:none;white-space:nowrap}
table thead th.v54-head:hover{background:#e8eef7!important}
.v54-sortmark{font-size:11px;opacity:.6;margin-left:4px}
.v54-filtered{box-shadow:inset 0 -3px 0 #64748b}
#v54TableMenu{
 position:fixed;z-index:100000;background:#fff;border:1px solid #cbd5e1;border-radius:10px;
 box-shadow:0 12px 35px rgba(15,23,42,.20);padding:10px;width:280px
}
#v54TableMenu input{width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:7px;padding:8px;margin:7px 0}
.v54-menu-btn{display:block;width:100%;text-align:left;border:0;background:transparent;padding:8px;border-radius:6px;cursor:pointer;font-weight:600}
.v54-menu-btn:hover{background:#f1f5f9}

.grouped-nav{display:flex;flex-direction:column;gap:6px}
.nav-group{border-radius:8px;overflow:hidden}
.nav-group-title{
  width:100%;display:flex!important;justify-content:space-between;align-items:center;
  font-size:12px!important;font-weight:800!important;letter-spacing:.5px;
  padding:9px 10px!important;background:rgba(255,255,255,.06)!important;
  color:#cbd5e1!important;border:0!important
}
.nav-group-title:hover{background:rgba(255,255,255,.11)!important}
.nav-group-items{display:none;padding:4px 0 5px}
.nav-group.open .nav-group-items{display:block}
.nav-group.open .nav-group-title{color:#fff!important}
.nav-group-items button{padding-left:18px!important;font-size:13px!important}
.nav-group-title span{font-size:11px;opacity:.8}
.aside{overflow-y:auto}

.op-click{cursor:pointer;transition:transform .12s ease,box-shadow .12s ease}
.op-click:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(15,23,42,.12)}

.dashboard-op-section{width:100%;display:block;clear:both;margin:12px 0 16px}
.dashboard-op-cards{width:100%;display:grid!important;grid-template-columns:repeat(5,minmax(150px,1fr));gap:12px}
.dashboard-op-detail{display:block;width:100%;box-sizing:border-box;margin-top:12px;padding:12px;background:#fff;border:1px solid #dbe3ef;border-radius:12px;clear:both;overflow-x:auto}
.dashboard-op-detail .table{width:100%;max-width:100%;overflow-x:auto}
.dashboard-op-detail table{width:100%}
@media(max-width:1200px){.dashboard-op-cards{grid-template-columns:repeat(3,minmax(150px,1fr))}}
@media(max-width:800px){.dashboard-op-cards{grid-template-columns:repeat(2,minmax(140px,1fr))}}

.autocomplete-wrap{position:relative;width:100%}
.autocomplete-list{position:absolute;z-index:100500;left:0;right:0;top:100%;background:#fff;border:1px solid #cbd5e1;border-radius:8px;box-shadow:0 10px 28px rgba(15,23,42,.18);max-height:240px;overflow:auto;margin-top:3px;display:none}
.autocomplete-item{padding:8px 10px;cursor:pointer;border-bottom:1px solid #f1f5f9;font-size:13px}
.autocomplete-item:hover,.autocomplete-item.active{background:#eef4ff}
.autocomplete-main{font-weight:700}
.autocomplete-sub{font-size:11px;color:#64748b;margin-top:2px}
</style>
</head>
<body>

<aside class="side">
<div class="brand">SAMA <span>TRACK</span></div>
<div class="nav grouped-nav">

<div class="nav-group open">
  <button class="nav-group-title" onclick="toggleNavGroup(this)">GENEL <span>▾</span></button>
  <div class="nav-group-items">
    <button class="active" onclick="show('dash',this)">Ana Sayfa</button>
  </div>
</div>

<div class="nav-group">
  <button class="nav-group-title" onclick="toggleNavGroup(this)">SEVKİYAT <span>▸</span></button>
  <div class="nav-group-items">
    <button onclick="show('trips',this)">Sevkiyatlar</button>
    <button onclick="show('exit',this)">Çıkış İşlemi</button>
    <button onclick="show('entry',this)">Giriş İşlemi</button>
    <button onclick="show('detail',this)">SCNA Detay</button>
    <button onclick="show('editcenter',this)">SCNA Düzenleme</button>
    <button onclick="show('quality',this)">Eksik Veri</button>
    <button onclick="show('compare',this)">Excel ↔ DB</button>
    <button onclick="show('bulkfix',this)">Toplu Düzeltme</button>
  </div>
</div>

<div class="nav-group">
  <button class="nav-group-title" onclick="toggleNavGroup(this)">OPERASYON <span>▸</span></button>
  <div class="nav-group-items">
    <button onclick="show('opcenter',this)">Operasyon Kontrol</button>
    <button onclick="show('liveops',this)">Canlı Operasyon</button>
    <button onclick="show('loadqueue',this)">Yükleme Sırası</button>
    <button onclick="show('vesselops',this)">Gemi Operasyonu</button>
    <button onclick="show('routes',this)">Rota Standartları</button>
  </div>
</div>

<div class="nav-group">
  <button class="nav-group-title" onclick="toggleNavGroup(this)">FİLO <span>▸</span></button>
  <div class="nav-group-items">
    <button onclick="show('fleetmanage',this)">Filo Yönetimi</button>
    <button onclick="show('vehiclecard',this)">Araç Kartı</button>
    <button onclick="show('maintenance',this)">Bakım Takibi</button>
  </div>
</div>

<div class="nav-group">
  <button class="nav-group-title" onclick="toggleNavGroup(this)">ŞOFÖR <span>▸</span></button>
  <div class="nav-group-items">
    <button onclick="show('drivermanage',this)">Şoför Yönetimi</button>
    <button onclick="show('drivercard',this)">Şoför Kartı</button>
  </div>
</div>

<div class="nav-group">
  <button class="nav-group-title" onclick="toggleNavGroup(this)">RAPORLAR <span>▸</span></button>
  <div class="nav-group-items">
    <button onclick="show('anomaly',this)">Anormallik Merkezi</button>
    <button onclick="show('daily',this)">Gün Sonu Özeti</button>
    <button onclick="show('performance',this)">Performans</button>
    <button onclick="show('finance',this)">Finans / Kârlılık</button>
    <button onclick="show('alerts',this)">Uyarılar</button>
    <button onclick="show('audit',this)">İşlem Geçmişi</button>
  </div>
</div>

</div>
</aside>

<main class="main">
<div class="top">
<div>
<h2 style="margin:0">Sevkiyat / Yakıt Tüketim / Para Hesabı</h2>
<span>V63 AUTOCOMPLETE 3+</span>
</div>
<div style="display:flex;gap:8px;align-items:center">
<button class="btn secondary" onclick="show('dash',document.querySelector('.nav button[onclick*="show(\'dash\'"]'))">🏠 Ana Sayfa</button>
<button class="btn danger" onclick="cikisYap()">🚪 Çıkış</button>
</div>
</div>

<div class="content">

<section id="dash" class="panel active">
<div class="cards">
<div class="card">Toplam Sevkiyat<b id="dTotal">0</b></div>
<div class="dashboard-op-section">
  <div class="cards dashboard-op-cards">
    <div class="card op-click" onclick="openDashboardFleet('GEMIDE')">Gemide Çalışan<b id="dOpVessel">0</b></div>
    <div class="card op-click" onclick="openDashboardFleet('BAKIM')">Bakımda<b id="dOpMaintenance">0</b></div>
    <div class="card op-click" onclick="openDashboardFleet('YOLDA')">Yolda<b id="dOpRoad">0</b></div>
    <div class="card op-click" onclick="openDashboardFleet('BEKLEMEDE')">Beklemede<b id="dOpWaiting">0</b></div>
    <div class="card op-click" onclick="openDashboardFleet('BOSTA')">Boşta<b id="dOpIdle">0</b></div>
  </div>
  <div id="dashFleetDetail" class="dashboard-op-detail" style="display:none"></div>
</div>

<div class="card">Toplam Navlun<b id="dFreight">0</b></div>
<div class="card">Toplam Mazot LT<b id="dFuelLiters">0</b></div>
<div class="card">SEVKİYAT SONUCU MÜŞTERİDEN ALINACAK KALAN PARA<b id="dDue">0</b></div>
<div class="card">Şoför Hesap Farkı<b id="dDiff">0</b></div>
</div>

<div class="table">
<table>
<thead>
<tr>
<th>SCNA</th>
<th>PLAKA</th>
<th>GERÇEK KM</th>
<th>TÜKETİLEN LT</th>
<th>LT/100 KM</th>
<th>KM/LT</th>
<th>TOPLAM NAVLUN</th>
<th>MÜŞTERİDEN TAHSİL EDİLEN</th>
<th>MÜŞTERİDEN KALAN</th>
<th>ŞOFÖR HESAP FARKI</th>
<th>DURUM</th>
</tr>
</thead>
<tbody id="dashRows"></tbody>
</table>
</div>
</section>

<section id="trips" class="panel">
<div class="filterbar">
<input id="q" class="grow" placeholder="SCNA / plaka / şoför ara..." oninput="tripPage=1;loadTrips()">
<select id="statusFilter" onchange="tripPage=1;loadTrips()">
  <option value="Tümü">Tüm Durumlar</option>
  <option value="Bekliyor">Bekliyor</option>
  <option value="Yolda">Yolda</option>
  <option value="Tamamlandı">Tamamlandı</option>
</select>
<select id="tripCustomerFilter" onchange="tripPage=1;loadTrips()"><option value="">Tüm Müşteriler</option></select>
<select id="tripAreaFilter" onchange="tripPage=1;loadTrips()"><option value="">Tüm Bölgeler</option></select>
<select id="tripCargoFilter" onchange="tripPage=1;loadTrips()"><option value="">Tüm Mallar</option></select>
<button class="btn secondary" onclick="clearTripFilters()">Filtreyi Temizle</button>
<input id="excelFile" type="file" accept=".xlsx,.xlsm" style="display:none" onchange="importExcel(this)">
<button class="btn green" onclick="excelImportMode='sync';document.getElementById('excelFile').click()">Excel Kontrol / Senkronize Et</button>
<button class="btn primary" onclick="toggleDirectOneDrive()">OneDrive Linkinden Oku</button>
<div id="directOneDrivePanel" class="column-panel" style="width:min(780px,95vw);padding:14px">
  <b>OneDrive Paylaşım Linkinden Canlı Okuma</b>
  <div class="small" style="margin:6px 0 10px">
    Microsoft Client ID gerekmez. Program yalnızca paylaşılan Excel'i indirmeyi dener; kaynak dosyaya yazmaz.
  </div>
  <div class="field wide">
    <label>OneDrive Excel Linki</label>
    <input id="directOneDriveUrl" value="https://1drv.ms/x/c/81409aab255dc057/IQBiVbpNV1kOQZEV8Vhp0CrgAe4nAh2ez_k4aJbuxv6mfD8?e=FHexAF">
  </div>
  <div class="compact-actions" style="margin-top:10px">
    <button class="btn secondary" onclick="testDirectOneDrive()">Bağlantıyı Test Et</button>
    <button class="btn green" onclick="syncDirectOneDrive()">Excel'i Oku ve Önizle</button>
  </div>
  <div id="directOneDriveInfo" class="calc" style="display:none;margin-top:10px"></div>
</div>

<button class="btn orange" onclick="document.getElementById('entryDateRepairFile').click()">Giriş Tarihlerini Excel'den Onar</button>
<input id="entryDateRepairFile" type="file" accept=".xlsx,.xlsm" style="display:none" onchange="repairEntryDatesFromExcel(this)">

<button class="btn secondary" onclick="exportAllExcel()">Tümünü Excel'e Aktar</button>
<button class="btn secondary" onclick="exportFilteredExcel()">Filtreyi Excel'e Aktar</button>
<button class="btn orange" onclick="document.getElementById('remainRepairFile').click()">REMAIN Toplu Onar</button>
<button class="btn orange" onclick="document.getElementById('freightRepairFile').click()">FREIGHT Toplu Onar</button>
<input id="freightRepairFile" type="file" accept=".xlsx,.xlsm" style="display:none" onchange="repairFreightFromExcel(this)">

<input id="remainRepairFile" type="file" accept=".xlsx,.xlsm" style="display:none" onchange="repairRemainFromExcel(this)">


<div class="column-picker">
  <button class="btn secondary" onclick="toggleColumnPanel(event)">Gösterilecek Bilgiler</button>
  <div id="columnPanel" class="column-panel">
    <label><input type="checkbox" data-col="scna" checked onchange="saveColumnPrefs()">SCNA</label>
    <label><input type="checkbox" data-col="plate" checked onchange="saveColumnPrefs()">Plaka</label>
    <label><input type="checkbox" data-col="driver" checked onchange="saveColumnPrefs()">Şoför</label>
    <label><input type="checkbox" data-col="customer" checked onchange="saveColumnPrefs()">Müşteri</label>
    <label><input type="checkbox" data-col="area" checked onchange="saveColumnPrefs()">Bölge</label>
    <label><input type="checkbox" data-col="vessel" checked onchange="saveColumnPrefs()">Gemi</label>
    <label><input type="checkbox" data-col="cargo" checked onchange="saveColumnPrefs()">Mal Cinsi</label>
    <label><input type="checkbox" data-col="cargo_type" checked onchange="saveColumnPrefs()">Yük Tipi</label>
    <label><input type="checkbox" data-col="kg" checked onchange="saveColumnPrefs()">Net KG</label>
    <label><input type="checkbox" data-col="freight" checked onchange="saveColumnPrefs()">Navlun</label>
    <label><input type="checkbox" data-col="exit_at" checked onchange="saveColumnPrefs()">Çıkış Tarihi</label>
    <label><input type="checkbox" data-col="entry_at" checked onchange="saveColumnPrefs()">Giriş Tarihi</label>
    <label><input type="checkbox" data-col="status" checked onchange="saveColumnPrefs()">Durum</label>
  </div>
</div>

<button class="btn primary" onclick="newTrip()">+ Yeni Sevkiyat</button>
</div>
<div id="excelResult" class="calc" style="display:none;margin-bottom:14px"></div>
<div class="table">
<table>
<thead>
<tr>
<th data-col="scna" class="clickhead" onclick="tripHeadClick(event,\'scna\')">SCNA <span id="sort_scna">↕</span></th>
<th data-col="plate" class="clickhead" onclick="tripHeadClick(event,\'plate\')">PLAKA <span id="sort_plate">↕</span></th>
<th data-col="driver" class="clickhead" onclick="tripHeadClick(event,\'driver\')">ŞOFÖR <span id="sort_driver">↕</span></th>
<th data-col="customer">MÜŞTERİ</th>
<th data-col="area" class="clickhead" onclick="tripHeadClick(event,\'area\')">BÖLGE <span id="sort_area">↕</span></th><th data-col="vessel">GEMİ</th>
<th data-col="cargo">MAL</th>
<th data-col="cargo_type" class="clickhead" onclick="tripHeadClick(event,\'cargo_type\')">TİP <span id="sort_cargo_type">↕</span></th>
<th data-col="kg">KG</th>
<th data-col="freight">NAVLUN</th>
<th data-col="exit_at" class="clickhead" onclick="tripHeadClick(event,\'exit_at\')">ÇIKIŞ TARİHİ <span id="sort_exit_at">↕</span></th>
<th data-col="entry_at" class="clickhead" onclick="tripHeadClick(event,\'entry_at\')">GİRİŞ TARİHİ <span id="sort_entry_at">↕</span></th>
<th data-col="status">DURUM / DEĞİŞTİR</th>
</tr>
</thead>
<tbody id="tripRows"></tbody>
</table>
</div>
<div id="tripHeadMenu" class="head-filter-menu" style="display:none">
  <div id="tripHeadMenuTitle" style="font-weight:800;margin-bottom:8px"></div>
  <button class="head-menu-btn" onclick="applyHeadSort('asc')">▲ Artan Sırala</button>
  <button class="head-menu-btn" onclick="applyHeadSort('desc')">▼ Azalan Sırala</button>
  <div style="border-top:1px solid #e5e7eb;margin:8px 0"></div>
  <input id="tripHeadSearch" placeholder="Bu sütunda ara..." oninput="applyHeadTextFilter()">
  <button class="head-menu-btn" onclick="clearHeadFilter()">Bu Filtreyi Temizle</button>
  <button class="head-menu-btn" onclick="clearAllHeadFilters()">Tüm Başlık Filtrelerini Temizle</button>
</div>
<div class="pager"><button class="btn secondary" onclick="prevTripPage()">← Önceki</button><span id="tripPageInfo">1 / 1</span><button class="btn secondary" onclick="nextTripPage()">Sonraki →</button></div>
</section>

<section id="exit" class="panel">
<div class="filterbar">
<b>Çıkış İşlemi</b>
<input id="exitQ" class="grow" placeholder="SCNA / plaka ara" oninput="loadExit()">
<select id="exitStatusFilter" onchange="loadExit()">
  <option value="Bekliyor">Bekliyor</option>
  <option value="Yolda">Yolda</option>
  <option value="Tümü">Tümü</option>
  <option value="Tamamlandı">Tamamlandı</option>
</select>
<button class="btn secondary" onclick="exitQ.value='';exitStatusFilter.value='Bekliyor';loadExit()">Temizle</button>
<span class="section-note">Çıkış bekleyen kayıtlar varsayılan gelir.</span>
</div>
<div class="table">
<table>
<thead>
<tr><th>SCNA</th><th>PLAKA</th><th>NAVLUN</th><th>ÇIKIŞ TARİHİ</th><th>DURUM</th><th>İŞLEM</th></tr>
</thead>
<tbody id="exitRows"></tbody>
</table>
</div>
</section>

<section id="entry" class="panel">
<div class="filterbar">
<b>Giriş İşlemi</b>
<input id="entryQ" class="grow" placeholder="SCNA / plaka ara" oninput="loadEntry()">
<select id="entryStatusFilter" onchange="loadEntry()">
  <option value="Yolda">Yolda</option>
  <option value="Tamamlandı">Tamamlandı</option>
  <option value="Tümü">Tümü</option>
</select>
<button class="btn secondary" onclick="entryQ.value='';entryStatusFilter.value='Yolda';loadEntry()">Temizle</button>
<span class="section-note">Yoldaki kayıtlar varsayılan gelir.</span>
</div>
<div class="table">
<table>
<thead>
<tr><th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>ÇIKIŞ KM</th><th>ÇIKIŞ TARİHİ</th><th>GİRİŞ TARİHİ</th><th>NAVLUN</th><th>İŞLEM</th></tr>
</thead>
<tbody id="entryRows"></tbody>
</table>
</div>
</section>



<section id="editcenter" class="panel">
<div class="filterbar">
  <b>SCNA Düzenleme Merkezi</b>
  <input id="editScna" class="grow" placeholder="SCNA yaz..." onkeydown="if(event.key==='Enter')loadEditCenter()">
  <button class="btn primary" onclick="loadEditCenter()">Kaydı Getir</button>
</div>
<div id="editCenterContent">
  <div class="empty-state">Düzenlemek için SCNA gir.</div>
</div>
</section>


<section id="quality" class="panel">
<div class="filterbar">
  <b>Eksik Veri Merkezi</b>
  <input id="qualityQ" class="grow" placeholder="SCNA / plaka / şoför ara" oninput="renderQuality()">
  <select id="qualityType" onchange="renderQuality()">
    <option value="">Tüm Sorunlar</option>
    <option value="entry_date_no_km">Giriş Tarihi Var / KM Yok</option>
    <option value="exit_km_no_date">Çıkış KM Var / Tarih Yok</option>
    <option value="collection_missing">COLLECTION Eksik</option>
    <option value="driver_missing">Şoför Eksik</option>
    <option value="customer_missing">Müşteri Eksik</option>
    <option value="area_missing">Bölge Eksik</option>
    <option value="cargo_missing">Mal Eksik</option>
  </select>
  <button class="btn secondary" onclick="loadQuality()">Yenile</button>
</div>
<div class="cards">
  <div class="card">Toplam Sorunlu<b id="qualityTotal">0</b></div>
  <div class="card">Giriş Tarihi/KM<b id="qualityEntryKm">0</b></div>
  <div class="card">Collection Eksik<b id="qualityCollection">0</b></div>
  <div class="card">Şoför Eksik<b id="qualityDriver">0</b></div>
</div>
<div class="table"><table><thead><tr>
<th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>MÜŞTERİ</th><th>BÖLGE</th>
<th>DURUM</th><th>ÇIKIŞ</th><th>GİRİŞ</th><th>SORUN</th><th>İŞLEM</th>
</tr></thead><tbody id="qualityRows"></tbody></table></div>
</section>

<section id="compare" class="panel">
<div class="filterbar">
  <b>Excel ↔ Veritabanı Karşılaştırma</b>
  <input id="compareExcelFile" type="file" accept=".xlsx,.xlsm" onchange="compareExcelDb(this)">
  <select id="compareFilter" onchange="renderCompare()">
    <option value="">Tüm Farklar</option>
    <option value="FARKLI">Aynı SCNA / Değer Farklı</option>
    <option value="EXCEL_VAR_DB_YOK">Excel'de Var / DB'de Yok</option>
    <option value="DB_VAR_EXCEL_YOK">DB'de Var / Excel'de Yok</option>
  </select>
</div>
<div class="cards">
  <div class="card">Değeri Farklı<b id="cmpDifferent">0</b></div>
  <div class="card">Excel'de Var / DB Yok<b id="cmpExcelOnly">0</b></div>
  <div class="card">DB'de Var / Excel Yok<b id="cmpDbOnly">0</b></div>
</div>
<div id="compareContent"></div>
</section>

<section id="bulkfix" class="panel">
<div class="filterbar"><b>Toplu Düzeltme</b><span class="section-note">Her satıra bir SCNA yaz.</span></div>
<div class="grid">
  <div class="field wide"><label>SCNA Listesi</label>
    <textarea id="bulkScnas" rows="12" placeholder="90812&#10;KENMOONYS40"></textarea>
  </div>
  <div class="field"><label>Düzeltilecek Alan</label>
    <select id="bulkField" onchange="refreshBulkValue()">
      <option value="status">Durum</option><option value="customer_id">Müşteri</option>
      <option value="area_id">Bölge</option><option value="cargo_category_id">Mal Cinsi</option>
      <option value="driver_id">Şoför</option><option value="cargo_type">Yük Tipi</option>
      <option value="trip_date">Sevkiyat Tarihi</option>
    </select>
  </div>
  <div class="field"><label>Yeni Değer</label><div id="bulkValueBox"></div></div>
</div>
<div class="compact-actions" style="margin-top:12px">
  <button class="btn orange" onclick="runBulkFix()">Toplu Düzeltmeyi Uygula</button>
</div>
<div id="bulkResult" class="calc" style="display:none;margin-top:12px"></div>
</section>

<section id="detail" class="panel">
<div class="toolbar">
  <input id="detailScna" placeholder="SCNA yaz..." onkeydown="if(event.key==='Enter')loadScnaDetail()">
  <button class="btn primary" onclick="loadScnaDetail()">SCNA Getir</button>
</div>
<div id="detailContent"></div>
</section>


<section id="vehiclecard" class="panel">
<div class="filterbar">
  <b>Araç Kartı</b>
  <input id="vehicleCardPlate" class="grow" placeholder="Plaka yaz..." onkeydown="if(event.key==='Enter')loadVehicleCard()">
  <button class="btn primary" onclick="loadVehicleCard()">Araç Getir</button>
</div>
<div id="vehicleCardContent"></div>
</section>

<section id="drivercard" class="panel">
<div class="filterbar">
  <b>Şoför Kartı</b>
  <input id="driverCardName" class="grow" placeholder="Şoför adı yaz..." onkeydown="if(event.key==='Enter')loadDriverCard()">
  <button class="btn primary" onclick="loadDriverCard()">Şoför Getir</button>
</div>
<div id="driverCardContent"></div>
</section>


<section id="daily" class="panel">
<div class="filterbar">
  <b>Gün Sonu / Yönetici Özeti</b>
  <input id="dailyDate" type="date">
  <button class="btn primary" onclick="loadDailySummary()">Raporu Getir</button>
  <button class="quick-btn" onclick="dailyToday()">Bugün</button>
  <button class="btn secondary" onclick="exportDailyExcel()">Excel</button>
  <button class="btn secondary" onclick="printDailyReport()">PDF / Yazdır</button>
</div>
<div id="dailyReport">
<div class="cards">
  <div class="card">Çıkan Araç<b id="dailyExited">0</b></div>
  <div class="card">Giren Araç<b id="dailyEntered">0</b></div>
  <div class="card">Şu An Yolda<b id="dailyOnroad">0</b></div>
  <div class="card">Gecikmiş<b id="dailyDelayed">0</b></div>
  <div class="card">Günlük Ton<b id="dailyTon">0</b></div>
</div>
<div class="cards">
  <div class="card">Navlun<b id="dailyFreight">0</b></div>
  <div class="card">Tahsilat<b id="dailyCollected">0</b></div>
  <div class="card">Gider<b id="dailyCost">0</b></div>
  <div class="card">Net Kâr<b id="dailyProfit">0</b></div>
  <div class="card">Şoför Para Farkı<b id="dailyDriverDiff">0</b></div>
</div>
<div id="dailyTable"></div>
</div>
</section>

<section id="anomaly" class="panel">
<div class="filterbar">
  <b>Akıllı Anormallik Merkezi</b>
  <select id="anomalyType" onchange="renderAnomalies()">
    <option value="all">Tümü</option>
    <option value="fuel">Yakıt</option>
    <option value="km">KM</option>
    <option value="cash">Para Farkı</option>
    <option value="driver">Tekrarlayan Şoför Para Eksiği</option>
  </select>
  <button class="btn secondary" onclick="loadAnomalies()">Yenile</button>
</div>
<div class="cards">
  <div class="card">Yakıt Uyarısı<b id="anFuelCount">0</b></div>
  <div class="card">KM Uyarısı<b id="anKmCount">0</b></div>
  <div class="card">Para Eksiği<b id="anCashCount">0</b></div>
  <div class="card">Tekrarlayan Şoför<b id="anDriverCount">0</b></div>
</div>
<div id="anomalyContent"></div>
</section>

<section id="performance" class="panel">
<div class="filterbar">
  <b>Performans Raporları</b>
  <input id="perfQ" class="grow" placeholder="Plaka / şoför ara" oninput="renderPerformanceFilter()">
  <button class="btn secondary" onclick="perfQ.value='';renderPerformanceFilter()">Temizle</button>
  <button class="btn secondary" onclick="loadVehiclePerformance()">Araç Performansı</button>
  <button class="btn secondary" onclick="loadDriverPerformance()">Şoför Performansı</button>
</div>
<div id="performanceContent"></div>
</section>



<section id="finance" class="panel">
<div class="filterbar">
  <b>Finans / Kârlılık</b>
  <input id="finFrom" type="date">
  <input id="finTo" type="date">
  <button class="btn primary" onclick="loadFinance()">Uygula</button>
  <button class="quick-btn" onclick="setFinancePreset('today')">Bugün</button>
  <button class="quick-btn" onclick="setFinancePreset('month')">Bu Ay</button>
  <button class="quick-btn" onclick="setFinancePreset('year')">Bu Yıl</button>
  <button class="btn secondary" onclick="clearFinanceDates()">Tüm Zamanlar</button>
</div>

<div class="cards">
  <div class="card">Toplam Navlun<b id="finFreight">0</b></div>
  <div class="card">Toplam Gider<b id="finCost">0</b></div>
  <div class="card">Net Kâr<b id="finProfit">0</b></div>
  <div class="card">Kâr Marjı<b id="finMargin">0%</b></div>
  <div class="card">Toplam Ton<b id="finTon">0</b></div>
</div>

<div class="cards">
  <div class="card">Yakıt Gideri<b id="finFuel">0</b></div>
  <div class="card">Diğer Giderler<b id="finOther">0</b></div>
  <div class="card">Toplam KM<b id="finKm">0</b></div>
  <div class="card">Kâr / KM<b id="finProfitKm">0</b></div>
  <div class="card">Kâr / Ton<b id="finProfitTon">0</b></div>
</div>

<div class="cards">
  <div class="card">Sefer Sayısı<b id="finTrips">0</b></div>
  <div class="card">Tahsil Edilen<b id="finCollected">0</b></div>
  <div class="card">Kalan Alacak<b id="finReceivable">0</b></div>
</div>

<div class="toolbar">
  <button class="btn secondary" onclick="loadFinanceTable('customer')">Müşteriye Göre</button>
  <button class="btn secondary" onclick="loadFinanceTable('area')">Bölgeye Göre</button>
  <button class="btn secondary" onclick="loadFinanceTable('cargo')">Mal Cinsine Göre</button>
  <button class="btn secondary" onclick="loadFinanceMonthly()">Aylık Özet</button>
</div>

<div id="financeTable"></div>
</section>


<section id="opcenter" class="panel">
<div class="filterbar">
  <b>Operasyon Kontrol Merkezi</b>
  <input id="opQ" class="grow" placeholder="SCNA / plaka / şoför / bölge ara" oninput="renderOperationCenter()">
  <select id="opState" onchange="renderOperationCenter()">
    <option value="">Tüm Aktifler</option>
    <option value="Yolda">Yolda</option>
    <option value="Bekliyor">Bekliyor</option>
    <option value="Gecikmiş">Sadece Gecikmiş</option>
  </select>
  <button class="btn secondary" onclick="loadOperationCenter()">Yenile</button>
</div>

<div class="cards">
  <div class="card">Toplam Kayıt<b id="opTotal">0</b></div>
  <div class="card">Yolda<b id="opOnRoad">0</b></div>
  <div class="card">Bekliyor<b id="opWaiting">0</b></div>
  <div class="card">Gecikmiş<b id="opDelayed">0</b></div>
  <div class="card">Bugün Çıkış<b id="opTodayExit">0</b></div>
  <div class="card">Bugün Giriş<b id="opTodayEntry">0</b></div>
</div>

<div class="table"><table><thead><tr>
<th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>BÖLGE</th><th>DURUM</th>
<th>ÇIKIŞ</th><th>YOLDA SAAT</th><th>ROTA ORT. SAAT</th><th>ROTA ORT. KM</th>
<th>ROTA ORT. LT/100</th><th>GEÇMİŞ SEFER</th><th>UYARI</th>
</tr></thead><tbody id="opRows"></tbody></table></div>

<div class="filterbar" style="margin-top:16px">
  <b>Rota Öğrenme</b>
  <input id="routeLearnQ" class="grow" placeholder="Bölge ara" oninput="renderRouteLearning()">
</div>
<div class="table"><table><thead><tr>
<th>BÖLGE</th><th>SEFER</th><th>ORT. KM</th><th>ORT. SÜRE (SAAT)</th>
<th>ORT. LT/100</th><th>ORT. GİDER</th>
</tr></thead><tbody id="routeLearnRows"></tbody></table></div>

<div class="filterbar" style="margin-top:16px">
  <b>Araç / Şoför Performans Karşılaştırması</b>
  <button class="btn secondary" onclick="renderOpPerformance('vehicle')">Araçlar</button>
  <button class="btn secondary" onclick="renderOpPerformance('driver')">Şoförler</button>
</div>
<div id="opPerformanceContent"></div>
</section>



<section id="fleetmanage" class="panel">
<div class="filterbar">
  <b>Araç Yönetimi</b>
  <input id="fleetManageQ" class="grow" placeholder="Plaka / marka / model ara" oninput="renderFleetManage()">
  <select id="fleetManageState" onchange="renderFleetManage()">
    <option value="">Tüm Araçlar</option><option value="1">Aktif</option><option value="0">Pasif</option>
  </select>
  <button class="btn secondary" onclick="fleetManageQ.value='';fleetManageState.value='';renderFleetManage()">Temizle</button>
  <button class="btn primary" onclick="openFleetVehicle()">+ Araç Ekle</button>
</div>
<div class="cards">
  <div class="card">Toplam Araç<b id="fmTotal">0</b></div>
  <div class="card">Aktif Araç<b id="fmActive">0</b></div>
  <div class="card">Pasif / Çıkmış<b id="fmPassive">0</b></div>
</div>
<div class="table"><table><thead><tr>
<th>PLAKA</th><th>MARKA</th><th>MODEL</th><th>ARAÇ TİPİ</th><th>SON ŞOFÖR</th><th>GARAJ DURUMU</th><th>AKTİF</th><th>NOT</th><th>İŞLEM</th>
</tr></thead><tbody id="fleetManageRows"></tbody></table></div>
</section>

<section id="drivermanage" class="panel">
<div class="filterbar">
  <b>Şoför Yönetimi</b>
  <input id="driverManageQ" class="grow" placeholder="Şoför / telefon / D.No ara" oninput="renderDriverManage()">
  <select id="driverManageState" onchange="renderDriverManage()">
    <option value="">Tüm Şoförler</option><option value="1">Aktif</option><option value="0">Pasif</option>
  </select>
  <button class="btn secondary" onclick="driverManageQ.value='';driverManageState.value='';renderDriverManage()">Temizle</button>
  <button class="btn primary" onclick="openFleetDriver()">+ Şoför Ekle</button>
</div>
<div class="cards">
  <div class="card">Toplam Şoför<b id="dmTotal">0</b></div>
  <div class="card">Aktif Şoför<b id="dmActive">0</b></div>
  <div class="card">Pasif / Ayrılmış<b id="dmPassive">0</b></div>
</div>
<div class="table"><table><thead><tr>
<th>ŞOFÖR</th><th>TELEFON</th><th>D.NO</th><th>SON PLAKA</th><th>AKTİF</th><th>NOT</th><th>İŞLEM</th>
</tr></thead><tbody id="driverManageRows"></tbody></table></div>
</section>

<section id="loadqueue" class="panel">
<div class="filterbar"><b>Yükleme Sırası / Araç Durumu</b>
<input id="fleetQ" class="grow" placeholder="Plaka / şoför / SCNA / bölge" oninput="renderFleetOps()">
<select id="fleetState" onchange="renderFleetOps()"><option value="">Tüm Araçlar</option><option value="BOS">Boş</option><option value="DOLU">Dolu</option><option value="SIRA">Sıra Bekliyor</option><option value="YUKLEMEDE">Yüklemede</option></select>
<button class="btn secondary" onclick="fleetQ.value='';fleetState.value='';renderFleetOps()">Temizle</button>
<button class="btn secondary" onclick="loadFleetOps()">Yenile</button>
<button class="btn primary" onclick="resequenceFleet()">Sırayı 1'den Düzenle</button></div>
<div class="cards"><div class="card">Toplam Araç<b id="fleetTotal">0</b></div><div class="card">Boş<b id="fleetEmpty">0</b></div><div class="card">Dolu<b id="fleetLoaded">0</b></div><div class="card">Sıra Bekliyor<b id="fleetWaiting">0</b></div><div class="card">Yüklemede<b id="fleetLoading">0</b></div></div>
<div class="table"><table><thead><tr><th>SIRA</th><th>PLAKA</th><th>DURUM</th><th>ŞOFÖR</th><th>SCNA</th><th>BÖLGE</th><th>GEMİ</th><th>NOT</th><th>İŞLEM</th></tr></thead><tbody id="fleetRows"></tbody></table></div>
</section>

<section id="vesselops" class="panel">
<div class="filterbar">
  <b>Gemi Operasyonu</b>
  <input id="vesselQ" class="grow" placeholder="Gemi / plaka / şoför ara" oninput="renderVesselOps()">
  <select id="vesselState" onchange="renderVesselOps()">
    <option value="">Tüm Araçlar</option>
    <option value="CALISIYOR">Gemide Çalışıyor</option>
    <option value="CIKTI">Operasyondan Çıktı</option>
  </select>
  <button class="btn secondary" onclick="vesselQ.value='';vesselState.value='';renderVesselOps()">Temizle</button>
  <button class="btn secondary" onclick="loadFleetOps()">Yenile</button>
</div>

<div class="cards">
  <div class="card">Gemide Çalışan<b id="vesselWorkingCount">0</b></div>
  <div class="card">Operasyondan Çıkan<b id="vesselOutCount">0</b></div>
  <div class="card">Gemi Atanmamış<b id="vesselUnassignedCount">0</b></div>
</div>

<div id="vesselSummary" class="cards"></div>

<div class="table"><table><thead><tr>
<th>GEMİ</th><th>PLAKA</th><th>ŞOFÖR</th><th>OPERASYON DURUMU</th><th>NOT</th><th>İŞLEM</th>
</tr></thead><tbody id="vesselRows"></tbody></table></div>
</section>

<section id="liveops" class="panel">
<div class="filterbar">
<b>Canlı Operasyon</b>
<input id="liveQ" class="grow" placeholder="SCNA / plaka / şoför / bölge" oninput="renderLiveOps()">
<select id="liveState" onchange="renderLiveOps()">
  <option value="">Tümü</option>
  <option value="Yolda">Yolda</option>
  <option value="Bekliyor">Bekliyor</option>
  <option value="Gecikmiş">Gecikmiş</option>
</select>
<button class="btn secondary" onclick="liveQ.value='';liveState.value='';renderLiveOps()">Temizle</button>
<button class="btn secondary" onclick="loadLiveOps()">Yenile</button>
</div>
<div class="cards">
<div class="card">Toplam<b id="liveTotal">0</b></div>
<div class="card">Yolda<b id="liveOnRoad">0</b></div>
<div class="card">Bekliyor<b id="liveWaiting">0</b></div>
<div class="card">Gecikmiş<b id="liveDelayed">0</b></div>
<div class="card">Bakıma Yakın<b id="liveMaint">0</b></div>
</div>
<div class="table"><table><thead><tr>
<th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>BÖLGE</th><th>DURUM</th>
<th>ÇIKIŞ</th><th>YOLDA SAAT</th><th>BEKLENEN SAAT</th><th>UYARI</th>
</tr></thead><tbody id="liveRows"></tbody></table></div>
</section>

<section id="routes" class="panel">
<div class="filterbar">
<b>Rota Standartları</b>
<input id="routeQ" class="grow" placeholder="Bölge ara" oninput="renderRouteStandards()">
<button class="btn secondary" onclick="routeQ.value='';renderRouteStandards()">Temizle</button>
<button class="btn secondary" onclick="loadRouteStandards()">Yenile</button>
</div>
<div class="table"><table><thead><tr>
<th>BÖLGE</th><th>BEKLENEN SAAT</th><th>BEKLENEN KM</th><th>HEDEF LT/100</th><th>TOLERANS %</th><th>İŞLEM</th>
</tr></thead><tbody id="routeRows"></tbody></table></div>
</section>

<section id="maintenance" class="panel">
<div class="filterbar">
<b>Bakım Takibi</b>
<input id="maintQ" class="grow" placeholder="Plaka ara" oninput="renderMaintenance()">
<select id="maintState" onchange="renderMaintenance()">
  <option value="">Tümü</option>
  <option value="due">Bakımı Geçmiş</option>
  <option value="soon">2.000 KM İçinde</option>
  <option value="ok">Normal</option>
</select>
<button class="btn secondary" onclick="maintQ.value='';maintState.value='';renderMaintenance()">Temizle</button>
<button class="btn primary" onclick="openMaintenance()">+ Bakım Kaydı</button>
<button class="btn secondary" onclick="loadMaintenance()">Yenile</button>
</div>
<div class="table"><table><thead><tr>
<th>PLAKA</th><th>GÜNCEL KM</th><th>SON BAKIM KM</th><th>SONRAKİ BAKIM KM</th><th>KALAN KM</th>
<th>YAĞ</th><th>LASTİK</th><th>FREN</th><th>MOTOR</th><th>İŞLEM</th>
</tr></thead><tbody id="maintRows"></tbody></table></div>
</section>

<section id="alerts" class="panel">
<div class="toolbar">
  <b>Operasyon Uyarıları</b>
  <button class="btn secondary" onclick="loadAlerts()">Yenile</button>
</div>
<div class="cards">
  <div class="card">Gecikmiş Sefer<b id="alertDelayCount">0</b></div>
  <div class="card">Yakıt Anormalliği<b id="alertFuelCount">0</b></div>
</div>
<div id="alertsContent"></div>
</section>

<section id="audit" class="panel">
<div class="filterbar">
<b>İşlem Geçmişi</b>
<input id="auditQ" class="grow" placeholder="SCNA / işlem / detay ara" oninput="filterAuditRows()">
<button class="btn secondary" onclick="auditQ.value='';filterAuditRows()">Temizle</button>
</div>
<div class="table">
<table>
<thead><tr><th>TARİH</th><th>İŞLEM</th><th>SCNA</th><th>DETAY</th></tr></thead>
<tbody id="auditRows"></tbody>
</table>
</div>
</section>

</div>
</main>


<div id="v54TableMenu" style="display:none">
  <div id="v54MenuTitle" style="font-weight:800"></div>
  <button class="v54-menu-btn" onclick="v54ApplySort('asc')">▲ Artan Sırala</button>
  <button class="v54-menu-btn" onclick="v54ApplySort('desc')">▼ Azalan Sırala</button>
  <div style="border-top:1px solid #e5e7eb;margin:7px 0"></div>
  <input id="v54FilterInput" placeholder="Bu sütunda ara..." oninput="v54ApplyFilter()">
  <button class="v54-menu-btn" onclick="v54ClearColumn()">Bu Sütun Filtresini Temizle</button>
  <button class="v54-menu-btn" onclick="v54ClearTable()">Bu Tablodaki Tüm Filtreleri Temizle</button>
</div>
<div class="modal" id="modal">
<div class="box">
<h3 id="mTitle"></h3>
<div id="mBody"></div>
<div class="actions">
<button class="btn secondary" onclick="closeM()">Kapat</button>
<button class="btn primary" id="mSave">Kaydet</button>
</div>
</div>
</div>




<script>
let samaAutocompleteSeq=0;

function samaAutocompleteItems(type){
  if(type==='plate'){
    const rows=(window.fleetManageData||[]);
    if(rows.length) return rows.filter(x=>Number(x.is_active)!==0).map(x=>({value:String(x.plate||'').trim().toUpperCase(),sub:[x.brand,x.model,x.vehicle_type].filter(Boolean).join(' • ')})).filter(x=>x.value);
    return ((window.fleetData||[])).map(x=>({value:String(x.plate||'').trim().toUpperCase(),sub:[x.driver,x.vessel].filter(Boolean).join(' • ')})).filter(x=>x.value);
  }
  if(type==='driver'){
    const rows=(window.driverManageData||[]);
    if(rows.length) return rows.filter(x=>Number(x.is_active)!==0).map(x=>({value:String(x.name||'').trim(),sub:[x.phone,x.d_no].filter(Boolean).join(' • ')})).filter(x=>x.value);
    const seen=new Set(), out=[];
    (window.fleetData||[]).forEach(x=>{const v=String(x.driver||'').trim(),k=v.toLocaleUpperCase('tr-TR');if(v&&!seen.has(k)){seen.add(k);out.push({value:v,sub:x.plate||''});}});
    return out;
  }
  return [];
}

function samaAttachAutocomplete(input,type){
  if(!input || input.dataset.samaAutocompleteReady==='1') return;
  let wrap=input.parentElement;
  if(!wrap.classList.contains('autocomplete-wrap')){
    const w=document.createElement('div');w.className='autocomplete-wrap';
    input.parentNode.insertBefore(w,input);w.appendChild(input);wrap=w;
  }
  const list=document.createElement('div');list.className='autocomplete-list';wrap.appendChild(list);
  input.dataset.samaAutocompleteReady='1';input.setAttribute('autocomplete','off');
  let active=-1;

  const render=()=>{
    const q=String(input.value||'').trim().toLocaleUpperCase('tr-TR');
    active=-1;
    if(q.length<3){
      list.innerHTML='<div class="autocomplete-item"><div class="autocomplete-sub">Aramak için en az 3 karakter yazın</div></div>';
      list.style.display='block';
      return;
    }
    const a=samaAutocompleteItems(type).filter(x=>(x.value+' '+(x.sub||'')).toLocaleUpperCase('tr-TR').includes(q)).slice(0,25);
    list.innerHTML=a.length?a.map((x,i)=>`<div class="autocomplete-item" data-value="${String(x.value).replace(/"/g,'&quot;')}"><div class="autocomplete-main">${x.value}</div>${x.sub?`<div class="autocomplete-sub">${x.sub}</div>`:''}</div>`).join(''):'<div class="autocomplete-item"><div class="autocomplete-sub">Eşleşme bulunamadı</div></div>';
    list.style.display='block';
    list.querySelectorAll('[data-value]').forEach(el=>el.onmousedown=e=>{e.preventDefault();input.value=el.dataset.value;input.dispatchEvent(new Event('change',{bubbles:true}));list.style.display='none';});
  };
  input.addEventListener('focus',render);
  input.addEventListener('input',render);
  input.addEventListener('keydown',e=>{
    const items=[...list.querySelectorAll('[data-value]')];
    if(!items.length)return;
    if(e.key==='ArrowDown'){e.preventDefault();active=Math.min(active+1,items.length-1);}
    else if(e.key==='ArrowUp'){e.preventDefault();active=Math.max(active-1,0);}
    else if(e.key==='Enter'&&active>=0){e.preventDefault();input.value=items[active].dataset.value;input.dispatchEvent(new Event('change',{bubbles:true}));list.style.display='none';return;}
    else if(e.key==='Escape'){list.style.display='none';return;} else return;
    items.forEach((el,i)=>el.classList.toggle('active',i===active));
  });
  input.addEventListener('blur',()=>setTimeout(()=>list.style.display='none',150));
}

function samaInitAllAutocompletes(root=document){
  root.querySelectorAll('input:not([readonly]):not([type="file"]):not([type="hidden"])').forEach(el=>{
    if(el.dataset.noAutocomplete==='1')return;
    const id=(el.id||'').toLowerCase(), ph=(el.placeholder||'').toLocaleLowerCase('tr-TR');
    const label=(el.closest('.field')?.querySelector('label')?.innerText||'').toLocaleLowerCase('tr-TR');
    const isSearch=ph.includes('ara')||id.endsWith('q')||id.includes('filter');
    if(id.includes('plate')||ph.includes('plaka')||label.includes('plaka')) samaAttachAutocomplete(el,'plate');
    else if(!isSearch&&(id.includes('driver')||ph.includes('şoför')||ph.includes('sofor')||label.includes('şoför')||label.includes('sofor'))) samaAttachAutocomplete(el,'driver');
  });
}
document.addEventListener('DOMContentLoaded',()=>{samaInitAllAutocompletes();new MutationObserver(()=>samaInitAllAutocompletes()).observe(document.body,{childList:true,subtree:true});});

let samaServerWasDown=false;

async function samaHeartbeat(){
  try{
    const r=await fetch('/api/health?ts='+Date.now(),{cache:'no-store'});
    if(r.ok){
      if(samaServerWasDown){
        location.reload();
        return;
      }
      samaServerWasDown=false;
    }else{
      samaServerWasDown=true;
    }
  }catch(e){
    samaServerWasDown=true;
  }
}

setInterval(samaHeartbeat,2000);
setTimeout(samaHeartbeat,1000);

let v54Ctx=null;
const v54States=new WeakMap();

function v54Text(td){ return (td?.innerText||td?.textContent||'').trim(); }
function v54Num(s){
  let x=(s||'').trim().replace(/\s/g,'');
  if(!x) return null;
  // TR/European formatted number: 1.234.567,89
  if(/^[-+]?\d{1,3}(\.\d{3})*(,\d+)?$/.test(x)) x=x.replace(/\./g,'').replace(',','.');
  else if(/^[-+]?\d+(,\d+)?$/.test(x)) x=x.replace(',','.');
  else return null;
  const n=Number(x); return Number.isFinite(n)?n:null;
}
function v54Date(s){
  let m=(s||'').match(/^(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{4})(?:\s+(\d{1,2}):(\d{2}))?/);
  if(!m) return null;
  return new Date(+m[3],+m[2]-1,+m[1],+(m[4]||0),+(m[5]||0)).getTime();
}
function v54Cmp(a,b){
  const da=v54Date(a),db=v54Date(b);
  if(da!==null&&db!==null) return da-db;
  const na=v54Num(a),nb=v54Num(b);
  if(na!==null&&nb!==null) return na-nb;
  return String(a).localeCompare(String(b),'tr',{numeric:true,sensitivity:'base'});
}
function v54State(table){
  if(!v54States.has(table)) v54States.set(table,{filters:{},sortCol:null,sortDir:null});
  return v54States.get(table);
}
function v54InitTables(root=document){
  root.querySelectorAll('table').forEach((table,ti)=>{
    if(table.dataset.v54Ready==='1') return;
    table.dataset.v54Ready='1';
    const heads=[...(table.tHead?.rows?.[0]?.cells||[])];
    heads.forEach((th,i)=>{
      // Trips has its own V53 richer handler. Avoid double menu.
      if(th.classList.contains('clickhead')) return;
      const title=v54Text(th);
      if(!title || ['İŞLEM','DÜZENLE'].includes(title.toLocaleUpperCase('tr-TR'))) return;
      th.classList.add('v54-head');
      th.dataset.v54Col=i;
      th.dataset.v54Title=title;
      if(!th.querySelector('.v54-sortmark')){
        const sp=document.createElement('span');sp.className='v54-sortmark';sp.textContent=' ↕';th.appendChild(sp);
      }
      th.addEventListener('click',e=>v54Open(e,table,i,th));
    });
  });
}
function v54Open(ev,table,col,th){
  v54Ctx={table,col,th};
  const st=v54State(table);
  v54MenuTitle.textContent=th.dataset.v54Title||v54Text(th);
  v54FilterInput.value=st.filters[col]||'';
  const r=th.getBoundingClientRect();
  v54TableMenu.style.left=Math.min(r.left,window.innerWidth-300)+'px';
  v54TableMenu.style.top=Math.min(r.bottom+4,window.innerHeight-260)+'px';
  v54TableMenu.style.display='block';
  setTimeout(()=>v54FilterInput.focus(),30);
}
function v54ApplySort(dir){
  if(!v54Ctx)return;
  const st=v54State(v54Ctx.table);st.sortCol=v54Ctx.col;st.sortDir=dir;
  v54TableMenu.style.display='none';v54Render(v54Ctx.table);
}
function v54ApplyFilter(){
  if(!v54Ctx)return;
  const st=v54State(v54Ctx.table),v=v54FilterInput.value.trim();
  if(v)st.filters[v54Ctx.col]=v;else delete st.filters[v54Ctx.col];
  v54Render(v54Ctx.table);
}
function v54ClearColumn(){
  if(!v54Ctx)return;
  const st=v54State(v54Ctx.table);delete st.filters[v54Ctx.col];
  v54FilterInput.value='';v54TableMenu.style.display='none';v54Render(v54Ctx.table);
}
function v54ClearTable(){
  if(!v54Ctx)return;
  v54States.set(v54Ctx.table,{filters:{},sortCol:null,sortDir:null});
  v54TableMenu.style.display='none';v54Render(v54Ctx.table);
}
function v54Render(table){
  const body=table.tBodies?.[0];if(!body)return;
  const st=v54State(table);
  let rows=[...body.rows];

  // Filtering
  rows.forEach(row=>{
    let ok=true;
    for(const [c,q] of Object.entries(st.filters)){
      const txt=v54Text(row.cells[+c]).toLocaleUpperCase('tr-TR');
      if(!txt.includes(String(q).toLocaleUpperCase('tr-TR'))){ok=false;break;}
    }
    row.style.display=ok?'':'none';
  });

  // Sorting keeps hidden rows too, so clearing filter restores correct order.
  if(st.sortCol!==null){
    const c=st.sortCol,m=st.sortDir==='desc'?-1:1;
    rows.sort((a,b)=>v54Cmp(v54Text(a.cells[c]),v54Text(b.cells[c]))*m);
    rows.forEach(r=>body.appendChild(r));
  }

  [...(table.tHead?.rows?.[0]?.cells||[])].forEach((th,i)=>{
    if(th.classList.contains('clickhead'))return;
    const mark=th.querySelector('.v54-sortmark');
    if(mark)mark.textContent=st.sortCol===i?(st.sortDir==='asc'?' ▲':' ▼'):' ↕';
    th.classList.toggle('v54-filtered',Object.prototype.hasOwnProperty.call(st.filters,i));
  });
}
document.addEventListener('click',e=>{
  if(v54TableMenu.style.display!=='none'&&!v54TableMenu.contains(e.target)&&!e.target.closest('.v54-head'))v54TableMenu.style.display='none';
});
document.addEventListener('DOMContentLoaded',()=>v54InitTables());
const v54Observer=new MutationObserver(()=>v54InitTables());
document.addEventListener('DOMContentLoaded',()=>v54Observer.observe(document.body,{childList:true,subtree:true}));

let L={vehicles:[],areas:[],cargo_categories:[],customers:[]},cache=[],cx=null;
let excelImportMode='sync';
let lastImportFailedRecords=[];
let lastExcelFile=null;
let lastExcelPreview=null;

const api=async(u,o={})=>{
  let r=await fetch(u,o);
  if(!r.ok){
    let e=await r.json();
    throw new Error(e.detail||'Hata');
  }
  return r.json();
};

const money=v=>Number(v||0).toLocaleString('tr-TR',{maximumFractionDigits:2});

function parseMoney(value){
  if(value===null || value===undefined) return 0;
  let s=String(value).trim().replace(/\s/g,'').replace(/[₺$€£₺]/g,'');
  if(!s) return 0;

  const hasDot=s.includes('.');
  const hasComma=s.includes(',');

  if(hasDot && hasComma){
    // Son görülen ayıracı ondalık kabul et, diğerini binlik kabul et.
    if(s.lastIndexOf(',') > s.lastIndexOf('.')){
      s=s.replace(/\./g,'').replace(',','.');
    }else{
      s=s.replace(/,/g,'');
    }
  }else if(hasDot){
    const parts=s.split('.');
    // 469.770 gibi 3 haneli son grup varsa binlik ayırıcı kabul et.
    if(parts.length>1 && parts.slice(1).every(p=>p.length===3)){
      s=parts.join('');
    }
  }else if(hasComma){
    const parts=s.split(',');
    // 469,770 gibi 3 haneli son grup varsa binlik ayırıcı kabul et.
    if(parts.length>1 && parts.slice(1).every(p=>p.length===3)){
      s=parts.join('');
    }else{
      s=s.replace(',','.');
    }
  }

  s=s.replace(/[^\d.-]/g,'');
  const n=Number(s);
  return Number.isFinite(n)?n:0;
}

function parseQty(value){
  if(value===null || value===undefined) return 0;
  let s=String(value).trim().replace(/\s/g,'');
  if(!s) return 0;
  // Miktarlarda virgülü ondalık kabul et.
  if(s.includes(',') && !s.includes('.')) s=s.replace(',','.');
  const n=Number(s);
  return Number.isFinite(n)?n:0;
}


function fmtDateTime(v){
  if(!v) return '';
  let s=String(v).replace('T',' ');
  // YYYY-MM-DD HH:mm:ss -> DD.MM.YYYY HH:mm
  const m=s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  if(m) return `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}`;
  return s;
}

function getColumnPrefs(){
  const def=['scna','plate','driver','customer','area','cargo','cargo_type','kg','freight','exit_at','entry_at','status'];
  try{
    const v=JSON.parse(localStorage.getItem('tripColumnPrefs')||'null');
    return Array.isArray(v)&&v.length?v:def;
  }catch(e){ return def; }
}

function applyColumnPrefs(){
  const selected=getColumnPrefs();
  document.querySelectorAll('#trips [data-col]').forEach(el=>{
    el.style.display=selected.includes(el.dataset.col)?'':'none';
  });
  document.querySelectorAll('#columnPanel input[data-col]').forEach(cb=>{
    cb.checked=selected.includes(cb.dataset.col);
  });
}

function saveColumnPrefs(){
  const selected=[...document.querySelectorAll('#columnPanel input[data-col]:checked')].map(x=>x.dataset.col);
  if(!selected.length) return;
  localStorage.setItem('tripColumnPrefs',JSON.stringify(selected));
  applyColumnPrefs();
}

function toggleColumnPanel(e){
  if(e) e.stopPropagation();
  columnPanel.classList.toggle('open');
}

document.addEventListener('click',e=>{
  const p=document.querySelector('.column-picker');
  if(p && !p.contains(e.target)) columnPanel.classList.remove('open');
});

function sBadge(s){
  if(s==='HESAP TAMAM') return '<span class="badge ok">HESAP TAMAM</span>';
  if(s==='EKSİK PARA') return '<span class="badge short">EKSİK PARA</span>';
  if(s==='FAZLA PARA') return '<span class="badge over">FAZLA PARA</span>';
  return '<span class="badge warn">AÇIK</span>';
}


function toggleNavGroup(btn){
  const group=btn.closest('.nav-group');
  if(!group) return;
  const willOpen=!group.classList.contains('open');

  document.querySelectorAll('.nav-group').forEach(g=>{
    g.classList.remove('open');
    const s=g.querySelector('.nav-group-title span');
    if(s) s.textContent='▸';
  });

  if(willOpen){
    group.classList.add('open');
    const s=group.querySelector('.nav-group-title span');
    if(s) s.textContent='▾';
  }
}

function openNavGroupForButton(btn){
  if(!btn) return;
  const group=btn.closest('.nav-group');
  if(!group) return;
  document.querySelectorAll('.nav-group').forEach(g=>{
    g.classList.remove('open');
    const s=g.querySelector('.nav-group-title span');
    if(s) s.textContent='▸';
  });
  group.classList.add('open');
  const s=group.querySelector('.nav-group-title span');
  if(s) s.textContent='▾';
}

function cikisYap(){
  if(confirm('SAMA TRACK\'tan çıkış yapmak istiyor musunuz?')){
    window.location.href = '/logout';
  }
}

function show(id,b){
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  openNavGroupForButton(b);

  if(id==='dash') loadDash();
  if(id==='trips') loadTrips();
  if(id==='exit') loadExit();
  if(id==='entry') loadEntry();
  if(id==='detail') document.getElementById('detailScna').focus();
  if(id==='editcenter') document.getElementById('editScna').focus();
  if(id==='quality') loadQuality();
  if(id==='bulkfix') refreshBulkValue();
  if(id==='vehiclecard') document.getElementById('vehicleCardPlate').focus();
  if(id==='drivercard') document.getElementById('driverCardName').focus();
  if(id==='anomaly') loadAnomalies();
  if(id==='daily') dailyToday();
  if(id==='performance') loadVehiclePerformance();
  if(id==='finance') loadFinance();
  if(id==='fleetmanage') loadFleetManage();
  if(id==='drivermanage') loadDriverManage();
  if(id==='opcenter') loadOperationCenter();
  if(id==='loadqueue') loadFleetOps();
  if(id==='vesselops') loadFleetOps();
  if(id==='liveops') loadLiveOps();
  if(id==='routes') loadRouteStandards();
  if(id==='maintenance') loadMaintenance();
  if(id==='alerts') loadAlerts();
  if(id==='audit') loadAudit();
}

function openM(t,b,s){
  mTitle.innerText=t;
  mBody.innerHTML=b;
  mSave.onclick=s;
  modal.style.display='flex';
}

function closeM(){
  modal.style.display='none';
}

let tripPage=1;
const tripPageSize=50;
let tripTotal=0;

async function ft(q='',status='',limit=50,offset=0,customer='',area='',cargo=''){
  let url='/api/trips?q='+encodeURIComponent(q||'')+
          '&status='+encodeURIComponent(status||'')+
          '&customer='+encodeURIComponent(customer||'')+
          '&area='+encodeURIComponent(area||'')+
          '&cargo='+encodeURIComponent(cargo||'')+
          '&limit='+limit+'&offset='+offset;
  cache=await api(url);
  return cache;
}

async function init(){
  L=await api('/api/lookups');

  const addOpts=(id,items,labelKey='name')=>{
    const el=document.getElementById(id);
    if(!el) return;
    items.forEach(x=>{
      const o=document.createElement('option');
      o.value=x[labelKey]||'';
      o.textContent=x[labelKey]||'';
      el.appendChild(o);
    });
  };

  addOpts('tripCustomerFilter',L.customers||[]);
  addOpts('tripAreaFilter',L.areas||[]);
  addOpts('tripCargoFilter',L.cargo_categories||[]);

  loadDash();
}


let integratedFleetRows=[];

async function loadIntegratedFleetStatus(){
  const d=await api('/api/integrated-fleet-status');
  integratedFleetRows=d.rows||[];
  const c=d.counts||{};
  if(document.getElementById('dOpVessel')){
    dOpVessel.innerText=c.GEMIDE||0;
    dOpMaintenance.innerText=c.BAKIM||0;
    dOpRoad.innerText=c.YOLDA||0;
    dOpWaiting.innerText=c.BEKLEMEDE||0;
    dOpIdle.innerText=c.BOSTA||0;
  }
  return d;
}
function integratedStateLabel(s){
  return {GEMIDE:'GEMİDE ÇALIŞIYOR',BAKIM:'BAKIMDA',YOLDA:'YOLDA',BEKLEMEDE:'BEKLEMEDE',BOSTA:'BOŞTA'}[s]||s;
}
async function openDashboardFleet(state){
  if(!integratedFleetRows.length)await loadIntegratedFleetStatus();
  const rows=integratedFleetRows.filter(x=>x.operation_state===state);
  const box=document.getElementById('dashFleetDetail');
  box.style.display='block';
  box.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:10px">
    <b>${integratedStateLabel(state)} — ${rows.length} ARAÇ</b>
    <button class="btn secondary" onclick="document.getElementById('dashFleetDetail').style.display='none'">Kapat</button>
  </div>
  <div class="table"><table><thead><tr>
    <th>PLAKA</th><th>ŞOFÖR</th><th>SCNA</th><th>BÖLGE</th><th>GEMİ</th><th>DURUM</th><th>ÇIKIŞ</th>
  </tr></thead><tbody>
  ${rows.map(x=>`<tr>
    <td><b>${x.plate||''}</b></td><td>${x.driver||''}</td><td>${x.scna||''}</td>
    <td>${x.area||''}</td><td>${x.vessel||''}</td><td>${integratedStateLabel(x.operation_state)}</td>
    <td>${fmtDateTime(x.exit_at)}</td>
  </tr>`).join('')}
  </tbody></table></div>`;
  if(typeof v54InitTables==='function')v54InitTables();
}

async function loadDash(){
  await loadIntegratedFleetStatus();
  const s=await api('/api/stats');
  const d=await ft('', '', 25, 0);

  dTotal.innerText=s.total||0;
  dFreight.innerText=money(s.freight_total||0);
  dFuelLiters.innerText=money(s.fuel_consumed||0);
  dDue.innerText=money(s.due_total||0);
  dDiff.innerText=money(s.driver_diff||0);

  let totalDiff=Number(s.driver_diff||0);
  let diffCard=dDiff.closest('.card');
  diffCard.classList.remove('diff-red','diff-green');
  if(totalDiff<0) diffCard.classList.add('diff-red');
  else if(totalDiff>0) diffCard.classList.add('diff-green');

  dashRows.innerHTML='';
  d.forEach(x=>{
    let diffClass=Number(x.driver_cash_diff||0)<0?'style="background:#fee2e2;color:#991b1b;font-weight:800"':
                  Number(x.driver_cash_diff||0)>0?'style="background:#dcfce7;color:#166534;font-weight:800"':'';
    dashRows.innerHTML+=`<tr>
      <td><b>${x.scna}</b></td><td>${x.plate}</td><td>${money(x.actual_km)}</td>
      <td>${money(x.fuel_consumed_liters)}</td><td>${money(x.liters_per_100km)}</td><td>${money(x.km_per_liter)}</td>
      <td>${money(x.freight_total)}</td><td>${money(x.expected_cash_handover)}</td>
      <td style="font-weight:800">${money(x.amount_due)}</td><td ${diffClass}>${money(x.driver_cash_diff)}</td>
      <td>${sBadge(x.driver_cash_status)}</td></tr>`;
  });
}


let tripHeadField='';
let tripSortField='';
let tripSortDir='';
let tripColumnFilters={};
let tripOriginalRows=[];

function tripHeadClick(ev,field){
  tripHeadField=field;
  const menu=document.getElementById('tripHeadMenu');
  tripHeadMenuTitle.textContent={scna:'SCNA',plate:'PLAKA',driver:'ŞOFÖR',area:'BÖLGE',cargo_type:'TİP',exit_at:'ÇIKIŞ TARİHİ',entry_at:'GİRİŞ TARİHİ'}[field]||field;
  tripHeadSearch.value=tripColumnFilters[field]||'';
  const r=ev.currentTarget.getBoundingClientRect();
  menu.style.left=Math.min(r.left,window.innerWidth-290)+'px';
  menu.style.top=(r.bottom+4)+'px';
  menu.style.display='block';
}
function applyHeadSort(dir){tripSortField=tripHeadField;tripSortDir=dir;updateTripSortIcons();tripHeadMenu.style.display='none';renderCurrentTripRows();}
function applyHeadTextFilter(){const v=tripHeadSearch.value.trim();if(v)tripColumnFilters[tripHeadField]=v;else delete tripColumnFilters[tripHeadField];renderCurrentTripRows();}
function clearHeadFilter(){delete tripColumnFilters[tripHeadField];tripHeadSearch.value='';tripHeadMenu.style.display='none';renderCurrentTripRows();}
function clearAllHeadFilters(){tripColumnFilters={};tripSortField='';tripSortDir='';tripHeadMenu.style.display='none';updateTripSortIcons();renderCurrentTripRows();}
function updateTripSortIcons(){
 ['scna','plate','driver','area','cargo_type','exit_at','entry_at'].forEach(f=>{const e=document.getElementById('sort_'+f);if(e)e.textContent=tripSortField===f?(tripSortDir==='asc'?'▲':'▼'):'↕';});
}
function tripVal(x,f){
 if(f==='entry_at')return x.entry_display_at||x.entry_at||x.delivery_time||'';
 if(f==='cargo_type')return x.cargo_type_name||x.cargo_type||'';
 if(f==='driver')return x.driver_name||x.driver||'';
 if(f==='area')return x.area_name||x.area||'';
 if(f==='customer')return x.customer_name||x.customer||'';
 if(f==='cargo')return x.cargo_name||x.cargo||'';
 if(f==='vessel')return x.vessel_name||x.vessel||'';
 return x[f]??'';
}
function currentTripRows(){
 let a=[...tripOriginalRows];
 for(const [f,q] of Object.entries(tripColumnFilters)){
   const n=String(q).toLocaleUpperCase('tr-TR');
   a=a.filter(x=>String(tripVal(x,f)).toLocaleUpperCase('tr-TR').includes(n));
 }
 if(tripSortField){
   const f=tripSortField,m=tripSortDir==='desc'?-1:1;
   a.sort((x,y)=>{
     let A=tripVal(x,f),B=tripVal(y,f);
     if(f==='exit_at'||f==='entry_at'){A=A?new Date(A).getTime():0;B=B?new Date(B).getTime():0;return(A-B)*m;}
     return String(A).localeCompare(String(B),'tr',{numeric:true,sensitivity:'base'})*m;
   });
 }
 return a;
}
function renderCurrentTripRows(){
 const d=currentTripRows();
 tripRows.innerHTML='';
 d.forEach(x=>{
    tripRows.innerHTML+=`<tr>
      <td data-col="scna"><b>${x.scna}</b></td>
      <td data-col="plate">${x.plate}</td>
      <td data-col="driver">${x.driver_name||x.driver||""}</td>
      <td data-col="customer">${x.customer_name||x.customer||""}</td>
      <td data-col="area">${x.area_name||x.area||""}</td>
      <td data-col="vessel">${x.vessel_name||''}</td>
      <td data-col="cargo">${x.cargo_name||x.cargo||""}</td>
      <td data-col="cargo_type">${x.cargo_type_name||x.cargo_type||''}</td>
      <td data-col="kg">${money(x.kg)}</td>
      <td data-col="freight">${money(x.freight_total||x.freight)}</td>
      <td data-col="exit_at">${fmtDateTime(x.exit_at)}</td>
      <td data-col="entry_at">${fmtDateTime(x.entry_display_at||x.entry_at||x.delivery_time)}</td>
      <td data-col="status">
        <div style="display:flex;gap:8px;align-items:center">
          <select onchange="changeTripStatus('${x.scna}',this.value)">
            <option value="Bekliyor" ${(x.status_display||x.status)==='Bekliyor'?'selected':''}>Bekliyor</option>
            <option value="Yolda" ${(x.status_display||x.status)==='Yolda'?'selected':''}>Yolda</option>
            <option value="Tamamlandı" ${(x.status_display||x.status)==='Tamamlandı'?'selected':''}>Tamamlandı</option>
          </select>
          <button class="btn secondary" onclick="openEditFrom('${x.scna}')">Düzenle</button>
        </div>
      </td></tr>`;
 });
 applyColumnPrefs();
}
document.addEventListener('click',e=>{
 const m=document.getElementById('tripHeadMenu');
 if(m&&m.style.display!=='none'&&!m.contains(e.target)&&!e.target.closest('.clickhead'))m.style.display='none';
});

async function loadTrips(){
  const query=q.value||'';
  const status=statusFilter.value||'Tümü';
  const customer=tripCustomerFilter.value||'';
  const area=tripAreaFilter.value||'';
  const cargo=tripCargoFilter.value||'';
  const cnt=await api('/api/trips-count?q='+encodeURIComponent(query)+
    '&status='+encodeURIComponent(status)+
    '&customer='+encodeURIComponent(customer)+
    '&area='+encodeURIComponent(area)+
    '&cargo='+encodeURIComponent(cargo));
  tripTotal=cnt.count||0;
  const maxPage=Math.max(1,Math.ceil(tripTotal/tripPageSize));
  if(tripPage>maxPage) tripPage=maxPage;
  const d=await ft(query,status,tripPageSize,(tripPage-1)*tripPageSize,customer,area,cargo);
  tripOriginalRows=d||[];
  renderCurrentTripRows();
  tripPageInfo.innerText=tripPage+' / '+maxPage+'  ('+tripTotal+' kayıt)';
  applyColumnPrefs();
}


function openEditFrom(scna){
  switchPanel('editcenter');
  editScna.value=scna;
  loadEditCenter();
}

function prevTripPage(){ if(tripPage>1){tripPage--;loadTrips();} }
function nextTripPage(){ const m=Math.max(1,Math.ceil(tripTotal/tripPageSize)); if(tripPage<m){tripPage++;loadTrips();} }

function clearTripFilters(){
  tripColumnFilters={};tripSortField='';tripSortDir='';updateTripSortIcons();
  q.value='';
  statusFilter.value='Tümü';
  tripCustomerFilter.value='';
  tripAreaFilter.value='';
  tripCargoFilter.value='';
  tripPage=1;
  loadTrips();
}

async function changeTripStatus(scna,status){
  try{
    await api('/api/trips/'+encodeURIComponent(scna)+'/status',{
      method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})
    });
    await loadTrips();
  }catch(e){ alert(e.message); }
}

async function loadExit(){
  const status=exitStatusFilter.value||'Bekliyor';
  const d=await ft(exitQ.value||'',status,100,0);
  exitRows.innerHTML='';
  d.forEach(x=>{
    exitRows.innerHTML+=`<tr>
      <td><b>${x.scna}</b></td>
      <td>${x.plate}</td>
      <td>${money(x.freight_total)}</td>
      <td>${fmtDateTime(x.exit_at)}</td>
      <td>${x.status}</td>
      <td><button class="btn orange" onclick="openExit('${x.scna}')">${x.exit_done?'Çıkışı Düzenle':'Çıkış Yap'}</button></td>
    </tr>`;
  });
}

async function loadEntry(){
  const status=entryStatusFilter.value||'Yolda';
  const d=await ft(entryQ.value||'',status,100,0);
  entryRows.innerHTML='';
  d.forEach(x=>{
    entryRows.innerHTML+=`<tr>
      <td><b>${x.scna}</b></td>
      <td>${x.plate}</td>
      <td>${x.driver_name||''}</td>
      <td>${money(x.exit_km)}</td>
      <td>${fmtDateTime(x.exit_at)}</td>
      <td>${fmtDateTime(x.entry_display_at||x.entry_at||x.delivery_time)}</td>
      <td>${money(x.freight_total)}</td>
      <td><button class="btn green" onclick="openEntry('${x.scna}')">${x.entry_done?'Girişi Düzenle':'Giriş Yap'}</button></td>
    </tr>`;
  });
}




let qualityCache={rows:[],counts:{},total:0};
let compareCache={rows:[],counts:{},total:0};

async function loadQuality(){
  qualityCache=await api('/api/data-quality');
  qualityTotal.innerText=qualityCache.total||0;
  qualityEntryKm.innerText=qualityCache.counts.entry_date_no_km||0;
  qualityCollection.innerText=qualityCache.counts.collection_missing||0;
  qualityDriver.innerText=qualityCache.counts.driver_missing||0;
  renderQuality();
}
function renderQuality(){
  const qv=(document.getElementById('qualityQ')?.value||'').toLowerCase();
  const type=document.getElementById('qualityType')?.value||'';
  const rows=(qualityCache.rows||[]).filter(x=>{
    const hay=[x.scna,x.plate,x.driver_name,x.customer_name,x.area_name].join(' ').toLowerCase();
    if(qv&&!hay.includes(qv)) return false;
    if(type&&!x[type]) return false;
    return true;
  });
  qualityRows.innerHTML='';
  if(!rows.length){
    qualityRows.innerHTML='<tr><td colspan="10" class="empty-state">Bu filtrede sorunlu kayıt yok.</td></tr>'; return;
  }
  rows.forEach(x=>{
    qualityRows.innerHTML+=`<tr class="alert-orange">
      <td><b>${x.scna}</b></td><td>${x.plate||''}</td><td>${x.driver_name||''}</td>
      <td>${x.customer_name||''}</td><td>${x.area_name||''}</td><td>${x.status||''}</td>
      <td>${fmtDateTime(x.exit_at)}</td><td>${fmtDateTime(x.entry_display_at||x.entry_at||x.delivery_time)}</td>
      <td>${(x.problems||[]).join('<br>')}</td>
      <td><button class="quick-btn" onclick="openEditFrom('${x.scna}')">Düzelt</button></td></tr>`;
  });
}

async function compareExcelDb(input){
  const file=input.files&&input.files[0]; if(!file) return;
  compareContent.innerHTML='<div class="calc"><b>Karşılaştırılıyor...</b></div>';
  try{
    const raw=await file.arrayBuffer();
    const r=await fetch('/api/compare-excel-db',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:raw});
    const data=await r.json(); if(!r.ok) throw new Error(data.detail||'Karşılaştırma hatası');
    compareCache=data;
    cmpDifferent.innerText=data.counts.different||0;
    cmpExcelOnly.innerText=data.counts.excel_only||0;
    cmpDbOnly.innerText=data.counts.db_only||0;
    renderCompare();
  }catch(e){ compareContent.innerHTML='<div class="calc"><b style="color:#991b1b">'+e.message+'</b></div>'; }
}
function renderCompare(){
  const type=document.getElementById('compareFilter')?.value||'';
  const rows=(compareCache.rows||[]).filter(x=>!type||x.result===type);
  let h=`<div class="table"><table><thead><tr><th>EXCEL SATIR</th><th>SCNA</th><th>SONUÇ</th><th>FARKLAR</th><th>İŞLEM</th></tr></thead><tbody>`;
  if(!rows.length) h+='<tr><td colspan="5" class="empty-state">Fark bulunmadı.</td></tr>';
  rows.forEach(x=>{
    h+=`<tr class="${x.result==='FARKLI'?'alert-orange':'alert-red'}">
      <td>${x.row||''}</td><td><b>${x.scna||''}</b></td><td>${x.result||''}</td>
      <td>${(x.differences||[]).join('<br>')}</td>
      <td>${x.result!=='DB_VAR_EXCEL_YOK'?`<button class="quick-btn" onclick="openEditFrom('${x.scna}')">DB Kaydını Aç</button>`:''}</td></tr>`;
  });
  h+='</tbody></table></div>'; compareContent.innerHTML=h;
}

function refreshBulkValue(){
  const f=bulkField.value; let h='';
  if(f==='status') h='<select id="bulkValue"><option>Bekliyor</option><option>Yolda</option><option>Tamamlandı</option></select>';
  else if(f==='customer_id') h='<select id="bulkValue"><option value="">Seçin</option>'+(L.customers||[]).map(x=>`<option value="${x.id}">${x.name}</option>`).join('')+'</select>';
  else if(f==='area_id') h='<select id="bulkValue"><option value="">Seçin</option>'+(L.areas||[]).map(x=>`<option value="${x.id}">${x.name}</option>`).join('')+'</select>';
  else if(f==='cargo_category_id') h='<select id="bulkValue"><option value="">Seçin</option>'+(L.cargo_categories||[]).map(x=>`<option value="${x.id}">${x.name}</option>`).join('')+'</select>';
  else if(f==='driver_id'){
    const seen=new Set(), arr=(L.vehicles||[]).filter(x=>{const id=x.current_driver_id||x.driver_id;if(!id||seen.has(id))return false;seen.add(id);return true;});
    h='<select id="bulkValue"><option value="">Seçin</option>'+arr.map(x=>`<option value="${x.current_driver_id||x.driver_id}">${x.driver_name||''}</option>`).join('')+'</select>';
  } else if(f==='cargo_type') h='<select id="bulkValue"><option>BULK</option><option>BAG</option></select>';
  else if(f==='trip_date') h='<input id="bulkValue" type="date">';
  bulkValueBox.innerHTML=h;
}
async function runBulkFix(){
  const scnas=(bulkScnas.value||'').split(/\r?\n|,|;/).map(x=>x.trim().toUpperCase()).filter(Boolean);
  if(!scnas.length){alert('SCNA listesi boş.');return;}
  if(!confirm(scansText(scans=scnas)))return;
  const value=document.getElementById('bulkValue')?.value||'';
  const r=await api('/api/bulk-fix',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scnas,field:bulkField.value,value})});
  bulkResult.style.display='block';
  bulkResult.innerHTML='<b style="color:#166534">'+r.updated+' kayıt güncellendi.</b>'+(r.failed?.length?'<br>'+r.failed.map(x=>x.scna+': '+x.reason).join('<br>'):'');
}
function scansText(scans){return scans.length+' kayıt toplu olarak değiştirilecek. Emin misin?';}


let editCx=null;

async function loadEditCenter(){
  const scna=(editScna.value||'').trim().toUpperCase();
  if(!scna) return;

  try{
    editCx=await api('/api/trips/'+encodeURIComponent(scna)+'/edit-data');

    const drivers=(L.vehicles||[])
      .filter((v,i,a)=>v.driver_id && a.findIndex(z=>z.driver_id===v.driver_id)===i)
      .map(v=>`<option value="${v.driver_id}">${v.driver_name||''}</option>`).join('');

    const areas=(L.areas||[]).map(a=>`<option value="${a.id}">${a.name}</option>`).join('');
    const cargos=(L.cargo_categories||[]).map(a=>`<option value="${a.id}">${a.name}</option>`).join('');
    const customers=(L.customers||[]).map(a=>`<option value="${a.id}">${a.name}</option>`).join('');

    editCenterContent.innerHTML=`
      <div class="calc">
        <b>${scna}</b> kaydı düzenleniyor.
        <span class="small">Kaydetmeden önce program mantık kontrolleri yapacak.</span>
        <div style="margin-top:8px">
          ${Number(editCx.manual_lock||0)===1
            ? `<span class="badge" style="background:#dcfce7;color:#166534">MANUEL KORUMALI</span>
               <span class="small">Excel güncellemesi bu SCNA'nın üzerine yazamaz.</span>`
            : `<span class="badge">EXCEL GÜNCELLEMESİNE AÇIK</span>
               <span class="small">İlk manuel kayıtta otomatik korunacak.</span>`}
        </div>
      </div>

      <div class="grid" style="margin-top:14px">
        <div class="field"><label>Plaka</label><input id="ePlate" value="${editCx.plate||''}"></div>
        <div class="field"><label>Şoför</label><select id="eDriver"><option value="">Seçin</option>${drivers}</select></div>
        <div class="field"><label>Müşteri</label><select id="eCustomer"><option value="">Seçin</option>${customers}</select></div>
        <div class="field"><label>Bölge</label><select id="eArea"><option value="">Seçin</option>${areas}</select></div>

        <div class="field"><label>Mal Cinsi</label><select id="eCargo"><option value="">Seçin</option>${cargos}</select></div>
        <div class="field"><label>Yük Tipi</label><select id="eCargoType"><option>BULK</option><option>BAG</option></select></div>
        <div class="field"><label>Sevkiyat Tarihi</label><input id="eDate" type="date" value="${editCx.trip_date||''}"></div>
        <div class="field"><label>Durum</label><select id="eStatus"><option>Bekliyor</option><option>Yolda</option><option>Tamamlandı</option></select></div>

        <div class="field"><label>Net KG</label><input id="eKg" type="number" value="${editCx.net_kg||0}"></div>
        <div class="field"><label>Navlun Birim Fiyat</label><input id="eRate" type="text" inputmode="decimal" value="${editCx.freight_rate||0}"></div>
        <div class="field"><label>Navlun Bazı</label><select id="eBasis"><option>KG</option><option>TON</option></select></div>
        <div class="field"><label>Çıkış KM</label><input id="eExitKm" type="number" value="${editCx.exit_km||0}"></div>

        <div class="field"><label>Başlangıç Depo Mazot</label><input id="eTankStart" type="number" value="${editCx.tank_start_liters||0}"></div>
        <div class="field"><label>Prim</label><input id="ePremium" type="text" inputmode="decimal" value="${editCx.exit_premium||0}"></div>
        <div class="field"><label>Dock Fee</label><input id="eDock" type="text" inputmode="decimal" value="${editCx.dock_fee||0}"></div>
        <div class="field"><label>Port Fee</label><input id="ePort" type="text" inputmode="decimal" value="${editCx.port_fee||0}"></div>

        <div class="field"><label>SONAR</label><input id="eSonar" type="text" inputmode="decimal" value="${editCx.sonar||0}"></div>
        <div class="field"><label>Harcırah</label><input id="eAllowance" type="text" inputmode="decimal" value="${editCx.exit_allowance||0}"></div>
        <div class="field"><label>Çıkış Diğer</label><input id="eOther" type="text" inputmode="decimal" value="${editCx.exit_other||0}"></div>
        <div class="field"><label>Giriş KM</label><input id="eEntryKm" type="number" value="${editCx.entry_km||0}"></div>

        <div class="field"><label>Dönüş Depoda Kalan LT</label><input id="eTankEnd" type="number" value="${editCx.tank_end_liters||0}"></div>
        <div class="field"><label>Ekstra Gider 1</label><input id="eExtra1" type="text" inputmode="decimal" value="${editCx.entry_extra_expense_1||0}"></div>
        <div class="field"><label>Ekstra Gider 2</label><input id="eExtra2" type="text" inputmode="decimal" value="${editCx.entry_extra_expense_2||0}"></div>
        <div class="field"><label>Ekstra Gider 3</label><input id="eExtra3" type="text" inputmode="decimal" value="${editCx.entry_extra_expense_3||0}"></div>

        <div class="field"><label>Müşteriden Alınan Para</label><input id="eCollection" type="text" inputmode="decimal" value="${editCx.entry_collection||0}"></div>
        <div class="field"><label>Şoförün Verdiği Para</label><input id="eHand" type="text" inputmode="decimal" value="${editCx.entry_cash_handed||0}"></div>
        <div class="field wide"><label>Not</label><textarea id="eNote">${editCx.entry_note||''}</textarea></div>
      </div>

      <div id="editValidation" class="calc" style="display:none;margin-top:12px"></div>

      <div class="compact-actions" style="margin-top:14px">
        <button class="btn green" onclick="validateAndSaveEdit()">Kontrol Et ve Kaydet</button>
        ${Number(editCx.manual_lock||0)===1
          ? `<button class="btn secondary" onclick="toggleManualLock(false)">Excel Korumasını Kaldır</button>`
          : `<button class="btn secondary" onclick="toggleManualLock(true)">Excel Korumasını Aç</button>`}
        <button class="btn orange" onclick="undoEntryEdit()">Giriş İşlemini Geri Al</button>
        <button class="btn secondary" onclick="undoExitEdit()">Çıkış İşlemini Geri Al</button>
      </div>
    `;

    eDriver.value=editCx.driver_id||'';
    eCustomer.value=editCx.customer_id||'';
    eArea.value=editCx.area_id||'';
    eCargo.value=editCx.cargo_category_id||'';
    eCargoType.value=editCx.cargo_type||'BULK';
    eBasis.value=editCx.freight_basis||'KG';
    eStatus.value=editCx.status||'Bekliyor';

  }catch(e){
    editCenterContent.innerHTML='<div class="calc"><b style="color:#991b1b">'+e.message+'</b></div>';
  }
}

function editPayload(){
  return {
    plate:ePlate.value,
    driver_id:eDriver.value?Number(eDriver.value):null,
    area_id:eArea.value?Number(eArea.value):null,
    cargo_category_id:eCargo.value?Number(eCargo.value):null,
    cargo_type:eCargoType.value,
    customer_id:eCustomer.value?Number(eCustomer.value):null,
    trip_date:eDate.value,
    net_kg:Number(eKg.value||0),
    freight_rate:parseMoney(eRate.value),
    freight_basis:eBasis.value,
    exit_km:Number(eExitKm.value||0),
    tank_start_liters:Number(eTankStart.value||0),
    exit_premium:parseMoney(ePremium.value),
    dock_fee:parseMoney(eDock.value),
    port_fee:parseMoney(ePort.value),
    sonar:parseMoney(eSonar.value),
    exit_allowance:parseMoney(eAllowance.value),
    exit_other:parseMoney(eOther.value),
    entry_km:Number(eEntryKm.value||0),
    tank_end_liters:Number(eTankEnd.value||0),
    entry_extra_expense_1:parseMoney(eExtra1.value),
    entry_extra_expense_2:parseMoney(eExtra2.value),
    entry_extra_expense_3:parseMoney(eExtra3.value),
    entry_collection:parseMoney(eCollection.value),
    entry_cash_handed:parseMoney(eHand.value),
    status:eStatus.value,
    note:eNote.value
  };
}


async function toggleManualLock(lockIt){
  const scna=(editScna.value||'').trim().toUpperCase();
  if(!scna) return;
  if(!lockIt){
    if(!confirm(scna+' için Excel koruması kaldırılacak. Sonraki Excel Güncelle işleminde bu kayıt değişebilir. Emin misin?')) return;
  }
  try{
    await api('/api/trips/'+encodeURIComponent(scna)+(lockIt?'/manual-lock':'/manual-unlock'),{method:'POST'});
    await loadEditCenter();
  }catch(e){
    alert(e.message);
  }
}

async function validateAndSaveEdit(){
  const scna=(editScna.value||'').trim().toUpperCase();
  if(!scna) return;
  const payload=editPayload();

  try{
    const v=await api('/api/trips/'+encodeURIComponent(scna)+'/validate',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });

    editValidation.style.display='block';

    if(v.errors && v.errors.length){
      editValidation.innerHTML='<b style="color:#991b1b">Kayıt engellendi:</b><br>'+v.errors.join('<br>');
      return;
    }

    if(v.warnings && v.warnings.length){
      editValidation.innerHTML='<b style="color:#9a3412">Uyarılar:</b><br>'+v.warnings.join('<br>')+
        '<br><br><button class="btn orange" onclick="saveEditConfirmed()">Uyarıya Rağmen Kaydet</button>';
      return;
    }

    await saveEditConfirmed();
  }catch(e){
    alert(e.message);
  }
}

async function saveEditConfirmed(){
  const scna=(editScna.value||'').trim().toUpperCase();
  const payload=editPayload();
  try{
    const r=await api('/api/trips/'+encodeURIComponent(scna),{
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    editValidation.style.display='block';
    editValidation.innerHTML='<b style="color:#166534">Kayıt güncellendi ve Excel güncellemelerine karşı korumaya alındı.</b>';
    await loadEditCenter();
  }catch(e){
    alert(e.message);
  }
}

async function undoEntryEdit(){
  const scna=(editScna.value||'').trim().toUpperCase();
  if(!confirm(scna+' giriş işlemi geri alınacak. Emin misin?')) return;
  await api('/api/trips/'+encodeURIComponent(scna)+'/undo-entry',{method:'POST'});
  await loadEditCenter();
}

async function undoExitEdit(){
  const scna=(editScna.value||'').trim().toUpperCase();
  if(!confirm(scna+' çıkış + giriş + yolda mazot kayıtları geri alınacak. Emin misin?')) return;
  await api('/api/trips/'+encodeURIComponent(scna)+'/undo-exit',{method:'POST'});
  await loadEditCenter();
}

async function loadScnaDetail(){
  const scna=(detailScna.value||'').trim().toUpperCase();
  if(!scna) return;
  try{
    const d=await api('/api/scna-detail/'+encodeURIComponent(scna));
    const x=d.trip;

    let html=`
      <div class="detail-grid">
        <div class="detail-box"><span>SCNA</span><strong>${x.scna}</strong></div>
        <div class="detail-box"><span>Plaka</span><strong>${x.plate||''}</strong></div>
        <div class="detail-box"><span>Şoför</span><strong>${x.driver_name||''}</strong></div>
        <div class="detail-box"><span>Durum</span><strong>${x.status||''}</strong></div>

        <div class="detail-box"><span>Müşteri</span><strong>${x.customer_name||''}</strong></div>
        <div class="detail-box"><span>Bölge</span><strong>${x.area_name||''}</strong></div>
        <div class="detail-box"><span>Mal / Tip</span><strong>${x.cargo_name||''} ${x.cargo_type_name||''}</strong></div>
        <div class="detail-box"><span>Net KG</span><strong>${money(x.net_kg)}</strong></div>

        <div class="detail-box"><span>Toplam Navlun</span><strong>${money(x.freight_total)}</strong></div>
        <div class="detail-box"><span>Müşteriden Alınan</span><strong>${money(x.entry_collection)}</strong></div>
        <div class="detail-box"><span>Müşteriden Kalan</span><strong>${money(x.amount_due)}</strong></div>
        <div class="detail-box"><span>Şoförün Vermesi Gereken</span><strong>${money(x.expected_cash_handover)}</strong></div>

        <div class="detail-box"><span>Çıkış</span><strong>${fmtDateTime(x.exit_at)}</strong></div>
        <div class="detail-box"><span>Giriş</span><strong>${fmtDateTime(x.entry_at)}</strong></div>
        <div class="detail-box"><span>Gerçek KM</span><strong>${money(x.actual_km)}</strong></div>
        <div class="detail-box"><span>LT / 100 KM</span><strong>${money(x.liters_per_100km)}</strong></div>

        <div class="detail-box"><span>Toplam Gider</span><strong>${money(x.total_expense)}</strong></div>
        <div class="detail-box"><span>Sefer Kârı</span><strong>${money(x.trip_profit)}</strong></div>
        <div class="detail-box"><span>Şoför Para Farkı</span><strong>${money(x.driver_cash_diff)}</strong></div>
        <div class="detail-box"><span>Sefer Süresi (Saat)</span><strong>${money(x.trip_duration_hours)}</strong></div>
      </div>`;

    html+=`<div class="table"><table><thead><tr>
      <th>YOLDA MAZOT LT</th><th>TOPLAM</th><th>BİRİM</th><th>NOT</th><th>TARİH</th>
    </tr></thead><tbody>`;

    if(d.fuels.length){
      d.fuels.forEach(f=>{
        html+=`<tr><td>${money(f.liters)}</td><td>${money(f.total)}</td>
          <td>${money(Number(f.total||0)/Number(f.liters||1))}</td>
          <td>${f.note||''}</td><td>${f.created_at||''}</td></tr>`;
      });
    }else{
      html+='<tr><td colspan="5">Yolda mazot kaydı yok.</td></tr>';
    }
    html+='</tbody></table></div>';

    html+=`<div class="table" style="margin-top:14px"><table><thead><tr>
      <th>TARİH</th><th>İŞLEM</th><th>DETAY</th>
    </tr></thead><tbody>`;

    if(d.logs.length){
      d.logs.forEach(l=>{
        html+=`<tr><td>${l.created_at||''}</td><td>${l.action||''}</td><td>${l.detail||''}</td></tr>`;
      });
    }else{
      html+='<tr><td colspan="3">İşlem geçmişi yok.</td></tr>';
    }
    html+='</tbody></table></div>';

    detailContent.innerHTML=html;
  }catch(e){
    detailContent.innerHTML='<div class="calc"><b style="color:#991b1b">'+e.message+'</b></div>';
  }
}


function switchPanel(id){
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
  const p=document.getElementById(id);
  if(p) p.classList.add('active');
  document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));
}

function openVehicleCardFrom(plate){
  switchPanel('vehiclecard');
  vehicleCardPlate.value=plate;
  loadVehicleCard();
}

function openDriverCardFrom(name){
  switchPanel('drivercard');
  driverCardName.value=name;
  loadDriverCard();
}

async function loadVehicleCard(){
  const plate=(vehicleCardPlate.value||'').trim().toUpperCase();
  if(!plate) return;

  try{
    const d=await api('/api/vehicle-card/'+encodeURIComponent(plate));
    const v=d.vehicle,s=d.summary,m=d.maintenance;

    let html=`
      <div class="detail-grid">
        <div class="detail-box"><span>Plaka</span><strong>${v.plate||''}</strong></div>
        <div class="detail-box"><span>Son / Aktif Sefer Şoförü</span><strong>${v.driver_name||''}</strong></div>
        <div class="detail-box"><span>Telefon</span><strong>${v.phone||''}</strong></div>
        <div class="detail-box"><span>D.No</span><strong>${v.d_no||''}</strong></div>

        <div class="detail-box"><span>Toplam Sefer</span><strong>${s.trip_count||0}</strong></div>
        <div class="detail-box"><span>Tamamlanan</span><strong>${s.completed_count||0}</strong></div>
        <div class="detail-box"><span>Toplam Ton</span><strong>${money(s.total_ton)}</strong></div>
        <div class="detail-box"><span>Toplam KM</span><strong>${money(s.total_km)}</strong></div>

        <div class="detail-box"><span>Ort. LT/100</span><strong>${money(s.avg_l100)}</strong></div>
        <div class="detail-box"><span>Toplam Navlun</span><strong>${money(s.total_freight)}</strong></div>
        <div class="detail-box"><span>Toplam Kâr</span><strong>${money(s.total_profit)}</strong></div>
        <div class="detail-box"><span>Sonraki Bakım</span><strong>${m?money(m.next_service_km):''}</strong></div>
      </div>`;

    if(m){
      html+=`<div class="calc"><b>Bakım:</b>
        Son bakım ${money(m.last_service_km)} KM |
        Sonraki bakım ${money(m.next_service_km)} KM |
        Yağ ${money(m.oil_change_km)} KM
        <br><span class="small">${m.note||''}</span>
      </div>`;
    }

    html+=`<div class="table" style="margin-top:14px"><table><thead><tr>
      <th>SCNA</th><th>TARİH</th><th>ŞOFÖR</th><th>BÖLGE</th><th>KG</th>
      <th>KM</th><th>LT/100</th><th>NAVLUN</th><th>KÂR</th><th>DURUM</th>
    </tr></thead><tbody>`;

    d.trips.forEach(x=>{
      html+=`<tr>
        <td><b>${x.scna}</b></td>
        <td>${x.trip_date||''}</td>
        <td>${x.driver_name||''}</td>
        <td>${x.area_name||''}</td>
        <td>${money(x.net_kg)}</td>
        <td>${money(x.actual_km)}</td>
        <td>${money(x.liters_per_100km)}</td>
        <td>${money(x.freight_total)}</td>
        <td>${money(x.trip_profit)}</td>
        <td>${x.status||''}</td>
      </tr>`;
    });

    html+='</tbody></table></div>';
    vehicleCardContent.innerHTML=html;
  }catch(e){
    vehicleCardContent.innerHTML='<div class="calc"><b style="color:#991b1b">'+e.message+'</b></div>';
  }
}

async function loadDriverCard(){
  const name=(driverCardName.value||'').trim();
  if(!name) return;

  try{
    const d=await api('/api/driver-card/'+encodeURIComponent(name));
    const x=d.driver,s=d.summary;

    let html=`
      <div class="detail-grid">
        <div class="detail-box"><span>Şoför</span><strong>${x.name||''}</strong></div>
        <div class="detail-box"><span>Telefon</span><strong>${x.phone||''}</strong></div>
        <div class="detail-box"><span>D.No</span><strong>${x.d_no||''}</strong></div>
        <div class="detail-box"><span>Kullandığı Araçlar</span><strong>${(d.plates||[]).join(', ')}</strong></div>

        <div class="detail-box"><span>Toplam Sefer</span><strong>${s.trip_count||0}</strong></div>
        <div class="detail-box"><span>Tamamlanan</span><strong>${s.completed_count||0}</strong></div>
        <div class="detail-box"><span>Aktif Sefer</span><strong>${s.active_trips||0}</strong></div>
        <div class="detail-box"><span>Toplam Ton</span><strong>${money(s.total_ton)}</strong></div>

        <div class="detail-box"><span>Toplam KM</span><strong>${money(s.total_km)}</strong></div>
        <div class="detail-box"><span>Ort. LT/100</span><strong>${money(s.avg_l100)}</strong></div>
        <div class="detail-box"><span>Toplam Para Farkı</span><strong>${money(s.cash_diff)}</strong></div>
      </div>`;

    html+=`<div class="table"><table><thead><tr>
      <th>SCNA</th><th>PLAKA</th><th>TARİH</th><th>BÖLGE</th><th>KG</th>
      <th>KM</th><th>LT/100</th><th>ŞOFÖR FARK</th><th>DURUM</th>
    </tr></thead><tbody>`;

    d.trips.forEach(t=>{
      const cls=Number(t.driver_cash_diff||0)<0?'class="alert-red"':'';
      html+=`<tr ${cls}>
        <td><b>${t.scna}</b></td>
        <td>${t.plate||''}</td>
        <td>${t.trip_date||''}</td>
        <td>${t.area_name||''}</td>
        <td>${money(t.net_kg)}</td>
        <td>${money(t.actual_km)}</td>
        <td>${money(t.liters_per_100km)}</td>
        <td>${money(t.driver_cash_diff)}</td>
        <td>${t.status||''}</td>
      </tr>`;
    });

    html+='</tbody></table></div>';
    driverCardContent.innerHTML=html;
  }catch(e){
    driverCardContent.innerHTML='<div class="calc"><b style="color:#991b1b">'+e.message+'</b></div>';
  }
}

let anomalyCache={fuel:[],km:[],cash:[],repeated_driver_cash:[]};


let dailyCache=null;

function localISODate(d=new Date()){
  const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),da=String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${da}`;
}
function dailyToday(){
  dailyDate.value=localISODate();
  loadDailySummary();
}
async function loadDailySummary(){
  const day=dailyDate.value||localISODate();
  dailyCache=await api('/api/daily-manager-summary?day='+encodeURIComponent(day));
  const d=dailyCache;
  dailyExited.innerText=d.exited||0;
  dailyEntered.innerText=d.entered||0;
  dailyOnroad.innerText=d.onroad||0;
  dailyDelayed.innerText=d.delayed||0;
  dailyTon.innerText=money(d.ton);
  dailyFreight.innerText=money(d.freight);
  dailyCollected.innerText=money(d.collected);
  dailyCost.innerText=money(d.cost);
  dailyProfit.innerText=money(d.profit);
  dailyDriverDiff.innerText=money(d.driver_diff);

  let h=`<div class="table"><table><thead><tr>
    <th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>BÖLGE</th><th>DURUM</th>
    <th>ÇIKIŞ</th><th>GİRİŞ</th><th>KG</th><th>NAVLUN</th>
  </tr></thead><tbody>`;
  if(d.rows.length){
    d.rows.forEach(x=>{
      h+=`<tr><td><b>${x.scna}</b></td><td>${x.plate||''}</td><td>${x.driver_name||''}</td>
      <td>${x.area_name||''}</td><td>${x.status||''}</td><td>${fmtDateTime(x.exit_at)}</td>
      <td>${fmtDateTime(x.entry_display_at||x.entry_at||x.delivery_time)}</td><td>${money(x.net_kg)}</td><td>${money(x.freight_total)}</td></tr>`;
    });
  } else h+='<tr><td colspan="9" class="empty-state">Bu tarihte giriş/çıkış hareketi yok.</td></tr>';
  h+='</tbody></table></div>';
  dailyTable.innerHTML=h;
}

function exportDailyExcel(){
  if(!dailyCache){ alert('Önce raporu getir.'); return; }
  const d=dailyCache;
  const rows=[
    ['GÜN SONU YÖNETİCİ ÖZETİ',d.day],
    ['Çıkan Araç',d.exited],['Giren Araç',d.entered],['Şu An Yolda',d.onroad],
    ['Gecikmiş',d.delayed],['Toplam Ton',d.ton],['Navlun',d.freight],
    ['Tahsilat',d.collected],['Gider',d.cost],['Net Kâr',d.profit],
    ['Şoför Para Farkı',d.driver_diff],[],
    ['SCNA','PLAKA','ŞOFÖR','BÖLGE','DURUM','ÇIKIŞ','GİRİŞ','KG','NAVLUN']
  ];
  d.rows.forEach(x=>rows.push([
    x.scna,x.plate,x.driver_name,x.area_name,x.status,x.exit_at,x.entry_at,x.net_kg,x.freight_total
  ]));
  const ws=XLSX.utils.aoa_to_sheet(rows);
  const wb=XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb,ws,'GUN SONU');
  XLSX.writeFile(wb,'GUN_SONU_'+d.day+'.xlsx');
}

function printDailyReport(){
  if(!dailyCache){ alert('Önce raporu getir.'); return; }
  const w=window.open('','_blank');
  w.document.write(`<html><head><title>Gün Sonu ${dailyCache.day}</title>
  <style>body{font-family:Arial;padding:25px}h2{margin-bottom:5px}.cards{display:flex;flex-wrap:wrap;gap:10px;margin:15px 0}
  .card{border:1px solid #ddd;padding:10px;min-width:150px}.card b{display:block;font-size:18px;margin-top:5px}
  table{width:100%;border-collapse:collapse;font-size:11px}th,td{border:1px solid #bbb;padding:6px;text-align:left}
  th{background:#eee}</style></head><body>
  <h2>Gün Sonu / Yönetici Özeti</h2><div>${dailyCache.day}</div>${dailyReport.innerHTML}</body></html>`);
  w.document.close();
  setTimeout(()=>w.print(),300);
}

async function loadAnomalies(){
  anomalyCache=await api('/api/anomalies');
  anFuelCount.innerText=anomalyCache.fuel.length;
  anKmCount.innerText=anomalyCache.km.length;
  anCashCount.innerText=anomalyCache.cash_total_count ?? anomalyCache.cash.length;
  anDriverCount.innerText=anomalyCache.repeated_driver_cash.length;
  renderAnomalies();
}

function renderAnomalies(){
  const type=anomalyType.value||'all';
  let html='';

  const renderTable=(title,rows,kind)=>{
    html+=`<div class="table" style="margin-top:14px"><table><thead><tr>
      <th colspan="7">${title}</th></tr><tr>
      <th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>BÖLGE</th>
      <th>GERÇEK</th><th>REFERANS</th><th>SAPMA</th>
    </tr></thead><tbody>`;

    if(rows.length){
      rows.forEach(x=>{
        html+=`<tr class="${kind==='cash'?'alert-red':'alert-orange'}">
          <td><b>${x.scna||''}</b></td>
          <td>${x.plate||''}</td>
          <td>${x.driver_name||''}</td>
          <td>${x.area_name||''}</td>
          <td>${money(x.value)}</td>
          <td>${money(x.baseline)}</td>
          <td>${kind==='cash'?(x.source||''):('%'+money(x.deviation))}</td>
        </tr>`;
      });
    }else{
      html+='<tr><td colspan="7">Kayıt yok.</td></tr>';
    }
    html+='</tbody></table></div>';
  };

  if(type==='all' || type==='fuel') renderTable('YAKIT ANORMALLİKLERİ',anomalyCache.fuel,'fuel');
  if(type==='all' || type==='km') renderTable('KM ANORMALLİKLERİ',anomalyCache.km,'km');
  if(type==='all' || type==='cash'){
    renderTable('ŞOFÖR PARA EKSİKLERİ',anomalyCache.cash,'cash');
    if((anomalyCache.cash_total_count||0)>(anomalyCache.cash||[]).length){
      html+=`<div class="calc"><b>Toplam ${(anomalyCache.cash_total_count||0)} para eksiği kaydı var.</b>
      Performans için tabloda en yüksek 500 kayıt gösteriliyor.</div>`;
    }
  }

  if(type==='all' || type==='driver'){
    html+=`<div class="table" style="margin-top:14px"><table><thead><tr>
      <th>TEKRARLAYAN ŞOFÖR PARA EKSİĞİ</th><th>SON KONTROL</th><th>EKSİK SAYISI</th>
    </tr></thead><tbody>`;
    if(anomalyCache.repeated_driver_cash.length){
      anomalyCache.repeated_driver_cash.forEach(x=>{
        html+=`<tr class="alert-red">
          <td><b>${x.driver_name||''}</b></td>
          <td>${x.checked_count||0} sefer</td>
          <td>${x.short_count||0}</td>
        </tr>`;
      });
    }else{
      html+='<tr><td colspan="3">Tekrarlayan şoför para eksiği bulunmadı.</td></tr>';
    }
    html+='</tbody></table></div>';
  }

  anomalyContent.innerHTML=html;
}

async function loadVehiclePerformance(){
  const d=await api('/api/performance/vehicles');
  let html=`<div class="table"><table><thead><tr>
    <th>PLAKA</th><th>SEFER</th><th>TAMAMLANAN</th><th>TON</th><th>TOPLAM KM</th>
    <th>ORT. LT/100</th><th>TOPLAM NAVLUN</th><th>TOPLAM KÂR</th>
  </tr></thead><tbody>`;
  d.forEach(x=>{
    html+=`<tr>
      <td><b class="perf-key">${x.plate||''}</b></td>
      <td>${x.trip_count||0}</td>
      <td>${x.completed_count||0}</td>
      <td>${money(x.total_ton)}</td>
      <td>${money(x.total_km)}</td>
      <td>${money(x.avg_l100)}</td>
      <td>${money(x.total_freight)}</td>
      <td>${money(x.total_profit)}</td>
    </tr>`;
  });
  html+='</tbody></table></div>';
  performanceContent.innerHTML=html;
  renderPerformanceFilter();
}


function renderPerformanceFilter(){
  const qv=(document.getElementById('perfQ')?.value||'').toLowerCase();
  document.querySelectorAll('#performanceContent tbody tr').forEach(tr=>{
    const key=(tr.querySelector('.perf-key')?.textContent||'').toLowerCase();
    tr.style.display=!qv || key.includes(qv)?'':'none';
  });
}

async function loadDriverPerformance(){
  const d=await api('/api/performance/drivers');
  let html=`<div class="table"><table><thead><tr>
    <th>ŞOFÖR</th><th>SEFER</th><th>TAMAMLANAN</th><th>TON</th><th>TOPLAM KM</th>
    <th>ORT. LT/100</th><th>TOPLAM NAVLUN</th><th>PARA FARKI</th>
  </tr></thead><tbody>`;
  d.forEach(x=>{
    let cls=Number(x.cash_diff||0)<0?'alert-red':Number(x.cash_diff||0)>0?'style="background:#dcfce7;color:#166534;font-weight:800"':'';
    html+=`<tr>
      <td><b class="perf-key">${x.driver_name||''}</b></td>
      <td>${x.trip_count||0}</td>
      <td>${x.completed_count||0}</td>
      <td>${money(x.total_ton)}</td>
      <td>${money(x.total_km)}</td>
      <td>${money(x.avg_l100)}</td>
      <td>${money(x.total_freight)}</td>
      <td ${cls}>${money(x.cash_diff)}</td>
    </tr>`;
  });
  html+='</tbody></table></div>';
  performanceContent.innerHTML=html;
  renderPerformanceFilter();
}



function financeParams(){
  const f=finFrom.value||'';
  const t=finTo.value||'';
  return 'date_from='+encodeURIComponent(f)+'&date_to='+encodeURIComponent(t);
}


function setFinancePreset(type){
  const now=new Date();
  const iso=d=>d.toISOString().slice(0,10);
  let from=new Date(now),to=new Date(now);
  if(type==='month') from=new Date(now.getFullYear(),now.getMonth(),1);
  if(type==='year') from=new Date(now.getFullYear(),0,1);
  finFrom.value=iso(from);
  finTo.value=iso(to);
  loadFinance();
}

function clearFinanceDates(){
  finFrom.value='';
  finTo.value='';
  loadFinance();
}

async function loadFinance(){
  const s=await api('/api/finance-summary?'+financeParams());

  finFreight.innerText=money(s.total_freight);
  finCost.innerText=money(s.total_cost);
  finProfit.innerText=money(s.total_profit);
  finMargin.innerText='%'+money(s.margin_percent);
  finTon.innerText=money(s.total_ton);

  finFuel.innerText=money(s.fuel_cost);
  finOther.innerText=money(s.other_cost);
  finKm.innerText=money(s.total_km);
  finProfitKm.innerText=money(s.profit_per_km);
  finProfitTon.innerText=money(s.profit_per_ton);

  finTrips.innerText=s.trip_count||0;
  finCollected.innerText=money(s.collected);
  finReceivable.innerText=money(s.receivable);

  const profitCard=finProfit.closest('.card');
  profitCard.classList.remove('diff-red','diff-green');
  if(Number(s.total_profit||0)<0) profitCard.classList.add('diff-red');
  else if(Number(s.total_profit||0)>0) profitCard.classList.add('diff-green');

  await loadFinanceTable('customer');
}

async function loadFinanceTable(type){
  let url='/api/finance-by-customer';
  let first='MÜŞTERİ';

  if(type==='area'){
    url='/api/finance-by-area';
    first='BÖLGE';
  }else if(type==='cargo'){
    url='/api/finance-by-cargo';
    first='MAL CİNSİ';
  }

  const d=await api(url+'?'+financeParams());

  let html=`<div class="table"><table><thead><tr>
    <th>${first}</th><th>SEFER</th><th>TON</th>`;
  if(type==='area') html+='<th>TOPLAM KM</th>';
  html+='<th>NAVLUN</th><th>GİDER</th><th>NET KÂR</th><th>KÂR MARJI</th></tr></thead><tbody>';

  d.forEach(x=>{
    const margin=Number(x.freight||0)>0?(Number(x.profit||0)/Number(x.freight))*100:0;
    const cls=Number(x.profit||0)<0?'class="alert-red"':'';
    html+=`<tr ${cls}>
      <td><b>${x.name||''}</b></td>
      <td>${x.trip_count||0}</td>
      <td>${money(x.total_ton)}</td>`;
    if(type==='area') html+=`<td>${money(x.total_km)}</td>`;
    html+=`
      <td>${money(x.freight)}</td>
      <td>${money(x.cost)}</td>
      <td>${money(x.profit)}</td>
      <td>%${money(margin)}</td>
    </tr>`;
  });

  html+='</tbody></table></div>';
  financeTable.innerHTML=html;
}

async function loadFinanceMonthly(){
  const d=await api('/api/finance-monthly');
  let html=`<div class="table"><table><thead><tr>
    <th>AY</th><th>SEFER</th><th>TON</th><th>NAVLUN</th><th>GİDER</th><th>NET KÂR</th><th>MARJ</th>
  </tr></thead><tbody>`;

  d.forEach(x=>{
    const margin=Number(x.freight||0)>0?(Number(x.profit||0)/Number(x.freight))*100:0;
    html+=`<tr ${Number(x.profit||0)<0?'class="alert-red"':''}>
      <td><b>${x.month||''}</b></td>
      <td>${x.trip_count||0}</td>
      <td>${money(x.total_ton)}</td>
      <td>${money(x.freight)}</td>
      <td>${money(x.cost)}</td>
      <td>${money(x.profit)}</td>
      <td>%${money(margin)}</td>
    </tr>`;
  });

  html+='</tbody></table></div>';
  financeTable.innerHTML=html;
}


let opCache={summary:{},rows:[]};
let routeLearnCache=[];
let opPerfCache={vehicles:[],drivers:[]};

async function loadOperationCenter(){
  const [op,routes,perf]=await Promise.all([
    api('/api/operation-center'),
    api('/api/route-learning'),
    api('/api/operation-performance')
  ]);
  opCache=op;
  routeLearnCache=routes;
  opPerfCache=perf;

  opTotal.innerText=op.summary.total||0;
  opOnRoad.innerText=op.summary.onroad||0;
  opWaiting.innerText=op.summary.waiting||0;
  opDelayed.innerText=op.summary.delayed||0;
  opTodayExit.innerText=op.summary.today_exit||0;
  opTodayEntry.innerText=op.summary.today_entry||0;

  renderOperationCenter();
  renderRouteLearning();
  renderOpPerformance('vehicle');
}

function renderOperationCenter(){
  const qv=(document.getElementById('opQ')?.value||'').toLowerCase();
  const state=document.getElementById('opState')?.value||'';

  const rows=(opCache.rows||[]).filter(x=>{
    const hay=[x.scna,x.plate,x.driver_name,x.area_name].join(' ').toLowerCase();
    if(qv&&!hay.includes(qv)) return false;
    if(state==='Gecikmiş'&&!x.delayed) return false;
    if(state&&state!=='Gecikmiş'&&x.status!==state) return false;
    return true;
  });

  opRows.innerHTML='';
  if(!rows.length){
    opRows.innerHTML='<tr><td colspan="12" class="empty-state">Bu filtrede aktif operasyon yok.</td></tr>';
    return;
  }

  rows.forEach(x=>{
    const refHours=Number(x.route_avg_hours||x.expected_hours||0);
    let warning='';
    if(x.delayed){
      warning='<span class="badge short">GECİKMİŞ</span>';
    }else if(x.status==='Yolda'){
      warning='<span class="badge warn">YOLDA</span>';
    }

    opRows.innerHTML+=`<tr class="${x.delayed?'alert-red':''}">
      <td><b>${x.scna}</b></td>
      <td><button class="quick-btn" onclick="openVehicleCardFrom('${x.plate}')">${x.plate||''}</button></td>
      <td>${x.driver_name?`<button class="quick-btn" onclick="openDriverCardFrom('${String(x.driver_name).replace(/'/g,"\\'")}')">${x.driver_name}</button>`:''}</td>
      <td>${x.area_name||''}</td>
      <td>${x.status||''}</td>
      <td>${fmtDateTime(x.exit_at)}</td>
      <td>${money(x.hours_on_road)}</td>
      <td>${money(refHours)}</td>
      <td>${money(x.route_avg_km||x.expected_km||0)}</td>
      <td>${money(x.route_avg_l100||x.expected_l100||0)}</td>
      <td>${x.completed_trips||0}</td>
      <td>${warning}</td>
    </tr>`;
  });
}

function renderRouteLearning(){
  const qv=(document.getElementById('routeLearnQ')?.value||'').toLowerCase();
  const rows=routeLearnCache.filter(x=>!qv||String(x.area_name||'').toLowerCase().includes(qv));
  routeLearnRows.innerHTML='';
  if(!rows.length){
    routeLearnRows.innerHTML='<tr><td colspan="6" class="empty-state">Rota geçmişi bulunamadı.</td></tr>';
    return;
  }
  rows.forEach(x=>{
    routeLearnRows.innerHTML+=`<tr>
      <td><b>${x.area_name||''}</b></td>
      <td>${x.trip_count||0}</td>
      <td>${money(x.avg_km)}</td>
      <td>${money(x.avg_hours)}</td>
      <td>${money(x.avg_l100)}</td>
      <td>${money(x.avg_cost)}</td>
    </tr>`;
  });
}

function renderOpPerformance(type){
  const rows=type==='driver'?(opPerfCache.drivers||[]):(opPerfCache.vehicles||[]);
  const first=type==='driver'?'ŞOFÖR':'PLAKA';
  let h=`<div class="table"><table><thead><tr>
    <th>${first}</th><th>SEFER</th><th>TOPLAM KM</th><th>ORT. LT/100</th><th>ORT. SEFER SÜRESİ</th>
  </tr></thead><tbody>`;
  if(!rows.length){
    h+='<tr><td colspan="5" class="empty-state">Performans verisi yok.</td></tr>';
  }else{
    rows.forEach(x=>{
      h+=`<tr>
        <td><b>${x.name||''}</b></td>
        <td>${x.trip_count||0}</td>
        <td>${money(x.total_km)}</td>
        <td>${money(x.avg_l100)}</td>
        <td>${money(x.avg_hours)}</td>
      </tr>`;
    });
  }
  h+='</tbody></table></div>';
  opPerformanceContent.innerHTML=h;
}


let liveCache={summary:{},rows:[]};



let fleetManageData=[];
let driverManageData=[];

async function loadFleetManage(){
  const d=await api('/api/fleet/vehicles');fleetManageData=d.rows||[];
  fmTotal.innerText=d.total||0;fmActive.innerText=d.active||0;fmPassive.innerText=d.passive||0;
  renderFleetManage();
}
function renderFleetManage(){
  if(!document.getElementById('fleetManageRows'))return;
  const q=(fleetManageQ.value||'').toLocaleUpperCase('tr-TR'),s=fleetManageState.value;
  const a=fleetManageData.filter(x=>(s===''||String(x.is_active)===s)&&(!q||[x.plate,x.brand,x.model,x.vehicle_type,x.current_driver,x.note].some(v=>String(v||'').toLocaleUpperCase('tr-TR').includes(q))));
  fleetManageRows.innerHTML=a.map(x=>`<tr><td><b>${x.plate}</b></td><td>${x.brand||''}</td><td>${x.model||''}</td><td>${x.vehicle_type||''}</td><td>${x.current_driver||''}</td><td>${x.garage_state||''}</td><td>${x.is_active?'AKTİF':'PASİF'}</td><td>${x.note||''}</td><td><button class="btn secondary" onclick="openFleetVehicle('${x.plate}')">Düzenle</button> <button class="btn ${x.is_active?'orange':'green'}" onclick="toggleFleetVehicle('${x.plate}',${x.is_active?0:1})">${x.is_active?'Pasife Al':'Aktif Et'}</button></td></tr>`).join('');
  if(typeof v54InitTables==='function')v54InitTables();
}
function openFleetVehicle(plate=''){
  const x=fleetManageData.find(z=>z.plate===plate)||{plate:'',brand:'',model:'',vehicle_type:'DAMPER',is_active:1,garage_state:'GARAGE',note:''};
  openM(plate?'Araç Düzenle':'Yeni Araç',`<div class="grid">
  <div class="field"><label>Plaka</label><input id="fvPlate" value="${x.plate||''}" ${plate?'readonly':''}></div>
  <div class="field"><label>Marka</label><input id="fvBrand" value="${x.brand||''}"></div>
  <div class="field"><label>Model</label><input id="fvModel" value="${x.model||''}"></div>
  <div class="field"><label>Araç Tipi</label><select id="fvType"><option ${x.vehicle_type==='DAMPER'?'selected':''}>DAMPER</option><option ${x.vehicle_type==='TANKER'?'selected':''}>TANKER</option><option ${x.vehicle_type==='TRAILER'?'selected':''}>TRAILER</option><option ${x.vehicle_type==='OTHER'?'selected':''}>OTHER</option></select></div>
  <div class="field"><label>Garaj Durumu</label><select id="fvGarage"><option value="GARAGE" ${x.garage_state==='GARAGE'?'selected':''}>GARAGE</option><option value="DISARIDA" ${x.garage_state==='DISARIDA'?'selected':''}>DIŞARIDA</option><option value="BAKIM" ${x.garage_state==='BAKIM'?'selected':''}>BAKIM</option></select></div>
  <div class="field"><label>Aktif</label><select id="fvActive"><option value="1" ${x.is_active?'selected':''}>AKTİF</option><option value="0" ${!x.is_active?'selected':''}>PASİF</option></select></div>
  <div class="field wide"><label>Not</label><input id="fvNote" value="${String(x.note||'').replace(/"/g,'&quot;')}"></div></div>`,
  async()=>{await api('/api/fleet/vehicles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plate:fvPlate.value,brand:fvBrand.value,model:fvModel.value,vehicle_type:fvType.value,is_active:Number(fvActive.value),garage_state:fvGarage.value,note:fvNote.value})});closeM();await loadFleetManage();await loadFleetOps();});
}
async function toggleFleetVehicle(plate,active){
  await api('/api/fleet/vehicles/'+encodeURIComponent(plate)+'/active',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({is_active:active})});
  await loadFleetManage();await loadFleetOps();
}

async function loadDriverManage(){
  const d=await api('/api/fleet/drivers');driverManageData=d.rows||[];
  dmTotal.innerText=d.total||0;dmActive.innerText=d.active||0;dmPassive.innerText=d.passive||0;
  renderDriverManage();
}
function renderDriverManage(){
  if(!document.getElementById('driverManageRows'))return;
  const q=(driverManageQ.value||'').toLocaleUpperCase('tr-TR'),s=driverManageState.value;
  const a=driverManageData.filter(x=>(s===''||String(x.is_active)===s)&&(!q||[x.name,x.phone,x.d_no,x.last_plate,x.note].some(v=>String(v||'').toLocaleUpperCase('tr-TR').includes(q))));
  driverManageRows.innerHTML=a.map(x=>`<tr><td><b>${x.name}</b></td><td>${x.phone||''}</td><td>${x.d_no||''}</td><td>${x.last_plate||''}</td><td>${x.is_active?'AKTİF':'PASİF'}</td><td>${x.note||''}</td><td><button class="btn secondary" onclick="openFleetDriver(${x.id})">Düzenle</button> <button class="btn ${x.is_active?'orange':'green'}" onclick="toggleFleetDriver(${x.id},${x.is_active?0:1})">${x.is_active?'Pasife Al':'Aktif Et'}</button></td></tr>`).join('');
  if(typeof v54InitTables==='function')v54InitTables();
}
function openFleetDriver(id=0){
  const x=driverManageData.find(z=>z.id===id)||{name:'',phone:'',d_no:'',is_active:1,note:''};
  openM(id?'Şoför Düzenle':'Yeni Şoför',`<div class="grid">
  <div class="field"><label>Ad Soyad</label><input id="fdName" value="${String(x.name||'').replace(/"/g,'&quot;')}"></div>
  <div class="field"><label>Telefon</label><input id="fdPhone" value="${x.phone||''}"></div>
  <div class="field"><label>D.No</label><input id="fdNo" value="${x.d_no||''}"></div>
  <div class="field"><label>Aktif</label><select id="fdActive"><option value="1" ${x.is_active?'selected':''}>AKTİF</option><option value="0" ${!x.is_active?'selected':''}>PASİF</option></select></div>
  <div class="field wide"><label>Not</label><input id="fdNote" value="${String(x.note||'').replace(/"/g,'&quot;')}"></div></div>`,
  async()=>{await api('/api/fleet/drivers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:fdName.value,phone:fdPhone.value,d_no:fdNo.value,is_active:Number(fdActive.value),note:fdNote.value})});closeM();await loadDriverManage();});
}
async function toggleFleetDriver(id,active){
  await api('/api/fleet/drivers/'+id+'/active',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({is_active:active})});
  await loadDriverManage();
}

let fleetData=[];
async function loadFleetOps(){
 const d=await api('/api/fleet-operations');fleetData=d.rows||[];const c=d.counts||{};
 if(document.getElementById('fleetTotal')){fleetTotal.innerText=c.TOPLAM||0;fleetEmpty.innerText=c.BOS||0;fleetLoaded.innerText=c.DOLU||0;fleetWaiting.innerText=c.SIRA||0;fleetLoading.innerText=c.YUKLEMEDE||0;}
 renderFleetOps();renderVesselOps();
}
function fleetLabel(s){return {BOS:'BOŞ',DOLU:'DOLU',SIRA:'SIRA BEKLİYOR',YUKLEMEDE:'YÜKLEMEDE'}[s]||s;}
function fleetFiltered(q,state){q=(q||'').trim().toLocaleUpperCase('tr-TR');return fleetData.filter(x=>!state||x.load_state===state).filter(x=>!q||[x.plate,x.driver,x.scna,x.area,x.vessel,x.operation_note].some(v=>String(v||'').toLocaleUpperCase('tr-TR').includes(q)));}
function renderFleetOps(){
 if(!document.getElementById('fleetRows'))return;const a=fleetFiltered(fleetQ.value,fleetState.value);
 fleetRows.innerHTML=a.map(x=>`<tr><td><b>${x.load_state==='SIRA'?(x.queue_no||'-'):'-'}</b></td><td><b>${x.plate}</b></td><td>${fleetLabel(x.load_state)}</td><td>${x.driver||''}</td><td>${x.scna||''}</td><td>${x.area||''}</td><td>${x.vessel||''}</td><td>${x.operation_note||''}</td><td><button class="btn secondary" onclick="editFleetOp('${x.plate}')">Durum Değiştir</button></td></tr>`).join('');
 if(typeof v54InitTables==='function')v54InitTables();
}
function vesselOpState(x){
  // Gemi atanmış ve araç operasyon dışı olarak işaretlenmemişse çalışıyor kabul edilir.
  return x.load_state==='CIKTI' ? 'CIKTI' : 'CALISIYOR';
}
function renderVesselOps(){
  if(!document.getElementById('vesselRows'))return;

  const q=(vesselQ.value||'').trim().toLocaleUpperCase('tr-TR');
  const state=vesselState.value;
  let a=fleetData.filter(x=>{
    const s=vesselOpState(x);
    if(state && s!==state)return false;
    if(!q)return true;
    return [x.vessel,x.plate,x.driver,x.operation_note].some(v=>
      String(v||'').toLocaleUpperCase('tr-TR').includes(q)
    );
  });

  const working=fleetData.filter(x=>vesselOpState(x)==='CALISIYOR' && String(x.vessel||'').trim()).length;
  const out=fleetData.filter(x=>vesselOpState(x)==='CIKTI').length;
  const unassigned=fleetData.filter(x=>!String(x.vessel||'').trim()).length;
  if(document.getElementById('vesselWorkingCount'))vesselWorkingCount.innerText=working;
  if(document.getElementById('vesselOutCount'))vesselOutCount.innerText=out;
  if(document.getElementById('vesselUnassignedCount'))vesselUnassignedCount.innerText=unassigned;

  const groups={};
  fleetData.filter(x=>vesselOpState(x)==='CALISIYOR' && String(x.vessel||'').trim())
    .forEach(x=>{const g=x.vessel.trim();groups[g]=(groups[g]||0)+1;});

  vesselSummary.innerHTML=Object.entries(groups)
    .sort((a,b)=>b[1]-a[1])
    .map(([g,n])=>`<div class="card">${g}<b>${n} araç</b></div>`).join('');

  vesselRows.innerHTML=a.map(x=>{
    const s=vesselOpState(x);
    return `<tr>
      <td><b>${x.vessel||'GEMİ ATANMADI'}</b></td>
      <td><b>${x.plate}</b></td>
      <td>${x.driver||''}</td>
      <td>${s==='CALISIYOR'?'GEMİDE ÇALIŞIYOR':'OPERASYONDAN ÇIKTI'}</td>
      <td>${x.operation_note||''}</td>
      <td><button class="btn secondary" onclick="editVesselAssignment('${x.plate}')">Düzenle</button></td>
    </tr>`;
  }).join('');

  if(typeof v54InitTables==='function')v54InitTables();
}

function editVesselAssignment(plate){
  const x=fleetData.find(z=>z.plate===plate)||{plate,vessel:'',load_state:'CALISIYOR',operation_note:''};
  const state=vesselOpState(x);

  openM('Gemi Operasyonu - '+plate,`<div class="grid">
    <div class="field"><label>Plaka</label><input id="voPlate" value="${plate}" readonly></div>
    <div class="field"><label>Gemi</label><input id="voVessel" value="${String(x.vessel||'').replace(/"/g,'&quot;')}" placeholder="Gemi adı"></div>
    <div class="field"><label>Durum</label><select id="voState">
      <option value="CALISIYOR" ${state==='CALISIYOR'?'selected':''}>GEMİDE ÇALIŞIYOR</option>
      <option value="CIKTI" ${state==='CIKTI'?'selected':''}>OPERASYONDAN ÇIKTI</option>
    </select></div>
    <div class="field wide"><label>Not</label><input id="voNote" value="${String(x.operation_note||'').replace(/"/g,'&quot;')}"></div>
  </div>`,
  async()=>{
    await api('/api/fleet-operations',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        plate:voPlate.value,
        load_state:voState.value,
        queue_no:0,
        vessel:voVessel.value,
        operation_note:voNote.value
      })
    });
    closeM();
    await loadFleetOps();
    await loadIntegratedFleetStatus();
    try{await loadTrips();}catch(e){}
  });
}

function editFleetOp(plate){
 const x=fleetData.find(z=>z.plate===plate)||{plate,load_state:'BOS',queue_no:0,vessel:'',operation_note:''};
 openM('Araç Operasyon Durumu - '+plate,`<div class="grid">
 <div class="field"><label>Plaka</label><input id="foPlate" value="${plate}" readonly></div>
 <div class="field"><label>Durum</label><select id="foState" onchange="foQueue.disabled=this.value!=='SIRA'"><option value="BOS" ${x.load_state==='BOS'?'selected':''}>BOŞ</option><option value="DOLU" ${x.load_state==='DOLU'?'selected':''}>DOLU</option><option value="SIRA" ${x.load_state==='SIRA'?'selected':''}>SIRA BEKLİYOR</option><option value="YUKLEMEDE" ${x.load_state==='YUKLEMEDE'?'selected':''}>YÜKLEMEDE</option></select></div>
 <div class="field"><label>Sıra No</label><input id="foQueue" type="number" min="0" value="${x.queue_no||0}" ${x.load_state==='SIRA'?'':'disabled'}></div>
 <div class="field"><label>Gemi</label><input id="foVessel" value="${String(x.vessel||'').replace(/"/g,'&quot;')}"></div>
 <div class="field wide"><label>Operasyon Notu</label><input id="foNote" value="${String(x.operation_note||'').replace(/"/g,'&quot;')}"></div></div>`,
 async()=>{await api('/api/fleet-operations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plate:foPlate.value,load_state:foState.value,queue_no:Number(foQueue.value||0),vessel:foVessel.value,operation_note:foNote.value})});closeM();await loadFleetOps();await loadIntegratedFleetStatus();try{await loadTrips();}catch(e){}});
}
async function resequenceFleet(){await api('/api/fleet-operations/resequence',{method:'POST'});await loadFleetOps();}

async function loadLiveOps(){
  const d=await api('/api/live-operations');
  liveCache=d;
  liveTotal.innerText=d.summary.total||0;
  liveOnRoad.innerText=d.summary.onroad||0;
  liveWaiting.innerText=d.summary.waiting||0;
  liveDelayed.innerText=d.summary.delayed||0;
  liveMaint.innerText=d.summary.maintenance_due||0;
  renderLiveOps();
}

function renderLiveOps(){
  const qv=(document.getElementById('liveQ')?.value||'').toLowerCase();
  const state=(document.getElementById('liveState')?.value||'');
  const rows=(liveCache.rows||[]).filter(x=>{
    const hay=[x.scna,x.plate,x.driver_name,x.area_name].join(' ').toLowerCase();
    if(qv && !hay.includes(qv)) return false;
    if(state==='Gecikmiş' && !x.delayed) return false;
    if(state && state!=='Gecikmiş' && x.status!==state) return false;
    return true;
  });

  liveRows.innerHTML='';
  if(!rows.length){
    liveRows.innerHTML='<tr><td colspan="9" class="empty-state">Bu filtrede kayıt yok.</td></tr>';
    return;
  }
  rows.forEach(x=>{
    const badge=x.delayed?'<span class="badge short">GECİKMİŞ</span>':
      (x.status==='Yolda'?'<span class="badge warn">YOLDA</span>':'');
    liveRows.innerHTML+=`<tr class="${x.delayed?'alert-red':''}">
      <td><b>${x.scna}</b></td><td>${x.plate||''}</td><td>${x.driver_name||''}</td>
      <td>${x.area_name||''}</td><td>${x.status||''}</td><td>${fmtDateTime(x.exit_at)}</td>
      <td>${money(x.hours_on_road)}</td><td>${money(x.expected_hours||0)}</td><td>${badge}</td></tr>`;
  });
}

let routeCache=[];

async function loadRouteStandards(){
  const d=await api('/api/route-standards');
  routeCache=d;
  renderRouteStandards();
}

function renderRouteStandards(){
  const qv=(document.getElementById('routeQ')?.value||'').toLowerCase();
  const d=routeCache.filter(x=>!qv || String(x.area_name||'').toLowerCase().includes(qv));
  routeRows.innerHTML='';
  if(!d.length){
    routeRows.innerHTML='<tr><td colspan="6" class="empty-state">Bu filtrede rota yok.</td></tr>';
    return;
  }
  d.forEach(x=>{
    routeRows.innerHTML+=`<tr>
      <td><b>${x.area_name||''}</b></td>
      <td><input id="rh_${x.area_id}" type="number" value="${x.expected_hours||0}" style="width:95px"></td>
      <td><input id="rk_${x.area_id}" type="number" value="${x.expected_km||0}" style="width:105px"></td>
      <td><input id="rl_${x.area_id}" type="number" value="${x.expected_l100||0}" style="width:95px"></td>
      <td><input id="rt_${x.area_id}" type="number" value="${x.tolerance_percent||0}" style="width:90px"></td>
      <td><button class="btn green" onclick="saveRoute(${x.area_id})">Kaydet</button></td></tr>`;
  });
}

async function saveRoute(areaId){
  try{
    await api('/api/route-standards',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        area_id:areaId,
        expected_hours:Number(document.getElementById('rh_'+areaId).value||0),
        expected_km:Number(document.getElementById('rk_'+areaId).value||0),
        expected_l100:Number(document.getElementById('rl_'+areaId).value||0),
        tolerance_percent:Number(document.getElementById('rt_'+areaId).value||0)
      })
    });
    loadRouteStandards();
  }catch(e){alert(e.message)}
}

let maintenanceCache=[];

async function loadMaintenance(){
  const d=await api('/api/maintenance');
  maintenanceCache=d;
  renderMaintenance();
}

function renderMaintenance(){
  const qv=(document.getElementById('maintQ')?.value||'').toLowerCase();
  const state=(document.getElementById('maintState')?.value||'');
  const d=maintenanceCache.filter(x=>{
    if(qv && !String(x.plate||'').toLowerCase().includes(qv)) return false;
    const km=Number(x.km_left||0);
    if(state==='due' && !(x.next_service_km>0 && km<=0)) return false;
    if(state==='soon' && !(x.next_service_km>0 && km>0 && km<=2000)) return false;
    if(state==='ok' && !(x.next_service_km<=0 || km>2000)) return false;
    return true;
  });
  maintRows.innerHTML='';
  if(!d.length){
    maintRows.innerHTML='<tr><td colspan="10" class="empty-state">Bu filtrede bakım kaydı yok.</td></tr>';
    return;
  }
  d.forEach(x=>{
    const km=Number(x.km_left||0);
    const cls=km<=0?'alert-red':(km<=2000?'alert-orange':'');
    maintRows.innerHTML+=`<tr class="${cls}">
      <td><b>${x.plate}</b></td><td>${money(x.current_km)}</td><td>${money(x.last_service_km)}</td>
      <td>${money(x.next_service_km)}</td><td>${x.next_service_km>0?money(x.km_left):''}</td>
      <td>${money(x.oil_change_km)}</td><td>${x.tire_note||''}</td><td>${x.brake_note||''}</td>
      <td>${x.engine_note||''}</td>
      <td><button class="btn secondary" onclick='openMaintenance(${JSON.stringify(x)})'>Düzenle</button></td></tr>`;
  });
}

function openMaintenance(x=null){
  const plates=(L.vehicles||[]).map(v=>`<option value="${v.plate}">${v.plate}</option>`).join('');
  openM(x?'Bakım Kaydı Düzenle':'Yeni Bakım Kaydı',`
    <div class="grid">
      <div class="field"><label>Plaka</label><select id="mPlate"><option value="">Seçin</option>${plates}</select></div>
      <div class="field"><label>Son Bakım KM</label><input id="mLast" type="number" value="${x?x.last_service_km||0:0}"></div>
      <div class="field"><label>Sonraki Bakım KM</label><input id="mNext" type="number" value="${x?x.next_service_km||0:0}"></div>
      <div class="field"><label>Yağ Değişim KM</label><input id="mOil" type="number" value="${x?x.oil_change_km||0:0}"></div>
      <div class="field"><label>Lastik</label><input id="mTire" value="${x?x.tire_note||'':''}"></div>
      <div class="field"><label>Fren</label><input id="mBrake" value="${x?x.brake_note||'':''}"></div>
      <div class="field"><label>Motor</label><input id="mEngine" value="${x?x.engine_note||'':''}"></div>
      <div class="field wide"><label>Not</label><textarea id="mNote">${x?x.note||'':''}</textarea></div>
    </div>
  `,async()=>{
    await api('/api/maintenance',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        plate:mPlate.value,last_service_km:Number(mLast.value||0),next_service_km:Number(mNext.value||0),
        oil_change_km:Number(mOil.value||0),tire_note:mTire.value,brake_note:mBrake.value,
        engine_note:mEngine.value,note:mNote.value
      })
    });
    closeM(); loadMaintenance();
  });
  if(x) mPlate.value=x.plate;
}

async function loadAlerts(){
  const d=await api('/api/alerts');
  alertDelayCount.innerText=d.delayed.length;
  alertFuelCount.innerText=d.fuel_alerts.length;

  let html=`<div class="calc">
    <b>Varsayılan kurallar:</b>
    Yolda 48 saati aşan sefer gecikmiş sayılır.
    Yakıt tüketimi aracın kendi geçmiş ortalamasının %20 üstüne çıkarsa uyarı oluşur.
  </div>`;

  html+=`<div class="table" style="margin-top:14px"><table><thead><tr>
    <th>GECİKMİŞ SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>BÖLGE</th><th>ÇIKIŞ</th><th>YOLDA SAAT</th>
  </tr></thead><tbody>`;
  if(d.delayed.length){
    d.delayed.forEach(x=>{
      html+=`<tr class="alert-red">
        <td><b>${x.scna}</b></td><td>${x.plate}</td><td>${x.driver_name||''}</td>
        <td>${x.area_name||''}</td><td>${fmtDateTime(x.exit_at)}</td><td>${money(x.hours_on_road)}</td>
      </tr>`;
    });
  }else{
    html+='<tr><td colspan="6">48 saati aşan yolda araç yok.</td></tr>';
  }
  html+='</tbody></table></div>';

  html+=`<div class="table" style="margin-top:14px"><table><thead><tr>
    <th>YAKIT UYARISI SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>SEFER LT/100</th><th>ARAÇ ORT.</th><th>FAZLA %</th>
  </tr></thead><tbody>`;
  if(d.fuel_alerts.length){
    d.fuel_alerts.forEach(x=>{
      html+=`<tr class="alert-orange">
        <td><b>${x.scna}</b></td><td>${x.plate}</td><td>${x.driver_name||''}</td>
        <td>${money(x.trip_l100)}</td><td>${money(x.avg_l100)}</td><td>%${money(x.percent_over)}</td>
      </tr>`;
    });
  }else{
    html+='<tr><td colspan="6">Yakıt anormalliği bulunmadı.</td></tr>';
  }
  html+='</tbody></table></div>';

  try{
    const rf=await api('/api/route-fuel-alerts');
    html+=`<div class="table" style="margin-top:14px"><table><thead><tr>
      <th>ROTA YAKIT UYARISI</th><th>PLAKA</th><th>ŞOFÖR</th><th>BÖLGE</th>
      <th>GERÇEK LT/100</th><th>HEDEF</th><th>TOLERANS %</th>
    </tr></thead><tbody>`;
    if(rf.length){
      rf.forEach(x=>{
        html+=`<tr class="alert-orange"><td><b>${x.scna}</b></td><td>${x.plate}</td>
          <td>${x.driver_name||''}</td><td>${x.area_name||''}</td><td>${money(x.actual_l100)}</td>
          <td>${money(x.expected_l100)}</td><td>%${money(x.tolerance_percent)}</td></tr>`;
      });
    }else html+='<tr><td colspan="7">Rota standardına göre yakıt uyarısı yok.</td></tr>';
    html+='</tbody></table></div>';
  }catch(e){}

  alertsContent.innerHTML=html;
}

async function loadAudit(){
  let d=await api('/api/audit');
  auditRows.innerHTML='';

  d.forEach(x=>{
    auditRows.innerHTML+=`
    <tr>
      <td>${x.created_at}</td>
      <td>${x.action}</td>
      <td>${x.scna}</td>
      <td>${x.detail||''}</td>
    </tr>`;
  });
  filterAuditRows();
}



function exportAllExcel(){
  window.location.href='/api/export-excel?mode=all';
}

function exportFilteredExcel(){
  const query=(document.getElementById('q')?.value||'');
  const status=(document.getElementById('statusFilter')?.value||'Tümü');
  window.location.href=
    '/api/export-excel?mode=filtered&q='+encodeURIComponent(query)+
    '&status='+encodeURIComponent(status);
}




async function repairFreightFromExcel(input){
  const file=input.files&&input.files[0];
  if(!file) return;

  if(!confirm('Excel AU/FREIGHT değerleri mevcut SCNA kayıtlarının navlun birim fiyatını düzeltecek. Devam edilsin mi?')){
    input.value=''; return;
  }

  const result=document.getElementById('excelResult');
  result.style.display='block';
  result.innerHTML='<b>FREIGHT değerleri Excel’den düzeltiliyor...</b>';

  try{
    const raw=await file.arrayBuffer();
    const r=await fetch('/api/repair-freight-from-excel',{
      method:'POST',
      headers:{'Content-Type':'application/octet-stream'},
      body:raw
    });
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'FREIGHT onarım hatası');

    let html='<b style="color:#166534">FREIGHT toplu onarım tamamlandı.</b><br>'+
      'Güncellenen: <b>'+d.updated+'</b>'+
      ' | Zaten doğru: <b>'+d.unchanged+'</b>'+
      ' | FREIGHT bulunamayan: <b>'+d.missing+'</b>'+
      ' | DB’de SCNA bulunamadı: <b>'+d.db_not_found+'</b>';

    if(d.samples&&d.samples.length){
      html+='<br><br><b>Örnek düzeltmeler:</b><br>'+
        d.samples.map(x=>x.scna+' | '+money(x.old_rate)+' → '+money(x.new_rate)+' | AMOUNT '+money(x.amount)).join('<br>');
    }

    result.innerHTML=html;
    try{ await loadAnomalies(); }catch(e){}
  }catch(e){
    result.innerHTML='<b style="color:#991b1b">'+e.message+'</b>';
  }finally{
    input.value='';
  }
}

async function repairRemainFromExcel(input){
  const file=input.files&&input.files[0];
  if(!file) return;

  if(!confirm('Excel REMAIN değerleri aynı SCNA kayıtlarına toplu olarak yazılacak. Devam edilsin mi?')){
    input.value='';
    return;
  }

  const result=document.getElementById('excelResult');
  result.style.display='block';
  result.innerHTML='<b>REMAIN değerleri Excel’den yeniden okunuyor...</b>';

  try{
    const raw=await file.arrayBuffer();
    const r=await fetch('/api/repair-remain-from-excel',{
      method:'POST',
      headers:{'Content-Type':'application/octet-stream'},
      body:raw
    });
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'REMAIN onarım hatası');

    let html='<b style="color:#166534">REMAIN toplu onarım tamamlandı.</b><br>'+
      'Sayfa: '+d.sheet+
      ' | Başlık satırı: '+d.header_row+
      ' | REMAIN kolonu: '+d.remain_column_index+
      ' | REMAIN okunan: <b>'+d.parsed+'</b>'+
      ' | DB güncellenen: <b>'+d.updated+'</b>'+
      ' | Excel’de REMAIN boş: <b>'+d.blank+'</b>'+
      ' | DB’de SCNA bulunamadı: <b>'+d.db_not_found+'</b>';

    if(!d.remain_header_found){
      html+='<br><b style="color:#9a3412">Uyarı:</b> REMAIN başlığı bulunamadı; eski format kolon fallback’i kullanıldı.';
    }

    if(d.samples&&d.samples.length){
      html+='<br><br><b>Örnek güncellenenler:</b><br>'+
        d.samples.map(x=>'Satır '+x.row+' | '+x.scna+' → '+money(x.remain)).join('<br>');
    }

    result.innerHTML=html;

    try{
      await loadAnomalies();
    }catch(e){}
  }catch(e){
    result.innerHTML='<b style="color:#991b1b">'+e.message+'</b>';
  }finally{
    input.value='';
  }
}

async function downloadImportErrors(){
  if(!lastImportFailedRecords.length){
    alert('Hatalı kayıt yok.');
    return;
  }

  const r=await fetch('/api/export-import-errors',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({failed_records:lastImportFailedRecords})
  });

  if(!r.ok){
    alert('Hata Excel dosyası oluşturulamadı.');
    return;
  }

  const blob=await r.blob();
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;
  a.download='EXCEL_AKTARIM_HATALARI.xlsx';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}



function toggleDirectOneDrive(){
  const p=document.getElementById('directOneDrivePanel');
  p.classList.toggle('open');
  const saved=localStorage.getItem('sama_direct_onedrive_url');
  if(saved) directOneDriveUrl.value=saved;
}

async function testDirectOneDrive(){
  const url=(directOneDriveUrl.value||'').trim();
  if(!url){alert('OneDrive linki gir.');return;}
  localStorage.setItem('sama_direct_onedrive_url',url);
  directOneDriveInfo.style.display='block';
  directOneDriveInfo.innerHTML='<b>OneDrive bağlantısı test ediliyor...</b>';

  try{
    const r=await fetch('/api/public-onedrive/preview',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({share_url:url})
    });
    const d=await r.json();
    if(!r.ok){
      const detail=d.detail||d;
      let msg=typeof detail==='string'?detail:(detail.message||JSON.stringify(detail));
      throw new Error(msg);
    }
    directOneDriveInfo.innerHTML=
      '<b style="color:#166534">BAĞLANTI BAŞARILI.</b><br>'+
      'Excel boyutu: '+money(d.size)+' byte'+
      ' | Sayfa: <b>'+d.sheet+'</b>'+
      ' | Yöntem: '+d.method+
      '<br><span class="small">Kaynak OneDrive dosyasına yazma yapılmadı.</span>';
  }catch(e){
    directOneDriveInfo.innerHTML=
      '<b style="color:#991b1b">Bağlantı kurulamadı:</b> '+e.message+
      '<br><span class="small">Dosya paylaşımını "Bağlantıya sahip herkes görüntüleyebilir" yapıp tekrar dene.</span>';
  }
}

async function syncDirectOneDrive(){
  const url=(directOneDriveUrl.value||'').trim();
  if(!url){alert('OneDrive linki gir.');return;}
  localStorage.setItem('sama_direct_onedrive_url',url);

  excelResult.style.display='block';
  excelResult.innerHTML='<b>OneDrive Web Excel okunuyor...</b>';

  try{
    const fr=await fetch('/api/public-onedrive/file',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({share_url:url})
    });

    if(!fr.ok){
      const d=await fr.json();
      const detail=d.detail||d;
      throw new Error(typeof detail==='string'?detail:(detail.message||JSON.stringify(detail)));
    }

    const blob=await fr.blob();
    const file=new File([blob],'WEB_EXCEL.xlsx',{
      type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    });
    lastExcelFile=file;

    const raw=await file.arrayBuffer();
    const r=await fetch(
      '/api/import-excel?filename=WEB_EXCEL.xlsx&update_existing=1&preview_only=1&skip_warnings=0',
      {
        method:'POST',
        headers:{'Content-Type':'application/octet-stream'},
        body:raw
      }
    );
    const data=await r.json();
    if(!r.ok) throw new Error(data.detail||'Web Excel önizleme hatası');

    lastExcelPreview=data;
    lastImportFailedRecords=data.failed_records||[];
    renderExcelPreview(data);

    excelResult.insertAdjacentHTML(
      'afterbegin',
      '<div class="calc" style="margin-bottom:8px"><b>Kaynak: ONEDRIVE PAYLAŞIM LİNKİ</b> '+
      '<span class="small">Excel yalnızca okundu. Kaynak dosya değiştirilmedi.</span></div>'
    );
  }catch(e){
    excelResult.innerHTML='<b style="color:#991b1b">OneDrive okuma hatası:</b> '+e.message;
  }
}

async function repairEntryDatesFromExcel(input){
  const file=input.files&&input.files[0];
  if(!file) return;

  if(!confirm(
    'Bu işlem Excel’den yalnızca SCNA, GİRİŞ TARİHİ ve eksikse GİRİŞ KM okuyacak. '+
    'Programda giriş tarihi boş olan kayıtları onaracak. Diğer alanlara ve kaynak Excel’e dokunmayacak. Devam edilsin mi?'
  )){
    input.value='';
    return;
  }

  const result=document.getElementById('excelResult');
  result.style.display='block';
  result.innerHTML='<b>Eksik giriş tarihleri kontrol ediliyor ve onarılıyor...</b>';

  try{
    const raw=await file.arrayBuffer();
    const r=await fetch('/api/repair-entry-dates-from-excel',{
      method:'POST',
      headers:{'Content-Type':'application/octet-stream'},
      body:raw
    });
    const d=await r.json();

    if(!r.ok) throw new Error(d.detail||'Giriş tarihi onarım hatası');

    let html='<b style="color:#166534">Giriş tarihi onarımı tamamlandı.</b><br>'+
      'Excel’de giriş tarihi olan: <b>'+d.excel_dates+'</b>'+
      ' | DB’de zaten doğru: <b>'+d.already_ok+'</b>'+
      ' | Onarılan: <b>'+d.repaired+'</b>'+
      ' | DB’de SCNA bulunamadı: <b>'+d.db_missing+'</b>'+
      ' | Son kontrolde hâlâ eksik: <b style="color:'+
        (d.verify_missing_count?'#991b1b':'#166534')+'">'+d.verify_missing_count+'</b>';

    if(d.repaired_rows&&d.repaired_rows.length){
      html+='<br><br><b>Onarılan kayıtlar:</b>'+
        '<div style="max-height:300px;overflow:auto;margin-top:6px;border:1px solid #bbf7d0;border-radius:8px;padding:8px">';
      html+=d.repaired_rows.map(x=>
        '<div class="small"><b>'+x.scna+'</b> → '+fmtDateTime(x.entry_date)+
        (x.entry_km?' | Giriş KM '+money(x.entry_km):' | Giriş KM Excel’de boş')+
        (x.was_manual_lock?' | <b>Manuel korumalıydı, yalnızca eksik giriş bilgisi dolduruldu</b>':'')+
        '</div>'
      ).join('');
      html+='</div>';
    }

    if(d.verify_missing&&d.verify_missing.length){
      html+='<br><br><b style="color:#991b1b">Hâlâ giriş tarihi eksik kalan SCNA:</b>'+
        '<div style="max-height:220px;overflow:auto;margin-top:6px;border:1px solid #fecaca;border-radius:8px;padding:8px">';
      html+=d.verify_missing.map(x=>
        '<div class="small">Satır '+x.row+' | <b>'+x.scna+'</b> | Excel '+x.excel_date+'</div>'
      ).join('');
      html+='</div>';
    }

    result.innerHTML=html;

    L=await api('/api/lookups');
    tripPage=1;
    await loadTrips();
    await loadDash();

  }catch(e){
    result.innerHTML='<b style="color:#991b1b">'+e.message+'</b>';
  }finally{
    input.value='';
  }
}

async function importExcel(input){
  const file=input.files && input.files[0];
  if(!file) return;

  lastExcelFile=file;
  const result=document.getElementById('excelResult');
  result.style.display='block';
  result.innerHTML='<b>Excel kontrol ediliyor...</b><br><span class="small">Yeni SCNA eklenecek, mevcut SCNA güncellenecek, manuel korumalı kayıtlar değiştirilmeyecek. Henüz kayıt yapılmıyor.</span>';

  try{
    const raw=await file.arrayBuffer();
    const r=await fetch(
      '/api/import-excel?filename='+encodeURIComponent(file.name)+
      '&update_existing=1'+
      '&preview_only=1',
      {
        method:'POST',
        headers:{'Content-Type':'application/octet-stream'},
        body:raw
      }
    );

    const data=await r.json();
    if(!r.ok) throw new Error(data.detail || 'Excel önizleme hatası');

    lastExcelPreview=data;
    lastImportFailedRecords=data.failed_records||[];
    renderExcelPreview(data);

  }catch(e){
    result.innerHTML='<b style="color:#991b1b">Excel kontrolü başarısız:</b> '+e.message;
  }finally{
    input.value='';
  }
}

function renderExcelPreview(data){
  const result=document.getElementById('excelResult');
  const c=data.preview_counts||{};

  let html=`
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">
      <b>Excel Kontrol Merkezi</b>
      <span class="badge">Okunan: ${data.processed||0}</span>
      <span class="badge" style="background:#dcfce7;color:#166534">Temiz: ${c.clean||0}</span>
      <span class="badge" style="background:#ffedd5;color:#9a3412">Uyarı: ${c.warning||0}</span>
      <span class="badge" style="background:#fee2e2;color:#991b1b">Hatalı: ${c.error||0}</span>
      <span class="badge">Mükerrer: ${c.duplicate||0}</span>
      <span class="badge">Güncellenecek: ${c.update||0}</span>
      <span class="badge">REMAIN okunan: ${data.remain_updated||0}</span>
      <span class="badge">REMAIN boş/yok: ${data.remain_missing||0}</span>
    </div>

    <div class="filterbar" style="margin-top:10px">
      <select id="previewStatusFilter" onchange="renderPreviewRows()">
        <option value="all">Tüm Önizleme</option>
        <option value="problem">Sadece Sorunlular</option>
        <option value="HATALI">Sadece Hatalı</option>
        <option value="UYARI">Sadece Uyarı</option>
                <option value="MANUEL KORUMALI">Sadece Manuel Korumalı</option>
      </select>
      <span class="small"><b>Uyarılar kayıt aktarımını engellemez.</b> Yalnızca gerçek hatalı satırlar durdurulur.</span>
      <button class="btn green" onclick="confirmExcelImport()">Onayla ve Aktar</button>
      <button class="btn secondary" onclick="cancelExcelPreview()">İptal</button>
      ${(data.failed_records||[]).length?'<button class="btn orange" onclick="downloadImportErrors()">Hatalı SCNA Listesini Excel İndir</button>':''}
    </div>

    <div id="previewRowsArea"></div>
  `;

  result.innerHTML=html;
  renderPreviewRows();
}

function renderPreviewRows(){
  if(!lastExcelPreview) return;
  const mode=document.getElementById('previewStatusFilter')?.value||'all';

  let rows=[];
  if(mode==='problem'){
    rows=lastExcelPreview.problem_records||[];
  }else if(mode==='all'){
    rows=lastExcelPreview.preview_records||[];
  }else{
    const base=(mode==='HATALI'||mode==='UYARI'||mode==='MÜKERRER'||mode==='MANUEL KORUMALI')
      ? (lastExcelPreview.problem_records||[])
      : (lastExcelPreview.preview_records||[]);
    rows=base.filter(x=>x.status===mode);
  }

  let h=`<div class="table"><table><thead><tr>
    <th>SATIR</th><th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>MÜŞTERİ</th>
    <th>BÖLGE</th><th>MAL</th><th>KG</th><th>PRICE (K)</th><th>FREIGHT (AU)</th><th>AMOUNT</th>
    <th>COLLECTION</th><th>REMAIN</th><th>GİRİŞ TARİHİ</th><th>ÇIKIŞ KM</th><th>GİRİŞ KM</th>
    <th>SONUÇ</th><th>UYARI / HATA</th>
  </tr></thead><tbody>`;

  if(!rows.length){
    h+='<tr><td colspan="18" class="empty-state">Bu filtrede kayıt yok.</td></tr>';
  }else{
    rows.forEach(x=>{
      let cls=x.status==='HATALI'?'alert-red':(x.status==='UYARI'?'alert-orange':'');
      h+=`<tr class="${cls}">
        <td>${x.row||''}</td>
        <td><b>${x.scna||''}</b></td>
        <td>${x.plate||''}</td>
        <td>${x.driver||''}</td>
        <td>${x.customer||''}</td>
        <td>${x.area||''}</td>
        <td>${x.cargo||''}</td>
        <td>${money(x.kg)}</td>
        <td>${money(x.price)}</td>
        <td>${money(x.freight_rate)}</td>
        <td>${money(x.amount)}</td>
        <td>${money(x.collection)}</td>
        <td>${x.excel_remain===null||x.excel_remain===undefined?'':money(x.excel_remain)}</td>
        <td>${fmtDateTime(x.delivery_time)}</td>
        <td>${money(x.exit_km)}</td>
        <td>${money(x.entry_km)}</td>
        <td><b>${x.status||''}</b></td>
        <td>${(x.messages||[]).join('<br>')}</td>
      </tr>`;
    });
  }
  h+='</tbody></table></div>';
  previewRowsArea.innerHTML=h;
}

async function confirmExcelImport(){
  if(!lastExcelFile){
    alert('Excel dosyası bulunamadı. Tekrar seç.');
    return;
  }

  const skipWarnings=0;
  const result=document.getElementById('excelResult');
  result.innerHTML='<b>Onaylanan kayıtlar aktarılıyor...</b>';

  try{
    const raw=await lastExcelFile.arrayBuffer();
    const r=await fetch(
      '/api/import-excel?filename='+encodeURIComponent(lastExcelFile.name)+
      '&update_existing=1'+
      '&preview_only=0&skip_warnings='+skipWarnings,
      {
        method:'POST',
        headers:{'Content-Type':'application/octet-stream'},
        body:raw
      }
    );
    const data=await r.json();
    if(!r.ok) throw new Error(data.detail || 'Excel aktarım hatası');

    lastImportFailedRecords=data.failed_records||[];

    let html=
      '<b style="color:#166534">Excel aktarımı tamamlandı.</b><br>'+
      'Sayfa: '+data.sheet+
      ' | Okunan: <b>'+data.processed+'</b>'+
      ' | Eklenen: <b>'+data.added+'</b>'+
      ' | Güncellenen: <b>'+(data.updated||0)+'</b>'+
      ' | Eski mükerrer atlama: <b>'+data.skipped+'</b>'+
      ' | Manuel korunan: <b>'+(data.manual_protected_skipped||0)+'</b>'+
      ' | Uyarılı atlanan: <b>'+(data.warning_skipped||0)+'</b>'+
      ' | REMAIN okunan: <b>'+(data.remain_updated||0)+'</b>'+
      ' | REMAIN boş/yok: <b>'+(data.remain_missing||0)+'</b>'+
      ' | Excel dönüş tarihi: <b>'+(data.delivery_date_source_count||0)+'</b>'+
      ' | Başarıyla yazılan dönüş tarihi: <b>'+(data.delivery_date_written_count||0)+'</b>'+
      ' | Yazılamayan dönüş tarihi: <b style="color:'+
        ((data.delivery_date_not_written_count||0)>0?'#991b1b':'#166534')+'">'+
        (data.delivery_date_not_written_count||0)+'</b>'+
      ' | Geçersiz SCNA atlanan: <b>'+(data.invalid_scna_skipped||0)+'</b>'+
      ' | Excel içi mükerrer: <b>'+(data.excel_duplicate_count||0)+'</b>'+
      ' | Kaydedilemeyen: <b style="color:#991b1b">'+data.error_count+'</b>';

    if(data.failed_records && data.failed_records.length){
      html+='<br><br><b style="color:#991b1b">Kaydedilemeyen SCNA kayıtları:</b>';
      html+='<div style="max-height:260px;overflow:auto;margin-top:6px;border:1px solid #fecaca;border-radius:8px;padding:8px;background:#fff7f7">';
      html+=data.failed_records.map(x=>
        '<div class="small"><b>Satır '+x.row+'</b> | <b>SCNA: '+(x.scna||'BOŞ')+'</b> | '+x.reason+'</div>'
      ).join('');
      html+='</div><div style="margin-top:8px"><button class="btn orange" onclick="downloadImportErrors()">Hatalı SCNA Listesini Excel İndir</button></div>';
    }

    // Aynı Excel ile giriş tarihlerini ikinci kez çapraz kontrol et.
    try{
      const verifyRaw=await lastExcelFile.arrayBuffer();
      const vr=await fetch('/api/check-entry-dates-from-excel',{
        method:'POST',
        headers:{'Content-Type':'application/octet-stream'},
        body:verifyRaw
      });
      const vd=await vr.json();
      if(vr.ok){
        html+='<br><br><b>Giriş Tarihi Son Kontrol:</b> '+
          'Excel tarihli: <b>'+vd.excel_with_entry_date+'</b>'+
          ' | DB tarihli: <b>'+vd.db_with_entry_date+'</b>'+
          ' | DB’de tarihi eksik: <b style="color:'+(vd.missing_date_count?'#991b1b':'#166534')+'">'+vd.missing_date_count+'</b>';

        if(vd.missing_dates&&vd.missing_dates.length){
          html+='<div style="max-height:220px;overflow:auto;margin-top:6px;border:1px solid #fecaca;border-radius:8px;padding:8px">';
          html+=vd.missing_dates.map(x=>
            '<div class="small">Satır '+x.row+' | <b>'+x.scna+'</b> | Excel: '+x.excel_date+
            ' | DB: BOŞ | '+(x.manual_lock?'MANUEL KORUMALI':'')+'</div>'
          ).join('');
          html+='</div>';
        }
        result.innerHTML=html;
      }
    }catch(e){}

    result.innerHTML=html;
    L=await api('/api/lookups');
    tripPage=1;
    await loadTrips();
    await loadDash();

  }catch(e){
    result.innerHTML='<b style="color:#991b1b">Excel aktarımı başarısız:</b> '+e.message;
  }
}

function cancelExcelPreview(){
  lastExcelFile=null;
  lastExcelPreview=null;
  lastImportFailedRecords=[];
  const result=document.getElementById('excelResult');
  result.innerHTML='<span class="small">Excel aktarımı iptal edildi.</span>';
}

function newTripPlateDriverSync(){
  const p=document.getElementById('nPlate'), d=document.getElementById('nDriver');
  if(!p||!d)return;
  const v=(L.vehicles||[]).find(x=>String(x.plate||'').toUpperCase()===String(p.value||'').trim().toUpperCase());
  if(v && v.driver_name && !d.value) d.value=v.driver_name;
}

async function newTrip(){
  let ao=L.areas.map(a=>`<option value="${a.id}">${a.name}</option>`).join('');
  let co=L.cargo_categories.map(c=>`<option value="${c.id}">${c.name}</option>`).join('');
  let cu=L.customers.map(c=>`<option value="${c.id}">${c.name}</option>`).join('');

  openM('Yeni Sevkiyat',`
  <div class="grid">
    <div class="field"><label>SCNA</label><input id="nScna"></div>
    <div class="field"><label>Plaka</label><input id="nPlate" placeholder="En az 3 karakter yazın" oninput="newTripPlateDriverSync()"></div>
    <div class="field"><label>Şoför</label><input id="nDriver" placeholder="En az 3 karakter yazın"></div>
    <div class="field"><label>Bölge</label><select id="nArea"><option value="">Seçin</option>${ao}</select></div>

    <div class="field"><label>Taşınan Mal Cinsi</label><select id="nCargo"><option value="">Seçin</option>${co}</select></div>
    <div class="field"><label>Yük Tipi</label><select id="nCargoType"><option value="BULK">BULK</option><option value="BAG">BAG</option></select></div>
    <div class="field"><label>Müşteri</label><select id="nCustomer"><option value="">Seçin</option>${cu}</select></div>
    <div class="field"><label>Tarih</label><input id="nDate" type="date"></div>
    <div class="field"><label>Net KG</label><input id="nKg" type="number" oninput="calcFreight()"></div>

    <div class="field"><label>Navlun Birimi</label><select id="nBasis" onchange="calcFreight()"><option value="TON">TON</option><option value="KG">KG</option></select></div>
    <div class="field"><label>Navlun Birim Fiyat</label><input id="nRate" type="text" inputmode="decimal" oninput="calcFreight()"></div>

    <div class="field"><label>Çıkış KM</label><input id="nExitKm" type="number"></div>
    <div class="field"><label>Depodaki Mevcut Mazot (LT)</label><input id="nTankStart" type="number"></div>
    <div class="field"><label>Prim</label><input id="nPremium" type="text" inputmode="decimal"></div>
    <div class="field"><label>Dock Fee</label><input id="nDockFee" type="text" inputmode="decimal"></div>
    <div class="field"><label>Port Fee</label><input id="nPortFee" type="text" inputmode="decimal"></div>
    <div class="field"><label>SONAR</label><input id="nSonar" type="text" inputmode="decimal"></div>
  </div>

  <div class="calc">
    Toplam Navlun: <b id="nTotal">0</b>
  </div>
  `, async()=>{
    let v=L.vehicles.find(x=>String(x.plate||'').toUpperCase()===String(nPlate.value||'').trim().toUpperCase());
    let driverName=String(nDriver.value||'').trim();
    let driverVehicle=L.vehicles.find(x=>String(x.driver_name||'').toLocaleUpperCase('tr-TR')===driverName.toLocaleUpperCase('tr-TR'));
    let selectedDriverId=driverVehicle ? (driverVehicle.current_driver_id||driverVehicle.driver_id||null) : (v ? (v.current_driver_id||v.driver_id||null) : null);

    try{
      await api('/api/trips',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          scna:nScna.value.trim(),
          plate:nPlate.value,
          driver_id:selectedDriverId,
          area_id:nArea.value?Number(nArea.value):null,
          cargo_category_id:nCargo.value?Number(nCargo.value):null,
          cargo_type:nCargoType.value,
          customer_id:nCustomer.value?Number(nCustomer.value):null,
          trip_date:nDate.value,
          net_kg:parseQty(nKg.value),
          freight_rate:parseMoney(nRate.value),
          freight_basis:nBasis.value,
          exit_km:parseQty(nExitKm.value),
          tank_start_liters:parseQty(nTankStart.value),
          exit_premium:parseMoney(nPremium.value),
          dock_fee:parseMoney(nDockFee.value),
          port_fee:parseMoney(nPortFee.value),
          sonar:parseMoney(nSonar.value)
        })
      });

      closeM();
      loadTrips();

    }catch(e){
      alert(e.message);
    }
  });
}

function calcFreight(){
  let kg=parseQty(nKg.value);
  let rate=parseMoney(nRate.value);
  nTotal.innerText=money(nBasis.value==='KG'?kg*rate:(kg/1000)*rate);
}

async function openExit(scna){
  cx=await api('/api/trips/'+scna);

  openM('Çıkış / Yakıt - '+scna,`
  <div class="grid">
    <div class="field"><label>Plaka</label><input value="${cx.plate}" disabled></div>
    <div class="field"><label>Toplam Navlun</label><input value="${money(cx.freight_total)}" disabled></div>
    <div class="field"><label>Çıkış Tarihi / Saati</label><input value="${fmtDateTime(cx.exit_at)||'Çıkış kaydedilince otomatik oluşur'}" disabled></div>
    <div class="field"><label>Çıkış KM</label><input value="${money(cx.exit_km)}" disabled></div>

    <div class="field"><label>Şoföre Verilen Avans</label><input id="xCash" type="text" inputmode="decimal" value="${cx.exit_cash||0}"></div>
    <div class="field"><label>Çıkışta Depodaki Mevcut Mazot (LT)</label><input value="${money(cx.tank_start_liters)}" disabled></div>

    <div class="field"><label>Resmi Mazot (LT)</label><input id="xOffLt" type="number" value="${cx.exit_official_fuel_liters||0}" oninput="calcExitFuel()"></div>
    <div class="field"><label>Resmi Mazot Toplam Tutar</label><input id="xOffTotal" type="text" inputmode="decimal" value="${cx.exit_official_fuel_total||0}" oninput="calcExitFuel()"></div>

    <div class="field"><label>Ticari Mazot (LT)</label><input id="xComLt" type="number" value="${cx.exit_commercial_fuel_liters||0}" oninput="calcExitFuel()"></div>
    <div class="field"><label>Ticari Mazot Toplam Tutar</label><input id="xComTotal" type="text" inputmode="decimal" value="${cx.exit_commercial_fuel_total||0}" oninput="calcExitFuel()"></div>

    <div class="field"><label>Bağdat Mazotu (LT)</label><input id="xBagLt" type="number" value="${cx.exit_baghdad_fuel_liters||0}" oninput="calcExitFuel()"></div>
    <div class="field"><label>Bağdat Mazotu Toplam Tutar</label><input id="xBagTotal" type="text" inputmode="decimal" value="${cx.exit_baghdad_fuel_total||0}" oninput="calcExitFuel()"></div>

    <div class="field"><label>Harcırah</label><input id="xAllow" type="text" inputmode="decimal" value="${cx.exit_allowance||0}"></div>
    <div class="field"><label>Prim</label><input value="${money(cx.exit_premium)}" disabled></div>
    <div class="field"><label>Dock Fee</label><input value="${money(cx.dock_fee)}" disabled></div>
    <div class="field"><label>Port Fee</label><input value="${money(cx.port_fee)}" disabled></div>
    <div class="field"><label>SONAR</label><input value="${money(cx.sonar)}" disabled></div>
    <div class="field"><label>Diğer</label><input id="xOther" type="text" inputmode="decimal" value="${cx.exit_other||0}"></div>

    <div class="field wide"><label>Çıkış Notu</label><textarea id="xNote">${cx.exit_note||''}</textarea></div>
  </div>

  <div class="settle">
    <div>Çıkışta Depo<strong id="xTankStartShow">0 LT</strong></div>
    <div>Çıkışta Alınan Toplam<strong id="xBoughtLt">0 LT</strong></div>
    <div>Yola Çıkarken Toplam Yakıt<strong id="xAvailableStart">0 LT</strong></div>
    <div>Çıkış Mazot Maliyeti<strong id="xFuelCost">0</strong></div>
  </div>
  `, async()=>{
    try{
      await api('/api/trips/'+scna+'/exit',{
        method:'PATCH',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          exit_cash:parseMoney(xCash.value),

          exit_official_fuel_liters:parseQty(xOffLt.value),
          exit_official_fuel_total:parseMoney(xOffTotal.value),

          exit_commercial_fuel_liters:parseQty(xComLt.value),
          exit_commercial_fuel_total:parseMoney(xComTotal.value),

          exit_baghdad_fuel_liters:parseQty(xBagLt.value),
          exit_baghdad_fuel_total:parseMoney(xBagTotal.value),

          exit_allowance:parseMoney(xAllow.value),
          exit_other:parseMoney(xOther.value),
          exit_note:xNote.value
        })
      });

      closeM();
      loadExit();

    }catch(e){
      alert(e.message);
    }
  });

  calcExitFuel();
}

function calcExitFuel(){
  let tank=Number(cx.tank_start_liters||0);

  let offLt=parseQty(xOffLt.value);
  let comLt=parseQty(xComLt.value);
  let bagLt=parseQty(xBagLt.value);

  let bought=offLt+comLt+bagLt;

  let fuelCost=
    parseMoney(xOffTotal.value)+
    parseMoney(xComTotal.value)+
    parseMoney(xBagTotal.value);

  xTankStartShow.innerText=money(tank)+' LT';
  xBoughtLt.innerText=money(bought)+' LT';
  xAvailableStart.innerText=money(tank+bought)+' LT';
  xFuelCost.innerText=money(fuelCost);
}

async function openEntry(scna){
  cx=await api('/api/trips/'+scna);
  let fuels=await api('/api/trips/'+scna+'/fuel');

  openM('Giriş / Yakıt Tüketim / Hesap - '+scna,`
  <div class="grid">
    <div class="field"><label>Plaka</label><input value="${cx.plate}" disabled></div>
    <div class="field"><label>Toplam Navlun</label><input value="${money(cx.freight_total)}" disabled></div>
    <div class="field"><label>Çıkış Tarihi / Saati</label><input value="${fmtDateTime(cx.exit_at)}" disabled></div>
    <div class="field"><label>Giriş Tarihi / Saati</label><input value="${fmtDateTime(cx.entry_at)||'Giriş kaydedilince otomatik oluşur'}" disabled></div>
    <div class="field"><label>Çıkış KM</label><input id="gExit" value="${cx.exit_km}" disabled></div>

    <div class="field"><label>Giriş KM</label><input id="gKm" type="number" value="${cx.entry_km||0}" oninput="calcEntry()"></div>
    <div class="field"><label>Dönüşte Depoda Kalan Mazot (LT)</label><input id="gTankEnd" type="number" value="${cx.tank_end_liters||0}" oninput="calcEntry()"></div>

    <div class="field"><label>Ekstra Gider 1</label><input id="gExtra1" type="text" inputmode="decimal" value="${cx.entry_extra_expense_1||0}" oninput="calcEntry()"></div>
    <div class="field"><label>Ekstra Gider 2</label><input id="gExtra2" type="text" inputmode="decimal" value="${cx.entry_extra_expense_2||0}" oninput="calcEntry()"></div>
    <div class="field"><label>Ekstra Gider 3</label><input id="gExtra3" type="text" inputmode="decimal" value="${cx.entry_extra_expense_3||0}" oninput="calcEntry()"></div>
    <div class="field"><label>Müşteriden Alınan Para</label><input id="gCollect" type="text" inputmode="decimal" value="${cx.entry_collection||0}" oninput="calcEntry()"></div>
    <div class="field"><label>Şoförün Teslim Ettiği Para</label><input id="gHand" type="text" inputmode="decimal" value="${cx.entry_cash_handed||0}" oninput="calcEntry()"></div>

    <div class="field wide"><label>Giriş Notu</label><textarea id="gNote">${cx.entry_note||''}</textarea></div>
  </div>

  <h4>Yolda Alınan Ek Mazot</h4>

  <div class="grid">
    <div class="field"><label>Alınan Mazot (LT)</label><input id="fLit" type="number" oninput="calcRoadFuelPreview()"></div>
    <div class="field"><label>Ödenen Toplam Tutar</label><input id="fTotal" type="text" inputmode="decimal" oninput="calcRoadFuelPreview()"></div>
    <div class="field"><label>Programın Hesapladığı Birim Fiyat</label><input id="fUnitPreview" disabled></div>
    <div class="field wide"><label>Açıklama</label><input id="fNote"></div>
  </div>

  <div style="margin-top:10px">
    <button class="btn green" onclick="addFuel('${scna}')">+ Mazot Alımı Ekle</button>
  </div>

  <div id="fuelList" style="margin-top:12px">${fuelHtml(fuels)}</div>

  <div class="settle">
    <div>Gerçek KM<strong id="gActualKm">0</strong></div>
    <div>Toplam Kullanılabilir Yakıt<strong id="gFuelAvailable">0 LT</strong></div>
    <div>Tüketilen Yakıt<strong id="gConsumed">0 LT</strong></div>
    <div>Dönüşte Kalan<strong id="gTankEndShow">0 LT</strong></div>
  </div>

  <div class="settle">
    <div>100 KM Tüketim<strong id="gL100">0 LT</strong></div>
    <div>KM / LT<strong id="gKmPerLt">0</strong></div>
    <div>Yolda Alınan Mazot<strong id="gRoadFuel">0 LT</strong></div>
  </div>

  <div class="settle">
    <div>Toplam Gider<strong id="gTotalExpense">0</strong></div>
    <div>Sefer Kârı<strong id="gProfit">0</strong></div>
    <div>Müşteriden Kalan Alacak<strong id="gDue">0</strong></div>
    <div>Dönüş Harcamaları<strong id="gReturnSpend">0</strong></div>
  </div>

  <div id="driverExpectedBox" class="diff-box diff-green">
    ŞOFÖRÜN VERMESİ GEREKEN PARA
    <strong id="gExpected">0</strong>
    <span class="small">Toplam Navlun − Dönüş Harcamaları</span>
    <div class="small" id="gFormulaTrace" style="margin-top:8px"></div>
  </div>

  <div class="settle">
    <div>Şoförün Verdiği Para<strong id="gHandShow">0</strong></div>
    <div>Şoför Para Farkı<strong id="gDiffSmall">0</strong></div>
  </div>

  <div id="driverDiffBox" class="diff-box diff-neutral">
    ŞOFÖR PARA FARKI
    <strong id="gDiff">0</strong>
  </div>

  <div class="calc">
    Şoför Hesabı: <span id="gStatus"></span>
  </div>
  `, async()=>{
    try{
      await api('/api/trips/'+scna+'/entry',{
        method:'PATCH',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          entry_km:parseQty(gKm.value),
          tank_end_liters:parseQty(gTankEnd.value),

          entry_extra_expense_1:parseMoney(gExtra1.value),
          entry_extra_expense_2:parseMoney(gExtra2.value),
          entry_extra_expense_3:parseMoney(gExtra3.value),

          entry_collection:parseMoney(gCollect.value),
          entry_cash_handed:parseMoney(gHand.value),
          entry_note:gNote.value
        })
      });

      closeM();
      loadEntry();
      loadDash();

    }catch(e){
      alert(e.message);
    }
  });

  calcEntry();
}

function calcRoadFuelPreview(){
  let lt=parseQty(fLit.value);
  let total=parseMoney(fTotal.value);
  fUnitPreview.value=lt>0?money(total/lt):'0';
}

function fuelHtml(f){
  if(!f.length){
    return '<span class="small">Henüz yolda alınmış mazot kaydı yok.</span>';
  }

  return `
  <table class="mini">
    <thead>
      <tr><th>LT</th><th>TOPLAM</th><th>BİRİM FİYAT</th><th>NOT</th><th></th></tr>
    </thead>
    <tbody>
      ${f.map(x=>`
        <tr>
          <td>${money(x.liters)}</td>
          <td>${money(x.total)}</td>
          <td>${money(Number(x.total||0)/Number(x.liters||1))}</td>
          <td>${x.note||''}</td>
          <td>
            <button class="btn danger" onclick="delFuel(${x.id},'${x.scna}')">Sil</button>
          </td>
        </tr>
      `).join('')}
    </tbody>
  </table>`;
}

async function addFuel(scna){
  try{
    await api('/api/trips/'+scna+'/fuel',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        liters:parseQty(fLit.value),
        total:parseMoney(fTotal.value),
        note:fNote.value
      })
    });

    let f=await api('/api/trips/'+scna+'/fuel');
    fuelList.innerHTML=fuelHtml(f);

    fLit.value='';
    fTotal.value='';
    fUnitPreview.value='';
    fNote.value='';

    cx=await api('/api/trips/'+scna);
    calcEntry();

  }catch(e){
    alert(e.message);
  }
}

async function delFuel(id,scna){
  await api('/api/fuel/'+id,{method:'DELETE'});

  let f=await api('/api/trips/'+scna+'/fuel');
  fuelList.innerHTML=fuelHtml(f);

  cx=await api('/api/trips/'+scna);
  calcEntry();
}

function calcEntry(){
  let actualKm=Math.max(0,parseQty(gKm.value)-Number(gExit.value||0));

  let roadFuelLt=Number(cx.road_fuel_liters||0);
  let roadFuelTotal=Number(cx.road_fuel_total||0);

  let totalAvailable=
    Number(cx.tank_start_liters||0)+
    Number(cx.exit_official_fuel_liters||0)+
    Number(cx.exit_commercial_fuel_liters||0)+
    Number(cx.exit_baghdad_fuel_liters||0)+
    roadFuelLt;

  let endTank=parseQty(gTankEnd.value);
  let consumed=Math.max(0,totalAvailable-endTank);

  let l100=actualKm>0?(consumed/actualKm)*100:0;
  let kmPerLt=consumed>0?actualKm/consumed:0;

  let extra=
    parseMoney(gExtra1.value)+
    parseMoney(gExtra2.value)+
    parseMoney(gExtra3.value);

  let exitFuelCost=
    Number(cx.exit_official_fuel_total||0)+
    Number(cx.exit_commercial_fuel_total||0)+
    Number(cx.exit_baghdad_fuel_total||0);

  let totalFuelCost=exitFuelCost+roadFuelTotal;

  let totalExpense=
    totalFuelCost+
    Number(cx.exit_allowance||0)+
    Number(cx.exit_premium||0)+
    Number(cx.dock_fee||0)+
    Number(cx.exit_other||0)+
    extra;

  // Üç ayrı para:
  // 1) Toplam Navlun
  // 2) Müşteriden fiilen alınan para
  // 3) Şoförün şirkete vermesi gereken para
  let customerMoney=parseMoney(gCollect.value);
  let hand=parseMoney(gHand.value);

  // Dönüş harcamaları:
  // Yolda alınan mazot + Ekstra Gider 1/2/3.
  let returnSpend=roadFuelTotal+extra;

  // Şoförün vermesi gereken:
  // Müşteriden alınan para - dönüş harcamaları.
  let expected=customerMoney-returnSpend;
  let diff=hand-expected;

  // Müşteriden kalan alacak:
  // Toplam Navlun - müşteriden alınan para.
  let due=Number(cx.freight_total||0)-customerMoney;

  // Sefer kârı tüm gerçek giderleri içerir.
  let profit=Number(cx.freight_total||0)-totalExpense;

  gActualKm.innerText=money(actualKm);
  gFuelAvailable.innerText=money(totalAvailable)+' LT';
  gConsumed.innerText=money(consumed)+' LT';
  gTankEndShow.innerText=money(endTank)+' LT';

  gL100.innerText=money(l100)+' LT';
  gKmPerLt.innerText=money(kmPerLt);
  gRoadFuel.innerText=money(roadFuelLt)+' LT';

  gTotalExpense.innerText=money(totalExpense);
  gProfit.innerText=money(profit);
  gDue.innerText=money(due);
  gReturnSpend.innerText=money(returnSpend);
  gExpected.innerText=money(expected);
  gFormulaTrace.innerText=money(customerMoney)+' − '+money(returnSpend)+' = '+money(expected);
  gHandShow.innerText=money(hand);
  gDiffSmall.innerText=money(diff);
  gDiff.innerText=money(diff);

  driverExpectedBox.classList.remove('diff-red','diff-green','diff-neutral');
  if(expected>0){
    driverExpectedBox.classList.add('diff-green');
  }else if(expected<0){
    driverExpectedBox.classList.add('diff-red');
  }else{
    driverExpectedBox.classList.add('diff-neutral');
  }


  driverDiffBox.classList.remove('diff-red','diff-green','diff-neutral');

  if(diff<0){
    driverDiffBox.classList.add('diff-red');
    gStatus.innerHTML='<span class="badge short">EKSİK PARA</span>';
  }else if(diff>0){
    driverDiffBox.classList.add('diff-green');
    gStatus.innerHTML='<span class="badge over">FAZLA PARA</span>';
  }else{
    driverDiffBox.classList.add('diff-neutral');
    gStatus.innerHTML='<span class="badge ok">HESAP TAMAM</span>';
  }
}

function filterAuditRows(){
  const qv=(document.getElementById('auditQ')?.value||'').toLowerCase();
  document.querySelectorAll('#auditRows tr').forEach(tr=>{
    const txt=(tr.textContent||'').toLowerCase();
    tr.style.display=!qv || txt.includes(qv)?'':'none';
  });
}


init();
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML



if __name__ == "__main__":
    import uvicorn
    print("")
    print("=" * 60)
    print("SAMA TRACK BASLATILIYOR")
    print("Yerel adres : http://127.0.0.1:8000")
    print("Network     : http://BILGISAYAR_IP:8000")
    print("Otomatik yeniden yukleme: AKTIF")
    print("=" * 60)
    print("")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        reload_includes=["*.py"]
    )
