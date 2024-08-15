import json
import random
import logging
import asyncio
import aiohttp
import uuid
import os
from random import randint
from database import log_timestamp

# Load configuration
config = json.loads(open('config.json').read())
ALL_EVENTS = config['EVENTS']
DEBUG_MODE = config['DEBUG']
PROXY_LIST = [{'proxy':proxy, 'work': False} for proxy in config['PROXY']]   # Load the list of proxies from config
farmed_keys, attempts = 0, {}
loading, MAX_LOAD = 0, 15

users = [x for x in ALL_EVENTS]

def get_random_proxy():
    global PROXY_LIST
    return random.choice(PROXY_LIST)['proxy']

def get_free_proxy():
    for proxy in PROXY_LIST:
        if not proxy['work']:  # Проверяем, что прокси не работает
            set_work_proxy(proxy['proxy'])
            return proxy['proxy']
    return get_random_proxy()

def set_work_proxy(proxy:str, work=True):
    for p in PROXY_LIST:
        if p['proxy'] == proxy:  # Сравнение строки с полем 'proxy'
            p['work'] = work
            return
    logger.warning(f"Прокси {proxy} не найден в списке.")

def get_logger(file_level=logging.DEBUG, console_level=logging.INFO, base_level=logging.DEBUG):
    # Создаем логгер
    logger = logging.getLogger("logger")
    logger.setLevel(base_level)  # Устанавливаем базовый уровень логирования

    # Проверяем, есть ли уже обработчики, и если да, удаляем их
    if logger.hasHandlers():
        logger.handlers.clear()

    # Создаем каталог для логов, если он не существует
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Создаем обработчик для записи в файл
    file_handler = logging.FileHandler(f'{log_dir}/{log_timestamp()}.log')
    file_handler.setLevel(file_level)  # Устанавливаем уровень логирования для файла

    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)  # Устанавливаем уровень логирования для консоли

    # Создаем форматтер
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Привязываем форматтер к обработчикам
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Добавляем обработчики к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Выводим тестовое сообщение для проверки форматирования
    logger.debug("Логгер настроен и работает корректно.")

    return logger

logger = get_logger()

def generate_loading_bar(progress=loading, length=MAX_LOAD, max=MAX_LOAD) -> str:
    global loading, MAX_LOAD
    text =  '[' + '▊' * int(progress / max * length if progress / max * length < length else length) +\
                 '▁' * (length - int(progress / max * length) if progress / max * length < length else 0) +\
            ']' + f' {progress / max * 100 if progress / max * 100 < 100 else 100:.2f}%'
    return text

def delay_random() -> float:
    return random.random() + 1

async def delay(ms) -> None:
    ms += delay_random()
    logger.debug(f"Waiting {ms}ms")
    await asyncio.sleep(ms / 1000)

async def fetch_api(session: aiohttp.ClientSession, path: str, body: dict, auth: str = None) -> dict:
    url = f'https://api.gamepromo.io{path}'
    headers = {'content-type': 'application/json', 'Accept-Encoding': 'gzip, deflate'}

    if auth:
        headers['authorization'] = f'Bearer {auth}'

    proxy = get_free_proxy()

    try:
        async with session.post(url, headers=headers, json=body, proxy=proxy) as res:
            if DEBUG_MODE:
                logger.debug(f"Using proxy: {proxy}")
                logger.debug(f'URL: {url}')
                logger.debug(f'Headers: {headers}')
                logger.debug(f'Body: {body}')
                logger.debug(f'Response Status: {res.status}')

            if not res.ok:
                await asyncio.sleep(10)
                set_work_proxy(proxy, False)
                raise Exception(f"{res.status} {res.reason}")

            # Парсинг только JSON (экономия трафика)
            response_data = await res.json()

            return response_data

    finally:
        # Независимо от успеха или ошибки, освобождаем прокси
        set_work_proxy(proxy, False)


async def get_key(session, game_key):
    global loading, MAX_LOAD
    
    if DEBUG_MODE:
        await asyncio.sleep(randint(config['DEBUG_DELAY'][0], config['DEBUG_DELAY'][1]) / 1000)
        game_key = 'C0D3'
        return config['DEBUG_KEY'] + "-" + "".join([random.choice("0123456789ABCDE") for _ in range(16)])
        
    game_config = config['EVENTS'][game_key]
    delay_ms = randint(config['EVENTS'][game_key]['EVENTS_DELAY'][0], config['EVENTS'][game_key]['EVENTS_DELAY'][1])
    client_id = str(uuid.uuid4())

    body = {
        'appToken': game_config['APP_TOKEN'],
        'clientId': client_id,
        'clientOrigin': 'ios'
    }
    login_client_data = await fetch_api(session, '/promo/login-client', body)
    loading = loading + 1 
    await delay(delay_ms)

    auth_token = login_client_data['clientToken']
    promo_code = None

    for attempt in range(config['MAX_RETRY']):
        # asyncio.sleep(config['DELAY'])
        logger.debug(f"Attempt {attempt + 1} of {config['MAX_RETRY']} for {game_key}...")
        body = {
            'promoId': game_config['PROMO_ID'],
            'eventId': str(uuid.uuid4()),
            'eventOrigin': 'undefined'
        }
        register_event_data = await fetch_api(session, '/promo/register-event', body, auth_token)
        loading = loading + 1 

        if not register_event_data.get('hasCode'):
            await delay(delay_ms)
            continue

        body = {
            'promoId': game_config['PROMO_ID'],
        }
        create_code_data = await fetch_api(session, '/promo/create-code', body, auth_token)
        loading = loading + 1 

        promo_code = create_code_data.get('promoCode')
        if promo_code:
            break

        await delay(delay_ms)

    if promo_code is None:
        logger.error('Failed to generate promo code after maximum retries')
        return None

    return promo_code