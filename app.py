import os
import datetime  # <--- BỔ SUNG DÒNG NÀY
import math      # <--- Bổ sung luôn để dùng cho phân trang sau này
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv # Nhớ pip install python-dotenv
load_dotenv() # Nó sẽ tự đọc file .env

app = Flask(__name__)
app.secret_key = 'khoa_bi_mat_sieu_cap'

@app.template_filter('currency')
def currency_filter(value):
    try:
        if value is None: return "0"
        return "{:,.0f}".format(value)
    except:
        return value

# --- CẤU HÌNH DATABASE ---

# Cách 1: Lấy từ biến môi trường (Khi chạy trên Render)
DATABASE_URL = os.environ.get('DATABASE_URL')

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

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Lỗi kết nối: {e}")
        return None

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
        hashed_pw = generate_password_hash('123456')
        cur.execute("INSERT INTO Users (username, password_hash, full_name, role_id) VALUES ('admin', %s, 'Super Admin', 1)", (hashed_pw,))
        conn.commit()
        return "Tạo Admin thành công! User: admin / Pass: 123456"
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
        cur = conn.cursor()
        cur.execute("SELECT * FROM Users WHERE username = %s", (username,))
        user = cur.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['user_id'], user['username'], user['full_name'], user['role_id'])
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        else:
            flash('Sai mật khẩu!')
    return render_template(LOGIN_HTML) # Đảm bảo bạn có file login.html

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

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

# --- QUẢN LÝ DỊCH VỤ ---

@app.route('/services')
@login_required
def services_page():
    conn = get_db_connection()
    cur = conn.cursor()
    # PostgreSQL dùng cú pháp SQL chuẩn, không khác biệt nhiều ở SELECT
    cur.execute("SELECT * FROM Services ORDER BY service_id DESC")
    services = cur.fetchall()
    conn.close()
    return render_template(SERVICES_HTML, services_list=services)

@app.route('/add_service', methods=['POST'])
@login_required
def add_service():
    if request.method == 'POST':
        name = request.form['service_name']
        price = request.form['base_price']
        unit = request.form['unit']
        # Các cột level 2, 3 tùy chọn
        u2 = request.form.get('unit_level2') or None
        u3 = request.form.get('unit_level3') or None
        desc = request.form.get('description', '')

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # KHÁC BIỆT: Thêm RETURNING service_id để lấy ID vừa tạo
            sql = """
                INSERT INTO Services (service_name, base_price, unit, unit_level2, unit_level3, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING service_id
            """
            cur.execute(sql, (name, price, unit, u2, u3, desc))
            
            # Lấy ID vừa tạo (thay cho cursor.lastrowid)
            new_id = cur.fetchone()['service_id']
            
            conn.commit()
            flash('Thêm dịch vụ thành công!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Lỗi: {e}', 'danger')
        finally:
            conn.close()
            
        return redirect(url_for('services_page'))

@app.route('/edit_service/<int:service_id>')
@login_required
def edit_service_page(service_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Services WHERE service_id = %s", (service_id,))
    service = cur.fetchone()
    conn.close()
    
    if service:
        return render_template(EDIT_SERVICE_HTML, service=service)
    return "Không tìm thấy dịch vụ", 404

@app.route('/update_service', methods=['POST'])
@login_required
def update_service():
    service_id = request.form['service_id']
    name = request.form['service_name']
    price = request.form['base_price']
    unit = request.form['unit']
    desc = request.form.get('description', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = """
            UPDATE Services 
            SET service_name=%s, base_price=%s, unit=%s, description=%s
            WHERE service_id=%s
        """
        cur.execute(sql, (name, price, unit, desc, service_id))
        conn.commit()
        flash('Cập nhật dịch vụ thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi cập nhật: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('services_page'))

# Route xóa (Soft Delete/Khóa)
@app.route('/toggle_service/<int:id>', methods=['POST'])
@login_required
def toggle_service(id):
    conn = get_db_connection()
    cur = conn.cursor()
    # PostgreSQL hiểu boolean là TRUE/FALSE, MySQL là 1/0. 
    # Nhưng cú pháp NOT is_active vẫn hoạt động tốt trên cả hai.
    cur.execute("UPDATE Services SET is_active = NOT is_active WHERE service_id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('services_page'))

# --- QUẢN LÝ KHÁCH HÀNG ---

@app.route('/customers')
@login_required
def customers_page():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Customers ORDER BY customer_id DESC")
    customers = cur.fetchall()
    conn.close()
    return render_template(CUSTOMERS_HTML, customers_list=customers)

# --- 1. SỬA HÀM THÊM KHÁCH HÀNG (Thêm billing_address) ---
@app.route('/add_customer', methods=['POST'])
@login_required
def add_customer():
    name = request.form['customer_name']
    phone = request.form['phone']
    company = request.form.get('company_name', '')
    address = request.form.get('address', '')
    tax = request.form.get('tax_id', '') 
    
    # Lấy địa chỉ hóa đơn (nếu form không nhập thì để trống)
    billing_addr = request.form.get('billing_address', '') 
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Cập nhật câu SQL INSERT có thêm billing_address
        sql = """
            INSERT INTO Customers (customer_name, phone, company_name, address, tax_id, billing_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(sql, (name, phone, company, address, tax, billing_addr))
        conn.commit()
        flash('Thêm khách hàng thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('customers_page'))

# --- CÁC HÀM KHÁCH HÀNG BỔ SUNG (Dán dưới hàm add_customer) ---

# 2. HÀM KHÓA/MỞ (Sửa lỗi BuildError hiện tại)
@app.route('/toggle_customer/<int:id>', methods=['POST'])
@login_required
def toggle_customer(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Cú pháp đảo ngược True/False trong Postgres
        cur.execute("UPDATE Customers SET is_active = NOT is_active WHERE customer_id = %s", (id,))
        conn.commit()
        flash('Đã thay đổi trạng thái khách hàng!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('customers_page'))

# 3. HÀM HIỆN TRANG SỬA (Để tránh lỗi BuildError tiếp theo cho nút Sửa)
@app.route('/edit_customer/<int:customer_id>')
@login_required
def edit_customer_page(customer_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Customers WHERE customer_id = %s", (customer_id,))
    cust = cur.fetchone()
    conn.close()
    
    if cust:
        return render_template(EDIT_CUSTOMER_HTML, customer=cust)
    return "Không tìm thấy khách hàng", 404

# --- 4. SỬA HÀM CẬP NHẬT KHÁCH HÀNG (Thêm billing_address) ---
@app.route('/update_customer', methods=['POST'])
@login_required
def update_customer():
    c_id = request.form['customer_id']
    name = request.form['customer_name']
    phone = request.form['phone']
    company = request.form.get('company_name', '')
    address = request.form.get('address', '')
    tax = request.form.get('tax_id', '')
    
    # Lấy địa chỉ hóa đơn từ form sửa
    billing_addr = request.form.get('billing_address', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Cập nhật câu SQL UPDATE
        sql = """
            UPDATE Customers 
            SET customer_name=%s, phone=%s, company_name=%s, address=%s, tax_id=%s, billing_address=%s
            WHERE customer_id=%s
        """
        cur.execute(sql, (name, phone, company, address, tax, billing_addr, c_id))
        conn.commit()
        flash('Cập nhật thông tin khách hàng thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi cập nhật: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('customers_page'))

# --- 1. LỊCH SỬ ĐƠN HÀNG (Code thật) ---
@app.route('/orders_history')
@login_required
def orders_history_page():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Query lấy đơn hàng kèm tên khách
    cur.execute("""
        SELECT O.*, C.customer_name 
        FROM Orders O
        LEFT JOIN Customers C ON O.customer_id = C.customer_id
        ORDER BY O.order_date DESC
    """)
    orders = cur.fetchall()
    conn.close()
    
    # Render template cũ của bạn
    # Lưu ý: Nếu template cần biến total_revenue..., ta tạm truyền 0 để không lỗi
    return render_template(LS_DH_HTML, 
                           orders_list=orders,
                           total_revenue=0,
                           total_due=0,
                           total_cancelled=0)

# --- 2. CÁC ROUTE GIỮ CHỖ (Placeholder) ---
# Mục đích: Để menu không bị lỗi BuildError. 
# Sau này làm đến phần nào ta sẽ xóa đi viết lại phần đó.

# app.py (THAY THẾ ROUTE create_order_page CŨ)

@app.route('/create_order')
@login_required
def create_order_page():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Lấy Khách hàng
    cur.execute("SELECT * FROM Customers WHERE is_active = TRUE ORDER BY customer_name")
    customers = cur.fetchall()
    
    # 2. Lấy Dịch vụ
    cur.execute("SELECT * FROM Services WHERE is_active = TRUE ORDER BY service_name")
    services = cur.fetchall()
    
    # 3. Lấy Thiết bị (MỚI THÊM)
    # (Chỉ lấy máy đang hoạt động 'active' và chưa bị khóa is_active=TRUE)
    cur.execute("SELECT * FROM Equipment WHERE status = 'active' AND is_active = TRUE ORDER BY equipment_name")
    equipment = cur.fetchall()
    
    conn.close()
    
    return render_template(TAO_DH_HTML, 
                           customers_list=customers, 
                           services_list=services,
                           equipment_list=equipment) # <-- Gửi biến này sang HTML

# --- XỬ LÝ LƯU ĐƠN HÀNG (QUAN TRỌNG) ---
@app.route('/submit_order', methods=['POST'])
@login_required
def submit_order():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Lấy dữ liệu từ Form
        customer_id = request.form['customer_id']
        
        # Lấy danh sách các mảng (Array) từ form (Vì có nhiều dòng sản phẩm)
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]') # Giá đơn vị (đã chỉnh sửa hoặc mặc định)
        descriptions = request.form.getlist('description[]') # Nếu form của bạn có cột ghi chú/mô tả

        # 2. Tính toán tổng tiền trước
        grand_total = 0
        items_data = [] # Lưu tạm để insert sau

        # Duyệt qua từng dòng sản phẩm để tính toán
        for i in range(len(service_ids)):
            srv_id = service_ids[i]
            if not srv_id: continue # Bỏ qua dòng trống
            
            qty = float(quantities[i])
            price = float(prices[i])
            desc = descriptions[i] if i < len(descriptions) else ""
            
            line_total = qty * price
            grand_total += line_total
            
            # Lưu vào list tạm
            items_data.append((srv_id, desc, qty, price, line_total))

        # 3. Insert vào bảng Orders (Tạo vỏ đơn hàng)
        # Lưu ý: Postgres dùng RETURNING order_id để lấy ID vừa tạo
        sql_order = """
            INSERT INTO Orders (customer_id, order_date, total_amount, status, payment_status)
            VALUES (%s, NOW(), %s, 'processing', 'unpaid')
            RETURNING order_id
        """
        cur.execute(sql_order, (customer_id, grand_total))
        new_order_id = cur.fetchone()['order_id']

        # 4. Insert chi tiết vào bảng Order_Items
        sql_item = """
            INSERT INTO Order_Items (order_id, service_id, description, quantity, unit_price, line_total)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        for item in items_data:
            # item = (srv_id, desc, qty, price, line_total)
            cur.execute(sql_item, (new_order_id, item[0], item[1], item[2], item[3], item[4]))

        conn.commit()
        flash(f'Đã tạo đơn hàng #{new_order_id} thành công!', 'success')
        
        # Chuyển hướng đến trang chi tiết đơn hàng (Chúng ta sẽ tạo route này ở bước 3)
        return redirect(url_for('order_detail_page', order_id=new_order_id))

    except Exception as e:
        conn.rollback()
        flash(f'Lỗi khi tạo đơn: {e}', 'danger')
        return redirect(url_for('create_order_page'))
    finally:
        conn.close()

# --- TRANG CHI TIẾT ĐƠN HÀNG ---

@app.route('/order_detail/<int:order_id>')
@login_required
def order_detail_page(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Lấy thông tin chung đơn hàng + Tên khách
    sql_order = """
        SELECT O.*, C.customer_name, C.phone, C.address, C.billing_address
        FROM Orders O
        JOIN Customers C ON O.customer_id = C.customer_id
        WHERE O.order_id = %s
    """
    cur.execute(sql_order, (order_id,))
    order_info = cur.fetchone()
    
    # 2. Lấy danh sách sản phẩm trong đơn
    sql_items = """
        SELECT OI.*, S.service_name, S.unit
        FROM Order_Items OI
        JOIN Services S ON OI.service_id = S.service_id
        WHERE OI.order_id = %s
    """
    cur.execute(sql_items, (order_id,))
    order_items = cur.fetchall()
    
    conn.close()
    
    if not order_info:
        return "Không tìm thấy đơn hàng", 404
        
    return render_template(CT_DH_HTML, 
                           order_info=order_info, 
                           order_items=order_items,
                           amount_due=(order_info['total_amount'] - order_info['amount_paid']))

@app.route('/materials')
@login_required
def materials_page():
    return "<h1>Tính năng VẬT TƯ đang được chuyển đổi...</h1><a href='/dashboard'>Quay lại</a>"

@app.route('/quotes_history')
@login_required
def quotes_history_page():
    return "<h1>Tính năng LỊCH SỬ BÁO GIÁ đang được chuyển đổi...</h1><a href='/dashboard'>Quay lại</a>"

@app.route('/create_quote')
@login_required
def create_quote_page():
    return "<h1>Tính năng TẠO BÁO GIÁ đang được chuyển đổi...</h1><a href='/dashboard'>Quay lại</a>"

# --- QUẢN LÝ THIẾT BỊ (MÁY MÓC) ---

# 1. Trang danh sách thiết bị
@app.route('/equipment')
@login_required
def equipment_page():
    conn = get_db_connection()
    cur = conn.cursor()
    # Lấy kèm tên nhà cung cấp (nếu có bảng Suppliers, nếu chưa thì bỏ đoạn JOIN đi)
    # Ở đây tôi viết query đơn giản trước
    cur.execute("SELECT * FROM Equipment ORDER BY equipment_id DESC")
    equip_list = cur.fetchall()
    conn.close()
    return render_template(TB_HTML, equipment_list=equip_list)

# 2. Thêm thiết bị mới
@app.route('/add_equipment', methods=['POST'])
@login_required
def add_equipment():
    name = request.form['equipment_name']
    model = request.form.get('model_number', '')
    serial = request.form.get('serial_number', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = """
            INSERT INTO Equipment (equipment_name, model_number, serial_number, status, is_active)
            VALUES (%s, %s, %s, 'active', TRUE)
        """
        cur.execute(sql, (name, model, serial))
        conn.commit()
        flash('Thêm thiết bị thành công!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('equipment_page'))

# 3. AJAX Thêm thiết bị nhanh (Dùng cho nút + ở trang Tạo đơn)
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

# 4. Toggle Khóa/Mở thiết bị
@app.route('/toggle_equipment/<int:id>', methods=['POST'])
@login_required
def toggle_equipment(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE Equipment SET is_active = NOT is_active WHERE equipment_id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('equipment_page'))

# --- CHI TIẾT & CẬP NHẬT THIẾT BỊ ---

# 1. Trang chi tiết thiết bị (Sửa lỗi BuildError)
@app.route('/equipment_detail/<int:equipment_id>')
@login_required
def equipment_detail_page(equipment_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Lấy thông tin thiết bị cụ thể
    cur.execute("SELECT * FROM Equipment WHERE equipment_id = %s", (equipment_id,))
    equip = cur.fetchone()
    
    # Lấy danh sách Nhà cung cấp (Để nạp vào dropdown chọn NCC khi sửa)
    cur.execute("SELECT * FROM Suppliers WHERE is_active = TRUE")
    suppliers = cur.fetchall()
    
    conn.close()
    
    if equip:
        return render_template(CT_TB_HTML, equipment=equip, suppliers_list=suppliers)
    return "Không tìm thấy thiết bị", 404

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

@app.route('/manage_users')
@login_required
def manage_users_page():
    return "<h1>Tính năng QUẢN LÝ USER đang được chuyển đổi...</h1><a href='/dashboard'>Quay lại</a>"

@app.route('/system_logs')
@login_required
def system_logs_page():
    return "<h1>Tính năng LOG HỆ THỐNG đang được chuyển đổi...</h1><a href='/dashboard'>Quay lại</a>"

# Các route con khác nếu menu có gọi (tránh lỗi tối đa)
@app.route('/imports')
@login_required
def imports_page(): return "Đang bảo trì..."

@app.route('/service_materials')
@login_required
def service_materials_page(): return "Đang bảo trì..."

@app.route('/adjustments')
@login_required
def create_adjustment_page(): return "Đang bảo trì..."

@app.route('/report/customer_debt')
@login_required
def customer_debt_report(): return "Đang bảo trì..."

@app.route('/report/supplier_debt')
@login_required
def supplier_debt_report(): return "Đang bảo trì..."

# --- XỬ LÝ MÃ GIẢM GIÁ (Thêm vào để sửa lỗi BuildError) ---

# 1. API Kiểm tra mã (AJAX gọi vào đây)
@app.route('/check_coupon', methods=['POST'])
def check_coupon():
    code = request.form.get('code', '').strip().upper()
    
    if not code:
        return jsonify({'valid': False, 'message': 'Vui lòng nhập mã!'})

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Tìm mã trong DB
    cur.execute("SELECT * FROM Coupons WHERE code = %s AND is_active = TRUE", (code,))
    coupon = cur.fetchone()
    conn.close()

    if coupon:
        # Kiểm tra ngày hết hạn
        today = datetime.date.today()
        start = coupon['start_date']
        end = coupon['end_date']
        
        if (start and today < start) or (end and today > end):
            return jsonify({'valid': False, 'message': 'Mã này chưa bắt đầu hoặc đã hết hạn!'})
            
        # Kiểm tra số lượt dùng
        if coupon['usage_limit'] > 0 and coupon['used_count'] >= coupon['usage_limit']:
            return jsonify({'valid': False, 'message': 'Mã này đã hết lượt sử dụng!'})

        # Nếu OK hết -> Trả về thành công
        return jsonify({
            'valid': True,
            'message': f"Áp dụng thành công: Giảm {coupon['discount_value']}%",
            'discount_type': coupon['discount_type'],
            'discount_value': float(coupon['discount_value'])
        })
    else:
        return jsonify({'valid': False, 'message': 'Mã giảm giá không tồn tại!'})

# 2. Route Quản lý mã giảm giá (Placeholder - để menu không bị lỗi nếu lỡ bấm vào)
@app.route('/coupons')
@login_required
def coupons_page():
    return "<h1>Trang Quản lý Mã giảm giá (Đang xây dựng...)</h1><a href='/dashboard'>Quay lại</a>"

@app.route('/create_import')
@login_required
def create_import_page(): return "Đang bảo trì..."

# --- XỬ LÝ AJAX THÊM KHÁCH HÀNG NHANH (Sửa lỗi BuildError) ---

@app.route('/ajax_add_customer', methods=['POST'])
@login_required
def ajax_add_customer():
    try:
        # 1. Lấy dữ liệu từ modal gửi lên
        name = request.form.get('customer_name')
        phone = request.form.get('phone')
        
        # Các trường tùy chọn (nếu modal có nhập)
        address = request.form.get('address', '')
        company = request.form.get('company_name', '')
        tax = request.form.get('tax_id', '')
        billing = request.form.get('billing_address', '') # Địa chỉ hóa đơn

        if not name or not phone:
            return jsonify({'success': False, 'error': 'Tên và SĐT là bắt buộc!'})

        conn = get_db_connection()
        cur = conn.cursor()
        
        # 2. Thêm vào Database (Dùng RETURNING để lấy ID ngay lập tức)
        sql = """
            INSERT INTO Customers (customer_name, phone, company_name, address, tax_id, billing_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING customer_id
        """
        cur.execute(sql, (name, phone, company, address, tax, billing))
        
        # Lấy ID vừa tạo
        new_customer_id = cur.fetchone()['customer_id']
        conn.commit()
        conn.close()

        # 3. Trả về JSON để JavaScript tự điền vào ô chọn
        return jsonify({
            'success': True,
            'new_id': new_customer_id,
            'new_name': name,
            # Trả về cả các thông tin phụ để JS điền vào khung hiển thị luôn
            'phone': phone,
            'address': address,
            'billing': billing,
            'tax': tax,
            'company': company
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# --- XỬ LÝ AJAX THÊM DỊCH VỤ NHANH (Sửa lỗi BuildError) ---

@app.route('/ajax_add_service', methods=['POST'])
@login_required
def ajax_add_service():
    try:
        # 1. Lấy dữ liệu từ modal gửi lên
        name = request.form.get('service_name')
        price = request.form.get('base_price')
        unit = request.form.get('unit')
        desc = request.form.get('description', '')

        # Kiểm tra dữ liệu bắt buộc
        if not name or not price:
            return jsonify({'success': False, 'error': 'Tên dịch vụ và Giá là bắt buộc!'})

        conn = get_db_connection()
        cur = conn.cursor()
        
        # 2. Thêm vào PostgreSQL (Dùng RETURNING service_id)
        sql = """
            INSERT INTO Services (service_name, base_price, unit, description)
            VALUES (%s, %s, %s, %s)
            RETURNING service_id
        """
        cur.execute(sql, (name, price, unit, desc))
        
        # Lấy ID vừa tạo
        new_id = cur.fetchone()['service_id']
        conn.commit()
        conn.close()

        # 3. Trả về JSON để JavaScript thêm vào bảng
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name,
            'new_price': float(price), # Chuyển sang số thực để JS dễ tính toán
            'new_unit': unit
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# --- QUẢN LÝ NHÀ CUNG CẤP (SUPPLIERS) ---

# 1. XỬ LÝ AJAX THÊM NHANH (Sửa lỗi BuildError hiện tại)
@app.route('/ajax_add_supplier', methods=['POST'])
@login_required
def ajax_add_supplier():
    try:
        # Lấy dữ liệu từ modal
        name = request.form.get('supplier_name')
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        address = request.form.get('address', '')

        if not name:
            return jsonify({'success': False, 'error': 'Tên nhà cung cấp là bắt buộc!'})

        conn = get_db_connection()
        cur = conn.cursor()
        
        # Thêm vào DB và lấy ID ngay lập tức
        sql = """
            INSERT INTO Suppliers (supplier_name, phone, email, address, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            RETURNING supplier_id
        """
        cur.execute(sql, (name, phone, email, address))
        new_id = cur.fetchone()['supplier_id']
        
        conn.commit()
        conn.close()

        # Trả về JSON
        return jsonify({
            'success': True,
            'new_id': new_id,
            'new_name': name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)