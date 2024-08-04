import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import requests
import json
from generate import USER_ID, USER, HASH, app
import threading

API_TOKEN = json.loads(open('config.json').read())['API_TOKEN']

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

FLASK_SERVER_URL = json.loads(open('config.json').read())['FLASK_SERVER']

@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    # Create inline keyboard
    inline_btn_generate = InlineKeyboardButton('Generate Key', callback_data='generate_key') # type: ignore
    inline_kb = InlineKeyboardMarkup().add(inline_btn_generate)

    await message.reply("Hi!\nI'm Hamster Bike Keygen Bot!\nClick the button below to generate a key.", reply_markup=inline_kb)

@dp.callback_query_handler(lambda c: c.data == 'generate_key')
async def process_callback_generate_key(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    try:
        loading_message = await bot.send_message(callback_query.from_user.id, "Generating key...")
        response = requests.get(FLASK_SERVER_URL, params={'id': USER_ID, 'user': USER, 'hash': HASH})
        if response.status_code == 200:
            await bot.edit_message_text(f"Generated key: {response.text}", callback_query.from_user.id, loading_message.message_id)
        else:
            await bot.edit_message_text(f"Failed to generate key: {response.text}", callback_query.from_user.id, loading_message.message_id)
    except Exception as e:
        logging.error(f"Error generating key: {e}")
        await bot.edit_message_text("An error occurred while generating the key.", callback_query.from_user.id, loading_message.message_id)


if __name__ == '__main__':
    threading.Thread(target=app.run, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
