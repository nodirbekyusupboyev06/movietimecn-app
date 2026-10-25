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

# O'z Telegram ID raqamingizni yozing (Admin bo'lish uchun)
ADMIN_ID = 7679905644  # <--- BU YERGA O'Z ID RAQAMINGIZNI YOZING

# Instagram sahifangiz havolasi
INSTAGRAM_URL = 'https://www.instagram.com/movietimecn?psln=NGJyODU3cGh2dmty'

# GitHub Pages orqali olingan Mini App havolangizni bu yerga yozing:
WEBAPP_URL = 'https://nodirbekyusupboyev06.github.io/movietimecn-app/'

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- SQLITE BAZASINI YARATISH ---
def init_db():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    # Kinolar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            caption TEXT
        )
    ''')
    
    # Multfilmlar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cartoons (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            caption TEXT
        )
    ''')
    
    # Obuna bo'lgan foydalanuvchilar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Kontent qo'shish uchun bosqichlar (FSM)
class AddContent(StatesGroup):
    waiting_for_type = State()
    waiting_for_code = State()
    waiting_for_video = State()

async def main():
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(Command("start"))
    async def send_welcome(message: types.Message):
        user_id = message.from_user.id
        
        # Har safar /start bosganda bazadan o'chiramiz (obunani qayta tekshirish uchun)
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✨ OBUNA BO'LDIM ✨", url=INSTAGRAM_URL)],
            [types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_insta")]
        ])
        await message.reply(
            "🎬 <b>MOVITIMECN</b>\n"
            "<i>CINEMA EXPERIENCE</i>\n\n"
            "🎬 <b>Xush kelibsiz!</b>\n\n"
            "Kinolar olamiga kirish uchun birgina qadam qoldi 🍿\n\n"
            "🔒 <b>Botdan foydalanish uchun</b>\n"
            "Avval Instagram sahifamizga obuna bo'ling. So'ng quyidagi tugmani bosib, kino olamiga yo'l oling!\n\n"
            "<i>MOVITIMECN • Your world of movies</i>",
            reply_markup=markup,
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "check_insta")
    async def process_check_insta(call: types.CallbackQuery):
        user_id = call.from_user.id
        
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        
        # Mini App ochiladigan tugma
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✨ Kino Olamiga Kirish 🎬", web_app=types.WebAppInfo(url=WEBAPP_URL))],
            [
                types.InlineKeyboardButton(text="🎬 Kinolar", callback_data="menu_movies"),
                types.InlineKeyboardButton(text="🧸 Multfilmlar", callback_data="menu_cartoons")
            ]
        ])
        
        await call.message.delete()
        await call.message.answer(
            "🎬 <b>MOVITIMECN</b>\n"
            "<i>CINEMA EXPERIENCE</i>\n\n"
            "✨ <b>Xush kelibsiz!</b>\n\n"
            "✅ <b>Obuna muvaffaqiyatli tasdiqlandi!</b>\n\n"
            "🍿 Kerakli kino yoki multfilm <b>kodini</b> yuboring:",
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
            await call.answer("❌ Avval Instagram sahifamizga obuna bo'lib, tasdiqlang!", show_alert=True)
            return

        text = "🎬 <b>Kinolar bo'limi</b>\nKino kodini yuboring (masalan: `1`):" if call.data == "menu_movies" else "🧸 <b>Multfilmlar bo'limi</b>\nMultfilm kodini yuboring:"
        await call.message.edit_text(text, parse_mode="HTML")
        await call.answer()

    # --- ADMIN: KINO YOKI MULTFILM QO'SHISH ---
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
        
        if not user:
            conn.close()
            markup = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="✨ OBUNA BO'LDIM ✨", url=INSTAGRAM_URL)],
                [types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_insta")]
            ])
            await message.reply(
                "🎬 <b>MOVITIMECN</b>\n"
                "<i>CINEMA EXPERIENCE</i>\n\n"
                "⚠️ Botdan foydalanish uchun avval **Instagram** sahifamizga obuna bo'ling va «✅ Tasdiqlash» tugmasini bosing:",
                reply_markup=markup,
                parse_mode="HTML"
            )
            return

        code = message.text.strip().lower()
        
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
                f"🎬 <b>Kodi:</b> <code>{code}</code>\n\nKerakli sifatni tanlang:",
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
            await call.answer("❌ Avval Instagram sahifamizga obuna bo'ling!", show_alert=True)
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
                caption=f"{caption}\n✨ Sifati: <b>{quality}p</b>",
                parse_mode="HTML"
            )
            await call.answer()
        else:
            await call.answer("❌ Kechirasiz, bu video topilmadi.", show_alert=True)

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())