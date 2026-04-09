import os
from dotenv import load_dotenv
load_dotenv()

from db import get_db_connection

def apply_schema():
    conn = get_db_connection()
    if not conn:
        print("Không kết nối được DB")
        return
    cur = conn.cursor()
    try:
        # 1. Create Combos table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Combos (
                combo_id SERIAL PRIMARY KEY,
                combo_name VARCHAR(255) NOT NULL,
                description TEXT,
                combo_price NUMERIC(15,2) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            );
        """)
        
        # 2. Create Combo_Items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Combo_Items (
                combo_item_id SERIAL PRIMARY KEY,
                combo_id INTEGER REFERENCES Combos(combo_id) ON DELETE CASCADE,
                service_id INTEGER REFERENCES Services(service_id) ON DELETE RESTRICT,
                quantity INTEGER NOT NULL DEFAULT 1
            );
        """)
        
        # 3. Add combo_id to Order_Items
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='order_items' AND column_name='combo_id'
                ) THEN
                    ALTER TABLE order_items ADD COLUMN combo_id INT REFERENCES Combos(combo_id) ON DELETE SET NULL;
                END IF;
            END $$;
        """)

        # 4. Add combo_id to Quote_Items
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='quote_items' AND column_name='combo_id'
                ) THEN
                    ALTER TABLE quote_items ADD COLUMN combo_id INT REFERENCES Combos(combo_id) ON DELETE SET NULL;
                END IF;
            END $$;
        """)

        conn.commit()
        print("Schema updated successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Lỗi: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    apply_schema()
