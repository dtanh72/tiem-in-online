from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
import datetime
import math
import io
import csv
from psycopg2.extras import RealDictCursor

from db import get_db_connection, get_mongo_collection
from utils import log_system_action, requires_permission
from constants import SYSTEM_LOG_HTML

system_bp = Blueprint('system', __name__)

@system_bp.route('/system_logs')
@requires_permission('all')
def system_logs_page():
    try:
        logs_col = get_mongo_collection()
    except Exception as e:
        return f"Lỗi kết nối MongoDB: {e}", 500
        
    page = request.args.get('page', 1, type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    action = request.args.get('action')
    
    items_per_page = 50
    offset = (page - 1) * items_per_page
    
    query = {}
    
    if start_date or end_date:
        query['created_at'] = {}
        if start_date:
            dt_start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            query['created_at']['$gte'] = dt_start
        if end_date:
            dt_end = datetime.datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query['created_at']['$lte'] = dt_end

    if action == 'export':
        all_logs = list(logs_col.find(query).sort("created_at", -1))
        
        si = io.StringIO()
        cw = csv.writer(si)
        si.write('\ufeff')
        cw.writerow(['Thời gian', 'User', 'Họ tên', 'Hành động', 'Module', 'Chi tiết', 'IP'])
        
        for log in all_logs:
            created_str = log.get('created_at').strftime('%Y-%m-%d %H:%M:%S') if log.get('created_at') else ''
            
            cw.writerow([
                created_str, 
                log.get('username', ''), 
                log.get('full_name', ''), 
                log.get('action_type', ''), 
                log.get('target_module', ''), 
                log.get('description', ''), 
                log.get('ip_address', '')
            ])
            
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=system_logs.csv"
        output.headers["Content-type"] = "text/csv"
        return output
    
    total_records = logs_col.count_documents(query)
    total_pages = math.ceil(total_records / items_per_page) if total_records > 0 else 1
    
    logs_list = list(
        logs_col.find(query)
        .sort("created_at", -1)
        .skip(offset)
        .limit(items_per_page)
    )
    
    return render_template(SYSTEM_LOG_HTML, 
                           logs_list=logs_list,
                           current_page=page,
                           total_pages=total_pages,
                           start_date=start_date,
                           end_date=end_date,
                           total_records=total_records)

@system_bp.route('/clear_system_logs', methods=['POST'])
@requires_permission('all')
def clear_system_logs():
    try:
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not start_date or not end_date:
            return "Vui lòng chọn khoảng thời gian để xóa log!", 400
            
        dt_start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        dt_end = datetime.datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        
        logs_col = get_mongo_collection()
        
        query = {
            "created_at": {
                "$gte": dt_start,
                "$lte": dt_end
            }
        }
        
        result = logs_col.delete_many(query)
        rows_deleted = result.deleted_count
        
        if rows_deleted > 0:
            description = f"Đã XÓA VĨNH VIỄN {rows_deleted} dòng nhật ký từ ngày {start_date} đến {end_date}"
            
            log_system_action(
                user_id=current_user.id,
                username=current_user.username,
                full_name=current_user.full_name,
                action_type='DELETE',
                target_module='System_Logs',
                description=description,
                ip_address=request.remote_addr
            )
            
    except Exception as err:
        print(f"🔴 Lỗi khi xóa log trong MongoDB: {err}")
        return f"Lỗi hệ thống: {err}", 500
    
    return redirect(url_for('system.system_logs_page'))

@system_bp.route('/operating_expenses', methods=['GET', 'POST'])
@requires_permission('all')
def operating_expenses_page():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if request.method == 'POST':
            expense_date = request.form.get('expense_date')
            expense_type = request.form.get('expense_type')
            amount = float(request.form.get('amount', 0))
            description = request.form.get('description', '')
            
            cursor.execute("""
                INSERT INTO operating_expenses (expense_date, expense_type, amount, description)
                VALUES (%s, %s, %s, %s)
            """, (expense_date, expense_type, amount, description))
            conn.commit()
            flash('Đã ghi nhận chi phí thành công!', 'success')
            return redirect(url_for('system.operating_expenses_page'))

        cursor.execute("""
            SELECT * FROM operating_expenses 
            ORDER BY expense_date DESC, expense_id DESC
            LIMIT 100
        """)
        expenses_list = cursor.fetchall()

        return render_template('operating_expenses.html', expenses_list=expenses_list)
        
    except Exception as e:
        print(f"🔴 Lỗi chi phí vận hành: {e}")
        flash(f'Lỗi hệ thống: {e}', 'danger')
        return redirect(url_for('dashboard.dashboard_page'))
    finally:
        cursor.close()
        conn.close()
