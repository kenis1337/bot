import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8860571736:AAHVPhypaxi68eBuV1LTQAgI0r9Sjim4fw"
CHANNEL_ID = -100443430263  # ID приватного канала для выдачи доступа
LOG_CHAT_ID = -100443430263  # Чат для логов продаж

# Ссылка на твое приложение на Render (замени на свой реальный домен render.com)
WEBHOOK_HOST = https://submanager-io.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

# Настройки оплаты
PROVIDER_TOKEN = ""  # Пусто для Telegram Stars (XTR)
CURRENCY = "XTR"
PRICE = 100
LABEL_TEXT = "Доступ в приватный канал"

PORT = int(os.environ.get("PORT", 10000))

# ================= ИНИЦИАЛИЗАЦИЯ =================
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
bot = Bot(token=BOT_TOKEN)
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


# ================= ХЕНДЛЕРЫ БОТА =================
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
        "Для получения доступа к прибыльному каналу нажми кнопку ниже:",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "buy_access")
async def process_buy(callback: types.CallbackQuery):
    await callback.answer()

    if not check_and_add(callback.id):
        return

    prices = [LabeledPrice(label=LABEL_TEXT, amount=PRICE)]
    try:
        await bot.send_invoice(
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
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            name=f"Link for {message.from_user.id}"
        )

        await message.answer(
            f"**Доступ оплачен!**\n\n"
            f"Твоя персональная одноразовая ссылка:\n"
            f"{invite_link.invite_link}\n\n"
            f"⚠️ *Ссылка работает только для одного перехода, не передавай её никому.*",
            parse_mode="Markdown"
        )

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


# ================= НАСТРОЙКА ВЕБ-СЕРВЕРА И ВЕБХУКОВ =================
async def on_startup(bot: Bot) -> None:
    # Устанавливаем вебхук при запуске сервера
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

async def handle_index(request):
    # Страница для пингов от Cron Job
    return web.Response(text="Bot is running via Webhooks!", content_type="text/plain")

def main():
    app = web.Application()

    # Главная страница для Cron Job (чтобы бот не засыпал)
    app.router.add_get("/", handle_index)

    # Регистрируем обработчик вебхуков от Telegram
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # Привязываем запуск и остановку к жизненному циклу приложения
    dp.startup.register(on_startup)
    setup_application(app, dp, bot=bot)

    # Запуск полноценного aiohttp сервера на порту Render
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
