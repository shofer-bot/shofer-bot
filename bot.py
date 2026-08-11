import asyncio
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
import aiohttp.web

TOKEN = "8984070226:AAEVfkbSBfaX3soWjy_kHN-FLAhBu_bqZ50"

router = Router()
DATA_DIR = "data"

FILES = {
    "admins": os.path.join(DATA_DIR, "admins.json"),
    "cars": os.path.join(DATA_DIR, "cars.json"),
    "students": os.path.join(DATA_DIR, "students.json"),
    "schedule": os.path.join(DATA_DIR, "schedule.json"),
    "history": os.path.join(DATA_DIR, "payout_history.json"),
    "reports": os.path.join(DATA_DIR, "daily_reports.json")
}

# --- ПОСТІЙНІ КЛАВІАТУРИ ВНИЗУ (REPLY) ---
def get_owner_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Додати учня"), KeyboardButton(text="👥 Учні та прогрес")],
            [KeyboardButton(text="📅 Графік занять"), KeyboardButton(text="💰 Фінанси")],
            [KeyboardButton(text="🚗 Авто та пробіг"), KeyboardButton(text="📋 Звіти інструктора")],
            [KeyboardButton(text="🩺 Медичні довідки"), KeyboardButton(text="❌ Видалити учня")]
        ],
        resize_keyboard=True
    )

def get_instructor_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Записатися на заняття"), KeyboardButton(text="📋 Розклад")],
            [KeyboardButton(text="👥 Учні та прогрес"), KeyboardButton(text="🏁 Завершити день (Звіт)")],
            [KeyboardButton(text="📋 Звіти інструктора")],
            [KeyboardButton(text="🩺 Медичні довідки")]
        ],
        resize_keyboard=True
    )

# --- ДОПОМІЖНІ ФУНКЦІЇ ДЛЯ JSON ---
def load_json(key, default):
    path = FILES[key]
    if not os.path.exists(path):
        os.makedirs(DATA_DIR, exist_ok=True)
        save_json(key, default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(key, data):
    path = FILES[key]
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def init_storage():
    load_json("admins", {"admin_ids": [454726428, 1936544706], "instructor_id": 0})
    load_json("cars", {
        "citroen": {"name": "Citroen (МКПП)", "total_mileage": 0},
        "hyundai": {"name": "Hyundai Accent (АКПП)", "total_mileage": 0}
    })
    # Перевірка наявності medical_photo у студентів
    current_students = load_json("students", [])
    updated = False
    for s in current_students:
        if "medical_photo" not in s:
            s["medical_photo"] = None
            updated = True
    if updated:
        save_json("students", current_students)

def is_admin(user_id: int) -> bool:
    data = load_json("admins", {"admin_ids": []})
    return user_id in data.get("admin_ids", [])

def is_authorized(user_id: int) -> bool:
    data = load_json("admins", {"admin_ids": [], "instructor_id": 0})
    return user_id in data.get("admin_ids", []) or user_id == data.get("instructor_id", 0)

# --- СТАНИ FSM ---
class AddStudent(StatesGroup):
    name = State()
    car_type = State()
    photo = State()

class UpdateMedicalPhoto(StatesGroup):
    student_id = State()
    photo = State()

class DailyReport(StatesGroup):
    citroen_mileage = State()
    hyundai_mileage = State()
    student_choice = State()
    hours_spent = State()
    preview = State()

class ScheduleLesson(StatesGroup):
    student_id = State()
    date = State()
    time = State()
    hours = State()

class StudentPaymentState(StatesGroup):
    student_id = State()
    hours = State()
    amount = State()
    date = State()

# --- СТАРТОВЕ МЕНЮ ---
@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.answer("❌ У вас немає доступу.")
        return
    if is_admin(user_id):
        await message.answer("Вітаю, пане власник!", reply_markup=get_owner_kb())
    else:
        await message.answer("Вітаю! Меню інструктора:", reply_markup=get_instructor_kb())

# ==========================================
# РОБОТА З МЕД. ДОВІДКАМИ
# ==========================================

@router.message(F.text == "🩺 Медичні довідки")
async def view_medical_certificates_msg(message: Message):
    if not is_authorized(message.from_user.id): return
    students = load_json("students", [])
    if not students:
        await message.answer("У системі немає учнів.")
        return

    kb_list = [[InlineKeyboardButton(text=f"{s['name']} ({'✅' if s.get('medical_photo') else '❌'})", callback_data=f"med_set_{s['id']}")] for s in students]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await message.answer("🩺 **Медичні довідки учнів:**", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("med_set_"))
async def med_set_callback(callback: CallbackQuery, state: FSMContext):
    st_id = int(callback.data.split("_")[2])
    students = load_json("students", [])
    student = next((s for s in students if s["id"] == st_id), None)
    if not student: return

    has_photo = student.get("medical_photo")
    status_text = "✅ Довідка завантажена." if has_photo else "❌ Довідка відсутня."
    
    # Кнопки
    kb_rows = [[InlineKeyboardButton(text="➕ Додати/Змінити довідку", callback_data=f"med_add_init_{st_id}")]]
    if has_photo:
        kb_rows.append([InlineKeyboardButton(text="👀 Переглянути довідку", callback_data=f"med_view_{st_id}")])
        kb_rows.append([InlineKeyboardButton(text="🗑 Видалити довідку", callback_data=f"med_del_{st_id}")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад до списку", callback_data="med_back_to_list")])
    
    await callback.message.edit_text(f"👤 **{student['name']}**\nСтатус: {status_text}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("med_add_init_"))
async def med_add_init_callback(callback: CallbackQuery, state: FSMContext):
    st_id = int(callback.data.split("_")[3])
    await state.update_data(student_id=st_id)
    await state.set_state(UpdateMedicalPhoto.photo)
    await callback.message.edit_text("📸 Надішліть фото довідки (або натисніть Скасувати):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Скасувати", callback_data="med_cancel")]]))
    await callback.answer()

@router.callback_query(F.data == "med_back_to_list")
async def med_back_to_list(callback: CallbackQuery):
    await view_medical_certificates_msg(callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith("med_view_"))
async def med_view_callback(callback: CallbackQuery):
    st_id = int(callback.data.split("_")[2])
    students = load_json("students", [])
    student = next((s for s in students if s["id"] == st_id), None)
    if student and student.get("medical_photo"):
        await callback.message.answer_photo(photo=student["medical_photo"], caption=f"Довідка: {student['name']}")
    await callback.answer()

@router.callback_query(F.data.startswith("med_del_"))
async def med_del_callback(callback: CallbackQuery, state: FSMContext):
    st_id = int(callback.data.split("_")[2])
    students = load_json("students", [])
    for s in students:
        if s["id"] == st_id: s["medical_photo"] = None
    save_json("students", students)
    await callback.message.edit_text("🗑 Довідку видалено.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="med_back_to_list")]]))
    await callback.answer()

@router.message(UpdateMedicalPhoto.photo, F.photo)
async def process_new_medical_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    st_id = data.get("student_id")
    students = load_json("students", [])
    for s in students:
        if s["id"] == st_id: s["medical_photo"] = message.photo[-1].file_id
    save_json("students", students)
    await message.answer("✅ Довідку оновлено!", reply_markup=get_owner_kb() if is_admin(message.from_user.id) else get_instructor_kb())
    await state.clear()

@router.callback_query(F.data == "med_cancel")
async def med_cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await med_back_to_list(callback)

# ==========================================
# ІНШІ ФУНКЦІЇ (ОСНОВА)
# ==========================================

@router.message(F.text == "➕ Додати учня")
async def process_add_student_btn(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("Введіть ПІБ нового учня:")
    await state.set_state(AddStudent.name)

@router.message(AddStudent.name)
async def process_student_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Citroen (МКПП)", callback_data="car_citroen")],
        [InlineKeyboardButton(text="Hyundai (АКПП)", callback_data="car_hyundai")]
    ])
    await message.answer("Оберіть авто:", reply_markup=kb)
    await state.set_state(AddStudent.car_type)

@router.callback_query(AddStudent.car_type, F.data.startswith("car_"))
async def process_student_car(callback: CallbackQuery, state: FSMContext):
    car_key = callback.data.split("_")[1]
    data = await state.get_data()
    students = load_json("students", [])
    students.append({
        "id": len(students) + 1,
        "name": data["name"],
        "car_type": car_key,
        "total_hours": 40,
        "spent_hours": 0,
        "paid_hours": 0,
        "school_payments": [],
        "medical_photo": None
    })
    save_json("students", students)
    await callback.message.answer("✅ Учня додано!")
    await state.clear()
    await callback.answer()

@router.message(F.text == "❌ Видалити учня")
async def process_delete_student_btn(message: Message):
    if not is_admin(message.from_user.id): return
    students = load_json("students", [])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🗑 {s['name']}", callback_data=f"del_st_{s['id']}")] for s in students])
    await message.answer("Оберіть учня для видалення:", reply_markup=kb)

@router.callback_query(F.data.startswith("del_st_"))
async def process_delete_student_callback(callback: CallbackQuery):
    st_id = int(callback.data.split("_")[2])
    students = [s for s in load_json("students", []) if s["id"] != st_id]
    save_json("students", students)
    await callback.message.edit_text("✅ Учня видалено.")
    await callback.answer()

# --- Вебсервер для Render ---
async def handle(request): return aiohttp.web.Response(text="Bot is running!")

async def web_server():
    app = aiohttp.web.Application()
    app.router.add_get("/", handle)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    await aiohttp.web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()

async def main():
    init_storage()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    asyncio.create_task(web_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())