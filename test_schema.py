from db import get_db_connection
from psycopg2.extras import RealDictCursor
conn = get_db_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'outsource_categories'")
print('Outsource_Categories:', [r['column_name'] for r in cur.fetchall()])
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'outsource_prices'")
print('Outsource_Prices:', [r['column_name'] for r in cur.fetchall()])
conn.close()
