import json
import random
import logging
import asyncio
import aiohttp
import uuid
import os
from database import log_timestamp
from proxy import get_free_proxy, set_proxy, get_proxies

# Load configuration
config = json.loads(open('config.json').read())
PROXY_LIST = asyncio.get_event_loop().run_until_complete(get_proxies())
PROXY_LIST = [{'link': x['link'], 'work': x['work']} for x in PROXY_LIST]  # Load the list of proxies from c_telegramig
farmed_keys, attempts = 0, {}
users = [x for x in config['EVENTS']]


async def check_proxy(proxy: str, test_url: str = 'http://httpbin.org/ip', timeout: int = 10, retries: int = 4) -> bool:
    proxy_connector = aiohttp.ProxyConnector(proxy=proxy)

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession(connector=proxy_connector) as session:
                async with session.get(test_url, timeout=timeout) as response:
                    if response.status == 200:
                        logger.debug(f"Proxy {proxy} work (try {attempt})")
                        return True
                    else:
                        logger.debug(f"Proxy {proxy} not work (try {attempt}), status: {response.status}")
        except Exception as e:
            print(f"Error with {proxy} (try {attempt}): {e}")
        
        # Ожидание перед следующей попыткой
        await asyncio.sleep(1)

    print(f"Proxy {proxy} cabt not work after {retries} tries")
    return False

def get_logger(file_level=logging.INFO, base_level=logging.INFO):
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

    logger.debug("Logger setup sucessfull!\n\tBase log level: %s, Console log level: %s, File log level: %s", 
                 base_level, console_lvl, file_level)

    return logger

logger = get_logger()

def generate_loading_bar(progress=0, length=15, max=100) -> str:
    done = int(progress / max * length if progress / max * length < length else length)
    left = length - done
    percentage = progress / max * 100 if progress / max * 100 < 100 else 100
    
    text =  '[' + '▊' * done + '▁' * left + ']' + f' {percentage:.2f}%'
    return text

async def delay(ms, comment="") -> None:
    ms += random.random() + 1
    _ = f'({comment})' if comment else ''
    logger.debug(f"Waiting {ms}ms {_}")
    await asyncio.sleep(ms / 1000)

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
                    if str(res.status) == '400':
                        logger.debug(f'Response: {res.status} {res.reason}')
                    else:
                        raise Exception(f"{res.status} {res.reason}")

                # Парсинг только JSON (экономия трафика)
                response_data = await res.json()

                return response_data
            
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error fetch_api: {error_text}')

async def get_key(session, game_key, pool=None):
    
    logger.debug(f'Fetching {game_key}...')
    proxy = await get_free_proxy(pool)
        
    try:
        game_config = config['EVENTS'][game_key]
        delay_ms = random.randint(config['EVENTS'][game_key]['EVENTS_DELAY'][0], config['EVENTS'][game_key]['EVENTS_DELAY'][1]) if not config['EVENTS'][game_key]['DISABLED'] \
                    else random.randint(1000, 2000)
        attempts = config['MAX_RETRY'] if not config['EVENTS'][game_key]['DISABLED'] else config['MAX_RETRY'] * 2
        client_id = str(uuid.uuid4())

        body = {
            'appToken': game_config['APP_TOKEN'],
            'clientId': client_id,
            'clientOrigin': ['ios', 'android'].pop(random.randint(0, 1))
        }
        login_client_data = await fetch_api(session, '/promo/login-client', body, proxy=proxy)
        await delay(delay_ms, "Login delay")
        
        if not login_client_data:
            raise Exception("Failed to login: no data")
        auth_token = login_client_data['clientToken']
        promo_code = None

        for attempt in range(attempts):
            # delay(config['DELAY'] * 1000)
            logger.debug(f"Attempt {attempt + 1} of {attempts} for {game_key}...")
            body = {
                'promoId': game_config['PROMO_ID'],
                'eventId': str(uuid.uuid4()),
                'eventOrigin': 'undefined'
            }
            register_event_data = await fetch_api(session, '/promo/register-event', body, auth_token, proxy=proxy)

            if register_event_data and not register_event_data.get('hasCode'):
                await delay(delay_ms, "Event delay")
                continue

            body = {
                'promoId': game_config['PROMO_ID'],
            }
            create_code_data = await fetch_api(session, '/promo/create-code', body, auth_token, proxy=proxy)

            if create_code_data and 'promoCode' in create_code_data:
                promo_code = create_code_data.get('promoCode')
                if promo_code:
                    break

            await delay(delay_ms, "Code delay")
    except Exception as e:
        logger.error(f'Error get_key: {e}')
    finally:
        await set_proxy({proxy['link']: False}, pool=pool)

    return promo_code