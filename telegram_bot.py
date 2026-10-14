# ROOF LOVE - Telegram-бот приёма заявок с лендинга.
# Токен и chat_id уже подставлены. Запуск: python telegram_bot.py

import json
import logging
import os
import time
from datetime import datetime

import requests

BOT_TOKEN = "8665212930:AAGKak9zp2HDffI2EaF5Ca1FIMw7ZJgT6I4"
MANAGER_CHAT_ID = 8825139730
LEADS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.json")
POLL_TIMEOUT = 30

API = "https://api.telegram.org/bot" + BOT_TOKEN + "/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rooflove-bot")

SOURCES = {
    "site_header": "Кнопка Telegram в шапке сайта",
    "lead_modal": "Модальное окно Зафиксировать цену и дату",
    "lead_booking": "Форма бронирования внизу сайта",
    "sticky_bar": "Синяя кнопка Telegram внизу сайта (мобильные)",
    "float_site": "Плавающая кнопка Telegram (десктоп)",
    "ask_manager": "Ссылка спросить в чате возле калькулятора",
}

USER_STATE = {}


def api(method, **params):
    for attempt in range(8):
        try:
            r = requests.post(API + method, data=params, timeout=POLL_TIMEOUT + 10)
            data = r.json()
            if not data.get("ok"):
                log.warning("API error %s: %s", method, data.get("description"))
            return data
        except requests.RequestException as exc:
            log.warning("Network error (%s), attempt %d: %s", method, attempt + 1, exc)
            time.sleep(2 + attempt * 2)
    return {"ok": False}


def send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    params = dict(chat_id=chat_id, text=text, parse_mode=parse_mode,
                  disable_web_page_preview=True)
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return api("sendMessage", **params)


def contact_keyboard():
    return {
        "keyboard": [[{"text": "Отправить контакт", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def hide_keyboard():
    return {"remove_keyboard": True}


def source_label(payload):
    if not payload:
        return "Прямой вход в бота (без сайта)"
    if payload in SOURCES:
        return SOURCES[payload]
    if payload.startswith("quiz_"):
        return "Квиз на сайте, сертификат " + payload[5:]
    return "Сайт, метка: " + payload


def save_lead(lead):
    leads = []
    if os.path.exists(LEADS_FILE):
        try:
            with open(LEADS_FILE, "r", encoding="utf-8") as fh:
                leads = json.load(fh)
        except (ValueError, OSError):
            leads = []
    leads.append(lead)
    with open(LEADS_FILE, "w", encoding="utf-8") as fh:
        json.dump(leads, fh, ensure_ascii=False, indent=2)


def notify_manager(lead):
    text = (
        "<b>НОВАЯ ЗАЯВКА С САЙТА</b>\n"
        "Источник: {source}\n"
        "Клиент: {name}\n"
        "Телефон: {phone}\n"
        "Комментарий: {comment}\n"
        "Время: {ts}"
    ).format(**lead)
    send(MANAGER_CHAT_ID, text)


def greet(chat_id, first_name, payload):
    label = source_label(payload)
    extra = ""
    if payload and payload.startswith("quiz_"):
        extra = ("\nВижу ваш сертификат <b>{}</b> - скидка 2 000 ₽ закреплена "
                 "за вами, применю её к любому расчёту.").format(payload[5:])
    text = (
        "Здравствуйте, {name}! Я бот ROOF LOVE - свидания на крыше "
        "в прозрачном куполе на высоте 25 этажа.\n\n"
        "Вы пришли сюда: {label}.{extra}\n\n"
        "Нажмите кнопку ниже, чтобы отправить контакт - координатор перезвонит "
        "в течение 10 минут, закрепим дату и цену. "
        "Или просто напишите вопрос текстом - отвечу я и менеджер."
    ).format(name=first_name or "друг", label=label, extra=extra)
    send(chat_id, text, reply_markup=contact_keyboard())


def handle_message(msg):
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    user = msg.get("from", {}) or {}
    first_name = user.get("first_name", "")
    text = (msg.get("text") or "").strip()

    if "contact" in msg:
        phone = msg["contact"].get("phone_number", "-")
        st = USER_STATE.get(chat_id, {})
        lead = {
            "source": source_label(st.get("source")),
            "name": st.get("name") or msg["contact"].get("first_name", "") or first_name,
            "phone": phone,
            "comment": "контакт получен кнопкой в боте",
            "ts": datetime.now().strftime("%d.%m.%Y %H:%M"),
        }
        save_lead(lead)
        notify_manager(lead)
        send(chat_id,
             "Спасибо! Контакт получен. Координатор свяжется с вами в течение 10 минут "
             "(с 9:00 до 23:00). А пока могу прислать свободные даты - просто напишите даты.",
             reply_markup=hide_keyboard())
        return

    if text.startswith("/start"):
        payload = text.split(" ", 1)[1].strip() if " " in text else ""
        USER_STATE[chat_id] = {"source": payload, "name": first_name,
                               "ts": datetime.now().isoformat()}
        greet(chat_id, first_name, payload)
        if payload:
            lead = {
                "source": source_label(payload),
                "name": first_name or "не указано",
                "phone": "ожидает кнопку контакта",
                "comment": "клиент зашёл с сайта в бота",
                "ts": datetime.now().strftime("%d.%m.%Y %H:%M"),
            }
            save_lead(lead)
            notify_manager(lead)
        return

    if text in ("/help", "/info"):
        send(chat_id,
             "Я бот ROOF LOVE.\n"
             "• даты - пришлю ближайшие свободные слоты;\n"
             "• цена - расскажу про тарифы (Light 8 900 ₽ / Premium 15 900 ₽ / VIP 28 900 ₽);\n"
             "• кнопка Отправить контакт - оставит заявку координатору.",
             reply_markup=contact_keyboard())
        return

    low = text.lower()
    if "дат" in low:
        reply = ("Ближайшие свободные слоты: сегодня 19:30 (закат) и завтра 21:00 (ночь в огнях). "
                 "Хотите закрепить один из них? Нажмите кнопку контакта - и координатор забронирует.")
    elif "цен" in low or "стоим" in low or "тариф" in low:
        reply = ("Тарифы: Light - 8 900 ₽, Premium - 15 900 ₽ (хит), VIP / Marry Me - 28 900 ₽. "
                 "На сайте есть калькулятор: формат + длительность + опции, цена считается мгновенно. "
                 "Плюс у гостей квиза - сертификат -2 000 ₽.")
    else:
        reply = ("Принял! Передал ваш вопрос координатору - ответим здесь же в течение 5-10 минут. "
                 "Если срочно - нажмите кнопку Отправить контакт, и мы перезвоним.")
    send(chat_id, reply, reply_markup=contact_keyboard())

    st = USER_STATE.get(chat_id, {})
    lead = {
        "source": source_label(st.get("source")),
        "name": first_name or "не указано",
        "phone": "ожидает кнопку контакта",
        "comment": "сообщение клиента: " + text[:300],
        "ts": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    save_lead(lead)
    notify_manager(lead)


def main():
    me = api("getMe")
    if not me.get("ok"):
        raise SystemExit("Неверный токен или нет сети: getMe не ответил.")
    log.info("Bot started: @%s", me["result"].get("username"))
    send(MANAGER_CHAT_ID, "Бот ROOF LOVE запущен и принимает заявки с сайта.")

    offset = 0
    while True:
        data = api("getUpdates", offset=offset, timeout=POLL_TIMEOUT,
                   allowed_updates=json.dumps(["message"]))
        updates = data.get("result") or []
        for upd in updates:
            offset = max(offset, upd.get("update_id", 0) + 1)
            msg = upd.get("message")
            if not msg:
                continue
            try:
                handle_message(msg)
            except Exception:
                log.exception("Error handling update %s", upd.get("update_id"))
        if not updates:
            time.sleep(1)


if __name__ == "__main__":
    main()
