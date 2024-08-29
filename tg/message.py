import traceback

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from aiogram.utils.exceptions import (MessageNotModified, MessageToDeleteNotFound, ChatNotFound, BotBlocked, 
                                      MessageToEditNotFound, MessageCantBeDeleted, MessageCantBeEdited, UserDeactivated)

from .cache import get_cached_data, set_cached_data

from c_telegram import BOT_INFO, bot, translate, db_config
from database import (delete_user)
from generate import get_logger

logger = get_logger()

def html_back_escape(text:str) -> str:
    return str(text).replace('&lt;', '＜').replace('&gt;', '＞').replace('&amp;', '＆')

async def try_to_delete(chat_id:int, message_id:int) -> bool:
    if message_id is None or message_id == 0:
        logger.debug('Message ID is None to delete in chat ' + str(chat_id))
        return False
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except MessageToDeleteNotFound:
        return False
    except MessageCantBeDeleted:
        return False
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
    
async def try_to_edit(text:str, chat_id:int, message_id:int, keyboard: InlineKeyboardMarkup = None) -> bool:
    if message_id is None or message_id == 0:
        logger.debug('Message ID is None to edit in chat ' + str(chat_id))
        return False
    try:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return True
    except MessageNotModified:
        return False
    except MessageToEditNotFound:
        return False
    except MessageCantBeEdited:
        return False
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
    
async def send_error_message(chat_id:int, message:str, e:Exception = None, only_dev:bool = False) -> types.Message:
    cache = await get_cached_data(chat_id) ##cache
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(translate[cache['lang']]['send_error_message'][0], callback_data='main_menu'))
    
    cache['process'] = True
    if cache['error']:
        await try_to_delete(chat_id, cache['error'])
    if cache['welcome']:
        await try_to_delete(chat_id, cache['welcome'])
        cache['welcome'] = None
        
    if e is not None:
        err_t = f'Error: {e}' if str(e) else 'Error: No details'
        logger.error(traceback.format_stack()[-2].split('\n')[0].strip() + f'\t{err_t}')
    if only_dev:
        ERROR_MESS = await new_message(text=message, chat_id=db_config['DEV_ID'], keyboard=keyboard)
    else:
        ERROR_MESS = await new_message(text=message, chat_id=chat_id, keyboard=keyboard)
    
    if cache['error']:
        cache['error'] = ERROR_MESS.message_id
    await set_cached_data(chat_id, cache) ##write
    return ERROR_MESS
    
async def new_message(text: str, chat_id: int, keyboard: InlineKeyboardMarkup = None, disable_preview:bool = True, document = None, parse_mode = ParseMode.HTML) -> types.Message:
    try:
        if document:
            return await bot.send_document(caption=html_back_escape(text), 
                                           chat_id=chat_id, 
                                           parse_mode=parse_mode, 
                                           reply_markup=keyboard, 
                                           document=document)
        return await bot.send_message(text=html_back_escape(text), 
                                      chat_id=chat_id, 
                                      parse_mode=parse_mode, 
                                      disable_web_page_preview=disable_preview, 
                                      reply_markup=keyboard)
    # except MessageIsTooLong:
    #     logger.warning('Message is too long to send in chat ' + str(chat_id))
    except UserDeactivated:
        logger.warning("User ({user_id}) deactivated".format(user_id=chat_id))
    except BotBlocked:
        logger.warning("Bot was blocked by user ({user_id})".format(user_id=chat_id))
    except ChatNotFound:
        logger.warning("Chat ({user_id}) not found".format(user_id=chat_id))
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
        
async def send_message_to_user(user_id:int, text: str, keyboard: InlineKeyboardMarkup) -> None:
    if user_id == BOT_INFO.id:
        return
    cache = await get_cached_data(user_id) ##cache
    try:
        await new_message(chat_id=user_id, text=text, keyboard=keyboard)
    except UserDeactivated:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][2].replace('{user_id}', str(user_id))}")
        await delete_user(user_id)
    except ChatNotFound:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][0].replace('{user_id}', str(user_id))}")
        await delete_user(user_id)
    except BotBlocked:
        logger.warning(f"{translate[cache['lang']]['send_message_to_user'][1].replace('{user_id}', str(user_id))}")
        await delete_user(user_id)
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {user_id}: {error_text}')
        return
    await set_cached_data(user_id, cache) ##write

