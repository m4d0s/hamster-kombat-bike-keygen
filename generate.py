import json
import random
import logging
import asyncio
import aiohttp
import uuid
from random import randint
from database import log_timestamp

# Set up logging
logging.basicConfig(level=logging.INFO, filename='logs/'+log_timestamp()+'.log', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Load configuration
config = json.loads(open('config.json').read())
ALL_EVENTS = config['EVENTS']
DEBUG_MODE = config['DEBUG']
PROXY_LIST = config['PROXY']  # Load the list of proxies from config
farmed_keys, attempts = 0, {}
loading, MAX_LOAD = 0, 15

# Configure logging
logging.basicConfig(level=logging.DEBUG if config['DEBUG'] else logging.INFO)
logger = logging.getLogger(__name__)

users = [x for x in ALL_EVENTS]

def generate_loading_bar(progress=loading, length=MAX_LOAD, max=MAX_LOAD):
    global loading, MAX_LOAD
    text = '[' + '█' * int(progress / max * length) + '  ' * (20 - int(progress / max * length)) + ']' + f' {progress / max * 100:.2f}%'
    return text

def delay_random():
    return random.random() + 1

async def delay(ms):
    ms += delay_random()
    logger.debug(f"Waiting {ms}ms")
    await asyncio.sleep(ms / 1000)

async def fetch_api(session, path, auth_token_or_body=None, body=None):
    url = f'https://api.gamepromo.io{path}'
    headers = {}

    if isinstance(auth_token_or_body, str):
        headers['authorization'] = f'Bearer {auth_token_or_body}'

    if auth_token_or_body is not None and not isinstance(auth_token_or_body, str):
        headers['content-type'] = 'application/json'
        body = auth_token_or_body

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

    login_client_data = await fetch_api(session, '/promo/login-client', {
        'appToken': game_config['APP_TOKEN'],
        'clientId': client_id,
        'clientOrigin': 'ios',
    })
    loading = loading + 1 
    await delay(delay_ms)

    auth_token = login_client_data['clientToken']
    promo_code = None

    for attempt in range(config['MAX_RETRY']):
        register_event_data = await fetch_api(session, '/promo/register-event', auth_token, {
            'promoId': game_config['PROMO_ID'],
            'eventId': str(uuid.uuid4()),
            'eventOrigin': 'undefined'
        })
        loading = loading + 1 

        if not register_event_data.get('hasCode'):
            await delay(delay_ms)
            continue

        create_code_data = await fetch_api(session, '/promo/create-code', auth_token, {
            'promoId': game_config['PROMO_ID'],
        })
        loading = loading + 1 

        promo_code = create_code_data.get('promoCode')
        if promo_code:
            break

        await delay(delay_ms)

    if promo_code is None:
        logger.error('Failed to generate promo code after maximum retries')
        return None

    return promo_code