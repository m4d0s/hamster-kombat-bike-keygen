import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from aiogram.utils.exceptions import MessageNotModified, MessageToDeleteNotFound, InvalidQueryID, ChatNotFound, BotBlocked
import asyncio
import aiohttp
import json
import re
import tracemalloc
from generate import generate_loading_bar
from database import log_timestamp, insert_key_generation, get_last_user_key, get_all_dev, get_all_user_ids
from database import relative_time, get_all_user_keys_24h, insert_user, format_remaining_time, delete_user, get_pool

json_config = json.loads(open('config.json').read())
API_TOKEN = json_config['API_TOKEN']
DELAY = json_config['DELAY']

# Configure logging
logging.basicConfig(
    filename=f'logs/{log_timestamp()}.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

def server_link(json, page):
    return f'{json["PROTOCOL"]}://{json["HOST"]}:{json["PORT"]}/{page}'

SERVER_URL = server_link(json_config["SERVER"], 'keygen')
EVENTS_DELAY = json_config['EVENTS_DELAY'][1] if json_config['DEBUG'] else json_config['EVENTS_DELAY'][0]
WELCOME = None
LOADING = None
REPORT = None
POOL = None

async def run_periodically(interval, func, *args, **kwargs):
    while True:
        await func(*args, **kwargs)
        await asyncio.sleep(interval)

def html_back_escape(text):
    return str(text).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

async def new_message(message: str, chat_id: int):
    return await bot.send_message(text=message, chat_id=chat_id, parse_mode=ParseMode.HTML)

async def update_loadbar(message: types.Message):
    global process_completed, loading
    while not process_completed:
        text, loading = generate_loading_bar(loading)
        try:
            await bot.edit_message_text("Generating key...\n" + text, message.chat.id, message.message_id, parse_mode=ParseMode.HTML)
        except MessageNotModified:
            pass
        await asyncio.sleep(1)

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
    inline_btn_generate = InlineKeyboardButton('Generate Key', callback_data='generate_key')
    inline_kb = InlineKeyboardMarkup().add(inline_btn_generate)

    if WELCOME:
        await try_to_delete(chat_id=message.chat.id, message_id=WELCOME.message_id)

    text = f"<b>I'm Hamster Bike Keygen Bot! (Beta)</b>\nYour id: <code>{message.from_user.id}</code>\n\n<b>Today you generate:</b>\n"
    if today_keys:
        text += '\n'.join([f'<code>{key}</code> ({format_remaining_time(key_time)})' for key, key_time in today_keys])
    else:
        text += '\n<i>No keys generated today</i>'
    text += f'\n\n<b>Your attempts today:</b> {5 - len(today_keys) if today_keys else 5}/5'
    text += "\n<i>Click the button below to generate a key</i>"
    text += "\n\n<i>!!! Bot now in beta version, on any bug or error please contact technical support or just try again</i>"

    WELCOME = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=inline_kb)
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    args=int(message.get_args()) if message.get_args() else 0
    await insert_user(message.from_user.id, message.from_user.username, ref=args, pool=POOL)
    today_keys = await get_all_user_keys_24h(message.from_user.id, pool=POOL)
    await update_welcome_message(message, today_keys)

async def generate_key(callback_query: types.CallbackQuery):
    global process_completed, LOADING
    process_completed = False
    await bot.answer_callback_query(callback_query.id)

    last_user_key = await get_last_user_key(callback_query.from_user.id, pool=POOL)
    today_keys = await get_all_user_keys_24h(callback_query.from_user.id, pool=POOL) or []

    if LOADING:
        await try_to_delete(chat_id=callback_query.from_user.id, message_id=LOADING.message_id)
        LOADING = None

    if not last_user_key or abs(relative_time(last_user_key[1])) > DELAY and not process_completed:
        if len(today_keys) < 5:
            LOADING = await new_message("Generating key...\nEstimated time: 2 minutes", callback_query.from_user.id)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(SERVER_URL) as response:
                        if response.status == 200:
                            key = await response.text()
                            process_completed = True
                            text = f'Key generated successfully!\nGenerated key: <code>{key}</code>'
                            await try_to_delete(chat_id=callback_query.from_user.id, message_id=LOADING.message_id)
                            LOADING = await new_message(text, callback_query.from_user.id)
                            await insert_key_generation(callback_query.from_user.id, key, pool=POOL)
                        else:
                            text = "An error occurred while generating the key!\nPlease try again later or contact technical support"
                            await try_to_delete(chat_id=callback_query.from_user.id, message_id=LOADING.message_id)
                            LOADING = await new_message(text, callback_query.from_user.id)
                            raise Exception("Failed to generate key")
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

    message = callback_query.message
    message.from_user = callback_query.from_user
    await send_welcome(callback_query.message)

@dp.callback_query_handler(lambda c: c.data == 'generate_key')
async def process_callback_generate_key(callback_query: types.CallbackQuery):
    try:
        await generate_key(callback_query)
    except InvalidQueryID:
        await new_message('Make another call now, your request was expired\nJust press /start', callback_query.from_user.id)
    except AttributeError as e:
        logging.error(f'Error generating key! Error: {e.with_traceback()}')

if __name__ == '__main__':
    POOL = asyncio.get_event_loop().run_until_complete(get_pool())
    print('Bot started...')
    executor.start_polling(dp, skip_updates=True)
