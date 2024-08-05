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
    
    cursor.execute("INSERT OR REPLACE INTO keys (tg_id, key, time) VALUES (?, ?, ?)", (user_id, key, now()))
    conn.commit()
    
    conn.close()
    
def get_last_user_key(user_id, db_path=db_path):
    if user_id is None:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT key, time FROM keys WHERE tg_id = ? ORDER BY time DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    return row

def get_all_user_keys_24h(user_id, day=0, db_path=db_path):
    if user_id is None:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT key, time FROM keys WHERE tg_id = ? AND time > ? ORDER BY time DESC", (user_id, now() - 86400 * (abs(day)+1)))
    rows = cursor.fetchall()
    conn.close()
    
    return rows

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

def format_remaining_time(target_time: int) -> str:
    waste = target_time - now()
    prefix = ""
    
    if waste < 0:
        prefix = 'ago'

    hours, remainder = divmod(waste, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Определение формата вывода
    if hours > 0:
        return f"{hours} hours {minutes} minutes {prefix}"
    elif minutes > 0:
        return f"{minutes} minutes {prefix}"
    else:
        return f"{seconds} seconds {prefix}"