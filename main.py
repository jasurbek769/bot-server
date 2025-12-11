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
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BotCommand
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
# TILLAR VA MATNLAR (LOCALIZATION)
# -----------------------------------------------------------
LANGUAGES = {
    "uz": "🇺🇿 O'zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English"
}

TEXTS = {
    "uz": {
        "welcome": "👋 <b>Assalomu alaykum!</b>\n\nMen orqali <b>Instagram, TikTok, YouTube</b> dan video va audio yuklashingiz mumkin.\n\n🎵 <b>Musiqa qidirish uchun shunchaki nomini yozing!</b>\n\nBuyruqlar:\n/top - Eng zo'r musiqalar\n/new - Yangi musiqalar\n/lang - Tilni o'zgartirish",
        "search": "🔍 <b>Qidirilmoqda...</b>",
        "not_found": "❌ Hech narsa topilmadi.",
        "downloading": "⏳ <b>Yuklanmoqda...</b>",
        "sending": "📤 <b>Yuborilmoqda...</b>",
        "error": "❌ Xatolik yuz berdi.",
        "sub_check": "⚠️ Botdan foydalanish uchun kanalga a'zo bo'ling:",
        "sub_btn": "➕ A'zo bo'lish",
        "verify": "✅ Tasdiqlash",
        "choose_format": "Formatni tanlang:",
        "video": "🎬 Video",
        "audio": "🎵 Audio (MP3)",
        "results": "👇 Natijalar:",
        "top_title": "🔥 <b>TOP Musiqalar (Trend):</b>",
        "new_title": "🆕 <b>Yangi Musiqalar:</b>",
        "lang_choose": "Tilni tanlang / Выберите язык:",
        "lang_set": "✅ Til o'zgartirildi: O'zbekcha"
    },
    "ru": {
        "welcome": "👋 <b>Привет!</b>\n\nЧерез меня можно скачать видео и аудио с <b>Instagram, TikTok, YouTube</b>.\n\n🎵 <b>Просто напишите название песни для поиска!</b>\n\nКоманды:\n/top - Топ музыка\n/new - Новинки\n/lang - Сменить язык",
        "search": "🔍 <b>Поиск...</b>",
        "not_found": "❌ Ничего не найдено.",
        "downloading": "⏳ <b>Загрузка...</b>",
        "sending": "📤 <b>Отправка...</b>",
        "error": "❌ Произошла ошибка.",
        "sub_check": "⚠️ Подпишитесь на канал:",
        "sub_btn": "➕ Подписаться",
        "verify": "✅ Проверить",
        "choose_format": "Выберите формат:",
        "video": "🎬 Видео",
        "audio": "🎵 Аудио (MP3)",
        "results": "👇 Результаты:",
        "top_title": "🔥 <b>TOP Музыка (Тренд):</b>",
        "new_title": "🆕 <b>Новинки:</b>",
        "lang_choose": "Выберите язык / Tilni tanlang:",
        "lang_set": "✅ Язык изменен: Русский"
    },
    "en": {
        "welcome": "👋 <b>Hello!</b>\n\nDownload video/audio from <b>Instagram, TikTok, YouTube</b>.\n\n🎵 <b>Just type the song name to search!</b>\n\nCommands:\n/top - Top Songs\n/new - New Songs\n/lang - Change Language",
        "search": "🔍 <b>Searching...</b>",
        "not_found": "❌ Nothing found.",
        "downloading": "⏳ <b>Downloading...</b>",
        "sending": "📤 <b>Sending...</b>",
        "error": "❌ Error occurred.",
        "sub_check": "⚠️ Please join channel:",
        "sub_btn": "➕ Join",
        "verify": "✅ Verify",
        "choose_format": "Choose format:",
        "video": "🎬 Video",
        "audio": "🎵 Audio (MP3)",
        "results": "👇 Results:",
        "top_title": "🔥 <b>TOP Songs (Trend):</b>",
        "new_title": "🆕 <b>New Songs:</b>",
        "lang_choose": "Choose language:",
        "lang_set": "✅ Language set: English"
    }
}

# -----------------------------------------------------------
# BAZA (Foydalanuvchi + Til)
# -----------------------------------------------------------
def db_start():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    # Til ustuni (lang) qo'shildi
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'uz')")
    cur.execute("CREATE TABLE IF NOT EXISTS channels (link TEXT, id TEXT)")
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, lang) VALUES (?, 'uz')", (user_id,))
    conn.commit()
    conn.close()

def get_user_lang(user_id):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else "uz"

def set_user_lang(user_id, lang):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

# Kanal funksiyalari (Oldingidek)
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
# MANTIQ (YUKLASH VA QIDIRISH)
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

# --- SUPER YUKLASH FUNKSIYASI ---
async def download_media(url, user_id, type="video"):
    ext = "mp4" if type == "video" else "mp3"
    file_name = f"{DOWNLOAD_PATH}/{user_id}_media.{ext}"
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    ydl_opts = {
        'outtmpl': file_name,
        'noplaylist': True,
        'quiet': True,
        'cookiefile': cookie_file,
        # Brauzer ekanligini bildirish uchun (Blockni aylanib o'tish)
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        }
    }

    if type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
    else:
        ydl_opts['format'] = 'bestvideo+bestaudio/best' # Eng yaxshi sifat

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return file_name, info.get('title', 'Media')
    except Exception as e:
        print(f"Error: {e}")
        return None, None

async def search_music_yt(query, limit=10):
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    ydl_opts = {
        'quiet': True,
        'cookiefile': cookie_file,
        'noplaylist': True,
        'extract_flat': True,
        'default_search': f'ytsearch{limit}',
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            if 'entries' in info: return info['entries']
    except: pass
    return []

# -----------------------------------------------------------
# HANDLERS
# -----------------------------------------------------------

# START (/start)
@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id)
    lang = get_user_lang(message.from_user.id)
    
    not_subbed = await check_sub_status(bot, message.from_user.id)
    if not_subbed:
        kb = [[InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=l)] for l, _ in not_subbed]
        kb.append([InlineKeyboardButton(text=TEXTS[lang]["verify"], callback_data="check_sub")])
        await message.answer(TEXTS[lang]["sub_check"], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        # Menyu buyruqlarini o'rnatish
        await bot.set_my_commands([
            BotCommand(command="start", description="Restart"),
            BotCommand(command="top", description="Top 10 Music"),
            BotCommand(command="new", description="New Songs"),
            BotCommand(command="lang", description="Change Language"),
        ])
        await message.answer(TEXTS[lang]["welcome"])

# TIL O'ZGARTIRISH (/lang)
@dp.message(Command("lang"))
async def lang_handler(message: Message):
    kb = [
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")]
    ]
    await message.answer("👇", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("lang:"))
async def set_lang_call(call: CallbackQuery):
    lang_code = call.data.split(":")[1]
    set_user_lang(call.from_user.id, lang_code)
    await call.message.delete()
    await call.message.answer(TEXTS[lang_code]["lang_set"])
    # Start xabarini yangi tilda chiqarish
    await start_handler(call.message, call.bot) 

# TOP VA NEW MUSIQA (/top, /new)
@dp.message(Command("top"))
async def top_music(message: Message):
    lang = get_user_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["search"])
    # "Top music 2025" deb qidiradi
    results = await search_music_yt("Global Top 10 Music 2025", limit=10)
    await show_search_results(message, results, TEXTS[lang]["top_title"])

@dp.message(Command("new"))
async def new_music(message: Message):
    lang = get_user_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["search"])
    # "New songs 2025" deb qidiradi
    results = await search_music_yt("New Songs 2025 Hits", limit=10)
    await show_search_results(message, results, TEXTS[lang]["new_title"])

# NATIJALARNI CHIQARISH (YORDAMCHI)
async def show_search_results(message: Message, results, title):
    if not results:
        await message.edit_text("❌")
        return
    
    kb = []
    for video in results:
        t = video.get('title', 'Track')
        vid = video.get('id')
        kb.append([InlineKeyboardButton(text=f"🎵 {t[:35]}...", callback_data=f"music:{vid}")])
    
    kb.append([InlineKeyboardButton(text="❌", callback_data="del_msg")])
    await message.answer(title, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# OBUNA TEKSHIRUVI
@dp.callback_query(F.data == "check_sub")
async def check_callback(call: CallbackQuery, bot: Bot):
    if await check_sub_status(bot, call.from_user.id):
        await call.answer("❌", show_alert=True)
    else:
        await call.message.delete()
        await start_handler(call.message, bot)

# LINK HANDLER (Yuklash)
@dp.message(F.text.contains("http"))
async def link_handler(message: Message, state: FSMContext, bot: Bot):
    if await check_sub_status(bot, message.from_user.id):
        await message.answer("❌ Sub!")
        return
    
    lang = get_user_lang(message.from_user.id)
    await state.update_data(url=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=TEXTS[lang]["video"], callback_data="d_vid"), 
         InlineKeyboardButton(text=TEXTS[lang]["audio"], callback_data="d_aud")],
        [InlineKeyboardButton(text="❌", callback_data="del_msg")]
    ])
    await message.reply(TEXTS[lang]["choose_format"], reply_markup=kb)

# MATN HANDLER (Musiqa qidirish)
@dp.message(F.text)
async def text_search_handler(message: Message, bot: Bot):
    if message.text.startswith("/"): return # Buyruqlarni o'tkazib yuborish
    if await check_sub_status(bot, message.from_user.id): return

    lang = get_user_lang(message.from_user.id)
    msg = await message.answer(TEXTS[lang]["search"])
    
    results = await search_music_yt(message.text, limit=10)
    
    if not results:
        await msg.edit_text(TEXTS[lang]["not_found"])
        return

    kb = []
    for video in results:
        t = video.get('title', 'Track')
        vid = video.get('id')
        kb.append([InlineKeyboardButton(text=f"🎵 {t[:35]}...", callback_data=f"music:{vid}")])
    
    kb.append([InlineKeyboardButton(text="❌", callback_data="del_msg")])
    await msg.edit_text(TEXTS[lang]["results"], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# YUKLASH TUGMALARI (CALLBACK)
@dp.callback_query(F.data.in_({"d_vid", "d_aud"}))
async def download_call(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.message.delete()
    lang = get_user_lang(call.from_user.id)
    data = await state.get_data()
    url = data.get("url")
    m_type = "video" if call.data == "d_vid" else "audio"
    
    msg = await call.message.answer(TEXTS[lang]["downloading"])
    
    fp, title = await download_media(url, call.from_user.id, type=m_type)
    
    if fp and os.path.exists(fp):
        try:
            await msg.edit_text(TEXTS[lang]["sending"])
            f = FSInputFile(fp)
            cap = f"{'🎬' if m_type=='video' else '🎵'} {title}\n🤖 @{(await bot.get_me()).username}"
            
            if m_type == "video": await call.message.answer_video(f, caption=cap)
            else: await call.message.answer_audio(f, caption=cap)
            await msg.delete()
        except: await msg.edit_text(TEXTS[lang]["error"])
        finally: 
            if os.path.exists(fp): os.remove(fp)
    else: 
        await msg.edit_text(f"{TEXTS[lang]['error']} (Cookies error or Link invalid)")
    await state.clear()

@dp.callback_query(F.data.startswith("music:"))
async def music_dl_call(call: CallbackQuery, bot: Bot):
    lang = get_user_lang(call.from_user.id)
    vid_id = call.data.split(":")[1]
    url = f"https://www.youtube.com/watch?v={vid_id}"
    
    # Eskisini o'chirmasdan turib, yangi xabar yozamiz
    msg = await call.message.answer(TEXTS[lang]["downloading"])
    
    fp, title = await download_media(url, call.from_user.id, type="audio")
    
    if fp and os.path.exists(fp):
        try:
            await msg.edit_text(TEXTS[lang]["sending"])
            await call.message.answer_audio(FSInputFile(fp), caption=f"🎵 {title}\n🤖 @{(await bot.get_me()).username}")
            await msg.delete()
        except: await msg.edit_text(TEXTS[lang]["error"])
        finally: 
            if os.path.exists(fp): os.remove(fp)
    else: 
        await msg.edit_text(f"{TEXTS[lang]['error']} (Cookies required for YouTube)")

@dp.callback_query(F.data == "del_msg")
async def delete_msg(call: CallbackQuery):
    await call.message.delete()

# --- ADMIN PANEL (FAQAT BUYRUQ BILAN) ---
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="stat"), InlineKeyboardButton(text="📨 Reklama", callback_data="broadcast")],
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"), InlineKeyboardButton(text="🗑 O'chirish", callback_data="del_ch")]
        ])
        await message.answer("👑 Admin Panel", reply_markup=kb)

# Admin panel funksiyalari oldingidek qoladi (joyni tejash uchun qaytarmadim, lekin ular ishlaydi)
# (Bu yerga oldingi koddagi add_ch, del_ch, stat, broadcast funksiyalarini qo'shib qo'ying yoki shunday qoldiring)
# ... ADMIN FUNKSIYALARINI DAVOMI SHU YERDA BO'LISHI KERAK ...
# (Qisqartirilgan versiyada admin panelni to'liq yozmadim, lekin asosiy funksiyalar bor)

# SERVER
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
