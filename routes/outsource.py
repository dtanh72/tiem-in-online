from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from utils import requires_permission, log_system_action
from constants import MANAGE_OUTSOURCE_HTML, MD_SALE

outsource_bp = Blueprint('outsource', __name__)

@outsource_bp.route('/manage_outsource')
@requires_permission('sale', 'accounting', 'inventory')
def manage_outsource():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM Outsource_Partners ORDER BY partner_name")
    partners = cur.fetchall()
    
    cur.execute("""
        SELECT C.category_id, C.partner_id, C.category_name, C.type, C.unit,
               P.price_id, P.item_name, P.min_qty, P.max_qty, P.unit_price
        FROM Outsource_Categories C
        LEFT JOIN Outsource_Prices P ON C.category_id = P.category_id
        ORDER BY C.category_name, P.min_qty ASC
    """)
    all_items = cur.fetchall()
    
    grouped_data = {}
    for item in all_items:
        pid = item['partner_id']
        if pid not in grouped_data:
            grouped_data[pid] = []
        grouped_data[pid].append(item)
        
    cur.close()
    conn.close()
    
    return render_template(MANAGE_OUTSOURCE_HTML, 
                           partners=partners, 
                           grouped_data=grouped_data)

@outsource_bp.route('/add_outsource_category', methods=['POST'])
@requires_permission('admin', 'inventory')
def add_outsource_category():
    partner_id = request.form['partner_id']
    name = request.form['category_name']
    cat_type = request.form['type']
    unit = request.form['unit']
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO Outsource_Categories (partner_id, category_name, type, unit) 
            VALUES (%s, %s, %s, %s)
        """, (partner_id, name, cat_type, unit))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_OUTSOURCE_CAT',
            target_module=MD_SALE,
            description=f"Thêm hạng mục gia công: {name}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Thêm Hạng mục gia công thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('outsource.manage_outsource'))

@outsource_bp.route('/add_outsource_partner', methods=['POST'])
@requires_permission('admin', 'inventory')
def add_outsource_partner():
    name = request.form['partner_name']
    phone = request.form.get('phone', '')
    address = request.form.get('address', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO Outsource_Partners (partner_name, phone, address) VALUES (%s, %s, %s)", (name, phone, address))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_OUTSOURCE_PARTNER',
            target_module=MD_SALE,
            description=f"Thêm đối tác gia công: {name}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Thêm Đối tác gia công thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('outsource.manage_outsource'))

@outsource_bp.route('/add_outsource_price', methods=['POST'])
@requires_permission('admin', 'inventory')
def add_outsource_price():
    category_id = request.form['category_id']
    item_name = request.form['item_name']
    min_qty = request.form.get('min_qty', 1)
    max_qty = request.form.get('max_qty') or 999999
    unit_price = request.form['unit_price']
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO Outsource_Prices (category_id, item_name, min_qty, max_qty, unit_price) 
            VALUES (%s, %s, %s, %s, %s)
        """, (category_id, item_name, min_qty, max_qty, unit_price))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_OUTSOURCE_PRICE',
            target_module=MD_SALE,
            description=f"Thêm mốc giá gia công: {item_name}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Thêm Mốc giá Gia công thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('outsource.manage_outsource'))

@outsource_bp.route('/edit_outsource_category', methods=['POST'])
@requires_permission('admin', 'inventory')
def edit_outsource_category():
    category_id = request.form['category_id']
    name = request.form['category_name']
    cat_type = request.form['type']
    unit = request.form['unit']
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE Outsource_Categories 
            SET category_name = %s, type = %s, unit = %s
            WHERE category_id = %s
        """, (name, cat_type, unit, category_id))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='EDIT_OUTSOURCE_CAT',
            target_module=MD_SALE,
            description=f"Cập nhật danh mục gia công ID #{category_id}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Cập nhật Danh mục gia công thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('outsource.manage_outsource'))

@outsource_bp.route('/edit_outsource_price', methods=['POST'])
@requires_permission('admin', 'inventory')
def edit_outsource_price():
    price_id = request.form['price_id']
    item_name = request.form['item_name']
    min_qty = request.form.get('min_qty', 1)
    max_qty = request.form.get('max_qty') or 999999
    unit_price = request.form['unit_price']
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # PostgreSQL DO UPDATE requires unique constraint, so we just do unconditional UPDATE directly on price_id
        cur.execute("""
            UPDATE Outsource_Prices 
            SET item_name = %s, min_qty = %s, max_qty = %s, unit_price = %s
            WHERE price_id = %s
        """, (item_name, min_qty, max_qty, unit_price, price_id))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='EDIT_OUTSOURCE_PRICE',
            target_module=MD_SALE,
            description=f"Cập nhật mốc giá gia công ID #{price_id}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Cập nhật Mốc giá thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('outsource.manage_outsource'))

@outsource_bp.route('/api/get_partner_prices/<int:partner_id>')
@login_required
def api_get_partner_prices(partner_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        sql = """
            SELECT C.category_name, P.item_name, P.min_qty, P.max_qty, P.unit_price
            FROM Outsource_Categories C
            JOIN Outsource_Prices P ON C.category_id = P.category_id
            WHERE C.partner_id = %s
            ORDER BY C.category_name, P.min_qty ASC
        """
        cur.execute(sql, (partner_id,))
        prices = cur.fetchall()
        return jsonify({'status': 'success', 'data': prices})
    except Exception as e:
        print(f"Lỗi tải giá đối tác: {e}")
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cur.close()
        conn.close()
