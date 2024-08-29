import os
import asyncio
import aiofiles

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .message import new_message, send_error_message, try_to_delete, try_to_edit
from .cache import get_cached_data, set_cached_data

from generate import generate_loading_bar, get_logger
from c_telegram import dp, BOT_INFO, bot, snippet, translate, POOL, request_level
from database import (get_all_user_ids, get_promotions)


logger = get_logger()

#debug
async def get_chat_members(chat_id):
    members = []
    try:
        async for member in bot.iter_chat_members(chat_id):
            member_info = f"ID: {member.user.id}, Name: {member.user.full_name}, Mention: {member.user.mention}"
            members.append(member_info)
    except Exception as e:
        logger.error(e)
    return members

async def get_user_info(user_id):
    try:
        chat_member = await bot.get_chat_member(user_id, user_id)
        user = chat_member.user
        return f"ID: {user.id}, Name: {user.first_name} {user.last_name}, Mention: {user.mention}"
    except Exception as e:
        logger.error(e)
        return f"ID: {user_id}, (Undefined for some reason: {e})"

async def get_chat_permissions(chat):
    try:
        if not chat.permissions:
            return {}

        permissions = dict(chat.permissions)
        return {k.split('can_')[1].replace('_', ' ').capitalize() : v for k,v in permissions.items()}

    except Exception as e:
        logger.error(f"Error getting chat permissions: {e}")
        return {}

async def get_chat_info(id, undefined="---"):
    try:
        chat = await bot.get_chat(id)
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        invite_link = chat.invite_link or await bot.export_chat_invite_link(chat.id)
        permissions = await get_chat_permissions(chat)

        chat_info = (
            f"Name: {chat.title} ({chat.id}), Type: {chat.type}\n"
            f"\tChat rights: {bot_member.status}\n"
            f"\tPublic Link: https://t.me/{chat.username}\n"
            f"\tInvite Link: {invite_link}\n"
            f"\tPermissions:\n" +
            "".join(f"\t\t{perm}: {value}\n" for perm, value in permissions.items())
        )
        return chat_info + "\n"
    except Exception as e:
        logger.error(e)
        chat_info = f"Name (task): {undefined} ({id}), Type: (Undefined for some reason: {e})\n\n"
        return chat_info

async def save_to_file(file_path, content):
    async with aiofiles.open(file_path, "w") as file:
        await file.write(content)

async def delete_file(file_path):
    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass

@dp.callback_query_handler(lambda c: c.data == 'debug')
async def send_files(callback_query: types.CallbackQuery):
    chat = callback_query.message.chat
    cache = await get_cached_data(chat.id)
    semaphore = asyncio.Semaphore(25)
    if not cache['process']:
        return
    cache['process'] = False
    if not request_level(cache['right'], 9, chat.id):  # 9 - debug level
        return
    
    if cache['loading']:
        await try_to_delete(chat_id=chat.id, message_id=cache['loading'])
    
    loading_message = await new_message("Starting debug", chat.id)
    cache['loading'] = loading_message.message_id
    await set_cached_data(chat.id, cache)

    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text="🛑 Stop process", callback_data="stop_process"))

    users = await get_all_user_ids(pool=POOL)
    promo = await get_promotions(pool=POOL)
    chats = [[promo[x]['check_id'], promo[x].get('name')] for x in promo] \
               + [[promo[x]['check_id'], promo[x].get('name')] for x in promo if 'chat_id' in x and promo[x].get('chat_id')]

    user_tasks = []
    chat_tasks = []
    
    async def bounded_get_user_info(user):
        async with semaphore:
            return await get_user_info(user)
    
    async def bounded_get_chat_info(chat_id, undefined='---'):
        async with semaphore:
            return await get_chat_info(chat_id, undefined)

    for user in users:
        user_tasks.append(asyncio.create_task(bounded_get_user_info(user)))
    for chats in chats:
        chat_tasks.append(asyncio.create_task(bounded_get_chat_info(chat_id=chats[0], undefined=chats[1])))

    while any(not task.done() for task in user_tasks + chat_tasks):
        cache = await get_cached_data(chat.id)
        if cache['process']:
            for task in user_tasks + chat_tasks:
                task.cancel()
            break
        loading_text = (
            f"M: {generate_loading_bar(sum(task.done() for task in user_tasks), 15, len(user_tasks))}\n"
            f"C: {generate_loading_bar(sum(task.done() for task in chat_tasks), 15, len(chat_tasks))}"
        )
        await try_to_edit(text=loading_text, chat_id=chat.id, message_id=cache['loading'], keyboard=stop_button)
        await asyncio.sleep(2)
    
    if cache['process']:
        return
        
    cache['process'] = True
    await try_to_delete(chat_id=chat.id, message_id=cache['loading'])
    cache['loading'] = None

    members_list = "\n".join(task.result() for task in user_tasks if task.result())
    chats_list = "\n".join(task.result() for task in chat_tasks if task.result())

    users_file_path = "logs/users_list.txt"
    chats_file_path = "logs/chats_list.txt"
    
    await asyncio.gather(
        save_to_file(users_file_path, members_list),
        save_to_file(chats_file_path, chats_list)
    )
    
    empty = [False, False]

    stop_button = InlineKeyboardMarkup().add(InlineKeyboardButton(text="Close message", callback_data="close"))

    if os.path.getsize(users_file_path) > 0:
        await callback_query.message.reply_document(
            document=types.InputFile(users_file_path),
            caption="List of users",
            reply_markup=stop_button
        )
    else:
        empty[0] = True

    if os.path.getsize(chats_file_path) > 0:
        await callback_query.message.reply_document(
            document=types.InputFile(chats_file_path),
            caption="List of chats",
            reply_markup=stop_button
        )
    else:
        empty[1] = True
        
    if empty[0] or empty[1]:
        text = "The lists are empty: " + ', '.join([users_file_path if empty[0] else "", chats_file_path if empty[1] else ""])
        ERR = await send_error_message(chat.id, text)
        cache['error'] = ERR.message_id

    await asyncio.gather(
        delete_file(users_file_path),
        delete_file(chats_file_path)
    )

