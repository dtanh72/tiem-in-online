import os
from flask import Flask, redirect, url_for, flash, render_template, request
import psycopg2
from dotenv import load_dotenv

from extensions import login_manager, csrf, limiter
from models import load_user
from utils import currency_filter

# Import Blueprints
from routes.auth import auth_bp
from routes.system import system_bp
from routes.dashboard import dashboard_bp
from routes.services import services_bp
from routes.customers import customers_bp
from routes.orders import orders_bp
from routes.quotes import quotes_bp
from routes.inventory import inventory_bp
from routes.equipment import equipment_bp
from routes.suppliers import suppliers_bp
from routes.coupons import coupons_bp
from routes.outsource import outsource_bp
from routes.combos import combos_bp
from routes.tools import tools_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mac_dinh_neu_khong_co_key')

# Cấu hình bảo mật Session & CSRF
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    WTF_CSRF_ENABLED=True
)

# Jinja Filter
app.template_filter('currency')(currency_filter)

# Định cấu hình các Extensions
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.user_loader(load_user)

csrf.init_app(app)
limiter.init_app(app)

@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# Đăng ký các Blueprint
app.register_blueprint(auth_bp)
app.register_blueprint(system_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(services_bp)
app.register_blueprint(customers_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(quotes_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(equipment_bp)
app.register_blueprint(suppliers_bp)
app.register_blueprint(coupons_bp)
app.register_blueprint(outsource_bp)
app.register_blueprint(combos_bp)
app.register_blueprint(tools_bp)

# Thêm route setup admin
from db import get_db_connection
from werkzeug.security import generate_password_hash

ADMIN_DEF = os.environ.get('ADMIN_DEF')
ADMIN_PAS_DEF = os.environ.get('ADMIN_PAS_DEF')

@app.route('/setup_admin')
def setup_admin():
    conn = get_db_connection()
    if conn is None: return "Database connection error"
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO Roles (role_id, role_name, permissions) VALUES (1, 'Admin', 'all') ON CONFLICT DO NOTHING")
        hashed_pw = generate_password_hash(ADMIN_PAS_DEF)
        cur.execute("INSERT INTO Users (username, password_hash, full_name, role_id) VALUES (%s, %s, 'Super Admin', 1) ON CONFLICT DO NOTHING", (ADMIN_DEF, hashed_pw))
        conn.commit()
        return "Tạo Admin thành công!"
    except Exception as e:
        conn.rollback()
        return f"Lỗi: {e}"
    finally:
        cur.close()
        conn.close()

# Route mặc định - Landing Page
@app.route('/')
def index():
    # Ghi nhận lượt truy cập
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            ip_addr = request.remote_addr
            referrer = request.referrer or 'Direct'
            user_agent = request.user_agent.string
            
            cur.execute("""
                INSERT INTO page_visits (ip_address, referrer, user_agent)
                VALUES (%s, %s, %s)
            """, (ip_addr, referrer, user_agent))
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print(f"Lỗi ghi nhận truy cập: {e}")
        
    return render_template('index.html')

# Bắt lỗi mất kết nối DB toàn cục
@app.errorhandler(psycopg2.OperationalError)
def handle_db_connection_error(e):
    flash('Mất kết nối với cơ sở dữ liệu (Database Connection Closed). Vui lòng đăng nhập lại.', 'danger')
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True)
