import asyncio
import logging
import sys
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
from dotenv import load_dotenv
from shazamio import Shazam
import yt_dlp

# --- SOZLAMALAR ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if ADMIN_ID: ADMIN_ID = int(ADMIN_ID)

dp = Dispatcher()
shazam = Shazam()

# Yuklash papkasi
DOWNLOAD_PATH = "downloads"
if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)

# --- BAZA (DATABASE) ---
def db_start():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS channels (link TEXT, id TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit(); conn.close()

def add_user(user_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,)); conn.commit(); conn.close()

def add_channel_db(link, ch_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("INSERT INTO channels VALUES (?, ?)", (link, ch_id)); conn.commit(); conn.close()

def get_channels():
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("SELECT * FROM channels"); return cur.fetchall()

def del_channel_db(ch_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("DELETE FROM channels WHERE id = ?", (ch_id,)); conn.commit(); conn.close()

# --- STATES ---
class AdminState(StatesGroup):
    add_channel = State()

# --- MAJBURIY OBUNA TEKSHIRUV ---
async def check_sub_status(bot: Bot, user_id: int):
    # Adminni tekshirmaymiz
    if user_id == ADMIN_ID: return True
    
    channels = get_channels()
    if not channels: return True # Kanal yo'q bo'lsa o'tkazvoramiz

    not_sub = []
    for link, ch_id in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            # A'zo bo'lmagan holatlar: left, kicked (ban)
            if member.status in ['left', 'kicked']:
                not_sub.append(link)
        except Exception as e:
            # Agar bot kanalga admin bo'lmasa yoki xato chiqsa, bu kanalni o'tkazib yuboramiz
            print(f"Kanal xatosi ({link}): {e}")
            continue

    return not_sub

# --- START ---
@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id)
    # 1. Obunani tekshirish
    not_sub_links = await check_sub_status(bot, message.from_user.id)
    
    if not_sub_links and not isinstance(not_sub_links, bool):
        kb = [[InlineKeyboardButton(text="➕ A'zo bo'lish", url=link)] for link in not_sub_links]
        kb.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer("⚠️ <b>Botdan foydalanish uchun kanallarga a'zo bo'ling:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        return

    await message.answer(f"👋 Salom <b>{message.from_user.full_name}</b>!\n\n"
                         "Menga <b>Instagram</b> video linkini yuboring.\n"
                         "Men videodagi musiqani <b>topib beraman!</b> 🎵")

@dp.callback_query(F.data == "check_sub")
async def check_callback(c: CallbackQuery, bot: Bot):
    not_sub = await check_sub_status(bot, c.from_user.id)
    if not not_sub or isinstance(not_sub, bool):
        await c.message.delete()
        await c.message.answer("✅ Rahmat! Endi link yuborishingiz mumkin.")
    else:
        await c.answer("❌ Hali hamma kanalga a'zo bo'lmadingiz!", show_alert=True)

# --- INSTAGRAM & MUSIC HANDLER ---
@dp.message(F.text.contains("instagram.com"))
async def insta_music_handler(message: Message, bot: Bot):
    # 1. Obuna tekshiruvi (Har safar link tashlaganda tekshiradi)
    not_sub_links = await check_sub_status(bot, message.from_user.id)
    if not_sub_links and not isinstance(not_sub_links, bool):
        kb = [[InlineKeyboardButton(text="➕ A'zo bo'lish", url=link)] for link in not_sub_links]
        kb.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer("⚠️ <b>Botdan foydalanish uchun kanallarga a'zo bo'ling:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        return

    msg = await message.reply("⏳ <b>Video yuklanmoqda va musiqa qidirilmoqda...</b>\n\nBu biroz vaqt olishi mumkin.")
    
    try:
        url = message.text
        file_path = f"{DOWNLOAD_PATH}/{message.from_user.id}.mp3"

        # 2. Videodan audio yuklash (yt-dlp)
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f"{DOWNLOAD_PATH}/{message.from_user.id}.%(ext)s",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        loop = asyncio.get_event_loop()
        # Synchronous yt-dlp ni async ichida ishlatish
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

        # 3. Shazam orqali aniqlash
        if os.path.exists(file_path):
            await msg.edit_text("🎵 <b>Musiqa aniqlanmoqda...</b>")
            try:
                out = await shazam.recognize(file_path)
                track = out.get('track', {})
                
                if track:
                    title = track.get('title', 'Noma\'lum')
                    artist = track.get('subtitle', 'Noma\'lum')
                    img_url = track.get('images', {}).get('coverart')
                    
                    caption = f"🎵 <b>Topildi!</b>\n\n🎹 <b>Nomi:</b> {title}\n🎤 <b>Ijrochi:</b> {artist}"
                    
                    # Agar rasm bo'lsa rasm bilan, bo'lmasa audio o'zini
                    if img_url:
                        await message.answer_photo(img_url, caption=caption)
                    else:
                        await message.answer(caption)
                    
                    # Audioni yuborish
                    await message.answer_audio(FSInputFile(file_path), caption=f"{artist} - {title}")
                else:
                    await message.answer("⚠️ Kechirasiz, bu videodagi musiqani topa olmadim.")
            except Exception as e:
                print(f"Shazam xatosi: {e}")
                await message.answer("⚠️ Musiqani aniqlashda xatolik bo'ldi.")
            
            # Faylni o'chirish
            os.remove(file_path)
            await msg.delete()
        else:
            await msg.edit_text("❌ Videoni yuklab bo'lmadi. Linkni tekshiring yoki profil yopiq bo'lishi mumkin.")

    except Exception as e:
        print(f"Umumiy xato: {e}")
        await msg.edit_text("❌ Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")

# --- ADMIN PANEL (Kanal qo'shish) ---
@dp.message(F.text == "/admin", F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch")],
        [InlineKeyboardButton(text="🗑 Kanal o'chirish", callback_data="del_ch")]
    ])
    await message.answer("Admin Panel:", reply_markup=kb)

@dp.callback_query(F.data == "add_ch")
async def ask_link(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Kanal linkini yuboring (Masalan: https://t.me/kanalim):")
    await state.set_state(AdminState.add_channel)

@dp.message(AdminState.add_channel)
async def save_channel(message: Message, state: FSMContext, bot: Bot):
    link = message.text
    try:
        # Linkdan username olish
        if "t.me/" in link: username = "@" + link.split("t.me/")[-1]
        else: username = link
        
        chat = await bot.get_chat(username)
        add_channel_db(link, chat.id)
        await message.answer(f"✅ Kanal qo'shildi!\nID: {chat.id}\n\n⚠️ Botni shu kanalga <b>Admin</b> qilishni unutmang!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: Kanal topilmadi yoki bot admin emas.\n{e}")
    await state.clear()

@dp.callback_query(F.data == "del_ch")
async def delete_channel_list(c: CallbackQuery):
    channels = get_channels()
    kb = []
    for link, ch_id in channels:
        kb.append([InlineKeyboardButton(text=f"❌ {link}", callback_data=f"del:{ch_id}")])
    kb.append([InlineKeyboardButton(text="🔙", callback_data="back_admin")])
    
    if not channels: await c.answer("Kanallar yo'q", show_alert=True); return
    await c.message.edit_text("O'chirish uchun tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del:"))
async def delete_process(c: CallbackQuery):
    ch_id = c.data.split(":")[1]
    del_channel_db(ch_id)
    await c.answer("O'chirildi!")
    await c.message.delete()

# --- SERVER ---
async def health(r): return web.Response(text="OK")
async def web_start():
    app = web.Application(); app.router.add_get('/', health)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

async def main():
    db_start()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await asyncio.gather(dp.start_polling(bot), web_start())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
