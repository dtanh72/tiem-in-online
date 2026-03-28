from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import datetime
from psycopg2.extras import RealDictCursor

from flask_login import current_user
from db import get_db_connection
from utils import requires_permission, log_system_action
from constants import COUPONS_HTML, MD_SALE

coupons_bp = Blueprint('coupons', __name__)

@coupons_bp.route('/coupons')
@requires_permission('sale', 'admin')
def coupons_page():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT service_id, service_name FROM services WHERE is_active = true ORDER BY service_name")
    services_list = cursor.fetchall()

    cursor.execute("""
        SELECT c.*, s.service_name 
        FROM coupons c
        LEFT JOIN services s ON c.applicable_service_id = s.service_id
        ORDER BY c.coupon_id DESC
    """)
    coupons_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(COUPONS_HTML, coupons_list=coupons_list, services_list=services_list)

@coupons_bp.route('/add_coupon', methods=['POST'])
@requires_permission('sale', 'admin')
def add_coupon():
    applicable_service_id = request.form.get('applicable_service_id')
    if not applicable_service_id:
        applicable_service_id = None
        
    min_service_quantity = int(request.form.get('min_service_quantity', 0))
    code = request.form['code'].upper()
    discount_type = request.form['discount_type']
    discount_value = request.form['discount_value']
    min_order_value = request.form['min_order_value']
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    usage_limit = request.form['usage_limit']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO coupons (
                code, discount_type, discount_value, min_order_value, 
                start_date, end_date, usage_limit, 
                applicable_service_id, min_service_quantity 
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (code, discount_type, discount_value, min_order_value, 
              start_date, end_date, usage_limit, 
              applicable_service_id, min_service_quantity))
              
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_COUPON',
            target_module=MD_SALE,
            description=f"Thêm mã giảm giá #{code}",
            ip_address=request.remote_addr
        )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi Coupon: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('coupons.coupons_page'))

@coupons_bp.route('/toggle_coupon_status/<int:coupon_id>', methods=['POST'])
@requires_permission('sale', 'admin')
def toggle_coupon_status(coupon_id):
    conn = get_db_connection()
    cur = conn.cursor()
    sql = """
        UPDATE Coupons 
        SET status = CASE WHEN status = 'active' THEN 'inactive' ELSE 'active' END 
        WHERE coupon_id = %s
        RETURNING status, code
    """
    cur.execute(sql, (coupon_id,))
    res = cur.fetchone()
    if res:
        new_status, code = res
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='TOGGLE_COUPON',
            target_module=MD_SALE,
            description=f"Đổi trạng thái mã #{code} thành {new_status}",
            ip_address=request.remote_addr
        )

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('coupons.coupons_page'))

@coupons_bp.route('/ajax/check_coupon', methods=['POST'])
@requires_permission('sale')
def check_coupon():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        code = request.form['code'].upper()
        order_total = float(request.form['order_total'])
        today = datetime.date.today()
        
        sql = "SELECT * FROM Coupons WHERE code = %s AND status = 'active'"
        cur.execute(sql, (code,))
        coupon = cur.fetchone()
        
        if not coupon:
            return jsonify({'valid': False, 'message': 'Mã không tồn tại hoặc đã bị tắt.'})
        
        if coupon['start_date'] > today or coupon['end_date'] < today:
            return jsonify({'valid': False, 'message': 'Mã chưa đến hạn hoặc đã hết hạn.'})
            
        min_val = float(coupon['min_order_value'])
        if order_total < min_val:
            return jsonify({'valid': False, 'message': f'Đơn hàng phải từ {min_val:,.0f} trở lên.'})
            
        if coupon['usage_limit'] > 0 and coupon['used_count'] >= coupon['usage_limit']:
                return jsonify({'valid': False, 'message': 'Mã đã hết lượt sử dụng.'})
        
        discount_amount = 0
        disc_val = float(coupon['discount_value'])
        
        if coupon['discount_type'] == 'fixed':
            discount_amount = disc_val
        else:
            discount_amount = order_total * (disc_val / 100)
            
        if discount_amount > order_total:
            discount_amount = order_total

        return jsonify({
            'valid': True,
            'message': 'Áp dụng mã thành công!',
            'code': coupon['code'],
            'discount_type': coupon['discount_type'],
            'discount_value': coupon['discount_value'],
            'min_order_value': coupon['min_order_value'],
            'applicable_service_id': coupon['applicable_service_id'],
            'min_service_quantity': coupon['min_service_quantity']
        })
        
    except Exception as e:
        print(f"Lỗi Check Coupon: {e}")
        return jsonify({'valid': False, 'message': f'Lỗi hệ thống: {str(e)}'})
    finally:
        cur.close()
        conn.close()
