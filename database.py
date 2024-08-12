import asyncpg
import logging
import json
from datetime import datetime, timedelta, time, timezone

def log_timestamp():
    return datetime.now().strftime('%Y-%m-%d')

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

async def get_pool() -> asyncpg.Pool:
    global POOL
    if POOL is None:
        POOL = await asyncpg.create_pool(
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password'],
            host=db_config['host'],
            port=db_config['port'],
            ssl=SSL_MODE
        )
    return POOL

async def get_promotions(pool=POOL):
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT * FROM "{SCHEMA}".promo')
    
    return {promo['id']:{
            'name': promo['name'],
            'desc': promo['desc'],
            'link': promo['link'],
            'channel': promo['check_id']
            } for promo in rows}

async def get_user_id(tg_id:int, pool=POOL):
    if tg_id is None:
        return
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            num = await conn.fetchrow(
                f'SELECT * FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1',
                tg_id
            )
            if num is None:
                return None
            return num['id']

async def insert_key_generation(user_id:int, key:str, key_type:str, used=True, pool=POOL) -> None:
    if user_id is None or key is None or key_type is None:
        return
    if pool is None:
        pool = await get_pool()
    
    num = await get_user_id(user_id, pool)
    if num is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                f'INSERT INTO "{SCHEMA}".keys (user_id, key, time, type, used) ' +
                'VALUES ($1, $2, $3, $4, $5) ' +
                'ON CONFLICT (key) DO UPDATE SET used = EXCLUDED.used, user_id = EXCLUDED.user_id, time = EXCLUDED.time',
                num, key, now(), key_type, used
            )
            

async def get_last_user_key(user_id:int , pool=POOL) -> dict:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    num = await get_user_id(user_id, pool)
    if num is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                f'SELECT key, time, type FROM "{SCHEMA}".keys WHERE user_id = $1 ORDER BY time DESC LIMIT 1',
                num
            )
    
    return {'key': row['key'], 'time': row['time'], 'type': row['type']} if row else None

async def get_unused_key_of_type(key_type:str, pool=POOL, day = 1) -> str:
    if key_type is None:
        return
    if pool is None:
        pool = await get_pool()
    
    progression_query = f'SELECT key FROM "{SCHEMA}".keys WHERE type = $1 AND used = false AND time > $2 ORDER BY time ASC LIMIT 1'
    regression_query = f'SELECT key FROM "{SCHEMA}".keys WHERE type = $1 AND used = false AND time < $2 ORDER BY time ASC LIMIT 1'
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(progression_query, key_type, now() )# - 86400 * abs(day))
            # row = await conn.fetchrow(regression_query, key_type, get_utc_time(0, 0, 0, False))
    
    return row['key'] if row else None

async def get_all_user_keys_24h(user_id:id, pool=POOL, day=1) -> list:
    if user_id is None:
        return []
    if pool is None:
        pool = await get_pool()
        
    progression_query = f'SELECT key, time, type FROM "{SCHEMA}".keys WHERE user_id = $1 AND time > $2 ORDER BY time DESC'
    regression_query = f'SELECT key, time, type FROM "{SCHEMA}".keys WHERE user_id = $1 AND time < $2 ORDER BY time DESC'
    
    num = await get_user_id(user_id, pool)
    if num is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(progression_query, num, now() - 86400 * abs(day))
            # rows = await conn.fetch(regression_query, num, get_utc_time(0, 0, 0, True))
    
    return [[row['key'], row['time'], row['type']] for row in rows] if rows and len(rows) > 0 else []

async def delete_user(user_id: int, pool=POOL) -> None:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'DELETE FROM "{SCHEMA}".users WHERE tg_id = $1', user_id)

async def get_all_user_ids(pool=POOL) -> list:
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT tg_id FROM "{SCHEMA}".users')
    
    return [row['tg_id'] for row in rows] if rows else None

async def get_all_dev(pool=POOL) -> list:
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT tg_id FROM "{SCHEMA}".users WHERE "right" > 0')
    
    return [row['tg_id'] for row in rows] if rows else None

async def get_cached_data(user_id:int, pool=POOL) -> dict:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    query = f'SELECT * FROM "{SCHEMA}".cache WHERE user_id = $1'
    num = await get_user_id(user_id, pool)
    if num is None:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(query, num)

    cached_data = {key: value for key, value in zip(rows[0].keys(), rows[0].values())}
    return cached_data

async def update_cache_process(pool=POOL) -> list:
    if pool is None:
        pool = await get_pool()
    
    # Запрос для обновления и получения tg_id
    update_query = f'''
    UPDATE "{SCHEMA}".cache
    SET process = true
    WHERE process = false
    RETURNING user_id
    '''
    
    # Запрос для получения tg_id по user_id
    user_query = f'''
    SELECT tg_id
    FROM "{SCHEMA}".users
    WHERE id = $1
    '''
    
    async with pool.acquire() as conn:
        # Выполняем обновление и получаем обновленные user_id
        updated_rows = await conn.fetch(update_query)
        
        # Получаем tg_id для обновленных user_id
        tg_ids = [row['user_id'] for row in updated_rows]
        tg_ids_list = []
        
        for user_id in tg_ids:
            tg_id_row = await conn.fetchrow(user_query, user_id)
            if tg_id_row:
                tg_ids_list.append(tg_id_row['tg_id'])
    
    return tg_ids_list

        

async def write_cached_data(user_id:int, cached_data: dict, pool=POOL) -> None:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    user_id_in_db = await get_user_id(user_id, pool)
    if user_id_in_db is None:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Формируем запрос на обновление
            update_query = f'''
                UPDATE "{SCHEMA}".cache
                SET {', '.join([f'{key} = ${i+2}' for i, key in enumerate(cached_data.keys())])}
                WHERE user_id = $1
            '''
            
            # Выполняем запрос на обновление
            update_result = await conn.execute(update_query, user_id_in_db, *cached_data.values())
            
            # Проверяем, было ли обновлено что-то
            if update_result == "UPDATE 0":
                # Если нет, вставляем новую запись
                insert_query = f'''
                    INSERT INTO "{SCHEMA}".cache (user_id, {', '.join(cached_data.keys())})
                    VALUES ($1, {', '.join([f'${i+2}' for i in range(len(cached_data))])})
                    ON CONFLICT (user_id) DO UPDATE SET {', '.join([f'{key} = EXCLUDED.{key}' for key in cached_data.keys()])}
                '''
                await conn.execute(insert_query, user_id_in_db, *cached_data.values())


async def get_all_refs(user_id:int, pool=POOL) -> list:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    query = f'SELECT ref_id FROM "{SCHEMA}".users WHERE ref_id = $1'
    
    async with pool.acquire() as conn:
        # Directly fetch the results without explicit transaction (SELECT query doesn't need it)
        rows = await conn.fetch(query, user_id)

    # Extract the 'ref_id' values
    ref_ids = [row['ref_id'] for row in rows] if rows else []
    return ref_ids
    
async def insert_user(user_id:int, username:str, ref=0, lang='en', pool=POOL) -> int:
    if user_id is None or username is None:
        return
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'INSERT INTO "{SCHEMA}".users (tg_id, tg_username, ref_id, lang) '+
                               'VALUES ($1, $2, $3, $4) '+
                               'ON CONFLICT (tg_id) DO UPDATE '+
                               'SET tg_username = EXCLUDED.tg_username', 
                               user_id, username, ref, lang)
            num = await conn.fetchrow(f'SELECT id FROM "{SCHEMA}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id)
            if num is None:
                return None
            num = num['id']
            await conn.execute(f'INSERT INTO "{SCHEMA}".cache (user_id) VALUES ($1) ON CONFLICT DO NOTHING', num)

async def get_user(user_id:int, pool=POOL) -> dict:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(f'SELECT * FROM "{SCHEMA}".users WHERE tg_id = $1', user_id)
    
    return {'username': row['tg_username'], 
            'tg_id': row['tg_id'], 
            'ref_id': row['ref_id'], 
            'lang': row['lang'], 
            'right': row['right'],
            'ref': row['ref_id'],
            'id': row['id']} if row else None

def relative_time(time, reverse=False):
    if reverse:
        return time - now()
    return now() - time

def format_remaining_time(target_time: int, pref=" ago", reverse=False) -> str:
    delta = relative_time(target_time, reverse)
    prefix = "" if delta < 0 else pref
    delta = abs(delta)

    seconds = delta % 60
    minutes = (delta // 60) % 60
    hours = (delta // 3600)
    
    if hours > 0:
        return f"{int(hours)} hours {int(minutes)} minutes{prefix}"
    elif minutes > 0:
        return f"{int(minutes)} minutes{prefix}"
    else:
        return f"{int(seconds)} seconds{prefix}"

def get_utc_time(target_hour: int, target_minute: int, target_second: int = 0, next = True) -> datetime:
    # Текущее время в UTC
    now = datetime.now(timezone.utc)
    
    # Время, заданное пользователем, но для текущего дня
    target_time_today = datetime.combine(now.date(), time(target_hour, target_minute, target_second, tzinfo=timezone.utc))
    
    # Если целевое время уже прошло сегодня, выбираем следующую дату
    if now >= target_time_today:
        if next:
            target_time_next_day = target_time_today + timedelta(days=1)
        else:
            target_time_next_day = target_time_today - timedelta(days=1)
    else:
        target_time_next_day = target_time_today

    return int(target_time_next_day.timestamp())