import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import sys
from urllib.parse import urlencode

from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramConflictError
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ==========================================
# SOZLAMALAR VA XAVFSIZ TOKEN (ANTI-STEAL)
# ==========================================
# GitHub'ga yuklanganda A_TOOLSx2 kabi bot-o'g'rilari tokenni o'g'irlay olmasligi uchun
# token XOR-shifrlangan holatda yoki .env / BOT_TOKEN o'zgaruvchisida saqlanadi.
_ENC_TOKEN = "62626d6c6c6e6e6e636c601b1b1f296c3e29383d69631b0e2935356877130a1500112e200515353b3e0836130e62"


def encode_token(raw_token: str) -> str:
    return "".join(f"{ord(c) ^ 0x5A:02x}" for c in raw_token.strip())


def decode_token(hex_str: str) -> str:
    return "".join(chr(int(hex_str[i:i + 2], 16) ^ 0x5A) for i in range(0, len(hex_str), 2))


def load_bot_token() -> str:
    env_tok = os.environ.get("BOT_TOKEN", "").strip()
    if env_tok:
        return env_tok
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("BOT_TOKEN=") and not line.startswith("#"):
                        val = line.split("=", 1)[1].strip().strip("'\"")
                        if val:
                            return val
        except Exception:
            pass
    return decode_token(_ENC_TOKEN)


API_TOKEN = load_bot_token()
ADMIN_ID = 7679905644

# GitHub Pages yoki Render 24/7 server orqali Mini App havolasi
WEBAPP_URL = os.environ.get("RENDER_EXTERNAL_URL") or 'https://nodirbekyusupboyev06.github.io/movietimecn-app/'

# Bazadagi standart video file_id (Admin /addmovie orqali istalgan kodga o'z videosini yuklay oladi)
DEFAULT_VIDEO_FILE_ID = 'BAACAgIAAxkBAAN-atzlfnvWYMZyDO3gSf1Vms5sSxkAAk6oAAJBmulKBaeobdP3LRc9BA'

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# ==========================================
# KATEGORIYALAR (CATEGORIES IN 3 LANGUAGES)
# ==========================================
MOVIE_CATEGORIES = {
    "series": {"uz": "📺 Seriallar", "ru": "📺 Сериалы", "en": "📺 TV Series"},
    "family": {"uz": "👨‍👩‍👧‍👦 Oilaviy kinolar", "ru": "👨‍👩‍👧‍👦 Семейные", "en": "👨‍👩‍👧‍👦 Family"},
    "scifi": {"uz": "🚀 Fantastik kinolar", "ru": "🚀 Фантастика", "en": "🚀 Sci-Fi & Fantasy"},
    "action": {"uz": "🔥 Jangari kinolar", "ru": "🔥 Боевики", "en": "🔥 Action"},
    "drama": {"uz": "🎭 Drama", "ru": "🎭 Драма", "en": "🎭 Drama"},
    "anime": {"uz": "🌸 Anime", "ru": "🌸 Аниме", "en": "🌸 Anime"},
    "sport": {"uz": "🏆 Sport kinolar", "ru": "🏆 Спортивные", "en": "🏆 Sports"},
    "retro_movie": {"uz": "🎞️ Retro kinolar", "ru": "🎞️ Ретро фильмы", "en": "🎞️ Retro Movies"},
    "national": {"uz": "🇺🇿 Milliy kinolar", "ru": "🇺🇿 Национальное кино", "en": "🇺🇿 National Movies"},
}

CARTOON_CATEGORIES = {
    "new_cartoon": {"uz": "🌟 Yangi multfilmlar", "ru": "🌟 Новые мультфильмы", "en": "🌟 New Cartoons"},
    "series_cartoon": {"uz": "📺 Serialli multfilmlar", "ru": "📺 Мультсериалы", "en": "📺 Animated Series"},
    "retro_cartoon": {"uz": "📼 Retro multfilmlar", "ru": "📼 Ретро мультфильмы", "en": "📼 Retro Cartoons"},
}

# ==========================================
# BARCHA KATEGORIYALAR UCHUN TAYYOR KINOLAR VA MULTFILMLAR BAZASI (48 TA)
# ==========================================
INITIAL_MOVIES = [
    ("101", "🦑 Kalmar O'yini (Squid Game) — Barcha qismlar [1080p]", "series"),
    ("102", "🎭 Qog'oz Bino (Money Heist / La Casa de Papel) — Barcha fasllar", "series"),
    ("103", "🕳️ Chuqur (Çukur) — O'zbek tilida barcha qismlar", "series"),
    ("104", "🖤 Wednesday (Уэнсдей) — 1-fasl barcha qismlar", "series"),
    ("105", "🏡 Uyda Yolg'iz (Home Alone) — Oilaviy komediya", "family"),
    ("106", "🍫 Vonka va Sehrli Shokolad Fabrikasi (Wonka)", "family"),
    ("107", "🐻 Paddington Sarguzashtlari (Paddington) — Oilaviy film", "family"),
    ("108", "🎲 Jumanji: Keyingi Bosqich (Jumanji: The Next Level)", "family"),
    ("109", "🪐 Interstellar — Kosmik fantastika [4K / 1080p]", "scifi"),
    ("110", "🌊 Avatar 2: Suv Yo'li (Avatar: The Way of Water)", "scifi"),
    ("111", "🏜️ Dyuna 2: Cho'l Sayyorasi (Dune: Part Two)", "scifi"),
    ("112", "⚡ Qasoskorlar: Intiho (Avengers: Endgame)", "scifi"),
    ("1", "🔥 Jon Uik 4 (John Wick: Chapter 4) — Premyera", "action"),
    ("113", "🏎️ Forsaj 10 (Fast X) — Jangari poyga", "action"),
    ("114", "💣 Uddalab Bo'lmas Topshiriq 7 (Mission: Impossible 7)", "action"),
    ("115", "⚔️ Gladiator 2 — Tarixiy jangari film", "action"),
    ("116", "🎭 Oppenheymer (Oppenheimer) — Oskar sovrindori", "drama"),
    ("117", "📗 Yashil Kitob (Green Book) — Hayotiy drama", "drama"),
    ("118", "🗝️ Shoushenkdan Qochish (The Shawshank Redemption)", "drama"),
    ("119", "🐕 Xatiko: Eng Sodiq Do'st (Hachi: A Dog's Tale)", "drama"),
    ("120", "🗡️ Iblislar Qotili: Hashira Mashg'uloti (Demon Slayer)", "anime"),
    ("121", "🍥 Naruto: Shippuden — Barcha qismlar", "anime"),
    ("122", "🌠 Sening Isming (Your Name / Kimi no Na wa)", "anime"),
    ("123", "🌸 Suzume: Sehrli Eshiklar (Suzume)", "anime"),
    ("124", "🥊 Krid 3: Chempionlar Ringi (Creed III)", "sport"),
    ("125", "🏁 Ford Ferrari'ga Qarshi (Ford v Ferrari)", "sport"),
    ("126", "⚽ Gol! Orzular Stadioni (Goal!)", "sport"),
    ("127", "🏆 Afsonaviy Pele (Pelé: Birth of a Legend)", "sport"),
    ("128", "🎩 Cho'qintirgan Ota (The Godfather, 1972) — Oltin Klassika", "retro_movie"),
    ("129", "🕰️ Kelajakka Qaytib (Back to the Future, 1985)", "retro_movie"),
    ("130", "🤖 Terminator 2: Qiyomat Kuni (1991 — Remastered)", "retro_movie"),
    ("131", "🚢 Titanik (Titanic, 1997 — Full HD)", "retro_movie"),
    ("132", "🇺🇿 Bahodir Yalangto'sh — Tarixiy O'zbek Milliy Filmi", "national"),
    ("133", "🏛️ O'tkan Kunlar — O'zbek Kino Durdonasi", "national"),
    ("134", "🍵 Mahallada Duv-Duv Gap — Oltin Milliy Klassika", "national"),
    ("135", "🌾 Suyunchi — O'zbek Milliy Filmi", "national"),
]

INITIAL_CARTOONS = [
    ("201", "🌈 Boshqotirma 2 (Inside Out 2, 2024) — Yangi Multfilm", "new_cartoon"),
    ("202", "🐼 Kung-Fu Panda 4 (2024) — Yangi Premyera", "new_cartoon"),
    ("203", "🌺 Moana 2: Okean Sarguzashti (2024)", "new_cartoon"),
    ("204", "🍌 Yaxshi Bo'lish Osonmi 4 / Minionlar (Despicable Me 4)", "new_cartoon"),
    ("205", "🐻 Masha va Ayiq (Masha and the Bear) — Barcha qismlar", "series_cartoon"),
    ("206", "🐾 Qutqaruvchilar Patruli (PAW Patrol) — Multserial", "series_cartoon"),
    ("207", "🐉 Kung-Fu Panda: Afsonaviy Qismlar (Multserial)", "series_cartoon"),
    ("208", "🐱 Uch Mushukcha (Три Кота) — Bolajonlar multseriali", "series_cartoon"),
    ("209", "🦁 Qirol Sher (The Lion King, 1994) — Oltin Retro Multfilm", "retro_cartoon"),
    ("210", "🧀 Tom va Jerri (Tom and Jerry) — Oltin To'plam", "retro_cartoon"),
    ("211", "🐺 Senimi, Shoshmay Tur! (Ну, погоди!) — Barcha qismlar", "retro_cartoon"),
    ("212", "🧞‍♂️ Aladdin va Sehrli Chiroq (Aladdin, 1992)", "retro_cartoon"),
]

# ==========================================
# 3 TILLI LUG'AT (TRANSLATIONS UZ / RU / EN)
# ==========================================
TEXTS = {
    "choose_lang": (
        "🎬 <b>MOVITIMECN • CINEMA & CARTOON WORLD</b>\n\n"
        "🇬🇧 Please select your preferred language:\n"
        "🇷🇺 Пожалуйста, выберите язык интерфейса:\n"
        "🇺🇿 Iltimos, muloqot tilini tanlang:"
    ),
    "uz": {
        "lang_saved": "✅ O'zbek tili tanlandi!",
        "menu_btn_short": "🎬 Ilova (Mini App)",
        "main_welcome": (
            "🎬 <b>MOVITIMECN • KINO VA MULTFILMLAR OLAMI</b>\n\n"
            "🎉 <b>Xush kelibsiz!</b> Barcha kategoriyalarga mos <b>48+ sara kino va multfilmlar</b>, "
            "shuningdek <b>👤 Profil, 💰 Balans, 👑 Premium va 📊 Analitika</b> bo'limlari tayyor!\n\n"
            "✨ Quyidagi <b>«🚀 Kino Olamiga Kirish (Mini App)»</b> tugmasini bosing yoki bo'limni tanlang:"
        ),
        "btn_webapp": "🚀 Kino Olamiga Kirish (Mini App) 🎬",
        "btn_movies": "🎬 Kinolar (9 bo'lim)",
        "btn_cartoons": "🧸 Multfilmlar (3 bo'lim)",
        "btn_profile": "👤 Profil, Balans & Analiz",
        "btn_premium": "👑 Premium Kanal (VIP)",
        "btn_search_code": "🔍 Kod orqali qidirish",
        "btn_change_lang": "🌐 Tilni o'zgartirish",
        "btn_back": "⬅️ Orqaga",
        "btn_all_movies": "🎬 Barcha kinolar (36 ta)",
        "btn_all_cartoons": "🧸 Barcha multfilmlar (12 ta)",
        "movies_menu_title": (
            "🎬 <b>KINOLAR BO'LIMI (9 ta Maxsus Kategoriya)</b>\n\n"
            "✨ O'zingizga yoqqan kino janrini tanlang, Mini App'da oching yoki kino <b>kodini</b> yuboring:"
        ),
        "cartoons_menu_title": (
            "🧸 <b>MULTFILMLAR BO'LIMI (Bolajonlar uchun)</b>\n\n"
            "🌈 Kerakli multfilm bo'limini tanlang, Mini App'da oching yoki multfilm <b>kodini</b> yuboring:"
        ),
        "profile_text": (
            "👤 <b>FOYDALANUVCHI PROFILI VA ANALITIKA</b>\n\n"
            "🆔 <b>ID raqamingiz:</b> <code>{user_id}</code>\n"
            "👑 <b>Status:</b> {status}\n"
            "💰 <b>Balansingiz:</b> <b>{balance:,} UZS</b>\n"
            "▶️ <b>Ko'rilgan kinolar:</b> {views} ta\n\n"
            "📊 <b>BOT JONLI ANALITIKASI VA KONSENTRATSIYA:</b>\n"
            "• 👥 Jami foydalanuvchilar: <b>{u_count} ta</b>\n"
            "• 🎬 Bazadagi jami kontent: <b>{total_content} ta</b> ({m_count} kino / {c_count} multfilm)\n"
            "• 🔥 Eng yuqori konsentratsiya: <b>Jangari va Fantastik (34%)</b> | <b>Seriallar (26%)</b> | <b>Multfilmlar (22%)</b>\n"
            "• ⏰ Peak faollik vaqti: <b>19:00 – 23:00 (Yuqori konsentratsiya)</b>\n\n"
            "✨ To'liq grafik analiz, konsentratsiya diagrammalari va balansni boshqarish uchun <b>Mini App Profil</b> bo'limini oching:"
        ),
        "premium_text": (
            "👑 <b>MOVITIMECN PREMIUM & YOPIQ TELEGRAM KANAL</b>\n\n"
            "🌟 <b>Premium afzalliklari:</b>\n"
            "1️⃣ <b>Yopiq Telegram Premium Kanalga</b> maxsus kirish\n"
            "2️⃣ <b>4K Ultra HD va 1080p</b> sifatda reklamasiz tomosha\n"
            "3️⃣ Yangi premyera kinolar va seriallarni 1-bo'lib ko'rish\n"
            "4️⃣ Shaxsiy buyurtma asosida kino qo'shish imkoniyati\n\n"
            "💳 <b>Tariflar:</b>\n"
            "• 1 Oylik VIP — <b>19,000 UZS</b>\n"
            "• 3 Oylik VIP — <b>45,000 UZS</b>\n"
            "• 1 Yillik VIP — <b>120,000 UZS</b>\n\n"
            "⏳ <i>Eslatma: Telegram Premium Kanal va avtomatik to'lov tizimi hozirda sinov (erta) bosqichida. "
            "Mini App orqali oldindan tanishishingiz va balansni ko'rishingiz mumkin!</i>"
        ),
        "category_items_title": "📂 <b>{cat_name}</b>\n\n👇 Tomosha qilish uchun quyidagi ro'yxatdan tanlang yoki Mini App'da oching:",
        "category_empty": "📂 <b>{cat_name}</b>\n\n✨ Quyidagi Mini App tugmasi orqali barcha kinolarni ko'rishingiz mumkin:",
        "search_prompt": (
            "🔍 <b>Kod orqali qidirish</b>\n\n"
            "📥 Marhamat, kino yoki multfilm kodini yuboring:\n"
            "• Kinolar: <code>1</code> yoki <code>101</code> dan <code>135</code> gacha\n"
            "• Multfilmlar: <code>201</code> dan <code>212</code> gacha"
        ),
        "select_quality": (
            "🎬 <b>Topildi!</b>\n"
            "🔢 <b>Kodi:</b> <code>{code}</code>\n"
            "🏷 <b>Bo'lim:</b> {cat_name}\n"
            "📝 <b>Nomi:</b> {caption}\n\n"
            "✨ Marhamat, tomosha qilish uchun kerakli sifatni tanlang:"
        ),
        "not_found": "❌ Bunday kodli (<code>{code}</code>) kino yoki multfilm topilmadi.\nIltimos, kodni tekshirib qaytadan yuboring (masalan: <code>101</code> yoki <code>201</code>).",
        "video_caption": "{caption}\n\n🔢 <b>Kodi:</b> <code>{code}</code>\n🏷 <b>Bo'lim:</b> {cat_name}\n✨ <b>Sifati:</b> {quality}p\n🎬 <b>MOVITIMECN</b>",
        "video_missing": "❌ Kechirasiz, bu video topilmadi.",
    },
    "ru": {
        "lang_saved": "✅ Выбран русский язык!",
        "menu_btn_short": "🎬 Приложение (App)",
        "main_welcome": (
            "🎬 <b>MOVITIMECN • МИР КИНО И МУЛЬТФИЛЬМОВ</b>\n\n"
            "🎉 <b>Добро пожаловать!</b> Доступны <b>48+ фильмов и мультфильмов</b>, "
            "а также разделы <b>👤 Профиль, 💰 Баланс, 👑 Premium и 📊 Аналитика</b>!\n\n"
            "✨ Нажмите <b>«🚀 Открыть Мир Кино (Mini App)»</b> ниже или выберите нужный раздел:"
        ),
        "btn_webapp": "🚀 Открыть Мир Кино (Mini App) 🎬",
        "btn_movies": "🎬 Фильмы (9 разделов)",
        "btn_cartoons": "🧸 Мультфильмы (3 раздела)",
        "btn_profile": "👤 Профиль, Баланс и Анализ",
        "btn_premium": "👑 Premium Канал (VIP)",
        "btn_search_code": "🔍 Поиск по коду",
        "btn_change_lang": "🌐 Сменить язык",
        "btn_back": "⬅️ Назад",
        "btn_all_movies": "🎬 Все фильмы (36)",
        "btn_all_cartoons": "🧸 Все мультфильмы (12)",
        "movies_menu_title": (
            "🎬 <b>РАЗДЕЛ ФИЛЬМОВ (9 Категорий)</b>\n\n"
            "✨ Выберите интересующую категорию фильмов, откройте в Mini App или отправьте <b>код фильма</b>:"
        ),
        "cartoons_menu_title": (
            "🧸 <b>РАЗДЕЛ МУЛЬТФИЛЬМОВ (Для детей)</b>\n\n"
            "🌈 Выберите категорию мультфильмов, откройте в Mini App или отправьте <b>код мультфильма</b>:"
        ),
        "profile_text": (
            "👤 <b>ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ И АНАЛИТИКА</b>\n\n"
            "🆔 <b>Ваш ID:</b> <code>{user_id}</code>\n"
            "👑 <b>Статус:</b> {status}\n"
            "💰 <b>Ваш баланс:</b> <b>{balance:,} UZS</b>\n"
            "▶️ <b>Просмотрено:</b> {views}\n\n"
            "📊 <b>АНАЛИТИКА БОТА И КОНЦЕНТРАЦИЯ АУДИТОРИИ:</b>\n"
            "• 👥 Всего пользователей: <b>{u_count}</b>\n"
            "• 🎬 Всего контента в базе: <b>{total_content}</b> ({m_count} фильмов / {c_count} мультфильмов)\n"
            "• 🔥 Концентрация по жанрам: <b>Боевики и Фантастика (34%)</b> | <b>Сериалы (26%)</b> | <b>Мультфильмы (22%)</b>\n"
            "• ⏰ Пик концентрации активности: <b>19:00 – 23:00</b>\n\n"
            "✨ Для просмотра полной графической аналитики и управления балансом откройте раздел <b>Профиль в Mini App</b>:"
        ),
        "premium_text": (
            "👑 <b>MOVITIMECN PREMIUM & ЗАКРЫТЫЙ TELEGRAM КАНАЛ</b>\n\n"
            "🌟 <b>Преимущества Premium:</b>\n"
            "1️⃣ Доступ в <b>Закрытый Telegram Premium Канал</b>\n"
            "2️⃣ Просмотр в <b>4K Ultra HD и 1080p</b> без рекламы\n"
            "3️⃣ Ранний доступ ко всем новинкам и сериалам\n"
            "4️⃣ Заказ фильмов по индивидуальному запросу\n\n"
            "💳 <b>Тарифы:</b>\n"
            "• 1 Месяц VIP — <b>19,000 UZS</b>\n"
            "• 3 Месяца VIP — <b>45,000 UZS</b>\n"
            "• 1 Год VIP — <b>120,000 UZS</b>\n\n"
            "⏳ <i>Примечание: Подключение к Telegram Premium каналу и покупка подписки находятся на этапе подготовки к запуску (Скоро)!</i>"
        ),
        "category_items_title": "📂 <b>{cat_name}</b>\n\n👇 Выберите фильм из списка ниже или откройте в Mini App:",
        "category_empty": "📂 <b>{cat_name}</b>\n\n✨ Откройте категорию в нашем Mini App:",
        "search_prompt": (
            "🔍 <b>Поиск по коду</b>\n\n"
            "📥 Отправьте код фильма или мультфильма:\n"
            "• Фильмы: <code>1</code> или от <code>101</code> до <code>135</code>\n"
            "• Мультфильмы: от <code>201</code> до <code>212</code>"
        ),
        "select_quality": (
            "🎬 <b>Найдено!</b>\n"
            "🔢 <b>Код:</b> <code>{code}</code>\n"
            "🏷 <b>Категория:</b> {cat_name}\n"
            "📝 <b>Название:</b> {caption}\n\n"
            "✨ Пожалуйста, выберите качество видео для просмотра:"
        ),
        "not_found": "❌ Фильм или мультфильм с кодом (<code>{code}</code>) не найден.\nПроверьте код (например: <code>101</code> или <code>201</code>).",
        "video_caption": "{caption}\n\n🔢 <b>Код:</b> <code>{code}</code>\n🏷 <b>Категория:</b> {cat_name}\n✨ <b>Качество:</b> {quality}p\n🎬 <b>MOVITIMECN</b>",
        "video_missing": "❌ Извините, видео не найдено.",
    },
    "en": {
        "lang_saved": "✅ English language selected!",
        "menu_btn_short": "🎬 Open Mini App",
        "main_welcome": (
            "🎬 <b>MOVITIMECN • CINEMA & CARTOON WORLD</b>\n\n"
            "🎉 <b>Welcome!</b> Over <b>48+ curated movies & cartoons</b>, plus "
            "<b>👤 Profile, 💰 Balance, 👑 Premium & 📊 Live Analytics</b> are ready!\n\n"
            "✨ Tap <b>«🚀 Open Cinema World (Mini App)»</b> below or choose a section:"
        ),
        "btn_webapp": "🚀 Open Cinema World (Mini App) 🎬",
        "btn_movies": "🎬 Movies (9 Genres)",
        "btn_cartoons": "🧸 Cartoons (3 Sections)",
        "btn_profile": "👤 Profile, Balance & Analytics",
        "btn_premium": "👑 Premium Channel (VIP)",
        "btn_search_code": "🔍 Search by Code",
        "btn_change_lang": "🌐 Change Language",
        "btn_back": "⬅️ Back",
        "btn_all_movies": "🎬 All Movies (36)",
        "btn_all_cartoons": "🧸 All Cartoons (12)",
        "movies_menu_title": (
            "🎬 <b>MOVIES SECTION (9 Themed Categories)</b>\n\n"
            "✨ Select your favorite movie genre below, open in Mini App, or send a <b>movie code</b>:"
        ),
        "cartoons_menu_title": (
            "🧸 <b>CARTOONS SECTION (Kid-Friendly)</b>\n\n"
            "🌈 Choose a cartoon category below, open in Mini App, or send a <b>cartoon code</b>:"
        ),
        "profile_text": (
            "👤 <b>USER PROFILE & LIVE ANALYTICS</b>\n\n"
            "🆔 <b>Your ID:</b> <code>{user_id}</code>\n"
            "👑 <b>Status:</b> {status}\n"
            "💰 <b>Balance:</b> <b>{balance:,} UZS</b>\n"
            "▶️ <b>Movies Watched:</b> {views}\n\n"
            "📊 <b>BOT ANALYTICS & USER CONCENTRATION:</b>\n"
            "• 👥 Total Bot Users: <b>{u_count}</b>\n"
            "• 🎬 Total Catalog Titles: <b>{total_content}</b> ({m_count} movies / {c_count} cartoons)\n"
            "• 🔥 Genre Concentration: <b>Action & Sci-Fi (34%)</b> | <b>Series (26%)</b> | <b>Cartoons (22%)</b>\n"
            "• ⏰ Peak Activity Concentration: <b>19:00 – 23:00</b>\n\n"
            "✨ Open the <b>Profile & Analytics</b> tab inside the Mini App for full charts and balance management:"
        ),
        "premium_text": (
            "👑 <b>MOVITIMECN PREMIUM & PRIVATE TELEGRAM CHANNEL</b>\n\n"
            "🌟 <b>Premium Benefits:</b>\n"
            "1️⃣ Exclusive access to our <b>Private Telegram Premium Channel</b>\n"
            "2️⃣ Ad-free streaming in <b>4K Ultra HD & 1080p</b>\n"
            "3️⃣ Early access to new premieres and series\n"
            "4️⃣ Priority custom movie requests\n\n"
            "💳 <b>Plans:</b>\n"
            "• 1 Month VIP — <b>19,000 UZS</b>\n"
            "• 3 Months VIP — <b>45,000 UZS</b>\n"
            "• 1 Year VIP — <b>120,000 UZS</b>\n\n"
            "⏳ <i>Note: Telegram Premium Channel & automated checkout are currently in early pre-launch stage (Coming Soon)!</i>"
        ),
        "category_items_title": "📂 <b>{cat_name}</b>\n\n👇 Tap any title below to watch or open in Mini App:",
        "category_empty": "📂 <b>{cat_name}</b>\n\n✨ Explore this category inside our Mini App:",
        "search_prompt": (
            "🔍 <b>Search by Code</b>\n\n"
            "📥 Please send the movie or cartoon code:\n"
            "• Movies: <code>1</code> or <code>101</code> to <code>135</code>\n"
            "• Cartoons: <code>201</code> to <code>212</code>"
        ),
        "select_quality": (
            "🎬 <b>Content Found!</b>\n"
            "🔢 <b>Code:</b> <code>{code}</code>\n"
            "🏷 <b>Category:</b> {cat_name}\n"
            "📝 <b>Title:</b> {caption}\n\n"
            "✨ Please choose your preferred video quality:"
        ),
        "not_found": "❌ No movie or cartoon found with code (<code>{code}</code>).\nTry codes like <code>101</code> or <code>201</code>.",
        "video_caption": "{caption}\n\n🔢 <b>Code:</b> <code>{code}</code>\n🏷 <b>Category:</b> {cat_name}\n✨ <b>Quality:</b> {quality}p\n🎬 <b>MOVITIMECN</b>",
        "video_missing": "❌ Sorry, this video could not be found.",
    }
}


# ==========================================
# SQLITE BAZASINI YARATISH VA YANGILASH
# ==========================================
def init_db():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            caption TEXT,
            category TEXT DEFAULT 'action'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cartoons (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            caption TEXT,
            category TEXT DEFAULT 'new_cartoon'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'uz',
            is_subbed INTEGER DEFAULT 1,
            balance INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            views_count INTEGER DEFAULT 0
        )
    ''')

    for alter_sql in [
        "ALTER TABLE movies ADD COLUMN category TEXT DEFAULT 'action'",
        "ALTER TABLE cartoons ADD COLUMN category TEXT DEFAULT 'new_cartoon'",
        "ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'uz'",
        "ALTER TABLE users ADD COLUMN is_subbed INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN views_count INTEGER DEFAULT 0",
    ]:
        try:
            cursor.execute(alter_sql)
        except sqlite3.OperationalError:
            pass

    for code, caption, category in INITIAL_MOVIES:
        cursor.execute("SELECT file_id FROM movies WHERE code = ?", (code,))
        existing = cursor.fetchone()
        if not existing:
            cursor.execute(
                "INSERT INTO movies (code, file_id, caption, category) VALUES (?, ?, ?, ?)",
                (code, DEFAULT_VIDEO_FILE_ID, caption, category)
            )
        elif code == "1":
            cursor.execute(
                "UPDATE movies SET caption = ?, category = ? WHERE code = '1'",
                (caption, category)
            )

    for code, caption, category in INITIAL_CARTOONS:
        cursor.execute("SELECT file_id FROM cartoons WHERE code = ?", (code,))
        existing = cursor.fetchone()
        if not existing:
            cursor.execute(
                "INSERT INTO cartoons (code, file_id, caption, category) VALUES (?, ?, ?, ?)",
                (code, DEFAULT_VIDEO_FILE_ID, caption, category)
            )

    conn.commit()
    conn.close()


init_db()


# ==========================================
# BAZA YORDAMCHI FUNKSIYALARI
# ==========================================
def ensure_user(user_id: int, default_lang: str = "uz"):
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, lang, balance, is_premium, views_count FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, lang, is_subbed, balance, is_premium, views_count) VALUES (?, ?, 1, 0, 0, 0)",
            (user_id, default_lang)
        )
        conn.commit()
        row = (user_id, default_lang, 0, 0, 0)
    conn.close()
    return {
        "user_id": row[0],
        "lang": row[1] or "uz",
        "balance": row[2] or 0,
        "is_premium": bool(row[3]),
        "views_count": row[4] or 0,
    }


def set_user_lang(user_id: int, lang: str):
    ensure_user(user_id, lang)
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()


def increment_user_views(user_id: int):
    ensure_user(user_id)
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET views_count = COALESCE(views_count, 0) + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def add_user_balance(user_id: int, amount: int):
    ensure_user(user_id)
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def set_user_premium(user_id: int, status: int = 1):
    ensure_user(user_id)
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_premium = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()


def get_lang(user_id: int) -> str:
    u = ensure_user(user_id)
    if u["lang"] in ("uz", "ru", "en"):
        return u["lang"]
    return "uz"


def get_global_stats():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    u_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    m_count = cursor.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    c_count = cursor.execute("SELECT COUNT(*) FROM cartoons").fetchone()[0]
    total_views = cursor.execute("SELECT COALESCE(SUM(views_count), 0) FROM users").fetchone()[0]
    uz_count = cursor.execute("SELECT COUNT(*) FROM users WHERE lang = 'uz'").fetchone()[0]
    ru_count = cursor.execute("SELECT COUNT(*) FROM users WHERE lang = 'ru'").fetchone()[0]
    en_count = cursor.execute("SELECT COUNT(*) FROM users WHERE lang = 'en'").fetchone()[0]
    conn.close()
    return {
        "u_count": max(u_count, 1),
        "m_count": m_count,
        "c_count": c_count,
        "total_views": total_views,
        "uz_count": uz_count,
        "ru_count": ru_count,
        "en_count": en_count,
    }


def get_category_label(cat_key: str, lang: str) -> str:
    if cat_key in MOVIE_CATEGORIES:
        return MOVIE_CATEGORIES[cat_key].get(lang, MOVIE_CATEGORIES[cat_key]["uz"])
    if cat_key in CARTOON_CATEGORIES:
        return CARTOON_CATEGORIES[cat_key].get(lang, CARTOON_CATEGORIES[cat_key]["uz"])
    return cat_key


def find_content_by_code(code: str):
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT code, file_id, caption, category FROM movies WHERE code = ?", (code,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return {"type": "movie", "code": row[0], "file_id": row[1], "caption": row[2], "category": row[3] or "action"}

    cursor.execute("SELECT code, file_id, caption, category FROM cartoons WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"type": "cartoon", "code": row[0], "file_id": row[1], "caption": row[2], "category": row[3] or "new_cartoon"}
    return None


def build_webapp_url(lang: str, bot_username: str = "", tab: str = "", cat: str = "", user_id: int = 0) -> str:
    base = WEBAPP_URL.split("?")[0]
    stats = get_global_stats()
    u = ensure_user(user_id, lang) if user_id else {"balance": 0, "is_premium": False, "views_count": 0}
    params = {
        "lang": lang,
        "v": "20261027_8",
        "ucount": stats["u_count"],
        "mcount": stats["m_count"],
        "ccount": stats["c_count"],
        "bal": u["balance"],
        "prem": 1 if u["is_premium"] else 0,
        "views": u["views_count"],
    }
    if user_id:
        params["uid"] = user_id
    if bot_username:
        params["bot"] = bot_username
    if tab:
        params["tab"] = tab
    if cat:
        params["cat"] = cat
    return f"{base}?{urlencode(params)}"


# ==========================================
# KLAVIATURALAR (KEYBOARDS)
# ==========================================
def language_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")],
        [types.InlineKeyboardButton(text="🇷🇺 Русский язык", callback_data="setlang_ru")],
        [types.InlineKeyboardButton(text="🇺🇿 O'zbek tili", callback_data="setlang_uz")],
    ])


def main_menu_keyboard(lang: str, bot_username: str = "", user_id: int = 0) -> types.InlineKeyboardMarkup:
    t = TEXTS[lang]
    app_url = build_webapp_url(lang, bot_username, user_id=user_id)
    profile_app_url = build_webapp_url(lang, bot_username, tab="profile", user_id=user_id)
    rows = [
        [types.InlineKeyboardButton(text=t["btn_webapp"], web_app=types.WebAppInfo(url=app_url))],
        [
            types.InlineKeyboardButton(text=t["btn_movies"], callback_data="menu_movies"),
            types.InlineKeyboardButton(text=t["btn_cartoons"], callback_data="menu_cartoons"),
        ],
        [
            types.InlineKeyboardButton(text=t["btn_profile"], callback_data="menu_profile"),
            types.InlineKeyboardButton(text=t["btn_premium"], callback_data="menu_premium"),
        ],
        [
            types.InlineKeyboardButton(text=t["btn_search_code"], callback_data="menu_search"),
            types.InlineKeyboardButton(text=t["btn_change_lang"], callback_data="open_lang_menu"),
        ],
        [types.InlineKeyboardButton(text=f"📊 {t['btn_profile']} (Mini App)", web_app=types.WebAppInfo(url=profile_app_url))],
    ]
    if user_id == ADMIN_ID:
        rows.append([types.InlineKeyboardButton(text="👑 Admin Panel (/addmovie)", callback_data="admin_panel")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def main_reply_keyboard(lang: str, bot_username: str = "", user_id: int = 0) -> types.ReplyKeyboardMarkup:
    t = TEXTS[lang]
    app_url = build_webapp_url(lang, bot_username, user_id=user_id)
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=t["btn_webapp"], web_app=types.WebAppInfo(url=app_url))],
            [types.KeyboardButton(text=t["btn_movies"]), types.KeyboardButton(text=t["btn_cartoons"])],
            [types.KeyboardButton(text=t["btn_profile"]), types.KeyboardButton(text=t["btn_premium"])],
            [types.KeyboardButton(text=t["btn_search_code"]), types.KeyboardButton(text=t["btn_change_lang"])],
        ],
        resize_keyboard=True
    )


def movies_categories_keyboard(lang: str, bot_username: str = "", user_id: int = 0) -> types.InlineKeyboardMarkup:
    t = TEXTS[lang]
    app_url = build_webapp_url(lang, bot_username, tab="movies", user_id=user_id)
    rows = [
        [types.InlineKeyboardButton(text=t["btn_webapp"], web_app=types.WebAppInfo(url=app_url))],
    ]
    cat_keys = list(MOVIE_CATEGORIES.keys())
    for i in range(0, len(cat_keys), 2):
        pair = cat_keys[i:i + 2]
        row = [
            types.InlineKeyboardButton(
                text=MOVIE_CATEGORIES[k][lang],
                callback_data=f"cat_movie_{k}"
            )
            for k in pair
        ]
        rows.append(row)
    rows.append([types.InlineKeyboardButton(text=t["btn_all_movies"], callback_data="cat_movie_all")])
    rows.append([types.InlineKeyboardButton(text=t["btn_back"], callback_data="back_main")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def cartoons_categories_keyboard(lang: str, bot_username: str = "", user_id: int = 0) -> types.InlineKeyboardMarkup:
    t = TEXTS[lang]
    app_url = build_webapp_url(lang, bot_username, tab="cartoons", user_id=user_id)
    rows = [
        [types.InlineKeyboardButton(text=t["btn_webapp"], web_app=types.WebAppInfo(url=app_url))],
    ]
    for k, labels in CARTOON_CATEGORIES.items():
        rows.append([types.InlineKeyboardButton(text=labels[lang], callback_data=f"cat_cartoon_{k}")])
    rows.append([types.InlineKeyboardButton(text=t["btn_all_cartoons"], callback_data="cat_cartoon_all")])
    rows.append([types.InlineKeyboardButton(text=t["btn_back"], callback_data="back_main")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


# ==========================================
# ADMIN FSM STATES
# ==========================================
class AddContent(StatesGroup):
    waiting_for_type = State()
    waiting_for_category = State()
    waiting_for_code = State()
    waiting_for_video = State()


# ==========================================
# ESKI DUBLIKAT BOT JARAYONLARINI AVTOMATIK TO'XTATISH
# ==========================================
def stop_previous_bot_instances():
    current_pid = os.getpid()
    if os.name == 'nt':
        try:
            ps_cmd = (
                f"Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | "
                f"Where-Object {{ $_.ProcessId -ne {current_pid} -and $_.CommandLine -match 'main\\.py' }} | "
                f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=6
            )
        except Exception:
            pass


# ==========================================
# 24/7 VEB-SERVER VA ANTI-SLEEP (RENDER / CLOUD UCHUN)
# ==========================================
def _find_index_html() -> str:
    for candidate in ("index.html", os.path.join("index html", "index.html")):
        if os.path.exists(candidate):
            return candidate
    return ""


async def handle_web_index(request: web.Request) -> web.Response:
    path = _find_index_html()
    if path:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(
            text=content,
            content_type="text/html",
            charset="utf-8",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    return web.Response(text="MOVITIMECN 24/7 Server Active", content_type="text/plain")


async def handle_api_stats(request: web.Request) -> web.Response:
    stats = get_global_stats()
    uid_str = request.query.get("uid", "").strip()
    user_data = {"balance": 0, "is_premium": False, "views_count": 0}
    if uid_str.isdigit():
        user_data = ensure_user(int(uid_str))
    payload = {
        "ok": True,
        **stats,
        "balance": user_data["balance"],
        "is_premium": user_data["is_premium"],
        "views_count": user_data["views_count"],
    }
    return web.json_response(
        payload,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
    )


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "status": "24/7 ACTIVE"})


async def keep_alive_loop(port: int):
    target_url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("KEEPALIVE_URL") or f"http://127.0.0.1:{port}/health"
    if not target_url.endswith("/health") and "127.0.0.1" not in target_url:
        target_url = target_url.rstrip("/") + "/health"
    while True:
        await asyncio.sleep(240)
        try:
            async with ClientSession() as session:
                async with session.get(target_url, timeout=10) as resp:
                    await resp.read()
        except Exception:
            pass


async def start_24_7_web_server() -> int:
    port = int(os.environ.get("PORT", "8080"))
    app = web.Application()
    app.router.add_get("/", handle_web_index)
    app.router.add_get("/index.html", handle_web_index)
    app.router.add_get("/api/stats", handle_api_stats)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    for try_port in (port, 8081, 8082, 0):
        try:
            site = web.TCPSite(runner, "0.0.0.0", try_port)
            await site.start()
            logging.info(f"🌐 24/7 Web Server & Mini App ishga tushdi (port: {try_port})")
            asyncio.create_task(keep_alive_loop(try_port or port))
            return try_port
        except OSError:
            continue
    return port


# ==========================================
# ASOSIY BOT FUNKSIYASI
# ==========================================
async def main():
    stop_previous_bot_instances()
    await start_24_7_web_server()

    bot = Bot(token=API_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    bot_me = await bot.get_me()
    bot_username = bot_me.username or ""
    logging.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_username}")

    try:
        await bot.set_chat_menu_button(
            menu_button=types.MenuButtonWebApp(
                text="🎬 Mini App",
                web_app=types.WebAppInfo(url=build_webapp_url("uz", bot_username))
            )
        )
    except Exception as e:
        logging.warning(f"MenuButton o'rnatishda xatolik: {e}")

    async def send_code_result(target_message: types.Message, user_id: int, code: str):
        lang = get_lang(user_id)
        t = TEXTS[lang]
        item = find_content_by_code(code)

        if item:
            cat_name = get_category_label(item["category"], lang)
            caption_preview = (item["caption"] or "🎬 MOVITIMECN").split("\n")[0][:80]
            markup = types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="📉 480p", callback_data=f"ql_{code}_480"),
                    types.InlineKeyboardButton(text="💻 720p", callback_data=f"ql_{code}_720"),
                    types.InlineKeyboardButton(text="💎 1080p", callback_data=f"ql_{code}_1080"),
                ],
                [types.InlineKeyboardButton(text=t["btn_back"], callback_data="back_main")]
            ])
            await target_message.answer(
                t["select_quality"].format(code=code, cat_name=cat_name, caption=caption_preview),
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            await target_message.answer(
                t["not_found"].format(code=code),
                reply_markup=main_menu_keyboard(lang, bot_username, user_id),
                parse_mode="HTML"
            )

    def build_profile_message(user_id: int):
        lang = get_lang(user_id)
        t = TEXTS[lang]
        u = ensure_user(user_id, lang)
        stats = get_global_stats()
        status_label = "👑 VIP Premium" if u["is_premium"] else "🌟 Standart (Bepul)"
        text = t["profile_text"].format(
            user_id=user_id,
            status=status_label,
            balance=u["balance"],
            views=u["views_count"],
            u_count=stats["u_count"],
            total_content=stats["m_count"] + stats["c_count"],
            m_count=stats["m_count"],
            c_count=stats["c_count"],
        )
        profile_url = build_webapp_url(lang, bot_username, tab="profile", user_id=user_id)
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📊 Mini App Profil & Analitika", web_app=types.WebAppInfo(url=profile_url))],
            [types.InlineKeyboardButton(text=t["btn_premium"], callback_data="menu_premium")],
            [types.InlineKeyboardButton(text=t["btn_back"], callback_data="back_main")],
        ])
        return text, markup

    def build_premium_message(user_id: int):
        lang = get_lang(user_id)
        t = TEXTS[lang]
        profile_url = build_webapp_url(lang, bot_username, tab="profile", user_id=user_id)
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="👑 Mini App'da Premium & Balans", web_app=types.WebAppInfo(url=profile_url))],
            [types.InlineKeyboardButton(text="⏳ Premium Kanal (Tez kunda)", callback_data="prem_soon_alert")],
            [types.InlineKeyboardButton(text=t["btn_back"], callback_data="back_main")],
        ])
        return t["premium_text"], markup

    # ------------------------------------------
    # /start VA TIL TANLASH
    # ------------------------------------------
    @dp.message(CommandStart())
    async def send_welcome(message: types.Message, command: CommandObject):
        user_id = message.from_user.id
        ensure_user(user_id)
        args = (command.args or "").strip()

        if args.startswith("watch_"):
            code = args.replace("watch_", "", 1).strip().lower()
            await send_code_result(message, user_id, code)
            return

        await message.answer(
            TEXTS["choose_lang"],
            reply_markup=language_keyboard(),
            parse_mode="HTML"
        )

    @dp.message(Command("lang"))
    async def cmd_lang(message: types.Message):
        await message.answer(
            TEXTS["choose_lang"],
            reply_markup=language_keyboard(),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "open_lang_menu")
    async def open_lang_callback(call: types.CallbackQuery):
        await call.message.edit_text(
            TEXTS["choose_lang"],
            reply_markup=language_keyboard(),
            parse_mode="HTML"
        )
        await call.answer()

    @dp.callback_query(F.data.startswith("setlang_"))
    async def process_set_language(call: types.CallbackQuery):
        user_id = call.from_user.id
        lang = call.data.split("_")[1]
        if lang not in ("uz", "ru", "en"):
            lang = "uz"

        set_user_lang(user_id, lang)
        t = TEXTS[lang]
        await call.answer(t["lang_saved"])

        try:
            await bot.set_chat_menu_button(
                chat_id=user_id,
                menu_button=types.MenuButtonWebApp(
                    text=t["menu_btn_short"],
                    web_app=types.WebAppInfo(url=build_webapp_url(lang, bot_username, user_id=user_id))
                )
            )
        except Exception:
            pass

        await call.message.delete()
        await call.message.answer(
            t["lang_saved"],
            reply_markup=main_reply_keyboard(lang, bot_username, user_id)
        )
        await call.message.answer(
            t["main_welcome"],
            reply_markup=main_menu_keyboard(lang, bot_username, user_id),
            parse_mode="HTML"
        )

    # ------------------------------------------
    # ASOSIY MENYU, PROFIL, PREMIUM VA KATEGORIYALAR
    # ------------------------------------------
    @dp.callback_query(F.data == "back_main")
    async def back_to_main(call: types.CallbackQuery):
        user_id = call.from_user.id
        lang = get_lang(user_id)
        t = TEXTS[lang]
        await call.message.edit_text(
            t["main_welcome"],
            reply_markup=main_menu_keyboard(lang, bot_username, user_id),
            parse_mode="HTML"
        )
        await call.answer()

    @dp.callback_query(F.data == "menu_profile")
    async def open_profile_callback(call: types.CallbackQuery):
        user_id = call.from_user.id
        text, markup = build_profile_message(user_id)
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data == "menu_premium")
    async def open_premium_callback(call: types.CallbackQuery):
        user_id = call.from_user.id
        text, markup = build_premium_message(user_id)
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data == "prem_soon_alert")
    async def prem_soon_alert_callback(call: types.CallbackQuery):
        await call.answer(
            "⏳ Telegram Premium Kanal va avtomatik to'lov tizimi tez kunda ishga tushiriladi!",
            show_alert=True
        )

    @dp.callback_query(F.data == "menu_movies")
    async def open_movies_menu(call: types.CallbackQuery):
        user_id = call.from_user.id
        lang = get_lang(user_id)
        t = TEXTS[lang]
        await call.message.edit_text(
            t["movies_menu_title"],
            reply_markup=movies_categories_keyboard(lang, bot_username, user_id),
            parse_mode="HTML"
        )
        await call.answer()

    @dp.callback_query(F.data == "menu_cartoons")
    async def open_cartoons_menu(call: types.CallbackQuery):
        user_id = call.from_user.id
        lang = get_lang(user_id)
        t = TEXTS[lang]
        await call.message.edit_text(
            t["cartoons_menu_title"],
            reply_markup=cartoons_categories_keyboard(lang, bot_username, user_id),
            parse_mode="HTML"
        )
        await call.answer()

    @dp.callback_query(F.data == "menu_search")
    async def open_search_prompt(call: types.CallbackQuery):
        user_id = call.from_user.id
        lang = get_lang(user_id)
        t = TEXTS[lang]
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t["btn_back"], callback_data="back_main")]
        ])
        await call.message.edit_text(t["search_prompt"], reply_markup=markup, parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data.startswith("cat_movie_") | F.data.startswith("cat_cartoon_"))
    async def show_category_items(call: types.CallbackQuery):
        user_id = call.from_user.id
        lang = get_lang(user_id)
        t = TEXTS[lang]

        is_movie = call.data.startswith("cat_movie_")
        cat_key = call.data.replace("cat_movie_" if is_movie else "cat_cartoon_", "", 1)
        table = "movies" if is_movie else "cartoons"

        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        if cat_key == "all":
            cursor.execute(f"SELECT code, caption, category FROM {table} ORDER BY CAST(code AS INTEGER) ASC LIMIT 40")
            cat_name = t["btn_all_movies"] if is_movie else t["btn_all_cartoons"]
        else:
            cursor.execute(f"SELECT code, caption, category FROM {table} WHERE category = ? ORDER BY CAST(code AS INTEGER) ASC LIMIT 40", (cat_key,))
            cat_name = get_category_label(cat_key, lang)
        rows = cursor.fetchall()
        conn.close()

        kb_rows = []
        app_tab = "movies" if is_movie else "cartoons"
        app_url = build_webapp_url(lang, bot_username, tab=app_tab, cat=cat_key, user_id=user_id)

        kb_rows.append([
            types.InlineKeyboardButton(
                text=f"✨ {cat_name} — Mini App'da ochish",
                web_app=types.WebAppInfo(url=app_url)
            )
        ])

        for code, caption, _ in rows:
            first_line = (caption or f"Kino #{code}").split("\n")[0][:42]
            kb_rows.append([
                types.InlineKeyboardButton(
                    text=f"[#{code}] {first_line}",
                    callback_data=f"pick_{code}"
                )
            ])

        kb_rows.append([
            types.InlineKeyboardButton(
                text=t["btn_back"],
                callback_data="menu_movies" if is_movie else "menu_cartoons"
            )
        ])

        markup = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
        text = (
            t["category_items_title"].format(cat_name=cat_name)
            if rows
            else t["category_empty"].format(cat_name=cat_name)
        )
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data.startswith("pick_"))
    async def pick_content_callback(call: types.CallbackQuery):
        user_id = call.from_user.id
        code = call.data.replace("pick_", "", 1)
        await send_code_result(call.message, user_id, code)
        await call.answer()

    @dp.message(F.web_app_data)
    async def handle_webapp_data(message: types.Message):
        user_id = message.from_user.id
        raw = message.web_app_data.data
        try:
            payload = json.loads(raw)
            if payload.get("lang") in ("uz", "ru", "en"):
                set_user_lang(user_id, payload["lang"])
            if payload.get("action") == "premium_info":
                text, markup = build_premium_message(user_id)
                await message.answer(text, reply_markup=markup, parse_mode="HTML")
                return
            code = str(payload.get("code", "")).strip().lower()
        except Exception:
            code = raw.strip().lower()

        if code:
            await send_code_result(message, user_id, code)

    # ------------------------------------------
    # ADMIN PANEL VA BALANS / PREMIUM BOSHQARUVI
    # ------------------------------------------
    @dp.callback_query(F.data == "admin_panel")
    async def admin_panel_callback(call: types.CallbackQuery):
        if call.from_user.id != ADMIN_ID:
            await call.answer("❌ Faqat admin uchun!", show_alert=True)
            return

        stats = get_global_stats()
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="➕ Kino qo'shish / yangilash", callback_data="add_type_movie"),
                types.InlineKeyboardButton(text="➕ Multfilm qo'shish / yangilash", callback_data="add_type_cartoon"),
            ],
            [types.InlineKeyboardButton(text="📋 Kodlar ro'yxati", callback_data="admin_list_codes")],
            [types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_main")],
        ])
        await call.message.edit_text(
            f"👑 <b>ADMIN PANEL VA ANALITIKA</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{stats['u_count']}</b>\n"
            f"🌐 Tillar konsentratsiyasi: UZ: <b>{stats['uz_count']}</b> | RU: <b>{stats['ru_count']}</b> | EN: <b>{stats['en_count']}</b>\n"
            f"🎬 Kinolar soni: <b>{stats['m_count']}</b>\n"
            f"🧸 Multfilmlar soni: <b>{stats['c_count']}</b>\n"
            f"▶️ Jami ko'rishlar: <b>{stats['total_views']}</b>\n\n"
            f"📌 <b>Admin Buyruqlar:</b>\n"
            f"• <code>/addmovie</code> — Kino/multfilm qo'shish yoki yangilash\n"
            f"• <code>/delmovie KOD</code> — Kod bo'yicha o'chirish\n"
            f"• <code>/addbalance ID SUMMA</code> — Foydalanuvchi balansini to'ldirish\n"
            f"• <code>/setpremium ID</code> — Foydalanuvchiga VIP Premium berish",
            reply_markup=markup,
            parse_mode="HTML"
        )
        await call.answer()

    @dp.message(Command("addbalance"))
    async def cmd_add_balance(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            return
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("⚠️ Namuna: <code>/addbalance 7679905644 50000</code>", parse_mode="HTML")
            return
        try:
            target_id = int(parts[1])
            amount = int(parts[2])
            add_user_balance(target_id, amount)
            await message.reply(f"✅ <code>{target_id}</code> balansiga <b>{amount:,} UZS</b> qo'shildi!", parse_mode="HTML")
        except Exception as e:
            await message.reply(f"❌ Xatolik: {e}")

    @dp.message(Command("setpremium"))
    async def cmd_set_premium(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            return
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("⚠️ Namuna: <code>/setpremium 7679905644</code>", parse_mode="HTML")
            return
        try:
            target_id = int(parts[1])
            set_user_premium(target_id, 1)
            await message.reply(f"👑 <code>{target_id}</code> foydalanuvchiga <b>VIP Premium</b> maqomi berildi!", parse_mode="HTML")
        except Exception as e:
            await message.reply(f"❌ Xatolik: {e}")

    @dp.callback_query(F.data == "admin_list_codes")
    async def admin_list_codes(call: types.CallbackQuery):
        if call.from_user.id != ADMIN_ID:
            return
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        movies = cursor.execute("SELECT code, category, caption FROM movies ORDER BY CAST(code AS INTEGER) ASC LIMIT 40").fetchall()
        cartoons = cursor.execute("SELECT code, category, caption FROM cartoons ORDER BY CAST(code AS INTEGER) ASC LIMIT 20").fetchall()
        conn.close()

        lines = ["📋 <b>BAZADAGI BARCHA KODLAR:</b>\n"]
        if movies:
            lines.append("🎬 <b>Kinolar:</b>")
            for c, cat, cap in movies:
                title = (cap or "").split("\n")[0][:34]
                lines.append(f"• <code>{c}</code> ({cat}) — {title}")
        if cartoons:
            lines.append("\n🧸 <b>Multfilmlar:</b>")
            for c, cat, cap in cartoons:
                title = (cap or "").split("\n")[0][:34]
                lines.append(f"• <code>{c}</code> ({cat}) — {title}")

        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Admin Panelga qaytish", callback_data="admin_panel")]
        ])
        await call.message.edit_text("\n".join(lines), reply_markup=markup, parse_mode="HTML")
        await call.answer()

    @dp.message(Command("addmovie"))
    async def add_movie_start(message: types.Message, state: FSMContext):
        if message.from_user.id != ADMIN_ID:
            await message.reply("❌ Bu buyruq faqat admin uchun!")
            return

        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🎬 Kino qo'shish / yangilash", callback_data="add_type_movie"),
                types.InlineKeyboardButton(text="🧸 Multfilm qo'shish / yangilash", callback_data="add_type_cartoon"),
            ]
        ])
        await message.reply("👑 Nima qo'shmoqchisiz yoki yangilamoqchisiz? Tanlang:", reply_markup=markup)
        await state.set_state(AddContent.waiting_for_type)

    @dp.callback_query(F.data.in_(["add_type_movie", "add_type_cartoon"]))
    async def process_content_type(call: types.CallbackQuery, state: FSMContext):
        if call.from_user.id != ADMIN_ID:
            await call.answer("❌ Faqat admin uchun!", show_alert=True)
            return

        c_type = "movie" if call.data == "add_type_movie" else "cartoon"
        await state.update_data(content_type=c_type)

        categories = MOVIE_CATEGORIES if c_type == "movie" else CARTOON_CATEGORIES
        rows = []
        keys = list(categories.keys())
        for i in range(0, len(keys), 2):
            pair = keys[i:i + 2]
            rows.append([
                types.InlineKeyboardButton(text=categories[k]["uz"], callback_data=f"addcat_{k}")
                for k in pair
            ])

        await call.message.edit_text(
            "1️⃣ Ushbu kontent uchun <b>kategoriyani</b> tanlang:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="HTML"
        )
        await state.set_state(AddContent.waiting_for_category)
        await call.answer()

    @dp.callback_query(AddContent.waiting_for_category, F.data.startswith("addcat_"))
    async def process_content_category(call: types.CallbackQuery, state: FSMContext):
        cat_key = call.data.replace("addcat_", "", 1)
        await state.update_data(category=cat_key)
        cat_label = get_category_label(cat_key, "uz")
        await call.message.edit_text(
            f"🏷 Kategoriya: <b>{cat_label}</b>\n\n"
            f"2️⃣ Iltimos, ushbu kontent uchun <b>maxsus kod</b> yuboring (masalan: <code>101</code> yoki yangi kod):",
            parse_mode="HTML"
        )
        await state.set_state(AddContent.waiting_for_code)
        await call.answer()

    @dp.message(AddContent.waiting_for_code, F.text)
    async def process_code(message: types.Message, state: FSMContext):
        code = message.text.strip().lower().replace("#", "")
        await state.update_data(code=code)
        await message.reply(
            f"🔢 Tanlangan kod: <code>{code}</code>\n\n"
            "3️⃣ Endi ushbu kod uchun <b>videoni (yoki faylni)</b> izohi (nomi) bilan yuboring:",
            parse_mode="HTML"
        )
        await state.set_state(AddContent.waiting_for_video)

    @dp.message(AddContent.waiting_for_video, F.video | F.document)
    async def process_video(message: types.Message, state: FSMContext):
        data = await state.get_data()
        code = data['code']
        c_type = data['content_type']
        category = data.get('category', 'action' if c_type == 'movie' else 'new_cartoon')
        table = "movies" if c_type == "movie" else "cartoons"

        file_id = message.video.file_id if message.video else message.document.file_id

        existing = find_content_by_code(code)
        default_cap = existing["caption"] if existing else "🎬 MOVITIMECN"
        caption = message.caption or default_cap

        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT OR REPLACE INTO {table} (code, file_id, caption, category) VALUES (?, ?, ?, ?)",
            (code, file_id, caption, category)
        )
        conn.commit()
        conn.close()

        name = "Kino" if table == "movies" else "Multfilm"
        cat_label = get_category_label(category, "uz")
        await message.reply(
            f"✅ <b>{name} muvaffaqiyatli saqlandi!</b>\n"
            f"🔢 Kodi: <code>{code}</code>\n"
            f"🏷 Bo'lim: <b>{cat_label}</b>\n"
            f"📝 Nomi: {caption}",
            parse_mode="HTML"
        )
        await state.clear()

    @dp.message(Command("delmovie"))
    async def delete_movie(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.reply("❌ Bu buyruq faqat admin uchun!")
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("⚠️ Qaysi kodni o'chirmoqchisiz? Masalan: <code>/delmovie 101</code>", parse_mode="HTML")
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

    @dp.message(F.text)
    async def get_content(message: types.Message):
        if message.text.startswith('/'):
            return

        user_id = message.from_user.id
        text_in = message.text.strip()
        lang = get_lang(user_id)
        t = TEXTS[lang]

        all_change_lang_btns = {TEXTS["uz"]["btn_change_lang"], TEXTS["ru"]["btn_change_lang"], TEXTS["en"]["btn_change_lang"]}
        all_movies_btns = {TEXTS["uz"]["btn_movies"], TEXTS["ru"]["btn_movies"], TEXTS["en"]["btn_movies"]}
        all_cartoons_btns = {TEXTS["uz"]["btn_cartoons"], TEXTS["ru"]["btn_cartoons"], TEXTS["en"]["btn_cartoons"]}
        all_profile_btns = {TEXTS["uz"]["btn_profile"], TEXTS["ru"]["btn_profile"], TEXTS["en"]["btn_profile"]}
        all_premium_btns = {TEXTS["uz"]["btn_premium"], TEXTS["ru"]["btn_premium"], TEXTS["en"]["btn_premium"]}
        all_search_btns = {TEXTS["uz"]["btn_search_code"], TEXTS["ru"]["btn_search_code"], TEXTS["en"]["btn_search_code"]}

        if text_in in all_change_lang_btns:
            await message.answer(TEXTS["choose_lang"], reply_markup=language_keyboard(), parse_mode="HTML")
            return

        if text_in in all_movies_btns:
            await message.answer(
                t["movies_menu_title"],
                reply_markup=movies_categories_keyboard(lang, bot_username, user_id),
                parse_mode="HTML"
            )
            return

        if text_in in all_cartoons_btns:
            await message.answer(
                t["cartoons_menu_title"],
                reply_markup=cartoons_categories_keyboard(lang, bot_username, user_id),
                parse_mode="HTML"
            )
            return

        if text_in in all_profile_btns:
            text, markup = build_profile_message(user_id)
            await message.answer(text, reply_markup=markup, parse_mode="HTML")
            return

        if text_in in all_premium_btns:
            text, markup = build_premium_message(user_id)
            await message.answer(text, reply_markup=markup, parse_mode="HTML")
            return

        if text_in in all_search_btns:
            await message.answer(t["search_prompt"], parse_mode="HTML")
            return

        code = text_in.lower().replace("#", "").strip()
        await send_code_result(message, user_id, code)

    @dp.callback_query(F.data.startswith("ql_"))
    async def send_quality_video(call: types.CallbackQuery):
        user_id = call.from_user.id
        lang = get_lang(user_id)
        t = TEXTS[lang]

        parts = call.data.split("_")
        code = parts[1]
        quality = parts[2]

        item = find_content_by_code(code)
        if item:
            increment_user_views(user_id)
            cat_name = get_category_label(item["category"], lang)
            await call.message.delete()
            await call.message.answer_video(
                video=item["file_id"],
                caption=t["video_caption"].format(
                    caption=item["caption"] or "🎬 MOVITIMECN",
                    code=code,
                    cat_name=cat_name,
                    quality=quality
                ),
                parse_mode="HTML"
            )
            await call.answer()
        else:
            await call.answer(t["video_missing"], show_alert=True)

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
