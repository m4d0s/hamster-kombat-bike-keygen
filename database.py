import asyncpg
import asyncio
import logging
import json
from datetime import datetime

def log_timestamp():
    return datetime.now().strftime('%Y-%m-%d')

# Configure logging
logging.basicConfig(level=logging.INFO, filename='logs/'+log_timestamp()+'.log')

# Load PostgreSQL configuration
with open('config.json') as f:
    config = json.load(f)

db_config = {
    'database': config['DB']['NAME'],
    'user': config['DB']['USER'],
    'password': config['DB']['PASSWORD'],
    'host': config['DB']['HOST'],
    'port': config['DB']['PORT']
}

SCHEMA = config['DB']['SCHEMA']
SSL_MODE = config['DB']['SSL']  # Assumes SSL configuration is handled correctly
POOL = None

def now() -> int:
    return int(datetime.now().timestamp())

async def get_pool():
    global POOL
    POOL = await asyncpg.create_pool(
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password'],
        host=db_config['host'],
        port=db_config['port'],
        ssl=SSL_MODE
    )
    return POOL


async def insert_key_generation(user_id, key, pool=POOL):
    if user_id is None or key is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            num = await conn.fetchrow(f'SELECT id FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id)
            if num is None:
                return None
            num = num['id']
            
            await conn.execute(f'INSERT INTO "{SCHEMA}".keys (user_id, key, time) '+ 
                               'VALUES ($1, $2, $3) ', num, key, now())

async def get_last_user_key(user_id, pool=POOL):
    if user_id is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            num = await conn.fetchrow(f'SELECT id FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id)
            if num is None:
                return None
            num = num['id']
            
            row = await conn.fetchrow(f'SELECT key, time FROM "{SCHEMA}".keys WHERE user_id = $1 ORDER BY time DESC LIMIT 1', num)
    
    return row

async def get_all_user_keys_24h(user_id, day=0, pool=POOL):
    if user_id is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            num = await conn.fetchrow(f'SELECT id FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id)
            if num is None:
                return None
            num = num['id']
            
            rows = await conn.fetch(f'SELECT key, time FROM "{SCHEMA}".keys WHERE user_id = $1 AND time > $2 ORDER BY time DESC', num, now() - 86400 * (abs(day) + 1))
    
    return rows

async def delete_user(user_id, pool=POOL):
    if user_id is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'DELETE FROM "{SCHEMA}".users WHERE tg_id = $1', user_id)

async def get_all_user_ids(pool=POOL):
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT tg_id FROM "{SCHEMA}".users')
    
    return [row['tg_id'] for row in rows]

async def get_all_dev(pool=POOL):
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT tg_id FROM "{SCHEMA}".users WHERE right > 0')
    
    return [row['tg_id'] for row in rows]

async def insert_user(user_id, username, ref=0, pool=POOL):
    if user_id is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'INSERT INTO "{SCHEMA}".users (tg_id, tg_username, ref_id) '+
                               'VALUES ($1, $2, $3) '+
                               'ON CONFLICT (tg_id) DO UPDATE '+
                               'SET tg_username = EXCLUDED.tg_username', user_id, username, ref)

def relative_time(time):
    return now() - time

def format_remaining_time(target_time: int) -> str:
    waste = target_time - now()
    prefix = ""
    
    if waste < 0:
        prefix = 'ago'

    hours, remainder = divmod(waste, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours} hours {minutes} minutes {prefix}"
    elif minutes > 0:
        return f"{minutes} minutes {prefix}"
    else:
        return f"{seconds} seconds {prefix}"
