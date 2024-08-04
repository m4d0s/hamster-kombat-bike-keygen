import sqlite3
import logging
import json
from datetime import datetime

def log_timestamp():
    return datetime.now().strftime('%Y-%m-%d')

# Configure logging
logging.basicConfig(level=logging.INFO, filename='logs/'+log_timestamp()+'.log')

db_path = json.loads(open('config.json').read())['DB_PATH']

def now() -> int:
    return int(datetime.now().timestamp())

def insert_key_generation(user_id, key, db_path=db_path):
    if user_id is None or key is None:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("INSERT OR REPLACE INTO keys (user_id, key, time) VALUES (?, ?, ?)", (user_id, key, now()))
    conn.commit()
    
    conn.close()
    
def get_last_user_key(user_id, db_path=db_path):
    if user_id is None:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT (key, time) FROM keys WHERE user_id = ? ORDER BY time DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    return row

def insert_user(user_id, db_path=db_path):
    if user_id is None:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("INSERT OR REPLACE INTO users (tg_id) VALUES (?)", (user_id,))
    conn.commit()
    
    conn.close()

def relative_time(time):
    return now() - time