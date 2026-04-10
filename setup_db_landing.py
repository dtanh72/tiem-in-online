import os
import shutil
from db import get_db_connection

def setup_page_visits():
    print("Setting up page_visits table...")
    conn = get_db_connection()
    if conn is None:
        print("Database connection error")
        return
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS page_visits (
                visit_id SERIAL PRIMARY KEY,
                ip_address VARCHAR(45),
                referrer TEXT,
                user_agent TEXT,
                visit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("Bảng page_visits đã được tạo thành công.")
    except Exception as e:
        conn.rollback()
        print(f"Lỗi tạo bảng: {e}")
    finally:
        cur.close()
        conn.close()

def setup_static_image():
    print("Copying image...")
    src = r"C:\Users\May06\.gemini\antigravity\brain\0bc65464-be80-4465-be6c-9a9e5047ca6d\print_shop_hero_1775802824939.png"
    dest_dir = r"c:\Users\May06\my_print_shop\static\images"
    dest = os.path.join(dest_dir, "print_shop_hero.png")
    
    os.makedirs(dest_dir, exist_ok=True)
    if os.path.exists(src):
        shutil.copy2(src, dest)
        print("Image copied successfully.")
    else:
        print(f"Source image not found: {src}")

if __name__ == '__main__':
    setup_page_visits()
    setup_static_image()
