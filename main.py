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
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

# -----------------------------------------------------------
# 1. SOZLAMALAR
# -----------------------------------------------------------
TOKEN = "7474552293:AAGd1oB9nJGiJKI9MjPMoxN2Oosebvli6Jg"
ADMIN_ID = 7950261926  # <-- ID RAQAMINGIZNI YOZING!

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
# 3. MANTIQ
# -----------------------------------------------------------
class AdminState(StatesGroup):
    broadcast = State()
    add_ch_link = State()
    add_ch_id = State()

class UserState(StatesGroup):
    waiting_for_question = State()
    search_music = State()

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

# UNIVERSAL YUKLASH (VIDEO & AUDIO AJRATISH)
async def download_media(url, user_id, type="video"):
    # Fayl formati
    ext = "mp4" if type == "video" else "mp3"
    file_name = f"{DOWNLOAD_PATH}/{user_id}_media.{ext}"
    
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    # Agar Audio bo'lsa, faqat eng sifatli ovozni olamiz
    if type == "video":
        format_spec = 'best'
    else:
        format_spec = 'bestaudio/best' # <-- SIRI SHU YERDA
        
    ydl_opts = {
        'format': format_spec,
        'outtmpl': file_name,
        'noplaylist': True,
        'quiet': True,
        'cookiefile': cookie_file,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return file_name, info.get('title', 'Media')
    except Exception as e: return None, None

# QO'SHIQ QIDIRISH (SEARCH)
async def search_music_yt(query):
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    ydl_opts = {'quiet': True, 'cookiefile': cookie_file, 'noplaylist': True, 'extract_flat': True, 'default_search': 'ytsearch5'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if 'entries' in info: return info['entries']
    except: pass
    return []

# -----------------------------------------------------------
# 4. BOT HANDLERS
# -----------------------------------------------------------
def get_main_menu(user_id):
    btns = [[KeyboardButton(text="📥 Link orqali yuklash"), KeyboardButton(text="🎧 Musiqa izlash")],
            [KeyboardButton(text="📞 Admin bilan aloqa")]]
    if user_id == ADMIN_ID: btns.append([KeyboardButton(text="👑 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)

@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id)
    if await check_sub_status(bot, message.from_user.id):
        kb = [[InlineKeyboardButton(text="➕ Kanalga qo'shilish", url=l)] for l, _ in get_channels_db()]
        kb.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer("⚠️ Botdan foydalanish uchun kanalga qo'shiling:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.answer(f"👋 Salom, {message.from_user.full_name}!\nLink tashlang yoki menyudan tanlang 👇", reply_markup=get_main_menu(message.from_user.id))

@dp.callback_query(F.data == "check_sub")
async def check_callback(call: CallbackQuery, bot: Bot):
    if await check_sub_status(bot, call.from_user.id): await call.answer("❌ Hali qo'shilmadingiz!", show_alert=True)
    else: 
        await call.message.delete()
        await call.message.answer("🎉 Rahmat! Bot ishga tushdi.", reply_markup=get_main_menu(call.from_user.id))

# MENYU
@dp.message(F.text == "📥 Link orqali yuklash")
async def menu_down(message: Message): await message.answer("Instagram, TikTok yoki YouTube linkini yuboring:")

@dp.message(F.text == "🎧 Musiqa izlash")
async def menu_music(message: Message, state: FSMContext):
    await message.answer("Qo'shiqchi yoki qo'shiq nomini yozing:")
    await state.set_state(UserState.search_music)

@dp.message(UserState.search_music)
async def search_handler(message: Message, state: FSMContext):
    msg = await message.answer("🔍 Qidiryapman...")
    res = await search_music_yt(message.text)
    if not res:
        await msg.edit_text("❌ Topilmadi.")
        await state.clear()
        return
    kb = []
    for v in res: kb.append([InlineKeyboardButton(text=f"🎵 {v.get('title', 'Nomisiz')}", callback_data=f"music:{v.get('id')}")])
    kb.append([InlineKeyboardButton(text="❌ Yopish", callback_data="cancel")])
    await msg.edit_text(f"👇 '{message.text}' bo'yicha:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.clear()

@dp.callback_query(F.data.startswith("music:"))
async def dl_music_call(call: CallbackQuery, bot: Bot):
    url = f"https://www.youtube.com/watch?v={call.data.split(':')[1]}"
    await call.message.delete()
    msg = await call.message.answer("⏳ Musiqa yuklanyapti...")
    fp, title = await download_media(url, call.from_user.id, type="audio")
    if fp and os.path.exists(fp):
        try:
            await msg.edit_text("📤 Yuboryapman...")
            await call.message.answer_audio(FSInputFile(fp), caption=f"🎵 {title}\n🤖 @{(await bot.get_me()).username}")
            await msg.delete()
        except: await msg.edit_text("Xato")
        finally: 
            if os.path.exists(fp): os.remove(fp)
    else: await msg.edit_text("❌ Xatolik.")

# ADMIN PANEL
@dp.message(F.text == "👑 Admin Panel")
async def admin_p(message: Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="stat"), InlineKeyboardButton(text="📨 Reklama", callback_data="broadcast")],
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"), InlineKeyboardButton(text="🗑 O'chirish", callback_data="del_ch")]
        ])
        await message.answer("Admin Panel:", reply_markup=kb)

@dp.callback_query(F.data == "stat")
async def stat_call(call: CallbackQuery): await call.answer(f"Odamlar: {get_users_count()}", show_alert=True)

@dp.callback_query(F.data == "broadcast")
async def broad_call(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Reklamani yuboring:")
    await state.set_state(AdminState.broadcast)

@dp.message(AdminState.broadcast)
async def broad_send(message: Message, state: FSMContext):
    u = get_all_users()
    await message.answer(f"Ketdi ({len(u)})...")
    c = 0
    for i in u:
        try:
            await message.copy_to(i)
            c += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"Yetib bordi: {c}")
    await state.clear()

@dp.callback_query(F.data == "add_ch")
async def add_ch_c(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal linkini yuboring (@kanal yoki link):")
    await state.set_state(AdminState.add_ch_link)

@dp.message(AdminState.add_ch_link)
async def add_ch_msg(message: Message, state: FSMContext, bot: Bot):
    link = message.text.strip()
    uname = link.split("/")[-1] if "/" in link else link
    if not uname.startswith("@") and not "t.me" in link: uname = "@" + uname
    
    try:
        chat = await bot.get_chat(uname)
        add_channel_db(link, str(chat.id))
        await message.answer(f"✅ Qo'shildi!\nNomi: {chat.title}\nID: {chat.id}")
    except: await message.answer("❌ Kanal topilmadi. Botni kanalga Admin qiling!")
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

# LINK VA AUDIO AJRATISH
@dp.message(F.text.contains("http"))
async def link_h(message: Message, state: FSMContext, bot: Bot):
    if await check_sub_status(bot, message.from_user.id):
        await message.answer("❌ Kanalga qo'shiling!")
        return
    await state.update_data(url=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Video", callback_data="d_vid"), InlineKeyboardButton(text="🎵 Musiqasini olish (MP3)", callback_data="d_aud")],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")]
    ])
    await message.reply("Nimasini yuklaymiz?", reply_markup=kb)

@dp.callback_query(F.data.in_({"d_vid", "d_aud"}))
async def down_call(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.message.delete()
    data = await state.get_data()
    t = "video" if call.data == "d_vid" else "audio"
    msg = await call.message.answer("⏳ Yuklanyapti...")
    
    fp, title = await download_media(data.get("url"), call.from_user.id, type=t)
    if fp and os.path.exists(fp):
        try:
            await msg.edit_text("📤 Yuboryapman...")
            f = FSInputFile(fp)
            cap = f"{'🎬' if t=='video' else '🎵'} {title}\n🤖 @{(await bot.get_me()).username}"
            if t == "video": await call.message.answer_video(f, caption=cap)
            else: await call.message.answer_audio(f, caption=cap)
            await msg.delete()
        except: await msg.edit_text("Xato")
        finally: 
            if os.path.exists(fp): os.remove(fp)
    else: await msg.edit_text("❌ Xatolik.")
    await state.clear()

@dp.callback_query(F.data == "cancel")
async def can_cl(call: CallbackQuery, state: FSMContext):
    await call.message.delete()
    await state.clear()

# ALOQA
@dp.message(F.text == "📞 Admin bilan aloqa")
async def contact_m(message: Message, state: FSMContext):
    await message.answer("Xabarni yozing:")
    await state.set_state(UserState.waiting_for_question)

@dp.message(UserState.waiting_for_question)
async def sent_q(message: Message, state: FSMContext, bot: Bot):
    try:
        await bot.send_message(ADMIN_ID, f"📨 <b>Xabar:</b>\n{message.from_user.full_name} (ID: <code>{message.from_user.id}</code>):\n\n{message.text}")
        await message.answer("✅ Yuborildi.")
    except: pass
    await state.clear()

@dp.message(F.reply_to_message)
async def rep_adm(message: Message, bot: Bot):
    if message.from_user.id == ADMIN_ID:
        try:
            uid = int(message.reply_to_message.text.split("ID:")[1].split(")")[0].replace("<code>", "").replace("</code>", "").strip())
            await bot.send_message(uid, f"☎️ <b>Javob:</b>\n{message.text}")
            await message.answer("Ketdi.")
        except: pass

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
