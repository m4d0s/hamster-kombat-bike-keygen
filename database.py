import asyncpg
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

HAMSTER = config['SCHEMAS']['HAMSTER']
SSL_MODE = config['DB']['SSL']  # Assumes SSL configuration is handled correctly
POOL = None

#base
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




#promo(tasks)
async def append_checker(user_id: int, promo_id: int, pool=POOL):
    if user_id is None or promo_id is None:
        return
    
    if pool is None:
        pool = await get_pool()  # Убедитесь, что get_pool() возвращает корректный пул соединений
    
    num = await get_user_id(user_id, pool)
    if num is None:
        return  # В случае, если пользователь не найден, можно также вести логирование
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                f'INSERT INTO "{HAMSTER}".checker (user_id, promo_id) VALUES ($1, $2)',
                num, promo_id
            )

async def get_checker_by_user_id(user_id:int, pool=POOL):
    if user_id is None:
        return
    
    if pool is None:
        pool = await get_pool()
        
    num = await get_user_id(user_id, pool)
    if num is None:
        return []

    async with pool.acquire() as conn:
        async with conn.transaction():
            nums = await conn.fetch(
                f'SELECT * FROM "{HAMSTER}".checker WHERE user_id = $1 ORDER BY id DESC LIMIT 1',
                num
            )
            return [row['promo_id'] for row in nums] if nums else []

async def get_promotions(pool=POOL):
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT * FROM "{HAMSTER}".promo')
    
    # Преобразование каждой строки в словарь
    result = {str(row['id']):dict(row) for row in rows}
    return result

async def insert_task(task: dict, check=1, pool=POOL) -> None:
    if task is None:
        return
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            record = await conn.fetchrow(
                f'INSERT INTO "{HAMSTER}".promo (name, "desc", link, check_id, control) ' +
                'VALUES ($1, $2, $3, $4, $5) ' +
                'ON CONFLICT (check_id) DO UPDATE SET name = EXCLUDED.name, "desc" = EXCLUDED."desc", link = EXCLUDED.link, control = EXCLUDED.control ' +
                'RETURNING id, name, "desc", link, check_id, control',
                task['name'], task['desc'], task['link'], task['check_id'], check
            )
            if record:
                return record['id']
            return None

async def delete_task_by_id(id:int, pool=POOL) -> None:
    if id is None:
        return
    
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                f'DELETE FROM "{HAMSTER}".promo WHERE id = $1',
                id
            )




#key funcs
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
                f'INSERT INTO "{HAMSTER}".keys (user_id, key, time, type, used) ' +
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
                f'SELECT * FROM "{HAMSTER}".keys WHERE user_id = $1 ORDER BY time DESC LIMIT 1',
                num
            )
    
    return {key: value for key, value in zip(row.keys(), row.values())} if row else None

async def get_unused_key_of_type(key_type:str, pool=POOL, day = 1) -> str:
    if key_type is None:
        return
    if pool is None:
        pool = await get_pool()
    
    progression_query = f'SELECT key FROM "{HAMSTER}".keys WHERE type = $1 AND used = false AND time > $2 ORDER BY time ASC LIMIT 1'
    regression_query = f'SELECT key FROM "{HAMSTER}".keys WHERE type = $1 AND used = false AND time < $2 ORDER BY time ASC LIMIT 1'
    
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
        
    progression_query = f'SELECT key, time, type FROM "{HAMSTER}".keys WHERE user_id = $1 AND time > $2 ORDER BY time DESC'
    regression_query = f'SELECT key, time, type FROM "{HAMSTER}".keys WHERE user_id = $1 AND time < $2 ORDER BY time DESC'
    
    num = await get_user_id(user_id, pool)
    if num is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(progression_query, num, now() - 86400 * abs(day))
            # rows = await conn.fetch(regression_query, num, get_utc_time(0, 0, 0, True))
    
    return [[row['key'], row['time'], row['type']] for row in rows] if rows and len(rows) > 0 else []




#cache funcs
async def get_cached_data(user_id:int, pool=POOL) -> dict:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    query = f'SELECT * FROM "{HAMSTER}".cache WHERE user_id = $1'
    num = await get_user_id(user_id, pool)
    if num is None:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(query, num)
    
    cached_data = {key: value for key, value in zip(rows[0].keys(), rows[0].values())} if rows else None
    return cached_data

async def update_cache_process(pool=POOL) -> list:
    if pool is None:
        pool = await get_pool()
    
    # Запрос для обновления и получения tg_id
    update_query = f'''
    UPDATE "{HAMSTER}".cache
    SET process = true
    WHERE process = false
    RETURNING user_id
    '''
    
    # Запрос для получения tg_id по user_id
    user_query = f'''
    SELECT tg_id
    FROM "{HAMSTER}".users
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
                UPDATE "{HAMSTER}".cache
                SET {', '.join([f'{key} = ${i+2}' for i, key in enumerate(cached_data.keys())])}
                WHERE user_id = $1
            '''
            
            # Выполняем запрос на обновление
            update_result = await conn.execute(update_query, user_id_in_db, *cached_data.values())
            
            # Проверяем, было ли обновлено что-то
            if update_result == "UPDATE 0":
                # Если нет, вставляем новую запись
                insert_query = f'''
                    INSERT INTO "{HAMSTER}".cache (user_id, {', '.join(cached_data.keys())})
                    VALUES ($1, {', '.join([f'${i+2}' for i in range(len(cached_data))])})
                    ON CONFLICT (user_id) DO UPDATE SET {', '.join([f'{key} = EXCLUDED.{key}' for key in cached_data.keys()])}
                '''
                await conn.execute(insert_query, user_id_in_db, *cached_data.values())





#user functions
async def get_all_refs(user_id:int, pool=POOL) -> list:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    query = f'SELECT ref_id FROM "{HAMSTER}".users WHERE ref_id = $1'
    
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
            await conn.execute(f'INSERT INTO "{HAMSTER}".users (tg_id, tg_username, ref_id, lang) '+
                               'VALUES ($1, $2, $3, $4) '+
                               'ON CONFLICT (tg_id) DO UPDATE '+
                               'SET tg_username = EXCLUDED.tg_username', 
                               user_id, username, ref, lang)
            num = await conn.fetchrow(f'SELECT id FROM "{HAMSTER}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id)
            if num is None:
                return None
            num = num['id']
            await conn.execute(f'INSERT INTO "{HAMSTER}".cache (user_id) VALUES ($1) ON CONFLICT DO NOTHING', num)

async def get_user(user_id:int, pool=POOL) -> dict:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(f'SELECT * FROM "{HAMSTER}".users WHERE tg_id = $1', user_id)
    
    return {'username': row['tg_username'], 
            'tg_id': row['tg_id'], 
            'ref_id': row['ref_id'], 
            'lang': row['lang'], 
            'right': row['right'],
            'ref': row['ref_id'],
            'id': row['id']} if row else None

async def delete_user(user_id: int, pool=POOL) -> None:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'DELETE FROM "{HAMSTER}".users WHERE tg_id = $1', user_id)

async def get_all_user_ids(pool=POOL) -> list:
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT tg_id FROM "{HAMSTER}".users')
    
    return [row['tg_id'] for row in rows] if rows else None

async def get_all_dev(pool=POOL, level= 1) -> list:
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT tg_id FROM "{HAMSTER}".users WHERE "right" > $1', level - 1)
    
    return [row['tg_id'] for row in rows] if rows else None

async def get_user_id(tg_id:int, pool=POOL):
    if tg_id is None:
        return
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            num = await conn.fetchrow(
                f'SELECT * FROM "{HAMSTER}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1',
                tg_id
            )
            if num is None:
                return None
            return num['id']





#time functions
def now() -> int:
    return int(datetime.now().timestamp())

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
        return f"{int(minutes)} minutes{prefix} {int(seconds)} seconds"
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