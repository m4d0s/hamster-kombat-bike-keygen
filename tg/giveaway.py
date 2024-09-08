import asyncio
import random
import re

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import (ChatNotFound,BadRequest)

from c_telegram import dp, BOT_INFO, bot, snippet, translate, POOL, request_level, db_config
from .message import new_message, try_to_delete, html_back_escape, try_to_edit
from .tasks import delete_task_message, send_task_example, reply_to_task, get_tasks_limit
from .cache import get_cached_data, set_cached_data
from .process import update_report

from generate import get_logger
from database import (get_promotions, get_full_checker, delete_user, get_user, format_remaining_time,
                      insert_task, get_checker_by_task_id, get_user_id, get_checker_by_user_id, now,
                      append_checker, delete_checker, get_tickets, append_ticket)

logger = get_logger()

async def wait_the_giveaway(giveaway_id, wait):
    logger.info(f'Giveaway #{giveaway_id} will be rolled in {format_remaining_time(now() + wait)}.')
    await asyncio.sleep(wait)
    await roll_the_dice_by_keys(giveaway_id)

def get_arg_link(id, arg='giveaway'):
    return f'https://t.me/{BOT_INFO.username}?start={arg}_{str(id)}'

# Giveaway funcs
@dp.callback_query_handler(lambda c: c.data == 'giveaways')
async def generate_giveaways_menu(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    
    giveaways = await get_promotions(pool=POOL, task_type='giveaway')
    all_giveaways = await get_promotions(pool=POOL, task_type='giveaway', all=True)
    participated = await get_checker_by_user_id(user_id=callback_query.message.chat.id, pool=POOL)
    participated = [int(giveaway) for giveaway in all_giveaways if int(giveaway) in participated]
    
    text = snippet['bold'].format(text=translate[cache['lang']]['generate_giveaways_menu'][4]) + '\n\n'
    text += snippet['italic'].format(text=translate[cache['lang']]['generate_giveaways_menu'][5].format(count=str(len(giveaways)))) + '\n'
    text += snippet['italic'].format(text=translate[cache['lang']]['generate_giveaways_menu'][6].format(count=str(len(participated)))) + '\n\n'
    text += snippet['bold'].format(text=translate[cache['lang']]['generate_giveaways_menu'][7]) + '\n'
    
    keyboard = InlineKeyboardMarkup()
    for giveaway in all_giveaways:
        now_time = now()
        prefix = '' if all_giveaways[giveaway]['expire'] > now_time else translate[cache['lang']]['generate_giveaways_menu'][11]
        keyboard.add(InlineKeyboardButton(text=all_giveaways[giveaway]['name'] + ' ' + prefix, callback_data=f'giveaway_{all_giveaways[giveaway]["id"]}'))
    if request_level(cache['right'], 2, callback_query.message.chat.id): # 2 - giveaways
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['generate_giveaways_menu'][8], callback_data='delete_giveaway'),
                     InlineKeyboardButton(text=translate[cache['lang']]['generate_giveaways_menu'][9], callback_data='add_giveaway'))
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['generate_giveaways_menu'][10], callback_data='main_menu'))

    TASK = await new_message(chat_id=callback_query.message.chat.id, text=text, keyboard=keyboard)
    cache['tasks']=TASK.message_id
    await try_to_delete(callback_query.message.chat.id, callback_query.message.message_id)
    
@dp.callback_query_handler(lambda c: c.data.startswith('giveaway_'))
async def process_callback_giveaway(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    giveaways = await get_promotions(task_type='giveaway', pool=POOL, all=True)
    tasks = await get_promotions(task_type='task', pool=POOL, all=True)
    used, all_t = await get_tasks_limit(callback_query.message.chat.id)
    promo_id = callback_query.data.split('_')[1]
    req = giveaways[promo_id]['link'].split(',') 
    unreq = [task for task in req if task not in tasks]
    req = [task for task in req if task not in unreq]
    
    if promo_id not in giveaways and str(promo_id) not in used:
        await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_giveaway'][8])
        return
    tickets = await get_tickets(user_id=callback_query.message.chat.id, start=giveaways[promo_id]['time'], end=giveaways[promo_id]['expire'], pool=POOL, tg=True)
    text = snippet['bold'].format(text=(translate[cache['lang']]['process_callback_giveaway'][1].format(name=giveaways[promo_id]['name'])))
    text += '\n\n' + translate[cache['lang']]['process_callback_giveaway'][2] + '\n'

    if giveaways[promo_id]['prizes']:
        prize_texts = []
        plus = ['link', 'name', 'owner_id']
        
        for i, prize in enumerate(giveaways[promo_id]['prizes']):
            prize_links = []
            # Преобразование значений в списки, разделённые знаком '+'
            for key in plus:
                prize[key] = prize.get(key, '').split("+") if '+' in prize.get(key, '') else [prize.get(key, '')]
                prize[key] = [x.strip() for x in prize[key]]
            
            # Определение максимальной длины списков
            max_len = max(len(prize[plus[0]]), len(prize[plus[1]]), len(prize[plus[2]]))
            
            # Добавляем пустые строки для списков, длина которых меньше максимальной
            for key in plus:
                while len(prize[key]) < max_len:
                    prize[key].append('')
            
            # Преобразуем данные для каждого приза
            for link, name, owner_id in zip(prize[plus[0]], prize[plus[1]], prize[plus[2]]):
                # Если ссылка начинается с '@', формируем полный URL
                if link.startswith('@'):
                    link = f'https://t.me/{link[1:]}'
                
                # Если есть ссылка, формируем строку с названием и ссылкой
                if link:
                    prize_links.append(snippet['link'].format(text=name, link=link))
                else:
                    prize_links.append(name)
            
            # Объединяем все призы для текущего места через '+'
            combined_prizes = ' + '.join(prize_links)
            
            # Формируем строку с информацией о призе
            if now() > giveaways[promo_id]['expire']:
                user = await get_user(user_id=prize['winner_id'], pool=POOL, tg=False)
                username = '@' + user.get('tg_username', '-') if user and user.get('tg_username', '-') != '-' else snippet['code'].format(text=str(user.get('tg_id', -1)))
                prize_text = f"#{i+1} {combined_prizes}\n\t{translate[cache['lang']]['process_callback_giveaway'][11]} " + username
            else:
                prize_text = f"#{i+1} {combined_prizes}\n\t{translate[cache['lang']]['process_callback_giveaway'][10]}{' + '.join(prize['owner_id'])}"
            
            prize_texts.append(prize_text)

        
        text += snippet['quote'].format(text='\n'.join(prize_texts))
    else:
        text += '\n' + snippet['italic'].format(text=translate[cache['lang']]['process_callback_giveaway'][6])

    text += '\n\n' + giveaways[promo_id]['desc']
    text += '\n\n' + translate[cache['lang']]['process_callback_giveaway'][5].format(count=len(tickets)) \
            + '\n' + snippet['italic'].format(text=translate[cache['lang']]['process_callback_giveaway'][3])\
            + '\n' + snippet['bold'].format(text=translate[cache['lang']]['process_callback_giveaway'][7]
                                    .format(time=format_remaining_time(giveaways[promo_id]['expire'])))
    keyboard = InlineKeyboardMarkup()
    if all(str(x) in used for x in req if x != ''):
        if str(promo_id) in used:
            keyboard.add(InlineKeyboardButton(text="✅ " + translate[cache['lang']]['process_callback_giveaway'][12], callback_data=f'delete_checker_giveaway_{promo_id}'))
        else:
            keyboard.add(InlineKeyboardButton(text="" + translate[cache['lang']]['process_callback_giveaway'][12], callback_data=f'set_checker_giveaway_{promo_id}'))
    else:
        for x in req:
            if str(x) not in used and str(x) in tasks:
                keyboard.add(InlineKeyboardButton(text="🔑 " + tasks[str(x)].get('name', f'task_id = {x}'), url=get_arg_link(x, arg='task')))
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_giveaway'][14], callback_data=callback_query.data))
    if request_level(cache['right'], 2, callback_query.message.chat.id): # 2 - giveaways
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_giveaway'][13], callback_data=f'setup_tasks_for_giveaway_{promo_id}'),
        InlineKeyboardButton(text=translate[cache['lang']]['process_callback_giveaway'][9], callback_data=f'add_prize_{promo_id}'))
    if request_level(cache['right'], 9, callback_query.message.chat.id): # 9 - debug
        keyboard.add(InlineKeyboardButton(text='🪭 Make test roll', callback_data=f'roll_giveaway_{promo_id}'))
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_giveaway'][4], callback_data='giveaways'))
    TASK = await new_message(chat_id=callback_query.message.chat.id, text=text, keyboard=keyboard)
    cache['tasks']=TASK.message_id
    await try_to_delete(callback_query.message.chat.id, callback_query.message.message_id)

@dp.callback_query_handler(lambda c: '_checker_giveaway_' in c.data)
async def set_checker_giveaway(callback_query: types.CallbackQuery) -> None:
    actions = ['set', 'delete']
    promo = callback_query.data.split('_')[3]
    action = callback_query.data.split('_')[0]
    message = callback_query.message
    if action not in actions:
        return
    if action == actions[0]:
        await append_checker(callback_query.message.chat.id, int(promo), pool=POOL)
    elif action == actions[1]:
        await delete_checker(callback_query.message.chat.id, int(promo), pool=POOL)
    
    keyboard = callback_query.message.reply_markup
    for i in range(len(keyboard.inline_keyboard)):
        for j in range(len(keyboard.inline_keyboard[i])):
            button = keyboard.inline_keyboard[i][j]
            if callback_query.data in button.callback_data:
                if action == actions[0]:
                    button = InlineKeyboardButton(text="✅ " + button.text, callback_data=f'{actions[1]}_checker_giveaway_{promo}')
                elif action == actions[1]:
                    button = InlineKeyboardButton(text=button.text.replace('✅ ', ''), callback_data=f'{actions[0]}_checker_giveaway_{promo}')
                keyboard.inline_keyboard[i][j] = button
                await try_to_edit(message.html_text, message.chat.id, message.message_id, keyboard=keyboard, format=False)
                return

@dp.callback_query_handler(lambda c: c.data == 'delete_giveaway')
async def delete_giveaway(callback_query: types.CallbackQuery) -> None:
    await delete_task_message(callback_query, task_type='giveaway')

@dp.callback_query_handler(lambda c: c.data.startswith('roll_giveaway_'))
async def roll_early_dice(callback_query: types.CallbackQuery) -> None:
    await roll_the_dice_by_keys(int(callback_query.data.split('_')[2]))

async def roll_the_dice_by_keys(giveaway_id:int) -> None:
    joined, fill_joined = await get_checker_by_task_id(giveaway_id, pool=POOL), []
    promo = await get_promotions(task_type='giveaway', pool=POOL, all=True)
    curr = promo[str(giveaway_id)]
    winners, tickets = [], []
    for user_id in joined:
        user = await get_user(user_id, pool=POOL, tg=False)
        if user:
            fill_joined.append(user_id)
            tickets_of_user = await get_tickets(user_id, start=curr['time'], end=curr['expire'], pool=POOL)
            tickets.extend(tickets_of_user)
            continue
    joined = fill_joined
    tickets.sort(key=lambda x: x['time'])
    if len(tickets) == 0:
        return
    
    index = 0
    over_prizes = len(curr['prizes']) > len(joined)
    while len(winners) < len(curr['prizes']):
        tg_user = None
        while not tg_user:
            winner = random.choice(tickets)
            win_user = await get_user(winner['user_id'], pool=POOL, tg=False)
            if win_user in winners and not over_prizes:
                continue
            winners.append(winner['user_id'])
            try:
                tg_user = await bot.get_chat_member(chat_id=win_user['tg_id'], user_id=win_user['tg_id'])
            except (ChatNotFound, BadRequest):
                await delete_user(win_user['tg_id'], pool=POOL)
                tickets = [t for t in tickets if t['user_id'] != winner['user_id']]
                continue
        cache = await get_cached_data(win_user['tg_id'])
        curr['prizes'][index]['winner_id'] = winner['user_id']
        text = snippet['bold'].format(text=translate[cache['lang']]['roll_the_dice_by_keys'][0]) + '\n\n'
        text += snippet['italic'].format(text=translate[cache['lang']]['roll_the_dice_by_keys'][1].format(prize=curr['prizes'][index]['name'])) + '\n'
        text += snippet['italic'].format(text=translate[cache['lang']]['roll_the_dice_by_keys'][2].format(sponsors=curr['prizes'][index]['owner_id'])) + '\n'
        keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(text=curr['name'], callback_data=f"giveaway_{curr['id']}"))
        await new_message(chat_id=win_user['tg_id'], text=text, keyboard=keyboard)
        index += 1
    
    await insert_task(curr, task_type='giveaway', pool=POOL)




@dp.callback_query_handler(lambda c: c.data == 'add_giveaway')
async def add_giveaway(callback_query: types.CallbackQuery) -> None:
    # cache = await get_cached_data(callback_query.message.chat.id) ##cache
    await send_task_example(callback_query.message, task_type='giveaway')
    
@dp.message_handler(lambda message: message.reply_to_message and \
                    any(message.reply_to_message.text.startswith(translate[x]['send_task_example'][10]) for x in translate))
async def setup_tasks_requirements(message: types.Message, giveaway:int=None) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    text = snippet['bold'].format(text=translate[cache['lang']]['setup_tasks_requirements'][0])
    id = await reply_to_task(message, 'giveaway') if not giveaway else None
    g_id = giveaway or id
    if not g_id:
        return
    cache['task_id'] = g_id
    giveaways = await get_promotions(task_type='giveaway', pool=POOL, all=True)
    contains = giveaways[str(g_id)].get('link', [])
    if isinstance(contains, str):
        contains = contains.split(',')
    keyboard = InlineKeyboardMarkup()
    tasks = await get_promotions(task_type='task', pool=POOL)
    for task in tasks:
        mark = '✅ ' if task in contains else ''
        arg = 'add' if task not in contains else 'delete'
        keyboard.add(InlineKeyboardButton(text=mark + tasks[task]['name'], callback_data=f'{arg}_giveaway_task_{cache["task_id"]}_{task}'))
        
    if not giveaway:
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['setup_tasks_requirements'][1], callback_data='reply_to_giveaway'))
    else:
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['setup_tasks_requirements'][2], callback_data=f'giveaway_{giveaway}'))
    await new_message(chat_id=message.chat.id, text=text, keyboard=keyboard)
    await set_cached_data(message.chat.id, cache)
    
@dp.callback_query_handler(lambda c: c.data == 'reply_to_giveaway')
async def send_prize_example(call: types.CallbackQuery) -> None:
    message = call.message
    cache = await get_cached_data(message.chat.id) ##cache
    text = snippet['bold'].format(text=translate[cache['lang']]['reply_to_giveaway'][0])
    text += '\n' + snippet['block'].format(text=translate[cache['lang']]['reply_to_giveaway'][1])
    await new_message(chat_id=message.chat.id, text=text)
    await try_to_delete(message.chat.id, message.message_id)
    await set_cached_data(message.chat.id, cache)
    
@dp.message_handler(lambda message: message.reply_to_message and \
                    any(message.reply_to_message.text.startswith(translate[x]['reply_to_giveaway'][0]) for x in translate))
async def reply_to_prizes(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    promos = await get_promotions(pool=POOL, task_type='giveaway')
    curr = promos[str(cache['task_id'])]
    # Регулярное выражение для поиска паттернов
    pattern = r'(.+?) \((.*?)\)(?: \[(.*?)\])?'

    # Найти все совпадения
    text = html_back_escape(message.text)
    matches = re.findall(pattern, text)
    
    prizes = curr['prizes'] if 'prizes' in curr else []
    for i, match in enumerate(matches):
        prizes.append({'name': match[0], 
                       'owner_id': match[1], 
                       'winner_id':  await get_user_id(db_config['DEV_ID'], pool=POOL),
                       'promo_id': cache['task_id'], 
                       'place': len(prizes) + 1, 
                       'link': match[2]})
    curr['prizes'] = prizes
    
    id = await insert_task(curr, task_type='giveaway', pool=POOL)
    await try_to_delete(message.chat.id, message.message_id)
    await try_to_delete(message.chat.id, message.reply_to_message.message_id)
    
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['reply_to_task'][0], callback_data='main_menu'))
    addm = await new_message(chat_id=message.chat.id, text=translate[cache['lang']]['send_task_example'][4], keyboard=keyboard)
    cache['addtask'] = addm.message_id
    await set_cached_data(message.chat.id, cache)
    
    text = {x:translate[x]['reply_to_prizes'][0].format(name=curr[x]['name']) for x in translate}
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['reply_to_prizes'][1], url=get_arg_link(id, arg='giveaway')))
    await update_report(chat_id=message.chat.id, text=text, keyboard=keyboard, warning=True)
    
    asyncio.create_task(wait_the_giveaway(cache['task_id'], curr['expire'] - now()))



@dp.callback_query_handler(lambda c: c.data.startswith('setup_tasks_for_giveaway_'))
async def setup_tasks_for_giveaway(callback_query: types.CallbackQuery) -> None:
    message = callback_query.message
    cache = await get_cached_data(message.chat.id) ##cache
    cache['task_id'] = int(callback_query.data.split('_')[4])
    await set_cached_data(message.chat.id, cache)
    await setup_tasks_requirements(message, giveaway=cache['task_id'])

@dp.callback_query_handler(lambda c: '_giveaway_task_' in c.data)
async def change_giveaway_tasks(callback_query: types.CallbackQuery) -> None:
    all_actions = ['add', 'delete']
    giveaway_id, task_id = callback_query.data.split('_')[3], callback_query.data.split('_')[4]
    action = callback_query.data.split('_')[0]
    message = callback_query.message
    promo = await get_promotions(task_type='all', pool=POOL, all=True)
    curr_g, curr_t = promo[str(giveaway_id)], promo.get(task_id, {})
    
    keyboard = message.reply_markup
    if action not in all_actions:
        return
    for i in range(len(keyboard.inline_keyboard)):
        for j in range(len(keyboard.inline_keyboard[i])):
            button = keyboard.inline_keyboard[i][j]
            if callback_query.data in button.callback_data:
                tasks = curr_g.get('link', [])
                if isinstance(tasks, str):
                    tasks = tasks.split(',')
                    
                if action == all_actions[0] and curr_t:
                    button = InlineKeyboardButton(text='✅ ' + button.text, callback_data=button.callback_data.replace('add', 'delete'))
                    keyboard.inline_keyboard[i][j] = button
                    tasks.append(task_id)
                elif action == all_actions[1] and curr_t:
                    button = InlineKeyboardButton(text=button.text.replace('✅ ', ''), callback_data=button.callback_data.replace('delete', 'add'))
                    keyboard.inline_keyboard[i][j] = button
                    tasks.remove(task_id)
                elif not curr_t:
                    keyboard.inline_keyboard[i].pop(j)
                for item in tasks:
                    if not item.isdigit():
                        tasks.remove(item)
                curr_g['link'] = ','.join(set(tasks))
                await insert_task(curr_g, task_type='giveaway', pool=POOL)
                await try_to_edit(message.html_text, message.chat.id, message.message_id, keyboard=keyboard)
                return



async def append_tickets_to(checker_id:int, user_id:int, tickets:int, pool, giveaway=True):
    for i in range(tickets):
        await append_ticket(user_id=user_id, checker_id=checker_id, pool=pool)
    promo = await get_promotions(task_type='all', pool=pool, all=True)
    check = await get_full_checker(checker_id, pool=pool)
    gv = promo.get(str(check['promo_id']), {})
    # giveaway_id = check['task_id']
    if not giveaway:
        append_checker(user_id, checker_id, count=tickets, pool=pool)
        return
    
    tasks = [promo.get(str(giveaway_id), {}) for giveaway_id in gv['link'].split(',') if giveaway_id.isdigit()]
    for task in tasks+ [gv]:
        if task:
            await append_checker(user_id, task['id'], count=tickets, pool=pool)
    
@dp.callback_query_handler(lambda c: c.data.startswith('add_prize_'))
async def add_prize(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    task_id = int(callback_query.data.split('_')[2])
    cache['task_id'] = task_id
    await set_cached_data(callback_query.message.chat.id, cache)
    await send_prize_example(callback_query)
    