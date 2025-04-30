import sqlite3
from datetime import datetime

DB_PATH = '/home/pi/projects/project/orders.db'

def setup_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            barcode TEXT,
            delegate_name TEXT,
            delegate_phone TEXT,
            delegate_email TEXT,
            company TEXT,
            status TEXT,
            created_at TEXT,
            delivery_code TEXT
        )
    ''')
    c.execute("SELECT * FROM orders WHERE barcode = '12'")
    if not c.fetchone():
        c.execute('''
            INSERT INTO orders (name, barcode, delegate_name, delegate_phone, delegate_email, company, status, created_at, delivery_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'سهام خالد', '12', 'مندوب أحمد', '+966501554229', 'ahmed@example.com',
            'سمسما', 'معلق', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '1234'
        ))
        conn.commit()
    conn.close()

setup_database()
