import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ContentType

# =========================================================================
# ⚙️ SOZLAMALAR (O'zingiznikiga almashtiring)
# =========================================================================
API_TOKEN = 'BU_YERGA_BOT_TOKEN_QOYING'  # BotFather'dan olingan token
ADMIN_ID = 12345678  # O'zingizning Telegram ID raqamingizni yozing (userinfobot orqali bilsa bo'ladi)

# To'lov tizimi tokenlari (BotFather -> Payments bo'limidan olinadi)
# Agar hozir yo'q bo'lsa, shunchaki bo'sh qoldiring, lekin to'lov ishlamaydi.
PAYME_TOKEN = "PAYME_TOKEN_YOKI_TEST" 
CLICK_TOKEN = "CLICK_TOKEN_YOKI_TEST"

# =========================================================================
# 📦 MA'LUMOTLAR BAZASI (SQLITE3)
# =========================================================================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

def db_start():
    base = sqlite3.connect('super_bot.db')
    cur = base.cursor()
    
    # 1. Foydalanuvchilar jadvali
    base.execute('''CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        full_name TEXT,
        username TEXT,
        usage_count INTEGER DEFAULT 0,
        balance INTEGER DEFAULT 0,
        referrer_id INTEGER DEFAULT 0
    )''')
    
    # 2. Sozlamalar jadvali
    base.execute('''CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY,
        free_limit INTEGER DEFAULT 10,       -- Bepul limit
        price_per_item INTEGER DEFAULT 500,  -- 1 rasm narxi
        referral_bonus INTEGER DEFAULT 2     -- Do'stini chaqirsa nechta bepul rasm beriladi
    )''')
    
    # Boshlang'ich sozlamalar
    check = cur.execute('SELECT * FROM settings').fetchone()
    if not check:
        cur.execute('INSERT INTO settings (id, free_limit, price_per_item, referral_bonus) VALUES (1, 10, 500, 2)')
    
    base.commit()
    return base, cur

base, cur = db_start()

# =========================================================================
# 🔘 TUGMALAR (KEYBOARDS)
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
# 🚀 FOYDALANUVCHI QISMI (START & REFERRAL)
# =========================================================================
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username
    
    # Referral orqali kirganini tekshirish (/start 12345)
    args = message.get_args()
    referrer_id = 0
    
    user = cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not user:
        if args and args.isdigit():
            ref_id = int(args)
            if ref_id != user_id: # O'zi o'zini taklif qilolmaydi
                referrer_id = ref_id
                # Taklif qilgan odamga bonus beramiz (Limitni kamaytiramiz = ko'proq bepul)
                settings = cur.execute("SELECT referral_bonus FROM settings").fetchone()
                bonus = settings[0]
                
                # Referrerning ishlatgan limitidan bonusni ayiramiz (yoki balansga pul berish mumkin)
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

# =========================================================================
# 🎨 RASM YASASH LOGIKASI (ENG MUHIM QISM)
# =========================================================================
@dp.message_handler(text="🎨 RASM YASASH")
async def generate_image_logic(message: types.Message):
    user_id = message.from_user.id
    
    # Sozlamalarni olish
    settings = cur.execute("SELECT free_limit, price_per_item FROM settings").fetchone()
    free_limit = settings[0]
    price = settings[1]
    
    # Userni tekshirish
    user = cur.execute("SELECT usage_count, balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
    usage_count = user[0]
    balance = user[1]
    
    # --- TEKSHIRUV ---
    if usage_count < free_limit:
        # BEPUL REJIM
        await message.answer("🎨 **RASM TAYYORLANMOQDA...**\n\n⏳ Iltimos kuting...", parse_mode="Markdown")
        
        # ... Bu yerda AI API chaqiriladi (Dall-E, Midjourney) ...
        # Biz hozircha rasm o'rniga fayl junatamiz yoki tekst yozamiz
        await message.answer_photo(
            photo="https://via.placeholder.com/500", # Test uchun rasm
            caption=f"✅ **RASMINGIZ TAYYOR!**\n\n🎁 Sizda yana **{free_limit - usage_count - 1}** ta bepul urinish qoldi."
        )
        
        # Hisobni yangilash
        cur.execute("UPDATE users SET usage_count = usage_count + 1 WHERE user_id = ?", (user_id,)).fetchone()
        base.commit()
        
    elif balance >= price:
        # PULLIK REJIM
        new_balance = balance - price
        cur.execute("UPDATE users SET balance = ?, usage_count = usage_count + 1 WHERE user_id = ?", (new_balance, user_id))
        base.commit()
        
        await message.answer(f"💸 **HISOBINGIZDAN {price} SO'M YECHILDI.**\n🎨 Rasm tayyorlanmoqda...", parse_mode="Markdown")
        
        await message.answer_photo(
            photo="https://via.placeholder.com/500",
            caption=f"✅ **RASMINGIZ TAYYOR!**\n\n💰 Balansingiz: **{new_balance} so'm**"
        )
        
    else:
        # PUL YETMASA
        await message.answer(
            f"🚫 **DIQQAT! BEPUL LIMIT TUGAGAN.**\n\n"
            f"❌ Sizning hisobingizda mablag' yetarli emas.\n"
            f"💵 Bitta rasm narxi: **{price} so'm**\n"
            f"💳 Sizning balansingiz: **{balance} so'm**\n\n"
            "⬇️ **DAVOM ETISH UCHUN HISOBNI TO'LDIRING:**",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

# =========================================================================
# 👤 KABINET VA DO'STLAR
# =========================================================================
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
    
    text = (
        f"👤 **SIZNING KABINETINGIZ**\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"💰 Balans: **{balance} so'm**\n"
        f"🎁 Bepul urinishlar: **{qolgan_bepul} ta**\n"
        f"🏷 Har bir rasm narxi: **{price} so'm**\n\n"
        f"📊 Jami yasalgan rasmlar: **{usage} ta**"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(text="🤝 DO'STLARNI TAKLIF QILISH")
async def referral_handler(message: types.Message):
    user_id = message.from_user.id
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    settings = cur.execute("SELECT referral_bonus FROM settings").fetchone()
    bonus = settings[0]
    
    text = (
        f"🔗 **DO'STLARNI TAKLIF QILING!**\n\n"
        f"Sizning shaxsiy havolangiz:\n`{ref_link}`\n\n"
        f"Har bir taklif qilgan do'stingiz uchun **{bonus} TA BEPUL RASM** oling!"
    )
    await message.answer(text, parse_mode="Markdown")

# =========================================================================
# 💰 BALANS TO'LDIRISH (CLICK / PAYME)
# =========================================================================
@dp.message_handler(text="💰 BALANS TOLDIRISH")
async def deposit_handler(message: types.Message):
    await message.answer("💳 **TO'LOV TIZIMINI TANLANG:**", reply_markup=payment_keyboard(), parse_mode="Markdown")

# Invoice jo'natish (Test yoki Haqiqiy)
@dp.callback_query_handler(lambda c: c.data in ['pay_payme', 'pay_click'])
async def process_payment(callback_query: types.CallbackQuery):
    amount = 5000 * 100 # 5000 so'm (tiyinda ko'rsatiladi)
    
    if callback_query.data == 'pay_payme':
        provider_token = PAYME_TOKEN
        title = "Payme orqali to'lov"
    else:
        provider_token = CLICK_TOKEN
        title = "Click orqali to'lov"
        
    if provider_token == "PAYME_TOKEN_YOKI_TEST" or provider_token == "CLICK_TOKEN_YOKI_TEST":
        await bot.send_message(callback_query.from_user.id, "⚠️ **ADMIN DIQQATIGA:**\nTokenlar kiritilmagan. Kodni tekshiring.")
        return

    await bot.send_invoice(
        callback_query.from_user.id,
        title="Balans to'ldirish",
        description="Bot hisobini 5000 so'mga to'ldirish",
        provider_token=provider_token,
        currency='UZS',
        prices=[types.LabeledPrice(label='Balans', amount=amount)],
        payload='balance_topup'
    )

# To'lov muvaffaqiyatli o'tganda
@dp.pre_checkout_query_handler(lambda query: True)
async def checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def got_payment(message: types.Message):
    user_id = message.from_user.id
    amount = message.successful_payment.total_amount // 100 # Tiyinni so'mga aylantirish
    
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    base.commit()
    
    await message.answer(
        f"✅ **TO'LOV QABUL QILINDI!**\n\n"
        f"Hisobingizga **{amount} so'm** qo'shildi."
    )

# =========================================================================
# 👮‍♂️ ADMIN PANEL (FAQAT SIZ UCHUN)
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
    
    await message.answer(
        f"📊 **STATISTIKA:**\n\n"
        f"👥 Foydalanuvchilar: **{users_count} ta**\n"
        f"🖼 Jami yasalgan rasmlar: **{total_generated} ta**\n"
        f"💰 Foydalanuvchilar balansidagi pul: **{total_money} so'm**",
        parse_mode="Markdown"
    )

# Limit va Narxni o'zgartirish buyruqlari
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
    # Tartib: /add_money ID SUMMA
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

# =========================================================================
# 🏁 BOTNI ISHGA TUSHIRISH
# =========================================================================
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
