"""Persistent DONCHI notifications, 21:00 Tashkent summaries and complete sales history."""
import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import Request, Depends

TZ = ZoneInfo("Asia/Tashkent")
LOG = logging.getLogger(__name__)


def install(app):
    from server import connection, allrows, onerow, now, uid, get_user, store_from, http

    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS store_notifications(
          id TEXT PRIMARY KEY,
          store_id TEXT NOT NULL REFERENCES stores(id),
          report_date TEXT NOT NULL,
          kind TEXT NOT NULL,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          created_at TEXT NOT NULL,
          read_at TEXT,
          UNIQUE(store_id,report_date,kind));
        CREATE INDEX IF NOT EXISTS store_notifications_order
          ON store_notifications(store_id,created_at);
        """)

    def day_bounds(day):
        local=datetime.fromisoformat(day).replace(tzinfo=TZ)
        return (local.astimezone(timezone.utc).isoformat(timespec='seconds'),
                (local+timedelta(days=1)).astimezone(timezone.utc).isoformat(timespec='seconds'))

    def total(db,sql,args):
        r=onerow(db,sql,args)
        return float(r['amount'] or 0) if r else 0.0

    def make_report(db,sid,day):
        start,end=day_bounds(day)
        s=onerow(db,"SELECT COUNT(*) AS n,COALESCE(SUM(subtotal),0) AS amount,COALESCE(SUM(cash_paid),0) AS cash,COALESCE(SUM(card_paid),0) AS card,COALESCE(SUM(debt),0) AS credit FROM sales WHERE store_id=? AND created_at>=? AND created_at<?",(sid,start,end))
        costs=total(db,"SELECT COALESCE(SUM(i.cost*i.qty),0) AS amount FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE s.store_id=? AND s.created_at>=? AND s.created_at<?",(sid,start,end))
        expenses=total(db,"SELECT COALESCE(SUM(amount),0) AS amount FROM expenses WHERE store_id=? AND created_at>=? AND created_at<?",(sid,start,end))
        returns=total(db,"SELECT COALESCE(SUM(total),0) AS amount FROM sale_returns WHERE store_id=? AND created_at>=? AND created_at<?",(sid,start,end))
        debtor_paid=total(db,"SELECT COALESCE(SUM(amount),0) AS amount FROM debt_payments WHERE store_id=? AND created_at>=? AND created_at<?",(sid,start,end))
        supplier_paid=total(db,"SELECT COALESCE(SUM(amount),0) AS amount FROM supplier_payments WHERE store_id=? AND created_at>=? AND created_at<?",(sid,start,end))
        purchases=total(db,"SELECT COALESCE(SUM(amount),0) AS amount FROM supplier_bills WHERE store_id=? AND created_at>=? AND created_at<?",(sid,start,end))
        supplier_debt=total(db,"SELECT COALESCE(SUM(amount-paid),0) AS amount FROM supplier_bills WHERE store_id=?",(sid,))
        debt_rows=allrows(db,"SELECT s.debt AS amount FROM sales s WHERE s.store_id=? AND s.debt>0",(sid,))
        total_customer_debt=round(sum(float(x['amount']) for x in debt_rows)-total(db,"SELECT COALESCE(SUM(amount),0) AS amount FROM debt_payments WHERE store_id=?",(sid,))-total(db,"SELECT COALESCE(SUM(credit_reduction),0) AS amount FROM sale_returns WHERE store_id=?",(sid,)),2)
        return dict(date=day,sales_count=s['n'],sales_total=round(s['amount'],2),cash=round(s['cash'],2),card=round(s['card'],2),new_credit=round(s['credit'],2),customer_repayments=round(debtor_paid,2),supplier_purchases=round(purchases,2),supplier_payments=round(supplier_paid,2),supplier_debt=round(supplier_debt,2),customer_debt=round(max(0,total_customer_debt),2),expenses=round(expenses,2),returns=round(returns,2),profit=round(s['amount']-costs-expenses-returns,2))

    def create_notification(db,sid,day):
        if onerow(db,"SELECT id FROM store_notifications WHERE store_id=? AND report_date=? AND kind='daily_report'",(sid,day)):
            return False
        report=make_report(db,sid,day)
        try:
            db.execute("""INSERT INTO store_notifications
              (id,store_id,report_date,kind,title,body,created_at,read_at)
              VALUES(?,?,?,?,?,?,?,NULL)""",
              (uid(),sid,day,'daily_report',day+' — soat 21:00 yakuniy hisobot',
               json.dumps(report,ensure_ascii=False),now()))
            return True
        except Exception:
            # Unique index protects against multiple Railway worker replicas.
            if onerow(db,"SELECT id FROM store_notifications WHERE store_id=? AND report_date=? AND kind='daily_report'",(sid,day)):
                return False
            raise

    def ensure_due(db,sid):
        local=datetime.now(TZ)
        if local.hour>=21:
            create_notification(db,sid,local.date().isoformat())

    @app.get('/api/v7/notifications')
    def list_notifications(request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            ensure_due(db,shop['id'])
            rows=allrows(db,'SELECT * FROM store_notifications WHERE store_id=? ORDER BY created_at DESC LIMIT 365',(shop['id'],))
            for n in rows:
                try:n['report']=json.loads(n['body'])
                except (ValueError,TypeError):n['report']={}
            return {'items':rows,'unread':sum(n['read_at'] is None for n in rows),'timezone':'Asia/Tashkent','report_hour':21}

    @app.post('/api/v7/notifications/{notification_id}/read')
    def mark_read(notification_id:str,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            row=onerow(db,'SELECT id FROM store_notifications WHERE id=? AND store_id=?',(notification_id,shop['id']))
            if not row:http(404,'Xabarnoma topilmadi')
            db.execute('UPDATE store_notifications SET read_at=COALESCE(read_at,?) WHERE id=? AND store_id=?',(now(),notification_id,shop['id']))
            return {'ok':True}

    @app.get('/api/v7/sales')
    def sales_history(request:Request,user=Depends(get_user),limit:int=200,offset:int=0):
        if limit<1 or limit>500 or offset<0:http(422,'Sahifalash parametrlari noto‘g‘ri')
        with connection() as db:
            shop=store_from(request,user,db,['owner','manager','seller'])
            sid=shop['id']
            sales=allrows(db,"SELECT s.*,c.name AS customer_name,u.full_name AS cashier_name FROM sales s LEFT JOIN customers c ON c.id=s.customer_id LEFT JOIN users u ON u.id=s.cashier_id WHERE s.store_id=? ORDER BY s.created_at DESC,s.id DESC LIMIT ? OFFSET ?",(sid,limit,offset))
            for s in sales:
                s['lines']=allrows(db,'SELECT product_id,name,qty,unit,price,cost FROM sale_items WHERE sale_id=?',(s['id'],))
                s['payment_label']='Nasiya' if s['debt']>0 and s['cash_paid']==0 and s['card_paid']==0 else ('Aralash' if sum(float(v)>0 for v in (s['cash_paid'],s['card_paid'],s['debt']))>1 else ('Naqd' if s['cash_paid']>0 else 'Karta'))
            count=onerow(db,'SELECT COUNT(*) AS n FROM sales WHERE store_id=?',(sid,))['n']
            return {'items':sales,'total':count,'limit':limit,'offset':offset}

    def tick():
        # Automatically generate a durable report at 21:00 local time.
        # The request handler also backfills when an instance was asleep.
        while True:
            try:
                local=datetime.now(TZ)
                if local.hour>=21:
                    with connection(write=True) as db:
                        stores=allrows(db,"SELECT id FROM stores WHERE status='active'")
                        for store in stores:create_notification(db,store['id'],local.date().isoformat())
            except Exception:
                LOG.exception('Daily DONCHI report generation failed')
            time.sleep(45)

    threading.Thread(target=tick,name='donchi-daily-notifications',daemon=True).start()
