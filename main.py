import asyncio
import logging
import sys
import os
import sqlite3
import random
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
import aiohttp
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image
import io

# --- SOZLAMALAR ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Admin ID ni songa o'tkazamiz
if ADMIN_ID: ADMIN_ID = int(ADMIN_ID)

# Gemini sozlash
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    print("❌ GEMINI_API_KEY topilmadi!")

dp = Dispatcher()

# --- BAZA (DATABASE) ---
def db_start():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    cur.execute("CREATE TABLE IF NOT EXISTS channels (link TEXT, id TEXT)")
    conn.commit(); conn.close()

def add_user(user_id):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,)); conn.commit(); conn.close()

def get_all_users():
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("SELECT user_id FROM users"); return [u[0] for u in cur.fetchall()]

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
    broadcast_text = State()
    broadcast_timer = State() # Vaqtinchalik reklama vaqti

# --- FUNKSIYALAR ---
async def check_sub_status(bot: Bot, user_id: int):
    if user_id == ADMIN_ID: return True
    channels = get_channels()
    if not channels: return True
    not_sub = []
    for link, ch_id in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ['left', 'kicked']: not_sub.append(link)
        except: continue
    return not_sub

async def generate_image(prompt):
    """Pollinations AI orqali rasm chizish"""
    seed = random.randint(1, 10000)
    safe_prompt = prompt.replace(" ", "%20")
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&seed={seed}&nologo=true"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200: return await resp.read()
    return None

async def delete_message_later(chat_id, message_id, delay_minutes, bot):
    """Reklamani vaqt o'tgach o'chirib tashlash"""
    await asyncio.sleep(delay_minutes * 60)
    try:
        await bot.delete_message(chat_id, message_id)
    except: pass

# --- START & MENU ---
@dp.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    add_user(message.from_user.id)
    
    # Obuna tekshiruvi
    not_sub = await check_sub_status(bot, message.from_user.id)
    if not_sub and not isinstance(not_sub, bool):
        kb = [[InlineKeyboardButton(text="➕ A'zo bo'lish", url=link)] for link in not_sub]
        kb.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer("⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        return

    await message.answer(
        f"👋 Salom <b>{message.from_user.full_name}</b>!\n\n"
        "🤖 <b>Men Super AI botman.</b> Nimalar qilaman?\n"
        "1. 💬 Savollarga javob beraman (Gemini).\n"
        "2. 📷 Rasmlarni tahlil qilaman (Rasmni menga yuboring).\n"
        "3. 🎨 Rasm chizaman (<code>/img olma</code> deb yozing).\n\n"
        "<i>Savolingizni yozib qoldiring!</i>"
    )

@dp.callback_query(F.data == "check_sub")
async def check_cb(c: CallbackQuery, bot: Bot):
    ns = await check_sub_status(bot, c.from_user.id)
    if not ns or isinstance(ns, bool):
        await c.message.delete()
        await c.message.answer("✅ Rahmat! Xizmatdan foydalanishingiz mumkin.")
    else: await c.answer("❌ Hali a'zo bo'lmadingiz!", show_alert=True)

# --- GEMINI CHAT & RASM TAHLILI ---
@dp.message(F.photo)
async def analyze_photo(message: Message, bot: Bot):
    msg = await message.reply("👀 Rasm tahlil qilinmoqda...")
    try:
        # Rasmni yuklab olish
        photo = await bot.download(message.photo[-1])
        img = Image.open(photo)
        
        # Geminiga yuborish
        response = model.generate_content(["Bu rasmda nima borligini batafsil tasvirlab ber (O'zbek tilida).", img])
        await msg.edit_text(response.text)
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {e}")

@dp.message(F.text.startswith("/img"))
async def image_gen_cmd(message: Message):
    prompt = message.text.replace("/img", "").strip()
    if not prompt:
        await message.reply("🎨 Rasm chizish uchun buyruqdan so'ng matn yozing.\nMasalan: <code>/img uchar mashina</code>")
        return
    
    msg = await message.reply("🎨 Rasm chizilmoqda...")
    img_bytes = await generate_image(prompt)
    if img_bytes:
        await msg.delete()
        await message.answer_photo(BufferedInputFile(img_bytes, "img.jpg"), caption=f"🖼 {prompt}")
    else:
        await msg.edit_text("❌ Rasm chizib bo'lmadi.")

@dp.message(F.text)
async def ai_chat(message: Message, bot: Bot):
    # Admin panel komandasi
    if message.text == "/admin" and message.from_user.id == ADMIN_ID:
        await show_admin_panel(message)
        return

    # Chat
    try:
        await bot.send_chat_action(message.chat.id, "typing")
        response = model.generate_content(message.text)
        
        # Javob uzun bo'lsa bo'lib tashlaymiz
        text = response.text
        if len(text) > 4000:
            for x in range(0, len(text), 4000):
                await message.answer(text[x:x+4000], parse_mode=ParseMode.MARKDOWN)
        else:
            await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await message.answer("⚠️ AI javob bera olmadi. Qayta urinib ko'ring.")

# --- ADMIN PANEL ---
async def show_admin_panel(message: Message):
    users_count = len(get_all_users())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Reklama (Doimiy)", callback_data="broad_perm"), InlineKeyboardButton(text="⏳ Reklama (Vaqtli)", callback_data="broad_temp")],
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"), InlineKeyboardButton(text="🗑 Kanal o'chirish", callback_data="del_ch")],
        [InlineKeyboardButton(text=f"📊 Statistika ({users_count})", callback_data="stat")]
    ])
    await message.answer("👑 <b>Admin Panel:</b>", reply_markup=kb)

@dp.callback_query(F.data == "stat")
async def stat_cb(c: CallbackQuery): await c.answer(f"Foydalanuvchilar: {len(get_all_users())}", show_alert=True)

# KANAL QO'SHISH
@dp.callback_query(F.data == "add_ch")
async def add_ch_cb(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Kanal linkini yuboring (Bot admin bo'lishi shart):")
    await state.set_state(AdminState.add_channel)

@dp.message(AdminState.add_channel)
async def save_ch(m: Message, state: FSMContext, bot: Bot):
    try:
        link = m.text
        uname = "@" + link.split("/")[-1] if "t.me" in link and "@" not in link else link
        chat = await bot.get_chat(uname)
        add_channel_db(link, chat.id)
        await m.answer("✅ Kanal qo'shildi!")
    except: await m.answer("❌ Xatolik! Bot kanalga adminmi?")
    await state.clear()

# KANAL O'CHIRISH
@dp.callback_query(F.data == "del_ch")
async def del_ch_list(c: CallbackQuery):
    kb = [[InlineKeyboardButton(text=f"❌ {x[0]}", callback_data=f"rm:{x[1]}")] for x in get_channels()]
    if kb: await c.message.edit_text("O'chirish uchun tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else: await c.answer("Bo'sh")

@dp.callback_query(F.data.startswith("rm:"))
async def rm_c(c: CallbackQuery): del_channel_db(c.data.split(":")[1]); await c.answer("O'chdi"); await c.message.delete()

# REKLAMA
@dp.callback_query(F.data.startswith("broad_"))
async def broadcast_ask(c: CallbackQuery, state: FSMContext):
    is_temp = "temp" in c.data
    await state.update_data(is_temp=is_temp)
    await c.message.answer("📣 Reklama postini yuboring (Rasm, video yoki matn):")
    await state.set_state(AdminState.broadcast_text)

@dp.message(AdminState.broadcast_text)
async def broadcast_get_msg(m: Message, state: FSMContext):
    await state.update_data(msg_id=m.message_id, from_chat=m.chat.id)
    data = await state.get_data()
    
    if data.get('is_temp'):
        await m.answer("⏳ <b>Necha daqiqadan keyin o'chsin?</b> (Raqam yozing, masalan: 5)")
        await state.set_state(AdminState.broadcast_timer)
    else:
        # Doimiy reklama
        await start_broadcast(m, state, 0)

@dp.message(AdminState.broadcast_timer)
async def broadcast_get_timer(m: Message, state: FSMContext):
    try:
        minutes = int(m.text)
        await start_broadcast(m, state, minutes)
    except: await m.answer("❌ Faqat raqam yozing!")

async def start_broadcast(m: Message, state: FSMContext, minutes: int):
    data = await state.get_data()
    users = get_all_users()
    msg_id = data['msg_id']
    from_chat = data['from_chat']
    bot = m.bot
    
    status_msg = await m.answer(f"🚀 Reklama ketmoqda... ({len(users)} kishi)")
    count = 0
    
    for uid in users:
        try:
            sent = await bot.copy_message(chat_id=uid, from_chat_id=from_chat, message_id=msg_id)
            count += 1
            # Agar vaqtinchalik bo'lsa, o'chirish vazifasini belgilaymiz
            if minutes > 0:
                asyncio.create_task(delete_message_later(uid, sent.message_id, minutes, bot))
            await asyncio.sleep(0.05)
        except: pass
    
    await status_msg.edit_text(f"✅ Reklama tugadi. {count} kishiga bordi.\n" + (f"⏳ {minutes} daqiqadan keyin o'chadi." if minutes > 0 else ""))
    await state.clear()

# --- SERVER ---
async def health(r): return web.Response(text="OK")
async def web_start():
    app = web.Application(); app.router.add_get('/', health)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

async def main():
    db_start()
    if not TOKEN: return
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await asyncio.gather(dp.start_polling(bot), web_start())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
