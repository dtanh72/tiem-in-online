from flask import Blueprint, render_template, request, redirect, url_for, flash
import datetime
import json
from flask_login import current_user
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from utils import log_system_action, requires_permission
from constants import (TAO_DH_HTML, LS_DH_HTML, CT_DH_HTML, MD_SALE, MD_ACC)

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/create_order')
@requires_permission('sale')
def create_order_page():
    conn = get_db_connection()
    if conn is None: return "Lỗi DB", 500
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    today = datetime.date.today()
    
    cur.execute("SELECT * FROM Customers WHERE is_active = TRUE ORDER BY customer_name")
    customers = cur.fetchall()
    
    cur.execute("SELECT * FROM Services WHERE is_active = TRUE ORDER BY service_name")
    services = cur.fetchall()
    
    cur.execute("SELECT * FROM Equipment WHERE status = 'active' AND is_active = TRUE ORDER BY equipment_name")
    equipment = cur.fetchall()
    
    sql_coupons = """
        SELECT * FROM Coupons 
        WHERE status = 'active' AND start_date <= %s AND end_date >= %s
        ORDER BY discount_value DESC
    """
    cur.execute(sql_coupons, (today, today))
    coupons = cur.fetchall()
    
    cur.execute("SELECT partner_id, partner_name FROM Outsource_Partners WHERE is_active = TRUE ORDER BY partner_name")
    partners_list = cur.fetchall()
    
    # Query Combos and their items
    cur.execute("SELECT * FROM Combos WHERE is_active = TRUE")
    combos_raw = cur.fetchall()
    combos_list = []
    for c in combos_raw:
        cur.execute("""
            SELECT ci.service_id, ci.quantity, s.service_name, s.base_price,
                   s.unit, s.unit_level2, s.unit_level3
            FROM Combo_Items ci 
            JOIN Services s ON ci.service_id = s.service_id 
            WHERE ci.combo_id = %s
        """, (c['combo_id'],))
        c['items'] = cur.fetchall()
        
        # Convert Decimals to float for JSON serialization
        c['combo_price'] = float(c['combo_price'])
        for item in c['items']:
            item['base_price'] = float(item['base_price'])
        
        combos_list.append(c)
        
    combos_json = json.dumps(combos_list)
    
    cur.close()
    conn.close()
    
    return render_template(TAO_DH_HTML, 
                           customers_list=customers, 
                           services_list=services,
                           equipment_list=equipment, 
                           active_coupons=coupons,
                           partners=partners_list,
                           combos_json=combos_json)

@orders_bp.route('/submit_order', methods=['POST'])
@requires_permission('sale')
def submit_order():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor) 
    
    try:
        is_outsourced = True if request.form.get('is_outsourced') == 'on' else False
        outsource_partner_id = request.form.get('outsource_partner_id') if is_outsourced else None
        outsource_base_cost = float(request.form.get('outsource_base_cost') or 0)
        
        customer_id = request.form['customer_id']
        tax_rate = float(request.form['tax_rate'])
        coupon_code = request.form.get('coupon_code')
        discount_amount = float(request.form.get('discount_amount') or 0)
        
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        equipment_ids = request.form.getlist('equipment_id[]')
        combo_ids = request.form.getlist('combo_id[]')
        
        qty_l1_list = request.form.getlist('qty_l1[]')
        qty_l2_list = request.form.getlist('qty_l2[]')
        qty_l3_list = request.form.getlist('qty_l3[]')
        
        subtotal = 0
        for i in range(len(service_ids)):
            subtotal += int(quantities[i]) * float(unit_prices[i])
        
        tax_amount = subtotal * (tax_rate / 100)
        total_amount = (subtotal + tax_amount) - discount_amount
        if total_amount < 0: total_amount = 0
        
        amount_paid = float(request.form.get('amount_paid', 0))
        payment_method = request.form.get('payment_method', 'cash')
        
        if amount_paid == 0:
            payment_status = 'unpaid'
        elif amount_paid >= total_amount:
            payment_status = 'paid'
            amount_paid = total_amount 
        else:
            payment_status = 'partially_paid'

        sql_order = """
            INSERT INTO Orders (customer_id, status, subtotal, tax_rate, tax_amount, coupon_code, 
            discount_amount, total_amount, amount_paid, payment_status, payment_method, is_outsourced, outsource_partner_id, outsource_base_cost, quote_id)
            VALUES (%s, 'processing', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
            RETURNING order_id
        """
        cur.execute(sql_order, (customer_id, subtotal, tax_rate, tax_amount, coupon_code, discount_amount, total_amount, amount_paid, payment_status, payment_method, is_outsourced, outsource_partner_id, outsource_base_cost))
        
        new_order_id = cur.fetchone()['order_id']
        
        outsource_data = request.form.get('outsource_data')
        if is_outsourced and outsource_data:
            items = json.loads(outsource_data)
            for item in items:
                cur.execute("""
                    INSERT INTO Order_Outsource_Items 
                    (order_id, category_name, item_name, quantity, unit_price, total_price, is_first_page_fee) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (new_order_id, item['category_name'], item['item_name'], 
                      item['quantity'], item['unit_price'], item['total_price'], item['is_first_page_fee']))
        
        if coupon_code:
            cur.execute("UPDATE Coupons SET used_count = used_count + 1 WHERE code = %s", (coupon_code,))

        for i in range(len(service_ids)):
            srv_id = service_ids[i]
            qty = int(quantities[i])
            price = float(unit_prices[i])
            equip_id = equipment_ids[i] if equipment_ids[i] else None
            line_total = qty * price
            
            total_cost_item = 0.0
            
            q1 = float(qty_l1_list[i]) if i < len(qty_l1_list) and qty_l1_list[i] else 0
            q2 = float(qty_l2_list[i]) if i < len(qty_l2_list) and qty_l2_list[i] else 0
            q3 = float(qty_l3_list[i]) if i < len(qty_l3_list) and qty_l3_list[i] else 0
            
            sql_bom = """
                SELECT SM.material_id, SM.quantity_consumed, SM.apply_to_unit_level, M.avg_cost_per_base_unit 
                FROM Service_Materials SM
                JOIN Materials M ON SM.material_id = M.material_id
                WHERE SM.service_id = %s
            """
            cur.execute(sql_bom, (srv_id,))
            bom_list = cur.fetchall()
            
            if bom_list:
                for mat in bom_list:
                    consume = float(mat['quantity_consumed'])
                    avg_cost = float(mat['avg_cost_per_base_unit'])
                    level = mat['apply_to_unit_level']
                    
                    deduct_qty = 0
                    if level == 1: deduct_qty = (q1 * q2 * q3) * consume
                    elif level == 2: deduct_qty = (q2 * q3) * consume
                    elif level == 3: deduct_qty = q3 * consume
                    
                    total_cost_item += (deduct_qty * avg_cost)
            
            profit = line_total - total_cost_item
            
            c_id = combo_ids[i] if i < len(combo_ids) and combo_ids[i] != '' else None
            
            sql_item = """
                INSERT INTO Order_Items (order_id, service_id, combo_id, equipment_id, quantity, unit_price, line_total, cost_of_goods, profit)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql_item, (new_order_id, srv_id, c_id, equip_id, qty, price, line_total, total_cost_item, profit))
            
            if equip_id and qty > 0:
                cur.execute("UPDATE Equipment SET print_count = print_count + %s WHERE equipment_id = %s", (qty, equip_id))

        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_ORDER',
            target_module=MD_SALE,
            description=f"Thêm Đơn Hàng ID #{new_order_id} chạy trên thiết bị ID #{equip_id}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi tạo đơn: {e}")
        return f"Lỗi: {e}", 500
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('orders.orders_history_page'))

@orders_bp.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT status, delivery_status, amount_paid, is_outsourced, outsource_status 
            FROM orders WHERE order_id = %s
        """, (order_id,))
        order = cursor.fetchone()

        if not order:
            flash('Không tìm thấy đơn hàng!', 'danger')
            return redirect(url_for('orders.orders_history_page'))

        if order['delivery_status'] == 'delivered':
            flash('Lỗi: Không thể hủy đơn hàng ĐÃ GIAO!', 'danger')
            return redirect(url_for('orders.orders_history_page'))
            
        if order.get('is_outsourced') and order.get('outsource_status') == 'Đã nhận hàng':
            flash('Lỗi: Đơn gia công đã NHẬN HÀNG TỪ XƯỞNG! KHÔNG THỂ HỦY!', 'danger')
            return redirect(url_for('orders.orders_history_page'))

        deposited_amount = float(order['amount_paid'] or 0)

        if order.get('is_outsourced') and order.get('outsource_status') not in ['Đang chờ xưởng', 'Chưa gửi xưởng']:
            cursor.execute("""
                UPDATE orders 
                SET status = 'abandoned',
                    notes = COALESCE(notes, '') || '\n[HỆ THỐNG]: Khách hủy đơn khi xưởng đang gia công -> MẤT CỌC.'
                WHERE order_id = %s
            """, (order_id,))
            
            log_system_action(
                user_id=current_user.id,
                username=current_user.username,
                full_name=current_user.full_name,
                action_type='CANCEL_ORDER',
                target_module=MD_SALE,
                description=f"Hủy đơn hàng ID #{order_id} (Đơn gia công mất cọc)",
                ip_address=request.remote_addr
            )

            conn.commit()
            
            if deposited_amount > 0:
                flash(f'Cảnh báo: Đã hủy đơn! Khách hàng MẤT CỌC ({deposited_amount:,.0f} vnđ) do xưởng đã tiến hành gia công.', 'warning')
            else:
                flash('Đã hủy đơn! (Khách chưa cọc nên xưởng chịu rủi ro chi phí này).', 'danger')

        else:
            cursor.execute("""
                UPDATE orders 
                SET status = 'cancelled',
                    amount_paid = 0,               
                    payment_status = 'unpaid'      
                WHERE order_id = %s
            """, (order_id,))
            
            log_system_action(
                user_id=current_user.id,
                username=current_user.username,
                full_name=current_user.full_name,
                action_type='CANCEL_ORDER',
                target_module=MD_SALE,
                description=f"Hủy đơn hàng ID #{order_id}",
                ip_address=request.remote_addr
            )

            conn.commit()
            
            if deposited_amount > 0:
                flash(f'Đã hủy đơn! CẦN HOÀN TRẢ {deposited_amount:,.0f} vnđ tiền cọc cho khách. Doanh thu đã được điều chỉnh giảm.', 'info')
            else:
                flash('Đã hủy đơn hàng thành công!', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi hủy đơn hàng: {e}")
        flash(f'Lỗi hệ thống khi hủy đơn: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('orders.orders_history_page'))

@orders_bp.route('/orders_history')
@requires_permission('sale', 'accounting')
def orders_history_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    mode = request.args.get('filter')
    
    today = datetime.date.today()
    if not start and not end and mode != 'all':
        start = (today - datetime.timedelta(days=6)).isoformat()
        end = today.isoformat()
        
    sql = """
        SELECT O.order_id, O.order_date, O.total_amount, O.status, O.amount_paid, 
               (O.total_amount - O.amount_paid) AS amount_due, 
               O.payment_status, O.delivery_status, C.customer_name
        FROM Orders O
        JOIN Customers C ON O.customer_id = C.customer_id
        WHERE 1=1
    """
    params = []
    if start:
        sql += " AND DATE(O.order_date) >= %s"
        params.append(start)
    if end:
        sql += " AND DATE(O.order_date) <= %s"
        params.append(end)
        
    sql += " ORDER BY O.order_date DESC"
    
    cur.execute(sql, tuple(params))
    orders = cur.fetchall()
    
    rev = sum(o['total_amount'] for o in orders if o['status'] != 'cancelled')
    due = sum(o['amount_due'] for o in orders if o['status'] != 'cancelled')
    canc = sum(o['total_amount'] for o in orders if o['status'] == 'cancelled')
    
    cur.close()
    conn.close()
    
    return render_template(LS_DH_HTML, orders_list=orders, start_date=start, end_date=end,
                           total_revenue=rev, total_due=due, total_cancelled=canc)

@orders_bp.route('/order/<int:order_id>')
@requires_permission('sale', 'inventory')
def order_detail_page(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT o.*, c.customer_name, c.phone, 
                   p.partner_name, p.phone as partner_phone
            FROM Orders o
            LEFT JOIN Customers c ON o.customer_id = c.customer_id
            LEFT JOIN Outsource_Partners p ON o.outsource_partner_id = p.partner_id
            WHERE o.order_id = %s
        """, (order_id,))
        order = cursor.fetchone()
        
        cursor.execute("""
            SELECT oi.*, s.service_name, s.unit, cb.combo_name
            FROM Order_Items oi
            LEFT JOIN Services s ON oi.service_id = s.service_id
            LEFT JOIN Combos cb ON oi.combo_id = cb.combo_id
            WHERE oi.order_id = %s
        """, (order_id,))
        order_items = cursor.fetchall()
        
        outsource_items = []
        if order and order['is_outsourced']:
            cursor.execute("SELECT * FROM Order_Outsource_Items WHERE order_id = %s", (order_id,))
            outsource_items = cursor.fetchall()
                
        missing_materials = []
        if not order.get('is_outsourced'): 
            cursor.execute("""
                SELECT 
                    m.material_id, 
                    m.material_name, 
                    m.base_unit,
                    m.stock_quantity AS current_stock,
                    SUM(sm.quantity_consumed * oi.quantity) AS required_qty,
                    (SUM(sm.quantity_consumed * oi.quantity) - m.stock_quantity) AS missing_qty
                FROM order_items oi
                JOIN service_materials sm ON oi.service_id = sm.service_id
                JOIN materials m ON sm.material_id = m.material_id
                WHERE oi.order_id = %s
                GROUP BY m.material_id, m.material_name, m.base_unit, m.stock_quantity
                HAVING SUM(sm.quantity_consumed * oi.quantity) > m.stock_quantity
            """, (order_id,))
            missing_materials = cursor.fetchall()
        
        return render_template(CT_DH_HTML, order=order, 
                                order_items=order_items,
                                outsource_items=outsource_items,
                                missing_materials=missing_materials) 
    except Exception as e:
        print(f"🔴 Lỗi khi xem chi tiết đơn hàng: {e}")
        flash(f"Đã xảy ra lỗi khi tải chi tiết đơn hàng: {e}", "danger")
        return redirect(url_for('orders.orders_history_page'))
    finally:
        cursor.close()
        conn.close()

@orders_bp.route('/log_payment/<int:order_id>', methods=['POST'])
@requires_permission('sale', 'accounting') 
def log_payment(order_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT status, total_amount, amount_paid FROM Orders WHERE order_id = %s", (order_id,))
        order = cur.fetchone()
        
        if not order or order['status'] == 'cancelled':
            return "LỖI: Không thể thanh toán cho đơn hàng đã hủy!", 403
    
        amount_received = float(request.form['amount_received'])
        payment_method = request.form['payment_method']
        
        sql_update = """
            UPDATE Orders 
            SET amount_paid = amount_paid + %s, 
                payment_method = %s 
            WHERE order_id = %s
        """
        cur.execute(sql_update, (amount_received, payment_method, order_id))
        
        new_paid = float(order['amount_paid']) + amount_received
        total = float(order['total_amount'])
        
        new_payment_status = 'unpaid'
        if new_paid >= total:
            new_payment_status = 'paid'
        elif new_paid > 0:
            new_payment_status = 'partially_paid'
        
        cur.execute("UPDATE Orders SET payment_status = %s WHERE order_id = %s", (new_payment_status, order_id))
        
        if new_payment_status == 'paid':
            cur.execute("SELECT delivery_status FROM orders WHERE order_id = %s", (order_id,))
            check_order = cur.fetchone()
            
            if check_order and check_order['delivery_status'] == 'delivered':
                cur.execute("""
                    UPDATE orders 
                    SET status = 'completed' 
                    WHERE order_id = %s
                """, (order_id,))
                flash('🎉 Đã thu đủ tiền! Đơn hàng tự động HOÀN THÀNH.', 'success')
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='PAY_ORDER',
            target_module=MD_ACC,
            description=f"Thanh toán đơn hàng #{order_id}. Số tiền: {amount_received:,.0f} VNĐ. Tổng thu: {new_paid:,.0f} / {total:,.0f} VNĐ",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback() 
        print(f"LỖI KHI GHI NHẬN THANH TOÁN: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('orders.order_detail_page', order_id=order_id))

@orders_bp.route('/update_delivery/<int:order_id>', methods=['POST'])
@requires_permission('inventory', 'sale') 
def update_delivery_status(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        new_status = request.form.get('delivery_status')
        
        if new_status:
            cursor.execute("""
                SELECT delivery_status, payment_status, is_outsourced 
                FROM orders 
                WHERE order_id = %s
            """, (order_id,))
            order = cursor.fetchone()
            
            current_status = order['delivery_status']
            payment_status = order['payment_status'] 
            is_outsourced = order.get('is_outsourced', False)

            cursor.execute("""
                UPDATE orders 
                SET delivery_status = %s 
                WHERE order_id = %s
            """, (new_status, order_id))

            if new_status == 'delivered' and current_status != 'delivered' and not is_outsourced:
                
                cursor.execute("""
                    SELECT 
                        sm.material_id, 
                        SUM(sm.quantity_consumed * oi.quantity) AS total_deduct_qty
                    FROM order_items oi
                    JOIN service_materials sm ON oi.service_id = sm.service_id
                    WHERE oi.order_id = %s
                    GROUP BY sm.material_id
                """, (order_id,))
                
                materials_to_deduct = cursor.fetchall()

                for mat in materials_to_deduct:
                    m_id = mat['material_id']
                    deduct_qty = float(mat['total_deduct_qty'] or 0)
                    
                    if deduct_qty > 0:
                        cursor.execute("""
                            UPDATE materials 
                            SET stock_quantity = stock_quantity - %s 
                            WHERE material_id = %s
                        """, (deduct_qty, m_id))
                        
            if new_status == 'delivered' and payment_status == 'paid':
                cursor.execute("""
                    UPDATE orders 
                    SET status = 'completed' 
                    WHERE order_id = %s
                """, (order_id,))
                flash('🎉 Đã xuất kho thành công! Đơn hàng HOÀN THÀNH.', 'success')
            else:
                flash('Đã cập nhật trạng thái giao hàng và xuất kho thành công!', 'success')
            
            log_system_action(
                user_id=current_user.id,
                username=current_user.username,
                full_name=current_user.full_name,
                action_type='UPD_DELIVERY',
                target_module=MD_SALE,
                description=f"Cập nhật trạng thái giao hàng đơn #{order_id} thành {new_status}",
                ip_address=request.remote_addr
            )

            conn.commit()
            
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi cập nhật giao hàng: {e}")
        flash(f'Lỗi khi cập nhật giao hàng: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('orders.order_detail_page', order_id=order_id))
    
@orders_bp.route('/update_outsource_status', methods=['POST'])
@requires_permission('sale', 'admin') 
def update_outsource_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        order_id = request.form.get('order_id')
        delivery_date = request.form.get('delivery_date')
        status = request.form.get('status')
        
        if not delivery_date or delivery_date.strip() == '':
            delivery_date = None  
            
        cursor.execute("""
            UPDATE Orders 
            SET outsource_delivery_date = %s, 
                outsource_status = %s 
            WHERE order_id = %s
        """, (delivery_date, status, order_id))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='UPD_OUTSOURCE',
            target_module=MD_SALE,
            description=f"Cập nhật tiến độ gia công đơn #{order_id} thành {status}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Đã cập nhật tiến độ gia công thành công!', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi khi cập nhật trạng thái gia công: {e}")
        flash(f'Đã xảy ra lỗi khi cập nhật: {e}', 'danger')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('orders.order_detail_page', order_id=order_id))
