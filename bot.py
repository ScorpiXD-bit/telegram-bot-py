import telebot
import requests
from telebot import types
from datetime import datetime, timedelta
import os
import os
from flask import Flask, request


TOKEN = os.getenv("TOKEN")
URL = "https://r.sch80.ru/"

bot = telebot.TeleBot(TOKEN)


# -------------------- НАСТРОЙКИ --------------------

SUPPORT_USERNAME = "@TexPoddershka80"
BLACKLIST = {14269529}
CACHE_TTL = 60*30  # 30 минут

user_class = {}
user_name = {}
schedule_cache = {}
last_schedule_message = {}
SPECIAL_USERS = {6231701085}  # сюда добавь ID пользователей, которым доступно
user_classes = user_class     # используем словарь с классами


# -------------------- КНОПКИ --------------------

def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📚 Показать расписание")
    kb.row("❤️ Поддержать автора", "🆘 Тех поддержка")
    return kb

# ===== КНОПКИ =====

def day_keyboard(offset):
    kb = telebot.types.InlineKeyboardMarkup(row_width=3)

    buttons = []

    if offset != -1:
        buttons.append(
            telebot.types.InlineKeyboardButton("⬅ Вчера", callback_data="day_-1")
        )
    if offset != 0:
        buttons.append(
            telebot.types.InlineKeyboardButton("📅 Сегодня", callback_data="day_0")
        )
    if offset != 1:
        buttons.append(
            telebot.types.InlineKeyboardButton("➡ Завтра", callback_data="day_1")
        )

    # Добавляем все кнопки в ОДНУ строку
    kb.row(*buttons)

    return kb


# -------------------- ПРОВЕРКА ЧС --------------------

def check_blacklist(message):
    if message.from_user.id in BLACKLIST:
        bot.send_message(
            message.chat.id,
            f"⛔ Ты в чёрном списке.\nНапиши в техподдержку: {SUPPORT_USERNAME}"
        )
        return True
    return False

# -------------------- СЛОВАРЬ СОКРАЩЕНИЙ УРОКОВ --------------------

LESSON_ABBREVIATIONS = {
    "Финансовая грамотность": "ФГ",
    "Основы финансовой грамотности": "ОФГ",
    "Родной язык": "Родн. рус.",
    "Математика": "Матем.",
    "Русский язык": "Рус. яз.",
    "Литература": "Лит.",
    "История": "Ист.",
    "География": "Геогр.",
    "Биология": "Биол.",
    "Физика": "Физ.",
    "Химия": "Хим.",
    "Информатика": "Инф.",
    "Обществознание": "Обществ.",
    "Физкультура": "Физ-ра",
    "ИЗО": "ИЗО",
    "Музыка": "Музыка",
    "Профессиональная ориентация": "ПО",
    "Иностранный язык": "Ин. яз.",
    "Физическая культура": "Физ-ра",
    "Труд (технология)": "Труд",
    "----": "-"
    # Добавляй новые предметы сюда
}

# -------------------- Функция для сокращения уроков --------------------

def short_lesson(name):
    for key in LESSON_ABBREVIATIONS:
        if key in name:
            return LESSON_ABBREVIATIONS[key]
    return name  # Если нет в словаре, возвращаем оригинальное название


def get_schedule(class_name, day_offset):
    today = datetime.now().date() + timedelta(days=day_offset)
    key = (class_name, today)

    if key in schedule_cache:
        data, ts = schedule_cache[key]
        if time.time() - ts < CACHE_TTL:
            return data

    url = "https://r.sch80.ru/api/v1/rasp/subject-rasp/"
    params = {
        "type": "klass",
        "name": class_name,
        "date": today.strftime("%d.%m.%Y")
    }

    r = requests.get(url, params=params, timeout=5)
    data = r.json()

    schedule_cache[key] = (data, time.time())
    return data

def format_schedule(class_name, day_offset):
    labels = {-1: "Вчера", 0: "Сегодня", 1: "Завтра"}
    header = f"📚 {labels[day_offset]}, {class_name}\n\n"

    data = get_schedule(class_name, day_offset)
    rasp = data.get("rasp", {})

    text = header
    for i in range(1, 13):
        lesson = rasp.get(str(i))

        # Проверяем, что урок существует и есть время
        if not lesson or not lesson.get("time_rasp"):
            text += f"{i}. ⏰- - 📘- -\n"
            continue

        t = lesson["time_rasp"]
        start, end = t.get("start", "-"), t.get("end", "-")

        if lesson.get("lesson_name"):
            name = short_lesson(lesson["lesson_name"][0])
            cab = lesson["cab"][0] if lesson.get("cab") else "-"
            text += f"{i}. ⏰{start}-{end} 📘{name} {cab}\n"
        else:
            text += f"{i}. ⏰{start}-{end} 📘- -\n"

    return text

# -------------------- ПРОВЕРКА СУЩЕСТВОВАНИЯ КЛАССА --------------------

def class_exists(class_name):
    """Проверяет, существует ли класс в системе расписания."""
    url = "https://r.sch80.ru/api/v1/rasp/subject-rasp/"
    params = {
        "type": "klass",
        "name": class_name,
        "date": datetime.now().strftime("%d.%m.%Y")
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        # Если ключ "rasp" пустой, значит класс не найден
        if not data.get("rasp"):
            return False
        return True
    except Exception:
        return False


# -------------------- СТАРТ --------------------

@bot.message_handler(commands=["start"])
def start(message):
    if check_blacklist(message):
        return

    bot.send_message(
        message.chat.id,
        "👋 Привет! Напиши класс (например: 6Г)",
        reply_markup=main_keyboard()
    )

# -------------------- СОХРАНЕНИЕ КЛАССА --------------------

@bot.message_handler(func=lambda m: m.text and m.text[0].isdigit())
def save_class(message):
    if check_blacklist(message):
        return

    class_name = message.text.upper()
    
    # Проверяем, существует ли класс
    if not class_exists(class_name):
        bot.send_message(message.chat.id, f"❗ Класса {class_name} не существует!")
        return

    user_class[message.chat.id] = class_name

    bot.send_message(
        message.chat.id,
        f"✅ Класс сохранён: {class_name}",
        reply_markup=main_keyboard()
    )

# -------------------- ПОКАЗАТЬ РАСПИСАНИЕ --------------------

@bot.message_handler(func=lambda m: m.text == "📚 Показать расписание")
def show_today(message):
    if check_blacklist(message):
        return

    if message.chat.id not in user_class:
        bot.send_message(message.chat.id, "❗ Сначала введи класс")
        return

    # Попытка удалить старое сообщение — безопасно
    if message.chat.id in last_schedule_message:
        try:
            bot.delete_message(message.chat.id, last_schedule_message[message.chat.id])
        except Exception:
            pass

    text = format_schedule(user_class[message.chat.id], 0)

    try:
        msg = bot.send_message(message.chat.id, text, reply_markup=day_keyboard(0))
        last_schedule_message[message.chat.id] = msg.message_id
    except Exception as e:
        print("Ошибка при отправке сообщения:", e)

# -------------------- КНОПКИ ДНЕЙ --------------------

@bot.callback_query_handler(func=lambda c: c.data.startswith("day_"))
def change_day(call):
    offset = int(call.data.split("_")[1])
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    class_name = user_class.get(chat_id)
    if not class_name:
        return

    bot.answer_callback_query(call.id)

    new_text = format_schedule(class_name, offset)

    try:
        bot.edit_message_text(
            new_text,
            chat_id,
            message_id,
            reply_markup=day_keyboard(offset)
        )
    except Exception:
        # ПРОСТО игнорируем ЛЮБУЮ ошибку редактирования
        pass

# -------------------- ДОНАТ --------------------

@bot.message_handler(func=lambda m: m.text == "❤️ Поддержать автора")
def donate(message):
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("⭐ 10", callback_data="donate_10"),
        types.InlineKeyboardButton("⭐ 50", callback_data="donate_50"),
        types.InlineKeyboardButton("⭐ 100", callback_data="donate_100"),
    )
    bot.send_message(message.chat.id, "❤️ Выбери сумму доната:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("donate_"))
def invoice(call):
    amount = int(call.data.split("_")[1])
    prices = [types.LabeledPrice(label=f"{amount} ⭐", amount=amount)]

    bot.send_invoice(
        call.message.chat.id,
        title="Поддержка автора ❤️",
        description="Спасибо за поддержку!",
        invoice_payload=str(amount),
        provider_token="",
        currency="XTR",
        prices=prices
    )

@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)


# -------------------- ТЕХ ПОДДЕРЖКА --------------------

@bot.message_handler(func=lambda m: m.text == "🆘 Тех поддержка")
def support(message):
    bot.send_message(
        message.chat.id,
        f"🆘 Тех поддержка: {SUPPORT_USERNAME}"
    )

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "циферки")
def send_id(msg):
    bot.send_message(msg.chat.id, f"🆔 Твой ID: {msg.chat.id}")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "секретики")
def secrets(msg):
    if msg.chat.id not in SPECIAL_USERS:
        return
    
    text = "👥 Пользователи:\n"
    for uid, cls in user_classes.items():
        # Получаем юзернейм, если есть
        username = bot.get_chat(uid).username if bot.get_chat(uid) and bot.get_chat(uid).username else "-"
        text += f"ID: {uid} | Класс: {cls} | @{username}\n"
    
    bot.send_message(msg.chat.id, text)
    
# -------------------- ЗАПУСК --------------------

print("🤖 Bot started")



app = Flask(__name__)
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL Render, который даст Render

bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL + TOKEN)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


