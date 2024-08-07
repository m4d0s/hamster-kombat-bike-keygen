import logging
import asyncio
import aiohttp
import json
import re

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from aiogram.utils.exceptions import MessageNotModified, MessageToDeleteNotFound, InvalidQueryID, ChatNotFound, BotBlocked

from generate import generate_loading_bar, get_key, MAX_LOAD
from database import (log_timestamp, insert_key_generation, get_last_user_key, get_all_dev, get_all_user_ids,
                      get_unused_key_of_type, relative_time, get_all_user_keys_24h, insert_user, format_remaining_time, 
                      delete_user, get_pool, get_all_refs)

# Load configuration
with open('config.json') as f:
    json_config = json.load(f)

API_TOKEN = json_config['API_TOKEN']
DELAY = json_config['DELAY']
DEBUG_KEY = json_config['DEBUG_KEY']
POOL = None

logging.basicConfig(level=logging.INFO, filename='logs/'+log_timestamp()+'.log', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

WELCOME = None
LOADING = None
REPORT = None
process_completed = False


def html_back_escape(text):
    return str(text).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')


async def new_message(message: str, chat_id: int):
    return await bot.send_message(text=message, chat_id=chat_id, parse_mode=ParseMode.HTML)


async def update_loadbar(message: types.Message):
    global process_completed, loading
    while not process_completed:
        text, loading = generate_loading_bar()
        try:
            await bot.edit_message_text("Generating key...\n" + text, message.chat.id, message.message_id, parse_mode=ParseMode.HTML)
        except MessageNotModified:
            pass
        await asyncio.sleep(1)
    text, loading = generate_loading_bar(loading=MAX_LOAD)
    await bot.edit_message_text("Generating key...\n" + text, message.chat.id, message.message_id, parse_mode=ParseMode.HTML)


async def try_to_delete(chat_id, message_id):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except MessageToDeleteNotFound:
        pass


async def send_report_example(message: types.Message):
    example = "[Buttons1][https://google.com]\n[Buttons2][https://t.me/hk_bike_bot]"
    global REPORT
    REPORT = await new_message("Reply a message to report on other users with buttons\n\n" + example, message.chat.id)
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)


@dp.message_handler(commands=['report'])
async def mass_report(message: types.Message):
    devs = await get_all_dev(pool=POOL)
    if message.from_user.id not in devs:
        return
    await send_report_example(message)


@dp.message_handler(lambda message: message.reply_to_message and message.reply_to_message.message_id == REPORT.message_id)
async def report(message: types.Message):
    devs = await get_all_dev(pool=POOL)
    if message.from_user.id not in devs:
        return

    keyboard = InlineKeyboardMarkup()
    urls = re.findall(r'\[(.+?)\]\[(.+?)\]', message.text)
    text_without_buttons = re.sub(r'\[(.+?)\]\[(.+?)\]', '', message.html_text).strip()

    if urls:
        for url_name, url in urls:
            button = InlineKeyboardButton(text=url_name, url=url)
            keyboard.add(button)

    await send_to_all_users(text_without_buttons, keyboard)


async def send_to_all_users(text: str, keyboard: InlineKeyboardMarkup):
    user_ids = await get_all_user_ids(pool=POOL)
    tasks = [send_message_to_user(user_id, text, keyboard) for user_id in user_ids]
    await asyncio.gather(*tasks)


async def send_message_to_user(user_id, text: str, keyboard: InlineKeyboardMarkup):
    try:
        await bot.send_message(chat_id=user_id, text=html_back_escape(text), parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=keyboard)
    except ChatNotFound:
        logging.warning(f'Chat with user {user_id} not found')
        await delete_user(user_id, pool=POOL)
    except BotBlocked:
        logging.warning(f'Chat with user {user_id} blocked')
        await delete_user(user_id, pool=POOL)


async def update_welcome_message(message: types.Message, today_keys):
    global WELCOME
    inline_btn_generate = InlineKeyboardButton('Generate Key', callback_data='generate_menu')
    inline_kb = InlineKeyboardMarkup().add(inline_btn_generate)
    limit_keys = json_config['COUNT'] + len(await get_all_refs(pool=POOL, user_id=message.chat.id))

    if WELCOME:
        await try_to_delete(chat_id=message.chat.id, message_id=WELCOME.message_id)

    text =  f"<b>I'm Hamster Bike Keygen Bot! (Beta)</b>\nYour id: <code>{message.chat.id}</code>\n"
    text += f"Your reflink: https://t.me/tonfastbot?start={message.chat.id}\n<i>Every ref get you +1 attempt</i>\n\n<b>Today you generate:</b>\n"
    if today_keys:
        text += '\n'.join([f'<b>{type}:</b> <code>{key}</code> ({format_remaining_time(key_time)})' for key, key_time, type in today_keys])
    else:
        text += '\n<i>No keys generated today</i>'
    text += f'\n\n<b>Your attempts today:</b> {limit_keys - len(today_keys) if today_keys else limit_keys}/{limit_keys}'
    text += "\n\n<i>!!! Bot now in beta version, on any bug or error please contact technical support or just try again</i>"

    WELCOME = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=inline_kb)
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)


@dp.callback_query_handler(lambda c: c.data == 'generate_menu')
async def process_callback_generate_menu(callback_query: types.CallbackQuery):
    global WELCOME
    message = callback_query.message
    today_keys = await get_all_user_keys_24h(callback_query.from_user.id, pool=POOL)
    limit_keys = json_config['COUNT'] + len(await get_all_refs(pool=POOL, user_id=callback_query.message.chat.id))
    
    if WELCOME:
        await try_to_delete(chat_id=message.chat.id, message_id=WELCOME.message_id)
    
    text = f"<b>Now choose you game to generate:</b>\n"
    text += f'\n<b>Your attempts today:</b> {limit_keys - len(today_keys) if today_keys else limit_keys}/{limit_keys}'
    text += "\n\n<i>!!! Bot now in beta version, on any bug or error please contact technical support or just try again</i>"

    keyboard = InlineKeyboardMarkup()
    for type in json_config['EVENTS']:
        inline_btn = InlineKeyboardButton(text=json_config['EVENTS'][type]['NAME'], callback_data=f'generate_key_{type}')
        keyboard.add(inline_btn)

    WELCOME = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)


@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    args = int(message.get_args()) if message.get_args() else 0
    await insert_user(message.from_user.id, message.from_user.username, ref=args, pool=POOL)
    today_keys = await get_all_user_keys_24h(message.from_user.id, pool=POOL)
    await update_welcome_message(message, today_keys)


@dp.callback_query_handler(lambda c: c.data.startswith('generate_key_'))
async def generate_key(callback_query: types.CallbackQuery):
    global process_completed, LOADING
    process_completed = False
    await bot.answer_callback_query(callback_query.id)
    game_key = callback_query.data.split('_')[2]

    last_user_key = await get_last_user_key(callback_query.from_user.id, pool=POOL)
    today_keys = await get_all_user_keys_24h(callback_query.from_user.id, pool=POOL) or []

    if LOADING:
        await try_to_delete(chat_id=callback_query.from_user.id, message_id=LOADING.message_id)
        LOADING = None

    def can_generate_key():
        return not last_user_key or abs(relative_time(last_user_key[1])) > DELAY

    if can_generate_key() and not process_completed:
        if len(today_keys) < json_config['COUNT'] + len(get_all_refs(callback_query.from_user.id)):
            mins = json_config['EVENTS'][game_key]['EVENTS_DELAY'][0] * 15 // 60000 // 2
            LOADING = await new_message(f"Generating key...\nEstimated time: ~{mins} minutes", callback_query.from_user.id)
            try:
                key = get_unused_key_of_type(game_key)
                if get_unused_key_of_type(game_key) is not None:
                    await try_to_delete(LOADING.chat.id, LOADING.message_id)
                    LOADING = await new_message("You lucky! You instantly get free key\nYour key: <code>{key}</code>", callback_query.from_user.id)
                    insert_key_generation(callback_query.from_user.id, key, game_key, pool=POOL)
                async with aiohttp.ClientSession() as session:
                    key_task = asyncio.create_task(get_key(session, game_key))
                    load_task = asyncio.create_task(update_loadbar(LOADING))
                    await asyncio.gather(key_task, load_task)
                    key = await key_task
                    if key is None:
                        await try_to_delete(LOADING.chat.id, LOADING.message_id)
                        LOADING = await new_message("An error occurred while generating the key!\nPlease try again later or contact technical support", callback_query.from_user.id)
                    else:
                        await try_to_delete(LOADING.chat.id, LOADING.message_id)
                        await insert_key_generation(callback_query.from_user.id, key, game_key, pool=POOL)
                        LOADING = await new_message(f"Key generated: <code>{key}</code>", callback_query.from_user.id)
                    process_completed = True
            except Exception as e:
                process_completed = True
                logging.error(f'Error generating key! Error: {e}')
                text = "An error occurred while generating the key!\nPlease try again later or contact technical support"
                await try_to_delete(chat_id=callback_query.from_user.id, message_id=LOADING.message_id)
                LOADING = await new_message(text, callback_query.from_user.id)
        else:
            process_completed = True
            text = "You have reached the limit of keys generated today.\nPlease come back tomorrow."
            if LOADING:
                await try_to_delete(chat_id=callback_query.from_user.id, message_id=LOADING.message_id)
            LOADING = await new_message(text, callback_query.from_user.id)
    else:
        process_completed = True
        text = f'Last generated key: <code>{last_user_key[0]}</code>\nNext can be generated in {60 - relative_time(last_user_key[1])} seconds'
        LOADING = await new_message(text, callback_query.from_user.id)
        if WELCOME and LOADING.message_id - 1 != WELCOME.message_id:
            await try_to_delete(chat_id=callback_query.from_user.id, message_id=LOADING.message_id - 1)

    await send_welcome(callback_query.message)


@dp.callback_query_handler(lambda c: c.data == 'generate_key')
async def process_callback_generate_key(callback_query: types.CallbackQuery):
    try:
        await generate_key(callback_query)
    except InvalidQueryID:
        await new_message('Make another call now, your request was expired\nJust press /start', callback_query.from_user.id)
    except AttributeError as e:
        logging.error(f'Error generating key! Error: {e}')

if __name__ == '__main__':
    POOL = asyncio.get_event_loop().run_until_complete(get_pool())
    print('Bot started...')
    executor.start_polling(dp, skip_updates=True)
