import asyncio
import aiohttp
import json
import re
import random
from io import BytesIO

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from aiogram.utils.exceptions import (MessageNotModified, MessageToDeleteNotFound, InvalidQueryID, ChatNotFound,
                                      BotBlocked, MessageIsTooLong, MessageToEditNotFound, MessageCantBeDeleted,
                                      BadRequest)

from generate import generate_loading_bar, get_key, logger
from database import (insert_key_generation, get_last_user_key, get_all_dev, get_all_user_ids, now, get_promotions,
                      get_unused_key_of_type, relative_time, get_all_user_keys_24h, insert_user, format_remaining_time, 
                      delete_user, get_pool, get_all_refs, get_user, get_cached_data as get_cached, write_cached_data, 
                      update_cache_process, insert_task, get_checker_by_user_id, append_checker, 
                      delete_task_by_id as delete_task)

# Load configuration
with open('config.json') as f:
    json_config = json.load(f)
with open('localization.json') as f:
    translate = json.load(f)
with open('tasks.json') as f:
    transl = json.load(f)

API_TOKEN = json_config['API_TOKEN']
DELAY = json_config['DELAY']
DEBUG_KEY = json_config['DEBUG_KEY']
DEBUG = json_config['DEBUG']
POOL = None

# f"https://t.me/{bot_info.username}?startgroup=true&admin=post_messages+edit_messages+delete_messages+invite_users"

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
sem = asyncio.Semaphore(25)

#Cache funcs
async def set_cached_data(user:int, data:dict, pool=POOL):
    data_copy = data.copy()
    
    data_copy.pop('lang', None)
    data_copy.pop('id', None)
    data_copy.pop('right', None)
    
    await write_cached_data(user, data_copy, pool=pool) 

async def get_cached_data(user_id:int) -> tuple:
    user = await get_user(user_id, pool=POOL)
    cache_default = {'user_id':0, 'welcome':0, 'loading':0, 'report':0, 'process':True, 'error':0, 'tasks': 0, 'lang': 'en'}
    if not user:
        cache_default['user_id'] = user_id
        await set_cached_data(user_id, cache_default)
    config = await get_cached(user_id, pool=POOL)
    config = config if config is not None else cache_default
    
    config['process'] = config['process'] if config['process'] else True
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



#loadbars
async def update_loadbar(chat_id:int, game_key:str) -> None:
    cache = await get_cached_data(chat_id) ##cache
    
    if DEBUG:
        sec = json_config['DEBUG_DELAY'][1] // 1000
    else:
        sec = json_config['EVENTS'][game_key]['EVENTS_DELAY'][1] * 15 // 1000 // 2
    loading = 0
    cache['process'] = False
    await set_cached_data(chat_id, cache) ##write
    while not cache['process']:
        text = generate_loading_bar(progress=loading, max=sec)
        
        time = translate[cache['lang']]['generate_key'][0].replace('{mins}', format_remaining_time(now() + sec))
        plus_text = translate[cache['lang']]['generate_key'][7].replace('{key}', game_key) if loading > sec else ''
        full = time + '\n\n' + text + '\n' + plus_text
        try:
            await try_to_edit(full, chat_id, cache['loading'])
        except MessageNotModified:
            pass
        loading += 1000 + random.randint(0, 100)
        await asyncio.sleep(1)
        cache = await get_cached_data(chat_id) ##cache
    cache['process'] = True
    loading = sec
    text = generate_loading_bar(progress=loading, max=sec)
    full = time + '\n\n' + text
    await try_to_edit(full, chat_id, cache['loading'])
    await set_cached_data(chat_id, cache) ##write

async def update_report(chat_id: int, 
                        text: str | dict, 
                        keyboard: InlineKeyboardMarkup = None, 
                        users = None, 
                        warning = False, 
                        max_concurrent_tasks: int = 10) -> None:
    
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
        async with semaphore:
            try:
                if isinstance(text, dict):
                    if cache['lang'] in text.keys():
                        await send_message_to_user(user_id, text[cache['lang']], keyboard)
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
        
        time_text = translate[cache['lang']]['update_report'][0].replace('{mins}', str(max))
        full_report_text = time_text + f'\n{loading}/{max}' + '\n\n' + progress_text
        
        try:
            await try_to_edit(full_report_text, chat_id, cache['report'])
        except MessageNotModified:
            logger.error(f'Message for report in chat {chat_id} not modified')
        
        await asyncio.sleep(1)

    cache['process'] = True
    await set_cached_data(chat_id, cache)  # Снова записываем изменения в кэш

    # Дожидаемся завершения всех задач
    await asyncio.gather(*tasks)



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
    
async def try_to_edit(text:str, chat_id:int, message_id:int) -> bool:
    if message_id is None or message_id == 0:
        logger.debug('Message ID is None to edit in chat ' + str(chat_id))
        return False
    try:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode=ParseMode.HTML)
        return True
    except MessageToEditNotFound:
        return False
    
async def send_error_message(chat_id:int, message:str, e = Exception('')) -> types.Message:
    cache = await get_cached_data(chat_id) ##cache
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['process_callback_generate_tasks'][3], callback_data='main_menu'))
    cache['process'] = True
    if cache['error']:
        await try_to_delete(chat_id, cache['error'])
    logger.error(f'Error generating key! Error: {e.with_traceback(e.__traceback__)}')
    ERROR_MESS = await bot.send_message(text=html_back_escape(message), chat_id=chat_id, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=keyboard)
    cache['error'] = ERROR_MESS.message_id
    await set_cached_data(chat_id, cache) ##write
    return ERROR_MESS
    
async def new_message(message: str, chat_id: int) -> types.Message:
    try:
        return await bot.send_message(text=html_back_escape(message), chat_id=chat_id, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except BotBlocked:
        logger.warning("Bot was blocked by user ({user_id})".format(user_id=chat_id))
        
async def send_message_to_user(user_id:int, text: str, keyboard: InlineKeyboardMarkup) -> None:
    bot_info = await bot.get_me()
    if user_id == bot_info.id:
        return
    cache = await get_cached_data(user_id) ##cache
    try:
        await bot.send_message(chat_id=user_id, text=html_back_escape(text), parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=keyboard)
    except ChatNotFound:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][0].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
    except BotBlocked:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][1].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
    await set_cached_data(user_id, cache) ##write



#user setup
@dp.callback_query_handler(lambda c: c.data == 'main_menu')
async def process_callback_main_menu(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    if cache['error']:
        await try_to_delete(callback_query.message.chat.id, cache['error'])
        cache['error'] = None
    await set_cached_data(callback_query.message.chat.id, cache) ##write
    await send_welcome(callback_query.message)

@dp.message_handler(commands=['start'])
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
        WELCOME_MESS = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        cache['welcome'] = WELCOME_MESS.message_id
    else:
        await send_welcome(message)
        await insert_user(message.chat.id, message.from_user.username, ref=user['ref'], lang=cache['lang'],  pool=POOL)
    await asyncio.sleep(1) ##delay1
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
@dp.message_handler(commands=['report'])
async def mass_report(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    devs = await get_all_dev(pool=POOL, level=2)
    if devs is None or message.chat.id not in devs or not cache['process']:
        return
    await send_report_example(message)

async def send_report_example(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    if cache['report']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['report'])
        cache['report'] = None
    code_example = translate[cache['lang']]['send_report_example'][2]
    example = translate[cache['lang']]['send_report_example'][3]
    warning = f"\n\n{translate[cache['lang']]['send_report_example'][1]}"
    text = f"{translate[cache['lang']]['send_report_example'][0]}\n\n"
    if cache['report']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['report'])
    REPORT_MESS = await new_message(text + code_example + example + warning, message.chat.id)
    cache['report'] = REPORT_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    await set_cached_data(message.chat.id, cache) ##write

@dp.message_handler(lambda message: message.reply_to_message)
async def report(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id)
    
    if not cache['process']:
        text = translate[cache['lang']]['generate_key'][6] 
        if cache['error']:
            await try_to_delete(chat_id=message.chat.id, message_id=cache['error'])
        ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
        cache['error'] = ERROR_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write

    # Проверяем, является ли ответом на нужное сообщение и завершен ли процесс
    if message.reply_to_message.message_id != cache['report'] or not cache['process']:
        await reply_to_task(message)
        return

    # Получаем список разработчиков
    devs = await get_all_dev(pool=POOL, level=2)
    if message.chat.id not in devs:
        return

    # Устанавливаем процесс как незавершенный
    cache['process'] = False
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)

    # Создаем клавиатуру и извлекаем URL и текст без кнопок
    keyboard = InlineKeyboardMarkup()
    urls = re.findall(r'\[(.+?)\]\[(.+?)\]', message.text)
    text_without_buttons = re.sub(r'\[(.+?)\]\[(.+?)\]', '', message.html_text).strip()
    # Регулярное выражение для извлечения текста на разных языках
    pattern = re.compile(r'<pre>```(\w+)\n(.*?)\n```</pre>', re.DOTALL)
    transl = pattern.findall(text_without_buttons)
    if not transl:
        pattern = re.compile(r'<pre><code class=\\"language-(\w+)\\">(.*?)<\/code><\/pre>', re.DOTALL)
        transl = pattern.findall(text_without_buttons)

    # Обработка `transl`
    if transl:
        text_without_buttons = {}  # Перезаписываем text_without_buttons как словарь
        first = True
        for x in transl:
            if first:
                text_without_buttons['default'] = x[1]
                first = False
            text_without_buttons[x[0]] = x[1]

    # Добавление кнопок, если есть URL
    if urls:
        for url_name, url in urls:
            button = InlineKeyboardButton(text=url_name, url=url)
            keyboard.add(button)

    # Сохранение обновленных данных в кэш
    await set_cached_data(message.chat.id, cache)

    # Обновление отчета
    await update_report(message.chat.id, text_without_buttons, keyboard)



# General menus
async def send_welcome(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    inline_btn_generate = InlineKeyboardButton(translate[cache['lang']]['update_welcome_message'][0], callback_data='generate_menu')
    other_games = InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_tasks'][4], callback_data='other_games')
    inline_tasks = InlineKeyboardButton(translate[cache['lang']]['update_welcome_message'][7], callback_data='generate_tasks')
    inline_kb = InlineKeyboardMarkup().add(inline_btn_generate)
    inline_kb.add(other_games)
    inline_kb.add(inline_tasks)
    today_keys = await get_all_user_keys_24h(user_id=message.chat.id, pool=POOL)
    user_limit_keys, global_limit_keys = await get_key_limit(user=message.chat.id)
    
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
    bot_info = await bot.get_me()
    text1 =  translate[cache['lang']]['update_welcome_message'][1].replace('{message.chat.id}', str(message.chat.id))
    text1 += translate[cache['lang']]['update_welcome_message'][2].replace('{message.chat.id}', str(message.chat.id)).replace('{bot_username}', bot_info.username)
    if today_keys:
        today_keys = sorted(today_keys, key=lambda x: x[1], reverse=True)
        if cheating:
            text2 = '\n'.join([f'<b>{type}:</b> <code>{key}</code> ({format_remaining_time(key_time, pref=translate[cache["lang"]]["format_remaining_time"][0])})' 
                               for key, key_time, type in today_keys[:-lost_tries]])
            text2 += '\n' + '\n'.join([f'<b>{type}:</b> <code>{hide_key(key)}</code> ({format_remaining_time(key_time, pref=translate[cache["lang"]]["format_remaining_time"][0])})' 
                               for key, key_time, type in today_keys[len(today_keys)-lost_tries:]])
            text2 += '\n' + translate[cache['lang']]['update_welcome_message'][8]
            
        else:
            text2 = '\n'.join([f'<b>{type}:</b> <code>{key}</code> ({format_remaining_time(key_time, pref=translate[cache["lang"]]["format_remaining_time"][0])})' 
                               for key, key_time, type in today_keys])
    else:

        text2 = translate[cache['lang']]['update_welcome_message'][3]
        
    
    text3 = f'\n\n<b>{translate[cache["lang"]]["update_welcome_message"][4]}</b> {lost_tries}/{global_limit_keys} (+{refs}) (-{delta})'
    
    text3 += translate[cache['lang']]['update_welcome_message'][5]
    
    text = text1 + text2 + text3
    try:
        WELCOME_MESS = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=inline_kb)
        cache['welcome'] = WELCOME_MESS.message_id
    except MessageIsTooLong:
        keys = '\n'.join([f'{type}:\t{key}\t({format_remaining_time(key_time, pref=translate[cache["lang"]]["format_remaining_time"][0])})' for key, key_time, type in user_limit_keys])
        pseudo_file = create_pseudo_file(keys)
        text = text1 + f" <i>{translate[cache['lang']]['update_welcome_message'][6]}</i>" + text3
        WELCOME_MESS = await bot.send_document(chat_id=message.chat.id, document=pseudo_file, caption=text, parse_mode=ParseMode.HTML, reply_markup=inline_kb)
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
    
    text = translate[cache['lang']]['process_callback_generate_menu'][0]
    text += f"\n<b>{translate[cache['lang']]['process_callback_generate_menu'][1]}</b> {global_limit_keys - user_limit_keys}/{global_limit_keys}"
    text += translate[cache['lang']]['process_callback_generate_menu'][2]

    keyboard = InlineKeyboardMarkup()
    for type in json_config['EVENTS']:
        inline_btn = InlineKeyboardButton(text=json_config['EVENTS'][type]['NAME'], callback_data=f'generate_key_{type}')
        keyboard.add(inline_btn)
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_menu'][3], callback_data='main_menu'))

    WELCOME_MESS = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
    cache['welcome'] = WELCOME_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    
    await set_cached_data(message.chat.id, cache) ##write

@dp.callback_query_handler(lambda c: c.data.startswith('generate_key_'))
async def generate_key(callback_query: types.CallbackQuery) -> None:
    global DEBUG
    message = callback_query.message
    cache = await get_cached_data(message.chat.id) ##cache
    try:
        await bot.answer_callback_query(callback_query.id)
    except InvalidQueryID:
        pass
    game_key = callback_query.data.split('_')[2]
    delay = 5 ##delay5
    
    last_user_key = await get_last_user_key(message.chat.id, pool=POOL)
    user_limit_keys, global_limit_keys = await get_key_limit(user=message.chat.id)

    if cache['loading'] and cache['process']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['loading'])
        cache['loading'] = None

    def can_generate_key():
        return not last_user_key or abs(relative_time(last_user_key['time'])) > DELAY or DEBUG

    if can_generate_key() and cache['process']:
        if user_limit_keys < global_limit_keys:
            mins = json_config['EVENTS'][game_key]['EVENTS_DELAY'][0] * 15 // 60000 // 2
            LOADING_MESS = await new_message(translate[cache['lang']]['generate_key'][0].replace('{mins}', str(mins)), message.chat.id)
            cache['loading'] = LOADING_MESS.message_id
            await set_cached_data(message.chat.id, cache) ##write
            try:
                key = await get_unused_key_of_type(game_key, pool=POOL)
                if key is not None:
                    await try_to_delete(message.chat.id, cache['loading'])
                    LOADING_MESS = await new_message(message=translate[cache['lang']]['generate_key'][1].replace('{key}', key), chat_id=message.chat.id)
                    cache['loading'] = LOADING_MESS.message_id
                    await set_cached_data(message.chat.id, cache) ##write
                    await insert_key_generation(message.chat.id, key, game_key, pool=POOL)
                else:
                    async with aiohttp.ClientSession() as session:
                        cache['process'] = False
                        load_task = asyncio.create_task(update_loadbar(message.chat.id, game_key))
                        await set_cached_data(message.chat.id, cache) ##write
                        key = await get_key(session, game_key)
                        load_task.cancel()
                        cache['process'] = True
                        if key is None:
                            await try_to_delete(message.chat.id, cache['loading'])
                            LOADING_MESS = await new_message(translate[cache['lang']]['generate_key'][2], message.chat.id)
                            cache['loading'] = LOADING_MESS.message_id
                            await set_cached_data(message.chat.id, cache) ##write
                        else:
                            await try_to_delete(message.chat.id, cache['loading'])
                            await insert_key_generation(message.chat.id, key, game_key, pool=POOL)
                            LOADING_MESS = await new_message(translate[cache['lang']]['generate_key'][3].replace('{key}', key).replace('{delay}', str(delay)), message.chat.id)
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
            LOADING_MESS = await new_message(text, message.chat.id)
            cache['loading'] = LOADING_MESS.message_id
            await set_cached_data(message.chat.id, cache) ##write
    elif not can_generate_key():
        text = translate[cache['lang']]['generate_key'][5].replace('{last_user_key}', last_user_key['key']).replace('{relative_time}', str(DELAY - relative_time(last_user_key['time'])))
        LOADING_MESS = await new_message(text, message.chat.id)
        cache['loading'] = LOADING_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write
    elif not cache['process']:
        text = translate[cache['lang']]['generate_key'][6]
        ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
        cache['error'] = ERROR_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write
            
    await set_cached_data(message.chat.id, cache) ##write
    await try_to_delete(chat_id=message.chat.id, message_id=cache['error'])
    await asyncio.sleep(delay)
    await send_welcome(callback_query.message)



#keys funcs
async def get_key_limit(user:int, default=json_config['COUNT']):
    cache = await get_cached_data(user)
    count = default
    today_keys = await get_all_user_keys_24h(user, pool=POOL)
    
    #Высчитываем рефов
    refs = await get_all_refs(pool=POOL, user_id=user)
    refs = len(refs) if refs else 0
    
    # Высчитываем, сколько было сделано заданий
    user_tasks, all_tasks = await get_tasks_limit(user)
    delta = len(all_tasks) - len(user_tasks)
    
    if refs < 4:
        count += refs
    else:
        count += 4
        refs -= 4
        i = 1
        while refs:
            count += refs % 2 ** i
            refs //= 2
            i += 1
    
    user_limit_keys = len(today_keys) if today_keys else 0
    completed = cache['tasks'] if cache['tasks'] else 0
    
    if len(user_tasks) < completed:
        if cache['error']:
            await try_to_delete(user, cache['error'])
        ERROR_MES = await new_message(translate[cache['lang']]['get_key_limit'][0]. replace('{num}', completed - len(user_tasks)), user)
        cache['tasks'] = len(user_tasks)
        cache['error'] = ERROR_MES.message_id
    cache['tasks'] = len(user_tasks)
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
                logger.warning(f"Promotion channel for task \"{promos[promo]['name']}\" ({promos[promo]['check_id']}) not found")
        elif promos[promo]['control'] == 0:
            if promo in used:
                count[promo] = promos[promo]
    return count

async def get_tasks_limit(user:int): 
    cache = await get_cached_data(user)
    user_tasks = await check_completed_tasks(user)
    all_tasks = await get_promotions(pool=POOL)
    for promo in all_tasks:
        if all_tasks[promo]['control'] == 1:
            try:
                checker = await bot.get_chat(chat_id=all_tasks[promo]['check_id'])
                if not checker or checker.id != all_tasks[promo]['check_id']:
                    all_tasks.pop(promo)
                    logger.warning(f"Error with task \"{all_tasks[promo]['name']}\" ({all_tasks[promo]['check_id']}) not found, task removed")
            except ChatNotFound:
                all_tasks.pop(promo)
                logger.warning(f"Promotion chat for task \"{all_tasks[promo]['name']}\" ({all_tasks[promo]['check_id']}) not found, task removed")
        
        elif all_tasks[promo]['control'] == 0:
            pass
    
    if cache['lang'] in transl and len(all_tasks) != 0:
        for x in transl[cache['lang']]:
            for y in transl[cache['lang']][x]:
                if x in all_tasks and y in all_tasks[x]:
                    all_tasks[x][y] = transl[cache['lang']][x][y]
                
        user_tasks = {str(x): all_tasks[x] for x in user_tasks}
         
    return user_tasks, all_tasks

@dp.callback_query_handler(lambda c: c.data == 'generate_tasks')
async def process_callback_generate_tasks(callback_query: types.CallbackQuery) -> None:
    message = callback_query.message
    cache = await get_cached_data(message.chat.id) ##cache
    await get_key_limit(user=message.chat.id)
    used, all = await get_tasks_limit(user=message.chat.id)
    
    if cache['welcome']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['welcome'])
    
    text = translate[cache['lang']]['process_callback_generate_tasks'][0]
    text += f"\n<b>{translate[cache['lang']]['process_callback_generate_tasks'][1]}</b> {len(used)}/{len(all)}"
    text += translate[cache['lang']]['process_callback_generate_tasks'][2]

    keyboard = InlineKeyboardMarkup()
    for task in all:
        mark = '✅ ' if str(task) in used else ''
        inline_btn = InlineKeyboardButton(text=mark + all[task]['name'], callback_data=f'generate_task_{task}')
        keyboard.add(inline_btn)
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_tasks'][3], callback_data='main_menu'))

    WELCOME_MESS = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
    cache['welcome'] = WELCOME_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    
    await set_cached_data(message.chat.id, cache) ##write
    
@dp.callback_query_handler(lambda c: c.data.startswith('generate_task_'))
async def generate_task_message(callback_query: types.CallbackQuery) -> None:
    used, all = await get_tasks_limit(user=callback_query.from_user.id)
    cache = await get_cached_data(callback_query.from_user.id)
    message = callback_query.message
    task_id = callback_query.data.replace('generate_task_', '')
    current = all[int(task_id)]
    try:
        checker = await bot.get_chat_member(chat_id=current['check_id'], user_id=callback_query.from_user.id)
    except ChatNotFound:
        checker = None
    except BadRequest:
        checker = None
    promo_ids = await get_checker_by_user_id(user_id=message.chat.id)
    mark = '✅ ' if checker and checker.status != 'left' and current['control'] == 1 or int(task_id) in promo_ids and current['control'] == 0 else ''
    foot = f"<i>{translate[cache['lang']]['generate_task_message'][0]}</i>" \
           if checker and checker.status != 'left' and current['control'] == 1 or int(task_id) in promo_ids and current['control'] == 0 \
            else f"<i>{translate[cache['lang']]['generate_task_message'][3]}</i>"
    
    text = mark + f"<b>{all[int(callback_query.data.replace('generate_task_', ''))]['name']}</b>\n\n" +\
            all[int(callback_query.data.replace('generate_task_', ''))]['desc'] + "\n\n" + foot
            
    but_text = translate[cache['lang']]['generate_task_message'][4] if checker and checker.status != 'left' and current['control'] == 1 or int(task_id) in promo_ids and current['control'] == 0 \
                else translate[cache['lang']]['generate_task_message'][1]
                   
    keyboard = InlineKeyboardMarkup()
    inline_btn = InlineKeyboardButton(text=but_text, callback_data=f'check_task_{callback_query.data.replace("generate_task_", "")}')
    inline_btn2 = InlineKeyboardButton(text=translate[cache['lang']]['generate_task_message'][2], callback_data='generate_tasks')
    in_but = InlineKeyboardButton(text=translate[cache['lang']]['generate_task_message'][5], url=current['link'])
    keyboard.add(inline_btn,in_but)
    keyboard.add(inline_btn2)
    
    if cache['welcome']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['welcome'])
    WELCOME_MESS = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
    cache['welcome'] = WELCOME_MESS.message_id
    
    await set_cached_data(message.chat.id, cache) ##write

@dp.callback_query_handler(lambda c: c.data.startswith('check_task_'))
async def check_task_message(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.from_user.id) ##cache
    message = callback_query.message
    
    used, all_tasks = await get_tasks_limit(user=callback_query.from_user.id)
    task_id = str(callback_query.data.replace('check_task_', ''))
    promo = all_tasks[int(task_id)]
    checker = None
    
    if str(task_id) in used:
        await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['check_task_message'][0])
        return
    
    success = False
    
    if promo['control'] == 1 and str(task_id) not in used:
        try:
            checker = await bot.get_chat_member(chat_id=promo['check_id'], user_id=message.chat.id)
            if checker and checker.status != 'left':
                await append_checker(user_id=message.chat.id, promo_id=int(task_id))
                success = True
        except ChatNotFound:
            all_tasks.pop(promo)
            logger.warning(f"Promotion chat for task \"{all_tasks[promo]['name']}\" ({all_tasks[promo]['check_id']}) not found, task removed")
    
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

@dp.message_handler(commands=['add_task'])
async def add_task(message: types.Message) -> None:
    dev = await get_all_dev(level=2)
    if message.from_user.id in dev:
        
        cache = await get_cached_data(message.chat.id) ##cache
        if not cache['process']:
            text = translate[cache['lang']]['generate_key'][6] 
            if cache['error']:
                await try_to_delete(chat_id=message.chat.id, message_id=cache['error'])
            ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
            cache['error'] = ERROR_MESS.message_id
            await set_cached_data(message.chat.id, cache) ##write
            return
        bot_info = await bot.get_me()
        text = '\n'.join(translate[cache['lang']]['add_task'][:3]) + "\n" + translate[cache['lang']]['add_task'][6].replace("{bot}", bot_info.username)
        if cache['addtask']:
            await try_to_delete(chat_id=message.chat.id, message_id=cache['addtask'])
        ADDTASK_MESS = await new_message(text, message.chat.id)
        cache['addtask'] = ADDTASK_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write

@dp.message_handler(lambda message: message.reply_to_message)
async def reply_to_task(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    
    # Проверяем, является ли ответом на нужное сообщение и завершен ли процесс
    if message.reply_to_message.message_id != cache['addtask'] or not cache['process'] or cache['right'] < 3:
        return
    
    dict_task = {}
    check_id = 1
    bot_info = await bot.get_me()
    pattern = re.compile(r'<pre>```(\w+)\n(.*?)\n```</pre>', re.DOTALL)
    transl_task = pattern.findall(message.html_text)
    if not transl_task:
        pattern = re.compile(r'<pre><code class="language-(\w+)">(.*?)<\/code><\/pre>', re.DOTALL)
        transl_task = pattern.findall(message.html_text)
        
    first = True
    for lang, content in transl_task:
        task_pattern = re.compile(r'\[(.+?)\]\[(.+?)\]', re.DOTALL)
        task_match = task_pattern.findall(content)
        
        if task_match:
            if lang not in translate:
                await send_error_message(message.chat.id, translate[cache['lang']]['add_task'][3])
                return
            
            dict_task[lang] = {t[0].lower():t[1] for t in task_match}
        if first:
            first = False
            dict_task['default'] = {t[0].lower():t[1] for t in task_match}
    
    db_task = dict_task.pop('default', None)
    try:
        checker = await bot.get_chat('@' + db_task['link'].split('/')[3])
        db_task['check_id'] = checker.id
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['add_task'][2], callback_data='main_menu'))
        await bot.send_message(chat_id=message.chat.id, 
                               text=translate[cache['lang']]['add_task'][4], 
                               parse_mode=ParseMode.HTML,
                               reply_markup=keyboard)
        
    except IndexError:
        if '://' not in db_task['link']:
            await send_error_message(message.chat.id, translate[cache['lang']]['add_task'][3])
            return
        else:
            check_id = 0
            await send_error_message(message.chat.id, translate[cache['lang']]['add_task'][5])
    except ChatNotFound:
        if '://' in db_task['link'] and 't.me' not in db_task['link'] and 'telegram.me' not in db_task['link'] or '@' not in db_task['link']:
            check_id = 0
            await send_error_message(message.chat.id, translate[cache['lang']]['add_task'][5])
        else:
            await send_error_message(message.chat.id, translate[cache['lang']]['add_task'][3])
            return
    db_task['check_id'] = bot_info.id if 'check_id' not in db_task else db_task['check_id']
    num = await insert_task(db_task, check_id)
    if not num:
        await send_error_message(message.chat.id, translate[cache['lang']]['add_task'][3])
    
    with open('tasks.json', 'r', encoding='utf-8') as f:
        exist_dict_task = json.loads(f.read())
    
    for key, value in dict_task.items():
        exist_dict_task[key][str(num)] = value
    
    with open('tasks.json', 'w', encoding='utf-8') as f:
        json.dump(exist_dict_task, f, ensure_ascii=False, indent=2)
    
    await message.delete()
    cache['addtask'] = None
    await set_cached_data(message.chat.id, cache) ##write

@dp.message_handler(commands=['delete_task'])
async def delete_task_message(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    if not cache['process']:
        return
    
    if cache['right'] < 3:
        return
    
    text = translate[cache['lang']]['delete_task'][0]
    keyboard = InlineKeyboardMarkup()
    tasks = await get_promotions(pool=POOL)
    for task in tasks:
        keyboard.add(InlineKeyboardButton(text=tasks[task]['name'], callback_data=f'delete_task_{tasks[task]["id"]}')) 
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_tasks'][3], callback_data='main_menu'))
    await bot.send_message(chat_id=message.chat.id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
 
@dp.callback_query_handler(lambda c: c.data.startswith('delete_task_'))
async def process_callback_delete_task(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    if not cache['process']:
        return
    
    if cache['right'] < 3:
        return
    
    deleted_task = {}
    task_id = callback_query.data.split('_')[2]
    await delete_task(int(task_id), pool=POOL)
    
    with open('tasks.json', 'r', encoding='utf-8') as f:
        exist_dict_task = json.loads(f.read())
    
    for lang in exist_dict_task:
        deleted_task[lang] = exist_dict_task[lang].pop(task_id, None)
        
    is_del = True
    for lang in deleted_task:
        is_del = is_del and deleted_task[lang] is not None
    
    if not is_del:
        await send_error_message(callback_query.message.chat.id, translate[cache['lang']]['process_callback_delete_task'][1])
        await delete_task(int(task_id), pool=POOL)
        return
        
    
    with open('tasks.json', 'w', encoding='utf-8') as f:
        json.dump(exist_dict_task, f, ensure_ascii=False, indent=2)
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_menu'][3], callback_data='main_menu'))
    await bot.send_message(chat_id=callback_query.message.chat.id, 
                           text=translate[cache['lang']]['process_callback_delete_task'][0].replace('{name}', deleted_task[cache['lang']]['name']),
                           reply_markup=keyboard, 
                           parse_mode=ParseMode.HTML)
    await callback_query.message.delete()
 
async def delete_task_by_id(task_id, pool):
    await delete_task(int(task_id), pool=pool)
    with open('tasks.json', 'r', encoding='utf-8') as f:
        exist_dict_task = json.loads(f.read())
    for lang in exist_dict_task:
        exist_dict_task[lang].pop(str(task_id), None)
    with open('tasks.json', 'w', encoding='utf-8') as f:
        json.dump(exist_dict_task, f, ensure_ascii=False, indent=2)
       


# Other games funcs
@dp.callback_query_handler(lambda c: c.data == 'other_games')
async def process_callback_other_games(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_other_games'][0])



#main
if __name__ == '__main__':
    POOL = asyncio.get_event_loop().run_until_complete(get_pool())
    users_id = asyncio.get_event_loop().run_until_complete(update_cache_process(POOL))
    logger.info("Send warning message to everyone who tried to generate key before....")
    
    text = {"ru": "Бот перезапущен, пожалуйста, сгенеруйте ключ заново (/start)", 
            "en": "Bot now restarted, please generate key again (/start)"}
    asyncio.get_event_loop().run_until_complete(update_report(json_config['FIRST_SETUP']['DEV'], text, None, users_id, True))
    
    logger.info('Telegram bot started...')
    executor.start_polling(dp, skip_updates=True)
