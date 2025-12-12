import asyncio
import logging
import sys
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
from dotenv import load_dotenv

# --- SOZLAMALAR ---
load_dotenv()
MAIN_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Barcha ishlayotgan botlarni shu yerda saqlaymiz (xotirada)
active_bots = {}

# --- BAZA (Database) ---
def db_start():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    # Foydalanuvchi botlari jadvali: token, egasining_id si, bot_nomi
    cur.execute("CREATE TABLE IF NOT EXISTS user_bots (token TEXT PRIMARY KEY, owner_id INTEGER, bot_username TEXT)")
    conn.commit()
    conn.close()

def add_new_bot(token, owner_id, username):
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO user_bots VALUES (?, ?, ?)", (token, owner_id, username))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_bots():
    conn = sqlite3.connect("bot.db"); cur = conn.cursor()
    cur.execute("SELECT token, owner_id FROM user_bots")
    return cur.fetchall()

# --- BOLA BOT MANTIG'I (Foydalanuvchilarning boti nima qiladi?) ---
async def start_user_bot(token, owner_id):
    """Bu funksiya yangi botni alohida jarayonda ishga tushiradi"""
    try:
        # Har bir bot uchun alohida dispatcher ochamiz
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()

        # Bot ma'lumotini olish (tekshirish uchun)
        bot_info = await bot.get_me()
        
        # 1. Start bosilganda
        @dp.message(CommandStart())
        async def child_start(message: Message):
            await message.answer(f"👋 Salom! Men <b>{bot_info.first_name}</b> man.\n\n"
                                 f"🤖 Meni @tezdatopbot2026bot orqali <code>{owner_id}</code> IDli odam yaratdi.")

        # 2. Oddiy xabar yozilganda (Echo)
        @dp.message()
        async def child_echo(message: Message):
            await message.answer(f"Siz yozdingiz: {message.text}")

        # Pollingni alohida task qilib ishlatamiz
        polling_task = asyncio.create_task(dp.start_polling(bot))
        active_bots[token] = polling_task
        print(f"✅ Bot ishga tushdi: @{bot_info.username}")
        return bot_info.username

    except Exception as e:
        print(f"❌ Botni yoqishda xatolik ({token[:10]}...): {e}")
        return None

# --- OTA BOT (ASOSIY) ---
main_dp = Dispatcher()

class BotState(StatesGroup):
    waiting_for_token = State()

@main_dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        "👋 <b>Bot Konstruktorga xush kelibsiz!</b>\n\n"
        "Men sizga shaxsiy botingizni ulashga yordam beraman.\n"
        "Buning uchun @BotFather ga kirib, yangi bot oching va menga <b>TOKEN</b> yuboring.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Bot qo'shish", callback_data="add_bot")]])
    )

@main_dp.callback_query(F.data == "add_bot")
async def ask_token(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Meng yangi botingizning <b>TOKENI</b>ni yuboring:")
    await state.set_state(BotState.waiting_for_token)

@main_dp.message(BotState.waiting_for_token)
async def process_token(message: Message, state: FSMContext):
    token = message.text.strip()
    
    # Token formatini oddiy tekshirish
    if ":" not in token or len(token) < 20:
        await message.answer("❌ Bu tokenga o'xshamayapti. Qayta yuboring:")
        return

    # Botni ishga tushirib ko'ramiz
    msg = await message.answer("⏳ Bot tekshirilmoqda...")
    username = await start_user_bot(token, message.from_user.id)

    if username:
        # Agar ishlsa, bazaga saqlaymiz
        if add_new_bot(token, message.from_user.id, username):
            await msg.edit_text(f"✅ <b>Tabriklayman!</b>\n\nBotingiz ishga tushdi: @{username}\n\nEndi unga kirib /start bosib ko'ring!")
        else:
            await msg.edit_text("⚠️ Bu bot allaqachon tizimda mavjud.")
    else:
        await msg.edit_text("❌ Token xato yoki yaroqsiz. Iltimos, to'g'ri token yuboring.")
    
    await state.clear()

# --- TIZIMNI YURGIZISH ---
async def startup_all_bots():
    """Server yonganda bazadagi eski botlarni ham qayta yoqadi"""
    bots = get_all_bots()
    print(f"🔄 Bazadan {len(bots)} ta bot qayta tiklanmoqda...")
    for token, owner_id in bots:
        if token not in active_bots:
            await start_user_bot(token, owner_id)

# --- SERVER QISMI ---
async def health(r): return web.Response(text="OK")
async def web_start():
    app = web.Application()
    app.router.add_get('/', health)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

async def main():
    db_start()
    
    # Avval eski saqlangan botlarni ishga tushiramiz
    await startup_all_bots()

    bot = Bot(token=MAIN_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("🚀 Asosiy bot ishga tushdi...")
    
    await asyncio.gather(main_dp.start_polling(bot), web_start())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
