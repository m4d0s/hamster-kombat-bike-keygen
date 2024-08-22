import logging
import asyncio
import aiohttp
import aiofiles
import asyncpg
import random
import json
import uuid
from datetime import datetime
import os

# Load configuration
MINING_POOL = None
config = json.loads(open('config.json').read())
SCHEMAS = config['SCHEMAS']

farmed_keys, attempts = 0, {}
users = [x for x in config['EVENTS']]

def log_timestamp():
    return datetime.now().strftime('%Y-%m-%d')

def now() -> int:
    return int(datetime.now().timestamp())

def generate_loading_bar(progress=0, length=15, max=100) -> str:
    done = int(progress / max * length if progress / max * length < length else length)
    left = length - done
    percentage = progress / max * 100 if progress / max * 100 < 100 else 100
    
    text =  '[' + '▊' * done + '▁' * left + ']' + f' {percentage:.2f}%'
    return text

def get_logger(file_level=logging.INFO, base_level=logging.INFO, log=True):
    # Создаем логгер
    # asyncio.get_event_loop().set_debug(config['DEBUG_LOG'])
    logger = logging.getLogger("logger")
    logger.setLevel(base_level)  # Устанавливаем базовый уровень логирования
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Проверяем, есть ли уже обработчики, и если да, удаляем их
    if logger.hasHandlers():
        logger.handlers.clear()

    # Создаем каталог для логов, если он не существует
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Создаем обработчик для записи в файл
    file_handler = logging.FileHandler(f'{log_dir}/{log_timestamp()}.log')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_lvl = logging.DEBUG if config['DEBUG_LOG'] else logging.INFO
    console_handler.setLevel(console_lvl)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log:
        logger.debug("Logger setup sucessfull!\tBase log level: %s, Console log level: %s, File log level: %s", 
                    base_level, console_lvl, file_level)

    return logger

async def delay(ms, comment="") -> None:
    ms += random.random() + 1
    _ = f'({comment})' if comment else ''
    logger.debug(f"Waiting {ms}ms {_}")
    await asyncio.sleep(ms / 1000)

async def load_config(file_path):
    async with aiofiles.open(file_path, mode='r') as f:
        return json.loads(await f.read())

async def get_pool() -> asyncpg.Pool:
    global MINING_POOL
    if MINING_POOL is None:
        MINING_POOL = await asyncpg.create_pool(dsn=config['MINING_DB'])
    return MINING_POOL



async def new_key(session, game, pool):
    logging.info(f"Generating new key for {game}...")
    try:
        key = await get_key(session, game)
        if key:
            logging.info(f"Key for game {game} generated: {key}")
        else:
            logging.warning(f"Failed to generate key for game {game}")
        await insert_key_generation(0, key, game, used=False, pool=pool)
    except Exception as e:
        logging.error(f"Error generating key for {game}: {e}")

async def get_key(session, game_key, pool=None):
    
    if config['DEBUG']:
        await delay(random.randint(config['DEBUG_DELAY'] // 2, config['DEBUG_DELAY']), "Debug key delay")
        game_key = 'C0D3'
        return config['DEBUG_KEY'] + "-" + "".join([random.choice("0123456789ABCDE") for _ in range(16)])
    
    logger.debug(f'Fetching {game_key}...')
    proxy = await get_free_proxy(pool)
    logger.debug(f'Using proxy: {proxy["link"].split("@")[1]} ({proxy["link"].split(":")[0].upper()})')
        
    try:
        game_config = config['EVENTS'][game_key]
        delay_ms = random.randint(config['EVENTS'][game_key]['EVENTS_DELAY'][0], config['EVENTS'][game_key]['EVENTS_DELAY'][1])
        client_id = str(uuid.uuid4())

        body = {
            'appToken': game_config['APP_TOKEN'],
            'clientId': client_id,
            'clientOrigin': 'ios'
        }
        login_client_data = await fetch_api(session, '/promo/login-client', body, proxy=proxy)
        await delay(delay_ms, "Login delay")

        auth_token = login_client_data['clientToken']
        promo_code = None

        for attempt in range(config['MAX_RETRY']):
            # delay(config['DELAY'] * 1000)
            logger.debug(f"Attempt {attempt + 1} of {config['MAX_RETRY']} for {game_key}...")
            body = {
                'promoId': game_config['PROMO_ID'],
                'eventId': str(uuid.uuid4()),
                'eventOrigin': 'undefined'
            }
            register_event_data = await fetch_api(session, '/promo/register-event', body, auth_token, proxy=proxy)

            if not register_event_data.get('hasCode'):
                await delay(delay_ms, "Event delay")
                continue

            body = {
                'promoId': game_config['PROMO_ID'],
            }
            create_code_data = await fetch_api(session, '/promo/create-code', body, auth_token, proxy=proxy)

            promo_code = create_code_data.get('promoCode')
            if promo_code:
                break

            await delay(delay_ms, "Code delay")

        if promo_code is None:
            logger.error('Failed to generate promo code after maximum retries')
            return None
    except Exception as e:
        logger.error(f'Error get_key: {e}')
    finally:
        await set_proxy({proxy['link']: False}, pool=pool)

    return promo_code

async def fetch_api(session: aiohttp.ClientSession, path: str, body: dict, auth: str = None, proxy: dict = None) -> dict:
    url = f'https://api.gamepromo.io{path}'
    headers = {'content-type': 'application/json', 'Accept-Encoding': 'gzip, deflate'}

    if auth:
        headers['authorization'] = f'Bearer {auth}'
    
    if not proxy or len(proxy) == 0:
        logger.warning('No proxy found, use localhost (no proxy)')
    else:
        logger.debug(f'Using proxy: {proxy["link"].split("@")[1]} ({proxy["link"].split(":")[0].upper()})')
    proxy_str = proxy['link'] if proxy else None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body, proxy=proxy_str) as res:
                logger.debug(f'Using proxy: {proxy["link"].split("@")[1] if proxy else "localhost"}')
                logger.debug(f'URL: {url}')
                logger.debug(f'Headers: {headers}')
                logger.debug(f'Body: {body}')
                logger.debug(f'Response Status: {res.status}')

                if not res.ok:
                    await delay(config['DELAY'] * 1000, "API error")
                    await set_proxy({proxy['link']: False})
                    raise Exception(f"{res.status} {res.reason}")

                # Парсинг только JSON (экономия трафика)
                response_data = await res.json()

                return response_data
            
    except Exception as e:
        error_text = " ".join(e.args) if e.args and len(e.args)!=0 else e.match if e.match else str(e)
        logger.error(f'Error fetch_api: {error_text}')



async def set_proxy(proxies:dict, pool=MINING_POOL):
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

async def get_free_proxy(pool=MINING_POOL):
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

            if proxy:
                await set_proxy({proxy['link']: True}, pool=pool)

    return {'link': proxy['link'], 'work': proxy['work']} if proxy else None



async def get_user_id(tg_id:int, pool=MINING_POOL):
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

async def insert_key_generation(user_id:int, key:str, key_type:str, used=True, pool=MINING_POOL) -> None:
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


logger = get_logger()

async def main():
    global MINING_POOL, logger
    config = await load_config('config.json')
    events = [x for x in config['EVENTS']]
    limit = config['GEN_PROXY']
    semaphore = asyncio.Semaphore(limit)
    await get_pool()

    async with aiohttp.ClientSession() as session:
        tasks, i = [], -1
        while True:
            i+=1; i%=len(events)
            async with semaphore:
                tasks.append(asyncio.create_task(new_key(session, events[i], MINING_POOL)))
                await asyncio.sleep(2)

if __name__ == '__main__':
    asyncio.run(main())
