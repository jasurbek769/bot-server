import asyncio
import logging
import sys
import os
import sqlite3
import yt_dlp
from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web # Render uchun kerak

# -----------------------------------------------------------
# 1. SOZLAMALAR (O'ZGARTIRISH SHART!)
# -----------------------------------------------------------
TOKEN = "7474552293:AAGd1oB9nJGiJKI9MjPMoxN2Oosebvli6Jg"
ADMIN_ID = 7950261926  # <-- SHU YERGA O'Z ID RAQAMINGIZNI YOZING!

dp = Dispatcher()
DOWNLOAD_PATH = "downloads"
if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)

# -----------------------------------------------------------
# 2. BAZA (Foydalanuvchi va Kanallar)
# -----------------------------------------------------------
def db_start():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    cur.execute("CREATE TABLE IF NOT EXISTS channels (link TEXT, id TEXT)")
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_users_count():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    return cur.fetchone()[0]

def get_all_users():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    return [user[0] for user in cur.fetchall()]

def add_channel_db(link, ch_id):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO channels VALUES (?, ?)", (link, ch_id))
    conn.commit()
    conn.close()

def del_channel_db(ch_id):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM channels WHERE id = ?", (ch_id,))
    conn.commit()
    conn.close()

def get_channels_db():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM channels")
    return cur.fetchall()

# -----------------------------------------------------------
# 3. STATES & LOGIKA
# -----------------------------------------------------------
class AdminState(StatesGroup):
    broadcast = State()
    add_ch_link = State()
    add_ch_id = State()

async def check_sub_status(bot: Bot, user_id: int):
    # Adminni tekshirmaymiz
    if user_id == ADMIN_ID: return []
    
    channels = get_channels_db()
    not_subbed = []
    for link, ch_id in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subbed.append((link, ch_id))
        except: 
            # Agar bot admin bo'lmasa yoki xato bo'lsa, o'tkazib yuboramiz
            continue
    return not_subbed

async def download_video(url, user_id):
    file_name = f"{DOWNLOAD_PATH}/{user_id}_video.mp4"
    # Cookies bor yoki yo'qligini tekshirish
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': file_name,
        'noplaylist': True,
        'quiet': True,
        'cookiefile': cookie_file,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return file_name, info.get('title', 'Video')
    except Exception as e: return None, None

# -----------------------------------------------------------
# 4. BOT HANDLERS
# -----------------------------------------------------------
@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id)
    
    # Majburiy obunani tekshirish
    not_subbed = await check_sub_status(bot, message.from_user.id)
    if not_subbed:
        kb = [[InlineKeyboardButton(text="➕ A'zo bo'lish", url=l)] for l, _ in not_subbed]
        kb.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer(
            f"Assalomu alaykum, {message.from_user.full_name}!\n"
            "Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    else:
        await message.answer("✅ Botga xush kelibsiz! Menga link yuboring.")

@dp.callback_query(F.data == "check_sub")
async def check_callback(call: CallbackQuery, bot: Bot):
    if await check_sub_status(bot, call.from_user.id):
        await call.answer("❌ Hali a'zo bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        await call.message.answer("🎉 Rahmat! Endi link yuborishingiz mumkin.")

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="stat")],
            [InlineKeyboardButton(text="📨 Reklama yuborish", callback_data="broadcast")],
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"), 
             InlineKeyboardButton(text="🗑 Kanal o'chirish", callback_data="del_ch")]
        ])
        await message.answer(f"👑 <b>Admin Panel</b>\n👥 Obunachilar: {get_users_count()} ta", reply_markup=kb)
    else:
        # Admin bo'lmasa, bildirmaymiz
        pass

@dp.callback_query(F.data == "stat")
async def show_stat(call: CallbackQuery):
    await call.answer(f"Jami foydalanuvchilar: {get_users_count()}", show_alert=True)

# REKLAMA
@dp.callback_query(F.data == "broadcast")
async def ask_broadcast(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Reklama xabarini yuboring (Rasm, Video yoki Matn):")
    await state.set_state(AdminState.broadcast)

@dp.message(AdminState.broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    users = get_all_users()
    await message.answer(f"🚀 Xabar {len(users)} kishiga yuborilmoqda...")
    c = 0
    for u in users:
        try:
            await message.copy_to(chat_id=u)
            c += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Yuborildi: {c} ta")
    await state.clear()

# KANAL QO'SHISH
@dp.callback_query(F.data == "add_ch")
async def ask_ch(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal LINKINI yuboring (masalan: https://t.me/kanalim):")
    await state.set_state(AdminState.add_ch_link)

@dp.message(AdminState.add_ch_link)
async def get_ch_l(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("Endi Kanal ID sini yuboring (masalan: -10012345678):\n\n⚠️ Bot kanalda ADMIN bo'lishi shart!")
    await state.set_state(AdminState.add_ch_id)

@dp.message(AdminState.add_ch_id)
async def get_ch_i(message: Message, state: FSMContext):
    d = await state.get_data()
    add_channel_db(d.get("link"), message.text)
    await message.answer("✅ Kanal majburiy obunaga qo'shildi!")
    await state.clear()

@dp.callback_query(F.data == "del_ch")
async def del_ch_show(call: CallbackQuery):
    kb = [[InlineKeyboardButton(text=f"❌ {l}", callback_data=f"del:{i}")] for l, i in get_channels_db()]
    if not kb: await call.answer("Kanallar ro'yxati bo'sh", show_alert=True)
    else: await call.message.answer("Qaysi kanalni o'chiramiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del:"))
async def del_ch_do(call: CallbackQuery):
    del_channel_db(call.data.split(":")[1])
    await call.answer("O'chirildi")
    await call.message.delete()

# LINKNI USHLASH
@dp.message(F.text.contains("http"))
async def vid_handler(message: Message, bot: Bot):
    # Majburiy obuna tekshiruvi
    if await check_sub_status(bot, message.from_user.id):
        await message.answer("❌ Botdan foydalanish uchun kanallarga a'zo bo'ling! /start ni bosing.")
        return

    msg = await message.reply("⏳ <b>Video yuklanmoqda...</b>")
    file_path, title = await download_video(message.text, message.from_user.id)
    
    if file_path and os.path.exists(file_path):
        try:
            await msg.edit_text("📤 Yuborilmoqda...")
            await message.reply_video(FSInputFile(file_path), caption=f"🎬 {title}\n🤖 Bot: @{(await bot.get_me()).username}")
            await msg.delete()
        except Exception as e: await msg.edit_text(f"Xatolik: {e}")
        finally:
            if os.path.exists(file_path): os.remove(file_path)
    else:
        await msg.edit_text("❌ Kechirasiz, bu videoni yuklay olmadim.\nYouTube bo'lsa Cookies kerak bo'lishi mumkin.")

# -----------------------------------------------------------
# 5. RENDER UCHUN WEB-SERVER (Bot o'chib qolmasligi uchun)
# -----------------------------------------------------------
async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080)) # Render bergan portni oladi
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    db_start()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # Ikkita ishni birdan boshlaymiz: Bot + Web Server
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
