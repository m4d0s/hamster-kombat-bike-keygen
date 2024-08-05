import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Message
from aiogram.utils.exceptions import MessageNotModified, MessageToDeleteNotFound
import requests
import json
from generate import app, sleep, generate_loading_bar
import threading
from database import log_timestamp, insert_key_generation, get_last_user_key
from database import relative_time, get_all_user_keys_24h, insert_user, format_remaining_time

json_config = json.loads(open('config.json').read())
API_TOKEN = json_config['API_TOKEN']
DELAY = json_config['DELAY']

# Configure logging
logging.basicConfig(level=logging.INFO, filename='logs/'+log_timestamp()+'.log', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

FLASK_SERVER_URL = json_config['FLASK_SERVER']
EVENTS_DELAY = json_config['EVENTS_DELAY'][1] if json_config['DEBUG'] else json_config['EVENTS_DELAY'][0]

async def new_message(message:str, chat_id: int):
    return await bot.send_message(text=message, chat_id=chat_id, parse_mode=ParseMode.HTML)

WELCOME = None

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    global WELCOME
    insert_user(message.from_user.id, message.from_user.username)
    # Create inline keyboard
    
    today_keys = get_all_user_keys_24h(message.from_user.id)
    inline_btn_generate = InlineKeyboardButton('Generate Key', callback_data='generate_key') # type: ignore
    inline_kb = InlineKeyboardMarkup().add(inline_btn_generate)
    
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=WELCOME.message_id)
    except Exception  as e:
        pass
    text = '<b>I\'m Hamster Bike Keygen Bot!</b>\n\n<b>Today you generate:</b>\n'
    if today_keys:
        text += '\n'.join([f'<code>{key}</code> ({format_remaining_time(key_time)})' for key, key_time in today_keys])
    else:
        text += '\n<i>No keys generated today</i>'
    text += '\n\n<b>Your attempts today:</b> {}/5'.format(5 - len(today_keys) if today_keys else 5)
    text += "\n<i>Click the button below to generate a key</i>"
    WELCOME = await bot.send_message(text=text, chat_id=message.chat.id, parse_mode=ParseMode.HTML, reply_markup=inline_kb)
    
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except MessageToDeleteNotFound:
        pass

async def update_loadbar(message: types.Message):
    while not process_completed:
        text, i = generate_loading_bar()
        await bot.edit_message_text("Generating key...\nEstimated time: 25~30 seconds" + '\n' + text, message.chat.id, message.message_id, parse_mode=ParseMode.HTML)

loading_message = None

@dp.callback_query_handler(lambda c: c.data == 'generate_key')
async def process_callback_generate_key(callback_query: types.CallbackQuery):
    global process_completed
    global loading_message
    process_completed = False
    await bot.answer_callback_query(callback_query.id)
    last_user_key = get_last_user_key(callback_query.from_user.id)
    today_keys = get_all_user_keys_24h(callback_query.from_user.id)
    if today_keys is None:
        today_keys = []
    if loading_message:
        try:
            await bot.delete_message(chat_id=callback_query.from_user.id, message_id=loading_message.message_id)
        except MessageNotModified or MessageToDeleteNotFound:
            pass
        loading_message = None
    if not last_user_key or abs(relative_time(last_user_key[1])) > DELAY:
        if len(today_keys) < 5:
            loading_message = await new_message("Generating key...", callback_query.from_user.id)
            
            # asyncio.create_task(update_loadbar(loading_message))
            
            await bot.delete_message(chat_id=callback_query.from_user.id, message_id=loading_message.message_id-1) if WELCOME and loading_message.message_id-1 != WELCOME.message_id else None
            try:
                response = requests.get(FLASK_SERVER_URL) #, params={'user_id': callback_query.from_user.id, 'message_id': loading_message.message_id})
                if response.status_code == 200:
                    process_completed = True
                    text = f'Key generated succesfully!\nGenerated key: <code>{response.text}</code>'
                    await bot.delete_message(chat_id=callback_query.from_user.id, message_id=loading_message.message_id)
                    loading_message =await new_message(text, callback_query.from_user.id)
                    insert_key_generation(callback_query.from_user.id, response.text)
                else:
                    process_completed = True
                    text = f'Failed to generate key!\n Responce: <code>{response.text}</code>'
                    await bot.delete_message(chat_id=callback_query.from_user.id, message_id=loading_message.message_id)
                    loading_message =await new_message(text, callback_query.from_user.id)
            except Exception as e:
                process_completed = True
                logging.error(f'Error generating key!\n Error: {e}')
                text = "An error occurred while generating the key!\n Please try again later or contact the developer"
                await bot.delete_message(chat_id=callback_query.from_user.id, message_id=loading_message.message_id)
                loading_message = await new_message(text, callback_query.from_user.id)
        else:
            process_completed = True
            text = "You have reached the limit of keys generated today.\n Please come back tomorrow."
            if loading_message:
                await bot.delete_message(chat_id=callback_query.from_user.id, message_id=loading_message.message_id)
            loading_message = await new_message(text, callback_query.from_user.id)
    else:
        process_completed = True
        text = f'Last generated key: <code>{last_user_key[0]}</code>\nNext can be generate in {60 - relative_time(last_user_key[1])} seconds'
        loading_message = await new_message(text, callback_query.from_user.id)
        await bot.delete_message(chat_id=callback_query.from_user.id, message_id=loading_message.message_id-1) if WELCOME and loading_message.message_id-1 != WELCOME.message_id else None
    message = callback_query.message
    message.from_user = callback_query.from_user
    sleep(1000)
    await send_welcome(callback_query.message)

if __name__ == '__main__':
    threading.Thread(target=app.run, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
