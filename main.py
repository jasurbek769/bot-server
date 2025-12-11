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
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

# -----------------------------------------------------------
# SOZLAMALAR
# -----------------------------------------------------------
TOKEN = "7474552293:AAGd1oB9nJGiJKI9MjPMoxN2Oosebvli6Jg"
ADMIN_ID = 7950261926 

dp = Dispatcher()
DOWNLOAD_PATH = "downloads"
if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)

# -----------------------------------------------------------
# BAZA (LITE)
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
# MANTIQ VA YUKLASH TIZIMI
# -----------------------------------------------------------
class AdminState(StatesGroup):
    broadcast = State()
    add_ch_link = State()
    add_ch_id = State()

async def check_sub_status(bot: Bot, user_id: int):
    if user_id == ADMIN_ID: return []
    channels = get_channels_db()
    not_subbed = []
    for link, ch_id in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subbed.append((link, ch_id))
        except: continue
    return not_subbed

# --- KUCHAYTIRILGAN YUKLASH FUNKSIYASI ---
async def download_media(url, user_id, type="video"):
    ext = "mp4" if type == "video" else "mp3"
    file_name = f"{DOWNLOAD_PATH}/{user_id}_media.{ext}"
    
    # Cookies faylini qidirish
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    ydl_opts = {
        'outtmpl': file_name,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_file,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    if type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
    else:
        ydl_opts['format'] = 'bestvideo+bestaudio/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return file_name, info.get('title', 'Media')
    except Exception as e:
        print(f"Yuklashda xato: {e}")
        return None, None

# --- MUSIQA QIDIRISH (Search) ---
async def search_music_yt(query):
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    ydl_opts = {
        'quiet': True,
        'cookiefile': cookie_file,
        'noplaylist': True,
        'extract_flat': True,
        'default_search': 'ytsearch5',
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if 'entries' in info: return info['entries']
    except: pass
    return []

# -----------------------------------------------------------
# BOT HANDLERS
# -----------------------------------------------------------

@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id)
    
    # Obuna tekshiruvi
    not_subbed = await check_sub_status(bot, message.from_user.id)
    if not_subbed:
        kb = [[InlineKeyboardButton(text="➕ Kanalga qo'shilish", url=l)] for l, _ in not_subbed]
        kb.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer("⚠️ <b>Botdan foydalanish uchun kanallarga a'zo bo'ling:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        return

    # SIZ SO'RAGAN UZUN MATN
    text = (
        f"🔥 <b>Assalomu alaykum. {message.from_user.full_name} ga Xush kelibsiz. Bot orqali quyidagilarni yuklab olishingiz mumkin:</b>\n\n"
        "• <b>Instagram</b> - post, stories, reels + audio bilan;\n"
        "• <b>TikTok</b> - suv belgisiz video + audio bilan;\n"
        "• <b>YouTube</b> - videolar va shorts + audio bilan;\n"
        "• <b>Snapchat</b> - suv belgisiz video + audio bilan;\n"
        "• <b>Likee</b> - suv belgisiz video + audio bilan;\n"
        "• <b>Pinterest</b> - suv belgisiz video va rasmlar + audio bilan;\n\n"
        "<b>Shazam funksiya:</b>\n"
        "• Qo‘shiq nomi yoki ijrochi ismi\n"
        "• Qo‘shiq matni\n"
        "• Ovozli xabar\n"
        "• Video\n"
        "• Audio\n"
        "• Video xabar\n\n"
        "🚀 <b>Yuklab olmoqchi bo'lgan videoga havolani yuboring!</b>\n"
        "<i>(Yoki shunchaki qo'shiq nomini yozing, men topib beraman)</i>"
    )
    
    await message.answer(text, disable_web_page_preview=True)

@dp.callback_query(F.data == "check_sub")
async def check_callback(call: CallbackQuery, bot: Bot):
    if await check_sub_status(bot, call.from_user.id):
        await call.answer("❌ Hali a'zo bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        await start_handler(call.message, bot) # Start xabarini qayta yuborish

# --- LINK KELGANDA ---
@dp.message(F.text.contains("http"))
async def link_handler(message: Message, state: FSMContext, bot: Bot):
    if await check_sub_status(bot, message.from_user.id):
        await message.answer("❌ Kanallarga a'zo bo'ling!")
        return
    
    await state.update_data(url=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Video", callback_data="d_vid"), InlineKeyboardButton(text="🎵 Audio (MP3)", callback_data="d_aud")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])
    await message.reply("Formatni tanlang:", reply_markup=kb)

# --- QO'SHIQ QIDIRUV (TEXT KELGANDA) ---
@dp.message(F.text)
async def text_handler(message: Message, bot: Bot):
    # Agar admin panel buyruqlari bo'lmasa va link bo'lmasa, demak bu musiqa qidiruvi
    if message.text.startswith("/"): return 
    if await check_sub_status(bot, message.from_user.id):
        await message.answer("❌ Kanallarga a'zo bo'ling!")
        return

    msg = await message.answer(f"🔍 <b>'{message.text}' qidirilmoqda...</b>")
    results = await search_music_yt(message.text)
    
    if not results:
        await msg.edit_text("❌ Afsuski musiqa topilmadi.")
        return

    kb = []
    for video in results:
        title = video.get('title', 'Noma\'lum')
        vid_id = video.get('id')
        kb.append([InlineKeyboardButton(text=f"🎵 {title[:40]}...", callback_data=f"music:{vid_id}")])
    
    kb.append([InlineKeyboardButton(text="❌ Yopish", callback_data="cancel")])
    await msg.edit_text(f"👇 <b>'{message.text}' bo'yicha natijalar:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# --- CALLBACKS (Tugmalar bosilganda) ---
@dp.callback_query(F.data.in_({"d_vid", "d_aud"}))
async def download_call(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.message.delete()
    data = await state.get_data()
    url = data.get("url")
    m_type = "video" if call.data == "d_vid" else "audio"
    
    msg = await call.message.answer("⏳ <b>Yuklab olinmoqda...</b>")
    file_path, title = await download_media(url, call.from_user.id, type=m_type)
    
    if file_path and os.path.exists(file_path):
        try:
            await msg.edit_text("📤 <b>Yuborilmoqda...</b>")
            media = FSInputFile(file_path)
            caption = f"{'🎬' if m_type=='video' else '🎵'} {title}\n🤖 Bot: @{(await bot.get_me()).username}"
            
            if m_type == "video": await call.message.answer_video(media, caption=caption)
            else: await call.message.answer_audio(media, caption=caption)
            await msg.delete()
        except: await msg.edit_text("❌ Fayl juda katta yoki xatolik yuz berdi.")
        finally: 
            if os.path.exists(file_path): os.remove(file_path)
    else: await msg.edit_text("❌ Yuklab bo'lmadi (Cookies xatosi yoki havola noto'g'ri).")
    await state.clear()

@dp.callback_query(F.data.startswith("music:"))
async def music_dl_call(call: CallbackQuery, bot: Bot):
    vid_id = call.data.split(":")[1]
    url = f"https://www.youtube.com/watch?v={vid_id}"
    
    await call.message.delete()
    msg = await call.message.answer("⏳ <b>Musiqa yuklanmoqda...</b>")
    file_path, title = await download_media(url, call.from_user.id, type="audio")
    
    if file_path and os.path.exists(file_path):
        try:
            await msg.edit_text("📤 <b>Yuborilmoqda...</b>")
            await call.message.answer_audio(FSInputFile(file_path), caption=f"🎵 {title}\n🤖 Bot: @{(await bot.get_me()).username}")
            await msg.delete()
        except: await msg.edit_text("❌ Xatolik.")
        finally: 
            if os.path.exists(file_path): os.remove(file_path)
    else: await msg.edit_text("❌ Yuklab bo'lmadi.")

@dp.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    await call.message.delete()
    await state.clear()

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_p(message: Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="stat"), InlineKeyboardButton(text="📨 Reklama", callback_data="broadcast")],
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"), InlineKeyboardButton(text="🗑 O'chirish", callback_data="del_ch")]
        ])
        await message.answer("👑 Admin Panel", reply_markup=kb)

@dp.callback_query(F.data == "stat")
async def stat_c(call: CallbackQuery): await call.answer(f"Odamlar: {get_users_count()}", show_alert=True)

@dp.callback_query(F.data == "add_ch")
async def add_ch_c(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal linkini yuboring:")
    await state.set_state(AdminState.add_ch_link)

@dp.message(AdminState.add_ch_link)
async def add_ch_msg(message: Message, state: FSMContext, bot: Bot):
    link = message.text
    uname = link.split("/")[-1] if "/" in link else link
    if not uname.startswith("@") and "t.me" not in link: uname = "@" + uname
    try:
        chat = await bot.get_chat(uname)
        add_channel_db(link, str(chat.id))
        await message.answer(f"✅ Qo'shildi: {chat.title}")
    except: await message.answer("❌ Kanal topilmadi yoki Bot admin emas!")
    await state.clear()

@dp.callback_query(F.data == "del_ch")
async def del_ch_c(call: CallbackQuery):
    kb = [[InlineKeyboardButton(text=f"❌ {l}", callback_data=f"del:{i}")] for l, i in get_channels_db()]
    if kb: await call.message.answer("Tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else: await call.answer("Bo'sh", show_alert=True)

@dp.callback_query(F.data.startswith("del:"))
async def del_do(call: CallbackQuery):
    del_channel_db(call.data.split(":")[1])
    await call.answer("O'chdi")
    await call.message.delete()

@dp.callback_query(F.data == "broadcast")
async def broad_c(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Reklamani yuboring:")
    await state.set_state(AdminState.broadcast)

@dp.message(AdminState.broadcast)
async def broad_s(message: Message, state: FSMContext):
    u = get_all_users()
    await message.answer(f"Ketdi ({len(u)})...")
    for i in u:
        try: await message.copy_to(i); await asyncio.sleep(0.05)
        except: pass
    await message.answer("Tugadi.")
    await state.clear()

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
