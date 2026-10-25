import asyncio
import logging
import sqlite3
import sys
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Sizning botingiz tokeni
API_TOKEN = '8876644496:AAEs6dsbg39ATsoo2-IPOZKtz_OoadRlIT8'

# Admin ID raqamingiz
ADMIN_ID = 7679905644

# Kanal username (Telegram kanalga obunani tekshirish uchun)
CHANNEL_USERNAME = '@movitimecn'

# Instagram sahifangiz havolasi
INSTAGRAM_URL = 'https://www.instagram.com/movietimecn?psln=NGJyODU3cGh2dmty'

# GitHub Pages orqali olingan Mini App havolasi
WEBAPP_URL = 'https://nodirbekyusupboyev06.github.io/movietimecn-app/'

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- SQLITE BAZASINI YARATISH ---
def init_db():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            caption TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cartoons (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            caption TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

class AddContent(StatesGroup):
    waiting_for_type = State()
    waiting_for_code = State()
    waiting_for_video = State()

async def main():
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Telegram kanal obunasini tekshirish funksiyasi
    async def check_telegram_sub(user_id: int) -> bool:
        try:
            member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
            if member.status in ["member", "administrator", "creator"]:
                return True
        except Exception as e:
            print(f"Obunani tekshirishda xatolik: {e}")
        return False

    @dp.message(Command("start"))
    async def send_welcome(message: types.Message):
        user_id = message.from_user.id
        
        # Har safar /start bosganda obunani qaytadan tekshirish uchun bazadan tozalaymiz
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📢 Telegram Kanalga A'zo Bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [types.InlineKeyboardButton(text="✨ Instagram Sahifaga Obuna Bo'lish", url=INSTAGRAM_URL)],
            [types.InlineKeyboardButton(text="✅ Obunani Tekshirish", callback_data="check_sub")]
        ])
        
        await message.reply(
            "🎬 <b>MOVITIMECN • CINEMA EXPERIENCE</b>\n\n"
            "✨ <b>Xush kelibsiz!</b> Botimizdan foydalanish uchun quyidagi 2 ta sahifamizga obuna bo'ling:\n\n"
            "1️⃣ Telegram kanalimizga qo'shiling\n"
            "2️⃣ Instagram sahifamizga obuna bo'ling\n\n"
            "So'ng <b>«✅ Obunani Tekshirish»</b> tugmasini bosing! 🍿",
            reply_markup=markup,
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "check_sub")
    async def process_check_sub(call: types.CallbackQuery):
        user_id = call.from_user.id
        
        # Telegram kanal obunasini tekshiramiz
        is_subbed = await check_telegram_sub(user_id)
        
        if not is_subbed:
            await call.answer("❌ Siz hali Telegram kanalimizga obuna bo'lmadingiz!", show_alert=True)
            return
        
        # Agar obuna bo'lgan bo'lsa bazaga saqlaymiz
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✨ Kino Olamiga Kirish (Mini App) 🎬", web_app=types.WebAppInfo(url=WEBAPP_URL))],
            [
                types.InlineKeyboardButton(text="🎬 Kinolar", callback_data="menu_movies"),
                types.InlineKeyboardButton(text="🧸 Multfilmlar", callback_data="menu_cartoons")
            ]
        ])
        
        await call.message.delete()
        await call.message.answer(
            "🎬 <b>MOVITIMECN • CINEMA EXPERIENCE</b>\n\n"
            "🎉 <b>Tabriklayman! Obunangiz tasdiqlandi.</b>\n\n"
            "🍿 Marhamat, quyidagi tugmalar yordamida Mini App oching yoki kino <b>kodini</b> yuboring:",
            reply_markup=markup,
            parse_mode="HTML"
        )
        await call.answer()

    @dp.callback_query(F.data.in_(["menu_movies", "menu_cartoons"]))
    async def menu_handler(call: types.CallbackQuery):
        user_id = call.from_user.id
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            await call.answer("❌ Avval kanal va Instagram sahifamizga obuna bo'ling!", show_alert=True)
            return

        text = "🎬 <b>Kinolar bo'limi</b>\n\n📥 Kino kodini yuboring (masalan: `1`):" if call.data == "menu_movies" else "🧸 <b>Multfilmlar bo'limi</b>\n\n📥 Multfilm kodini yuboring:"
        await call.message.edit_text(text, parse_mode="HTML")
        await call.answer()

    # --- ADMIN: KINO YOKI MULTFILM QO'SHish ---
    @dp.message(Command("addmovie"))
    async def add_movie_start(message: types.Message, state: FSMContext):
        if message.from_user.id != ADMIN_ID:
            await message.reply("❌ Bu buyruq faqat admin uchun!")
            return
        
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="add_type_movie"),
                types.InlineKeyboardButton(text="🧸 Multfilm qo'shish", callback_data="add_type_cartoon")
            ]
        ])
        await message.reply("Nimmo qo'shmoqchisiz? Tanlang:", reply_markup=markup)
        await state.set_state(AddContent.waiting_for_type)

    @dp.callback_query(AddContent.waiting_for_type, F.data.startswith("add_type_"))
    async def process_content_type(call: types.CallbackQuery, state: FSMContext):
        c_type = "movie" if call.data == "add_type_movie" else "cartoon"
        await state.update_data(content_type=c_type)
        
        await call.message.delete()
        await call.message.answer("1️⃣ Iltimos, ushbu kontent uchun **maxsus kod** yuboring (masalan: `1` yoki `101`):")
        await state.set_state(AddContent.waiting_for_code)
        await call.answer()

    @dp.message(AddContent.waiting_for_code, F.text)
    async def process_code(message: types.Message, state: FSMContext):
        code = message.text.strip().lower()
        data = await state.get_data()
        table = "movies" if data['content_type'] == "movie" else "cartoons"
        
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute(f"SELECT code FROM {table} WHERE code = ?", (code,))
        exists = cursor.fetchone()
        conn.close()
        
        if exists:
            await message.reply(f"⚠️ <code>{code}</code> bu kod allaqachon mavjud! Boshqa kod kiriting:", parse_mode="HTML")
            return

        await state.update_data(code=code)
        await message.reply("2️⃣ Endi ushbu kod uchun **videoni (yoki faylni)** yuboring:")
        await state.set_state(AddContent.waiting_for_video)

    @dp.message(AddContent.waiting_for_video, F.video | F.document)
    async def process_video(message: types.Message, state: FSMContext):
        data = await state.get_data()
        code = data['code']
        table = "movies" if data['content_type'] == "movie" else "cartoons"
        
        file_id = message.video.file_id if message.video else message.document.file_id
        caption = message.caption or "🎬 MOVITIMECN"
        
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute(f"INSERT OR REPLACE INTO {table} (code, file_id, caption) VALUES (?, ?, ?)", (code, file_id, caption))
        conn.commit()
        conn.close()
        
        name = "Kino" if table == "movies" else "Multfilm"
        await message.reply(f"✅ {name} muvaffaqiyatli saqlandi!\nKodi: <code>{code}</code>", parse_mode="HTML")
        await state.clear()

    # --- KINONI O'CHIRISH ---
    @dp.message(Command("delmovie"))
    async def delete_movie(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.reply("❌ Bu buyruq faqat admin uchun!")
            return
        
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("⚠️ Qaysi kodni o'chirmoqchisiz? Masalan: /delmovie 1")
            return
        
        code = args[1].strip().lower()
        
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("SELECT code FROM movies WHERE code = ?", (code,))
        m_exists = cursor.fetchone()
        
        cursor.execute("SELECT code FROM cartoons WHERE code = ?", (code,))
        c_exists = cursor.fetchone()
        
        if m_exists:
            cursor.execute("DELETE FROM movies WHERE code = ?", (code,))
            conn.commit()
            conn.close()
            await message.reply(f"✅ <code>{code}</code> kodli kino o'chirib tashlandi!", parse_mode="HTML")
        elif c_exists:
            cursor.execute("DELETE FROM cartoons WHERE code = ?", (code,))
            conn.commit()
            conn.close()
            await message.reply(f"✅ <code>{code}</code> kodli multfilm o'chirib tashlandi!", parse_mode="HTML")
        else:
            conn.close()
            await message.reply(f"❌ <code>{code}</code> kodli kontent topilmadi.", parse_mode="HTML")

    # --- FOYDALANUVCHI KOD YUBORGANDA ---
    @dp.message(F.text)
    async def get_content(message: types.Message):
        if message.text.startswith('/'):
            return

        user_id = message.from_user.id
        
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📢 Telegram Kanalga A'zo Bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
                [types.InlineKeyboardButton(text="✨ Instagram Sahifaga Obuna Bo'lish", url=INSTAGRAM_URL)],
                [types.InlineKeyboardButton(text="✅ Obunani Tekshirish", callback_data="check_sub")]
            ])
            await message.reply(
                "🎬 <b>MOVITIMECN • CINEMA EXPERIENCE</b>\n\n"
                "⚠️ Botdan foydalanish uchun avval kanalimiz va Instagram sahifamizga obuna bo'ling, so'ng **«✅ Obunani Tekshirish»** tugmasini bosing:",
                reply_markup=markup,
                parse_mode="HTML"
            )
            return

        code = message.text.strip().lower()
        
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("SELECT file_id, caption FROM movies WHERE code = ?", (code,))
        content = cursor.fetchone()
        
        if not content:
            cursor.execute("SELECT file_id, caption FROM cartoons WHERE code = ?", (code,))
            content = cursor.fetchone()

        conn.close()
        
        if content:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="📉 480p", callback_data=f"ql_{code}_480"),
                    types.InlineKeyboardButton(text="💻 720p", callback_data=f"ql_{code}_720"),
                    types.InlineKeyboardButton(text="💎 1080p", callback_data=f"ql_{code}_1080")
                ]
            ])
            
            await message.reply(
                f"🎬 <b>Kodi:</b> <code>{code}</code>\n\n✨ Marhamat, kerakli sifatni tanlang:",
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            await message.reply("❌ Bunday kodli kino yoki multfilm topilmadi. Kodni tekshirib qaytadan yuboring.")

    # --- SIFAT TANLANGANDA VIDEONI YUBORISH ---
    @dp.callback_query(F.data.startswith("ql_"))
    async def send_quality_video(call: types.CallbackQuery):
        user_id = call.from_user.id
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            conn.close()
            await call.answer("❌ Avval kanal va Instagram sahifamizga obuna bo'ling!", show_alert=True)
            return

        parts = call.data.split("_")
        code = parts[1]
        quality = parts[2]
        
        cursor.execute("SELECT file_id, caption FROM movies WHERE code = ?", (code,))
        content = cursor.fetchone()
        
        if not content:
            cursor.execute("SELECT file_id, caption FROM cartoons WHERE code = ?", (code,))
            content = cursor.fetchone()
            
        conn.close()
        
        if content:
            file_id, caption = content
            await call.message.delete()
            await call.message.answer_video(
                video=file_id,
                caption=f"{caption}\n✨ Sifati: <b>{quality}p</b>\n\n@movitimecn",
                parse_mode="HTML"
            )
            await call.answer()
        else:
            await call.answer("❌ Kechirasiz, bu video topilmadi.", show_alert=True)

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())