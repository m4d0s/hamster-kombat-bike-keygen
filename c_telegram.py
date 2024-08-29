import asyncio
import json
import tg  # noqa: F401

from aiogram import Bot, Dispatcher

from database import (get_config, set_config)
from proxy import set_proxy

# Предполагается, что set_config и set_proxies уже реализованы

json_config = json.loads(open('config.json').read())
with open('localization.json') as f:
    translate = json.load(f)
    snippet = translate.pop('snippets')

POOL = None

def request_level(level:int, require, user_id) -> bool:
    return level >= require or user_id == db_config['DEV_ID']

async def reload_config(config_path='config.json', pool=POOL):
    # 1. Загрузить локальный конфиг
    with open(config_path, 'r') as f:
        local_config = json.load(f)
    
    # 2. Получить текущие значения из базы данных
    db_config = await get_config(pool)
    proxies = {}
    
    # 3. Списки обязательных и дефолтных значений
    config_must = {
        'number': ['DEV_ID'],
        'text': ['API_TOKEN']
    }
    
    defaults = {
        'DELAY': 30,
        'GEN_PROXY': 0,
        'MAX_RETRY': 10,
        'COUNT': 16,
        'DEBUG_DELAY': 10000,
        'DEBUG_KEY': 'C0D3-TH1S-1S-JU5T-T35T',
        'DEBUG_GAME': 'C0D3',
    }
    
    dont_touch = ["EVENTS", "SCHEMAS", "DEBUG_DELAY", "DEBUG_KEY", "DEBUG", "DB", "DEBUG_GAME",
                  "GEN_PROXY", "MAX_RETRY", "DELAY", "DEBUG_LOG", "MINING", "MINING_DB", "DEV_ID", "IPV6"]
    need_to = ["DEV_ID", "API_TOKEN", "MAIN_GROUP", "MAIN_CHANNEL", "PROXY"]
    
    # Инициализация итогового конфига
    final_config = db_config.copy()
    
    # 4. Проверка обязательных параметров и загрузка из локального или БД
    for category, keys in config_must.items():
        for key in keys:
            if key.upper() in local_config and local_config[key.upper()] not in (0, ''):
                final_config[category][key] = local_config[key]
            elif key.upper() in defaults and key.upper() not in final_config[category]:
                final_config[category][key] = defaults[key]
    
    # 6. Обработка прокси
    if 'PROXY' in local_config:
        for proxy in local_config['PROXY']:
            if proxy not in proxies:
                proxies[proxy] = False
    
    useless = []
    # 7. Обнуление значений в локальном конфиге (за исключением "EVENTS" и "SCHEMAS")
    for key in local_config:
        if key not in dont_touch and key in need_to:
            if isinstance(local_config[key], int):
                local_config[key] = 0
            elif isinstance(local_config[key], str):
                local_config[key] = ""
            elif isinstance(local_config[key], list):
                local_config[key] = []
        elif key not in dont_touch:
            useless.append(key)
    
    for key in useless:
        local_config.pop(key)
    
    # 8. Перезапись локального файла
    with open(config_path, 'w') as f:
        json.dump(local_config, f, indent=4)
    
    # 9. Вставка итогового конфига в базу данных
    await set_config(final_config, pool)
    await set_proxy(proxies, pool)
    
    real_final = {}
    # 10. Возврат итогового конфига
    for type in final_config:
        for key in final_config[type]:
            real_final[key] = final_config[type][key]
    return real_final


# f"https://t.me/{bot_info.username}?startgroup=true&admin=post_messages+edit_messages+delete_messages+invite_users"

# Initialize bot and dispatcher
db_config = asyncio.get_event_loop().run_until_complete(reload_config())
bot = Bot(token=db_config['API_TOKEN'])
BOT_INFO = asyncio.get_event_loop().run_until_complete(bot.get_me())
dp = Dispatcher(bot)
sem = asyncio.Semaphore(25)
