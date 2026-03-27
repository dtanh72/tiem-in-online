from flask_login import UserMixin
from db import get_db_connection

class User(UserMixin):
    def __init__(self, id, username, full_name, role_id):
        self.id = id
        self.username = username
        self.full_name = full_name
        self.role_id = role_id
        
    def can(self, perm):
        return True # Tạm thời cho full quyền để test

def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Users WHERE user_id = %s", (user_id,))
    u = cur.fetchone()
    conn.close()
    if u:
        return User(u['user_id'], u['username'], u['full_name'], u['role_id'])
    return None
