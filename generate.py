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
PROXY_LIST = config['PROXY']  # Load the list of proxies from config
farmed_keys, attempts = 0, {}
loading, MAX_LOAD = 0, 15

users = [x for x in ALL_EVENTS]

def get_logger(file_level=logging.DEBUG, console_level=logging.DEBUG, base_level=logging.DEBUG):
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

async def fetch_api(session:aiohttp.ClientSession, path: str, body=None|dict, auth:str = None) -> dict:
    url = f'https://api.gamepromo.io{path}'
    headers = {}

    if auth:
        headers['authorization'] = f'Bearer {auth}'
    else:
        headers['content-type'] = 'application/json'

    # Select a random proxy from the list
    proxy = random.choice(PROXY_LIST)
    logger.debug(f"Using proxy: {proxy}")

    async with session.post(url, headers=headers, json=body, proxy=proxy) as res:
        data = await res.text()

        if config['DEBUG']:
            logger.debug(f'URL: {url}')
            logger.debug(f'Headers: {headers}')
            logger.debug(f'Body: {body}')
            logger.debug(f'Response Status: {res.status}')
            logger.debug(f'Response Body: {data}')

        if not res.ok:
            raise Exception(f"{res.status} {res.reason}: {data}")

        return await res.json()

async def get_key(session, game_key):
    global loading, MAX_LOAD
    game_config = config['EVENTS'][game_key]
    delay_ms = randint(config['EVENTS'][game_key]['EVENTS_DELAY'][0], config['EVENTS'][game_key]['EVENTS_DELAY'][1])
    client_id = str(uuid.uuid4())

    body = {
        'appToken': game_config['APP_TOKEN'],
        'clientId': client_id,
        'clientOrigin': ['ios','android'].pop(random.randint(0,1))
    }
    login_client_data = await fetch_api(session, '/promo/login-client', body)
    loading = loading + 1 
    await delay(delay_ms)

    auth_token = login_client_data['clientToken']
    promo_code = None

    for attempt in range(config['MAX_RETRY']):
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