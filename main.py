import asyncio
import logging
import sys
import os
import random
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
import aiohttp
from dotenv import load_dotenv
from gtts import gTTS
from deep_translator import GoogleTranslator

# --- XAVFSIZLIK QISMI ---
load_dotenv()

# Tokenlarni Environment Variable dan olamiz
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)

dp = Dispatcher()
DOWNLOAD_PATH = "downloads"
if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)

# --- BAZA (Database) ---
def db_start():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    cur.execute("CREATE TABLE IF NOT EXISTS channels (link TEXT, id TEXT)")
    conn.commit(); conn.close()

def add_user(user_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,))
    conn.commit(); conn.close()

def get_channels_db():
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("SELECT * FROM channels"); return cur.fetchall()

def add_channel_db(link, ch_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("INSERT INTO channels VALUES (?, ?)", (link, ch_id)); conn.commit(); conn.close()

def del_channel_db(ch_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("DELETE FROM channels WHERE id = ?", (ch_id,)); conn.commit(); conn.close()

def get_users_count():
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users"); return cur.fetchone()[0]

def get_all_users():
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("SELECT user_id FROM users"); return [u[0] for u in cur.fetchall()]

# --- STATES (Holatlar) ---
# XATOLIK TOG'IRLANDI: Barcha statelar bitta class ichiga olindi
class ServiceState(StatesGroup):
    image_prompt = State()
    tts_text = State()
    trans_text = State()
    contact_admin = State()
    add_ch_link = State()  # Admin uchun
    broadcast = State()    # Admin uchun

# --- YORDAMCHI FUNKSIYALAR ---
async def check_sub(bot, user_id):
    if user_id == ADMIN_ID: return []
    channels = get_channels_db()
    not_sub = []
    for link, ch_id in channels:
        try:
            m = await bot.get_chat_member(ch_id, user_id)
            if m.status in ['left', 'kicked']: not_sub.append((link, ch_id))
        except: pass
    return not_sub

async def generate_image_api(prompt):
    seed = random.randint(1, 10000)
    safe_prompt = prompt.replace(" ", "%20")
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&seed={seed}&nologo=true"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200: return await resp.read()
    except: return None

# --- HANDLERS (Bot javoblari) ---
@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id)
    ns = await check_sub(bot, message.from_user.id)
    if ns:
        kb = [[InlineKeyboardButton(text="➕ A'zo bo'lish", url=l)] for l, _ in ns]
        kb.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer("⚠️ Botdan foydalanish uchun kanalga a'zo bo'ling:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Rasm Yasash", callback_data="srv_img"), InlineKeyboardButton(text="🗣 Ovoz (TTS)", callback_data="srv_tts")],
        [InlineKeyboardButton(text="🌍 Tarjimon", callback_data="srv_tr"), InlineKeyboardButton(text="📞 Admin", callback_data="contact")]
    ])
    if message.from_user.id == ADMIN_ID:
        kb.inline_keyboard.append([InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")])
    
    await message.answer(f"👋 <b>Salom {message.from_user.full_name}!</b>\nXizmatni tanlang:", reply_markup=kb)

@dp.callback_query(F.data == "check_sub")
async def check_cb(c: CallbackQuery, bot: Bot):
    if await check_sub(bot, c.from_user.id): await c.answer("❌ A'zo bo'lmadingiz!", show_alert=True)
    else: await c.message.delete(); await start_handler(c.message, bot)

@dp.callback_query(F.data == "back")
async def back_home(c: CallbackQuery, state: FSMContext):
    await state.clear(); await c.message.delete(); await start_handler(c.message, c.bot)

# --- 1. RASM ---
@dp.callback_query(F.data == "srv_img")
async def ask_img(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("🎨 <b>Nima chizib beray?</b> (Inglizcha yozing):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back")]]))
    await state.set_state(ServiceState.image_prompt)

@dp.message(ServiceState.image_prompt)
async def gen_img(m: Message, state: FSMContext):
    msg = await m.reply("🎨 Chizilmoqda...")
    img = await generate_image_api(m.text)
    if img:
        await msg.delete()
        await m.answer_photo(BufferedInputFile(img, "img.jpg"), caption=f"🖼 {m.text}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="back")]]))
    else: await msg.edit_text("Xatolik.")
    await state.clear()

# --- 2. OVOZ (TTS) ---
@dp.callback_query(F.data == "srv_tts")
async def ask_tts(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("🗣 <b>Matnni yozing (O'zbek, Rus yoki Ingliz):</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back")]]))
    await state.set_state(ServiceState.tts_text)

@dp.message(ServiceState.tts_text)
async def gen_tts(m: Message, state: FSMContext):
    msg = await m.reply("🗣 Ovoz yozilmoqda...")
    try:
        tts = gTTS(text=m.text, lang='en', slow=False)
        path = f"{DOWNLOAD_PATH}/{m.from_user.id}.mp3"
        tts.save(path)
        await msg.delete()
        await m.answer_audio(FSInputFile(path), caption="🔊 Tayyor", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back")]]))
        os.remove(path)
    except: await msg.edit_text("Xatolik.")
    await state.clear()

# --- 3. TARJIMON ---
@dp.callback_query(F.data == "srv_tr")
async def ask_tr(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("🌍 <b>Tarjima uchun matn yozing:</b>\n(Avtomatik aniqlab O'zbekchaga o'giradi)", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back")]]))
    await state.set_state(ServiceState.trans_text)

@dp.message(ServiceState.trans_text)
async def gen_tr(m: Message, state: FSMContext):
    try:
        res = GoogleTranslator(source='auto', target='uz').translate(m.text)
        await m.reply(f"🌍 <b>Tarjima:</b>\n\n{res}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back")]]))
    except: await m.reply("Xatolik.")
    await state.clear()

# --- ALOQA VA ADMIN ---
@dp.callback_query(F.data == "contact")
async def contact(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("✍️ Xabar yozing:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back")]]))
    await state.set_state(ServiceState.contact_admin)

@dp.message(ServiceState.contact_admin)
async def send_admin(m: Message, state: FSMContext, bot: Bot):
    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, f"📨 <b>Xabar:</b>\n{m.from_user.full_name} (ID: <code>{m.from_user.id}</code>):\n{m.text}")
        await m.reply("✅ Yuborildi.")
    await state.clear()

@dp.message(F.reply_to_message)
async def reply_user(m: Message, bot: Bot):
    if m.from_user.id == ADMIN_ID:
        try:
            # ID ni xavfsiz ajratib olish
            reply_text = m.reply_to_message.text
            if "ID:" in reply_text:
                uid_str = reply_text.split("ID:")[1].split(")")[0].replace("<code>", "").replace("</code>", "").strip()
                uid = int(uid_str)
                await bot.send_message(uid, f"☎️ <b>Admin javobi:</b>\n{m.text}")
                await m.reply("✅ Javob yuborildi.")
        except Exception as e:
            print(f"Reply xatolik: {e}")

# --- ADMIN PANEL ---
@dp.callback_query(F.data == "admin_panel")
async def adm_p(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Stat", callback_data="stat"), InlineKeyboardButton(text="📨 Reklama", callback_data="broad")],
        [InlineKeyboardButton(text="➕ Kanal", callback_data="add_ch"), InlineKeyboardButton(text="🗑 O'chirish", callback_data="del_ch")],
        [InlineKeyboardButton(text="🔙 Chiqish", callback_data="back")]
    ])
    await c.message.edit_text("Admin Panel:", reply_markup=kb)

@dp.callback_query(F.data == "stat")
async def stat(c: CallbackQuery): await c.answer(f"Odamlar: {get_users_count()}", show_alert=True)

@dp.callback_query(F.data == "broad")
async def broad(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Reklama yuboring:"); await state.set_state(ServiceState.broadcast)

@dp.message(ServiceState.broadcast)
async def send_broad(m: Message, state: FSMContext):
    u = get_all_users(); await m.answer("Ketdi..."); 
    for i in u:
        try: await m.copy_to(i); await asyncio.sleep(0.05)
        except: pass
    await m.answer("Tugadi."); await state.clear()

@dp.callback_query(F.data == "add_ch")
async def add_c(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Kanal linki:"); await state.set_state(ServiceState.add_ch_link)

@dp.message(ServiceState.add_ch_link)
async def save_ch(m: Message, state: FSMContext, bot: Bot):
    try: 
        link = m.text
        if "t.me" in link and not "@" in link: username = "@" + link.split("/")[-1]
        else: username = link
        c = await bot.get_chat(username); add_channel_db(link, str(c.id)); await m.answer("Qo'shildi!")
    except: await m.answer("Xato! Bot adminmi?")
    await state.clear()

@dp.callback_query(F.data == "del_ch")
async def del_c(c: CallbackQuery):
    kb = [[InlineKeyboardButton(text=f"❌ {x[0]}", callback_data=f"rm:{x[1]}")] for x in get_channels_db()]
    if kb: await c.message.edit_text("Tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else: await c.answer("Bo'sh")

@dp.callback_query(F.data.startswith("rm:"))
async def rm_c(c: CallbackQuery): del_channel_db(c.data.split(":")[1]); await c.answer("O'chdi"); await c.message.delete()

# --- WEB SERVER (Render uchun) ---
async def health(r): return web.Response(text="OK")

async def web_start():
    app = web.Application()
    app.router.add_get('/', health)
    runner = web.AppRunner(app)
    await runner.setup()
    # PORT ni Render avtomatik beradi, agar bo'lmasa 8080 ni oladi
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()

async def main():
    db_start()
    # Agar token bo'lmasa bot ishlamaydi
    if not TOKEN: 
        print("DIQQAT: BOT_TOKEN topilmadi!")
        return
        
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Bir vaqtning o'zida ham botni, ham serverni ishga tushiramiz
    await asyncio.gather(dp.start_polling(bot), web_start())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
