import json
import random
import logging
import asyncio
import aiohttp
import uuid
import os
from random import randint
from database import log_timestamp, get_proxies, set_proxy, get_free_proxy

# Load configuration
config = json.loads(open('config.json').read())
PROXY_LIST = asyncio.get_event_loop().run_until_complete(get_proxies())
PROXY_LIST = [{'link': x['link'], 'work': x['work']} for x in PROXY_LIST]  # Load the list of proxies from config
farmed_keys, attempts = 0, {}
users = [x for x in config['EVENTS']]

def get_logger(file_level=logging.DEBUG, console_level=logging.DEBUG, base_level=logging.DEBUG):
    # Создаем логгер
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
                    raise Exception(f"{res.status} {res.reason}")

                # Парсинг только JSON (экономия трафика)
                response_data = await res.json()

                return response_data
            
    except Exception as e:
        error_text = " ".join(e.args) if e.args and len(e.args)!=0 else e.match if e.match else str(e)
        logger.error(f'Error fetch_api: {error_text}')

async def get_key(session, game_key, pool=None):
    
    if config['DEBUG']:
        await delay(randint(config['DEBUG_DELAY'] // 2, config['DEBUG_DELAY']), "Debug key delay")
        game_key = 'C0D3'
        return config['DEBUG_KEY'] + "-" + "".join([random.choice("0123456789ABCDE") for _ in range(16)])
       
    proxy = await get_free_proxy(pool)    
    try:
        game_config = config['EVENTS'][game_key]
        delay_ms = randint(config['EVENTS'][game_key]['EVENTS_DELAY'][0], config['EVENTS'][game_key]['EVENTS_DELAY'][1])
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