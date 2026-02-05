# app.py
from flask import Flask, request, render_template, redirect, url_for
import mysql.connector
# Dùng thư viện 'datetime' để lấy ngày hôm nay
import datetime

# các thư viện hỗ trợ xử lý file CSV
import csv
import io
import math
from flask import Response, make_response # Để trả về file CSV

from flask import Flask, request, render_template, redirect, url_for, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json # Để xử lý quyền hạn

from functools import wraps # Thêm thư viện này để tạo decorator
from flask import abort # Để trả về lỗi 403 (Cấm truy cập)

from flask import jsonify # Nhớ import 'jsonify' ở đầu tệp

# KHAI BÁO LINK FILE
SERVICES_HTML = "HHDV/services.html"
EDIT_SERVICE_HTML = "HHDV/edit_service.html"
CUSTOMERS_HTML = "HHKH/customers.html"
EDIT_CUSTOMER_HTML = "HHKH/edit_customer.html"
CUSTOMER_DEBT_REPORT_HTML = "HHKH/customer_debt_report.html"
CUSTOMER_DEBT_DETAIL_HTML = "HHKH/customer_debt_detail.html"
MATERIALS_HTML = "HHVT/materials.html" 
EDIT_MATERIAL_HTML = "HHVT/edit_material.html"
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
CREATE_IMPORT_HTML = "HHKO/create_import.html"
CREATE_ADJUSTMENT_INV_HTML = "HHKO/create_adjustment.html"
COUPONS_HTML = "HHKM/coupons.html"
LOGIN_HTML = "HHBM/login.html"
MANAGE_USERS_HTML = "HHBM/manage_users.html"
SYSTEM_LOG_HTML = "HHBM/system_logs.html"

# Cấu hình kết nối Database
# !!! THAY ĐỔI CÁC GIÁ TRỊ NÀY !!!
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root', # Thường là 'root' trên XAMPP
    'password': '', # Mật khẩu MySQL của bạn (nếu có)
    'database': 'db_hoahongvl_cs2' # Tên database bạn đã tạo
}

# Hàm để kết nối đến DB
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Lỗi kết nối: {err}")
        return None

# Khởi tạo ứng dụng Flask
app = Flask(__name__)

app.secret_key = 'chuoi_bi_mat_sieu_kho_doan' # BẮT BUỘC CÓ để chạy session

# --- CẤU HÌNH FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page' # Nếu chưa đăng nhập, tự chuyển về trang này

# --- CLASS USER (MÔ HÌNH NGƯỜI DÙNG) ---
class User(UserMixin):
    def __init__(self, id, username, full_name, role_name, permissions):
        self.id = id
        self.username = username
        self.full_name = full_name
        self.role_name = role_name
        self.permissions = permissions # List các quyền

    # Hàm kiểm tra quyền: user.can('sales')
    def can(self, perm):
        if 'all' in self.permissions: return True # Admin chấp hết
        return perm in self.permissions

# --- HÀM LOAD USER (FLASK-LOGIN CẦN HÀM NÀY) ---
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Join bảng Users và Roles để lấy quyền
    sql = """
        SELECT U.*, R.role_name, R.permissions 
        FROM Users U 
        JOIN Roles R ON U.role_id = R.role_id 
        WHERE U.user_id = %s
    """
    cursor.execute(sql, (user_id,))
    user_data = cursor.fetchone()
    
    # == THÊM DÒNG NÀY ==
    #log_desc = f"Đăng nhập User ID #{user_id}"
    #log_system_action(cursor, 'LOAD', 'Users', log_desc)
    # ===================
    
    conn.close()
    
    if user_data:
        # Chuyển chuỗi JSON permissions thành List Python
        perms = json.loads(user_data['permissions']) if user_data['permissions'] else []
        return User(user_data['user_id'], user_data['username'], 
                    user_data['full_name'], user_data['role_name'], perms)
    return None

# -- Audit log (Nhật ký hệ thống)
def log_system_action(cursor, action_type, target_module, description):
    """
    Hàm hỗ trợ ghi log hệ thống.
    Lưu ý: Hàm này nhận vào 'cursor' đang mở của transaction hiện tại
    để đảm bảo log chỉ được lưu khi giao dịch thành công.
    """
    if not current_user.is_authenticated:
        user_id = None # Hoặc ID của user hệ thống/khách
    else:
        user_id = current_user.id
        
    ip_address = request.remote_addr
    device_info = request.user_agent.string # Lấy thông tin trình duyệt/OS
    
    sql = """
        INSERT INTO System_Logs (user_id, action_type, target_module, description, ip_address, device_info)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (user_id, action_type, target_module, description, ip_address, device_info))

# === BƯỚC 1: THÊM 3 DÒNG NÀY ===
# "Dạy" Python cách định dạng tiền tệ
def format_currency(value):
    # 'f"{value:,.0f}"' là một f-string đặc biệt của Python
    # : ,   -> Thêm dấu phẩy (,) ngăn cách hàng nghìn
    # : .0f -> Làm tròn đến 0 chữ số thập phân (vì tiền Việt không dùng số lẻ)
    return f"{value:,.0f}"

# Đăng ký hàm này với Jinja (hệ thống template của Flask)
# Giờ đây bạn có thể dùng {{ ten_bien | currency }} trong HTML
app.jinja_env.filters['currency'] = format_currency
# === KẾT THÚC BƯỚC 1 ===

# --- Định nghĩa các Route (Tuyến đường) ---

# ======================================================
# QUẢN LÝ BẢO MẬT (Securities) - CRUD
# ======================================================
# 1. Trang Đăng nhập
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Users WHERE username = %s", (username,))
        user_data = cursor.fetchone()
        if user_data and check_password_hash(user_data['password_hash'], password):
            # 1. Thực hiện đăng nhập
            user_obj = load_user(user_data['user_id'])
            login_user(user_obj)
            
            # === 2. GHI LOG ĐĂNG NHẬP (MỚI) ===
            try:
                ip_address = request.remote_addr
                device_info = request.user_agent.string
                
                sql_log = """
                    INSERT INTO System_Logs (user_id, action_type, target_module, description, ip_address, device_info)
                    VALUES (%s, 'LOGIN', 'Auth', 'Đăng nhập vào hệ thống', %s, %s)
                """
                # Sử dụng lại cursor đang mở
                cursor.execute(sql_log, (user_data['user_id'], ip_address, device_info))
                conn.commit() # Lưu log
            except Exception as e:
                print(f"Lỗi ghi log login: {e}")
            # ==================================

            cursor.close()
            conn.close() # Đóng kết nối tại đây
            
            return redirect(url_for('dashboard_page'))
        else:
            cursor.close()
            conn.close() # Đóng kết nối nếu login sai
            flash('Sai tên đăng nhập hoặc mật khẩu!', 'danger')
            
    return render_template(LOGIN_HTML)

# --- HÀM TẠO Ổ KHÓA (DECORATOR NÂNG CẤP) ---
# Bây giờ nó chấp nhận nhiều quyền: @requires_permission('sale', 'inventory')
def requires_permission(*permissions):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Kiểm tra đăng nhập
            if not current_user.is_authenticated:
                return redirect(url_for('login_page'))
            
            # 2. Kiểm tra quyền Admin tối cao
            if current_user.can('all'):
                return f(*args, **kwargs)

            # 3. Kiểm tra: Người dùng có ÍT NHẤT 1 trong các quyền được yêu cầu không?
            # Ví dụ: trang yêu cầu ('sale', 'inventory'). User có 'sale' -> Cho qua.
            has_access = False
            for perm in permissions:
                if current_user.can(perm):
                    has_access = True
                    break
            
            if not has_access:
                return "BẠN KHÔNG CÓ QUYỀN TRUY CẬP TRANG NÀY!", 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 2. Đăng xuất
@app.route('/logout')
@login_required
def logout():
    # === 1. GHI LOG ĐĂNG XUẤT TRƯỚC (MỚI) ===
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        user_id = current_user.id
        ip_address = request.remote_addr
        device_info = request.user_agent.string
        
        sql_log = """
            INSERT INTO System_Logs (user_id, action_type, target_module, description, ip_address, device_info)
            VALUES (%s, 'LOGOUT', 'Auth', 'Đăng xuất khỏi hệ thống', %s, %s)
        """
        cursor.execute(sql_log, (user_id, ip_address, device_info))
        conn.commit()
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Lỗi ghi log logout: {e}")
    # ========================================
    
    logout_user()
    return redirect(url_for('login_page'))

# 3. SETUP ADMIN ĐẦU TIÊN (CHẠY 1 LẦN RỒI XÓA)
@app.route('/setup_admin')
def setup_admin():
    # Tạo user: admin / pass: 123456
    hashed_pw = generate_password_hash('123456')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Giả sử Role ID 1 là Admin (đã tạo ở bước SQL)
        sql = "INSERT INTO Users (username, password_hash, full_name, role_id) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, ('admin', hashed_pw, 'Super Admin', 1))
        conn.commit()
        return "Tạo Admin thành công! Hãy vào /login"
    except Exception as e:
        return f"Lỗi (có thể đã tồn tại): {e}"
    finally:
        conn.close()

@app.route('/system_logs')
@requires_permission('all') # Chỉ Admin được xem
def system_logs_page():
    conn = get_db_connection()
    if conn is None: return "Lỗi kết nối DB", 500
    cursor = conn.cursor(dictionary=True)
    
    # 1. Lấy tham số từ URL
    page = request.args.get('page', 1, type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    action = request.args.get('action') # 'view' hoặc 'export'
    
    items_per_page = 50
    offset = (page - 1) * items_per_page
    
    # 2. Xây dựng câu SQL cơ bản (Base Query)
    # Chúng ta dùng danh sách params để tránh SQL Injection
    where_clauses = ["1=1"]
    params = []
    
    if start_date:
        where_clauses.append("DATE(L.created_at) >= %s")
        params.append(start_date)
        
    if end_date:
        where_clauses.append("DATE(L.created_at) <= %s")
        params.append(end_date)
        
    where_sql = " AND ".join(where_clauses)
    
    # --- TRƯỜNG HỢP 1: XUẤT CSV (Không phân trang) ---
    if action == 'export':
        sql_export = f"""
            SELECT L.created_at, U.username, U.full_name, L.action_type, 
                   L.target_module, L.description, L.ip_address
            FROM System_Logs L
            LEFT JOIN Users U ON L.user_id = U.user_id
            WHERE {where_sql}
            ORDER BY L.created_at DESC
        """
        cursor.execute(sql_export, tuple(params))
        all_logs = cursor.fetchall()
        conn.close()
        
        # Tạo file CSV trong bộ nhớ
        si = io.StringIO()
        cw = csv.writer(si)
        # Ghi tiêu đề (Thêm BOM \ufeff để Excel mở tiếng Việt không lỗi)
        si.write('\ufeff') 
        cw.writerow(['Thời gian', 'User', 'Họ tên', 'Hành động', 'Module', 'Chi tiết', 'IP'])
        
        for log in all_logs:
            cw.writerow([
                log['created_at'], log['username'], log['full_name'], 
                log['action_type'], log['target_module'], log['description'], log['ip_address']
            ])
            
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=system_logs.csv"
        output.headers["Content-type"] = "text/csv"
        return output

    # --- TRƯỜNG HỢP 2: XEM TRÊN WEB (Có phân trang) ---
    
    # Bước A: Đếm tổng số bản ghi (để tính số trang)
    sql_count = f"SELECT COUNT(*) as total FROM System_Logs L WHERE {where_sql}"
    cursor.execute(sql_count, tuple(params))
    total_records = cursor.fetchone()['total']
    total_pages = math.ceil(total_records / items_per_page)
    
    # Bước B: Lấy dữ liệu trang hiện tại
    sql_data = f"""
        SELECT L.*, U.username, U.full_name 
        FROM System_Logs L
        LEFT JOIN Users U ON L.user_id = U.user_id
        WHERE {where_sql}
        ORDER BY L.created_at DESC
        LIMIT %s OFFSET %s
    """
    # Thêm limit/offset vào params
    params.extend([items_per_page, offset])
    
    cursor.execute(sql_data, tuple(params))
    logs_list = cursor.fetchall()
    
    conn.close()
    
    return render_template(SYSTEM_LOG_HTML, 
                           logs_list=logs_list,
                           current_page=page,
                           total_pages=total_pages,
                           start_date=start_date,
                           end_date=end_date,
                           total_records=total_records)


@app.route('/clear_system_logs', methods=['POST'])
@requires_permission('all')
def clear_system_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        # Kiểm tra dữ liệu đầu vào
        if not start_date or not end_date:
            conn.close()
            return "Vui lòng chọn khoảng thời gian để xóa log!", 400
            
        # --- BƯỚC 1: XÓA LOG CŨ ---
        # Lưu ý: Chúng ta xóa dựa trên ngày tạo
        sql_delete = "DELETE FROM System_Logs WHERE DATE(created_at) >= %s AND DATE(created_at) <= %s"
        cursor.execute(sql_delete, (start_date, end_date))
        
        # Lấy số lượng dòng vừa bị xóa
        rows_deleted = cursor.rowcount
        
        # --- BƯỚC 2: GHI LOG VỀ HÀNH ĐỘNG XÓA (QUAN TRỌNG) ---
        # Chỉ ghi log nếu thực sự có dữ liệu bị xóa
        if rows_deleted > 0:
            description = f"Đã XÓA VĨNH VIỄN {rows_deleted} dòng nhật ký từ ngày {start_date} đến {end_date}"
            
            # Gọi hàm log_system_action (Hàm này chúng ta đã viết ở bài trước)
            # Hàm này sẽ INSERT một dòng mới với thời gian hiện tại (NOW)
            # Vì NOW > end_date (thường là vậy), nên dòng log này sẽ KHÔNG bị xóa bởi lệnh DELETE ở trên
            log_system_action(cursor, 'DELETE', 'System_Logs', description)
            
        conn.commit()
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Lỗi khi xóa log: {err}")
        return f"Lỗi Database: {err}", 500
    finally:
        cursor.close()
        conn.close()
    
    # Quay lại trang log
    return redirect(url_for('system_logs_page'))

# ======================================================
# QUẢN LÝ NGƯỜI DÙNG (USERS) - CRUD
# ======================================================
@app.route('/manage_users')
@requires_permission('all', 'hr') # (Lưu ý: trong SQL role Admin phải có quyền này hoặc 'all', nhân sự)
def manage_users_page():
    # Kiểm tra quyền Admin
    if not current_user.can('admin_users'): return "Bạn không có quyền truy cập!", 403
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Lấy danh sách Users
    cursor.execute("SELECT U.*, R.role_name FROM Users U JOIN Roles R ON U.role_id = R.role_id")
    users = cursor.fetchall()
    
    # Lấy danh sách Roles
    cursor.execute("SELECT * FROM Roles")
    roles = cursor.fetchall()
    
    conn.close()
    return render_template(MANAGE_USERS_HTML, users=users, roles=roles)

@app.route('/add_user', methods=['POST'])
@requires_permission('all', 'hr') # (Lưu ý: trong SQL role Admin phải có quyền này hoặc 'all', nhân sự)
def add_user():
    if not current_user.can('admin_users'): return "Access Denied", 403
    
    username = request.form['username']
    password = request.form['password']
    full_name = request.form['full_name']
    role_id = request.form['role_id']
    
    # Mã hóa mật khẩu
    hashed_pw = generate_password_hash(password)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Users (username, password_hash, full_name, role_id) VALUES (%s, %s, %s, %s)", 
                   (username, hashed_pw, full_name, role_id))
    
    # == THÊM DÒNG NÀY ==
    log_desc = f"Tạo User ID #{cursor.lastrowid}"
    log_system_action(cursor, 'CREATE', 'Users', log_desc)
    # ===================
    
    conn.commit()
    conn.close()
    return redirect(url_for('manage_users_page'))

# ======================================================
# QUẢN LÝ DỊCH VỤ (SERVICES) - CRUD
# ======================================================
# 1. Route để HIỂN THỊ danh sách dịch vụ VÀ form thêm mới
@app.route('/services')
@requires_permission('sale', 'inventory') # Kinh Doanh
def services_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True) # dictionary=True để trả về kết quả dạng {tên_cột: giá_trị}
    
    # Lấy (SELECT) tất cả dịch vụ
    cursor.execute("SELECT * FROM Services ORDER BY service_id DESC")
    services_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Gửi danh sách services_list ra tệp HTML
    return render_template(SERVICES_HTML, services_list=services_list)

# 2. Route để XỬ LÝ việc thêm dịch vụ mới (nhận dữ liệu từ form)
@app.route('/add_service', methods=['POST'])
@requires_permission('sale', 'inventory') # Kinh Doanh và kho
def add_service():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Lấy dữ liệu được gửi từ form HTML
    name = request.form['service_name']
    price = request.form['base_price']
    description = request.form['description']
    
    # Lấy 3 tầng đơn vị
    u1 = request.form['unit'] # Tầng 1 (Bắt buộc)
    u2 = request.form.get('unit_level2') # Tầng 2 (Tùy chọn)
    u3 = request.form.get('unit_level3') # Tầng 3 (Tùy chọn)
    
    # Xử lý rỗng
    if not u2 or u2.strip() == '': u2 = None
    if not u3 or u3.strip() == '': u3 = None

    sql = """
        INSERT INTO Services (service_name, base_price, description, unit, unit_level2, unit_level3) 
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (name, price, description, u1, u2, u3))
    conn.commit()
    
    cursor.close()
    conn.close()
    return redirect(url_for('services_page'))

# 3. Route để XỬ LÝ việc XÓA một dịch vụ
@app.route('/delete_service/<int:service_id>', methods=['POST'])
@requires_permission('all') # admin
def delete_service(service_id):
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor()
    
    # Lệnh SQL DELETE
    sql = "DELETE FROM Services WHERE service_id = %s"
    val = (service_id,)
    
    cursor.execute(sql, val)
    conn.commit() # Lưu thay đổi
    
    cursor.close()
    conn.close()
    
    # Chuyển hướng về trang danh sách
    return redirect(url_for('services_page'))

# 4. Route để HIỂN THỊ form sửa (Bước Sửa 1 - GET)
@app.route('/edit_service/<int:service_id>')
@requires_permission('sale') # Kinh Doanh
def edit_service_page(service_id):
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Lấy thông tin của CHỈ 1 dịch vụ
    sql = "SELECT * FROM Services WHERE service_id = %s"
    val = (service_id,)
    
    cursor.execute(sql, val)
    service_data = cursor.fetchone() # fetchone() để lấy 1 hàng
    
    cursor.close()
    conn.close()
    
    if service_data:
        # Gửi dữ liệu của dịch vụ đó ra tệp edit_service.html
        return render_template(EDIT_SERVICE_HTML, service=service_data)
    else:
        return "Không tìm thấy dịch vụ!", 404

# 5. Route để XỬ LÝ dữ liệu Sửa (Bước Sửa 2 - POST)
@app.route('/update_service', methods=['POST'])
@requires_permission('sale') # Kinh Doanh
def update_service():
    # Lấy dữ liệu từ form
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
    cursor = conn.cursor()
    
    sql = """
        UPDATE Services 
        SET service_name=%s, base_price=%s, description=%s, 
            unit=%s, unit_level2=%s, unit_level3=%s
        WHERE service_id=%s
    """
    cursor.execute(sql, (name, price, description, u1, u2, u3, service_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('services_page'))

# 6. Thay the delete để bảo toàn dữ liệu
@app.route('/toggle_service/<int:id>', methods=['POST'])
@requires_permission('all') # admin
def toggle_service(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Logic: Đảo ngược trạng thái (Nếu đang 1 thành 0, đang 0 thành 1)
    cursor.execute("UPDATE Services SET is_active = NOT is_active WHERE service_id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('services_page'))

# ======================================================
# QUẢN LÝ KHÁCH HÀNG (CUSTOMERS) - CRUD
# ======================================================

# 1. (R)ead - Hiển thị danh sách khách hàng VÀ form thêm mới
@app.route('/customers')
@requires_permission('sale') # Kinh Doanh
def customers_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Customers ORDER BY customer_id DESC")
    customers_list = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template(CUSTOMERS_HTML, customers_list=customers_list)

# 2. (C)reate - Xử lý thêm khách hàng mới
@app.route('/add_customer', methods=['POST'])
@requires_permission('sale') # Kinh Doanh
def add_customer():
    # Lấy dữ liệu từ form
    customer_name = request.form['customer_name']
    phone = request.form['phone']
    email = request.form['email']
    address = request.form['address']
    company_name = request.form['company_name']
    tax_id = request.form['tax_id']
    billing_address = request.form['billing_address']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = "INSERT INTO Customers (customer_name, phone, email, address, company_name, tax_id, billing_address) VALUES (%s, %s, %s, %s)"
    val = (customer_name, phone, email, address, company_name, tax_id, billing_address)
    
    cursor.execute(sql, val)
    
    # == THÊM DÒNG NÀY ==
    log_desc = f"Thêm Khách Hàng ID {cursor.lastrowid}"
    log_system_action(cursor, 'ADD', 'Customers', log_desc)
    # ===================
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('customers_page'))

# 3. (D)elete - Xử lý xóa khách hàng
@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
@requires_permission('all') # admin
def delete_customer(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = "DELETE FROM Customers WHERE customer_id = %s"
    val = (customer_id,)
    
    cursor.execute(sql, val)
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('customers_page'))

# 4. (U)pdate - Hiển thị form sửa khách hàng (GET)
@app.route('/edit_customer/<int:customer_id>')
@requires_permission('sale') # Kinh Doanh
def edit_customer_page(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = "SELECT * FROM Customers WHERE customer_id = %s"
    val = (customer_id,)
    
    cursor.execute(sql, val)
    customer_data = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if customer_data:
        return render_template(EDIT_CUSTOMER_HTML, customer=customer_data)
    else:
        return "Không tìm thấy khách hàng!", 404

# 5. (U)pdate - Xử lý cập nhật khách hàng (POST)
@app.route('/update_customer', methods=['POST'])
@requires_permission('sale') # Kinh Doanh
def update_customer():
    # Lấy dữ liệu từ form
    customer_id = request.form['customer_id']
    customer_name = request.form['customer_name']
    phone = request.form['phone']
    email = request.form['email']
    address = request.form['address']
    company_name = request.form['company_name']
    tax_id = request.form['tax_id']
    billing_address = request.form['billing_address']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = """
        UPDATE Customers 
        SET customer_name = %s, phone = %s, email = %s, address = %s, company_name = %s, tax_id = %s, billing_address = %s
        WHERE customer_id = %s
    """
    val = (customer_name, phone, email, address, customer_id, company_name, tax_id, billing_address)
    
    cursor.execute(sql, val)
    
    # == THÊM DÒNG NÀY ==
    log_desc = f"Cập nhật thông tin Khách hàng ID {customer_id}"
    log_system_action(cursor, 'UPDATE', 'Customers', log_desc)
    # ===================
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('customers_page'))

# 6. Thay the delete để bảo toàn dữ liệu
@app.route('/toggle_customer/<int:id>', methods=['POST'])
@requires_permission('all') # admin
def toggle_customer(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Customers SET is_active = NOT is_active WHERE customer_id = %s", (id,))
    
    # == THÊM DÒNG NÀY ==
    log_desc = f"Khóa thông tin Khách hàng ID {id}"
    log_system_action(cursor, 'TOGGLE', 'Customers', log_desc)
    # ===================
    
    conn.commit()
    conn.close()
    return redirect(url_for('customers_page'))
    
# ======================================================
# QUẢN LÝ VẬT TƯ (MATERIALS) - CRUD
# ======================================================

# 1. (R)ead - Hiển thị danh sách vật tư
@app.route('/materials')
@requires_permission('inventory') # KHO
def materials_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Materials ORDER BY material_id DESC")
    materials_list = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template(MATERIALS_HTML, materials_list=materials_list)

# 2. (C)reate - Xử lý thêm vật tư mới (ĐÃ Nâng cấp Vòng đời)
@app.route('/add_material', methods=['POST'])
@requires_permission('inventory') # KHO
def add_material():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Lấy dữ liệu từ form (thêm các trường mới)
    material_name = request.form['material_name']
    material_type = request.form['material_type'] # <--- TRƯỜNG MỚI
    lifespan_prints = request.form['lifespan_prints'] if material_type == 'maintenance' else 0 # <--- TRƯỜNG MỚI
    base_unit = request.form['base_unit']
    import_unit = request.form['import_unit']
    import_conversion_factor = request.form['import_conversion_factor']
    stock_quantity = request.form['stock_quantity'] 
    
    sql = """
        INSERT INTO Materials (material_name, material_type, lifespan_prints, base_unit, import_unit, import_conversion_factor, stock_quantity) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    val = (material_name, material_type, lifespan_prints, base_unit, import_unit, import_conversion_factor, stock_quantity)
    
    cursor.execute(sql, val)
    
    # == THÊM DÒNG NÀY ==
    log_desc = f"Thêm Vật Tư ID {cursor.lastrowid}"
    log_system_action(cursor, 'ADD', 'Materials', log_desc)
    # ===================
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('materials_page'))

# 3. (D)elete - Xử lý xóa vật tư
@app.route('/delete_material/<int:material_id>', methods=['POST'])
@requires_permission('all') # admin
def delete_material(material_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # !!! CẨN THẬN: Trước khi xóa vật tư, bạn cần xóa các
    # bản ghi liên quan trong Material_Imports trước.
    # Tạm thời chúng ta sẽ bỏ qua bước kiểm tra này để giữ code đơn giản.
    
    sql = "DELETE FROM Materials WHERE material_id = %s"
    val = (material_id,)
    
    cursor.execute(sql, val)
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('materials_page'))

# 4. (U)pdate - Hiển thị form sửa vật tư (GET)
@app.route('/edit_material/<int:material_id>')
@requires_permission('inventory') # KHO
def edit_material_page(material_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = "SELECT * FROM Materials WHERE material_id = %s"
    val = (material_id,)
    
    cursor.execute(sql, val)
    material_data = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if material_data:
        return render_template(EDIT_MATERIAL_HTML, material=material_data)
    else:
        return "Không tìm thấy vật tư!", 404

# 5. (U)pdate - Xử lý cập nhật vật tư (POST) (ĐÃ Nâng cấp Vòng đời)
@app.route('/update_material', methods=['POST'])
@requires_permission('inventory') # KHO
def update_material():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy dữ liệu từ form (thêm các trường mới)
    material_id = request.form['material_id']
    material_name = request.form['material_name']
    material_type = request.form['material_type'] # <--- TRƯỜNG MỚI
    lifespan_prints = request.form['lifespan_prints'] if material_type == 'maintenance' else 0 # <--- TRƯỜNG MỚI
    base_unit = request.form['base_unit']
    import_unit = request.form['import_unit']
    import_conversion_factor = request.form['import_conversion_factor']
    stock_quantity = request.form['stock_quantity']

    sql = """
        UPDATE Materials 
        SET material_name = %s, material_type = %s, lifespan_prints = %s, base_unit = %s, import_unit = %s, 
            import_conversion_factor = %s, stock_quantity = %s
        WHERE material_id = %s
    """
    val = (material_name, material_type, lifespan_prints, base_unit, import_unit, import_conversion_factor, stock_quantity, material_id)
    
    cursor.execute(sql, val)
    
    # == THÊM DÒNG NÀY ==
    log_desc = f"Cập nhật thông tin vật tư ID {material_id}"
    log_system_action(cursor, 'UPDATE', 'Materials', log_desc)
    # ===================
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('materials_page'))

# 6. Thay the delete để bảo toàn dữ liệu
@app.route('/toggle_material/<int:id>', methods=['POST'])
@requires_permission('all') # admin
def toggle_material(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Materials SET is_active = NOT is_active WHERE material_id = %s", (id,))
    
    # == THÊM DÒNG NÀY ==
    log_desc = f"Khóa thông tin Vật Tư ID {id}"
    log_system_action(cursor, 'TOGGLE', 'Materials', log_desc)
    # ===================
    
    conn.commit()
    conn.close()
    return redirect(url_for('materials_page'))
    
# ======================================================
# QUẢN LÝ NHẬP KHO (MATERIAL IMPORTS)
# ======================================================

# 1. (R)ead - Hiển thị trang Nhập kho (Form + Lịch sử)
@app.route('/imports')
@requires_permission('inventory') # KHO
def imports_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query 1: Lấy lịch sử nhập kho (JOIN 3 bảng)
    sql_imports = """
        SELECT 
            MI.import_date, 
            M.material_name, 
            S.supplier_name, 
            MI.quantity_imported, 
            M.import_unit,
            MI.import_price  -- Dòng này đã bị thiếu ở bước trước
        FROM Material_Imports AS MI
        JOIN Materials AS M ON MI.material_id = M.material_id
        LEFT JOIN Suppliers AS S ON MI.supplier_id = S.supplier_id
        ORDER BY MI.import_date DESC
    """
    cursor.execute(sql_imports)
    imports_list = cursor.fetchall()
    
    # Query 2: Lấy danh sách vật tư (để làm dropdown)
    cursor.execute("SELECT material_id, material_name, import_unit FROM Materials")
    materials_list = cursor.fetchall()
    
    # Query 3: Lấy danh sách nhà cung cấp (để làm dropdown)
    cursor.execute("SELECT supplier_id, supplier_name FROM Suppliers")
    suppliers_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('imports.html', 
                           imports_list=imports_list, 
                           materials_list=materials_list, 
                           suppliers_list=suppliers_list)

# 2. (C)reate - Xử lý thêm phiếu nhập kho (ĐÃ NÂNG CẤP GIÁ VỐN TRUNG BÌNH)
@app.route('/add_import', methods=['POST'])
@requires_permission('inventory') # KHO
def add_import():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) # Dùng dictionary=True
    
    try:
        # 1. Lấy dữ liệu từ form
        material_id = request.form['material_id']
        supplier_id = request.form['supplier_id']
        quantity_imported_units = int(request.form['quantity_imported']) # Ví dụ: 10 ram
        import_price_per_unit = float(request.form['import_price']) # Ví dụ: 60,000 (cho 1 ram)
        import_date = request.form['import_date']

        # 2. Lấy thông tin hiện tại của Vật tư
        cursor.execute("""
            SELECT stock_quantity, import_conversion_factor, avg_cost_per_base_unit 
            FROM Materials WHERE material_id = %s
        """, (material_id,))
        material = cursor.fetchone()
        
        if not material:
            return "Lỗi: Không tìm thấy vật tư!", 404
            
        current_stock_base = material['stock_quantity'] # Ví dụ: 100,000 tờ
        conversion_factor = material['import_conversion_factor'] # Ví dụ: 500
        current_avg_cost_base = material['avg_cost_per_base_unit'] # Ví dụ: 62.5đ

        # 3. Tính toán các giá trị mới
        # Giá trị kho hiện tại
        current_total_value = current_stock_base * current_avg_cost_base
        
        # Số lượng nhập (quy đổi về đơn vị cơ sở)
        quantity_imported_base = quantity_imported_units * conversion_factor # Ví dụ: 10 * 500 = 5000 tờ
        
        # Giá nhập (quy đổi về đơn vị cơ sở)
        # (Phải kiểm tra conversion_factor != 0 để tránh lỗi chia)
        if conversion_factor == 0: conversion_factor = 1
        import_price_per_base = import_price_per_unit / conversion_factor # Ví dụ: 60000 / 500 = 120đ/tờ
        
        # Giá trị của lô hàng nhập mới
        new_import_value = quantity_imported_base * import_price_per_base
        
        # Tính toán giá vốn trung bình MỚI
        new_total_stock = current_stock_base + quantity_imported_base
        new_total_value = current_total_value + new_import_value
        
        # Đây là con số "vàng":
        new_avg_cost_base = new_total_value / new_total_stock if new_total_stock > 0 else 0

        # 4. Ghi nhận Phiếu nhập kho (với giá nhập gốc)
        sql_insert = """
            INSERT INTO Material_Imports (material_id, supplier_id, import_date, quantity_imported, import_price, payment_status) 
            VALUES (%s, %s, %s, %s, %s, 'unpaid')
        """
        val_insert = (material_id, supplier_id, import_date, quantity_imported_units, import_price_per_unit)
        cursor.execute(sql_insert, val_insert)
        
        # 5. Cập nhật Tồn kho VÀ Giá vốn trung bình mới
        sql_update = """
            UPDATE Materials 
            SET stock_quantity = %s, avg_cost_per_base_unit = %s
            WHERE material_id = %s
        """
        val_update = (new_total_stock, new_avg_cost_base, material_id)
        cursor.execute(sql_update, val_update)
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thêm Nhập Kho ID {cursor.lastrowid}"
        log_system_action(cursor, 'ADD', 'Material_Imports', log_desc)
        # ===================
        
        conn.commit() 
        
    except mysql.connector.Error as err:
        conn.rollback() 
        print(f"Lỗi: {err}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('imports_page'))

# ======================================================
# QUẢN LÝ PHIẾU NHẬP KHO (NHIỀU VẬT TƯ)
# ======================================================

# 1. (GET) Hiển thị trang Tạo Phiếu Nhập
@app.route('/create_import')
@requires_permission('inventory') # KHO
def create_import_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Lấy danh sách NCC
    cursor.execute("SELECT supplier_id, supplier_name FROM Suppliers WHERE is_active = 1 ORDER BY supplier_name")
    suppliers_list = cursor.fetchall()
    
    # Lấy danh sách Vật tư (kèm đơn vị nhập để hiển thị)
    cursor.execute("SELECT material_id, material_name, import_unit FROM Materials WHERE is_active = 1 ORDER BY material_name")
    materials_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # === THÊM DÒNG NÀY: Lấy ngày hôm nay ===
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
    cursor = conn.cursor(dictionary=True)
    
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
            total_amount += int(quantities[i]) * float(unit_prices[i])

        # --- BƯỚC 1: TẠO PHIẾU NHẬP (Import_Slips) ---
        sql_slip = """
            INSERT INTO Import_Slips (supplier_id, import_date, total_amount, payment_status)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql_slip, (supplier_id, import_date, total_amount, payment_status))
        new_slip_id = cursor.lastrowid

        # --- BƯỚC 2: LẶP QUA TỪNG VẬT TƯ ---
        for i in range(len(material_ids)):
            mat_id = material_ids[i]
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
            # Lấy thông tin vật tư hiện tại
            cursor.execute("SELECT stock_quantity, import_conversion_factor, avg_cost_per_base_unit FROM Materials WHERE material_id = %s", (mat_id,))
            material = cursor.fetchone()
            
            if material:
                current_stock_base = material['stock_quantity']
                conversion_factor = material['import_conversion_factor']
                current_avg_cost = material['avg_cost_per_base_unit']
                
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
        
    except mysql.connector.Error as err:
        conn.rollback()
        return f"Lỗi SQL: {err}", 500
    finally:
        cursor.close()
        conn.close()
    
    # Quay về trang kho hoặc trang chi tiết phiếu nhập (nếu làm)
    return redirect(url_for('materials_page'))

# ======================================================
# QUẢN LÝ PHIẾU ĐIỀU CHỈNH KHO (NHIỀU VẬT TƯ)
# ======================================================

# 1. (GET) Hiển thị trang Tạo Phiếu Điều chỉnh
@app.route('/create_adjustment')
@requires_permission('accounting') # Kế Toán
def create_adjustment_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
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
    cursor = conn.cursor()
    
    try:
        # A. Lấy thông tin chung
        adjustment_date = request.form['adjustment_date']
        
        # B. Lấy danh sách chi tiết
        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity_adjusted[]')
        reasons = request.form.getlist('reason[]')
        
        # --- BƯỚC 1: TẠO PHIẾU CHA ---
        sql_slip = "INSERT INTO Adjustment_Slips (adjustment_date) VALUES (%s)"
        cursor.execute(sql_slip, (adjustment_date,))
        new_slip_id = cursor.lastrowid

        # --- BƯỚC 2: LẶP QUA TỪNG VẬT TƯ ---
        for i in range(len(material_ids)):
            mat_id = material_ids[i]
            qty = int(quantities[i]) # Số này có thể âm hoặc dương
            reason = reasons[i]
            
            # 2a. Lưu vào bảng chi tiết
            sql_item = """
                INSERT INTO Adjustment_Slip_Items (slip_id, material_id, quantity_adjusted, reason)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql_item, (new_slip_id, mat_id, qty, reason))
            
            # 2b. CẬP NHẬT KHO (Cộng dồn số lượng)
            # Nếu qty là -5 (hủy), kho sẽ giảm 5. Nếu qty là +2 (thừa), kho tăng 2.
            sql_update_stock = """
                UPDATE Materials 
                SET stock_quantity = stock_quantity + %s 
                WHERE material_id = %s
            """
            cursor.execute(sql_update_stock, (qty, mat_id))
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thêm Phiếu Điều Chỉnh Kho ID {new_slip_id}"
        log_system_action(cursor, 'ADD', 'Adjustment_Slip_Items', log_desc)
        # ===================

        conn.commit()
        
    except mysql.connector.Error as err:
        conn.rollback()
        return f"Lỗi SQL: {err}", 500
    finally:
        cursor.close()
        conn.close()
    
    # Quay về trang Vật tư
    return redirect(url_for('materials_page'))
    
# ======================================================
# QUẢN LÝ ĐIỀU CHỈNH KHO (STOCK ADJUSTMENTS)
# ======================================================

# 1. (R)ead - Hiển thị trang Điều chỉnh (Form + Lịch sử)
@app.route('/adjustments')
@requires_permission('accounting') # Kế Toán
def adjustments_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query 1: Lấy lịch sử điều chỉnh (JOIN 2 bảng)
    sql_adjustments = """
        SELECT SA.adjustment_date, M.material_name, SA.quantity_adjusted, SA.reason
        FROM Stock_Adjustments AS SA
        JOIN Materials AS M ON SA.material_id = M.material_id
        ORDER BY SA.adjustment_date DESC
    """
    cursor.execute(sql_adjustments)
    adjustments_list = cursor.fetchall()
    
    # Query 2: Lấy danh sách vật tư (để làm dropdown)
    cursor.execute("SELECT material_id, material_name FROM Materials")
    materials_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Gửi cả 2 danh sách ra template
    return render_template('adjustments.html', 
                           adjustments_list=adjustments_list, 
                           materials_list=materials_list)

# 2. (C)reate - Xử lý thêm phiếu điều chỉnh
@app.route('/add_adjustment', methods=['POST'])
@requires_permission('accounting') # Kế Toán
def add_adjustment():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Lấy dữ liệu từ form
        material_id = request.form['material_id']
        # Lấy số lượng điều chỉnh (có thể là số âm)
        quantity = int(request.form['quantity_adjusted']) 
        reason = request.form['reason']
        adjustment_date = request.form['adjustment_date']

        # === NGHIỆP VỤ 1: INSERT vào nhật ký điều chỉnh ===
        sql_insert = """
            INSERT INTO Stock_Adjustments (material_id, adjustment_date, quantity_adjusted, reason) 
            VALUES (%s, %s, %s, %s)
        """
        val_insert = (material_id, adjustment_date, quantity, reason)
        cursor.execute(sql_insert, val_insert)
        
        # === NGHIỆP VỤ 2: UPDATE tồn kho ===
        # (Lưu ý: chúng ta dùng 'quantity', dù nó âm hay dương)
        sql_update = """
            UPDATE Materials 
            SET stock_quantity = stock_quantity + %s 
            WHERE material_id = %s
        """
        val_update = (quantity, material_id)
        cursor.execute(sql_update, val_update)
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thêm Điều Chỉnh Kho ID {cursor.lastrowid}"
        log_system_action(cursor, 'ADD', 'Stock_Adjustments', log_desc)
        # ===================
        
        conn.commit() # Lưu thay đổi
        
    except mysql.connector.Error as err:
        conn.rollback() 
        print(f"Lỗi: {err}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('adjustments_page'))
    
# ======================================================
# QUẢN LÝ ĐỊNH MỨC VẬT TƯ (SERVICE_MATERIALS - BOM)
# ======================================================

# 1. (R)ead - Hiển thị trang Định mức (Form + Danh sách)
@app.route('/service_materials')
@requires_permission('sale', 'inventory') # Kinh Doanh và Kho
def service_materials_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # 1. Lấy danh sách Dịch vụ (để làm dropdown thêm mới)
    cursor.execute("""
                    SELECT service_id, service_name, unit, unit_level2, unit_level3 
                    FROM Services
                    WHERE is_active = 1
                    ORDER BY service_name
                    """)
    services_list = cursor.fetchall()

    # 2. Lấy danh sách Vật tư (để làm dropdown thêm mới)
    cursor.execute("SELECT material_id, material_name, base_unit FROM Materials WHERE is_active = 1 ORDER BY material_name")
    materials_list = cursor.fetchall()

    # ...
    # Query 3: Lấy dữ liệu BOM (Lấy thêm cột đơn vị của Service và Level áp dụng)
    sql_boms = """
        SELECT 
            S.service_id, S.service_name, S.base_price AS selling_price,
            S.unit AS u1, S.unit_level2 AS u2, S.unit_level3 AS u3, -- Lấy tên 3 đơn vị
            M.material_name, M.base_unit, 
            SM.quantity_consumed, SM.service_material_id, SM.apply_to_unit_level, -- Lấy Level áp dụng
            M.avg_cost_per_base_unit,
            (SM.quantity_consumed * M.avg_cost_per_base_unit) AS estimated_cost
        FROM Service_Materials AS SM
        JOIN Services AS S ON SM.service_id = S.service_id
        JOIN Materials AS M ON SM.material_id = M.material_id
        ORDER BY S.service_name
    """
    cursor.execute(sql_boms)
    raw_boms = cursor.fetchall()
    
    # 4. Xử lý dữ liệu: Gom nhóm theo Service (Python Logic)
    # Kết quả mong muốn: { service_id: { info: {...}, items: [...] } }
    grouped_boms = {}
    
    for row in raw_boms:
        s_id = row['service_id']
        
        if s_id not in grouped_boms:
            grouped_boms[s_id] = {
                'service_name': row['service_name'],
                'selling_price': row['selling_price'],
                'total_cost': 0, # Sẽ cộng dồn
                'items': []
            }
        
        # Thêm item vào danh sách con
        grouped_boms[s_id]['items'].append(row)
        # Cộng dồn giá vốn
        grouped_boms[s_id]['total_cost'] += row['estimated_cost']

    cursor.close()
    conn.close()
    
    return render_template('service_materials.html', 
                           services_list=services_list,
                           materials_list=materials_list,
                           grouped_boms=grouped_boms) # Gửi dữ liệu đã gom nhóm

# 2. (C)reate - Xử lý thêm một định mức mới
@app.route('/add_service_material', methods=['POST'])
@requires_permission('sale', 'inventory') # Kinh Doanh và Kho
def add_service_material():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Lấy Dịch vụ Cha (chỉ có 1)
        service_id = request.form['service_id']
        
        # 2. Lấy Danh sách Vật tư Con (mảng)
        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity_consumed[]')
        
        # === LẤY DỮ LIỆU MỚI (Mảng các level tương ứng) ===
        levels = request.form.getlist('apply_to_level[]') 
        # ===================================================

        # 3. Lặp và Lưu
        for i in range(len(material_ids)):
            mat_id = material_ids[i]
            qty = quantities[i]
            level = levels[i] # Lấy level tương ứng của dòng đó
            
            # Kiểm tra dữ liệu rỗng
            if not mat_id or not qty: 
                continue

            # Cập nhật SQL: Thêm apply_to_unit_level
            sql = """
                INSERT INTO Service_Materials (service_id, material_id, quantity_consumed, apply_to_unit_level) 
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (service_id, mat_id, float(qty), int(level)))
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thêm Công Thức Định Mức ID {cursor.lastrowid}"
        log_system_action(cursor, 'ADD', 'Service_Materials', log_desc)
        # ===================
            
        conn.commit() 
        
    except mysql.connector.Error as err:
        conn.rollback() 
        print(f"Lỗi: {err}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('service_materials_page'))

# 3. (D)elete - Xử lý xóa một định mức
@app.route('/delete_service_material/<int:sm_id>', methods=['POST'])
@requires_permission('all') # admin
def delete_service_material(sm_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        sql = "DELETE FROM Service_Materials WHERE service_material_id = %s"
        val = (sm_id,)
        cursor.execute(sql, val)
        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Lỗi: {err}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('service_materials_page'))

# ======================================================
# TẠO ĐƠN HÀNG MỚI (ORDERS)
# ======================================================

# 1. (GET) Hiển thị trang tạo đơn hàng
@app.route('/create_order')
@requires_permission('sale') # Kinh Doanh
def create_order_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    today = datetime.date.today() # Lấy ngày hôm nay
    
    # Query 1: Lấy danh sách khách hàng
    cursor.execute("SELECT customer_id, customer_name, phone, email, address, company_name, tax_id FROM Customers WHERE is_active = 1 ORDER BY customer_name")
    customers_list = cursor.fetchall()
    
    # Query 2: Lấy thêm unit_level2, unit_level3
    cursor.execute("SELECT service_id, service_name, base_price, unit, unit_level2, unit_level3 FROM Services WHERE is_active = 1 ORDER BY service_name")
    services_list = cursor.fetchall()
    
    # === QUERY MỚI ===
    # Query 3: Lấy danh sách máy móc đang hoạt động
    cursor.execute("SELECT equipment_id, equipment_name FROM Equipment WHERE status = 'active' AND is_active = 1 ORDER BY equipment_name")
    equipment_list = cursor.fetchall()
    # === KẾT THÚC ===
    
    # === 2. LẤY MÃ KHUYẾN MÃI ĐANG CHẠY (MỚI) ===
    # Điều kiện: Status='active' VÀ Hôm nay nằm trong khoảng Start-End
    sql_coupons = """
        SELECT * FROM Coupons 
        WHERE status = 'active' 
          AND start_date <= %s 
          AND end_date >= %s
        ORDER BY discount_value DESC
    """
    cursor.execute(sql_coupons, (today, today))
    active_coupons = cursor.fetchall()
    # ============================================
    
    cursor.close()
    conn.close()
    
    return render_template(TAO_DH_HTML, 
                           customers_list=customers_list, 
                           services_list=services_list,
                           equipment_list=equipment_list, # <-- Gửi danh sách máy ra
                           active_coupons=active_coupons) # <-- Gửi danh sách mã ra

# ======================================================
# TẠO ĐƠN HÀNG MỚI (ORDERS) - PHẦN XỬ LÝ
# ======================================================

# 2. (POST) Xử lý lưu đơn hàng, tính tiền, VÀ TRỪ KHO (Nâng cấp: TRỪ BỘ ĐẾM MÁY)
@app.route('/submit_order', methods=['POST'])
@requires_permission('sale') # Kinh Doanh
def submit_order():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    new_order_id = -1 # Đặt ID mặc định
    
    try:
        # Lấy thông tin chung
        customer_id = request.form['customer_id']
        tax_rate = float(request.form['tax_rate']) # Lấy thuế suất
        
        # === LẤY THÔNG TIN COUPON (MỚI) ===
        coupon_code = request.form.get('coupon_code')
        discount_amount = float(request.form.get('discount_amount') or 0)
        # ==================================
        
        # Lấy danh sách các dịch vụ từ form
        # request.form.getlist() sẽ lấy tất cả các input có cùng tên
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        equipment_ids = request.form.getlist('equipment_id[]') # <--- DANH SÁCH MÁY MỚI
        
        # Lấy thêm các mảng số lượng chi tiết
        qty_l1_list = request.form.getlist('qty_l1[]')
        qty_l2_list = request.form.getlist('qty_l2[]')
        qty_l3_list = request.form.getlist('qty_l3[]')
        
        # --- BƯỚC 1: Tính tổng tiền và tạo Đơn hàng (Orders) ---
        #total_amount = 0
        subtotal = 0
        for i in range(len(service_ids)):
            #total_amount += int(quantities[i]) * float(unit_prices[i])
            subtotal += int(quantities[i]) * float(unit_prices[i])
        
        tax_amount = subtotal * (tax_rate / 100)
        
        # Tính total_amount cuối cùng
        total_amount = (subtotal + tax_amount) - discount_amount
        if total_amount < 0: total_amount = 0

        # --- BƯỚC 2: Tạo Đơn hàng (Orders) ---
        sql_insert_order = """
            INSERT INTO Orders (customer_id, status, subtotal, tax_rate, tax_amount, coupon_code, discount_amount, total_amount, quote_id)
            VALUES (%s, 'processing', %s, %s, %s, %s, NULL)
        """
        val_insert_order = (customer_id, subtotal, tax_rate, tax_amount, coupon_code, discount_amount, total_amount)
        cursor.execute(sql_insert_order, val_insert_order)
        
        # === CẬP NHẬT SỐ LẦN DÙNG COUPON ===
        if coupon_code:
            cursor.execute("UPDATE Coupons SET used_count = used_count + 1 WHERE code = %s", (coupon_code,))
        
        # Lấy ID của đơn hàng MỚI NHẤT vừa tạo
        new_order_id = cursor.lastrowid

        # --- BƯỚC 3, 4, 5: Lặp qua từng dịch vụ ---
        for i in range(len(service_ids)):
            service_id = service_ids[i]
            quantity = int(quantities[i])
            unit_price = float(unit_prices[i])
            equipment_id = equipment_ids[i] # <--- Lấy máy cho dịch vụ này
            line_total = quantity * unit_price
            
           # === PHẦN MỚI: TÍNH GIÁ VỐN (COST OF GOODS) ===
            total_cost_for_item = 0.0 # Đảm bảo khởi tạo là float (0.0)
            
            # --- BƯỚC 3: Tra cứu "Công thức" & TRỪ KHO
            # --- LOGIC MỚI: XÁC ĐỊNH SỐ LƯỢNG DỰA TRÊN LEVEL ---
            # Chúng ta cần lấy được số lượng cụ thể của từng tầng từ form input
            # Nhưng form input hiện tại gửi lên mảng 'quantity[]' là TỔNG CUỐI CÙNG (L1*L2*L3)
            
            # ĐỂ LÀM ĐƯỢC CHÍNH XÁC, FRONTEND PHẢI GỬI LÊN CHI TIẾT SL TỪNG TẦNG
            # Tuy nhiên, để đơn giản hóa mà không sửa quá nhiều frontend:
            # Ta có thể dùng logic suy luận ngược hoặc cập nhật form submit_order để gửi q1, q2, q3 riêng biệt.
            
            # CÁCH ĐƠN GIẢN NHẤT:
            # Hệ thống hiện tại đang lưu 'quantity' là tổng số đơn vị L1 (Tờ).
            # Nếu định mức tính theo L1 (Tờ) -> Nhân trực tiếp quantity.
            # Nếu định mức tính theo L2 (Cuốn) -> Cần biết số lượng Cuốn.
            
            # => GIẢI PHÁP: Cần sửa 'create_order.html' để gửi thêm hidden field 
            # 'quantity_l1', 'quantity_l2', 'quantity_l3' cho mỗi dòng dịch vụ.
            
            # Lấy số lượng cụ thể của dòng này
            q1 = float(qty_l1_list[i])
            q2 = float(qty_l2_list[i])
            q3 = float(qty_l3_list[i])
            
            # Tra cứu "Công thức"
            sql_get_bom = """
                SELECT SM.material_id, SM.quantity_consumed, SM.apply_to_unit_level, M.avg_cost_per_base_unit 
                FROM Service_Materials AS SM
                JOIN Materials AS M ON SM.material_id = M.material_id
                WHERE SM.service_id = %s
            """
            cursor.execute(sql_get_bom, (service_id,))
            materials_to_update = cursor.fetchall()
            
            if not materials_to_update:
                # Nếu dịch vụ này không cần vật tư (ví dụ: 'Scan ảnh'), bỏ qua
                continue 

            # --- Lặp qua các vật tư trong công thức và TRỪ KHO ---
            for material in materials_to_update:
                # --- SỬA LỖI TẠI ĐÂY: Ép kiểu sang float ---
                qty_consumed = float(material['quantity_consumed'])
                avg_cost = float(material['avg_cost_per_base_unit'])
                
                # Logic nhân theo tầng
                level = material['apply_to_unit_level']
                
                total_material_to_deduct = 0
                
                # Tính tổng số vật tư cần trừ
                if level == 1: 
                    # Áp dụng cho Tờ (Ví dụ: Giấy, Mực)
                    # Tổng Tờ = q1 * q2 * q3
                    total_material_to_deduct = (q1 * q2 * q3) * qty_consumed
                    
                elif level == 2:
                    # Áp dụng cho Cuốn (Ví dụ: Bìa, Lò xo)
                    # Tổng Cuốn = q2 * q3
                    total_material_to_deduct = (q2 * q3) * qty_consumed
                    
                elif level == 3:
                    # Áp dụng cho Bộ (Ví dụ: Hộp đựng)
                    # Tổng Bộ = q3
                    total_material_to_deduct = q3 * qty_consumed
                
                # (Kiểm tra tồn kho nâng cao - Tạm bỏ qua để giữ code đơn giản)
                # (Trong hệ thống thực tế, bạn phải SELECT để check xem có đủ kho không)
                
                
                # (Code mới - Thêm hàm float())
                cost_of_material = total_material_to_deduct * avg_cost
                # Cộng dồn (bây giờ cả 2 đều là float nên không lỗi nữa)
                total_cost_for_item += cost_of_material
                
                # --- BƯỚC 4: TRỪ KHO  ---
                sql_update_stock = "UPDATE Materials SET stock_quantity = stock_quantity - %s WHERE material_id = %s"
                val_update_stock = (total_material_to_deduct, material['material_id'])
                cursor.execute(sql_update_stock, val_update_stock)
                    
            
            # Tính lợi nhuận
            profit_for_item = line_total - total_cost_for_item
            # === KẾT THÚC PHẦN MỚI ===
            
            # --- BƯỚC 4: INSERT vào Order_Items ---
            sql_insert_item = """
                INSERT INTO Order_Items (order_id, service_id, equipment_id, quantity, unit_price, line_total, cost_of_goods, profit)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            #line_total = quantity * unit_price
            val_insert_item = (new_order_id, service_id,
                                (equipment_id if equipment_id else None), # Xử lý nếu không chọn máy
                                quantity, unit_price, line_total,
                                total_cost_for_item, (line_total - total_cost_for_item))
            cursor.execute(sql_insert_item, val_insert_item)
            
            # --- BƯỚC 5: CẬP NHẬT BỘ ĐẾM CỦA MÁY (MỚI) ---
            if equipment_id and quantity > 0:
                sql_update_counter = """
                    UPDATE Equipment 
                    SET print_count = print_count + %s
                    WHERE equipment_id = %s
                """
                cursor.execute(sql_update_counter, (quantity, equipment_id))        
                
        # == THÊM DÒNG NÀY ==
        log_desc = f"Tạo đơn hàng #{new_order_id}. Tổng tiền: {total_amount:,.0f}"
        log_system_action(cursor, 'CREATE', 'Orders', log_desc)
        # ===================

        # Nếu tất cả các bước trên thành công...
        conn.commit() # ...Lưu tất cả thay đổi
        
    except mysql.connector.Error as err:
        # Nếu có bất kỳ lỗi nào...
        conn.rollback() # ...Hủy bỏ toàn bộ giao dịch
        print(f"LỖI KHI TẠO ĐƠN HÀNG: {err}")
        return f"Đã xảy ra lỗi: {err}", 500
    finally:
        # Luôn đóng kết nối
        cursor.close()
        conn.close()
    
    # Nếu thành công, chuyển hướng người dùng (ví dụ: về trang chủ)
    return redirect(url_for('services_page'))

# 3. Hủy đơn hàng và hoàn kho
@app.route('/cancel_order/<int:order_id>', methods=['POST'])
# @requires_permission('sale') # Bỏ comment dòng này nếu bạn đang dùng hệ thống phân quyền
def cancel_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Kiểm tra xem đơn hàng có tồn tại và đang ở trạng thái 'processing' không
        cursor.execute("SELECT status FROM Orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()
        
        if not order:
            return "Không tìm thấy đơn hàng!", 404
            
        if order['status'] != 'processing':
            return "Chỉ có thể hủy đơn hàng đang ở trạng thái 'Chờ xử lý' (Processing)!", 400

        # 2. Lấy danh sách các dịch vụ trong đơn hàng đó để tính toán hoàn kho
        sql_get_items = "SELECT service_id, quantity FROM Order_Items WHERE order_id = %s"
        cursor.execute(sql_get_items, (order_id,))
        order_items = cursor.fetchall()
        
        # 3. Vòng lặp HOÀN KHO (Reverse Inventory)
        for item in order_items:
            service_id = item['service_id']
            quantity_sold = float(item['quantity']) # Số lượng đã bán (Tờ/Cuốn/Bộ...)
            
            # Lấy công thức định mức của dịch vụ này
            # (Lưu ý: Ta không cần quan tâm unit level ở đây nữa, vì quantity_sold 
            # trong Order_Items đã là con số tổng cuối cùng được tính toán rồi)
            sql_bom = "SELECT material_id, quantity_consumed FROM Service_Materials WHERE service_id = %s"
            cursor.execute(sql_bom, (service_id,))
            bom_materials = cursor.fetchall()
            
            for mat in bom_materials:
                material_id = mat['material_id']
                qty_consumed_per_unit = float(mat['quantity_consumed'])
                
                # Tính tổng lượng vật tư cần trả lại kho
                qty_to_return = quantity_sold * qty_consumed_per_unit
                
                # Thực hiện cộng lại kho (+)
                sql_restock = "UPDATE Materials SET stock_quantity = stock_quantity + %s WHERE material_id = %s"
                cursor.execute(sql_restock, (qty_to_return, material_id))

        # 4. Cập nhật trạng thái đơn hàng thành 'cancelled'
        cursor.execute("UPDATE Orders SET status = 'cancelled' WHERE order_id = %s", (order_id,))
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Hủy đơn hàng #{order_id}. Tổng tiền: {total_amount:,.0f}"
        log_system_action(cursor, 'CANCEL', 'Orders', log_desc)
        # ===================
        
        conn.commit()
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"LỖI KHI HỦY ĐƠN: {err}")
        return f"Lỗi cơ sở dữ liệu: {err}", 500
    finally:
        cursor.close()
        conn.close()
    
    # Quay lại trang lịch sử
    return redirect(url_for('orders_history_page'))

# ======================================================
# BÁO CÁO: LỊCH SỬ ĐƠN HÀNG (DOANH THU)
# ======================================================

# 1. (GET) Hiển thị trang Lịch sử Đơn hàng (ĐÃ NÂNG CẤP CÔNG NỢ)
@app.route('/orders_history')
@requires_permission('sale', 'accounting') # Kinh Doanh và Kế Toán
def orders_history_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Lấy tham số từ URL
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    filter_mode = request.args.get('filter') # Dùng để "Xóa lọc"
    
    # === LOGIC NGÀY MẶC ĐỊNH (MỚI) ===
    today = datetime.date.today()
    
    # Nếu không có ngày nào được cung cấp VÀ không phải là "Xóa lọc"
    if not start_date_str and not end_date_str and filter_mode != 'all':
        # Mặc định là 7 ngày gần nhất
        seven_days_ago = today - datetime.timedelta(days=6)
        start_date_str = seven_days_ago.isoformat()
        end_date_str = today.isoformat()
    # === KẾT THÚC LOGIC MỚI ===
    
    # Lấy thêm các cột mới
    sql = """
        SELECT O.order_id, O.order_date, O.total_amount, O.status, O.amount_paid, 
               (O.total_amount - O.amount_paid) AS amount_due, 
               O.payment_status, O.delivery_status, C.customer_name
        FROM Orders AS O
        JOIN Customers AS C ON O.customer_id = C.customer_id
        WHERE 1=1 
    """
    params = []

    if start_date_str:
        sql += " AND DATE(O.order_date) >= %s"
        params.append(start_date_str)
    if end_date_str:
        sql += " AND DATE(O.order_date) <= %s"
        params.append(end_date_str)
        
    sql += " ORDER BY O.order_date DESC"
    
    cursor.execute(sql, tuple(params))
    orders_list = cursor.fetchall()
    
    # TÍNH TỔNG (CẬP NHẬT LOGIC)
    # Chỉ cộng nếu status KHÁC 'cancelled'
    total_revenue = sum(order['total_amount'] for order in orders_list if order['status'] != 'cancelled')
    
    # Công nợ cũng phải trừ đơn hủy ra
    total_due = sum(order['amount_due'] for order in orders_list if order['status'] != 'cancelled')
    
    # Tính riêng tổng tiền các đơn đã hủy (để hiển thị tham khảo nếu muốn)
    total_cancelled = sum(order['total_amount'] for order in orders_list if order['status'] == 'cancelled')
    
    cursor.close()
    conn.close()
    
    return render_template(LS_DH_HTML, 
                           orders_list=orders_list,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           total_revenue=total_revenue,
                           total_due=total_due, # Gửi tổng công nợ ra
                           total_cancelled=total_cancelled) # <-- Gửi thêm biến này

# 2. (GET) Hiển thị trang CHI TIẾT của một đơn hàng
@app.route('/order/<int:order_id>')
@requires_permission('sale', 'inventory') # Kinh Doanh va Kho
def order_detail_page(order_id):
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query 1: Lấy thông tin chung của Đơn hàng (và tên khách)
    sql_order = """
        SELECT O.*, C.customer_name, C.phone
        FROM Orders AS O
        JOIN Customers AS C ON O.customer_id = C.customer_id
        WHERE O.order_id = %s
    """
    cursor.execute(sql_order, (order_id,))
    order_info = cursor.fetchone() # Lấy 1 hàng
    
    # Query 2: Lấy các dịch vụ bên trong đơn hàng đó
    sql_items = """
        SELECT QI.quantity, QI.unit_price, QI.line_total, 
               QI.cost_of_goods, QI.profit, 
               S.service_name, S.unit
        FROM Order_Items AS QI
        JOIN Services AS S ON QI.service_id = S.service_id
        WHERE QI.order_id = %s
    """
    cursor.execute(sql_items, (order_id,))
    order_items = cursor.fetchall() # Lấy nhiều hàng
    
    cursor.close()
    conn.close()
    
    if not order_info:
        return "Không tìm thấy đơn hàng!", 404
        
    return render_template(CT_DH_HTML, 
                           order_info=order_info,
                           order_items=order_items)
                           
# 3. (POST) Ghi nhận Thanh toán cho một Đơn hàng
@app.route('/log_payment/<int:order_id>', methods=['POST'])
@requires_permission('sale', 'accounting') # Kinh Doanh và Kế toán
def log_payment(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 0. Kiểm tra trạng thái trước
    cursor.execute("SELECT status FROM Orders WHERE order_id = %s", (order_id,))
    order = cursor.fetchone()
    
    if not order or order['status'] == 'cancelled':
        conn.close()
        return "LỖI: Không thể thanh toán cho đơn hàng đã hủy!", 403
    
    try:
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
        cursor.execute(sql_update, (amount_received, payment_method, order_id))
        
        # 2. Lấy lại dữ liệu để cập nhật trạng thái (status)
        cursor.execute("SELECT total_amount, amount_paid FROM Orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()
        
        new_payment_status = 'unpaid'
        if order['amount_paid'] >= order['total_amount']:
            new_payment_status = 'paid'
        elif order['amount_paid'] > 0:
            new_payment_status = 'partially_paid'
        
        # 3. Cập nhật trạng thái thanh toán
        cursor.execute("UPDATE Orders SET payment_status = %s WHERE order_id = %s", (new_payment_status, order_id))
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thanh toán đơn hàng #{order_id}. Tổng tiền: {total_amount:,.0f}"
        log_system_action(cursor, 'PAYMENT', 'Orders', log_desc)
        # ===================
        
        conn.commit()
        
    except mysql.connector.Error as err:
        conn.rollback() 
        print(f"LỖI KHI GHI NHẬN THANH TOÁN: {err}")
    finally:
        cursor.close()
        conn.close()
    
    # Quay lại trang chi tiết của chính đơn hàng đó
    return redirect(url_for('order_detail_page', order_id=order_id))

# 4. (POST) Cập nhật Trạng thái Giao hàng
@app.route('/update_delivery/<int:order_id>', methods=['POST'])
@requires_permission('inventory', 'sale' ) # Kinh Doanh và Kho
def update_delivery_status(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Kiểm tra trạng thái
    cursor.execute("SELECT status FROM Orders WHERE order_id = %s", (order_id,))
    # fetchone trả về tuple (status,) nên lấy [0]
    result = cursor.fetchone() 
    
    if not result or result[0] == 'cancelled':
        conn.close()
        return "LỖI: Không thể cập nhật giao hàng cho đơn đã hủy!", 403
    
    try:
        new_status = request.form['delivery_status']
        sql = "UPDATE Orders SET delivery_status = %s WHERE order_id = %s"
        cursor.execute(sql, (new_status, order_id))
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Tình trang giao đơn hàng #{order_id}. Tổng tiền: {total_amount:,.0f}"
        log_system_action(cursor, 'DELIVERY', 'Orders', log_desc)
        # ===================
        
        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"LỖI KHI CẬP NHẬT GIAO HÀNG: {err}")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('order_detail_page', order_id=order_id))

# ======================================================
# QUẢN LÝ BÁO GIÁ (QUOTES)
# ======================================================

# 1. (GET) Hiển thị trang Lịch sử Báo giá (có lọc)
@app.route('/quotes_history')
@requires_permission('sale') # Kinh Doanh
def quotes_history_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    filter_mode = request.args.get('filter') # Dùng để "Xóa lọc"
    
    # === LOGIC NGÀY MẶC ĐỊNH (MỚI) ===
    today = datetime.date.today()
    if not start_date_str and not end_date_str and filter_mode != 'all':
        # Mặc định là 7 ngày gần nhất
        seven_days_ago = today - datetime.timedelta(days=6)
        start_date_str = seven_days_ago.isoformat()
        end_date_str = today.isoformat()
    # === KẾT THÚC LOGIC MỚI ===
    
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
    
    cursor.execute(sql, tuple(params))
    quotes_list = cursor.fetchall()
    
    # Tính tổng tiền của các báo giá (đã lọc)
    total_quotes_value = sum(quote['total_amount'] for quote in quotes_list)
    
    cursor.close()
    conn.close()
    
    return render_template(LS_BG_HTML, 
                           quotes_list=quotes_list,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           total_quotes_value=total_quotes_value)

# 2. (GET) Hiển thị trang TẠO Báo giá Mới
# (Đây là bản sao của create_order_page)
@app.route('/create_quote')
@requires_permission('sale') # Kinh Doanh
def create_quote_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    today = datetime.date.today() # Lấy ngày hôm nay
    
    cursor.execute("SELECT customer_id, customer_name, phone, email, address, company_name, tax_id FROM Customers WHERE is_active = 1 ORDER BY customer_name")
    customers_list = cursor.fetchall()
    
    cursor.execute("SELECT service_id, service_name, base_price, unit, unit_level2, unit_level3 FROM Services WHERE is_active = 1 ORDER BY service_name")
    services_list = cursor.fetchall()
    
    # === 2. LẤY MÃ KHUYẾN MÃI ĐANG CHẠY (MỚI) ===
    # Điều kiện: Status='active' VÀ Hôm nay nằm trong khoảng Start-End
    sql_coupons = """
        SELECT * FROM Coupons 
        WHERE status = 'active' 
          AND start_date <= %s 
          AND end_date >= %s
        ORDER BY discount_value DESC
    """
    cursor.execute(sql_coupons, (today, today))
    active_coupons = cursor.fetchall()
    # ============================================
    
    cursor.close()
    conn.close()
    
    # Dùng một template MỚI
    return render_template(TAO_BG_HTML, 
                           customers_list=customers_list, 
                           services_list=services_list,
                           active_coupons=active_coupons) # <-- Gửi danh sách mã ra

# 3. (POST) Xử lý LƯU Báo giá
# (Bản sao của submit_order, nhưng KHÔNG TRỪ KHO)
@app.route('/submit_quote', methods=['POST'])
@requires_permission('sale') # Kinh Doanh
def submit_quote():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    new_quote_id = -1
    
    try:
        # Lấy thông tin chung
        customer_id = request.form['customer_id']
        notes = request.form['notes'] # Lấy thêm ghi chú
        tax_rate = float(request.form['tax_rate'])
        
        # === LẤY THÔNG TIN GIẢM GIÁ (MỚI) ===
        coupon_code = request.form.get('coupon_code')
        discount_amount = float(request.form.get('discount_amount') or 0)
        # ====================================
        
        service_ids = request.form.getlist('service_id[]')
        # Lưu ý: Lấy quantity[] là lấy tổng số lượng (đã tính toán ở frontend)
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        
        # --- BƯỚC 1: Tính tổng tiền và tạo Báo giá (Quotes) ---
        #total_amount = 0
        subtotal = 0
        for i in range(len(service_ids)):
            #total_amount += int(quantities[i]) * float(unit_prices[i])
            subtotal += int(quantities[i]) * float(unit_prices[i])
            
        tax_amount = subtotal * (tax_rate / 100)
        #total_amount = subtotal + tax_amount
        # Tính tổng cuối cùng (Sau thuế - Giảm giá)
        total_amount = (subtotal + tax_amount) - discount_amount
        if total_amount < 0: total_amount = 0
        
        # --- BƯỚC 2: Tạo Báo giá (Quotes) ---
        sql_insert_quote = """
            INSERT INTO Quotes (customer_id, status, notes, subtotal, tax_rate, tax_amount, 
            coupon_code, discount_amount, total_amount)
            VALUES (%s, 'pending', %s, %s, %s, %s, %s, %s, %s)
        """
        val_insert_quote = (customer_id, notes, subtotal, tax_rate, tax_amount, coupon_code, discount_amount, total_amount)
        cursor.execute(sql_insert_quote, val_insert_quote)
        
        new_quote_id = cursor.lastrowid # Lấy ID báo giá mới

        # --- BƯỚC 3: Lặp qua từng dịch vụ và INSERT vào Quote_Items ---
        for i in range(len(service_ids)):
            service_id = service_ids[i]
            quantity = int(quantities[i])
            unit_price = float(unit_prices[i])
            line_total = quantity * unit_price
            
            sql_insert_item = """
                INSERT INTO Quote_Items (quote_id, service_id, description, quantity, unit_price, line_total)
                VALUES (%s, %s, '', %s, %s, %s)
            """
            val_insert_item = (new_quote_id, service_id, quantity, unit_price, line_total)
            cursor.execute(sql_insert_item, val_insert_item)
            
            # (KHÔNG CÓ BƯỚC 3 & 4 - KHÔNG TRA CÔNG THỨC, KHÔNG TRỪ KHO)
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Tạo Báo Giá #{new_quote_id}. Tổng tiền: {total_amount:,.0f}"
        log_system_action(cursor, 'CREATE', 'Quotes', log_desc)
        # ===================
        
        conn.commit() # Lưu tất cả thay đổi
        
    except mysql.connector.Error as err:
        conn.rollback() 
        print(f"LỖI KHI TẠO BÁO GIÁ: {err}")
        return f"Đã xảy ra lỗi: {err}", 500
    finally:
        cursor.close()
        conn.close()
    
    # Chuyển hướng về trang lịch sử BÁO GIÁ
    #return redirect(url_for('quotes_history_page'))
    # Chuyển hướng đến chi tiết BÁO GIÁ vừa tạo
    return redirect(url_for('quote_detail_page', quote_id=new_quote_id))

# 4. (GET) Hiển thị trang CHI TIẾT của một Báo giá
# (Bản sao của order_detail_page)
@app.route('/quote/<int:quote_id>')
@requires_permission('sale','inventory') # Kinh Doanh
def quote_detail_page(quote_id):
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query 1: Lấy thông tin chung Báo giá
    sql_quote = """
        SELECT Q.*, C.customer_name, C.phone
        FROM Quotes AS Q
        JOIN Customers AS C ON Q.customer_id = C.customer_id
        WHERE Q.quote_id = %s
    """
    cursor.execute(sql_quote, (quote_id,))
    quote_info = cursor.fetchone()
    
    # Query 2: Lấy các dịch vụ bên trong Báo giá đó
    sql_items = """
        SELECT QI.quantity, QI.unit_price, QI.line_total, S.service_name, S.unit
        FROM Quote_Items AS QI
        JOIN Services AS S ON QI.service_id = S.service_id
        WHERE QI.quote_id = %s
    """
    cursor.execute(sql_items, (quote_id,))
    quote_items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    if not quote_info:
        return "Không tìm thấy báo giá!", 404
        
    return render_template(CT_BG_HTML, 
                           quote_info=quote_info,
                           quote_items=quote_items)

# 5. (POST) Cập nhật Trạng thái Báo giá
@app.route('/update_quote_status/<int:quote_id>', methods=['POST'])
@requires_permission('sale') # Kinh Doanh
def update_quote_status(quote_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        new_status = request.form['quote_status']
        sql = "UPDATE Quotes SET status = %s WHERE quote_id = %s"
        cursor.execute(sql, (new_status, quote_id))
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Cập nhật Trạng thái Báo Giá #{quote_id}. Tổng tiền: {total_amount:,.0f}"
        log_system_action(cursor, 'UPDATE STATUS', 'Quotes', log_desc)
        # ===================
        
        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"LỖI KHI CẬP NHẬT TRẠNG THÁI BÁO GIÁ: {err}")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('quote_detail_page', quote_id=quote_id))

# 6. (POST) CHUYỂN BÁO GIÁ THÀNH ĐƠN HÀNG (VÀ TRỪ KHO)
@app.route('/convert_quote/<int:quote_id>', methods=['POST'])
@requires_permission('sale') # Kinh Doanh
def convert_quote_to_order(quote_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    new_order_id = -1 # Khởi tạo
    
    try:
        # --- BƯỚC 0: Kiểm tra xem Báo giá này đã được chuyển đổi chưa ---
        # (Chúng ta dùng cột 'quote_id' trong bảng 'Orders' mà ta đã tạo trước đó)
        cursor.execute("SELECT order_id FROM Orders WHERE quote_id = %s", (quote_id,))
        existing_order = cursor.fetchone()
        if existing_order:
            # Nếu đã có, không làm gì cả, chỉ chuyển đến đơn hàng đó
            return redirect(url_for('order_detail_page', order_id=existing_order['order_id']))

        # --- BƯỚC 1: Lấy thông tin Báo giá gốc ---
        cursor.execute("SELECT * FROM Quotes WHERE quote_id = %s", (quote_id,))
        quote_info = cursor.fetchone()
        
        cursor.execute("SELECT * FROM Quote_Items WHERE quote_id = %s", (quote_id,))
        quote_items_list = cursor.fetchall()
        
        if not quote_info or not quote_items_list:
            return "Lỗi: Báo giá không hợp lệ hoặc không có dịch vụ.", 400

        # --- BƯỚC 2: Tạo Đơn hàng (Orders) mới ---
        # (Lưu ý: chúng ta liên kết nó với quote_id)
        sql_insert_order = """
            INSERT INTO Orders (customer_id, total_amount, status, quote_id)
            VALUES (%s, %s, 'processing', %s)
        """
        val_insert_order = (quote_info['customer_id'], quote_info['total_amount'], quote_id)
        cursor.execute(sql_insert_order, val_insert_order)
        new_order_id = cursor.lastrowid # Lấy ID của Đơn hàng mới

        # --- BƯỚC 3 & 4: Lặp qua từng mục, INSERT và TRỪ KHO ---
        for item in quote_items_list:
            # --- BƯỚC 3a: INSERT vào Order_Items ---
            sql_insert_item = """
                INSERT INTO Order_Items (order_id, service_id, quantity, unit_price, line_total)
                VALUES (%s, %s, %s, %s, %s)
            """
            val_insert_item = (new_order_id, item['service_id'], item['quantity'], item['unit_price'], item['line_total'])
            cursor.execute(sql_insert_item, val_insert_item)
            
            # --- BƯỚC 3b: Tra cứu "Công thức" (Định mức) ---
            sql_get_bom = "SELECT material_id, quantity_consumed FROM Service_Materials WHERE service_id = %s"
            cursor.execute(sql_get_bom, (item['service_id'],))
            materials_to_update = cursor.fetchall()

            if not materials_to_update:
                continue # Dịch vụ này không cần vật tư, tiếp tục

            # --- BƯỚC 4: TRỪ KHO (Logic y hệt /submit_order) ---
            for material in materials_to_update:
                total_material_to_deduct = item['quantity'] * material['quantity_consumed']
                
                sql_update_stock = """
                    UPDATE Materials 
                    SET stock_quantity = stock_quantity - %s
                    WHERE material_id = %s
                """
                val_update_stock = (float(total_material_to_deduct), material['material_id'])
                cursor.execute(sql_update_stock, val_update_stock)
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Chuyển Báo Giá #{quote_id} thành đơn hàng. Tổng tiền: {total_amount:,.0f}"
        log_system_action(cursor, 'CONVERT', 'Quotes', log_desc)
        # ===================
        
        conn.commit() # Lưu tất cả thay đổi
        
    except mysql.connector.Error as err:
        conn.rollback() 
        print(f"LỖI KHI CHUYỂN BÁO GIÁ: {err}")
        return f"Đã xảy ra lỗi khi chuyển báo giá: {err}", 500
    finally:
        cursor.close()
        conn.close()
    
    # Chuyển hướng người dùng đến trang CHI TIẾT ĐƠN HÀNG vừa tạo
    return redirect(url_for('order_detail_page', order_id=new_order_id))

# ======================================================
# CẬP NHẬT BÁO GIÁ (EDIT QUOTES)
# ======================================================

# 1. (GET) Hiển thị trang SỬA Báo giá (đổ dữ liệu cũ vào)
@app.route('/edit_quote/<int:quote_id>')
@requires_permission('sale') # Kinh Doanh
def edit_quote_page(quote_id):
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query 1: Lấy thông tin chung của Báo giá
    cursor.execute("SELECT * FROM Quotes WHERE quote_id = %s", (quote_id,))
    quote_info = cursor.fetchone()
    
    # Query 2: Lấy các MỤC DỊCH VỤ (items) của báo giá này
    cursor.execute("SELECT * FROM Quote_Items WHERE quote_id = %s", (quote_id,))
    quote_items_list = cursor.fetchall()
    
    # Query 3 & 4: Lấy danh sách Khách hàng và Dịch vụ (cho dropdowns)
    cursor.execute("SELECT customer_id, customer_name FROM Customers ORDER BY customer_name")
    customers_list = cursor.fetchall()
    cursor.execute("SELECT service_id, service_name, base_price, unit FROM Services ORDER BY service_name")
    services_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    if not quote_info:
        return "Không tìm thấy báo giá!", 404
        
    # Chỉ cho sửa nếu báo giá đang 'pending'
    if quote_info['status'] != 'pending':
        return "Báo giá này đã được xử lý, không thể sửa.", 403
        
    return render_template(EDIT_QUOTE_HTML, 
                           quote_info=quote_info,
                           quote_items_list=quote_items_list, # <--- Rất quan trọng
                           customers_list=customers_list,
                           services_list=services_list)

# 2. (POST) Xử lý CẬP NHẬT Báo giá
@app.route('/update_quote/<int:quote_id>', methods=['POST'])
@requires_permission('sale') # Kinh Doanh
def update_quote(quote_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Lấy dữ liệu mới từ form
        customer_id = request.form['customer_id']
        tax_rate = float(request.form['tax_rate'])
        notes = request.form['notes']
        
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        # --- BƯỚC 1: XÓA SẠCH các Quote_Items CŨ ---
        cursor.execute("DELETE FROM Quote_Items WHERE quote_id = %s", (quote_id,))

        # --- BƯỚC 2: Tính toán lại tiền ---
        subtotal = 0
        for i in range(len(service_ids)):
            subtotal += int(quantities[i]) * float(unit_prices[i])
            
        tax_amount = subtotal * (tax_rate / 100)
        total_amount = subtotal + tax_amount

        # --- BƯỚC 3: INSERT LẠI các Quote_Items MỚI ---
        for i in range(len(service_ids)):
            service_id = service_ids[i]
            quantity = int(quantities[i])
            unit_price = float(unit_prices[i])
            line_total = quantity * unit_price
            
            sql_insert_item = """
                INSERT INTO Quote_Items (quote_id, service_id, description, quantity, unit_price, line_total)
                VALUES (%s, %s, '', %s, %s, %s)
            """
            val_insert_item = (quote_id, service_id, quantity, unit_price, line_total)
            cursor.execute(sql_insert_item, val_insert_item)
            
        # --- BƯỚC 4: CẬP NHẬT Bảng Quotes (và +1 count) ---
        sql_update_quote = """
            UPDATE Quotes 
            SET customer_id = %s, tax_rate = %s, notes = %s, 
                subtotal = %s, tax_amount = %s, total_amount = %s, 
                update_count = update_count + 1
            WHERE quote_id = %s
        """
        val_update = (customer_id, tax_rate, notes, subtotal, tax_amount, total_amount, quote_id)
        cursor.execute(sql_update_quote, val_update)
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Cập nhật Báo Giá #{quote_id}. Tổng tiền: {total_amount:,.0f}"
        log_system_action(cursor, 'UPDATE', 'Quotes', log_desc)
        # ===================
        
        conn.commit()
        
    except mysql.connector.Error as err:
        conn.rollback() 
        print(f"LỖI KHI CẬP NHẬT BÁO GIÁ: {err}")
        return f"Đã xảy ra lỗi: {err}", 500
    finally:
        cursor.close()
        conn.close()
    
    # Chuyển hướng về trang CHI TIẾT Báo giá
    return redirect(url_for('quote_detail_page', quote_id=quote_id))

# ======================================================
# QUẢN LÝ THIẾT BỊ (EQUIPMENT)
# ======================================================

# 1. (R)ead - Hiển thị trang Quản lý Thiết bị (ĐÃ NÂNG CẤP)
@app.route('/equipment')
@requires_permission('asset','accounting') # Kế toán và kho
def equipment_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query 1: Lấy danh sách thiết bị (JOIN với Suppliers)
    sql_eq = """
        SELECT E.*, S.supplier_name 
        FROM Equipment AS E
        LEFT JOIN Suppliers AS S ON E.supplier_id = S.supplier_id
        ORDER BY E.equipment_name
    """
    cursor.execute("SELECT * FROM Equipment ORDER BY equipment_name")
    equipment_list = cursor.fetchall()
    
    # Query 2: Lấy danh sách nhà cung cấp (cho dropdown)
    cursor.execute("SELECT supplier_id, supplier_name FROM Suppliers ORDER BY supplier_name")
    suppliers_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template(TB_HTML, 
                            equipment_list=equipment_list,
                            suppliers_list=suppliers_list)

# 2. (C)reate - Xử lý thêm thiết bị mới (ĐÃ NÂNG CẤP)
@app.route('/add_equipment', methods=['POST'])
@requires_permission('asset','accounting') # Kế toán và kho
def add_equipment():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Lấy dữ liệu cơ bản
        name = request.form['equipment_name']
        model = request.form['model_number']
        
        # === LẤY DỮ LIỆU MỚI ===
        ip_addr = request.form.get('ip_address')
        serial = request.form.get('serial_number')
        # === KẾT THÚC ===
        
        p_date = request.form['purchase_date']
        supplier_id = request.form['supplier_id'] # <--- TRƯỜNG MỚI
        
        # === LẤY DỮ LIỆU BẢO HÀNH (MỚI) ===
        w_date = request.form.get('warranty_end_date')
        w_counter = request.form.get('warranty_end_counter')
        
        # === LẤY COUNTER BAN ĐẦU (MỚI) ===
        init_counter = request.form.get('initial_counter')
        # Nếu không nhập thì mặc định là 0
        val_print_count = int(init_counter) if init_counter and init_counter.strip() else 0
        # === KẾT THÚC ===
        
        # Xử lý giá trị Null (nếu người dùng để trống)
        val_supplier = (supplier_id if supplier_id else None)
        val_p_date = (p_date if p_date else None)
        val_w_date = (w_date if w_date else None)
        val_w_counter = (int(w_counter) if w_counter and w_counter.strip() else None)
        
        sql = """
            INSERT INTO Equipment (
                equipment_name, ip_address, serial_number, model_number, supplier_id, purchase_date, 
                warranty_end_date, warranty_end_counter, status, print_count
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s)
        """
        
        val = (name, ip_addr, serial, model, val_supplier, val_p_date, val_w_date, val_w_counter, val_print_count)
        
        cursor.execute(sql, val)
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thêm Thiết Bị #{cursor.lastrowid}."
        log_system_action(cursor, 'ADD', 'Equipment', log_desc)
        # ===================
        
        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Lỗi SQL: {err}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('equipment_page'))

# 3. (D)elete - Xử lý xóa thiết bị
@app.route('/delete_equipment/<int:equipment_id>', methods=['POST'])
@requires_permission('all') # Admin
def delete_equipment(equipment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # (Lưu ý: Để xóa máy, bạn phải xóa các log bảo trì của nó trước)
        # Chúng ta sẽ thêm logic này sau
        sql = "DELETE FROM Equipment WHERE equipment_id = %s"
        cursor.execute(sql, (equipment_id,))
        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Lỗi: {err}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('equipment_page'))

# 4. (GET) Hiển thị trang CHI TIẾT của một Thiết bị (ĐÃ NÂNG CẤP)
@app.route('/equipment_detail/<int:equipment_id>')
@requires_permission('asset','accounting') # Kế toán và kho
def equipment_detail_page(equipment_id):
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query 1: Lấy thông tin của máy
    sql_eq = "SELECT * FROM Equipment WHERE equipment_id = %s"
    cursor.execute(sql_eq, (equipment_id,))
    equipment_info = cursor.fetchone()
    
    # Query 2: Lấy lịch sử bảo trì (JOIN với Suppliers VÀ Materials)
    sql_logs = """
        SELECT ML.*, S.supplier_name, M.material_name AS replaced_part_name 
        FROM Maintenance_Logs AS ML
        LEFT JOIN Suppliers AS S ON ML.supplier_id = S.supplier_id
        LEFT JOIN Materials AS M ON ML.replaced_material_id = M.material_id
        WHERE ML.equipment_id = %s 
        ORDER BY ML.maintenance_date DESC
    """
    cursor.execute(sql_logs, (equipment_id,))
    logs_list = cursor.fetchall()
    
    # Query 3: Lấy danh sách nhà cung cấp (cho dropdown NCC)
    cursor.execute("SELECT supplier_id, supplier_name FROM Suppliers ORDER BY supplier_name")
    suppliers_list = cursor.fetchall()
    
    # === QUERY MỚI ===
    # Query 4: Lấy danh sách LINH KIỆN BẢO TRÌ (cho dropdown linh kiện)
    sql_parts = """
        SELECT material_id, material_name, stock_quantity 
        FROM Materials 
        WHERE material_type = 'maintenance'
        ORDER BY material_name
    """
    cursor.execute(sql_parts)
    maintenance_parts_list = cursor.fetchall()
    # === KẾT THÚC ===
    
    cursor.close()
    conn.close()
    
    if not equipment_info:
        return "Không tìm thấy thiết bị!", 404
        
    return render_template(CT_TB_HTML, 
                           equipment_info=equipment_info,
                           logs_list=logs_list,
                           suppliers_list=suppliers_list, # Gửi danh sách NCC ra)
                           maintenance_parts_list=maintenance_parts_list) # <-- Gửi danh sách linh kiện

# 5. (POST) Xử lý thêm một Nhật ký Bảo trì mới
@app.route('/add_maintenance_log', methods=['POST'])
@requires_permission('asset','accounting') # Kế toán và kho
def add_maintenance_log():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Lấy dữ liệu từ form (bao gồm cả ID ẩn)
        equipment_id = request.form['equipment_id']
        maintenance_date = request.form['maintenance_date']
        description = request.form['description']
        
        #cost = float(request.form['cost']) if request.form['cost'] else 0
        # Xử lý cost an toàn
        cost_str = request.form.get('cost')
        cost = float(cost_str) if cost_str and cost_str.strip() else 0
        
        supplier_id = request.form['supplier_id'] # <--- TRƯỜNG MỚI
        technician_name = request.form['technician_name']
        
        # === DỮ LIỆU MỚI TỪ FORM ===
        replaced_material_id = request.form['replaced_material_id']
        
        #replaced_quantity = int(request.form['replaced_quantity'])
        # Xử lý quantity an toàn
        qty_str = request.form.get('replaced_quantity')
        replaced_quantity = int(qty_str) if qty_str and qty_str.strip() else 0
        
        # Lấy số Counter hiện tại mà người dùng nhập vào (để cập nhật cho máy)
        #current_machine_counter = int(request.form['current_machine_counter'])
        # === SỬA LỖI TẠI ĐÂY (Dùng .get thay vì []) ===
        # Lấy Counter an toàn: Nếu không tìm thấy, mặc định là 0
        counter_str = request.form.get('current_machine_counter')
        current_machine_counter = int(counter_str) if counter_str and counter_str.strip() else 0 
        # === KẾT THÚC ===
        
        # Tự động quyết định trạng thái thanh toán
        #payment_status = 'unpaid' if cost > 0 else 'paid'
        # === LOGIC MỚI (LẤY TỪ FORM) ===
        # Lấy lựa chọn của người dùng ('paid' hoặc 'unpaid')
        payment_status_input = request.form.get('payment_status')
        
        if payment_status_input:
            payment_status = payment_status_input
        else:
            # Fallback: Nếu không chọn gì thì dùng logic cũ (an toàn)
            payment_status = 'unpaid' if cost > 0 else 'paid'
        # === KẾT THÚC ===
        
        # --- LẤY DỮ LIỆU BẢO HÀNH (KÉP) ---
        # 1. Bảo hành theo ngày
        warranty_date = request.form.get('warranty_end_date')
        val_warranty_date = (warranty_date if warranty_date else None)
        
        # 2. Bảo hành theo Counter (MỚI)
        warranty_counter_str = request.form.get('warranty_end_counter')
        val_warranty_counter = int(warranty_counter_str) if warranty_counter_str and warranty_counter_str.strip() else None
        # === KẾT THÚC ===
        
        val_supplier = (supplier_id if supplier_id else None)
        val_material = (replaced_material_id if replaced_material_id else None)
        
        # === [LOGIC MỚI] XỬ LÝ NHẬP KHO TỰ ĐỘNG (NẾU CÓ NHÀ CUNG CẤP) ===
        # Nếu có chọn NCC và có thay linh kiện -> Tự động nhập kho trước
        if val_supplier and val_material and replaced_quantity > 0:
            
            # 1. Cộng Tồn kho (+)
            sql_stock_in = "UPDATE Materials SET stock_quantity = stock_quantity + %s WHERE material_id = %s"
            cursor.execute(sql_stock_in, (replaced_quantity, val_material))
            
            # 2. Tạo Phiếu Nhập Kho tự động (Để lưu vết)
            # Lưu ý: Giá nhập = 0 và Status = 'paid' để tránh tính công nợ KÉP
            # (Vì công nợ đã được tính vào chi phí bảo trì ở dưới rồi)
            sql_auto_import = """
                INSERT INTO Material_Imports (material_id, supplier_id, import_date, 
                                            quantity_imported, import_price, payment_status)
                VALUES (%s, %s, %s, %s, 0, %s)
            """
            cursor.execute(sql_auto_import, (val_material, val_supplier, maintenance_date, replaced_quantity))
        # === KẾT THÚC LOGIC MỚI ===
        
       # --- BƯỚC 1: INSERT LOG (CẬP NHẬT SQL THÊM warranty_end_counter) ---
        # Dù là nhập lại nhật ký cũ, ta vẫn lưu counter cũ vào log để tính toán lịch sử thay thế
        sql = """
            INSERT INTO Maintenance_Logs (equipment_id, supplier_id, maintenance_date, 
                                        description, cost, technician_name, payment_status,
                                        replaced_material_id, replaced_quantity, current_counter_at_log,
                                        warranty_end_date, warranty_end_counter) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        val = (equipment_id, val_supplier, maintenance_date, description, cost, 
               technician_name, payment_status, val_material, replaced_quantity, current_machine_counter,
               val_warranty_date, val_warranty_counter)
        cursor.execute(sql, val)
        
        # --- BƯỚC 2: CẬP NHẬT COUNTER CHO MÁY (LOGIC MỚI THÔNG MINH) ---
        # Chỉ cập nhật NẾU số mới (current_machine_counter) LỚN HƠN số hiện tại trong DB
        if current_machine_counter > 0:
            sql_update_counter = """
                UPDATE Equipment 
                SET print_count = %s 
                WHERE equipment_id = %s AND print_count < %s
            """
            # Tham số thứ 3 cũng là current_machine_counter để so sánh
            cursor.execute(sql_update_counter, (current_machine_counter, equipment_id, current_machine_counter))
        
        # --- BƯỚC 3: TRỪ KHO Linh kiện (Nếu có thay) ---
        if val_material and replaced_quantity > 0:
            
            # TRỪ KHO Linh kiện
            sql_update_stock = """
                UPDATE Materials 
                SET stock_quantity = stock_quantity - %s
                WHERE material_id = %s
            """
            cursor.execute(sql_update_stock, (replaced_quantity, val_material))
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Bảo trì máy ID {equipment_id}. Chi phí: {cost:,.0f}"
        log_system_action(cursor, 'MAINTENANCE', 'Equipment', log_desc)
        # ===================
        
        conn.commit()
        
    except mysql.connector.Error as err:
        conn.rollback() 
        print(f"LỖI KHI THÊM NHẬT KÝ BẢO TRÌ: {err}")
    finally:
        cursor.close()
        conn.close()
    
    # Quay lại trang chi tiết của chính máy đó
    return redirect(url_for('equipment_detail_page', equipment_id=equipment_id))

# 6. (POST) Cập nhật Thông tin Thiết bị (Sửa tên, IP, Serial...)
@app.route('/edit_equipment_info', methods=['POST'])
@requires_permission('asset') # Kho
def edit_equipment_info():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        equipment_id = request.form['equipment_id']
        name = request.form['equipment_name']
        ip_addr = request.form.get('ip_address')
        serial = request.form.get('serial_number')
        model = request.form['model_number']
        supplier_id = request.form.get('supplier_id')
        p_date = request.form.get('purchase_date')
        w_date = request.form.get('warranty_end_date')
        
        # Xử lý null
        val_supplier = (supplier_id if supplier_id else None)
        val_p_date = (p_date if p_date else None)
        val_w_date = (w_date if w_date else None)

        sql = """
            UPDATE Equipment 
            SET equipment_name = %s, ip_address = %s, serial_number = %s, 
                model_number = %s, supplier_id = %s, purchase_date = %s, 
                warranty_end_date = %s
            WHERE equipment_id = %s
        """
        val = (name, ip_addr, serial, model, val_supplier, val_p_date, val_w_date, equipment_id)
        
        cursor.execute(sql, val)
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Cập nhật thông tin Thiết Bị #{equipment_id}."
        log_system_action(cursor, 'UPDATE', 'Equipment', log_desc)
        # ===================
        
        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Lỗi SQL: {err}")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('equipment_detail_page', equipment_id=equipment_id))

# 7. Thay the delete để bảo toàn dữ liệu
@app.route('/toggle_equipment/<int:id>', methods=['POST'])
@requires_permission('all') # Admin
def toggle_equipment(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Equipment SET is_active = NOT is_active WHERE equipment_id = %s", (id,))
    
    # == THÊM DÒNG NÀY ==
    log_desc = f"Khóa Thiết Bị #{id}."
    log_system_action(cursor, 'TOGGLE', 'Equipment', log_desc)
    # ===================
    
    conn.commit()
    conn.close()
    return redirect(url_for('equipment_page'))

# ======================================================
# TRANG CHỦ (DASHBOARD)
# ======================================================
@app.route('/dashboard')
@login_required # <--- THÊM DÒNG NÀY
def dashboard_page():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    today = datetime.date.today()
    
    # === 1. LOGIC TỰ ĐỘNG HỦY BÁO GIÁ QUÁ 7 NGÀY ===
    # Logic: Tìm các báo giá 'pending' mà ngày tạo < (Hôm nay - 7 ngày)
    # Cập nhật thành 'rejected' và thêm ghi chú tự động
    sql_auto_expire = """
        UPDATE Quotes 
        SET status = 'rejected', 
            notes = CONCAT(IFNULL(notes, ''), ' [HỆ THỐNG: Tự động hủy do quá hạn 7 ngày]')
        WHERE status = 'pending' 
          AND created_date < DATE_SUB(NOW(), INTERVAL 7 DAY)
    """
    cursor.execute(sql_auto_expire)
    conn.commit() # Lưu thay đổi ngay lập tức
    # ===============================================

    # --- CHẠY CÁC TRUY VẤN (QUERY) ĐỂ LẤY SỐ LIỆU ---

    # 1. Doanh thu hôm nay
    sql_rev_today = "SELECT SUM(total_amount) AS total FROM Orders WHERE DATE(order_date) = %s AND status != 'cancelled'" 
    cursor.execute(sql_rev_today, (today,))
    revenue_today = cursor.fetchone()['total'] or 0
    
    # 1b. [MỚI] Doanh thu bị hủy hôm nay (Để theo dõi)
    cursor.execute("""
        SELECT SUM(total_amount) AS total 
        FROM Orders 
        WHERE DATE(order_date) = %s AND status = 'cancelled'
    """, (today,))
    revenue_cancelled_today = cursor.fetchone()['total'] or 0

    # 2. Số đơn hàng mới hôm nay
    sql_orders_today = "SELECT COUNT(order_id) AS count FROM Orders WHERE DATE(order_date) = %s AND status != 'cancelled'"
    cursor.execute(sql_orders_today, (today,))
    orders_today = cursor.fetchone()['count']

    # 3. Tổng công nợ PHẢI THU (Khách nợ mình)
    cursor.execute("SELECT SUM(total_amount - amount_paid) AS total FROM Orders WHERE payment_status != 'paid' AND status != 'cancelled'")
    total_due_customer = cursor.fetchone()['total'] or 0

    # 4. Tổng công nợ PHẢI TRẢ (Mình nợ NCC)
    # 4a. Nợ nhập kho (SỬA: Lấy từ Import_Slips)
    cursor.execute("SELECT SUM(total_amount) AS total FROM Import_Slips WHERE payment_status = 'unpaid'")
    due_imports = cursor.fetchone()['total'] or 0
    # 4b. Nợ bảo trì
    cursor.execute("SELECT SUM(cost) AS total FROM Maintenance_Logs WHERE payment_status = 'unpaid' AND cost > 0")
    due_maintenance = cursor.fetchone()['total'] or 0
    # 4c. Tổng nợ NCC
    total_due_supplier = due_imports + due_maintenance
    
    # 5. Số báo giá đang chờ (pending)
    cursor.execute("SELECT COUNT(quote_id) AS count FROM Quotes WHERE status = 'pending'")
    pending_quotes = cursor.fetchone()['count'] or 0

    # 6. Đơn hàng đang chờ giao
    sql_pending_delivery = "SELECT COUNT(order_id) AS count FROM Orders WHERE delivery_status = 'pending'"
    cursor.execute(sql_pending_delivery)
    pending_delivery = cursor.fetchone()['count']
    
    # 7. Vật tư sắp hết (ví dụ: tồn kho dưới 500 tờ giấy)
    LOW_STOCK_THRESHOLD = 500 # Bạn có thể thay đổi con số này
    sql_low_stock = "SELECT * FROM Materials WHERE stock_quantity < %s ORDER BY stock_quantity ASC"
    cursor.execute(sql_low_stock, (LOW_STOCK_THRESHOLD,))
    low_stock_items = cursor.fetchall()
    
    # === 8. QUERY MỚI: CẢNH BÁO BẢO TRÌ ===
    # Logic:
    # 1. Lấy log thay thế linh kiện gần nhất cho mỗi cặp (Máy, Linh kiện)
    # 2. Tính toán độ bền còn lại
    sql_maintenance_alerts = """
        SELECT 
            E.equipment_name,
            E.print_count AS current_machine_counter,
            M.material_name,
            M.lifespan_prints,
            ML.current_counter_at_log AS last_replaced_at,
            (ML.current_counter_at_log + M.lifespan_prints) AS next_due_at,
            (ML.current_counter_at_log + M.lifespan_prints - E.print_count) AS remaining_prints
        FROM Maintenance_Logs AS ML
        JOIN Equipment AS E ON ML.equipment_id = E.equipment_id
        JOIN Materials AS M ON ML.replaced_material_id = M.material_id
        WHERE M.material_type = 'maintenance' AND M.lifespan_prints > 0
        AND ML.log_id IN (
            SELECT MAX(log_id)
            FROM Maintenance_Logs
            WHERE replaced_material_id IS NOT NULL
            GROUP BY equipment_id, replaced_material_id
        )
        -- SỬA DÒNG NÀY: Tăng ngưỡng lên thật cao (ví dụ 1 triệu) để hiện TẤT CẢ
        -- Hoặc xóa hẳn dòng HAVING này đi để test
        HAVING remaining_prints < 1000000 
        ORDER BY remaining_prints ASC
    """
    cursor.execute(sql_maintenance_alerts)
    maintenance_alerts = cursor.fetchall()
    # === KẾT THÚC ===
    
    # === 9. DANH SÁCH BÁO GIÁ VỪA HẾT HẠN (QUERY MỚI) ===
    # Lấy danh sách các báo giá đã bị hủy và có ghi chú của hệ thống
    sql_expired_quotes = """
        SELECT Q.quote_id, Q.created_date, C.customer_name, Q.total_amount
        FROM Quotes AS Q
        JOIN Customers AS C ON Q.customer_id = C.customer_id
        WHERE Q.status = 'rejected' 
          AND Q.notes LIKE '%[HỆ THỐNG: Tự động hủy%'
        ORDER BY Q.created_date DESC
        LIMIT 5
    """
    cursor.execute(sql_expired_quotes)
    expired_quotes_list = cursor.fetchall()
    # ====================================================
    
    cursor.close()
    conn.close()

    # Gửi tất cả số liệu ra template
    return render_template('dashboard.html',
                           revenue_today=revenue_today,
                           revenue_cancelled_today=revenue_cancelled_today, # <-- Gửi biến mới
                           orders_today=orders_today,
                           total_due_customer=total_due_customer,
                           total_due_supplier=total_due_supplier, # <--- BIẾN MỚI
                           pending_quotes=pending_quotes,
                           pending_delivery=pending_delivery,
                           low_stock_items=low_stock_items,
                           maintenance_alerts=maintenance_alerts, # <-- Gửi biến mới ra
                           expired_quotes_list=expired_quotes_list # <-- Gửi danh sách hết hạn
                           )

# ======================================================
# BÁO CÁO: CÔNG NỢ KHÁCH HÀNG (AI NỢ MÌNH)
# ======================================================
@app.route('/report/customer_debt')
@requires_permission('accounting', 'sale') # Kế toán và Kinh doanh
def customer_debt_report():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query: Nhóm tất cả công nợ theo TỪNG KHÁCH HÀNG
    # Chỉ lấy những khách hàng có tổng nợ > 0
    sql = """
        SELECT 
            C.customer_id, 
            C.customer_name, 
            C.phone,
            SUM(O.total_amount - O.amount_paid) AS total_due
        FROM Orders AS O
        JOIN Customers AS C ON O.customer_id = C.customer_id
        WHERE O.payment_status != 'paid'
            AND O.status != 'cancelled' -- THÊM DÒNG NÀY
        GROUP BY C.customer_id, C.customer_name, C.phone
        HAVING total_due > 0
        ORDER BY total_due DESC
    """
    cursor.execute(sql)
    debt_list = cursor.fetchall()
    
    # Tính tổng của tất cả công nợ
    total_all_due = sum(item['total_due'] for item in debt_list)
    
    cursor.close()
    conn.close()
    
    return render_template(CUSTOMER_DEBT_REPORT_HTML, 
                           debt_list=debt_list,
                           total_all_due=total_all_due)

# ======================================================
# BÁO CÁO: CHI TIẾT CÔNG NỢ (THEO TỪNG KHÁCH)
# ======================================================
@app.route('/report/customer_debt/<int:customer_id>')
@requires_permission('accounting', 'sale') # Kế toán và Kinh doanh
def customer_debt_detail_report(customer_id):
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query 1: Lấy thông tin khách hàng
    cursor.execute("SELECT * FROM Customers WHERE customer_id = %s", (customer_id,))
    customer_info = cursor.fetchone()

    # Query 2: Lấy tất cả các ĐƠN HÀNG CHƯA THANH TOÁN của khách này
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
            AND status != 'cancelled' -- THÊM DÒNG NÀY
        ORDER BY order_date ASC
    """
    cursor.execute(sql, (customer_id,))
    unpaid_orders_list = cursor.fetchall()
    
    # Tính tổng nợ của riêng khách này
    total_due = sum(item['amount_due'] for item in unpaid_orders_list)
    
    cursor.close()
    conn.close()
    
    if not customer_info:
        return "Không tìm thấy khách hàng!", 404
        
    return render_template(CUSTOMER_DEBT_DETAIL_HTML, 
                           customer_info=customer_info,
                           unpaid_orders_list=unpaid_orders_list,
                           total_due=total_due)

# ======================================================
# BÁO CÁO: CÔNG NỢ NHÀ CUNG CẤP (MÌNH NỢ AI)
# ======================================================
@app.route('/report/supplier_debt')
@requires_permission('accounting', 'inventory') # Kế toán và Kho
def supplier_debt_report():
    conn = get_db_connection()
    if conn is None:
        return "Lỗi kết nối database!", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query 1: Lấy công nợ từ PHIẾU NHẬP KHO (Import_Slips) - [MỚI]
    sql_imports = """
        SELECT 
            S.slip_id AS id, 
            S.import_date AS date, 
            COALESCE(Sup.supplier_name, 'Không xác định') as supplier_name,
            S.total_amount,
            'Phiếu nhập kho' AS type,
            S.payment_status,
            'import_slip' AS source, -- Đánh dấu nguồn mới
            NULL AS material_id
        FROM Import_Slips AS S
        LEFT JOIN Suppliers AS Sup ON S.supplier_id = Sup.supplier_id
        WHERE S.payment_status = 'unpaid'
    """
    cursor.execute(sql_imports)
    import_debts = cursor.fetchall()
    
    # Query 2: Lấy công nợ BẢO TRÌ (Sửa JOIN thành LEFT JOIN)
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
    
    # Gộp 2 danh sách nợ lại và sắp xếp theo ngày
    all_debts = import_debts + maintenance_debts
    all_debts.sort(key=lambda x: x['date'], reverse=True)
    
    # Tính tổng nợ phải trả
    total_all_due = sum(item['total_amount'] for item in all_debts)
    
    cursor.close()
    conn.close()
    
    return render_template(SUPPLIER_DEBT_REPORT, 
                           all_debts=all_debts,
                           total_all_due=total_all_due)

# ======================================================
# BÁO CÁO: XỬ LÝ THANH TOÁN CÔNG NỢ NCC
# ======================================================
@app.route('/pay_supplier_bill', methods=['POST'])
@requires_permission('accounting') # Kế toán và Kho
def pay_supplier_bill():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Lấy dữ liệu từ form (qua các trường ẩn)
        bill_id = request.form['bill_id']
        bill_source = request.form['bill_source'] # ('import' hoặc 'maintenance')

        if bill_source == 'import_slip': # <--- SỬA DÒNG NÀY
            # Cập nhật bảng Import_Slips
            sql = "UPDATE Import_Slips SET payment_status = 'paid' WHERE slip_id = %s"
        
        elif bill_source == 'maintenance':
            # Nếu là nợ bảo trì
            sql = "UPDATE Maintenance_Logs SET payment_status = 'paid' WHERE log_id = %s"
        
        else:
            # Trường hợp không xác định
            return "Lỗi: Nguồn công nợ không xác định.", 400

        cursor.execute(sql, (bill_id,))
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Trả tiền NCC Hóa Đơn ID #{bill_id}."
        log_system_action(cursor, 'UPDATE', 'Maintenance_Logs', log_desc)
        # ===================
        
        conn.commit()
        
    except mysql.connector.Error as err:
        conn.rollback() 
        print(f"LỖI KHI THANH TOÁN NCC: {err}")
        return f"Đã xảy ra lỗi: {err}", 500
    finally:
        cursor.close()
        conn.close()
    
    # Quay lại trang báo cáo công nợ
    return redirect(url_for('supplier_debt_report'))

# ======================================================
# QUẢN LÝ COUPONS (Mã Giảm Giá)
# ======================================================
# 1. (R)ead - Danh sách Mã giảm giá
@app.route('/coupons')
def coupons_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Coupons ORDER BY end_date DESC")
    coupons_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(COUPONS_HTML, coupons_list=coupons_list)

# 2. (C)reate - Thêm Mã mới
@app.route('/add_coupon', methods=['POST'])
def add_coupon():
    conn = get_db_connection()
    cursor = conn.cursor()
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
        cursor.execute(sql, val)
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Tạo Mã KM ID #{cursor.lastrowid}."
        log_system_action(cursor, 'CREATE', 'Coupons', log_desc)
        # ===================
        
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Lỗi: {err}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('coupons_page'))

# 3. (D)elete - Xóa/Vô hiệu hóa Mã
@app.route('/toggle_coupon_status/<int:coupon_id>', methods=['POST'])
def toggle_coupon_status(coupon_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Đảo ngược trạng thái (Active <-> Inactive) thay vì xóa hẳn
    cursor.execute("UPDATE Coupons SET status = IF(status='active','inactive','active') WHERE coupon_id = %s", (coupon_id,))
    
    # == THÊM DÒNG NÀY ==
    log_desc = f"Bật Tắt Mã KM ID #{coupon_id}."
    log_system_action(cursor, 'TOGGLE', 'Coupons', log_desc)
    # ===================
    
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('coupons_page'))

# ======================================================
# AJAX (GIAO TIẾP NGẦM)
# ======================================================
# 1. AJAX - Thêm nhanh Khách hàng
@app.route('/ajax/add_customer', methods=['POST'])
@requires_permission('accounting', 'sale') # Kế toán và Kho
def ajax_add_customer():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        name = request.form['customer_name']
        phone = request.form['phone']
        
        sql = "INSERT INTO Customers (customer_name, phone) VALUES (%s, %s)"
        val = (name, phone)
        cursor.execute(sql, val)
        new_id = cursor.lastrowid # Lấy ID của khách vừa tạo
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thêm nhanh Khách Hàng ID {new_id}"
        log_system_action(cursor, 'QUICK ADD', 'Customers', log_desc)
        # ===================
        
        conn.commit()
        
        # Trả về dữ liệu JSON cho JavaScript
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'error': str(err)})
    finally:
        cursor.close()
        conn.close()

# 2. AJAX - Thêm nhanh Dịch vụ
@app.route('/ajax/add_service', methods=['POST'])
@requires_permission('sale', 'inventory') # Kế toán và Kho
def ajax_add_service():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Lấy dữ liệu cơ bản từ form modal
        name = request.form['service_name']
        price = float(request.form['base_price'])
        
        # === LẤY 3 TẦNG ĐƠN VỊ ===
        u1 = request.form['unit'] # Tầng 1 (Bắt buộc)
        u2 = request.form.get('unit_level2') # Tùy chọn
        u3 = request.form.get('unit_level3') # Tùy chọn
        
        # Xử lý chuỗi rỗng thành None để lưu vào DB cho sạch
        if not u2 or u2.strip() == '': u2 = None
        if not u3 or u3.strip() == '': u3 = None
        # ==========================
        
        sql = """
            INSERT INTO Services (service_name, base_price, unit, unit_level2, unit_level3, description) 
            VALUES (%s, %s, %s, %s, %s, '')
        """
        val = (name, price, u1, u2, u3)
        cursor.execute(sql, val)
        new_id = cursor.lastrowid
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thêm nhanh Dịch vụ ID {new_id}"
        log_system_action(cursor, 'QUICK ADD', 'Services', log_desc)
        # ===================
        
        conn.commit()
        
        # Trả về JSON đầy đủ thông tin để JS cập nhật giao diện
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name,
            'new_price': price,
            'new_u1': u1,
            'new_u2': u2 if u2 else '',
            'new_u3': u3 if u3 else ''
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'error': str(err)})
    finally:
        cursor.close()
        conn.close()

# 3. AJAX - Thêm nhanh Vật tư
@app.route('/ajax/add_material', methods=['POST'])
@requires_permission('sale', 'inventory') # Kế toán và Kho
def ajax_add_material():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Lấy đầy đủ thông tin từ form modal
        name = request.form['material_name']
        base_unit = request.form['base_unit']
        import_unit = request.form['import_unit']
        conversion_factor = float(request.form['import_conversion_factor'])
        
        sql = """
            INSERT INTO Materials (material_name, material_type, base_unit, import_unit, 
                                   import_conversion_factor, stock_quantity) 
            VALUES (%s, 'production', %s, %s, %s, 0)
        """
        # Mặc định thêm là 'production' và tồn kho 0
        val = (name, base_unit, import_unit, conversion_factor)
        cursor.execute(sql, val)
        new_id = cursor.lastrowid # Lấy ID của vật tư vừa tạo
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thêm nhanh Vật Tư ID {new_id}"
        log_system_action(cursor, 'QUICK ADD', 'Materials', log_desc)
        # ===================
        
        conn.commit()
        
        # Trả về dữ liệu JSON cho JavaScript
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name,
            'new_import_unit': import_unit
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'error': str(err)})
    finally:
        cursor.close()
        conn.close()

# 4. AJAX - Thêm nhanh Nhà cung cấp
@app.route('/ajax/add_supplier', methods=['POST'])
@requires_permission('accounting', 'inventory') # Kế toán và Kho
def ajax_add_supplier():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        name = request.form['supplier_name']
        phone = request.form['phone']
        email = request.form['email']
        
        sql = "INSERT INTO Suppliers (supplier_name, phone, email) VALUES (%s, %s, %s)"
        cursor.execute(sql, (name, phone, email))
        new_id = cursor.lastrowid
        
        # == THÊM DÒNG NÀY ==
        log_desc = f"Thêm nhanh NCC ID {new_id}"
        log_system_action(cursor, 'QUICK ADD', 'Suppliers', log_desc)
        # ===================
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name
        })
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'error': str(err)})
    finally:
        cursor.close()
        conn.close()

# 5. THÊM API KIỂM TRA MÃ
@app.route('/ajax/check_coupon', methods=['POST'])
@requires_permission('sale') # Kinh doanh
def check_coupon():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    code = request.form['code'].upper()
    order_total = float(request.form['order_total'])
    today = datetime.date.today()
    
    # 1. Tìm mã trong DB
    sql = "SELECT * FROM Coupons WHERE code = %s AND status = 'active'"
    cursor.execute(sql, (code,))
    coupon = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not coupon:
        return jsonify({'valid': False, 'message': 'Mã không tồn tại hoặc đã bị tắt.'})
    
    # 2. Kiểm tra điều kiện
    if coupon['start_date'] > today or coupon['end_date'] < today:
        return jsonify({'valid': False, 'message': 'Mã chưa đến hạn hoặc đã hết hạn.'})
        
    if order_total < coupon['min_order_value']:
        return jsonify({'valid': False, 'message': f'Đơn hàng phải từ {coupon["min_order_value"]} trở lên.'})
        
    if coupon['usage_limit'] > 0 and coupon['used_count'] >= coupon['usage_limit']:
        return jsonify({'valid': False, 'message': 'Mã đã hết lượt sử dụng.'})
    
    # 3. Tính toán số tiền giảm
    discount_amount = 0
    if coupon['discount_type'] == 'fixed':
        discount_amount = float(coupon['discount_value'])
    else:
        discount_amount = order_total * (float(coupon['discount_value']) / 100)
        
    # Không giảm quá giá trị đơn hàng
    if discount_amount > order_total:
        discount_amount = order_total

    return jsonify({
        'valid': True,
        'message': 'Áp dụng thành công!',
        'discount_amount': discount_amount,
        'code': code
    })

# Route mặc định (chuyển thẳng đến trang services)
@app.route('/')
def index():
    return redirect(url_for('dashboard_page'))

# Dòng này để chạy ứng dụng
if __name__ == '__main__':
    app.run(debug=True) # debug=True giúp tự động tải lại khi có thay đổi