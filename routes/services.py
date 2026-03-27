from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import current_user
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from utils import log_system_action, requires_permission
from constants import (SERVICES_HTML, EDIT_SERVICE_HTML, SERVICE_MATERIALS_HTML, MD_SALE)

services_bp = Blueprint('services', __name__)

@services_bp.route('/services')
@requires_permission('sale', 'inventory')
def services_page():
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM Services ORDER BY service_id DESC")
    services_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template(SERVICES_HTML, services_list=services_list)

@services_bp.route('/add_service', methods=['POST'])
@requires_permission('sale', 'inventory')
def add_service():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        name = request.form['service_name']
        price = request.form['base_price']
        description = request.form['description']
        u1 = request.form['unit']
        u2 = request.form.get('unit_level2')
        u3 = request.form.get('unit_level3')
                
        if not u2 or u2.strip() == '': u2 = None
        if not u3 or u3.strip() == '': u3 = None

        sql = """
            INSERT INTO Services (service_name, base_price, description, unit, 
                                  unit_level2, unit_level3) 
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING service_id
        """
        cur.execute(sql, (name, price, description, u1, u2, u3))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_SERVICES',
            target_module=MD_SALE,
            description=f"Tạo Service #{name}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi: {e}")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('services.services_page'))

@services_bp.route('/delete_service/<int:service_id>', methods=['POST'])
@requires_permission('all')
def delete_service(service_id):
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
        
    cur = conn.cursor()
    try:
        sql = "DELETE FROM Services WHERE service_id = %s"
        cur.execute(sql, (service_id,))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='DEL_SERVICES',
            target_module=MD_SALE,
            description=f"Xóa ServiceID #{service_id}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi xóa dịch vụ: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('services.services_page'))

@services_bp.route('/edit_service/<int:service_id>')
@requires_permission('sale')
def edit_service_page(service_id):
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
        
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql = "SELECT * FROM Services WHERE service_id = %s"
    cur.execute(sql, (service_id,))
    service_data = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if service_data:
        return render_template(EDIT_SERVICE_HTML, service=service_data)
    else:
        return "Không tìm thấy dịch vụ!", 404

@services_bp.route('/update_service', methods=['POST'])
@requires_permission('sale')
def update_service():
    service_id = request.form['service_id']
    name = request.form['service_name']
    price = request.form['base_price']
    description = request.form['description']
    u1 = request.form['unit']
    u2 = request.form.get('unit_level2')
    u3 = request.form.get('unit_level3')
    
    if not u2 or u2.strip() == '': u2 = None
    if not u3 or u3.strip() == '': u3 = None

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = """
            UPDATE Services 
            SET service_name=%s, base_price=%s, description=%s, 
                unit=%s, unit_level2=%s, unit_level3=%s
            WHERE service_id=%s
        """
        cur.execute(sql, (name, price, description, u1, u2, u3, service_id))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='UPD_SERVICES',
            target_module=MD_SALE,
            description=f"Cập nhật ServiceID #{service_id}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi update dịch vụ: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('services.services_page'))

@services_bp.route('/toggle_service/<int:id>', methods=['POST'])
@requires_permission('all')
def toggle_service(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE Services SET is_active = NOT is_active WHERE service_id = %s", (id,))
        
        sql = "SELECT is_active FROM Services WHERE service_id = %s"
        cur.execute(sql, (id,))
        sv_active = cur.fetchone()[0] # Dùng cursor thường sẽ trả tuple
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ACT_SERVICES',
            target_module=MD_SALE,
            description=f"Trạng thái ServiceID #{id} là #{sv_active}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi thay đổi trạng thái dịch vụ: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('services.services_page'))

@services_bp.route('/service_materials')
@requires_permission('sale', 'inventory') 
def service_materials_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
                    SELECT service_id, service_name, unit, unit_level2, unit_level3 
                    FROM Services
                    WHERE is_active = TRUE
                    ORDER BY service_name
                    """)
    services_list = cursor.fetchall()

    cursor.execute("SELECT material_id, material_name, base_unit FROM Materials WHERE is_active = TRUE ORDER BY material_name")
    materials_list = cursor.fetchall()

    sql_boms = """
        SELECT 
            S.service_id, S.service_name, S.base_price AS selling_price,
            S.unit AS u1, S.unit_level2 AS u2, S.unit_level3 AS u3,
            M.material_name, M.base_unit, 
            SM.quantity_consumed, SM.service_material_id, SM.apply_to_unit_level,
            M.avg_cost_per_base_unit,
            (SM.quantity_consumed * M.avg_cost_per_base_unit) AS estimated_cost
        FROM Service_Materials AS SM
        JOIN Services AS S ON SM.service_id = S.service_id
        JOIN Materials AS M ON SM.material_id = M.material_id
        ORDER BY S.service_name
    """
    cursor.execute(sql_boms)
    raw_boms = cursor.fetchall()
    
    grouped_boms = {}
    for row in raw_boms:
        s_id = row['service_id']
        if s_id not in grouped_boms:
            grouped_boms[s_id] = {
                'service_name': row['service_name'],
                'selling_price': row['selling_price'],
                'total_cost': 0, 
                'items': []
            }
        grouped_boms[s_id]['items'].append(row)
        grouped_boms[s_id]['total_cost'] += float(row['estimated_cost'] or 0)

    cursor.close()
    conn.close()
    
    return render_template(SERVICE_MATERIALS_HTML, 
                           services_list=services_list,
                           materials_list=materials_list,
                           grouped_boms=grouped_boms) 

@services_bp.route('/add_service_material', methods=['POST'])
@requires_permission('sale', 'inventory') 
def add_service_material():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        service_id = request.form['service_id']
        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity_consumed[]')
        levels = request.form.getlist('apply_to_level[]') 

        last_new_id = None

        for i in range(len(material_ids)):
            mat_id = material_ids[i]
            qty = quantities[i]
            level = levels[i] 
            
            if not mat_id or not qty: 
                continue

            sql = """
                INSERT INTO Service_Materials (service_id, material_id, quantity_consumed, apply_to_unit_level) 
                VALUES (%s, %s, %s, %s) RETURNING service_material_id
            """
            cursor.execute(sql, (service_id, mat_id, float(qty), int(level)))
            last_new_id = cursor.fetchone()['service_material_id']
        
        conn.commit() 
    except Exception as e:
        conn.rollback() 
        print(f"🔴 Lỗi thêm BOM: {e}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('services.service_materials_page'))

@services_bp.route('/delete_service_material/<int:sm_id>', methods=['POST'])
@requires_permission('all') 
def delete_service_material(sm_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        sql = "DELETE FROM Service_Materials WHERE service_material_id = %s"
        cursor.execute(sql, (sm_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi xóa BOM: {e}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('services.service_materials_page'))

@services_bp.route('/ajax/add_service', methods=['POST'])
@requires_permission('sale', 'inventory')
def ajax_add_service():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        service_name = request.form.get('service_name')
        base_price = float(request.form.get('base_price', 0))
        unit = request.form.get('unit')
        unit_level2 = request.form.get('unit_level2')
        unit_level3 = request.form.get('unit_level3')
        
        sql = """
            INSERT INTO Services (service_name, base_price, unit, unit_level2, unit_level3, is_active) 
            VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING service_id
        """
        cursor.execute(sql, (service_name, base_price, unit, unit_level2, unit_level3))
        new_id = cursor.fetchone()['service_id']
        conn.commit()
        
        return jsonify({
            'success': True, 
            'new_id': new_id, 
            'new_name': service_name,
            'new_price': base_price,
            'new_u1': unit,
            'new_u2': unit_level2 or '',
            'new_u3': unit_level3 or ''
        })
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi ajax_add_service: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()
