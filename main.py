import logging
import os
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
import yt_dlp

# --- SOZLAMALAR ---
BOT_TOKEN = "8162216400:AAH-zzA8Fq0rAJKWW6B6nu-rz8uu3KmT4Ng" # @BotFather dan olingan token
ADMIN_ID = 7950261926  # O'zingizning Telegram ID raqamingiz (userinfobot dan oling)

# --- DASTUR ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# --- BAZA BILAN ISHLASH (SQLite) ---
DB_NAME = "bot_database.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Foydalanuvchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                full_name TEXT
            )
        """)
        # Majburiy obuna kanallari jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY,
                channel_id TEXT UNIQUE,
                channel_url TEXT
            )
        """)
        await db.commit()

async def add_user(user_id, full_name):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute("INSERT INTO users (user_id, full_name) VALUES (?, ?)", (user_id, full_name))
            await db.commit()
        except:
            pass

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            return await cursor.fetchall()

async def get_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT channel_id, channel_url FROM channels") as cursor:
            return await cursor.fetchall()

async def add_channel_db(channel_id, channel_url):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute("INSERT INTO channels (channel_id, channel_url) VALUES (?, ?)", (channel_id, channel_url))
            await db.commit()
            return True
        except:
            return False

async def delete_channel_db(channel_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await db.commit()

# --- HOLATLAR (STATES) ---
class AdminState(StatesGroup):
    broadcast = State()
    add_channel_id = State()
    add_channel_url = State()
    del_channel = State()

# --- TEKSHIRUV FUNKSIYASI ---
async def check_sub(user_id):
    channels = await get_channels()
    not_subscribed = []
    for ch_id, ch_url in channels:
        try:
            status = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if status.status in ['left', 'kicked']:
                not_subscribed.append((ch_id, ch_url))
        except:
            # Agar bot kanal admini bo'lmasa, xatolik beradi
            continue
    return not_subscribed

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="stat")],
            [InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="broadcast")],
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"),
             InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="del_ch")]
        ])
        await message.answer("👨‍💻 Admin Panelga xush kelibsiz:", reply_markup=kb)
    else:
        await message.answer("Siz admin emassiz.")

@dp.callback_query(F.data == "stat")
async def show_stats(callback: types.CallbackQuery):
    users = await get_all_users()
    await callback.message.answer(f"📊 Jami foydalanuvchilar: {len(users)} ta")
    await callback.answer()

@dp.callback_query(F.data == "broadcast")
async def ask_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Reklama xabarini yuboring (Rasm, Video, Matn):")
    await state.set_state(AdminState.broadcast)

@dp.message(AdminState.broadcast)
async def send_broadcast(message: types.Message, state: FSMContext):
    users = await get_all_users()
    count = 0
    await message.answer("📢 Reklama yuborish boshlandi...")
    for user in users:
        try:
            await message.copy_to(chat_id=user[0])
            count += 1
            await asyncio.sleep(0.05) # Spamdan saqlanish
        except:
            pass
    await message.answer(f"✅ Reklama {count} ta odamga yetib bordi.")
    await state.clear()

# --- KANAL QO'SHISH TIZIMI ---
@dp.callback_query(F.data == "add_ch")
async def ask_channel_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal ID sini yuboring (Masalan: -100123456789): \n\n⚠️ Bot kanalda Admin bo'lishi shart!")
    await state.set_state(AdminState.add_channel_id)

@dp.message(AdminState.add_channel_id)
async def ask_channel_url(message: types.Message, state: FSMContext):
    await state.update_data(ch_id=message.text)
    await message.answer("Kanal havolasini yuboring (Masalan: https://t.me/kanalim):")
    await state.set_state(AdminState.add_channel_url)

@dp.message(AdminState.add_channel_url)
async def save_channel(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ch_id = data.get("ch_id")
    ch_url = message.text
    if await add_channel_db(ch_id, ch_url):
        await message.answer("✅ Kanal muvaffaqiyatli qo'shildi!")
    else:
        await message.answer("❌ Xatolik! Bu kanal oldin qo'shilgan bo'lishi mumkin.")
    await state.clear()

# --- USER HANDLERS ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await add_user(message.from_user.id, message.from_user.full_name)
    
    # Obunani tekshirish
    not_sub = await check_sub(message.from_user.id)
    if not_sub:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Obuna bo'lish", url=url)] for _, url in not_sub
        ])
        kb.inline_keyboard.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        await message.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=kb)
    else:
        await message.answer("👋 Salom! Menga Instagram, TikTok yoki YouTube linkini yuboring.")

@dp.callback_query(F.data == "check_sub")
async def check_subscription_btn(callback: types.CallbackQuery):
    not_sub = await check_sub(callback.from_user.id)
    if not not_sub:
        await callback.message.delete()
        await callback.message.answer("✅ Rahmat! Endi link yuborishingiz mumkin.")
    else:
        await callback.answer("❌ Hali hamma kanalga a'zo bo'lmadingiz!", show_alert=True)

# --- DOWNLOADER MANTIQI ---
@dp.message(F.text)
async def download_video(message: types.Message):
    # Obunani qayta tekshirish
    if await check_sub(message.from_user.id):
        await message.answer("Iltimos, avval kanallarga a'zo bo'ling! /start ni bosing.")
        return

    url = message.text
    if "http" not in url:
        await message.answer("❌ Iltimos, to'g'ri havola yuboring.")
        return

    wait_msg = await message.answer("⏳ Video yuklanmoqda... Iltimos kuting.")
    
    try:
        ydl_opts = {
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'format': 'best[ext=mp4]', # Faqat MP4
            'max_filesize': 50 * 1024 * 1024, # 50MB dan katta videolarni olmaslik (Telegram limiti)
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        
        # Videoni yuborish
        video_file = FSInputFile(filename)
        await message.answer_video(video_file, caption="🤖 @SizningBotingizUseri orqali yuklandi")
        
        # Faylni o'chirish (Xotirani to'ldirmaslik uchun)
        os.remove(filename)
        await wait_msg.delete()
        
    except Exception as e:
        await wait_msg.edit_text(f"❌ Kechirasiz, bu videoni yuklab bo'lmadi.\nSabab: {e}")
        if os.path.exists('downloads'): # Tozalash
             for f in os.listdir('downloads'):
                 os.remove(os.path.join('downloads', f))

# --- MAIN LOOP ---
async def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi")
