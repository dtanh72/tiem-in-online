from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import datetime
from flask_login import current_user, login_required
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from utils import log_system_action, requires_permission
from constants import (MATERIALS_HTML, EDIT_MATERIAL_HTML, CREATE_IMPORT_HTML,
                       IMPORT_DETAIL_HTML, CREATE_ADJUSTMENT_INV_HTML, ADJUSTMENT_DETAIL_HTML)

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/materials')
@login_required
def materials_page():
    if current_user.role_id not in [1, 2, 3]:
        flash('Bạn không có quyền truy cập kho!', 'danger')
        return redirect(url_for('dashboard.dashboard_page'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM materials WHERE is_active = TRUE ORDER BY material_id DESC")
    materials_list = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template(MATERIALS_HTML, materials_list=materials_list)

@inventory_bp.route('/add_material', methods=['POST'])
@login_required
def add_material():
    try:
        name = request.form['material_name']
        m_type = request.form['material_type']
        
        lifespan = request.form.get('lifespan_prints', 0) if m_type == 'maintenance' else 0
        
        base_unit = request.form['base_unit']
        import_unit = request.form.get('import_unit', '')
        
        conv_factor = request.form.get('import_conversion_factor')
        conv_factor = float(conv_factor) if conv_factor and float(conv_factor) > 0 else 1.0
        
        stock_qty = request.form.get('stock_quantity', 0)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        sql = """
            INSERT INTO materials 
            (material_name, material_type, lifespan_prints, base_unit, import_unit, import_conversion_factor, stock_quantity, is_active) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING material_id
        """
        cur.execute(sql, (name, m_type, lifespan, base_unit, import_unit, conv_factor, stock_qty))
        
        new_id = cur.fetchone()['material_id']
        conn.commit()
        flash('Thêm vật tư thành công!', 'success')
        
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        if 'conn' in locals(): conn.close()
    
    return redirect(url_for('inventory.materials_page'))

@inventory_bp.route('/edit_material/<int:material_id>')
@login_required
def edit_material_page(material_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM materials WHERE material_id = %s", (material_id,))
    material_data = cur.fetchone()
    cur.close()
    conn.close()
    
    if material_data:
        return render_template(EDIT_MATERIAL_HTML, material=material_data)
    else:
        return "Không tìm thấy vật tư!", 404

@inventory_bp.route('/update_material', methods=['POST'])
@login_required
def update_material():
    try:
        m_id = request.form['material_id']
        name = request.form['material_name']
        m_type = request.form['material_type']
        
        lifespan = request.form.get('lifespan_prints', 0) if m_type == 'maintenance' else 0
        base_unit = request.form['base_unit']
        import_unit = request.form.get('import_unit', '')
        
        conv_factor = request.form.get('import_conversion_factor')
        conv_factor = float(conv_factor) if conv_factor and float(conv_factor) > 0 else 1.0
        stock_qty = request.form.get('stock_quantity', 0)

        conn = get_db_connection()
        cur = conn.cursor()

        sql = """
            UPDATE materials 
            SET material_name = %s, material_type = %s, lifespan_prints = %s, 
                base_unit = %s, import_unit = %s, import_conversion_factor = %s, stock_quantity = %s
            WHERE material_id = %s
        """
        cur.execute(sql, (name, m_type, lifespan, base_unit, import_unit, conv_factor, stock_qty, m_id))
        
        conn.commit()
        flash('Cập nhật vật tư thành công!', 'success')
        
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        if 'conn' in locals(): conn.close()
    
    return redirect(url_for('inventory.materials_page'))

@inventory_bp.route('/toggle_material/<int:id>', methods=['POST'])
@login_required
def toggle_material(id):
    if current_user.role_id not in [1, 2]:
        flash('Bạn không có quyền thực hiện thao tác này!', 'danger')
        return redirect(url_for('inventory.materials_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE materials SET is_active = NOT is_active WHERE material_id = %s", (id,))
        conn.commit()
        flash('Đã thay đổi trạng thái vật tư.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('inventory.materials_page'))

@inventory_bp.route('/imports')
@login_required
def imports_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql_imports = """
        SELECT 
            MI.import_date, 
            M.material_name, 
            S.supplier_name, 
            MI.quantity_imported, 
            M.import_unit,
            MI.import_price
        FROM material_imports AS MI
        JOIN materials AS M ON MI.material_id = M.material_id
        LEFT JOIN suppliers AS S ON MI.supplier_id = S.supplier_id
        ORDER BY MI.import_date DESC
    """
    cur.execute(sql_imports)
    imports_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('imports.html', imports_list=imports_list)

@inventory_bp.route('/create_import')
@requires_permission('inventory')
def create_import_page():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("SELECT supplier_id, supplier_name FROM Suppliers WHERE is_active = TRUE ORDER BY supplier_name")
        suppliers_list = cursor.fetchall()
        
        cursor.execute("SELECT material_id, material_name, import_unit FROM Materials WHERE is_active = TRUE ORDER BY material_name")
        materials_list = cursor.fetchall()

        filter_date = request.args.get('filter_date')
        filter_supplier = request.args.get('filter_supplier')
        
        query = """
            SELECT i.*, s.supplier_name 
            FROM Import_Slips i
            LEFT JOIN Suppliers s ON i.supplier_id = s.supplier_id
            WHERE 1=1
        """
        params = []
        
        if filter_date:
            query += " AND DATE(i.import_date) = %s"
            params.append(filter_date)
            
        if filter_supplier:
            query += " AND i.supplier_id = %s"
            params.append(filter_supplier)
            
        query += " ORDER BY i.import_date DESC, i.import_id DESC"
        
        cursor.execute(query, tuple(params))
        import_slips_list = cursor.fetchall()
        
        today = datetime.date.today().strftime('%Y-%m-%d')
        
        return render_template(CREATE_IMPORT_HTML, 
                               suppliers_list=suppliers_list,
                               materials_list=materials_list,
                               import_slips_list=import_slips_list,
                               today=today)
    except Exception as e:
        print(f"🔴 Lỗi load trang tạo phiếu nhập: {e}")
        flash(f"Có lỗi xảy ra: {e}", "danger")
        return redirect(url_for('dashboard.dashboard_page'))
    finally:
        cursor.close()
        conn.close()

@inventory_bp.route('/submit_import_slip', methods=['POST'])
@requires_permission('inventory')
def submit_import_slip():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        supplier_id = request.form.get('supplier_id')
        import_date = request.form.get('import_date')
        payment_status = request.form.get('payment_status')
        notes = request.form.get('notes', '') 

        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        total_amount = 0
        valid_items = []

        for i in range(len(material_ids)):
            if material_ids[i] and float(quantities[i] or 0) > 0:
                m_id = material_ids[i]
                qty = float(quantities[i])
                price = float(unit_prices[i])
                line_total = qty * price
                total_amount += line_total
                
                valid_items.append({
                    'material_id': m_id,
                    'quantity': qty,
                    'unit_price': price,
                    'line_total': line_total
                })

        if not valid_items:
            flash('Phiếu nhập phải có ít nhất 1 vật tư hợp lệ!', 'danger')
            return redirect(url_for('inventory.create_import_page'))

        cursor.execute("""
            INSERT INTO Import_Slips (supplier_id, import_date, total_amount, payment_status, notes)
            VALUES (%s, %s, %s, %s, %s) RETURNING import_id
        """, (supplier_id, import_date, total_amount, payment_status, notes))
        
        new_import_id = cursor.fetchone()['import_id'] 

        for item in valid_items:
            cursor.execute("""
                INSERT INTO Import_Details (import_id, material_id, quantity, unit_price, line_total)
                VALUES (%s, %s, %s, %s, %s)
            """, (new_import_id, item['material_id'], item['quantity'], item['unit_price'], item['line_total']))

            cursor.execute("SELECT import_conversion_factor FROM Materials WHERE material_id = %s", (item['material_id'],))
            factor_data = cursor.fetchone()
            
            conversion_factor = float(factor_data['import_conversion_factor'] if factor_data and factor_data['import_conversion_factor'] else 1)
            qty_to_add = item['quantity'] * conversion_factor

            cursor.execute("""
                UPDATE Materials 
                SET stock_quantity = COALESCE(stock_quantity, 0) + %s 
                WHERE material_id = %s
            """, (qty_to_add, item['material_id']))

        conn.commit()
        flash('Đã lưu phiếu nhập kho và cập nhật số lượng tồn thành công!', 'success')

    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi submit_import_slip: {e}")
        flash(f'Lỗi hệ thống khi lưu phiếu: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('inventory.create_import_page'))

@inventory_bp.route('/import_slip/<int:import_id>')
@requires_permission('admin', 'inventory')
def view_import_slip(import_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT * FROM Import_Slips WHERE import_id = %s", (import_id,))
    slip = cursor.fetchone()
    
    if not slip:
        flash('Không tìm thấy phiếu nhập này!', 'danger')
        return redirect(url_for('inventory.create_import_page'))
        
    cursor.execute("""
        SELECT id.*, m.material_name, m.base_unit 
        FROM Import_Details id
        JOIN Materials m ON id.material_id = m.material_id
        WHERE id.import_id = %s
    """, (import_id,))
    items = cursor.fetchall()
    
    cursor.execute("SELECT material_id, material_name, base_unit FROM Materials WHERE is_active = TRUE")
    materials_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template(IMPORT_DETAIL_HTML, slip=slip, items=items, materials_list=materials_list)

@inventory_bp.route('/update_import_slip/<int:import_id>', methods=['POST'])
@requires_permission('admin', 'inventory')
def update_import_slip(import_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        notes = request.form.get('notes')
        import_date = request.form.get('import_date')
        
        cursor.execute("SELECT material_id, quantity FROM Import_Details WHERE import_id = %s", (import_id,))
        old_items = cursor.fetchall()
        for old in old_items:
            cursor.execute("""
                UPDATE Materials 
                SET stock_quantity = stock_quantity - %s 
                WHERE material_id = %s
            """, (old['quantity'], old['material_id']))
            
        cursor.execute("DELETE FROM Import_Details WHERE import_id = %s", (import_id,))
        
        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('unit_price[]')
        total_amount = 0
        
        for i in range(len(material_ids)):
            if material_ids[i] and float(quantities[i] or 0) > 0:
                m_id = material_ids[i]
                qty = float(quantities[i])
                price = float(prices[i])
                line_total = qty * price
                total_amount += line_total
                
                cursor.execute("""
                    INSERT INTO Import_Details (import_id, material_id, quantity, unit_price, line_total)
                    VALUES (%s, %s, %s, %s, %s)
                """, (import_id, m_id, qty, price, line_total))
                
                cursor.execute("""
                    UPDATE Materials 
                    SET stock_quantity = stock_quantity + %s 
                    WHERE material_id = %s
                """, (qty, m_id))

        cursor.execute("""
            UPDATE Import_Slips 
            SET notes = %s, import_date = %s, total_amount = %s 
            WHERE import_id = %s
        """, (notes, import_date, total_amount, import_id))
        
        conn.commit()
        flash('Đã cập nhật phiếu nhập kho và tính lại tồn kho thành công!', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi khi cập nhật phiếu nhập: {e}")
        flash(f'Lỗi hệ thống: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('inventory.view_import_slip', import_id=import_id))

@inventory_bp.route('/adjustments')
@requires_permission('accounting') 
def adjustments_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    sql_adjustments = """
        SELECT SA.adjustment_date, M.material_name, SA.quantity_adjusted, SA.reason
        FROM Stock_Adjustments AS SA
        JOIN Materials AS M ON SA.material_id = M.material_id
        ORDER BY SA.adjustment_date DESC
    """
    cursor.execute(sql_adjustments)
    adjustments_list = cursor.fetchall()
    
    cursor.execute("SELECT material_id, material_name FROM Materials")
    materials_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template(CREATE_ADJUSTMENT_INV_HTML, 
                           adjustments_list=adjustments_list, 
                           materials_list=materials_list)

@inventory_bp.route('/add_adjustment', methods=['POST'])
@requires_permission('accounting') 
def add_adjustment():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        material_id = request.form['material_id']
        quantity = int(request.form['quantity_adjusted']) 
        reason = request.form['reason']
        adjustment_date = request.form['adjustment_date']

        sql_insert = """
            INSERT INTO Stock_Adjustments (material_id, adjustment_date, quantity_adjusted, reason) 
            VALUES (%s, %s, %s, %s) RETURNING adjustment_id
        """
        cursor.execute(sql_insert, (material_id, adjustment_date, quantity, reason))
        new_id = cursor.fetchone()['adjustment_id']
        
        sql_update = """
            UPDATE Materials 
            SET stock_quantity = stock_quantity + %s 
            WHERE material_id = %s
        """
        cursor.execute(sql_update, (quantity, material_id))
        
        conn.commit() 
        
    except Exception as e: 
        conn.rollback() 
        print(f"🔴 Lỗi Điều chỉnh kho: {e}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('inventory.adjustments_page'))

@inventory_bp.route('/create_adjustment')
@requires_permission('accounting') 
def create_adjustment_page():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT material_id, material_name, base_unit, import_unit, stock_quantity, cost_price 
            FROM Materials 
            WHERE is_active = TRUE 
            ORDER BY material_name
        """)
        materials_list = cursor.fetchall()

        filter_date = request.args.get('filter_date')
        filter_material = request.args.get('filter_material')
        
        query = """
            SELECT 
                a.adjustment_id AS id, 
                a.adjustment_date,
                STRING_AGG(m.material_name || ' (' || i.quantity_adjusted || ')', ', ') as materials_summary
            FROM Adjustment_Slips a
            LEFT JOIN Adjustment_Slip_Items i ON a.adjustment_id = i.adjustment_id
            LEFT JOIN Materials m ON i.material_id = m.material_id
            WHERE 1=1
        """
        params = []
        
        if filter_date:
            query += " AND DATE(a.adjustment_date) = %s"
            params.append(filter_date)
            
        if filter_material:
            query += " AND a.adjustment_id IN (SELECT adjustment_id FROM Adjustment_Slip_Items WHERE material_id = %s)"
            params.append(filter_material)
            
        query += " GROUP BY a.adjustment_id, a.adjustment_date ORDER BY a.adjustment_date DESC, a.adjustment_id DESC"
        
        cursor.execute(query, tuple(params))
        adjustment_slips_list = cursor.fetchall()
        
        today = datetime.date.today().strftime('%Y-%m-%d')
    
        return render_template(CREATE_ADJUSTMENT_INV_HTML, 
                               materials_list=materials_list,
                               adjustment_slips_list=adjustment_slips_list,
                               today=today)
    except Exception as e:
        print(f"🔴 Lỗi load trang điều chỉnh: {e}")
        flash(f"Có lỗi xảy ra: {e}", "danger")
        return redirect(url_for('dashboard.dashboard_page'))
    finally:
        cursor.close()
        conn.close()

@inventory_bp.route('/submit_adjustment_slip', methods=['POST'])
@requires_permission('accounting') 
def submit_adjustment_slip():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        adjustment_date = request.form.get('adjustment_date')
        
        cursor.execute("""
            INSERT INTO Adjustment_Slips (adjustment_date) 
            VALUES (%s) RETURNING adjustment_id
        """, (adjustment_date,))
        adj_id = cursor.fetchone()['adjustment_id']

        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity_adjusted[]')
        reasons = request.form.getlist('reason[]')
        unit_costs = request.form.getlist('unit_cost[]')
        unit_types = request.form.getlist('unit_type[]')

        for i in range(len(material_ids)):
            m_id = material_ids[i]
            qty_str = quantities[i]
            
            if m_id and qty_str:
                qty_input = float(qty_str) 
                cost_input = float(unit_costs[i] or 0) 
                unit_type = unit_types[i] if i < len(unit_types) else 'base'
                reason = reasons[i] if i < len(reasons) else ''
                
                if qty_input == 0: continue

                cursor.execute("""
                    SELECT stock_quantity, cost_price, import_conversion_factor 
                    FROM Materials WHERE material_id = %s
                """, (m_id,))
                mat = cursor.fetchone()
                
                current_stock = float(mat['stock_quantity'] or 0)
                current_mac = float(mat['cost_price'] or 0)
                factor = float(mat['import_conversion_factor'] or 1)

                if unit_type == 'import':
                    actual_qty = qty_input * factor       
                    actual_cost = cost_input / factor     
                else:
                    actual_qty = qty_input                
                    actual_cost = cost_input

                cursor.execute("""
                    INSERT INTO Adjustment_Slip_Items (adjustment_id, material_id, quantity_adjusted, reason, unit_cost)
                    VALUES (%s, %s, %s, %s, %s)
                """, (adj_id, m_id, actual_qty, reason, actual_cost))

                new_stock = current_stock + actual_qty
                new_mac = current_mac 

                if actual_qty > 0:
                    total_old_value = current_stock * current_mac
                    total_added_value = actual_qty * actual_cost
                    
                    if new_stock > 0:
                        new_mac = (total_old_value + total_added_value) / new_stock

                cursor.execute("""
                    UPDATE Materials 
                    SET stock_quantity = %s, cost_price = %s 
                    WHERE material_id = %s
                """, (new_stock, new_mac, m_id))

        conn.commit()
        flash('Đã lưu Phiếu điều chỉnh và cập nhật lại Tồn kho, Giá vốn thành công!', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi submit_adjustment_slip: {e}")
        flash(f'Lỗi hệ thống khi lưu: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('inventory.create_adjustment_page'))

@inventory_bp.route('/view_adjustment_slip/<int:id>', methods=['GET'])
@requires_permission('admin', 'inventory') 
def view_adjustment_slip(id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT adjustment_id, adjustment_date
            FROM Adjustment_Slips
            WHERE adjustment_id = %s
        """, (id,))
        slip = cursor.fetchone()

        if not slip:
            flash('Không tìm thấy phiếu điều chỉnh này!', 'danger')
            return redirect(url_for('inventory.create_adjustment_page'))

        cursor.execute("""
            SELECT i.quantity_adjusted, i.unit_cost, i.reason,
                   m.material_name, m.base_unit
            FROM Adjustment_Slip_Items i
            JOIN Materials m ON i.material_id = m.material_id
            WHERE i.adjustment_id = %s
        """, (id,))
        items = cursor.fetchall()

        return render_template(ADJUSTMENT_DETAIL_HTML, slip=slip, items=items)
        
    except Exception as e:
        print(f"🔴 Lỗi xem phiếu điều chỉnh: {e}")
        flash(f"Lỗi hệ thống: {e}", "danger")
        return redirect(url_for('inventory.create_adjustment_page'))
    finally:
        cursor.close()
        conn.close()

@inventory_bp.route('/ajax/add_material', methods=['POST'])
@requires_permission('sale', 'inventory')
def ajax_add_material():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        material_name = request.form.get('material_name')
        base_unit = request.form.get('base_unit')
        import_unit = request.form.get('import_unit')
        factor = float(request.form.get('import_conversion_factor') or 1)
        
        sql = """
            INSERT INTO Materials (material_name, base_unit, import_unit, import_conversion_factor, is_active) 
            VALUES (%s, %s, %s, %s, TRUE) RETURNING material_id
        """
        cursor.execute(sql, (material_name, base_unit, import_unit, factor))
        new_id = cursor.fetchone()['material_id']
        conn.commit()
        
        return jsonify({
            'success': True, 
            'new_id': new_id, 
            'new_name': material_name,
            'new_import_unit': import_unit
        })
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi ajax_add_material: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()
