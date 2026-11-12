"""Persistent, owner-scoped in-app notifications for DONCHI Owner Pro.

Daily reports are snapshots for 00:00–20:00 Asia/Tashkent and remain in history
after they are marked read. Background generation catches up after application
downtime; reliable retention requires a persistent database and offsite backups.
"""
import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import datetime, time, timezone
from fastapi import Depends, HTTPException, Query, Request

LOGGER=logging.getLogger(__name__)

def install(app, *, get_user, connection, store_from, role, local_tz):
    with connection(write=True) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS owner_notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            store_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            report_date TEXT NOT NULL,
            title TEXT NOT NULL,
            body_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT,
            UNIQUE(user_id, store_id, kind, report_date)
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS idx_owner_notifications_history
                      ON owner_notifications(user_id,store_id,created_at DESC,id DESC)""")

    def check_owner(request, user):
        role(user, ["owner"])
        with connection() as db:
            store=store_from(request,user,db,allowed=["owner"])
        return store["id"]

    def snapshot(db, sid, day):
        start=datetime.combine(day,time(0,0),tzinfo=local_tz).astimezone(timezone.utc).isoformat()
        end=datetime.combine(day,time(20,0),tzinfo=local_tz).astimezone(timezone.utc).isoformat()
        def aggregate(table,columns):
            if table not in ("sales","sale_returns","expenses","debt_payments"):
                raise ValueError("Unsupported table")
            return db.execute(f"SELECT {columns} FROM {table} WHERE store_id=? AND created_at>=? AND created_at<?",
                              (sid,start,end)).fetchone()
        s=aggregate("sales","COUNT(*),COALESCE(SUM(subtotal),0),COALESCE(SUM(cash_paid),0),COALESCE(SUM(card_paid),0),COALESCE(SUM(debt),0)")
        r=aggregate("sale_returns","COALESCE(SUM(total),0),COALESCE(SUM(refund_cash),0),COALESCE(SUM(refund_card),0)")
        e=aggregate("expenses","COALESCE(SUM(amount),0)")
        p=aggregate("debt_payments","COALESCE(SUM(amount),0)")
        cost=db.execute("""SELECT COALESCE(SUM(si.qty*si.cost),0) FROM sale_items si
            JOIN sales s ON s.id=si.sale_id
            WHERE s.store_id=? AND s.created_at>=? AND s.created_at<?""",(sid,start,end)).fetchone()[0]
        refund_cost=db.execute("""SELECT COALESCE(SUM(ri.qty*ri.cost),0) FROM return_items ri
            JOIN sale_returns sr ON sr.id=ri.return_id
            WHERE sr.store_id=? AND sr.created_at>=? AND sr.created_at<?""",(sid,start,end)).fetchone()[0]
        low=db.execute("""SELECT COUNT(*) FROM products
            WHERE store_id=? AND active=1 AND stock<=min_stock""",(sid,)).fetchone()[0]
        debt=db.execute("""SELECT COALESCE(SUM(CASE WHEN balance>0 THEN balance ELSE 0 END),0)
            FROM (SELECT c.id,
            COALESCE((SELECT SUM(s.debt) FROM sales s WHERE s.customer_id=c.id AND s.store_id=c.store_id),0)
            -COALESCE((SELECT SUM(dp.amount) FROM debt_payments dp WHERE dp.customer_id=c.id AND dp.store_id=c.store_id),0)
            -COALESCE((SELECT SUM(sr.credit_reduction) FROM sale_returns sr WHERE sr.customer_id=c.id AND sr.store_id=c.store_id),0)
            AS balance FROM customers c WHERE c.store_id=?)""",(sid,)).fetchone()[0]
        rnd=lambda v:round(float(v),2)
        net=float(s[1])-float(r[0])
        return {"report_date":day.isoformat(),"timezone":"Asia/Tashkent","period":"00:00–20:00",
            "currency":"UZS","sale_count":int(s[0]),"sales":rnd(s[1]),"returns":rnd(r[0]),
            "net_sales":rnd(net),"cash_sales_after_returns":rnd(float(s[2])-float(r[1])),
            "card_sales_after_returns":rnd(float(s[3])-float(r[2])),
            "new_debt":rnd(s[4]),"debt_payments":rnd(p[0]),"expenses":rnd(e[0]),
            "estimated_profit":rnd(net-float(cost)+float(refund_cost)-float(e[0])),
            "profit_is_estimate":True,"outstanding_debt":rnd(debt),"low_stock":int(low),
            "snapshot_note":"Qarz va ombor qiymatlari hisobot yaratilgan vaqtdagi holat."}

    def generate_due():
        current=datetime.now(local_tz)
        if current.time()<time(20,0):
            return
        # Only one per store/owner/date; never alter or replace a prior snapshot.
        with connection(write=True) as db:
            owners=db.execute("""SELECT id,store_id FROM users
                WHERE role='owner' AND active=1 AND store_id IS NOT NULL""").fetchall()
            cache={}
            for uid,sid in owners:
                if sid not in cache:
                    cache[sid]=snapshot(db,sid,current.date())
                db.execute("""INSERT OR IGNORE INTO owner_notifications
                    (id,user_id,store_id,kind,report_date,title,body_json,created_at,read_at)
                    VALUES(?,?,?,'daily_report',?,?,?,?,NULL)""",
                    (str(uuid.uuid4()),uid,sid,current.date().isoformat(),
                     current.strftime("%d.%m.%Y")+" — 20:00 kunlik hisobot",
                     json.dumps(cache[sid],ensure_ascii=False),datetime.now(timezone.utc).isoformat()))

    @app.get("/api/owner-pro/notifications")
    def list_notifications(request:Request, offset:int=Query(0,ge=0), limit:int=Query(30,ge=1,le=100),
                           user=Depends(get_user)):
        sid=check_owner(request,user)
        generate_due()
        with connection() as db:
            total=db.execute("""SELECT COUNT(*) FROM owner_notifications
                 WHERE user_id=? AND store_id=?""",(user["id"],sid)).fetchone()[0]
            unread=db.execute("""SELECT COUNT(*) FROM owner_notifications
                 WHERE user_id=? AND store_id=? AND read_at IS NULL""",(user["id"],sid)).fetchone()[0]
            rows=db.execute("""SELECT id,kind,report_date,title,body_json,created_at,read_at
                FROM owner_notifications WHERE user_id=? AND store_id=?
                ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?""",
                (user["id"],sid,limit,offset)).fetchall()
        return {"total":total,"unread":unread,"offset":offset,"limit":limit,
            "has_more":offset+len(rows)<total,"notifications":[
            {"id":r[0],"kind":r[1],"report_date":r[2],"title":r[3],
             "details":json.loads(r[4]),"created_at":r[5],"read":r[6] is not None,
             "read_at":r[6]} for r in rows]}

    @app.post("/api/owner-pro/notifications/{notification_id}/read")
    def mark_read(notification_id:str,request:Request,user=Depends(get_user)):
        sid=check_owner(request,user)
        with connection(write=True) as db:
            result=db.execute("""UPDATE owner_notifications
                SET read_at=COALESCE(read_at,?)
                WHERE id=? AND user_id=? AND store_id=?""",
                (datetime.now(timezone.utc).isoformat(),notification_id,user["id"],sid))
            if result.rowcount!=1:raise HTTPException(404,"Xabarnoma topilmadi")
        return {"ok":True}

    async def runner():
        # Runs while an app worker stays online; duplicates protected by UNIQUE.
        while True:
            try:await asyncio.to_thread(generate_due)
            except (sqlite3.Error,OSError,ValueError):
                LOGGER.exception("Owner daily report generation failed")
            await asyncio.sleep(30)

    @app.on_event("startup")
    async def start_reports():
        app.state.owner_notification_task=asyncio.create_task(runner())

    @app.on_event("shutdown")
    async def stop_reports():
        task=getattr(app.state,"owner_notification_task",None)
        if task:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
