import datetime
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from db import get_mongo_collection

def currency_filter(value):
    try:
        if value is None: return "0"
        return "{:,.0f}".format(value)
    except:
        return value

def requires_permission(*allowed_permissions):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))

            user_role = current_user.role_id 
            if user_role == 1:
                return f(*args, **kwargs)

            permission_map = {
                'inventory': [2],       
                'sale': [3],            
                'accounting': [4],      
                'asset': [2, 4],        
                'HR': [5],              
                'all': [1]              
            }

            has_permission = False
            for perm in allowed_permissions:
                if perm in permission_map and user_role in permission_map[perm]:
                    has_permission = True
                    break
            
            if not has_permission:
                flash('Bạn không có quyền truy cập trang này!', 'danger')
                return redirect(url_for('dashboard.dashboard_page'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_system_action(user_id, username, full_name, action_type, target_module, description, ip_address):
    try:
        logs_col = get_mongo_collection()
        log_document = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "action_type": action_type,
            "target_module": target_module,
            "description": description,
            "ip_address": ip_address,
            "created_at": datetime.datetime.now()
        }
        logs_col.insert_one(log_document)
    except Exception as e:
        print(f"Lỗi không ghi được Log vào Mongo: {e}")

def number_to_vietnamese_text(amount):
    """Chuyển đổi số tiền thành chữ tiếng Việt."""
    if amount == 0:
        return "Không đồng"
        
    amount = int(amount)
    
    digits = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
    
    def read_block_3(num, full_hundred=True):
        res = ""
        h = num // 100
        t = (num % 100) // 10
        u = num % 10
        if full_hundred:
            res += digits[h] + " trăm "
            if t == 0 and u != 0: res += "lẻ "
        if t == 1: res += "mười "
        elif t > 1: res += digits[t] + " mươi "
        if u == 1 and t > 1: res += "mốt "
        elif u == 5 and t > 0: res += "lăm "
        elif u > 0: res += digits[u] + " "
        return res.strip()

    s = str(amount)
    blocks = []
    while len(s) > 0:
        blocks.append(int(s[-3:]))
        s = s[:-3]
        
    words = []
    for i, b in enumerate(blocks):
        if b == 0: continue
        full = i < len(blocks) - 1 or b >= 100
        part = read_block_3(b, full)
        words.insert(0, part + " " + units[i])
        
    return " ".join(words).strip().capitalize() + "."
