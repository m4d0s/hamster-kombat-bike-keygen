import asyncpg
import json
from datetime import datetime, timedelta, time, timezone

def log_timestamp():
    return datetime.now().strftime('%Y-%m-%d')

# Load PostgreSQL configuration
with open('config.json') as f:
    config = json.load(f)

SCHEMAS = config['SCHEMAS']
POOL = None
MINING_POOL = None

#base
async def get_pool(mining=False) -> asyncpg.Pool:
    global POOL, MINING_POOL
    if not mining:
        if POOL is None:
            POOL = await asyncpg.create_pool(dsn=config['DB'])
        return POOL
    else:
        if MINING_POOL is None:
            MINING_POOL = await asyncpg.create_pool(dsn=config['DB'])
        return MINING_POOL

#config
async def get_config(pool=POOL):
    if pool is None:
        pool = await get_pool()  # Убедитесь, что get_pool() возвращает корректный пул соединений

    config = {}

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Предполагаем, что таблицы содержат столбцы 'key' и 'value'
            number_rows = await conn.fetch(f'SELECT key, value FROM "{SCHEMAS["CONFIG"]}".number')
            text_rows = await conn.fetch(f'SELECT key, value FROM "{SCHEMAS["CONFIG"]}".text')

            config = {
                'number': {row['key'].upper(): row['value'] for row in number_rows},
                'text': {row['key'].upper(): row['value'] for row in text_rows}
            }

    return config

async def get_proxies(pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан

    proxies = {}

    async with pool.acquire() as conn:
        async with conn.transaction():
            proxy_rows = await conn.fetch(f'SELECT id, proxy, work FROM "{SCHEMAS["CONFIG"]}".proxy')
            proxies = {
                row['proxy']: row['work']
                for row in proxy_rows
            }

    return proxies

async def set_config(config, pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Обработка секции 'number'
            for key, value in config.get('number', {}).items():
                await conn.execute(f'''
                    INSERT INTO "{SCHEMAS["CONFIG"]}".number (key, value)
                    VALUES ($1, $2)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value
                ''', key.lower(), value)

            # Обработка секции 'text'
            for key, value in config.get('text', {}).items():
                await conn.execute(f'''
                    INSERT INTO "{SCHEMAS["CONFIG"]}".text (key, value)
                    VALUES ($1, $2)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value
                ''', key.lower(), value)
           
async def set_proxy(proxies:dict, pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан

    async with pool.acquire() as conn:
        async with conn.transaction():
            for proxy in proxies:
                await conn.execute(f'''
                    INSERT INTO "{SCHEMAS["CONFIG"]}".proxy (link, work, time)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (link) DO UPDATE
                    SET work = EXCLUDED.work, time = EXCLUDED.time
                ''', proxy, proxies[proxy], now())       

async def get_free_proxy(pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            proxy = await conn.fetchrow(f'''
                SELECT link, work FROM "{SCHEMAS["CONFIG"]}".proxy
                WHERE work = false LIMIT 1
            ''')
            
            if not proxy:
                proxy = await conn.fetchrow(f'''
                    SELECT link, work FROM "{SCHEMAS["CONFIG"]}".proxy
                    ORDER BY RANDOM() LIMIT 1
                ''')
                
            await set_proxy({proxy['link']: True}, pool=pool)
    
    return {'link':proxy['link'], 'work': proxy['work']} if proxy else None





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
                f'INSERT INTO "{SCHEMAS["PROMOTION"]}".checker (user_id, promo_id) VALUES ($1, $2)',
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
                f'SELECT * FROM "{SCHEMAS["PROMOTION"]}".checker WHERE user_id = $1 ORDER BY id DESC LIMIT 1',
                num
            )
            return [row['promo_id'] for row in nums] if nums else []

async def get_promotions(task_type: str = 'task', pool=None):
    if not pool:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Получаем все промо по типу
            promo_rows = await conn.fetch(
                f'SELECT * FROM "{SCHEMAS["PROMOTION"]}".promo WHERE type = $1 and expire > $2',
                task_type, now()
            )
            # Преобразуем строки в словарь
            result = {str(row['id']): dict(row) for row in promo_rows}
            
            # Получаем все переводы, связанные с этими промо
            promo_ids = tuple(result.keys())
            if promo_ids:  # Проверяем, есть ли что-то для запроса
                for promo_id in promo_ids:
                    translate_rows = await conn.fetch(
                        f'SELECT * FROM "{SCHEMAS["PROMOTION"]}".promo_translate WHERE promo_id = $1',
                        int(promo_id)
                    )
                    
                    for row in translate_rows:
                        lang = row['lang']
                        translation_type = row['type']
                        value = row['value'] if translation_type not in ['check_id'] else int(row['value'])
                        
                        if lang not in result[promo_id]:
                            result[promo_id][lang] = {}
                        
                        result[promo_id][lang][translation_type] = value

    return result

async def insert_task(task: dict, check: int = 1, task_type: str = 'task', expire=9999999999999, pool=None) -> int:
    if not task:
        return None
    
    if not pool:
        pool = await get_pool()
        
    if 'expire' not in task:
        task['expire'] = expire
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Insert or update the main task record
            record = await conn.fetchrow(
                f'''
                INSERT INTO "{SCHEMAS["PROMOTION"]}".promo (name, "desc", link, check_id, control, type, time, expire) 
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (check_id) 
                DO UPDATE SET 
                    name = EXCLUDED.name, 
                    "desc" = EXCLUDED."desc", 
                    link = EXCLUDED.link, 
                    control = EXCLUDED.control,
                    time = EXCLUDED.time,
                    expire = EXCLUDED.expire
                RETURNING id
                ''',
                task['name'], task['desc'], task['link'], task['check_id'], check, task_type, now(), task['expire']
            )
            
            task_id = record['id']
            
            # Insert or update translations
            for lang, translations in task.items():
                if lang in ['name', 'desc', 'link', 'check_id', 'id', 'control', 'type', 'time', 'expire', 'day']:  # Skip non-translation keys
                    continue
                
                for obj, value in translations.items():
                    if obj in ['check_id']:
                        value = str(value)
                    some_id = await conn.fetchrow(
                        f'''
                        SELECT id FROM "{SCHEMAS["PROMOTION"]}".promo_translate
                        WHERE promo_id = $1 AND lang = $2 AND type = $3
                        ''',
                        task_id, lang, obj
                    )
                    
                    if some_id is None:
                        await conn.execute(
                            f'''
                            INSERT INTO "{SCHEMAS["PROMOTION"]}".promo_translate (promo_id, lang, type, value)
                            VALUES ($1, $2, $3, $4)
                            ''',
                            task_id, lang, obj, value
                        )
                    else:
                        await conn.execute(
                            f'''
                            UPDATE "{SCHEMAS["PROMOTION"]}".promo_translate
                            SET value = $1
                            WHERE id = $2
                            ''',
                            value, some_id['id']
                        )
    
    return task_id


async def delete_task_by_id(id:int, pool=POOL) -> None:
    if id is None:
        return
    
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                f'DELETE FROM "{SCHEMAS["PROMOTION"]}".promo WHERE id = $1',
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
                f'INSERT INTO "{SCHEMAS["HAMSTER"]}".keys (user_id, key, time, type, used) ' +
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
                f'SELECT * FROM "{SCHEMAS["HAMSTER"]}".keys WHERE user_id = $1 ORDER BY time DESC LIMIT 1',
                num
            )
    
    return {key: value for key, value in zip(row.keys(), row.values())} if row else None

async def get_unused_key_of_type(key_type:str, pool=POOL, day = 1.0) -> str:
    if key_type is None:
        return
    if pool is None:
        pool = await get_pool()
    
    progression_query = f'SELECT key FROM "{SCHEMAS["HAMSTER"]}".keys WHERE type = $1 AND used = false AND time > $2 ORDER BY time ASC LIMIT 1'
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(progression_query, key_type, now()  - 86400 * abs(day))
    
    return row['key'] if row else None

async def get_all_user_keys_24h(user_id:id, pool=POOL, day=1.0) -> list:
    if user_id is None:
        return []
    if pool is None:
        pool = await get_pool()
        
    progression_query = f'SELECT key, time, type FROM "{SCHEMAS["HAMSTER"]}".keys WHERE user_id = $1 AND time > $2 ORDER BY time DESC'
    
    num = await get_user_id(user_id, pool)
    if num is None:
        return
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(progression_query, num, now() - 86400 * abs(day))
            # rows = await conn.fetch(regression_query, num, get_utc_time(0, 0, 0, True))
    
    return [[row['key'], row['time'], row['type']] for row in rows] if rows is not None and len(rows) > 0 else []




#cache funcs
async def get_cached_data(user_id:int, pool=POOL) -> dict:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    query = f'SELECT * FROM "{SCHEMAS["HAMSTER"]}".cache WHERE user_id = $1'
    num = await get_user_id(user_id, pool)
    if num is None:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(query, num)
    
    cached_data = {key: value for key, value in zip(rows[0].keys(), rows[0].values())} if rows else None
    return cached_data

async def update_proxy_work(pool=POOL) -> None:
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'UPDATE "{SCHEMAS["CONFIG"]}".proxy SET work = false')

async def update_cache_process(pool=POOL) -> list:
    if pool is None:
        pool = await get_pool()
    
    # Запрос для обновления и получения tg_id
    update_query = f'''
    UPDATE "{SCHEMAS["HAMSTER"]}".cache
    SET process = true
    WHERE process = false
    RETURNING user_id
    '''
    
    # Запрос для получения tg_id по user_id
    user_query = f'''
    SELECT tg_id
    FROM "{SCHEMAS["HAMSTER"]}".users
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
                UPDATE "{SCHEMAS["HAMSTER"]}".cache
                SET {', '.join([f'{key} = ${i+2}' for i, key in enumerate(cached_data.keys())])}
                WHERE user_id = $1
            '''
            
            # Выполняем запрос на обновление
            update_result = await conn.execute(update_query, user_id_in_db, *cached_data.values())
            
            # Проверяем, было ли обновлено что-то
            if update_result == "UPDATE 0":
                # Если нет, вставляем новую запись
                insert_query = f'''
                    INSERT INTO "{SCHEMAS["HAMSTER"]}".cache (user_id, {', '.join(cached_data.keys())})
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
        
    query = f'SELECT ref_id FROM "{SCHEMAS["HAMSTER"]}".users WHERE ref_id = $1'
    
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
            await conn.execute(f'INSERT INTO "{SCHEMAS["HAMSTER"]}".users (tg_id, tg_username, ref_id, lang) '+
                               'VALUES ($1, $2, $3, $4) '+
                               'ON CONFLICT (tg_id) DO UPDATE '+
                               'SET tg_username = EXCLUDED.tg_username', 
                               user_id, username, ref, lang)
            num = await conn.fetchrow(f'SELECT id FROM "{SCHEMAS["HAMSTER"]}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id)
            if num is None:
                return None
            num = num['id']
            await conn.execute(f'INSERT INTO "{SCHEMAS["HAMSTER"]}".cache (user_id) VALUES ($1) ON CONFLICT DO NOTHING', num)

async def get_user(user_id:int, pool=POOL) -> dict:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(f'SELECT * FROM "{SCHEMAS["HAMSTER"]}".users WHERE tg_id = $1', user_id)
    
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
            await conn.execute(f'DELETE FROM "{SCHEMAS["HAMSTER"]}".users WHERE tg_id = $1', user_id)

async def get_all_user_ids(pool=POOL) -> list:
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f'SELECT tg_id FROM "{SCHEMAS["HAMSTER"]}".users')
    
    return [row['tg_id'] for row in rows] if rows else None

async def get_user_id(tg_id:int, pool=POOL):
    if tg_id is None:
        return
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            num = await conn.fetchrow(
                f'SELECT * FROM "{SCHEMAS["HAMSTER"]}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1',
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

def format_remaining_time(target_time: int, pref='en', reverse=False) -> str:
    translate = json.load(open('localization.json'))[pref]['format_remaining_time']
    delta = relative_time(target_time, reverse)
    prefix = "" if delta < 0 else translate[0]
    delta = abs(delta)

    seconds = delta % 60
    minutes = (delta // 60) % 60
    hours = int(delta // 3600)
    
    if hours > 0:
        return ' '.join([str(hours), translate[1], str(minutes), translate[2], prefix])
    elif minutes > 0:
        return ' '.join([str(minutes), translate[2], str(seconds), translate[3], prefix])
    else:
        return ' '.join([str(seconds), translate[3], prefix])

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