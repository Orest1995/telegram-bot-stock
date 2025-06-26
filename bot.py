import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
import schedule
import time
import threading

# --- Конфіг ---
TOKEN = "7511733078:AAEJtVmqp_4WttaaZPUB4uqbP8u3KTYGE1E"
SHEET_NAME = "Склад"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1d4kA7Gh22BcvffhQjx53XvquKUljIjd_kyZ0yySOxvQ/edit?usp=sharing"

# --- Google Sheets API ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
import os
import json
from oauth2client.service_account import ServiceAccountCredentials

# отримати JSON із змінної середовища
creds_json = os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"].replace('\\n', '\n')

# тимчасово записати у файл
with open("creds.json", "w") as f:
    f.write(creds_json)

# використовуємо тимчасовий файл
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)

client = gspread.authorize(creds)
sheet = client.open_by_url(SPREADSHEET_URL).worksheet(SHEET_NAME)

# --- Логування ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Функція читання залишків ---
def get_stocks():
    data = sheet.get_all_values()
    headers = data[0][2:]
    last_row = data[-1][2:]
    return dict(zip(headers, last_row))

def get_all_stocks_text():
    stocks = get_stocks()
    msg = "Загальні залишки:\n"
    warnings = []
    for name, qty in stocks.items():
        try:
            qty_float = float(qty.replace(",", "."))
            msg += f"{name}: {qty_float} тонн\n"
            if qty_float < 1:
                warnings.append(f"⚠️ Увага! {name} менше ніж 1 тонна ({qty_float} т)")
        except:
            msg += f"{name}: Невідомо\n"
    return msg.strip(), warnings

def get_single_stock(name):
    stocks = get_stocks()
    if name not in stocks:
        return "Немає такого товару."
    try:
        qty = float(stocks[name].replace(",", "."))
        warning = f"\n⚠️ Увага! Менше 1 тонни!" if qty < 1 else ""
        return f"{name}: {qty} тонн{warning}"
    except:
        return f"{name}: Невідомо"

# --- Обробник повідомлень ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    chat_id = update.effective_chat.id

    if "chat_ids" not in context.bot_data:
        context.bot_data["chat_ids"] = set()
    context.bot_data["chat_ids"].add(chat_id)

    if text == "залишки: все":
        msg, warnings = get_all_stocks_text()
        await context.bot.send_message(chat_id=chat_id, text=msg)
        for w in warnings:
            await context.bot.send_message(chat_id=chat_id, text=w)

    elif text.startswith("залишок: "):
        name = update.message.text[9:].strip()
        response = get_single_stock(name)
        await context.bot.send_message(chat_id=chat_id, text=response)

# --- Розсилка ---
async def daily_report(context: ContextTypes.DEFAULT_TYPE):
    if "chat_ids" not in context.bot_data:
        return
    msg, warnings = get_all_stocks_text()
    for chat_id in context.bot_data["chat_ids"]:
        try:
            await context.bot.send_message(chat_id=chat_id, text=msg)
            for w in warnings:
                await context.bot.send_message(chat_id=chat_id, text=w)
        except Exception as e:
            logger.warning(f"Не вдалося надіслати в {chat_id}: {e}")

# --- Планувальник ---
def schedule_loop(application):
    schedule.every().day.at("18:00").do(lambda: application.create_task(daily_report(application)))
    while True:
        schedule.run_pending()
        time.sleep(60)

# --- Головна функція ---
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    threading.Thread(target=schedule_loop, args=(application,), daemon=True).start()
    application.run_polling()

if __name__ == "__main__":
    main()
