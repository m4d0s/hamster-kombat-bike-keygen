from quart import Quart, request
import json
import random
import logging
import time
import asyncio
import base64
import aiohttp
from database import log_timestamp

# Configure logging
logging.basicConfig(
    filename=f'logs/{log_timestamp()}.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Quart(__name__)

json_config = json.loads(open('config.json').read())
ALL_PAIRS = [[json_config['EVENTS'][i]["APP_TOKEN"], json_config['EVENTS'][i]["PROMO_ID"]] for i in json_config['EVENTS']]
DEBUG_MODE = json_config['DEBUG']
EVENTS_DELAY = json_config['EVENTS_DELAY'][1] if DEBUG_MODE else json_config['EVENTS_DELAY'][0]
USER_ID, USER, HASH = None, None, None
farmed_keys, attempts = 0, {}
MAX_LOAD = 12

def delay_random():
    return random.random() / 3 + 1

def generate_client_id():
    timestamp = int(time.time() * 1000)
    random_numbers = ''.join(str(random.randint(0, 9)) for _ in range(19))
    return f'{timestamp}-{random_numbers}'

async def login(client_id, app_token):
    if not client_id:
        raise ValueError('No client id')
    if DEBUG_MODE:
        return app_token + ':deviceid:' + generate_client_id() + ':8B5BnSuEV2W:' + str(int(time.time()))
    
    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.gamepromo.io/promo/login-client', json={
            'appToken': app_token,
            'clientId': client_id,
            'clientOrigin': 'deviceid'
        }) as response:
            response_data = await response.json()
            return response_data['clientToken']

async def emulate_progress(client_token, promo_id):
    if not client_token:
        raise ValueError('No access token')
    if DEBUG_MODE:
        return attempts.get(client_token, 0) >= 5
    
    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.gamepromo.io/promo/register-event', headers={
            'Authorization': f'Bearer {client_token}'
        }, json={
            'promoId': promo_id,
            'eventId': generate_client_id(),
            'eventOrigin': 'undefined'
        }) as response:
            response_data = await response.json()
            return response_data['hasCode']

async def generate_key(client_token, promo_id):
    if DEBUG_MODE:
        return 'BIKE-TH1S-1S-JU5T-T35T' if attempts.get(client_token, 0) >= 5 else ''
    
    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.gamepromo.io/promo/create-code', headers={
            'Authorization': f'Bearer {client_token}'
        }, json={
            'promoId': promo_id
        }) as response:
            response_data = await response.json()
            return response_data['promoCode']

loading = 0
def generate_loading_bar(progress=loading, length=MAX_LOAD, max=MAX_LOAD):
    text = '[' + '█' * int(progress / max * length) + '  ' * (20 - int(progress / max * length)) + ']' + f' {progress / max * 100:.2f}%'
    return text, progress + 1

async def process_pair(app_token, promo_id):
    client_id = generate_client_id()
    text, _ = generate_loading_bar(loading)
    client_token = await login(client_id, app_token)
    text, _ = generate_loading_bar(loading)

    for i in range(7):
        await asyncio.sleep(EVENTS_DELAY * delay_random())
        text, _ = generate_loading_bar(loading)
        if await emulate_progress(client_token, promo_id):
            loading = MAX_LOAD - 3
            break

    key = await generate_key(client_token, promo_id)
    text, _ = generate_loading_bar(loading)
    return key

@app.route('/keygen', methods=['GET'])
async def start():
    global USER_ID, USER, HASH, farmed_keys, loading
    USER_ID = request.args.get('id')
    USER = request.args.get('user')
    HASH = request.args.get('hash')
    
    tasks = [process_pair(app_token, promo_id) for app_token, promo_id in ALL_PAIRS]
    keys = await asyncio.gather(*tasks)
    
    if USER_ID:
        keys_data = [{'id': USER_ID, 'user': USER, 'hash': HASH, 'key': key} for key in keys]
        keys_base64 = [base64.b64encode(json.dumps(key_data).encode()).decode() for key_data in keys_data]
        
        async with aiohttp.ClientSession() as session:
            results = []
            for key_data in keys_base64:
                async with session.post('http://176.119.159.166:7000/key', params={'v': key_data}) as response:
                    response_data = await response.json()
                    status = response_data.get('status')
                    points = response_data.get('points')
                    if status != 'ok':
                        return f"⛔ {status}", 400
                    farmed_keys += 1
                    results.append(f"@{USER}: +💎{points * farmed_keys}")
            return "\n".join(results), 200
    return json.dumps(keys), 200

if __name__ == '__main__':
    print('Quart app started...')
    app.run(debug=DEBUG_MODE)
