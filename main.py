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
# 1. SOZLAMALAR
# -----------------------------------------------------------
TOKEN = "7474552293:AAGd1oB9nJGiJKI9MjPMoxN2Oosebvli6Jg"
ADMIN_ID = 7950261926  # <-- O'Z ID RAQAMINGIZ!

dp = Dispatcher()
DOWNLOAD_PATH = "downloads"
if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)

# -----------------------------------------------------------
# 2. BAZA
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
# 3. STATES & MANTIQ
# -----------------------------------------------------------
class AdminState(StatesGroup):
    broadcast = State()
    add_ch_link = State()
    add_ch_id = State()
    reply_msg = State() # Javob yozish uchun

class UserState(StatesGroup):
    waiting_for_question = State() # Admin ga savol yozish holati

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

# -----------------------------------------------------------
# 4. BOT HANDLERS
# -----------------------------------------------------------

# ASOSIY MENYU TUGMALARI
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Video/Audio Yuklash"), KeyboardButton(text="📞 Admin bilan aloqa")],
        [KeyboardButton(text="📊 Statistika")]
    ],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id)
    not_subbed = await check_sub_status(bot, message.from_user.id)
    
    if not_subbed:
        kb = [[InlineKeyboardButton(text="➕ A'zo bo'lish", url=l)] for l, _ in not_subbed]
        kb.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer("⚠️ <b>Botdan to'liq foydalanish uchun kanallarga a'zo bo'ling:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.answer(
            f"👋 Assalomu alaykum, {message.from_user.full_name}!\n\n"
            "🤖 <b>Men Professional Yuklovchi va Yordamchi botman.</b>\n"
            "Quyidagi menudan kerakli bo'limni tanlang 👇", 
            reply_markup=main_menu
        )

@dp.callback_query(F.data == "check_sub")
async def check_callback(call: CallbackQuery, bot: Bot):
    if await check_sub_status(bot, call.from_user.id):
        await call.answer("❌ Hali a'zo bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        await call.message.answer("🎉 Rahmat! Endi bemalol foydalaning.", reply_markup=main_menu)

# --- MENYU BUYRUQLARI ---
@dp.message(F.text == "📥 Video/Audio Yuklash")
async def menu_download(message: Message):
    await message.answer("🔗 <b>TikTok, Instagram yoki YouTube linkini yuboring:</b>")

@dp.message(F.text == "📊 Statistika")
async def menu_stat(message: Message):
    count = get_users_count()
    await message.answer(f"👥 Bot foydalanuvchilari: <b>{count} ta</b>")

# --- ALOQA TIZIMI (FOYDALANUVCHI TOMONI) ---
@dp.message(F.text == "📞 Admin bilan aloqa")
async def contact_admin(message: Message, state: FSMContext):
    await message.answer("✍️ <b>Xabaringizni yozib qoldiring:</b>\n(Savol, taklif yoki shikoyat)")
    await state.set_state(UserState.waiting_for_question)

@dp.message(UserState.waiting_for_question)
async def receive_question(message: Message, state: FSMContext, bot: Bot):
    # Xabarni Adminga yuborish
    try:
        # Biz xabarni adminga forward qilamiz va tagiga ID sini yozamiz
        # Shunda admin Reply qilganda bot kimga javob qaytarishni biladi
        await bot.send_message(
            chat_id=ADMIN_ID, 
            text=f"📨 <b>YANGI MUROJAAT!</b>\n\n👤 <b>Kimdan:</b> {message.from_user.full_name}\n🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n📄 <b>Xabar:</b>\n{message.text}\n\n<i>Javob berish uchun shu xabarga Reply (Javob) qiling.</i>"
        )
        await message.answer("✅ <b>Xabaringiz Adminga yuborildi!</b>\nTez orada javob olasiz.")
    except Exception as e:
        await message.answer("❌ Xatolik yuz berdi.")
    
    await state.clear()

# --- ALOQA TIZIMI (ADMIN TOMONI - REPLY) ---
@dp.message(F.reply_to_message)
async def admin_reply_handler(message: Message, bot: Bot):
    # Faqat admin javob yozsa ishlaydi
    if message.from_user.id == ADMIN_ID:
        try:
            # Reply qilingan xabarning ichidan foydalanuvchi ID sini topishga harakat qilamiz
            original_text = message.reply_to_message.text
            
            # ID ni qidiramiz (Biz yuborgan format bo'yicha "ID: 12345" qatorini topish)
            user_id = None
            for line in original_text.split("\n"):
                if "ID:" in line:
                    user_id = int(line.split("ID:")[1].replace("<code>", "").replace("</code>", "").strip())
                    break
            
            if user_id:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"☎️ <b>ADMINDAN JAVOB:</b>\n\n{message.text}"
                )
                await message.answer("✅ Javob yuborildi!")
            else:
                await message.answer("❌ Foydalanuvchi ID sini topa olmadim. Murojaat formati buzilgan bo'lishi mumkin.")
                
        except Exception as e:
            await message.answer(f"❌ Xatolik: {e}")

# --- ADMIN PANEL (COMMAND) ---
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="stat"),
             InlineKeyboardButton(text="💾 Bazani yuklash", callback_data="backup")],
            [InlineKeyboardButton(text="📨 Reklama yuborish", callback_data="broadcast")],
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"), 
             InlineKeyboardButton(text="🗑 Kanal o'chirish", callback_data="del_ch")]
        ])
        await message.answer(f"👑 <b>Admin Panel</b>", reply_markup=kb)

# ... (ADMIN PANEL CALLBACKLARI - OLDINGI KOD BILAN BIR XIL) ...
@dp.callback_query(F.data == "stat")
async def show_stat(call: CallbackQuery):
    await call.answer(f"Jami: {get_users_count()}", show_alert=True)

@dp.callback_query(F.data == "backup")
async def backup_db(call: CallbackQuery):
    try:
        file = FSInputFile("bot.db")
        await call.message.answer_document(file, caption="📂 Baza.")
    except: await call.answer("Topilmadi", show_alert=True)

@dp.callback_query(F.data == "broadcast")
async def ask_broadcast(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Reklamani yuboring:")
    await state.set_state(AdminState.broadcast)

@dp.message(AdminState.broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    users = get_all_users()
    await message.answer(f"🚀 Ketdi... ({len(users)} ta)")
    c = 0
    for u in users:
        try:
            await message.copy_to(chat_id=u)
            c += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Yetib bordi: {c}")
    await state.clear()

@dp.callback_query(F.data == "add_ch")
async def ask_ch(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal LINKI:")
    await state.set_state(AdminState.add_ch_link)

@dp.message(AdminState.add_ch_link)
async def get_ch_l(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("Kanal IDsi (yoki Forward qiling):")
    await state.set_state(AdminState.add_ch_id)

@dp.message(AdminState.add_ch_id)
async def get_ch_i(message: Message, state: FSMContext):
    ch_id = str(message.forward_from_chat.id) if message.forward_from_chat else message.text
    d = await state.get_data()
    add_channel_db(d.get("link"), ch_id)
    await message.answer(f"✅ Qo'shildi: {ch_id}")
    await state.clear()

@dp.callback_query(F.data == "del_ch")
async def del_ch_show(call: CallbackQuery):
    kb = [[InlineKeyboardButton(text=f"❌ {l}", callback_data=f"del:{i}")] for l, i in get_channels_db()]
    if not kb: await call.answer("Bo'sh", show_alert=True)
    else: await call.message.answer("O'chirish:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del:"))
async def del_ch_do(call: CallbackQuery):
    del_channel_db(call.data.split(":")[1])
    await call.answer("O'chirildi")
    await call.message.delete()

# --- LINK HANDLER ---
@dp.message(F.text.contains("http"))
async def link_handler(message: Message, state: FSMContext, bot: Bot):
    if await check_sub_status(bot, message.from_user.id):
        await message.answer("❌ Kanallarga a'zo bo'ling!")
        return
    
    await state.update_data(url=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Video", callback_data="get_video"),
         InlineKeyboardButton(text="🎵 Audio (MP3)", callback_data="get_audio")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])
    await message.reply("Formatni tanlang:", reply_markup=kb)

@dp.callback_query(F.data.in_({"get_video", "get_audio"}))
async def process_media(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.message.delete()
    data = await state.get_data()
    url = data.get("url")
    m_type = "video" if call.data == "get_video" else "audio"
    
    msg = await call.message.answer("⏳ Yuklanmoqda...")
    file_path, title = await download_media(url, call.from_user.id, type=m_type)
    
    if file_path and os.path.exists(file_path):
        try:
            await msg.edit_text("📤 Yuborilmoqda...")
            media = FSInputFile(file_path)
            caption = f"{'🎬' if m_type=='video' else '🎵'} {title}\n🤖 @{(await bot.get_me()).username}"
            
            if m_type == "video": await call.message.answer_video(media, caption=caption)
            else: await call.message.answer_audio(media, caption=caption)
            await msg.delete()
        except: await msg.edit_text("❌ Xato.")
        finally: 
            if os.path.exists(file_path): os.remove(file_path)
    else: await msg.edit_text("❌ Yuklab bo'lmadi.")
    await state.clear()

@dp.callback_query(F.data == "cancel")
async def cancel_action(call: CallbackQuery, state: FSMContext):
    await call.message.delete()
    await state.clear()

# --- SERVER ---
async def health_check(request): return web.Response(text="Running")
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
