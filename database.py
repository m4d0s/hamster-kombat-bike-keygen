import asyncpg
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

async def insert_key_generation(user_id, key, key_type, used=True, pool=None):
    if user_id is None or key is None:
        return
    
    pool = pool or POOL
    async with pool.acquire() as conn:
        async with conn.transaction():
            num = await conn.fetchrow(
                f'SELECT id FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1',
                user_id
            )
            if num is None:
                return None
            num = num['id']
            
            await conn.execute(
                f'INSERT INTO "{SCHEMA}".keys (user_id, key, time, type, used) ' +
                'VALUES ($1, $2, $3, $4, $5) ' +
                'ON CONFLICT (key) DO UPDATE SET used = EXCLUDED.used, user_id = EXCLUDED.user_id',
                num, key, now(), key_type, used
            )

async def get_last_user_key(user_id, pool=None):
    if user_id is None:
        return
    
    pool = pool or POOL
    async with pool.acquire() as conn:
        async with conn.transaction():
            num = await conn.fetchrow(
                f'SELECT id FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1',
                user_id
            )
            if num is None:
                return None
            num = num['id']
            
            row = await conn.fetchrow(
                f'SELECT key, time, type FROM "{SCHEMA}".keys WHERE user_id = $1 ORDER BY time DESC LIMIT 1',
                num
            )
    
    return {'key': row['key'], 'time': row['time'], 'type': row['type']} if row else None

async def get_unused_key_of_type(key_type, pool=None):
    if key_type is None:
        return
    
    pool = pool or POOL
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                f'SELECT key FROM "{SCHEMA}".keys WHERE type = $1 AND used = false ORDER BY time ASC LIMIT 1',
                key_type
            )
    
    return row['key'] if row else None

async def get_all_user_keys_24h(user_id, day=0, pool=POOL):
    if user_id is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            num = await conn.fetchrow(f'SELECT id FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id)
            if num is None:
                return None
            num = num['id']
            
            rows = await conn.fetch(f'SELECT key, time, type FROM "{SCHEMA}".keys WHERE user_id = $1 AND time > $2 ORDER BY time DESC', num, now() - 86400 * (abs(day) + 1))
    
    return [[row['key'], row['time'], row['type']] for row in rows] if rows else None

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
    
    return [row['tg_id'] for row in rows] if rows else None

async def get_all_dev(pool=POOL):
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT tg_id FROM "{SCHEMA}".users WHERE right > 0')
    
    return [row['tg_id'] for row in rows] if rows else None

async def get_cashed_data(user_id, pool=POOL):
    if user_id is None:
        return

    query = f'SELECT * FROM "{SCHEMA}".cashe WHERE user_id = $1'

    async with pool.acquire() as conn:
        async with conn.transaction():  
            num = await conn.fetchrow(f'SELECT id FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id)
            if num is None:
                return None
            num = num['id']
        # Directly fetch the results without explicit transaction (SELECT query doesn't need it)
        rows = await conn.fetch(query, num)

    # Extract the 'cashed_data' value
    cashed_data = {'user_id': num, 
                   'welcome': rows[0]['welcome'], 
                   'loading': rows[0]['loading'], 
                   'report': rows[0]['report'], 
                   'process': rows[0]['process'], 
                   'error': rows[0]['error']} if rows else None
    return cashed_data

async def update_cashe_process(pool=POOL):
    query = f'UPDATE "{SCHEMA}".cashe SET process = true'
    async with pool.acquire() as conn:
        await conn.execute(query)
        

async def write_cashed_data(user_id, cashed_data, pool=POOL):
    if user_id is None:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Получаем id пользователя из таблицы users
            user_record = await conn.fetchrow(
                f'SELECT id FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id
            )
            
            # Если пользователь не найден, возвращаем None
            if user_record is None:
                return None
            
            user_id_in_db = user_record['id']

            # Формируем запрос на обновление
            update_query = f'''
                UPDATE "{SCHEMA}".cashe
                SET {', '.join([f'{key} = ${i+2}' for i, key in enumerate(cashed_data.keys())])}
                WHERE user_id = $1
            '''
            
            # Выполняем запрос на обновление
            update_result = await conn.execute(update_query, user_id_in_db, *cashed_data.values())
            
            # Проверяем, было ли обновлено что-то
            if update_result == "UPDATE 0":
                # Если нет, вставляем новую запись
                insert_query = f'''
                    INSERT INTO "{SCHEMA}".cashe (user_id, {', '.join(cashed_data.keys())})
                    VALUES ($1, {', '.join([f'${i+2}' for i in range(len(cashed_data))])})
                '''
                await conn.execute(insert_query, user_id_in_db, *cashed_data.values())


async def get_all_refs(user_id, pool):
    if user_id is None:
        return

    query = f'SELECT ref_id FROM "{SCHEMA}".users WHERE ref_id = $1'
    
    async with pool.acquire() as conn:
        # Directly fetch the results without explicit transaction (SELECT query doesn't need it)
        rows = await conn.fetch(query, user_id)

    # Extract the 'ref_id' values
    ref_ids = [row['ref_id'] for row in rows] if rows else []
    return ref_ids
    
async def insert_user(user_id, username, ref=0, lang='en', pool=POOL):
    if user_id is None or username is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'INSERT INTO "{SCHEMA}".users (tg_id, tg_username, ref_id, lang) '+
                               'VALUES ($1, $2, $3, $4) '+
                               'ON CONFLICT (tg_id) DO UPDATE '+
                               'SET tg_username = EXCLUDED.tg_username', 
                               user_id, username, ref, lang)
            await conn.execute(f'INSERT INTO "{SCHEMA}".cashe (user_id) VALUES ($1) ON CONFLICT DO NOTHING', user_id)

async def get_user(user_id, pool=POOL):
    if user_id is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(f'SELECT * FROM "{SCHEMA}".users WHERE tg_id = $1', user_id)
    
    return {'username': row['tg_username'], 
            'tg_id': row['tg_id'], 
            'ref_id': row['ref_id'], 
            'lang': row['lang'], 
            'right': row['right'],
            'ref': row['ref_id']} if row else None

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
