from flask import Blueprint, render_template
from flask_login import login_required
import datetime
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from utils import requires_permission
from constants import DASHBOARD_HTML

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard_page():
    conn = get_db_connection()
    if not conn: return "Lỗi kết nối DB"
    
    cur = conn.cursor(cursor_factory=RealDictCursor) # Ensure we get rectdicts like in original
    today = datetime.date.today()
    
    cur.execute("SELECT SUM(total_amount) as total FROM Orders WHERE date(order_date) = %s AND status != 'cancelled'", (today,))
    res_rev = cur.fetchone()
    revenue_today = res_rev['total'] if res_rev and res_rev['total'] else 0

    cur.execute("SELECT COUNT(*) as count FROM Orders WHERE date(order_date) = %s", (today,))
    res_ord = cur.fetchone()
    orders_today = res_ord['count'] if res_ord else 0

    cur.execute("SELECT SUM(total_amount - amount_paid) as total FROM Orders WHERE payment_status != 'paid' AND status != 'cancelled'")
    res_due = cur.fetchone()
    total_due_customer = res_due['total'] if res_due and res_due['total'] else 0

    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(total_amount) FROM import_slips WHERE EXTRACT(MONTH FROM import_date) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM import_date) = EXTRACT(YEAR FROM CURRENT_DATE)), 0) AS total_import_cost,
            COALESCE((SELECT SUM(cost) FROM maintenance_logs WHERE EXTRACT(MONTH FROM maintenance_date) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM maintenance_date) = EXTRACT(YEAR FROM CURRENT_DATE)), 0) AS total_maintenance_cost,
            COALESCE((SELECT SUM(outsource_base_cost) FROM orders WHERE is_outsourced = TRUE AND status != 'cancelled' AND EXTRACT(MONTH FROM order_date) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM order_date) = EXTRACT(YEAR FROM CURRENT_DATE)), 0) AS total_outsource_cost,
            COALESCE((SELECT SUM(amount) FROM operating_expenses WHERE EXTRACT(MONTH FROM expense_date) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM expense_date) = EXTRACT(YEAR FROM CURRENT_DATE)), 0) AS total_operating_cost
    """)
    costs = cur.fetchone()
    
    import_cost = float(costs['total_import_cost'] or 0)
    maintenance_cost = float(costs['total_maintenance_cost'] or 0)
    outsource_cost = float(costs['total_outsource_cost'] or 0)
    operating_cost = float(costs['total_operating_cost'] or 0)
    
    total_expense = import_cost + maintenance_cost + outsource_cost + operating_cost

    cur.execute("""
        SELECT 
            TO_CHAR(order_date, 'MM/YYYY') as month_str,
            SUM(total_amount) as total
        FROM Orders
        WHERE status != 'cancelled' 
          AND order_date >= date_trunc('month', CURRENT_DATE) - INTERVAL '5 months'
        GROUP BY TO_CHAR(order_date, 'MM/YYYY'), date_trunc('month', order_date)
        ORDER BY date_trunc('month', order_date) ASC
    """)
    monthly_data = cur.fetchall()
    
    monthly_labels = [row['month_str'] for row in monthly_data]
    monthly_revenue = [float(row['total'] or 0) for row in monthly_data]

    # Landing page visit stats
    cur.execute("SELECT COUNT(*) as total_visits FROM page_visits")
    res_visits = cur.fetchone()
    total_visits = res_visits['total_visits'] if res_visits else 0
    
    cur.execute("""
        SELECT referrer, COUNT(*) as count 
        FROM page_visits 
        GROUP BY referrer 
        ORDER BY count DESC 
        LIMIT 5
    """)
    top_referrers = cur.fetchall()

    conn.close()

    return render_template(DASHBOARD_HTML, 
                           import_cost=import_cost, 
                           maintenance_cost=maintenance_cost, 
                           outsource_cost=outsource_cost, 
                           operating_cost=operating_cost,
                           total_expense=total_expense,
                           revenue_today=revenue_today,
                           orders_today=orders_today,
                           total_due_customer=total_due_customer,
                           revenue_cancelled_today=0, 
                           due_imports=0,
                           due_maintenance=0,
                           low_stock_count=0,
                           top_services=[],
                           monthly_revenue=monthly_revenue,
                           monthly_labels=monthly_labels,
                           total_visits=total_visits,
                           top_referrers=top_referrers)
