import logging
import sqlite3
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ContentType

# .env yoki Render Environment o'zgaruvchilarini yuklaymiz
load_dotenv()

# =========================================================================
# ⚙️ SOZLAMALAR (HAMMASI RENDERDAN OLINADI)
# =========================================================================

# 1. Tokenni Renderdan oladi
API_TOKEN = os.getenv("BOT_TOKEN")

# 2. Admin ID ni Renderdan oladi va songa aylantiradi
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except:
    print("DIQQAT: ADMIN_ID Renderga kiritilmagan yoki xato! Vaqtincha 0 deb olindi.")
    ADMIN_ID = 0

# 3. To'lov tizimlari (Agar Renderga kiritilgan bo'lsa)
PAYME_TOKEN = os.getenv("PAYME_TOKEN", "PAYME_TOKEN_YOKI_TEST") 
CLICK_TOKEN = os.getenv("CLICK_TOKEN", "CLICK_TOKEN_YOKI_TEST")

# =========================================================================
# 📦 MA'LUMOTLAR BAZASI
# =========================================================================
logging.basicConfig(level=logging.INFO)

# Token borligini tekshirish
if not API_TOKEN:
    print("❌ XATOLIK: BOT_TOKEN topilmadi! Iltimos, Render Environment Variables bo'limini tekshiring.")
    exit() # Botni to'xtatish

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

def db_start():
    base = sqlite3.connect('super_bot.db')
    cur = base.cursor()
    
    base.execute('''CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        full_name TEXT,
        username TEXT,
        usage_count INTEGER DEFAULT 0,
        balance INTEGER DEFAULT 0,
        referrer_id INTEGER DEFAULT 0
    )''')
    
    base.execute('''CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY,
        free_limit INTEGER DEFAULT 10,
        price_per_item INTEGER DEFAULT 500,
        referral_bonus INTEGER DEFAULT 2
    )''')
    
    check = cur.execute('SELECT * FROM settings').fetchone()
    if not check:
        cur.execute('INSERT INTO settings (id, free_limit, price_per_item, referral_bonus) VALUES (1, 10, 500, 2)')
    
    base.commit()
    return base, cur

base, cur = db_start()

# =========================================================================
# 🔘 TUGMALAR
# =========================================================================
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = KeyboardButton("🎨 RASM YASASH")
    btn2 = KeyboardButton("👤 KABINET")
    btn3 = KeyboardButton("💰 BALANS TOLDIRISH")
    btn4 = KeyboardButton("🤝 DO'STLARNI TAKLIF QILISH")
    kb.add(btn1).add(btn2, btn3).add(btn4)
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📊 Statistika", "⚙️ Limitni O'zgartirish")
    kb.add("💸 Narxni O'zgartirish", "➕ Balans Berish")
    kb.add("⬅️ Asosiy menyu")
    return kb

def payment_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    btn1 = InlineKeyboardButton(text="💳 Payme orqali to'lash", callback_data="pay_payme")
    btn2 = InlineKeyboardButton(text="🔹 Click orqali to'lash", callback_data="pay_click")
    kb.add(btn1, btn2)
    return kb

# =========================================================================
# 🚀 ASOSIY LOGIKA
# =========================================================================
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username
    args = message.get_args()
    referrer_id = 0
    
    user = cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not user:
        if args and args.isdigit():
            ref_id = int(args)
            if ref_id != user_id:
                referrer_id = ref_id
                settings = cur.execute("SELECT referral_bonus FROM settings").fetchone()
                bonus = settings[0]
                cur.execute("UPDATE users SET usage_count = usage_count - ? WHERE user_id = ?", (bonus, referrer_id))
                try:
                    await bot.send_message(referrer_id, f"🎉 **TABRIKLAYMIZ!**\n\nSiz do'stingizni taklif qildingiz va sizga **{bonus} TA BEPUL RASM** qo'shildi!")
                except:
                    pass
        
        cur.execute("INSERT INTO users (user_id, full_name, username, referrer_id) VALUES (?, ?, ?, ?)", 
                    (user_id, full_name, username, referrer_id))
        base.commit()
    
    await message.answer(
        f"👋 **SALOM, {full_name.upper()}!**\n\n"
        "MEN SUN'IY INTELLEKT ORQALI RASM YARATIB BERUVCHI BOTMAN.\n\n"
        "🔽 **QUYIDAGI TUGMALARDAN FOYDALANING:**",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@dp.message_handler(text="🎨 RASM YASASH")
async def generate_image_logic(message: types.Message):
    user_id = message.from_user.id
    
    settings = cur.execute("SELECT free_limit, price_per_item FROM settings").fetchone()
    free_limit = settings[0]
    price = settings[1]
    
    user = cur.execute("SELECT usage_count, balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
    usage_count = user[0]
    balance = user[1]
    
    if usage_count < free_limit:
        await message.answer("🎨 **RASM TAYYORLANMOQDA...**\n\n⏳ Iltimos kuting...", parse_mode="Markdown")
        # Rasm yaratish logikasi (Hozircha test)
        await message.answer_photo(
            photo="https://via.placeholder.com/500", 
            caption=f"✅ **RASMINGIZ TAYYOR!**\n\n🎁 Sizda yana **{free_limit - usage_count - 1}** ta bepul urinish qoldi."
        )
        cur.execute("UPDATE users SET usage_count = usage_count + 1 WHERE user_id = ?", (user_id,))
        base.commit()
        
    elif balance >= price:
        new_balance = balance - price
        cur.execute("UPDATE users SET balance = ?, usage_count = usage_count + 1 WHERE user_id = ?", (new_balance, user_id))
        base.commit()
        await message.answer(f"💸 **HISOBINGIZDAN {price} SO'M YECHILDI.**\n🎨 Rasm tayyorlanmoqda...", parse_mode="Markdown")
        await message.answer_photo(
            photo="https://via.placeholder.com/500",
            caption=f"✅ **RASMINGIZ TAYYOR!**\n\n💰 Balansingiz: **{new_balance} so'm**"
        )
    else:
        await message.answer(
            f"🚫 **DIQQAT! BEPUL LIMIT TUGAGAN.**\n\n❌ Sizning hisobingizda mablag' yetarli emas.\n💵 Bitta rasm narxi: **{price} so'm**\n⬇️ **DAVOM ETISH UCHUN HISOBNI TO'LDIRING:**",
            reply_markup=main_menu(), parse_mode="Markdown"
        )

@dp.message_handler(text="👤 KABINET")
async def profile_handler(message: types.Message):
    user_id = message.from_user.id
    user = cur.execute("SELECT usage_count, balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
    settings = cur.execute("SELECT free_limit, price_per_item FROM settings").fetchone()
    usage = user[0]
    balance = user[1]
    limit = settings[0]
    price = settings[1]
    qolgan_bepul = max(0, limit - usage)
    
    await message.answer(
        f"👤 **SIZNING KABINETINGIZ**\n\n🆔 ID: `{user_id}`\n💰 Balans: **{balance} so'm**\n🎁 Bepul urinishlar: **{qolgan_bepul} ta**\n🏷 Har bir rasm narxi: **{price} so'm**\n📊 Jami yasalgan rasmlar: **{usage} ta**",
        parse_mode="Markdown"
    )

@dp.message_handler(text="🤝 DO'STLARNI TAKLIF QILISH")
async def referral_handler(message: types.Message):
    user_id = message.from_user.id
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    settings = cur.execute("SELECT referral_bonus FROM settings").fetchone()
    bonus = settings[0]
    await message.answer(
        f"🔗 **DO'STLARNI TAKLIF QILING!**\n\nSizning shaxsiy havolangiz:\n`{ref_link}`\n\nHar bir taklif qilgan do'stingiz uchun **{bonus} TA BEPUL RASM** oling!",
        parse_mode="Markdown"
    )

# =========================================================================
# 💰 BALANS TO'LDIRISH
# =========================================================================
@dp.message_handler(text="💰 BALANS TOLDIRISH")
async def deposit_handler(message: types.Message):
    await message.answer("💳 **TO'LOV TIZIMINI TANLANG:**", reply_markup=payment_keyboard(), parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data in ['pay_payme', 'pay_click'])
async def process_payment(callback_query: types.CallbackQuery):
    amount = 5000 * 100 
    if callback_query.data == 'pay_payme':
        provider_token = PAYME_TOKEN
    else:
        provider_token = CLICK_TOKEN
        
    if "TOKEN_YOKI_TEST" in provider_token or not provider_token:
        await bot.send_message(callback_query.from_user.id, "⚠️ **ADMIN DIQQATIGA:**\nTokenlar Renderga kiritilmagan.")
        return

    await bot.send_invoice(callback_query.from_user.id, title="Balans to'ldirish", description="Bot hisobini 5000 so'mga to'ldirish", provider_token=provider_token, currency='UZS', prices=[types.LabeledPrice(label='Balans', amount=amount)], payload='balance_topup')

@dp.pre_checkout_query_handler(lambda query: True)
async def checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def got_payment(message: types.Message):
    user_id = message.from_user.id
    amount = message.successful_payment.total_amount // 100
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    base.commit()
    await message.answer(f"✅ **TO'LOV QABUL QILINDI!**\n\nHisobingizga **{amount} so'm** qo'shildi.")

# =========================================================================
# 👮‍♂️ ADMIN PANEL
# =========================================================================
@dp.message_handler(commands=['admin'], user_id=ADMIN_ID)
async def admin_start(message: types.Message):
    await message.answer("👨‍💻 **ADMIN PANELGA XUSH KELIBSIZ!**", reply_markup=admin_menu(), parse_mode="Markdown")

@dp.message_handler(text="⬅️ Asosiy menyu", user_id=ADMIN_ID)
async def back_home(message: types.Message):
    await message.answer("Bosh menyu", reply_markup=main_menu())

@dp.message_handler(text="📊 Statistika", user_id=ADMIN_ID)
async def admin_stats(message: types.Message):
    users_count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_generated = cur.execute("SELECT SUM(usage_count) FROM users").fetchone()[0] or 0
    total_money = cur.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
    await message.answer(f"📊 **STATISTIKA:**\n\n👥 Foydalanuvchilar: **{users_count} ta**\n🖼 Jami yasalgan rasmlar: **{total_generated} ta**\n💰 Foydalanuvchilar balansidagi pul: **{total_money} so'm**", parse_mode="Markdown")

@dp.message_handler(commands=['set_limit'], user_id=ADMIN_ID)
async def set_limit(message: types.Message):
    try:
        limit = int(message.get_args())
        cur.execute("UPDATE settings SET free_limit = ? WHERE id = 1", (limit,))
        base.commit()
        await message.answer(f"✅ Bepul limit **{limit} ta** qilib belgilandi.")
    except:
        await message.answer("⚠️ Xato! Yozish tartibi: `/set_limit 15`")

@dp.message_handler(commands=['set_price'], user_id=ADMIN_ID)
async def set_price(message: types.Message):
    try:
        price = int(message.get_args())
        cur.execute("UPDATE settings SET price_per_item = ? WHERE id = 1", (price,))
        base.commit()
        await message.answer(f"✅ Bir rasm narxi **{price} so'm** qilib belgilandi.")
    except:
        await message.answer("⚠️ Xato! Yozish tartibi: `/set_price 1000`")

@dp.message_handler(commands=['add_money'], user_id=ADMIN_ID)
async def add_money_admin(message: types.Message):
    try:
        args = message.get_args().split()
        target_id = int(args[0])
        amount = int(args[1])
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        base.commit()
        await message.answer(f"✅ {target_id} ga **{amount} so'm** qo'shildi.")
        await bot.send_message(target_id, f"🎁 **ADMIN SIZGA {amount} SO'M BONUS BERDI!**")
    except:
        await message.answer("⚠️ Xato! Yozish tartibi: `/add_money 12345678 10000`")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
