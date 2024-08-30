from io import BytesIO
from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .giveaway import process_callback_giveaway
from .tasks import check_completed_tasks, get_key_limit
from .message import new_message, try_to_delete
from .cache import get_cached_data, set_cached_data

from c_telegram import dp, BOT_INFO, snippet, translate, POOL, request_level
from generate import get_logger, delay
from database import (format_remaining_time, get_all_refs, get_all_user_keys_24h, get_promotions, get_user, insert_user)

logger = get_logger()

def hide_key(key:str) -> str:
    hide_symb = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    hiden_key = ''
    for i in range(len(key)):
        if key[i] in hide_symb:
            hiden_key += '*'
        else:
            hiden_key += key[i]
    return hiden_key

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
    if message.chat.type != types.ChatType.PRIVATE:
        return
    arguments = list(message.get_args().split())
    if len(arguments) == 1 and arguments[0].isdigit() or len(arguments) == 0:
        await send_language_choose(message)
    elif len(arguments) == 1 and arguments[0].startswith('giveaway_'):
        fake_callback = types.CallbackQuery(id=f"simulated_{arguments[0]}",
                                            data=f'{arguments[0]}', message=message,
                                            from_user=message.from_user)
        await process_callback_giveaway(fake_callback)     

@dp.message_handler(commands=['language'])    
async def send_language_choose(message: types.Message) -> None:
    if message.chat.type != types.ChatType.PRIVATE:
        return
    cache = await get_cached_data(message.chat.id) ##cache
    user = await get_user(message.chat.id, pool=POOL)
    logger.debug("User {user_id} started bot, lang: {lang}".format(user_id=message.chat.id, lang=message.from_user.language_code))
    if not user and message.text.startswith('/language'):
        lang_code = message.from_user.language_code
        if lang_code and lang_code in translate.keys() and not message.text.startswith('/language'):
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
        await insert_user(message.chat.id, message.from_user.username, ref=user['ref_id'], lang=cache['lang'], tg_lang=message.from_user.language_code, pool=POOL)
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
    await insert_user(message.chat.id, callback_query.from_user.username, ref=ref, lang=LANG, tg_lang=callback_query.from_user.language_code, pool=POOL)
    await send_welcome(callback_query.message)
    
# General menus
async def send_welcome(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    WELCOME_MESS = None
    
    if cache['welcome']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['welcome'])
        cache['welcome'] = None
    
    inline_kb = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['send_welcome'][0], callback_data='generate_menu'))
    
    inline_kb.add(InlineKeyboardButton(text=translate[cache['lang']]['send_welcome'][15], callback_data='other_games'))
    inline_kb.add(InlineKeyboardButton(translate[cache['lang']]['send_welcome'][7], callback_data='generate_tasks'))
    inline_kb.add(InlineKeyboardButton(text=translate[cache['lang']]['send_welcome'][10], callback_data='giveaways'))
    
    if request_level(cache['right'], 9, message.chat.id): # 9 - debug
        inline_kb.add(InlineKeyboardButton(translate[cache['lang']]['send_welcome'][9], callback_data='report'), 
                      InlineKeyboardButton(text=translate[cache['lang']]['send_welcome'][16], callback_data='debug'))   
         
    elif request_level(cache['right'], 3, message.chat.id): # 3 - report
        inline_kb.add(InlineKeyboardButton(translate[cache['lang']]['send_welcome'][9], callback_data='report'))
    

        
    if not cache['process']:
        inline_kb.add(InlineKeyboardButton(text=translate[cache['lang']]['send_welcome'][17], callback_data="stop_process"))
        
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
    lost_tries = abs(lost_tries)
    
    def create_pseudo_file(content: str, filename: str = "keys.txt"):
        pseudo_file = BytesIO()
        pseudo_file.write(content.encode('utf-8'))
        pseudo_file.seek(0)
        pseudo_file.name = filename
        return pseudo_file
    
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
            text2 += '\n' + snippet['quote'].format(text=(translate[cache['lang']]['send_welcome'][8]))
            
        else:
            text2 = '\n'.join([f'{snippet["bold"].format(text=type + ":")} {snippet["code"].format(text=key)} ({format_remaining_time(key_time, pref=cache["lang"])})' 
                               for key, key_time, type in today_keys])
    else:

        text2 = snippet['italic'].format(text=translate[cache['lang']]['send_welcome'][3])
        
    
    text3 = f'\n\n{snippet["bold"].format(text=translate[cache["lang"]]["send_welcome"][4])} {lost_tries if not cheating else 0}/{global_limit_keys} (+{refs}) (-{delta})'
    text3 += "\n\n" + snippet['italic'].format(text=translate[cache['lang']]['send_welcome'][5])
    
    text = text1 + text2 + text3
    
    if len(text) < 4096:
        WELCOME_MESS = await new_message(text=text, chat_id=message.chat.id, keyboard=inline_kb, disable_preview=False)
    else:
        keys = '\n'.join([f'{type}:\t{key}\t({format_remaining_time(key_time, pref=cache["lang"])})' for key, key_time, type in today_keys])
        pseudo_file = create_pseudo_file(keys)
        text = text1 + f" {snippet['italic'].format(text=translate[cache['lang']]['send_welcome'][6])}" + text3
        WELCOME_MESS = await new_message(chat_id=message.chat.id, document=pseudo_file, text=text, keyboard=inline_kb)
    
    if WELCOME_MESS:
        cache['welcome'] = WELCOME_MESS.message_id
        
    await set_cached_data(message.chat.id, cache) ##write    