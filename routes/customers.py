from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from utils import log_system_action, requires_permission
from constants import (CUSTOMERS_HTML, EDIT_CUSTOMER_HTML, 
                       CUSTOMER_DEBT_REPORT_HTML, CUSTOMER_DEBT_DETAIL_HTML, MD_SALE)

customers_bp = Blueprint('customers', __name__)

@customers_bp.route('/customers')
@requires_permission('sale')
def customers_page():
    conn = get_db_connection()
    if conn is None: return "Lỗi DB", 500
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM Customers ORDER BY customer_id DESC")
    customers_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template(CUSTOMERS_HTML, customers_list=customers_list)

@customers_bp.route('/add_customer', methods=['POST'])
@requires_permission('sale')
def add_customer():
    def clean(val):
        return val if val and val.strip() != '' else None

    name = request.form.get('customer_name')
    phone = clean(request.form.get('phone'))
    email = clean(request.form.get('email'))
    address = clean(request.form.get('address'))
    company = clean(request.form.get('company_name'))
    tax = clean(request.form.get('tax_id'))
    billing = clean(request.form.get('billing_address'))

    if not name:
        flash("Tên khách hàng là thông tin bắt buộc!", "danger")
        return redirect(url_for('customers.customers_page'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor) 
    
    try:
        sql = """
            INSERT INTO Customers 
            (customer_name, phone, email, address, company_name, tax_id, billing_address, is_active) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING customer_id
        """
        val = (name, phone, email, address, company, tax, billing)
        cur.execute(sql, val)
        
        new_row = cur.fetchone()
        if new_row:
            new_id = new_row['customer_id'] 
        else:
            raise Exception("Database không trả về ID mới!")
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_CUSTOMER',
            target_module=MD_SALE,
            description=f"Thêm Khách hàng #{name}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
        flash("Thêm khách hàng thành công!", "success")
        
    except Exception as e:
        conn.rollback()
        print(f"Lỗi khi thêm khách hàng: {e}")
        flash(f"Lỗi khi thêm khách hàng: {str(e)}", "danger") 
        
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('customers.customers_page'))

@customers_bp.route('/delete_customer/<int:customer_id>', methods=['POST'])
@requires_permission('all')
def delete_customer(customer_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM Customers WHERE customer_id = %s", (customer_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi xóa khách hàng: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('customers.customers_page'))

@customers_bp.route('/edit_customer/<int:customer_id>')
@requires_permission('sale')
def edit_customer_page(customer_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM Customers WHERE customer_id = %s", (customer_id,))
    data = cur.fetchone()
    cur.close()
    conn.close()
    
    if data:
        return render_template(EDIT_CUSTOMER_HTML, customer=data)
    else:
        return "Không tìm thấy khách hàng!", 404

@customers_bp.route('/update_customer', methods=['POST'])
@requires_permission('sale')
def update_customer():
    c_id = request.form['customer_id']
    name = request.form['customer_name']
    phone = request.form['phone']
    email = request.form['email']
    addr = request.form['address']
    comp = request.form['company_name']
    tax = request.form['tax_id']
    bill = request.form['billing_address']

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = """
            UPDATE Customers 
            SET customer_name=%s, phone=%s, email=%s, address=%s, company_name=%s, tax_id=%s, billing_address=%s
            WHERE customer_id=%s
        """
        cur.execute(sql, (name, phone, email, addr, comp, tax, bill, c_id))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='UPD_CUSTOMER',
            target_module=MD_SALE,
            description=f"Cập nhật thông tin Khách hàng ID #{c_id}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi update khách: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('customers.customers_page'))

@customers_bp.route('/toggle_customer/<int:id>', methods=['POST'])
@requires_permission('all')
def toggle_customer(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("UPDATE Customers SET is_active = NOT is_active WHERE customer_id = %s", (id,))
        
        sql = "SELECT is_active FROM Customers WHERE customer_id = %s"
        cur.execute(sql, (id,))
        cus_active = cur.fetchone()
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ACT_CUSTOMER',
            target_module=MD_SALE,
            description=f"Trạng thái CustomerID #{id} là #{cus_active['is_active']}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi thay đổi trạng thái khách hàng: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('customers.customers_page'))

@customers_bp.route('/report/customer_debt')
@requires_permission('accounting', 'sale') 
def customer_debt_report():
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    sql = """
        SELECT 
            C.customer_id, 
            C.customer_name, 
            C.phone,
            SUM(O.total_amount - O.amount_paid) AS total_due
        FROM Orders AS O
        JOIN Customers AS C ON O.customer_id = C.customer_id
        WHERE O.payment_status != 'paid'
            AND O.status != 'cancelled'
        GROUP BY C.customer_id, C.customer_name, C.phone
        HAVING SUM(O.total_amount - O.amount_paid) > 0 
        ORDER BY total_due DESC
    """
    cursor.execute(sql)
    debt_list = cursor.fetchall()
    
    total_all_due = sum(float(item['total_due'] or 0) for item in debt_list)
    
    cursor.close()
    conn.close()
    
    return render_template(CUSTOMER_DEBT_REPORT_HTML, 
                           debt_list=debt_list,
                           total_all_due=total_all_due)

@customers_bp.route('/report/customer_debt/<int:customer_id>')
@requires_permission('accounting', 'sale') 
def customer_debt_detail_report(customer_id):
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT * FROM Customers WHERE customer_id = %s", (customer_id,))
    customer_info = cursor.fetchone()

    sql = """
        SELECT 
            order_id, 
            order_date,
            total_amount,
            amount_paid,
            (total_amount - amount_paid) AS amount_due
        FROM Orders
        WHERE customer_id = %s 
            AND payment_status != 'paid' 
            AND status != 'cancelled'
        ORDER BY order_date ASC
    """
    cursor.execute(sql, (customer_id,))
    unpaid_orders_list = cursor.fetchall()
    
    total_due = sum(float(item['amount_due'] or 0) for item in unpaid_orders_list)
    
    cursor.close()
    conn.close()
    
    if not customer_info: return "Không tìm thấy khách hàng!", 404
        
    return render_template(CUSTOMER_DEBT_DETAIL_HTML, 
                           customer_info=customer_info,
                           unpaid_orders_list=unpaid_orders_list,
                           total_due=total_due)


@customers_bp.route('/ajax/add_customer', methods=['POST'])
@requires_permission('accounting', 'sale')
def ajax_add_customer():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        name = request.form.get('customer_name')
        phone = request.form.get('phone', '')
        
        if not name:
            return jsonify({'success': False, 'error': 'Tên khách hàng là bắt buộc!'})
        
        sql = "INSERT INTO Customers (customer_name, phone, is_active) VALUES (%s, %s, TRUE) RETURNING customer_id"
        cur.execute(sql, (name, phone))
        
        new_row = cur.fetchone()
        
        if new_row:
            try:
                new_id = new_row['customer_id']
            except (TypeError, KeyError, IndexError):
                new_id = new_row[0]
        else:
            raise Exception("Không tạo được ID")
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name
        })
        
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi AJAX Customer: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()
