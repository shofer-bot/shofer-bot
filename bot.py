import os
import sqlite3
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

# Ініціалізація бази даних SQLite
def init_db():
    conn = sqlite3.connect('shofer_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_number TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            photo_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Описуємо стани для покрокового додавання учня (FSM)
class AddStudent(StatesGroup):
    waiting_for_group = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_photo = State()

router = Router()

# 1. Натиснули кнопку "додати учня"
@router.message(F.text.casefold() == "додати учня")
async def cmd_add_student(message: Message, state: FSMContext):
    await state.set_state(AddStudent.waiting_for_group)
    await message.answer(
        "📝 Введіть **номер групи** (лише цифри):",
        parse_mode="Markdown"
    )

# 2. Отримуємо номер групи
@router.message(AddStudent.waiting_for_group)
async def process_group(message: Message, state: FSMContext):
    group_number = message.text.strip()
    
    if not group_number.isdigit():
        await message.answer("❌ Номер групи повинен складатися **лише з цифр**. Спробуйте ще раз:", parse_mode="Markdown")
        return

    await state.update_data(group_number=group_number)
    await state.set_state(AddStudent.waiting_for_name)
    await message.answer("👤 Тепер введіть **ПІБ учня** (Прізвище Ім'я По батькові):", parse_mode="Markdown")

# 3. Отримуємо ПІБ
@router.message(AddStudent.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    await state.update_data(full_name=full_name)
    await state.set_state(AddStudent.waiting_for_phone)
    await message.answer("📱 Введіть **номер телефону** учня:", parse_mode="Markdown")

# 4. Отримуємо телефон
@router.message(AddStudent.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)
    await state.set_state(AddStudent.waiting_for_photo)
    await message.answer("📷 Надішліть **фото медичної довідки** (або напишіть будь-який текст, якщо фото немає):", parse_mode="Markdown")

# Внутрішня функція збереження учня в базу даних
async def save_student_to_db(message: Message, state: FSMContext, photo_id: str):
    data = await state.get_data()
    group_number = data.get("group_number")
    full_name = data.get("full_name")
    phone = data.get("phone")

    conn = sqlite3.connect('shofer_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO students (group_number, full_name, phone, photo_id) VALUES (?, ?, ?, ?)",
        (group_number, full_name, phone, photo_id)
    )
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        f"✅ **Учня успішно додано!**\n\n"
        f"📌 Група: {group_number}\n"
        f"👤 ПІБ: {full_name}\n"
        f"📱 Телефон: {phone}\n"
        f"📷 Меддовідка: {'Додано' if photo_id else 'Немає'}",
        parse_mode="Markdown"
    )

# 5. Отримуємо фото довідки
@router.message(AddStudent.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await save_student_to_db(message, state, photo_id)

# Якщо замість фото надіслали текст (пропуск)
@router.message(AddStudent.waiting_for_photo, F.text)
async def process_no_photo(message: Message, state: FSMContext):
    photo_id = None
    await save_student_to_db(message, state, photo_id)

# 6. Відображення розділу "Учні та прогрес" з сортуванням за групами та порядком додавання
@router.message(F.text.casefold() == "учні та прогрес")
async def show_students_progress(message: Message):
    conn = sqlite3.connect('shofer_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT group_number, full_name, phone, photo_id FROM students ORDER BY group_number, id ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("📭 Список учнів наразі порожній.")
        return

    groups = {}
    for group_num, full_name, phone, photo_id in rows:
        if group_num not in groups:
            groups[group_num] = []
        groups[group_num].append((full_name, phone, photo_id))

    response = "📋 **Список учнів за групами:**\n"
    for group_num, students in groups.items():
        response += f"\n📌 **Група № {group_num}:**\n"
        for idx, (name, phone, photo_id) in enumerate(students, start=1):
            med_status = "🟢 є довідка" if photo_id else "🔴 немає довідки"
            response += f"{idx}. {name} | Тел: {phone} | {med_status}\n"

    await message.answer(response, parse_mode="Markdown")

# Веб-сервер для утримання сервісу активним на Render
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# Головна точка запуску
async def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        print("Помилка: не знайдено змінну середовища BOT_TOKEN!")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(router)

    # Запускаємо веб-сервер
    await start_web_server()
    print("Бот автошколи «Шофер» успішно запущено...")

    # Запускаємо поллінг
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())