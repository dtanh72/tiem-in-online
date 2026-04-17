from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from utils import log_system_action, requires_permission
from constants import (TB_HTML, CT_TB_HTML, EQUIP_HIST_HTML, MD_TECH)

equipment_bp = Blueprint('equipment', __name__)

@equipment_bp.route('/equipment')
@requires_permission('asset','accounting')
def equipment_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT E.*, S.supplier_name 
        FROM Equipment E LEFT JOIN Suppliers S ON E.supplier_id = S.supplier_id 
        ORDER BY E.equipment_name
    """)
    eq_list = cur.fetchall()
    
    cur.execute("SELECT * FROM Suppliers ORDER BY supplier_name")
    sup_list = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_template(TB_HTML, equipment_list=eq_list, suppliers_list=sup_list)

@equipment_bp.route('/add_equipment', methods=['POST'])
@requires_permission('asset','accounting')
def add_equipment():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        name = request.form['equipment_name']
        model = request.form['model_number']
        ip = request.form.get('ip_address')
        serial = request.form.get('serial_number')
        p_date = request.form['purchase_date'] or None
        sup_id = request.form['supplier_id'] or None
        
        w_date = request.form.get('warranty_end_date') or None
        w_count = request.form.get('warranty_end_counter')
        w_count = int(w_count) if w_count else None
        
        init_c = request.form.get('initial_counter')
        print_c = int(init_c) if init_c else 0
        
        sql = """
            INSERT INTO Equipment (equipment_name, ip_address, serial_number, model_number, supplier_id, 
                                   purchase_date, warranty_end_date, warranty_end_counter, status, print_count, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, TRUE)
            RETURNING equipment_id
        """
        cur.execute(sql, (name, ip, serial, model, sup_id, p_date, w_date, w_count, print_c))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_EQUIPMENT',
            target_module=MD_TECH,
            description=f"Thêm thiết bị mới: {name}",
            ip_address=request.remote_addr
        )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('equipment.equipment_page'))
    
@equipment_bp.route('/delete_equipment/<int:equipment_id>', methods=['POST'])
@requires_permission('all') 
def delete_equipment(equipment_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        sql = "DELETE FROM Equipment WHERE equipment_id = %s"
        cur.execute(sql, (equipment_id,))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='DEL_EQUIPMENT',
            target_module=MD_TECH,
            description=f"Xóa thiết bị ID #{equipment_id}",
            ip_address=request.remote_addr
        )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi xóa thiết bị: {e}")
        flash(f"Không thể xóa thiết bị (có thể đang có dữ liệu liên quan). Lỗi: {e}", "danger")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('equipment.equipment_page'))

@equipment_bp.route('/equipment_detail/<int:equipment_id>')
@requires_permission('asset','accounting') 
def equipment_detail_page(equipment_id):
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql_eq = """
        SELECT E.*, S.supplier_name 
        FROM Equipment E 
        LEFT JOIN Suppliers S ON E.supplier_id = S.supplier_id 
        WHERE E.equipment_id = %s
    """
    cur.execute(sql_eq, (equipment_id,))
    equipment_info = cur.fetchone()
    
    sql_logs = """
        SELECT ML.*, S.supplier_name, M.material_name AS replaced_part_name 
        FROM Maintenance_Logs AS ML
        LEFT JOIN Suppliers AS S ON ML.supplier_id = S.supplier_id
        LEFT JOIN Materials AS M ON ML.replaced_material_id = M.material_id
        WHERE ML.equipment_id = %s 
        ORDER BY ML.maintenance_date DESC
    """
    cur.execute(sql_logs, (equipment_id,))
    logs_list = cur.fetchall()
    
    cur.execute("SELECT supplier_id, supplier_name FROM Suppliers ORDER BY supplier_name")
    suppliers_list = cur.fetchall()
    
    sql_parts = """
        SELECT material_id, material_name, stock_quantity 
        FROM Materials 
        WHERE material_type = 'maintenance'
        ORDER BY material_name
    """
    cur.execute(sql_parts)
    maintenance_parts_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not equipment_info: return "Không tìm thấy thiết bị!", 404
        
    return render_template(CT_TB_HTML, 
                           equipment_info=equipment_info,
                           logs_list=logs_list,
                           suppliers_list=suppliers_list,
                           maintenance_parts_list=maintenance_parts_list)

@equipment_bp.route('/edit_equipment_info', methods=['POST'])
@requires_permission('asset') 
def edit_equipment_info():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        equipment_id = request.form['equipment_id']
        name = request.form['equipment_name']
        ip_addr = request.form.get('ip_address')
        serial = request.form.get('serial_number')
        model = request.form['model_number']
        supplier_id = request.form.get('supplier_id')
        
        p_date = request.form.get('purchase_date')
        if not p_date or p_date.strip() == '': p_date = None
        
        w_date = request.form.get('warranty_end_date')
        if not w_date or w_date.strip() == '': w_date = None
        
        val_supplier = supplier_id if supplier_id and supplier_id.strip() != '' else None

        sql = """
            UPDATE Equipment 
            SET equipment_name = %s, ip_address = %s, serial_number = %s, 
                model_number = %s, supplier_id = %s, purchase_date = %s, 
                warranty_end_date = %s
            WHERE equipment_id = %s
        """
        cur.execute(sql, (name, ip_addr, serial, model, val_supplier, p_date, w_date, equipment_id))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='EDIT_EQUIPMENT',
            target_module=MD_TECH,
            description=f"Cập nhật thông tin chi tiết thiết bị ID #{equipment_id}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Cập nhật thông tin thiết bị thành công!', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"Lỗi SQL Edit Equipment: {e}")
        flash(f"Lỗi cập nhật: {e}", "danger")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('equipment.equipment_detail_page', equipment_id=equipment_id))

@equipment_bp.route('/toggle_equipment/<int:id>', methods=['POST'])
@requires_permission('all') 
def toggle_equipment(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE Equipment SET is_active = NOT is_active WHERE equipment_id = %s", (id,))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='TOGGLE_EQUIPMENT',
            target_module=MD_TECH,
            description=f"Thay đổi trạng thái thiết bị ID #{id}",
            ip_address=request.remote_addr
        )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi Toggle Equipment: {e}")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('equipment.equipment_page'))

@equipment_bp.route('/update_equipment', methods=['POST'])
@login_required
def update_equipment():
    e_id = request.form['equipment_id']
    name = request.form['equipment_name']
    model = request.form.get('model_number', '')
    serial = request.form.get('serial_number', '')
    supplier = request.form.get('supplier_id') or None 
    
    p_date = request.form.get('purchase_date') or None
    w_date = request.form.get('warranty_end_date') or None
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = """
            UPDATE Equipment 
            SET equipment_name=%s, model_number=%s, serial_number=%s, 
                supplier_id=%s, purchase_date=%s, warranty_end_date=%s
            WHERE equipment_id=%s
        """
        cur.execute(sql, (name, model, serial, supplier, p_date, w_date, e_id))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='UPD_EQUIPMENT',
            target_module=MD_TECH,
            description=f"Cập nhật thiết bị ID #{e_id}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Cập nhật thông tin thiết bị thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi cập nhật: {e}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('equipment.equipment_detail_page', equipment_id=e_id))

@equipment_bp.route('/maintenance_history', methods=['GET'])
@requires_permission('admin', 'inventory') 
def maintenance_history():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT equipment_id, equipment_name FROM equipment ORDER BY equipment_name")
        equipment_list = cursor.fetchall()

        filter_equipment = request.args.get('filter_equipment')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = """
            SELECT 
                ml.log_id, 
                ml.maintenance_date, 
                ml.description, 
                ml.cost, 
                ml.current_counter_at_log,
                ml.technician_name,
                ml.replaced_quantity,
                e.equipment_name,
                m.material_name AS replaced_part_name,
                m.base_unit
            FROM maintenance_logs ml
            LEFT JOIN equipment e ON ml.equipment_id = e.equipment_id
            LEFT JOIN materials m ON ml.replaced_material_id = m.material_id
            WHERE 1=1
        """
        params = []

        if filter_equipment:
            query += " AND ml.equipment_id = %s"
            params.append(filter_equipment)
            
        if start_date:
            query += " AND ml.maintenance_date >= %s"
            params.append(start_date)
            
        if end_date:
            query += " AND ml.maintenance_date <= %s"
            params.append(end_date)

        query += " ORDER BY ml.maintenance_date DESC, ml.log_id DESC"

        cursor.execute(query, tuple(params))
        maintenance_logs = cursor.fetchall()

        return render_template(EQUIP_HIST_HTML, 
                               equipment_list=equipment_list,
                               maintenance_logs=maintenance_logs)

    except Exception as e:
        print(f"🔴 Lỗi load lịch sử bảo trì: {e}")
        flash(f"Lỗi hệ thống: {e}", "danger")
        return redirect(url_for('dashboard.dashboard_page'))
    finally:
        cursor.close()
        conn.close()

@equipment_bp.route('/add_maintenance_log', methods=['POST'])
@requires_permission('asset','accounting')
def add_maintenance_log():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        eq_id = request.form['equipment_id']
        m_date = request.form['maintenance_date']
        desc = request.form['description']
        
        cost_str = request.form.get('cost')
        cost = float(cost_str) if cost_str and cost_str.strip() else 0
        
        sup_id = request.form.get('supplier_id') or None
        tech_name = request.form.get('technician_name')
        
        rep_mat_id = request.form.get('replaced_material_id') or None
        qty_str = request.form.get('replaced_quantity')
        rep_qty = int(qty_str) if qty_str and qty_str.strip() else 0
        
        curr_cnt_str = request.form.get('current_machine_counter')
        curr_cnt = int(curr_cnt_str) if curr_cnt_str and curr_cnt_str.strip() else 0
        
        payment_status = request.form.get('payment_status') or ('unpaid' if cost > 0 else 'paid')
        
        w_date = request.form.get('warranty_end_date') or None
        w_cnt_str = request.form.get('warranty_end_counter')
        w_cnt = int(w_cnt_str) if w_cnt_str and w_cnt_str.strip() else None
        
        if sup_id and rep_mat_id and rep_qty > 0:
            cur.execute("UPDATE Materials SET stock_quantity = stock_quantity + %s WHERE material_id = %s", (rep_qty, rep_mat_id))
            
            cur.execute("""
                INSERT INTO Material_Imports (material_id, supplier_id, import_date, quantity_imported, import_price, payment_status)
                VALUES (%s, %s, %s, %s, 0, %s)
            """, (rep_mat_id, sup_id, m_date, rep_qty, 'paid')) 
            
        sql_log = """
            INSERT INTO Maintenance_Logs (equipment_id, supplier_id, maintenance_date, 
                                        description, cost, technician_name, payment_status,
                                        replaced_material_id, replaced_quantity, current_counter_at_log,
                                        warranty_end_date, warranty_end_counter) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(sql_log, (eq_id, sup_id, m_date, desc, cost, tech_name, payment_status, 
                              rep_mat_id, rep_qty, curr_cnt, w_date, w_cnt))
        
        if curr_cnt > 0:
            cur.execute("""
                UPDATE Equipment SET print_count = %s 
                WHERE equipment_id = %s AND print_count < %s
            """, (curr_cnt, eq_id, curr_cnt))
            
        if rep_mat_id and rep_qty > 0:
            cur.execute("UPDATE Materials SET stock_quantity = stock_quantity - %s WHERE material_id = %s", (rep_qty, rep_mat_id))
            
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_MAINTENANCE',
            target_module=MD_TECH,
            description=f"Thêm nhật ký bảo trì thiết bị ID #{eq_id}",
            ip_address=request.remote_addr
        )

        conn.commit()
        
    except Exception as e:
        conn.rollback() 
        print(f"Lỗi Logs: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('equipment.equipment_detail_page', equipment_id=eq_id))

@equipment_bp.route('/ajax_add_equipment', methods=['POST'])
@login_required
def ajax_add_equipment():
    try:
        name = request.form.get('equipment_name')
        if not name:
            return jsonify({'success': False, 'error': 'Tên thiết bị là bắt buộc!'})

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        sql = """
            INSERT INTO Equipment (equipment_name, status, is_active)
            VALUES (%s, 'active', TRUE)
            RETURNING equipment_id
        """
        cur.execute(sql, (name,))
        new_id = cur.fetchone()['equipment_id']
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_EQUIPMENT_AJAX',
            target_module=MD_TECH,
            description=f"Thêm nhanh thiết bị: {name}",
            ip_address=request.remote_addr
        )

        conn.commit()
        conn.close()

        return jsonify({
            'success': True, 
            'new_id': new_id, 
            'new_name': name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
