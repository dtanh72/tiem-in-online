from dotenv import load_dotenv
load_dotenv()
from db import get_db_connection

def create_quick_actions_table():
    conn = get_db_connection()
    if conn is None:
        print("Loi ket noi CSDL")
        return
        
    try:
        cur = conn.cursor()
        # Tạo bảng quick_actions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quick_actions (
                action_id SERIAL PRIMARY KEY,
                slot_index INTEGER UNIQUE NOT NULL,
                service_id INTEGER REFERENCES services(service_id) ON DELETE SET NULL,
                button_label VARCHAR(50),
                bg_color VARCHAR(20) DEFAULT '#0d6efd'
            )
        """)
        
        # Khởi tạo 10 nút mặc định nếu chưa có
        cur.execute("SELECT COUNT(*) FROM quick_actions")
        count = cur.fetchone()[0]
        if count == 0:
            for i in range(1, 11):
                cur.execute("""
                    INSERT INTO quick_actions (slot_index, button_label, bg_color) 
                    VALUES (%s, %s, %s)
                """, (i, f"Trống {i}", "#6c757d"))
                
        conn.commit()
        print("Tao bang quick_actions thanh cong!")
    except Exception as e:
        conn.rollback()
        print(f"Loi: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

if __name__ == '__main__':
    create_quick_actions_table()
