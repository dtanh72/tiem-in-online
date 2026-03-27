from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor

from db import get_db_connection, ADMIN_DEF, ADMIN_PAS_DEF
from models import User
from utils import log_system_action, requires_permission
from constants import LOGIN_HTML, MANAGE_USERS_HTML, MD_AUTH, MD_HR
from extensions import limiter

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/setup_admin')
def setup_admin():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO Roles (role_id, role_name, permissions) VALUES (1, 'Admin', 'all') ON CONFLICT DO NOTHING")
        hashed_pw = generate_password_hash(ADMIN_PAS_DEF)
        cur.execute("INSERT INTO Users (username, password_hash, full_name, role_id) VALUES (%s, %s, 'Super Admin', 1)", (ADMIN_DEF, hashed_pw))
        conn.commit()
        return "Tạo Admin thành công!"
    except Exception as e:
        conn.rollback()
        return f"Lỗi: {e}"
    finally:
        conn.close()

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cur.execute("SELECT * FROM Users WHERE username = %s", (username,))
            user = cur.fetchone()
            conn.close()
            
            if user and check_password_hash(user['password_hash'], password):
                user_obj = User(user['user_id'], user['username'], user['full_name'], user['role_id'])
                login_user(user_obj)
                
                log_system_action(
                    user_id=user['user_id'],
                    username=user['username'],
                    full_name=user.get('full_name', ''),
                    action_type='LOGIN',
                    target_module=MD_AUTH,
                    description='Đăng nhập hệ thống thành công',
                    ip_address=request.remote_addr
                )
                
                return redirect(url_for('dashboard.dashboard_page'))
            else:
                flash('Sai tài khoản hoặc mật khẩu!', 'danger')
        except Exception as e:
            print(f"🔴 Lỗi hệ thống: {e}")
            return f"Lỗi hệ thống: {e}", 500
            
    return render_template(LOGIN_HTML)

@auth_bp.route('/logout')
@login_required
def logout():
    log_system_action(
        user_id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        action_type='LOGOUT',
        target_module=MD_AUTH,
        description='Đăng xuất khỏi hệ thống',
        ip_address=request.remote_addr
    )
    logout_user()
    flash('Bạn đã đăng xuất thành công.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/manage_users')
@requires_permission('all', 'HR') 
def manage_users_page():
    if not current_user.can('admin_users'): return "Bạn không có quyền truy cập!", 403
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT U.*, R.role_name FROM Users U JOIN Roles R ON U.role_id = R.role_id")
    users = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Roles")
    roles = cursor.fetchall()
    
    conn.close()
    return render_template(MANAGE_USERS_HTML, users=users, roles=roles)

@auth_bp.route('/add_user', methods=['POST'])
@requires_permission('all', 'HR') 
def add_user():
    if not current_user.can('admin_users'): return "Access Denied", 403
    
    username = request.form['username']
    password = request.form['password']
    full_name = request.form['full_name']
    role_id = request.form['role_id']
    
    hashed_pw = generate_password_hash(password)
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        sql = """
            INSERT INTO Users (username, password_hash, full_name, role_id) 
            VALUES (%s, %s, %s, %s) RETURNING user_id
        """
        cursor.execute(sql, (username, hashed_pw, full_name, role_id))
        new_id = cursor.fetchone()['user_id']
        
        log_system_action(
            user_id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            action_type='ADD_USER',
            target_module=MD_HR,
            description=f"Tạo Username #{username}",
            ip_address=request.remote_addr
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi thêm User: {e}")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('auth.manage_users_page'))
