from flask import Blueprint, render_template, request, redirect, url_for, flash
import datetime
from flask_login import current_user
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from utils import log_system_action, requires_permission
from constants import (LS_BG_HTML, TAO_BG_HTML, CT_BG_HTML, EDIT_QUOTE_HTML, MD_SALE)

quotes_bp = Blueprint('quotes', __name__)

@quotes_bp.route('/quotes_history')
@requires_permission('sale') 
def quotes_history_page():
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
        
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    filter_mode = request.args.get('filter')
    
    today = datetime.date.today()
    if not start_date_str and not end_date_str and filter_mode != 'all':
        start_date_str = (today - datetime.timedelta(days=6)).isoformat()
        end_date_str = today.isoformat()
    
    sql = """
        SELECT Q.quote_id, Q.created_date, Q.total_amount, Q.status, C.customer_name
        FROM Quotes AS Q
        JOIN Customers AS C ON Q.customer_id = C.customer_id
        WHERE 1=1 
    """
    params = []

    if start_date_str:
        sql += " AND DATE(Q.created_date) >= %s"
        params.append(start_date_str)
    if end_date_str:
        sql += " AND DATE(Q.created_date) <= %s"
        params.append(end_date_str)
        
    sql += " ORDER BY Q.created_date DESC"
    
    cur.execute(sql, tuple(params))
    quotes_list = cur.fetchall()
    
    total_quotes_value = sum(quote['total_amount'] for quote in quotes_list)
    
    cur.close()
    conn.close()
    
    return render_template(LS_BG_HTML, 
                           quotes_list=quotes_list,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           total_quotes_value=total_quotes_value)

@quotes_bp.route('/create_quote')
@requires_permission('sale')
def create_quote_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    today = datetime.date.today()
    
    cur.execute("SELECT customer_id, customer_name, phone, email, address, company_name, tax_id FROM Customers WHERE is_active = TRUE ORDER BY customer_name")
    customers_list = cur.fetchall()
    
    cur.execute("SELECT * FROM services WHERE is_active = true ORDER BY service_name")
    services_list = cur.fetchall()
    
    sql_coupons = """
        SELECT * FROM Coupons 
        WHERE status = 'active' AND start_date <= %s AND end_date >= %s
        ORDER BY discount_value DESC
    """
    cur.execute(sql_coupons, (today, today))
    active_coupons = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template(TAO_BG_HTML, 
                           customers_list=customers_list, 
                           services_list=services_list,
                           active_coupons=active_coupons)

@quotes_bp.route('/submit_quote', methods=['POST'])
@requires_permission('sale')
def submit_quote():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor) 
    new_quote_id = -1
    
    try:
        customer_id = request.form['customer_id']
        notes = request.form['notes']
        tax_rate = float(request.form['tax_rate'])
        
        coupon_code = request.form.get('coupon_code')
        discount_amount = float(request.form.get('discount_amount') or 0)
        
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        
        subtotal = 0
        for i in range(len(service_ids)):
            subtotal += int(quantities[i]) * float(unit_prices[i])
            
        tax_amount = subtotal * (tax_rate / 100)
        total_amount = (subtotal + tax_amount) - discount_amount
        if total_amount < 0: total_amount = 0
        
        sql_insert_quote = """
            INSERT INTO Quotes (customer_id, status, notes, subtotal, tax_rate, tax_amount, 
            coupon_code, discount_amount, total_amount)
            VALUES (%s, 'pending', %s, %s, %s, %s, %s, %s, %s)
            RETURNING quote_id
        """
        val_insert = (customer_id, notes, subtotal, tax_rate, tax_amount, coupon_code, discount_amount, total_amount)
        cur.execute(sql_insert_quote, val_insert)
        
        new_quote_id = cur.fetchone()['quote_id']

        for i in range(len(service_ids)):
            sql_item = """
                INSERT INTO Quote_Items (quote_id, service_id, description, quantity, unit_price, line_total)
                VALUES (%s, %s, '', %s, %s, %s)
            """
            line_total = int(quantities[i]) * float(unit_prices[i])
            cur.execute(sql_item, (new_quote_id, service_ids[i], quantities[i], unit_prices[i], line_total))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_QUOTE',
            target_module=MD_SALE,
            description=f"Tạo Báo Giá ID #{new_quote_id} cho khách hàng ID #{customer_id}. Tổng tiền: {total_amount:,.0f}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
        
    except Exception as e:
        conn.rollback() 
        print(f"LỖI TẠO BÁO GIÁ: {e}")
        return f"Đã xảy ra lỗi: {e}", 500
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('quotes.quote_detail_page', quote_id=new_quote_id))

@quotes_bp.route('/quote/<int:quote_id>')
@requires_permission('sale','inventory')
def quote_detail_page(quote_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql_quote = """
        SELECT Q.*, C.customer_name, C.phone
        FROM Quotes AS Q
        JOIN Customers AS C ON Q.customer_id = C.customer_id
        WHERE Q.quote_id = %s
    """
    cur.execute(sql_quote, (quote_id,))
    quote_info = cur.fetchone()
    
    sql_items = """
        SELECT QI.quantity, QI.unit_price, QI.line_total, S.service_name, S.unit
        FROM Quote_Items AS QI
        JOIN Services AS S ON QI.service_id = S.service_id
        WHERE QI.quote_id = %s
    """
    cur.execute(sql_items, (quote_id,))
    quote_items = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not quote_info: return "Không tìm thấy báo giá!", 404
    return render_template(CT_BG_HTML, quote_info=quote_info, quote_items=quote_items)

@quotes_bp.route('/quote/<int:quote_id>/print')
@requires_permission('sale','inventory')
def print_quote_page(quote_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql_quote = """
        SELECT Q.*, C.customer_name, C.phone, C.address, C.company_name, C.tax_id, C.email
        FROM Quotes AS Q
        JOIN Customers AS C ON Q.customer_id = C.customer_id
        WHERE Q.quote_id = %s
    """
    cur.execute(sql_quote, (quote_id,))
    quote_info = cur.fetchone()
    
    sql_items = """
        SELECT QI.quantity, QI.unit_price, QI.line_total, S.service_name, S.unit
        FROM Quote_Items AS QI
        JOIN Services AS S ON QI.service_id = S.service_id
        WHERE QI.quote_id = %s
    """
    cur.execute(sql_items, (quote_id,))
    quote_items = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not quote_info: return "Not Found", 404

    from utils import number_to_vietnamese_text
    amount_in_words = number_to_vietnamese_text(quote_info['total_amount'])
    
    import datetime
    today = datetime.datetime.now()
    date_str = f"Vĩnh Long, ngày {today.day:02d} tháng {today.month:02d} năm {today.year}"
    
    return render_template('HHBG/print_quote.html', quote_info=quote_info, quote_items=quote_items, amount_in_words=amount_in_words, date_str=date_str)

@quotes_bp.route('/update_quote_status/<int:quote_id>', methods=['POST'])
@requires_permission('sale')
def update_quote_status(quote_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        new_status = request.form['quote_status']
        cur.execute("UPDATE Quotes SET status = %s WHERE quote_id = %s", (new_status, quote_id))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='UPD_QUOTE',
            target_module=MD_SALE,
            description=f"Cập nhật trạng thái Báo Giá ID #{quote_id} qua #{new_status}.",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi: {e}")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('quotes.quote_detail_page', quote_id=quote_id))

@quotes_bp.route('/convert_quote/<int:quote_id>', methods=['POST'])
@requires_permission('sale')
def convert_quote_to_order(quote_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    new_order_id = -1
    
    try:
        cur.execute("SELECT order_id FROM Orders WHERE quote_id = %s", (quote_id,))
        existing_order = cur.fetchone()
        if existing_order:
            return redirect(url_for('orders.order_detail_page', order_id=existing_order['order_id']))

        cur.execute("SELECT * FROM Quotes WHERE quote_id = %s", (quote_id,))
        quote_info = cur.fetchone()
        
        cur.execute("SELECT * FROM Quote_Items WHERE quote_id = %s", (quote_id,))
        quote_items_list = cur.fetchall()
        
        if not quote_info: return "Lỗi: Báo giá không hợp lệ.", 400

        sql_insert = """
            INSERT INTO Orders (customer_id, total_amount, status, quote_id)
            VALUES (%s, %s, 'processing', %s)
            RETURNING order_id
        """
        cur.execute(sql_insert, (quote_info['customer_id'], quote_info['total_amount'], quote_id))
        new_order_id = cur.fetchone()['order_id']

        for item in quote_items_list:
            sql_item = """
                INSERT INTO Order_Items (order_id, service_id, quantity, unit_price, line_total)
                VALUES (%s, %s, %s, %s, %s)
            """
            cur.execute(sql_item, (new_order_id, item['service_id'], item['quantity'], item['unit_price'], item['line_total']))
            
            cur.execute("SELECT material_id, quantity_consumed FROM Service_Materials WHERE service_id = %s", (item['service_id'],))
            boms = cur.fetchall()

            for b in boms:
                deduct = float(item['quantity']) * float(b['quantity_consumed'])
                cur.execute("UPDATE Materials SET stock_quantity = stock_quantity - %s WHERE material_id = %s", 
                           (deduct, b['material_id']))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='CONVERT_QUOTE',
            target_module=MD_SALE,
            description=f"Chuyển đổi Báo Giá ID #{quote_id} thành Đơn hàng ID #{new_order_id}.",
            ip_address=request.remote_addr
        )
        
        conn.commit()
        
    except Exception as e:
        conn.rollback() 
        print(f"Lỗi Convert Quote: {e}")
        return f"Lỗi: {e}", 500
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('orders.order_detail_page', order_id=new_order_id))


@quotes_bp.route('/edit_quote/<int:quote_id>')
@requires_permission('sale')
def edit_quote_page(quote_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM Quotes WHERE quote_id = %s", (quote_id,))
    quote_info = cur.fetchone()
    
    cur.execute("""
                    SELECT qi.*, s.service_name, s.unit, s.unit_level2, s.unit_level3 
                    FROM quote_items qi
                    JOIN services s ON qi.service_id = s.service_id
                    WHERE qi.quote_id = %s
                """, (quote_id,))
    quote_items_list = cur.fetchall()
    
    cur.execute("SELECT customer_id, customer_name FROM Customers ORDER BY customer_name")
    customers_list = cur.fetchall()
    
    cur.execute("SELECT * FROM services WHERE is_active = true ORDER BY service_name")
    services_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not quote_info: return "Not Found", 404
    if quote_info['status'] != 'pending': return "Không thể sửa báo giá đã xử lý.", 403
        
    return render_template(EDIT_QUOTE_HTML, 
                           quote_info=quote_info,
                           quote_items_list=quote_items_list,
                           customers_list=customers_list,
                           services_list=services_list)

@quotes_bp.route('/update_quote/<int:quote_id>', methods=['POST'])
@requires_permission('sale')
def update_quote(quote_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        customer_id = request.form['customer_id']
        tax_rate = float(request.form['tax_rate'])
        notes = request.form['notes']
        
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        cur.execute("DELETE FROM Quote_Items WHERE quote_id = %s", (quote_id,))

        subtotal = 0
        for i in range(len(service_ids)):
            qty = int(quantities[i])
            price = float(unit_prices[i])
            line = qty * price
            subtotal += line
            
            cur.execute("""
                INSERT INTO Quote_Items (quote_id, service_id, description, quantity, unit_price, line_total)
                VALUES (%s, %s, '', %s, %s, %s)
            """, (quote_id, service_ids[i], qty, price, line))
            
        tax_amount = subtotal * (tax_rate / 100)
        total_amount = subtotal + tax_amount

        sql_update = """
            UPDATE Quotes 
            SET customer_id = %s, tax_rate = %s, notes = %s, 
                subtotal = %s, tax_amount = %s, total_amount = %s, 
                update_count = update_count + 1
            WHERE quote_id = %s
        """
        cur.execute(sql_update, (customer_id, tax_rate, notes, subtotal, tax_amount, total_amount, quote_id))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='UPD_QUOTE',
            target_module=MD_SALE,
            description=f"Cập nhật thông tin Báo Giá ID #{quote_id}. Tổng tiền: {total_amount:,.0f}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback() 
        print(f"Lỗi Update Quote: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('quotes.quote_detail_page', quote_id=quote_id))
