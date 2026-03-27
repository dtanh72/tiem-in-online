import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient

# --- DATABASE CONFIG ---
DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_DEF = os.environ.get('ADMIN_DEF')
ADMIN_PAS_DEF = os.environ.get('ADMIN_PAS_DEF')

# Khởi tạo Global Pool
_db_pool = None
try:
    if DATABASE_URL:
        _db_pool = psycopg2.pool.ThreadedConnectionPool(
            1, 20, dsn=DATABASE_URL, cursor_factory=RealDictCursor
        )
except Exception as e:
    print(f"Lỗi thiết lập DB Pool: {e}")

class PooledConnectionWrapper:
    """
    Proxy class intercept lời gọi close(), chuyển thành putconn() để thả về Pool.
    Tương thích ngược 100% với code cũ đang gọi conn.close().
    """
    def __init__(self, conn, db_pool):
        self._conn = conn
        self._pool = db_pool
        self._closed = False

    def close(self):
        if not self._closed:
            self._pool.putconn(self._conn)
            self._closed = True

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_db_connection():
    if not _db_pool:
        print("Chưa cấu hình DATABASE_URL hoặc Pool chưa khởi tạo thành công!")
        return None
    try:
        conn = _db_pool.getconn()
        return PooledConnectionWrapper(conn, _db_pool)
    except Exception as e:
        print(f"Lỗi lấy kết nối từ pool: {e}")
        return None

def get_mongo_collection():
    mongo_uri = os.environ.get('MONGO_URL')
    if not mongo_uri:
        raise Exception("Chưa cấu hình MONGO_URL")
    client = MongoClient(mongo_uri)
    db = client['app_database']
    return db['system_logs']
