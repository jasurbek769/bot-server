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
ADMIN_ID = 7950261926  # <-- O'Z ID RAQAMINGIZNI YOZING!

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
    add_ch_link = State() # Faqat link so'raymiz
    reply_msg = State()

class UserState(StatesGroup):
    waiting_for_question = State()
    search_music = State()

async def check_sub_status(bot: Bot, user_id: int):
    if user_id == ADMIN_ID: return [] # Adminni tekshirmasin
    channels = get_channels_db()
    not_subbed = []
    for link, ch_id in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subbed.append((link, ch_id))
        except: 
            # Agar bot admin bo'lmasa yoki xato bo'lsa
            continue
    return not_subbed

async def download_media(url, user_id, type="video"):
    ext = "mp4" if type == "video" else "mp3"
    file_name = f"{DOWNLOAD_PATH}/{user_id}_media.{ext}"
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    format_spec = 'best' if type == "video" else 'bestaudio/best'
    ydl_opts = {
        'format': format_spec,
        'outtmpl': file_name,
        'noplaylist': True,
        'quiet': True,
        'cookiefile': cookie_file,
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return file_name, info.get('title', 'Media')
    except Exception as e: return None, None

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
# 4. BOT MENYULARI (ODDIY VA ADMIN UCHUN ALOHIDA)
# -----------------------------------------------------------
def get_main_menu(user_id):
    # Oddiy foydalanuvchi uchun menyu
    buttons = [
        [KeyboardButton(text="📥 Video Yuklash"), KeyboardButton(text="🎧 Qo'shiq topish")],
        [KeyboardButton(text="📞 Admin bilan aloqa")]
    ]
    
    # AGAR ADMIN BO'LSA - Qo'shimcha tugmalar qo'shiladi
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="👑 Admin Panel")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# Admin Panel tugmalari (Bot ichida)
admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📨 Reklama yuborish")],
        [KeyboardButton(text="➕ Kanal qo'shish"), KeyboardButton(text="🗑 Kanal o'chirish")],
        [KeyboardButton(text="🏠 Bosh menyu")]
    ],
    resize_keyboard=True
)

# -----------------------------------------------------------
# 5. HANDLERS
# -----------------------------------------------------------

@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id)
    
    # Obuna tekshiruvi
    not_subbed = await check_sub_status(bot, message.from_user.id)
    if not_subbed:
        kb = [[InlineKeyboardButton(text="➕ A'zo bo'lish", url=l)] for l, _ in not_subbed]
        kb.append([InlineKeyboardButton(text="✅ A'zo bo'ldim", callback_data="check_sub")])
        await message.answer("⚠️ <b>Bot ishlashi uchun mana bu kanallarga qo'shiling:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.answer(
            f"👋 Salom, {message.from_user.full_name}!\n\n"
            "Men orqali Video yuklashingiz yoki Musiqa topishingiz mumkin.\n"
            "Pastdagi tugmalardan birini tanlang 👇", 
            reply_markup=get_main_menu(message.from_user.id)
        )

@dp.callback_query(F.data == "check_sub")
async def check_callback(call: CallbackQuery, bot: Bot):
    if await check_sub_status(bot, call.from_user.id):
        await call.answer("❌ Hali qo'shilmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        await call.message.answer("🎉 Rahmat! Bot ishga tushdi.", reply_markup=get_main_menu(call.from_user.id))

# --- MENYU TUGMALARI ---
@dp.message(F.text == "📥 Video Yuklash")
async def menu_download(message: Message):
    await message.answer("Linkni yuboring (Instagram, TikTok, YouTube):")

@dp.message(F.text == "🎧 Qo'shiq topish")
async def menu_music(message: Message, state: FSMContext):
    await message.answer("Qo'shiq nomini yoki aytgan odamni yozing:")
    await state.set_state(UserState.search_music)

@dp.message(UserState.search_music)
async def search_music_handler(message: Message, state: FSMContext):
    msg = await message.answer("🔍 Qidiryapman...")
    results = await search_music_yt(message.text)
    
    if not results:
        await msg.edit_text("❌ Hech narsa topilmadi.")
        await state.clear()
        return

    kb = []
    for video in results:
        title = video.get('title', 'Noma\'lum')
        vid_id = video.get('id')
        kb.append([InlineKeyboardButton(text=f"🎵 {title}", callback_data=f"music:{vid_id}")])
    
    kb.append([InlineKeyboardButton(text="❌ Yopish", callback_data="cancel")])
    await msg.edit_text(f"👇 <b>'{message.text}' bo'yicha topilganlar:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.clear()

@dp.callback_query(F.data.startswith("music:"))
async def download_music_callback(call: CallbackQuery, bot: Bot):
    vid_id = call.data.split(":")[1]
    url = f"https://www.youtube.com/watch?v={vid_id}"
    await call.message.delete()
    msg = await call.message.answer("⏳ Yuklabyabman...")
    
    file_path, title = await download_media(url, call.from_user.id, type="audio")
    if file_path and os.path.exists(file_path):
        try:
            await msg.edit_text("📤 Yuboryapman...")
            await call.message.answer_audio(FSInputFile(file_path), caption=f"🎵 {title}\n🤖 @{(await bot.get_me()).username}")
            await msg.delete()
        except: await msg.edit_text("❌ Xatolik.")
        finally: 
            if os.path.exists(file_path): os.remove(file_path)
    else: await msg.edit_text("❌ Yuklab bo'lmadi.")

# --- ADMIN PANEL (Faqat Admin uchun ko'rinadi) ---
@dp.message(F.text == "👑 Admin Panel")
async def admin_panel_btn(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Xush kelibsiz, Boss! 😎", reply_markup=admin_kb)

@dp.message(F.text == "🏠 Bosh menyu")
async def back_home(message: Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))

@dp.message(F.text == "📊 Statistika")
async def show_stat_msg(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(f"👥 Jami odamlar: <b>{get_users_count()} ta</b>")

@dp.message(F.text == "📨 Reklama yuborish")
async def ask_broadcast_msg(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Reklama xabarini yuboring (Rasm, matn yoki video):", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminState.broadcast)

@dp.message(AdminState.broadcast)
async def send_broadcast_msg(message: Message, state: FSMContext):
    users = get_all_users()
    await message.answer(f"🚀 Xabar {len(users)} kishiga ketdi...")
    c = 0
    for u in users:
        try:
            await message.copy_to(chat_id=u)
            c += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Yetib bordi: {c} ta", reply_markup=admin_kb)
    await state.clear()

# --- KANAL QO'SHISH (LINK ORQALI) ---
@dp.message(F.text == "➕ Kanal qo'shish")
async def add_channel_msg(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "Kanal linkini yoki usernamesini yuboring.\n"
            "Misol: <code>@mening_kanalim</code> yoki <code>https://t.me/kanalim</code>\n\n"
            "⚠️ <b>Diqqat:</b> Bot o'sha kanalda <b>ADMIN</b> bo'lishi shart!",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(AdminState.add_ch_link)

@dp.message(AdminState.add_ch_link)
async def process_add_channel(message: Message, state: FSMContext, bot: Bot):
    link = message.text.strip()
    
    # Username ni ajratib olish
    username = link
    if "t.me/" in link:
        username = "@" + link.split("t.me/")[-1]
    
    msg = await message.answer("⏳ Kanal tekshirilmoqda...")
    
    try:
        # Bot o'zi kanal ID sini topishga harakat qiladi
        chat = await bot.get_chat(username)
        ch_id = str(chat.id)
        title = chat.title
        
        # Bazaga qo'shish
        add_channel_db(link, ch_id)
        await msg.edit_text(f"✅ <b>Kanal qo'shildi!</b>\n\n📢 Nomi: {title}\n🆔 ID: {ch_id}")
        await message.answer("Yana nima qilamiz?", reply_markup=admin_kb)
        
    except Exception as e:
        await msg.edit_text(
            f"❌ <b>Xatolik!</b> Bot kanalni topa olmadi.\n\n"
            "1. Botni kanalga <b>Admin</b> qildingizmi?\n"
            "2. Kanal username (@nomi) to'g'rimi?\n"
            f"Xato: {e}"
        )
    
    await state.clear()

@dp.message(F.text == "🗑 Kanal o'chirish")
async def del_channel_msg(message: Message):
    if message.from_user.id == ADMIN_ID:
        channels = get_channels_db()
        kb = [[InlineKeyboardButton(text=f"❌ {l}", callback_data=f"del:{i}")] for l, i in channels]
        if not kb: await message.answer("Kanallar yo'q")
        else: await message.answer("O'chirish uchun tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del:"))
async def del_ch_action(call: CallbackQuery):
    del_channel_db(call.data.split(":")[1])
    await call.answer("O'chirildi")
    await call.message.delete()

# --- ALOQA TIZIMI ---
@dp.message(F.text == "📞 Admin bilan aloqa")
async def contact_admin_msg(message: Message, state: FSMContext):
    await message.answer("Xabaringizni yozing:")
    await state.set_state(UserState.waiting_for_question)

@dp.message(UserState.waiting_for_question)
async def send_to_admin(message: Message, state: FSMContext, bot: Bot):
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📨 <b>YANGI XABAR!</b>\n👤 {message.from_user.full_name}\n🆔 ID: <code>{message.from_user.id}</code>\n\n📄 {message.text}"
        )
        await message.answer("✅ Yuborildi! Admin javob berishini kuting.")
    except: await message.answer("Xatolik.")
    await state.clear()

@dp.message(F.reply_to_message)
async def reply_to_user(message: Message, bot: Bot):
    if message.from_user.id == ADMIN_ID:
        try:
            txt = message.reply_to_message.text
            if "ID:" in txt:
                uid = int(txt.split("ID:")[1].split("\n")[0].replace("<code>", "").replace("</code>", "").strip())
                await bot.send_message(uid, f"☎️ <b>Javob:</b>\n{message.text}")
                await message.answer("Yuborildi.")
        except: pass

# --- LINK HANDLER ---
@dp.message(F.text.contains("http"))
async def link_handler(message: Message, state: FSMContext, bot: Bot):
    if await check_sub_status(bot, message.from_user.id):
        await message.answer("❌ Bot ishlashi uchun kanallarga qo'shiling!")
        return
    await state.update_data(url=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Video", callback_data="g_vid"), InlineKeyboardButton(text="🎵 Audio", callback_data="g_aud")],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")]
    ])
    await message.reply("Qaysi formatda?", reply_markup=kb)

@dp.callback_query(F.data.in_({"g_vid", "g_aud"}))
async def get_media_call(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.message.delete()
    data = await state.get_data()
    url = data.get("url")
    t = "video" if call.data == "g_vid" else "audio"
    msg = await call.message.answer("⏳ Yuklabyabman...")
    
    fp, title = await download_media(url, call.from_user.id, type=t)
    if fp and os.path.exists(fp):
        try:
            await msg.edit_text("📤 Yuboryapman...")
            f = FSInputFile(fp)
            cap = f"{title}\n🤖 @{(await bot.get_me()).username}"
            if t == "video": await call.message.answer_video(f, caption=cap)
            else: await call.message.answer_audio(f, caption=cap)
            await msg.delete()
        except: await msg.edit_text("Xato.")
        finally: 
            if os.path.exists(fp): os.remove(fp)
    else: await msg.edit_text("❌ Yuklab bo'lmadi.")
    await state.clear()

@dp.callback_query(F.data == "cancel")
async def cancel_op(call: CallbackQuery, state: FSMContext):
    await call.message.delete()
    await state.clear()

# --- SERVER ---
async def health_check(request): return web.Response(text="OK")
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    db_start()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await asyncio.gather(dp.start_polling(bot), start_web_server())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
