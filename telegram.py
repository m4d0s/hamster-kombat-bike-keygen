import asyncio
import aiohttp
import json
import re
from io import BytesIO

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from aiogram.utils.exceptions import (MessageNotModified, MessageToDeleteNotFound, InvalidQueryID, ChatNotFound,
                                      ChatNotFound, BotBlocked, MessageIsTooLong, MessageToEditNotFound)

from generate import generate_loading_bar, get_key, logger
from database import (log_timestamp, insert_key_generation, get_last_user_key, get_all_dev, get_all_user_ids,
                      get_unused_key_of_type, relative_time, get_all_user_keys_24h, insert_user, format_remaining_time, 
                      delete_user, get_pool, get_all_refs, get_user, get_cashed_data, write_cashed_data, update_cashe_process)

# Load configuration
with open('config.json') as f:
    json_config = json.load(f)
with open('localization.json') as f:
    translate = json.load(f)

API_TOKEN = json_config['API_TOKEN']
DELAY = json_config['DELAY']
DEBUG_KEY = json_config['DEBUG_KEY']
POOL = None

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

cashe = {'user_id':0, 'welcome':0, 'loading':0, 'report':0, 'process':False}

async def get_cached_data(user_id:int) -> tuple:
    config = await get_cashed_data(user_id, pool=POOL)
    user = await get_user(user_id, pool=POOL)
    
    welcome = config['welcome'] if config else None
    loading = config['loading'] if config else None
    report = config['report'] if config else None
    process = config['process'] if config else True
    error = config['error'] if config else None
    lang = user['lang'] if user else 'en'
    right = user['right'] if user else None
    
    return welcome, loading, report, process, lang, right, error

async def set_cached_data(user_id:int, welcome:int, loading:int, report:int, process:bool, error:int) -> None:
    await write_cashed_data(user_id, {'welcome': welcome, 
                                      'loading': loading, 
                                      'report': report, 
                                      'process': process, 
                                      'error': error}, pool=POOL)

def html_back_escape(text:str) -> str:
    return str(text).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

async def update_loadbar(chat_id:int, game_key:str) -> None:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(chat_id) ##cashe
    sec = json_config['EVENTS'][game_key]['EVENTS_DELAY'][1] * 15 // 1000
    mins = json_config['EVENTS'][game_key]['EVENTS_DELAY'][1] * 15 // 60000 // 2
    loading = 0
    process_completed = False
    await set_cached_data(chat_id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
    while not process_completed:
        text = generate_loading_bar(progress=loading, max=sec)
        
        time = translate[LANG]['generate_key'][0].replace('{mins}', '5')
        plus_text = translate[LANG]['generate_key'][7].replace('{key}', game_key) if loading > sec else ''
        full = time + '\n\n' + text + '\n' + plus_text
        try:
            await try_to_edit(full, chat_id, LOADING)
        except MessageNotModified:
            pass
        loading += 1
        await asyncio.sleep(1)
        WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(chat_id) ##cashe
    process_completed = True
    loading = sec
    text = generate_loading_bar(progress=loading, max=mins)
    full = time + '\n\n' + text
    await try_to_edit(full, chat_id, LOADING)
    await set_cached_data(chat_id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write

async def update_report(chat_id:int, text:str|dict, keyboard: InlineKeyboardMarkup = None, users = None, warning = False) -> None:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(chat_id) ##cashe
    loading = 0
    if users is None:
        user_ids = await get_all_user_ids(pool=POOL)
    else:
        if users == []:
            return
        user_ids = users
    max = len(user_ids)
    
    tasks = []
    for user_id in user_ids:
        if type(text) is dict:
            wel, loa, rep, pro, lang, ri, err = await get_cached_data(user_id) ##cashe
            if lang in text.keys():
                tasks.append(asyncio.create_task(send_message_to_user(user_id, text[lang], keyboard)))
            else:
                tasks.append(asyncio.create_task(send_message_to_user(user_id, text['default'], keyboard)))
        else:
            tasks.append(asyncio.create_task(send_message_to_user(user_id, text, keyboard)))
    # await asyncio.gather(*tasks)
    process_completed = False
    await set_cached_data(chat_id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
    while not process_completed:
        text = generate_loading_bar(progress=loading, max=max)
        loading = len([x for x in tasks if x.done()])
        if loading == max:
            process_completed = True
            break
        time = translate[LANG]['update_report'][0].replace('{mins}', str(max))
        full = time + f'\n{loading}/{max}' + '\n\n' + text
        try:
            await try_to_edit(full, chat_id, REPORT)
        except MessageNotModified:
            logger.error(f'Message for report in chat {chat_id} not modified')
        except BotBlocked:
            await delete_user(user_id, pool=POOL)
        except ChatNotFound:
            await delete_user(user_id, pool=POOL)
        loading += 1
        await asyncio.sleep(1)
    process_completed = True
    await set_cached_data(chat_id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write



async def try_to_delete(chat_id:int, message_id:int) -> bool:
    if message_id is None or message_id == 0:
        logger.warning('Message ID is None to delete in chat ' + str(chat_id))
        return False
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except MessageToDeleteNotFound:
        return False
    
async def try_to_edit(text:str, chat_id:int, message_id:int) -> bool:
    if message_id is None or message_id == 0:
        logger.warning('Message ID is None to edit in chat ' + str(chat_id))
        return False
    try:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode=ParseMode.HTML)
        return True
    except MessageToEditNotFound:
        return False
    
async def send_error_message(chat_id:int, message:str, e = Exception('')) -> types.Message:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(chat_id) ##cashe
    process_completed = True
    if ERROR:
        await try_to_delete(chat_id, ERROR)
    logger.error(f'Error generating key! Error: {e.with_traceback(e.__traceback__)}')
    ERROR_MESS = await new_message(message, chat_id)
    ERROR = ERROR_MESS.message_id
    await set_cached_data(chat_id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
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
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(user_id) ##cashe
    try:
        await bot.send_message(chat_id=user_id, text=html_back_escape(text), parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=keyboard)
    except ChatNotFound:
        logger.warning(f"{translate[LANG]['send_message_to_user'][0].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
    except BotBlocked:
        logger.warning(f"{translate[LANG]['send_message_to_user'][1].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
    await set_cached_data(user_id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write



@dp.message_handler(commands=['start'])
async def send_language_choose(message: types.Message) -> None:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(message.chat.id) ##cashe
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
        text = f"{translate[LANG]['send_language_choose'][0]}\n"
        keyboard = InlineKeyboardMarkup(row_width=2)
        for x in translate:
            inline_btn = InlineKeyboardButton(text=translate[x]["NAME"], callback_data=f'lang_{x}_{message.get_args()}')
            keyboard.add(inline_btn)
        WELCOME_MESS = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        WELCOME = WELCOME_MESS.message_id
    else:
        await send_welcome(message)
        await insert_user(message.chat.id, message.from_user.username, ref=user['ref'], lang=LANG,  pool=POOL)
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    await set_cached_data(message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('lang_'))
async def process_callback_language(callback_query: types.CallbackQuery) -> None:
    data = callback_query.data
    LANG = data.split('_')[1]
    ref = int(data.split('_')[2]) if data.split('_')[2] and data.split('_')[2].isdigit() and int(data.split('_')[2]) != callback_query.message.chat.id else 0
    await try_to_delete(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    await insert_user(callback_query.message.chat.id, callback_query.from_user.username, ref=ref, lang=LANG, pool=POOL)
    await send_welcome(callback_query.message)

async def send_welcome(message: types.Message) -> None:
    today_keys = await get_all_user_keys_24h(message.chat.id, pool=POOL)
    await update_welcome_message(message, today_keys)
    
@dp.message_handler(commands=['report'])
async def mass_report(message: types.Message) -> None:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(message.chat.id) ##cashe
    devs = await get_all_dev(pool=POOL)
    if devs is None or message.chat.id not in devs or not process_completed:
        return
    await send_report_example(message)

async def send_report_example(message: types.Message) -> None:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(message.chat.id) ##cashe
    if REPORT:
        await try_to_delete(chat_id=message.chat.id, message_id=REPORT)
        REPORT = None
    code_example = translate[LANG]['send_report_example'][2]
    example = translate[LANG]['send_report_example'][3]
    warning = f'\n\n{translate[LANG]["send_report_example"][1]}'
    text = f"{translate[LANG]['send_report_example'][0]}\n\n"
    REPORT_MESS = await new_message(text + code_example + example + warning, message.chat.id)
    REPORT = REPORT_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    await set_cached_data(message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write

@dp.message_handler(lambda message: message.reply_to_message)
async def report(message: types.Message) -> None:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(message.chat.id)
    
    if not process_completed:
        text = translate[LANG]['generate_key'][6]
        ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
        ERROR = ERROR_MESS.message_id
        await set_cached_data(message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write

    # Проверяем, является ли ответом на нужное сообщение и завершен ли процесс
    if message.reply_to_message.message_id != REPORT or not process_completed:
        return

    # Получаем список разработчиков
    devs = await get_all_dev(pool=POOL)
    if message.chat.id not in devs:
        return

    # Устанавливаем процесс как незавершенный
    process_completed = False
    try_to_delete(chat_id=message.chat.id, message_id=message.message_id)

    # Создаем клавиатуру и извлекаем URL и текст без кнопок
    keyboard = InlineKeyboardMarkup()
    urls = re.findall(r'\[(.+?)\]\[(.+?)\]', message.text)
    text_without_buttons = re.sub(r'\[(.+?)\]\[(.+?)\]', '', message.html_text).strip()
    # Регулярное выражение для извлечения текста на разных языках
    pattern = re.compile(r'<pre>```(\w+)\n(.*?)\n```</pre>', re.DOTALL)
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
    await set_cached_data(message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR)

    # Обновление отчета
    await update_report(message.chat.id, text_without_buttons, keyboard)


async def update_welcome_message(message: types.Message, today_keys:list) -> None:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(message.chat.id) ##cashe
    inline_btn_generate = InlineKeyboardButton(translate[LANG]['update_welcome_message'][0], callback_data='generate_menu')
    inline_kb = InlineKeyboardMarkup().add(inline_btn_generate)
    refs = await get_all_refs(pool=POOL, user_id=message.chat.id)
    limit_keys = json_config['COUNT'] + len(refs)
    
    def create_pseudo_file(content: str, filename: str = "keys.txt"):
        pseudo_file = BytesIO()
        pseudo_file.write(content.encode('utf-8'))
        pseudo_file.seek(0)
        pseudo_file.name = filename
        return pseudo_file

    if WELCOME:
        await try_to_delete(chat_id=message.chat.id, message_id=WELCOME)
    bot_info = await bot.get_me()
    text1 =  translate[LANG]['update_welcome_message'][1].replace('{message.chat.id}', str(message.chat.id))
    text1 += translate[LANG]['update_welcome_message'][2].replace('{message.chat.id}', str(message.chat.id)).replace('{bot_username}', bot_info.username)
    if today_keys:
        today_keys = sorted(today_keys, key=lambda x: x[1], reverse=True)
        text2 = '\n'.join([f'<b>{type}:</b> <code>{key}</code> ({format_remaining_time(key_time)})' for key, key_time, type in today_keys])
    else:

        text2 = translate[LANG]['update_welcome_message'][3]
    text3 = f'\n\n<b>{translate[LANG]["update_welcome_message"][4]}</b> {limit_keys - len(today_keys) if today_keys else limit_keys}/{limit_keys}'
    text3 += translate[LANG]['update_welcome_message'][5]
    
    text = text1 + text2 + text3
    try:
        WELCOME_MESS = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=inline_kb)
        WELCOME = WELCOME_MESS.message_id
    except MessageIsTooLong:
        keys = '\n'.join([f'{format_remaining_time(key_time)}({type}): {key}' for key, key_time, type in today_keys])
        pseudo_file = create_pseudo_file(keys)
        text = text1 + f" <i>{translate[LANG]['update_welcome_message'][6]}</i>" + text3
        WELCOME_MESS = await bot.send_document(chat_id=message.chat.id, document=pseudo_file, caption=text, parse_mode=ParseMode.HTML, reply_markup=inline_kb)
        WELCOME = WELCOME_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    
    await set_cached_data(message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write


@dp.callback_query_handler(lambda c: c.data == 'generate_menu')
async def process_callback_generate_menu(callback_query: types.CallbackQuery) -> None:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(callback_query.message.chat.id) ##cashe
    message = callback_query.message
    today_keys = await get_all_user_keys_24h(callback_query.message.chat.id, pool=POOL)
    limit_keys = json_config['COUNT'] + len(await get_all_refs(pool=POOL, user_id=callback_query.message.chat.id))
    
    if WELCOME:
        await try_to_delete(chat_id=message.chat.id, message_id=WELCOME)
    
    text = translate[LANG]['process_callback_generate_menu'][0]
    text += f"\n<b>{translate[LANG]['process_callback_generate_menu'][1]}</b> {limit_keys - len(today_keys) if today_keys else limit_keys}/{limit_keys}"
    text += translate[LANG]['process_callback_generate_menu'][2]

    keyboard = InlineKeyboardMarkup()
    for type in json_config['EVENTS']:
        inline_btn = InlineKeyboardButton(text=json_config['EVENTS'][type]['NAME'], callback_data=f'generate_key_{type}')
        keyboard.add(inline_btn)

    WELCOME_MESS = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
    WELCOME = WELCOME_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    
    await set_cached_data(message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write



@dp.callback_query_handler(lambda c: c.data.startswith('generate_key_'))
async def generate_key(callback_query: types.CallbackQuery) -> None:
    WELCOME, LOADING, REPORT, process_completed, LANG, RIGHT, ERROR = await get_cached_data(callback_query.message.chat.id) ##cashe
    try:
        await bot.answer_callback_query(callback_query.id)
    except InvalidQueryID:
        pass
    game_key = callback_query.data.split('_')[2]
    limit_keys = json_config['COUNT'] + len(await get_all_refs(pool=POOL, user_id=callback_query.message.chat.id))

    last_user_key = await get_last_user_key(callback_query.message.chat.id, pool=POOL)
    today_keys = await get_all_user_keys_24h(callback_query.message.chat.id, pool=POOL) or []

    if LOADING and process_completed:
        await try_to_delete(chat_id=callback_query.message.chat.id, message_id=LOADING)
        LOADING = None

    def can_generate_key():
        return not last_user_key or abs(relative_time(last_user_key['time'])) > DELAY

    if can_generate_key() and process_completed:
        if len(today_keys) < limit_keys:
            mins = json_config['EVENTS'][game_key]['EVENTS_DELAY'][0] * 15 // 60000 // 2
            LOADING_MESS = await new_message(translate[LANG]['generate_key'][0].replace('{mins}', str(mins)), callback_query.message.chat.id)
            LOADING = LOADING_MESS.message_id
            await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
            try:
                key = await get_unused_key_of_type(game_key, pool=POOL)
                if key is not None:
                    await try_to_delete(callback_query.message.chat.id, LOADING)
                    LOADING_MESS = await new_message(message=translate[LANG]['generate_key'][1].replace('{key}', key), chat_id=callback_query.message.chat.id)
                    LOADING = LOADING_MESS.message_id
                    await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
                    await insert_key_generation(callback_query.message.chat.id, key, game_key, pool=POOL)
                else:
                    async with aiohttp.ClientSession() as session:
                        process_completed = False
                        load_task = asyncio.create_task(update_loadbar(callback_query.message.chat.id, game_key))
                        await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
                        key = await get_key(session, game_key)
                        load_task.cancel()
                        process_completed = True
                        if key is None:
                            await try_to_delete(callback_query.message.chat.id, LOADING)
                            LOADING_MESS = await new_message(translate[LANG]['generate_key'][2], callback_query.message.chat.id)
                            LOADING = LOADING_MESS.message_id
                            await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
                        else:
                            await try_to_delete(callback_query.message.chat.id, LOADING)
                            await insert_key_generation(callback_query.message.chat.id, key, game_key, pool=POOL)
                            LOADING_MESS = await new_message(translate[LANG]['generate_key'][3].replace('{key}', key), callback_query.message.chat.id)
                            LOADING = LOADING_MESS.message_id
                            await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
                        process_completed = True
            except Exception as e:
                if LOADING:
                    await try_to_delete(callback_query.message.chat.id, LOADING)
                LOADING_MESS = await send_error_message(callback_query.message.chat.id, translate[LANG]['generate_key'][2], e)
                process_completed = True
                LOADING = LOADING_MESS.message_id
                await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
        else:
            process_completed = True
            text = translate[LANG]['generate_key'][4]
            if LOADING:
                await try_to_delete(chat_id=callback_query.message.chat.id, message_id=LOADING)
            LOADING_MESS = await new_message(text, callback_query.message.chat.id)
            LOADING = LOADING_MESS.message_id
            await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
    elif not can_generate_key():
        text = translate[LANG]['generate_key'][5].replace('{last_user_key}', last_user_key['key']).replace('{relative_time}', str(60 - relative_time(last_user_key['time'])))
        LOADING_MESS = await new_message(text, callback_query.message.chat.id)
        LOADING = LOADING_MESS.message_id
        await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
    elif not process_completed:
        text = translate[LANG]['generate_key'][6]
        ERROR_MESS = await send_error_message(callback_query.message.chat.id, text, Exception('Process not completed'))
        ERROR = ERROR_MESS.message_id
        await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
            
    await set_cached_data(callback_query.message.chat.id, WELCOME, LOADING, REPORT, process_completed, ERROR) ##write
    await try_to_delete(chat_id=callback_query.message.chat.id, message_id=WELCOME)
    await send_welcome(callback_query.message)

if __name__ == '__main__':
    POOL = asyncio.get_event_loop().run_until_complete(get_pool())
    users_id = asyncio.get_event_loop().run_until_complete(update_cashe_process(POOL))
    logger.info("Send warning message to everyone who tried to generate key before....")
    text = {"ru": "Бот перезапущен, пожалуйста, сгенеруйте ключ заново (/start)", 
            "en": "Bot now restarted, please generate key again (/start)"}
    asyncio.get_event_loop().run_until_complete(update_report(json_config['FIRST_SETUP']['DEV'], text, None, users_id, True))
    
    logger.info('Telegram bot started...')
    executor.start_polling(dp, skip_updates=True)
