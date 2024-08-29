import asyncio
import time

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from generate import logger, get_logger
from database import (now, get_promotions, update_proxy_work, get_pool, update_cache_process)

from tg.giveaway import wait_the_giveaway
from tg.process import update_report

from c_telegram import db_config, bot, dp

async def on_startup():
    POOL = await get_pool()  # Создание пула
    logger.info('DB pool created...')

    # Получение информации о боте
    BOT_INFO = await bot.get_me()
    logger.info('Telegram bot created... ID: %s, username: @%s', BOT_INFO.id, BOT_INFO.username)

    # Обновление кэша пользователей
    users_id = await update_cache_process(POOL)
    logger.info('Free all proxies from work...')
    
    logger.info("Setup giveaways shredule...")
    promo = await get_promotions(task_type='giveaway', pool=POOL)
    for x in promo:
        asyncio.create_task(wait_the_giveaway(int(x), promo[x]['expire'] - now()))

    # Обновление статуса прокси
    await update_proxy_work(POOL)
    logger.info("Send warning message to everyone who tried to generate key before....")

    # Подготовка сообщения для разработчика
    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text="Main menu", callback_data="main_menu"))
    text = {
        "ru": "Бот перезапущен, пожалуйста, сгенеруйте ключ заново (/start)", 
        "en": "Bot now restarted, please generate key again (/start)"
    }
    await update_report(db_config['DEV_ID'], text, stop_button, users_id, True)
    logger.info('Sucessfull report! Bot pooling now...')

if __name__ == '__main__':
    logger = get_logger()
    while True:
        try:
            logger.info("Telegram bot started...")
            asyncio.get_event_loop().run_until_complete(on_startup())
            asyncio.get_event_loop().run_until_complete(dp.start_polling())
        except Exception as e:
            error_text =  str(e)
            logger.error(f'Error: {error_text}, retry in 30 seconds...')
            time.sleep(30)