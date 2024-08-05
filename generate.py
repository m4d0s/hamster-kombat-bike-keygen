from flask import Flask, request
import json
import random
import logging
import time
import asyncio
import base64
import requests
from database import log_timestamp

# Configure logging
logging.basicConfig(level=logging.INFO, filename='logs/'+log_timestamp()+'.log', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__)

json_config = json.loads(open('config.json').read())
APP_TOKEN, PROMO_ID = json_config['APP_TOKEN'], json_config['PROMO_ID']
DEBUG_MODE = json_config['DEBUG']
EVENTS_DELAY = json_config['EVENTS_DELAY'][1] if DEBUG_MODE else json_config['EVENTS_DELAY'][0]
USER_ID, USER, HASH = None, None, None
farmed_keys, attempts = 0, {}
MAX_LOAD = 12

def delay_random():
    return random.random() / 3 + 1

def sleep(ms):
    time.sleep(ms / 1000)

def generate_client_id():
    timestamp = int(time.time() * 1000)
    random_numbers = ''.join(str(random.randint(0, 9)) for _ in range(19))
    return f'{timestamp}-{random_numbers}'

def login(client_id):
    if not client_id:
        raise ValueError('No client id')
    if DEBUG_MODE:
        return APP_TOKEN + ':deviceid:'+generate_client_id()+':8B5BnSuEV2W:' + str(int(time.time()))
    
    response = requests.post('https://api.gamepromo.io/promo/login-client', headers={
        'content-type': 'application/json; charset=utf-8',
        'Host': 'api.gamepromo.io'
    }, json={
        'appToken': APP_TOKEN,
        'clientId': client_id,
        'clientOrigin': 'deviceid'
    })
    response_data = response.json()
    return response_data['clientToken']

def emulate_progress(client_token):
    if not client_token:
        raise ValueError('No access token')
    if DEBUG_MODE:
        return attempts.get(client_token, 0) >= 5
    response = requests.post('https://api.gamepromo.io/promo/register-event', headers={
        'content-type': 'application/json; charset=utf-8',
        'Host': 'api.gamepromo.io',
        'Authorization': f'Bearer {client_token}'
    }, json={
        'promoId': PROMO_ID,
        'eventId': generate_client_id(),
        'eventOrigin': 'undefined'
    })
    response_data = response.json()
    return response_data['hasCode']

def generate_key(client_token):
    if DEBUG_MODE:
        return 'BIKE-TH1S-1S-JU5T-T35T' if attempts.get(client_token, 0) >= 5 else ''
    
    response = requests.post('https://api.gamepromo.io/promo/create-code', headers={
        'content-type': 'application/json; charset=utf-8',
        'Host': 'api.gamepromo.io',
        'Authorization': f'Bearer {client_token}'
    }, json={
        'promoId': PROMO_ID
    })
    response_data = response.json()
    return response_data['promoCode']

loading = 0
def generate_loading_bar(progress = loading, length=MAX_LOAD, max = MAX_LOAD):
    text = '['+'█' * int(progress/max * length)+'  ' * (20 - int(progress/max * length))+']'+ f' {0:.2f}%'.format(progress/max * 100)
    return text, progress + 1

@app.route('/keygen', methods=['GET'])
def start():
    global USER_ID, USER, HASH, farmed_keys, loading
    USER_ID = request.args.get('id')
    USER = request.args.get('user')
    HASH = request.args.get('hash')
    text = ''
    
    # message_id = request.args.get('message_id')
    # user_id = request.args.get('user_id')

    client_id = generate_client_id()
    text, loading = generate_loading_bar(loading)
    client_token = login(client_id)
    text, loading = generate_loading_bar(loading)

    for i in range(7):
        sleep(EVENTS_DELAY * delay_random() * 1000)
        text, loading = generate_loading_bar(loading)
        if emulate_progress(client_token):
            loading = MAX_LOAD - 3
            break

    key = generate_key(client_token)
    text, loading = generate_loading_bar(loading)
    
    if USER_ID:
        key_data = base64.b64encode(json.dumps({'id': USER_ID, 'user': USER, 'hash': HASH, 'key': key}).encode()).decode()
        text, loading = generate_loading_bar(loading)
        response = requests.post('http://176.119.159.166:7000/key', params={'v': key_data})
        text, loading = generate_loading_bar(loading)
        response_data = response.json()
        status = response_data.get('status')
        points = response_data.get('points')
        text, loading = generate_loading_bar(loading)
        if status != 'ok':
            return f"⛔ {status}", 400
        farmed_keys += 1
        return f"@{USER}: +💎{points * farmed_keys}", 200
    return key, 200
