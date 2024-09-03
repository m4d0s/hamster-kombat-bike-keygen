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

async def check_db_connection(pool):
    async with pool.acquire() as conn:
       return True if await conn.fetchval('SELECT 1') else False

#base
async def get_pool(mining=False) -> asyncpg.Pool:
    global POOL, MINING_POOL
    if not mining:
        if POOL is None:
            POOL = await asyncpg.create_pool(dsn=config['DB'], )
        return POOL
    else:
        if MINING_POOL is None:
            MINING_POOL = await asyncpg.create_pool(dsn=config['MINING_DB'])
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




#promo
async def append_checker(user_id: int, promo_id: int, count=0, pool=None):
    # Early return if essential parameters are missing
    if user_id is None or promo_id is None:
        return
    
    # Ensure a valid connection pool is available
    if pool is None:
        pool = await get_pool()  # Ensure get_pool() returns a valid connection pool
    
    # Retrieve the numeric user ID (or another key) from the database
    num = await get_user_id(user_id, pool)
    if num is None:
        return  # Log this event if needed, since user was not found
    
    # Use the connection pool to acquire a connection
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check if the record already exists in the checker table
            id = await conn.fetchval(
                f'SELECT id FROM "{SCHEMAS["PROMOTION"]}".checker WHERE user_id = $1 AND promo_id = $2',
                num, promo_id
            )
            
            # If the record does not exist, insert a new one
            if not id:
                await conn.execute(
                    f'INSERT INTO "{SCHEMAS["PROMOTION"]}".checker (user_id, promo_id) VALUES ($1, $2)',
                    num, promo_id
                )
            
            # If the record exists and count > 0, update the count
            elif count > 0:
                await conn.execute(
                    f'UPDATE "{SCHEMAS["PROMOTION"]}".checker SET count = count + ($1) WHERE id = $2',
                    count, id
                )

async def append_ticket(user_id: int, promo_id: int, pool=POOL):
    if user_id is None or promo_id is None:
        return

    if pool is None:
        pool = await get_pool()  # Ensure get_pool() returns a valid connection pool
        
    num = await get_user_id(user_id, pool)
    if num is None:
        return  # Log this event if needed, since user was not found

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                f'INSERT INTO "{SCHEMAS["PROMOTION"]}".tickets (user_id, promo_id, time) VALUES ($1, $2, $3)',
                num, promo_id, now()
            )

async def get_tickets(user_id: int, start=0, end=None, giveaway_id=None, pool=POOL):
    end = end or now()
    
    if user_id is None:
        return []
    
    if pool is None:
        pool = await get_pool()
    
    num = await get_user_id(user_id, pool)
    if num is None:
        return []

    async with pool.acquire() as conn:
        async with conn.transaction():
            args = [f"time >= {start}" if start else "", f"time <= {end}" if end else "", f"task_id = {giveaway_id}" if giveaway_id else ""]
            args = "AND " + " AND ".join(arg for arg in args if arg) if args else ""
            records = await conn.fetch(f'SELECT * FROM "{SCHEMAS["PROMOTION"]}".tickets WHERE user_id = $1 {args}', num)
            return [dict(record) for record in records] or []

async def get_full_checkers(user_id: int, pool=POOL):
    if user_id is None:
        return

    if pool is None:
        pool = await get_pool()  # Убедитесь, что get_pool() возвращает корректный пул соединений

    num = await get_user_id(user_id, pool)
    if num is None:
        return  # В случае, если пользователь не найден, можно также вести логирование

    full_dict = {}
    async with pool.acquire() as conn:
        async with conn.transaction():
            records = await conn.fetch(f'SELECT * FROM "{SCHEMAS["PROMOTION"]}".checker WHERE user_id = $1', num)
            for record in records:
                full_dict[record['promo_id']] = dict(record)

    return full_dict
        

async def delete_checker(user_id: int, promo_id: int, pool=POOL):
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
                f'DELETE FROM "{SCHEMAS["PROMOTION"]}".checker WHERE user_id = $1 AND promo_id = $2',
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
                f'SELECT * FROM "{SCHEMAS["PROMOTION"]}".checker WHERE user_id = $1 ORDER BY id DESC',
                num
            )
            return [row['promo_id'] for row in nums] if nums else []

async def get_checker_by_task_id(task_id:int, pool=POOL):
    if task_id is None:
        return
    
    if pool is None:
        pool = await get_pool()
        

    async with pool.acquire() as conn:
        async with conn.transaction():
            nums = await conn.fetch(
                f'SELECT * FROM "{SCHEMAS["PROMOTION"]}".checker WHERE promo_id = $1 ORDER BY id ASC',
                task_id
            )
            return set([row['user_id'] for row in nums]) if nums else []


async def get_promotions(task_type: str = 'task', all=False, delay=0, pool=None):
    if not pool:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Получаем все промо по типу
            if task_type == 'all':
                promo_rows = await conn.fetch(
                    f'SELECT * FROM "{SCHEMAS["PROMOTION"]}".promo {"WHERE expire > " + str(now() + delay) if not all else ""}'
                )
            else:
                promo_rows = await conn.fetch(
                    f'SELECT * FROM "{SCHEMAS["PROMOTION"]}".promo WHERE type = $1 {"AND expire > " + str(now() + delay) if not all else ""}',
                    task_type
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
            
                    if result[promo_id]['type'] == 'giveaway':
                        prizes_q = f"SELECT * FROM \"{SCHEMAS['PROMOTION']}\".promo_prizes WHERE promo_id = $1 ORDER BY place ASC"
                        prizes = await conn.fetch(prizes_q, int(promo_id))
                        result[promo_id]['prizes'] = []
                        for row in prizes:
                            input = dict(row)
                            result[promo_id]['prizes'].append(input)

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
            # Initialize task_id
            task_id = None

            # Insert or update the main task record
            id = await conn.fetchval(
                f'''
                SELECT id FROM "{SCHEMAS["PROMOTION"]}".promo
                WHERE check_id = $1
                LIMIT 1
                ''',
                task['check_id']
            )
            
            if not id:
                record = await conn.fetchrow(
                    f'''
                    INSERT INTO "{SCHEMAS["PROMOTION"]}".promo (name, "desc", link, check_id, control, type, time, expire) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                    ''',
                    task['name'], task['desc'], task['link'], task['check_id'], check, task_type, now(), task['expire']
                )
                task_id = record['id']
            else:
                task_id = id
                await conn.execute(
                    f'''
                    UPDATE "{SCHEMAS["PROMOTION"]}".promo
                    SET name = $1, "desc" = $2, link = $3, control = $4, type = $5, time = $6, expire = $7
                    WHERE id = $8
                    ''',
                    task['name'], task['desc'], task['link'], check, task_type, now(), task['expire'], id
                )
            
            # Insert or update translations
            for lang, translations in task.items():
                if not isinstance(translations, dict):  # Skip non-translation keys
                    continue
                
                for obj, value in translations.items():
                    value = str(value)
                    some_id = await conn.fetchval(
                        f'''
                        SELECT id FROM "{SCHEMAS["PROMOTION"]}".promo_translate
                        WHERE promo_id = $1 AND lang = $2 AND type = $3
                        ''',
                        task_id, lang, obj
                    )
                    
                    if not some_id:
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
                            value, some_id
                        )
                
            if task_type == 'giveaway' and 'prizes' in task:
                for prize in task['prizes']:
                    task_id = prize.pop('promo_id') or task_id
                    if 'id' in prize:
                        prize_id = prize.pop('id')
                        query = f'''
                            UPDATE "{SCHEMAS["PROMOTION"]}".promo_prizes 
                            SET {", ".join([f"{key} = ${i+3}" for i, key in enumerate(prize.keys())])} 
                            WHERE promo_id = $1 AND id = $2
                        '''

                        await conn.execute(query, task_id, prize_id, *[prize[key] for key in prize])

                    else:
                        query = f'''
                            INSERT INTO "{SCHEMAS["PROMOTION"]}".promo_prizes (promo_id, {", ".join(prize.keys())})
                            VALUES ($1, {", ".join([f"${i+2}" for i in range(len(prize))])})
                            RETURNING id
                        '''

                        await conn.execute(query, task_id, *[prize[key] for key in prize])
    
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
                f'SELECT * FROM "{SCHEMAS["HAMSTER"]}".keys WHERE user_id = $1 and used = true ORDER BY time DESC LIMIT 1',
                num
            )
    
    return {key: value for key, value in zip(row.keys(), row.values())} if row else None

async def get_unused_key_of_type(key_type: str, pool=None, day: float = 1.0):
    if not key_type:  # Проверяем, что key_type не пустая строка и не None
        return None
    if pool is None:
        pool = await get_pool()
    if day <= 0:  # Проверяем, что day больше 0
        return None
    
    regression_query = (
        f'SELECT key FROM "{SCHEMAS["HAMSTER"]}".keys '
        'WHERE type = $1 AND used = false '
        'AND $2 < time AND time < $3 '
        'ORDER BY time ASC LIMIT 1'
    )
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                regression_query, 
                key_type, 
                get_utc_time(0, delta_days=(-(day - 1))), 
                get_utc_time(0, delta_days=1)
            )
    
    return row['key'] if row else None


async def get_all_user_keys_24h(user_id: int, start=None, end=None, pool=None) -> list:
    if user_id is None:
        return []
    if pool is None:
        pool = await get_pool()
    
    user_id_db = await get_user_id(user_id, pool)
    if user_id_db is None:
        return []

    # SQL запрос для получения ключей пользователя за последние 24 часа
    query = (
        f'SELECT key, time, type FROM "{SCHEMAS["HAMSTER"]}".keys '
        'WHERE user_id = $1 AND used = true '
        'AND $2 < time AND time < $3 '
        'ORDER BY time ASC'
    )
    
    start_time = start or get_utc_time(0, 0, 0, delta_days=0)
    end_time = end or get_utc_time(0, 0, 0, delta_days=1)

    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(query, user_id_db, start_time, end_time)
    
    return [[row['key'], row['time'], row['type']] for row in rows] if rows else []





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
    
async def insert_user(user_id:int, username:str, ref=0, lang='en', tg_lang='en', pool=POOL) -> int:
    if user_id is None or username is None:
        return
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'INSERT INTO "{SCHEMAS["HAMSTER"]}".users (tg_id, tg_username, ref_id, lang, tg_lang) '+
                               'VALUES ($1, $2, $3, $4, $5) '+
                               'ON CONFLICT (tg_id) DO UPDATE '+
                               'SET tg_username = EXCLUDED.tg_username, lang = EXCLUDED.lang, tg_lang = EXCLUDED.tg_lang', 
                               user_id, username, ref, lang, tg_lang)
            num = await conn.fetchrow(f'SELECT id FROM "{SCHEMAS["HAMSTER"]}".users WHERE tg_id = $1 ORDER BY id DESC LIMIT 1', user_id)
            if num is None:
                return None
            num = num['id']
            await conn.execute(f'INSERT INTO "{SCHEMAS["HAMSTER"]}".cache (user_id) VALUES ($1) ON CONFLICT DO NOTHING', num)

async def get_user(user_id:int, pool=POOL, tg = True) -> dict:
    if user_id is None:
        return
    if pool is None:
        pool = await get_pool()
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(f'SELECT * FROM "{SCHEMAS["HAMSTER"]}".users WHERE tg_id = $1', user_id) if tg \
                else await conn.fetchrow(f'SELECT * FROM "{SCHEMAS["HAMSTER"]}".users WHERE id = $1', user_id)
    
    return {key: value for key, value in zip(row.keys(), row.values())} if row else None

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
    return int(datetime.now(timezone.utc).timestamp())

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
    hours = int(delta // 3600) % 24
    days = int(delta // 86400) 
    
    if days > 0:
        return ' '.join([str(days), translate[4], prefix])
    if hours > 0:
        return ' '.join([str(hours), translate[1], str(minutes), translate[2], prefix])
    elif minutes > 0:
        return ' '.join([str(minutes), translate[2], str(seconds), translate[3], prefix])
    else:
        return ' '.join([str(seconds), translate[3], prefix])


def get_utc_time(target_hour: int = 0, target_minute: int = 0, target_second: int = 0, delta_days: float = 0.0) -> int:
    # Текущее время в UTC
    now = datetime.now(timezone.utc)
    
    # Время, заданное пользователем, но для текущего дня
    target_time_today = datetime.combine(now.date(), time(target_hour, target_minute, target_second, tzinfo=timezone.utc))
    
    # Корректируем целевое время на количество дней
    target_time = target_time_today + timedelta(days=delta_days)
    
    return int(target_time.timestamp())
