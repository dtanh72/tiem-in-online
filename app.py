import os
import datetime  # <--- BỔ SUNG DÒNG NÀY
import math      # <--- Bổ sung luôn để dùng cho phân trang sau này
import csv
import io
import json # Đảm bảo đã import thư viện này ở đầu file app.py
from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv # Nhớ pip install python-dotenv
load_dotenv() # Nó sẽ tự đọc file .env

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mac_dinh_neu_khong_co_key') # Key bảo mật

from functools import wraps

@app.template_filter('currency')
def currency_filter(value):
    try:
        if value is None: return "0"
        return "{:,.0f}".format(value)
    except:
        return value

# --- CẤU HÌNH DATABASE ---

# Cách 1: Lấy từ biến môi trường (Khi chạy trên vercel)
DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_DEF = os.environ.get('ADMIN_DEF')
ADMIN_PAS_DEF = os.environ.get('ADMIN_PAS_DEF')

# Cách 2: Nếu đang chạy Local (trên máy tính) mà không tìm thấy biến môi trường
# Thì dùng chuỗi kết nối trực tiếp (nhưng KHÔNG ĐƯỢC để lộ khi push lên Git)
if not DATABASE_URL:
    # Bạn có thể dùng thư viện python-dotenv để load từ file .env (an toàn)
    # Hoặc nếu lười, hãy để dòng này, NHƯNG nhớ là Render sẽ dùng dòng trên.
    # Khi push lên Git, hãy đảm bảo bạn không để lộ pass thật ở đây, 
    # hoặc dùng file .env như hướng dẫn dưới.
    pass 

def get_db_connection():
    try:
        # Nếu có DATABASE_URL (Trên Render) thì dùng nó
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        else:
            # Nếu chạy local, bạn hãy tạo file .env để chứa link này
            # Hoặc tạm thời dán link vào đây để test, NHƯNG KHI PUSH GIT PHẢI XÓA ĐI
            print("Chưa cấu hình DATABASE_URL!")
            return None
    except Exception as e:
        print(f"Lỗi kết nối: {e}")
        return None

# KHAI BÁO LINK FILE
DASHBOARD_HTML = "dashboard.html"
SERVICES_HTML = "HHDV/services.html"
EDIT_SERVICE_HTML = "HHDV/edit_service.html"
CUSTOMERS_HTML = "HHKH/customers.html"
EDIT_CUSTOMER_HTML = "HHKH/edit_customer.html"
CUSTOMER_DEBT_REPORT_HTML = "HHKH/customer_debt_report.html"
CUSTOMER_DEBT_DETAIL_HTML = "HHKH/customer_debt_detail.html"
MATERIALS_HTML = "HHVT/materials.html" 
EDIT_MATERIAL_HTML = "HHVT/edit_material.html"
SERVICE_MATERIALS_HTML = "service_materials.html"
TAO_DH_HTML = "HHDH/create_order.html"
LS_DH_HTML = "HHDH/orders_history.html"
CT_DH_HTML = "HHDH/order_detail.html"
TAO_BG_HTML = "HHBG/create_quote.html"
LS_BG_HTML = "HHBG/quotes_history.html"
CT_BG_HTML = "HHBG/quote_detail.html"
EDIT_QUOTE_HTML = "HHBG/edit_quote.html"
TB_HTML = "HHTB/equipment.html"
CT_TB_HTML = "HHTB/equipment_detail.html"
SUPPLIER_DEBT_REPORT = "HHCC/supplier_debt_report.html"
NCC_HTML="HHCC/suppliers.html"
CREATE_IMPORT_HTML = "HHKO/create_import.html"
CREATE_ADJUSTMENT_INV_HTML = "HHKO/create_adjustment.html"
COUPONS_HTML = "HHKM/coupons.html"
LOGIN_HTML = "HHBM/login.html"
MANAGE_USERS_HTML = "HHBM/manage_users.html"
SYSTEM_LOG_HTML = "HHBM/system_logs.html"
OUTSOURCE_CALCULATOR_HTML="HHGC/outsource_calculator.html"
MANAGE_OUTSOURCE_HTML="HHGC/manage_outsource.html"

#def get_db_connection():
#    try:
#        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
#        return conn
#    except Exception as e:
#        print(f"Lỗi kết nối: {e}")
#        return None
#
# --- CẤU HÌNH LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, full_name, role_id):
        self.id = id
        self.username = username
        self.full_name = full_name
        self.role_id = role_id
        
    def can(self, perm):
        return True # Tạm thời cho full quyền để test

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Users WHERE user_id = %s", (user_id,))
    u = cur.fetchone()
    conn.close()
    if u:
        return User(u['user_id'], u['username'], u['full_name'], u['role_id'])
    return None

# --- ROUTE CỨU HỘ: TẠO ADMIN ---
@app.route('/setup_admin')
def setup_admin():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. Tạo Role
        cur.execute("INSERT INTO Roles (role_id, role_name, permissions) VALUES (1, 'Admin', 'all') ON CONFLICT DO NOTHING")
        # 2. Tạo User
        hashed_pw = generate_password_hash(ADMIN_PAS_DEF)
        cur.execute("INSERT INTO Users (username, password_hash, full_name, role_id) VALUES (%s, %s, 'Super Admin', 1)", ADMIN_DEF, (hashed_pw,))
        conn.commit()
        return "Tạo Admin thành công!"
    except Exception as e:
        conn.rollback()
        return f"Lỗi: {e}"
    finally:
        conn.close()

# --- ROUTE CHÍNH ---
@app.route('/login', methods=['GET', 'POST'])
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
                login_user(user_obj) #luu session
                
                # 🟢 1. GỌI LỆNH GHI LOG ĐĂNG NHẬP Ở ĐÂY
                log_system_action(
                    user_id=user['user_id'],
                    username=user['username'],
                    full_name=user.get('full_name', ''), # Dùng .get() cho an toàn
                    action_type='LOGIN',
                    target_module='Authentication',
                    description='Đăng nhập hệ thống thành công',
                    ip_address=request.remote_addr # Lấy IP của người dùng
                )
                
                return redirect(url_for('dashboard_page'))
            else:
                flash('Sai tài khoản hoặc mật khẩu!', 'danger')
        except Exception as e:
            print(f"🔴 Lỗi hệ thống: {e}")
            return f"Lỗi hệ thống: {e}", 500
            
    return render_template(LOGIN_HTML) # Đảm bảo bạn có file login.html

# --- HÀM PHÂN QUYỀN (DECORATOR) ---
def requires_permission(*allowed_permissions):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Chưa đăng nhập -> Đá về trang login
            if not current_user.is_authenticated:
                return redirect(url_for('login'))

            # 2. Lấy Role ID của user hiện tại (Giả sử bạn đã lưu role_id trong session hoặc User object)
            # Theo SQL của bạn: 1=Admin, 2=Kho, 3=Sale, 4=Kế toán, 5=Nhân sự
            user_role = current_user.role_id 
            
            # 3. Admin (ID 1) luôn có quyền "all"
            if user_role == 1:
                return f(*args, **kwargs)

            # 4. Định nghĩa bảng map quyền (Khớp với logic code cũ)
            # Bạn có thể sửa các số ID này cho khớp với bảng 'roles' trong DB của bạn
            permission_map = {
                'inventory': [2],       # Thủ kho
                'sale': [3],            # Kinh doanh
                'accounting': [4],      # Kế toán
                'asset': [2, 4],        # Quản lý tài sản (Kho + Kế toán)
                'HR': [5],              # Nhân sự
                'all': [1]              # Chỉ Admin
            }

            # 5. Kiểm tra quyền
            has_permission = False
            for perm in allowed_permissions:
                # Nếu user có role nằm trong danh sách được phép của quyền đó
                if perm in permission_map and user_role in permission_map[perm]:
                    has_permission = True
                    break
            
            if not has_permission:
                flash('Bạn không có quyền truy cập trang này!', 'danger')
                return redirect(url_for('dashboard_page')) # Hoặc trang chủ

            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/logout')
@login_required
def logout():
    
    # 🟢 2. GỌI LỆNH GHI LOG ĐĂNG XUẤT TRƯỚC KHI XÓA SESSION
    log_system_action(
        user_id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        action_type='LOGOUT',
        target_module='Authentication',
        description='Đăng xuất khỏi hệ thống',
        ip_address=request.remote_addr
    )
    
    # Xóa thẻ phiên làm việc (Session)
    logout_user()
    
    flash('Bạn đã đăng xuất thành công.', 'info')
    return redirect(url_for('login'))

# ======================================================
# HÀM KẾT NỐI MONGODB
# ======================================================
def get_mongo_collection():
    # Lấy URI từ biến môi trường
    mongo_uri = os.environ.get('MONGO_URL')
    if not mongo_uri:
        raise Exception("Chưa cấu hình MONGO_URL")
    
    # Kết nối tới MongoDB
    client = MongoClient(mongo_uri)
    
    # Tạo/Chọn Database tên là 'app_database'
    db = client['app_database']
    
    # Tạo/Chọn Collection (Bảng) tên là 'system_logs'
    collection = db['system_logs']
    
    return collection

# ======================================================
# QUẢN LÝ SYSTEM LOGS (MONGODB)
# ======================================================
@app.route('/system_logs')
@requires_permission('all') # Chỉ Admin được xem
def system_logs_page():
    try:
        logs_col = get_mongo_collection()
    except Exception as e:
        return f"Lỗi kết nối MongoDB: {e}", 500
        
    # 1. Lấy tham số từ URL
    page = request.args.get('page', 1, type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    action = request.args.get('action')
    
    items_per_page = 50
    offset = (page - 1) * items_per_page
    
    # 2. Xây dựng bộ lọc (Query) cho MongoDB
    query = {}
    
    # Xử lý lọc theo ngày tháng
    if start_date or end_date:
        query['created_at'] = {}
        if start_date:
            # Chuyển chuỗi 'YYYY-MM-DD' thành đối tượng datetime
            dt_start = datetime.strptime(start_date, '%Y-%m-%d')
            query['created_at']['$gte'] = dt_start # $gte: Greater than or equal
        if end_date:
            # Cuối ngày của end_date
            dt_end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query['created_at']['$lte'] = dt_end # $lte: Less than or equal

    # --- TRƯỜNG HỢP 1: XUẤT CSV ---
    if action == 'export':
        # Tìm tất cả, sắp xếp created_at giảm dần (-1)
        all_logs = list(logs_col.find(query).sort("created_at", -1))
        
        si = io.StringIO()
        cw = csv.writer(si)
        si.write('\ufeff') # BOM cho Excel tiếng Việt
        cw.writerow(['Thời gian', 'User', 'Họ tên', 'Hành động', 'Module', 'Chi tiết', 'IP'])
        
        for log in all_logs:
            # Format lại datetime ra chuỗi để in vào CSV
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

    # --- TRƯỜNG HỢP 2: XEM TRÊN WEB ---
    
    # Đếm tổng số bản ghi
    total_records = logs_col.count_documents(query)
    total_pages = math.ceil(total_records / items_per_page) if total_records > 0 else 1
    
    # Lấy dữ liệu phân trang (dùng skip và limit)
    logs_list = list(
        logs_col.find(query)
        .sort("created_at", -1)
        .skip(offset)
        .limit(items_per_page)
    )
    
    return render_template(SYSTEM_LOG_HTML, # Đảm bảo tên HTML đúng
                           logs_list=logs_list,
                           current_page=page,
                           total_pages=total_pages,
                           start_date=start_date,
                           end_date=end_date,
                           total_records=total_records)

#ham ghi log
def log_system_action(user_id, username, full_name, action_type, target_module, description, ip_address):
    try:
        logs_col = get_mongo_collection()
        log_document = {
            "user_id": user_id,
            "username": username,       # Lưu thẳng tên vào đây
            "full_name": full_name,     # Lưu thẳng họ tên vào đây
            "action_type": action_type,
            "target_module": target_module,
            "description": description,
            "ip_address": ip_address,
            "created_at": datetime.datetime.now() # MongoDB rất thích kiểu đối tượng Datetime
        }
        logs_col.insert_one(log_document) # Lệnh này sẽ tạo ra bảng nếu bảng chưa tồn tại!
    except Exception as e:
        print(f"Lỗi không ghi được Log vào Mongo: {e}")

@app.route('/clear_system_logs', methods=['POST'])
@requires_permission('all')
def clear_system_logs():
    try:
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        # Kiểm tra dữ liệu đầu vào
        if not start_date or not end_date:
            return "Vui lòng chọn khoảng thời gian để xóa log!", 400
            
        # Chuyển đổi chuỗi ngày tháng (YYYY-MM-DD) sang datetime cho MongoDB
        dt_start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        # Ép thời gian của ngày kết thúc thành 23:59:59 để bao trọn ngày hôm đó
        dt_end = datetime.datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        
        # Gọi hàm lấy Collection từ MongoDB (Hàm ta đã viết ở bước trước)
        logs_col = get_mongo_collection()
        
        # --- BƯỚC 1: XÓA LOG CŨ ---
        # Query xóa của Mongo: tìm các document có created_at nằm trong khoảng thời gian
        query = {
            "created_at": {
                "$gte": dt_start,
                "$lte": dt_end
            }
        }
        
        # Thực hiện xóa hàng loạt
        result = logs_col.delete_many(query)
        rows_deleted = result.deleted_count
        
        # --- BƯỚC 2: GHI LOG VỀ HÀNH ĐỘNG XÓA (QUAN TRỌNG) ---
        if rows_deleted > 0:
            description = f"Đã XÓA VĨNH VIỄN {rows_deleted} dòng nhật ký từ ngày {start_date} đến {end_date}"
            
            # Gọi hàm log_system_action (phiên bản MongoDB mới)
            # Truyền trực tiếp thông tin user vào, không cần cursor nữa
            log_system_action(
                user_id=current_user.id,
                username=current_user.username,
                full_name=current_user.full_name,
                action_type='DELETE',
                target_module='System_Logs',
                description=description,
                ip_address=request.remote_addr
            )
            
    # Xử lý Exception chuẩn của Python thay vì mysql.connector.Error
    except Exception as err:
        print(f"🔴 Lỗi khi xóa log trong MongoDB: {err}")
        return f"Lỗi hệ thống: {err}", 500
    
    # Quay lại trang log
    return redirect(url_for('system_logs_page'))

# --- DASHBOARD CHÍNH THỨC ---
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard_page():
    conn = get_db_connection()
    if not conn: return "Lỗi kết nối DB"
    
    cur = conn.cursor()
    today = datetime.date.today()
    
    # 1. Thống kê Doanh thu hôm nay
    cur.execute("SELECT SUM(total_amount) as total FROM Orders WHERE date(order_date) = %s AND status != 'cancelled'", (today,))
    res_rev = cur.fetchone()
    revenue_today = res_rev['total'] if res_rev and res_rev['total'] else 0

    # 2. Đếm số đơn hôm nay
    cur.execute("SELECT COUNT(*) as count FROM Orders WHERE date(order_date) = %s", (today,))
    res_ord = cur.fetchone()
    orders_today = res_ord['count'] if res_ord else 0

    # 3. Tổng công nợ khách hàng
    cur.execute("SELECT SUM(total_amount - amount_paid) as total FROM Orders WHERE payment_status != 'paid' AND status != 'cancelled'")
    res_due = cur.fetchone()
    total_due_customer = res_due['total'] if res_due and res_due['total'] else 0

    conn.close()

    # Trả về giao diện Dashboard thật
    # Các biến khác chưa có tính năng (nhập kho, bảo trì...) ta truyền tạm số 0
    return render_template(DASHBOARD_HTML,
                           revenue_today=revenue_today,
                           orders_today=orders_today,
                           total_due_customer=total_due_customer,
                           revenue_cancelled_today=0, # Tạm thời
                           due_imports=0,
                           due_maintenance=0,
                           low_stock_count=0,
                           top_services=[],
                           monthly_revenue=[],
                           monthly_labels=[])

# ======================================================
# QUẢN LÝ NGƯỜI DÙNG (USERS) - CRUD
# ======================================================
@app.route('/manage_users')
@requires_permission('all', 'hr') 
def manage_users_page():
    if not current_user.can('admin_users'): return "Bạn không có quyền truy cập!", 403
    
    conn = get_db_connection()
    # POSTGRES: Ép kiểu trả về Dictionary
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT U.*, R.role_name FROM Users U JOIN Roles R ON U.role_id = R.role_id")
    users = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Roles")
    roles = cursor.fetchall()
    
    conn.close()
    return render_template(MANAGE_USERS_HTML, users=users, roles=roles)

@app.route('/add_user', methods=['POST'])
@requires_permission('all', 'hr') 
def add_user():
    if not current_user.can('admin_users'): return "Access Denied", 403
    
    username = request.form['username']
    password = request.form['password']
    full_name = request.form['full_name']
    role_id = request.form['role_id']
    
    hashed_pw = generate_password_hash(password)
    
    conn = get_db_connection()
    # Dùng RealDictCursor để dễ lấy ID trả về
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # POSTGRES: Thêm RETURNING user_id thay cho lastrowid
        sql = """
            INSERT INTO Users (username, password_hash, full_name, role_id) 
            VALUES (%s, %s, %s, %s) RETURNING user_id
        """
        cursor.execute(sql, (username, hashed_pw, full_name, role_id))
        
        # Lấy ID vừa tạo
        new_id = cursor.fetchone()['user_id']
        
        log_desc = f"Tạo User ID #{new_id}"
        # log_system_action(cursor, 'CREATE', 'Users', log_desc) # Mở comment nếu đã có hàm
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"🔴 Lỗi thêm User: {e}")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('manage_users_page'))

# ======================================================
# QUẢN LÝ DỊCH VỤ (SERVICES) - CRUD (POSTGRESQL)
# ======================================================

# 1. Route để HIỂN THỊ danh sách dịch vụ VÀ form thêm mới
@app.route('/services')
@requires_permission('sale', 'inventory')
def services_page():
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
        
    # Dùng RealDictCursor để lấy kết quả dạng Dictionary
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Lấy (SELECT) tất cả dịch vụ
    cur.execute("SELECT * FROM Services ORDER BY service_id DESC")
    services_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template(SERVICES_HTML, services_list=services_list)

# 2. Route để XỬ LÝ việc thêm dịch vụ mới
@app.route('/add_service', methods=['POST'])
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

        # POSTGRES: Dùng RETURNING service_id để lấy ID ngay
        sql = """
            INSERT INTO Services (service_name, base_price, description, unit, unit_level2, unit_level3) 
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING service_id
        """
        cur.execute(sql, (name, price, description, u1, u2, u3))
        # new_id = cur.fetchone()[0] # Nếu cần dùng ID thì lấy ở đây
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi: {e}")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('services_page'))

# 3. Route để XỬ LÝ việc XÓA (Thực ra là KHÓA) một dịch vụ
@app.route('/delete_service/<int:service_id>', methods=['POST'])
@requires_permission('all')
def delete_service(service_id):
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
        
    cur = conn.cursor()
    try:
        sql = "DELETE FROM Services WHERE service_id = %s"
        cur.execute(sql, (service_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi xóa dịch vụ: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('services_page'))

# 4. Route để HIỂN THỊ form sửa (GET)
@app.route('/edit_service/<int:service_id>')
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

# 5. Route để XỬ LÝ dữ liệu Sửa (POST)
@app.route('/update_service', methods=['POST'])
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
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi update dịch vụ: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('services_page'))

# 6. Toggle Service
@app.route('/toggle_service/<int:id>', methods=['POST'])
@requires_permission('all')
def toggle_service(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Postgres hỗ trợ boolean toán tử NOT trực tiếp
        cur.execute("UPDATE Services SET is_active = NOT is_active WHERE service_id = %s", (id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('services_page'))

# ======================================================
# QUẢN LÝ KHÁCH HÀNG (CUSTOMERS) - CRUD (POSTGRESQL)
# ======================================================

# 1. (R)ead
@app.route('/customers')
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

# 2. (C)reate - Thêm Khách Hàng Mới
@app.route('/add_customer', methods=['POST'])
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
        return redirect(url_for('customers_page'))

    conn = get_db_connection()
    # Dùng RealDictCursor để lấy đúng tên cột (nếu hàm get_db_connection không mặc định)
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
        
        # 4. SỬA LỖI "0" Ở ĐÂY: Dùng tên cột thay vì số 0
        new_row = cur.fetchone()
        if new_row:
            # Lấy giá trị qua key 'customer_id' thay vì [0]
            new_id = new_row['customer_id'] 
        else:
            raise Exception("Database không trả về ID mới!")
        
        conn.commit()
        flash("Thêm khách hàng thành công!", "success")
        
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc() # In toàn bộ lỗi chi tiết ra Terminal để dễ nhìn hơn
        flash(f"Lỗi khi thêm khách hàng: {str(e)}", "danger") 
        
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('customers_page'))

# 3. (D)elete
@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
@requires_permission('all')
def delete_customer(customer_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM Customers WHERE customer_id = %s", (customer_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('customers_page'))

# 4. (U)pdate - GET
@app.route('/edit_customer/<int:customer_id>')
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

# 5. (U)pdate - POST
@app.route('/update_customer', methods=['POST'])
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
        
        # Log
        log_desc = f"Cập nhật thông tin Khách hàng ID {c_id}"
        # log_system_action(cur, 'UPDATE', 'Customers', log_desc)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi update khách: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('customers_page'))

# 6. Toggle Customer
@app.route('/toggle_customer/<int:id>', methods=['POST'])
@requires_permission('all')
def toggle_customer(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE Customers SET is_active = NOT is_active WHERE customer_id = %s", (id,))
        # log_desc = f"Khóa thông tin Khách hàng ID {id}"
        # log_system_action(cur, 'TOGGLE', 'Customers', log_desc)
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('customers_page'))

# ======================================================
# TẠO ĐƠN HÀNG (ORDERS) - POSTGRESQL
# ======================================================

# 1. (GET) Trang tạo đơn
@app.route('/create_order')
@requires_permission('sale')
def create_order_page():
    conn = get_db_connection()
    if conn is None: return "Lỗi DB", 500
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    today = datetime.date.today()
    
    # Lấy Khách hàng
    cur.execute("SELECT * FROM Customers WHERE is_active = TRUE ORDER BY customer_name")
    customers = cur.fetchall()
    
    # Lấy Dịch vụ
    cur.execute("SELECT * FROM Services WHERE is_active = TRUE ORDER BY service_name")
    services = cur.fetchall()
    
    # Lấy Thiết bị
    cur.execute("SELECT * FROM Equipment WHERE status = 'active' AND is_active = TRUE ORDER BY equipment_name")
    equipment = cur.fetchall()
    
    # Lấy Mã KM (Postgres so sánh ngày cũng OK)
    sql_coupons = """
        SELECT * FROM Coupons 
        WHERE status = 'active' AND start_date <= %s AND end_date >= %s
        ORDER BY discount_value DESC
    """
    cur.execute(sql_coupons, (today, today))
    coupons = cur.fetchall()
    
    # 🟢 THÊM 2 DÒNG NÀY VÀO ĐỂ LẤY DANH SÁCH XƯỞNG
    cur.execute("SELECT partner_id, partner_name FROM Outsource_Partners WHERE is_active = TRUE ORDER BY partner_name")
    partners_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template(TAO_DH_HTML, 
                           customers_list=customers, 
                           services_list=services,
                           equipment_list=equipment, 
                           active_coupons=coupons,
                           partners=partners_list) # <-- Bổ sung dòng này

# 2. (POST) Xử lý Submit Order (LOGIC PHỨC TẠP NHẤT)
@app.route('/submit_order', methods=['POST'])
@requires_permission('sale')
def submit_order():
    conn = get_db_connection()
    # Dùng RealDictCursor để truy vấn lấy tên cột
    cur = conn.cursor(cursor_factory=RealDictCursor) 
    
    try:
        # --- Lấy Input ---
        customer_id = request.form['customer_id']
        tax_rate = float(request.form['tax_rate'])
        coupon_code = request.form.get('coupon_code')
        discount_amount = float(request.form.get('discount_amount') or 0)
        
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        equipment_ids = request.form.getlist('equipment_id[]')
        
        # Các mảng số lượng tầng (Nếu frontend gửi lên)
        qty_l1_list = request.form.getlist('qty_l1[]')
        qty_l2_list = request.form.getlist('qty_l2[]')
        qty_l3_list = request.form.getlist('qty_l3[]')
        
        # --- B1: Tính Tổng tiền ---
        subtotal = 0
        for i in range(len(service_ids)):
            subtotal += int(quantities[i]) * float(unit_prices[i])
        
        tax_amount = subtotal * (tax_rate / 100)
        total_amount = (subtotal + tax_amount) - discount_amount
        if total_amount < 0: total_amount = 0

        # --- B2: Insert Order (POSTGRES RETURNING) ---
        sql_order = """
            INSERT INTO Orders (customer_id, status, subtotal, tax_rate, tax_amount, coupon_code, discount_amount, total_amount, quote_id)
            VALUES (%s, 'processing', %s, %s, %s, %s, %s, %s, NULL)
            RETURNING order_id
        """
        cur.execute(sql_order, (customer_id, subtotal, tax_rate, tax_amount, coupon_code, discount_amount, total_amount))
        
        # Lấy ID đơn hàng mới
        new_order_id = cur.fetchone()['order_id']
        
        # Cập nhật Coupon used_count
        if coupon_code:
            cur.execute("UPDATE Coupons SET used_count = used_count + 1 WHERE code = %s", (coupon_code,))

        # --- B3: Loop Items ---
        for i in range(len(service_ids)):
            srv_id = service_ids[i]
            qty = int(quantities[i])
            price = float(unit_prices[i])
            equip_id = equipment_ids[i] if equipment_ids[i] else None
            line_total = qty * price
            
            # Tính toán Cost (Giá vốn)
            total_cost_item = 0.0
            
            # Lấy số lượng chi tiết tầng (An toàn với mảng rỗng)
            q1 = float(qty_l1_list[i]) if i < len(qty_l1_list) and qty_l1_list[i] else 0
            q2 = float(qty_l2_list[i]) if i < len(qty_l2_list) and qty_l2_list[i] else 0
            q3 = float(qty_l3_list[i]) if i < len(qty_l3_list) and qty_l3_list[i] else 0
            
            # Tra cứu BOM (Định mức)
            sql_bom = """
                SELECT SM.material_id, SM.quantity_consumed, SM.apply_to_unit_level, M.avg_cost_per_base_unit 
                FROM Service_Materials SM
                JOIN Materials M ON SM.material_id = M.material_id
                WHERE SM.service_id = %s
            """
            cur.execute(sql_bom, (srv_id,))
            bom_list = cur.fetchall()
            
            if bom_list:
                for mat in bom_list:
                    consume = float(mat['quantity_consumed'])
                    avg_cost = float(mat['avg_cost_per_base_unit'])
                    level = mat['apply_to_unit_level']
                    
                    deduct_qty = 0
                    if level == 1: deduct_qty = (q1 * q2 * q3) * consume
                    elif level == 2: deduct_qty = (q2 * q3) * consume
                    elif level == 3: deduct_qty = q3 * consume
                    
                    # Cộng giá vốn
                    total_cost_item += (deduct_qty * avg_cost)
                    
                    # TRỪ KHO
                    cur.execute("UPDATE Materials SET stock_quantity = stock_quantity - %s WHERE material_id = %s", 
                               (deduct_qty, mat['material_id']))
            
            profit = line_total - total_cost_item
            
            # Insert Order Items
            sql_item = """
                INSERT INTO Order_Items (order_id, service_id, equipment_id, quantity, unit_price, line_total, cost_of_goods, profit)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql_item, (new_order_id, srv_id, equip_id, qty, price, line_total, total_cost_item, profit))
            
            # Update Equipment Counter
            if equip_id and qty > 0:
                cur.execute("UPDATE Equipment SET print_count = print_count + %s WHERE equipment_id = %s", (qty, equip_id))

        # Log
        # log_system_action(cur, 'CREATE', 'Orders', f"Tạo đơn #{new_order_id}")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi tạo đơn: {e}")
        return f"Lỗi: {e}", 500
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('services_page')) # Hoặc trang chi tiết

# 3. Hủy đơn hàng
@app.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT status FROM Orders WHERE order_id = %s", (order_id,))
        order = cur.fetchone()
        
        if not order or order['status'] != 'processing':
            return "Chỉ hủy được đơn đang xử lý", 400
            
        # Lấy Items để hoàn kho
        cur.execute("SELECT service_id, quantity FROM Order_Items WHERE order_id = %s", (order_id,))
        items = cur.fetchall()
        
        for item in items:
            # Postgres logic hoàn kho (tương tự mysql logic nhưng đổi cú pháp execute)
            # Ở đây tôi viết rút gọn logic bom
            cur.execute("SELECT material_id, quantity_consumed FROM Service_Materials WHERE service_id = %s", (item['service_id'],))
            boms = cur.fetchall()
            
            for b in boms:
                # Giả sử quantity trong Order_Items là tổng (đơn giản hóa cho ví dụ)
                return_qty = float(item['quantity']) * float(b['quantity_consumed'])
                cur.execute("UPDATE Materials SET stock_quantity = stock_quantity + %s WHERE material_id = %s", 
                           (return_qty, b['material_id']))
        
        cur.execute("UPDATE Orders SET status = 'cancelled' WHERE order_id = %s", (order_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi hủy đơn: {e}")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('orders_history_page'))

# ======================================================
# LỊCH SỬ ĐƠN HÀNG & CHI TIẾT (POSTGRESQL)
# ======================================================

@app.route('/orders_history')
@requires_permission('sale', 'accounting')
def orders_history_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    mode = request.args.get('filter')
    
    # Logic ngày mặc định
    today = datetime.date.today()
    if not start and not end and mode != 'all':
        start = (today - datetime.timedelta(days=6)).isoformat()
        end = today.isoformat()
        
    sql = """
        SELECT O.order_id, O.order_date, O.total_amount, O.status, O.amount_paid, 
               (O.total_amount - O.amount_paid) AS amount_due, 
               O.payment_status, O.delivery_status, C.customer_name
        FROM Orders O
        JOIN Customers C ON O.customer_id = C.customer_id
        WHERE 1=1
    """
    params = []
    if start:
        sql += " AND DATE(O.order_date) >= %s"
        params.append(start)
    if end:
        sql += " AND DATE(O.order_date) <= %s"
        params.append(end)
        
    sql += " ORDER BY O.order_date DESC"
    
    cur.execute(sql, tuple(params))
    orders = cur.fetchall()
    
    # Tính toán Python sum
    rev = sum(o['total_amount'] for o in orders if o['status'] != 'cancelled')
    due = sum(o['amount_due'] for o in orders if o['status'] != 'cancelled')
    canc = sum(o['total_amount'] for o in orders if o['status'] == 'cancelled')
    
    cur.close()
    conn.close()
    
    return render_template(LS_DH_HTML, orders_list=orders, start_date=start, end_date=end,
                           total_revenue=rev, total_due=due, total_cancelled=canc)

@app.route('/order/<int:order_id>')
@requires_permission('sale', 'inventory')
def order_detail_page(order_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Info
    sql_info = """
        SELECT O.*, C.customer_name, C.phone 
        FROM Orders O JOIN Customers C ON O.customer_id = C.customer_id
        WHERE O.order_id = %s
    """
    cur.execute(sql_info, (order_id,))
    info = cur.fetchone()
    
    # Items
    sql_items = """
        SELECT QI.*, S.service_name, S.unit 
        FROM Order_Items QI JOIN Services S ON QI.service_id = S.service_id
        WHERE QI.order_id = %s
    """
    cur.execute(sql_items, (order_id,))
    items = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not info: return "Not Found", 404
    return render_template(CT_DH_HTML, order_info=info, order_items=items)

# ======================================================
# XỬ LÝ THANH TOÁN & GIAO HÀNG (ORDERS) - POSTGRESQL
# ======================================================

# 3. (POST) Ghi nhận Thanh toán cho một Đơn hàng
@app.route('/log_payment/<int:order_id>', methods=['POST'])
@requires_permission('sale', 'accounting') # Kinh Doanh và Kế toán
def log_payment(order_id):
    conn = get_db_connection()
    # Dùng RealDictCursor để truy cập bằng tên cột
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # 0. Kiểm tra trạng thái trước
        cur.execute("SELECT status, total_amount, amount_paid FROM Orders WHERE order_id = %s", (order_id,))
        order = cur.fetchone()
        
        if not order or order['status'] == 'cancelled':
            return "LỖI: Không thể thanh toán cho đơn hàng đã hủy!", 403
    
        # Lấy số tiền vừa nhận từ form
        amount_received = float(request.form['amount_received'])
        payment_method = request.form['payment_method']
        
        # 1. Cập nhật số tiền đã trả
        sql_update = """
            UPDATE Orders 
            SET amount_paid = amount_paid + %s, 
                payment_method = %s 
            WHERE order_id = %s
        """
        cur.execute(sql_update, (amount_received, payment_method, order_id))
        
        # 2. Tính toán trạng thái thanh toán mới (Logic Python)
        new_paid = float(order['amount_paid']) + amount_received
        total = float(order['total_amount'])
        
        new_payment_status = 'unpaid'
        if new_paid >= total:
            new_payment_status = 'paid'
        elif new_paid > 0:
            new_payment_status = 'partially_paid'
        
        # 3. Cập nhật trạng thái thanh toán
        cur.execute("UPDATE Orders SET payment_status = %s WHERE order_id = %s", (new_payment_status, order_id))
        
        # Ghi Log
        log_desc = f"Thanh toán đơn hàng #{order_id}. Số tiền: {amount_received:,.0f}"
        # log_system_action(cur, 'PAYMENT', 'Orders', log_desc)
        
        conn.commit()
        
    except Exception as e:
        conn.rollback() 
        print(f"LỖI KHI GHI NHẬN THANH TOÁN: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('order_detail_page', order_id=order_id))

# 4. (POST) Cập nhật Trạng thái Giao hàng
@app.route('/update_delivery/<int:order_id>', methods=['POST'])
@requires_permission('inventory', 'sale') # Kinh Doanh và Kho
def update_delivery_status(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Kiểm tra trạng thái
        cur.execute("SELECT status FROM Orders WHERE order_id = %s", (order_id,))
        result = cur.fetchone() 
        
        # Postgres fetchone trả về tuple nếu không dùng RealDictCursor, hoặc Dict nếu dùng.
        # Ở đây cursor() mặc định là tuple.
        if not result or result[0] == 'cancelled':
            return "LỖI: Không thể cập nhật giao hàng cho đơn đã hủy!", 403
    
        new_status = request.form['delivery_status']
        sql = "UPDATE Orders SET delivery_status = %s WHERE order_id = %s"
        cur.execute(sql, (new_status, order_id))
        
        # log_desc = f"Cập nhật giao hàng đơn #{order_id} -> {new_status}"
        # log_system_action(cur, 'DELIVERY', 'Orders', log_desc)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"LỖI KHI CẬP NHẬT GIAO HÀNG: {e}")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('order_detail_page', order_id=order_id))

# ======================================================
# QUẢN LÝ BÁO GIÁ (QUOTES) - POSTGRESQL
# ======================================================

# 1. (GET) Hiển thị trang Lịch sử Báo giá
@app.route('/quotes_history')
@requires_permission('sale') # Kinh Doanh
def quotes_history_page():
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối database!", 500
        
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    filter_mode = request.args.get('filter')
    
    # Logic ngày mặc định
    today = datetime.date.today()
    if not start_date_str and not end_date_str and filter_mode != 'all':
        start_date_str = (today - datetime.timedelta(days=6)).isoformat()
        end_date_str = today.isoformat()
    
    sql = """
        SELECT Q.quote_id, Q.created_date, Q.total_amount, Q.status, C.customer_name
        FROM Quotes AS Q
        JOIN Customers AS C ON Q.customer_id = C.customer_id
        WHERE 1=1 
    """
    params = []

    if start_date_str:
        sql += " AND DATE(Q.created_date) >= %s"
        params.append(start_date_str)
    if end_date_str:
        sql += " AND DATE(Q.created_date) <= %s"
        params.append(end_date_str)
        
    sql += " ORDER BY Q.created_date DESC"
    
    cur.execute(sql, tuple(params))
    quotes_list = cur.fetchall()
    
    total_quotes_value = sum(quote['total_amount'] for quote in quotes_list)
    
    cur.close()
    conn.close()
    
    return render_template(LS_BG_HTML, 
                           quotes_list=quotes_list,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           total_quotes_value=total_quotes_value)

# 2. (GET) Trang TẠO Báo giá Mới
@app.route('/create_quote')
@requires_permission('sale')
def create_quote_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    today = datetime.date.today()
    
    cur.execute("SELECT customer_id, customer_name, phone, email, address, company_name, tax_id FROM Customers WHERE is_active = TRUE ORDER BY customer_name")
    customers_list = cur.fetchall()
    
    cur.execute("SELECT service_id, service_name, base_price, unit FROM Services WHERE is_active = TRUE ORDER BY service_name")
    services_list = cur.fetchall()
    
    sql_coupons = """
        SELECT * FROM Coupons 
        WHERE status = 'active' AND start_date <= %s AND end_date >= %s
        ORDER BY discount_value DESC
    """
    cur.execute(sql_coupons, (today, today))
    active_coupons = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template(TAO_BG_HTML, 
                           customers_list=customers_list, 
                           services_list=services_list,
                           active_coupons=active_coupons)

# 3. (POST) Xử lý LƯU Báo giá
@app.route('/submit_quote', methods=['POST'])
@requires_permission('sale')
def submit_quote():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor) # Để fetchone() nếu cần
    new_quote_id = -1
    
    try:
        customer_id = request.form['customer_id']
        notes = request.form['notes']
        tax_rate = float(request.form['tax_rate'])
        
        coupon_code = request.form.get('coupon_code')
        discount_amount = float(request.form.get('discount_amount') or 0)
        
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        
        # Tính tổng
        subtotal = 0
        for i in range(len(service_ids)):
            subtotal += int(quantities[i]) * float(unit_prices[i])
            
        tax_amount = subtotal * (tax_rate / 100)
        total_amount = (subtotal + tax_amount) - discount_amount
        if total_amount < 0: total_amount = 0
        
        # INSERT Quote (POSTGRES RETURNING)
        sql_insert_quote = """
            INSERT INTO Quotes (customer_id, status, notes, subtotal, tax_rate, tax_amount, 
            coupon_code, discount_amount, total_amount)
            VALUES (%s, 'pending', %s, %s, %s, %s, %s, %s, %s)
            RETURNING quote_id
        """
        val_insert = (customer_id, notes, subtotal, tax_rate, tax_amount, coupon_code, discount_amount, total_amount)
        cur.execute(sql_insert, val_insert)
        
        new_quote_id = cur.fetchone()['quote_id']

        # INSERT Items
        for i in range(len(service_ids)):
            sql_item = """
                INSERT INTO Quote_Items (quote_id, service_id, description, quantity, unit_price, line_total)
                VALUES (%s, %s, '', %s, %s, %s)
            """
            line_total = int(quantities[i]) * float(unit_prices[i])
            cur.execute(sql_item, (new_quote_id, service_ids[i], quantities[i], unit_prices[i], line_total))
        
        # log_desc = f"Tạo Báo Giá #{new_quote_id}. Tổng tiền: {total_amount:,.0f}"
        # log_system_action(cur, 'CREATE', 'Quotes', log_desc)
        
        conn.commit()
        
    except Exception as e:
        conn.rollback() 
        print(f"LỖI TẠO BÁO GIÁ: {e}")
        return f"Đã xảy ra lỗi: {e}", 500
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('quote_detail_page', quote_id=new_quote_id))

# 4. (GET) Chi tiết Báo giá
@app.route('/quote/<int:quote_id>')
@requires_permission('sale','inventory')
def quote_detail_page(quote_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql_quote = """
        SELECT Q.*, C.customer_name, C.phone
        FROM Quotes AS Q
        JOIN Customers AS C ON Q.customer_id = C.customer_id
        WHERE Q.quote_id = %s
    """
    cur.execute(sql_quote, (quote_id,))
    quote_info = cur.fetchone()
    
    sql_items = """
        SELECT QI.quantity, QI.unit_price, QI.line_total, S.service_name, S.unit
        FROM Quote_Items AS QI
        JOIN Services AS S ON QI.service_id = S.service_id
        WHERE QI.quote_id = %s
    """
    cur.execute(sql_items, (quote_id,))
    quote_items = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not quote_info: return "Không tìm thấy báo giá!", 404
    return render_template(CT_BG_HTML, quote_info=quote_info, quote_items=quote_items)

# 5. (POST) Cập nhật Trạng thái Báo giá
@app.route('/update_quote_status/<int:quote_id>', methods=['POST'])
@requires_permission('sale')
def update_quote_status(quote_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        new_status = request.form['quote_status']
        cur.execute("UPDATE Quotes SET status = %s WHERE quote_id = %s", (new_status, quote_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi: {e}")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('quote_detail_page', quote_id=quote_id))

# 6. (POST) CHUYỂN BÁO GIÁ THÀNH ĐƠN HÀNG
@app.route('/convert_quote/<int:quote_id>', methods=['POST'])
@requires_permission('sale')
def convert_quote_to_order(quote_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    new_order_id = -1
    
    try:
        # B0: Check exist
        cur.execute("SELECT order_id FROM Orders WHERE quote_id = %s", (quote_id,))
        existing_order = cur.fetchone()
        if existing_order:
            return redirect(url_for('order_detail_page', order_id=existing_order['order_id']))

        # B1: Get Quote Info
        cur.execute("SELECT * FROM Quotes WHERE quote_id = %s", (quote_id,))
        quote_info = cur.fetchone()
        
        cur.execute("SELECT * FROM Quote_Items WHERE quote_id = %s", (quote_id,))
        quote_items_list = cur.fetchall()
        
        if not quote_info: return "Lỗi: Báo giá không hợp lệ.", 400

        # B2: Create Order (RETURNING ID)
        sql_insert = """
            INSERT INTO Orders (customer_id, total_amount, status, quote_id)
            VALUES (%s, %s, 'processing', %s)
            RETURNING order_id
        """
        cur.execute(sql_insert, (quote_info['customer_id'], quote_info['total_amount'], quote_id))
        new_order_id = cur.fetchone()['order_id']

        # B3 & 4: Insert Items & Update Stock
        for item in quote_items_list:
            # Insert Item
            sql_item = """
                INSERT INTO Order_Items (order_id, service_id, quantity, unit_price, line_total)
                VALUES (%s, %s, %s, %s, %s)
            """
            cur.execute(sql_item, (new_order_id, item['service_id'], item['quantity'], item['unit_price'], item['line_total']))
            
            # Check BOM & Deduct Stock
            cur.execute("SELECT material_id, quantity_consumed FROM Service_Materials WHERE service_id = %s", (item['service_id'],))
            boms = cur.fetchall()

            for b in boms:
                deduct = float(item['quantity']) * float(b['quantity_consumed'])
                cur.execute("UPDATE Materials SET stock_quantity = stock_quantity - %s WHERE material_id = %s", 
                           (deduct, b['material_id']))
        
        conn.commit()
        
    except Exception as e:
        conn.rollback() 
        print(f"Lỗi Convert Quote: {e}")
        return f"Lỗi: {e}", 500
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('order_detail_page', order_id=new_order_id))

# ======================================================
# CẬP NHẬT BÁO GIÁ (EDIT)
# ======================================================

@app.route('/edit_quote/<int:quote_id>')
@requires_permission('sale')
def edit_quote_page(quote_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM Quotes WHERE quote_id = %s", (quote_id,))
    quote_info = cur.fetchone()
    
    cur.execute("SELECT * FROM Quote_Items WHERE quote_id = %s", (quote_id,))
    quote_items_list = cur.fetchall()
    
    cur.execute("SELECT customer_id, customer_name FROM Customers ORDER BY customer_name")
    customers_list = cur.fetchall()
    
    cur.execute("SELECT service_id, service_name, base_price, unit FROM Services ORDER BY service_name")
    services_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not quote_info: return "Not Found", 404
    if quote_info['status'] != 'pending': return "Không thể sửa báo giá đã xử lý.", 403
        
    return render_template(EDIT_QUOTE_HTML, 
                           quote_info=quote_info,
                           quote_items_list=quote_items_list,
                           customers_list=customers_list,
                           services_list=services_list)

@app.route('/update_quote/<int:quote_id>', methods=['POST'])
@requires_permission('sale')
def update_quote(quote_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        customer_id = request.form['customer_id']
        tax_rate = float(request.form['tax_rate'])
        notes = request.form['notes']
        
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        # 1. DELETE OLD ITEMS
        cur.execute("DELETE FROM Quote_Items WHERE quote_id = %s", (quote_id,))

        # 2. INSERT NEW ITEMS & CALC
        subtotal = 0
        for i in range(len(service_ids)):
            qty = int(quantities[i])
            price = float(unit_prices[i])
            line = qty * price
            subtotal += line
            
            cur.execute("""
                INSERT INTO Quote_Items (quote_id, service_id, description, quantity, unit_price, line_total)
                VALUES (%s, %s, '', %s, %s, %s)
            """, (quote_id, service_ids[i], qty, price, line))
            
        tax_amount = subtotal * (tax_rate / 100)
        total_amount = subtotal + tax_amount

        # 3. UPDATE QUOTE
        sql_update = """
            UPDATE Quotes 
            SET customer_id = %s, tax_rate = %s, notes = %s, 
                subtotal = %s, tax_amount = %s, total_amount = %s, 
                update_count = update_count + 1
            WHERE quote_id = %s
        """
        cur.execute(sql_update, (customer_id, tax_rate, notes, subtotal, tax_amount, total_amount, quote_id))
        
        conn.commit()
    except Exception as e:
        conn.rollback() 
        print(f"Lỗi Update Quote: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('quote_detail_page', quote_id=quote_id))

# ======================================================
# QUẢN LÝ VẬT TƯ (MATERIALS) - POSTGRESQL VERSION
# ======================================================

# 1. (R)ead - Hiển thị danh sách vật tư
@app.route('/materials')
@login_required
def materials_page():
    # Kiểm tra quyền: Chỉ Admin và Thủ kho (Role 1, 2) hoặc Kinh doanh (Role 3) được xem
    if current_user.role_id not in [1, 2, 3]:
        flash('Bạn không có quyền truy cập kho!', 'danger')
        return redirect(url_for('dashboard_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Lấy danh sách vật tư còn hoạt động
    cur.execute("SELECT * FROM materials WHERE is_active = TRUE ORDER BY material_id DESC")
    materials_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template(MATERIALS_HTML, materials_list=materials_list)

# 2. (C)reate - Xử lý thêm vật tư mới
@app.route('/add_material', methods=['POST'])
@login_required
def add_material():
    try:
        # Lấy dữ liệu từ form
        name = request.form['material_name']
        m_type = request.form['material_type']
        
        # Nếu là linh kiện bảo trì thì lấy vòng đời, ngược lại là 0
        lifespan = request.form.get('lifespan_prints', 0) if m_type == 'maintenance' else 0
        
        base_unit = request.form['base_unit']
        import_unit = request.form.get('import_unit', '')
        
        # Xử lý hệ số quy đổi (tránh lỗi chia cho 0 hoặc rỗng)
        conv_factor = request.form.get('import_conversion_factor')
        conv_factor = float(conv_factor) if conv_factor and float(conv_factor) > 0 else 1.0
        
        stock_qty = request.form.get('stock_quantity', 0)

        conn = get_db_connection()
        cur = conn.cursor()
        
        # Câu lệnh SQL cho Postgres (Dùng RETURNING material_id để lấy ID ngay)
        sql = """
            INSERT INTO materials 
            (material_name, material_type, lifespan_prints, base_unit, import_unit, import_conversion_factor, stock_quantity, is_active) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING material_id
        """
        cur.execute(sql, (name, m_type, lifespan, base_unit, import_unit, conv_factor, stock_qty))
        
        # Lấy ID vừa tạo để ghi log (thay cho lastrowid của MySQL)
        new_id = cur.fetchone()['material_id']
        
        # Ghi Log (Hàm log_system_action cần được viết lại cho Postgres nếu chưa có)
        # log_system_action(cur, current_user.id, 'ADD', 'Materials', f"Thêm Vật Tư ID {new_id}")

        conn.commit()
        flash('Thêm vật tư thành công!', 'success')
        
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        if 'conn' in locals(): conn.close()
    
    return redirect(url_for('materials_page'))

# 3. (U)pdate - Hiển thị form sửa vật tư
@app.route('/edit_material/<int:material_id>')
@login_required
def edit_material_page(material_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM materials WHERE material_id = %s", (material_id,))
    material_data = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if material_data:
        return render_template(EDIT_MATERIAL_HTML, material=material_data)
    else:
        return "Không tìm thấy vật tư!", 404

# 4. (U)pdate - Xử lý cập nhật vật tư
@app.route('/update_material', methods=['POST'])
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
    
    return redirect(url_for('materials_page'))

# 5. Khóa / Mở khóa vật tư (Thay vì xóa hẳn)
@app.route('/toggle_material/<int:id>', methods=['POST'])
@login_required
def toggle_material(id):
    # Chỉ Admin hoặc Thủ kho được xóa
    if current_user.role_id not in [1, 2]:
        flash('Bạn không có quyền thực hiện thao tác này!', 'danger')
        return redirect(url_for('materials_page'))

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
    return redirect(url_for('materials_page'))



# ======================================================
# QUẢN LÝ THIẾT BỊ (EQUIPMENT) - POSTGRESQL
# ======================================================

@app.route('/equipment')
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

@app.route('/add_equipment', methods=['POST'])
@requires_permission('asset','accounting')
def add_equipment():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Lấy form (tương tự code cũ)
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
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('equipment_page'))
    
 # 3. (D)elete - Xử lý xóa thiết bị
@app.route('/delete_equipment/<int:equipment_id>', methods=['POST'])
@requires_permission('all') # Admin
def delete_equipment(equipment_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # (Lưu ý: Để xóa máy, bạn phải xóa các log bảo trì của nó trước)
        # Postgres có cơ chế ràng buộc khóa ngoại chặt chẽ, nếu không xóa Logs trước sẽ báo lỗi.
        sql = "DELETE FROM Equipment WHERE equipment_id = %s"
        cur.execute(sql, (equipment_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi xóa thiết bị: {e}")
        flash(f"Không thể xóa thiết bị (có thể đang có dữ liệu liên quan). Lỗi: {e}", "danger")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('equipment_page'))

# 4. (GET) Hiển thị trang CHI TIẾT của một Thiết bị
@app.route('/equipment_detail/<int:equipment_id>')
@requires_permission('asset','accounting') # Kế toán và kho
def equipment_detail_page(equipment_id):
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
    
    # POSTGRES: Sử dụng RealDictCursor để lấy kết quả dạng Dictionary (giống dictionary=True của MySQL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Query 1: Lấy thông tin của máy
    sql_eq = "SELECT * FROM Equipment WHERE equipment_id = %s"
    cur.execute(sql_eq, (equipment_id,))
    equipment_info = cur.fetchone()
    
    # Query 2: Lấy lịch sử bảo trì (JOIN với Suppliers VÀ Materials)
    # Lưu ý: Postgres phân biệt chữ hoa thường tên bảng nếu tạo bảng có ""
    # Nhưng nếu tạo bảng bình thường thì không sao. Giữ nguyên SQL logic.
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
    
    # Query 3: Lấy danh sách nhà cung cấp (cho dropdown NCC)
    cur.execute("SELECT supplier_id, supplier_name FROM Suppliers ORDER BY supplier_name")
    suppliers_list = cur.fetchall()
    
    # Query 4: Lấy danh sách LINH KIỆN BẢO TRÌ (cho dropdown linh kiện)
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
    
    if not equipment_info:
        return "Không tìm thấy thiết bị!", 404
        
    return render_template(CT_TB_HTML, 
                           equipment_info=equipment_info,
                           logs_list=logs_list,
                           suppliers_list=suppliers_list,
                           maintenance_parts_list=maintenance_parts_list)

# 6. (POST) Cập nhật Thông tin Thiết bị
@app.route('/edit_equipment_info', methods=['POST'])
@requires_permission('asset') # Kho
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
        
        # Xử lý ngày tháng: Nếu rỗng gửi lên là '', Postgres cần None hoặc NULL
        p_date = request.form.get('purchase_date')
        if not p_date or p_date.strip() == '': p_date = None
        
        w_date = request.form.get('warranty_end_date')
        if not w_date or w_date.strip() == '': w_date = None
        
        # Xử lý Supplier ID
        val_supplier = supplier_id if supplier_id and supplier_id.strip() != '' else None

        sql = """
            UPDATE Equipment 
            SET equipment_name = %s, ip_address = %s, serial_number = %s, 
                model_number = %s, supplier_id = %s, purchase_date = %s, 
                warranty_end_date = %s
            WHERE equipment_id = %s
        """
        cur.execute(sql, (name, ip_addr, serial, model, val_supplier, p_date, w_date, equipment_id))
        
        # Ghi Log
        # log_desc = f"Cập nhật thông tin Thiết Bị #{equipment_id}."
        # log_system_action(cur, 'UPDATE', 'Equipment', log_desc)
        
        conn.commit()
        flash('Cập nhật thông tin thiết bị thành công!', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"Lỗi SQL Edit Equipment: {e}")
        flash(f"Lỗi cập nhật: {e}", "danger")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('equipment_detail_page', equipment_id=equipment_id))

# 7. Toggle Equipment (Thay thế delete để bảo toàn dữ liệu)
@app.route('/toggle_equipment/<int:id>', methods=['POST'])
@requires_permission('all') # Admin
def toggle_equipment(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Postgres hỗ trợ boolean NOT trực tiếp (TRUE -> FALSE, FALSE -> TRUE)
        cur.execute("UPDATE Equipment SET is_active = NOT is_active WHERE equipment_id = %s", (id,))
        
        # Ghi log
        # log_desc = f"Khóa/Mở khóa Thiết Bị #{id}."
        # log_system_action(cur, 'TOGGLE', 'Equipment', log_desc)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi Toggle Equipment: {e}")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('equipment_page'))


# 2. Xử lý Lưu cập nhật thiết bị (Backend cho nút Lưu ở trang chi tiết)
@app.route('/update_equipment', methods=['POST'])
@login_required
def update_equipment():
    e_id = request.form['equipment_id']
    name = request.form['equipment_name']
    model = request.form.get('model_number', '')
    serial = request.form.get('serial_number', '')
    supplier = request.form.get('supplier_id') or None # Nếu không chọn thì là None
    
    # Xử lý ngày tháng (nếu rỗng thì là None)
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
        conn.commit()
        flash('Cập nhật thông tin thiết bị thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi cập nhật: {e}', 'danger')
    finally:
        conn.close()
        
    # Quay lại trang chi tiết sau khi lưu
    return redirect(url_for('equipment_detail_page', equipment_id=e_id))

# ======================================================
# QUẢN LÝ BẢO TRÌ THIẾT BỊ (LOGS) - POSTGRESQL
# ======================================================

@app.route('/add_maintenance_log', methods=['POST'])
@requires_permission('asset','accounting')
def add_maintenance_log():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Lấy Input
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
        
        # 1. Tự động Nhập kho (Nếu có NCC + Thay linh kiện)
        if sup_id and rep_mat_id and rep_qty > 0:
            cur.execute("UPDATE Materials SET stock_quantity = stock_quantity + %s WHERE material_id = %s", (rep_qty, rep_mat_id))
            
            cur.execute("""
                INSERT INTO Material_Imports (material_id, supplier_id, import_date, quantity_imported, import_price, payment_status)
                VALUES (%s, %s, %s, %s, 0, %s)
            """, (rep_mat_id, sup_id, m_date, rep_qty, 'paid')) # Giá 0 để không tính công nợ kép
            
        # 2. Insert Log
        sql_log = """
            INSERT INTO Maintenance_Logs (equipment_id, supplier_id, maintenance_date, 
                                        description, cost, technician_name, payment_status,
                                        replaced_material_id, replaced_quantity, current_counter_at_log,
                                        warranty_end_date, warranty_end_counter) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(sql_log, (eq_id, sup_id, m_date, desc, cost, tech_name, payment_status, 
                              rep_mat_id, rep_qty, curr_cnt, w_date, w_cnt))
        
        # 3. Update Equipment Counter (Chỉ update nếu lớn hơn)
        if curr_cnt > 0:
            cur.execute("""
                UPDATE Equipment SET print_count = %s 
                WHERE equipment_id = %s AND print_count < %s
            """, (curr_cnt, eq_id, curr_cnt))
            
        # 4. Trừ kho (Dùng linh kiện)
        if rep_mat_id and rep_qty > 0:
            cur.execute("UPDATE Materials SET stock_quantity = stock_quantity - %s WHERE material_id = %s", (rep_qty, rep_mat_id))
            
        conn.commit()
        
    except Exception as e:
        conn.rollback() 
        print(f"Lỗi Logs: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('equipment_detail_page', equipment_id=eq_id))

# ======================================================
# QUẢN LÝ NHÀ CUNG CẤP (SUPPLIERS) - POSTGRESQL
# ======================================================

# 2. TRANG DANH SÁCH NHÀ CUNG CẤP (Phòng hờ lỗi tiếp theo)
@app.route('/suppliers')
@login_required
def suppliers_page():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Suppliers ORDER BY supplier_id DESC")
    suppliers = cur.fetchall()
    conn.close()
    return render_template(NCC_HTML, suppliers_list=suppliers)

# 3. THÊM NHÀ CUNG CẤP (Cách thông thường - Submit Form)
@app.route('/add_supplier', methods=['POST'])
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
        conn.commit()
        flash('Thêm nhà cung cấp thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('suppliers_page'))

# 4. KHÓA/MỞ NHÀ CUNG CẤP
@app.route('/toggle_supplier/<int:id>', methods=['POST'])
@login_required
def toggle_supplier(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE Suppliers SET is_active = NOT is_active WHERE supplier_id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('suppliers_page'))

# ======================================================
# QUẢN LÝ NHẬP KHO (MATERIAL IMPORTS)
# ======================================================

# 1. Trang danh sách nhập kho
@app.route('/imports')
@login_required
def imports_page():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Query lịch sử nhập kho
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

# ======================================================
# QUẢN LÝ PHIẾU NHẬP KHO (NHIỀU VẬT TƯ)
# ======================================================

# 1. (GET) Hiển thị trang Tạo Phiếu Nhập
@app.route('/create_import')
@requires_permission('inventory') # KHO
def create_import_page():
    conn = get_db_connection()
    # 🟢 SỬA LỖI 1: Thay dictionary=True bằng cursor_factory
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Lấy danh sách NCC (Sửa is_active = 1 thành TRUE)
    cursor.execute("SELECT supplier_id, supplier_name FROM Suppliers WHERE is_active = TRUE ORDER BY supplier_name")
    suppliers_list = cursor.fetchall()
    
    # Lấy danh sách Vật tư (Sửa is_active = 1 thành TRUE)
    cursor.execute("SELECT material_id, material_name, import_unit FROM Materials WHERE is_active = TRUE ORDER BY material_name")
    materials_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Lấy ngày hôm nay
    today = datetime.date.today().isoformat()
    
    return render_template(CREATE_IMPORT_HTML, 
                           suppliers_list=suppliers_list, 
                           materials_list=materials_list,
                           today=today) # <-- Gửi biến 'today' ra HTML

# 2. (POST) Xử lý Lưu Phiếu Nhập (Tính giá vốn & Tồn kho)
@app.route('/submit_import_slip', methods=['POST'])
@requires_permission('inventory') # KHO
def submit_import_slip():
    conn = get_db_connection()
    # 🟢 SỬA LỖI 1: Dùng RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # A. Lấy thông tin chung (Header)
        supplier_id = request.form['supplier_id']
        import_date = request.form['import_date']
        payment_status = request.form['payment_status']
        
        # B. Lấy danh sách chi tiết (Items)
        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity[]')     # Số lượng (theo ĐV Nhập)
        unit_prices = request.form.getlist('unit_price[]')  # Giá (theo ĐV Nhập)
        
        # Tính tổng tiền phiếu
        total_amount = 0
        for i in range(len(material_ids)):
            # Bỏ qua nếu dòng bị trống dữ liệu
            if material_ids[i] and quantities[i] and unit_prices[i]:
                total_amount += int(quantities[i]) * float(unit_prices[i])

        # --- BƯỚC 1: TẠO PHIẾU NHẬP (Import_Slips) ---
        # 🟢 SỬA LỖI 2: Dùng RETURNING slip_id thay cho lastrowid
        sql_slip = """
            INSERT INTO Import_Slips (supplier_id, import_date, total_amount, payment_status)
            VALUES (%s, %s, %s, %s) RETURNING slip_id
        """
        cursor.execute(sql_slip, (supplier_id, import_date, total_amount, payment_status))
        new_slip_id = cursor.fetchone()['slip_id']

        # --- BƯỚC 2: LẶP QUA TỪNG VẬT TƯ ---
        for i in range(len(material_ids)):
            mat_id = material_ids[i]
            
            # Kiểm tra an toàn: Bỏ qua nếu form gửi lên mảng trống
            if not mat_id or not quantities[i] or not unit_prices[i]:
                continue
                
            qty_import_unit = int(quantities[i])
            price_import_unit = float(unit_prices[i])
            line_total = qty_import_unit * price_import_unit
            
            # 2a. Lưu vào bảng chi tiết (Import_Slip_Items)
            sql_item = """
                INSERT INTO Import_Slip_Items (slip_id, material_id, quantity, unit_price, line_total)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql_item, (new_slip_id, mat_id, qty_import_unit, price_import_unit, line_total))
            
            # 2b. TÍNH GIÁ VỐN TRUNG BÌNH & CẬP NHẬT KHO (Logic cũ)
            cursor.execute("SELECT stock_quantity, import_conversion_factor, avg_cost_per_base_unit FROM Materials WHERE material_id = %s", (mat_id,))
            material = cursor.fetchone()
            
            if material:
                # Xử lý an toàn nếu Database trả về None
                current_stock_base = material['stock_quantity'] or 0
                conversion_factor = material['import_conversion_factor'] or 1.0
                current_avg_cost = float(material['avg_cost_per_base_unit'] or 0)
                
                # Quy đổi ra Đơn vị Cơ sở (Base Unit)
                qty_base = qty_import_unit * conversion_factor
                price_base = price_import_unit / conversion_factor if conversion_factor else 0
                
                # Công thức Bình quân gia quyền
                old_value = current_stock_base * current_avg_cost
                new_value = qty_base * price_base
                total_stock_new = current_stock_base + qty_base
                
                new_avg_cost = (old_value + new_value) / total_stock_new if total_stock_new > 0 else 0
                
                # Cập nhật bảng Materials
                cursor.execute("UPDATE Materials SET stock_quantity = %s, avg_cost_per_base_unit = %s WHERE material_id = %s", 
                               (total_stock_new, new_avg_cost, mat_id))

        conn.commit()
        
    # 🟢 SỬA LỖI 3: Đổi từ mysql.connector.Error sang Exception chuẩn
    except Exception as err:
        if 'conn' in locals(): conn.rollback()
        print(f"🔴 Lỗi SQL Tạo Phiếu Nhập: {err}")
        return f"Lỗi hệ thống: {err}", 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
    
    # Quay về trang kho hoặc trang chi tiết phiếu nhập (nếu làm)
    return redirect(url_for('materials_page'))

# ======================================================
# QUẢN LÝ ĐỊNH MỨC VẬT TƯ (SERVICE_MATERIALS - BOM)
# ======================================================

@app.route('/service_materials')
@requires_permission('sale', 'inventory') 
def service_materials_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # POSTGRES: Đổi is_active = 1 thành is_active = TRUE
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
        # Ép kiểu float phòng trường hợp Decimal của DB không tự cộng được
        grouped_boms[s_id]['total_cost'] += float(row['estimated_cost'] or 0)

    cursor.close()
    conn.close()
    
    return render_template(SERVICE_MATERIALS_HTML, 
                           services_list=services_list,
                           materials_list=materials_list,
                           grouped_boms=grouped_boms) 

@app.route('/add_service_material', methods=['POST'])
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

            # POSTGRES: RETURNING để lấy ID
            sql = """
                INSERT INTO Service_Materials (service_id, material_id, quantity_consumed, apply_to_unit_level) 
                VALUES (%s, %s, %s, %s) RETURNING service_material_id
            """
            cursor.execute(sql, (service_id, mat_id, float(qty), int(level)))
            last_new_id = cursor.fetchone()['service_material_id']
        
        if last_new_id:
            log_desc = f"Thêm/Cập nhật Công Thức Định Mức (Lần cuối ID {last_new_id})"
            # log_system_action(cursor, 'ADD', 'Service_Materials', log_desc)
            
        conn.commit() 
        
    except Exception as e:
        conn.rollback() 
        print(f"🔴 Lỗi thêm BOM: {e}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('service_materials_page'))

@app.route('/delete_service_material/<int:sm_id>', methods=['POST'])
@requires_permission('all') 
def delete_service_material(sm_id):
    conn = get_db_connection()
    cursor = conn.cursor() # Hàm xóa không cần trả dữ liệu nên để con trỏ mặc định cũng được
    
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
    
    return redirect(url_for('service_materials_page'))

# ======================================================
# QUẢN LÝ ĐIỀU CHỈNH KHO (STOCK ADJUSTMENTS)
# ======================================================

@app.route('/adjustments')
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

@app.route('/add_adjustment', methods=['POST'])
@requires_permission('accounting') 
def add_adjustment():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        material_id = request.form['material_id']
        quantity = int(request.form['quantity_adjusted']) 
        reason = request.form['reason']
        adjustment_date = request.form['adjustment_date']

        # POSTGRES: Thêm RETURNING adjustment_id
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
        
        log_desc = f"Thêm Điều Chỉnh Kho ID {new_id}"
        # log_system_action(cursor, 'ADD', 'Stock_Adjustments', log_desc)
        
        conn.commit() 
        
    except Exception as e: # Đổi từ mysql.connector.Error
        conn.rollback() 
        print(f"🔴 Lỗi Điều chỉnh kho: {e}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('adjustments_page'))

# ======================================================
# QUẢN LÝ PHIẾU ĐIỀU CHỈNH KHO (NHIỀU VẬT TƯ)
# ======================================================

# 1. (GET) Hiển thị trang Tạo Phiếu Điều chỉnh
@app.route('/create_adjustment')
@requires_permission('accounting') # Kế Toán
def create_adjustment_page():
    conn = get_db_connection()
    # 🟢 SỬA LỖI 1: Thay dictionary=True bằng cursor_factory
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Lấy danh sách Vật tư (kèm Tồn kho để hiển thị tham khảo)
    cursor.execute("SELECT material_id, material_name, base_unit, stock_quantity FROM Materials ORDER BY material_name")
    materials_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    today = datetime.date.today().isoformat()
    
    return render_template(CREATE_ADJUSTMENT_INV_HTML, 
                           materials_list=materials_list,
                           today=today)

# 2. (POST) Xử lý Lưu Phiếu Điều chỉnh
@app.route('/submit_adjustment_slip', methods=['POST'])
@requires_permission('accounting') # Kế Toán
def submit_adjustment_slip():
    conn = get_db_connection()
    # Nên dùng RealDictCursor ở đây để lấy ID trả về cho an toàn
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # A. Lấy thông tin chung (Dùng .get() cho an toàn)
        adjustment_date = request.form.get('adjustment_date')
        
        # B. Lấy danh sách chi tiết
        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity_adjusted[]')
        reasons = request.form.getlist('reason[]')
        
        # --- BƯỚC 1: TẠO PHIẾU CHA ---
        # 🟢 SỬA LỖI 2: Dùng RETURNING slip_id thay cho lastrowid
        sql_slip = "INSERT INTO Adjustment_Slips (adjustment_date) VALUES (%s) RETURNING slip_id"
        cursor.execute(sql_slip, (adjustment_date,))
        new_slip_id = cursor.fetchone()['slip_id']

        # --- BƯỚC 2: LẶP QUA TỪNG VẬT TƯ ---
        for i in range(len(material_ids)):
            mat_id = material_ids[i]
            
            # Kiểm tra an toàn: Bỏ qua nếu dòng bị trống (người dùng bấm nhầm thêm dòng)
            if not mat_id or not quantities[i]:
                continue
                
            qty = int(quantities[i]) # Số này có thể âm hoặc dương
            reason = reasons[i]
            
            # 2a. Lưu vào bảng chi tiết
            sql_item = """
                INSERT INTO Adjustment_Slip_Items (slip_id, material_id, quantity_adjusted, reason)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql_item, (new_slip_id, mat_id, qty, reason))
            
            # 2b. CẬP NHẬT KHO (Cộng dồn số lượng)
            sql_update_stock = """
                UPDATE Materials 
                SET stock_quantity = stock_quantity + %s 
                WHERE material_id = %s
            """
            cursor.execute(sql_update_stock, (qty, mat_id))
        
        # == GHI LOG ==
        log_desc = f"Thêm Phiếu Điều Chỉnh Kho ID {new_slip_id}"
        # Nhớ mở comment nếu bạn đã viết lại hàm log_system_action cho Postgres
        # log_system_action(cursor, 'ADD', 'Adjustment_Slips', log_desc) 
        # ===================

        conn.commit()
        
    # 🟢 SỬA LỖI 3: Đổi từ mysql.connector.Error sang Exception chuẩn
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f"🔴 Lỗi SQL Tạo Phiếu Điều Chỉnh: {e}")
        return f"Lỗi hệ thống: {e}", 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
    
    # Quay về trang Vật tư
    return redirect(url_for('materials_page'))

# ======================================================
# BÁO CÁO: CÔNG NỢ KHÁCH HÀNG (AI NỢ MÌNH)
# ======================================================
@app.route('/report/customer_debt')
@requires_permission('accounting', 'sale') # Kế toán và Kinh doanh
def customer_debt_report():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    # 🟢 SỬA LỖI 1: Dùng RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Query: Nhóm tất cả công nợ theo TỪNG KHÁCH HÀNG
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
        HAVING SUM(O.total_amount - O.amount_paid) > 0 -- Ép điều kiện HAVING rõ ràng cho Postgres
        ORDER BY total_due DESC
    """
    cursor.execute(sql)
    debt_list = cursor.fetchall()
    
    # 🟢 CẬP NHẬT: Ép kiểu float() để tránh lỗi Decimal của Postgres và bọc (or 0) phòng khi Null
    total_all_due = sum(float(item['total_due'] or 0) for item in debt_list)
    
    cursor.close()
    conn.close()
    
    return render_template(CUSTOMER_DEBT_REPORT_HTML, # Thay bằng biến hằng số của bạn nếu cần
                           debt_list=debt_list,
                           total_all_due=total_all_due)

# ======================================================
# BÁO CÁO: CHI TIẾT CÔNG NỢ (THEO TỪNG KHÁCH)
# ======================================================
@app.route('/report/customer_debt/<int:customer_id>')
@requires_permission('accounting', 'sale') 
def customer_debt_detail_report(customer_id):
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
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
    
    # 🟢 CẬP NHẬT: Ép kiểu an toàn
    total_due = sum(float(item['amount_due'] or 0) for item in unpaid_orders_list)
    
    cursor.close()
    conn.close()
    
    if not customer_info:
        return "Không tìm thấy khách hàng!", 404
        
    return render_template(CUSTOMER_DEBT_DETAIL_HTML, # Thay bằng biến hằng số của bạn nếu cần
                           customer_info=customer_info,
                           unpaid_orders_list=unpaid_orders_list,
                           total_due=total_due)

# ======================================================
# BÁO CÁO: CÔNG NỢ NHÀ CUNG CẤP (MÌNH NỢ AI)
# ======================================================
@app.route('/report/supplier_debt')
@requires_permission('accounting', 'inventory') 
def supplier_debt_report():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    sql_imports = """
        SELECT 
            S.slip_id AS id, 
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
    
    # 🟢 CẬP NHẬT: Ép kiểu an toàn
    total_all_due = sum(float(item['total_amount'] or 0) for item in all_debts)
    
    cursor.close()
    conn.close()
    
    return render_template(SUPPLIER_DEBT_REPORT, # Thay bằng biến hằng số của bạn nếu cần
                           all_debts=all_debts,
                           total_all_due=total_all_due)

# ======================================================
# BÁO CÁO: XỬ LÝ THANH TOÁN CÔNG NỢ NCC
# ======================================================
@app.route('/pay_supplier_bill', methods=['POST'])
@requires_permission('accounting') 
def pay_supplier_bill():
    conn = get_db_connection()
    cursor = conn.cursor() # Hàm UPDATE không cần trả dữ liệu nên không cần RealDictCursor
    
    try:
        bill_id = request.form['bill_id']
        bill_source = request.form['bill_source']

        table_name = ""
        if bill_source == 'import_slip':
            sql = "UPDATE Import_Slips SET payment_status = 'paid' WHERE slip_id = %s"
            table_name = "Import_Slips"
        elif bill_source == 'maintenance':
            sql = "UPDATE Maintenance_Logs SET payment_status = 'paid' WHERE log_id = %s"
            table_name = "Maintenance_Logs"
        else:
            return "Lỗi: Nguồn công nợ không xác định.", 400

        cursor.execute(sql, (bill_id,))
        
        # 🟢 Ghi log linh hoạt theo table_name
        log_desc = f"Trả tiền NCC Hóa Đơn ID #{bill_id} ({bill_source})."
        # Mở comment nếu đã có hàm này:
        # log_system_action(cursor, 'UPDATE', table_name, log_desc) 
        
        conn.commit()
        
    # 🟢 SỬA LỖI 2: Đổi sang Exception chuẩn
    except Exception as err:
        if 'conn' in locals(): conn.rollback() 
        print(f"🔴 LỖI KHI THANH TOÁN NCC: {err}")
        return f"Đã xảy ra lỗi: {err}", 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
    
    return redirect(url_for('supplier_debt_report'))

# ======================================================
# QUẢN LÝ COUPONS - POSTGRESQL
# ======================================================

@app.route('/coupons')
def coupons_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM Coupons ORDER BY end_date DESC")
    coupons_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template(COUPONS_HTML, coupons_list=coupons_list)

@app.route('/add_coupon', methods=['POST'])
def add_coupon():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = """
            INSERT INTO Coupons (code, discount_type, discount_value, min_order_value, 
                                 start_date, end_date, usage_limit, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
        """
        val = (request.form['code'].upper(), request.form['discount_type'], 
               request.form['discount_value'], request.form['min_order_value'],
               request.form['start_date'], request.form['end_date'], 
               request.form['usage_limit'])
        cur.execute(sql, val)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Lỗi Coupon: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('coupons_page'))

@app.route('/toggle_coupon_status/<int:coupon_id>', methods=['POST'])
def toggle_coupon_status(coupon_id):
    conn = get_db_connection()
    cur = conn.cursor()
    # Logic: CASE WHEN status='active' THEN 'inactive' ELSE 'active' END
    sql = """
        UPDATE Coupons 
        SET status = CASE WHEN status = 'active' THEN 'inactive' ELSE 'active' END 
        WHERE coupon_id = %s
    """
    cur.execute(sql, (coupon_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('coupons_page'))

# ==========================================
# 1. TRANG QUẢN LÝ XƯỞNG VÀ BẢNG GIÁ
# ==========================================
@app.route('/manage_outsource')
@requires_permission('admin', 'sale')
def manage_outsource():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Lấy danh sách xưởng
    cursor.execute("SELECT * FROM Outsource_Partners ORDER BY partner_id DESC")
    partners = cursor.fetchall()
    
    # Lấy toàn bộ danh mục và giá đi kèm
    sql_prices = """
        SELECT C.partner_id, C.category_id, C.category_name, C.type, C.unit, 
               P.price_id, P.item_name, P.min_qty, P.max_qty, P.unit_price
        FROM Outsource_Categories C
        LEFT JOIN Outsource_Prices P ON C.category_id = P.category_id
        ORDER BY C.partner_id, C.type, P.min_qty
    """
    cursor.execute(sql_prices)
    all_prices = cursor.fetchall()
    
    # Nhóm dữ liệu theo partner_id để hiển thị ra HTML dễ hơn
    grouped_data = defaultdict(list)
    for row in all_prices:
        grouped_data[row['partner_id']].append(row)
        
    cursor.close()
    conn.close()
    
    return render_template(MANAGE_OUTSOURCE_HTML, partners=partners, grouped_data=grouped_data)
    
# --- 1. THÊM XƯỞNG GIA CÔNG MỚI ---
@app.route('/add_outsource_partner', methods=['POST'])
@requires_permission('admin', 'sale')
def add_outsource_partner():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        name = request.form['partner_name']
        phone = request.form['phone']
        address = request.form['address']
        cursor.execute("INSERT INTO Outsource_Partners (partner_name, phone, address) VALUES (%s, %s, %s)", (name, phone, address))
        conn.commit()
        flash('Đã thêm xưởng mới thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi thêm xưởng: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('manage_outsource'))

# --- 2. THÊM DANH MỤC CHO XƯỞNG (VD: "Namecard C300", "In nhanh 4 màu") ---
@app.route('/add_outsource_category', methods=['POST'])
@requires_permission('admin', 'sale')
def add_outsource_category():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        partner_id = request.form['partner_id']
        category_name = request.form['category_name']
        type_val = request.form['type']
        unit = request.form['unit']
        
        cursor.execute("""
            INSERT INTO Outsource_Categories (partner_id, category_name, type, unit) 
            VALUES (%s, %s, %s, %s)
        """, (partner_id, category_name, type_val, unit))
        conn.commit()
        flash('Đã tạo danh mục dịch vụ mới!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi tạo danh mục: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('manage_outsource'))

# --- 3. THÊM MỐC GIÁ (HỖ TRỢ GIÁ BẬC THANG) ---
@app.route('/add_outsource_price', methods=['POST'])
@requires_permission('admin', 'sale')
def add_outsource_price():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        category_id = request.form['category_id']
        item_name = request.form['item_name']
        min_qty = int(request.form['min_qty'] or 1)
        max_qty = int(request.form['max_qty'] or 999999)
        unit_price = float(request.form['unit_price'])
        
        cursor.execute("""
            INSERT INTO Outsource_Prices (category_id, item_name, min_qty, max_qty, unit_price) 
            VALUES (%s, %s, %s, %s, %s)
        """, (category_id, item_name, min_qty, max_qty, unit_price))
        conn.commit()
        flash('Đã thêm mốc giá thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi thêm giá: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('manage_outsource'))

# --- 4. CẬP NHẬT CHỈNH SỬA DANH MỤC ---
@app.route('/edit_outsource_category', methods=['POST'])
@requires_permission('admin', 'sale')
def edit_outsource_category():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cat_id = request.form['category_id']
        cat_name = request.form['category_name']
        cat_type = request.form['type']
        unit = request.form['unit']
        
        cursor.execute("""
            UPDATE Outsource_Categories 
            SET category_name = %s, type = %s, unit = %s 
            WHERE category_id = %s
        """, (cat_name, cat_type, unit, cat_id))
        conn.commit()
        flash('Đã cập nhật danh mục!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi cập nhật danh mục: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('manage_outsource'))

# --- 5. CẬP NHẬT CHỈNH SỬA MỐC GIÁ ---
@app.route('/edit_outsource_price', methods=['POST'])
@requires_permission('admin', 'sale')
def edit_outsource_price():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        price_id = request.form['price_id']
        item_name = request.form['item_name']
        min_qty = int(request.form['min_qty'] or 1)
        max_qty = int(request.form['max_qty'] or 999999)
        unit_price = float(request.form['unit_price'])
        
        cursor.execute("""
            UPDATE Outsource_Prices 
            SET item_name = %s, min_qty = %s, max_qty = %s, unit_price = %s 
            WHERE price_id = %s
        """, (item_name, min_qty, max_qty, unit_price, price_id))
        conn.commit()
        flash('Đã cập nhật mốc giá!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi cập nhật mốc giá: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('manage_outsource'))

# ==========================================
# 2. API LẤY BẢNG GIÁ KHI CHỌN XƯỞNG (DÙNG CHO TẠO ĐƠN HÀNG)
# ==========================================
@app.route('/api/get_partner_prices/<int:partner_id>')
@requires_permission('sale')
def api_get_partner_prices(partner_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT C.category_id, C.category_name, C.type, C.unit, 
               P.price_id, P.item_name, P.min_qty, P.max_qty, CAST(P.unit_price AS FLOAT) as unit_price
        FROM Outsource_Categories C
        JOIN Outsource_Prices P ON C.category_id = P.category_id
        WHERE C.partner_id = %s
        ORDER BY C.type, P.min_qty
    """, (partner_id,))
    
    prices = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success', 'data': prices})

# ======================================================
# AJAX (GIAO TIẾP NGẦM) - POSTGRESQL
# ======================================================

# 1. AJAX - Thêm nhanh Khách hàng (SỬA LỖI 0 DỨT ĐIỂM)
@app.route('/ajax/add_customer', methods=['POST'])
@requires_permission('accounting', 'sale')
def ajax_add_customer():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Lấy dữ liệu an toàn
        name = request.form.get('customer_name')
        phone = request.form.get('phone', '')
        
        if not name:
            return jsonify({'success': False, 'error': 'Tên khách hàng là bắt buộc!'})
        
        # INSERT và RETURNING
        sql = "INSERT INTO Customers (customer_name, phone, is_active) VALUES (%s, %s, TRUE) RETURNING customer_id"
        cur.execute(sql, (name, phone))
        
        # SỬA LỖI 0 Ở ĐÂY: Viết code tương thích với mọi loại Cursor
        new_row = cur.fetchone()
        
        if new_row:
            try:
                # Nếu database trả về Dictionary -> Lấy bằng tên cột
                new_id = new_row['customer_id']
            except (TypeError, KeyError, IndexError):
                # Nếu database trả về Tuple mặc định -> Lấy bằng vị trí 0
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
        # In lỗi chi tiết ra console
        print(f"🔴 Lỗi AJAX Customer: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()

# 2. AJAX - Thêm nhanh Dịch vụ (Dùng trong trang Tạo đơn/Báo giá)
@app.route('/ajax/add_service', methods=['POST'])
@requires_permission('sale', 'inventory')
def ajax_add_service():
    conn = get_db_connection()
    # Bắt buộc dùng RealDictCursor để lấy ID bằng RETURNING
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        service_name = request.form.get('service_name')
        base_price = float(request.form.get('base_price', 0))
        unit = request.form.get('unit')
        unit_level2 = request.form.get('unit_level2')
        unit_level3 = request.form.get('unit_level3')
        
        # INSERT và lấy ra ID của dịch vụ vừa tạo
        sql = """
            INSERT INTO Services (service_name, base_price, unit, unit_level2, unit_level3, is_active) 
            VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING service_id
        """
        cursor.execute(sql, (service_name, base_price, unit, unit_level2, unit_level3))
        new_id = cursor.fetchone()['service_id']
        conn.commit()
        
        # Trả về JSON đúng chuẩn cho Javascript
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

# 3. AJAX - Thêm nhanh Vật tư (Dùng trong trang Định mức/Kho)
@app.route('/ajax/add_material', methods=['POST'])
@requires_permission('sale', 'inventory')
def ajax_add_material():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        name = request.form['material_name']
        base_unit = request.form['base_unit']
        import_unit = request.form['import_unit']
        # Lưu ý: Database Postgres dùng cột 'import_conversion_factor'
        conversion_factor = float(request.form['import_conversion_factor'])
        
        # POSTGRES: RETURNING material_id
        sql = """
            INSERT INTO Materials (material_name, material_type, base_unit, import_unit, 
                                   import_conversion_factor, stock_quantity) 
            VALUES (%s, 'production', %s, %s, %s, 0)
            RETURNING material_id
        """
        cur.execute(sql, (name, base_unit, import_unit, conversion_factor))
        new_id = cur.fetchone()[0]
        
        # log_system_action(cur, 'QUICK ADD', 'Materials', f"Thêm nhanh VT ID {new_id}")
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name,
            'new_import_unit': import_unit
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Lỗi AJAX Material: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()

# 4. AJAX - Thêm nhanh Nhà cung cấp (Dùng trong trang Nhập kho/Thiết bị)
@app.route('/ajax/add_supplier', methods=['POST'])
@requires_permission('accounting', 'inventory')
def ajax_add_supplier():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Lấy dữ liệu an toàn bằng .get() để tránh lỗi KeyError nếu bỏ trống form
        name = request.form.get('supplier_name')
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        
        if not name:
            return jsonify({'success': False, 'error': 'Tên nhà cung cấp là bắt buộc!'})
        
        # POSTGRES: Thêm is_active=TRUE cho chuẩn với Database mới
        sql = "INSERT INTO Suppliers (supplier_name, phone, email, is_active) VALUES (%s, %s, %s, TRUE) RETURNING supplier_id"
        cur.execute(sql, (name, phone, email))
        
        # SỬA LỖI 0 DỨT ĐIỂM Ở ĐÂY
        new_row = cur.fetchone()
        
        if new_row:
            try:
                # Cố gắng lấy theo tên cột (nếu dùng RealDictCursor)
                new_id = new_row['supplier_id']
            except (TypeError, KeyError, IndexError):
                # Nếu không được thì lấy theo vị trí số 0 (nếu dùng Tuple bình thường)
                new_id = new_row[0]
        else:
            raise Exception("Không lấy được ID mới từ Database")
        
        # Ghi log (Tạm bỏ qua hoặc mở comment nếu đã có hàm log)
        # log_system_action(cur, 'QUICK ADD', 'Suppliers', f"Thêm nhanh NCC ID {new_id}")
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name
        })
        
    except Exception as e:
        conn.rollback()
        # In rõ tên lỗi ra màn hình đen để dễ bắt bệnh hơn
        print(f"🔴 Lỗi AJAX Supplier: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()

# 5. API KIỂM TRA MÃ KHUYẾN MÃI (Check Coupon)
@app.route('/ajax/check_coupon', methods=['POST'])
@requires_permission('sale')
def check_coupon():
    conn = get_db_connection()
    # Dùng RealDictCursor để lấy dữ liệu dạng {key: value}
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        code = request.form['code'].upper()
        order_total = float(request.form['order_total'])
        today = datetime.date.today()
        
        # 1. Tìm mã trong DB
        sql = "SELECT * FROM Coupons WHERE code = %s AND status = 'active'"
        cur.execute(sql, (code,))
        coupon = cur.fetchone()
        
        if not coupon:
            return jsonify({'valid': False, 'message': 'Mã không tồn tại hoặc đã bị tắt.'})
        
        # 2. Kiểm tra điều kiện
        # Postgres trả về kiểu Date object, so sánh trực tiếp với datetime.date.today() được
        if coupon['start_date'] > today or coupon['end_date'] < today:
            return jsonify({'valid': False, 'message': 'Mã chưa đến hạn hoặc đã hết hạn.'})
            
        # Chuyển đổi Decimal sang float để so sánh (Postgres trả về Decimal cho cột tiền tệ)
        min_val = float(coupon['min_order_value'])
        if order_total < min_val:
            return jsonify({'valid': False, 'message': f'Đơn hàng phải từ {min_val:,.0f} trở lên.'})
            
        if coupon['usage_limit'] > 0 and coupon['used_count'] >= coupon['usage_limit']:
            return jsonify({'valid': False, 'message': 'Mã đã hết lượt sử dụng.'})
        
        # 3. Tính toán số tiền giảm
        discount_amount = 0
        disc_val = float(coupon['discount_value'])
        
        if coupon['discount_type'] == 'fixed':
            discount_amount = disc_val
        else:
            discount_amount = order_total * (disc_val / 100)
            
        # Không giảm quá giá trị đơn hàng
        if discount_amount > order_total:
            discount_amount = order_total

        return jsonify({
            'valid': True,
            'message': 'Áp dụng thành công!',
            'discount_amount': discount_amount,
            'code': code
        })
        
    except Exception as e:
        print(f"Lỗi Check Coupon: {e}")
        return jsonify({'valid': False, 'message': f'Lỗi hệ thống: {str(e)}'})
    finally:
        cur.close()
        conn.close()
        
# 6. AJAX Thêm thiết bị nhanh (Dùng cho nút + ở trang Tạo đơn)
@app.route('/ajax_add_equipment', methods=['POST'])
@login_required
def ajax_add_equipment():
    try:
        name = request.form.get('equipment_name')
        if not name:
            return jsonify({'success': False, 'error': 'Tên thiết bị là bắt buộc!'})

        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = """
            INSERT INTO Equipment (equipment_name, status, is_active)
            VALUES (%s, 'active', TRUE)
            RETURNING equipment_id
        """
        cur.execute(sql, (name,))
        new_id = cur.fetchone()['equipment_id']
        conn.commit()
        conn.close()

        return jsonify({
            'success': True, 
            'new_id': new_id, 
            'new_name': name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Route mặc định (chuyển thẳng đến trang services)
@app.route('/')
def index():
    return redirect(url_for('dashboard_page'))

if __name__ == '__main__':
    app.run(debug=True)
