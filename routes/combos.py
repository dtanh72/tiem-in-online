from flask import Blueprint, render_template, request, redirect, url_for, flash
import json
from psycopg2.extras import RealDictCursor
from flask_login import current_user

from db import get_db_connection
from utils import log_system_action, requires_permission
from constants import COMBOS_HTML, MD_SALE

combos_bp = Blueprint('combos', __name__)

@combos_bp.route('/manage_combos')
@requires_permission('admin', 'sale')
def manage_combos():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM Combos ORDER BY combo_id DESC")
        combos = cur.fetchall()
        
        for c in combos:
            cur.execute("""
                SELECT ci.combo_item_id, ci.service_id, ci.quantity, s.service_name 
                FROM Combo_Items ci
                JOIN Services s ON ci.service_id = s.service_id
                WHERE ci.combo_id = %s
            """, (c['combo_id'],))
            c['items'] = cur.fetchall()
            
        cur.execute("SELECT * FROM Services WHERE is_active = TRUE ORDER BY service_name")
        services = cur.fetchall()
        
    finally:
        cur.close()
        conn.close()
        
    return render_template(COMBOS_HTML, combos_list=combos, services_list=services)

@combos_bp.route('/add_combo', methods=['POST'])
@requires_permission('admin', 'sale')
def add_combo():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        combo_name = request.form['combo_name']
        description = request.form.get('description', '')
        combo_price = float(request.form['combo_price'])
        
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')

        cur.execute("""
            INSERT INTO Combos (combo_name, description, combo_price, is_active)
            VALUES (%s, %s, %s, TRUE) RETURNING combo_id
        """, (combo_name, description, combo_price))
        combo_id = cur.fetchone()[0]
        
        for i in range(len(service_ids)):
            s_id = service_ids[i]
            qty = int(quantities[i])
            if s_id and qty > 0:
                cur.execute("""
                    INSERT INTO Combo_Items (combo_id, service_id, quantity)
                    VALUES (%s, %s, %s)
                """, (combo_id, s_id, qty))

        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_COMBO',
            target_module=MD_SALE,
            description=f"Thêm Combo mới: {combo_name}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Đã thêm Gói Combo thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi khi thêm Combo: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('combos.manage_combos'))

@combos_bp.route('/edit_combo/<int:combo_id>', methods=['POST'])
@requires_permission('admin', 'sale')
def edit_combo(combo_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        combo_name = request.form['combo_name']
        description = request.form.get('description', '')
        combo_price = float(request.form['combo_price'])
        
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')

        cur.execute("""
            UPDATE Combos 
            SET combo_name = %s, description = %s, combo_price = %s
            WHERE combo_id = %s
        """, (combo_name, description, combo_price, combo_id))

        # Clear old items and insert new
        cur.execute("DELETE FROM Combo_Items WHERE combo_id = %s", (combo_id,))
        for i in range(len(service_ids)):
            s_id = service_ids[i]
            qty = int(quantities[i])
            if s_id and qty > 0:
                cur.execute("""
                    INSERT INTO Combo_Items (combo_id, service_id, quantity)
                    VALUES (%s, %s, %s)
                """, (combo_id, s_id, qty))

        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='EDIT_COMBO',
            target_module=MD_SALE,
            description=f"Cập nhật Combo: {combo_name}",
            ip_address=request.remote_addr
        )

        conn.commit()
        flash('Đã cập nhật Combo thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi khi cập nhật Combo: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('combos.manage_combos'))

@combos_bp.route('/toggle_combo/<int:combo_id>', methods=['POST'])
@requires_permission('admin', 'sale')
def toggle_combo(combo_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE Combos SET is_active = NOT is_active WHERE combo_id = %s RETURNING combo_name, is_active", (combo_id,))
        res = cur.fetchone()
        if res:
            combo_name = res[0]
            status_text = "kích hoạt" if res[1] else "vô hiệu hóa"
            
            log_system_action(
                user_id=current_user.id,
                username=current_user.username,
                full_name=current_user.full_name,
                action_type='TOGGLE_COMBO',
                target_module=MD_SALE,
                description=f"{status_text.capitalize()} Combo: {combo_name}",
                ip_address=request.remote_addr
            )
            conn.commit()
            flash(f'Đã {status_text} Combo {combo_name}!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('combos.manage_combos'))
