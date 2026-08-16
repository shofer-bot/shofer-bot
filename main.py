import os, re, io, imaplib, email, telebot, subprocess, time, threading, requests, logging
from email.header import decode_header
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from docxtpl import DocxTemplate, RichText
from pypdf import PdfReader
from PIL import Image
from telebot import types

# Прибираємо спам-попередження від бібліотеки читання PDF у терміналі
logging.getLogger("pypdf").setLevel(logging.ERROR)

TOKEN = '8348009327:AAHaVlYvANlqHAZMc6l6AzDFc10nB2jFlE8'
bot = telebot.TeleBot(TOKEN)
IMAP_SERVER = 'imap.gmail.com'
EMAIL_USER = 'stolicaadvokat@gmail.com'
EMAIL_PASS = 'ffxotzqyftrpwwvj'
PROCESSED_FILE = 'processed_emails.txt'

# Часова зона України для точної перевірки робочого часу
KYIV_TZ = ZoneInfo("Europe/Kyiv")

def load_processed():
    if not os.path.exists(PROCESSED_FILE):
        return set()
    processed = set()
    with open(PROCESSED_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',', 1)
            processed.add(parts[0])
    return processed

def save_processed(msg_id):
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{msg_id}\n")

def decode_str(s):
    if not s: return ""
    decoded_list = decode_header(s)
    result = ""
    for text, encoding in decoded_list:
        if isinstance(text, bytes): result += text.decode(encoding or 'utf-8', errors='ignore')
        else: result += str(text)
    return result

def clean_subject_prefix(subject):
    s = subject.strip()
    while True:
        new_s = re.sub(r'^(?:fw[d]?|re|forward|зв):\s*', '', s, flags=re.IGNORECASE).strip()
        if new_s == s: break
        s = new_s
    return s

def get_urgency_prefix(subject):
    """Повертає префікс 'ТЕРМІНОВА_' якщо в темі є відповідне слово"""
    if subject and re.search(r'термінов[аио]', subject, re.IGNORECASE):
        return "ТЕРМІНОВА_"
    return ""

def extract_text_from_pdf(pdf_bytes):
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted: text += "\n" + extracted
        return text
    except: return ""

def format_racs_contract_date(dt):
    months = {
        1: 'січня', 2: 'лютого', 3: 'березня', 4: 'квітня',
        5: 'травня', 6: 'червня', 7: 'липня', 8: 'серпня',
        9: 'вересня', 10: 'жовтня', 11: 'листопада', 12: 'грудня'
    }
    return f"{dt.strftime('%d')} {months.get(dt.month, '')} {dt.year} року"

def check_mvs_wanted(full_name):
    api_url = "https://services.mvs.gov.ua/wnt/services/wanted-person-search"
    params = {"query": full_name}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    }
    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            text = response.text.strip()
            if not text or text.startswith('<'):
                return []
            data = response.json()
            matches = []
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get('result', data.get('items', data.get('data', [])))
            for item in items:
                if not isinstance(item, dict):
                    continue
                db_pib = f"{item.get('last_name', '')} {item.get('first_name', '')} {item.get('middle_name', '')}".strip()
                db_birth_date = item.get('birth_date', item.get('birthday', 'Не вказано'))
                if db_pib:
                    matches.append({
                        "pib": db_pib,
                        "birth_date": db_birth_date
                    })
            return matches
    except Exception:
        pass
    return []

def parse_email_content(subject_text, body_text):
    clean_subj = clean_subject_prefix(subject_text)
    is_urgent = bool(re.search(r'термінов[аио]', clean_subj, re.IGNORECASE))
    apostille_text = '+ так'
    if re.search(r'без\s+апостиля?', clean_subj, re.IGNORECASE): 
        apostille_text = 'ні'
    subject_cleaned = re.sub(r'(?i)\b(установи|апостиль|без апостиля|термінова|терміново|термін)\b|\+?\s*апостиль|без\s+апостиля?|[\+\-\!\#\@\(\)]', ' ', clean_subj)
    words = ' '.join(subject_cleaned.split()).split()
    if not words: return None
    last_name = words[0] if len(words) >= 1 else ''
    first_name = words[1] if len(words) >= 2 else ''
    middle_name = ' '.join(words[2:]) if len(words) >= 3 else ''
    full_name = f"{last_name} {first_name} {middle_name}".strip()
    result = {
        'purpose_adoption': False, 'purpose_visa': False, 'purpose_foreign': True, 
        'purpose_work': False, 'purpose_weapon': False, 'purpose_drugs': False, 
        'purpose_tender': False, 'purpose_citizenship': False, 'purpose_tck': False, 
        'purpose_requirement': False, 'apostille_text': apostille_text, 
        'full_name': full_name, 'last_name': last_name, 'first_name': first_name, 'middle_name': middle_name, 
        'birth_date': '15.05.1990', 'birth_place': 'Україна', 
        'passport': '010074635', 'rnkpp': '3974511939',
        'is_urgent': is_urgent
    }
    if body_text:
        bd_match = re.search(r'\b(0[1-9]|[12]\d|3[01])[\.\-/](0[1-9]|1[0-2])[\.\-/](\d{4})\b', body_text)
        if bd_match: result['birth_date'] = f"{bd_match.group(1)}.{bd_match.group(2)}.{bd_match.group(3)}"
        rnkpp_match = re.search(r'\b\d{10}\b', body_text)
        if rnkpp_match: result['rnkpp'] = rnkpp_match.group(0)
        pass_match = re.search(r'\b([A-ZА-ЯІЇЄҐa-zа-яіїєґ]{2}\d{6}|\d{9})\b', body_text)
        if pass_match: result['passport'] = pass_match.group(1).upper()
        for line in body_text.split('\n'):
            if any(kw in line.lower() for kw in ['місце народження', 'place of birth', 'народився', 'народилася']):
                clean_p = re.sub(r'.*?(місце народження|place of birth|народився|народилася)[:\s\-]*', '', line, flags=re.IGNORECASE).strip()
                if len(clean_p) > 2: result['birth_place'] = clean_p; break
    return result

def parse_racs_email_content(subject_text):
    clean_subj = clean_subject_prefix(subject_text)
    is_urgent = bool(re.search(r'термінов[аио]', clean_subj, re.IGNORECASE))
    
    copies = 1
    copies_match = re.search(r'(\d+)\s*(?:екз\.?|екземпляр[а-яІЇЄҐіїєґ]*|примірник[а-яІЇЄҐіїєґ]*|экземпляр[а-я]*)', clean_subj, re.IGNORECASE)
    if copies_match:
        try: copies = int(copies_match.group(1))
        except: copies = 1
    else:
        word_to_num = {
            'два': 2, 'дві': 2, 'двох': 2, 'двух': 2,
            'три': 3, 'трьох': 3, 'трех': 3,
            'чотири': 4, 'чотирьох': 4, 'четыре': 4,
            'п\'ять': 5, 'п\'яти': 5, 'пять': 5, 'пяти': 5,
            'шість': 6, 'шести': 6, 'шесть': 6,
            'сім': 7, 'семи': 7,
            'вісім': 8, 'восьми': 8,
            'дев\'ять': 9, 'девять': 9, 'девяти': 9,
            'десять': 10, 'десяти': 10
        }
        for word, num in word_to_num.items():
            pattern = rf'\b{word}\b.*?(?:екз\.?|екземпляр[а-яІЇЄҐіїєґ]*|примірник[а-яІЇЄҐіїєґ]*|экземпляр[а-я]*|экз\.?)'
            if re.search(pattern, clean_subj, re.IGNORECASE):
                copies = num
                break

    apostille_text = '+ так'
    if re.search(r'без\s+апостиля?', clean_subj, re.IGNORECASE): apostille_text = 'ні'
    
    subject_cleaned = re.sub(r'(?i)\b(?:в|у)?\s*(?:\d+|двох|трьох|чотирьох|п\'яти|шести|семи|восьми|дев\'яти|десяти|два|дві|двух|три|трех|чотири|п\'ять|пять|шість|сім|вісім|дев\'ять|девять|десять)?\s*(?:екз\.?|екземпляр[а-яІЇЄҐіїєґ]*|примірник[а-яІЇЄҐіїєґ]*|экземпляр[а-я]*|экз\.?)\b', ' ', clean_subj)
    
    # Додано захист від опечаток у назві відділу (наприклад, "подідський" замість "подільський")
    subject_cleaned = re.sub(r'(?i)\b(рацс|драцс|под[а-яі]*льськ[а-я]*|по[іі]дльськ[а-я]*|под[а-яі]*дськ[а-я]*|шевченківський|святошинський|голосіївський|печерський|солом[’\']янський|оболонський|деснянський|дніпровський|дарницький|міський|відділ|реєстрації|актів|цивільного|стану|установи|апостиль|без апостиля|термінова|терміново|термін)\b|\+?\s*апостиль|без\s+апостиля?|[\+\-\!\#\@\(\)]', ' ', subject_cleaned)
    
    words = ' '.join(subject_cleaned.split()).split()
    if not words: return None
    last_name = words[0] if len(words) >= 1 else ''
    first_name = words[1] if len(words) >= 2 else ''
    middle_name = ' '.join(words[2:]) if len(words) >= 3 else ''
    full_name = f"{last_name} {first_name} {middle_name}".strip()
    return {'full_name': full_name, 'last_name': last_name, 'first_name': first_name, 'middle_name': middle_name, 'apostille_text': apostille_text, 'is_urgent': is_urgent, 'copies': copies}

def parse_tsc_email_content(subject_text):
    clean_subj = clean_subject_prefix(subject_text)
    subject_cleaned = re.sub(r'(?i)\b(довідка\s+даі|даі|тсц|установи|апостиль|без апостиля|термінова|терміново|термін)\b|\+?\s*апостиль|без\s+апостиля?|[\+\-\!\#\@\(\)]', ' ', clean_subj)
    words = ' '.join(subject_cleaned.split()).split()
    if not words: return None
    full_name = ' '.join(words).strip()
    return {'full_name': full_name, 'last_name': words[0] if words else '', 'first_name': words[1] if len(words)>1 else '', 'middle_name': ' '.join(words[2:]) if len(words)>2 else ''}

def make_goal_rt(text, is_selected):
    rt = RichText()
    if is_selected: rt.add("☑ ", bold=True); rt.add(text, bold=True)
    else: rt.add("   ", bold=False); rt.add(text, bold=False)
    return rt

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔄 Перевірити пошту"))
    return markup

def convert_to_pdf_robust(docx_path, out_dir):
    soffice_path = '/Applications/LibreOffice.app/Contents/MacOS/soffice'
    pdf_path = docx_path.replace('.docx', '.pdf')
    if not os.path.exists(soffice_path): return None
    try:
        subprocess.run([soffice_path, '--headless', '--convert-to', 'pdf', docx_path, '--outdir', out_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return pdf_path if os.path.exists(pdf_path) else None
    except: return None

def process_incoming_emails(chat_id, sub_date=None):
    now_time = datetime.now(KYIV_TZ)
    if sub_date is None:
        sub_date = now_time
            
    processed_ids = load_processed()
    base_dir = os.path.expanduser('~/Desktop/Advocate_Auto')
    checked_clients = []
    
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select('inbox')
        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK' or not messages[0]:
            mail.logout()
            bot.send_message(chat_id, "📭 Немає нових непрочитаних листів.", reply_markup=get_main_keyboard())
            return
            
        for e_id in messages[0].split():
            res, msg_data = mail.fetch(e_id, '(BODY.PEEK[])')
            msg = email.message_from_bytes(msg_data[0][1])
            if 'info.perevod@ukr.net' not in msg.get('From', ''): continue
            msg_id = msg.get('Message-ID')
            if not msg_id or msg_id in processed_ids: continue
            subject = decode_str(msg['Subject'])
            
            urgency_prefix = get_urgency_prefix(subject)
            
            # --- 1. ОБРОБКА ДЛЯ ТСЦ (ДАІ) — ТІЛЬКИ ЗАПИТИ ---
            if re.search(r'\b(даі|довідка\s+даі)\b', subject, re.IGNORECASE):
                tsc_data = parse_tsc_email_content(subject)
                if tsc_data and tsc_data['last_name']:
                    wanted_matches = check_mvs_wanted(tsc_data['full_name'])
                    if wanted_matches:
                        alert_text = f"⚠️ **УВАГА! Знайдено збіги в розшуку МВС!**\nПІБ: <b>{tsc_data['full_name']}</b>\n\nМожливі збіги в базі:\n"
                        for match in wanted_matches:
                            alert_text += f"• <b>{match['pib']}</b> (Дата народження: {match['birth_date']})\n"
                        bot.send_message(chat_id, alert_text, parse_mode="HTML")
                    else:
                        checked_clients.append(tsc_data['full_name'])

                    tsc_dir = os.path.join(base_dir, 'Тсц')
                    os.makedirs(tsc_dir, exist_ok=True)
                    
                    ctx = {'ПІБ': tsc_data['full_name'], 'SUBMISSION_DATE': now_time.strftime('%d.%m.%Y')}
                    
                    tpl_z = os.path.join(base_dir, 'запит_тсц.docx')
                    if os.path.exists(tpl_z):
                        doc = DocxTemplate(tpl_z); doc.render(ctx)
                        path = os.path.join(tsc_dir, f"{urgency_prefix}запит_тсц_{tsc_data['last_name']}.docx")
                        doc.save(path)
                        with open(path, 'rb') as f: bot.send_document(chat_id, f)
                        
                save_processed(msg_id)
                continue

            # --- 2. ОБРОБКА ДЛЯ РАЦС ---
            if re.search(r'\b(рацс|драцс)\b', subject, re.IGNORECASE):
                racs_data = parse_racs_email_content(subject)
                if racs_data and racs_data['last_name']:
                    wanted_matches = check_mvs_wanted(racs_data['full_name'])
                    if wanted_matches:
                        alert_text = f"⚠️ **УВАГА! Знайдено збіги в розшуку МВС!**\nПІБ: <b>{racs_data['full_name']}</b>\n\nМожливі збіги в базі:\n"
                        for match in wanted_matches:
                            alert_text += f"• <b>{match['pib']}</b> (Дата народження: {match['birth_date']})\n"
                        bot.send_message(chat_id, alert_text, parse_mode="HTML")
                    else:
                        checked_clients.append(racs_data['full_name'])

                    racs_orders_dir = os.path.join(base_dir, 'Ордери РАЦС')
                    racs_contracts_dir = os.path.join(base_dir, 'Договори РАЦС')
                    os.makedirs(racs_orders_dir, exist_ok=True); os.makedirs(racs_contracts_dir, exist_ok=True)
                    
                    days_add = 14 if racs_data['apostille_text'] == 'ні' else 21
                    sub_str = sub_date.strftime('%d.%m.%Y')
                    rec_str = f"___.___.{sub_date.year}" if racs_data['is_urgent'] else (sub_date + timedelta(days=days_add)).strftime('%d.%m.%Y')
                    
                    order_context = {'LAST_NAME': racs_data['last_name'], 'FIRST_NAME': racs_data['first_name'], 'MIDDLE_NAME': racs_data['middle_name'], 'ПІБ': racs_data['full_name'], 'APOSTILLE': racs_data['apostille_text'], 'SUBMISSION_DATE': sub_str, 'RECEIPT_DATE': rec_str}
                    contract_sub_str = format_racs_contract_date(sub_date)
                    contract_context = {'LAST_NAME': racs_data['last_name'], 'FIRST_NAME': racs_data['first_name'], 'MIDDLE_NAME': racs_data['middle_name'], 'ПІБ': racs_data['full_name'], 'APOSTILLE': racs_data['apostille_text'], 'SUBMISSION_DATE': contract_sub_str, 'RECEIPT_DATE': rec_str}
                    
                    copies = racs_data.get('copies', 1)
                    for i in range(1, copies + 1):
                        suffix = f"_{i}" if copies > 1 else ""
                        tpl_o = os.path.join(base_dir, 'ордер_рацс.docx')
                        if os.path.exists(tpl_o):
                            doc = DocxTemplate(tpl_o); doc.render(order_context)
                            path = os.path.join(racs_orders_dir, f"{urgency_prefix}ордер_рацс_{racs_data['last_name']}{suffix}.docx")
                            doc.save(path)
                            pdf = convert_to_pdf_robust(path, racs_orders_dir)
                            if pdf: os.remove(path); path = pdf
                            with open(path, 'rb') as f: bot.send_document(chat_id, f)
                            
                        tpl_c = os.path.join(base_dir, 'договір_рацс.docx')
                        if os.path.exists(tpl_c):
                            doc = DocxTemplate(tpl_c); doc.render(contract_context)
                            path = os.path.join(racs_contracts_dir, f"{urgency_prefix}договір_рацс_{racs_data['last_name']}{suffix}.docx")
                            doc.save(path)
                            with open(path, 'rb') as f: bot.send_document(chat_id, f)
                save_processed(msg_id)
                continue

            # --- 3. ОБРОБКА ДЛЯ СПИСКІВ ТА КВИТАНЦІЙ ---
            if re.search(r'\b(список|списки|квитанці[яіŭ]|квитанци[яи])\b', subject, re.IGNORECASE):
                target_folder = 'Квитанції' if re.search(r'квитанці', subject, re.IGNORECASE) else 'СПИСКИ'
                lists_receipts_dir = os.path.join(base_dir, target_folder)
                os.makedirs(lists_receipts_dir, exist_ok=True)
                
                saved_count = 0
                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart': continue
                    if part.get('Content-Disposition') is None: continue
                    payload = part.get_payload(decode=True)
                    if not payload: continue
                    
                    fname = part.get_filename()
                    if fname:
                        decoded_list = decode_header(fname)
                        fname, encoding = decoded_list[0]
                        if isinstance(fname, bytes):
                            fname = fname.decode(encoding or 'utf-8', errors='ignore')
                    else:
                        fname = f"attachment_{int(time.time())}.bin"
                        
                    att_path = os.path.join(lists_receipts_dir, fname)
                    counter = 1
                    while os.path.exists(att_path):
                        name, ext = os.path.splitext(fname)
                        att_path = os.path.join(lists_receipts_dir, f"{name}_{counter}{ext}")
                        counter += 1
                        
                    with open(att_path, 'wb') as f:
                        f.write(payload)
                    saved_count += 1
                
                bot.send_message(chat_id, f"📁 Отримано та збережено в папку <b>{target_folder}</b>: {saved_count} файл(ів).\nТема: <i>{subject}</i>", parse_mode="HTML")
                save_processed(msg_id)
                continue

            # --- 4. ОБРОБКА ЛИСТІВ МВС (АВТОМАТИЧНИЙ ВИБІР ДАТИ) ---
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_filename() and part.get_filename().lower().endswith('.pdf'): body += "\n" + extract_text_from_pdf(part.get_payload(decode=True))
                    elif part.get_content_type() in ["text/plain", "text/html"]: body += "\n" + (re.sub(r'<[^>]+>', ' ', part.get_payload(decode=True).decode('utf-8', errors='ignore')) if part.get_content_type() == "text/html" else part.get_payload(decode=True).decode('utf-8', errors='ignore'))
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    content_type = msg.get_content_type()
                    text_part = payload.decode('utf-8', errors='ignore')
                    if content_type == "text/html":
                        text_part = re.sub(r'<[^>]+>', ' ', text_part)
                    body += "\n" + text_part
            
            client_data = parse_email_content(subject, body)
            if client_data:
                wanted_matches = check_mvs_wanted(client_data['full_name'])
                if wanted_matches:
                    alert_text = f"⚠️ **УВАГА! Знайдено збіги в розшуку МВС!**\nПІБ з листа: <b>{client_data['full_name']}</b>\n\nМожливі збіги в базі:\n"
                    for match in wanted_matches:
                        alert_text += f"• <b>{match['pib']}</b> (Дата народження: {match['birth_date']})\n"
                    alert_text += "\n<i>Будь ласка, перевірте дату народження клієнта самостійно.</i>"
                    bot.send_message(chat_id, alert_text, parse_mode="HTML")
                else:
                    checked_clients.append(client_data['full_name'])

                # Розрахунок дати за новими правилами
                weekday = now_time.weekday() # 0:Пн, 1:Вт, 2:Ср, 3:Чт, 4:Пт, 5:Сб, 6:Нд
                if weekday < 5: # Будні дні (Пн-Пт)
                    if now_time.hour < 16:
                        mvs_date = now_time # До 16:00 -> сьогодні
                    else:
                        if weekday == 4: # П'ятниця після 16:00 -> понеділок (+3 дні)
                            mvs_date = now_time + timedelta(days=3)
                        else: # Пн-Чт після 16:00 -> завтра (+1 день)
                            mvs_date = now_time + timedelta(days=1)
                else: # Вихідні (Сб-Нд)
                    if weekday == 5: # Субота -> понеділок (+2 дні)
                        mvs_date = now_time + timedelta(days=2)
                    else: # Неділя -> понеділок (+1 день)
                        mvs_date = now_time + timedelta(days=1)

                sub_str = mvs_date.strftime('%d.%m.%Y')
                
                req_dir, ord_dir = os.path.join(base_dir, 'Запити'), os.path.join(base_dir, 'Ордери')
                os.makedirs(req_dir, exist_ok=True); os.makedirs(ord_dir, exist_ok=True)
                
                days_add = 14 if client_data['apostille_text'] == 'ні' else 21
                rec_str = f"___.___.{mvs_date.year}" if client_data['is_urgent'] else (mvs_date + timedelta(days=days_add)).strftime('%d.%m.%Y')
                
                # Генерація запиту
                tpl_z = os.path.join(base_dir, 'запит.docx')
                if os.path.exists(tpl_z):
                    doc = DocxTemplate(tpl_z)
                    doc.render({
                        'LAST_NAME': client_data['last_name'], 
                        'FIRST_NAME': client_data['first_name'], 
                        'MIDDLE_NAME': client_data['middle_name'], 
                        'ПІБ': client_data['full_name'], 
                        'APOSTILLE': client_data['apostille_text'], 
                        'SUBMISSION_DATE': sub_str, 
                        'RECEIPT_DATE': rec_str
                    })
                    path = os.path.join(req_dir, f"{urgency_prefix}запит_{client_data['last_name']}.docx")
                    doc.save(path)
                    with open(path, 'rb') as f: bot.send_document(chat_id, f)
                 
                # Генерація ордера та конвертація в PDF
                tpl_o = os.path.join(base_dir, 'ордер .docx')
                if os.path.exists(tpl_o):
                    doc = DocxTemplate(tpl_o)
                    doc.render({
                        'LAST_NAME': client_data['last_name'], 
                        'FIRST_NAME': client_data['first_name'], 
                        'MIDDLE_NAME': client_data['middle_name'], 
                        'BIRTH_DATE': client_data['birth_date'], 
                        'BIRTH_PLACE': client_data['birth_place'], 
                        'CITIZENSHIP': 'Україна', 
                        'PASSPORT': client_data['passport'], 
                        'RNKpp': client_data['rnkpp'], 
                        'GOAL_ADOPTION': make_goal_rt("усиновлення...", client_data['purpose_adoption']), 
                        'GOAL_VISA': make_goal_rt("оформлення візи...", client_data['purpose_visa']), 
                        'GOAL_FOREIGN': make_goal_rt("іноземні держави...", client_data['purpose_foreign']), 
                        'GOAL_WORK': make_goal_rt("оформлення на роботу...", client_data['purpose_work']), 
                        'GOAL_WEAPON': make_goal_rt("зброя...", client_data['purpose_weapon']), 
                        'GOAL_DRUGS': make_goal_rt("наркотичні засоби...", client_data['purpose_drugs']), 
                        'GOAL_TENDER': make_goal_rt("тендер...", client_data['purpose_tender']), 
                        'GOAL_CITIZENSHIP': make_goal_rt("громадянство...", client_data['purpose_citizenship']), 
                        'GOAL_TCK': make_goal_rt("ТЦК...", client_data['purpose_tck']), 
                        'GOAL_REQUIREMENT': make_goal_rt("за вимогою...", client_data['purpose_requirement']), 
                        'APOSTILLE': client_data['apostille_text'], 
                        'SUBMISSION_DATE': sub_str, 
                        'RECEIPT_DATE': rec_str, 
                        'ПІБ': client_data['full_name']
                    })
                    path = os.path.join(ord_dir, f"{urgency_prefix}ордер_{client_data['last_name']}.docx")
                    doc.save(path)
                    pdf = convert_to_pdf_robust(path, ord_dir)
                    if pdf: os.remove(path); path = pdf
                    with open(path, 'rb') as f: bot.send_document(chat_id, f)
                    
                save_processed(msg_id)
        
        mail.logout()

        final_message = "✅ Перевірку пошти завершено."
        if checked_clients:
            names_list = "\n".join([f"• <b>{name}</b>" for name in checked_clients])
            final_message += f"\n\n🛡 <b>Перевірку на розшуку МВС успішно пройдено:</b>\n{names_list}\n\n<i>Ніхто з перелічених осіб не перебуває в розшуку (0 збігів).</i>"
            
        bot.send_message(chat_id, final_message, reply_markup=get_main_keyboard(), parse_mode="HTML")
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Помилка: {e}", reply_markup=get_main_keyboard())


@bot.message_handler(commands=['start'])
def send_welcome(m):
    bot.reply_to(m, "Вітаю! Бот готовий.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and "Перевірити пошту" in message.text)
def check_button(m):
    bot.send_message(m.chat.id, "⏳ Починаю перевірку пошти...", reply_markup=get_main_keyboard())
    def run_async():
        process_incoming_emails(m.chat.id, datetime.now(KYIV_TZ))
    threading.Thread(target=run_async).start()

if __name__ == "__main__":
    print("Бот запущено і слухає події (Polling)...")
    try:
        bot.infinity_polling(none_stop=True, interval=0, timeout=20, long_polling_timeout=20)
    except Exception as e:
        print(f"Сталася помилка: {e}")