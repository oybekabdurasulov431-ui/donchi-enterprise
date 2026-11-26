"""DONCHI Enterprise 4.0 read-only SaaS analytics API. No schema changes."""
from fastapi import Depends

def install(app, get_user, connection, allrows, onerow, role, http, now):
    @app.get('/api/v4/platform/overview')
    def overview(user=Depends(get_user)):
        role(user,['superadmin'])
        with connection() as db:
            shops=allrows(db, """
              SELECT s.id,s.name,s.plan,s.status,s.created_at,
              (SELECT count(*) FROM users u WHERE u.store_id=s.id) AS users,
              (SELECT count(*) FROM branches b WHERE b.store_id=s.id) AS branches,
              (SELECT count(*) FROM sales x WHERE x.store_id=s.id) AS sale_count,
              (SELECT COALESCE(sum(subtotal),0) FROM sales x WHERE x.store_id=s.id)
               - (SELECT COALESCE(sum(total),0) FROM sale_returns r WHERE r.store_id=s.id) AS revenue,
              (SELECT COALESCE(sum(debt),0) FROM sales x WHERE x.store_id=s.id)
               - (SELECT COALESCE(sum(amount),0) FROM debt_payments d WHERE d.store_id=s.id)
               - (SELECT COALESCE(sum(credit_reduction),0) FROM sale_returns r WHERE r.store_id=s.id) AS debt
              FROM stores s ORDER BY created_at DESC
            """)
        for s in shops:
            s['debt']=round(float(s['debt'] or 0),2)
            s['revenue']=round(float(s['revenue'] or 0),2)
        return {'as_of':now(),'stores':shops,'totals':{
          'stores':len(shops),'active':sum(s['status']=='active' for s in shops),
          'revenue':round(sum(s['revenue'] for s in shops),2),
          'debt':round(sum(s['debt'] for s in shops),2),
          'users':sum(s['users'] for s in shops)}}

    @app.get('/api/v4/platform/stores/{store_id}')
    def store_360(store_id:str,user=Depends(get_user)):
        role(user,['superadmin'])
        with connection() as db:
            shop=onerow(db,'SELECT id,name,phone,address,plan,status,created_at FROM stores WHERE id=?',(store_id,))
            if not shop:http(404,"Do‘kon topilmadi")
            users=allrows(db,'SELECT id,username,full_name,role,active,created_at FROM users WHERE store_id=?',(store_id,))
            branches=allrows(db,'SELECT id,name FROM branches WHERE store_id=?',(store_id,))
            stock=onerow(db,'SELECT count(*) AS products,COALESCE(sum(stock*cost),0) AS value FROM products WHERE store_id=?',(store_id,))
            sales=onerow(db,'SELECT count(*) AS count,COALESCE(sum(subtotal),0) AS gross FROM sales WHERE store_id=?',(store_id,))
        return {'store':shop,'users':users,'branches':branches,'stock':stock,'sales':sales}

    @app.get('/api/v4/platform/billing')
    def billing(user=Depends(get_user)):
        role(user,['superadmin'])
        with connection() as db:
            shops=allrows(db,'SELECT id,name,plan,status FROM stores ORDER BY name')
        return {'stores':shops,'payments_connected':False,
                'renewals_automated':False,
                'notice':"Tariflar ko‘rsatiladi; to‘lov provayderi hali ulanmagan."}

    @app.get('/api/v4/platform/protection')
    def protection(user=Depends(get_user)):
        role(user,['superadmin'])
        import os
        return {'database_engine':os.getenv('DONCHI_DB_ENGINE','sqlite'),
                'backup_verified':False,'restore_test_verified':False,
                'notice':"Railway backup holati mustaqil tasdiqlanmaguncha tayyor deb ko‘rsatilmaydi."}

    @app.get('/api/v4/platform/alerts')
    def alerts(user=Depends(get_user)):
        role(user,['superadmin'])
        with connection() as db:
            low=allrows(db, """SELECT p.store_id,s.name AS store_name,count(*) AS product_count
              FROM products p JOIN stores s ON s.id=p.store_id
              WHERE p.active=1 AND p.stock<=p.min_stock
              GROUP BY p.store_id,s.name ORDER BY product_count DESC LIMIT 100""")
            inactive=allrows(db,"SELECT id,name,status FROM stores WHERE status<>'active' ORDER BY name LIMIT 100")
        return {'low_stock':low,'inactive_stores':inactive,'security_monitor_connected':False}

    @app.get('/api/v4/owner/dashboard')
    def owner_dashboard(user=Depends(get_user)):
        role(user,['owner','manager'])
        sid=user.get('store_id')
        if not sid:http(403,"Do‘kon biriktirilmagan")
        with connection() as db:
            shop=onerow(db,'SELECT id,name,status,plan FROM stores WHERE id=?',(sid,))
            if not shop:http(404,"Do‘kon topilmadi")
            sales=onerow(db,'SELECT count(*) AS count,COALESCE(sum(subtotal),0) AS total,COALESCE(sum(debt),0) AS debt FROM sales WHERE store_id=?',(sid,))
            payments=onerow(db,'SELECT COALESCE(sum(amount),0) AS total FROM debt_payments WHERE store_id=?',(sid,))
            returns=onerow(db,'SELECT COALESCE(sum(total),0) AS total,COALESCE(sum(credit_reduction),0) AS credit FROM sale_returns WHERE store_id=?',(sid,))
            products=onerow(db,'SELECT count(*) AS count,COALESCE(sum(stock*cost),0) AS stock_value FROM products WHERE store_id=?',(sid,))
        return {'store':shop,'sales_total':round(float(sales['total'])-float(returns['total']),2),
                'sale_count':sales['count'],
                'debt':round(float(sales['debt'])-float(payments['total'])-float(returns['credit']),2),
                'products':products,'as_of':now()}
