"""DONCHI Super Admin account and platform settings (demo SQLite backend)."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, re, secrets, sqlite3, struct, tempfile, time, urllib.parse, urllib.request, urllib.error
from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from server import app, DB, DATA, connection, onerow, allrows, audit, get_user, role, now, checkpwd, COOKIE_NAME

STARTED=time.monotonic()
DEFAULTS={'brand_name':'DONCHI Enterprise','tagline':'Savdo, ombor va nasiyani bir joydan boshqaring','support_phone':'','support_email':'','logo':'',
          'telegram_enabled':False,'telegram_chat_id':'','notify_new_store':True,'notify_service_errors':True}
PLANS={'Start':(0,30,2,1),'Business':(99000,30,8,2),'Premium':(199000,30,25,6),'Enterprise':(399000,30,100,30)}
with connection(write=True) as db:
    db.execute('CREATE TABLE IF NOT EXISTS platform_preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS platform_plan_catalog(name TEXT PRIMARY KEY,price INTEGER NOT NULL,days INTEGER NOT NULL,max_users INTEGER NOT NULL,max_branches INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS platform_totp(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,last_used INTEGER NOT NULL DEFAULT -1)')
    for name,fields in PLANS.items():
        db.execute('INSERT OR IGNORE INTO platform_plan_catalog VALUES(?,?,?,?,?)',(name,*fields))

def _admin(user): role(user,('superadmin',))
def _prefs(db):
    result=DEFAULTS.copy()
    for row in db.execute('SELECT key,value FROM platform_preferences'):
        if row['key'] in DEFAULTS: result[row['key']]=json.loads(row['value'])
    return result
def _save(db,key,value):
    db.execute('INSERT INTO platform_preferences(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value,ensure_ascii=False)))
def _otp(secret,counter):
    h=hmac.new(base64.b32decode(secret,casefold=True),struct.pack('>Q',counter),hashlib.sha1).digest()
    offset=h[-1]&15
    return f'{(struct.unpack(">I",h[offset:offset+4])[0]&0x7fffffff)%1000000:06d}'
def _otp_counter(secret,code,last=-1):
    if not re.fullmatch(r'\d{6}',str(code or '')): return None
    current=int(time.time()//30)
    for counter in (current-1,current,current+1):
        if counter>last and hmac.compare_digest(_otp(secret,counter),str(code)): return counter
    return None
def totp_required(user_id):
    with connection() as db: row=onerow(db,'SELECT enabled FROM platform_totp WHERE user_id=?',(user_id,))
    return bool(row and row['enabled'])
def verify_login_totp(user_id,code):
    with connection(write=True) as db:
        row=onerow(db,'SELECT secret,enabled,last_used FROM platform_totp WHERE user_id=?',(user_id,))
        if not row or not row['enabled']: return True
        counter=_otp_counter(row['secret'],code,row['last_used'])
        if counter is None: return False
        db.execute('UPDATE platform_totp SET last_used=? WHERE user_id=?',(counter,user_id))
    return True

def _rotate_admin_sessions(db, request, user):
    """Keep the verified current browser session, invalidate all others.

    Also increments the account session version to invalidate legacy bearer
    tokens issued before a 2FA security change.
    """
    raw = request.cookies.get(COOKIE_NAME, '')
    if not raw:
        raise HTTPException(403, 'Xavfsizlik sozlamasi uchun brauzer sessiyasi kerak')
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    current = onerow(db, 'SELECT token_hash FROM device_sessions WHERE token_hash=? AND user_id=? AND revoked_at IS NULL', (token_hash, user['id']))
    if not current:
        raise HTTPException(403, 'Faol brauzer sessiyasi talab qilinadi')
    version = user['session_version'] + 1
    db.execute('UPDATE users SET session_version=? WHERE id=?', (version, user['id']))
    db.execute('UPDATE device_sessions SET revoked_at=? WHERE user_id=? AND token_hash<>? AND revoked_at IS NULL',
               (int(time.time()), user['id'], token_hash))
    db.execute('UPDATE device_sessions SET session_version=? WHERE token_hash=?', (version, token_hash))


class ProfileIn(BaseModel):
    username:str=Field(min_length=4,max_length=60)
    full_name:str=Field(min_length=2,max_length=120)
    current_password:str=Field(min_length=1)
class BrandIn(BaseModel):
    brand_name:str=Field(min_length=2,max_length=90)
    tagline:str=Field(max_length=180)
    support_phone:str=Field(max_length=60)
    support_email:str=Field(max_length=100)
    logo:str=Field(default='',max_length=270000)
class PlanIn(BaseModel):
    price:int=Field(ge=0,le=100000000)
    days:int=Field(ge=1,le=730)
    max_users:int=Field(ge=1,le=10000)
    max_branches:int=Field(ge=1,le=1000)
class NotifyIn(BaseModel):
    telegram_enabled:bool=False
    telegram_chat_id:str=Field(default='',max_length=50)
    notify_new_store:bool=True
    notify_service_errors:bool=True
class OTPIn(BaseModel): code:str=Field(min_length=6,max_length=6)
class DisableOTP(BaseModel):
    code:str=Field(min_length=6,max_length=6)
    current_password:str=Field(min_length=1)

@app.get('/api/platform-admin/settings')
def pa_settings(request:Request,user=Depends(get_user)):
    _admin(user)
    stamp=int(time.time())
    raw=request.cookies.get(COOKIE_NAME,'')
    current_hash=hashlib.sha256(raw.encode()).hexdigest() if raw else ''
    with connection() as db:
        prefs=_prefs(db)
        plans=allrows(db,'SELECT * FROM platform_plan_catalog ORDER BY CASE name WHEN "Start" THEN 1 WHEN "Business" THEN 2 WHEN "Premium" THEN 3 ELSE 4 END')
        sessions=allrows(db,'SELECT token_hash,created_at,last_seen,expires_at FROM device_sessions WHERE user_id=? AND revoked_at IS NULL AND expires_at>? ORDER BY last_seen DESC LIMIT 30',(user['id'],stamp))
        sess=[{'id':hashlib.sha256(s['token_hash'].encode()).hexdigest()[:24],'created_at':s['created_at'],'last_seen':s['last_seen'],
              'expires_at':s['expires_at'],'current':s['token_hash']==current_hash} for s in sessions]
        logs=allrows(db,'SELECT username,action,details,created_at FROM audit ORDER BY created_at DESC LIMIT 80')
        twofa=onerow(db,'SELECT enabled FROM platform_totp WHERE user_id=?',(user['id'],))
        counts={name:db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ('stores','users','sales','products','audit')}
    fs=os.statvfs(DATA)
    try: size=DB.stat().st_size
    except OSError: size=0
    # A non-empty database path does not prove durability. Render's free
    # service has no persistent disk attached. Only a verified infrastructure
    # migration can remove this warning.
    render_free = bool(os.environ.get('RENDER')) and os.environ.get('RENDER_SERVICE_TYPE','web')=='web'
    storage_warning = (
        'Render Free SQLite: qayta ishga tushganda ma’lumotlar yo‘qolishi mumkin.'
        if render_free else
        'SQLite bazasi ishlayapti, lekin doimiy saqlash alohida tasdiqlanishi kerak.'
    )
    try:
        with connection() as check_db:
            integrity = check_db.execute('PRAGMA quick_check(1)').fetchone()[0]
    except sqlite3.DatabaseError:
        integrity = 'database_error'
    return {'profile':{'username':user['username'],'full_name':user['full_name']},
            'brand':{k:prefs[k] for k in ('brand_name','tagline','support_phone','support_email','logo')},
            'notifications':{k:prefs[k] for k in ('telegram_enabled','telegram_chat_id','notify_new_store','notify_service_errors')},
            'telegram_token_configured':bool(os.environ.get('DONCHI_TELEGRAM_BOT_TOKEN')),
            'plans':plans,'sessions':sess,'audit':logs,'totp_enabled':bool(twofa and twofa['enabled']),
            'monitor':{'uptime_seconds':int(time.monotonic()-STARTED),'database_bytes':size,
                       'disk_available_bytes':fs.f_bavail*fs.f_frsize,'counts':counts,'server_time':now(),
                       'mode':'SQLite (doimiy saqlash tasdiqlanmagan)',
                       'storage_warning':storage_warning,
                       'integrity_check':integrity,
                       'automatic_offsite_backup':False,
                       'backup_restore_supported':False}}

@app.put('/api/platform-admin/profile')
def pa_profile(body:ProfileIn,user=Depends(get_user)):
    _admin(user)
    username=body.username.strip().lower()
    name=body.full_name.strip()
    if not re.fullmatch(r'[a-z0-9_.-]{4,60}',username): raise HTTPException(422,'Login formati noto‘g‘ri')
    if not name: raise HTTPException(422,'Ismni kiriting')
    with connection(write=True) as db:
        original=onerow(db,'SELECT password_hash FROM users WHERE id=?',(user['id'],))
        if not original or not checkpwd(body.current_password,original['password_hash']): raise HTTPException(403,'Joriy parol noto‘g‘ri')
        if username!=user['username'] and onerow(db,'SELECT id FROM users WHERE username=?',(username,)):
            raise HTTPException(409,'Bu login band')
        db.execute('UPDATE users SET username=?,full_name=? WHERE id=?',(username,name,user['id']))
        audit(db,None,user,'PLATFORM_PROFILE_CHANGED',{'username':username})
    return {'ok':True,'user':{'username':username,'full_name':name}}

@app.put('/api/platform-admin/brand')
def pa_brand(body:BrandIn,user=Depends(get_user)):
    _admin(user)
    logo=body.logo.strip()
    if logo and not re.fullmatch(r'data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+',logo):
        raise HTTPException(422,'Logotip PNG/JPG/WEBP bo‘lishi kerak')
    if body.support_email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',body.support_email.strip()):
        raise HTTPException(422,'Email noto‘g‘ri')
    with connection(write=True) as db:
        for key in ('brand_name','tagline','support_phone','support_email'): _save(db,key,getattr(body,key).strip())
        _save(db,'logo',logo)
        audit(db,None,user,'PLATFORM_BRAND_CHANGED',{'brand_name':body.brand_name})
    return {'ok':True}

@app.put('/api/platform-admin/plans/{name}')
def pa_plan(name:str,body:PlanIn,user=Depends(get_user)):
    _admin(user)
    if name not in PLANS: raise HTTPException(404,'Tarif topilmadi')
    with connection(write=True) as db:
        db.execute('UPDATE platform_plan_catalog SET price=?,days=?,max_users=?,max_branches=? WHERE name=?',
                   (body.price,body.days,body.max_users,body.max_branches,name))
        audit(db,None,user,'PLATFORM_PLAN_CHANGED',{'plan':name,'price':body.price})
    return {'ok':True}

@app.put('/api/platform-admin/notifications')
def pa_notifications(body:NotifyIn,user=Depends(get_user)):
    _admin(user)
    if body.telegram_chat_id and not re.fullmatch(r'-?\d{3,20}',body.telegram_chat_id):
        raise HTTPException(422,'Telegram Chat ID noto‘g‘ri')
    with connection(write=True) as db:
        for key in ('telegram_enabled','telegram_chat_id','notify_new_store','notify_service_errors'):
            _save(db,key,getattr(body,key))
        audit(db,None,user,'PLATFORM_NOTIFICATIONS_CHANGED',{'enabled':body.telegram_enabled})
    return {'ok':True}

@app.post('/api/platform-admin/notifications/test')
def pa_telegram_test(user=Depends(get_user)):
    _admin(user)
    token=os.environ.get('DONCHI_TELEGRAM_BOT_TOKEN','')
    with connection() as db: prefs=_prefs(db)
    if not token or not prefs['telegram_enabled'] or not prefs['telegram_chat_id']:
        raise HTTPException(409,'Telegram tokeni Render Environment va Chat ID sozlanishi kerak')
    params=urllib.parse.urlencode({'chat_id':prefs['telegram_chat_id'],'text':'DONCHI Enterprise test bildirishnomasi'}).encode()
    try:
        req=urllib.request.Request('https://api.telegram.org/bot'+token+'/sendMessage',data=params,method='POST')
        with urllib.request.urlopen(req,timeout=6) as response:
            if not json.load(response).get('ok'): raise ValueError('Telegram failed')
    except (urllib.error.URLError,ValueError,TimeoutError) as error:
        raise HTTPException(502,'Telegram yuborilmadi. Token va Chat ID ni tekshiring') from error
    with connection(write=True) as db: audit(db,None,user,'PLATFORM_TELEGRAM_TEST',{})
    return {'ok':True}

@app.post('/api/platform-admin/2fa/start')
def pa_2fa_start(user=Depends(get_user)):
    _admin(user)
    with connection(write=True) as db:
        old=onerow(db,'SELECT enabled FROM platform_totp WHERE user_id=?',(user['id'],))
        if old and old['enabled']: raise HTTPException(409,'2FA allaqachon yoqilgan')
        secret=base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
        db.execute('INSERT INTO platform_totp(user_id,secret,enabled,last_used) VALUES(?,?,0,-1) ON CONFLICT(user_id) DO UPDATE SET secret=excluded.secret,enabled=0,last_used=-1',(user['id'],secret))
    uri='otpauth://totp/'+urllib.parse.quote('DONCHI:'+user['username'])+'?'+urllib.parse.urlencode({'secret':secret,'issuer':'DONCHI','digits':'6','period':'30'})
    return {'secret':secret,'uri':uri}

@app.post('/api/platform-admin/2fa/confirm')
def pa_2fa_confirm(body:OTPIn,request:Request,user=Depends(get_user)):
    _admin(user)
    with connection(write=True) as db:
        row=onerow(db,'SELECT secret,enabled FROM platform_totp WHERE user_id=?',(user['id'],))
        if not row or row['enabled'] or _otp_counter(row['secret'],body.code) is None:
            raise HTTPException(400,'Kod noto‘g‘ri yoki 2FA allaqachon yoqilgan')
        _rotate_admin_sessions(db, request, user)
        db.execute('UPDATE platform_totp SET enabled=1,last_used=-1 WHERE user_id=?',(user['id'],))
        audit(db,None,user,'PLATFORM_2FA_ENABLED',{})
    return {'ok':True}

@app.post('/api/platform-admin/2fa/disable')
def pa_2fa_disable(body:DisableOTP,request:Request,user=Depends(get_user)):
    _admin(user)
    with connection(write=True) as db:
        account=onerow(db,'SELECT password_hash FROM users WHERE id=?',(user['id'],))
        row=onerow(db,'SELECT secret,enabled FROM platform_totp WHERE user_id=?',(user['id'],))
        if not account or not checkpwd(body.current_password,account['password_hash']) or not row or not row['enabled'] or _otp_counter(row['secret'],body.code) is None:
            raise HTTPException(403,'Parol yoki 2FA kodi noto‘g‘ri')
        _rotate_admin_sessions(db, request, user)
        db.execute('DELETE FROM platform_totp WHERE user_id=?',(user['id'],))
        audit(db,None,user,'PLATFORM_2FA_DISABLED',{})
    return {'ok':True}

@app.post('/api/platform-admin/sessions/revoke-others')
def pa_revoke_other_sessions(request:Request,user=Depends(get_user)):
    _admin(user)
    raw=request.cookies.get(COOKIE_NAME,'')
    if not raw: raise HTTPException(403,'Brauzer sessiyasi kerak')
    current=hashlib.sha256(raw.encode()).hexdigest()
    with connection(write=True) as db:
        db.execute('UPDATE device_sessions SET revoked_at=? WHERE user_id=? AND token_hash<>? AND revoked_at IS NULL',
                   (int(time.time()),user['id'],current))
        audit(db,None,user,'PLATFORM_OTHER_SESSIONS_REVOKED',{})
    return {'ok':True}

@app.get('/api/platform-admin/backup')
def pa_backup(user=Depends(get_user)):
    _admin(user)
    fd,path=tempfile.mkstemp(prefix='donchi-backup-',suffix='.sqlite3')
    os.close(fd)
    try:
        os.chmod(path,0o600)
        source=sqlite3.connect(DB)
        try:
            destination=sqlite3.connect(path)
            try:
                source.backup(destination)
                check=destination.execute('PRAGMA quick_check(1)').fetchone()
                if not check or check[0]!='ok':
                    raise sqlite3.DatabaseError('Backup integrity check failed')
            finally: destination.close()
        finally: source.close()
        with connection(write=True) as db: audit(db,None,user,'PLATFORM_DB_BACKUP_DOWNLOADED',{})
    except Exception:
        os.unlink(path)
        raise
    return FileResponse(path,filename='DONCHI-full-backup-'+time.strftime('%Y-%m-%d')+'.sqlite3',
                        media_type='application/octet-stream',background=BackgroundTask(os.unlink,path),
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
