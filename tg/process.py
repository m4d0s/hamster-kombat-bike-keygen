import asyncio
import aiohttp
import random

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import (MessageNotModified, ChatNotFound, BotBlocked)

from .message import send_error_message, new_message, try_to_delete, try_to_edit, send_message_to_user
from .cache import get_cached_data, set_cached_data

from c_telegram import dp, BOT_INFO, bot, snippet, translate, POOL, db_config, json_config
from database import (insert_key_generation, get_all_user_ids, now, get_unused_key_of_type, format_remaining_time, delete_user)
from generate import generate_loading_bar, get_key, delay, get_logger

logger = get_logger()

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
    loadbars = [generate_loading_bar(progress=0, max=max_sec) for _ in range(count)]
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
            plus_text = snippet['italic'].format(text=translate[cache['lang']]['update_loadbar'][2]
                                         .replace('{max}', format_remaining_time(now() + max_sec, pref=cache['lang']))) \
                                            if loading > sec else ''
            cache = await get_cached_data(chat_id)
            mark = "[!] " if loading > sec else ""
            if cache['process']:
               task.cancel()
               return [key for key in keys if key is not None]

            loadbars[i] = mark + generate_loading_bar(progress=part_load, max=max_sec // count)
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
     
    if cache['report']:     
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
