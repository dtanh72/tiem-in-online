from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from utils import requires_permission, log_system_action
from constants import (NCC_HTML, SUPPLIER_DEBT_REPORT, MD_ACC)

suppliers_bp = Blueprint('suppliers', __name__)

@suppliers_bp.route('/suppliers')
@login_required
def suppliers_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM Suppliers ORDER BY supplier_id DESC")
    suppliers = cur.fetchall()
    conn.close()
    return render_template(NCC_HTML, suppliers_list=suppliers)

@suppliers_bp.route('/add_supplier', methods=['POST'])
@login_required
def add_supplier():
    name = request.form['supplier_name']
    phone = request.form.get('phone', '')
    email = request.form.get('email', '')
    address = request.form.get('address', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = """
            INSERT INTO Suppliers (supplier_name, phone, email, address)
            VALUES (%s, %s, %s, %s)
        """
        cur.execute(sql, (name, phone, email, address))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_SUPPLIER',
            target_module=MD_ACC,
            description=f"Thêm nhà cung cấp: {name}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Thêm nhà cung cấp thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('suppliers.suppliers_page'))

@suppliers_bp.route('/toggle_supplier/<int:id>', methods=['POST'])
@login_required
def toggle_supplier(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE Suppliers SET is_active = NOT is_active WHERE supplier_id = %s", (id,))
    
    log_system_action(
        user_id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        action_type='TOGGLE_SUPPLIER',
        target_module=MD_ACC,
        description=f"Thay đổi trạng thái nhà cung cấp ID #{id}",
        ip_address=request.remote_addr
    )

    conn.commit()
    conn.close()
    return redirect(url_for('suppliers.suppliers_page'))

@suppliers_bp.route('/report/supplier_debt')
@requires_permission('accounting', 'inventory') 
def supplier_debt_report():
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    sql_imports = """
        SELECT 
            S.import_id AS id, 
            S.import_date AS date, 
            COALESCE(Sup.supplier_name, 'Không xác định') as supplier_name,
            S.total_amount,
            'Phiếu nhập kho' AS type,
            S.payment_status,
            'import_slip' AS source,
            NULL AS material_id
        FROM Import_Slips AS S
        LEFT JOIN Suppliers AS Sup ON S.supplier_id = Sup.supplier_id
        WHERE S.payment_status = 'unpaid'
    """
    cursor.execute(sql_imports)
    import_debts = cursor.fetchall()
    
    sql_maintenance = """
        SELECT 
            ML.log_id AS id, 
            ML.maintenance_date AS date, 
            COALESCE(S.supplier_name, 'Tự làm / Không xác định') as supplier_name,
            ML.cost AS total_amount,
            ML.description AS type,
            ML.payment_status,
            'maintenance' AS source,
            ML.equipment_id
        FROM Maintenance_Logs AS ML
        LEFT JOIN Suppliers AS S ON ML.supplier_id = S.supplier_id
        WHERE ML.payment_status = 'unpaid' AND ML.cost > 0
    """
    cursor.execute(sql_maintenance)
    maintenance_debts = cursor.fetchall()
    
    all_debts = import_debts + maintenance_debts
    all_debts.sort(key=lambda x: x['date'], reverse=True)
    
    total_all_due = sum(float(item['total_amount'] or 0) for item in all_debts)
    
    cursor.close()
    conn.close()
    
    return render_template(SUPPLIER_DEBT_REPORT,
                           all_debts=all_debts,
                           total_all_due=total_all_due)

@suppliers_bp.route('/pay_supplier_bill', methods=['POST'])
@requires_permission('accounting') 
def pay_supplier_bill():
    conn = get_db_connection()
    cursor = conn.cursor() 
    
    try:
        bill_id = request.form['bill_id']
        bill_source = request.form['bill_source']

        table_name = ""
        if bill_source == 'import_slip':
            sql = "UPDATE Import_Slips SET payment_status = 'paid' WHERE import_id = %s"
            table_name = "Import_Slips"
        elif bill_source == 'maintenance':
            sql = "UPDATE Maintenance_Logs SET payment_status = 'paid' WHERE log_id = %s"
            table_name = "Maintenance_Logs"
        else:
            return "Lỗi: Nguồn công nợ không xác định.", 400

        cursor.execute(sql, (bill_id,))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='PAY_SUPPLIER',
            target_module=MD_ACC,
            description=f"Thanh toán công nợ NCC cho {bill_source} ID #{bill_id}",
            ip_address=request.remote_addr
        )

        conn.commit()
    except Exception as err:
        if 'conn' in locals(): conn.rollback() 
        print(f"🔴 LỖI KHI THANH TOÁN NCC: {err}")
        return f"Đã xảy ra lỗi: {err}", 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
    
    return redirect(url_for('suppliers.supplier_debt_report'))


@suppliers_bp.route('/ajax/add_supplier', methods=['POST'])
@requires_permission('accounting', 'inventory')
def ajax_add_supplier():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        name = request.form.get('supplier_name')
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        
        if not name:
            return jsonify({'success': False, 'error': 'Tên nhà cung cấp là bắt buộc!'})
        
        sql = "INSERT INTO Suppliers (supplier_name, phone, email, is_active) VALUES (%s, %s, %s, TRUE) RETURNING supplier_id"
        cur.execute(sql, (name, phone, email))
        
        new_row = cur.fetchone()
        
        if new_row:
            try:
                new_id = new_row['supplier_id']
            except (TypeError, KeyError, IndexError):
                new_id = new_row[0]
        else:
            raise Exception("Không lấy được ID mới từ Database")
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_SUPPLIER_AJAX',
            target_module=MD_ACC,
            description=f"Thêm nhanh nhà cung cấp: {name}",
            ip_address=request.remote_addr
        )

        conn.commit()
        
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name
        })
        
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi AJAX Supplier: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()
