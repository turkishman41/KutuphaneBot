import os
import logging
import random
import asyncio
from Script import script
from pyrogram import Client, filters
from pyrogram.errors.exceptions.bad_request_400 import ChatAdminRequired, UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import Media, get_file_details, unpack_new_file_id
from database.users_chats_db import db
from info import CHANNELS, ADMINS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, LOG_CHANNEL, PICS, SUPPORT_CHAT
from utils import get_size, is_subscribed
import re
logger = logging.getLogger(__name__)


@Client.on_message(filters.command("start") & filters.private)
async def start(client, message):
  chat_id = message.from_user.id
  if (chat_id < 1740985941) == True:
      if AUTH_CHANNEL:
          try:
              user = await client.get_chat_member(AUTH_CHANNEL, message.chat.id)
              if user.status == "banned":
                  await client.delete_messages(
                      chat_id=message.chat.id,
                      message_ids=message.message_id,
                      revoke=True
                  )
                  return
          except UserNotParticipant:
              print("User is not participant.")
  else:
      await client.delete_messages(
          chat_id=message.chat.id,
          message_ids=message.message_id,
          revoke=True
      )

      if not await db.is_user_exist(chat_id):
          data = await client.get_me()
          BOT_USERNAME = data.username
          await db.add_user(chat_id, message.from_user.first_name)
          if LOG_CHANNEL:
              await client.send_message(LOG_CHANNEL,
                                        text=script.LOG_TEXT_P.format(chat_id, message.from_user.mention, BOT_USERNAME))
          else:
              logging.info(f"#YeniKullanıcı :- Ad : {message.from_user.first_name} ID : {chat_id}")

      if len(message.command) != 2:
          buttons = [[
              InlineKeyboardButton('🔍 Ara', switch_inline_query_current_chat='')
          ]]
          reply_markup = InlineKeyboardMarkup(buttons)
          await client.send_photo(
              chat_id=chat_id,
              photo=random.choice(PICS),
              caption=script.START_TXT.format(message.from_user.mention),
              reply_markup=reply_markup,
              parse_mode='html',
              protect_content=True
          )
          return
      if AUTH_CHANNEL and not await is_subscribed(client, message):
          try:
              date = message.date + 120
              invite_link = await client.create_chat_invite_link(int(AUTH_CHANNEL), expire_date=date, member_limit=1)
          except ChatAdminRequired:
              logger.error("Bot'un Forcesub kanalında yönetici olduğundan emin olun.")
              return
          btn = [
              [
                  InlineKeyboardButton(
                      "🤖 Kanala Katılın", url=invite_link.invite_link
                  )
              ]
          ]
          if message.command[1] != "subscribe":
              btn.append([InlineKeyboardButton(" 🔄 Tekrar deneyin", callback_data=f"checksub#{message.command[1]}")])
          await client.send_message(
              chat_id=chat_id,
              text="**Botu sadece kanal aboneleri kullanabilir.**",
              reply_markup=InlineKeyboardMarkup(btn),
              parse_mode="markdown",
              protect_content=True
          )
          return
      if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help", "start"]:
          buttons = [[
              InlineKeyboardButton('🔍 Ara', switch_inline_query_current_chat='')
          ]]
          reply_markup = InlineKeyboardMarkup(buttons)
          await client.send_photo(
              chat_id=chat_id,
              photo=random.choice(PICS),
              caption=script.START_TXT.format(message.from_user.mention),
              reply_markup=reply_markup,
              parse_mode='html',
              protect_content=True
          )
          return
      file_id = message.command[1]
      files_ = await get_file_details(file_id)
      if not files_:
          return await message.reply('Böyle bir dosya yok.')
      files = files_[0]
      title = files.file_name
      size = get_size(files.file_size)
      f_caption = files.caption
      if CUSTOM_FILE_CAPTION:
          try:
              f_caption = CUSTOM_FILE_CAPTION.format(file_name=title, file_size=size, file_caption=f_caption)
          except Exception as e:
              logger.exception(e)
              f_caption = f_caption
      if f_caption is None:
          f_caption = f"{files.file_name}"
      await client.send_cached_media(
          chat_id=chat_id,
          file_id=file_id,
          caption=f_caption,
          protect_content=True,
      )
                    

@Client.on_message(filters.command('kanal') & filters.user(ADMINS))
async def channel_info(bot, message):
           
    """Send basic information of channel"""
    if isinstance(CHANNELS, (int, str)):
        channels = [CHANNELS]
    elif isinstance(CHANNELS, list):
        channels = CHANNELS
    else:
        raise ValueError("Unexpected type of CHANNELS")

    text = '📑 **İndekslenen kanallar/gruplar**\n'
    for channel in channels:
        chat = await bot.get_chat(channel)
        if chat.username:
            text += '\n@' + chat.username
        else:
            text += '\n' + chat.title or chat.first_name

    text += f'\n\n**Toplam:** {len(CHANNELS)}'

    if len(text) < 4096:
        await message.reply(text)
    else:
        file = 'İndekslenen kanallar.txt'
        with open(file, 'w') as f:
            f.write(text)
        await message.reply_document(file)
        os.remove(file)


@Client.on_message(filters.command('log') & filters.user(ADMINS))
async def log_file(bot, message):
    """Send log file"""
    try:
        await message.reply_document('TelegramBot.log')
    except Exception as e:
        await message.reply(str(e))


@Client.on_message(filters.command('sil') & filters.user(ADMINS))
async def delete(bot, message):
    """Delete file from database"""
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("İşleniyor...⏳", quote=True)
    else:
        await message.reply('Silmek istediğiniz dosyayı /sil ile yanıtlayın', quote=True)
        return

    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    else:
        await msg.edit('Bu desteklenen bir dosya biçimi değil.')
        return
    
    file_id, file_ref = unpack_new_file_id(media.file_id)

    result = await Media.collection.delete_one({
        '_id': file_id,
    })
    if result.deleted_count:
        await msg.edit('Dosya veritabanından başarıyla silindi.')
    else:
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
        result = await Media.collection.delete_one({
            'file_name': file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
            })
        if result.deleted_count:
            await msg.edit('Dosya veritabanından başarıyla silindi.')
        else:
            # files indexed before https://github.com/EvamariaTG/EvaMaria/commit/f3d2a1bcb155faf44178e5d7a685a1b533e714bf#diff-86b613edf1748372103e94cacff3b578b36b698ef9c16817bb98fe9ef22fb669R39 
            # have original file name.
            result = await Media.collection.delete_one({
                'file_name': media.file_name,
                'file_size': media.file_size,
                'mime_type': media.mime_type
            })
            if result.deleted_count:
                await msg.edit('Dosya veritabanından başarıyla silindi.')
            else:
                await msg.edit('Veritabanında dosya bulunamadı.')


@Client.on_message(filters.command('deleteall') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'İndekslenen tüm dosyalar silinecektir.\ndevam etmek istiyor musunuz?',
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Evet", callback_data="autofilter_delete"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="İptal et", callback_data="close_data"
                    )
                ],
            ]
        ),
        quote=True,
    )


@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, message):
    await Media.collection.drop()
    await message.answer()
    await message.message.edit('İndekslenen tüm dosyalar başarıyla silindi.')

