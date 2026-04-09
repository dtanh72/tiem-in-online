import os
from dotenv import load_dotenv
load_dotenv()

import psycopg2.extras
import json
from db import get_db_connection

def dump_schema():
    conn = get_db_connection()
    if not conn:
        print("No db connection")
        return
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name, ordinal_position")
    
    res = {}
    for r in cur.fetchall():
        res.setdefault(r['table_name'], []).append(f"{r['column_name']} ({r['data_type']})")
    
    with open('schema_output.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2)
    print("Schema dumped to schema_output.json")
    conn.close()

if __name__ == '__main__':
    dump_schema()
