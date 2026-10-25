import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage

# ⚙️ TOKEN va KANAL SOZLAMALARI
TOKEN = "SIZNING_BOT_TOKENINGIZNI_SHU_YERGA_YOZING"  # Bot tokeningizni yozing
CHANNEL_USERNAME = "@movitimecn"  # Kino tashlab boriladigan asosiy kanal
WEB_APP_URL = "https://nodirbekyusupboyev06.github.io/movietimecn-app/"  # GitHub Pages sayt havolangiz

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# 🗄️ BAZANI YARATISH (Kino va obuna bo'lgan foydalanuvchilar uchun)
def db_start():
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    # Foydalanuvchilar bazasi (obunadan o'tganini saqlash uchun)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)
    # Kinolar bazasi
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            movie_code TEXT PRIMARY KEY,
            title TEXT,
            file_id TEXT
        )
    """)
    conn.commit()
    conn.close()

db_start()

# 🔍 Obunani tekshirish funksiyasi
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception:
        pass
    return False

# 👥 Foydalanuvchi bazada bormi (Oldin obuna bo'lganmi) tekshirish
def is_user_subscribed_db(user_id: int) -> bool:
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def add_user_to_db(user_id: int):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# ▶️ /start buyrug'i (Yangi dizayn + Mini App tugmasi)
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Agar foydalanuvchi oldin obuna bo'lmagan bo'lsa va kanalda yo'q bo'lsa
    if not is_user_subscribed_db(user_id):
        if not await check_subscription(user_id):
            # Yangi dizayndagi obuna talab qilish oynasi
            join_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
                [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")]
            ])
            await message.answer(
                "✨ **MovieTime CN** kinoteatr botiga xush kelibsiz!\n\n"
                "⚠️ Botdan foydalanish va kinolarni qidirish uchun quyidagi kanalimizga obuna bo'ling:",
                reply_markup=join_kb,
                parse_mode="Markdown"
            )
            return
        else:
            add_user_to_db(user_id)

    # Asosiy yangi dizayndagi menyu va Mini App tugmasi
    menu_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kinoteatr Mini App", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text="🔍 Kino kodini yuborish", callback_data="help_code")]
    ])
    
    await message.answer(
        f"👋 Salom, **{message.from_user.first_name}**!\n\n"
        "🎥 Bizning bot orqali istalgan kinoni tomosha qiling yoki **Mini App** tugmasi orqali katalogdan tanlang.\n\n"
        "👇 Marhamat, quyidagi tugmani bosing:",
        reply_markup=menu_kb,
        parse_mode="Markdown"
    )

# 🔄 Obunani tekshirish tugmasi (Callback)
@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        add_user_to_db(user_id)
        await callback.message.delete()
        
        menu_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kinoteatr Mini App", web_app=WebAppInfo(url=WEB_APP_URL))]
        ])
        await callback.message.answer(
            "🎉 **Tabriklayman!** Obunangiz tasdiqlandi.\n\n"
            "Endi kinolardan bemalol foydalanishingiz mumkin!",
            reply_markup=menu_kb,
            parse_mode="Markdown"
        )
    else:
        await callback.answer("❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

@dp.callback_query(F.data == "help_code")
async def help_code_handler(callback: types.CallbackQuery):
    await callback.message.answer("📥 Menga kino kodini yuboring (masalan: `01` yoki `kino1`), men sizga kinoni topib beraman!")
    await callback.answer()

# 🎬 Kanalga tashlangan kinolarni avtomatik bazaga qo'shish (Admin kanalga kino tashlasa)
@dp.message(F.chat.type.in_({"channel", "supergroup"}) & (F.chat.username == CHANNEL_USERNAME.replace('@', '')))
async def auto_save_channel_movie(message: types.Message):
    # Kanalga post tashlanganda agar matnda kod bo'lsa uni bazaga saqlaydi
    if message.caption:
        lines = message.caption.split("\n")
        code = lines[0].strip() # Masalan postning birinchi qatori kino kodi bo'lsa
        conn = sqlite3.connect("movies.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO movies (movie_code, title, file_id) VALUES (?, ?, ?)",
                       (code, message.caption[:30], message.photo[-1].file_id if message.photo else ""))
        conn.commit()
        conn.close()

# 🔎 Foydalanuvchi kino kodi yuborganda qidirib berish
@dp.message(F.text)
async def search_movie(message: types.Message):
    user_id = message.from_user.id
    
    # Har safar obuna so'ramasligi uchun bazadan tekshiramiz
    if not is_user_subscribed_db(user_id):
        if await check_subscription(user_id):
            add_user_to_db(user_id)
        else:
            join_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
                [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")]
            ])
            await message.answer("⚠️ Botdan foydalanish uchun avval kanalimizga obuna bo'ling!", reply_markup=join_kb)
            return

    code = message.text.strip()
    
    # Bazadan kinoni qidirish
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, file_id FROM movies WHERE movie_code = ?", (code,))
    movie = cursor.fetchone()
    conn.close()

    if movie:
        title, file_id = movie
        if file_id:
            await message.answer_video(video=file_id, caption=f"🎬 **{title}**\n\n@movitimecn", parse_mode="Markdown")
        else:
            await message.answer(f"🎬 Kino topildi: **{title}**, lekin fayliktari topilmadi.", parse_mode="Markdown")
    else:
        # Agar bazada topilmasa, kanalga yo'naltiramiz yoki topilmadi deymiz
        await message.answer(
            "❌ Bunday kodli kino topilmadi.\n\n"
            "🔍 Barcha kinolarni ko'rish uchun quyidagi **Mini App** tugmasini bosing:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎬 Kinoteatrni ochish (Mini App)", web_app=WebAppInfo(url=WEB_APP_URL))]
            ])
        )

# Botni ishga tushirish
async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())