"""DONCHI 1.0 Enterprise — two-portal offline-first POS demonstration server.
Python 3.10+, FastAPI, SQLite. Not production hardened.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Request, Depends, Body
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get('DONCHI_DATA_DIR', os.environ.get('YEMPRO_DATA_DIR', BASE / 'data'))) # legacy key supported
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'yempro.sqlite3'
SECRETFILE = DATA / '.secret'
if not SECRETFILE.exists():
    SECRETFILE.write_text(secrets.token_hex(48), encoding='utf-8')
    try: os.chmod(SECRETFILE, 0o600)
    except OSError: pass
SECRET = SECRETFILE.read_text(encoding='utf-8').strip().encode()
TOKEN_TTL = 72 * 3600  # legacy API tokens, for old client compatibility
COOKIE_NAME = "yempro_session"
SESSION_TTL = 30 * 24 * 3600  # 30 days; renewed on each online application visit
LOCAL_TZ = ZoneInfo(os.environ.get('DONCHI_TZ', os.environ.get('YEMPRO_TZ','Asia/Tashkent')))
app = FastAPI(title='DONCHI Clean Start 1.1 API', version='5.1.1', docs_url=None, redoc_url=None)


def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def http(status, detail): raise HTTPException(status_code=status, detail=detail)

def sql_conn():
    con = sqlite3.connect(DB, timeout=20, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=20000')
    return con

@contextmanager
def connection(write=False):
    db = sql_conn()
    try:
        if write: db.execute('BEGIN IMMEDIATE')
        yield db
        if write: db.execute('COMMIT')
    except Exception:
        if write: db.execute('ROLLBACK')
        raise
    finally:
        db.close()

def allrows(db, query, params=()): return [dict(r) for r in db.execute(query, params).fetchall()]
def onerow(db, query, params=()):
    r = db.execute(query, params).fetchone()
    return dict(r) if r else None

def pwdhash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 350000)
    return f'pbkdf2_sha256$350000${salt.hex()}${digest.hex()}'

def checkpwd(password, hashed):
    try:
        alg, n, salt, digest = hashed.split('$')
        if alg != 'pbkdf2_sha256': return False
        check = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(n))
        return hmac.compare_digest(check, bytes.fromhex(digest))
    except (ValueError, TypeError): return False

def token_for(user):
    payload = {'u':user['id'], 'v':user.get('session_version',0), 'exp':int(time.time()) + TOKEN_TTL}
    blob = base64.urlsafe_b64encode(json.dumps(payload, separators=(',',':')).encode()).decode().rstrip('=')
    mac = hmac.new(SECRET, blob.encode(), hashlib.sha256).hexdigest()
    return f'{blob}.{mac}'

def parse_token(token):
    try:
        blob, mac = token.split('.')
        expected = hmac.new(SECRET, blob.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected): http(401,'Sessiya noto‘g‘ri')
        payload = json.loads(base64.urlsafe_b64decode(blob + '='*(-len(blob)%4)))
        if payload['exp'] < time.time(): http(401,'Sessiya muddati tugagan')
        return payload
    except (ValueError, KeyError, TypeError): http(401,'Sessiya noto‘g‘ri')

def origin_matches_request(request: Request, origin: str) -> bool:
    """Compare the browser Origin with the public Host, including proxy TLS.

    Render terminates HTTPS ahead of Uvicorn, which can see an internal HTTP
    scheme. Only a matching public host and port is accepted; unrelated
    origins, malformed values and HTTP origins for HTTPS are rejected.
    """
    from urllib.parse import urlsplit
    try:
        parsed = urlsplit(origin)
        if parsed.scheme not in ('https', 'http') or not parsed.netloc:
            return False
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return False
        host = request.headers.get('host', '').lower()
        if parsed.netloc.lower() != host:
            return False
        scheme = request.url.scheme
        return parsed.scheme == scheme or (scheme == 'http' and parsed.scheme == 'https')
    except (ValueError, TypeError):
        return False


async def get_user(request: Request):
    header = request.headers.get('Authorization','')
    if header.startswith('Bearer '):
        payload = parse_token(header[7:])  # legacy/automated integrations
    else:
        raw = request.cookies.get(COOKIE_NAME, '')
        if not raw: http(401,'Tizimga kiring')
        with connection() as db:
            record = onerow(db,'SELECT user_id,session_version,expires_at,revoked_at FROM device_sessions WHERE token_hash=?',(hashlib.sha256(raw.encode()).hexdigest(),))
        if not record or record['revoked_at'] or record['expires_at'] <= int(time.time()): http(401,'Sessiya tugagan. Qayta kiring')
        payload = {'u':record['user_id'],'v':record['session_version']}
        # A browser cookie can't be used by a different origin to change business data.
        if request.method not in ('GET','HEAD','OPTIONS'):
            site = request.headers.get('sec-fetch-site','')
            origin = request.headers.get('origin','')
            if site == 'cross-site': http(403,'Begona saytdan so‘rov bloklandi')
            if origin and not origin_matches_request(request, origin):
                http(403,'So‘rov manbasi mos emas')
    with connection() as db:
        user = onerow(db,'SELECT id,username,full_name,role,store_id,active,created_at,session_version FROM users WHERE id=?',(payload['u'],))
    if not user or not user['active'] or user['session_version']!=payload.get('v',0): http(401,'Sessiya faol emas. Qayta kiring')
    return user

ROLES = ('superadmin','owner','manager','seller','warehouse')

def role(user, allowed):
    if user['role'] not in allowed: http(403,'Bu amal uchun ruxsat yo‘q')

def store_from(request, user, db, allowed=None):
    if user['role']=='superadmin': http(403,'Platforma admini do‘kon operatsiyalarini bajarmaydi')
    if allowed: role(user,allowed)
    store_id = request.headers.get('X-Store-ID') or user['store_id']
    if not store_id: http(400,'Do‘konni tanlang')
    if store_id != user['store_id']: http(403,'Boshqa do‘konni boshqarish mumkin emas')
    shop = onerow(db,'SELECT * FROM stores WHERE id=?',(store_id,))
    if not shop: http(404,'Do‘kon topilmadi')
    if shop['status'] != 'active': http(403,'Do‘kon faol emas')
    return shop

def audit(db, store_id, user, event, details):
    db.execute('INSERT INTO audit(id,store_id,user_id,username,action,details,created_at) VALUES(?,?,?,?,?,?,?)',
               (uid(),store_id,user['id'] if user else None,user['username'] if user else 'system',event,json.dumps(details,ensure_ascii=False)[:2000],now()))

SCHEMA = """
CREATE TABLE IF NOT EXISTS stores(id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT DEFAULT '', address TEXT DEFAULT '', logo TEXT DEFAULT '', plan TEXT DEFAULT 'Business', status TEXT DEFAULT 'active', created_at TEXT);
CREATE TABLE IF NOT EXISTS device_sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), session_version INTEGER NOT NULL, created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL, expires_at INTEGER NOT NULL, revoked_at INTEGER);
CREATE INDEX IF NOT EXISTS idx_device_sessions_user ON device_sessions(user_id,expires_at);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, store_id TEXT REFERENCES stores(id), active INTEGER NOT NULL DEFAULT 1, created_at TEXT);
CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id), name TEXT NOT NULL, sku TEXT NOT NULL, category TEXT DEFAULT '', unit TEXT DEFAULT 'qop', price REAL NOT NULL DEFAULT 0, cost REAL NOT NULL DEFAULT 0, stock REAL NOT NULL DEFAULT 0, min_stock REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created_at TEXT, UNIQUE(store_id,sku));
CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id), name TEXT NOT NULL, phone TEXT DEFAULT '', address TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS sales(id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id), cashier_id TEXT NOT NULL REFERENCES users(id), customer_id TEXT REFERENCES customers(id), subtotal REAL NOT NULL, cash_paid REAL NOT NULL, card_paid REAL NOT NULL, debt REAL NOT NULL, method TEXT NOT NULL, client_id TEXT NOT NULL, created_at TEXT, UNIQUE(store_id, client_id));
CREATE TABLE IF NOT EXISTS sale_items(id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES sales(id), product_id TEXT NOT NULL REFERENCES products(id), name TEXT NOT NULL, qty REAL NOT NULL, unit TEXT NOT NULL, price REAL NOT NULL, cost REAL NOT NULL);
CREATE TABLE IF NOT EXISTS debt_payments(id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id), customer_id TEXT NOT NULL REFERENCES customers(id), amount REAL NOT NULL, method TEXT NOT NULL, client_id TEXT NOT NULL, created_at TEXT, UNIQUE(store_id,client_id));
CREATE TABLE IF NOT EXISTS movements(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),product_id TEXT NOT NULL REFERENCES products(id),delta REAL NOT NULL,reason TEXT NOT NULL,note TEXT DEFAULT '',created_at TEXT,user_id TEXT REFERENCES users(id));
CREATE TABLE IF NOT EXISTS expenses(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),category TEXT NOT NULL,note TEXT DEFAULT '',amount REAL NOT NULL,created_at TEXT,user_id TEXT REFERENCES users(id));
CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,store_id TEXT,user_id TEXT,username TEXT,action TEXT,details TEXT,created_at TEXT);
CREATE INDEX IF NOT EXISTS sales_store_date ON sales(store_id,created_at);
CREATE INDEX IF NOT EXISTS products_store ON products(store_id);
CREATE INDEX IF NOT EXISTS debt_customer ON sales(store_id,customer_id);
CREATE TABLE IF NOT EXISTS store_modules(store_id TEXT NOT NULL REFERENCES stores(id),module TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(store_id,module));
CREATE TABLE IF NOT EXISTS cash_shifts(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),cashier_id TEXT NOT NULL REFERENCES users(id),opening_cash REAL NOT NULL DEFAULT 0,closing_cash REAL,expected_cash REAL,variance REAL,status TEXT NOT NULL DEFAULT 'open',opened_at TEXT NOT NULL,closed_at TEXT,note TEXT DEFAULT '');
CREATE UNIQUE INDEX IF NOT EXISTS unique_open_shift ON cash_shifts(store_id,cashier_id) WHERE status='open';
CREATE TABLE IF NOT EXISTS sale_returns(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),sale_id TEXT NOT NULL REFERENCES sales(id),customer_id TEXT REFERENCES customers(id),client_id TEXT NOT NULL,credit_reduction REAL NOT NULL DEFAULT 0,refund_cash REAL NOT NULL DEFAULT 0,refund_card REAL NOT NULL DEFAULT 0,total REAL NOT NULL,shift_id TEXT REFERENCES cash_shifts(id),processed_by TEXT REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(store_id,client_id));
CREATE TABLE IF NOT EXISTS return_items(id TEXT PRIMARY KEY,return_id TEXT NOT NULL REFERENCES sale_returns(id),sale_item_id TEXT NOT NULL REFERENCES sale_items(id),qty REAL NOT NULL,price REAL NOT NULL,cost REAL NOT NULL);
CREATE INDEX IF NOT EXISTS shift_store_date ON cash_shifts(store_id,opened_at);
CREATE INDEX IF NOT EXISTS returns_store_sale ON sale_returns(store_id,sale_id);
"""

def seed():
    with connection() as schema_db:
        schema_db.execute('PRAGMA journal_mode=WAL')
        schema_db.executescript(SCHEMA)
        # Safe additive migrations for existing YemPro 3.0 data.
        for table in ('sales','debt_payments'):
            columns=[r[1] for r in schema_db.execute(f'PRAGMA table_info({table})')]
            if 'shift_id' not in columns:
                schema_db.execute(f'ALTER TABLE {table} ADD COLUMN shift_id TEXT REFERENCES cash_shifts(id)')
    # Clean start: no sample stores, employees, products, customers or sales.
    # The platform owner is initialized locally by setup_admin.py, never hard-coded.
    # Existing databases are not modified here; use RESET_DONCHI.bat for an explicit reset.

seed()

class Login(BaseModel): username:str; password:str; totp:Optional[str]=None
class ChangePassword(BaseModel): old_password:str; new_password:str; totp:Optional[str]=None
class StoreCreate(BaseModel): name:str; username:str; owner_name:str; password:str; plan:str='Start'
class ProductIn(BaseModel): name:str; sku:str; category:str=''; unit:str='qop'; price:float; cost:float=0; stock:float=0; min_stock:float=0
class CustomerIn(BaseModel): id:Optional[str]=None; name:str; phone:str=''; address:str=''
class LineIn(BaseModel): product_id:str; qty:float; unit_price:Optional[float]=None
class SaleIn(BaseModel): client_id:str; customer_id:Optional[str]=None; lines:list[LineIn]; cash_paid:float=0; card_paid:float=0
class PayIn(BaseModel): client_id:str; customer_id:str; amount:float; method:str='cash'
class MovementIn(BaseModel): product_id:str; delta:float; reason:str='kirim'; note:str=''
class ExpenseIn(BaseModel): category:str; amount:float; note:str=''
class SettingsIn(BaseModel): name:str; phone:str=''; address:str=''; logo:str=''
class UserIn(BaseModel): username:str; full_name:str; role:str; password:str
class ShiftOpen(BaseModel): opening_cash:float=0
class ShiftClose(BaseModel): counted_cash:float; note:str=''
class ReturnLine(BaseModel): sale_item_id:str; qty:float
class ReturnIn(BaseModel): client_id:str; items:list[ReturnLine]; refund_method:str='cash'
class StorePlan(BaseModel): plan:str
class StoreModule(BaseModel): module:str; enabled:bool
class StoreModulesBatch(BaseModel): modules:dict[str,bool]


def clean_name(s,n=120):
    x=(s or '').strip()
    if not x or len(x)>n: http(422,f'Matn 1–{n} belgi bo‘lishi kerak')
    return x

def money(n):
    if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n < 0 or n > 1e12: http(422,'Summa noto‘g‘ri')
    return round(float(n),2)

MODULES=('debts','returns','analytics','delivery','finance','crm','branches','telegram','insights')

def features_for(db,store_id):
    flags={k:True for k in MODULES}
    for r in allrows(db,'SELECT module,enabled FROM store_modules WHERE store_id=?',(store_id,)):
        if r['module'] in flags:flags[r['module']]=bool(r['enabled'])
    return flags

def require_feature(db,store,module):
    if not features_for(db,store['id'])[module]:
        http(403,'Bu modul Super Admin tomonidan ushbu do‘konda o‘chirilgan')

def summarize(db,store):
    store_id=store['id']
    p=allrows(db,'SELECT * FROM products WHERE store_id=? AND active=1 ORDER BY name',(store_id,))
    c=allrows(db,'SELECT * FROM customers WHERE store_id=? ORDER BY name',(store_id,))
    sales=allrows(db,'SELECT s.*,c.name AS customer_name,u.full_name AS cashier_name FROM sales s LEFT JOIN customers c ON c.id=s.customer_id LEFT JOIN users u ON u.id=s.cashier_id WHERE s.store_id=? ORDER BY s.created_at DESC LIMIT 250',(store_id,))
    for sale in sales:
        sale['lines']=allrows(db,'SELECT id,product_id,name,qty,unit,price,cost FROM sale_items WHERE sale_id=?',(sale['id'],))
    payments=allrows(db,'SELECT dp.*,c.name AS customer_name FROM debt_payments dp JOIN customers c ON c.id=dp.customer_id WHERE dp.store_id=? ORDER BY dp.created_at DESC LIMIT 300',(store_id,))
    bal=allrows(db,'SELECT c.id,c.name,c.phone, COALESCE((SELECT SUM(s.debt) FROM sales s WHERE s.customer_id=c.id),0)-COALESCE((SELECT SUM(d.amount) FROM debt_payments d WHERE d.customer_id=c.id),0)-COALESCE((SELECT SUM(r.credit_reduction) FROM sale_returns r WHERE r.customer_id=c.id),0) AS balance FROM customers c WHERE c.store_id=? ORDER BY c.name',(store_id,))
    returns=allrows(db,'SELECT r.*,s.client_id AS sale_reference,c.name AS customer_name,u.full_name AS processed_by_name FROM sale_returns r JOIN sales s ON s.id=r.sale_id LEFT JOIN customers c ON c.id=r.customer_id LEFT JOIN users u ON u.id=r.processed_by WHERE r.store_id=? ORDER BY r.created_at DESC LIMIT 140',(store_id,))
    for ret in returns:
        ret['items']=allrows(db,'SELECT sale_item_id,qty FROM return_items WHERE return_id=?',(ret['id'],))
    shifts=allrows(db,'SELECT sh.*,u.full_name AS cashier_name FROM cash_shifts sh JOIN users u ON u.id=sh.cashier_id WHERE sh.store_id=? ORDER BY sh.opened_at DESC LIMIT 100',(store_id,))
    for sh in shifts:
        sh.update(shift_money(db,sh))
    move=allrows(db,'SELECT m.*,p.name AS product_name,u.full_name AS user_name FROM movements m JOIN products p ON p.id=m.product_id LEFT JOIN users u ON u.id=m.user_id WHERE m.store_id=? ORDER BY m.created_at DESC LIMIT 140',(store_id,))
    exp=allrows(db,'SELECT * FROM expenses WHERE store_id=? ORDER BY created_at DESC LIMIT 250',(store_id,))
    users=allrows(db,'SELECT id,username,full_name,role,active,created_at FROM users WHERE store_id=? ORDER BY created_at DESC',(store_id,))
    logs=allrows(db,'SELECT username,action,details,created_at FROM audit WHERE store_id=? ORDER BY created_at DESC LIMIT 80',(store_id,))
    date=datetime.now(LOCAL_TZ).date()
    gross=onerow(db,'SELECT COUNT(*) AS n,COALESCE(SUM(subtotal),0) AS total FROM sales WHERE store_id=?',(store_id,))
    refunds=onerow(db,'SELECT COALESCE(SUM(total),0) AS total FROM sale_returns WHERE store_id=?',(store_id,))
    all_profit=onerow(db,'SELECT COALESCE(SUM(si.qty*(si.price-si.cost)),0) AS total FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.store_id=?',(store_id,))['total']
    return_profit=onerow(db,'SELECT COALESCE(SUM(ri.qty*(ri.price-ri.cost)),0) AS total FROM return_items ri JOIN sale_returns r ON r.id=ri.return_id WHERE r.store_id=?',(store_id,))['total']
    exp_all=onerow(db,'SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE store_id=?',(store_id,))['total']
    # Date-scoped totals computed over full history (not just the 250 visible latest rows).
    today_sales=allrows(db,'SELECT subtotal,created_at FROM sales WHERE store_id=? AND created_at>=?',(store_id,(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()))
    today_returns=allrows(db,'SELECT total,created_at FROM sale_returns WHERE store_id=? AND created_at>=?',(store_id,(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()))
    today=sum(v['subtotal'] for v in today_sales if datetime.fromisoformat(v['created_at']).astimezone(LOCAL_TZ).date()==date)-sum(v['total'] for v in today_returns if datetime.fromisoformat(v['created_at']).astimezone(LOCAL_TZ).date()==date)
    stats={'today':round(today,2),'revenue':round(gross['total']-refunds['total'],2),'gross_sales':gross['total'],'returned_total':refunds['total'],'debt':round(sum(max(0,v['balance']) for v in bal),2), 'stock_value':round(sum(v['stock']*v['cost'] for v in p),2),'low_stock':len([v for v in p if v['stock']<=v['min_stock']]),'profit':round(all_profit-return_profit-exp_all,2), 'sale_count':gross['n']}
    return {'store':store,'products':p,'customers':c,'sales':sales,'payments':payments,'balances':bal,'movements':move,'expenses':exp,'users':users,'audit':logs,'stats':stats,'shifts':shifts,'returns':returns,'features':features_for(db,store_id)}


def open_shift_for(db,store_id,user_id):
    return onerow(db,"SELECT * FROM cash_shifts WHERE store_id=? AND cashier_id=? AND status='open'",(store_id,user_id))


def shift_money(db,shift):
    sid=shift['id']
    a=onerow(db,'SELECT COALESCE(SUM(cash_paid),0) AS cash,COALESCE(SUM(card_paid),0) AS card,COUNT(*) AS count FROM sales WHERE shift_id=?',(sid,))
    d=onerow(db,"SELECT COALESCE(SUM(amount),0) AS cash FROM debt_payments WHERE shift_id=? AND method='cash'",(sid,))
    r=onerow(db,'SELECT COALESCE(SUM(refund_cash),0) AS cash,COALESCE(SUM(refund_card),0) AS card FROM sale_returns WHERE shift_id=?',(sid,))
    cash_expected=round(shift['opening_cash']+a['cash']+d['cash']-r['cash'],2)
    return {'expected_live':cash_expected,'sale_cash':round(a['cash'],2),'sale_card':round(a['card'],2),'debt_cash':round(d['cash'],2),'refund_cash_total':round(r['cash'],2),'refund_card_total':round(r['card'],2),'sale_count':a['count']}

@app.middleware('http')
async def sec_headers(request:Request,call_next):
    resp = await call_next(request)
    resp.headers['X-Content-Type-Options']='nosniff'
    resp.headers['X-Frame-Options']='DENY'
    resp.headers['Referrer-Policy']='no-referrer'
    # external embeds/scripts blocked; UI code keeps scripts in separate file
    resp.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; worker-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'"
    if request.url.path.startswith('/api/'):
        resp.headers['Cache-Control']='no-store'
    return resp

def set_session_cookie(request: Request, response: Response, raw: str):
    # Production HTTPS deployments must set YEMPRO_COOKIE_SECURE=1 behind TLS proxies.
    secure = request.url.scheme == 'https' or os.getenv('DONCHI_COOKIE_SECURE',os.getenv('YEMPRO_COOKIE_SECURE')) == '1'
    response.set_cookie(key=COOKIE_NAME, value=raw, max_age=SESSION_TTL, path='/',
                        secure=secure, httponly=True, samesite='lax')

def save_browser_session(user):
    raw = secrets.token_urlsafe(48)
    stamp = int(time.time())
    with connection(write=True) as db:
        db.execute('DELETE FROM device_sessions WHERE expires_at<? OR revoked_at IS NOT NULL',(stamp,))
        db.execute('INSERT INTO device_sessions(token_hash,user_id,session_version,created_at,last_seen,expires_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)',
                   (hashlib.sha256(raw.encode()).hexdigest(),user['id'],user.get('session_version',0),stamp,stamp,stamp+SESSION_TTL))
    return raw

@app.get('/api/session')
def current_session(request:Request,response:Response,user=Depends(get_user)):
    raw=request.cookies.get(COOKIE_NAME)
    if raw:
        stamp=int(time.time())
        with connection(write=True) as db:
            db.execute('UPDATE device_sessions SET last_seen=?,expires_at=? WHERE token_hash=? AND revoked_at IS NULL',
                       (stamp,stamp+SESSION_TTL,hashlib.sha256(raw.encode()).hexdigest()))
        set_session_cookie(request,response,raw)
    return {'user':{k:user[k] for k in ('id','username','full_name','role','store_id')}}

@app.post('/api/session/upgrade')
def upgrade_legacy_session(request:Request,response:Response,user=Depends(get_user)):
    if not request.headers.get('Authorization','').startswith('Bearer '): http(403,'Faqat eski sessiyani yangilash uchun')
    raw=save_browser_session(user)
    set_session_cookie(request,response,raw)
    return {'user':{k:user[k] for k in ('id','username','full_name','role','store_id')}}

@app.post('/api/logout')
def server_logout(request:Request,response:Response):
    origin=request.headers.get('origin','')
    if request.headers.get('sec-fetch-site','')=='cross-site' or (origin and not origin_matches_request(request, origin)):
        http(403,'Begona saytdan chiqish so‘rovi bloklandi')
    raw=request.cookies.get(COOKIE_NAME)
    if raw:
        with connection(write=True) as db:
            db.execute('UPDATE device_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL',
                       (int(time.time()),hashlib.sha256(raw.encode()).hexdigest()))
    response.delete_cookie(COOKIE_NAME,path='/',samesite='lax')
    return {'ok':True}

@app.post('/api/login')
def login(payload:Login, request:Request, response:Response):
    with connection() as db:
        key=payload.username.strip().lower()[:60]
        guard=onerow(db,'SELECT * FROM login_guards WHERE login_key=?',(key,))
        if guard and guard['locked_until'] and guard['locked_until']>now():http(429,'Juda ko‘p urinish. 5 daqiqadan keyin qayta urinib ko‘ring')
        u=onerow(db,'SELECT * FROM users WHERE username=?',(key,))
        if not u or not u['active'] or not checkpwd(payload.password,u['password_hash']):
            with connection(write=True) as wdb:
                old=onerow(wdb,'SELECT * FROM login_guards WHERE login_key=?',(key,))
                failed=(old['failed'] if old else 0)+1
                until=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(timespec='seconds') if failed>=8 else ''
                wdb.execute('INSERT INTO login_guards(login_key,failed,locked_until,last_failed) VALUES(?,?,?,?) ON CONFLICT(login_key) DO UPDATE SET failed=excluded.failed,locked_until=excluded.locked_until,last_failed=excluded.last_failed',(key,failed,until,now()))
            http(401,'Login yoki parol noto‘g‘ri')
        if u['role']=='superadmin' and not verify_login_totp(u['id'],payload.totp):
            with connection(write=True) as wdb:
                old=onerow(wdb,'SELECT * FROM login_guards WHERE login_key=?',(key,))
                failed=(old['failed'] if old else 0)+1
                until=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(timespec='seconds') if failed>=8 else ''
                wdb.execute('INSERT INTO login_guards(login_key,failed,locked_until,last_failed) VALUES(?,?,?,?) ON CONFLICT(login_key) DO UPDATE SET failed=excluded.failed,locked_until=excluded.locked_until,last_failed=excluded.last_failed',(key,failed,until,now()))
            http(401,'2FA kodi noto‘g‘ri yoki kiritilmagan')
        with connection(write=True) as wdb:wdb.execute('DELETE FROM login_guards WHERE login_key=?',(key,))
        safe={k:u[k] for k in ['id','username','full_name','role','store_id']}
        raw=save_browser_session(u)
        set_session_cookie(request,response,raw)
        return {'token':token_for(u),'user':safe}  # legacy API tests; browser doesn't store token

@app.post('/api/account/password')
def change_password(payload:ChangePassword,response:Response,user=Depends(get_user)):
    if len(payload.new_password)<10: http(422,'Parol kamida 10 ta belgidan iborat bo‘lsin')
    if user['role']=='superadmin' and totp_required(user['id']) and not verify_login_totp(user['id'],payload.totp): http(403,'Parolni yangilash uchun 2FA kodi kerak')
    with connection(write=True) as db:
        u=onerow(db,'SELECT password_hash FROM users WHERE id=?',(user['id'],))
        if not checkpwd(payload.old_password,u['password_hash']): http(400,'Eski parol noto‘g‘ri')
        db.execute('UPDATE users SET password_hash=?,session_version=session_version+1 WHERE id=?',(pwdhash(payload.new_password),user['id']))
        db.execute('UPDATE device_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL',(int(time.time()),user['id']))
        audit(db,user['store_id'],user,'PASSWORD_CHANGED',{})
    response.delete_cookie(COOKIE_NAME,path='/',samesite='lax')
    return {'ok':True}

@app.get('/api/bootstrap')
def bootstrap(request:Request,user=Depends(get_user)):
    with connection() as db:
        if user['role']=='superadmin':
            stores=allrows(db,'SELECT id,name,phone,address,plan,status,created_at FROM stores ORDER BY name')
            platform=allrows(db,"""SELECT s.id,s.name,s.plan,s.status,s.created_at,
                (SELECT COUNT(*) FROM users u WHERE u.store_id=s.id) AS users,
                (SELECT COUNT(*) FROM sales x WHERE x.store_id=s.id) AS sales,
                (SELECT COALESCE(SUM(subtotal),0) FROM sales x WHERE x.store_id=s.id) -
                (SELECT COALESCE(SUM(total),0) FROM sale_returns r WHERE r.store_id=s.id) AS revenue
                FROM stores s ORDER BY s.created_at DESC""")
            for shop in platform:shop['features']=features_for(db,shop['id'])
            releases=allrows(db,'SELECT * FROM releases ORDER BY created_at DESC LIMIT 100')
            inquiries=allrows(db,'SELECT * FROM demo_inquiries ORDER BY created_at DESC LIMIT 300')
            return {'user':user,'stores':stores,'data':{'platform':platform,'releases':releases,'inquiries':inquiries},'server_time':now()}
        store=store_from(request,user,db)
        data=summarize(db,store)
        extra=extra_summary(db,store,request.headers.get('X-Branch-ID'))
        data.update(extra)
        data['smart_insights']=smart_insights(data)
        if user['role'] not in ('owner','manager'):
            for key in ('users','audit','expenses','supplier_bills'):
                data.pop(key,None)
            data['stats'].pop('profit',None)
        if user['role']=='seller':
            data.pop('supplier_bills',None)
            for product in data.get('products',[]): product.pop('cost',None)
            for sale in data.get('sales',[]):
                for line in sale.get('lines',[]): line.pop('cost',None)
            data.get('stats',{}).pop('stock_value',None)
            data['shifts']=[sh for sh in data['shifts'] if sh['cashier_id']==user['id']]
        if user['role']=='warehouse':
            for key in ('payments','balances','sales','customers','returns','shifts','deliveries','supplier_bills','telegram'):
                data.pop(key,None)
        stores=allrows(db,'SELECT id,name,phone,address,plan,status,created_at FROM stores WHERE id=?',(user['store_id'],))
    return {'user':user,'stores':stores,'data':data,'server_time':now()}

@app.post('/api/stores')
def create_store(payload:StoreCreate,user=Depends(get_user)):
    role(user,['superadmin'])
    name=clean_name(payload.name)
    login_name=clean_name(payload.username,40).lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,40}',login_name): http(422,'Login faqat a-z, 0-9 va ._- belgilaridan iborat bo‘lsin')
    if payload.plan not in ('Start','Business','Premium','Enterprise'): http(422,'Bunday tarif mavjud emas')
    if len(payload.password)<10: http(422,'Parol kamida 10 belgidan iborat bo‘lsin')
    with connection(write=True) as db:
        if onerow(db,'SELECT id FROM users WHERE username=?',(login_name,)): http(409,'Bu login band')
        store_id=uid()
        db.execute('INSERT INTO stores VALUES(?,?,?,?,?,?,?,?)',(store_id,name,'','','',payload.plan[:30],'active',now()))
        bid=uid();db.execute('INSERT INTO branches VALUES(?,?,?,?,?,?)',(bid,store_id,'Asosiy filial','',1,now()))
        db.execute('INSERT INTO users(id,username,full_name,password_hash,role,store_id,active,created_at) VALUES(?,?,?,?,?,?,?,?)',(uid(),login_name,clean_name(payload.owner_name),pwdhash(payload.password),'owner',store_id,1,now()))
        audit(db,store_id,user,'STORE_CREATED',{'name':name})
    return {'ok':True,'store_id':store_id}

@app.post('/api/stores/{store_id}/status')
def set_store_status(store_id:str,payload:dict=Body(...),user=Depends(get_user)):
    role(user,['superadmin'])
    status=payload.get('status')
    if status not in ('active','paused'): http(422,'Status noto‘g‘ri')
    with connection(write=True) as db:
        if not onerow(db,'SELECT id FROM stores WHERE id=?',(store_id,)):http(404,'Do‘kon topilmadi')
        db.execute('UPDATE stores SET status=? WHERE id=?',(status,store_id))
        audit(db,store_id,user,'STORE_STATUS',{'status':status})
    return {'ok':True}

@app.post('/api/stores/{store_id}/plan')
def set_store_plan(store_id:str,payload:StorePlan,user=Depends(get_user)):
    role(user,['superadmin'])
    if payload.plan not in ('Start','Business','Premium','Enterprise'):http(422,'Tarif noto‘g‘ri')
    with connection(write=True) as db:
        if not onerow(db,'SELECT id FROM stores WHERE id=?',(store_id,)):http(404,'Do‘kon topilmadi')
        db.execute('UPDATE stores SET plan=? WHERE id=?',(payload.plan,store_id))
        audit(db,store_id,user,'STORE_PLAN',{'plan':payload.plan})
    return {'ok':True}

@app.post('/api/stores/{store_id}/modules')
def set_store_module(store_id:str,payload:StoreModule,user=Depends(get_user)):
    role(user,['superadmin'])
    if payload.module not in MODULES:http(422,'Modul noto‘g‘ri')
    with connection(write=True) as db:
        if not onerow(db,'SELECT id FROM stores WHERE id=?',(store_id,)):http(404,'Do‘kon topilmadi')
        db.execute('INSERT INTO store_modules(store_id,module,enabled) VALUES(?,?,?) ON CONFLICT(store_id,module) DO UPDATE SET enabled=excluded.enabled',(store_id,payload.module,int(payload.enabled)))
        audit(db,store_id,user,'MODULE_TOGGLED',{'module':payload.module,'enabled':payload.enabled})
    return {'ok':True}

@app.put('/api/stores/{store_id}/modules')
def set_store_modules_batch(store_id:str,payload:StoreModulesBatch,user=Depends(get_user)):
    """Apply all module permissions in one database transaction."""
    role(user,['superadmin'])
    # Reject invalid or partial payloads before any database writes.
    if set(payload.modules) != set(MODULES):
        http(422,'Barcha modullar to‘liq yuborilishi kerak')
    if any(type(enabled) is not bool for enabled in payload.modules.values()):
        http(422,'Modul qiymatlari true yoki false bo‘lishi kerak')
    with connection(write=True) as db:
        if not onerow(db,'SELECT id FROM stores WHERE id=?',(store_id,)):
            http(404,'Do‘kon topilmadi')
        for module in MODULES:
            enabled=payload.modules[module]
            db.execute(
                'INSERT INTO store_modules(store_id,module,enabled) VALUES(?,?,?) '
                'ON CONFLICT(store_id,module) DO UPDATE SET enabled=excluded.enabled',
                (store_id,module,int(enabled)),
            )
        audit(db,store_id,user,'MODULES_BATCH_UPDATED',{'modules':payload.modules})
    return {'ok':True,'modules':payload.modules}


@app.post('/api/users')
def add_user(payload:UserIn,request:Request,user=Depends(get_user)):
    role(user,['owner'])
    if payload.role not in ('owner','manager','seller','warehouse'): http(422,'Rol noto‘g‘ri')
    if len(payload.password)<10: http(422,'Parol kamida 10 belgidan iborat bo‘lsin')
    login_name=clean_name(payload.username,40).lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,40}',login_name): http(422,'Login noto‘g‘ri')
    with connection(write=True) as db:
        store=store_from(request,user,db)
        if onerow(db,'SELECT id FROM users WHERE username=?',(login_name,)):http(409,'Bu login band')
        db.execute('INSERT INTO users(id,username,full_name,password_hash,role,store_id,active,created_at) VALUES(?,?,?,?,?,?,?,?)',(uid(),login_name,clean_name(payload.full_name),pwdhash(payload.password),payload.role,store['id'],1,now()))
        audit(db,store['id'],user,'USER_CREATED',{'username':login_name,'role':payload.role})
    return {'ok':True}


@app.post('/api/users/{user_id}/status')
def update_user_status(user_id:str,payload:dict,request:Request,user=Depends(get_user)):
    with connection(write=True) as db:
        store=store_from(request,user,db,['owner'])
        if user_id==user['id']:http(422,'O‘z hisobingizni bloklay olmaysiz')
        u=onerow(db,'SELECT * FROM users WHERE id=? AND store_id=?',(user_id,store['id']))
        if not u:http(404,'Xodim topilmadi')
        active=payload.get('active')
        if not isinstance(active,bool):http(422,'active qiymati kerak')
        db.execute('UPDATE users SET active=?,session_version=session_version+1 WHERE id=?',(int(active),user_id))
        audit(db,store['id'],user,'USER_STATUS',{'id':user_id,'active':active})
    return {'ok':True}

@app.post('/api/products')
def add_product(payload:ProductIn,request:Request,user=Depends(get_user)):
    with connection(write=True) as db:
        store=store_from(request,user,db,['owner','manager'])
        if payload.unit not in ('kg','qop','tonna','dona'):http(422,'O‘lchov noto‘g‘ri')
        qty=money(payload.stock); minimum=money(payload.min_stock); price=money(payload.price); cost=money(payload.cost)
        pid=uid()
        try: db.execute('INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,store['id'],clean_name(payload.name),clean_name(payload.sku,40),payload.category[:70],payload.unit,price,cost,qty,minimum,1,now()))
        except sqlite3.IntegrityError: http(409,'Bu shtrix-kod / SKU mavjud')
        branch=branch_for(db,store['id'],request)
        adjust_branch(db,store['id'],branch['id'],pid,qty)
        audit(db,store['id'],user,'PRODUCT_CREATED',{'id':pid,'name':payload.name})
    return {'ok':True,'id':pid}

@app.put('/api/products/{pid}')
def update_product(pid:str,payload:ProductIn,request:Request,user=Depends(get_user)):
    with connection(write=True) as db:
        store=store_from(request,user,db,['owner','manager'])
        p=onerow(db,'SELECT * FROM products WHERE id=? AND store_id=? AND active=1',(pid,store['id']))
        if not p: http(404,'Mahsulot topilmadi')
        if payload.unit not in ('kg','qop','tonna','dona'):http(422,'O‘lchov noto‘g‘ri')
        try:
            db.execute('UPDATE products SET name=?,sku=?,category=?,unit=?,price=?,cost=?,min_stock=? WHERE id=?',(clean_name(payload.name),clean_name(payload.sku,40),payload.category[:70],payload.unit,money(payload.price),money(payload.cost),money(payload.min_stock),pid))
        except sqlite3.IntegrityError: http(409,'SKU band')
        audit(db,store['id'],user,'PRODUCT_UPDATED',{'id':pid,'name':payload.name})
    return {'ok':True}

@app.delete('/api/products/{pid}')
def delete_product(pid:str,request:Request,user=Depends(get_user)):
    with connection(write=True) as db:
        store=store_from(request,user,db,['owner','manager'])
        if not onerow(db,'SELECT id FROM products WHERE id=? AND store_id=?',(pid,store['id'])):http(404,'Mahsulot topilmadi')
        db.execute('UPDATE products SET active=0 WHERE id=? AND store_id=?',(pid,store['id']))
        audit(db,store['id'],user,'PRODUCT_DELETED',{'id':pid})
    return {'ok':True}

@app.post('/api/customers')
def add_customer(payload:CustomerIn,request:Request,user=Depends(get_user)):
    with connection(write=True) as db:
        store=store_from(request,user,db,['seller','manager','owner'])
        cid=payload.id or uid()
        try: uuid.UUID(cid)
        except ValueError:http(422,'Mijoz ID noto‘g‘ri')
        found=onerow(db,'SELECT id FROM customers WHERE id=? AND store_id=?',(cid,store['id']))
        if found:return {'ok':True,'id':cid,'duplicate':True}
        try: db.execute('INSERT INTO customers(id,store_id,name,phone,address,created_at) VALUES(?,?,?,?,?,?)',(cid,store['id'],clean_name(payload.name),payload.phone[:60],payload.address[:180],now()))
        except sqlite3.IntegrityError: http(409,'Mijoz identifikatori band')
        audit(db,store['id'],user,'CUSTOMER_CREATED',{'id':cid,'name':payload.name})
    return {'ok':True,'id':cid}

@app.post('/api/sales')
def create_sale(payload:SaleIn,request:Request,user=Depends(get_user)):
    if not payload.client_id or len(payload.client_id)>100: http(422,'Operatsiya ID noto‘g‘ri')
    if not payload.lines or len(payload.lines)>60: http(422,'Savatcha bo‘sh yoki juda katta')
    if payload.customer_id is not None and len(payload.customer_id)>80: http(422,'Mijoz ID noto‘g‘ri')
    with connection(write=True) as db:
        store=store_from(request,user,db,['seller','owner','manager'])
        dup=onerow(db,'SELECT id FROM sales WHERE store_id=? AND client_id=?',(store['id'],payload.client_id))
        if dup:return {'ok':True,'id':dup['id'],'duplicate':True}
        active_shift=open_shift_for(db,store['id'],user['id'])
        if not active_shift:http(409,'Savdodan oldin kassa smenasini oching')
        branch=branch_for(db,store['id'],request)
        if payload.customer_id and not onerow(db,'SELECT id FROM customers WHERE id=? AND store_id=?',(payload.customer_id,store['id'])):
            http(422,'Mijoz topilmadi (offline operatsiyalar tartibini tekshiring)')
        calc=[]; total=0
        ids=[x.product_id for x in payload.lines]
        if len(ids)!=len(set(ids)): http(422,'Bir mahsulot savatchada takrorlangan')
        for line in payload.lines:
            if line.qty <= 0 or line.qty > 100000 or line.qty != line.qty:http(422,'Miqdor noto‘g‘ri')
            p=onerow(db,'SELECT * FROM products WHERE id=? AND store_id=? AND active=1',(line.product_id,store['id']))
            if not p:http(422,'Mahsulot yo‘q yoki o‘chirilgan')
            if line.unit_price is not None and abs(line.unit_price-p['price'])>0.01:http(409,f"{p['name']}: narx o‘zgargan. Qayta tekshiring.")
            if stock_at(db,store['id'],branch['id'],p['id'])+0.0000001<line.qty:http(409,f"{p['name']}: tanlangan filialda qoldiq yetarli emas")
            calc.append((p,line.qty))
            total+=round(p['price']*line.qty,2)
        total=round(total,2)
        cash=money(payload.cash_paid); card=money(payload.card_paid)
        if cash+card-total>0.01:http(422,'To‘langan summa savdodan katta')
        debt=round(total-cash-card,2)
        if debt>0: require_feature(db,store,'debts')
        if debt>0 and not payload.customer_id:http(422,'Nasiya uchun mijozni tanlang')
        if debt>0 and payload.customer_id:
            customer=onerow(db,'SELECT credit_limit FROM customers WHERE store_id=? AND id=?',(store['id'],payload.customer_id))
            if customer and customer['credit_limit']>0:
                outstanding=onerow(db,'SELECT COALESCE((SELECT SUM(debt) FROM sales WHERE customer_id=?),0)-COALESCE((SELECT SUM(amount) FROM debt_payments WHERE customer_id=?),0)-COALESCE((SELECT SUM(credit_reduction) FROM sale_returns WHERE customer_id=?),0) AS balance',(payload.customer_id,payload.customer_id,payload.customer_id))['balance']
                if outstanding+debt>customer['credit_limit']+.01:http(409,'Mijoz nasiya limiti oshib ketdi')
        sid=uid()
        method='debt' if debt else ('mixed' if cash>0 and card>0 else 'card' if card>0 else 'cash')
        db.execute('INSERT INTO sales(id,store_id,cashier_id,customer_id,subtotal,cash_paid,card_paid,debt,method,client_id,created_at,shift_id,branch_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,store['id'],user['id'],payload.customer_id,total,cash,card,debt,method,payload.client_id,now(),active_shift['id'],branch['id']))
        for p,qty in calc:
            adjust_branch(db,store['id'],branch['id'],p['id'],-qty)
            consume_lots(db,store['id'],branch['id'],p['id'],qty)
            db.execute('UPDATE products SET stock=stock-? WHERE id=? AND store_id=?',(qty,p['id'],store['id']))
            db.execute('INSERT INTO sale_items VALUES(?,?,?,?,?,?,?,?)',(uid(),sid,p['id'],p['name'],qty,p['unit'],p['price'],p['cost']))
            db.execute('INSERT INTO movements(id,store_id,product_id,delta,reason,note,created_at,user_id,branch_id) VALUES(?,?,?,?,?,?,?,?,?)',(uid(),store['id'],p['id'],-qty,'sotuv',f'Savdo #{sid[:8]}',now(),user['id'],branch['id']))
        audit(db,store['id'],user,'SALE_CREATED',{'id':sid,'total':total,'debt':debt,'customer':payload.customer_id})
    return {'ok':True,'id':sid,'total':total,'debt':debt}

@app.post('/api/debts/pay')
def pay_debt(payload:PayIn,request:Request,user=Depends(get_user)):
    if payload.method not in ('cash','card'):http(422,'To‘lov usuli noto‘g‘ri')
    with connection(write=True) as db:
        store=store_from(request,user,db,['seller','owner','manager'])
        require_feature(db,store,'debts')
        dup=onerow(db,'SELECT id FROM debt_payments WHERE store_id=? AND client_id=?',(store['id'],payload.client_id))
        if dup:return {'ok':True,'id':dup['id'],'duplicate':True}
        active_shift=open_shift_for(db,store['id'],user['id'])
        if not active_shift:http(409,'Qarz to‘lovidan oldin kassa smenasini oching')
        if not onerow(db,'SELECT id FROM customers WHERE id=? AND store_id=?',(payload.customer_id,store['id'])):http(422,'Mijoz topilmadi')
        bal=onerow(db,'SELECT COALESCE((SELECT SUM(debt) FROM sales WHERE customer_id=?),0)-COALESCE((SELECT SUM(amount) FROM debt_payments WHERE customer_id=?),0)-COALESCE((SELECT SUM(credit_reduction) FROM sale_returns WHERE customer_id=?),0) AS balance',(payload.customer_id,payload.customer_id,payload.customer_id))['balance']
        amount=money(payload.amount)
        if amount<=0 or amount-bal>0.01:http(422,f'Qarzdan ortiq to‘lov kiritib bo‘lmaydi. Qoldiq: {bal:,.0f}')
        did=uid()
        db.execute('INSERT INTO debt_payments(id,store_id,customer_id,amount,method,client_id,created_at,shift_id) VALUES(?,?,?,?,?,?,?,?)',(did,store['id'],payload.customer_id,amount,payload.method,payload.client_id,now(),active_shift['id']))
        audit(db,store['id'],user,'DEBT_PAYMENT',{'id':did,'amount':amount,'customer':payload.customer_id})
    return {'ok':True,'id':did}

@app.post('/api/inventory/adjust')
def stock_adjust(payload:MovementIn,request:Request,user=Depends(get_user)):
    with connection(write=True) as db:
        store=store_from(request,user,db,['warehouse','manager','owner'])
        p=onerow(db,'SELECT * FROM products WHERE id=? AND store_id=? AND active=1',(payload.product_id,store['id']))
        if not p:http(404,'Mahsulot topilmadi')
        if payload.delta==0 or payload.delta != payload.delta or abs(payload.delta)>1e8:http(422,'Miqdor noto‘g‘ri')
        if p['stock']+payload.delta < -0.00001:http(409,'Omborda yetarli mahsulot yo‘q')
        branch=branch_for(db,store['id'],request)
        adjust_branch(db,store['id'],branch['id'],p['id'],payload.delta)
        if payload.delta<0:consume_lots(db,store['id'],branch['id'],p['id'],-payload.delta)
        db.execute('UPDATE products SET stock=stock+? WHERE id=?',(payload.delta,payload.product_id))
        db.execute('INSERT INTO movements(id,store_id,product_id,delta,reason,note,created_at,user_id,branch_id) VALUES(?,?,?,?,?,?,?,?,?)',(uid(),store['id'],p['id'],payload.delta,clean_name(payload.reason,40),payload.note[:250],now(),user['id'],branch['id']))
        audit(db,store['id'],user,'STOCK_ADJUSTED',{'product':p['name'],'delta':payload.delta})
    return {'ok':True}

@app.post('/api/expenses')
def create_expense(payload:ExpenseIn,request:Request,user=Depends(get_user)):
    with connection(write=True) as db:
        store=store_from(request,user,db,['owner','manager'])
        require_feature(db,store,'analytics')
        amount=money(payload.amount)
        if amount<=0:http(422,'Summa musbat bo‘lishi kerak')
        db.execute('INSERT INTO expenses VALUES(?,?,?,?,?,?,?)',(uid(),store['id'],clean_name(payload.category,80),payload.note[:250],amount,now(),user['id']))
        audit(db,store['id'],user,'EXPENSE_CREATED',{'amount':amount,'category':payload.category})
    return {'ok':True}

@app.put('/api/settings')
def update_settings(payload:SettingsIn,request:Request,user=Depends(get_user)):
    with connection(write=True) as db:
        store=store_from(request,user,db,['owner'])
        if len(payload.logo)>250000 or (payload.logo and not re.match(r'^data:image/(png|jpeg|webp);base64,',payload.logo)):http(422,'Logotip PNG/JPG/WEBP va 180KB dan kichik bo‘lsin')
        db.execute('UPDATE stores SET name=?,phone=?,address=?,logo=? WHERE id=?',(clean_name(payload.name),payload.phone[:60],payload.address[:250],payload.logo,store['id']))
        audit(db,store['id'],user,'SETTINGS_UPDATED',{'name':payload.name})
    return {'ok':True}


@app.get('/api/export')
def store_export(request:Request,user=Depends(get_user)):
    """Tenant-isolated full JSON data export. No password hashes or other tenants."""
    with connection() as db:
        store=store_from(request,user,db,['owner'])
        sid=store['id']
        products=allrows(db,'SELECT * FROM products WHERE store_id=?',(sid,))
        customers=allrows(db,'SELECT * FROM customers WHERE store_id=?',(sid,))
        sales=allrows(db,'SELECT * FROM sales WHERE store_id=?',(sid,))
        sale_ids=[x['id'] for x in sales]
        items=allrows(db,'SELECT si.* FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.store_id=?',(sid,))
        payments=allrows(db,'SELECT * FROM debt_payments WHERE store_id=?',(sid,))
        movements=allrows(db,'SELECT * FROM movements WHERE store_id=?',(sid,))
        expenses=allrows(db,'SELECT * FROM expenses WHERE store_id=?',(sid,))
        users=allrows(db,'SELECT id,username,full_name,role,store_id,active,created_at FROM users WHERE store_id=?',(sid,))
        shifts=allrows(db,'SELECT * FROM cash_shifts WHERE store_id=?',(sid,))
        refunds=allrows(db,'SELECT * FROM sale_returns WHERE store_id=?',(sid,))
        returned_items=allrows(db,'SELECT ri.* FROM return_items ri JOIN sale_returns r ON r.id=ri.return_id WHERE r.store_id=?',(sid,))
        branches=allrows(db,'SELECT * FROM branches WHERE store_id=?',(sid,))
        branch_stock=allrows(db,'SELECT * FROM branch_stock WHERE store_id=?',(sid,))
        lots=allrows(db,'SELECT * FROM inventory_lots WHERE store_id=?',(sid,))
        deliveries=allrows(db,'SELECT * FROM deliveries WHERE store_id=?',(sid,))
        supplier_bills=allrows(db,'SELECT * FROM supplier_bills WHERE store_id=?',(sid,))
        supplier_payments=allrows(db,'SELECT * FROM supplier_payments WHERE store_id=?',(sid,))
        transfers=allrows(db,'SELECT * FROM branch_transfers WHERE store_id=?',(sid,))
        telegram=allrows(db,'SELECT * FROM telegram_settings WHERE store_id=?',(sid,))
        logs=allrows(db,'SELECT * FROM audit WHERE store_id=?',(sid,))
    return {'export_version':3,'exported_at':now(),'store':store,'products':products,'customers':customers,'sales':sales,'sale_items':items,'debt_payments':payments,'movements':movements,'expenses':expenses,'users':users,'cash_shifts':shifts,'sale_returns':refunds,'return_items':returned_items, 'branches':branches, 'branch_stock':branch_stock, 'inventory_lots':lots, 'deliveries':deliveries, 'supplier_bills':supplier_bills, 'supplier_payments':supplier_payments, 'branch_transfers':transfers, 'telegram_settings':telegram, 'audit':logs}

@app.post('/api/shifts/open')
def shift_open(payload:ShiftOpen,request:Request,user=Depends(get_user)):
    amount=money(payload.opening_cash)
    with connection(write=True) as db:
        store=store_from(request,user,db,['owner','manager','seller'])
        if open_shift_for(db,store['id'],user['id']): http(409,'Sizda ochiq kassa smenasi mavjud')
        shift_id=uid()
        db.execute('INSERT INTO cash_shifts(id,store_id,cashier_id,opening_cash,status,opened_at) VALUES(?,?,?,?,?,?)',
                   (shift_id,store['id'],user['id'],amount,'open',now()))
        audit(db,store['id'],user,'SHIFT_OPEN',{'id':shift_id,'opening_cash':amount})
    return {'ok':True,'id':shift_id}

@app.post('/api/shifts/close')
def shift_close(payload:ShiftClose,request:Request,user=Depends(get_user)):
    counted=money(payload.counted_cash)
    with connection(write=True) as db:
        store=store_from(request,user,db,['owner','manager','seller'])
        shift=open_shift_for(db,store['id'],user['id'])
        if not shift:http(409,'Ochiq smena yo‘q')
        expected=shift_money(db,shift)['expected_live']
        variance=round(counted-expected,2)
        db.execute("UPDATE cash_shifts SET status='closed',closing_cash=?,expected_cash=?,variance=?,closed_at=?,note=? WHERE id=? AND status='open'",(counted,expected,variance,now(),payload.note[:250],shift['id']))
        audit(db,store['id'],user,'SHIFT_CLOSE',{'id':shift['id'],'expected':expected,'counted':counted,'variance':variance})
    return {'ok':True,'id':shift['id'],'expected':expected,'counted':counted,'variance':variance}

@app.post('/api/sales/{sale_id}/return')
def return_sale(sale_id:str,payload:ReturnIn,request:Request,user=Depends(get_user)):
    if not payload.client_id or len(payload.client_id)>100:http(422,'Operatsiya ID noto‘g‘ri')
    if payload.refund_method not in ('cash','card'):http(422,'Qaytarish usuli noto‘g‘ri')
    if not payload.items or len(payload.items)>60:http(422,'Qaytariladigan mahsulotni tanlang')
    if len(set(v.sale_item_id for v in payload.items))!=len(payload.items):http(422,'Takror mahsulot kiritilgan')
    with connection(write=True) as db:
        store=store_from(request,user,db,['owner','manager'])
        require_feature(db,store,'returns')
        dup=onerow(db,'SELECT id,total FROM sale_returns WHERE store_id=? AND client_id=?',(store['id'],payload.client_id))
        if dup:return {'ok':True,'id':dup['id'],'total':dup['total'],'duplicate':True}
        shift=open_shift_for(db,store['id'],user['id'])
        if not shift:http(409,'Qaytarishdan oldin o‘z kassa smenangizni oching')
        sale=onerow(db,'SELECT * FROM sales WHERE id=? AND store_id=?',(sale_id,store['id']))
        if not sale:http(404,'Savdo topilmadi')
        items=[];total=0
        for line in payload.items:
            if not (0 < line.qty <= 100000) or line.qty!=line.qty:http(422,'Miqdor noto‘g‘ri')
            row=onerow(db,'SELECT si.* FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE si.id=? AND s.id=? AND s.store_id=?',(line.sale_item_id,sale_id,store['id']))
            if not row:http(422,'Savdo mahsuloti topilmadi')
            previously=onerow(db,'SELECT COALESCE(SUM(ri.qty),0) AS qty FROM return_items ri JOIN sale_returns r ON r.id=ri.return_id WHERE r.sale_id=? AND ri.sale_item_id=?',(sale_id,line.sale_item_id))['qty']
            if line.qty+previously>row['qty']+0.0000001:http(409,'Qaytarish miqdori sotilgan mahsulotdan oshib ketdi')
            items.append((row,round(line.qty,4)))
            total+=round(row['price']*line.qty,2)
        total=round(total,2)
        if total<=0:http(422,'Qaytarish summasi noto‘g‘ri')
        outstanding=0
        if sale['customer_id']:
            cid=sale['customer_id']
            bal=onerow(db,"""SELECT COALESCE((SELECT SUM(debt) FROM sales WHERE customer_id=?),0)
                     -COALESCE((SELECT SUM(amount) FROM debt_payments WHERE customer_id=?),0)
                     -COALESCE((SELECT SUM(credit_reduction) FROM sale_returns WHERE customer_id=?),0) AS balance""",(cid,cid,cid))['balance']
            outstanding=max(0,round(bal,2))
        # Credits may only reverse existing recorded debt from this sale; any remaining
        # refund is paid back using the chosen tender. This demo uses account-level debt.
        used=onerow(db,'SELECT COALESCE(SUM(credit_reduction),0) AS amt FROM sale_returns WHERE sale_id=?',(sale_id,))['amt']
        credit=min(total,outstanding,max(0,round(sale['debt']-used,2)))
        paid=round(total-credit,2)
        cash=paid if payload.refund_method=='cash' else 0.0
        card=paid if payload.refund_method=='card' else 0.0
        if cash > shift_money(db,shift)['expected_live'] + 0.01:
            http(409,'Kassada naqd qaytim uchun yetarli pul yo‘q. Boshqa qaytim usulini tanlang yoki smenani tekshiring.')
        return_id=uid()
        db.execute('INSERT INTO sale_returns(id,store_id,sale_id,customer_id,client_id,credit_reduction,refund_cash,refund_card,total,shift_id,processed_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                   (return_id,store['id'],sale_id,sale['customer_id'],payload.client_id,credit,cash,card,total,shift['id'],user['id'],now()))
        for row,qty in items:
            db.execute('INSERT INTO return_items VALUES(?,?,?,?,?,?)',(uid(),return_id,row['id'],qty,row['price'],row['cost']))
            branch_id=sale['branch_id'] or branch_for(db,store['id'],request)['id']
            adjust_branch(db,store['id'],branch_id,row['product_id'],qty)
            db.execute('UPDATE products SET stock=stock+? WHERE id=? AND store_id=?',(qty,row['product_id'],store['id']))
            db.execute('INSERT INTO movements(id,store_id,product_id,delta,reason,note,created_at,user_id,branch_id) VALUES(?,?,?,?,?,?,?,?,?)',(uid(),store['id'],row['product_id'],qty,'qaytarish',f'Savdo #{sale_id[:8]}',now(),user['id'],branch_id))
        audit(db,store['id'],user,'SALE_RETURN',{'sale_id':sale_id,'total':total,'credit_reduction':credit,'refund_cash':cash,'refund_card':card})
    return {'ok':True,'id':return_id,'total':total,'credit_reduction':credit,'refund_cash':cash,'refund_card':card}


# DONCHI public demo inquiries — local MVP, restricted platform review.
# PII is stored only in the local server database; do not use on public internet
# without a privacy policy, HTTPS, retention controls and proper spam protection.
from collections import defaultdict
from threading import Lock
LEAD_IP_WINDOW = defaultdict(list)
LEAD_LOCK = Lock()

class DemoInquiry(BaseModel):
    name: str = Field(min_length=2,max_length=100)
    phone: str = Field(min_length=7,max_length=25)
    business: str = Field(default='Yem do‘koni',max_length=80)
    city: str = Field(default='',max_length=80)
    consent: bool = False
    website: str = Field(default='',max_length=100) # honeypot

class InquiryStatus(BaseModel):
    status: str

with connection(write=True) as db:
    db.execute("""CREATE TABLE IF NOT EXISTS demo_inquiries(
      id TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,
      business TEXT NOT NULL,city TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'new',
      created_at TEXT NOT NULL)""")

@app.post('/api/public/inquiries',status_code=201)
def submit_inquiry(payload:DemoInquiry,request:Request):
    if payload.website.strip(): return {'ok':True} # silent bot honeypot
    if not payload.consent: http(422,'Ma’lumotlarni qayta ishlashga rozilik kerak')
    if not re.fullmatch(r'[+0-9() .-]{7,25}',payload.phone.strip()):http(422,'Telefon raqamini to‘g‘ri kiriting')
    name=clean_name(payload.name.strip(),100)
    key=request.client.host if request.client else 'anonymous'
    timestamp=time.monotonic()
    with LEAD_LOCK:
        active=[v for v in LEAD_IP_WINDOW[key] if timestamp-v < 600]
        if len(active)>=3:http(429,'Juda ko‘p so‘rov. Keyinroq urinib ko‘ring')
        active.append(timestamp)
        LEAD_IP_WINDOW[key]=active
    with connection(write=True) as db:
        db.execute('INSERT INTO demo_inquiries(id,name,phone,business,city,status,created_at) VALUES(?,?,?,?,?,?,?)',
                   (uid(),name,payload.phone.strip(),payload.business.strip() or 'Yem do‘koni',payload.city.strip(),'new',now()))
    return {'ok':True,'message':'Murojaat qabul qilindi'}

@app.get('/api/platform/inquiries')
def platform_inquiries(user=Depends(get_user)):
    role(user,['superadmin'])
    with connection() as db:
        return {'inquiries':allrows(db,'SELECT * FROM demo_inquiries ORDER BY created_at DESC LIMIT 300')}

@app.post('/api/platform/inquiries/{inquiry_id}/status')
def update_inquiry(inquiry_id:str,payload:InquiryStatus,user=Depends(get_user)):
    role(user,['superadmin'])
    if payload.status not in ('new','contacted','closed'):http(422,'Holat noto‘g‘ri')
    with connection(write=True) as db:
        row=onerow(db,'SELECT id FROM demo_inquiries WHERE id=?',(inquiry_id,))
        if not row:http(404,'Murojaat topilmadi')
        db.execute('UPDATE demo_inquiries SET status=? WHERE id=?',(payload.status,inquiry_id))
        audit(db,None,user,'INQUIRY_STATUS',{'id':inquiry_id,'status':payload.status})
    return {'ok':True}

extra_summary,smart_insights,branch_for,stock_at,adjust_branch,consume_lots = __import__('v5_features').install(app)

@app.get('/api/health')
def health():
    """Readiness: verify SQLite is actually accessible before reporting success."""
    try:
        with connection() as db:
            db.execute('SELECT 1 FROM users LIMIT 1').fetchone()
    except sqlite3.Error:
        # Never expose DB paths, statements or credentials in public responses.
        return JSONResponse(
            status_code=503,
            content={'ok': False, 'service': 'DONCHI 1.0', 'status': 'database_unavailable'},
            headers={'Cache-Control': 'no-store', 'Retry-After': '10'},
        )
    return {'ok': True, 'service': 'DONCHI 1.0', 'status': 'ready', 'time': now()}

# The web UI is intentionally served from the same origin as the API.
from platform_admin import totp_required, verify_login_totp

app.mount('/',StaticFiles(directory=BASE/'web',html=True),name='web')
