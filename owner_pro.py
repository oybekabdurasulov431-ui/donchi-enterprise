"""Read-only DONCHI Owner Pro 3.0 endpoints.

This module deliberately does not create tables, change balances, or alter stock.
Only a logged-in store owner may view its own store data.
"""
from datetime import datetime, timedelta, timezone
from fastapi import Depends, Request


def install(app, *, get_user, connection, store_from, onerow, allrows, role, require_feature, local_tz):
    def owner_data(request, user):
        role(user, ["owner"])
        with connection() as db:
            store = store_from(request, user, db, allowed=["owner"])
            require_feature(db, store, "analytics")
            return store["id"], store["name"]

    @app.get("/api/owner-pro/overview")
    def owner_pro_overview(request: Request, user=Depends(get_user)):
        store_id, store_name = owner_data(request, user)
        with connection() as db:
            sales = onerow(db, """SELECT COUNT(*) AS n, COALESCE(SUM(subtotal),0) AS amount,
                      COALESCE(SUM(cash_paid),0) AS cash, COALESCE(SUM(card_paid),0) AS card
                      FROM sales WHERE store_id=?""", (store_id,))
            returned = onerow(db, "SELECT COALESCE(SUM(total),0) AS amount FROM sale_returns WHERE store_id=?", (store_id,))
            costs = onerow(db, """SELECT COALESCE(SUM(si.qty*si.cost),0) AS cost
                      FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.store_id=?""", (store_id,))
            returned_cost = onerow(db, """SELECT COALESCE(SUM(ri.qty*ri.cost),0) AS cost
                      FROM return_items ri JOIN sale_returns r ON r.id=ri.return_id WHERE r.store_id=?""", (store_id,))
            expenses = onerow(db, "SELECT COALESCE(SUM(amount),0) AS amount FROM expenses WHERE store_id=?", (store_id,))
            stock = onerow(db, """SELECT COUNT(*) AS products,
                         COALESCE(SUM(CASE WHEN stock<=min_stock THEN 1 ELSE 0 END),0) AS low,
                         COALESCE(SUM(stock*cost),0) AS value
                         FROM products WHERE store_id=? AND active=1""", (store_id,))
            receivables = onerow(db, """SELECT COALESCE(SUM(CASE WHEN balance>0 THEN balance ELSE 0 END),0) AS total FROM (
              SELECT c.id,
                COALESCE((SELECT SUM(s.debt) FROM sales s WHERE s.store_id=c.store_id AND s.customer_id=c.id),0)
               -COALESCE((SELECT SUM(dp.amount) FROM debt_payments dp WHERE dp.store_id=c.store_id AND dp.customer_id=c.id),0)
               -COALESCE((SELECT SUM(r.credit_reduction) FROM sale_returns r WHERE r.store_id=c.store_id AND r.customer_id=c.id),0)
                AS balance FROM customers c WHERE c.store_id=?
            )""", (store_id,))
            # Bounded recent records; bucket in the configured local timezone.
            cutoff=(datetime.now(timezone.utc)-timedelta(days=9)).isoformat()
            recent_sales=allrows(db, "SELECT subtotal AS amount,created_at FROM sales WHERE store_id=? AND created_at>=?", (store_id,cutoff))
            recent_returns=allrows(db, "SELECT total AS amount,created_at FROM sale_returns WHERE store_id=? AND created_at>=?", (store_id,cutoff))
        today=datetime.now(local_tz).date()
        dates=[today-timedelta(days=i) for i in range(6,-1,-1)]
        day_values={str(day):0.0 for day in dates}
        for sign, events in ((1,recent_sales),(-1,recent_returns)):
            for event in events:
                try:
                    stamp=datetime.fromisoformat(event["created_at"])
                    if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=timezone.utc)
                    day=str(stamp.astimezone(local_tz).date())
                    if day in day_values: day_values[day]+=sign*float(event["amount"])
                except (ValueError, TypeError, OverflowError):
                    continue
        net=float(sales["amount"])-float(returned["amount"])
        # Estimate only: purchase costs and operating expenses may be incomplete.
        estimated_profit=net-(float(costs["cost"])-float(returned_cost["cost"]))-float(expenses["amount"])
        return {"store":{"id":store_id,"name":store_name},
                "currency":"UZS","profit_is_estimate":True,
                "kpis":{"today_revenue":round(day_values[str(today)],2),
                        "net_revenue_all_time":round(net,2),
                        "estimated_profit_all_time":round(estimated_profit,2),
                        "sale_count_all_time":sales["n"],
                        "gross_cash_collected_all_time":round(float(sales["cash"]),2),
                        "gross_card_collected_all_time":round(float(sales["card"]),2),
                        "receivables":round(float(receivables["total"]),2),
                        "low_stock_count":int(stock["low"]),
                        "stock_value_at_recorded_cost":round(float(stock["value"]),2)},
                "weekly_sales":[{"day":day,"revenue":round(amount,2)} for day,amount in day_values.items()]}

    @app.get("/api/owner-pro/inventory")
    def owner_pro_inventory(request: Request, user=Depends(get_user)):
        store_id,_=owner_data(request,user)
        with connection() as db:
            rows=allrows(db, """SELECT id,sku,name,category,unit,stock,min_stock,cost,price
                FROM products WHERE store_id=? AND active=1 AND stock<=min_stock
                ORDER BY (min_stock-stock) DESC,name LIMIT 200""",(store_id,))
        return {"low_stock":rows,"count":len(rows),"truncated":len(rows)==200}

    @app.get("/api/owner-pro/receivables")
    def owner_pro_receivables(request: Request, user=Depends(get_user)):
        store_id,_=owner_data(request,user)
        with connection() as db:
            rows=allrows(db, """SELECT c.id,c.name,c.phone,
                COALESCE((SELECT SUM(s.debt) FROM sales s WHERE s.store_id=c.store_id AND s.customer_id=c.id),0)
               -COALESCE((SELECT SUM(dp.amount) FROM debt_payments dp WHERE dp.store_id=c.store_id AND dp.customer_id=c.id),0)
               -COALESCE((SELECT SUM(r.credit_reduction) FROM sale_returns r WHERE r.store_id=c.store_id AND r.customer_id=c.id),0)
                AS balance FROM customers c WHERE c.store_id=? ORDER BY balance DESC,c.name LIMIT 200""",(store_id,))
        positive=[{"id":r["id"],"name":r["name"],"phone":r["phone"],"balance":round(r["balance"],2)} for r in rows if r["balance"]>0]
        return {"customers":positive,"count":len(positive),"truncated":len(rows)==200}

    @app.get("/api/owner-pro/cash")
    def owner_pro_cash(request: Request, user=Depends(get_user)):
        store_id,_=owner_data(request,user)
        with connection() as db:
            shifts=allrows(db, """SELECT sh.id,sh.status,sh.opening_cash,sh.closing_cash,sh.expected_cash,
                sh.variance,sh.opened_at,sh.closed_at,u.full_name AS cashier
                FROM cash_shifts sh JOIN users u ON u.id=sh.cashier_id
                WHERE sh.store_id=? ORDER BY sh.opened_at DESC LIMIT 100""",(store_id,))
        return {"shifts":shifts,"count":len(shifts),"truncated":len(shifts)==100}

    @app.get("/api/owner-pro/audit")
    def owner_pro_audit(request: Request, user=Depends(get_user)):
        store_id,_=owner_data(request,user)
        with connection() as db:
            entries=allrows(db, """SELECT username,action,created_at
                FROM audit WHERE store_id=? ORDER BY created_at DESC LIMIT 100""",(store_id,))
        return {"events":entries,"count":len(entries),"truncated":len(entries)==100}
