import asyncio
import aiohttp
import random

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import MessageNotModified, ChatNotFound, BotBlocked

from .message import send_error_message, new_message, try_to_delete, try_to_edit, send_message_to_user
from .cache import get_cached_data, set_cached_data

from c_telegram import dp, BOT_INFO, bot, snippet, translate, POOL, db_config, json_config
from database import (get_all_user_ids, now, get_unused_key_of_type, format_remaining_time, delete_user, insert_key_generation)
from generate import generate_loading_bar, get_key, delay, get_logger

logger = get_logger()

async def update_loadbar(chat_id: int, game_key: str, session: aiohttp.ClientSession, count=1, update_delay=2) -> list:
    cache = await get_cached_data(chat_id)
    cache['process'] = False
    await set_cached_data(chat_id, cache)

    event = json_config['EVENTS'][game_key]
    event_delay = event['EVENTS_DELAY']
    retry_num = event['RETRY'] if not event['ALGORITMV0'] else json_config['V0_RETRY']
    sec = event_delay[0] * (1 + retry_num * 2) // 1000 // 2 * count
    max_sec = event_delay[1] * (1 + retry_num * 2) // 1000 * count

    if json_config['DEBUG']:
        sec = json_config['DEBUG_DELAY'] // 1000 
        max_sec = json_config['DEBUG_DELAY'] // 1000 * count
        game_key = json_config['DEBUG_GAME']

    time_text = translate[cache['lang']]['update_loadbar'][1].format(mins=format_remaining_time(now() + sec, pref=cache['lang']))
    starting_text = f"{time_text}"
    loadbars = [generate_loading_bar(progress=0, max=max_sec) for _ in range(count)]
    keys = []
    loading = 0

    for i in range(count):
        part_load = 0
        free_key = await get_unused_key_of_type(game_key, pool=POOL)
        
        if free_key:
            keys.append(free_key)
            await insert_key_generation(user_id=cache['user_id'], key=free_key, key_type=game_key, used=True, pool=POOL)
            loadbars[i] = snippet['bold'].format(text=game_key + ": ") + snippet['code'].format(text=free_key)
            continue
        
        task = asyncio.create_task(get_key(session, game_key))
        
        while not task.done():
            cache = await get_cached_data(chat_id)
            if cache['process']:
                task.cancel()
                return [key for key in keys if key is not None]

            plus_text = snippet['italic'].format(text=translate[cache['lang']]['update_loadbar'][2]
                        .format(max=format_remaining_time(now() + max_sec, pref=cache['lang'])))\
                        if loading > sec else ''
            mark = "[!] " if loading > sec else ""
            loadbars[i] = mark + generate_loading_bar(progress=part_load, max=max_sec // count)
            joined_loadbars = '\n'.join(loadbars)
            full_text = f"{starting_text}\n\n{joined_loadbars}\n{plus_text}"
            stop_button = InlineKeyboardMarkup()\
                         .add(InlineKeyboardButton(text=translate[cache['lang']]['update_loadbar'][3], 
                                                   callback_data="stop_process"))

            await try_to_edit(full_text, chat_id, cache['loading'], keyboard=stop_button)
            
            delay_s = update_delay + random.random()
            loading += delay_s
            part_load += delay_s
            await delay(delay_s * 1000, f"Update loadbar for {chat_id}")
        
        try:
            key = task.result()
            keys.append(key)
            await insert_key_generation(user_id=cache['user_id'], key=key, key_type=game_key, used=True, pool=POOL)
            loadbars[i] = snippet['bold'].format(text=game_key + ": ") + \
                            snippet['code'].format(text=key or translate[cache['lang']]['update_loadbar'][4])
        except Exception as e:
            logger.warning(f"Failed to obtain key: {str(e)}")
            keys.append(None)
            loadbars[i] = snippet['bold'].format(text=game_key + ": ") + \
                            snippet['code'].format(text=translate[cache['lang']]['update_loadbar'][4])

    cache['process'] = True
    await set_cached_data(chat_id, cache)

    return [key for key in keys if key is not None]

async def update_report(chat_id: int, 
                        text: str | dict, 
                        keyboard: InlineKeyboardMarkup = None, 
                        users: list = None, 
                        warning: bool = False, 
                        max_concurrent_tasks: int = 10) -> None:
    
    cache = await get_cached_data(chat_id)
    if users is None:
        user_ids = await get_all_user_ids(pool=POOL)
    else:
        if not users:
            return
        user_ids = users
        
    if isinstance(text, str):
        text = {'default': text}
    
    max_users = len(user_ids)
    semaphore = asyncio.Semaphore(max_concurrent_tasks)

    async def send_with_semaphore(user_id):
        async with semaphore:
            user_cache = await get_cached_data(user_id)
            try:
                message_text = text.get(user_cache['lang'], text.get('default')) if isinstance(text, dict) else text
                await send_message_to_user(user_id, message_text, keyboard)
            except (BotBlocked, ChatNotFound):
                await delete_user(user_id, pool=POOL)

    cache['process'] = False
    await set_cached_data(chat_id, cache)
    
    if cache['report']:
        await try_to_delete(chat_id, cache['report'])
    start_text = '\n'.join([snippet['code-block'].format(lang=x, text=text[x]) for x in text.keys()]) +'\n\n' + 'Report started in 5 seconds.....' \
                if isinstance(text, dict) else text 
    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['update_report'][4], 
                                                                  callback_data="stop_process"))
    REPORT_MESS = await new_message(chat_id=chat_id, text=start_text, keyboard=stop_button)
    cache['report'] = REPORT_MESS.message_id
    await asyncio.sleep(5)
    
    tasks = [asyncio.create_task(send_with_semaphore(user_id)) for user_id in user_ids]
    
    while not cache['process']:
        loading = len([task for task in tasks if task.done()])
        progress_text = generate_loading_bar(progress=loading, max=max_users)

        if loading == max_users:
            cache['process'] = True
            break

        stop_button = InlineKeyboardMarkup()\
            .add(InlineKeyboardButton(text=translate[cache['lang']]['update_report'][4], callback_data="stop_process"))
        time_text = translate[cache['lang']]['update_report'][0].replace('{mins}', str(max_users))
        full_report_text = f"{time_text}\n{loading}/{max_users}\n\n{progress_text}"

        try:
            await try_to_edit(full_report_text, chat_id, cache['report'], stop_button)
        except MessageNotModified:
            logger.error(f"Message for report in chat {chat_id} not modified")
        
        await delay(1000, f"Update report load for {chat_id}")
    
    for task in [task for task in tasks if not task.done()]:
        task.cancel()   
    
    if (db_config['MAIN_CHANNEL'] or db_config['MAIN_GROUP']) and not warning:
        try:
            checker_group = await bot.get_chat(db_config['MAIN_GROUP'])
        except ChatNotFound:
            logger.warning(f'Group {db_config["FIRST_SETUP"]["MAIN_GROUP"]} not found')
            checker_group = None
        except Exception as e:
            send_error_message(chat_id, "Group not found or another issue occurred", e, True)    
        
        try: 
            checker_channel = await bot.get_chat(db_config['MAIN_CHANNEL'])
        except ChatNotFound:
            logger.warning(f'Channel {db_config["FIRST_SETUP"]["MAIN_CHANNEL"]} not found')
            checker_channel = None
        except Exception as e:
            send_error_message(chat_id, "Channel not found or another issue occurred", e, True) 
        
        if not warning: 
            links = []
            if checker_group:
                link = checker_group.invite_link or f'https://t.me/{checker_group.username}'
                if link:
                    links.append(f"💬 {snippet['link'].format(link=link, text=translate[cache['lang']]['update_report'][1])}")
            if checker_channel:
                link = checker_channel.invite_link or f'https://t.me/{checker_channel.username}'
                if link:
                    links.append(f"📢 {snippet['link'].format(link=link, text=translate[cache['lang']]['update_report'][2])}")
            if BOT_INFO:
                link = f"https://t.me/{BOT_INFO.username}"
                links.append(f"🤖 {snippet['link'].format(link=link, text=translate[cache['lang']]['update_report'][3])}")  
                
            text_to_send = '\n'.join([snippet['quoteV2'].format(text=(snippet['bold']
                                     .format(text=translate[lang]['NAME']) + "\n" + code)) 
                                      for lang, code in text.items() if lang != 'default']) + "\n\n" + " | ".join(links)
        
            if checker_channel:
                await new_message(text=text_to_send, chat_id=checker_channel.id)
            elif checker_group:
                await new_message(text=text_to_send, chat_id=checker_group.id)
     
    if cache['report']:     
        await try_to_delete(chat_id, cache['report'])
    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['update_report'][6], 
                                                                  callback_data="main_menu"))
    REPORT_MESS = await new_message(translate[cache['lang']]['update_report'][5], chat_id, stop_button)
    cache['report'] = REPORT_MESS.message_id
    cache['process'] = True
    await set_cached_data(chat_id, cache)

    await asyncio.gather(*tasks)

@dp.callback_query_handler(lambda c: c.data == 'stop_process')
async def stop_process(callback_query: types.CallbackQuery) -> None:
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    cache = await get_cached_data(chat_id)
    cache['process'] = True  # This will stop the while loop in update_report
    await set_cached_data(chat_id, cache)
    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['stop_process'][2], 
                                                                  callback_data="main_menu"))

    await callback_query.answer(translate[cache['lang']]['stop_process'][0])
    await try_to_edit(translate[cache['lang']]['stop_process'][1], chat_id, message_id, stop_button)
