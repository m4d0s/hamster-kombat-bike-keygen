import re

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .message import send_error_message, new_message, try_to_delete, try_to_edit
from .cache import get_cached_data, set_cached_data
from .process import update_report

from c_telegram import dp, BOT_INFO, bot, snippet, translate, POOL, request_level
from generate import get_logger

logger = get_logger()

#mass report
@dp.callback_query_handler(lambda c: c.data == 'report')
async def process_callback_report(callback_query: types.CallbackQuery) -> None:
    await mass_report(callback_query.message)

@dp.message_handler(commands=['report'])
async def mass_report(message: types.Message) -> None:
    if message.chat.type != types.ChatType.PRIVATE:
        return
    cache = await get_cached_data(message.chat.id) ##cache
    if not request_level(cache['right'], 2, message.chat.id) or not cache['process']: # 2 - report
        return
    await send_report_example(message)

async def send_report_example(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id) ##cache
    if cache['report']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['report'])
        cache['report'] = None
        
    code_example = translate[cache['lang']]['send_report_example'][2] + ":\n" \
        + snippet['code-block'].format(lang=cache['lang'], text=translate[cache['lang']]['send_report_example'][4]) + "\n\n"
    example = translate[cache['lang']]['send_report_example'][3] + ":\n" \
        + snippet['code'].format(text=translate[cache['lang']]['send_report_example'][5])
        
    warning = f"\n\n{translate[cache['lang']]['send_report_example'][1]}"
    text = f"{translate[cache['lang']]['send_report_example'][0]}\n\n"
    if cache['report']:
        await try_to_delete(chat_id=message.chat.id, message_id=cache['report'])
    key = InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton(text=translate[cache['lang']]['send_report_example'][6], callback_data='main_menu'))
    REPORT_MESS = await new_message(text=text + code_example + example + warning, chat_id=message.chat.id, keyboard=key)
    cache['report'] = REPORT_MESS.message_id
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)
    await set_cached_data(message.chat.id, cache) ##write

@dp.message_handler(lambda message: message.reply_to_message and \
                    any(message.reply_to_message.text.startswith(translate[x]['send_report_example'][0]) for x in translate))
async def report(message: types.Message) -> None:
    cache = await get_cached_data(message.chat.id)

    if not cache.get('process'):
        text = translate[cache['lang']]['report'][0]
        if cache.get('error'):
            await try_to_delete(chat_id=message.chat.id, message_id=cache['error'])
        cache['error'] = (await send_error_message(message.chat.id, text, Exception('Process not completed'))).message_id
        await set_cached_data(message.chat.id, cache)
        return

    if not request_level(cache['right'], 2, message.chat.id): # 2 - report
        return

    cache['process'] = False
    await try_to_delete(chat_id=message.chat.id, message_id=message.message_id)

    urls = re.findall(r'\[(.+?)\]\[(.+?)\]', message.text, re.DOTALL)
    text_without_buttons = re.sub(r'\[(.+?)\]\[(.+?)\]', '', message.html_text).strip()

    transl = re.findall(r'<pre>```(\w+)\n(.*?)\n```<\/pre>|<pre><code class="language-(\w+)">(.*?)<\/code><\/pre>', text_without_buttons, re.DOTALL)
    if not transl:
        transl = [('default',text_without_buttons,'','')]
    else:
        default = transl[0]
        default = ('default', default[1], default[2], default[3])
        transl = [default] + transl
    text_dict = {x[0] or x[2]: x[1] or x[3] for x in transl} if transl else {}

    keyboard = InlineKeyboardMarkup()
    for name, url in urls:
        keyboard.add(InlineKeyboardButton(text=name, url=url))
    
    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text=translate[cache['lang']]['update_report'][4], callback_data="stop_process"))
    await try_to_edit(chat_id=message.chat.id, message_id=cache['report'], text=message.html_text, keyboard=stop_button)

    await set_cached_data(message.chat.id, cache)
    await update_report(message.chat.id, text_dict, keyboard)

