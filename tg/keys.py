import aiohttp

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import InvalidQueryID

from .message import send_error_message, new_message, try_to_delete, try_to_edit
from .cache import get_cached_data, set_cached_data
from .process import update_loadbar
from .tasks import get_key_limit
from .giveaway import append_tickets_to

from c_telegram import dp, BOT_INFO, bot, snippet, translate, POOL, db_config, json_config
from database import get_last_user_key, get_promotions, relative_time, get_full_checkers, now, insert_key_generation
from generate import get_logger

logger = get_logger()

def get_arg_link(id, arg='giveaway'):
    return f'https://t.me/{BOT_INFO.username}?start={arg}_{str(id)}'

# keys funcs
@dp.callback_query_handler(lambda c: c.data == 'generate_menu')
async def process_callback_generate_menu(callback_query: types.CallbackQuery) -> None:
    message = callback_query.message
    cache = await get_cached_data(message.chat.id)  # cache
    user_limit_keys, global_limit_keys = await get_key_limit(user=message.chat.id)
    
    if cache.get('welcome'):
        await try_to_delete(chat_id=message.chat.id, message_id=cache['welcome'])
        cache['welcome'] = None
    
    if user_limit_keys >= global_limit_keys:
        await send_error_message(message.chat.id, translate[cache['lang']]['process_callback_generate_menu'][4])
        return
    
    text = (
        snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_menu'][0] + ':') + "\n"
        f"\n{snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_menu'][1])}" +
        f" {global_limit_keys - user_limit_keys}/{global_limit_keys}\n\n"
        + snippet['italic'].format(text=translate[cache['lang']]['process_callback_generate_menu'][2])
    )

    keyboard = InlineKeyboardMarkup()
    
    # Create a list of buttons from the configuration
    buttons = [InlineKeyboardButton(text=json_config['EVENTS'][type]['NAME'], callback_data=f'generate_key_{type}')\
                for type in json_config['EVENTS'] if not json_config['EVENTS'][type]['DISABLED']]
    
    # Add buttons two per row
    for i in range(0, len(buttons), 2):
        keyboard.add(*buttons[i:i + 2])
    
    # Add the main menu button in a separate row
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_menu'][3], callback_data='main_menu'))

    WELCOME_MESS = await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard)
    cache['welcome'] = WELCOME_MESS.message_id
    
    await set_cached_data(message.chat.id, cache)  # write

@dp.callback_query_handler(lambda c: c.data.startswith('generate_key_'))
async def process_callback_generate_key(callback_query: types.CallbackQuery) -> None:
    used, all = await get_key_limit(user=callback_query.message.chat.id)
    limit = all - used
    cache = await get_cached_data(callback_query.message.chat.id)
    
    text = (
        snippet['bold'].format(text=translate[cache['lang']]['process_callback_generate_key'][0]) + "\n\n"
        + snippet['italic'].format(text=translate[cache['lang']]['process_callback_generate_key'][1])
    )
    
    keyboard = InlineKeyboardMarkup(row_width=4)
    buttons = [InlineKeyboardButton(text=str(i + 1), callback_data=f'countkey_{i + 1}_{callback_query.data.split("_")[2]}') \
                for i in range(min(4, limit))]
    keyboard.add(*buttons)
    keyboard.add(InlineKeyboardButton(text=translate[cache['lang']]['process_callback_generate_key'][2], callback_data='generate_menu'))

    mess = await new_message(text=text, chat_id=callback_query.message.chat.id, keyboard=keyboard)
    if cache.get('welcome'):
        await try_to_delete(chat_id=callback_query.message.chat.id, message_id=cache['welcome'])
        cache['welcome'] = mess.message_id
    await set_cached_data(callback_query.message.chat.id, cache)

@dp.callback_query_handler(lambda c: c.data.startswith('countkey_'))
async def generate_key(callback_query: types.CallbackQuery) -> None:
    message = callback_query.message
    cache = await get_cached_data(message.chat.id)  # cache
    try:
        await bot.answer_callback_query(callback_query.id)
    except InvalidQueryID:
        pass
    
    count = int(callback_query.data.split('_')[1])
    game_key = callback_query.data.split('_')[2]
    
    last_user_key = await get_last_user_key(message.chat.id, pool=POOL)
    user_limit_keys, global_limit_keys = await get_key_limit(user=message.chat.id)

    def can_generate_key():
        return not last_user_key or abs(relative_time(last_user_key['time'])) > db_config['DELAY'] or json_config['DEBUG']

    if can_generate_key() and cache.get('process'):
        if user_limit_keys < global_limit_keys:
            mins = json_config['EVENTS'][game_key]['EVENTS_DELAY'][0] * 15 // 60000 // 2 * count
            stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['generate_key'][7], 
                                                                          callback_data="main_menu"))
            LOADING_MESS = await new_message(
                text=translate[cache['lang']]['generate_key'][0].format(mins=mins), 
                chat_id=message.chat.id, 
                keyboard=stop_button
            )
            cache['loading'] = LOADING_MESS.message_id
            await set_cached_data(message.chat.id, cache)
            try:
                async with aiohttp.ClientSession() as session:
                    key = await update_loadbar(message.chat.id, game_key, session, count)
                await try_to_edit(
                    text=message.html_text, 
                    chat_id=message.chat.id, 
                    message_id=message.message_id, 
                    keyboard=stop_button
                )
                
                key_text = (
                    '\n'.join([snippet['bold'].format(text=game_key) + ": " + snippet['code'].format(text=k) for k in key if k])
                    if key else translate[cache['lang']]['generate_key'][2]
                )
                # for k in key:
                #     await insert_key_generation(user_id=message.chat.id, key=k, key_type=game_key, pool=POOL)
                
                giveaways = await get_promotions(task_type='giveaway', pool=POOL)
                if giveaways and key:
                    give_txt = "\n\n" + snippet['bold'].format(text=translate[cache['lang']]['generate_key'][8])
                    checkers = await get_full_checkers(user_id=message.chat.id, pool=POOL)
                    giveaways_ids = [int(x) for x in giveaways]

                    for check in checkers:
                        if checkers[check]['promo_id'] in giveaways_ids:
                            gv_id = str(checkers[check]['promo_id']) ; giveaways_ids.remove(checkers[check]['promo_id'])
                            give_txt += f"\n{snippet['link'].format(text=giveaways[str(gv_id)][cache['lang']]['name'], link=get_arg_link(int(gv_id)))}: {len(key)} 🎟"
                            await append_tickets_to(int(check), message.chat.id, len(key), pool=POOL)   
                            
                    for gv_id in giveaways_ids:
                        give_txt += f"\n{snippet['link'].format(text=giveaways[str(gv_id)][cache['lang']]['name'], link=get_arg_link(gv_id))} ({translate[cache['lang']]['generate_key'][9]})" \
                                    if giveaways[str(gv_id)]['expire'] > now() > giveaways[str(gv_id)]['time'] else ''
                                    
                    key_text += give_txt
                
                stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['generate_key'][7], 
                                                                              callback_data="main_menu"))
                LOADING_MESS = await new_message(
                    text=translate[cache['lang']]['generate_key'][3].format(key=key_text), 
                    chat_id=message.chat.id, 
                    keyboard=stop_button
                )
            except Exception as e:
                LOADING_MESS = await send_error_message(message.chat.id, translate[cache['lang']]['generate_key'][2], e)
        else:
            text = translate[cache['lang']]['generate_key'][4]
            if cache.get('loading'):
                await try_to_delete(chat_id=message.chat.id, message_id=cache['loading'])
            LOADING_MESS = await new_message(text=text, chat_id=message.chat.id)
        
        cache['process'] = True
        await set_cached_data(message.chat.id, cache)  # write    
        if cache.get('loading'):
            await try_to_delete(chat_id=message.chat.id, message_id=cache['loading'])
        if LOADING_MESS:
            cache['loading'] = LOADING_MESS.message_id
        await set_cached_data(message.chat.id, cache)  # write
    elif not can_generate_key():
        text = translate[cache['lang']]['generate_key'][5].format(
            last_user_key=snippet['code'].format(text=last_user_key['key']),
            relative_time=db_config['DELAY'] - relative_time(last_user_key['time'])
        )
        LOADING_MESS = await new_message(text=text, chat_id=message.chat.id)
        cache['loading'] = LOADING_MESS.message_id
        await set_cached_data(message.chat.id, cache)  # write
    elif not cache.get('process'):
        text = translate[cache['lang']]['generate_key'][6]
        ERROR_MESS = await send_error_message(message.chat.id, text, Exception('Process not completed'))
        cache['error'] = ERROR_MESS.message_id
        await set_cached_data(message.chat.id, cache)  # write
            
    await set_cached_data(message.chat.id, cache)  # write
