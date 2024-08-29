import asyncio
import random
import re

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import (ChatNotFound,BadRequest)

from c_telegram import dp, BOT_INFO, bot, snippet, translate, POOL, request_level, db_config
from .message import new_message, try_to_delete, html_back_escape
from .tasks import delete_task_message, send_task_example, reply_to_task
from .cache import get_cached_data, set_cached_data

from generate import get_logger
from database import (get_promotions, get_all_user_keys_24h, delete_user, get_user, format_remaining_time,
                      insert_task, get_checker_by_task_id, get_user_id, get_checker_by_user_id, now)

logger = get_logger()

async def wait_the_giveaway(giveaway_id, wait):
    await asyncio.sleep(wait)
    await roll_the_dice_by_keys(giveaway_id)

def get_giveaway_link(giveaway_id):
    return f'https://t.me/{BOT_INFO.username}?start=giveaway_{giveaway_id}'

# Giveaway funcs
@dp.callback_query_handler(lambda c: c.data == 'giveaways')
async def generate_giveaways_menu(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    
    giveaways = await get_promotions(pool=POOL, task_type='giveaway')
    all_giveaways = await get_promotions(pool=POOL, task_type='giveaway', all=True)
    participated = await get_checker_by_user_id(user_id=callback_query.from_user.id, pool=POOL)
    participated = [int(giveaway) for giveaway in all_giveaways if int(giveaway) in participated]
    
    text = snippet['bold'].format(text=translate[cache['lang']]['generate_giveaways_menu'][4]) + '\n\n'
    text += snippet['italic'].format(text=translate[cache['lang']]['generate_giveaways_menu'][5].format(count=str(len(giveaways)))) + '\n'
    text += snippet['italic'].format(text=translate[cache['lang']]['generate_giveaways_menu'][6].format(count=str(len(participated)))) + '\n\n'
    text += snippet['bold'].format(text=translate[cache['lang']]['generate_giveaways_menu'][7]) + '\n'
    
    keyboard = InlineKeyboardMarkup()
    for giveaway in giveaways:
        keyboard.add(InlineKeyboardButton(text=giveaways[giveaway]['name'], callback_data=f'giveaway_{giveaways[giveaway]["id"]}'))
    if request_level(cache['right'], 2, callback_query.message.chat.id): # 2 - giveaways
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['generate_giveaways_menu'][8], callback_data='delete_giveaway'))
        keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['generate_giveaways_menu'][9], callback_data='add_giveaway'))
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['generate_giveaways_menu'][10], callback_data='main_menu'))

    TASK = await new_message(chat_id=callback_query.message.chat.id, text=text, keyboard=keyboard)
    cache['tasks']=TASK.message_id
    await try_to_delete(callback_query.message.chat.id, callback_query.message.message_id)
    
    
    # await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['generate_giveaways_menu'][0])
    
@dp.callback_query_handler(lambda c: c.data.startswith('giveaway_'))
async def process_callback_giveaway(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    promo = await get_promotions(task_type='giveaway', pool=POOL, all=True)
    checkers = await get_checker_by_user_id(user_id=callback_query.from_user.id, pool=POOL)
    promo_id = callback_query.data.split('_')[1]
    if promo_id not in promo and int(promo_id) not in checkers:
        await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_giveaway'][8])
        return
    tickets = await get_all_user_keys_24h(callback_query.from_user.id, pool=POOL, start=promo[promo_id]['time'], end=promo[promo_id]['expire'])
    text = snippet['bold'].format(text=(translate[cache['lang']]['process_callback_giveaway'][1].format(name=promo[promo_id]['name'])))
    text += '\n\n' + translate[cache['lang']]['process_callback_giveaway'][2] + '\n' +\
            snippet['quote'].format(text=('\n'.join(f"#{i+1} {prize['name']} ({prize['winner_id'] if prize['winner_id'] else prize['owner_id']})" \
            for i, prize in enumerate(promo[promo_id]['prizes'])))) if promo[promo_id]['prizes']\
            else '\n' + snippet['italic'].format(text=translate[cache['lang']]['process_callback_giveaway'][6])
    text += '\n\n' + promo[promo_id]['desc']
    text += '\n\n' + translate[cache['lang']]['process_callback_giveaway'][5].format(count=len(tickets)) \
            + '\n' + snippet['italic'].format(text=translate[cache['lang']]['process_callback_giveaway'][3])\
            + '\n' + snippet['bold'].format(text=translate[cache['lang']]['process_callback_giveaway'][7].format(time=format_remaining_time(promo[promo_id]['expire'])))
    keyboard = InlineKeyboardMarkup()\
                .add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_giveaway'][4], callback_data='giveaways'))
    TASK = await new_message(chat_id=callback_query.message.chat.id, text=text, keyboard=keyboard)
    cache['tasks']=TASK.message_id
    await try_to_delete(callback_query.message.chat.id, callback_query.message.message_id)
    
    
    
    
    # await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_giveaway'][0])
    
    
@dp.callback_query_handler(lambda c: c.data == 'delete_giveaway')
async def delete_giveaway(callback_query: types.CallbackQuery) -> None:
    await delete_task_message(callback_query, task_type='giveaway')

async def roll_the_dice_by_keys(giveaway_id):
    joined = await get_checker_by_task_id(giveaway_id, pool=POOL)
    promo = await get_promotions(task_type='giveaway', pool=POOL, all=True)
    curr = promo[str(giveaway_id)]
    tickets = []
    for user_id in joined:
        user = await get_user(user_id, pool=POOL, tg=False)
        keys = await get_all_user_keys_24h(user['tg_id'], start=curr['time'], end=curr['expire'], pool=POOL)
        for key in keys:
            tickets.append([key[1], user['tg_id']])
    tickets.sort(key=lambda x: x[0])
    if len(tickets) == 0:
        return
    for prize in range(len(curr['prizes'])):
        tg_user = None
        while not tg_user:
            winner = random.choice(tickets)
            win_user = await get_user(winner[1], pool=POOL)
            try:
                tg_user = bot.get_chat_member(chat_id=win_user['tg_id'], user_id=win_user['tg_id'])
            except (ChatNotFound, BadRequest):
                await delete_user(win_user['tg_id'], pool=POOL)
                for i in range(len(tickets)):
                    if tickets[i][1] == winner[1]:
                        tickets.pop(i)
                continue
        cache = await get_cached_data(win_user['tg_id'])
        curr['prizes'][prize]['winner_id'] = await get_user_id(winner[1], pool=POOL)
        text = snippet['bold'].format(text=translate[cache['lang']]['roll_the_dice_by_keys'][0]) + '\n\n'
        text += snippet['italic'].format(text=translate[cache['lang']]['roll_the_dice_by_keys'][1]) + '\n'
        text += snippet['italic'].format(text=translate[cache['lang']]['roll_the_dice_by_keys'][2]) + '\n'
        
        await new_message(chat_id=winner[1], text=text)
    
    await insert_task(curr, task_type='giveaway', pool=POOL)

@dp.callback_query_handler(lambda c: c.data == 'add_giveaway')
async def add_giveaway(callback_query: types.CallbackQuery) -> None:
    # cache = await get_cached_data(callback_query.message.chat.id) ##cache
    await send_task_example(callback_query.message, task_type='giveaway')

@dp.message_handler(lambda message: message.reply_to_message and \
                    any(message.reply_to_message.text.startswith(translate[x]['send_task_example'][10]) for x in translate))
async def reply_to_giveaway(message: types.Message) -> None:
    cache = await get_cached_data(message.from_user.id) ##cache
    id = await reply_to_task(message, task_type='giveaway')
    if id:
        text = snippet['bold'].format(text=translate[cache['lang']]['reply_to_giveaway'][0])
        text += '\n' + snippet['block'].format(text=translate[cache['lang']]['reply_to_giveaway'][1])
        cache['task_id'] = id
        await new_message(chat_id=message.from_user.id, text=text)
        await set_cached_data(message.from_user.id, cache)

@dp.message_handler(lambda message: message.reply_to_message and \
                    any(message.reply_to_message.text.startswith(translate[x]['reply_to_giveaway'][0]) for x in translate))
async def reply_to_prizes(message: types.Message) -> None:
    cache = await get_cached_data(message.from_user.id) ##cache
    promos = await get_promotions(pool=POOL, task_type='giveaway')
    curr = promos[str(cache['task_id'])]
    # Регулярное выражение для поиска паттернов
    pattern = r'(.+?) \(@(.*?)\)(?: \[(.*?)\])?'

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
    
    await insert_task(curr, task_type='giveaway', pool=POOL)
    await try_to_delete(message.chat.id, message.message_id)
    await try_to_delete(message.chat.id, message.reply_to_message.message_id)
    
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['reply_to_task'][0], callback_data='main_menu'))
    addm = await new_message(chat_id=message.chat.id, text=translate[cache['lang']]['send_task_example'][4], keyboard=keyboard)
    cache['addtask'] = addm.message_id
    await set_cached_data(message.from_user.id, cache)
    asyncio.create_task(wait_the_giveaway(cache['task_id'], curr['expire'] - now()))
    
    