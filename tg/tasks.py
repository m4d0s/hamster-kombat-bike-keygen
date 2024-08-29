import re
from datetime import datetime, timezone

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import (ChatNotFound,BadRequest)

from .message import send_error_message, new_message, try_to_delete
from .cache import get_cached_data, set_cached_data

from c_telegram import dp, BOT_INFO, bot, snippet, translate, POOL, request_level, db_config
from generate import get_logger
from database import (get_all_refs, get_all_user_keys_24h, now, get_promotions, insert_task, 
                      get_checker_by_user_id, append_checker, delete_task_by_id)

logger = get_logger()

def username_valid(username:str) -> bool:
    symbols = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
    return all(i in symbols for i in username) \
            and 4 <= len(username) <= 32 \
            and not (username[0].isdigit() or username[0] == '_')

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

async def get_key_limit(user: int, default:int=16):
    cache = await get_cached_data(user)

    today_keys = await get_all_user_keys_24h(user, pool=POOL) or []
    refs = len(await get_all_refs(pool=POOL, user_id=user)) or 0
    user_tasks, all_tasks = await get_tasks_limit(user)
    delta = len(all_tasks) - len(user_tasks)
    
    # Compute key limit based on refs
    if refs < 4:
        count = cache.get('try') or default + refs
    else:
        count = cache.get('try') or default + 4 + sum(refs // (2 ** i) % 2 ** i for i in range(1, refs.bit_length()))
    
    user_limit_keys = len(today_keys)
    completed = cache.get('tasks', 0) or 0

    # Handle task completion error
    if len(user_tasks) < completed:
        num_str = str(completed - len(user_tasks))
        # if cache.get('error'):
        #     await try_to_delete(user, cache['error'])
        await send_error_message(user, translate[cache.get('lang', 'en')]['get_key_limit'][0] + ": " + snippet['bold'].format(text=num_str))

    cache.update({'tasks': len(user_tasks)})
    
    await set_cached_data(user, cache, pool=POOL)
    return user_limit_keys, count - delta

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
        mark = '✅ ' if str(task) in used else '❌ '
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
    is_task_completed = False

    if not current_task:
        await send_error_message(message.chat.id, translate[cache['lang']]['generate_task_message'][6], only_dev=True)
        return
    
    # Проверяем членство пользователя в чате
    try:
        if current_task['control'] == 1:
            checker = await bot.get_chat_member(chat_id=current_task['check_id'], user_id=user_id)
            is_task_completed = checker and checker.status != 'left'
        elif current_task['control'] == 0:
            is_task_completed = int(task_id) in [int(x) for x in used]
    except (ChatNotFound):
        if current_task['control'] != 0 and 't.me' in current_task['link']:
            error_key = 7 
            await send_error_message(
                message.chat.id, 
                translate[cache['lang']]['generate_task_message'][error_key]\
                .format(num=str(current_task['check_id']), task=current_task['name'],
                        link=current_task['link'], id=str(current_task['id'])),
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
                .format(num=str(current_task['check_id']), task=current_task['name'],
                        link=current_task['link'], id=str(current_task['id'])),
                only_dev=True
            )
            await insert_task(current_task, check=0, pool=POOL)
            is_task_completed = False
    except (Exception) as e:
        await send_error_message(message.chat.id, 'Error occured: ' + str(e), only_dev=True)

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

async def send_task_example(message: types.Message, task_type='task') -> None:
    cache = await get_cached_data(message.chat.id)  ##cache
    if request_level(cache['right'], 2, message.chat.id):  # 2 - report
        if not cache['process']:
            text = translate[cache['lang']]['send_task_example'][8]
            if cache['error']:
                await try_to_delete(chat_id=message.chat.id, message_id=cache['error'])
            ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
            cache['error'] = ERROR_MESS.message_id
            await set_cached_data(message.chat.id, cache)  ##write
            return

        text = '\n'.join([
            snippet['bold'].format(text=translate[cache['lang']]['send_task_example'][0]) if task_type == 'task' \
                else snippet['bold'].format(text=translate[cache['lang']]['send_task_example'][10]),
            snippet['code-block'].format(text=translate[cache['lang']]['send_task_example'][1], lang=cache['lang']) if task_type == 'task' \
                else snippet['code-block'].format(text=translate[cache['lang']]['send_task_example'][11].format(date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")), lang=cache['lang']),
            snippet['italic'].format(text=translate[cache['lang']]['send_task_example'][2]) if task_type == 'task' \
                else snippet['italic'].format(text=translate[cache['lang']]['send_task_example'][12]),
        ]) + "\n\n"

        if task_type == 'task':
            text += translate[cache['lang']]['send_task_example'][6] + "\n" + \
                    snippet['bold'].format(text=translate[cache['lang']]['send_task_example'][7].replace("{bot}", BOT_INFO.username))

        if cache['addtask']:
            await try_to_delete(chat_id=message.chat.id, message_id=cache['addtask'])
        if task_type == 'task':
            key = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['send_task_example'][14], callback_data='generate_tasks'))
        elif task_type == 'giveaway':
            key = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['send_task_example'][13], callback_data='giveaways'))
        ADDTASK_MESS = await new_message(chat_id=message.chat.id, text=text, keyboard=key)
        cache['addtask'] = ADDTASK_MESS.message_id
        await set_cached_data(message.chat.id, cache)  ##write



@dp.message_handler(lambda message: message.reply_to_message and \
                    any(message.reply_to_message.text.startswith(translate[x]['send_task_example'][0]) for x in translate))
async def reply_to_task(message: types.Message, task_type='task') -> None:
    cache = await get_cached_data(message.chat.id)
    
    if not cache['process'] \
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
        if 'name' not in namespaces or 'desc' not in namespaces or ('link' not in namespaces and 'id' not in namespaces and task_type == 'task'):
            await send_error_message(message.chat.id, translate[cache['lang']]['send_task_example'][3])
            await try_to_delete(message.chat.id, message.message_id)
            return
        if task_match:    
            dict_task[lang] = {t[0].lower(): t[1] for t in task_match}  
            
            if task_type == 'task':
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
            elif task_type == 'giveaway':
                control = 0
                dict_task[lang]['check_id'] = BOT_INFO.id
                dict_task[lang]['link'] = 'https://t.me/' + BOT_INFO.username
                iso_date = 'T'.join(dict_task[lang]['date'].split())+'Z'
                dict_task[lang]['expire'] = int(datetime.fromisoformat(iso_date).astimezone(timezone.utc).timestamp())
                if dict_task[lang]['expire'] < now():
                    await send_error_message(message.chat.id, translate[cache['lang']]['send_task_example'][3] + f'\nError: now less then expire ({iso_date} less then {datetime.now().isoformat()})')
                    return
                
            if first:
                for key in dict_task[lang]:
                    dict_task[key] = dict_task[lang][key]
                first = False

    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['reply_to_task'][0], callback_data='main_menu'))

    dict_task['day'] = int(dict_task['day']) if 'day' in dict_task else 99999
    # Вызов новой функции для вставки задачи и обновления JSON
    dict_task['id'] = await insert_task(dict_task, check=control, expire=now()+dict_task['day']*86400, task_type=task_type, pool=POOL)  # передайте pool, который используется в insert_task_by_id
    if not dict_task['id']:
        await send_error_message(message.chat.id, translate[cache['lang']]['send_task_example'][3])
        return
    
    cache['task_id'] = dict_task['id']
    await try_to_delete(message.chat.id, message.message_id)
    if task_type == 'task':
        addm = await new_message(chat_id=message.chat.id, text=translate[cache['lang']]['send_task_example'][4], keyboard=keyboard)
        cache['addtask'] = addm.message_id
    await set_cached_data(message.chat.id, cache)
    return cache['task_id']

@dp.callback_query_handler(lambda c: c.data == 'delete_task')
async def delete_task_message(callback_query: types.CallbackQuery, task_type='task') -> None:
    message = callback_query.message
    cache = await get_cached_data(message.chat.id) ##cache
    if not cache['process']:
        return
    
    if not request_level(cache['right'], 5, message.chat.id): # 5 - delete_task
        return
    
    text = translate[cache['lang']]['delete_task'][0]
    keyboard = InlineKeyboardMarkup()
    tasks = await get_promotions(pool=POOL, task_type=task_type, all=True)
    for task in tasks:
        keyboard.add(InlineKeyboardButton(text=tasks[task]['name'], callback_data=f'delete_task_{tasks[task]["id"]}')) 
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['delete_task_message'][0], callback_data='main_menu'))
    await new_message(chat_id=message.chat.id, text=text, keyboard=keyboard)
 
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

