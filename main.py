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

# --- SOZLAMALAR ---
TOKEN = "7474552293:AAGd1oB9nJGiJKI9MjPMoxN2Oosebvli6Jg"
ADMIN_ID = 7950261926 

dp = Dispatcher()
DOWNLOAD_PATH = "downloads"
if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)

# --- MATNLAR ---
TEXTS = {
    "uz": {
        "welcome": (
            "🎧 <b>Assalomu alaykum! @MeningBotim ga Xush kelibsiz.</b>\n\n"
            "Bu bot orqali siz:\n"
            "🔥 <b>Trenddagi Top Musiqalarni</b> tinglashingiz,\n"
            "🔍 <b>Istalgan qo'shiqni</b> nomini yozib topishingiz,\n"
            "📥 <b>Instagram, TikTok, YouTube</b> videolarini yuklashingiz mumkin.\n\n"
            "👇 <b>Qo'shiq topish uchun nomini yozing yoki quyidagi buyruqlardan foydalaning:</b>"
        ),
        "search": "🔍 <b>Qidirilmoqda...</b>",
        "not_found": "⚠️ <b>Afsuski musiqa topilmadi.</b>",
        "downloading": "⏳ <b>Yuklanmoqda...</b>",
        "sending": "📤 <b>Yuborilmoqda...</b>",
        "error": "❌ Xatolik yuz berdi.",
        "sub_check": "⚠️ Botdan foydalanish uchun kanalga a'zo bo'ling:",
        "btn_sub": "➕ A'zo bo'lish",
        "btn_verify": "✅ Tasdiqlash",
        "choose": "Formatni tanlang:",
        "video": "🎬 Video",
        "audio": "🎵 Audio (MP3)",
        "top_title": "🔥 <b>O'zbekiston TOP 10 (Trend):</b>",
        "new_title": "🆕 <b>Jahon Xitlari (Yangi):</b>",
        "lang_set": "✅ Til o'zgartirildi: O'zbekcha"
    },
    "ru": {
        "welcome": (
            "🎧 <b>Привет! Добро пожаловать в @MeningBotim.</b>\n\n"
            "Здесь вы можете:\n"
            "🔥 Слушать <b>ТОП Треки</b>,\n"
            "🔍 Найти <b>любую песню</b> по названию,\n"
            "📥 Скачать видео с <b>Instagram, TikTok, YouTube</b>.\n\n"
            "👇 <b>Напишите название песни для поиска или выберите команду:</b>"
        ),
        "search": "🔍 <b>Поиск...</b>",
        "not_found": "⚠️ <b>Музыка не найдена.</b>",
        "downloading": "⏳ <b>Загрузка...</b>",
        "sending": "📤 <b>Отправка...</b>",
        "error": "❌ Ошибка.",
        "sub_check": "⚠️ Подпишитесь на канал:",
        "btn_sub": "➕ Подписаться",
        "btn_verify": "✅ Проверить",
        "choose": "Выберите формат:",
        "video": "🎬 Видео",
        "audio": "🎵 Аудио (MP3)",
        "top_title": "🔥 <b>ТОП 10 Узбекистан (Тренд):</b>",
        "new_title": "🆕 <b>Мировые Хиты (New):</b>",
        "lang_set": "✅ Язык изменен: Русский"
    }
}

# --- BAZA ---
def db_start():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'uz')")
    cur.execute("CREATE TABLE IF NOT EXISTS channels (link TEXT, id TEXT)")
    conn.commit(); conn.close()

def add_user(user_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, lang) VALUES (?, 'uz')", (user_id,))
    conn.commit(); conn.close()

def get_lang(user_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
    r = cur.fetchone(); conn.close()
    return r[0] if r else "uz"

def set_lang(user_id, lang):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
    conn.commit(); conn.close()

# Kanal funksiyalari
def get_channels():
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("SELECT * FROM channels"); r = cur.fetchall(); conn.close(); return r
def add_channel(link, ch_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("INSERT INTO channels VALUES (?, ?)", (link, ch_id)); conn.commit(); conn.close()
def del_channel(ch_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("DELETE FROM channels WHERE id=?", (ch_id,)); conn.commit(); conn.close()

# --- MANTIQ ---
class AdminState(StatesGroup):
    add_ch_link = State()

async def check_sub(bot, user_id):
    if user_id == ADMIN_ID: return []
    ch = get_channels()
    not_sub = []
    for l, i in ch:
        try:
            m = await bot.get_chat_member(i, user_id)
            if m.status in ['left', 'kicked']: not_sub.append((l, i))
        except: pass
    return not_sub

# --- SUPER YUKLASH FUNKSIYASI (Musiqa uchun optimallashtirilgan) ---
async def dl_media(url, user_id, type="video"):
    ext = "mp4" if type == "video" else "mp3"
    fn = f"{DOWNLOAD_PATH}/{user_id}.{ext}"
    
    opts = {
        'outtmpl': fn,
        'noplaylist': True,
        'quiet': True,
        # Cookies fayli SHART EMAS, chunki biz User-Agent ishlatamiz
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    if type == "audio": 
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{  # MP3 ga aylantirish (Sifatni oshiradi)
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else: 
        opts['format'] = 'bestvideo+bestaudio/best'
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return fn if type == "video" else fn.replace(".mp3", ".mp3"), info.get('title', 'Media')
    except Exception as e: 
        print(e)
        return None, None

# --- QIDIRUV (TOP MUSIQA) ---
async def search_yt(q, limit=10):
    opts = {
        'quiet': True, 
        'noplaylist': True, 
        'extract_flat': True, 
        'default_search': f'ytsearch{limit}',
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(f"ytsearch{limit}:{q}", download=False)
            return res.get('entries', [])
    except: return []

# -----------------------------------------------------------
# HANDLERS
# -----------------------------------------------------------
@dp.message(CommandStart())
async def start(m: Message, bot: Bot):
    add_user(m.from_user.id)
    l = get_lang(m.from_user.id)
    
    ns = await check_sub(bot, m.from_user.id)
    if ns:
        kb = [[InlineKeyboardButton(text=TEXTS[l]["btn_sub"], url=x[0])] for x in ns]
        kb.append([InlineKeyboardButton(text=TEXTS[l]["btn_verify"], callback_data="check")])
        return await m.answer(TEXTS[l]["sub_check"], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    
    await bot.set_my_commands([
        BotCommand(command="start", description="Restart"),
        BotCommand(command="top", description="🔥 TOP Uzbekistan"),
        BotCommand(command="new", description="🌍 TOP World"),
        BotCommand(command="lang", description="🌐 Til/Language"),
    ])
    await m.answer(TEXTS[l]["welcome"], disable_web_page_preview=True)

@dp.message(Command("lang"))
async def lang_h(m: Message):
    kb = [[InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"), InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")]]
    await m.answer("👇", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("lang:"))
async def set_l(c: CallbackQuery):
    l = c.data.split(":")[1]
    set_lang(c.from_user.id, l)
    await c.message.delete()
    await c.message.answer(TEXTS[l]["lang_set"])
    await start(c.message, c.bot)

@dp.callback_query(F.data == "check")
async def check_c(c: CallbackQuery, bot: Bot):
    if await check_sub(bot, c.from_user.id): await c.answer("❌", show_alert=True)
    else: await c.message.delete(); await start(c.message, bot)

# TOP & NEW (Musica qidirishni avtomatlashtirish)
@dp.message(Command("top"))
async def top_m(m: Message):
    l = get_lang(m.from_user.id)
    await m.answer(TEXTS[l]["search"])
    # O'zbekistonning eng zo'r qo'shiqlarini qidiradi
    res = await search_yt("Uzbekistan Top 10 Music Hits 2025", 10)
    await show_res(m, res, TEXTS[l]["top_title"])

@dp.message(Command("new"))
async def new_m(m: Message):
    l = get_lang(m.from_user.id)
    await m.answer(TEXTS[l]["search"])
    # Jahon xitlarini qidiradi
    res = await search_yt("Global Top Songs 2025", 10)
    await show_res(m, res, TEXTS[l]["new_title"])

async def show_res(m, res, title):
    if not res: return await m.answer("❌")
    kb = []
    for v in res: kb.append([InlineKeyboardButton(text=f"🎵 {v['title'][:35]}", callback_data=f"m:{v['id']}")])
    kb.append([InlineKeyboardButton(text="❌", callback_data="del")])
    await m.answer(title, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# LINK (Video Yuklash)
@dp.message(F.text.contains("http"))
async def link_h(m: Message, state: FSMContext, bot: Bot):
    if await check_sub(bot, m.from_user.id): return await m.answer("❌ Sub!")
    l = get_lang(m.from_user.id)
    await state.update_data(url=m.text)
    kb = [[InlineKeyboardButton(text=TEXTS[l]["video"], callback_data="vid"), InlineKeyboardButton(text=TEXTS[l]["audio"], callback_data="aud")]]
    await m.reply(TEXTS[l]["choose"], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ODDIY SEARCH (Qo'shiq qidirish)
@dp.message(F.text)
async def search_h(m: Message, bot: Bot):
    if m.text.startswith("/"): return
    if await check_sub(bot, m.from_user.id): return
    l = get_lang(m.from_user.id)
    msg = await m.answer(TEXTS[l]["search"])
    
    # Qidiruv
    res = await search_yt(m.text, limit=10)
    
    if not res: return await msg.edit_text(TEXTS[l]["not_found"])
    
    kb = []
    for v in res:
        kb.append([InlineKeyboardButton(text=f"🎵 {v['title'][:40]}", callback_data=f"m:{v['id']}")])
    kb.append([InlineKeyboardButton(text="❌", callback_data="del")])
    await msg.edit_text(f"👇 <b>{m.text}</b> bo'yicha natijalar:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# CALLBACKLAR
@dp.callback_query(F.data.in_({"vid", "aud"}))
async def dl_call(c: CallbackQuery, state: FSMContext):
    await c.message.delete()
    l = get_lang(c.from_user.id)
    d = await state.get_data()
    t = "video" if c.data == "vid" else "audio"
    msg = await c.message.answer(TEXTS[l]["downloading"])
    fp, ti = await dl_media(d.get("url"), c.from_user.id, t)
    if fp and os.path.exists(fp):
        try:
            await msg.edit_text(TEXTS[l]["sending"])
            f = FSInputFile(fp)
            cap = f"{ti}\n🤖 @{(await c.bot.get_me()).username}"
            if t == "video": await c.message.answer_video(f, caption=cap)
            else: await c.message.answer_audio(f, caption=cap)
            await msg.delete()
        except: await msg.edit_text("Error sending file")
        finally: 
            if os.path.exists(fp): os.remove(fp)
    else: await msg.edit_text(TEXTS[l]["error"])
    await state.clear()

@dp.callback_query(F.data.startswith("m:"))
async def m_dl(c: CallbackQuery):
    url = f"https://youtube.com/watch?v={c.data.split(':')[1]}"
    await c.message.delete()
    l = get_lang(c.from_user.id)
    msg = await c.message.answer(TEXTS[l]["downloading"])
    
    # Faqat AUDIO yuklaymiz
    fp, ti = await dl_media(url, c.from_user.id, "audio")
    
    if fp and os.path.exists(fp):
        try:
            await msg.edit_text(TEXTS[l]["sending"])
            await c.message.answer_audio(FSInputFile(fp), caption=f"🎵 {ti}\n🤖 @{(await c.bot.get_me()).username}")
            await msg.delete()
        except: await msg.edit_text("Error sending file")
        finally: 
            if os.path.exists(fp): os.remove(fp)
    else: await msg.edit_text(TEXTS[l]["error"])

@dp.callback_query(F.data == "del")
async def del_m(c: CallbackQuery): await c.message.delete()

# ADMIN
@dp.message(Command("admin"))
async def adm(m: Message):
    if m.from_user.id == ADMIN_ID:
        kb = [[InlineKeyboardButton(text="➕ Kanal", callback_data="add_ch"), InlineKeyboardButton(text="🗑 O'chirish", callback_data="del_ch")]]
        await m.answer("Admin:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "add_ch")
async def add_c(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Link (@kanal):"); await state.set_state(AdminState.add_ch_link)

@dp.message(AdminState.add_ch_link)
async def save_ch(m: Message, state: FSMContext, bot: Bot):
    l = m.text; u = l.split("/")[-1]
    if "t.me" not in l and not u.startswith("@"): u = "@"+u
    try: c = await bot.get_chat(u); add_channel(l, str(c.id)); await m.answer("OK"); await state.clear()
    except: await m.answer("Xato! Bot adminmi?")

@dp.callback_query(F.data == "del_ch")
async def del_c(c: CallbackQuery):
    kb = [[InlineKeyboardButton(text=f"❌ {x[0]}", callback_data=f"rm:{x[1]}")] for x in get_channels()]
    if kb: await c.message.answer("O'chirish:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else: await c.answer("Bo'sh")

@dp.callback_query(F.data.startswith("rm:"))
async def rm_c(c: CallbackQuery): del_channel(c.data.split(":")[1]); await c.answer("O'chdi"); await c.message.delete()

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
