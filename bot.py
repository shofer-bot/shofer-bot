[cite: 5]import asyncio
import json
import os
import io
import csv
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
import aiohttp.web

# Токен береться із змінних середовища для безпеки та коректної роботи на Render.com
TOKEN = os.getenv("BOT_TOKEN")

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

# --- КЛАВІАТУРИ ---
def get_owner_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Додати учня"), KeyboardButton(text="👥 Учні та прогрес")],
            [KeyboardButton(text="📅 Графік занять"), KeyboardButton(text="💰 Фінанси")],
            [KeyboardButton(text="🚗 Авто та пробіг"), KeyboardButton(text="📋 Звіти інструктора")],
            [KeyboardButton(text="🩺 Медичні довідки"), KeyboardButton(text="❌ Видалити учня")],
            [KeyboardButton(text="📥 Вивантажити звіт в Excel")]
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

def get_student_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Мій прогрес")],
            [KeyboardButton(text="🔗 Зв'язати профіль")]
        ],
        resize_keyboard=True
    )

# --- ДОПОМІЖНІ ФУНКЦІЇ ДЛЯ JSON ТА ДОСТУПУ ---
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
    load_json("admins", {
        "admin_ids": [454726428, 1936544706], 
        "instructor_id": 0
    })
    load_json("cars", {
        "citroen": {"name": "Citroen (МКПП)", "total_mileage": 0},
        "hyundai": {"name": "Hyundai Accent (АКПП)", "total_mileage": 0}
    })
    
    initial_students = [
        {"id": 1, "name": "Грановський Даніїл Костянтинович", "car_type": "citroen", "total_hours": 40, "spent_hours": 22, "paid_hours": 22, "school_payments": [{"hours": 22, "amount": 22 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None},
        {"id": 2, "name": "Гаібова Вероніка Хуршедівна", "car_type": "citroen", "total_hours": 40, "spent_hours": 26, "paid_hours": 26, "school_payments": [{"hours": 26, "amount": 26 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None},
        {"id": 3, "name": "Криворот Єгор Олександрович", "car_type": "citroen", "total_hours": 40, "spent_hours": 16, "paid_hours": 16, "school_payments": [{"hours": 16, "amount": 16 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None},
        {"id": 4, "name": "Мосейчук Єлізавета Вадимівна", "car_type": "citroen", "total_hours": 40, "spent_hours": 6, "paid_hours": 6, "school_payments": [{"hours": 6, "amount": 6 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None},
        {"id": 5, "name": "Абрамова Анна Леонідівна", "car_type": "citroen", "total_hours": 40, "spent_hours": 4, "paid_hours": 4, "school_payments": [{"hours": 4, "amount": 4 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None},
        {"id": 6, "name": "Подплетньов Олексій Васильович", "car_type": "citroen", "total_hours": 40, "spent_hours": 36, "paid_hours": 36, "school_payments": [{"hours": 36, "amount": 36 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None},
        {"id": 7, "name": "Зіміна Аріна Володимирівна", "car_type": "hyundai", "total_hours": 40, "spent_hours": 28, "paid_hours": 28, "school_payments": [{"hours": 28, "amount": 28 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None},
        {"id": 8, "name": "Алексеєва Марія Владиславівна", "car_type": "hyundai", "total_hours": 40, "spent_hours": 32, "paid_hours": 32, "school_payments": [{"hours": 32, "amount": 32 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None},
        {"id": 9, "name": "Брьохова Софія Олександрівна", "car_type": "hyundai", "total_hours": 40, "spent_hours": 26, "paid_hours": 26, "school_payments": [{"hours": 26, "amount": 26 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None},
        {"id": 10, "name": "Кардаш Станіслав Анатолійович", "car_type": "hyundai", "total_hours": 40, "spent_hours": 18, "paid_hours": 18, "school_payments": [{"hours": 18, "amount": 18 * 900, "date": "01.08.2026"}], "rate_type": "old", "medical_photo": None, "telegram_id": None}
    ]
    
    path = FILES["students"]
    if not os.path.exists(path):
        save_json("students", initial_students)
    else:
        current = load_json("students", [])
        if not current:
            save_json("students", initial_students)
        else:
            updated = False
            for s in current:
                if "medical_photo" not in s:
                    s["medical_photo"] = None
                    updated = True
                if "telegram_id" not in s:
                    s["telegram_id"] = None
                    updated = True
            if updated:
                save_json("students", current)

    history_path = FILES["history"]
    if not os.path.exists(history_path):
        initial_history = [{
            "date": "2026-08-01 12:00",
            "hours_paid": 214,
            "instructor_amount": 214 * 450
        }]
        save_json("history", initial_history)

    load_json("schedule", [])
    load_json("reports", [])

def load_admins_data():
    return load_json("admins", {"admin_ids": [454726428, 1936544706], "instructor_id": 0})

def is_admin(user_id: int) -> bool:
    data = load_admins_data()
    return user_id in data.get("admin_ids", [])

def is_instructor(user_id: int) -> bool:
    data = load_admins_data()
    return user_id == data.get("instructor_id", 0)

def get_student_by_telegram(user_id: int):
    students = load_json("students", [])
    for s in students:
        if s.get("telegram_id") == user_id:
            return s
    return None

def is_student(user_id: int) -> bool:
    return get_student_by_telegram(user_id) is not None

def is_authorized(user_id: int) -> bool:
    data = load_admins_data()
    return user_id in data.get("admin_ids", []) or user_id == data.get("instructor_id", 0) or is_student(user_id)

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
    
    if is_admin(user_id):
        await message.answer("Вітаю, пане власник! Оберіть потрібну дію на панелі внизу:", reply_markup=get_owner_kb())
    elif is_instructor(user_id):
        await message.answer("Вітаю! Меню інструктора автошколи «Шофер»:", reply_markup=get_instructor_kb())
    elif is_student(user_id):
        student = get_student_by_telegram(user_id)
        await message.answer(f"Вітаю, {student['name']}! Це ваш кабінет учня в автошколі «Шофер».", reply_markup=get_student_kb())
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Зв'язати профіль учня", callback_data="link_student_start")]
        ])
        await message.answer(
            f"❌ Ваш Telegram ID: `{user_id}` не знайдено серед адміністраторів чи інструкторів.\n\n"
            f"Якщо ви учень нашої автошколи, натисніть кнопку нижче, щоб прив'язати свій акаунт:",
            reply_markup=kb,
            parse_mode="Markdown"
        )

# ==========================================
# МІНІ-КАБІНЕТ УЧНЯ ТА ЗВ'ЯЗУВАННЯ
# ==========================================
@router.callback_query(F.data == "link_student_start")
async def link_student_start_callback(callback: CallbackQuery):
    students = load_json("students", [])
    unlinked = [s for s in students if not s.get("telegram_id")]
    
    if not unlinked:
        await callback.message.answer("Усі учні в системі вже мають прив'язані акаунти, або список порожній.")
        await callback.answer()
        return

    kb_list = [[InlineKeyboardButton(text=f"{s['name']} ({s['car_type'].upper()})", callback_data=f"link_st_id_{s['id']}")] for s in unlinked]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await callback.message.answer("Оберіть ваше прізвище зі списку для зв'язування акаунта:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("link_st_id_"))
async def link_student_finish_callback(callback: CallbackQuery):
    st_id = int(callback.data.split("_")[3])
    user_id = callback.from_user.id

    students = load_json("students", [])
    student_name = ""
    for s in students:
        if s["id"] == st_id:
            s["telegram_id"] = user_id
            student_name = s["name"]
            break
    save_json("students", students)

    await callback.message.edit_text(f"✅ Профіль успішно зв'язано з учнем: **{student_name}**!", parse_mode="Markdown")
    await callback.message.answer("Оберіть дію у вашому кабінеті:", reply_markup=get_student_kb())
    await callback.answer()

@router.message(F.text.func(lambda t: t and "Зв'язати профіль" in t))
async def link_profile_btn(message: Message):
    user_id = message.from_user.id
    if is_student(user_id):
        student = get_student_by_telegram(user_id)
        await message.answer(f"Ваш акаунт уже зв'язано з учнем: **{student['name']}**.", parse_mode="Markdown", reply_markup=get_student_kb())
        return
    
    students = load_json("students", [])
    unlinked = [s for s in students if not s.get("telegram_id")]
    if not unlinked:
        await message.answer("Немає вільних учнів для зв'язування.")
        return

    kb_list = [[InlineKeyboardButton(text=f"{s['name']} ({s['car_type'].upper()})", callback_data=f"link_st_id_{s['id']}")] for s in unlinked]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await message.answer("Оберіть ваше прізвище зі списку для зв'язування акаунта:", reply_markup=kb)

@router.message(F.text.func(lambda t: t and "Мій прогрес" in t))
async def student_my_progress(message: Message):
    user_id = message.from_user.id
    student = get_student_by_telegram(user_id)
    if not student:
        await message.answer("❌ Ваш акаунт не прив'язаний до жодного учня. Натисніть «Зв'язати профіль».", reply_markup=get_student_kb())
        return

    total = student.get("total_hours", 40)
    spent = student.get("spent_hours", 0)
    left = total - spent
    car_lbl = "Citroen (МКПП)" if student["car_type"] == "citroen" else "Hyundai Accent (АКПП)"
    med_status = "✅ Завантажена" if student.get("medical_photo") else "❌ Відсутня"

    msg = (
        f"📊 **ВАШ ПРОГРЕС НАВЧАННЯ**\n\n"
        f"👤 ПІБ: **{student['name']}**\n"
        f"🚗 Автомобіль: {car_lbl}\n\n"
        f"⏱ Всього годин за курсом: **{total} год**\n"
        f"🚙 Від'їздено годин: **{spent} год**\n"
        f"⏳ Залишилось годин: **{left} год**\n\n"
        f"🩺 Медична довідка: {med_status}"
    )
    await message.answer(msg, parse_mode="Markdown", reply_markup=get_student_kb())

# ==========================================
# ЕКСПОРТ ДАНИХ У EXCEL (CSV)
# ==========================================
@router.message(F.text.func(lambda t: t and "Вивантажити звіт в Excel" in t))
async def export_excel_report(message: Message):
    if not is_authorized(message.from_user.id) or not is_admin(message.from_user.id):
        await message.answer("❌ Ця функція доступна лише власнику.")
        return

    students = load_json("students", [])
    if not students:
        await message.answer("У системі немає даних про учнів для експорту.")
        return

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    
    writer.writerow(["ID", "ПІБ учня", "Авто", "Всього годин", "Від'їздено годин", "Оплачено годин", "Медична довідка"])
    
    for s in students:
        car_lbl = "Citroen (МКПП)" if s["car_type"] == "citroen" else "Hyundai Accent (АКПП)"
        med_status = "Є довідка" if s.get("medical_photo") else "Немає"
        writer.writerow([
            s["id"],
            s["name"],
            car_lbl,
            s["total_hours"],
            s["spent_hours"],
            s["paid_hours"],
            med_status
        ])

    csv_data = output.getvalue().encode('utf-8-sig')
    output.close()

    file = BufferedInputFile(csv_data, filename=f"students_report_{datetime.now().strftime('%Y-%m-%d')}.csv")
    await message.answer_document(
        file, 
        caption="📊 **Ось звіт по учнях та їхньому прогресу у форматі CSV** (можна вільно відкривати в Microsoft Excel або Google Таблицях).",
        parse_mode="Markdown"
    )

# ==========================================
# ДОДАВАННЯ ТА РОБОТА З МЕД. ДОВІДКАМИ
# ==========================================
@router.message(F.text.func(lambda t: t and "Додати учня" in t))
async def process_add_student_btn(message: Message, state: FSMContext):
    if not is_authorized(message.from_user.id) or not is_admin(message.from_user.id):
        await message.answer("❌ Недостатньо прав. Ця функція лише для власників.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add_student")]
    ])
    
    await message.answer(
        "Введіть ПІБ нового учня:\n*(або натисніть кнопку скасування нижче)*", 
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await state.set_state(AddStudent.name)

@router.callback_query(F.data == "cancel_add_student")
async def cancel_add_student_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    if is_admin(user_id):
        kb = get_owner_kb()
    elif is_instructor(user_id):
        kb = get_instructor_kb()
    else:
        kb = get_student_kb()
    try:
        await callback.message.edit_text("❌ Додавання учня скасовано.")
    except Exception:
        pass
    await callback.message.answer("Оберіть дію на панелі:", reply_markup=kb)
    await callback.answer()

@router.message(AddStudent.name)
async def process_student_name(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text in ["скасувати", "відміна", "назад", "exit"]:
        await state.clear()
        user_id = message.from_user.id
        kb = get_owner_kb() if is_admin(user_id) else (get_instructor_kb() if is_instructor(user_id) else get_student_kb())
        await message.answer("❌ Додавання учня скасовано.", reply_markup=kb)
        return

    await state.update_data(name=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Citroen (Механіка)", callback_data="car_citroen")],
        [InlineKeyboardButton(text="Hyundai Accent (Автомат)", callback_data="car_hyundai")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add_student")]
    ])
    await message.answer(
        "Оберіть авто (тип коробки передач) для учня (40 годин курсу):\n*(Тариф: 900 грн/год)*", 
        reply_markup=kb, 
        parse_mode="Markdown"
    )
    await state.set_state(AddStudent.car_type)

@router.callback_query(AddStudent.car_type, F.data.startswith("car_"))
async def process_student_car(callback: CallbackQuery, state: FSMContext):
    car_key = callback.data.split("_")[1]
    await state.update_data(car_type=car_key)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add_student")]
    ])
    
    await callback.message.edit_text(
        "🩺 **Медична довідка:**\n"
        "Надішліть фото медичної довідки учня (або зробіть фото та надішліть у чат).\n"
        "*(Якщо довідки немає зараз, напишіть `пропустити` або натисніть кнопку скасування)*",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await state.set_state(AddStudent.photo)
    await callback.answer()

@router.message(AddStudent.photo, F.photo)
async def process_student_photo_file(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await save_new_student_to_db(message, state, medical_photo=photo_file_id)

@router.message(AddStudent.photo, F.text)
async def process_student_photo_text(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text in ["скасувати", "відміна", "назад", "exit"]:
        await state.clear()
        user_id = message.from_user.id
        kb = get_owner_kb() if is_admin(user_id) else (get_instructor_kb() if is_instructor(user_id) else get_student_kb())
        await message.answer("❌ Додавання учня скасовано.", reply_markup=kb)
        return
    await save_new_student_to_db(message, state, medical_photo=None)

async def save_new_student_to_db(message: Message, state: FSMContext, medical_photo: str = None):
    data = await state.get_data()
    name = data["name"]
    car_key = data["car_type"]

    students = load_json("students", [])
    new_student = {
        "id": len(students) + 1,
        "name": name,
        "car_type": car_key,
        "total_hours": 40,
        "spent_hours": 0,
        "paid_hours": 0,
        "school_payments": [],
        "rate_type": "new",
        "medical_photo": medical_photo,
        "telegram_id": None
    }
    students.append(new_student)
    save_json("students", students)

    car_name = "Citroen (МКПП)" if car_key == "citroen" else "Hyundai Accent (АКПП)"
    user_id = message.from_user.id
    kb = get_owner_kb() if is_admin(user_id) else (get_instructor_kb() if is_instructor(user_id) else get_student_kb())
    
    photo_status = "✅ Збережено" if medical_photo else "❌ Не додано"
    await message.answer(
        f"✅ Учня успішно додано (тариф 900 грн/год)!\n\n"
        f"ПІБ: {name}\n"
        f"Авто: {car_name}\n"
        f"Баланс: 40 годин\n"
        f"Медична довідка: {photo_status}",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await state.clear()

@router.message(F.text.func(lambda t: t and "Медичні довідки" in t))
async def view_medical_certificates_msg(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("❌ Недостатньо прав.")
        return
    students = load_json("students", [])
    if not students:
        await message.answer("У системі немає учнів.")
        return

    kb_list = []
    for s in students:
        status = "✅ Є" if s.get("medical_photo") else "❌ Немає"
        car_lbl = "Citroen" if s["car_type"] == "citroen" else "Hyundai"
        kb_list.append([InlineKeyboardButton(text=f"{s['name']} ({car_lbl}) — [{status}]", callback_data=f"med_set_{s['id']}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await message.answer(
        "🩺 **МЕДИЧНІ ДОВІДКИ УЧНІВ**\n\n"
        "Оберіть учня нижче, щоб додати, переглянути чи видалити довідку:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("med_set_"))
async def med_set_callback(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Недостатньо прав", show_alert=True)
        return
    st_id = int(callback.data.split("_")[2])
    students = load_json("students", [])
    student = next((s for s in students if s["id"] == st_id), None)
    if not student:
        await callback.answer("Учня не знайдено.", show_alert=True)
        return

    await state.update_data(student_id=st_id)
    
    has_photo = student.get("medical_photo")
    status_text = "✅ Завантажена" if has_photo else "❌ Відсутня"
    text = f"👤 Учень: **{student['name']}**\nМедична довідка: {status_text}\n\nОберіть потрібну дію:"
    
    kb_rows = [
        [InlineKeyboardButton(text="➕ Додати / Змінити довідку", callback_data=f"med_add_init_{st_id}")]
    ]
    
    if has_photo:
        kb_rows.append([InlineKeyboardButton(text="👀 Переглянути довідку", callback_data=f"med_view_{st_id}")])
        kb_rows.append([InlineKeyboardButton(text="🗑 Видалити довідку", callback_data=f"med_del_{st_id}")])
    
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад до списку", callback_data="med_back_to_list")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("med_add_init_"))
async def med_add_init_callback(callback: CallbackQuery, state: FSMContext):
    st_id = int(callback.data.split("_")[3])
    await state.update_data(student_id=st_id)
    await state.set_state(UpdateMedicalPhoto.photo)
    await callback.message.edit_text(
        "📸 **Надішліть нове фото медичної довідки** у цей чат.\n\n"
        "Або натисніть кнопку нижче для скасування.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="med_cancel")]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "med_back_to_list")
async def med_back_to_list(callback: CallbackQuery):
    await view_medical_certificates_msg(callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith("med_view_"))
async def med_view_callback(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id): return
    st_id = int(callback.data.split("_")[2])
    students = load_json("students", [])
    student = next((s for s in students if s["id"] == st_id), None)
    if student and student.get("medical_photo"):
        car_lbl = "Citroen (МКПП)" if student["car_type"] == "citroen" else "Hyundai Accent (АКПП)"
        try:
            await callback.message.answer_photo(
                photo=student["medical_photo"], 
                caption=f"🩺 Медична довідка учня: **{student['name']}** ({car_lbl})", 
                parse_mode="Markdown"
            )
        except Exception:
            await callback.message.answer("Не вдалося завантажити фото довідки.")
    await callback.answer()

@router.callback_query(F.data.startswith("med_del_"))
async def med_del_callback(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Недостатньо прав", show_alert=True)
        return
    st_id = int(callback.data.split("_")[2])
    students = load_json("students", [])
    student_name = "Учень"
    for s in students:
        if s["id"] == st_id:
            s["medical_photo"] = None
            student_name = s["name"]
            break
    save_json("students", students)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад до списку", callback_data="med_back_to_list")]
    ])

    await callback.message.edit_text(f"🗑 Медичну довідку для учня **{student_name}** успішно видалено.", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "med_cancel")
async def med_cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Операцію з довідкою скасовано.")
    await med_back_to_list(callback)

@router.message(UpdateMedicalPhoto.photo, F.photo)
async def process_new_medical_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    st_id = data.get("student_id")
    photo_file_id = message.photo[-1].file_id

    students = load_json("students", [])
    student_name = "Учень"
    for s in students:
        if s["id"] == st_id:
            s["medical_photo"] = photo_file_id
            student_name = s["name"]
            break
    save_json("students", students)

    user_id = message.from_user.id
    kb = get_owner_kb() if is_admin(user_id) else (get_instructor_kb() if is_instructor(user_id) else get_student_kb())

    await message.answer(
        f"✅ Медичну довідку для учня **{student_name}** успішно збережено/оновлено!",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await state.clear()

@router.message(UpdateMedicalPhoto.photo, F.text)
async def process_new_medical_photo_text(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text in ["скасувати", "відміна", "назад", "exit"]:
        await state.clear()
        user_id = message.from_user.id
        kb = get_owner_kb() if is_admin(user_id) else (get_instructor_kb() if is_instructor(user_id) else get_student_kb())
        await message.answer("❌ Оновлення довідки скасовано.", reply_markup=kb)
    else:
        await message.answer("Будь ласка, надішліть **фотографію** медичної довідки або натисніть кнопку скасування.")

# ==========================================
# ІНШІ ФУНКЦІЇ БОТА (ВИДАЛЕННЯ, УЧНІ, ІНШЕ)
# ==========================================
@router.message(F.text.func(lambda t: t and "Видалити учня" in t))
async def process_delete_student_btn(message: Message):
    if not is_authorized(message.from_user.id) or not is_admin(message.from_user.id):
        await message.answer("❌ Недостатньо прав. Ця функція лише для власників.")
        return
        
    students = load_json("students", [])
    if not students:
        await message.answer("У системі немає учнів для видалення.")
        return

    kb_list = [[InlineKeyboardButton(text=f"🗑 {s['name']} ({s['car_type'].upper()})", callback_data=f"del_st_{s['id']}")] for s in students]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await message.answer("⚠️ Оберіть учня, якого хочете НАЗАВЖДИ видалити з бази:", reply_markup=kb)

@router.callback_query(F.data.startswith("del_st_"))
async def process_delete_student_callback(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id) or not is_admin(callback.from_user.id):
        await callback.answer("Недостатньо прав!", show_alert=True)
        return

    st_id = int(callback.data.split("_")[2])
    students = load_json("students", [])
    schedule = load_json("schedule", [])
    
    student_name = "Невідомий учень"
    for s in students:
        if s["id"] == st_id:
            student_name = s["name"]
            break

    students = [s for s in students if s["id"] != st_id]
    save_json("students", students)

    schedule = [item for item in schedule if item["student_id"] != st_id]
    save_json("schedule", schedule)

    await callback.message.edit_text(f"✅ Учня **{student_name}** та всі його заплановані заняття успішно видалено з бази.", parse_mode="Markdown")
    await callback.answer()

@router.message(F.text.func(lambda t: t and "Учні та прогрес" in t))
async def view_students_list_msg(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("❌ Недостатньо прав.")
        return
    students = load_json("students", [])
    if not students:
        await message.answer("У системі поки немає жодного учня.")
        return

    citroen_students = [s for s in students if s["car_type"] == "citroen"]
    hyundai_students = [s for s in students if s["car_type"] == "hyundai"]

    msg = "👥 **СПИСОК УЧНІВ ТА ЇХ ПРОГРЕС**\n\n"

    def fmt(val):
        try:
            f = float(val)
            if f.is_integer():
                return str(int(f))
        except Exception:
            pass
        return str(val)

    msg += "🚗 **Citroen (МКПП):**\n"
    if citroen_students:
        for i, s in enumerate(citroen_students, 1):
            instructor_paid = s.get("paid_hours", 0)
            student_paid_hours = sum(p.get("hours", 0) for p in s.get("school_payments", []))
            med_status = "✅ Є довідка" if s.get("medical_photo") else "❌ Немає довідки"
            msg += (
                f"{i}. **{s['name']}**\n"
                f"Від'їздив: {fmt(s['spent_hours'])} з {fmt(s['total_hours'])} год | "
                f"Оплачено занять учнем: {fmt(student_paid_hours)} год | "
                f"Оплачено інструктору: {fmt(instructor_paid)} год | "
                f"Медична довідка: {med_status}\n\n"
            )
    else:
        msg += "• Немає учнів\n\n"

    msg += "🚙 **Hyundai Accent (АКПП):**\n"
    if hyundai_students:
        for i, s in enumerate(hyundai_students, 1):
            instructor_paid = s.get("paid_hours", 0)
            student_paid_hours = sum(p.get("hours", 0) for p in s.get("school_payments", []))
            med_status = "✅ Є довідка" if s.get("medical_photo") else "❌ Немає довідки"
            msg += (
                f"{i}. **{s['name']}**\n"
                f"Від'їздив: {fmt(s['spent_hours'])} з {fmt(s['total_hours'])} год | "
                f"Оплачено занять учнем: {fmt(student_paid_hours)} год | "
                f"Оплачено інструктору: {fmt(instructor_paid)} год | "
                f"Медична довідка: {med_status}\n\n"
            )
    else:
        msg += "• Немає учнів\n"

    await message.answer(msg, parse_mode="Markdown")

@router.message(F.text.func(lambda t: t and "Графік занять" in t))
async def view_schedule_admin_msg(message: Message):
    if not is_authorized(message.from_user.id) or not is_admin(message.from_user.id):
        await message.answer("❌ Ця функція доступна лише власнику.")
        return

    schedule = load_json("schedule", [])
    if not schedule:
        await message.answer("📅 Наразі немає запланованих занять у графіку автошколи.")
        return

    msg = "📅 **ГРАФІК ЗАНЯТЬ АВТОШКОЛИ «ШОФЕР»:**\n\n"
    for item in schedule:
        car_lbl = "Citroen (МКПП)" if item["car_type"] == "citroen" else "Hyundai Accent (АКПП)"
        hours = item.get("hours", 1.0)
        msg += f"• **{item['date']} о {item['time']}** ({hours} год)\n  - Учень: {item['student_name']} | Авто: {car_lbl}\n\n"

    await message.answer(msg, parse_mode="Markdown")

@router.message(F.text.func(lambda t: t and "Авто та пробіг" in t))
async def view_cars_msg(message: Message):
    if not is_authorized(message.from_user.id) or not is_admin(message.from_user.id):
        await message.answer("❌ Ця функція доступна лише власнику.")
        return
    cars = load_json("cars", {})
    msg = "🚗 **Стан автопарку:**\n\n"
    for key, val in cars.items():
        msg += f"- {val['name']}: **{val['total_mileage']} км**\n"
    await message.answer(msg, parse_mode="Markdown")

@router.message(F.text.func(lambda t: t and "Звіти інструктора" in t))
async def view_instructor_reports_msg(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("❌ Недостатньо прав.")
        return
    reports = load_json("reports", [])
    if not reports:
        await message.answer("📋 Архів звітів інструктора наразі порожній.")
        return

    msg = "📋 **АРХІВ ЩОДЕННИХ ЗВІТІВ ІНСТРУКТОРА:**\n\n"
    for i, rep in enumerate(reports[-10:], 1):
        msg += f"📌 **Звіт #{i} від {rep['date']}**\n{rep['text']}\n\n"

    if len(msg) > 4000:
        await message.answer("📋 Звітів занадто багато, ось останні п'ять:")
        for rep in reports[-5:]:
            await message.answer(f"📌 **Звіт від {rep['date']}**:\n\n{rep['text']}", parse_mode="Markdown")
    else:
        await message.answer(msg, parse_mode="Markdown")

# ==========================================
# ФІНАНСИ ТА ОПЛАТИ
# ==========================================
def calculate_financials():
    students = load_json("students", [])
    
    unpaid_hours = 0
    unpaid_instructor = 0
    unpaid_father_citroen = 0
    unpaid_user_hyundai = 0
    unpaid_father_org = 0

    total_spent_hours = 0
    total_gross_income = 0
    total_instructor_pay = 0
    total_father_citroen = 0
    total_user_hyundai = 0
    total_father_org = 0

    for s in students:
        spent = s.get("spent_hours", 0)
        paid = s.get("paid_hours", 0)
        car_type = s.get("car_type", "citroen")
        
        total_spent_hours += spent
        total_gross_income += spent * 900
        total_instructor_pay += spent * 450
        
        if car_type == "citroen":
            total_father_citroen += spent * 450
        else:
            total_user_hyundai += spent * 350
            total_father_org += spent * 100

        unpaid = spent - paid
        if unpaid > 0:
            unpaid_hours += unpaid
            unpaid_instructor += unpaid * 450
            if car_type == "citroen":
                unpaid_father_citroen += unpaid * 450
            else:
                unpaid_user_hyundai += unpaid * 350
                unpaid_father_org += unpaid * 100

    return {
        "unpaid_hours": unpaid_hours,
        "unpaid_instructor": unpaid_instructor,
        "unpaid_father_total": unpaid_father_citroen + unpaid_father_org,
        "unpaid_user_hyundai": unpaid_user_hyundai,
        
        "total_spent_hours": total_spent_hours,
        "total_gross_income": total_gross_income,
        "total_instructor_pay": total_instructor_pay,
        "total_father_citroen": total_father_citroen,
        "total_father_org": total_father_org,
        "total_father_sum": total_father_citroen + total_father_org,
        "total_user_hyundai": total_user_hyundai
    }

@router.message(F.text.func(lambda t: t and "Фінанси" in t))
async def show_finances_msg(message: Message):
    if not is_authorized(message.from_user.id) or not is_admin(message.from_user.id):
        await message.answer("❌ Ця функція доступна лише власнику.")
        return

    fin = calculate_financials()
    
    msg = (
        f"💰 **ФІНАНСОВИЙ РОЗРАХУНОК АВТОШКОЛИ**\n"
        f"*(Усі години за тарифом 900 грн/год)*\n\n"
        f"📊 **ЗАГАЛЬНИЙ ПІДСУМОК ({fin['total_spent_hours']} ГОДИН):**\n"
        f"💵 Валовий дохід каси: **{fin['total_gross_income']} грн**\n"
        f"🧑‍🏫 Всього інструктору (по 450 грн): **{fin['total_instructor_pay']} грн**\n"
        f"🚗 Citroen (МКПП): **{fin['total_father_citroen']} грн**\n"
        f"🏛 Сервісний збір Hyundai: **{fin['total_father_org']} грн**\n"
        f"🚙 Hyundai Accent (АКПП): **{fin['total_user_hyundai']} грн**\n\n"
        f"----------------------------------------\n"
        f"⏳ **ПОТОЧНИЙ БАЛАНС ДО ВИПЛАТИ:**\n"
        f"🧑‍🏫 БОРГ ІНСТРУКТОРУ зараз: **{fin['unpaid_instructor']} грн** ({fin['unpaid_hours']} год)\n"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Внести оплату від учня в касу", callback_data="add_student_payment")],
        [InlineKeyboardButton(text="📜 Історія оплат учнів (каса)", callback_data="view_students_payments")],
        [InlineKeyboardButton(text="✅ Підтвердити виплату інструктору", callback_data="mark_paid")]
    ])
    await message.answer(msg, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "add_student_payment")
async def start_student_payment(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостатньо прав", show_alert=True)
        return
        
    students = load_json("students", [])
    if not students:
        await callback.answer("У системі немає учнів.", show_alert=True)
        return

    kb_list = [[InlineKeyboardButton(text=f"{s['name']} ({s['car_type'].upper()})", callback_data=f"pay_st_{s['id']}")] for s in students]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await callback.message.answer("Оберіть учня, від якого надійшла оплата:", reply_markup=kb)
    await state.set_state(StudentPaymentState.student_id)
    await callback.answer()

@router.callback_query(StudentPaymentState.student_id, F.data.startswith("pay_st_"))
async def process_payment_student_chosen(callback: CallbackQuery, state: FSMContext):
    st_id = int(callback.data.split("_")[2])
    await state.update_data(student_id=st_id)
    await callback.message.answer("Введіть кількість годин, які сплатив учень (наприклад, `10` або `20`):", parse_mode="Markdown")
    await state.set_state(StudentPaymentState.hours)
    await callback.answer()

@router.message(StudentPaymentState.hours)
async def process_payment_hours(message: Message, state: FSMContext):
    text_val = message.text.strip().replace(",", ".")
    try:
        hours = float(text_val)
    except ValueError:
        await message.answer("Будь ласка, введіть числове значення годин (наприклад: 10):")
        return
    await state.update_data(hours=hours)
    await message.answer("Введіть суму оплати в грн (тільки число, наприклад `9000`):", parse_mode="Markdown")
    await state.set_state(StudentPaymentState.amount)

@router.message(StudentPaymentState.amount)
async def process_payment_amount(message: Message, state: FSMContext):
    text_val = message.text.strip().replace(" ", "").replace("грн", "")
    try:
        amount = float(text_val)
    except ValueError:
        await message.answer("Будь ласка, введіть суму числами (наприклад: 9000):")
        return
    await state.update_data(amount=amount)
    
    current_date = datetime.now().strftime("%d.%m.%Y")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Оплачено сьогодні", callback_data="pay_date_today")]
    ])
    await message.answer(
        f"Введіть дату оплати (у форматі **ДД.ММ.РРРР**)\n"
        f"Або просто натисніть кнопку нижче для поточної дати ({current_date}):",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await state.set_state(StudentPaymentState.date)

async def save_and_finish_payment(message: Message, state: FSMContext, date_text: str):
    data = await state.get_data()
    st_id = data["student_id"]
    hours = data["hours"]
    amount = data["amount"]

    students = load_json("students", [])
    student_name = "Учень"
    for s in students:
        if s["id"] == st_id:
            student_name = s["name"]
            if "school_payments" not in s:
                s["school_payments"] = []
            s["school_payments"].append({
                "hours": hours,
                "amount": amount,
                "date": date_text
            })
            break
    save_json("students", students)

    await message.answer(
        f"✅ **Оплату від учня успішно внесено!**\n\n"
        f"👤 Учень: {student_name}\n"
        f"⏳ Годин сплачено: {hours} год\n"
        f"💵 Сума: {amount} грн\n"
        f"📅 Дата: {date_text}",
        reply_markup=get_owner_kb(),
        parse_mode="Markdown"
    )
    await state.clear()

@router.callback_query(StudentPaymentState.date, F.data == "pay_date_today")
async def process_payment_date_callback(callback: CallbackQuery, state: FSMContext):
    date_text = datetime.now().strftime("%d.%m.%Y")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await save_and_finish_payment(callback.message, state, date_text)
    await callback.answer()

@router.message(StudentPaymentState.date)
async def process_payment_date(message: Message, state: FSMContext):
    date_text = message.text.strip()
    if date_text.lower() == "сьогодні":
        date_text = datetime.now().strftime("%d.%m.%Y")
    await save_and_finish_payment(message, state, date_text)

@router.callback_query(F.data == "view_students_payments")
async def view_students_payments_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    students = load_json("students", [])
    msg = "📜 **ІСТОРІЯ ОПЛАТ УЧНІВ АВТОШКОЛІ (КАСА):**\n\n"
    has_payments = False

    for s in students:
        payments = s.get("school_payments", [])
        if payments:
            has_payments = True
            msg += f"👤 **{s['name']}** ({s['car_type'].upper()}):\n"
            for p in payments:
                msg += f"  • {p['date']} — {p['hours']} год | **{p['amount']} грн**\n"
            msg += "\n"

    if not has_payments:
        msg = "📜 У системі ще немає зареєстрованих оплат від учнів до автошколи."

    await callback.message.answer(msg, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "mark_paid")
async def mark_paid_callback(callback: CallbackQuery, bot: Bot):
    if not is_authorized(callback.from_user.id) or not is_admin(callback.from_user.id): return

    fin = calculate_financials()
    if fin["unpaid_hours"] == 0:
        await callback.answer("Немає заборгованості перед інструктором.", show_alert=True)
        return

    history = load_json("history", [])
    record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "hours_paid": fin["unpaid_hours"],
        "instructor_amount": fin["unpaid_instructor"]
    }
    history.append(record)
    save_json("history", history)

    students = load_json("students", [])
    for s in students:
        s["paid_hours"] = s["spent_hours"]
    save_json("students", students)

    admins = load_admins_data().get("admin_ids", [])
    log_text = (
        f"✅ **ФІНАНСОВУ ВИПЛАТУ ІНСТРУКТОРУ ЗАФІКСОВАНО**\n\n"
        f"📅 Дата: {record['date']}\n"
        f"🧑‍🏫 Оплачено за {fin['unpaid_hours']} годин.\n"
        f"💸 Сума виплати: **{fin['unpaid_instructor']} грн**"
    )

    for admin_id in admins:
        if admin_id != 0:
            try:
                await bot.send_message(admin_id, log_text, parse_mode="Markdown")
            except Exception:
                pass

    await callback.message.answer("✅ Виплату інструктору успішно закрито та збережено в архіві.")
    await callback.answer()

# ==========================================
# БЛОК ІНСТРУКТОРА: РОЗКЛАД ТА ЗВІТИ
# ==========================================
@router.message(F.text.func(lambda t: t and "Записатися на заняття" in t))
async def sch_add_start_msg(message: Message, state: FSMContext):
    if not is_authorized(message.from_user.id):
        await message.answer("❌ Недостатньо прав.")
        return
    students = load_json("students", [])
    if not students:
        await message.answer("У системі немає учнів. Попросіть власників додати учнів.")
        return

    kb_list = [[InlineKeyboardButton(text=f"{s['name']} ({s['car_type'].upper()})", callback_data=f"sch_st_{s['id']}")] for s in students]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await message.answer("Оберіть учня для запису на заняття:", reply_markup=kb)
    await state.set_state(ScheduleLesson.student_id)

@router.callback_query(ScheduleLesson.student_id, F.data.startswith("sch_st_"))
async def sch_choose_student(callback: CallbackQuery, state: FSMContext):
    st_id = int(callback.data.split("_")[2])
    await state.update_data(student_id=st_id)
    await callback.message.answer("Введіть дату заняття у форматі **ДД.ММ.РРРР** (наприклад, *15.08.2026*):", parse_mode="Markdown")
    await state.set_state(ScheduleLesson.date)
    await callback.answer()

@router.message(ScheduleLesson.date)
async def sch_enter_date(message: Message, state: FSMContext):
    date_text = message.text.strip()
    if "." not in date_text or len(date_text) < 8:
        await message.answer("Будь ласка, введіть дату у правильному форматі, наприклад: 15.08.2026")
        return
    await state.update_data(date=date_text)
    await message.answer("Введіть час початку заняття (наприклад, *10:00* або *14:30*):", parse_mode="Markdown")
    await state.set_state(ScheduleLesson.time)

@router.message(ScheduleLesson.time)
async def sch_enter_time(message: Message, state: FSMContext):
    time_text = message.text.strip()
    if ":" not in time_text:
        await message.answer("Будь ласка, введіть час у форматі HH:MM (наприклад, 10:00):")
        return
    await state.update_data(time=time_text)
    await message.answer("Введіть кількість годин заняття (наприклад, `1`, `1.5`, `2`):", parse_mode="Markdown", reply_markup=None)
    await state.set_state(ScheduleLesson.hours)

@router.message(ScheduleLesson.hours)
async def sch_enter_hours(message: Message, state: FSMContext):
    text_val = message.text.strip().replace(",", ".")
    try:
        hours = float(text_val)
    except ValueError:
        await message.answer("Будь ласка, введіть числове значення годин (наприклад: 1, 1.5, 2):")
        return
    
    if hours <= 0:
        await message.answer("Кількість годин має бути більше 0.")
        return

    data = await state.get_data()
    st_id = data["student_id"]
    lesson_date = data["date"]
    lesson_time = data["time"]

    try:
        t_parts = lesson_time.split(":")
        new_start_min = int(t_parts[0]) * 60 + int(t_parts[1])
    except Exception:
        await message.answer("Помилка формату часу. Спробуйте розпочати запис заново.")
        await state.clear()
        return

    new_end_min = new_start_min + int(hours * 60)

    schedule = load_json("schedule", [])
    conflict = False
    conflict_info = ""

    for item in schedule:
        if item["date"] == lesson_date:
            exist_time = item.get("time", "10:00")
            exist_hours = item.get("hours", 1.0)
            try:
                e_parts = exist_time.split(":")
                exist_start_min = int(e_parts[0]) * 60 + int(e_parts[1])
                exist_end_min = exist_start_min + int(exist_hours * 60)
                
                if max(new_start_min, exist_start_min) < min(new_end_min, exist_end_min):
                    conflict = True
                    conflict_info = f"{item['student_name']} ({item['date']} о {item['time']}, тривалість {exist_hours} год)"
                    break
            except Exception:
                continue

    if conflict:
        await message.answer(
            f"❌ **Цей проміжок часу вже зайнятий!**\n"
            f"Перетинається з іншим заняттям: {conflict_info}\n\n"
            f"Будь ласка, введіть **інший час початку** заняття (наприклад, *12:00*):",
            parse_mode="Markdown"
        )
        await state.set_state(ScheduleLesson.time)
        return

    students = load_json("students", [])
    student_name = "Невідомо"
    car_type = "citroen"
    for s in students:
        if s["id"] == st_id:
            student_name = s["name"]
            car_type = s["car_type"]
            break

    new_lesson = {
        "id": len(schedule) + 1,
        "student_id": st_id,
        "student_name": student_name,
        "car_type": car_type,
        "date": lesson_date,
        "time": lesson_time,
        "hours": hours
    }
    schedule.append(new_lesson)
    save_json("schedule", schedule)

    car_label = "Citroen (МКПП)" if car_type == "citroen" else "Hyundai Accent (АКПП)"
    user_id = message.from_user.id
    if is_admin(user_id):
        kb = get_owner_kb()
    elif is_instructor(user_id):
        kb = get_instructor_kb()
    else:
        kb = get_student_kb()
    
    await message.answer(
        f"✅ Заняття успішно створено!\n\n"
        f"👤 Учень: {student_name}\n"
        f"🚗 Авто: {car_label}\n"
        f"📅 Дата та час: {lesson_date} о {lesson_time}\n"
        f"⏱ Тривалість: {hours} год",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await state.clear()

@router.message(F.text.func(lambda t: t and "Розклад" in t))
async def sch_view_instructor_msg(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("❌ Недостатньо прав.")
        return
    schedule = load_json("schedule", [])
    if not schedule:
        await message.answer("📅 Наразі немає запланованих занять у розкладі.")
        return

    msg = "📋 **АКТУАЛЬНИЙ РОЗКЛАД ЗАНЯТЬ:**\n\n"
    kb_list = []
    for item in schedule:
        car_lbl = "Citroen (МКПП)" if item["car_type"] == "citroen" else "Hyundai Accent (АКПП)"
        hours = item.get("hours", 1.0)
        msg += f"• **{item['date']} о {item['time']}** ({hours} год)\n  - Учень: {item['student_name']} | Авто: {car_lbl}\n\n"
        kb_list.append([InlineKeyboardButton(text=f"❌ Скасувати #{item['id']} ({item['student_name']})", callback_data=f"sch_del_{item['id']}")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await message.answer(msg, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("sch_del_"))
async def sch_delete_lesson(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id): return
    lesson_id = int(callback.data.split("_")[2])
    schedule = load_json("schedule", [])
    
    schedule = [item for item in schedule if item["id"] != lesson_id]
    save_json("schedule", schedule)

    await callback.message.answer("✅ Заняття успішно видалено/скасовано з розкладу.")
    await callback.answer()

# --- ЩОДЕННИЙ ЗВІТ З ІНЛАЙН-КНОПКАМИ ТА ПЕРЕВІРКОЮ ПРОБІГУ ---
@router.message(F.text.func(lambda t: t and "Завершити день" in t))
async def start_daily_report_msg(message: Message, state: FSMContext):
    if not is_authorized(message.from_user.id):
        await message.answer("❌ Недостатньо прав.")
        return
    
    cars = load_json("cars", {})
    citroen_last = cars.get("citroen", {}).get("total_mileage", 0)
    
    await state.update_data(today_sessions=[], citroen_mil=0, hyundai_mil=0, citroen_last=citroen_last)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ввести кілометраж", callback_data="input_citroen_mil")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_daily_report")]
    ])
    
    await message.answer(
        f"🚗 **Оновлення пробігу Citroen (МКПП)**\n"
        f"Попередній збережений пробіг: **{citroen_last} км**.\n"
        f"Натисніть кнопку нижче, щоб ввести новий поточний загальний пробіг:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "cancel_daily_report")
async def cancel_daily_report_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Звіт дня скасовано.")
    user_id = callback.from_user.id
    kb = get_owner_kb() if is_admin(user_id) else (get_instructor_kb() if is_instructor(user_id) else get_student_kb())
    await callback.message.answer("Оберіть дію на панелі:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "input_citroen_mil")
async def input_citroen_mil_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введіть поточний **загальний пробіг** авто **Citroen (МКПП)** в кілометрах (тільки число):", parse_mode="Markdown")
    await state.set_state(DailyReport.citroen_mileage)
    await callback.answer()

@router.message(DailyReport.citroen_mileage)
async def process_citroen_mil(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Будь ласка, введіть числове значення пробігу.")
        return
    
    val = int(message.text)
    data = await state.get_data()
    last_val = data.get("citroen_last", 0)

    if val < last_val:
        await message.answer(
            f"⚠️ **Увага!** Введений пробіг ({val} км) менший за попередній збережений ({last_val} км).\n"
            f"Будь ласка, введіть коректний актуальний пробіг:",
            parse_mode="Markdown"
        )
        return

    await state.update_data(citroen_mil=val)
    
    cars = load_json("cars", {})
    hyundai_last = cars.get("hyundai", {}).get("total_mileage", 0)
    await state.update_data(hyundai_last=hyundai_last)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ввести кілометраж Hyundai", callback_data="input_hyundai_mil")]
    ])
    await message.answer(
        f"🚙 **Оновлення пробігу Hyundai Accent (АКПП)**\n"
        f"Попередній збережений пробіг: **{hyundai_last} км**.\n"
        f"Натисніть кнопку нижче, щоб ввести новий пробіг:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "input_hyundai_mil")
async def input_hyundai_mil_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введіть поточний **загальний пробіг** авто **Hyundai Accent (АКПП)** в кілометрах (тільки число):", parse_mode="Markdown")
    await state.set_state(DailyReport.hyundai_mileage)
    await callback.answer()

@router.message(DailyReport.hyundai_mileage)
async def process_hyundai_mil(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Будь ласка, введіть числове значення пробігу.")
        return
    
    val = int(message.text)
    data = await state.get_data()
    last_val = data.get("hyundai_last", 0)

    if val < last_val:
        await message.answer(
            f"⚠️ **Увага!** Введений пробіг ({val} км) менший за попередній збережений ({last_val} км).\n"
            f"Будь ласка, введіть коректний актуальний пробіг:",
            parse_mode="Markdown"
        )
        return

    await state.update_data(hyundai_mil=val)
    
    students = load_json("students", [])
    if not students:
        await message.answer("У системі немає учнів. Зверніться до власників.")
        await state.clear()
        return

    await state.set_state(DailyReport.student_choice)
    await send_student_menu(message, state, "Оберіть учня, який займався сьогодні:")

async def send_student_menu(message_or_callback, state: FSMContext, text: str):
    students = load_json("students", [])
    data = await state.get_data()
    today_sessions = data.get("today_sessions", [])

    kb_list = [[InlineKeyboardButton(text=f"{s['name']} ({s['car_type'].upper()})", callback_data=f"rep_st_{s['id']}")] for s in students]
    kb_list.append([InlineKeyboardButton(text="🏁 Переглянути звіт (Готово)", callback_data="preview_report_flow")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)

    summary = "📋 **Додані заняття на сьогодні:**\n"
    if today_sessions:
        for sess in today_sessions:
            summary += f"• {sess['name']}: {sess['hours']} год\n"
    else:
        summary += "• Поки нічого не додано\n"

    full_text = f"{summary}\n{text}"

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.answer(full_text, reply_markup=kb, parse_mode="Markdown")
    else:
        await message_or_callback.answer(full_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(DailyReport.student_choice, F.data.startswith("rep_st_"))
async def choose_student_for_report(callback: CallbackQuery, state: FSMContext):
    st_id = int(callback.data.split("_")[2])
    students = load_json("students", [])
    st_name = next((s["name"] for s in students if s["id"] == st_id), "Учень")
    
    await state.update_data(current_student_id=st_id)
    await state.set_state(DailyReport.hours_spent)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 година", callback_data="hours_1_0"), InlineKeyboardButton(text="1.5 години", callback_data="hours_1_5")],
        [InlineKeyboardButton(text="2 години", callback_data="hours_2_0")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_daily_report")]
    ])
    
    await callback.message.edit_text(
        f"👤 Обрано учня: **{st_name}**\n\n"
        f"Оберіть кількість годин заняття або введіть вручну числом (наприклад, `1`, `1.5`, `2`):",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(DailyReport.hours_spent, F.data.startswith("hours_"))
async def process_hours_callback(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    hours = float(f"{parts[1]}.{parts[2]}")
    await handle_hours_saving(callback.message, state, hours, is_callback=True)
    await callback.answer()

@router.message(DailyReport.hours_spent)
async def save_student_daily_hours_msg(message: Message, state: FSMContext):
    text_val = message.text.strip().replace(",", ".")
    try:
        hours = float(text_val)
    except ValueError:
        await message.answer("❌ Будь ласка, введіть числове значення годин (наприклад: `1`, `1.5`, `2`).", parse_mode="Markdown")
        return
    await handle_hours_saving(message, state, hours, is_callback=False)

async def handle_hours_saving(message: Message, state: FSMContext, hours: float, is_callback: bool = False):
    if not (1.0 <= hours <= 2.0):
        err_text = (
            "❌ **Помилка у кількості годин!**\n"
            "Одне заняття зазвичай триває від 1 до 2 годин.\n"
            "Якщо учень від'їздив більше 2 годин, внесіть дані про нього у звіт **двічі**.\n\n"
            "Спробуйте ввести коректну кількість годин:"
        )
        if is_callback:
            await message.answer(err_text, parse_mode="Markdown")
        else:
            await message.answer(err_text, parse_mode="Markdown")
        return

    data = await state.get_data()
    st_id = data["current_student_id"]

    students = load_json("students", [])
    target_student = next((s for s in students if s["id"] == st_id), None)

    if not target_student:
        await message.answer("Помилка: учня не знайдено.")
        await state.set_state(DailyReport.student_choice)
        await send_student_menu(message, state, "Оберіть учня:")
        return

    today_sessions = data.get("today_sessions", [])
    found = False
    for session in today_sessions:
        if session["student_id"] == st_id:
            session["hours"] += hours
            found = True
            break
    
    if not found:
        today_sessions.append({
            "student_id": st_id,
            "name": target_student["name"],
            "car_type": target_student["car_type"],
            "total_hours": target_student["total_hours"],
            "current_spent": target_student["spent_hours"],
            "hours": hours
        })
    
    await state.update_data(today_sessions=today_sessions)
    await state.set_state(DailyReport.student_choice)
    await send_student_menu(message, state, f"✅ Додано {hours} год для {target_student['name']}. Оберіть наступного учня або натисніть «Переглянути звіт»:")

@router.callback_query(DailyReport.student_choice, F.data == "preview_report_flow")
async def preview_daily_report(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    citroen_mil = data.get("citroen_mil", 0)
    hyundai_mil = data.get("hyundai_mil", 0)
    today_sessions = data.get("today_sessions", [])

    citroen_sessions = [s for s in today_sessions if s["car_type"] == "citroen"]
    hyundai_sessions = [s for s in today_sessions if s["car_type"] == "hyundai"]

    report_text = (
        f"🔍 **ПОПЕРЕДНІЙ ПЕРЕГЛЯД ЗВІТУ** (ще не надіслано)\n"
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y')}\n\n"
    )

    report_text += f"🚗 **Citroen (МКПП):** пробіг — {citroen_mil} км\n"
    if citroen_sessions:
        report_text += "Заняття:\n"
        for sess in citroen_sessions:
            new_spent = sess["current_spent"] + sess["hours"]
            report_text += f"• **{sess['name']}**: +**{sess['hours']} год** (всього буде {new_spent} з {sess['total_hours']} год)\n"
    else:
        report_text += "Занять не було.\n"

    report_text += f"\n🚙 **Hyundai Accent (АКПП):** пробіг — {hyundai_mil} км\n"
    if hyundai_sessions:
        report_text += "Заняття:\n"
        for sess in hyundai_sessions:
            new_spent = sess["current_spent"] + sess["hours"]
            report_text += f"• **{sess['name']}**: +**{sess['hours']} год** (всього буде {new_spent} з {sess['total_hours']} год)\n"
    else:
        report_text += "Занять не було.\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити та надіслати", callback_data="confirm_send_report")],
        [InlineKeyboardButton(text="✏️ Редагувати / Почати спочатку", callback_data="edit_report_flow")]
    ])

    await state.set_state(DailyReport.preview)
    await callback.message.edit_text(report_text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(DailyReport.preview, F.data == "edit_report_flow")
async def edit_report_flow(callback: CallbackQuery, state: FSMContext):
    await state.update_data(today_sessions=[], citroen_mil=0, hyundai_mil=0)
    await callback.message.edit_text("Давайте заповнимо звіт спочатку.\n\nВведіть поточний **загальний пробіг** авто **Citroen (МКПП)** в кілометрах (тільки число):", parse_mode="Markdown")
    await state.set_state(DailyReport.citroen_mileage)
    await callback.answer()

@router.callback_query(DailyReport.preview, F.data == "confirm_send_report")
async def confirm_and_send_report(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    citroen_mil = data.get("citroen_mil", 0)
    hyundai_mil = data.get("hyundai_mil", 0)
    today_sessions = data.get("today_sessions", [])

    cars = load_json("cars", {})
    cars["citroen"]["total_mileage"] = citroen_mil
    cars["hyundai"]["total_mileage"] = hyundai_mil
    save_json("cars", cars)

    students = load_json("students", [])
    for sess in today_sessions:
        for s in students:
            if s["id"] == sess["student_id"]:
                s["spent_hours"] += sess["hours"]
                break
    save_json("students", students)

    citroen_sessions = [s for s in today_sessions if s["car_type"] == "citroen"]
    hyundai_sessions = [s for s in today_sessions if s["car_type"] == "hyundai"]

    report_text = (
        f"🏁 **ЩОДЕННИЙ ЗВІТ ІНСТРУКТОРА**\n"
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y')}\n\n"
    )

    report_text += f"🚗 **Citroen (МКПП):** пробіг — {citroen_mil} км\n"
    if citroen_sessions:
        report_text += "Сьогодні займалися:\n"
        for sess in citroen_sessions:
            updated_spent = next((s["spent_hours"] for s in students if s["id"] == sess["student_id"]), sess["current_spent"] + sess["hours"])
            report_text += f"• **{sess['name']}**: від'їздив сьогодні **{sess['hours']} год** (всього {updated_spent} з {sess['total_hours']} год)\n"
    else:
        report_text += "Сьогодні занять не було.\n"

    report_text += f"\n🚙 **Hyundai Accent (АКПП):** пробіг — {hyundai_mil} км\n"
    if hyundai_sessions:
        report_text += "Сьогодні займалися:\n"
        for sess in hyundai_sessions:
            updated_spent = next((s["spent_hours"] for s in students if s["id"] == sess["student_id"]), sess["current_spent"] + sess["hours"])
            report_text += f"• **{sess['name']}**: від'їздив сьогодні **{sess['hours']} год** (всього {updated_spent} з {sess['total_hours']} год)\n"
    else:
        report_text += "Сьогодні занять не було.\n"

    reports = load_json("reports", [])
    reports.append({
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "text": report_text
    })
    save_json("reports", reports)

    admins_data = load_admins_data()
    admins = admins_data.get("admin_ids", [])
    instructor_id = admins_data.get("instructor_id", 0)
    
    recipients = set(admins)
    if instructor_id != 0:
        recipients.add(instructor_id)
    recipients.add(callback.from_user.id)

    for rec_id in recipients:
        if rec_id != 0:
            try:
                await bot.send_message(rec_id, report_text, parse_mode="Markdown")
            except Exception:
                pass

    user_id = callback.from_user.id
    if is_admin(user_id):
        kb = get_owner_kb()
    elif is_instructor(user_id):
        kb = get_instructor_kb()
    else:
        kb = get_student_kb()
    
    await callback.message.edit_text("✅ Щоденний звіт успішно підтверджено, збережено в архів та надіслано!")
    await callback.message.answer("Оберіть дію на панелі:", reply_markup=kb)
    await state.clear()
    await callback.answer()

# --- ВЕБСЕРВЕР ДЛЯ RENDER.COM ---
async def handle(request):
    return aiohttp.web.Response(text="Bot is running!")

async def web_server():
    app = aiohttp.web.Application()
    app.router.add_get("/", handle)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = aiohttp.web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- ЗАПУСК БОТА ---
async def main():
    init_storage()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    asyncio.create_task(web_server())
    
    print("Бот автошколи «Шофер» успішно запущено...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())