"""YemPro 5.0 opt-in enterprise features. Local MVP, tenant-isolated.
External Telegram requires env YEMPRO_TELEGRAM_BOT_TOKEN and network access.
This module intentionally does not invoke any paid AI API; insights are explainable rules.
"""
import json, os, re, sqlite3, urllib.request, urllib.error
from datetime import date, datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel
from fastapi import Request, Depends

def install(app):
    # Loaded late, after server's helpers exist; no side effects during import.
    from server import (connection, onerow, allrows, now, uid, audit, money, clean_name,
                        http, get_user, store_from, role, require_feature, sql_conn)
    schema='''
    CREATE TABLE IF NOT EXISTS branches(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),name TEXT NOT NULL,address TEXT DEFAULT '',is_default INTEGER NOT NULL DEFAULT 0,created_at TEXT);
    CREATE INDEX IF NOT EXISTS branches_by_store ON branches(store_id);
    CREATE TABLE IF NOT EXISTS branch_stock(store_id TEXT NOT NULL REFERENCES stores(id),branch_id TEXT NOT NULL REFERENCES branches(id),product_id TEXT NOT NULL REFERENCES products(id),qty REAL NOT NULL DEFAULT 0,PRIMARY KEY(branch_id,product_id));
    CREATE TABLE IF NOT EXISTS inventory_lots(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),branch_id TEXT NOT NULL REFERENCES branches(id),product_id TEXT NOT NULL REFERENCES products(id),lot_code TEXT NOT NULL,manufacturer TEXT DEFAULT '',expires_on TEXT,quantity_initial REAL NOT NULL,quantity_remaining REAL NOT NULL,unit_cost REAL NOT NULL,created_at TEXT);
    CREATE INDEX IF NOT EXISTS lots_store_product ON inventory_lots(store_id,product_id,branch_id);
    CREATE TABLE IF NOT EXISTS branch_transfers(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),from_branch TEXT NOT NULL REFERENCES branches(id),to_branch TEXT NOT NULL REFERENCES branches(id),product_id TEXT NOT NULL REFERENCES products(id),qty REAL NOT NULL,created_by TEXT NOT NULL,created_at TEXT);
    CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),sale_id TEXT REFERENCES sales(id),customer_id TEXT REFERENCES customers(id),destination TEXT NOT NULL,driver TEXT DEFAULT '',phone TEXT DEFAULT '',fee REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'new',note TEXT DEFAULT '',created_at TEXT,updated_at TEXT);
    CREATE TABLE IF NOT EXISTS supplier_bills(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),supplier TEXT NOT NULL,reference TEXT DEFAULT '',amount REAL NOT NULL,paid REAL NOT NULL DEFAULT 0,due_on TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS supplier_payments(id TEXT PRIMARY KEY,bill_id TEXT NOT NULL REFERENCES supplier_bills(id),store_id TEXT NOT NULL REFERENCES stores(id),amount REAL NOT NULL,created_at TEXT,user_id TEXT);
    CREATE TABLE IF NOT EXISTS telegram_settings(store_id TEXT PRIMARY KEY REFERENCES stores(id),chat_id TEXT NOT NULL DEFAULT '',enabled INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS releases(id TEXT PRIMARY KEY,version TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT);
    CREATE TABLE IF NOT EXISTS login_guards(login_key TEXT PRIMARY KEY,failed INTEGER NOT NULL DEFAULT 0,locked_until TEXT DEFAULT '',last_failed TEXT DEFAULT '');
    '''
    with connection() as db:
        db.executescript(schema)
        for table,defs in {
            'customers':{'tag':"TEXT DEFAULT 'Oddiy'",'notes':"TEXT DEFAULT ''",'credit_limit':'REAL DEFAULT 0','loyalty_points':'INTEGER DEFAULT 0'},
            'sales':{'branch_id':'TEXT REFERENCES branches(id)'},
            'movements':{'branch_id':'TEXT REFERENCES branches(id)'},
            'users':{'session_version':'INTEGER NOT NULL DEFAULT 0'}
        }.items():
            existing={row[1] for row in db.execute(f'PRAGMA table_info({table})')}
            for col,decl in defs.items():
                if col not in existing: db.execute(f'ALTER TABLE {table} ADD COLUMN {col} {decl}')
    with connection(write=True) as db:
        for store in allrows(db,'SELECT id FROM stores'):
            sid=store['id']
            existing=onerow(db,'SELECT id FROM branches WHERE store_id=? ORDER BY is_default DESC LIMIT 1',(sid,))
            if not existing:
                bid=uid();db.execute('INSERT INTO branches VALUES(?,?,?,?,?,?)',(bid,sid,'Asosiy filial','',1,now()))
            else: bid=existing['id']
            for p in allrows(db,'SELECT id,stock FROM products WHERE store_id=?',(sid,)):
                qty=onerow(db,'SELECT qty FROM branch_stock WHERE branch_id=? AND product_id=?',(bid,p['id']))
                # Migration only for products that have no branch records yet.
                any_record=onerow(db,'SELECT 1 AS found FROM branch_stock WHERE store_id=? AND product_id=? LIMIT 1',(sid,p['id']))
                if not any_record: db.execute('INSERT INTO branch_stock VALUES(?,?,?,?)',(sid,bid,p['id'],p['stock']))
            db.execute('UPDATE sales SET branch_id=? WHERE store_id=? AND branch_id IS NULL',(bid,sid))
            db.execute('UPDATE movements SET branch_id=? WHERE store_id=? AND branch_id IS NULL',(bid,sid))

    def branch_for(db, sid, request):
        branch_id=request.headers.get('X-Branch-ID')
        if branch_id:
            branch=onerow(db,'SELECT * FROM branches WHERE id=? AND store_id=?',(branch_id,sid))
            if not branch:http(403,'Filialga ruxsat yo‘q')
            return branch
        branch=onerow(db,'SELECT * FROM branches WHERE store_id=? ORDER BY is_default DESC,created_at LIMIT 1',(sid,))
        if not branch:http(409,'Filial mavjud emas')
        return branch

    def stock_at(db, sid, branch_id, pid):
        row=onerow(db,'SELECT qty FROM branch_stock WHERE store_id=? AND branch_id=? AND product_id=?',(sid,branch_id,pid))
        return float(row['qty']) if row else 0.

    def adjust_branch(db, sid, branch_id, pid, delta):
        exists=onerow(db,'SELECT qty FROM branch_stock WHERE store_id=? AND branch_id=? AND product_id=?',(sid,branch_id,pid))
        current=exists['qty'] if exists else 0.
        if current+delta < -0.000001:http(409,'Tanlangan filialda mahsulot yetarli emas')
        db.execute('INSERT INTO branch_stock(store_id,branch_id,product_id,qty) VALUES(?,?,?,?) ON CONFLICT(branch_id,product_id) DO UPDATE SET qty=qty+excluded.qty',(sid,branch_id,pid,delta))

    # Preserve lot metadata as stock is transferred. Legacy unbatched stock can be moved too.
    def transfer_lots(db,sid,source,target,pid,qty):
        remaining=qty
        lots=allrows(db,'SELECT * FROM inventory_lots WHERE store_id=? AND branch_id=? AND product_id=? AND quantity_remaining>0 ORDER BY CASE WHEN expires_on IS NULL THEN 1 ELSE 0 END,expires_on,created_at',(sid,source,pid))
        for lot in lots:
            take=min(lot['quantity_remaining'],remaining)
            if take<=0:break
            db.execute('UPDATE inventory_lots SET quantity_remaining=quantity_remaining-? WHERE id=?',(take,lot['id']))
            db.execute('INSERT INTO inventory_lots VALUES(?,?,?,?,?,?,?,?,?,?,?)',(uid(),sid,target,pid,lot['lot_code'],lot['manufacturer'],lot['expires_on'],take,take,lot['unit_cost'],now()))
            remaining-=take
            if remaining<=0.00000001:break

    # FIFO lot consumption in the corresponding branch. Legacy opening stock stays unbatched.
    def consume_lots(db, sid, branch_id, pid, qty):
        remaining=qty
        for lot in allrows(db,'SELECT id,quantity_remaining FROM inventory_lots WHERE store_id=? AND branch_id=? AND product_id=? AND quantity_remaining>0 ORDER BY CASE WHEN expires_on IS NULL THEN 1 ELSE 0 END,expires_on,created_at',(sid,branch_id,pid)):
            take=min(remaining,lot['quantity_remaining'])
            db.execute('UPDATE inventory_lots SET quantity_remaining=quantity_remaining-? WHERE id=?',(take,lot['id']))
            remaining-=take
            if remaining<=0.0000001:break

    class BranchIn(BaseModel): name:str; address:str=''
    class TransferIn(BaseModel): from_branch:str; to_branch:str; product_id:str; qty:float
    class LotIn(BaseModel): product_id:str; branch_id:str; lot_code:str; manufacturer:str=''; expires_on:Optional[str]=None; qty:float; unit_cost:float=0
    class DeliveryIn(BaseModel): sale_id:Optional[str]=None; customer_id:Optional[str]=None; destination:str; driver:str=''; phone:str=''; fee:float=0; note:str=''
    class DeliveryStatus(BaseModel): status:str
    class SupplierBillIn(BaseModel): supplier:str; reference:str=''; amount:float; due_on:Optional[str]=None
    class SupplierPayIn(BaseModel): amount:float
    class CRMIn(BaseModel): tag:str='Oddiy'; notes:str=''; credit_limit:float=0; loyalty_points:int=0
    class TelegramIn(BaseModel): chat_id:str; enabled:bool=True
    class ReleaseIn(BaseModel): version:str; title:str; body:str; active:bool=True

    def valid_date(x):
        if x in (None,''):return None
        try:return date.fromisoformat(x).isoformat()
        except (ValueError,TypeError):http(422,'Sana YYYY-MM-DD bo‘lishi kerak')

    def extra_summary(db,store,branch_id=None):
        sid=store['id']
        branches=allrows(db,'SELECT * FROM branches WHERE store_id=? ORDER BY is_default DESC,created_at',(sid,))
        if branch_id and branch_id not in [b['id'] for b in branches]:http(403,'Filialga ruxsat yo‘q')
        if not branch_id:branch_id=branches[0]['id'] if branches else None
        branchqty=allrows(db,'SELECT product_id,qty FROM branch_stock WHERE store_id=? AND branch_id=?',(sid,branch_id)) if branch_id else []
        lots=allrows(db,'SELECT l.*,p.name AS product_name,b.name AS branch_name FROM inventory_lots l JOIN products p ON p.id=l.product_id JOIN branches b ON b.id=l.branch_id WHERE l.store_id=? ORDER BY l.created_at DESC LIMIT 160',(sid,))
        transfers=allrows(db,'SELECT t.*,p.name AS product_name,fb.name AS from_name,tb.name AS to_name FROM branch_transfers t JOIN products p ON p.id=t.product_id JOIN branches fb ON fb.id=t.from_branch JOIN branches tb ON tb.id=t.to_branch WHERE t.store_id=? ORDER BY t.created_at DESC LIMIT 80',(sid,))
        deliveries=allrows(db,'SELECT d.*,c.name AS customer_name FROM deliveries d LEFT JOIN customers c ON c.id=d.customer_id WHERE d.store_id=? ORDER BY d.created_at DESC LIMIT 130',(sid,))
        bills=allrows(db,'SELECT * FROM supplier_bills WHERE store_id=? ORDER BY created_at DESC LIMIT 150',(sid,))
        notices=allrows(db,'SELECT id,version,title,body,created_at FROM releases WHERE active=1 ORDER BY created_at DESC LIMIT 15')
        tg=onerow(db,'SELECT chat_id,enabled FROM telegram_settings WHERE store_id=?',(sid,)) or {'chat_id':'','enabled':0}
        return {'branches':branches,'branch_id':branch_id,'branch_stock':{x['product_id']:x['qty'] for x in branchqty},'lots':lots,'transfers':transfers,'deliveries':deliveries,'supplier_bills':bills,'releases':notices,'telegram':tg,'telegram_configured':bool((os.environ.get('DONCHI_TELEGRAM_BOT_TOKEN') or os.environ.get('YEMPRO_TELEGRAM_BOT_TOKEN')))}

    def smart_insights(data):
        """Explainable local heuristics, NOT a machine learning model."""
        p=data.get('products',[]);sales=data.get('sales',[]);bal=data.get('balances',[])
        insights=[]
        low=[x for x in p if x['stock']<=x['min_stock']]
        if low:insights.append({'type':'warning','title':'Zaxira tugab bormoqda','body':f"{len(low)} ta mahsulot minimal chegaraga yetgan. Xarid ro‘yxatini tekshiring.",'target':'inventory'})
        if not sales:insights.append({'type':'info','title':'Savdo ma’lumoti kerak','body':'Yetarli savdo tarixi paydo bo‘lgach, talabni tahlil qilish mumkin.','target':'pos'})
        else:
            totals={}
            for s in sales:
                for item in s.get('lines',[]):totals[item['name']]=totals.get(item['name'],0)+item['qty']
            if totals:
                name=max(totals,key=totals.get);insights.append({'type':'success','title':'Ko‘p sotilgan mahsulot','body':f'{name}: oxirgi ko‘rsatilgan savdolarda {totals[name]:g} birlik sotilgan.','target':'products'})
        bad=[b for b in bal if b['balance']>0]
        if bad:
            biggest=max(bad,key=lambda x:x['balance'])
            insights.append({'type':'warning','title':'Nasiya nazorati','body':f"{biggest['name']}: eng katta ochiq qarz {biggest['balance']:,.0f} so‘m.",'target':'debts'})
        upcoming=[l for l in data.get('lots',[]) if l['quantity_remaining']>0 and l.get('expires_on') and l['expires_on']<=str(date.today()+timedelta(days=30))]
        if upcoming:insights.append({'type':'warning','title':'Partiyalarni tekshiring','body':f'{len(upcoming)} ta partiyaning yaroqlilik muddati 30 kun ichida tugaydi yoki o‘tgan.','target':'lots'})
        return insights

    @app.post('/api/v5/branches')
    def new_branch(payload:BranchIn,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner']);require_feature(db,shop,'branches')
            bid=uid();db.execute('INSERT INTO branches VALUES(?,?,?,?,?,?)',(bid,shop['id'],clean_name(payload.name),payload.address[:240],0,now()))
            audit(db,shop['id'],user,'BRANCH_CREATED',{'name':payload.name})
            return {'ok':True,'id':bid}

    @app.post('/api/v5/branches/transfer')
    def transfer(payload:TransferIn,request:Request,user=Depends(get_user)):
        q=money(payload.qty)
        if q<=0 or payload.from_branch==payload.to_branch:http(422,'Miqdor va filiallarni tekshiring')
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager','warehouse']);require_feature(db,shop,'branches')
            for b in (payload.from_branch,payload.to_branch):
                if not onerow(db,'SELECT id FROM branches WHERE store_id=? AND id=?',(shop['id'],b)):http(403,'Filialga ruxsat yo‘q')
            if not onerow(db,'SELECT id FROM products WHERE id=? AND store_id=? AND active=1',(payload.product_id,shop['id'])):http(404,'Mahsulot topilmadi')
            adjust_branch(db,shop['id'],payload.from_branch,payload.product_id,-q)
            adjust_branch(db,shop['id'],payload.to_branch,payload.product_id,q)
            transfer_lots(db,shop['id'],payload.from_branch,payload.to_branch,payload.product_id,q)
            tid=uid();db.execute('INSERT INTO branch_transfers VALUES(?,?,?,?,?,?,?,?)',(tid,shop['id'],payload.from_branch,payload.to_branch,payload.product_id,q,user['id'],now()))
            audit(db,shop['id'],user,'STOCK_TRANSFER',{'from':payload.from_branch,'to':payload.to_branch,'qty':q})
        return {'ok':True,'id':tid}

    @app.post('/api/v5/lots')
    def new_lot(payload:LotIn,request:Request,user=Depends(get_user)):
        qty=money(payload.qty); cost=money(payload.unit_cost)
        if qty<=0:http(422,'Miqdor musbat bo‘lishi kerak')
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager','warehouse'])
            if not onerow(db,'SELECT id FROM products WHERE store_id=? AND id=? AND active=1',(shop['id'],payload.product_id)):http(404,'Mahsulot yo‘q')
            if not onerow(db,'SELECT id FROM branches WHERE store_id=? AND id=?',(shop['id'],payload.branch_id)):http(403,'Filial yo‘q')
            lid=uid()
            db.execute('INSERT INTO inventory_lots VALUES(?,?,?,?,?,?,?,?,?,?,?)',(lid,shop['id'],payload.branch_id,payload.product_id,clean_name(payload.lot_code,60),payload.manufacturer[:100],valid_date(payload.expires_on),qty,qty,cost,now()))
            adjust_branch(db,shop['id'],payload.branch_id,payload.product_id,qty)
            db.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,payload.product_id))
            db.execute('INSERT INTO movements(id,store_id,product_id,delta,reason,note,created_at,user_id,branch_id) VALUES(?,?,?,?,?,?,?,?,?)',(uid(),shop['id'],payload.product_id,qty,'partiya_kirim',payload.lot_code[:200],now(),user['id'],payload.branch_id))
            audit(db,shop['id'],user,'LOT_RECEIVED',{'lot':payload.lot_code,'qty':qty})
        return {'ok':True,'id':lid}

    @app.post('/api/v5/deliveries')
    def create_delivery(payload:DeliveryIn,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager','seller']);require_feature(db,shop,'delivery')
            if payload.sale_id and not onerow(db,'SELECT id FROM sales WHERE id=? AND store_id=?',(payload.sale_id,shop['id'])):http(404,'Savdo topilmadi')
            if payload.customer_id and not onerow(db,'SELECT id FROM customers WHERE id=? AND store_id=?',(payload.customer_id,shop['id'])):http(404,'Mijoz topilmadi')
            did=uid();db.execute('INSERT INTO deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,shop['id'],payload.sale_id,payload.customer_id,clean_name(payload.destination,250),payload.driver[:100],payload.phone[:60],money(payload.fee),'new',payload.note[:250],now(),now()))
            audit(db,shop['id'],user,'DELIVERY_CREATED',{'id':did})
        return {'ok':True,'id':did}

    @app.post('/api/v5/deliveries/{delivery_id}/status')
    def update_delivery(delivery_id:str,payload:DeliveryStatus,request:Request,user=Depends(get_user)):
        allowed={'new':['assigned','cancelled'],'assigned':['transit','cancelled'],'transit':['delivered','cancelled'],'delivered':[],'cancelled':[]}
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager','seller']);require_feature(db,shop,'delivery')
            d=onerow(db,'SELECT * FROM deliveries WHERE id=? AND store_id=?',(delivery_id,shop['id']))
            if not d:http(404,'Buyurtma topilmadi')
            if payload.status not in allowed[d['status']]:http(409,'Status ketma-ketligi noto‘g‘ri')
            db.execute('UPDATE deliveries SET status=?,updated_at=? WHERE id=?',(payload.status,now(),delivery_id))
            audit(db,shop['id'],user,'DELIVERY_STATUS',{'id':delivery_id,'status':payload.status})
        return {'ok':True}

    @app.post('/api/v5/bills')
    def new_bill(payload:SupplierBillIn,request:Request,user=Depends(get_user)):
        amt=money(payload.amount)
        if amt<=0:http(422,'Summa musbat bo‘lishi kerak')
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager']);require_feature(db,shop,'finance')
            bid=uid();db.execute('INSERT INTO supplier_bills VALUES(?,?,?,?,?,?,?,?)',(bid,shop['id'],clean_name(payload.supplier),payload.reference[:120],amt,0,valid_date(payload.due_on),now()))
            audit(db,shop['id'],user,'BILL_CREATED',{'id':bid,'amount':amt})
        return {'ok':True,'id':bid}

    @app.post('/api/v5/bills/{bill_id}/pay')
    def pay_bill(bill_id:str,payload:SupplierPayIn,request:Request,user=Depends(get_user)):
        amt=money(payload.amount)
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager']);require_feature(db,shop,'finance')
            b=onerow(db,'SELECT * FROM supplier_bills WHERE store_id=? AND id=?',(shop['id'],bill_id))
            if not b:http(404,'To‘lov hujjati topilmadi')
            if amt<=0 or amt>b['amount']-b['paid']+.001:http(422,'To‘lov qoldiqdan oshmasin')
            db.execute('UPDATE supplier_bills SET paid=paid+? WHERE id=?',(amt,bill_id))
            db.execute('INSERT INTO supplier_payments VALUES(?,?,?,?,?,?)',(uid(),bill_id,shop['id'],amt,now(),user['id']))
            audit(db,shop['id'],user,'BILL_PAID',{'id':bill_id,'amount':amt})
        return {'ok':True}

    @app.put('/api/v5/customers/{customer_id}/crm')
    def update_crm(customer_id:str,payload:CRMIn,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager']);require_feature(db,shop,'crm')
            if not onerow(db,'SELECT id FROM customers WHERE id=? AND store_id=?',(customer_id,shop['id'])):http(404,'Mijoz topilmadi')
            if payload.loyalty_points<0 or payload.loyalty_points>100000000:http(422,'Bonuslar noto‘g‘ri')
            db.execute('UPDATE customers SET tag=?,notes=?,credit_limit=?,loyalty_points=? WHERE id=? AND store_id=?',(payload.tag[:60],payload.notes[:600],money(payload.credit_limit),payload.loyalty_points,customer_id,shop['id']))
            audit(db,shop['id'],user,'CRM_UPDATED',{'customer_id':customer_id,'credit_limit':payload.credit_limit})
        return {'ok':True}

    @app.put('/api/v5/telegram')
    def set_telegram(payload:TelegramIn,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner']);require_feature(db,shop,'telegram')
            if payload.chat_id and not re.fullmatch(r'-?[0-9]{5,22}',payload.chat_id):http(422,'Telegram chat ID raqam bo‘lishi kerak')
            db.execute('INSERT INTO telegram_settings VALUES(?,?,?) ON CONFLICT(store_id) DO UPDATE SET chat_id=excluded.chat_id,enabled=excluded.enabled',(shop['id'],payload.chat_id,int(payload.enabled)))
            audit(db,shop['id'],user,'TELEGRAM_SETTINGS',{'enabled':payload.enabled})
        return {'ok':True}

    @app.post('/api/v5/telegram/digest')
    def send_digest(request:Request,user=Depends(get_user)):
        token=(os.environ.get('DONCHI_TELEGRAM_BOT_TOKEN') or os.environ.get('YEMPRO_TELEGRAM_BOT_TOKEN',''))
        if not token:http(409,'YEMPRO_TELEGRAM_BOT_TOKEN serverda sozlanmagan')
        with connection() as db:
            shop=store_from(request,user,db,['owner']);require_feature(db,shop,'telegram')
            t=onerow(db,'SELECT * FROM telegram_settings WHERE store_id=?',(shop['id'],))
            if not t or not t['enabled'] or not t['chat_id']:http(409,'Telegram chat ID va ruxsatni sozlang')
            gross=onerow(db,'SELECT COALESCE(SUM(subtotal),0) AS total FROM sales WHERE store_id=? AND created_at>=?',(shop['id'],now()[:10]+'T00:00:00'))['total']
            text=f"DONCHI hisoboti\n{shop['name']}\nBugungi savdolar (UTC): {gross:,.0f} so‘m\nVaqt: {now()}"
            chat_id=t['chat_id']
        # No token echoed, no chat ID returned. Manual opt-in only, no hidden scheduler.
        url=f'https://api.telegram.org/bot{token}/sendMessage'
        data=json.dumps({'chat_id':chat_id,'text':text}).encode()
        req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=7) as resp:
                answer=json.loads(resp.read(2000))
                if not answer.get('ok'):http(502,'Telegram xabarni qabul qilmadi')
        except (urllib.error.URLError,TimeoutError,ValueError):http(502,'Telegramga xabar yuborilmadi; internet va bot ruxsatini tekshiring')
        with connection(write=True) as db:audit(db,shop['id'],user,'TELEGRAM_DIGEST_SENT',{})
        return {'ok':True}

    @app.post('/api/v5/releases')
    def add_release(payload:ReleaseIn,user=Depends(get_user)):
        role(user,['superadmin'])
        with connection(write=True) as db:
            rid=uid();db.execute('INSERT INTO releases VALUES(?,?,?,?,?,?)',(rid,clean_name(payload.version,30),clean_name(payload.title,140),clean_name(payload.body,1200),int(payload.active),now()))
            audit(db,None,user,'RELEASE_PUBLISHED',{'version':payload.version,'id':rid})
        return {'ok':True,'id':rid}

    @app.post('/api/v5/releases/{rid}/status')
    def release_status(rid:str,payload:dict, user=Depends(get_user)):
        role(user,['superadmin'])
        if not isinstance(payload.get('active'),bool):http(422,'active kerak')
        with connection(write=True) as db:
            if not onerow(db,'SELECT id FROM releases WHERE id=?',(rid,)):http(404,'Yangilik topilmadi')
            db.execute('UPDATE releases SET active=? WHERE id=?',(int(payload['active']),rid))
            audit(db,None,user,'RELEASE_STATUS',{'id':rid,'active':payload['active']})
        return {'ok':True}

    @app.get('/api/v5/health')
    def health_v5():return {'ok':True,'version':'5.0.0','telegram_configured':bool((os.environ.get('DONCHI_TELEGRAM_BOT_TOKEN') or os.environ.get('YEMPRO_TELEGRAM_BOT_TOKEN')))}

    return extra_summary, smart_insights, branch_for, stock_at, adjust_branch, consume_lots
