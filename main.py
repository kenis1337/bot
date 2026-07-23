import http.server
import asyncio
import logging
import os
import socketserver
import threading
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import sys
# ==================== НАСТРОЙКИ (ИЗМЕНЯЙТЕ ПОД СВОИ ЗАДАЧИ) ====================
BOT_TOKEN = "8860571736:AAHVhPyhpaxI68eBuV1LTQAgI0r9Sjim4fw"
CHANNEL_ID = -100443430263  # ID приватного канала для выдачи доступа

# Чат или канал для отправки логов продаж (чтобы партнер видел каждую покупку)
# Сюда бот будет автоматически отправлять уведомление с юзернеймом и суммой
LOG_CHAT_ID = -100443430263  
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = "https://твой-домен.com" + WEBHOOK_PATH


dp = Dispatcher()

# Настройки оплаты:
# Для Telegram Stars: PROVIDER_TOKEN = "", CURRENCY = "XTR", PRICE = 100
# Для долларов (USD): PROVIDER_TOKEN = "ВАШ_ТОКЕН_ИЗ_BOTFATHER", CURRENCY = "USD", PRICE = 500 (5.00 USD)

async def on_startup(Bot: Bot) -> None:
    # При запуске сервера автоматически регистрируем вебхук в Telegram
    await Bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

async def handle_index(request):
    # Главная страница твоего сайта или заглушка для Cron Job
    return web.Response(text="SubManager Web & Bot Server is Active!", content_type="text/html")

def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Создаем единое веб-приложение
    app = web.Application()

    # Добавляем маршрут для сайта/пингов (сюда будет стучаться Cron Job каждые 5 минут)
    app.router.add_get("/", handle_index)

    # Регистрируем обработчик входящих запросов от Telegram
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        Bot=Bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # Привязываем жизненный цикл бота к веб-серверу
    dp.startup.register(on_startup)
    setup_application(app, dp, Bot=Bot)

    # Запускаем сервер (порт обычно выдается хостингом автоматически, локально по умолчанию 8080)
    web.run_app(app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()

PROVIDER_TOKEN = ""
CURRENCY = "XTR"
PRICE = 100
LABEL_TEXT = "Доступ в приватный канал"
# ===========================================================================

PORT = int(os.environ.get("PORT", 10000))

class SimpleHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_web_server():
    with socketserver.TCPServer(("", PORT), SimpleHandler) as httpd:
        httpd.serve_forever()

# Запуск легковесного веб-сервера в фоночном потоке для Render
threading.Thread(target=run_web_server, daemon=True).start()

logging.basicConfig(level=logging.INFO)
Bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Защита от дубликатов с ограничением памяти
processed_updates = set()

def check_and_add(identifier):
    if len(processed_updates) > 10000:
        processed_updates.clear()
    if identifier in processed_updates:
        return False
    processed_updates.add(identifier)
    return True

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    if not check_and_add((message.chat.id, message.message_id)):
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="💳 Оплатить и получить доступ",
        callback_data="buy_access"
    )
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Для получения доступа к приватному каналу нажми кнопку ниже:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "buy_access")
async def process_buy(callback: types.CallbackQuery):
    await callback.answer()
    
    if not check_and_add(callback.id):
        return

    prices = [LabeledPrice(label=LABEL_TEXT, amount=PRICE)]
    try:
        await Bot.send_invoice(
            chat_id=callback.from_user.id,
            title="Доступ в закрытый канал",
            description="Покупка персональной одноразовой ссылки-приглашения.",
            payload="channel_access_payment",
            provider_token=PROVIDER_TOKEN,
            currency=CURRENCY,
            prices=prices,
            start_parameter="create_invoice"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке инвойса: {e}")
        await callback.message.answer("❌ Не удалось сформировать счёт на оплату.")

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await Bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    if not check_and_add((message.chat.id, message.message_id)):
        return
    
    try:
        # Создание одноразовой ссылки на впуск в канал
        invite_link = await Bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            name=f"Link for {message.from_user.id}"
        )
        
        # Отправка ссылки покупателю в личные сообщения
        await message.answer(
            f"✅ **Доступ оплачен!**\n\n"
            f"Твоя персональная одноразовая ссылка:\n"
            f"{invite_link.invite_link}\n\n"
            f"⚠️ *Ссылка сработает только для одного перехода, не передавай её никому.*",
            parse_mode="Markdown"
        )

        # Автоматическая отправка лога о продаже в партнерский/логирующий чат
        username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
        log_text = (
            f"💰 **Новая успешная покупка!**\n"
            f"👤 Покупатель: {username} (Имя: {message.from_user.first_name})\n"
            f"💵 Сумма: {PRICE} {CURRENCY}"
        )
        await bot.send_message(chat_id=LOG_CHAT_ID, text=log_text, parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Ошибка при обработке успешной оплаты: {e}")
        await message.answer("❌ Оплата прошла, но произошла ошибка при генерации ссылки. Обратитесь к администратору.")

async def main():
    await Bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(Bot)

if __name__ == "__main__":
    asyncio.run(main())
