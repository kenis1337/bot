import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery

PRICE = 100  # Стоимость в Telegram Stars
BOT_TOKEN = "8860571736:AAHVhPyhpaxI68eBuV1lTQAgl0r9SjiM4fw"
CHANNEL_ID = -100443430263

# Множество для хранения ID уже обработанных событий (защита от дублей Telegram)
processed_updates = set()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик /start
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    # Проверка на дубликат сообщения
    if message.message_id in processed_updates:
        return
    processed_updates.add(message.message_id)

    builder = InlineKeyboardBuilder()
    builder.button(
        text="💳 Оплатить и получить доступ",
        callback_data="buy_access"
    )
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Для получения доступа к приватному каналу нажми кнопку ниже:",
        reply_markup=builder.as_markup()
    )

# Обработчик нажатия на кнопку "Оплатить"
@dp.callback_query(F.data == "buy_access")
async def process_buy(callback: types.CallbackQuery):
    # МГНОВЕННО отвечаем Telegram, чтобы он не шёл на повторный запрос
    await callback.answer()

    # Проверка на дубликат клика
    if callback.id in processed_updates:
        return
    processed_updates.add(callback.id)

    prices = [LabeledPrice(label="Доступ в приватный канал", amount=PRICE)]
    
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title="Доступ в закрытый канал",
            description="Покупка персональной одноразовой ссылки-приглашения.",
            payload="channel_access_payment",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="create_invoice"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке инвойса: {e}")
        await callback.message.answer("❌ Не удалось сформировать счёт на оплату.")

# Подтверждение готовности принять платеж
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Выдача одноразовой ссылки после успешной оплаты
@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    if message.message_id in processed_updates:
        return
    processed_updates.add(message.message_id)

    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            name=f"Link for {message.from_user.id}"
        )
        
        await message.answer(
            f"✅ **Доступ оплачен!**\n\n"
            f"Твоя персональная одноразовая ссылка:\n"
            f"{invite_link.invite_link}\n\n"
            f"⚠️ *Ссылка сработает только для одного перехода, не передавай её никому.*",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка при создании ссылки после оплаты: {e}")
        await message.answer(
            "❌ Оплата прошла, но произошла ошибка при генерации ссылки. Обратитесь к администратору."
        )

async def main():
    # Очищаем старые застрявшие апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())