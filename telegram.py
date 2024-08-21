import asyncio
import aiohttp
import json
import re
import os
import random
import traceback
import aiofiles
from io import BytesIO
from multiprocessing import Process
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ChatPermissions, ChatType
from aiogram.utils.exceptions import (MessageNotModified, MessageToDeleteNotFound, InvalidQueryID, ChatNotFound,
                                      BotBlocked, MessageIsTooLong, MessageToEditNotFound, MessageCantBeDeleted,
                                      BadRequest, MessageCantBeEdited, UserDeactivated)

# from solo import mining
from generate import generate_loading_bar, get_key, logger, delay
from database import (insert_key_generation, get_last_user_key, get_all_user_ids, now, get_promotions, update_proxy_work,
                      get_unused_key_of_type, relative_time, get_all_user_keys_24h, insert_user, format_remaining_time, 
                      delete_user, get_pool, get_all_refs, get_user, get_cached_data as get_cached, write_cached_data, 
                      update_cache_process, insert_task, get_checker_by_user_id, append_checker, delete_task_by_id,
                      get_config, set_config, set_proxy)

# Предполагается, что set_config и set_proxies уже реализованы

json_config = json.loads(open('config.json').read())
with open('localization.json') as f:
    translate = json.load(f)
    snippet = translate.pop('snippets')

BOT_INFO = None
POOL = None

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
                  "GEN_PROXY", "MAX_RETRY", "DELAY", "DEBUG_LOG", "MINING"]
    need_to = ["DEV_ID", "API_TOKEN", "COUNT", "MAIN_GROUP", "MAIN_CHANNEL", "PROXY"]
    
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
dp = Dispatcher(bot)
sem = asyncio.Semaphore(25)

#Cache funcs
async def set_cached_data(user:int, data:dict, pool=POOL):
    data_copy = data.copy()
    data_copy.pop('id', None)
    data_copy.pop('lang', None)
    data_copy.pop('user_id', None)
    data_copy.pop('right', None)
    
    await write_cached_data(user, data_copy, pool=pool) 

async def get_cached_data(user_id:int) -> tuple:
    user = await get_user(user_id, pool=POOL)
    cache_default = {'user_id':None, 
                     'welcome':None, 
                     'loading':None, 
                     'report':None, 
                     'process':True, 
                     'error':None, 
                     'tasks': None, 
                     'lang': 'en', 
                     'addtask': None, 
                     'deletetask': None}
    if not user:
        cache_default['user_id'] = user_id
        await set_cached_data(user_id, cache_default)
    config = await get_cached(user_id, pool=POOL)
    config = config if config is not None else cache_default
    
    config['process'] = config['process'] if 'process' in config else True
    config['lang'] = user['lang'] if user and user['lang'] else 'en'
    config['right'] = user['right'] if user and user['right'] else 0
    
    return config




#helpful
def html_back_escape(text:str) -> str:
    return str(text).replace('&lt;', '＜').replace('&gt;', '＞').replace('&amp;', '＆')

def hide_key(key:str) -> str:
    hide_symb = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    hiden_key = ''
    for i in range(len(key)):
        if key[i] in hide_symb:
            hiden_key += '*'
        else:
            hiden_key += key[i]
    return hiden_key

def request_level(level:int, require, user_id) -> bool:
    return level >= require or user_id == db_config['DEV_ID']

def username_valid(username:str) -> bool:
    symbols = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
    return all(i in symbols for i in username) \
            and 4 <= len(username) <= 32 \
            and not (username[0].isdigit() or username[0] == '_')

@dp.callback_query_handler(lambda c: c.data == 'close')
async def close(call: types.CallbackQuery):
    await call.message.delete()


#loadbars
async def update_loadbar(chat_id: int, game_key: str, session: aiohttp.ClientSession, count=1, update_delay=2) -> None:
    # Получаем кэш один раз в начале
    cache = await get_cached_data(chat_id)
    cache['process'] = False
    await set_cached_data(chat_id, cache)

    # Определяем время задержки
    if json_config['DEBUG']:
        sec = json_config['DEBUG_DELAY'] // 1000 
        max_sec = json_config['DEBUG_DELAY'] // 1000 * count
    else:
        event_delay = json_config['EVENTS'][game_key]['EVENTS_DELAY']
        delay_rand = random.randint(event_delay[0], event_delay[1])
        sec = delay_rand * (1 + db_config["MAX_RETRY"] * 2) // 1000 // 3 * count
        max_sec = event_delay[1] * (1 + db_config["MAX_RETRY"] * 2) // 1000 * count
    
    # Начальная настройка текста и прогресс-баров
    time_text = translate[cache['lang']]['update_loadbar'][1].replace('{mins}', format_remaining_time(now() + sec, pref=cache['lang']))
    starting_text = f"{time_text}"
    loadbars = [generate_loading_bar(progress=0, max=sec) for _ in range(count)]
    keys = []
    if json_config['DEBUG']:
        game_key = json_config['DEBUG_GAME']

    loading = 0
    for i in range(count):
        part_load = 0
        free_key = await get_unused_key_of_type(game_key, pool=POOL)
        
        if free_key is not None:
            keys.append(free_key)
            loadbars[i] = snippet['bold'].format(text=game_key + ": ") + snippet['code'].format(text=free_key)
            await insert_key_generation(chat_id, free_key, game_key, used=True, pool=POOL)
            continue
        
        task = asyncio.create_task(get_key(session, game_key))
        
        while not task.done():
            plus_text = snippet['italic'].format(text=translate[cache['lang']]['update_loadbar'][2].replace('{max}', format_remaining_time(now() + max_sec, pref=cache['lang']))) if loading > sec else ''
            cache = await get_cached_data(chat_id)
            mark = "[!] " if loading > sec else ""
            if cache['process']:
               task.cancel()
               return [key for key in keys if key is not None]

            loadbars[i] = mark + generate_loading_bar(progress=part_load, max=sec // count)
            some_text = '\n'.join(loadbars)
            full_text = f"{starting_text}\n\n{some_text}\n{plus_text}"
            stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['update_loadbar'][3], callback_data="stop_process"))

            await try_to_edit(full_text, chat_id, cache['loading'], keyboard=stop_button)
            
            delay_s = update_delay + random.random()
            loading += delay_s
            part_load += delay_s
            await delay(delay_s * 1000, f"Update loadbar for {chat_id}")
        
        # Обработка завершения задачи
        try:
            key = task.result()
            keys.append(key)
            if key is not None:
                loadbars[i] = snippet['bold'].format(text=game_key + ": ") + snippet['code'].format(text=key)
            else:
                loadbars[i] = snippet['bold'].format(text=game_key + ": ") + snippet['code'].format(text=translate[cache['lang']]['update_loadbar'][4])
        except Exception as e:
            logger.warning(f"Не удалось получить ключ: {str(e)}")
            keys.append(None)
            loadbars[i] = snippet['bold'].format(text=game_key + ": ") + snippet['code'].format(text=translate[cache['lang']]['update_loadbar'][4])


    # Обновляем кэш в конце выполнения
    cache['process'] = True
    await set_cached_data(chat_id, cache)

    return [key for key in keys if key is not None]

async def update_report(chat_id: int, 
                        text: str | dict, 
                        keyboard: InlineKeyboardMarkup = None, 
                        users:list = None, 
                        warning:bool = False, 
                        max_concurrent_tasks:int = 10) -> None:
    
    cache = await get_cached_data(chat_id)  # Получаем кэшированные данные
    loading = 0
    
    # Получаем список всех пользователей, если он не был передан
    if users is None:
        user_ids = await get_all_user_ids(pool=POOL)
    else:
        if users == []:
            return
        user_ids = users
    
    max = len(user_ids)  # Общее количество пользователей
    
    semaphore = asyncio.Semaphore(max_concurrent_tasks)  # Ограничение на количество параллельных задач

    async def send_with_semaphore(user_id):
        user_cache = await get_cached_data(user_id)
        async with semaphore:
            try:
                if isinstance(text, dict):
                    if user_cache['lang'] in text.keys():
                        await send_message_to_user(user_id, text[user_cache['lang']], keyboard)
                    else:
                        await send_message_to_user(user_id, text['default'], keyboard)
                else:
                    await send_message_to_user(user_id, text, keyboard)
            except BotBlocked:
                await delete_user(user_id, pool=POOL)
            except ChatNotFound:
                await delete_user(user_id, pool=POOL)

    # Создаем задачи для отправки сообщений
    tasks = [asyncio.create_task(send_with_semaphore(user_id)) for user_id in user_ids]

    cache['process'] = False
    await set_cached_data(chat_id, cache)  # Записываем изменения в кэш
    
    while not cache['process']:
        loading = len([x for x in tasks if x.done()])
        progress_text = generate_loading_bar(progress=loading, max=max)
        
        if loading == max:
            cache['process'] = True
            break
        stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['update_report'][4], callback_data="stop_process"))
        time_text = translate[cache['lang']]['update_report'][0].replace('{mins}', str(max))
        full_report_text = time_text + f"\n{loading}/{max}" + '\n\n' + progress_text
        
        try:
            await try_to_edit(full_report_text, chat_id, cache['report'], stop_button)
        except MessageNotModified:
            logger.error(f"Message for report in chat {chat_id} not modified")
        
        await delay(1000, f"Update report load for {chat_id}")
    
    undone = [x for x in tasks if not x.done()]
    for task in undone:
        task.cancel()   
    
    if db_config['MAIN_CHANNEL'] or db_config['MAIN_GROUP'] and not warning:
        try:
            checker_group = await bot.get_chat(db_config['MAIN_GROUP'])
        except ChatNotFound:
            logger.warning(f'Group {db_config["FIRST_SETUP"]["MAIN_GROUP"]} not found')
            checker_group = None
        except Exception as e:
            send_error_message(chat_id, "Chat to report not found or something else happened, check logs", e, True)    
        
        try: 
            checker_channel = await bot.get_chat(db_config['MAIN_CHANNEL'])
        except ChatNotFound:
            logger.warning(f'Channel {db_config["FIRST_SETUP"]["MAIN_CHANNEL"]} not found')
            checker_channel = None
        except Exception as e:
            send_error_message(chat_id, "Channels to report not found or something else happened, check logs", e, True) 
        
        if not warning: 
            strs = []
            if checker_group:
                link = checker_group.invite_link if checker_group.invite_link else 'https://t.me/' + checker_group.username
                if link is not None:
                    strs.append(f"💬 {snippet['link'].format(link=link, text=translate[cache['lang']]['update_report'][1])}")
            if checker_channel:
                link = checker_channel.invite_link if checker_channel.invite_link else 'https://t.me/' + checker_channel.username
                if link is not None:
                    strs.append(f"📢 {snippet['link'].format(link=link, text=translate[cache['lang']]['update_report'][2])}")
            if BOT_INFO:
                link = f"https://t.me/{BOT_INFO.username}"
                strs.append(f"🤖 {snippet['link'].format(link=link, text=translate[cache['lang']]['update_report'][3])}")  
                
            text_to_send = '\n'.join([snippet['quoteV2'].format(text=(snippet['bold'].format(text=translate[lang]['NAME']) \
                            + "\n" + code if lang in translate else code))for lang, code in text.items() if lang != 'default']) \
                            + "\n\n" + " | ".join(strs)
        
            if checker_channel is not None:
                await new_message(text=text_to_send, chat_id=checker_channel.id)
            elif checker_group is not None:
                await new_message(text=text_to_send, chat_id=checker_group.id)
         
    await try_to_delete(chat_id, cache['report'])
    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['update_report'][6], callback_data="main_menu"))
    REPORT_MESS = await new_message(translate[cache['lang']]['update_report'][5], chat_id, stop_button)
    cache['report'] = REPORT_MESS.message_id
    cache['process'] = True
    await set_cached_data(chat_id, cache)  # Снова записываем изменения в кэш

    # Дожидаемся завершения всех задач
    await asyncio.gather(*tasks)

@dp.callback_query_handler(lambda c: c.data == 'stop_process')
async def stop_process(callback_query: types.CallbackQuery) -> None:
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    # Получаем текущий кэш и устанавливаем флаг process в False
    cache = await get_cached_data(chat_id)
    cache['process'] = True  # Это прервет цикл while в update_report
    await set_cached_data(chat_id, cache)
    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['stop_process'][2], callback_data="main_menu"))

    # Отправляем сообщение о завершении
    await callback_query.answer(translate[cache['lang']]['stop_process'][0])
    await try_to_edit(translate[cache['lang']]['stop_process'][1], chat_id, message_id, stop_button)



#messages
async def try_to_delete(chat_id:int, message_id:int) -> bool:
    if message_id is None or message_id == 0:
        logger.debug('Message ID is None to delete in chat ' + str(chat_id))
        return False
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except MessageToDeleteNotFound:
        return False
    except MessageCantBeDeleted:
        return False
    except Exception as e:
        error_text = " ".join(e.args) if e.args and len(e.args)!=0 else e.match if e.match else str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
    
async def try_to_edit(text:str, chat_id:int, message_id:int, keyboard: InlineKeyboardMarkup = None) -> bool:
    if message_id is None or message_id == 0:
        logger.debug('Message ID is None to edit in chat ' + str(chat_id))
        return False
    try:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return True
    except MessageNotModified:
        return False
    except MessageToEditNotFound:
        return False
    except MessageCantBeEdited:
        return False
    except Exception as e:
        error_text = " ".join(e.args) if e.args and len(e.args)!=0 else e.match if e.match else str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
    
async def send_error_message(chat_id:int, message:str, e:Exception = None, only_dev:bool = False) -> types.Message:
    cache = await get_cached_data(chat_id) ##cache
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['send_error_message'][0], callback_data='main_menu'))
    
    cache['process'] = True
    if cache['error']:
        await try_to_delete(chat_id, cache['error'])
    if e is not None:
        err_t = f'Error: {e}' if str(e) else ''
        logger.error(traceback.format_stack()[-2].split('\n')[0].strip() + f'\t{err_t}')
    if only_dev:
        ERROR_MESS = await new_message(text=message, chat_id=db_config['DEV_ID'], keyboard=keyboard)
    else:
        ERROR_MESS = await new_message(text=message, chat_id=chat_id, keyboard=keyboard)
    cache['error'] = ERROR_MESS.message_id
    await set_cached_data(chat_id, cache) ##write
    return ERROR_MESS
    
async def new_message(text: str, chat_id: int, keyboard: InlineKeyboardMarkup = None, disable_preview:bool = True, document = None, parse_mode = ParseMode.HTML) -> types.Message:
    try:
        if document:
            return await bot.send_document(text=html_back_escape(text), 
                                           chat_id=chat_id, 
                                           parse_mode=parse_mode, 
                                           disable_web_page_preview=disable_preview, 
                                           reply_markup=keyboard, 
                                           document=document)
        return await bot.send_message(text=html_back_escape(text), 
                                      chat_id=chat_id, 
                                      parse_mode=parse_mode, 
                                      disable_web_page_preview=disable_preview, 
                                      reply_markup=keyboard)
    # except MessageIsTooLong:
    #     logger.warning('Message is too long to send in chat ' + str(chat_id))
    except UserDeactivated:
        logger.warning("User ({user_id}) deactivated".format(user_id=chat_id))
    except BotBlocked:
        logger.warning("Bot was blocked by user ({user_id})".format(user_id=chat_id))
    except ChatNotFound:
        logger.warning("Chat ({user_id}) not found".format(user_id=chat_id))
    except Exception as e:
        error_text = " ".join(e.args) if e.args and len(e.args)!=0 else e.match if e.match else str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
        
async def send_message_to_user(user_id:int, text: str, keyboard: InlineKeyboardMarkup) -> None:
    if user_id == BOT_INFO.id:
        return
    cache = await get_cached_data(user_id) ##cache
    try:
        await new_message(chat_id=user_id, text=text, keyboard=keyboard)
    except UserDeactivated:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][2].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
    except ChatNotFound:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][0].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
    except BotBlocked:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][1].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
    except Exception as e:
        error_text = " ".join(e.args) if e.args and len(e.args)!=0 else e.match if e.match else str(e)
        logger.error(f'Error sending message in chat {user_id}: {error_text}')
        return
    await set_cached_data(user_id, cache) ##write



#user setup
@dp.callback_query_handler(lambda c: c.data == 'main_menu')
async def process_callback_main_menu(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    if cache['error']:
        await try_to_delete(callback_query.message.chat.id, cache['error'])
        cache['error'] = None
    if cache['addtask']:
        await try_to_delete(callback_query.message.chat.id, cache['addtask'])
        cache['addtask'] = None
    await try_to_delete(callback_query.message.chat.id, callback_query.message.message_id)
    await set_cached_data(callback_query.message.chat.id, cache) ##write
    await send_welcome(callback_query.message)

@dp.message_handler(commands=['start'])
async def start_pointer(message: types.Message) -> None:
    if len(message.get_args()) == 1 and message.get_args()[0].isdigit() or len(message.get_args()) == 0:
        await send_language_choose(message)
    elif len(message.get_args()) == 1 and message.get_args()[0].startswith('giveaway_'):
        fake_callback = types.CallbackQuery(id=f"simulated_giveaway_{message.get_args()}", data=f'giveaway_{message.get_args()}', message=message, from_user=message.from_user)
        await process_callback_giveaway(fake_callback)     
    
async def send_language_choose(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    user = await get_user(message.chat.id, pool=POOL)
    logger.debug("User {user_id} started bot, lang: {lang}".format(user_id=message.chat.id, lang=message.from_user.language_code))
    if not user:
        lang_code = message.from_user.language_code
        if lang_code and lang_code in translate.keys():
            fake_callback = types.CallbackQuery(id=f"simulated_lang_{lang_code}_{message.from_user.id}",
                                                                data=f'lang_{lang_code}_{message.get_args()}', 
                                                                message=message, 
                                                                from_user=message.from_user)
            fake_callback.from_user = message.from_user
            await process_callback_language(fake_callback)
            return
        text = f"{translate[cache['lang']]['send_language_choose'][0]}\n"
        keyboard = InlineKeyboardMarkup(row_width=2)
        for x in translate:
            inline_btn = InlineKeyboardButton(text=translate[x]["NAME"], callback_data=f'lang_{x}_{message.get_args()}')
            keyboard.add(inline_btn)
        if cache['welcome']:
            await try_to_delete(chat_id=message.chat.id, message_id=cache['welcome'])
        WELCOME_MESS = await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard)
        cache['welcome'] = WELCOME_MESS.message_id
    else:
        await send_welcome(message)
        await insert_user(message.chat.id, message.from_user.username, ref=user['ref'], lang=cache['lang'],  pool=POOL)
    await delay(1000, "Language choose")
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    await set_cached_data(message.chat.id, cache) ##write

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('lang_'))
async def process_callback_language(callback_query: types.CallbackQuery) -> None:
    data = callback_query.data
    LANG = data.split('_')[1]
    message = callback_query.message
    ref = int(data.split('_')[2]) if data.split('_')[2] and data.split('_')[2].isdigit() and int(data.split('_')[2]) != message.chat.id else 0
    await try_to_delete(chat_id=message.chat.id, message_id=callback_query.message.message_id)
    await insert_user(message.chat.id, callback_query.from_user.username, ref=ref, lang=LANG, pool=POOL)
    await send_welcome(callback_query.message)
    
    
    
#mass report
@dp.callback_query_handler(lambda c: c.data == 'report')
async def process_callback_report(callback_query: types.CallbackQuery) -> None:
    await mass_report(callback_query.message)

@dp.message_handler(commands=['report'])
async def mass_report(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    if not request_level(cache['right'], 1, message.chat.id) or not cache['process']:
        return
    await send_report_example(message)

async def send_report_example(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    if cache['report']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['report'])
        cache['report'] = None
        
    code_example = translate[cache['lang']]['send_report_example'][2] + ":\n" \
        + snippet['code-block'].format(lang=cache['lang'], text=translate[cache['lang']]['send_report_example'][4]) + "\n\n"
    example = translate[cache['lang']]['send_report_example'][3] + ":\n" \
        + snippet['code'].format(text=translate[cache['lang']]['send_report_example'][5])
        
    warning = f"\n\n{translate[cache['lang']]['send_report_example'][1]}"
    text = f"{translate[cache['lang']]['send_report_example'][0]}\n\n"
    if cache['report']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['report'])
    key = InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton(text=translate[cache['lang']]['send_report_example'][6], callback_data='main_menu'))
    REPORT_MESS = await new_message(text=text + code_example + example + warning, chat_id=message.chat.id, keyboard=key)
    cache['report'] = REPORT_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    await set_cached_data(message.chat.id, cache) ##write

@dp.message_handler(lambda message: message.reply_to_message)
async def report(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id)

    if not cache.get('process'):
        text = translate[cache['lang']]['report'][0]
        if cache.get('error'):
            await try_to_delete(chat_id=message.chat.id, message_id=cache['error'])
        cache['error'] = (await send_error_message(message.chat.id, text, Exception('Process not completed'))).message_id
        await set_cached_data(message.chat.id, cache)
        return

    if message.reply_to_message.message_id != cache.get('report'):
        await reply_to_task(message)
        return

    if not request_level(cache['right'], 2, message.chat.id): # 2 - report
        return

    cache['process'] = False
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)

    urls = re.findall(r'\[(.+?)\]\[(.+?)\]', message.text, re.DOTALL)
    text_without_buttons = re.sub(r'\[(.+?)\]\[(.+?)\]', '', message.html_text).strip()

    transl = re.findall(r'<pre>```(\w+)\n(.*?)\n```<\/pre>|<pre><code class="language-(\w+)">(.*?)<\/code><\/pre>', text_without_buttons, re.DOTALL)
    if transl is None:
        transl = [('default',message.html_text,'','')]
    else:
        default = transl[0]
        default = ('default', default[1], default[2], default[3])
        transl.append(default)
    text_dict = {x[0] or x[2]: x[1] or x[3] for x in transl} if transl else {}

    keyboard = InlineKeyboardMarkup()
    for name, url in urls:
        keyboard.add(InlineKeyboardButton(text=name, url=url))
    
    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['update_report'][4], callback_data="stop_process"))
    await try_to_edit(chat_id=message.chat.id, message_id=cache['report'], text=message.html_text, keyboard=stop_button)

    await set_cached_data(message.chat.id, cache)
    await update_report(message.chat.id, text_dict, keyboard)




# General menus
async def send_welcome(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    inline_btn_generate = InlineKeyboardButton(translate[cache['lang']]['send_welcome'][0], callback_data='generate_menu')
    other_games = InlineKeyboardButton(text=translate[cache['lang']]['send_welcome'][15], callback_data='other_games')
    giveaways = InlineKeyboardButton(text=translate[cache['lang']]['send_welcome'][10], callback_data='giveaways')
    inline_tasks = InlineKeyboardButton(translate[cache['lang']]['send_welcome'][7], callback_data='generate_tasks')
    inline_report = InlineKeyboardButton(translate[cache['lang']]['send_welcome'][9], callback_data='report')
    inline_kb = InlineKeyboardMarkup().add(inline_btn_generate)
    debug = InlineKeyboardButton(text=translate[cache['lang']]['send_welcome'][16], callback_data='debug')
    inline_kb.add(other_games)
    inline_kb.add(inline_tasks)
    inline_kb.add(giveaways)
    if request_level(cache['right'], 3, message.chat.id): # 3 - report
        inline_kb.add(inline_report)
    if request_level(cache['right'], 9, message.chat.id): # 9 - debug
        inline_kb.add(debug)
    today_keys = await get_all_user_keys_24h(user_id=message.chat.id, pool=POOL)
    user_limit_keys, global_limit_keys = await get_key_limit(user=message.chat.id)
    cache = await get_cached_data(message.chat.id) ##cache
    
    refs = await get_all_refs(pool=POOL, user_id=message.chat.id)
    refs = len(refs) if refs else 0
    
    user_tasks = await check_completed_tasks(message.chat.id)
    all_tasks = await get_promotions(pool=POOL)
    delta = len(all_tasks) - len(user_tasks)
    
    lost_tries = global_limit_keys - user_limit_keys
    cheating = lost_tries < 0
    lost_tries = abs(lost_tries) if not cheating else 0
    
    def create_pseudo_file(content: str, filename: str = "keys.txt"):
        pseudo_file = BytesIO()
        pseudo_file.write(content.encode('utf-8'))
        pseudo_file.seek(0)
        pseudo_file.name = filename
        return pseudo_file

    if cache['welcome']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['welcome'])
    
    text1 =  snippet['bold'].format(text=translate[cache['lang']]['send_welcome'][1]) + "\n" + \
            translate[cache['lang']]['send_welcome'][11] + ":" +\
            snippet['code'].format(text=str(message.chat.id)) + "\n"
            
    text1 += translate[cache['lang']]['send_welcome'][2].replace('{message.chat.id}', str(message.chat.id)).replace('{bot_username}', BOT_INFO.username) + "\n" + \
            snippet['italic'].format(text=translate[cache['lang']]['send_welcome'][12]) + "\n\n" + \
            snippet['bold'].format(text=translate[cache['lang']]['send_welcome'][13] + ":") + "\n"
            
    if today_keys:
        today_keys = sorted(today_keys, key=lambda x: x[1], reverse=True)
        if cheating:
            text2 = '\n'.join([f'{snippet["bold"].format(text=type + ":")} {snippet["code"].format(text=key)} ({format_remaining_time(key_time, pref=cache["lang"])})' 
                               for key, key_time, type in today_keys[:-lost_tries]])
            
            text2 += '\n' + '\n'.join([f"{snippet['bold'].format(text=type + ':')} {snippet['code'].format(text=hide_key(key))} ({format_remaining_time(key_time, pref=cache['lang'])})" 
                               for key, key_time, type in today_keys[len(today_keys)-lost_tries:]])
            text2 += '\n' + translate[cache['lang']]['send_welcome'][8]
            
        else:
            text2 = '\n'.join([f'{snippet["bold"].format(text=type + ":")} {snippet["code"].format(text=key)} ({format_remaining_time(key_time, pref=cache["lang"])})' 
                               for key, key_time, type in today_keys])
    else:

        text2 = snippet['italic'].format(text=translate[cache['lang']]['send_welcome'][3])
        
    
    text3 = f'\n\n{snippet["bold"].format(text=translate[cache["lang"]]["send_welcome"][4])} {lost_tries}/{global_limit_keys} (+{refs}) (-{delta})'
    
    text3 += "\n\n" + snippet['italic'].format(text=translate[cache['lang']]['send_welcome'][5])
    
    text = text1 + text2 + text3
    
    if len(text) < 4096:
        WELCOME_MESS = await new_message(text=text, chat_id=message.chat.id, keyboard=inline_kb, disable_preview=False)
        cache['welcome'] = WELCOME_MESS.message_id
    else:
        keys = '\n'.join([f'{type}:\t{key}\t({format_remaining_time(key_time, pref=cache["lang"])})' for key, key_time, type in user_limit_keys])
        pseudo_file = create_pseudo_file(keys)
        text = text1 + f" {snippet['italic'].format(text=translate[cache['lang']]['send_welcome'][6])}" + text3
        WELCOME_MESS = await new_message(chat_id=message.chat.id, document=pseudo_file, text=text, keyboard=inline_kb)
        cache['welcome'] = WELCOME_MESS.message_id
        
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    await set_cached_data(message.chat.id, cache) ##write

@dp.callback_query_handler(lambda c: c.data == 'generate_menu')
async def process_callback_generate_menu(callback_query: types.CallbackQuery) -> None:
    message = callback_query.message
    cache = await get_cached_data(message.chat.id) ##cache
    user_limit_keys, global_limit_keys = await get_key_limit(user=message.chat.id)
    
    if cache['welcome']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['welcome'])
    
    text = snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_menu'][0] + ":") + "\n"
    text += f"\n{snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_menu'][1])} {global_limit_keys - user_limit_keys}/{global_limit_keys}\n\n"
    text += snippet['italic'].format(text=translate[cache['lang']]['process_callback_generate_menu'][2])

    keyboard = InlineKeyboardMarkup()
    def mark(game):
        return '✅ ' if not json_config['EVENTS'][game]['DISABLED'] else '❌ '
    # Создаем список кнопок из конфигурации
    buttons = [InlineKeyboardButton(text=mark(type) + json_config['EVENTS'][type]['NAME'], callback_data=f'generate_key_{type}') for type in json_config['EVENTS']]
    
    # Добавляем кнопки по две в строке
    for i in range(0, len(buttons), 2):
        keyboard.add(*buttons[i:i + 2])
    
    # Добавляем кнопку главного меню в отдельной строке
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_menu'][3], callback_data='main_menu'))

    WELCOME_MESS = await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard)
    cache['welcome'] = WELCOME_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    
    await set_cached_data(message.chat.id, cache) ##write


@dp.callback_query_handler(lambda c: c.data.startswith('generate_key_'))
async def process_callback_generate_key(callback_query: types.CallbackQuery) -> None:
    used, all = await get_key_limit(user=callback_query.message.chat.id)
    limit = all - used
    cache = await get_cached_data(callback_query.message.chat.id)
    text = snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_key'][0]) + \
           "\n\n" + snippet['italic'].format(text=translate[cache['lang']]['process_callback_generate_key'][1])
    keyboard = InlineKeyboardMarkup(row_width=4)
    butts = [InlineKeyboardButton(text=str(i+1), callback_data=f'countkey_{i+1}_{callback_query.data.split("_")[2]}') for i in range(min(4, limit))]
    keyboard.add(*butts)
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_key'][2], callback_data='generate_menu'))

    mess= await new_message(text=text, chat_id=callback_query.message.chat.id, keyboard=keyboard)
    if cache['welcome']:
        await try_to_delete(chat_id=callback_query.message.chat.id, message_id=cache['welcome'])
    cache['welcome'] = mess.message_id
    await set_cached_data(callback_query.message.chat.id, cache)

#keys funcs
@dp.callback_query_handler(lambda c: c.data.startswith('countkey_'))
async def generate_key(callback_query: types.CallbackQuery) -> None:
    message = callback_query.message
    cache = await get_cached_data(message.chat.id) ##cache
    try:
        await bot.answer_callback_query(callback_query.id)
    except InvalidQueryID:
        pass
    count = int(callback_query.data.split('_')[1])
    game_key = callback_query.data.split('_')[2]
    
    last_user_key = await get_last_user_key(message.chat.id, pool=POOL)
    user_limit_keys, global_limit_keys = await get_key_limit(user=message.chat.id)

    if cache['loading'] and cache['process']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['loading'])
        cache['loading'] = None

    def can_generate_key():
        return not last_user_key or abs(relative_time(last_user_key['time'])) > db_config['DELAY'] or json_config['DEBUG']

    if can_generate_key() and cache['process']:
        if user_limit_keys < global_limit_keys:
            mins = json_config['EVENTS'][game_key]['EVENTS_DELAY'][0] * 15 // 60000 // 2 * count
            stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['generate_key'][7], callback_data="main_menu"))
            LOADING_MESS = await new_message(text=translate[cache['lang']]['generate_key'][0].replace('{mins}', str(mins)), chat_id=message.chat.id, keyboard=stop_button)
            cache['loading'] = LOADING_MESS.message_id
            await set_cached_data(message.chat.id, cache) ##write
            try:
                async with aiohttp.ClientSession() as session:
                    # cache['process'] = False
                    key = await update_loadbar(message.chat.id, game_key, session, count)
                await try_to_edit(text=message.html_text, chat_id=message.chat.id, message_id=message.message_id, keyboard=stop_button)
                
                # await set_cached_data(message.chat.id, cache) ##write
                cache['process'] = True
                await try_to_delete(message.chat.id, cache['loading'])
                if key:
                    for k in key:
                        await insert_key_generation(message.chat.id, k, game_key, pool=POOL)
                key_text = '\n'.join([snippet['bold'].format(text=game_key) + ": " + snippet['code'].format(text=k) for k in key if k is not None]) \
                            if key and len(key) > 0 else translate[cache['lang']]['generate_key'][2]
                stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['generate_key'][7], callback_data="main_menu"))
                LOADING_MESS = await new_message(text=translate[cache['lang']]['generate_key'][3].replace('{key}', key_text), chat_id=message.chat.id, keyboard=stop_button)
                cache['loading'] = LOADING_MESS.message_id
                await set_cached_data(message.chat.id, cache) ##write
                cache['process'] = True
            except Exception as e:
                if cache['loading']:
                    await try_to_delete(message.chat.id, cache['loading'])
                LOADING_MESS = await send_error_message(message.chat.id, translate[cache['lang']]['generate_key'][2], e)
                cache['process'] = True
                cache['loading'] = LOADING_MESS.message_id
                await set_cached_data(message.chat.id, cache) ##write
        else:
            cache['process'] = True
            text = translate[cache['lang']]['generate_key'][4]
            if cache['loading']:
                await try_to_delete(chat_id=message.chat.id, message_id=cache['loading'])
            LOADING_MESS = await new_message(text=text, chat_id=message.chat.id)
            cache['loading'] = LOADING_MESS.message_id
            await set_cached_data(message.chat.id, cache) ##write
    elif not can_generate_key():
        text = translate[cache['lang']]['generate_key'][5].replace('{last_user_key}', snippet['code'].format(text=last_user_key['key'])).replace('{relative_time}', str(db_config['DELAY'] - relative_time(last_user_key['time'])))
        LOADING_MESS = await new_message(text=text, chat_id=message.chat.id)
        cache['loading'] = LOADING_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write
    elif not cache['process']:
        text = translate[cache['lang']]['generate_key'][6]
        ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
        cache['error'] = ERROR_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write
            
    await set_cached_data(message.chat.id, cache) ##write

async def get_key_limit(user: int, default:int=db_config['COUNT']):
    cache = await get_cached_data(user)

    today_keys = await get_all_user_keys_24h(user, pool=POOL) or []
    refs = len(await get_all_refs(pool=POOL, user_id=user)) or 0
    user_tasks, all_tasks = await get_tasks_limit(user)
    delta = len(all_tasks) - len(user_tasks)
    
    # Compute key limit based on refs
    if refs < 4:
        count = default + refs
    else:
        count = default + 4 + sum(refs // (2 ** i) % 2 ** i for i in range(1, refs.bit_length()))
    
    user_limit_keys = len(today_keys)
    completed = cache.get('tasks', 0) or 0

    # Handle task completion error
    if len(user_tasks) < completed:
        num_str = str(completed - len(user_tasks))
        # if cache.get('error'):
        #     await try_to_delete(user, cache['error'])
        ERROR_MES = await send_error_message(user, translate[cache.get('lang', 'en')]['get_key_limit'][0] + ": " + snippet['bold'].format(text=num_str))
        cache.update({'tasks': len(user_tasks), 'error': ERROR_MES.message_id})
    
    await set_cached_data(user, cache, pool=POOL)
    return user_limit_keys, count - delta





# Tasks funcs
async def check_completed_tasks(user_id:int):
    global POOL
    promos = await get_promotions(pool=POOL)
    used = await get_checker_by_user_id(user_id, pool=POOL)
    count = {}
    for promo in promos:
        if promos[promo]['control'] == 1:
            try:
                checker = await bot.get_chat_member(chat_id=promos[promo]['check_id'], user_id=user_id)
                if checker.status != 'left':
                    count[promo] = promos[promo]
            except ChatNotFound:
                if promos[promo]['check_id'] == BOT_INFO.id:
                    logger.warning(f"Promotion channel for task \"{promos[promo]['name']}\" ({promos[promo]['check_id']}) not found")
            except BadRequest as e:
                if e.args[0] == 'Member list is inaccessible':
                    logger.warning(f"Error with task \"{promos[promo]['name']}\" ({promos[promo]['check_id']}): {e.args[0]}, task check removed")
                    await send_error_message(chat_id=user_id, message=f"Error with task \"{promos[promo]['name']}\" ({promos[promo]['check_id']})", only_dev=True)
                    await insert_task(promos[promo], 0)
                else:
                    logger.warning(f"Error with task \"{promos[promo]['name']}\" ({promos[promo]['check_id']}) not found")
        elif promos[promo]['control'] == 0:
            if int(promo) in used:
                count[promo] = promos[promo]
    return count

async def get_tasks_limit(user: int):
    user_tasks = await check_completed_tasks(user)
    all_tasks = await get_promotions(pool=POOL)

    valid_tasks = {}

    for promo_id, promo in all_tasks.items():
        promo_id = str(promo_id)
        
        if promo['control'] == 1:
            try:
                checker = await bot.get_chat(chat_id=promo['check_id'])
                if checker and checker.id == promo['check_id']:
                    valid_tasks[promo_id] = promo
            except ChatNotFound:
                if promo['check_id'] == BOT_INFO.id:
                    logger.warning(f"Promotion chat for task \"{promo['name']}\" ({promo['check_id']}) not found, task removed")
                    await delete_task_by_id(promo['id'], pool=POOL)
                    await send_error_message(user, f"Promotion chat for task \"{promo['name']}\" ({promo['check_id']}) not found, task removed", only_dev=True)
        elif promo['control'] == 0:
            valid_tasks[promo_id] = promo

    user_tasks = {str(task_id): valid_tasks[task_id] for task_id in user_tasks if task_id in valid_tasks}
    
    return user_tasks, valid_tasks

@dp.callback_query_handler(lambda c: c.data == 'generate_tasks')
async def process_callback_generate_tasks(callback_query: types.CallbackQuery) -> None:
    message = callback_query.message
    cache = await get_cached_data(message.chat.id) ##cache
    await get_key_limit(user=message.chat.id)
    used, all = await get_tasks_limit(user=message.chat.id)
    
    if cache['welcome']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['welcome'])
    
    text = snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_tasks'][0])
    text += f"\n{snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_tasks'][1])} {len(used)}/{len(all)}"
    text += "\n\n" + snippet['italic'].format(text=translate[cache['lang']]['process_callback_generate_tasks'][2])

    keyboard = InlineKeyboardMarkup()
    for task in all:
        mark = '✅ ' if str(task) in used else ''
        inline_btn = InlineKeyboardButton(text=mark + all[task]['name'], callback_data=f'generate_task_{task}')
        keyboard.add(inline_btn)
        
    if request_level(cache['right'], 4, message.chat.id): # 4 - add_task
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_tasks'][5], callback_data='delete_task'),
                     InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_tasks'][4], callback_data='add_task'))
    else:
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_tasks'][4], callback_data='add_task'))
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_tasks'][3], callback_data='main_menu'))


    WELCOME_MESS = await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard)
    cache['welcome'] = WELCOME_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    
    await set_cached_data(message.chat.id, cache) ##write
    
@dp.callback_query_handler(lambda c: c.data.startswith('generate_task_'))
async def generate_task_message(callback_query: types.CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    task_id = str(callback_query.data.replace('generate_task_', ''))
    
    # Получаем данные из кэша и проверяем задания
    cache = await get_cached_data(user_id)
    used, all_tasks = await get_tasks_limit(user=user_id)
    current_task = all_tasks.get(task_id)
    message = callback_query.message

    if not current_task:
        await send_error_message(message.chat.id, translate[cache['lang']]['generate_task_message'][6], only_dev=True)
        return
    
    # Проверяем членство пользователя в чате
    try:
        if current_task['control'] == 1:
            checker = await bot.get_chat_member(chat_id=current_task['check_id'], user_id=user_id)
            is_task_completed = checker and checker.status != 'left'
    except (ChatNotFound):
        if current_task['control'] != 0:
            current_task['control'] = 0
            error_key = 7 
            await send_error_message(
                message.chat.id, 
                translate[cache['lang']]['generate_task_message'][error_key]
                .replace('{num}', str(current_task['check_id']))
                .replace('{task}', current_task['name']), 
                only_dev=True
            )
            await delete_task_by_id(int(current_task['id']), pool=POOL)
            is_task_completed = False
    except (BadRequest):
        if current_task['control'] != 0:
            current_task['control'] = 0
            error_key = 6 
            await send_error_message(
                message.chat.id, 
                translate[cache['lang']]['generate_task_message'][error_key]
                .replace('{num}', str(current_task['check_id']))
                .replace('{task}', current_task['name']), 
                only_dev=True
            )
            await insert_task(current_task, check=0, pool=POOL)
            is_task_completed = False
    except (Exception) as e:
        await send_error_message(message.chat.id, 'Error occured: ' + str(e), only_dev=True)

    # Проверяем выполненные задания
    promo_ids = await get_checker_by_user_id(user_id=user_id)
    is_task_completed = is_task_completed or (int(task_id) in promo_ids and current_task['control'] == 0)

    # Формируем текст и кнопки для сообщения
    mark = '✅ ' if is_task_completed else ''
    foot = translate[cache['lang']]['generate_task_message'][3 if is_task_completed else 0]
    text = f"{mark}{snippet['bold'].format(text=current_task['name'])}\n\n{current_task['desc']}\n\n{snippet['italic'].format(text=foot)}"

    but_text = translate[cache['lang']]['generate_task_message'][4 if is_task_completed else 1]
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text=but_text, callback_data=f'check_task_{task_id}'),
        InlineKeyboardButton(text=translate[cache['lang']]['generate_task_message'][5], url=current_task['link']),
        InlineKeyboardButton(text=translate[cache['lang']]['generate_task_message'][2], callback_data='generate_tasks')
    )
    
    # Удаляем старое сообщение и отправляем новое
    if cache.get('welcome'):
        await try_to_delete(chat_id=message.chat.id, message_id=cache['welcome'])
    
    welcome_message = await new_message(chat_id=message.chat.id, text=text, keyboard=keyboard)
    
    # Обновляем кэш
    cache['welcome'] = welcome_message.message_id
    await set_cached_data(user_id, cache)

@dp.callback_query_handler(lambda c: c.data.startswith('check_task_'))
async def check_task_message(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.from_user.id) ##cache
    message = callback_query.message
    
    used, all_tasks = await get_tasks_limit(user=callback_query.from_user.id)
    task_id = str(callback_query.data.replace('check_task_', ''))
    promo = all_tasks[task_id]
    checker = None
    
    if str(task_id) in used:
        await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['check_task_message'][0])
    
    success = False
    
    if promo['control'] == 1 and str(task_id) not in used:
        try:
            checker = await bot.get_chat_member(chat_id=promo['check_id'], user_id=message.chat.id)
            if checker and checker.status != 'left':
                await append_checker(user_id=message.chat.id, promo_id=int(task_id))
                success = True
        except ChatNotFound as e:
            if all_tasks[task_id]['check_id'] != BOT_INFO.id:
                war_text = f"Promotion chat for task \"{all_tasks[task_id]['name']}\" ({snippet['code'].format(text=all_tasks[task_id]['check_id'])}) not found, task removed"
                logger.warning(war_text)
                await send_error_message(message.chat.id, war_text, e=e, only_dev=True)
                await delete_task_by_id(task_id, pool=POOL)
                all_tasks.pop(task_id)
            else:
                await append_checker(user_id=message.chat.id, promo_id=int(task_id))
                await insert_task(task=all_tasks[task_id], check=0, pool=POOL)
                war_text = f"Promotion chat for task \"{all_tasks[task_id]['name']}\" ({snippet['code'].format(text=all_tasks[task_id]['check_id'])}) not found, task still without checking"
                logger.warning(war_text)
                all_tasks[task_id]['control'] = 0
                await send_error_message(message.chat.id, war_text, e=e, only_dev=True)
                success = True
    
    elif promo['control'] == 0:
        await append_checker(user_id=message.chat.id, promo_id=int(task_id))
        success = True
    
    promo_ids = await get_checker_by_user_id(user_id=message.chat.id)
    if cache['welcome'] and success:
        but_text = translate[cache['lang']]['generate_task_message'][4] if checker and checker.status != 'left' and promo['control'] == 1 or int(task_id) in promo_ids and promo['control'] == 0 \
                    else translate[cache['lang']]['generate_task_message'][1]
        keyboard = InlineKeyboardMarkup()
        inline_btn = InlineKeyboardButton(text=but_text, callback_data=f'check_task_{callback_query.data.replace("generate_task_", "")}')
        inline_btn2 = InlineKeyboardButton(text=translate[cache['lang']]['generate_task_message'][2], callback_data='generate_tasks')
        in_but = InlineKeyboardButton(text=translate[cache['lang']]['generate_task_message'][5], url=promo['link'])
        keyboard.add(inline_btn,in_but)
        keyboard.add(inline_btn2)
        await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=cache['welcome'], reply_markup=keyboard)
    
    await set_cached_data(message.chat.id, cache) ##write

@dp.callback_query_handler(lambda c: c.data == 'add_task')
async def add_task_message(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.from_user.id) ##cache
    if not request_level(cache['right'], 4, callback_query.from_user.id): # 4 - add_task
        text = snippet['bold'].format(text=translate[cache['lang']]['add_task_message'][0])
        channel = await bot.get_chat(chat_id=db_config["MAIN_CHANNEL"])
        key = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['add_task_message'][1], url=await channel.get_url()))
        key.add(InlineKeyboardButton(translate[cache['lang']]['add_task_message'][2], callback_data='generate_tasks'))
        if cache['welcome']:
            await try_to_delete(chat_id=callback_query.from_user.id, message_id=cache['welcome'])
        WELCOME_MESS = await new_message(text=text, chat_id=callback_query.from_user.id, keyboard=key)
        cache['welcome'] = WELCOME_MESS.message_id
        await set_cached_data(callback_query.from_user.id, cache) ##write
    else:
        await send_task_example(callback_query.message)

@dp.message_handler(commands=['add_task'])
async def send_task_example(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    if request_level(cache['right'], 2, message.chat.id): # 2 - report
        if not cache['process']:
            text = translate[cache['lang']]['send_task_example'][8] 
            if cache['error']:
                await try_to_delete(chat_id=message.chat.id, message_id=cache['error'])
            ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
            cache['error'] = ERROR_MESS.message_id
            await set_cached_data(message.chat.id, cache) ##write
            return
        text = '\n'.join([snippet['bold'].format(text=translate[cache['lang']]['send_task_example'][0]),
                          snippet['code-block'].format(text=translate[cache['lang']]['send_task_example'][1], lang=cache['lang']),
                          snippet['italic'].format(text=translate[cache['lang']]['send_task_example'][2])]) + "\n\n" +\
                            translate[cache['lang']]['send_task_example'][6] + "\n"+\
                            snippet['bold'].format(text=translate[cache['lang']]['send_task_example'][7].replace("{bot}", BOT_INFO.username))
                            
        if cache['addtask']:
            await try_to_delete(chat_id=message.chat.id, message_id=cache['addtask'])
        key = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['add_task_message'][2], callback_data='main_menu'))
        ADDTASK_MESS = await new_message(chat_id=message.chat.id, text=text, keyboard=key)
        cache['addtask'] = ADDTASK_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write

@dp.message_handler(lambda message: message.reply_to_message)
async def reply_to_task(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id)
    
    if message.reply_to_message.message_id != cache['addtask'] or not cache['process'] \
        or not request_level(cache['right'], 4, message.chat.id): # 4 - add_task
        return
    control = 1
    transl_task = re.findall(r'<pre>```(\w+)\n(.*?)\n```<\/pre>|<pre><code class="language-(\w+)">(.*?)<\/code><\/pre>', message.html_text, re.DOTALL)

    if not transl_task:
        await send_error_message(message.chat.id, translate[cache['lang']]['send_task_example'][3])
        return
    
    first = True
    dict_task = {}
    for lang, content1, _, __ in transl_task:
        lang = lang or _
        content = content1 or __
        task_match = re.findall(r'\[(.+?)\]\[(.+?)\]', content, re.DOTALL)
        namespaces = [task_match[i][0].lower() for i in range(len(task_match))]
        if 'name' not in namespaces or 'desc' not in namespaces or ('link' not in namespaces and 'id' not in namespaces):
            await send_error_message(message.chat.id, translate[cache['lang']]['send_task_example'][3])
            await try_to_delete(message.chat.id, message.message_id)
            return
        if task_match:
            dict_task[lang] = {t[0].lower(): t[1] for t in task_match}
            slash_sep = dict_task[lang]['link'].split('/') if 'link' in dict_task[lang] else dict_task[lang]['id']
            what_to_check = dict_task[lang]['id'] if 'id' in dict_task[lang] else dict_task[lang]['check_id'] if 'check_id' in dict_task[lang] \
                else slash_sep[3] if 'link' in dict_task[lang] and len(slash_sep) > 3 and any(x not in dict_task[lang]['link'] for x in ['/+', 'joinchat']) and username_valid(slash_sep[3]) \
                else dict_task[lang]['link'] if 'link' in dict_task[lang] and dict_task[lang]['link'].startswith('@') and username_valid(dict_task[lang]['link'][1:]) \
                else None
            
            if what_to_check:
                try:
                    checker = await bot.get_chat(what_to_check)
                    dict_task[lang]['check_id'] = checker.id
                    if not checker.invite_link and checker.permissions.can_invite_users:
                        await checker.create_invite_link()
                    elif not checker.invite_link:
                        raise Exception(f'No invite link, recheck permissions of bot in chat {checker.mention} ({checker.id})')
                    else:    
                        dict_task[lang]['link'] = checker.invite_link or 'https://t.me/' + checker.username
                        if not dict_task[lang]['link'].startswith('https://t.me/'):
                            logger.warning(f"Not invite link ({dict_task[lang]['link']}) for chat ({what_to_check})")
                except ChatNotFound:
                    logger.warning(f"Chat ({what_to_check}) not found")
                    control = 0
                    dict_task[lang]['check_id'] = BOT_INFO.id
                except Exception as e:
                    await send_error_message(message.chat.id, translate[cache['lang']]['send_task_example'][3] + f"\nError: {str(e)}", e)
                    await try_to_delete(message.chat.id, message.message_id)
                    return
            else:
                if 'link' not in dict_task[lang]:
                    await send_error_message(message.chat.id, translate[cache['lang']]['send_task_example'][3] + f"\nError: {translate[cache['lang']]['send_task_example'][9]}", Exception(translate[cache['lang']]['send_task_example'][9]))
                    await try_to_delete(message.chat.id, message.message_id)
                    return
                control = 0
                
            
                
            if first:
                for key in dict_task[lang]:
                    dict_task[key] = dict_task[lang][key]
                first = False

    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['reply_to_task'][0], callback_data='main_menu'))

    dict_task['day'] = int(dict_task['day']) if 'day' in dict_task else 99999
    # Вызов новой функции для вставки задачи и обновления JSON
    dict_task['id'] = await insert_task(dict_task, check=control, expire=now()+dict_task['day']*86400, pool=POOL)  # передайте pool, который используется в insert_task_by_id
    if not dict_task['id']:
        await send_error_message(message.chat.id, translate[cache['lang']]['send_task_example'][3])
        return
    
    await try_to_delete(message.chat.id, message.message_id)
    addm = await new_message(chat_id=message.chat.id, text=translate[cache['lang']]['send_task_example'][4], keyboard=keyboard)
    cache['addtask'] = addm.message_id
    await set_cached_data(message.chat.id, cache)

@dp.message_handler(commands=['delete_task'])
async def delete_task_message(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    if not cache['process']:
        return
    
    if not request_level(cache['right'], 5, message.chat.id): # 5 - delete_task
        return
    
    text = translate[cache['lang']]['delete_task'][0]
    keyboard = InlineKeyboardMarkup()
    tasks = await get_promotions(pool=POOL)
    for task in tasks:
        keyboard.add(InlineKeyboardButton(text=tasks[task]['name'], callback_data=f'delete_task_{tasks[task]["id"]}')) 
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['delete_task_message'][0], callback_data='main_menu'))
    await new_message(chat_id=message.chat.id, text=text, keyboard=keyboard)
 
@dp.callback_query_handler(lambda c: c.data == 'delete_task')
async def delete_task_callback(callback_query: types.CallbackQuery) -> None:
    await delete_task_message(callback_query.message)
 
@dp.callback_query_handler(lambda c: c.data.startswith('delete_task_'))
async def process_callback_delete_task(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    if not cache['process']:
        return
    
    if not request_level(cache['right'], 5, callback_query.message.chat.id): # 5 - delete_task
        return
    
    task_id = callback_query.data.split('_')[2]
    await delete_task_by_id(int(task_id), pool=POOL)
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_delete_task'][2], callback_data='main_menu'))
    await new_message(chat_id=callback_query.message.chat.id, 
                           text=translate[cache['lang']]['process_callback_delete_task'][0].replace('{name}', "id "+ task_id),
                           keyboard=keyboard)
    await try_to_delete(callback_query.message.chat.id, callback_query.message.message_id)




# Giveaway funcs
@dp.callback_query_handler(lambda c: c.data == 'giveaways')
async def generate_giveaways_menu(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    
    giveaways = get_promotions(pool=POOL, task_type='giveaway')
    
    
    await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['generate_giveaways_menu'][0])
    
@dp.callback_query_handler(lambda c: c.data.startswith('giveaway_'))
async def process_callback_giveaway(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_giveaway'][1])







# Other games funcs
@dp.callback_query_handler(lambda c: c.data == 'other_games')
async def process_callback_other_games(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_other_games'][0])



#debug
async def get_chat_members(chat_id):
    members = []
    try:
        async for member in bot.iter_chat_members(chat_id):
            member_info = f"ID: {member.user.id}, Name: {member.user.full_name}, Mention: {member.user.mention}"
            members.append(member_info)
    except Exception as e:
        logger.error(e)
    return members

async def get_user_info(user_id):
    try:
        chat_member = await bot.get_chat_member(user_id, user_id)
        user = chat_member.user
        return f"ID: {user.id}, Name: {user.first_name} {user.last_name}, Mention: {user.mention}"
    except Exception as e:
        logger.error(e)
        return f"ID: {user_id}, (Undefined for some reason: {e})"

async def get_chat_permissions(chat):
    try:
        if not chat.permissions:
            return {}

        permissions = dict(chat.permissions)
        return {k.split('can_')[1].replace('_', ' ').capitalize() : v for k,v in permissions.items()}

    except Exception as e:
        logger.error(f"Error getting chat permissions: {e}")
        return {}


async def get_chat_info(id):
    try:
        chat = await bot.get_chat(id)
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        invite_link = chat.invite_link or await bot.export_chat_invite_link(chat.id)
        permissions = await get_chat_permissions(chat)

        chat_info = (
            f"Name: {chat.title} ({chat.id}), Type: {chat.type}\n"
            f"\tChat rights: {bot_member.status}\n"
            f"\tPublic Link: https://t.me/{chat.username}\n"
            f"\tInvite Link: {invite_link}\n"
            f"\tPermissions:\n" +
            "".join(f"\t\t{perm}: {value}\n" for perm, value in permissions.items())
        )
        return chat_info + "\n"
    except Exception as e:
        logger.error(e)
        chat_info = f"Name: --- ({id}), Type: (Undefined for some reason: {e})\n\n"
        return chat_info

async def save_to_file(file_path, content):
    async with aiofiles.open(file_path, "w") as file:
        await file.write(content)

async def delete_file(file_path):
    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass

@dp.callback_query_handler(lambda c: c.data == 'debug')
async def send_files(callback_query: types.CallbackQuery):
    chat = callback_query.message.chat
    cache = await get_cached_data(chat.id)
    semaphore = asyncio.Semaphore(25)
    if not cache['process']:
        return
    cache['process'] = False
    if not request_level(cache['right'], 9, chat.id):  # 9 - debug level
        return
    
    if cache['loading']:
        await try_to_delete(chat_id=chat.id, message_id=cache['loading'])
    
    loading_message = await new_message("Starting debug", chat.id)
    cache['loading'] = loading_message.message_id
    await set_cached_data(chat.id, cache)

    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text="🛑 Stop process", callback_data="stop_process"))

    users = await get_all_user_ids(pool=POOL)
    promo = await get_promotions(pool=POOL)
    chat_ids = set(promo[x]['check_id'] for x in promo) | set(promo[x].get('chat_id') for x in promo if 'chat_id' in x and promo[x].get('chat_id'))

    user_tasks = []
    chat_tasks = []
    
    async def bounded_get_user_info(user):
        async with semaphore:
            return await get_user_info(user)
    
    async def bounded_get_chat_info(chat_id):
        async with semaphore:
            return await get_chat_info(chat_id)

    for user in users:
        user_tasks.append(asyncio.create_task(bounded_get_user_info(user)))
    for chat_id in chat_ids:
        chat_tasks.append(asyncio.create_task(bounded_get_chat_info(chat_id)))

    while any(not task.done() for task in user_tasks + chat_tasks):
        cache = await get_cached_data(chat.id)
        if cache['process']:
            for task in user_tasks + chat_tasks:
                task.cancel()
            break
        loading_text = (
            f"M: {generate_loading_bar(sum(task.done() for task in user_tasks), 15, len(user_tasks))}\n"
            f"C: {generate_loading_bar(sum(task.done() for task in chat_tasks), 15, len(chat_tasks))}"
        )
        await try_to_edit(text=loading_text, chat_id=chat.id, message_id=cache['loading'], keyboard=stop_button)
        await asyncio.sleep(2)
    
    if cache['process']:
        return
        
    cache['process'] = True
    await try_to_delete(chat_id=chat.id, message_id=cache['loading'])
    cache['loading'] = None

    members_list = "\n".join(task.result() for task in user_tasks if task.result())
    chats_list = "\n".join(task.result() for task in chat_tasks if task.result())

    users_file_path = "logs/users_list.txt"
    chats_file_path = "logs/chats_list.txt"
    
    await asyncio.gather(
        save_to_file(users_file_path, members_list),
        save_to_file(chats_file_path, chats_list)
    )
    
    empty = [False, False]

    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text="Close message", callback_data="close"))

    if os.path.getsize(users_file_path) > 0:
        await callback_query.message.reply_document(
            document=types.InputFile(users_file_path),
            caption="List of users",
            reply_markup=stop_button
        )
    else:
        empty[0] = True

    if os.path.getsize(chats_file_path) > 0:
        await callback_query.message.reply_document(
            document=types.InputFile(chats_file_path),
            caption="List of chats",
            reply_markup=stop_button
        )
    else:
        empty[1] = True
        
    if empty[0] or empty[1]:
        text = "The lists are empty: " + ', '.join([users_file_path if empty[0] else "", chats_file_path if empty[1] else ""])
        ERR = await send_error_message(chat.id, text)
        cache['error'] = ERR.message_id

    await asyncio.gather(
        delete_file(users_file_path),
        delete_file(chats_file_path)
    )








async def on_startup(dp):
    global POOL, BOT_INFO
    POOL = await get_pool()  # Создание пула
    logger.info('DB pool created...')

    # Получение информации о боте
    BOT_INFO = await bot.get_me()
    logger.info('Telegram bot created... ID: %s, username: @%s', BOT_INFO.id, BOT_INFO.username)

    # Обновление кэша пользователей
    users_id = await update_cache_process(POOL)
    logger.info('Free all proxies from work...')

    # Обновление статуса прокси
    await update_proxy_work(POOL)
    logger.info("Send warning message to everyone who tried to generate key before....")

    # Запуск майнинга в отдельном потоке, если включено в конфигурации
    # if json_config['MINING']:
    #     asyncio.create_task(mining(POOL))

    # Подготовка сообщения для разработчика
    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text="Main menu", callback_data="close"))
    text = {
        "ru": "Бот перезапущен, пожалуйста, сгенеруйте ключ заново (/start)", 
        "en": "Bot now restarted, please generate key again (/start)"
    }
    await update_report(db_config['DEV_ID'], text, stop_button, users_id, True)
    logger.info('Sucessfull report! Bot pooling now...')




if __name__ == '__main__':
    # Запуск бота и ожидание завершения его работы
    # asyncio.get_event_loop().set_debug(True)
    while True:
        try:
            logger.info("Telegram bot started...")
            executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
        except Exception as e:
            error_text = " ".join(e.args) if e.args and len(e.args)!=0 else e.match if e.match else str(e)
            logger.error(f'Error: {error_text}, retry in 30 seconds...')
            time.sleep(30)
