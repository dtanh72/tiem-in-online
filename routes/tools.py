from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from db import get_db_connection
from psycopg2.extras import RealDictCursor
from utils import log_system_action, requires_permission
from constants import MD_SALE
import time
import csv
import os
import ipaddress
import json

tools_bp = Blueprint('tools', __name__, url_prefix='/tools')

@tools_bp.route('/calculators')
@login_required
def calculators_page():
    # Pass a default tools page entirely handled by JS.
    return render_template('tools/calculators.html')

@tools_bp.route('/public-scanner')
def public_scanner():
    conn = get_db_connection()
    equip_ips = []
    equip_map = {}
    if conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT ip_address, equipment_name FROM Equipment WHERE is_active=TRUE AND ip_address IS NOT NULL AND ip_address != ''")
                for row in cur.fetchall():
                    ip = row['ip_address'].strip()
                    equip_ips.append(ip)
                    equip_map[ip] = row['equipment_name']
        except Exception as e:
            print("Err load IPs:", e)
        finally:
            conn.close()
    
    default_ips = ", ".join(equip_ips) if equip_ips else "192.168.1.1-20"
    return render_template('tools/scanner.html', default_ips=default_ips, equip_map_json=json.dumps(equip_map))

@tools_bp.route('/api/parse-ips', methods=['POST'])
def api_parse_ips():
    ip_list_str = request.form.get('ip_list', '')
    ips = set()
    for item in ip_list_str.split(','):
        item = item.strip()
        if not item: continue
        if '-' in item:
            parts = item.split('-')
            if len(parts) == 2:
                start_ip, end_ip = parts[0].strip(), parts[1].strip()
                try:
                    if '.' not in end_ip:
                        start_ip_obj = ipaddress.IPv4Address(start_ip)
                        prefix = start_ip.rsplit('.', 1)[0]
                        end_ip = f"{prefix}.{end_ip}"
                    start = int(ipaddress.IPv4Address(start_ip))
                    end = int(ipaddress.IPv4Address(end_ip))
                    if start <= end:
                        for ip_int in range(start, end + 1):
                            ips.add(str(ipaddress.IPv4Address(ip_int)))
                except: pass
        else:
            try:
                ips.add(str(ipaddress.IPv4Address(item)))
            except: pass
    
    # Sort them nicely
    sorted_ips = sorted(list(ips), key=lambda ip: int(ipaddress.IPv4Address(ip)))
    return jsonify({'success': True, 'ips': sorted_ips})

@tools_bp.route('/api/sync_counters', methods=['POST'])
@login_required
@requires_permission('tech', 'inventory', 'accounting', 'sale')
def api_sync_counters():
    """ 
    API Này nhận kết quả mảng đã quét thành công từ Local Agent (truyền qua Javascript).
    Dữ liệu yêu cầu: {"results": [{"ip": "...", "counter": 1234, "status": "OK", "name": "..."}]}
    """
    results_str = request.form.get('results')
    if not results_str:
        return jsonify({'success': False, 'error': 'Missing results data'})
    
    try:
        results = json.loads(results_str)
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'Invalid JSON format for results'})

    # Cập nhật số counter vào Database Equipment
    db_updated_count = 0
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            for r in results:
                if r['status'] == 'OK' and r['counter'] is not None and r['counter'] > 0:
                    cur.execute("UPDATE Equipment SET print_count = %s WHERE ip_address = %s", (r['counter'], r['ip']))
                    if cur.rowcount > 0:
                        db_updated_count += cur.rowcount
                        log_system_action(
                            user_id=1,  # System default if caller holds no session or just run by script
                            username='system',
                            full_name='System Auto Scanner',
                            action_type='UPD_EQUIPMENT_COUNTER',
                            target_module=MD_SALE, # Or "EQUIPMENT"
                            description=f"Auto đồng bộ Counter máy {r['name']}({r['ip']}) = {r['counter']}",
                            ip_address='127.0.0.1'
                        )
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print(f"Err update DB: {e}")

    return jsonify({'success': True, 'results': results, 'db_updated_count': db_updated_count})

@tools_bp.route('/manage-quick-actions')
@login_required
def manage_quick_actions():
    if current_user.role_id != 1:
        flash("Bạn không có quyền quản lý Nút Thao Tác Nhanh!", "danger")
        return redirect(url_for('dashboard.dashboard_page'))
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM quick_actions ORDER BY slot_index ASC")
    quick_actions = cur.fetchall()
    
    cur.execute("SELECT service_id, service_name, base_price FROM services WHERE is_active = TRUE ORDER BY service_name ASC")
    services = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('tools/manage_quick_actions.html', quick_actions=quick_actions, services=services)

@tools_bp.route('/update-quick-actions', methods=['POST'])
@login_required
def update_quick_actions():
    if current_user.role_id != 1:
        return "Access denied", 403
        
    slot_indices = request.form.getlist('slot_indices[]')
    labels = request.form.getlist('labels[]')
    service_ids = request.form.getlist('service_ids[]')
    colors = request.form.getlist('colors[]')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for i in range(len(slot_indices)):
            slot = int(slot_indices[i])
            label = labels[i]
            sid = service_ids[i] if service_ids[i] else None
            color = colors[i]
            
            cur.execute("""
                UPDATE quick_actions 
                SET service_id = %s, button_label = %s, bg_color = %s
                WHERE slot_index = %s
            """, (sid, label, color, slot))
            
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='UPD_QUICK_ACTIONS',
            target_module=MD_SALE,
            description="Cập nhật 10 nút thao tác nhanh",
            ip_address=request.remote_addr
        )
        conn.commit()
        flash("Đã lưu cấu hình 10 nút thao tác nhanh!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Lỗi lưu: {e}", "danger")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('tools.manage_quick_actions'))

@tools_bp.route('/quick-pos')
@login_required
def quick_pos():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM quick_actions ORDER BY slot_index ASC")
    quick_actions = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('tools/quick_pos.html', quick_actions=quick_actions)

@tools_bp.route('/execute-quick-pos', methods=['POST'])
@login_required
def execute_quick_pos():
    service_id = request.form.get('service_id')
    if not service_id:
        flash("Lỗi không tìm thấy Dịch vụ được gán vào nút này!", "danger")
        return redirect(url_for('tools.quick_pos'))
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Lấy giá của service
        cur.execute("SELECT service_name, base_price FROM services WHERE service_id = %s", (service_id,))
        sv = cur.fetchone()
        if not sv:
            flash("Dịch vụ không tồn tại!", "danger")
            return redirect(url_for('tools.quick_pos'))
            
        # Tìm hoặc tạo khách vãng lai
        cur.execute("SELECT customer_id FROM customers WHERE customer_name ILIKE '%khách lẻ%' OR customer_id = 1 LIMIT 1")
        cust = cur.fetchone()
        if cust:
            customer_id = cust['customer_id']
        else:
            cur.execute("INSERT INTO customers (customer_name, phone, is_active) VALUES ('Khách lẻ', '', TRUE) RETURNING customer_id")
            customer_id = cur.fetchone()['customer_id']
            
        # Tạo Order đã hoàn thành
        price = sv['base_price']
        cur.execute("""
            INSERT INTO orders (customer_id, order_date, total_amount, subtotal, status, payment_status, payment_method, delivery_status)
            VALUES (%s, CURRENT_TIMESTAMP, %s, %s, 'completed', 'paid', 'cash', 'delivered')
            RETURNING order_id
        """, (customer_id, price, price))
        new_order_id = cur.fetchone()['order_id']
        
        # Thêm order_items
        cur.execute("""
            INSERT INTO order_items (order_id, service_id, quantity, unit_price, line_total)
            VALUES (%s, %s, 1, %s, %s)
        """, (new_order_id, service_id, price, price))
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='QUICK_POS_ORDER',
            target_module=MD_SALE,
            description=f"Quick POS thu tiền nhanh mã #{new_order_id} - Dịch vụ: {sv['service_name']}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
        flash(f"Đã tạo nhanh đơn hàng #{new_order_id} ({sv['service_name']}) thành công!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Lỗi tạo đơn: {e}", "danger")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('tools.quick_pos'))

