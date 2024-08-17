import asyncio
import aiohttp
import json
import re
import random
import traceback
from io import BytesIO

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from aiogram.utils.exceptions import (MessageNotModified, MessageToDeleteNotFound, InvalidQueryID, ChatNotFound,
                                      BotBlocked, MessageIsTooLong, MessageToEditNotFound, MessageCantBeDeleted,
                                      BadRequest, MessageCantBeEdited, UserDeactivated)

from generate import generate_loading_bar, get_key, logger
from database import (insert_key_generation, get_last_user_key, get_all_dev, get_all_user_ids, now, get_promotions,
                      get_unused_key_of_type, relative_time, get_all_user_keys_24h, insert_user, format_remaining_time, 
                      delete_user, get_pool, get_all_refs, get_user, get_cached_data as get_cached, write_cached_data, 
                      update_cache_process, insert_task, get_checker_by_user_id, append_checker, 
                      delete_task_by_id as delete_task)

# Load configuration

def reload_config():
    global json_config, translate, transl, snippet
    with open('config.json') as f:
        json_config = json.load(f)
    with open('localization.json') as f:
        translate = json.load(f)
        snippet = translate.pop('snippets')
    with open('tasks.json') as f:
        transl = json.load(f)


with open('config.json') as f:
    json_config = json.load(f)
with open('localization.json') as f:
    translate = json.load(f)
    snippet = translate.pop('snippets')
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
    reload_config()
    data_copy = data.copy()
    
    data_copy.pop('lang', None)
    data_copy.pop('id', None)
    data_copy.pop('right', None)
    
    await write_cached_data(user, data_copy, pool=pool) 

async def get_cached_data(user_id:int) -> tuple:
    reload_config()
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



#loadbars
async def update_loadbar(chat_id:int, game_key:str) -> None:
    cache = await get_cached_data(chat_id) ##cache
    
    if DEBUG:
        sec = json_config['DEBUG_DELAY'][1] // 1000
    else:
        delay_rand = random.randint(json_config['EVENTS'][game_key]['EVENTS_DELAY'][0], json_config['EVENTS'][game_key]['EVENTS_DELAY'][1])
        sec = delay_rand * (1 + (json_config["MAX_RETRY"]) * 2) // 1000 // 3
        max_sec = json_config['EVENTS'][game_key]['EVENTS_DELAY'][1] * (1 + (json_config["MAX_RETRY"]) * 2) // 1000
    loading = 0
    cache['process'] = False
    await set_cached_data(chat_id, cache) ##write
    while not cache['process']:
        text = generate_loading_bar(progress=loading, max=sec)
        
        time = translate[cache['lang']]['update_loadbar'][1].replace('{mins}', format_remaining_time(now() + sec, pref=cache['lang']))
        plus_text = snippet['italic'].format(text=translate[cache['lang']]['update_loadbar'][2].replace('{max}', format_remaining_time(now() + max_sec, pref=cache['lang']))) if loading >= sec else ''
        full = time + '\n' + plus_text + '\n\n' + text 
        try:
            await try_to_edit(full, chat_id, cache['loading'])
        except MessageNotModified:
            pass
        delay = 1 + random.random()
        loading += delay
        await asyncio.sleep(delay)
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
        
        time_text = translate[cache['lang']]['update_report'][0].replace('{mins}', str(max))
        full_report_text = time_text + f"\n{loading}/{max}" + '\n\n' + progress_text
        
        try:
            await try_to_edit(full_report_text, chat_id, cache['report'])
        except MessageNotModified:
            logger.error(f"Message for report in chat {chat_id} not modified")
        
        await asyncio.sleep(1)
        
    if json_config['FIRST_SETUP']['MAIN_CHANNEL'] or json_config['FIRST_SETUP']['MAIN_GROUP'] and not warning:
        try:
            checker_group = await bot.get_chat(json_config['FIRST_SETUP']['MAIN_GROUP'])
        except ChatNotFound:
            logger.warning(f'Group {json_config["FIRST_SETUP"]["MAIN_GROUP"]} not found')
            checker_group = None
        except Exception as e:
            send_error_message(chat_id, "Chat to report not found or something else happened, check logs", e, True)    
        
        try: 
            checker_channel = await bot.get_chat(json_config['FIRST_SETUP']['MAIN_CHANNEL'])
        except ChatNotFound:
            logger.warning(f'Channel {json_config["FIRST_SETUP"]["MAIN_CHANNEL"]} not found')
            checker_channel = None
        except Exception as e:
            send_error_message(chat_id, "Channels to report not found or something else happened, check logs", e, True) 
        try:
            bot_info = await bot.get_me()
        except Exception as e:
            send_error_message(chat_id, "Bot not found or something else happened, check logs", e, True)
            bot_info = None
        
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
            if bot_info:
                link = f"https://t.me/{bot_info.username}"
                strs.append(f"🤖 {snippet['link'].format(link=link, text=translate[cache['lang']]['update_report'][3])}")  
                
            text_to_send = '\n'.join([snippet['code-block'].format(text=code, lang=lang) for lang, code in text.items() if lang != 'default']) + "\n\n" \
                + " | ".join(strs)
        
            if checker_channel is not None:
                await new_message(text=text_to_send, chat_id=checker_channel.id)
            elif checker_group is not None:
                await new_message(text=text_to_send, chat_id=checker_group.id)
         
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
    except Exception as e:
        logger.debug(f'Error deleting message in chat {chat_id}: {e}')
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
    except MessageCantBeEdited:
        return False
    except Exception as e:
        logger.debug(f'Error editing message in chat {chat_id}: {e}')
        return False
    
async def send_error_message(chat_id:int, message:str, e = None, only_dev = False) -> types.Message:
    cache = await get_cached_data(chat_id) ##cache
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['send_error_message'][0], callback_data='main_menu'))
    if only_dev and cache['right'] < 0:
        ERROR_MESS = await new_message(text=message, chat_id=json_config['FIRST_SETUP']['DEV'], keyboard=keyboard)
    
    cache['process'] = True
    if cache['error']:
        await try_to_delete(chat_id, cache['error'])
    if e is not None:
        err_t = f'Error: {e}' if str(e) else ''
        logger.error(f'{traceback.format_stack()[-2]}\t{err_t}')
    ERROR_MESS = await new_message(text=message, chat_id=chat_id, keyboard=keyboard)
    cache['error'] = ERROR_MESS.message_id
    await set_cached_data(chat_id, cache) ##write
    return ERROR_MESS
    
async def new_message(text: str, chat_id: int, keyboard: InlineKeyboardMarkup = None, disable_preview = True, parse_mode = ParseMode.HTML) -> types.Message:
    try:
        return await bot.send_message(text=html_back_escape(text), 
                                      chat_id=chat_id, 
                                      parse_mode=parse_mode, 
                                      disable_web_page_preview=disable_preview, 
                                      reply_markup=keyboard)
    except BotBlocked:
        logger.warning("Bot was blocked by user ({user_id})".format(user_id=chat_id))
    except ChatNotFound:
        logger.warning("Chat ({user_id}) not found".format(user_id=chat_id))
    except Exception as e:
        logger.error(f'Error sending message in chat {chat_id}: {e}')
        return
        
async def send_message_to_user(user_id:int, text: str, keyboard: InlineKeyboardMarkup) -> None:
    bot_info = await bot.get_me()
    if user_id == bot_info.id:
        return
    cache = await get_cached_data(user_id) ##cache
    try:
        await new_message(chat_id=user_id, text=text, keyboard=keyboard)
    except ChatNotFound:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][0].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
    except BotBlocked:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][1].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
    except UserDeactivated:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][2].replace('{user_id}', str(user_id))}")
        await delete_user(user_id, pool=POOL)
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
@dp.callback_query_handler(lambda c: c.data == 'report')
async def process_callback_report(callback_query: types.CallbackQuery) -> None:
    await mass_report(callback_query.message)

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

    if message.chat.id not in await get_all_dev(pool=POOL, level=2):
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
    inline_kb.add(other_games)
    inline_kb.add(inline_tasks)
    inline_kb.add(giveaways)
    if cache['right'] > 0:
        inline_kb.add(inline_report)
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
    
    text1 =  snippet['bold'].format(text=translate[cache['lang']]['send_welcome'][1]) + "\n" + \
            translate[cache['lang']]['send_welcome'][11] + ":" +\
            snippet['code'].format(text=str(message.chat.id)) + "\n"
            
    text1 += translate[cache['lang']]['send_welcome'][2].replace('{message.chat.id}', str(message.chat.id)).replace('{bot_username}', bot_info.username) + "\n" + \
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
    try:
        WELCOME_MESS = await new_message(text=text, chat_id=message.chat.id, keyboard=inline_kb, disable_preview=False)
        cache['welcome'] = WELCOME_MESS.message_id
    except MessageIsTooLong:
        keys = '\n'.join([f'{type}:\t{key}\t({format_remaining_time(key_time, pref=cache["lang"])})' for key, key_time, type in user_limit_keys])
        pseudo_file = create_pseudo_file(keys)
        text = text1 + f" {snippet['italic'].format(text=translate[cache['lang']]['send_welcome'][6])}" + text3
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
    
    text = snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_menu'][0] + ":") + "\n"
    text += f"\n{snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_menu'][1])} {global_limit_keys - user_limit_keys}/{global_limit_keys}\n\n"
    text += snippet['italic'].format(text=translate[cache['lang']]['process_callback_generate_menu'][2])

    keyboard = InlineKeyboardMarkup()
    
    # Создаем список кнопок из конфигурации
    buttons = [InlineKeyboardButton(text=json_config['EVENTS'][type]['NAME'], callback_data=f'generate_key_{type}') for type in json_config['EVENTS']]
    
    # Добавляем кнопки по две в строке
    for i in range(0, len(buttons), 2):
        keyboard.add(*buttons[i:i + 2])
    
    # Добавляем кнопку главного меню в отдельной строке
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_menu'][3], callback_data='main_menu'))

    WELCOME_MESS = await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard)
    cache['welcome'] = WELCOME_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    
    await set_cached_data(message.chat.id, cache) ##write


#keys funcs
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
            LOADING_MESS = await new_message(text=translate[cache['lang']]['generate_key'][0].replace('{mins}', str(mins)), chat_id=message.chat.id)
            cache['loading'] = LOADING_MESS.message_id
            await set_cached_data(message.chat.id, cache) ##write
            try:
                key = await get_unused_key_of_type(game_key, pool=POOL)
                if key is not None:
                    await try_to_delete(message.chat.id, cache['loading'])
                    LOADING_MESS = await new_message(text=translate[cache['lang']]['generate_key'][1].replace('{key}', snippet['code'].format(text=key)), chat_id=message.chat.id)
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
                            if json_config['DEBUG_KEY'] in key:
                                game_key = json_config['DEBUG_KEY']
                            await try_to_delete(message.chat.id, cache['loading'])
                            LOADING_MESS = await new_message(text=translate[cache['lang']]['generate_key'][2], chat_id=message.chat.id)
                            cache['loading'] = LOADING_MESS.message_id
                            await set_cached_data(message.chat.id, cache) ##write
                        else:
                            await try_to_delete(message.chat.id, cache['loading'])
                            await insert_key_generation(message.chat.id, key, game_key, pool=POOL)
                            LOADING_MESS = await new_message(text=translate[cache['lang']]['generate_key'][3].replace('{key}', snippet['code'].format(text=key)).replace('{delay}', str(delay)), chat_id=message.chat.id)
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
        text = translate[cache['lang']]['generate_key'][5].replace('{last_user_key}', snippet['code'].format(text=last_user_key['key'])).replace('{relative_time}', str(DELAY - relative_time(last_user_key['time'])))
        LOADING_MESS = await new_message(text=text, chat_id=message.chat.id)
        cache['loading'] = LOADING_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write
    elif not cache['process']:
        text = translate[cache['lang']]['generate_key'][6]
        ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
        cache['error'] = ERROR_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write
            
    await set_cached_data(message.chat.id, cache) ##write
    # await try_to_delete(chat_id=message.chat.id, message_id=cache['error'])
    await asyncio.sleep(delay)
    await send_welcome(callback_query.message)

async def get_key_limit(user: int, default=json_config['COUNT']):
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
    
    user_limit_keys = len(today_keys) or 0
    completed = cache['tasks'] or 0

    # Handle task completion error
    if len(user_tasks) < completed:
        num_str = str(completed - len(user_tasks))
        if cache.get('error'):
            await try_to_delete(user, cache['error'])
        ERROR_MES = await send_error_message(user, translate[cache['lang']]['get_key_limit'][0] + ": " + snippet['bold'].format(text=num_str))
        cache.update({'tasks': len(user_tasks), 'error': ERROR_MES.message_id})
    else:
        cache['tasks'] = len(user_tasks)
    
    await set_cached_data(user, cache, pool=POOL)
    return user_limit_keys, count - delta




# Tasks funcs
async def check_completed_tasks(user_id:int):
    global POOL
    promos = await get_promotions(pool=POOL)
    used = await get_checker_by_user_id(user_id, pool=POOL)
    bot_info = await bot.get_me()
    count = {}
    for promo in promos:
        if promos[promo]['control'] == 1:
            try:
                checker = await bot.get_chat_member(chat_id=promos[promo]['check_id'], user_id=user_id)
                if checker.status != 'left':
                    count[promo] = promos[promo]
            except ChatNotFound:
                if promos[promo]['check_id'] == bot_info.id:
                    logger.warning(f"Promotion channel for task \"{promos[promo]['name']}\" ({promos[promo]['check_id']}) not found")
            except BadRequest as e:
                if e.args[0] == 'Member list is inaccessible':
                    logger.warning(f"Error with task \"{promos[promo]['name']}\" ({promos[promo]['check_id']}): {e.args[0]}, task check removed")
                    await send_error_message(user_id, f"Error with task \"{promos[promo]['name']}\" ({promos[promo]['check_id']})", only_dev=True)
                    await insert_task(promos[promo], 0)
                else:
                    logger.warning(f"Error with task \"{promos[promo]['name']}\" ({promos[promo]['check_id']}) not found")
        elif promos[promo]['control'] == 0:
            if int(promo) in used:
                count[promo] = promos[promo]
    return count

async def get_tasks_limit(user: int):
    cache = await get_cached_data(user)
    user_tasks = await check_completed_tasks(user)
    all_tasks = await get_promotions(pool=POOL)
    bot_info = await bot.get_me()

    valid_tasks = {}

    for promo_id, promo in all_tasks.items():
        promo_id = str(promo_id)
        
        if promo['control'] == 1:
            try:
                checker = await bot.get_chat(chat_id=promo['check_id'])
                if checker and checker.id == promo['check_id']:
                    valid_tasks[promo_id] = promo
            except ChatNotFound:
                if promo['check_id'] == bot_info.id:
                    logger.warning(f"Promotion chat for task \"{promo['name']}\" ({promo['check_id']}) not found, task removed")
                    await delete_task_by_id(promo['id'], pool=POOL)
        else:
            valid_tasks[promo_id] = promo
    
    global transl
    if not transl:
        transl = {}
    if cache['lang'] in transl and valid_tasks:
        for lang, translations in transl[cache['lang']].items():
            if lang in valid_tasks:
                for key, value in translations.items():
                    if key in valid_tasks[lang]:
                        valid_tasks[lang][key] = value

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
    if cache['right'] > 3-1:
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
        checker = await bot.get_chat_member(chat_id=current_task['check_id'], user_id=user_id)
        is_task_completed = checker and checker.status != 'left' and current_task['control'] == 1
    except (ChatNotFound, BadRequest):
        current_task['control'] = 0
        error_key = 6 if isinstance(ChatNotFound, Exception) else 7
        await send_error_message(
            message.chat.id, 
            translate[cache['lang']]['generate_task_message'][error_key]
            .replace('{num}', str(current_task['check_id']))
            .replace('{task}', current_task['name']), 
            only_dev=True
        )
        await delete_task_by_id(task_id, pool=POOL) if isinstance(ChatNotFound, Exception) else await insert_task(current_task, check=0, pool=POOL)
        is_task_completed = False

    # Проверяем выполненные задания
    promo_ids = await get_checker_by_user_id(user_id=user_id)
    is_task_completed = is_task_completed or (int(task_id) in promo_ids and current_task['control'] == 0)

    # Формируем текст и кнопки для сообщения
    mark = '✅ ' if is_task_completed else ''
    foot = translate[cache['lang']]['generate_task_message'][3 if is_task_completed else 0]
    text = f"{mark}{snippet['bold'].format(text=current_task['name'])}\n\n{current_task['desc']}\n\n{snippet['italic'].format(text=foot)}"

    but_text = translate[cache['lang']]['generate_task_message'][4 if is_task_completed else 1]
    keyboard = InlineKeyboardMarkup(row_width=1)
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
    bot_info = await bot.get_me()
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
            if all_tasks[task_id]['check_id'] != bot_info.id:
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
    if cache['right'] < 3:
        text = snippet['bold'].format(text=translate[cache['lang']]['add_task_message'][0])
        channel = await bot.get_chat(chat_id=json_config["FIRST_SETUP"]["MAIN_CHANNEL"])
        key = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['add_task_message'][1], url=await channel.get_url()))
        key.add(InlineKeyboardButton(translate[cache['lang']]['add_task_message'][2], callback_data='generate_tasks'))
        if cache['welcome']:
            await try_to_delete(chat_id=callback_query.from_user.id, message_id=cache['welcome'])
        WELCOME_MESS = await new_message(text=text, chat_id=callback_query.from_user.id, keyboard=key)
        cache['welcome'] = WELCOME_MESS.message_id
        await set_cached_data(callback_query.from_user.id, cache) ##write
    else:
        await add_task(callback_query.message)

@dp.message_handler(commands=['add_task'])
async def add_task(message: types.Message) -> None:
    dev = await get_all_dev(level=2)
    if message.chat.id in dev:
        cache = await get_cached_data(message.chat.id) ##cache
        if not cache['process']:
            text = translate[cache['lang']]['add_task'][8] 
            if cache['error']:
                await try_to_delete(chat_id=message.chat.id, message_id=cache['error'])
            ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
            cache['error'] = ERROR_MESS.message_id
            await set_cached_data(message.chat.id, cache) ##write
            return
        bot_info = await bot.get_me()
        text = '\n'.join([snippet['bold'].format(text=translate[cache['lang']]['add_task'][0]),
                          snippet['code'].format(text=translate[cache['lang']]['add_task'][1], lang=cache['lang']),
                          snippet['italic'].format(text=translate[cache['lang']]['add_task'][2])]) + "\n\n" +\
                            translate[cache['lang']]['add_task'][6] + "\n"+\
                            snippet['block'].format(text=translate[cache['lang']]['add_task'][7].replace("{bot}", bot_info.username))
                            
        if cache['addtask']:
            await try_to_delete(chat_id=message.chat.id, message_id=cache['addtask'])
        key = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['add_task_message'][2], callback_data='main_menu'))
        ADDTASK_MESS = await new_message(chat_id=message.chat.id, text=text, keyboard=key)
        cache['addtask'] = ADDTASK_MESS.message_id
        await set_cached_data(message.chat.id, cache) ##write

@dp.message_handler(lambda message: message.reply_to_message)
async def reply_to_task(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id)
    
    if message.reply_to_message.message_id != cache['addtask'] or not cache['process'] or cache['right'] < 3:
        return

    bot_info = await bot.get_me()
    transl_task = re.findall(r'<pre>```(\w+)\n(.*?)\n```<\/pre>|<pre><code class="language-(\w+)">(.*?)<\/code><\/pre>', message.html_text, re.DOTALL)

    if not transl_task:
        await send_error_message(message.chat.id, translate[cache['lang']]['add_task'][3])
        return
    
    dict_task = {}
    for lang, content1, _, content2 in transl_task:
        content = content1 or content2
        task_match = re.findall(r'\[(.+?)\]\[(.+?)\]', content, re.DOTALL)

        if task_match:
            lang = lang or _
            dict_task[lang] = {t[0].lower(): t[1] for t in task_match}
            dict_task[lang]['check_id'] = int(dict_task[lang].get('id', bot_info.id))

            try:
                checker = await bot.get_chat(dict_task[lang]['check_id'])
                dict_task[lang]['link'] = checker.invite_link or dict_task[lang]['link']
                dict_task[lang]['check_id'] = checker.id
            except ChatNotFound:
                logger.warning(f"Chat ({dict_task[lang]['check_id']}) not found")

            if '+' not in dict_task[lang]['link'].split('/')[3] and 'joinchat' not in dict_task[lang]['link']:
                try:
                    checker = await bot.get_chat('@' + dict_task[lang]['link'].split('/')[3])
                    dict_task[lang]['link'] = checker.invite_link or dict_task[lang]['link']
                    dict_task[lang]['check_id'] = checker.id
                except ChatNotFound:
                    logger.warning(f"Chat ({dict_task[lang]['link']}) not found")

    db_task = dict_task.get('default', list(dict_task.values())[0])
    
    try:
        checker = await bot.get_chat(db_task.get('check_id') or '@' + db_task['link'].split('/')[3])
        db_task['check_id'] = checker.id
        db_task['link'] = checker.invite_link or db_task['link']

        keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(
            text=translate[cache['lang']]['reply_to_task'][0], callback_data='main_menu'))
        await new_message(chat_id=message.chat.id, text=translate[cache['lang']]['add_task'][4], keyboard=keyboard)

    except (IndexError, ChatNotFound):
        await send_error_message(message.chat.id, translate[cache['lang']]['add_task'][3])
        return

    # Вызов новой функции для вставки задачи и обновления JSON
    await insert_task_by_id(db_task, pool=POOL)  # передайте pool, который используется в insert_task_by_id

    await try_to_delete(message.chat.id, message.message_id)
    cache['addtask'] = None
    await set_cached_data(message.chat.id, cache)

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
    
    if cache['right'] < 3:
        return
    
    deleted_task = {}
    task_id = callback_query.data.split('_')[2]
    await delete_task_by_id(task_id, pool=POOL)
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_delete_task'][2], callback_data='main_menu'))
    await new_message(chat_id=callback_query.message.chat.id, 
                           text=translate[cache['lang']]['process_callback_delete_task'][0].replace('{name}', deleted_task[cache['lang']]['name']),
                           keyboard=keyboard)
    await try_to_delete(callback_query.message.chat.id, callback_query.message.message_id)
 
async def delete_task_by_id(task_id:str, pool):
    await delete_task(int(task_id), pool=pool)
    with open('tasks.json', 'r', encoding='utf-8') as f:
        exist_dict_task = json.loads(f.read())
    for lang in exist_dict_task:
        exist_dict_task[lang].pop(str(task_id), None)
    with open('tasks.json', 'w', encoding='utf-8') as f:
        json.dump(exist_dict_task, f, ensure_ascii=False, indent=2)

async def insert_task_by_id(task:dict, pool):
    task_id = await insert_task(task, pool=pool)
    with open('tasks.json', 'r', encoding='utf-8') as f:
        exist_dict_task = json.loads(f.read())
    for lang in exist_dict_task:
        exist_dict_task[lang][task_id] = task[lang]
    with open('tasks.json', 'w', encoding='utf-8') as f:
        json.dump(exist_dict_task, f, ensure_ascii=False, indent=2)
       


# Giveaway funcs
@dp.callback_query_handler(lambda c: c.data == 'giveaways')
async def process_giveaways(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_giveaway'][0])
    
@dp.callback_query_handler(lambda c: c.data.startswith('giveaway_'))
async def process_callback_giveaway(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_giveaway'][1])







# Other games funcs
@dp.callback_query_handler(lambda c: c.data == 'other_games')
async def process_callback_other_games(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_other_games'][0])



#main
if __name__ == '__main__':
    reload_config()
    POOL = asyncio.get_event_loop().run_until_complete(get_pool())
    users_id = asyncio.get_event_loop().run_until_complete(update_cache_process(POOL))
    logger.info("Send warning message to everyone who tried to generate key before....")
    
    text = {"ru": "Бот перезапущен, пожалуйста, сгенеруйте ключ заново (/start)", 
            "en": "Bot now restarted, please generate key again (/start)"}
    asyncio.get_event_loop().run_until_complete(update_report(json_config['FIRST_SETUP']['DEV'], text, None, users_id, True))
    
    logger.info('Telegram bot started...')
    executor.start_polling(dp, skip_updates=True)
