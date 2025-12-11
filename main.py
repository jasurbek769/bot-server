import asyncio
import logging
import sys
import os
import sqlite3
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
import aiohttp
from dotenv import load_dotenv
from gtts import gTTS
from deep_translator import GoogleTranslator

# -----------------------------------------------------------
# 1. XAVFSIZLIK VA SOZLAMALAR
# -----------------------------------------------------------
load_dotenv() # .env faylini o'qish (Lokalda ishlash uchun)

# Token va ID kodda ko'rinmaydi!
TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN:
    print("DIQQAT: Token topilmadi! Serverga kiritish kerak.")
    # Agar token bo'lmasa, kod to'xtamasligi uchun soxta qiymat (faqat test uchun)
    TOKEN = "TOKEN_YOQ"

# Admin ID ni songa aylantiramiz
try:
    ADMIN_ID = int(ADMIN_ID)
except:
    ADMIN_ID = 0

dp = Dispatcher()
DOWNLOAD_PATH = "downloads"
if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)

# -----------------------------------------------------------
# 2. BAZA (FOYDALANUVCHI TARIXI BILAN)
# -----------------------------------------------------------
def db_start():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    # Users: ID, Username, Ism, Qo'shilgan vaqti
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            username TEXT, 
            full_name TEXT, 
            joined_at TEXT
        )
    """)
    # Channels: Link, ID
    cur.execute("CREATE TABLE IF NOT EXISTS channels (link TEXT, id TEXT)")
    conn.commit()
    conn.close()

def add_user(user_id, username, full_name):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    # Bugungi sana
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at) VALUES (?, ?, ?, ?)", 
                (user_id, username, full_name, date))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    # Bugun qo'shilganlar
    today = datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) FROM users WHERE joined_at LIKE ?", (f"{today}%",))
    daily = cur.fetchone()[0]
    conn.close()
    return total, daily

def get_all_users():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = [row[0] for row in cur.fetchall()]
    conn.close()
    return users

# Kanal funksiyalari
def add_channel_db(link, ch_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("INSERT INTO channels VALUES (?, ?)", (link, ch_id)); conn.commit(); conn.close()

def del_channel_db(ch_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("DELETE FROM channels WHERE id = ?", (ch_id,)); conn.commit(); conn.close()

def get_channels_db():
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("SELECT * FROM channels"); return cur.fetchall()

# -----------------------------------------------------------
# 3. STATES (HOLATLAR)
# -----------------------------------------------------------
class ServiceState(StatesGroup):
    # Rasm
    image_prompt = State()
    # Ovoz (TTS)
    tts_lang = State()
    tts_text = State()
    # Tarjima
    trans_lang = State()
    trans_text = State()
    # Aloqa
    contact_admin = State()

class AdminState(StatesGroup):
    broadcast = State()
    add_ch_link = State()

# -----------------------------------------------------------
# 4. YORDAMCHI FUNKSIYALAR
# -----------------------------------------------------------
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

# --- POLLINATIONS.AI (RASM) ---
async def generate_image_api(prompt):
    seed = random.randint(1, 10000)
    prompt_safe = prompt.replace(" ", "%20")
    url = f"https://image.pollinations.ai/prompt/{prompt_safe}?width=1024&height=1024&seed={seed}&nologo=true"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200: return await resp.read()
    except: return None
    return None

# -----------------------------------------------------------
# 5. HANDLERS
# -----------------------------------------------------------

@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    # Majburiy obuna
    ns = await check_sub(bot, message.from_user.id)
    if ns:
        kb = [[InlineKeyboardButton(text="➕ Kanalga qo'shilish", url=l)] for l, _ in ns]
        kb.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer("⚠️ <b>Botdan foydalanish uchun kanalga a'zo bo'ling:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        return

    # TEPADA CHIQUVCHI 3 TUGMA (INLINE)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Rasm Yasash", callback_data="srv_image")],
        [InlineKeyboardButton(text="🗣 Matnni Ovozga Aylantirish", callback_data="srv_tts")],
        [InlineKeyboardButton(text="🌍 Tarjimon", callback_data="srv_trans")],
        [InlineKeyboardButton(text="📞 Admin bilan aloqa", callback_data="contact_admin")]
    ])
    
    # Admin bo'lsa panel chiqadi
    if message.from_user.id == ADMIN_ID:
        kb.inline_keyboard.append([InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")])

    await message.answer(
        f"👋 <b>Assalomu alaykum {message.from_user.full_name}!</b>\n\n"
        "Men Universal AI Yordamchiman. Xizmat turini tanlang 👇",
        reply_markup=kb
    )

@dp.callback_query(F.data == "check_sub")
async def check_cb(call: CallbackQuery, bot: Bot):
    if await check_sub(bot, call.from_user.id): await call.answer("❌ Hali a'zo bo'lmadingiz!", show_alert=True)
    else: await call.message.delete(); await start_handler(call.message, bot)

@dp.callback_query(F.data == "back_home")
async def go_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await start_handler(call.message, call.bot)

# --- 1. AI RASM YASASH ---
@dp.callback_query(F.data == "srv_image")
async def srv_image_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🎨 <b>Rasm Yasash Bo'limi</b>\n\nNimani chizib beray? Tasvirni yozing:\n<i>(Masalan: O'zbekiston bayrog'ini ko'tarib turgan kosmonavt)</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_home")]])
    )
    await state.set_state(ServiceState.image_prompt)

@dp.message(ServiceState.image_prompt)
async def process_image(message: Message, state: FSMContext):
    msg = await message.reply("🎨 <b>Chizilmoqda...</b>")
    img_bytes = await generate_image_api(message.text)
    
    if img_bytes:
        await msg.delete()
        file = BufferedInputFile(img_bytes, filename="art.jpg")
        await message.answer_photo(
            photo=file, 
            caption=f"🖼 <b>So'rov:</b> {message.text}\n🤖 @{(await message.bot.get_me()).username}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="back_home")]])
        )
    else:
        await msg.edit_text("❌ Xatolik.")
    await state.clear()

# --- 2. MATNNI OVOZGA AYLANTIRISH (TTS) ---
@dp.callback_query(F.data == "srv_tts")
async def srv_tts_lang(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="tts:uz"), InlineKeyboardButton(text="🇷🇺 Русский", callback_data="tts:ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="tts:en")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_home")]
    ])
    await call.message.edit_text("🗣 <b>Tilni tanlang:</b>", reply_markup=kb)
    await state.set_state(ServiceState.tts_lang)

@dp.callback_query(F.data.startswith("tts:"))
async def srv_tts_text(call: CallbackQuery, state: FSMContext):
    lang = call.data.split(":")[1]
    await state.update_data(lang=lang)
    await call.message.edit_text(f"📝 <b>Matnni yozing ({lang}):</b>")
    await state.set_state(ServiceState.tts_text)

@dp.message(ServiceState.tts_text)
async def process_tts(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang")
    msg = await message.reply("🗣 <b>Ovoz yozilmoqda...</b>")
    
    try:
        # gTTS orqali ovoz yaratish
        tts = gTTS(text=message.text, lang=lang, slow=False)
        filename = f"{DOWNLOAD_PATH}/{message.from_user.id}.mp3"
        tts.save(filename)
        
        await msg.delete()
        await message.answer_audio(
            audio=FSInputFile(filename),
            caption=f"🗣 <b>Matn:</b> {message.text[:50]}...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="back_home")]])
        )
        os.remove(filename)
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {e}")
    await state.clear()

# --- 3. TARJIMON ---
@dp.callback_query(F.data == "srv_trans")
async def srv_trans_lang(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇬🇧 Inglizchaga", callback_data="tr:en"), InlineKeyboardButton(text="🇷🇺 Ruschaga", callback_data="tr:ru")],
        [InlineKeyboardButton(text="🇺🇿 O'zbekchaga", callback_data="tr:uz")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_home")]
    ])
    await call.message.edit_text("🌍 <b>Qaysi tilga tarjima qilay?</b>", reply_markup=kb)
    await state.set_state(ServiceState.trans_lang)

@dp.callback_query(F.data.startswith("tr:"))
async def srv_trans_text(call: CallbackQuery, state: FSMContext):
    target = call.data.split(":")[1]
    await state.update_data(target=target)
    await call.message.edit_text("📝 <b>Tarjima uchun matn yozing:</b>")
    await state.set_state(ServiceState.trans_text)

@dp.message(ServiceState.trans_text)
async def process_trans(message: Message, state: FSMContext):
    data = await state.get_data()
    target = data.get("target")
    
    try:
        translated = GoogleTranslator(source='auto', target=target).translate(message.text)
        await message.reply(
            f"🌍 <b>Tarjima ({target}):</b>\n\n<code>{translated}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="back_home")]])
        )
    except:
        await message.reply("❌ Xatolik.")
    await state.clear()

# --- ALOQA VA ADMIN JAVOBI ---
@dp.callback_query(F.data == "contact_admin")
async def contact_admin(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("✍️ <b>Admin uchun xabaringizni yozing:</b>\n(Taklif, shikoyat yoki savol)", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_home")]]))
    await state.set_state(ServiceState.contact_admin)

@dp.message(ServiceState.contact_admin)
async def send_to_admin(message: Message, state: FSMContext, bot: Bot):
    if ADMIN_ID:
        try:
            # Adminga xabar yuborish (ID si bilan, javob berish oson bo'lishi uchun)
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📨 <b>YANGI XABAR!</b>\n\n👤 <b>Kimdan:</b> {message.from_user.full_name}\n🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n🔗 @{message.from_user.username}\n\n📄 <b>Matn:</b>\n{message.text}\n\n<i>Javob berish uchun shu xabarga Reply qiling.</i>"
            )
            await message.reply("✅ Xabar Adminga yuborildi! Javobni kuting.")
        except:
            await message.reply("❌ Adminga yuborib bo'lmadi.")
    else:
        await message.reply("❌ Admin ID sozlanmagan.")
    await state.clear()

@dp.message(F.reply_to_message)
async def admin_reply(message: Message, bot: Bot):
    if message.from_user.id == ADMIN_ID:
        try:
            # Xabar ichidan ID ni qidirib topish
            orig_text = message.reply_to_message.text
            user_id = int(orig_text.split("ID:")[1].split("\n")[0].replace("<code>", "").replace("</code>", "").strip())
            
            await bot.send_message(user_id, f"☎️ <b>ADMINDAN JAVOB:</b>\n\n{message.text}")
            await message.reply("✅ Javob foydalanuvchiga yuborildi.")
        except:
            await message.reply("❌ ID topilmadi yoki foydalanuvchi botni bloklagan.")

# --- ADMIN PANEL ---
@dp.callback_query(F.data == "admin_panel")
async def admin_dashboard(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stat"), InlineKeyboardButton(text="📨 Reklama", callback_data="broadcast")],
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"), InlineKeyboardButton(text="🗑 Kanal o'chirish", callback_data="del_ch")],
        [InlineKeyboardButton(text="🔙 Chiqish", callback_data="back_home")]
    ])
    await call.message.edit_text("👑 <b>Admin Boshqaruv Paneli</b>", reply_markup=kb)

@dp.callback_query(F.data == "stat")
async def show_stat(call: CallbackQuery):
    total, daily = get_stats()
    await call.answer(f"👥 Jami: {total}\n📅 Bugun: {daily}", show_alert=True)

@dp.callback_query(F.data == "broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📢 <b>Reklama xabarini yuboring (Rasm/Video/Matn):</b>")
    await state.set_state(AdminState.broadcast)

@dp.message(AdminState.broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    users = get_all_users()
    await message.reply(f"🚀 Xabar {len(users)} kishiga yuborilmoqda...")
    count = 0
    for user_id in users:
        try:
            await message.copy_to(chat_id=user_id)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.reply(f"✅ <b>{count}</b> ta odamga yetib bordi.")
    await state.clear()

@dp.callback_query(F.data == "add_ch")
async def add_channel_req(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🔗 <b>Kanal linkini yuboring (masalan: @kanal yoki https://...):</b>\nBot kanalda admin bo'lishi shart!")
    await state.set_state(AdminState.add_ch_link)

@dp.message(AdminState.add_ch_link)
async def process_add_channel(message: Message, state: FSMContext, bot: Bot):
    link = message.text.strip()
    username = link.split("/")[-1] if "/" in link else link
    if "t.me" not in link and not username.startswith("@"): username = "@" + username
    
    try:
        chat = await bot.get_chat(username)
        add_channel_db(link, str(chat.id))
        await message.reply(f"✅ <b>Kanal qo'shildi!</b>\nNomi: {chat.title}\nID: {chat.id}")
    except Exception as e:
        await message.reply(f"❌ Xatolik: {e}\nBotni kanalga admin qiling va linkni to'g'ri yozing.")
    await state.clear()

@dp.callback_query(F.data == "del_ch")
async def del_channel_list(call: CallbackQuery):
    channels = get_channels_db()
    kb = []
    for link, ch_id in channels:
        kb.append([InlineKeyboardButton(text=f"❌ {link}", callback_data=f"rm:{ch_id}")])
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_panel")])
    if not channels: await call.answer("Kanallar yo'q", show_alert=True)
    else: await call.message.edit_text("O'chirish uchun tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("rm:"))
async def process_del_channel(call: CallbackQuery):
    del_channel_db(call.data.split(":")[1])
    await call.answer("O'chirildi!")
    await call.message.delete()

# --- SERVER (UPTIMEROBOT) ---
async def health(r): return web.Response(text="Bot is Running!")
async def web_start():
    app = web.Application(); app.router.add_get('/', health)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

async def main():
    db_start()
    # Tokenni Environment Variable dan oladi (xavfsiz)
    if TOKEN == "TOKEN_YOQ":
        print("Bot ishlashi uchun TOKEN kiritish kerak (Render Settings da)!")
        return
        
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await asyncio.gather(dp.start_polling(bot), web_start())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
