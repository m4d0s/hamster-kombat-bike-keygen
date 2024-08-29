import asyncio
import random

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import (ChatNotFound,BadRequest)

from .cache import get_cached_data

from c_telegram import dp, BOT_INFO, bot, snippet, translate, POOL, request_level


# Other games funcs
@dp.callback_query_handler(lambda c: c.data == 'other_games')
async def process_callback_other_games(callback_query: types.CallbackQuery) -> None:
    cache = await get_cached_data(callback_query.message.chat.id) ##cache
    await bot.answer_callback_query(callback_query.id, show_alert=True, text=translate[cache['lang']]['process_callback_other_games'][0])

